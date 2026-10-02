#!/usr/bin/env python
"""T1 scratch probe (2026-09-23) -- calibrate the tail threshold against D13's own
controls BEFORE run 17 exists. Reuses diagnose_merge_power.py's estimators verbatim.

Question: at what tau does an absolute harm-count rule (a) stay quiet on the three
published nulls and (b) fire on the -64 pt NEGATED control, and is it tied on the
threshold (does < vs <= matter)?
"""
import os
import sys
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagnose_merge_power import (  # noqa: E402
    load_rows, RUN13, RUN14, build_contrasts, trimmed_mean, res_trimmed,
    res_mean, boot_ci, excludes_zero, arr, paired,
)

r13, r14 = load_rows(RUN13), load_rows(RUN14)
contrasts = build_contrasts(r13, r14)

print(f"{'contrast':34s} {'kind':9s} {'trim':>7s} {'res_tm':>7s} {'p10':>8s} {'min':>8s}"
      f" | {'H10':>4s} {'H10<=':>5s} {'G10':>4s} | {'H15':>4s} {'G15':>4s} | {'H20':>4s} {'H20<=':>5s} {'G20':>4s}")
print("-" * 140)
for label, d, kind in contrasts:
    s = sorted(d)
    p10 = s[int(0.10 * len(s))]
    def H(t, incl=False):
        return sum(1 for x in d if (x <= -t if incl else x < -t))
    def G(t, incl=False):
        return sum(1 for x in d if (x >= t if incl else x > t))
    print(f"{label:34s} {kind:9s} {trimmed_mean(d):+7.2f} {res_trimmed(d):7.2f} {p10:+8.2f} {min(d):+8.2f}"
          f" | {H(10):4d} {H(10,True):5d} {G(10):4d} | {H(15):4d} {G(15):4d} | {H(20):4d} {H(20,True):5d} {G(20):4d}")

print("\nexact ties on the round thresholds (|x| within 1e-9 of 10/15/20):")
for label, d, kind in contrasts:
    ties = [f"{x:+.4f}" for x in d if min(abs(abs(x) - t) for t in (10.0, 15.0, 20.0)) < 1e-9]
    if ties:
        print(f"  {label:34s} {kind:9s} {ties}")

print("\nzero-change documents per contrast (|delta| < 1e-9):")
for label, d, kind in contrasts:
    print(f"  {label:34s} {kind:9s} {sum(1 for x in d if abs(x) < 1e-9):2d}/{len(d)}")

print("\nNED-native scale check -- same contrast, `ned` field, NO x100:")
row_a, row_b = r14["keep=0.50 m=0.40 router"], r14["keep=0.50 router"]
dn = [a - b for a, b in zip([p["ned"] for p in row_a["per_image"]],
                            [p["ned"] for p in row_b["per_image"]])]
dnp = paired(arr(row_a, "ned"), arr(row_b, "ned"))
print(f"  ned fractions : trim {trimmed_mean(dn):+.4f}  min {min(dn):+.4f}  "
      f"#<-10 {sum(1 for x in dn if x < -10):d}  #>+10 {sum(1 for x in dn if x > 10):d}")
print(f"  ned x100 (pts): trim {trimmed_mean(dnp):+.2f}  min {min(dnp):+.2f}  "
      f"#<-10 {sum(1 for x in dnp if x < -10):d}  #>+10 {sum(1 for x in dnp if x > 10):d}")
print("  (harm direction on NED is +x, since NED is lower-better)")
print(f"  charAcc-pts = -ned_pts: trim {-trimmed_mean(dnp):+.2f}  worst {-max(dnp):+.2f}")
