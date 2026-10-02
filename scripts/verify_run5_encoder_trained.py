"""Differential check: did the Phase 2b unfreeze actually TRAIN the Swin tail?

Run 4 froze the whole encoder, so its encoder weights == pretrained donut-base.
Run 5 unfroze only the last stage. So the expected signature is:
    - encoder stages 0..2  : IDENTICAL between run 4 and run 5 (still frozen)
    - encoder stage 3      : DIFFERENT (trained)
That distinguishes "requires_grad was set and the optimizer moved the weights"
from "we only flipped a flag". Memory-frugal: loads one checkpoint at a time and
keeps only per-tensor float summaries, never both full state_dicts at once.
"""
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import torch

CKPTS = {
    "run4_frozen": r"c:\Users\Nafis\Desktop\Project\pruned_ocr_results-4\checkpoints\adaptive_donut_funsd.pt",
    "run5_unfroze": r"c:\Users\Nafis\Desktop\Project\run 5\checkpoints\adaptive_donut_funsd.pt",
}

# summarize encoder params only, bucketed by Swin stage
def summarize(path):
    sd = torch.load(path, map_location="cpu", weights_only=True)
    out = {}
    for k, v in sd.items():
        if not torch.is_floating_point(v):
            continue
        if ".encoder.encoder.layers." in k or k.startswith("model.encoder."):
            out[k] = (float(v.float().sum()), float(v.float().pow(2).sum()), tuple(v.shape))
    del sd
    return out

a = summarize(CKPTS["run4_frozen"])
b = summarize(CKPTS["run5_unfroze"])
shared = sorted(set(a) & set(b))
print(f"encoder tensors compared: {len(shared)}")


def stage_of(key):
    marker = ".encoder.encoder.layers."
    if marker in key:
        return int(key.split(marker)[1].split(".")[0])
    return None


buckets = {}
for k in shared:
    s = stage_of(k)
    label = f"stage {s}" if s is not None else "other encoder (embeddings/norm/pooler)"
    changed = a[k][:2] != b[k][:2]
    hit = buckets.setdefault(label, [0, 0])
    hit[0] += 1
    hit[1] += 1 if changed else 0

print("\nper-bucket: changed / total tensors")
for label in sorted(buckets, key=lambda x: (x != "other encoder (embeddings/norm/pooler)", x)):
    tot, ch = buckets[label][0], buckets[label][1]
    verdict = "CHANGED (trained)" if ch else "identical (frozen)"
    print(f"  {label:42s} {ch:3d}/{tot:3d}  -> {verdict}")

stages_present = sorted({stage_of(k) for k in shared if stage_of(k) is not None})
last = max(stages_present) if stages_present else None
tail_changed = buckets.get(f"stage {last}", [0, 0])[1] > 0
prefix_changed = any(buckets.get(f"stage {s}", [0, 0])[1] > 0 for s in stages_present if s != last)

print(f"\nexpected: only stage {last} changes")
print(f"  tail (stage {last}) trained : {tail_changed}")
print(f"  frozen prefix leaked       : {prefix_changed}")
ok = tail_changed and not prefix_changed
print("\nRESULT:", "PASS - unfreeze genuinely trained the tail only" if ok else "FAIL / unexpected pattern")
raise SystemExit(0 if ok else 1)
