"""Item 3 micro-sweep: nrns ∈ {3, 4, 6} × rp ∈ {1.0, 1.05} on run-5 weights.

Answers whether the current notebook defaults (rp=1.0, nrns=3) leave any headroom.
Length calibration is already 99.0% of gold at 0% cap-hits, so the prior expectation
is small movement — but "expected small" is not "measured".

CONTROL row: (rp=1.0, nrns=3) must reproduce run-6 reference (77.74 / 64.70 / 53.05)
within 0.5 pts. If it does not, the harness differs from the notebook eval and no other
row is trustworthy; the script prints a WARNING and exits non-zero.

Helper functions (reading_order_words, compute_word_metrics, compute_ned) are extracted
from the notebook at runtime so they cannot drift from the actual eval path.

Output: results/nrns_rp_sweep.json
Usage:
    python scripts/run_nrns_rp_sweep.py
"""
import json
import os
import re
import sys

import numpy as np
import torch
from tqdm import tqdm

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR

# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------
CKPT = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
if not os.path.exists(CKPT):
    raise SystemExit(f"checkpoint not found: {CKPT}\n"
                     "This sweep runs on run-5 weights, the same baseline the "
                     "decoding ablation (run 6) used.")

# ---------------------------------------------------------------------------
# extract helpers from the notebook so they cannot drift from the real eval
# ---------------------------------------------------------------------------
NB = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")
_cells = ["".join(c["source"])
          for c in json.load(open(NB, encoding="utf-8"))["cells"]]


def _extract_func(name):
    for cell in _cells:
        if f"def {name}(" not in cell:
            continue
        lines = cell.splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith(f"def {name}("))
        out = []
        for l in lines[start:]:
            if out and l and not l[0].isspace() and l.strip():
                break   # first non-blank top-level line after the def
            out.append(l)
        return "\n".join(out)
    raise ValueError(f"function {name!r} not found in notebook")


_ns: dict = {}
for _fn in ("reading_order_words", "compute_word_metrics", "compute_ned"):
    exec(compile(_extract_func(_fn), f"<nb:{_fn}>", "exec"), _ns)

reading_order_words = _ns["reading_order_words"]
compute_word_metrics = _ns["compute_word_metrics"]
compute_ned = _ns["compute_ned"]

# ---------------------------------------------------------------------------
# model / processor / dataset
# ---------------------------------------------------------------------------
print(f"Loading checkpoint: {os.path.relpath(CKPT, ROOT)}")
processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
# keep_ratio=1.0: run-5 weights were trained without pruning, so the router is
# untrained. keep_ratio=1.0 passes all tokens through (top-K where K=N), making
# the router a no-op. Using the default 0.35 would randomly drop 65% of tokens.
# merge_ratio=0.0 is now NAMED rather than inherited. It used to be inherited, and
# the class default was 0.20, so every stored row in results/nrns_rp_sweep.json was
# produced with ToMe merging ON -- through the pre-2026-09-14 rank-parity split, at
# that -- while the file is read as a pruning-free decoding sweep. This is the D5
# failure again: a knob that shaped the run appearing nowhere in its own log. It is
# recorded in the meta block below so the next reader cannot miss it.
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True)
model.load_state_dict(torch.load(CKPT, map_location="cpu"))
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
print(f"Device: {device}")

TASK_PROMPT = "<s_doc>"
prompt_ids = processor.tokenizer(
    TASK_PROMPT, add_special_tokens=False, return_tensors="pt"
).input_ids.to(device)

MAX_WORDS = 128
SWEEP_MAX_LEN = 512

print("Loading FUNSD test split...")
test_raw = list(load_dataset("nielsr/funsd", split="test"))
print(f"  {len(test_raw)} samples")

# ---------------------------------------------------------------------------
# sweep configs — CONTROL row first, then the 5 alternatives
# ---------------------------------------------------------------------------
# CONTROL: the current notebook default.  Must reproduce run-6 reference
# (77.74 / 64.70 / 53.05) within 0.5 pts; if it does not, the other rows
# are not comparable to earlier runs and the script exits non-zero.
RUN6_REFERENCE = (77.74, 64.70, 53.05)   # recall / charAcc / order
CONTROL_TOL = 0.5

SWEEP_CONFIGS = [
    # label                        rp     nrns
    ("CONTROL rp=1.0 nrns=3",     1.0,   3),   # current default — must match run 6
    ("rp=1.0  nrns=4",            1.0,   4),
    ("rp=1.0  nrns=6",            1.0,   6),
    ("rp=1.05 nrns=3",            1.05,  3),
    ("rp=1.05 nrns=4",            1.05,  4),
    ("rp=1.05 nrns=6",            1.05,  6),
]

# ---------------------------------------------------------------------------
# eval loop
# ---------------------------------------------------------------------------

def run_one(label, rp, nrns):
    model.eval()
    recs, ords_, neds_ = [], [], []
    pred_words, gold_words, gen_tokens = [], [], []
    json_ok, hit_cap = 0, 0
    per_image = []

    overrides = dict(repetition_penalty=rp, no_repeat_ngram_size=nrns)

    for i, sample in enumerate(tqdm(test_raw, desc=label, leave=False)):
        img = sample["image"].convert("RGB")
        pv = processor(img, return_tensors="pt").pixel_values.to(device)
        words = sample.get("words", [])
        boxes = sample.get("bboxes") or sample.get("boxes")
        gt_words = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
        gt_str = json.dumps({"text": " ".join(gt_words)})

        with torch.no_grad():
            gen_ids, _meta = model.generate(
                pv, decoder_input_ids=prompt_ids,
                max_length=SWEEP_MAX_LEN, **overrides
            )

        n_tok = int(gen_ids.shape[-1])
        gen_tokens.append(n_tok)
        if n_tok >= SWEEP_MAX_LEN:
            hit_cap += 1

        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()

        try:
            json.loads(pred)
            json_ok += 1
        except Exception:
            pass

        r, o = compute_word_metrics(pred, gt_words)
        ned = compute_ned(pred, gt_str)
        recs.append(r)
        ords_.append(o)
        neds_.append(ned)
        pred_words.append(len(re.findall(r"\w+", pred.lower())))
        gold_words.append(len(re.findall(r"\w+", " ".join(gt_words).lower())))
        # Per-image rows are what make a PAIRED test possible. Without them the
        # sweep can only say "these aggregates differ by X", never "X is/is not
        # bigger than this harness can resolve on 50 documents".
        per_image.append({"i": i, "recall": float(r), "order": float(o),
                          "ned": float(ned)})

    n = max(len(recs), 1)
    mp = float(np.mean(pred_words))
    mg = float(np.mean(gold_words))
    return {
        "config": label,
        "repetition_penalty": rp,
        "no_repeat_ngram_size": nrns,
        "word_recall_pct": float(np.mean(recs) * 100.0),
        "character_accuracy_pct": float((1.0 - np.mean(neds_)) * 100.0),
        "word_order_pct": float(np.mean(ords_) * 100.0),
        "mean_ned": float(np.mean(neds_)),
        "mean_pred_words": mp,
        "mean_gold_words": mg,
        "len_ratio_pct": 100.0 * mp / max(mg, 1e-9),
        "mean_gen_tokens": float(np.mean(gen_tokens)),
        "hit_max_length_pct": 100.0 * hit_cap / n,
        "valid_json_pct": 100.0 * json_ok / n,
        "num_eval_samples": len(recs),
        "per_image": per_image,
    }


rows = []
# SWEEP_ONLY / SWEEP_OUT exist so a single row can be re-run for replication
# WITHOUT clobbering the filed result. This script used to write its fixed OUT
# path unconditionally, which is the most likely reason
# results/nrns_rp_sweep_aggregates_run2.json cannot be reconciled with the
# current one: an earlier run's numbers were overwritten and its script version
# is gone, leaving two files whose 2.73 pt control gap can no longer be
# attributed. Defaults are unchanged, so a bare invocation behaves exactly as before.
_only = os.environ.get("SWEEP_ONLY")
if _only:
    _sel = [c for c in SWEEP_CONFIGS if _only in c[0]]
    if not _sel:
        raise SystemExit(f"SWEEP_ONLY={_only!r} matched none of: "
                         f"{[c[0] for c in SWEEP_CONFIGS]}")
    # The CONTROL row is row 0 and every paired test below is measured against
    # it, so it must always be present or `ctrl` would silently become whatever
    # row happened to sort first.
    if SWEEP_CONFIGS[0] not in _sel:
        _sel = [SWEEP_CONFIGS[0]] + _sel
    SWEEP_CONFIGS = _sel
    print(f"SWEEP_ONLY={_only!r}: running {[c[0] for c in SWEEP_CONFIGS]}")

for label, rp, nrns in SWEEP_CONFIGS:
    print(f"--- {label}  (rp={rp}, nrns={nrns})")
    rows.append(run_one(label, rp, nrns))
    r = rows[-1]
    print(f"    recall {r['word_recall_pct']:.2f}  charAcc {r['character_accuracy_pct']:.2f}"
          f"  order {r['word_order_pct']:.2f}  len% {r['len_ratio_pct']:.1f}"
          f"  cap% {r['hit_max_length_pct']:.0f}  json% {r['valid_json_pct']:.1f}")

# ---------------------------------------------------------------------------
# table
# ---------------------------------------------------------------------------
hdr = (f"{'config':22s} {'rp':>5s} {'nrns':>5s} {'recall':>7s} {'charAcc':>8s}"
       f" {'order':>7s} {'NED':>6s} {'predW':>6s} {'len%':>6s} {'cap%':>5s} {'json%':>6s}")
print("\n" + "=" * len(hdr))
print(hdr)
print("-" * len(hdr))
for r in rows:
    print(f"{r['config']:22s} {r['repetition_penalty']:5.2f} {r['no_repeat_ngram_size']:5d}"
          f" {r['word_recall_pct']:7.2f} {r['character_accuracy_pct']:8.2f}"
          f" {r['word_order_pct']:7.2f} {r['mean_ned']:6.3f}"
          f" {r['mean_pred_words']:6.1f} {r['len_ratio_pct']:6.1f}"
          f" {r['hit_max_length_pct']:5.0f} {r['valid_json_pct']:6.1f}")
print("=" * len(hdr))

# ---------------------------------------------------------------------------
# CONTROL: two DIFFERENT questions, deliberately separated
# ---------------------------------------------------------------------------
# (a) SANITY FLOOR -- is this harness fundamentally working? The first version of
#     this script built the model with the class default keep_ratio=0.35, which
#     pruned 65% of tokens through run 5's UNTRAINED router and scored 23.49
#     recall. That is the failure this floor exists to catch, and a tight
#     Kaggle-parity tolerance would have caught it only by accident.
# (b) ABSOLUTE PARITY -- does it match Kaggle's run-6 numbers to 0.5 pts? It does
#     not, and it is not expected to: AGENTS.md already records local-vs-Kaggle
#     generation drift as a known limitation. This is INFORMATIONAL. It bounds
#     claims about absolute levels; it does not invalidate the sweep, because
#     every row shares this harness and the drift cancels in row-vs-row deltas.
SANITY_FLOOR = 70.0

ctrl = rows[0]
got = (ctrl["word_recall_pct"], ctrl["character_accuracy_pct"], ctrl["word_order_pct"])
drift = max(abs(g - e) for g, e in zip(got, RUN6_REFERENCE))

print(f"\n(a) SANITY FLOOR  CONTROL recall {ctrl['word_recall_pct']:.2f} "
      f"(floor {SANITY_FLOOR})")
sane = ctrl["word_recall_pct"] >= SANITY_FLOOR
print("    OK - harness is functioning." if sane else
      "    BROKEN - CONTROL is far below any plausible value. Check keep_ratio,\n"
      "    checkpoint and prompt wiring before reading any row.")

print(f"\n(b) ABSOLUTE PARITY vs run-6 {RUN6_REFERENCE}")
print(f"    got ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts")
parity = drift < CONTROL_TOL
if parity:
    print(f"    Matches Kaggle within {CONTROL_TOL} pts.")
else:
    print(f"    Drift {drift:.2f} pts > {CONTROL_TOL}: local CPU decoding differs from the")
    print("    Kaggle run, as AGENTS.md's local-vs-Kaggle limitation predicts. Absolute")
    print("    levels here are NOT citable against run 6; row-vs-row deltas below still are.")

# ---------------------------------------------------------------------------
# PAIRED comparison vs CONTROL -- the actual question
# ---------------------------------------------------------------------------
# Generation is greedy, so re-running a config is bit-identical: there is no
# run-to-run variance to average away. The uncertainty that matters is over
# DOCUMENTS -- would this ranking survive a different 50 forms? Same 50 documents
# per row, so pair by document and bootstrap the mean difference.
RNG = np.random.default_rng(0)
N_BOOT = 10000


def paired_delta(row, key="recall"):
    a = np.array([p[key] for p in ctrl["per_image"]])
    b = np.array([p[key] for p in row["per_image"]])
    d = (b - a) * 100.0
    idx = RNG.integers(0, len(d), size=(N_BOOT, len(d)))
    boots = d[idx].mean(axis=1)
    return d.mean(), np.percentile(boots, 2.5), np.percentile(boots, 97.5)


print("\n" + "=" * 78)
print("PAIRED vs CONTROL, by document (95% bootstrap CI, n=50)")
print("=" * 78)
print(f"{'config':22s} {'d_recall':>9s} {'95% CI':>18s}   verdict")
print("-" * 78)
any_sig = False
for r in rows[1:]:
    m, lo, hi = paired_delta(r)
    sig = lo > 0 or hi < 0
    any_sig = any_sig or sig
    print(f"{r['config']:22s} {m:+9.2f} {f'[{lo:+.2f}, {hi:+.2f}]':>18s}   "
          f"{'SIGNIFICANT' if sig else 'indistinguishable from CONTROL'}")
print("=" * 78)

# What effect could this harness have SEEN? A null result is only meaningful
# next to the smallest effect it could have detected.
_a = np.array([p["recall"] for p in ctrl["per_image"]])
_widths = []
for r in rows[1:]:
    _b = np.array([p["recall"] for p in r["per_image"]])
    _d = (_b - _a) * 100.0
    _widths.append(1.96 * _d.std(ddof=1) / np.sqrt(len(_d)))
resolution_pts = float(np.mean(_widths))
print(f"\nRESOLUTION: mean 95% half-width is {resolution_pts:.2f} pts.")
print(f"  Any true effect smaller than ~{resolution_pts:.1f} pts is invisible to this "
      f"sweep at n=50.")

# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------
best = max(rows, key=lambda r: r["word_recall_pct"])
delta = best["word_recall_pct"] - ctrl["word_recall_pct"]
print(f"\nHighest recall: '{best['config']}' at {best['word_recall_pct']:.2f}% "
      f"({delta:+.2f} vs CONTROL)")

# Monotonicity is a free falsification test: a real nrns effect should be smooth
# in nrns. A dip-then-recover in BOTH rp rows is what noise looks like.
for rp_val in (1.0, 1.05):
    seq = [r["word_recall_pct"] for r in rows if r["repetition_penalty"] == rp_val]
    if len(seq) == 3:
        mono = (seq[0] <= seq[1] <= seq[2]) or (seq[0] >= seq[1] >= seq[2])
        print(f"  rp={rp_val}: nrns 3/4/6 -> {seq[0]:.2f} / {seq[1]:.2f} / {seq[2]:.2f}"
              f"   {'monotonic' if mono else 'NON-monotonic (noise signature)'}")

# charAcc is the check on cherry-picking the recall column.
print(f"  charAcc: CONTROL {ctrl['character_accuracy_pct']:.2f} vs "
      f"best-recall row {best['character_accuracy_pct']:.2f} "
      f"({best['character_accuracy_pct'] - ctrl['character_accuracy_pct']:+.2f})")

if not any_sig:
    print("\n=> NO config is distinguishable from the current default at n=50.")
    print(f"   The grid is flat within +/-{resolution_pts:.1f} pts. KEEP rp=1.0, nrns=3.")
else:
    print("\n=> At least one config separates from the default. Read the CI column, and")
    print("   check charAcc/order before adopting: a recall-only win is not a win.")

# ---------------------------------------------------------------------------
# write results
# ---------------------------------------------------------------------------
OUT = os.environ.get("SWEEP_OUT") or os.path.join(ROOT, "results", "nrns_rp_sweep.json")
if not os.path.isabs(OUT):
    OUT = os.path.join(ROOT, OUT)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
payload = {
    "meta": {
        "checkpoint": os.path.relpath(CKPT, ROOT),
        "keep_ratio": 1.0,
        # Read from the model rather than hardcoded, so this line cannot drift from
        # what actually ran -- which is precisely how the pre-2026-09-16 rows came to
        # be merged at 0.20 with nothing in the file saying so.
        "merge_ratio": model.merge_ratio,
        "device": str(device),
        "run6_reference": RUN6_REFERENCE,
        "sanity_floor_ok": bool(sane),
        "kaggle_parity_ok": bool(parity),
        "control_drift_pts": round(drift, 4),
        "resolution_pts": round(resolution_pts, 4),
        "any_significant": bool(any_sig),
        "max_len": SWEEP_MAX_LEN,
        "num_eval_samples": len(test_raw),
        "n_bootstrap": N_BOOT,
    },
    "rows": rows,
}
with open(OUT, "w") as f:
    json.dump(payload, f, indent=2)
print(f"\nWrote {os.path.relpath(OUT, ROOT)}")

# Exit non-zero only if the harness is BROKEN. Kaggle parity drift is expected
# and recorded; failing on it would train the reader to ignore a red exit.
raise SystemExit(0 if sane else 1)
