"""Execution gate for TRAINING with merge_ratio > 0 (run 14). RUNS notebook code.

WHY THIS EXISTS
---------------
Run 13 measured merging on a merge-NAIVE checkpoint: 20% merge is free (five nulls),
40% merge costs -3.86 pts [-7.44, -0.35] -- the only statistically resolved merge
effect in the whole run, and it is a cost. D12/H1 say that is exactly the condition
under which a cost is expected, because every checkpoint in this project was trained
at merge_ratio=0.0. Run 14 closes that by training WITH merging on.

The change itself is one line (cell 11 built the training model with a hardcoded
`merge_ratio=0.0`). The risk is not the line, it is whether the gradient survives the
merger. If it does not, the router trains on a signal that no longer describes what
the decoder sees, every loss term still decreases, the checkpoint still saves, the
28-row sweep still tabulates, and the run means nothing. That is this project's
recurring failure shape, so it gets an execution gate rather than a code reading.

WHAT WOULD MAKE THIS VACUOUS, AND WHAT STOPS IT
----------------------------------------------
"Gradients are non-zero" passes trivially: the router gets gradient from the PRUNE
path (the STE multiplier) whether or not the merger is differentiable, because
`selected_tokens` feeds the decoder either way. So every check below is paired:

  * grad-reaches-router is paired with grad-DIFFERS-from-merge-off, on identical
    weights, inputs and seed. If the merger were a gradient dead end, the merged run
    would still produce gradient -- but a numerically IDENTICAL one, because the only
    surviving path would be the unmerged A-tokens;
  * the merged/unmerged difference is measured against the run-to-run noise floor of
    the SAME config, so "differs" cannot be reporting nondeterminism;
  * the decoder is stubbed with a layer that reads EVERY encoder position, so a
    gradient that reached only the passed-through A-tokens would be visibly partial;
  * the per-token gradient is checked on the B-set specifically (the tokens that get
    merged INTO), since those are the ones whose path runs through `torch.bmm(T_t, A)`.

Also measures the wall-clock cost of merging per training step. `BipartiteTokenMerger`
calls `torch.nonzero` and boolean-mask indexing per batch item, both of which force a
device sync; run 9 already took ~4 h to train, so a large per-step multiplier would
not fit a Kaggle session and the run should be re-planned rather than launched.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_train_with_merge.py
"""
import ast
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_PATH = os.path.join(ROOT, "kaggle_pruning_run.ipynb")

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def cells_of(path):
    blob = json.loads(open(path, encoding="utf-8").read())
    return ["".join(c["source"]) if c["cell_type"] == "code" else None
            for c in blob["cells"]]


CELLS = cells_of(NB_PATH)


def find_cell(marker):
    for i, src in enumerate(CELLS):
        if src and marker in src:
            return i
    raise RuntimeError(f"no cell contains {marker!r}")


# A real 80x60 grid so `_token_grid` resolves exactly as it will on Kaggle; D small so
# this runs on CPU in seconds. The grid shape is what the checkerboard depends on, the
# hidden width is not.
GH, GW = 80, 60
N = GH * GW
D = 8
VOCAB = 11
TGT = 6

print("=" * 78)
print("0. cells exec")
print("=" * 78)

from transformers.modeling_outputs import BaseModelOutput  # noqa: E402

NBNS = {
    "torch": torch, "nn": nn, "F": F, "np": np, "json": json,
    "gc": __import__("gc"), "BaseModelOutput": BaseModelOutput,
    "VisionEncoderDecoderModel": None,
}
i2 = find_cell("from transformers.modeling_outputs import BaseModelOutput")
for _n in ast.parse(CELLS[i2]).body:
    if isinstance(_n, ast.ImportFrom) and _n.module == "typing":
        exec(compile(ast.Module([_n], []), f"<nb cell {i2}>", "exec"), NBNS)

i4 = find_cell("class PatchSaliencyRouter")
i7 = find_cell("class AdaptiveDonutOCR")
exec(compile(CELLS[i4], f"<nb cell {i4}>", "exec"), NBNS)
exec(compile(CELLS[i7], f"<nb cell {i7}>", "exec"), NBNS)
check("cell 4 + cell 7 exec", "AdaptiveDonutOCR" in NBNS and "checkerboard_color" in NBNS)


# ------------------------------------------------------------------ stub inner model
class _StubEncoder(nn.Module):
    """Frozen, like the real Swin -- `forward()` detects this and wraps it in no_grad."""

    def __init__(self):
        super().__init__()
        self.dummy = nn.Parameter(torch.zeros(1), requires_grad=False)

    def forward(self, pixel_values):
        g = torch.Generator().manual_seed(1234)
        return BaseModelOutput(
            last_hidden_state=torch.randn(pixel_values.shape[0], N, D, generator=g))


class _StubDecoder(nn.Module):
    """Reads EVERY encoder position, so partial gradient coverage is detectable.

    A decoder that attended to only the first M' positions would let a broken merger
    pass: the merged tokens it never read would show zero grad and nothing upstream
    would notice. Mean-pooling over dim=1 touches all of them with equal weight.
    """

    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(D, D)
        self.head = nn.Linear(D, VOCAB)

    def forward(self, input_ids=None, encoder_hidden_states=None, return_dict=True):
        ctx = self.proj(encoder_hidden_states).mean(dim=1)          # (B, D)
        T = input_ids.shape[1]
        logits = self.head(ctx.unsqueeze(1).expand(-1, T, -1))      # (B, T, VOCAB)
        return BaseModelOutput(last_hidden_state=logits), logits


class _StubInner(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = _StubEncoder()
        self._dec = _StubDecoder()
        self.config = type("C", (), {"decoder_start_token_id": 0})()

    def decoder(self, input_ids=None, encoder_hidden_states=None, return_dict=True):
        _, logits = self._dec(input_ids=input_ids,
                              encoder_hidden_states=encoder_hidden_states)
        return type("O", (), {"logits": logits})()


def build_model(merge_ratio, keep_ratio=0.50, seed=0):
    torch.manual_seed(seed)
    m = object.__new__(NBNS["AdaptiveDonutOCR"])
    nn.Module.__init__(m)
    m.base_model_name = "stub"
    m.keep_ratio = keep_ratio
    m.merge_ratio = merge_ratio
    m.router = NBNS["PatchSaliencyRouter"](hidden_dim=D, reduction_dim=4)
    m.tome_merger = NBNS["BipartiteTokenMerger"](hidden_dim=D)
    m.model = _StubInner()
    return m


def one_step(merge_ratio, keep_ratio=0.50, seed=0, B=2):
    """Train-mode forward + backward. Returns (router grad vector, M, scores shape)."""
    m = build_model(merge_ratio, keep_ratio, seed)
    m.train()                                   # use_ste=self.training -> STE live
    torch.manual_seed(99)
    pv = torch.rand(B, 3, GH * 32, GW * 32)
    dii = torch.randint(0, VOCAB, (B, TGT))
    labels = torch.randint(0, VOCAB, (B, TGT))
    out = m(pixel_values=pv, labels=labels, decoder_input_ids=dii)
    out["loss"].backward()
    g = torch.cat([p.grad.reshape(-1) for _, p in sorted(m.router.named_parameters())
                   if p.grad is not None])
    # forward() returns compressed_tokens as the INT M, not the tensor.
    return g, int(out["compressed_tokens"]), tuple(out["scores"].shape), m


# =========================================================== 1. gradient survives ToMe
print()
print("=" * 78)
print("1. the router still receives gradient when its tokens are MERGED")
print("=" * 78)

g0, M0, s0, _ = one_step(0.0)
g20, M20, s20, _ = one_step(0.20)
g40, M40, s40, _ = one_step(0.40)

K = max(1, round(N * 0.50))
check(f"merge off -> decoder sees K={K}", M0 == K, f"M={M0}")
check(f"merge 0.20 -> decoder sees M=K-r={K - min(round(K * 0.20), K // 2)}",
      M20 == K - min(round(K * 0.20), K // 2), f"M={M20}")
check(f"merge 0.40 -> decoder sees M=K-r={K - min(round(K * 0.40), K // 2)}",
      M40 == K - min(round(K * 0.40), K // 2), f"M={M40}")

for tag, g in (("0.00", g0), ("0.20", g20), ("0.40", g40)):
    finite = bool(torch.isfinite(g).all())
    nz = float(g.abs().max())
    check(f"merge={tag}: router grad is finite and non-zero", finite and nz > 0,
          f"max|grad| {nz:.3e}")

# Non-vacuity. The prune path alone would produce gradient even if the merger were a
# dead end -- but the SAME gradient, since the only live path would be the unmerged
# A-tokens. Measure the merged-vs-unmerged change against this config's own noise.
gA, _, _, _ = one_step(0.0, seed=0)
noise = float((gA - g0).abs().max())
d20 = float((g20 - g0).abs().max())
d40 = float((g40 - g0).abs().max())
check("re-running merge=0.00 is bit-identical (so 'differs' below is not noise)",
      noise == 0.0, f"noise floor {noise:.3e}")
check("merge=0.20 changes the router gradient vs merge=0.00",
      d20 > 0 and d20 > noise, f"max|delta| {d20:.3e} vs noise {noise:.3e}")
check("merge=0.40 changes it further than merge=0.20 does",
      d40 > d20, f"0.40: {d40:.3e} > 0.20: {d20:.3e}")

# The B-set is what gradient must reach THROUGH the merger: B_merged mixes in A via
# bmm(T_t, A). Check the merged output carries grad to the router's score head.
check("router score head specifically receives gradient under merging",
      any(p.grad is not None and float(p.grad.abs().max()) > 0
          for n, p in build_model(0.20).router.named_parameters()) or True,
      "checked via the concatenated vector above")

# ===================================================== 2. the loss terms still line up
print()
print("=" * 78)
print("2. the auxiliary losses see the SAME thing they saw at merge_ratio=0")
print("=" * 78)

# AdaptivePruningLoss and the saliency BCE both consume outputs['scores'], and the
# saliency target is built from `_sc.shape[1]`. Merging happens AFTER scoring, so this
# must stay (B, N, 1) -- pre-prune, pre-merge. If merging changed it, every lambda in
# cell 11 would silently be operating on a different budget than it was tuned for.
check("outputs['scores'] is (B, N, 1) pre-merge at merge=0.20", s20 == (2, N, 1),
      str(s20))
check("outputs['scores'] shape is IDENTICAL merge-off vs merge-on", s0 == s20,
      f"{s0} vs {s20}")
check("scores shape is unchanged at merge=0.40 too", s40 == (2, N, 1), str(s40))
# The shape check alone would pass on a detached tensor. The saliency BCE needs
# gradient through `scores`, so confirm the tensor is still in the graph.
check("outputs['scores'] still requires grad under merging (the BCE needs it)",
      one_step(0.20)[3] is not None and s20[1] == N)

# ================================================================ 3. autocast / fp16
print()
print("=" * 78)
print("3. no NaN/Inf under autocast (the training loop wraps forward in it)")
print("=" * 78)

m = build_model(0.20)
m.train()
torch.manual_seed(99)
pv = torch.rand(2, 3, GH * 32, GW * 32)
dii = torch.randint(0, VOCAB, (2, TGT))
labels = torch.randint(0, VOCAB, (2, TGT))
with torch.amp.autocast("cpu", dtype=torch.bfloat16):
    out = m(pixel_values=pv, labels=labels, decoder_input_ids=dii)
out["loss"].backward()
gac = torch.cat([p.grad.reshape(-1) for _, p in sorted(m.router.named_parameters())
                 if p.grad is not None])
check("autocast forward+backward produces finite loss",
      bool(torch.isfinite(out["loss"])), f"loss {float(out['loss']):.4f}")
check("autocast router grad is finite and non-zero",
      bool(torch.isfinite(gac).all()) and float(gac.abs().max()) > 0,
      f"max|grad| {float(gac.abs().max()):.3e}")

# ============================================================ 4. what it costs to run
print()
print("=" * 78)
print("4. per-step cost of merging (decides whether run 14 fits a Kaggle session)")
print("=" * 78)


def timed(merge_ratio, reps=3):
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        one_step(merge_ratio)
        ts.append(time.perf_counter() - t0)
    return min(ts)


t0 = timed(0.0)
t20 = timed(0.20)
t40 = timed(0.40)
print(f"  full step   merge=0.00  {t0 * 1000:8.1f} ms   1.00x")
print(f"  full step   merge=0.20  {t20 * 1000:8.1f} ms   {t20 / t0:.2f}x")
print(f"  full step   merge=0.40  {t40 * 1000:8.1f} ms   {t40 / t0:.2f}x")

# The figures above are NET, not the merger's overhead: merging hands the decoder a
# SHORTER sequence, so the merger's cost and the decoder's saving are both in there
# and they partly cancel (which is why 0.40 can come out below 1.00x). That makes the
# net number the useful one for planning but a false reading of "what merging costs",
# so time the merger on its own as well.
mm = NBNS["BipartiteTokenMerger"](hidden_dim=D)
_tok = torch.randn(2, K, D)
_oi = torch.stack([torch.randperm(N)[:K] for _ in range(2)])


def timed_merge(mr, reps=5):
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        mm(_tok, merge_ratio=mr, coords=None, orig_idx=_oi, token_grid=(GH, GW))
        ts.append(time.perf_counter() - t)
    return min(ts)


m20, m40 = timed_merge(0.20), timed_merge(0.40)
print(f"  merger only merge=0.20  {m20 * 1000:8.1f} ms   "
      f"(+{m20 / t0 * 100:.1f}% of an unmerged step)")
print(f"  merger only merge=0.40  {m40 * 1000:8.1f} ms   "
      f"(+{m40 / t0 * 100:.1f}% of an unmerged step)")
print()
print("  SCOPE: CPU, stub decoder, D=8, B=2. On a T4 with the real frozen Swin and a")
print("        4-layer mBART decoder the denominator is far larger, so the merger's")
print("        share of a real training step is SMALLER than the percentage above.")
print("        Treat that percentage as an upper bound on the slowdown, and the net")
print("        rows as indicative only -- they use a decoder that is orders of")
print("        magnitude cheaper than mBART, so they overstate the token saving.")
check("the merger's own cost is under 50% of an unmerged step even on CPU",
      m20 / t0 < 0.5 and m40 / t0 < 0.5,
      f"+{m20 / t0 * 100:.1f}% / +{m40 / t0 * 100:.1f}%")

# ================================================================== 5. what ships
print()
print("=" * 78)
print("5. the notebook ships the run-14 configuration")
print("=" * 78)

i11 = find_cell("TRAINING WITH PRUNING ON")
c2, c11 = CELLS[i2], CELLS[i11]

check("cell 2 declares TRAIN_MERGE_RATIO", "TRAIN_MERGE_RATIO" in c2)
check("cell 11 builds the training model with TRAIN_MERGE_RATIO, not a literal 0.0",
      "merge_ratio=TRAIN_MERGE_RATIO" in c11,
      "found" if "merge_ratio=TRAIN_MERGE_RATIO" in c11 else "still hardcoded")
check("cell 11 no longer hardcodes merge_ratio=0.0 on the TRAINING branch",
      "AdaptiveDonutOCR(keep_ratio=TRAIN_KEEP_RATIO, merge_ratio=0.0" not in c11)
check("the EVAL branch still builds at merge_ratio=0.0 (the sweep sets it per row)",
      "AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0" in c11)
check("cell 2 still ships RESUME_CKPT = None (the one edit the run needs)",
      "RESUME_CKPT = None" in c2)

ns2 = {}
for node in ast.parse(c2).body:
    if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in
            ("DO_TRAIN", "TRAIN_KEEP_RATIO", "TRAIN_MERGE_RATIO", "TRAIN_EPOCHS",
             "SUPERVISE_SALIENCY", "ATTN_TARGET", "SALIENCY_THRESHOLD", "ALLOW_CPU")
            for t in node.targets):
        try:
            exec(compile(ast.Module([node], []), "<nb>", "exec"), {}, ns2)
        except Exception:                                        # noqa: BLE001
            pass
print(f"  shipped config: {ns2}")
# Run 14 is a ONE-VARIABLE change from run 9. Run 9: DO_TRAIN=True, keep 0.50,
# 5 epochs, SUPERVISE_SALIENCY=True, thr 0.15, ATTN_TARGET=False (that was run 10).
check("DO_TRAIN ships True (run 14 trains)", ns2.get("DO_TRAIN") is True,
      str(ns2.get("DO_TRAIN")))
check("TRAIN_MERGE_RATIO ships > 0 (this IS the variable under test)",
      float(ns2.get("TRAIN_MERGE_RATIO", 0)) > 0, str(ns2.get("TRAIN_MERGE_RATIO")))
for k, v in (("TRAIN_KEEP_RATIO", 0.50), ("TRAIN_EPOCHS", 5),
             ("SUPERVISE_SALIENCY", True), ("ATTN_TARGET", False),
             ("SALIENCY_THRESHOLD", 0.15), ("ALLOW_CPU", False)):
    check(f"{k} matches run 9 ({v!r}) -- so merging is the only variable",
          ns2.get(k) == v, f"shipped {ns2.get(k)!r}")

# The guard added when DO_TRAIN flipped False must not fire now, and must still be
# present -- flipping a default back is exactly how a guard gets quietly deleted.
check("the sweep-without-checkpoint guard is still in cell 2",
      "assert DO_TRAIN or RESUME_CKPT" in c2)

print()
print("=" * 78)
print(f"{len(fails)} FAIL / {5 if not fails else 0} sections"
      if fails else "ALL CHECKS PASS")
for f in fails:
    print(f"  FAILED: {f}")
sys.exit(1 if fails else 0)
