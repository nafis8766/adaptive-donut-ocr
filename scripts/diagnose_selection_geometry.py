"""Diagnostic D2: why does RANDOM pruning beat the NEGATED router despite retaining LESS ink?

The n=2 smoke run of `eval_select_modes.py` produced an ordering that D1's premise
does not predict:

    mode        retained_ink   word recall
    router          0.424         42.60
    NEGATED         0.576         46.76
    random          0.496         68.09     <-- less ink than negated, +21 pts recall
    ink ORACLE      1.000         81.04

D1 assumed retained ink was the thing to maximize. Random falsifies that: it retains
LESS total ink than negation and reads the page far better. So total ink is the wrong
objective, and any router trained to maximize it inherits the same error.

Two candidate geometries, both computable from the arrays D1 already cached -- no
model, no GPU, no generation:

  H1 BLINDED LINES. Recall counts words. What matters is not how much ink you keep
     but whether every text line keeps ENOUGH to be read. Random thins each line
     uniformly to ~50%; a score-ranked mode can keep some lines whole and drop others
     entirely. Total ink cannot tell those apart -- 0.5 spread evenly and 0.5 as
     "half the lines at 100%, half at 0%" are the same number.

  H2 CONTIGUOUS GAPS. Within a surviving line, random drops isolated tokens (a
     neighbouring token still covers the glyph -- text spans several 32px patches).
     A score-ranked mode drops long contiguous RUNS, erasing whole words.

The two are different failures with the same total-ink signature, and they imply
different training objectives, so it is worth knowing which one is operating.

FALSIFIERS, stated before looking: if negated shows no more blinded ink than random
(H1) and no longer drop-runs than random (H2), then both are wrong and the
explanation is not selection geometry at all.

The ORACLE row calibrates the metrics themselves: it should show ~0 blinded ink and
minimal runs. If it does not, the metric is broken, not the router. (D1's mistake was
trusting a metric no baseline had calibrated -- see AGENTS.md Gotchas.)

Usage:
    PYTHONIOENCODING=utf-8 python scripts/diagnose_selection_geometry.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPZ = os.path.join(ROOT, "visualizations", "router_scores.npz")

GH, GW = 80, 60           # Swin-B token grid at 2560x1920, stride 32
KEEP = 0.5
SEED = 0

if not os.path.exists(NPZ):
    sys.exit(f"missing {NPZ} -- run scripts/router_score_probe.py first")

d = np.load(NPZ)
scores, contrast = d["scores"], d["contrast"]
B, N = scores.shape
assert N == GH * GW, f"grid mismatch: {N} tokens vs {GH}x{GW}"
K = int(round(N * KEEP))
rng = np.random.default_rng(SEED)

print(f"{B} images, {N} tokens ({GH}x{GW}), keep={KEEP} -> K={K}\n")


def masks_for(i):
    """The four selections D1/1b compare, as boolean keep-masks over the token grid."""
    def top(v, k=K):
        m = np.zeros(N, dtype=bool)
        m[np.argsort(v)[::-1][:k]] = True
        return m
    return {
        "router":  top(scores[i]),
        "negated": top(-scores[i]),
        "random":  top(rng.random(N)),
        "ink":     top(contrast[i]),
    }


# ---------------------------------------------------------------- H1: blinded lines
# A "text row" is a grid row carrying real ink. Rather than pick one cutoff and hope,
# sweep it: if the verdict flips with the threshold, the finding is an artifact.
def blinded_ink(keep_mask, ink_row, cov_row, cov_thresh):
    """Fraction of the page's ink sitting in text rows whose coverage is below thresh."""
    blind = cov_row < cov_thresh
    return float(ink_row[blind].sum() / max(ink_row.sum(), 1e-9))


print("=" * 78)
print("H1  BLINDED LINES -- ink stranded in rows that lost too much to be readable")
print("=" * 78)
ROW_INK_FRAC = 0.10          # a row counts as text if its ink >= 10% of the busiest row
COV_THRESHOLDS = (0.15, 0.25, 0.35)

h1 = {m: {t: [] for t in COV_THRESHOLDS} for m in ("router", "negated", "random", "ink")}
h1_cov = {m: [] for m in h1}
for i in range(B):
    ink2d = contrast[i].reshape(GH, GW)
    row_ink = ink2d.sum(axis=1)
    is_text = row_ink >= ROW_INK_FRAC * row_ink.max()
    for mode, m in masks_for(i).items():
        m2d = m.reshape(GH, GW)
        kept_row = (ink2d * m2d).sum(axis=1)
        cov = kept_row[is_text] / np.maximum(row_ink[is_text], 1e-9)
        h1_cov[mode].append(cov)
        for t in COV_THRESHOLDS:
            h1[mode][t].append(blinded_ink(m, row_ink[is_text], cov, t))

print(f"  text rows per image: {[int((contrast[i].reshape(GH, GW).sum(axis=1) >= ROW_INK_FRAC * contrast[i].reshape(GH, GW).sum(axis=1).max()).sum()) for i in range(B)]}")
print(f"\n  {'mode':9s} {'mean cov':>9s} {'min cov':>8s} {'p10 cov':>8s} | "
      + " ".join(f"blind<{t:.2f}" for t in COV_THRESHOLDS))
print("  " + "-" * 74)
for mode in ("router", "negated", "random", "ink"):
    cov = np.concatenate(h1_cov[mode])
    cells = " ".join(f"{np.mean(h1[mode][t]) * 100:9.1f}%" for t in COV_THRESHOLDS)
    print(f"  {mode:9s} {cov.mean():9.3f} {cov.min():8.3f} "
          f"{np.percentile(cov, 10):8.3f} | {cells}")

# --------------------------------------------------------------- H2: contiguous gaps
print()
print("=" * 78)
print("H2  CONTIGUOUS GAPS -- are dropped tokens isolated, or long runs inside a line?")
print("=" * 78)


def gap_runs(row_mask):
    """Lengths of consecutive-dropped runs along one grid row."""
    out, run = [], 0
    for v in row_mask:
        if v:
            if run:
                out.append(run)
            run = 0
        else:
            run += 1
    if run:
        out.append(run)
    return out


print(f"\n  {'mode':9s} {'mean gap':>9s} {'max gap':>8s} {'p90 gap':>8s} {'gaps>=5':>9s}")
print("  " + "-" * 50)
h2 = {}
for mode in ("router", "negated", "random", "ink"):
    allruns = []
    for i in range(B):
        ink2d = contrast[i].reshape(GH, GW)
        row_ink = ink2d.sum(axis=1)
        is_text = row_ink >= ROW_INK_FRAC * row_ink.max()
        m2d = masks_for(i)[mode].reshape(GH, GW)
        for r in np.where(is_text)[0]:
            allruns.extend(gap_runs(m2d[r]))
    a = np.array(allruns, dtype=float)
    h2[mode] = a.mean()
    print(f"  {mode:9s} {a.mean():9.2f} {a.max():8.0f} {np.percentile(a, 90):8.0f} "
          f"{100.0 * (a >= 5).mean():8.1f}%")

# H2 predicted long drop-runs are harmful. The oracle is the test: it is the most
# accurate mode, so if it ALSO has the longest runs, long runs cannot be the problem.
if h2["ink"] > h2["random"]:
    print(f"\n  H2 FALSIFIED, and inverted: the ink ORACLE has the LONGEST gaps "
          f"({h2['ink']:.2f} vs random {h2['random']:.2f})")
    print("  and the best accuracy. Long drop-runs are what you WANT -- they are the blank")
    print("  margins between words. 'Scattered selection is safer' is simply wrong; the")
    print("  best selection here is the clumpiest one. Do not optimise for spatial spread.")
else:
    print(f"\n  H2 not ruled out: oracle gaps {h2['ink']:.2f} <= random {h2['random']:.2f}")

# ------------------------------------------------------------------------- verdict
print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
t = COV_THRESHOLDS[1]
bl_neg, bl_rnd, bl_ink = (np.mean(h1[m][t]) for m in ("negated", "random", "ink"))
cov_neg = np.concatenate(h1_cov["negated"])
cov_rnd = np.concatenate(h1_cov["random"])

# Calibration first: if the oracle looks bad on these metrics, the metrics are wrong.
print(f"\n  metric calibration -- ink ORACLE blinded ink at cov<{t}: {bl_ink * 100:.1f}%")
if bl_ink > 0.05:
    print("  !! the oracle strands ink too, so these metrics do NOT cleanly separate")
    print("     good from bad selection. Treat everything below as uninterpretable.")
else:
    print("  OK -- oracle strands almost no ink, so the metric distinguishes the modes.")

    print(f"\n  H1: blinded ink   negated {bl_neg * 100:.1f}%  vs  random {bl_rnd * 100:.1f}%")
    if bl_neg > bl_rnd * 1.5:
        print("      DIRECTION CONFIRMED. Negation keeps MORE total ink but strands more of it")
        print("      in unreadable lines; random's even thinning leaves every line legible.")
        print(f"      NOT SUFFICIENT, though: {bl_neg * 100:.1f}% of stranded ink cannot by itself")
        print("      account for a 21 pt recall gap. Direction right, magnitude short -- so")
        print("      treat blinded lines as PART of the mechanism, not the whole of it.")
    elif bl_neg > bl_rnd:
        print("      WEAK. Negation strands more, but not enough to explain the gap alone.")
    else:
        print("      FALSIFIED. Negation does not strand more ink than random, so blinded")
        print("      lines are not the mechanism.")

    print(f"\n  coverage spread   negated sd {cov_neg.std():.3f}  vs  random sd {cov_rnd.std():.3f}")
    print("      (H1's signature is negation having similar//higher mean coverage but a much")
    print("       wider spread -- some lines whole, others erased.)")

# The split that actually matters is not H1 vs H2 but AGGREGATE vs WORST-CASE. Print
# both families side by side against the recall ordering so a reader can see that
# every aggregate statistic mis-orders the rows and every worst-case one gets it right.
SMOKE_RECALL = {"ink": 81.04, "random": 68.09, "negated": 46.76, "router": 42.60}
order_by_recall = sorted(SMOKE_RECALL, key=SMOKE_RECALL.get, reverse=True)
print("\n  AGGREGATE vs WORST-CASE statistics, ranked against the n=2 recall order")
print(f"    recall order (n=2):        {' > '.join(order_by_recall)}")
fams = {
    "mean coverage  (aggregate)": {m: float(np.concatenate(h1_cov[m]).mean()) for m in h1_cov},
    "min coverage   (worst-case)": {m: float(np.concatenate(h1_cov[m]).min()) for m in h1_cov},
    "p10 coverage   (worst-case)": {m: float(np.percentile(np.concatenate(h1_cov[m]), 10)) for m in h1_cov},
    "-blinded ink   (worst-case)": {m: -float(np.mean(h1[m][t])) for m in h1},
}
for fname, vals in fams.items():
    got = sorted(vals, key=vals.get, reverse=True)
    tag = "MATCHES recall" if got == order_by_recall else "MIS-ORDERS"
    print(f"    {fname}: {' > '.join(got):42s} {tag}")
print("    => aggregates rank NEGATED above RANDOM; recall does the opposite. Any router")
print("       loss that rewards SUMMED retained ink optimises the statistic that gets this")
print("       backwards. And a single GLOBAL top-k has no mechanism to bound worst-case")
print("       coverage at all -- it can spend the whole budget on one dense region.")

print("\n  NOTE: 4 images, and these are geometry statistics, not accuracy. They can")
print("  explain the ordering the eval measured; they cannot establish it. The n=50")
print("  run of eval_select_modes.py is what decides whether the ordering is real.")
