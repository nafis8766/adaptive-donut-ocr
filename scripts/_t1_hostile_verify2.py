"""Does the gate's demotion target (Johnson skewness-corrected t) actually fix the rate it demotes for?"""
import json, math, os
import numpy as np
from scipy import stats
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r13 = {r["config"]: r for r in json.load(open(os.path.join(HERE,"run 13","ablation_selection.json"),encoding="utf-8"))["rows"]}
r14 = {r["config"]: r for r in json.load(open(os.path.join(HERE,"run14","ablation_selection.json"),encoding="utf-8"))["rows"]}
def rec(row): return np.array([pi["recall"]*100.0 for pi in row["per_image"]])
CON=[("13 m0.20-m0.00",r13,"keep=0.50 m=0.20 router","keep=0.50 router"),
     ("13 M=1920 mrg-prn",r13,"keep=0.50 m=0.20 router","keep=0.40 router TWIN"),
     ("14 m0.40-m0.00",r14,"keep=0.50 m=0.40 router","keep=0.50 router"),
     ("13 m0.40-m0.00",r13,"keep=0.50 m=0.40 router","keep=0.50 router")]
M=20000; rng=np.random.default_rng(7)
print("Recentred-null type-I of Student-t vs Johnson-corrected t, n=50, M=%d outer draws"%M)
print("gate: two-sided <=6.0%, each one-sided <=3.5%")
print(f"{'contrast':20s} | {'t 2s':>6s} {'t up':>6s} {'t lo':>6s} {'gate':>6s} | {'J 2s':>6s} {'J up':>6s} {'J lo':>6s} {'gate':>6s} | {'|shift|':>8s} {'as % of h':>9s}")
for lab,R,a,b in CON:
    d=rec(R[a])-rec(R[b]); d0=d-d.mean(); n=len(d0)
    idx=rng.integers(0,n,size=(M,50)); s=d0[idx]
    m=s.mean(axis=1); sd=s.std(axis=1,ddof=1); se=sd/math.sqrt(50)
    tc=stats.t.ppf(0.975,49)
    up=(m-tc*se>0); lo=(m+tc*se<0)
    mu3=((s-m[:,None])**3).mean(axis=1); shift=mu3/(6*sd**2*50)
    mj=m+shift
    upj=(mj-tc*se>0); loj=(mj+tc*se<0)
    g1="PASS" if ((up|lo).mean()<=.06 and up.mean()<=.035 and lo.mean()<=.035) else "FAIL"
    g2="PASS" if ((upj|loj).mean()<=.06 and upj.mean()<=.035 and loj.mean()<=.035) else "FAIL"
    h=tc*d.std(ddof=1)/math.sqrt(50); sh=abs(mu3.mean()/(6*d.var(ddof=1)*50))
    print(f"{lab:20s} | {(up|lo).mean()*100:5.2f}% {up.mean()*100:5.2f}% {lo.mean()*100:5.2f}% {g1:>6s} | "
          f"{(upj|loj).mean()*100:5.2f}% {upj.mean()*100:5.2f}% {loj.mean()*100:5.2f}% {g2:>6s} | {sh:8.3f} {100*sh/h:8.2f}%")
print()
print("Draft's headline numbers vs the per-contrast spread (from _t1_orthodox_probe.py section F):")
tt=[4.42,7.05,6.30,4.55,4.78,5.90,4.47]; bb=[8.17,8.92,8.25,6.92,5.75,9.67,6.58]; btt=[9.58,10.33,6.67,7.75,4.25,13.17,8.17]
print(f"  Student-t: draft says ~5.4%  | measured mean {np.mean(tt):.2f}%  min {min(tt)}%  MAX {max(tt)}% (> its own 6.0% gate)")
print(f"  pct boot : draft says ~7.4%  | measured mean {np.mean(bb):.2f}%  min {min(bb)}%  max {max(bb)}%")
print(f"  boot-t   : draft says ~8.3%  | measured mean {np.mean(btt):.2f}%  min {min(btt)}%  max {max(btt)}%")
