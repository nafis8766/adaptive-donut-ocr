"""Hostile-review verification for the ORTHODOX T1 draft. Throwaway, reads cached artifacts only."""
import json, math, os
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r13 = {r["config"]: r for r in json.load(open(os.path.join(HERE, "run 13", "ablation_selection.json"), encoding="utf-8"))["rows"]}
r14 = {r["config"]: r for r in json.load(open(os.path.join(HERE, "run14", "ablation_selection.json"), encoding="utf-8"))["rows"]}

def fld(row, k):
    return np.array([pi[k] for pi in row["per_image"]])

CON = [
    ("13 m0.40-m0.00", r13, "keep=0.50 m=0.40 router", "keep=0.50 router", -3.86, 3.57),
    ("13 m0.20-m0.00", r13, "keep=0.50 m=0.20 router", "keep=0.50 router", +0.54, 3.07),
    ("14 m0.40-m0.00", r14, "keep=0.50 m=0.40 router", "keep=0.50 router", -0.28, 3.95),
    ("13 M=1920 mrg-prn", r13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN", +2.86, 3.10),
    ("13 M=3840 mrg-prn", r13, "keep=1.00 m=0.20 router", "keep=0.80 router TWIN", +3.12, 2.90),
]

print("=" * 110)
print("1. UNITS AS STORED. per_image fields are FRACTIONS in [0,1]; the file's prose is in pts.")
print("=" * 110)
k0 = list(r13.keys())[0]
print("   per_image keys, run13:", sorted(r13[k0]["per_image"][0].keys()))
print("   run13 row0 per_image[0]:", {k: v for k, v in r13[k0]["per_image"][0].items() if k in ("recall", "ned")})
print()
print(f"   {'contrast':20s} | {'NATIVE (as stored)':>34s} | {'x100 (pts)':>22s}")
print(f"   {'':20s} | {'mean':>8s} {'res_z':>8s} {'POWERED?':>15s} | {'mean':>8s} {'res_z':>8s}")
for lab, R, a, b, _, _ in CON:
    for key in ("recall",):
        d = fld(R[a], key) - fld(R[b], key)
        rz = 1.96 * d.std(ddof=1) / math.sqrt(len(d))
        print(f"   {lab:20s} | {d.mean():+8.4f} {rz:8.4f} {'res<=2.0 -> YES':>15s} | "
              f"{d.mean()*100:+8.2f} {rz*100:8.2f}")
print()
print("   NED as stored (native, LOWER better) -- the family member the draft KEEPS:")
for lab, R, a, b, _, _ in CON:
    d = fld(R[a], "ned") - fld(R[b], "ned")
    rz = 1.96 * d.std(ddof=1) / math.sqrt(len(d))
    print(f"   {lab:20s} | mean {d.mean():+8.4f} res {rz:8.4f} -> res<=delta*=2.0 ? "
          f"{'YES (POWERED, always)' if rz <= 2.0 else 'no'}   worst-doc min {d.min():+8.4f} "
          f"(tail needs < -20) fires={'YES' if (d.min() < -20 or (d < -10).sum() >= 3) else 'NO'}")
print()
print("   Max conceivable res for a quantity bounded in [0,1] at n=50: "
      f"{1.96*0.5/math.sqrt(50):.4f} pts -- delta*=2.0 can never bind.")

print()
print("=" * 110)
print("2. D13 CALIBRATION CLASH: adopting Student-t as the governing half-width vs RES_TOL=0.10")
print("   scripts/diagnose_merge_power.py section 1 EXITS 1 if |res - published| > 0.10")
print("=" * 110)
print(f"   {'contrast':20s} {'pub res (z)':>12s} {'z res':>8s} {'t res':>8s} {'|t-pub|':>8s} {'verdict':>10s}")
nfail = 0
for lab, R, a, b, pm, pr in CON:
    d = (fld(R[a], "recall") - fld(R[b], "recall")) * 100.0
    se = d.std(ddof=1) / math.sqrt(len(d))
    rz, rt = 1.96 * se, stats.t.ppf(0.975, len(d) - 1) * se
    bad = abs(rt - pr) > 0.10
    nfail += bad
    print(f"   {lab:20s} {pr:12.2f} {rz:8.2f} {rt:8.2f} {abs(rt-pr):8.3f} {'**FAIL**' if bad else 'pass':>10s}")
print(f"   -> {nfail}/5 published rows would FAIL D13's own calibration gate if res is restated as Student-t.")

print()
print("=" * 110)
print("3. JOHNSON SKEWNESS-CORRECTED SHIFT (the gate's demotion target): mu3/(6 s^2 n)")
print("=" * 110)
print(f"   {'contrast':20s} {'mean':>8s} {'skew':>7s} {'shift':>8s} {'shift/res':>10s} {'direction':>28s}")
for lab, R, a, b, _, _ in CON:
    d = (fld(R[a], "recall") - fld(R[b], "recall")) * 100.0
    n = len(d)
    mu3 = ((d - d.mean()) ** 3).mean()
    s2 = d.var(ddof=1)
    shift = mu3 / (6 * s2 * n)
    rt = stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / math.sqrt(n)
    print(f"   {lab:20s} {d.mean():+8.2f} {stats.skew(d):+7.2f} {shift:+8.3f} {shift/rt:10.3f} "
          f"{('moves CI DOWN (toward DEGRADED)' if shift < 0 else 'moves CI UP (toward IMPROVED)'):>28s}")

print()
print("=" * 110)
print("4. POWERED gate ambiguity: unadjusted vs Holm-worst-case half-width at delta*=2.0")
print("=" * 110)
for sd in (11.28, 12.81, 12.94):
    lo = hi = None
    for n in range(50, 600):
        hu = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
        hb = stats.t.ppf(1 - 0.05 / 3, n - 1) * sd / math.sqrt(n)
        if lo is None and hu <= 2.0:
            lo = n
        if hi is None and hb <= 2.0:
            hi = n
    print(f"   sd={sd:5.2f}: POWERED at n>={lo} on the UNADJUSTED interval, "
          f"but only at n>={hi} on the Holm(alpha/3) interval -> ambiguity window n in [{lo},{hi-1}] "
          f"({hi-lo} documents wide)")
print("   Plausible pooled n from T2 candidates: FUNSD 50 + CORD ~100 = ~150; + SROIE ~347 = ~397.")

print()
print("=" * 110)
print("5. TAIL OVERLAY at pooled n: count(<-10)>=3 is a COUNT, so it scales with n")
print("=" * 110)
for lab, R, a, b, _, _ in CON:
    d = (fld(R[a], "recall") - fld(R[b], "recall")) * 100.0
    c = int((d < -10).sum())
    print(f"   {lab:20s} n=50 count={c:3d} min={d.min():+7.2f} | expected count at n=150: {c*3:4d} "
          f"at n=397: {round(c*7.94):4d}  -> threshold 3 crossed by chance alone")

print()
print("=" * 110)
print("6. DEGRADED vs UNDERPOWERED are NOT mutually exclusive when the gate fails")
print("=" * 110)
d = (fld(r13["keep=0.50 m=0.20 router"], "recall") - fld(r13["keep=0.40 router TWIN"], "recall")) * 100.0
d5 = np.tile(d, 10)
m, s = d5.mean(), d5.std(ddof=1)
h = stats.t.ppf(0.975, len(d5) - 1) * s / math.sqrt(len(d5))
print(f"   13 M=1920 at n=500 (10x replicate): mean {m:+.2f} t-CI [{m-h:+.2f},{m+h:+.2f}] h={h:.2f}")
print(f"   CI excludes zero -> DEGRADED/IMPROVED condition met (does NOT require POWERED).")
print(f"   Gate measured FAIL on this contrast (t 2-sided 6.30% > 6.0%, one-sided lower 5.22% > 3.5%)")
print(f"   -> UNDERPOWERED condition ALSO met ('gate could not certify'), and it is the DEFAULT branch.")
print(f"   No precedence rule is given. Same data, two admissible verdicts.")
print(f"   Note |mean| {abs(m):.2f} < delta* 2.0 is NOT required by DEGRADED/IMPROVED either.")
