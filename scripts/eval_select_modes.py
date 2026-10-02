"""Pending 1b: eval the two free experiments D1 opened up, locally, no GPU.

  1. NEGATED router -- D1 measured the trained scorer as anti-correlated with ink
     (r ~ -0.24), so selecting its LOWEST-scoring tokens retains 0.62-0.66 of a
     page's ink versus 0.50 for random. Does that translate into accuracy?
  2. INK ORACLE -- rank by patch contrast, no learning at all. Bounds what any
     ink-seeking router could achieve on this decoder. If this row also collapses,
     the premise that half these tokens are droppable is wrong and no amount of
     router training fixes it.

Both are meaningless without the two rows that frame them, so all four run together:
a keep_ratio=1.0 CONTROL (must reproduce the known ceiling, or nothing else here is
trustworthy -- same role row 0 played in the run-6 ablation) and a RANDOM baseline
at the same budget (which D1 showed is the *stronger* baseline on these weights).

METRICS ARE EXTRACTED FROM THE NOTEBOOK, NOT REIMPLEMENTED. `compute_word_metrics`,
`compute_ned` and `reading_order_words` are exec'd out of the real cells, so these
rows cannot drift from runs 2-6 through a paraphrase. MAX_WORDS is read from the
notebook too.

CAVEAT recorded in the output: this runs local transformers 5.4.0, Kaggle ran 4.x.
The CONTROL row is what tells us whether that matters -- compare rows to each other
and to the control, not to Kaggle's absolute numbers.

Usage:
    PYTHONPATH=. HF_HUB_OFFLINE=1 python scripts/eval_select_modes.py [--n 50]
"""
import argparse
import ast
import json
import os
import re
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")
CKPT_DEFAULT = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
# Deliberately NOT `ablation_selection.json`: Phase 2d's notebook cell writes that
# name to /kaggle/working/, and downloading it would silently overwrite these local
# rows -- which are on a different transformers version and not comparable anyway.
OUT = os.path.join(ROOT, "results", "ablation_selection_local.json")

# Run 6's measured ceiling (Kaggle, transformers 4.x, rp=1.0 + nrns=3, keep_ratio=1.0)
RUN6_REFERENCE = (77.74, 64.70, 53.05)   # recall / charAcc / order
MAX_LEN = 512
TASK_PROMPT = "<s_doc>"
GH, GW = 80, 60           # Swin-B token grid at 2560x1920, stride 32
ROW_INK_FRAC = 0.10      # a grid row counts as "text" if its ink >= 10% of the busiest

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=50, help="FUNSD test images (50 = full protocol)")
p.add_argument("--keep", type=float, default=0.5, help="keep_ratio for the pruning rows")
p.add_argument("--ckpt", type=str, default=CKPT_DEFAULT)
p.add_argument("--seed", type=int, default=0, help="seeds the random-pruning control")
args = p.parse_args()


# ----------------------------------------------------------- notebook metric import
def load_notebook_metrics():
    """exec the REAL metric defs out of the notebook so they cannot drift."""
    nb = json.loads(open(NOTEBOOK, encoding="utf-8").read())
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    ns = {}
    wanted = {"reading_order_words", "compute_word_metrics", "compute_ned"}
    found = set()
    for src in cells:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue                       # cell 1 is `!pip install`, never valid Python
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add(node.name)
            # MAX_WORDS caps the gold word list; a different value silently rescales
            # recall, so take the notebook's rather than restating 128.
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MAX_WORDS" for t in node.targets
            ):
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add("MAX_WORDS")
    missing = (wanted | {"MAX_WORDS"}) - found
    if missing:
        raise RuntimeError(f"could not extract {sorted(missing)} from the notebook")
    return ns


NB = load_notebook_metrics()
reading_order_words = NB["reading_order_words"]
compute_word_metrics = NB["compute_word_metrics"]
compute_ned = NB["compute_ned"]
MAX_WORDS = NB["MAX_WORDS"]
print(f"metrics loaded from notebook (MAX_WORDS={MAX_WORDS})")

try:
    import editdistance  # noqa: F401
    print("editdistance present -- metrics use the exact path, not the crude fallback")
except ImportError:
    print("WARNING: editdistance MISSING. compute_word_metrics/compute_ned silently "
          "fall back to a length-difference approximation and these numbers will NOT "
          "be comparable to runs 2-6. Install it before trusting this table.")

# ------------------------------------------------------------------------- model
from datasets import load_dataset  # noqa: E402
from transformers import DonutProcessor  # noqa: E402

from src.model import AdaptiveDonutOCR  # noqa: E402

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"device: {device}  |  transformers: ", end="")
import transformers  # noqa: E402
print(transformers.__version__)

processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
sd = torch.load(args.ckpt, map_location=device, weights_only=True)
missing, unexpected = model.load_state_dict(sd, strict=False)
print(f"checkpoint: {args.ckpt}  (missing={len(missing)}, unexpected={len(unexpected)})")
if missing or unexpected:
    raise SystemExit(f"refusing to eval a partially-loaded model: {missing[:5]} {unexpected[:5]}")
model.eval()

ds = load_dataset("nielsr/funsd", split="test")
n = min(args.n, len(ds))
prompt_ids = processor.tokenizer(
    TASK_PROMPT, add_special_tokens=False, return_tensors="pt"
).input_ids.to(device)

# Preprocess once: identical across configs, and it keeps the per-config timing
# about generation rather than about JPEG decoding.
print(f"preprocessing {n} images...")
SAMPLES = []
for i in range(n):
    s = ds[i]
    pv = processor(s["image"].convert("RGB"), return_tensors="pt").pixel_values.to(device)
    words = s.get("words", [])
    boxes = s.get("bboxes") or s.get("boxes")
    gt_words = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
    SAMPLES.append((pv, gt_words, json.dumps({"text": " ".join(gt_words)})))

CONFIGS = [
    ("keep=1.00 router (CONTROL)", 1.0, "router"),
    (f"keep={args.keep:.2f} router", args.keep, "router"),
    (f"keep={args.keep:.2f} NEGATED", args.keep, "negated"),
    (f"keep={args.keep:.2f} random", args.keep, "random"),
    (f"keep={args.keep:.2f} ink ORACLE", args.keep, "ink"),
]


def line_coverage(pv, topk_indices):
    """Per-text-row retained-ink fractions for one image -> 1-D array.

    D2 found that summed retained ink ranks `negated` above `random` while accuracy
    does the opposite, and that the WORST-covered text line is what tracks recall.
    That was measured on 4 cached images against 4 aggregate accuracy rows, which is
    thin. Recording it per image here turns it into a real per-image correlation
    (n x 4 points) that either holds up or does not.
    """
    from src.model import patch_ink
    N = GH * GW
    if pv.shape[-2] // 32 != GH or pv.shape[-1] // 32 != GW:
        return None                        # non-standard grid; accuracy rows still fine
    ink = patch_ink(pv, N)[0].reshape(GH, GW).cpu().numpy().astype(np.float64)
    keep = np.zeros(N, dtype=bool)
    keep[topk_indices[0].cpu().numpy()] = True
    keep2d = keep.reshape(GH, GW)
    row_ink = ink.sum(axis=1)
    is_text = row_ink >= ROW_INK_FRAC * row_ink.max()
    if not is_text.any():
        return None
    return (ink * keep2d).sum(axis=1)[is_text] / np.maximum(row_ink[is_text], 1e-9)


def run_eval(label, keep_ratio, select_mode):
    # Reseed per config so the random control draws the same sequence on every run
    # while still getting a FRESH mask per image -- one fixed mask reused across
    # images is a positional prior, which D1 showed is a different (easier) thing.
    torch.manual_seed(args.seed)
    recs, ords_, neds_, inks, lats = [], [], [], [], []
    pred_words, gold_words, gen_tokens = [], [], []
    json_ok, hit_cap = 0, 0
    kept_tokens = None
    per_image = []

    for idx, (pv, gt_words, gt_str) in enumerate(SAMPLES):
        t0 = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,
                merge_ratio=0.0, max_length=MAX_LEN, select_mode=select_mode
            )
        lats.append((time.perf_counter() - t0) * 1000.0)
        kept_tokens = meta["compressed_tokens"]
        if meta["retained_ink"] is not None:
            inks.append(meta["retained_ink"])

        cov = line_coverage(pv, meta["topk_indices"])

        n_tok = int(gen_ids.shape[-1])
        gen_tokens.append(n_tok)
        if n_tok >= MAX_LEN:
            hit_cap += 1

        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()

        try:                              # diagnostic only -- pred is never repaired
            json.loads(pred)
            json_ok += 1
        except Exception:
            pass

        r, o = compute_word_metrics(pred, gt_words)
        recs.append(r)
        ords_.append(o)
        neds_.append(compute_ned(pred, gt_str))
        pred_words.append(len(re.findall(r"\w+", pred.lower())))
        gold_words.append(len(re.findall(r"\w+", " ".join(gt_words).lower())))
        per_image.append({
            "i": idx,
            "recall": float(r),
            "ned": float(neds_[-1]),
            "retained_ink": meta["retained_ink"],
            "gen_tokens": n_tok,
            "min_line_cov": None if cov is None else float(cov.min()),
            "p10_line_cov": None if cov is None else float(np.percentile(cov, 10)),
            "mean_line_cov": None if cov is None else float(cov.mean()),
            "n_text_rows": None if cov is None else int(cov.size),
        })
        print(f"    {label}: {idx + 1}/{len(SAMPLES)}", end="\r", flush=True)

    cnt = max(len(recs), 1)
    mp, mg = float(np.mean(pred_words)), float(np.mean(gold_words))
    covs = [p["min_line_cov"] for p in per_image if p["min_line_cov"] is not None]
    return {
        "config": label,
        "keep_ratio": keep_ratio,
        "select_mode": select_mode,
        "visual_tokens": kept_tokens,
        "retained_ink": float(np.mean(inks)) if inks else None,
        "mean_min_line_cov": float(np.mean(covs)) if covs else None,
        "word_recall_pct": float(np.mean(recs) * 100.0),
        "character_accuracy_pct": float((1.0 - np.mean(neds_)) * 100.0),
        "word_order_pct": float(np.mean(ords_) * 100.0),
        "mean_ned": float(np.mean(neds_)),
        "mean_pred_words": mp,
        "mean_gold_words": mg,
        "len_ratio_pct": 100.0 * mp / max(mg, 1e-9),
        "mean_gen_tokens": float(np.mean(gen_tokens)),
        "hit_max_length_pct": 100.0 * hit_cap / cnt,
        "valid_json_pct": 100.0 * json_ok / cnt,
        "avg_latency_ms": float(np.mean(lats)),
        "num_eval_samples": len(recs),
        "per_image": per_image,
    }


rows = []
t_start = time.perf_counter()
for _label, _kr, _mode in CONFIGS:
    print(f"--- {_label}")
    rows.append(run_eval(_label, _kr, _mode))
    r = rows[-1]
    print(f"    -> recall {r['word_recall_pct']:.2f}  charAcc {r['character_accuracy_pct']:.2f}"
          f"  ink {r['retained_ink']:.3f}  {r['avg_latency_ms']:.0f} ms/img")
print(f"total {(time.perf_counter() - t_start) / 60:.1f} min")

hdr = (f"{'config':28s} {'tok':>5s} {'ink':>5s} {'minCov':>6s} {'recall':>7s} {'charAcc':>8s} "
       f"{'order':>7s} {'NED':>6s} {'len%':>6s} {'cap%':>5s} {'json%':>6s} {'ms':>7s}")
print("\n" + "=" * len(hdr))
print(hdr)
print("-" * len(hdr))
for r in rows:
    ink = f"{r['retained_ink']:.3f}" if r["retained_ink"] is not None else "  -  "
    mc = f"{r['mean_min_line_cov']:.3f}" if r["mean_min_line_cov"] is not None else "  -  "
    print(f"{r['config']:28s} {r['visual_tokens']:5d} {ink:>5s} {mc:>6s} "
          f"{r['word_recall_pct']:7.2f} {r['character_accuracy_pct']:8.2f} "
          f"{r['word_order_pct']:7.2f} {r['mean_ned']:6.3f} {r['len_ratio_pct']:6.1f} "
          f"{r['hit_max_length_pct']:5.0f} {r['valid_json_pct']:6.1f} {r['avg_latency_ms']:7.0f}")
print("=" * len(hdr))

# ----------------------------------------------------------------------- CONTROL
ctrl = rows[0]
got = (ctrl["word_recall_pct"], ctrl["character_accuracy_pct"], ctrl["word_order_pct"])
drift = max(abs(g - e) for g, e in zip(got, RUN6_REFERENCE))
print(f"\nCONTROL vs run 6 {RUN6_REFERENCE} (Kaggle, transformers 4.x)")
print(f"  got ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts")
if drift < 0.5:
    print("  OK -- local harness reproduces Kaggle; absolute numbers are comparable.")
else:
    print(f"  DRIFT: local transformers {transformers.__version__} vs Kaggle 4.x, or a")
    print("  harness difference. Rows below are still comparable TO EACH OTHER and to")
    print("  this control, but do not quote them against Kaggle's absolute numbers.")

# ------------------------------------------------------------------- the questions
by_mode = {r["select_mode"]: r for r in rows[1:]}
rt, ng, rd, ik = (by_mode[m] for m in ("router", "negated", "random", "ink"))


def verdict(title, lines):
    print(f"\n{title}")
    for line in lines:
        print(f"  {line}")


verdict("Q1. Does negating the router help?", [
    f"router  {rt['word_recall_pct']:6.2f} recall  (ink {rt['retained_ink']:.3f})",
    f"NEGATED {ng['word_recall_pct']:6.2f} recall  (ink {ng['retained_ink']:.3f})   "
    f"{ng['word_recall_pct'] - rt['word_recall_pct']:+.2f} vs router",
    f"random  {rd['word_recall_pct']:6.2f} recall  (ink {rd['retained_ink']:.3f})   "
    f"{ng['word_recall_pct'] - rd['word_recall_pct']:+.2f} negated vs random",
    ("=> NEGATION IS A REAL FIX: it beats both the forward router and random. "
     "Flip the sign and the existing checkpoint becomes usable."
     if ng["word_recall_pct"] > max(rt["word_recall_pct"], rd["word_recall_pct"])
     else "=> negation does not beat random: retaining ink is necessary but not "
          "sufficient, so training with pruning is still the fix."),
])

verdict("Q2. Is the premise sound -- are half these tokens droppable at all?", [
    f"keep=1.00 CONTROL   {ctrl['word_recall_pct']:6.2f} recall  ({ctrl['visual_tokens']} tokens)",
    f"ink ORACLE          {ik['word_recall_pct']:6.2f} recall  ({ik['visual_tokens']} tokens, "
    f"ink {ik['retained_ink']:.3f})   {ik['word_recall_pct'] - ctrl['word_recall_pct']:+.2f} vs control",
    ("=> PREMISE HOLDS: an ink-ranked half of the tokens nearly matches the full "
     "page, so the headroom a trained router could reach is real."
     if ik["word_recall_pct"] > ctrl["word_recall_pct"] - 5.0
     else "=> PREMISE IS WEAK: even a perfect ink ranking loses accuracy at this "
          "budget. The decoder needs the tokens, so cap expectations for ANY router "
          "-- and consider merge_ratio (which compresses rather than discards) "
          "before more pruning work."),
    f"ceiling for a learned router at keep={args.keep:.2f}: "
    f"~{ik['word_recall_pct']:.2f} recall (the oracle), floor "
    f"~{rd['word_recall_pct']:.2f} (random). Router is at {rt['word_recall_pct']:.2f}.",
])

os.makedirs(os.path.dirname(OUT), exist_ok=True)

# ------------------------------------------------- Q3: which statistic predicts recall?
# D2 claimed the discriminating quantity is WORST-CASE line coverage rather than summed
# retained ink, but measured it on 4 cached images against 4 aggregate accuracy rows --
# a single statistic ordering 4 rows correctly is 1-in-24 by luck. Here it is a per-image
# test over the four equal-budget modes, so it can actually fail.
def spearman(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


pooled = [(p, r["select_mode"]) for r in rows[1:] for p in r["per_image"]
          if p["min_line_cov"] is not None]
if len(pooled) >= 12:
    rec = [p["recall"] for p, _ in pooled]
    print("\nQ3. Which statistic predicts per-image recall? "
          f"(pooled over the 4 equal-budget modes, n={len(pooled)})")
    print(f"  {'statistic':22s} {'family':12s} {'Spearman vs recall':>19s}")
    print("  " + "-" * 56)
    for key, fam in (("retained_ink", "aggregate"), ("mean_line_cov", "aggregate"),
                     ("p10_line_cov", "worst-case"), ("min_line_cov", "worst-case")):
        print(f"  {key:22s} {fam:12s} {spearman([p[key] for p, _ in pooled], rec):19.3f}")
    rho_ink = spearman([p["retained_ink"] for p, _ in pooled], rec)
    rho_min = spearman([p["min_line_cov"] for p, _ in pooled], rec)
    if rho_min > rho_ink + 0.05:
        print("  => D2 CONFIRMED per-image: worst-case coverage predicts recall better than")
        print("     summed ink. Do not build a router objective on total retained saliency.")
    elif rho_ink > rho_min + 0.05:
        print("  => D2 FALSIFIED per-image: summed ink is the better predictor after all.")
        print("     D2's 4-row ordering was luck; revise it and re-check Pending 1a/1d.")
    else:
        print("  => INCONCLUSIVE: the two statistics predict about equally well, so this")
        print("     eval does not separate them. D2's claim stands unconfirmed, not refuted.")
    # Within-mode is the harder test: it removes the between-mode contrast that could
    # carry the pooled correlation on its own.
    print("\n  within-mode (controls for the mode, so only image-to-image variation):")
    for mode in ("router", "negated", "random", "ink"):
        sub = [p for p, m in pooled if m == mode]
        if len(sub) >= 5:
            print(f"    {mode:9s} ink {spearman([p['retained_ink'] for p in sub], [p['recall'] for p in sub]):6.3f}"
                  f"   min-cov {spearman([p['min_line_cov'] for p in sub], [p['recall'] for p in sub]):6.3f}"
                  f"   (n={len(sub)})")
else:
    print("\nQ3 skipped: too few per-image coverage records to correlate.")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "meta": {
            "checkpoint": args.ckpt,
            "num_eval_samples": n,
            "keep_ratio": args.keep,
            "transformers": transformers.__version__,
            "device": str(device),
            "max_words": MAX_WORDS,
            "run6_reference": RUN6_REFERENCE,
            "control_drift_pts": drift,
            "seed": args.seed,
        },
        "rows": rows,
    }, f, indent=2)
print(f"\nWrote {OUT}")
