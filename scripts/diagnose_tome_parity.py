"""
diagnose_tome_parity.py — Regression check for the ToMe A/B split (Gotchas / Pending 15).

WHAT THIS MEASURES
  ToMe only merges tokens from set A into set B. A genuinely-redundant token pair
  that the split lands BOTH in A or BOTH in B can NEVER be merged. So the split
  choice is what decides which redundancy is reachable at all.

  Two splits, three redundancy geometries, two arrival orders -> a 3x2x2 table of
  "missed-redundancy rate": of the truly-redundant pairs, the fraction ToMe fails
  to merge.

WHY IT MATTERS (the history this guards against)
  * The OLD split (`arange(0,K,2)` / `arange(1,K,2)`) reads SEQUENCE position.
    Under raster order it merges horizontal neighbours fine (0.0% missed) but the
    grid is 60 wide and 60 is even, so a token and the one directly below it share
    parity -> 100.0% of VERTICAL redundancy is unreachable. And the router hands
    ToMe tokens in DESCENDING-SCORE order, not raster order, at which point even
    horizontal redundancy is ~50% missed (score rank is not spatial adjacency).
  * The NEW split is a CHECKERBOARD over ORIGINAL page position `(row+col)%2`.
    Every 4-neighbour lands in the opposite set, so horizontal AND vertical
    redundancy are 0.0% missed, and -- because colour is a function of the
    original index, not the sequence position -- this holds under ANY arrival
    order. The honest cost: diagonal-only redundancy becomes 100% missed, which
    is acceptable because every token still has four 4-neighbours in set B.

  A green run here is the pre-GPU gate: it proves the merge sweep will merge
  spatial neighbours rather than score-rank neighbours BEFORE spending a Kaggle
  session on it.

Pure numpy/torch, CPU, no model/checkpoint. Run: python scripts/diagnose_tome_parity.py
"""
import os
import sys

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the SHIPPED implementation rather than restating it here. An earlier
# version of this script defined its own `(row + col) % 2` and therefore passed
# 10/10 against a deliberately corrupted src/tome.py: it was validating a copy of
# the algorithm, not the code that runs. Same species as the rule that
# check_writeup_numbers.py does not read AGENTS.md -- prose checked against prose
# proves nothing, and an algorithm checked against its own restatement proves
# nothing either. `parity_color` below stays local ON PURPOSE: it is the OLD,
# deleted split, kept as a guard that this harness can still detect breakage.
from src.tome import checkerboard_color as _shipped_checkerboard_color

GH, GW = 80, 60          # the real Swin-B token grid
N = GH * GW
D = 64
MERGE_RATIO = 0.5        # large ratio to expose all reachable redundancy


# --------------------------------------------------------------------------- #
# Redundancy geometries. Each returns a set of frozenset({i, j}) neighbour pairs
# on the flattened GHxGW grid, and a matching feature tensor in which ONLY those
# pairs are near-identical (everything else is distinct + tiny noise).
# --------------------------------------------------------------------------- #
def _rc(i):
    return i // GW, i % GW


def horizontal_pairs():
    pairs = set()
    for r in range(GH):
        for c in range(0, GW - 1, 2):
            pairs.add(frozenset((r * GW + c, r * GW + c + 1)))
    return pairs


def vertical_pairs():
    pairs = set()
    for r in range(0, GH - 1, 2):
        for c in range(GW):
            pairs.add(frozenset((r * GW + c, (r + 1) * GW + c)))
    return pairs


def diagonal_pairs():
    pairs = set()
    for r in range(0, GH - 1, 2):
        for c in range(0, GW - 1, 2):
            pairs.add(frozenset((r * GW + c, (r + 1) * GW + c + 1)))
    return pairs


def features_for(pairs, seed=0):
    """One shared vector per pair, distinct across pairs; singletons distinct too."""
    g = torch.Generator().manual_seed(seed)
    feat = torch.randn(1, N, D, generator=g)
    for pr in pairs:
        a, b = tuple(pr)
        feat[0, b] = feat[0, a]
    feat = feat + torch.randn(1, N, D, generator=g) * 1e-3
    return feat


# --------------------------------------------------------------------------- #
# The two splits, as colour(seq_pos, orig_idx) -> {0,1}. A = colour 0.
#
# Both arguments are supplied because the two splits read DIFFERENT things, and
# that difference is the entire bug: parity reads where a token sits in the
# sequence the router handed over, checkerboard reads where it sat on the page.
# Passing only one domain to both would silently model the old split as though it
# were already fixed.
# --------------------------------------------------------------------------- #
def parity_color(seq_pos, orig_idx):
    """OLD split: even/odd of SEQUENCE position (arange(0,K,2)/arange(1,K,2)).
    Ignores orig_idx entirely -- which is precisely why it broke."""
    return seq_pos % 2


def checkerboard_color(seq_pos, orig_idx):
    """NEW split: delegates to src.tome.checkerboard_color, the shipped code.

    The two-argument signature is kept so this and `parity_color` stay
    interchangeable in the sweep below; `seq_pos` is unused because reading page
    position instead of sequence position is the entire fix.
    """
    return _shipped_checkerboard_color(orig_idx, GW)


# --------------------------------------------------------------------------- #
# Run ToMe's assignment for a given split + arrival order and recover the pairs
# it actually merged, in ORIGINAL-index space.
# --------------------------------------------------------------------------- #
def merged_pairs(feat, order, color_of_seqpos):
    """
    feat            : (1, N, D) features in ORIGINAL index order.
    order           : permutation; order[s] = original index at sequence pos s.
    color_of_seqpos : (K,) colour per SEQUENCE position, already permuted.
    Returns list of frozenset({orig_i, orig_j}) merged pairs.
    """
    toks = feat[:, order]                      # (1, K, D) in arrival order
    K = toks.shape[1]
    r = min(int(round(K * MERGE_RATIO)), K // 2)
    if r <= 0:
        return []

    seq_A = torch.nonzero(color_of_seqpos == 0, as_tuple=False).squeeze(-1)
    seq_B = torch.nonzero(color_of_seqpos == 1, as_tuple=False).squeeze(-1)
    if seq_A.numel() == 0 or seq_B.numel() == 0:
        return []
    r = min(r, seq_A.numel())

    A = F.normalize(toks[:, seq_A], p=2, dim=-1)
    Bs = F.normalize(toks[:, seq_B], p=2, dim=-1)
    sim = torch.bmm(A, Bs.transpose(1, 2))
    maxv, maxi = sim.max(dim=-1)
    _, top = torch.topk(maxv, k=r, dim=-1)
    tb = torch.gather(maxi, 1, top)

    pairs = []
    for j, ai in enumerate(top[0].tolist()):
        seq_a = seq_A[ai].item()
        seq_b = seq_B[tb[0, j].item()].item()
        pairs.append(frozenset((order[seq_a].item(), order[seq_b].item())))
    return pairs


def missed_rate(true_pairs, feat, order, color_fn):
    # Sequence position s holds original index order[s]. The split gets both, and
    # picks whichever it actually reads.
    seq_pos = torch.arange(order.numel())
    color_seq = color_fn(seq_pos, order)
    merged = set(merged_pairs(feat, order, color_seq))
    captured = sum(1 for p in true_pairs if p in merged)
    return (len(true_pairs) - captured) / len(true_pairs)


def main():
    torch.manual_seed(0)
    raster = torch.arange(N)
    score = torch.randn(N)
    router_sorted = score.argsort(descending=True)   # what actually reaches ToMe

    geometries = [
        ("horizontal", horizontal_pairs()),
        ("vertical", vertical_pairs()),
        ("diagonal", diagonal_pairs()),
    ]
    splits = [
        ("parity (OLD)", parity_color),
        ("checkerboard (NEW)", checkerboard_color),
    ]
    orders = [
        ("raster", raster),
        ("router-sorted", router_sorted),
    ]

    print("=" * 78)
    print(f" ToMe missed-redundancy rate  (grid {GH}x{GW}, merge_ratio={MERGE_RATIO})")
    print("=" * 78)
    print(f" {'split':<20} {'redundancy':<12} {'raster':>10} {'router-sorted':>16}")
    print("-" * 78)

    table = {}
    for sname, cfn in splits:
        for gname, pairs in geometries:
            feat = features_for(pairs)
            rates = {}
            for oname, order in orders:
                rates[oname] = missed_rate(pairs, feat, order, cfn)
            table[(sname, gname)] = rates
            print(f" {sname:<20} {gname:<12} "
                  f"{rates['raster']*100:>9.1f}% {rates['router-sorted']*100:>15.1f}%")
        print("-" * 78)

    # ------ automatic verdict: the properties the fix must have ---------------
    cb = "checkerboard (NEW)"
    par = "parity (OLD)"
    checks = []

    # 1. checkerboard: horizontal + vertical fully reachable under BOTH orders.
    for g in ("horizontal", "vertical"):
        for o in ("raster", "router-sorted"):
            checks.append((
                f"checkerboard {g}/{o} == 0% missed",
                table[(cb, g)][o] < 1e-9,
            ))
    # 2. checkerboard is order-independent (raster == router-sorted everywhere).
    for g in ("horizontal", "vertical", "diagonal"):
        checks.append((
            f"checkerboard {g} order-independent",
            abs(table[(cb, g)]["raster"] - table[(cb, g)]["router-sorted"]) < 1e-9,
        ))
    # 3. the documented regressions the OLD split had (guards the narrative).
    checks.append((
        "parity vertical/raster == 100% missed (the even-width bug)",
        table[(par, "vertical")]["raster"] > 0.99,
    ))
    checks.append((
        "parity horizontal degrades under router-sort (>=40% missed)",
        table[(par, "horizontal")]["router-sorted"] >= 0.40,
    ))
    # 4. the honest cost: checkerboard misses diagonal-only redundancy.
    checks.append((
        "checkerboard diagonal == 100% missed (accepted cost)",
        table[(cb, "diagonal")]["raster"] > 0.99,
    ))

    print("\nProperty checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok = all_ok and ok

    if all_ok:
        print("\n  VERDICT: checkerboard split behaves as designed. The merge sweep")
        print("  will merge spatial neighbours under the router's score-sort, and")
        print("  the old parity split's vertical/order failures are reproduced as a")
        print("  guard. Safe to queue the merge_ratio>0 sweep behind run 11.")
        return 0
    print("\n  VERDICT: FAIL. A property the checkerboard fix must hold was violated;")
    print("  do NOT spend a GPU session on the merge sweep. Investigate above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
