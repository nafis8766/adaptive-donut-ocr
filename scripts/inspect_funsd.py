"""Probe FUNSD structure: does it carry bounding boxes, and is the stored
word order the visual reading order? This decides whether the current
'0% sequence' symptom is a model failure or a label-ordering artifact."""
import os, sys
from datasets import load_dataset

ds = load_dataset("nielsr/funsd", split="test")
print("FEATURES:", list(ds.features.keys()))
s = ds[0]
print("SAMPLE KEYS:", list(s.keys()))
for k in s.keys():
    if k == "image":
        print(f"  image: size={s[k].size}")
        continue
    v = s[k]
    n = len(v) if hasattr(v, "__len__") else v
    print(f"  {k}: type={type(v).__name__} len/val={n}")

words = s.get("words")
boxes = s.get("bboxes") or s.get("boxes") or s.get("bbox")
print("\nN words:", len(words) if words else None)
print("ANNOTATION ORDER (first 30):", words[:30] if words else None)

if boxes:
    print("first 3 boxes:", boxes[:3])
    # reading-order sort: bucket rows by y (top-left), then left->right by x
    idx = list(range(len(words)))
    idx.sort(key=lambda i: (round(boxes[i][1] / 25.0), boxes[i][0]))
    reading = [words[i] for i in idx]
    print("READING ORDER  (first 30):", reading[:30])
    same = words[:30] == reading[:30]
    print("\nannotation order == reading order (first 30)?", same)
else:
    print("No bbox field found on this dataset build.")
