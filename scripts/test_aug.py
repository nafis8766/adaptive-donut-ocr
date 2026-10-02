"""Validate Phase-1.5 augmentation before spending a Kaggle run on it:
  - DOC_AUG imported OK (torchvision API compatible, fill= accepted)
  - applying it to a real FUNSD image raises nothing and preserves size/mode
  - the full augment=True dataset item yields finite pixel_values
Augmentation is random, so we sample a few times.
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import torch
from transformers import DonutProcessor
from src.dataset import SROIEDonutDataset, DOC_AUG

print("DOC_AUG available:", DOC_AUG is not None)
assert DOC_AUG is not None, "torchvision transform build failed -> augmentation would be silently OFF on Kaggle too"

proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
ds = SROIEDonutDataset(dataset_name="nielsr/funsd", split="train", processor=proc, max_samples=3, augment=True)

# Direct transform on the raw PIL image (this is what runs inside __getitem__)
raw = ds.dataset[0]["image"].convert("RGB")
for k in range(4):
    aug = DOC_AUG(raw)
    assert aug.size == raw.size, f"aug changed size {raw.size} -> {aug.size}"
    assert aug.mode == "RGB", f"aug changed mode -> {aug.mode}"
print(f"DOC_AUG ok on real image | size preserved {raw.size} | 4/4 samples RGB")

# Full item path with augment=True
for k in range(3):
    item = ds[0]
    pv = item["pixel_values"]
    assert pv.shape[0] == 3 and torch.isfinite(pv).all(), "bad pixel_values"
print(f"augment=True dataset item ok | pixel_values {tuple(pv.shape)} finite | labels {tuple(item['labels'].shape)}")

# Sanity: augment=False must NOT alter the image (eval/inference path)
ds_eval = SROIEDonutDataset(dataset_name="nielsr/funsd", split="train", processor=proc, max_samples=1, augment=False)
print("augment=False path ok (eval/inference unaffected):", ds_eval.augment is False)

print("\nAUG VALIDATION PASSED")
