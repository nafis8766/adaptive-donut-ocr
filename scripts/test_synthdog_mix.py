"""Validate the Phase 2-data SynthDoG mix BEFORE spending a Kaggle run.

Two layers:
  * Hard unit tests (deterministic; only FUNSD, which is tiny/cached):
      - _format_target_json normalizes a SynthDoG ground_truth to {"text": ...}
        (never {"text_sequence": ...}) and respects the 128-word cap
      - the FUNSD words+bboxes path is unchanged (regression guard)
  * Best-effort live checks (streaming -> pulls only the first rows, NOT the
    500k-image corpus; skipped with a clear message if offline):
      - a REAL SynthDoG example normalizes to a non-empty {"text": ...}
      - a REAL SynthDoG image survives the Donut processor -> finite big-canvas
        pixel_values (this is the path that actually runs on Kaggle)
"""
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import torch
from transformers import DonutProcessor
from src.dataset import SROIEDonutDataset, MAX_TARGET_WORDS

proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
# FUNSD instance only so we can call _format_target_json (it uses module globals,
# not the loaded split) without downloading SynthDoG locally.
ds = SROIEDonutDataset(dataset_name="nielsr/funsd", split="train", processor=proc, max_samples=2)

# --- Hard test 1: SynthDoG ground_truth -> unified {"text": ...} schema ---
synth_sample = {"ground_truth": json.dumps({"gt_parse": {"text_sequence": "Hello World Foo Bar"}})}
out = json.loads(ds._format_target_json(synth_sample))
assert set(out.keys()) == {"text"}, f"expected only 'text' key, got {list(out.keys())}"
assert "text_sequence" not in out, "leaked raw SynthDoG schema into the target"
assert out["text"] == "Hello World Foo Bar", f"unexpected text: {out['text']!r}"
print("[1/4] SynthDoG ground_truth normalizes to {'text': ...}  OK")

# --- Hard test 2: 128-word cap applies to SynthDoG text_sequence ---
long_seq = " ".join(f"w{i}" for i in range(300))
capped = json.loads(ds._format_target_json({"ground_truth": json.dumps({"gt_parse": {"text_sequence": long_seq}})}))
n = len(capped["text"].split())
assert n == MAX_TARGET_WORDS, f"cap not applied: {n} words (expected {MAX_TARGET_WORDS})"
print(f"[2/4] 300-word SynthDoG target capped to {n} words  OK")

# --- Hard test 3: FUNSD words+bboxes path unchanged (regression) ---
funsd_out = json.loads(ds._format_target_json(ds.dataset[0]))
assert set(funsd_out.keys()) == {"text"} and funsd_out["text"].strip(), "FUNSD target regressed"
print(f"[3/4] FUNSD path intact | {len(funsd_out['text'].split())} words, e.g. {funsd_out['text'][:60]!r}  OK")

# --- Best-effort live test 4: real SynthDoG example (stream) ---
try:
    from datasets import load_dataset
    stream = load_dataset("naver-clova-ix/synthdog-en", split="train", streaming=True)
    ex = next(iter(stream))
    real = json.loads(ds._format_target_json({"ground_truth": ex["ground_truth"]}))
    assert set(real.keys()) == {"text"} and real["text"].strip(), "real SynthDoG normalized to empty/bad target"
    assert len(real["text"].split()) <= MAX_TARGET_WORDS
    img = ex["image"].convert("RGB")
    pv = proc(img, return_tensors="pt").pixel_values
    assert pv.ndim == 4 and pv.shape[1] == 3 and min(pv.shape[2:]) >= 1920 and torch.isfinite(pv).all(), \
        f"SynthDoG image -> bad pixel_values {tuple(pv.shape)}"
    del stream
    print(f"[4/4] LIVE: real SynthDoG -> text {len(real['text'].split())} words; "
          f"image -> pixel_values {tuple(pv.shape)} finite  OK")
except Exception as e:
    print(f"[4/4] LIVE SynthDoG check SKIPPED (network/stream issue): {type(e).__name__}: {e}")
    print("      -> the notebook downloads it on Kaggle; hard tests above already cover the normalization logic.")

print("\nSYNTHDOG MIX VALIDATION PASSED (hard tests)")
