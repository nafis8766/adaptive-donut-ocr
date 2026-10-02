#!/usr/bin/env python
"""Does the 13(b) attention target beat the ink target where the budget actually BINDS?

Run 10 came out null at keep=0.50 (recall 79.63 -> 79.41). But keep=0.50 is **not a
binding budget** on either checkpoint: keep=1.00 scores 77.3 while keep=0.50 scores
79.4-79.6, i.e. discarding half the visual tokens BEATS keeping all of them. At a
budget that is not binding, the discarded tokens carried nothing the decoder needed,
so *no* selection objective can raise recall there and run 10's null says nothing
about whether attention is a better target than ink. See AGENTS.md "Run 10 -- result".

This re-asks the question at keep=0.25 and keep=0.20, on the two checkpoints that
already exist -- eval only, no training, no GPU.

Three things make this more than a re-run of the sweep:

1.  **It is PAIRED.** Both checkpoints see the same images in the same order, and
    `random` mode is reseeded per config so the two checkpoints get identical random
    masks. That lets us report the per-image delta's standard error, which is what
    AGENTS.md's "+-1 pt is not a result" floor was standing in for. A paired test is
    far more sensitive than comparing two independent 50-image means.

2.  **The controls can actually fail.** Three of them. (a) `random`-mode retained ink
    must be *identical* across the two checkpoints -- it depends only on the masks, so
    if it differs the reseeding is not working and "paired" is a lie. (b) Router-mode
    retained ink at keep=0.50/0.35 must match the Kaggle rows, which is a sharp test of
    checkpoint identity because ink is near-deterministic given the weights (a swapped
    or half-loaded checkpoint moves it by 0.25+, sampling moves it by <0.08). (c) The
    recall delta is compared to Kaggle's too, but only *reported*: Kaggle's own delta
    has an unknown SE, so agreement within a couple of points mostly means "both are
    consistent with zero" and cannot fail for the right reason.

3.  **A flat result is not automatically a null.** The script prints T_SIGNIF x SE --
    the smallest delta it could call significant -- and where that exceeds
    MIN_EFFECT_PTS it reports UNDERPOWERED instead of "no effect". Local numbers are on
    a different device and transformers version than Kaggle, so the absolute level is
    NOT expected to match; the delta between the two checkpoints is the comparable
    quantity.

4.  **Every threshold below is pre-registered**, written before any output was read,
    the same discipline as D8/D9/D10.

    PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
        python -u scripts/eval_budget_binding.py [--n 50]

Cost: ~13 s/image/config on CPU. 2 checkpoints x 9 configs x n images.
n=50 is ~3.2 h; use --n 12 for a smoke run.
"""
import argparse
import ast
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The notebook that actually produced runs 9 and 10 -- NOT the older
# kaggle_token_pruning_ocr.ipynb that eval_select_modes.py reads. (Verified
# 2026-09-03: all four metric defs are byte-identical between the two, so this is a
# provenance fix rather than a behaviour change. Re-check if either notebook moves.)
NOTEBOOK = os.path.join(ROOT, "kaggle_pruning_run.ipynb")

# Deliberately NOT ablation_selection_local.json: that file holds the historical
# Pending-1b n=4 rows and nothing here should overwrite them.
OUT = os.path.join(ROOT, "results", "budget_binding_local.json")

CKPTS = [
    ("run 9  (ink target)", os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")),
    ("run 10 (attn target)", os.path.join(ROOT, "run 10", "adaptive_donut_pruned.pt")),
]

MAX_LEN = 512
TASK_PROMPT = "<s_doc>"
CONTROL_BUDGETS = (0.50, 0.35)      # already measured on Kaggle -> these are the controls
NEW_BUDGETS = (0.25, 0.20)          # the question
BUDGETS = CONTROL_BUDGETS + NEW_BUDGETS

# ----------------------------------------------------------------- PRE-REGISTERED
# Kaggle run10 - run9 word-recall delta, in points, from each run's
# ablation_selection.json. Reported for consistency, NOT used as a gate: Kaggle's own
# delta has an unknown standard error (n=50, one run), so "agrees within 2 pts" would
# mostly mean "both are consistent with zero" -- a control that cannot fail for the
# right reason. The smoke run at n=2 passed it, which is what exposed this.
KAGGLE_DELTA = {0.50: -0.22, 0.35: +0.49}

# The gate is retained_ink instead, which is what a control should be: nearly
# deterministic given the weights, so it is sharp where recall is noisy. A swapped or
# half-loaded checkpoint moves it by 0.25+; sampling moves it by <0.08.
KAGGLE_INK = {
    "run 9  (ink target)":  {1.00: 1.000, 0.50: 0.922, 0.35: 0.826},
    "run 10 (attn target)": {1.00: 1.000, 0.50: 0.675, 0.35: 0.511},
}
INK_TOL = 0.10           # |local ink - Kaggle ink| at a control budget
BIND_MARGIN = 1.0        # pts; budget binds iff recall(keep) < recall(1.00) - this
SELECT_MARGIN = 2.0      # pts; selection matters iff router - random > this
T_SIGNIF = 2.0           # |mean/SE| at or above this = the paired delta is real
# Smallest run9-vs-run10 gap worth acting on. If T_SIGNIF * SE exceeds it, this test
# cannot see an effect that size and the verdict must be UNDERPOWERED, not "null".
# Without this the script reports a confident null exactly when it is noisiest.
MIN_EFFECT_PTS = 3.0
# --------------------------------------------------------------------------------

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=50, help="FUNSD test images (50 = full protocol)")
p.add_argument("--seed", type=int, default=0, help="seeds the random-pruning control")
args = p.parse_args()

for _lbl, _pth in CKPTS:
    if not os.path.exists(_pth):
        raise SystemExit(f"missing checkpoint for {_lbl}: {_pth}")

try:
    import editdistance  # noqa: F401
except ImportError:
    raise SystemExit(
        "editdistance is MISSING. compute_word_metrics/compute_ned fall back to a "
        "length-difference approximation, which would make every number here "
        "incomparable to the Kaggle rows -- including the controls this script "
        "depends on. Install it before running."
    )


def load_notebook_metrics():
    """exec the REAL metric defs out of the notebook so they cannot drift."""
    nb = json.loads(open(NOTEBOOK, encoding="utf-8").read())
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    ns, found = {}, set()
    wanted = {"reading_order_words", "compute_word_metrics", "compute_ned"}
    for src in cells:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue                       # the pip cell is never valid Python
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add(node.name)
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MAX_WORDS" for t in node.targets
            ):
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add("MAX_WORDS")
    missing = (wanted | {"MAX_WORDS"}) - found
    if missing:
        raise SystemExit(f"could not extract {sorted(missing)} from {NOTEBOOK}")
    return ns


NB = load_notebook_metrics()
reading_order_words = NB["reading_order_words"]
compute_word_metrics = NB["compute_word_metrics"]
compute_ned = NB["compute_ned"]
MAX_WORDS = NB["MAX_WORDS"]

from datasets import load_dataset            # noqa: E402
from transformers import DonutProcessor      # noqa: E402
import transformers                          # noqa: E402

from src.model import AdaptiveDonutOCR       # noqa: E402

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("=" * 78)
print("BUDGET-BINDING SWEEP -- is 13(b) better where the budget actually bites?")
print("=" * 78)
print(f"  device {device} | transformers {transformers.__version__} | "
      f"MAX_WORDS={MAX_WORDS} MAX_LEN={MAX_LEN}")
print(f"  budgets: controls {CONTROL_BUDGETS} + new {NEW_BUDGETS}, paired, seed {args.seed}")

processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
model.eval()

ds = load_dataset("nielsr/funsd", split="test")
n = min(args.n, len(ds))
prompt_ids = processor.tokenizer(
    TASK_PROMPT, add_special_tokens=False, return_tensors="pt"
).input_ids.to(device)

# Keep the PIL images, not the pixel tensors: 1x3x2560x1920 fp32 is 56 MB, so caching
# 50 of them would cost ~2.8 GB alongside the model. Re-preprocessing is deterministic
# (resize + normalize, no inference-time augmentation) and costs ~0.2 s/image against
# ~13 s of generation.
GOLD = []
for i in range(n):
    s = ds[i]
    words = s.get("words", [])
    boxes = s.get("bboxes") or s.get("boxes")
    gt = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
    GOLD.append((s["image"].convert("RGB"), gt, json.dumps({"text": " ".join(gt)})))
print(f"  {n} FUNSD test images, gold capped at MAX_WORDS={MAX_WORDS}")


def run_eval(keep_ratio, select_mode):
    """One (budget, mode) row. Returns a dict incl. per-image recall for pairing."""
    # Reseed per config so `random` draws the SAME masks for both checkpoints -- that
    # is what makes the random rows comparable across runs 9 and 10 at all. A fresh
    # mask per image is still drawn; one fixed mask reused across images would be a
    # positional prior, which D1 showed is a different and easier thing.
    torch.manual_seed(args.seed)
    per_recall, per_order, per_ned, inks, lats, gen_toks = [], [], [], [], [], []
    json_ok, hit_cap, kept = 0, 0, None
    for img, gt_words, gt_str in GOLD:
        pv = processor(img, return_tensors="pt").pixel_values.to(device)
        t0 = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,
                merge_ratio=0.0, max_length=MAX_LEN, select_mode=select_mode,
            )
        lats.append((time.perf_counter() - t0) * 1000.0)
        kept = meta["compressed_tokens"]
        if meta.get("retained_ink") is not None:
            inks.append(float(meta["retained_ink"]))
        n_tok = int(gen_ids.shape[-1])
        gen_toks.append(n_tok)
        hit_cap += int(n_tok >= MAX_LEN)
        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()
        try:                                  # diagnostic only -- pred is never repaired
            json.loads(pred)
            json_ok += 1
        except Exception:
            pass
        r, o = compute_word_metrics(pred, gt_words)
        per_recall.append(float(r))
        per_order.append(float(o))
        per_ned.append(float(compute_ned(pred, gt_str)))
    return {
        "keep_ratio": keep_ratio,
        "select_mode": select_mode,
        "visual_tokens": kept,
        "word_recall_pct": float(np.mean(per_recall) * 100.0),
        "word_order_pct": float(np.mean(per_order) * 100.0),
        "mean_ned": float(np.mean(per_ned)),
        "retained_ink": float(np.mean(inks)) if inks else None,
        "mean_gen_tokens": float(np.mean(gen_toks)),
        "hit_max_length_pct": 100.0 * hit_cap / max(n, 1),
        "valid_json_pct": 100.0 * json_ok / max(n, 1),
        "avg_latency_ms": float(np.mean(lats)),
        "num_eval_samples": n,
        "per_image_recall": per_recall,       # kept for the paired statistic
    }


CONFIGS = [(1.00, "router")] + [(k, m) for k in BUDGETS for m in ("router", "random")]

RESULTS = {}
t_start = time.time()
for ci, (label, path) in enumerate(CKPTS):
    sd = torch.load(path, map_location=device, weights_only=True)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing or unexpected:
        raise SystemExit(
            f"refusing to eval a partially-loaded model for {label}: "
            f"missing={len(missing)} unexpected={len(unexpected)} "
            f"{missing[:5]} {unexpected[:5]}"
        )
    model.eval()
    print(f"\n{'-' * 78}\n{label}  <- {os.path.relpath(path, ROOT)}  "
          f"(missing=0, unexpected=0)\n{'-' * 78}")
    RESULTS[label] = {}
    for keep, mode in CONFIGS:
        row = run_eval(keep, mode)
        RESULTS[label][(keep, mode)] = row
        ink = "  -  " if row["retained_ink"] is None else f"{row['retained_ink']:.3f}"
        done = ci * len(CONFIGS) + len(RESULTS[label])
        eta = (time.time() - t_start) / done * (2 * len(CONFIGS) - done) / 60.0
        print(f"  keep={keep:.2f} {mode:7s} recall {row['word_recall_pct']:6.2f}  "
              f"ink {ink}  tok {row['visual_tokens']:4d}  "
              f"{row['avg_latency_ms'] / 1000:5.1f}s/img   ETA {eta:5.1f} min", flush=True)

A, B = CKPTS[0][0], CKPTS[1][0]


def paired(keep, mode):
    """run10 - run9 per-image recall delta, in points, with its standard error."""
    a = np.asarray(RESULTS[A][(keep, mode)]["per_image_recall"]) * 100.0
    b = np.asarray(RESULTS[B][(keep, mode)]["per_image_recall"]) * 100.0
    d = b - a
    se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else float("nan")
    t = float(d.mean() / se) if se and se == se and se > 0 else float("nan")
    return float(d.mean()), se, t


print("\n" + "=" * 78)
print("TABLE -- word recall, paired on the same images")
print("=" * 78)
print(f"{'keep':>5s} {'mode':7s} {'run 9':>7s} {'run 10':>7s} {'delta':>7s} "
      f"{'SE':>5s} {'t':>6s}  {'ink 9':>6s} {'ink 10':>6s}")
for keep, mode in CONFIGS:
    ra, rb = RESULTS[A][(keep, mode)], RESULTS[B][(keep, mode)]
    d, se, t = paired(keep, mode)
    ia = "  -   " if ra["retained_ink"] is None else f"{ra['retained_ink']:.3f} "
    ib = "  -   " if rb["retained_ink"] is None else f"{rb['retained_ink']:.3f} "
    star = " *" if abs(t) >= T_SIGNIF else ""
    print(f"{keep:5.2f} {mode:7s} {ra['word_recall_pct']:7.2f} {rb['word_recall_pct']:7.2f} "
          f"{d:+7.2f} {se:5.2f} {t:+6.2f}{star:2s} {ia:>6s} {ib:>6s}")
print(f"  (* = |t| >= {T_SIGNIF}, pre-registered; delta and t are run 10 minus run 9)")

verdicts = []


def say(ok, title, detail):
    verdicts.append({"check": title, "pass": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {title}: {detail}")


print("\n" + "=" * 78)
print("CONTROLS")
print("=" * 78)
controls_ok = True

# (1) PAIRING. random-mode masks are drawn from a per-config reseeded generator and
# retained_ink does not depend on the weights, so the two checkpoints MUST report the
# same random-mode ink to within float noise. If they do not, the reseed is not taking
# effect, the two checkpoints saw different masks, and every paired delta below is
# comparing different draws. This is the assertion that makes "paired" a fact.
for keep in BUDGETS:
    ia = RESULTS[A][(keep, "random")]["retained_ink"]
    ib = RESULTS[B][(keep, "random")]["retained_ink"]
    if ia is None or ib is None:
        say(False, f"pairing keep={keep:.2f}",
            "random-mode retained_ink is None, so the pairing cannot be verified -- "
            "treating that as a failure rather than assuming the masks matched")
        controls_ok = False
        continue
    gap = abs(ia - ib)
    ok = gap < 1e-6
    controls_ok &= ok
    say(ok, f"pairing keep={keep:.2f}",
        f"random-mode ink {ia:.6f} vs {ib:.6f} -> |gap| {gap:.2e} (must be ~0: same masks)")

# (2) CHECKPOINT IDENTITY. retained_ink at a budget Kaggle already measured. Near
# deterministic given the weights, so unlike the recall delta this fails loudly for the
# right reason -- a swapped, stale or half-loaded checkpoint moves it by 0.25+.
for label in (A, B):
    for keep, kag in sorted(KAGGLE_INK[label].items(), reverse=True):
        got = RESULTS[label][(keep, "router")]["retained_ink"]
        if got is None:
            # keep=1.00 prunes nothing, so the model may not report retained_ink at all.
            # Skip rather than crash, and skip rather than score it as a pass.
            print(f"  [skip] ink {label} keep={keep:.2f}: model reported no retained_ink "
                  f"(nothing pruned at this budget)")
            continue
        gap = abs(got - kag)
        ok = gap <= INK_TOL
        controls_ok &= ok
        say(ok, f"ink {label} keep={keep:.2f}",
            f"local {got:.3f} vs Kaggle {kag:.3f} -> |gap| {gap:.3f} (tol {INK_TOL:.2f})")

# (3) RECALL-DELTA CONSISTENCY -- reported, never gating. See KAGGLE_DELTA's comment.
print("\n  recall-delta consistency with Kaggle (informational, not a gate):")
for keep in CONTROL_BUDGETS:
    d, se, t = paired(keep, "router")
    print(f"    keep={keep:.2f}  local {d:+.2f} +-{se:.2f}  Kaggle {KAGGLE_DELTA[keep]:+.2f}  "
          f"|gap| {abs(d - KAGGLE_DELTA[keep]):.2f}")

# (4) POWER. T_SIGNIF * SE is the smallest delta this test could call significant. If
# that exceeds MIN_EFFECT_PTS the test cannot see an effect worth acting on, so a flat
# result there is UNDERPOWERED, not a null. Printed for every budget because it is the
# number that decides whether "indistinguishable" means anything.
print(f"\n  resolution -- smallest detectable delta at |t|={T_SIGNIF:.0f} "
      f"(want <= {MIN_EFFECT_PTS:.1f} pts):")
POWER = {}
for keep in BUDGETS:
    _, se, _ = paired(keep, "router")
    mde = T_SIGNIF * se
    POWER[keep] = mde
    print(f"    keep={keep:.2f}  SE {se:5.2f}  detectable >= {mde:5.2f} pts  "
          f"{'OK' if mde <= MIN_EFFECT_PTS else 'UNDERPOWERED'}")

print("\n" + "=" * 78)
print("IS THE BUDGET BINDING? -- the question run 10 could not answer at keep=0.50")
print("=" * 78)
for label in (A, B):
    ceil = RESULTS[label][(1.00, "router")]["word_recall_pct"]
    print(f"  {label}: keep=1.00 ceiling {ceil:.2f}")
    for keep in BUDGETS:
        r = RESULTS[label][(keep, "router")]["word_recall_pct"]
        rr = RESULTS[label][(keep, "random")]["word_recall_pct"]
        binds = r < ceil - BIND_MARGIN
        sel = (r - rr) > SELECT_MARGIN
        print(f"    keep={keep:.2f} router {r:6.2f} ({r - ceil:+6.2f} vs ceiling) "
              f"random {rr:6.2f} (router-random {r - rr:+6.2f})  "
              f"{'BINDS' if binds else 'not binding':11s}  "
              f"{'selection matters' if sel else 'selection irrelevant'}")

print("\n" + "=" * 78)
print("THE ANSWER")
print("=" * 78)
if not controls_ok:
    print("  WITHHELD. A control failed, so this harness is not measuring what the "
          "run 9 / run 10 comparison measured (or the pairing did not hold). The "
          "keep=0.25 / 0.20 rows above are printed for the record but must NOT be used "
          "to accept or reject 13(b).")
else:
    any_binding = False
    for keep in NEW_BUDGETS:
        d, se, t = paired(keep, "router")
        mde = POWER[keep]
        ceil_a = RESULTS[A][(1.00, "router")]["word_recall_pct"]
        ceil_b = RESULTS[B][(1.00, "router")]["word_recall_pct"]
        binds = (RESULTS[A][(keep, "router")]["word_recall_pct"] < ceil_a - BIND_MARGIN
                 and RESULTS[B][(keep, "router")]["word_recall_pct"] < ceil_b - BIND_MARGIN)
        any_binding |= binds
        if not binds:
            print(f"  keep={keep:.2f}: NOT BINDING on both checkpoints -- delta {d:+.2f} "
                  f"is uninformative for the same reason keep=0.50 was.")
        elif abs(t) >= T_SIGNIF:
            verdict = "BEATS ink" if d > 0 else "LOSES to ink"
            print(f"  keep={keep:.2f}: budget binds, and the attention target {verdict} "
                  f"by {d:+.2f} pts (SE {se:.2f}, t {t:+.2f}). This is a real result.")
        elif mde > MIN_EFFECT_PTS:
            # The distinction this branch exists for: "we looked and saw nothing" versus
            # "we could not have seen it". Reporting the second as the first is how a
            # noisy eval manufactures a confident null.
            print(f"  keep={keep:.2f}: budget binds, but this test is UNDERPOWERED -- "
                  f"delta {d:+.2f}, SE {se:.2f}, so nothing below {mde:.2f} pts is "
                  f"detectable and a {MIN_EFFECT_PTS:.1f}-pt effect could hide here. "
                  f"NOT a null. Need ~{int(np.ceil(n * (mde / MIN_EFFECT_PTS) ** 2))} "
                  f"images for a {MIN_EFFECT_PTS:.1f}-pt resolution; FUNSD test has "
                  f"{len(ds)}.")
        else:
            print(f"  keep={keep:.2f}: budget binds, resolution is {mde:.2f} pts, and the "
                  f"attention target is INDISTINGUISHABLE from ink: {d:+.2f} pts, "
                  f"SE {se:.2f}, t {t:+.2f}. This IS a null -- the test could have seen "
                  f"a {MIN_EFFECT_PTS:.1f}-pt effect and did not.")
    if not any_binding:
        print("  No tested budget binds on both checkpoints. Push lower than "
              f"{min(NEW_BUDGETS):.2f} before concluding anything about the target.")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "meta": {
            "purpose": "re-ask 13(b) at budgets that bind; paired on the same images",
            "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checkpoints": {lbl: os.path.relpath(pth, ROOT) for lbl, pth in CKPTS},
            "num_eval_samples": n,
            "seed": args.seed,
            "device": str(device),
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "max_len": MAX_LEN,
            "max_words": MAX_WORDS,
            "notebook_metrics_from": os.path.basename(NOTEBOOK),
            "preregistered": {
                "kaggle_delta_informational": {str(k): v for k, v in KAGGLE_DELTA.items()},
                "kaggle_ink_gate": {lbl: {str(k): v for k, v in d.items()}
                                    for lbl, d in KAGGLE_INK.items()},
                "ink_tol": INK_TOL,
                "bind_margin_pts": BIND_MARGIN,
                "select_margin_pts": SELECT_MARGIN,
                "t_signif": T_SIGNIF,
                "min_effect_pts": MIN_EFFECT_PTS,
            },
            "controls_passed": controls_ok,
            "resolution_pts": {str(k): v for k, v in POWER.items()},
            "resolution_note": (
                "T_SIGNIF * SE = smallest paired delta callable significant. Where this "
                "exceeds min_effect_pts a flat result is UNDERPOWERED, not a null."
            ),
            "not_comparable_to_kaggle_in_level": (
                "different device and transformers version; the DELTA between the two "
                "checkpoints is the comparable quantity, which is why the controls exist"
            ),
        },
        "verdicts": verdicts,
        "rows": [
            {"checkpoint": lbl, **{k: v for k, v in row.items()}}
            for lbl in RESULTS for row in RESULTS[lbl].values()
        ],
        "paired": [
            {"keep_ratio": keep, "select_mode": mode,
             "delta_pts": paired(keep, mode)[0], "se_pts": paired(keep, mode)[1],
             "t": paired(keep, mode)[2]}
            for keep, mode in CONFIGS
        ],
    }, f, indent=1)
print(f"\nwrote {os.path.relpath(OUT, ROOT)}   ({(time.time() - t_start) / 60:.1f} min)")
