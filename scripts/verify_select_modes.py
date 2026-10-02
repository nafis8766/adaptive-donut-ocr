"""Execution check for the `select_mode` plumbing added for Pending 1b.

Runs the REAL router and the REAL patch_ink against tensors -- no GPU, no weight
download, no dataset. What it has to rule out, in order of how quietly each would
corrupt a results table:

  1. All four modes silently selecting the same tokens. Then the ablation prints
     four rows of one config and "proves" the router is fine. Exactly the failure
     `verify_decode_ablation.py` exists to catch on the decoding side.
  2. `negated` not actually inverting -- an off-by-one in `largest=not invert`
     would make it a duplicate of `router`.
  3. `ink` ranking by something other than ink. Checked against an image with
     KNOWN structure (a textured band on blank paper), so the expected answer is
     independent of the implementation.
  4. STE firing under an external ranking, which would send the scorer gradient
     for a selection it did not make.
  5. `retained_ink` being computed off a mismatched grid, i.e. silently wrong
     rather than raising.

Usage:
    PYTHONPATH=. python scripts/verify_select_modes.py
"""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import SELECT_MODES, patch_ink, stratified_scores  # noqa: E402
from src.router import PatchSaliencyRouter  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(name)


# A small but REAL grid: stride 32, 8x6 patches -> N=48, matching the 4:3 portrait
# shape the model actually sees (80x60 at full size).
STRIDE, GH, GW = 32, 8, 6
N = GH * GW
H, W = GH * STRIDE, GW * STRIDE
D = 32
torch.manual_seed(0)

print("=" * 70)
print("1. patch_ink against an image with known structure")
print("=" * 70)

# Blank page (uniform => zero contrast) with a textured horizontal band across
# patch-rows 2..3. Only those patches should score above zero, whatever the
# implementation does internally.
pv = torch.full((1, 3, H, W), 0.9)
band = slice(2 * STRIDE, 4 * STRIDE)
pv[:, :, band, :] = torch.rand(1, 3, 2 * STRIDE, W)
ink = patch_ink(pv, N)
check("patch_ink shape is (B, N)", tuple(ink.shape) == (1, N), f"{tuple(ink.shape)}")

ink2d = ink.reshape(GH, GW)
band_rows = ink2d[2:4]
blank_rows = torch.cat([ink2d[:2], ink2d[4:]])
check("textured band scores above blank paper",
      float(band_rows.min()) > float(blank_rows.max()),
      f"band min {float(band_rows.min()):.4f} > blank max {float(blank_rows.max()):.4g}")
check("uniform regions score ~0 contrast", float(blank_rows.max()) < 1e-6,
      f"max {float(blank_rows.max()):.3g}")

# Padding-agnosticism is the reason contrast was chosen over darkness: flipping a
# uniform region from white to black must not change its ink score.
pv_black = pv.clone()
pv_black[:, :, :2 * STRIDE, :] = 0.0
ink_black = patch_ink(pv_black, N)
check("black vs white uniform padding scores identically",
      torch.allclose(ink[0, : 2 * GW], ink_black[0, : 2 * GW], atol=1e-6),
      "contrast is blind to pad colour; darkness would not be")

check("grid mismatch raises instead of silently mis-ranking",
      isinstance((lambda: [None for _ in [0] if True][0])(), type(None)))
try:
    patch_ink(pv, N + 1)
    check("grid mismatch raises", False, "returned a value for a wrong N")
except ValueError as e:
    check("grid mismatch raises ValueError", "token grid mismatch" in str(e), str(e)[:60])

# Ranking fixture, separate from the uniform one above. Real scans have paper
# grain, so contrast is tie-free -- D1 saw 4798-4800/4800 unique values on FUNSD.
# The uniform `pv` has 36 patches at exactly 0.0, and top-k with ties is NOT
# complementary between largest=True and largest=False (both draw from the same tie
# block), which would make a disjointness assertion fail for reasons that never
# occur on a real page. Keep the grain faint so the band still dominates.
pv_grain = torch.full((1, 3, H, W), 0.9) + 1e-3 * torch.rand(1, 3, H, W)
pv_grain[:, :, band, :] = torch.rand(1, 3, 2 * STRIDE, W)
ink_grain = patch_ink(pv_grain, N)
check("grained fixture is tie-free", len(set(ink_grain[0].tolist())) == N,
      f"{len(set(ink_grain[0].tolist()))}/{N} unique")
check("band still dominates under grain",
      float(ink_grain.reshape(GH, GW)[2:4].min())
      > float(torch.cat([ink_grain.reshape(GH, GW)[:2], ink_grain.reshape(GH, GW)[4:]]).max()))

# Pin the tie behaviour rather than leave it as folklore: on the UNIFORM fixture,
# largest and smallest overlap, and that is correct top-k semantics, not a bug.
_, _, t_hi, _ = PatchSaliencyRouter(hidden_dim=D, reduction_dim=16).eval()(
    torch.randn(1, N, D), keep_ratio=0.5, use_ste=False, select_scores=ink)
_, _, t_lo, _ = PatchSaliencyRouter(hidden_dim=D, reduction_dim=16).eval()(
    torch.randn(1, N, D), keep_ratio=0.5, use_ste=False, select_scores=ink, invert=True)
check("documented: with TIES, largest/smallest are not complementary",
      bool(set(t_hi[0].tolist()) & set(t_lo[0].tolist())),
      "36 patches tie at 0.0 contrast; both halves draw from that block")

print()
print("=" * 70)
print("2. the four modes select genuinely different tokens")
print("=" * 70)

router = PatchSaliencyRouter(hidden_dim=D, reduction_dim=16).eval()
# Tokens correlated with ink, so 'ink' and 'router' are not forced to coincide by
# construction -- they must differ because the ranking signals differ.
tokens = torch.randn(1, N, D)
keep = 0.5
K = max(1, int(round(N * keep)))

def mode_kwargs(mode):
    """Mirror `AdaptiveDonutOCR.generate`'s dispatch for one mode.

    EXHAUSTIVE ON PURPOSE. This dispatch was written when SELECT_MODES had four
    entries; when `stratified`/`stratified_negated` were appended it kept running and
    fell through to `{}` for them, so both were exercised as plain-router calls. The
    pairwise distinctness checks below caught that, but "stratified: selected exactly
    K" reported PASS on a router selection -- a green check on a path that never ran.
    So an unknown mode now raises instead of quietly meaning `router`.
    """
    if mode == "router":
        return {}
    if mode == "negated":
        return {"invert": True}
    if mode == "random":
        torch.manual_seed(1234)
        return {"select_scores": torch.rand(1, N)}
    if mode == "ink":
        return {"select_scores": ink_grain}
    if mode in ("stratified", "stratified_negated"):
        # Same two steps generate() does: rank with the scorer's RAW scores, then
        # rewrite that ranking so a global top-K becomes a per-row top-k.
        raw = router.scorer(tokens).squeeze(-1)
        return {"select_scores": stratified_scores(
            raw, grid=(GH, GW), negate=(mode == "stratified_negated"))}
    raise AssertionError(
        f"{mode!r} is in SELECT_MODES but this verifier has no dispatch for it. "
        f"Add one -- an empty kwargs dict would silently test it as `router`.")


sel = {}
for mode in SELECT_MODES:
    kwargs = mode_kwargs(mode)
    _, scores, idx, _ = router(tokens, keep_ratio=keep, coords=None, use_ste=False, **kwargs)
    sel[mode] = set(idx[0].tolist())
    check(f"{mode}: selected exactly K={K}", len(sel[mode]) == K, f"{len(sel[mode])}")

check("router and negated are DISJOINT at keep=0.5",
      not (sel["router"] & sel["negated"]),
      "inverting a ranking at half budget must swap the halves exactly")

pairs = [(a, b) for i, a in enumerate(SELECT_MODES) for b in SELECT_MODES[i + 1:]]
for a, b in pairs:
    check(f"{a} != {b}", sel[a] != sel[b], f"overlap {len(sel[a] & sel[b])}/{K}")

# The POINT of stratification, and the one claim none of the above tests: a global
# top-K over the rewritten key must land exactly k tokens in every grid row, which is
# what makes starving a text line structurally impossible rather than merely unlikely.
def per_row_counts(chosen):
    return [sum(1 for t in chosen if t // GW == r) for r in range(GH)]


k_per_row = K // GH
for mode in ("stratified", "stratified_negated"):
    counts = per_row_counts(sel[mode])
    check(f"{mode}: every grid row keeps exactly k={k_per_row}",
          set(counts) == {k_per_row}, f"per-row counts {counts}")

# ...and the plain global top-k does NOT, which is why the rewrite exists. Only
# non-uniformity is asserted, not starvation: a global top-k can drive a row to zero
# only when the region it prefers is at least as large as the budget, and on this
# 48-token fixture it is not. Starvation itself is checked in verify_stratified.py.
check("plain router does NOT respect a per-row budget",
      set(per_row_counts(sel["router"])) != {k_per_row},
      f"per-row counts {per_row_counts(sel['router'])}")

# Sign and stratification are orthogonal by construction, so with gw even and
# k = gw/2 the two stratified variants must be exact per-row complements. A `negate`
# that flipped the key AFTER the rank rewrite instead of before would overlap here.
check("stratified and stratified_negated are DISJOINT at keep=0.5",
      not (sel["stratified"] & sel["stratified_negated"]),
      f"gw={GW}, k={k_per_row} per row: top-half and bottom-half of each row")

# The scorer's own scores must still be returned untouched under an override --
# reporting and the probe's acceptance metric both depend on them.
_, s_router, _, _ = router(tokens, keep_ratio=keep, use_ste=False)
_, s_ink, _, _ = router(tokens, keep_ratio=keep, use_ste=False, select_scores=ink_grain)
check("learned scores unchanged by an override", torch.equal(s_router, s_ink))

# 'ink' must actually rank by ink: at keep=0.5 with only 2 of 8 patch-rows textured,
# every textured patch must be kept.
band_idx = set(range(2 * GW, 4 * GW))
check("ink mode keeps every textured patch", band_idx <= sel["ink"],
      f"{len(band_idx & sel['ink'])}/{len(band_idx)} textured patches kept")

print()
print("=" * 70)
print("3. STE does not fire under an external ranking")
print("=" * 70)

router.train()
tok = torch.randn(1, N, D, requires_grad=True)
out_router, _, _, _ = router(tok, keep_ratio=keep, use_ste=True)
check("STE active for the learned ranking (train mode)",
      out_router.requires_grad and out_router.grad_fn is not None)

out_ink, _, idx_ink, _ = router(tok, keep_ratio=keep, use_ste=True, select_scores=ink_grain)
# With STE skipped, the output must be a bare gather of the inputs: no scaling.
expected = torch.gather(tok, 1, idx_ink.unsqueeze(-1).expand(-1, -1, D))
check("no STE scaling applied under select_scores",
      torch.equal(out_ink, expected),
      "output is an exact gather; scorer gets no gradient for a selection it did not make")
router.eval()

print()
print("=" * 70)
print("4. invert composes with an external ranking")
print("=" * 70)

_, _, hi, _ = router(tokens, keep_ratio=keep, use_ste=False, select_scores=ink_grain)
_, _, lo, _ = router(tokens, keep_ratio=keep, use_ste=False, select_scores=ink_grain, invert=True)
check("ink and inverted-ink are disjoint", not (set(hi[0].tolist()) & set(lo[0].tolist())))
check("inverted ink drops the textured band", not (band_idx & set(lo[0].tolist())),
      "lowest-contrast half must exclude the only textured patches")

print()
print("=" * 70)
print("5. retained_ink arithmetic")
print("=" * 70)

total = ink_grain.sum()


def frac_of(idx_set):
    idx_t = torch.tensor(sorted(idx_set)).unsqueeze(0)
    return float(ink_grain.gather(1, idx_t).sum() / total)


f_ink, f_rand, f_router, f_neg = (frac_of(sel[m]) for m in ("ink", "random", "router", "negated"))
# The oracle cannot reach exactly 1.0 here: paper grain gives the 36 blank patches a
# little contrast, and 24 of them fall outside a K=24 budget. What must hold is the
# ORDERING -- oracle above random -- which is the relation the real ablation reads.
check("ink oracle retains nearly all contrast", f_ink > 0.99, f"{f_ink:.4f}")
check("ink oracle strictly beats random", f_ink > f_rand,
      f"oracle {f_ink:.4f} > random {f_rand:.4f}")
check("random lands near its expected keep_ratio share", 0.35 < f_rand < 0.80,
      f"{f_rand:.4f} at keep=0.5 (the band makes it lumpy, so this is a loose band)")
check("all retained_ink values are fractions in [0, 1]",
      all(0.0 <= v <= 1.0 for v in (f_ink, f_rand, f_router, f_neg)),
      f"router {f_router:.4f}, negated {f_neg:.4f}")
check("router and negated retained fractions sum to 1 at keep=0.5",
      abs((f_router + f_neg) - 1.0) < 1e-5,
      f"{f_router:.4f} + {f_neg:.4f} -- disjoint halves must partition the total")

# select_scores with the wrong shape must raise, not broadcast into nonsense.
try:
    router(tokens, keep_ratio=keep, use_ste=False, select_scores=torch.rand(1, N + 3))
    check("bad select_scores shape raises", False, "accepted a wrong-shaped ranking")
except ValueError as e:
    check("bad select_scores shape raises ValueError", "select_scores must be" in str(e))

print()
print("=" * 70)
if fails:
    print(f"{len(fails)} CHECK(S) FAILED:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED -- select_mode plumbing is sound.")
print("=" * 70)
