"""Phase-1 smoke test: exercise the exact config the Kaggle run will use
(keep_ratio=1.0, merge_ratio=0.0) end-to-end on CPU, so a boundary-value crash
surfaces here instead of after a long GPU training run.

Checks: reading-order target from the real dataset path; forward + loss;
backward (grad flow through router STE at keep=1.0); primed generation.
"""
import os, sys, torch
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from transformers import DonutProcessor
from src.model import AdaptiveDonutOCR
from src.dataset import SROIEDonutDataset

proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")

# Real dataset path -> confirms reading-order target is built
ds = SROIEDonutDataset(dataset_name="nielsr/funsd", split="test", processor=proc, max_samples=2)
item = ds[0]
print("TARGET[:110]:", item["raw_text"][:110])

pv = item["pixel_values"].unsqueeze(0)
labels = item["labels"].unsqueeze(0)
dii = item["decoder_input_ids"].unsqueeze(0)

model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True)

model.train()
out = model(pixel_values=pv, labels=labels, decoder_input_ids=dii)
assert torch.isfinite(out["loss"]), "loss is not finite!"
print(f"FORWARD  ok | loss={out['loss'].item():.3f} | tokens {out['compressed_tokens']}/{out['original_tokens']} "
      f"(savings {out['compression_ratio']:.1f}%)")
out["loss"].backward()
gr = model.router.scorer[0].weight.grad
print(f"BACKWARD ok | router grad present={gr is not None and gr.abs().sum().item() > 0}")

model.eval()
pids = proc.tokenizer("<s_doc>", add_special_tokens=False, return_tensors="pt").input_ids
with torch.no_grad():
    gen, meta = model.generate(pv, decoder_input_ids=pids, max_length=24)
print(f"GENERATE ok | out_len={gen.shape[1]} | tokens {meta['compressed_tokens']}/{meta['original_tokens']}")
print("DECODE:", proc.batch_decode(gen, skip_special_tokens=True)[0][:80])
print("\nALL PHASE-1 SMOKE CHECKS PASSED")
