#!/usr/bin/env python
"""T1 scratch probe 2 (2026-09-23) -- does a HARM-EXCESS RATE gate separate where an
absolute harm ceiling and a p-value gate both fail, and does it survive n=500?

tau = 10 pts is not invented here: diagnose_merge_power.py's section_variance already
prints "documents moving >10 pts either way" as its own descriptive statistic.

n=500 is modelled the way D13 section 4 models it -- same distribution, more documents
-- by replicating each contrast's delta vector 10x. That is not new data and is not a
claim about run 17; it is a scale-stability test of the RULE.
"""
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagnose_merge_power import (  # noqa: E402
    load_rows, RUN13, RUN14, build_contrasts, trimmed_mean, res_trimmed,
    boot_ci, excludes_zero,
)

TAU = 10.0
BAR = 0.10          # harm-excess rate bar, in fraction of documents
B = 20_000
SEED = 0


def counts(d, tau=TAU):
    """Inclusive on both sides: a document that lost exactly tau pts lost tau pts."""
    h = sum(1 for x in d if x <= -tau)
    g = sum(1 for x in d if x >= +tau)
    return h, g


def harm_excess(d, tau=TAU):
    h, g = counts(d, tau)
    return (h - g) / len(d)


def binom_two_sided(h, g):
    m = h + g
    if m == 0:
        return 1.0
    k = min(h, g)
    tail = sum(math.comb(m, i) for i in range(0, k + 1)) / 2.0 ** m
    return min(1.0, 2.0 * tail)


def boot_lo_one_sided(d, stat, b=B, seed=SEED):
    """One-sided 95% lower bound, percentile bootstrap over documents, same RNG
    convention as diagnose_merge_power.boot_ci (random.Random, index 0.05*b)."""
    import random
    rnd = random.Random(seed)
    n = len(d)
    vals = sorted(stat([d[rnd.randrange(n)] for _ in range(n)]) for _ in range(b))
    return vals[int(0.05 * b)]


r13, r14 = load_rows(RUN13), load_rows(RUN14)
contrasts = build_contrasts(r13, r14)

print(f"{'contrast':34s} {'kind':9s} | {'H':>3s} {'G':>3s} {'HE%':>7s} {'HE_lo95%':>8s}"
      f" {'binom_p':>8s} {'VETO':>5s} | {'n=500 HE%':>9s} {'lo95%':>7s} {'p':>8s} {'VETO':>5s}")
print("-" * 132)
fires_50, fires_500 = {}, {}
for label, d, kind in contrasts:
    h, g = counts(d)
    he = harm_excess(d)
    lo = boot_lo_one_sided(d, harm_excess)
    p = binom_two_sided(h, g)
    veto = (he >= BAR) and (lo > 0.0)

    d5 = list(d) * 10
    h5, g5 = counts(d5)
    he5 = harm_excess(d5)
    lo5 = boot_lo_one_sided(d5, harm_excess)
    p5 = binom_two_sided(h5, g5)
    veto5 = (he5 >= BAR) and (lo5 > 0.0)

    fires_50[label] = (veto, kind)
    fires_500[label] = (veto5, kind)
    print(f"{label:34s} {kind:9s} | {h:3d} {g:3d} {100*he:+7.1f} {100*lo:+8.1f} {p:8.4f} "
          f"{'FIRE' if veto else '-':>5s} | {100*he5:+9.1f} {100*lo5:+7.1f} {p5:8.4f} "
          f"{'FIRE' if veto5 else '-':>5s}")

print("\n--- what a P-VALUE gate would do instead (the alternative I am rejecting) ---")
for label, d, kind in contrasts:
    h, g = counts(d)
    d5 = list(d) * 10
    h5, g5 = counts(d5)
    print(f"  {label:34s} {kind:9s} p(n=50) {binom_two_sided(h,g):7.4f} "
          f"-> p(n=500) {binom_two_sided(h5,g5):9.6f}  "
          f"{'FIRES ON A PUBLISHED NULL' if kind=='null_ctl' and binom_two_sided(h5,g5)<=0.05 else ''}")

print("\n--- location branch, and whether UNDERPOWERED preempts a resolved effect ---")
TIGHT = 1.5
for label, d, kind in contrasts:
    for n_lbl, dd in (("n=50", list(d)), ("n=500", list(d) * 10)):
        tm, r_ = trimmed_mean(dd), res_trimmed(dd)
        lo, hi = boot_ci(dd, trimmed_mean, b=4000)
        sig = excludes_zero(lo, hi)
        if sig:
            v = "COSTS" if tm < 0 else "GAINS"
        elif r_ <= TIGHT:
            v = "TIGHT NULL"
        else:
            v = "UNDERPOWERED"
        if n_lbl == "n=500" or kind != "merge":
            print(f"  {label:34s} {kind:9s} {n_lbl:5s} trim {tm:+7.2f} res_tm {r_:5.2f} "
                  f"CI[{lo:+6.2f},{hi:+6.2f}] -> {v}")

print("\nSUMMARY")
print("  n=50 : veto fires on", [l.strip() for l, (v, k) in fires_50.items() if v])
print("  n=50 : veto SILENT on all null_ctl?",
      all(not v for v, k in fires_50.values() if k == "null_ctl"))
print("  n=50 : veto FIRES on huge_ctl?",
      all(v for v, k in fires_50.values() if k == "huge_ctl"))
print("  n=500: veto SILENT on all null_ctl?",
      all(not v for v, k in fires_500.values() if k == "null_ctl"))
print("  n=500: veto FIRES on huge_ctl?",
      all(v for v, k in fires_500.values() if k == "huge_ctl"))
