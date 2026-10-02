"""D10 (2026-09-02, local CPU) — does 13(b)'s target stay put while the encoder drifts?

13(b) computes its target on the fly: `topK(run5_decoder.cross_attention(student_encoder(page)))`.
The teacher decoder is a frozen run-5 snapshot, so the DECODER's drift is irrelevant by
construction. But the encoder is not frozen — `UNFREEZE_STAGES = 1` trains the top Swin stage —
so the target is recomputed from features that move, and the router is chasing a target that
moves with them. If it moves a lot, the router is fitting noise and 13(b) fails for a reason
that has nothing to do with the hypothesis.

I do not have to speculate: run 5 -> run 9 is a COMPLETED run under the identical config, so the
drift run 10 will experience is already on disk. Measured 2026-09-02, relative weight drift:
Swin stages 0/1/2 exactly 0.000000 (315 tensors), stage 3 moved on 34/34 with max 0.0120,
router median 0.298. So the encoder barely moves. This script asks whether that translates into
a stable target, which is the question that actually matters.

THE CONTROL IS THE POINT. A high same-page overlap under drift means nothing on its own,
because these targets share page-invariant structure — both avoid the margins, so two targets
from DIFFERENT pages already overlap well above the combinatorial 0.500. So the number to read
is the gap:

    S = overlap(target from run-5 features, target from run-9 features)   -- same page
    X = overlap(target from page i, target from page j)                   -- different pages

S is only meaningful ABOVE X. If S ~= X the target carries no page-specific information that
survives drift, and the "stability" figure is vacuous. This is the mistake the ink-overlap
number in Pending 13 already made once by being read against 0.500.

Usage:
    PYTHONIOENCODING=utf-8 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
        python -u scripts/diagnose_target_drift.py [--n 5]
Read-only. CPU. No GPU, no downloads (donut-base and FUNSD are both cached).
"""
import argparse
import copy
import gc
import json
import os
import statistics
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import DonutProcessor, VisionEncoderDecoderModel
from transformers.modeling_outputs import BaseModelOutput

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

RUN5 = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
RUN9 = os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")
KEEP = 0.50
GRID = (80, 60)


def hr(c="="):
    print(c * 78)


def load_notebook_defs():
    """Execute cells 4 and 7 so this measures the SHIPPED attn_topk_target, not a copy."""
    nb = json.loads(open(os.path.join(ROOT, "kaggle_pruning_run.ipynb"),
                         encoding="utf-8").read())
    ns = {"torch": torch, "nn": nn, "F": F, "gc": gc, "os": os, "json": json,
          "VisionEncoderDecoderModel": VisionEncoderDecoderModel,
          "BaseModelOutput": BaseModelOutput, "__name__": "nb"}
    for i in (4, 7):
        exec(compile("".join(nb["cells"][i]["source"]), f"<cell{i}>", "exec"), ns)
    return ns


def overlap(a, b):
    """Fraction of a's positives that are also b's positives (both have K positives)."""
    return float((a * b).sum() / a.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5, help="FUNSD train pages")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    for p in (RUN5, RUN9):
        if not os.path.exists(p):
            raise SystemExit(f"missing checkpoint: {p}")

    ns = load_notebook_defs()
    attn_topk_target = ns["attn_topk_target"]

    from datasets import load_dataset
    from diagnose_ste_signal import MAX_LEN, build_target_text

    print(f"D10 -- target stability under encoder drift (run 5 -> run 9), "
          f"{args.n} FUNSD {args.split} pages")
    hr()
    proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split=args.split)
    pages = []
    for i in range(args.n):
        pv = proc(ds[i]["image"].convert("RGB"), return_tensors="pt").pixel_values
        lab = proc.tokenizer([build_target_text(ds[i])], add_special_tokens=False,
                            max_length=MAX_LEN, padding="max_length", truncation=True,
                            return_tensors="pt").input_ids
        lab[lab == proc.tokenizer.pad_token_id] = -100
        din = lab.clone()
        din[din == -100] = proc.tokenizer.pad_token_id
        pages.append((pv, lab, din))
    print(f"  {len(pages)} pages, pixel_values {tuple(pages[0][0].shape)}")

    model = ns["AdaptiveDonutOCR"](keep_ratio=KEEP, merge_ratio=0.0, freeze_encoder=True)

    # The teacher is run 5's decoder, frozen -- exactly what cell 11 snapshots. It never
    # changes below, so every difference measured is attributable to the ENCODER alone.
    model.load_state_dict(torch.load(RUN5, map_location="cpu", weights_only=True),
                          strict=False)
    model.eval()
    teacher = copy.deepcopy(model.model.decoder).eval()
    for cfg in (getattr(teacher, "config", None),
                getattr(getattr(teacher, "model", None), "config", None)):
        if cfg is not None:
            cfg._attn_implementation = "eager"
            cfg.output_attentions = True
    print("  teacher: run 5 decoder, frozen, eager attention (decoder drift is irrelevant "
          "by construction -- only the encoder moves)")

    def features(tag):
        out = []
        with torch.no_grad():
            for pv, _, _ in pages:
                out.append(model.model.encoder(pv).last_hidden_state)
        print(f"  encoded {len(out)} pages with {tag} features "
              f"{tuple(out[0].shape)}")
        return out

    f5 = features("run 5")
    model.load_state_dict(torch.load(RUN9, map_location="cpu", weights_only=True),
                          strict=False)
    model.eval()
    f9 = features("run 9")

    N = f5[0].shape[1]
    K = max(1, int(round(N * KEEP)))

    def target(feat, i):
        _, lab, din = pages[i]
        return attn_topk_target(teacher, feat, din, lab, N, KEEP)[0]

    print()
    hr()
    print("A. FEATURE DRIFT -- does 1% of weight movement move the representation?")
    hr()
    print("  Weight drift was max 0.0120 on Swin stage 3 and exactly 0 on stages 0-2. That")
    print("  bounds nothing on its own: a small weight change can move features further.")
    print()
    print(f"  {'page':>5} {'rel L2 dF/F':>13} {'cos(f5,f9)':>12} {'per-token cos':>15}")
    fdrift = []
    for i in range(len(pages)):
        a, b = f5[i][0].float(), f9[i][0].float()
        rel = float((b - a).norm() / a.norm())
        cos = float(F.cosine_similarity(a.flatten(), b.flatten(), dim=0))
        tok = float(F.cosine_similarity(a, b, dim=1).mean())
        fdrift.append(rel)
        print(f"  {i:5d} {rel:13.4f} {cos:12.4f} {tok:15.4f}")
    print(f"  median relative feature drift: {statistics.median(fdrift):.4f}")

    print()
    hr()
    print("B. TARGET STABILITY -- and the page-invariance floor it must beat")
    hr()
    t5 = [target(f5[i], i) for i in range(len(pages))]
    t9 = [target(f9[i], i) for i in range(len(pages))]
    same = [overlap(t5[i], t9[i]) for i in range(len(pages))]
    cross = [overlap(t5[i], t5[j])
             for i in range(len(pages)) for j in range(len(pages)) if i != j]

    print(f"  {'page':>5} {'S = ov(T_run5, T_run9)':>24} {'changed positives':>19}")
    for i, s in enumerate(same):
        print(f"  {i:5d} {s:24.4f} {int(round((1 - s) * K)):13d}/{K}")
    S = statistics.median(same)
    X = statistics.median(cross)
    print()
    print(f"  S  same page, drifted encoder : {S:.4f}  (median over {len(same)} pages)")
    print(f"  X  different pages, floor     : {X:.4f}  (median over {len(cross)} pairs)")
    print(f"  chance (combinatorial)        : {K / N:.4f}  -- NOT the right null; X is")
    print(f"  gap S - X                     : {S - X:+.4f}")

    print()
    hr()
    print("C. IS THE DRIFTED TARGET STILL WELL-POSED?")
    hr()
    for tag, ts in (("run 5", t5), ("run 9", t9)):
        ks = {int(t.sum()) for t in ts}
        rows = statistics.median([(t.view(*GRID).sum(dim=1) > 0).sum().item() for t in ts])
        print(f"  {tag}: positives {ks} (want {{{K}}}), median rows touched {rows:.0f}/{GRID[0]}")

    print()
    hr()
    print("VERDICT")
    hr()
    # Thresholds stated before reading, so this can come out against me.
    #   S >= 0.90 and gap >= 0.20 -> stationary enough; launch run 10.
    #   S <  0.75  or gap <  0.10 -> the router chases a moving//uninformative target; the
    #                                on-the-fly design needs revisiting before spending GPU.
    ok_stable = S >= 0.90
    ok_gap = (S - X) >= 0.20
    print(f"  pre-registered: S >= 0.90 (got {S:.4f} -> {'PASS' if ok_stable else 'FAIL'})")
    print(f"  pre-registered: S - X >= 0.20 (got {S - X:+.4f} -> "
          f"{'PASS' if ok_gap else 'FAIL'})")
    if ok_stable and ok_gap:
        print("  -> The target is effectively stationary under the drift a real run produces,")
        print("     AND it is page-specific rather than page-invariant structure. The")
        print("     on-the-fly design holds. This says nothing about whether the target")
        print("     HELPS -- that is still recall at keep=0.50/0.35 vs run 9.")
    else:
        print("  -> DO NOT launch run 10 on this design yet. Record which threshold failed")
        print("     and why in AGENTS.md before changing anything.")
    print("D10 done")


if __name__ == "__main__":
    main()
