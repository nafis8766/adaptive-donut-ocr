"""Execution check for `stratified_scores` (Pending 1d) -- does a global top-K on the
rewritten key REALLY equal a per-row top-k?

That equivalence is the whole trick, and it is the kind of claim that fails by one
rank band and still produces a plausible-looking mask: roughly the right number of
tokens, roughly the right places, and a coverage number that looks improved. Nothing
downstream would notice. So it is checked against an INDEPENDENT reference
implementation -- an explicit per-row `topk` loop -- rather than against a restatement
of the same arithmetic.

What each section rules out:

  1. Off-by-one in the rank band. Checked as exact set equality against the loop, on
     random scores, at several keep ratios.
  2. Band bleed: a very high score in a low rank band jumping into a higher band.
     Checked with adversarial scores (one row two orders of magnitude hotter than the
     rest) -- the row-budget must hold anyway, which is the entire point.
  3. `negate` flipping something other than the within-row order.
  4. The coverage claim itself: on a synthetic page with one line the router hates,
     stratification must raise MIN line coverage where a global top-k starves it.
     If it does not, 1d is answered NO here for free and no GPU is needed.
  5. Non-divisible K degrading gracefully instead of raising or silently truncating.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_stratified.py
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


def per_row_topk_reference(scores, gh, gw, k):
    """INDEPENDENT reference: explicit per-row topk. Deliberately not clever."""
    B, N = scores.shape
    out = []
    for b in range(B):
        s2 = scores[b].reshape(gh, gw)
        idx = set()
        for r in range(gh):
            top = torch.topk(s2[r], k=k, largest=True).indices
            idx.update((r * gw + int(c)) for c in top)
        out.append(idx)
    return out


def global_topk(sel, K):
    return [set(torch.topk(sel[b], k=K, largest=True).indices.tolist())
            for b in range(sel.shape[0])]


GH, GW = 8, 6              # small but real: same 4:3 portrait shape, N=48
N = GH * GW
torch.manual_seed(0)

print("=" * 74)
print("1. global top-K on the key == per-row top-k (vs an independent reference)")
print("=" * 74)

scores = torch.rand(3, N)
for keep in (0.5, 0.25, 0.75):
    k = int(round(GW * keep))              # per-row budget
    K = GH * k                             # equivalent global budget
    key = stratified_scores(scores, grid=(GH, GW))
    got = global_topk(key, K)
    want = per_row_topk_reference(scores, GH, GW, k)
    check(f"keep={keep:.2f} (k={k}/row, K={K}): exact set match on all 3 images",
          got == want,
          f"first-image symmetric difference {len(got[0] ^ want[0])}")

# Every row must contribute exactly k -- the guarantee the whole idea rests on.
key = stratified_scores(scores, grid=(GH, GW))
K = GH * (GW // 2)
mask = torch.zeros(3, N, dtype=torch.bool)
for b in range(3):
    mask[b, torch.topk(key[b], k=K).indices] = True
counts = mask.reshape(3, GH, GW).sum(dim=-1)
check("every grid row contributes exactly k tokens",
      bool((counts == GW // 2).all()), f"row counts {counts[0].tolist()}")

print()
print("=" * 74)
print("2. adversarial scores cannot bleed across rank bands")
print("=" * 74)

# One row 100x hotter than every other. A global top-k would hand it the entire
# budget; stratification must still give it exactly k. This is the failure D2 found.
adv = torch.rand(1, N) * 0.01
adv.reshape(1, GH, GW)[0, 3, :] = torch.rand(GW) * 100.0
k = GW // 2
K = GH * k

plain = torch.zeros(N, dtype=torch.bool)
plain[torch.topk(adv[0], k=K).indices] = True
plain_counts = plain.reshape(GH, GW).sum(dim=-1)

strat = torch.zeros(N, dtype=torch.bool)
strat[torch.topk(stratified_scores(adv, grid=(GH, GW))[0], k=K).indices] = True
strat_counts = strat.reshape(GH, GW).sum(dim=-1)

check("global top-k DOES over-serve the hot row (the bug being fixed)",
      int(plain_counts[3]) == GW and int(plain_counts.max()) == GW,
      f"hot row got {int(plain_counts[3])}/{GW}; counts {plain_counts.tolist()}")
check("stratified gives the hot row exactly its budget",
      bool((strat_counts == k).all()),
      f"counts {strat_counts.tolist()}")
check("stratified starves no row", int(strat_counts.min()) == k,
      f"min row {int(strat_counts.min())} of k={k}")

print()
print("=" * 74)
print("3. negate flips the WITHIN-ROW order and nothing else")
print("=" * 74)

s = torch.rand(1, N)
hi = stratified_scores(s, grid=(GH, GW))
lo = stratified_scores(s, grid=(GH, GW), negate=True)
k = GW // 2
K = GH * k
set_hi = set(torch.topk(hi[0], k=K).indices.tolist())
set_lo = set(torch.topk(lo[0], k=K).indices.tolist())
check("stratified and stratified_negated are disjoint at keep=0.5",
      not (set_hi & set_lo), f"overlap {len(set_hi & set_lo)}")
check("their union is everything at keep=0.5", len(set_hi | set_lo) == N,
      f"{len(set_hi | set_lo)}/{N}")
neg_ref = per_row_topk_reference(-s, GH, GW, k)
check("negated matches a per-row topk of the NEGATED scores", set_lo == neg_ref[0])
lo_counts = torch.zeros(N, dtype=torch.bool)
lo_counts[list(set_lo)] = True
check("negated still respects the per-row budget",
      bool((lo_counts.reshape(GH, GW).sum(dim=-1) == k).all()))

print()
print("=" * 74)
print("4. THE POINT: does stratification actually raise worst-case line coverage?")
print("=" * 74)

# A synthetic page: every row has ink, but the scorer is inverted (it prefers the
# blank columns), and it hates row 5 in particular. A global top-k should starve
# row 5 entirely; stratification must not.
STRIDE = 32
pv = torch.full((1, 3, GH * STRIDE, GW * STRIDE), 0.9)
for r in range(GH):                        # a text-like textured band in every row
    pv[:, :, r * STRIDE + 8: r * STRIDE + 24, :] = torch.rand(1, 3, 16, GW * STRIDE)
ink = patch_ink(pv, N)

bad = ink.clone() * -1.0                   # inverted scorer: prefers low ink
bad.reshape(1, GH, GW)[0, 5, :] -= 10.0    # and especially hates row 5

k, K = GW // 2, GH * (GW // 2)


def min_row_coverage(keep_idx):
    m = torch.zeros(N, dtype=torch.bool)
    m[keep_idx] = True
    ink2 = ink[0].reshape(GH, GW)
    kept = (ink2 * m.reshape(GH, GW)).sum(dim=-1)
    return float((kept / ink2.sum(dim=-1).clamp(min=1e-9)).min())


mc_global = min_row_coverage(torch.topk(bad[0], k=K).indices)
mc_strat = min_row_coverage(
    torch.topk(stratified_scores(bad, grid=(GH, GW))[0], k=K).indices)
mc_strat_neg = min_row_coverage(
    torch.topk(stratified_scores(bad, grid=(GH, GW), negate=True)[0], k=K).indices)

print(f"  min row coverage:  global top-k {mc_global:.3f} | "
      f"stratified {mc_strat:.3f} | stratified_negated {mc_strat_neg:.3f}")
check("global top-k starves a row on this fixture (reproduces D2's 0.000)",
      mc_global < 0.01, f"{mc_global:.4f}")
check("stratification lifts min row coverage off zero", mc_strat > mc_global,
      f"{mc_global:.3f} -> {mc_strat:.3f}")
check("stratified_negated (coverage AND correct sign) is best of the three",
      mc_strat_neg > mc_strat, f"{mc_strat_neg:.3f} > {mc_strat:.3f}")
print("  NOTE: 0.492 vs 0.503 is a near-tie, and that is a property of this fixture,")
print("  not evidence that sign does not matter. Every row here carries a uniform")
print("  textured band, so ink is spread evenly across a row's columns and keeping ANY")
print("  half of them retains ~half the ink. The fixture tests the COVERAGE GUARANTEE")
print("  only. On a real page ink is clumped into words with gaps between them, so the")
print("  within-row ranking -- and therefore the sign -- should separate the two. That")
print("  is what the real eval row is for; it cannot be settled here.")

print()
print("=" * 74)
print("5. edge cases")
print("=" * 74)

check("both new modes are registered in SELECT_MODES",
      {"stratified", "stratified_negated"} <= set(SELECT_MODES), str(SELECT_MODES))
try:
    stratified_scores(torch.rand(1, N), grid=(GH, GW + 1))
    check("grid mismatch raises", False, "accepted a wrong grid")
except ValueError as e:
    check("grid mismatch raises ValueError", "token grid mismatch" in str(e))

# Non-divisible K: whole bands fill first, remainder by score. No row may exceed
# ceil(K/gh) and none may fall below floor(K/gh).
K_odd = GH * (GW // 2) + 3
m = torch.zeros(N, dtype=torch.bool)
m[torch.topk(stratified_scores(scores[:1], grid=(GH, GW))[0], k=K_odd).indices] = True
c = m.reshape(GH, GW).sum(dim=-1)
check("non-divisible K degrades gracefully (rows differ by at most 1)",
      int(c.max()) - int(c.min()) <= 1, f"K={K_odd}, row counts {c.tolist()}")

# A constant score is the degenerate case: every rank band is a tie, so the only
# requirement is that the budget is still respected.
flat = torch.full((1, N), 0.5)
m = torch.zeros(N, dtype=torch.bool)
m[torch.topk(stratified_scores(flat, grid=(GH, GW))[0], k=K).indices] = True
check("constant scores still respect the per-row budget",
      bool((m.reshape(GH, GW).sum(dim=-1) == k).all()),
      f"counts {m.reshape(GH, GW).sum(dim=-1).tolist()}")

# And it must compose with the real router end to end, not just as bare arithmetic.
router = PatchSaliencyRouter(hidden_dim=32, reduction_dim=16).eval()
tok = torch.randn(1, N, 32)
raw = router.scorer(tok).squeeze(-1)
_, _, idx, _ = router(tok, keep_ratio=0.5, use_ste=False,
                      select_scores=stratified_scores(raw, grid=(GH, GW)))
c = torch.zeros(N, dtype=torch.bool)
c[idx[0]] = True
check("composes with the real router: per-row budget survives router.forward",
      bool((c.reshape(GH, GW).sum(dim=-1) == GW // 2).all()),
      f"counts {c.reshape(GH, GW).sum(dim=-1).tolist()}")

print()
print("=" * 74)
if fails:
    print(f"{len(fails)} CHECK(S) FAILED:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED -- stratified selection is sound and does what 1d needs.")
print("=" * 74)
