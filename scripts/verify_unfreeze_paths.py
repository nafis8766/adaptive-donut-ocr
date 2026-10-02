"""Verify the Phase 2b unfreeze targets real modules on donut-base's Swin encoder.

Builds the donut-base architecture FROM CONFIG (random weights -- no ~1GB weight
download, no GPU), then runs the EXACT unfreeze loop from the patched training
cell against the real module tree. Confirms:
  1. encoder.encoder.layers exists (the Swin stages) and its length,
  2. the final norm is handled defensively (present on tx 4.x, absent on 5.x),
  3. the unfreeze flips requires_grad on the tail (and ONLY the tail),
  4. forward()'s `encoder_is_frozen` check flips True -> False as expected.

NOTE: local transformers may differ from Kaggle's (>=4.38). encoder.encoder.layers
is stable across both; the final norm name is not, hence the getattr guard.
"""
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import torch
from transformers import VisionEncoderDecoderModel, AutoConfig

REPO = "naver-clova-ix/donut-base"
ved = VisionEncoderDecoderModel(AutoConfig.from_pretrained(REPO))
enc = ved.encoder
print(f"transformers-local encoder type: {type(enc).__name__}")

# --- the paths the patch relies on (mirrors the notebook exactly) ---
stages = enc.encoder.layers                          # encoder.encoder.layers
final_norm = getattr(enc, "layernorm", None)         # defensive: 4.x has it, 5.x folded it
print(f"Swin stages (encoder.encoder.layers): {len(stages)}")
print(f"final norm (encoder.layernorm): {type(final_norm).__name__ if final_norm is not None else 'ABSENT (folded in this tx version)'}")

# --- baseline: freeze whole encoder like the notebook does ---
for p in enc.parameters():
    p.requires_grad = False
frozen_before = not any(p.requires_grad for p in enc.parameters())

# --- run the EXACT patch unfreeze loop ---
UNFREEZE_STAGES = 1
assert len(stages) >= UNFREEZE_STAGES, f"unexpected Swin structure: {len(stages)} stages"
for _stage in stages[-UNFREEZE_STAGES:]:
    for _p in _stage.parameters():
        _p.requires_grad = True
if final_norm is not None:
    for _p in final_norm.parameters():
        _p.requires_grad = True

frozen_after = not any(p.requires_grad for p in enc.parameters())
trainable = sum(p.numel() for p in enc.parameters() if p.requires_grad)
total = sum(p.numel() for p in enc.parameters())

# confirm ONLY last stage (+ layernorm) got unfrozen -- nothing leaked
last = len(stages) - 1
unfrozen = [n for n, p in enc.named_parameters() if p.requires_grad]
leaked = [n for n in unfrozen
          if not (n.startswith(f"encoder.layers.{last}.") or n.startswith("layernorm."))]

print(f"encoder_is_frozen before -> after: {frozen_before} -> {frozen_after}  (expect True -> False)")
print(f"trainable encoder params: {trainable/1e6:.2f}M / {total/1e6:.2f}M")
print(f"unfrozen tensors: {len(unfrozen)}; leaked outside tail: {leaked if leaked else 'none'}")

ok = frozen_before and (not frozen_after) and trainable > 0 and not leaked
print("\nRESULT:", "PASS - unfreeze targets valid modules and is tail-only" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
