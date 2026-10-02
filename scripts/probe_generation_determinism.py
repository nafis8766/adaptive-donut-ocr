"""Probe: is `model.generate()` bit-identical across repeat calls and across processes?

WHY THIS EXISTS
---------------
`scripts/run_nrns_rp_sweep.py:263` states, as the justification for its whole
uncertainty model:

    "Generation is greedy, so re-running a config is bit-identical: there is no
     run-to-run variance to average away. The uncertainty that matters is over
     DOCUMENTS"

Every CI in `results/nrns_rp_sweep.json` rests on that sentence, because it is the
reason the script bootstraps over documents ONLY. But the two stored sweeps disagree
by **2.73 pts** on the IDENTICAL control config (rp=1.0, nrns=3) on the IDENTICAL
checkpoint:

    results/nrns_rp_sweep_aggregates_run2.json   CONTROL word_recall = 79.370
    results/nrns_rp_sweep.json                   CONTROL word_recall = 76.645

Those two files have different meta schemas, so they came from different versions of
the script and are NOT a clean replication test -- and the older one stored no
per-image rows, so the gap cannot be diagnosed from the artifacts. Hence a direct
test. This is the project's standing rule applied to a claim *about* the code: assert
it by execution, not by reading.

WHAT IT TESTS
-------------
Pass A and pass B run the same images in the SAME process  -> within-process determinism.
The token IDs are also written to results/determinism_probe_<tag>.json, so a second
invocation under a different tag tests ACROSS-process determinism -- which is the
condition the two sweep files actually differ under, and the one that matters.

Within-process equality alone does NOT clear the claim: a process-startup-dependent
difference (thread count, BLAS kernel choice, allocator layout) reproduces perfectly
inside one process and still moves the aggregate between runs.

DELIBERATELY NOT SEEDED
-----------------------
No `torch.manual_seed`, no `use_deterministic_algorithms`. The sweep did not set them
either, and the question is whether the sweep's OWN conditions are reproducible.
Seeding here would mask the exact effect under test -- a green check that cannot fail.

Usage:
    python scripts/probe_generation_determinism.py run1
    python scripts/probe_generation_determinism.py run2
    python scripts/probe_generation_determinism.py --compare run1 run2
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

OUTDIR = os.path.join(ROOT, "results")


def outpath(tag):
    return os.path.join(OUTDIR, f"determinism_probe_{tag}.json")


# ---------------------------------------------------------------------------
# compare mode -- no torch import, no checkpoint load
# ---------------------------------------------------------------------------
def compare(tag_a, tag_b):
    pa, pb = outpath(tag_a), outpath(tag_b)
    for p in (pa, pb):
        if not os.path.exists(p):
            raise SystemExit(f"missing {p} -- run the probe under that tag first")
    a, b = json.load(open(pa)), json.load(open(pb))

    print("=" * 74)
    print(f"ACROSS-PROCESS: {tag_a} vs {tag_b}")
    print("=" * 74)
    print(f"  {tag_a}: device={a['meta']['device']}  torch={a['meta']['torch']}  "
          f"threads={a['meta']['threads']}")
    print(f"  {tag_b}: device={b['meta']['device']}  torch={b['meta']['torch']}  "
          f"threads={b['meta']['threads']}")
    print()

    ids_a = {r["i"]: r["pass_a_ids"] for r in a["rows"]}
    ids_b = {r["i"]: r["pass_a_ids"] for r in b["rows"]}
    txt_a = {r["i"]: r["pass_a_text"] for r in a["rows"]}
    txt_b = {r["i"]: r["pass_a_text"] for r in b["rows"]}
    shared = sorted(set(ids_a) & set(ids_b))
    if not shared:
        raise SystemExit("no overlapping image indices between the two runs")

    n_same = 0
    for i in shared:
        same = ids_a[i] == ids_b[i]
        n_same += same
        if not same:
            la, lb = len(ids_a[i]), len(ids_b[i])
            first = next((k for k in range(min(la, lb))
                          if ids_a[i][k] != ids_b[i][k]), min(la, lb))
            print(f"  image {i}: DIFFER  len {la} vs {lb}, first divergence at token {first}")
            print(f"      {tag_a}: ...{txt_a[i][max(0, first - 40):first + 60]!r}")
            print(f"      {tag_b}: ...{txt_b[i][max(0, first - 40):first + 60]!r}")

    print()
    print(f"  identical: {n_same}/{len(shared)} images")
    verdict = n_same == len(shared)
    print()
    if verdict:
        print("  VERDICT: generation IS bit-identical across processes.")
        print("    The sweep's stated assumption holds, so its document-only bootstrap")
        print("    is the right uncertainty model and the 2.73 pt control gap between")
        print("    the two stored files must come from a CODE difference between the")
        print("    two script versions, not from run-to-run noise.")
    else:
        print("  VERDICT: generation is NOT bit-identical across processes.")
        print("    run_nrns_rp_sweep.py:263 is FALSE, and every CI in")
        print("    results/nrns_rp_sweep.json is understated: it bootstraps over")
        print("    documents only and therefore omits a real second variance source.")
        print("    The '+4.74 pts, [+1.49, +8.11]' headline is not adoptable as stated.")
    return 0 if verdict else 1


if len(sys.argv) >= 2 and sys.argv[1] == "--compare":
    if len(sys.argv) != 4:
        raise SystemExit("usage: probe_generation_determinism.py --compare TAG_A TAG_B")
    raise SystemExit(compare(sys.argv[2], sys.argv[3]))

# ---------------------------------------------------------------------------
# probe mode
# ---------------------------------------------------------------------------
TAG = sys.argv[1] if len(sys.argv) > 1 else "run1"
N_IMAGES = int(os.environ.get("PROBE_N", "6"))

import torch                                    # noqa: E402
from transformers import DonutProcessor         # noqa: E402
from datasets import load_dataset               # noqa: E402
from src.model import AdaptiveDonutOCR          # noqa: E402

# Mirrors run_nrns_rp_sweep.py exactly: same checkpoint, same keep_ratio=1.0
# (run-5 weights have an untrained router, so K=N makes it a no-op), same
# prompt, same max_length, same CONTROL decoding config.
#
# merge_ratio=0.0 is NAMED, not inherited. Before 2026-09-16 the class default was
# 0.20 and neither this line nor gen() mentioned it, so this probe ran a MERGED
# pipeline while its docstring claimed to mirror an unmerged sweep. Any stored
# results/determinism_probe_*.json written before that date is a probe of the
# merged path; re-run under a fresh tag before comparing against a new one.
CKPT = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
if not os.path.exists(CKPT):
    raise SystemExit(f"checkpoint not found: {CKPT}")

TASK_PROMPT = "<s_doc>"
SWEEP_MAX_LEN = 512
CONTROL = dict(repetition_penalty=1.0, no_repeat_ngram_size=3)

print(f"[{TAG}] loading checkpoint: {os.path.relpath(CKPT, ROOT)}")
processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True)
model.load_state_dict(torch.load(CKPT, map_location="cpu"))
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
prompt_ids = processor.tokenizer(
    TASK_PROMPT, add_special_tokens=False, return_tensors="pt").input_ids.to(device)

print(f"[{TAG}] device={device} torch={torch.__version__} "
      f"threads={torch.get_num_threads()}")
print(f"[{TAG}] loading FUNSD test split...")
test_raw = list(load_dataset("nielsr/funsd", split="test"))[:N_IMAGES]
print(f"[{TAG}] probing {len(test_raw)} images, two passes each")


def gen(pv):
    with torch.no_grad():
        gen_ids, _meta = model.generate(
            pv, decoder_input_ids=prompt_ids,
            max_length=SWEEP_MAX_LEN, **CONTROL)
    ids = gen_ids[0].tolist()
    text = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
    return ids, text


rows = []
n_within_same = 0
for i, sample in enumerate(test_raw):
    img = sample["image"].convert("RGB")
    pv = processor(img, return_tensors="pt").pixel_values.to(device)

    ids_a, txt_a = gen(pv)
    ids_b, txt_b = gen(pv)
    same = ids_a == ids_b
    n_within_same += same
    print(f"  image {i}: {len(ids_a):4d} tok  within-process "
          f"{'IDENTICAL' if same else 'DIFFERS'}")
    rows.append({"i": i, "pass_a_ids": ids_a, "pass_b_ids": ids_b,
                 "pass_a_text": txt_a, "pass_b_text": txt_b,
                 "within_identical": bool(same)})

os.makedirs(OUTDIR, exist_ok=True)
payload = {
    "meta": {
        "tag": TAG,
        "checkpoint": os.path.relpath(CKPT, ROOT),
        "device": str(device),
        "torch": torch.__version__,
        "threads": torch.get_num_threads(),
        "n_images": len(rows),
        "decoding": CONTROL,
        "max_length": SWEEP_MAX_LEN,
        "keep_ratio": 1.0,
        "merge_ratio": model.merge_ratio,
        "seeded": False,
        "within_process_identical": f"{n_within_same}/{len(rows)}",
    },
    "rows": rows,
}
with open(outpath(TAG), "w") as f:
    json.dump(payload, f, indent=2)

print()
print(f"[{TAG}] within-process identical: {n_within_same}/{len(rows)}")
print(f"[{TAG}] wrote {os.path.relpath(outpath(TAG), ROOT)}")
print()
print("Within-process equality does NOT clear the sweep's claim on its own.")
print(f"Run again under a different tag, then:")
print(f"    python scripts/probe_generation_determinism.py --compare {TAG} <other>")
