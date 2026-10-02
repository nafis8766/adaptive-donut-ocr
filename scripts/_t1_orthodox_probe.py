"""Throwaway probe: stress-test the ORTHODOX (mean + Student-t + tail-overlay) T1 draft.
Reads only cached artifacts in `run 13/` and `run14/`. No GPU, no model, no network.
"""
import json, math, os
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R13 = json.load(open(os.path.join(HERE, "run 13", "ablation_selection.json"), encoding="utf-8"))
R14 = json.load(open(os.path.join(HERE, "run14", "ablation_selection.json"), encoding="utf-8"))
r13 = {r["config"]: r for r in R13["rows"]}
r14 = {r["config"]: r for r in R14["rows"]}


def rec(row):                     # recall in pts, higher better
    return np.array([pi["recall"] * 100.0 for pi in row["per_image"]])


def ned_raw(row):                 # ned in native units, LOWER better
    return np.array([pi["ned"] for pi in row["per_image"]])


def cacc(row):                    # charAcc-scale, pts, higher better = -100*ned
    return np.array([-100.0 * pi["ned"] for pi in row["per_image"]])


def tmean(d, g=0.10):
    s = np.sort(d); k = int(math.floor(len(s) * g))
    return float(np.mean(s[k:len(s) - k]))


def winsd(d, g=0.10):
    s = np.sort(d); n = len(s); k = int(math.floor(n * g))
    if k == 0:
        return float(np.std(s, ddof=1))
    w = np.concatenate([np.repeat(s[k], k), s[k:n - k], np.repeat(s[n - k - 1], k)])
    return float(np.std(w, ddof=1))


def res_tm(d, g=0.10):
    return 1.96 * winsd(d, g) / ((1 - 2 * g) * math.sqrt(len(d)))


def tci(d):
    n = len(d); m = float(np.mean(d)); s = float(np.std(d, ddof=1))
    se = s / math.sqrt(n); h = stats.t.ppf(0.975, n - 1) * se
    p = 2 * stats.t.sf(abs(m / se), n - 1) if se > 0 else 1.0
    return m, s, se, h, m - h, m + h, p


def boot_pct(d, b=20000, seed=0):
    rng = np.random.default_rng(seed)
    n = len(d)
    idx = rng.integers(0, n, size=(b, n))
    ms = d[idx].mean(axis=1)
    return float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))


CON = [
    ("13 m0.40-m0.00",        r13, "keep=0.50 m=0.40 router", "keep=0.50 router"),
    ("13 m0.20-m0.00",        r13, "keep=0.50 m=0.20 router", "keep=0.50 router"),
    ("13 m0.20@k1.00",        r13, "keep=1.00 m=0.20 router", "keep=1.00 router CONTROL"),
    ("13 m0.20@k0.35",        r13, "keep=0.35 m=0.20 router", "keep=0.35 router"),
    ("13 M=3840 mrg-prn",     r13, "keep=1.00 m=0.20 router", "keep=0.80 router TWIN"),
    ("13 M=1920 mrg-prn",     r13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN"),
    ("13 M=1344 mrg-prn",     r13, "keep=0.35 m=0.20 router", "keep=0.28 router TWIN"),
    ("13 M=1440 mrg-prn",     r13, "keep=0.50 m=0.40 router", "keep=0.30 router TWIN"),
    ("13 M=1344 ink mrg-prn", r13, "keep=0.35 m=0.20 ink",    "keep=0.28 ink TWIN"),
    ("13 M=1920 ink mrg-prn", r13, "keep=0.50 m=0.20 ink",    "keep=0.40 ink TWIN"),
    ("13 SABOTAGE ckb-rnkp",  r13, "keep=0.50 m=0.20 router", "keep=0.50 m=0.20 RANKPAR"),
    ("13 NEGATED ctl",        r13, "keep=0.50 NEGATED",       "keep=0.50 router"),
    ("14 m0.40-m0.00",        r14, "keep=0.50 m=0.40 router", "keep=0.50 router"),
    ("14 m0.20-m0.00",        r14, "keep=0.50 m=0.20 router", "keep=0.50 router"),
    ("14 m0.20@k1.00",        r14, "keep=1.00 m=0.20 router", "keep=1.00 router CONTROL"),
    ("14 m0.20@k0.35",        r14, "keep=0.35 m=0.20 router", "keep=0.35 router"),
    ("14 M=1440 mrg-prn",     r14, "keep=0.50 m=0.40 router", "keep=0.30 router TWIN"),
    ("14 M=1920 mrg-prn",     r14, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN"),
    ("14 M=1920 ink mrg-prn", r14, "keep=0.50 m=0.20 ink",    "keep=0.40 ink TWIN"),
    ("14 SABOTAGE ckb-rnkp",  r14, "keep=0.50 m=0.20 router", "keep=0.50 m=0.20 RANKPAR"),
    ("14 NEGATED ctl",        r14, "keep=0.50 NEGATED",       "keep=0.50 router"),
]

print("=" * 124)
print("A. GOVERNING Student-t vs pre-registered percentile bootstrap, on RECALL (pts).  t*_{.975,49}=%.4f"
      % stats.t.ppf(0.975, 49))
print("=" * 124)
print(f"{'contrast':22s} {'mean':>7s} {'sd':>6s} {'t_h':>5s} {'t_CI':>18s} {'t_p':>8s} "
      f"{'boot_CI':>18s} {'agree?':>7s} {'trim':>7s} {'TMres':>6s}")
tp_recall = {}
for lab, R, a, b in CON:
    d = rec(R[a]) - rec(R[b])
    m, s, se, h, lo, hi, p = tci(d)
    blo, bhi = boot_pct(d)
    tex = (lo > 0) or (hi < 0)
    bex = (blo > 0) or (bhi < 0)
    tp_recall[lab] = p
    print(f"{lab:22s} {m:+7.2f} {s:6.2f} {h:5.2f} [{lo:+7.2f},{hi:+7.2f}] {p:8.4f} "
          f"[{blo:+7.2f},{bhi:+7.2f}] {'same' if tex == bex else '*DIFF*':>7s} "
          f"{tmean(d):+7.2f} {res_tm(d):6.2f}")

print()
print("=" * 124)
print("B. SAME on charAcc scale (-100*ned, pts, higher better) + HOLM over the 2 storable quantities")
print("=" * 124)
print(f"{'contrast':22s} {'cA_mean':>8s} {'cA_t_h':>7s} {'cA_t_CI':>18s} {'cA_t_p':>9s} | "
      f"{'rec_p':>8s} {'HOLM rec':>9s} {'HOLM cA':>9s} {'m=3 rec':>9s}")
for lab, R, a, b in CON:
    dc = cacc(R[a]) - cacc(R[b])
    m, s, se, h, lo, hi, p = tci(dc)
    pr = tp_recall[lab]
    ps = sorted([("rec", pr), ("cA", p)], key=lambda t: t[1])
    adj = {}
    run = 0.0
    for j, (k, pv) in enumerate(ps):
        run = max(run, pv * (2 - j))
        adj[k] = min(1.0, run)
    # what Holm over THREE quantities would do to recall if a 3rd quantity existed
    ps3 = sorted([pr, p, 1.0])
    run3 = 0.0; adj3 = {}
    for j, pv in enumerate(ps3):
        run3 = max(run3, pv * (3 - j)); adj3[pv] = min(1.0, run3)
    print(f"{lab:22s} {m:+8.2f} {h:7.2f} [{lo:+7.2f},{hi:+7.2f}] {p:9.5f} | {pr:8.4f} "
          f"{adj['rec']:9.4f} {adj['cA']:9.4f} {adj3[pr]:9.4f}")

print()
print("=" * 124)
print("C. THE DRAFT'S QUOTED NEGATED-CONTROL Student-t CI  [-69.43, -58.53]  -- does it reproduce?")
print("=" * 124)
for lab in ("13 NEGATED ctl", "14 NEGATED ctl"):
    _, R, a, b = next(c for c in CON if c[0] == lab)
    d = rec(R[a]) - rec(R[b])
    m, s, se, h, lo, hi, p = tci(d)
    print(f"{lab}: mean {m:+.2f} sd {s:.2f} Student-t CI [{lo:+.2f}, {hi:+.2f}]  half-width {h:.2f}   "
          f"D13 published (bootstrap) [-69.17, -58.67]")
    print(f"    trimmed {tmean(d):+.2f}  TM res {res_tm(d):.2f}  (D13: trim res 6.09 WIDER than mean res 5.31)")

print()
print("=" * 124)
print("D. TAIL OVERLAY  count(delta < -10) >= 3  OR  min < -20  -- how often does it fire?")
print("   recall pts | charAcc pts (-100*ned) | NED native units (what the rule literally says)")
print("=" * 124)
print(f"{'contrast':22s} {'REC n<-10':>9s} {'n<=-10':>7s} {'min':>8s} {'FIRE':>5s} || "
      f"{'cA n<-10':>9s} {'cA min':>8s} {'FIRE':>5s} || {'NEDraw min':>10s} {'FIRE':>5s} | n500_cnt")
fires_r = fires_c = fires_n = 0
for lab, R, a, b in CON:
    d = rec(R[a]) - rec(R[b])
    dc = cacc(R[a]) - cacc(R[b])
    dn = ned_raw(R[a]) - ned_raw(R[b])          # native NED delta, LOWER-better metric
    cr = int((d < -10).sum()); crE = int((d <= -10).sum())
    cc = int((dc < -10).sum())
    cn = int((dn < -10).sum())
    fr = (cr >= 3) or (d.min() < -20)
    fc = (cc >= 3) or (dc.min() < -20)
    fn = (cn >= 3) or (dn.min() < -20)
    fires_r += fr; fires_c += fc; fires_n += fn
    print(f"{lab:22s} {cr:9d} {crE:7d} {d.min():8.2f} {'FIRE' if fr else '  --':>5s} || "
          f"{cc:9d} {dc.min():8.2f} {'FIRE' if fc else '  --':>5s} || "
          f"{dn.min():10.4f} {'FIRE' if fn else '  --':>5s} | {cr*10:5d}")
print(f"\n  overlay fires: recall {fires_r}/{len(CON)}   charAcc {fires_c}/{len(CON)}   "
      f"NED-native {fires_n}/{len(CON)}")

print()
print("=" * 124)
print("E. TIES / GRANULARITY -- exact zeros and documents sitting EXACTLY on a threshold")
print("=" * 124)
for lab, R, a, b in CON:
    d = rec(R[a]) - rec(R[b])
    z = int((np.abs(d) < 1e-9).sum())
    on10 = int((np.abs(d + 10.0) < 1e-9).sum())
    on20 = int((np.abs(d + 20.0) < 1e-9).sum())
    near10 = int((np.abs(d + 10.0) < 0.05).sum())
    near20 = int((np.abs(d + 20.0) < 0.05).sum())
    if z or on10 or on20 or near10 or near20:
        print(f"{lab:22s} zeros={z:2d}  exactly -10: {on10}  exactly -20: {on20}  "
              f"within 0.05 of -10: {near10}  of -20: {near20}")

print()
print("=" * 124)
print("F. RECENTRED-NULL TYPE-I CALIBRATION at n=50 and n=500 (the draft's CALIBRATION GATE)")
print("   gate: two-sided t <= 6.0% AND each one-sided <= 3.5%, else demote/UNDERPOWERED")
print("=" * 124)
M_OUT, B_IN = 4000, 400
rng = np.random.default_rng(12345)
t50 = stats.t.ppf(0.975, 49)
print(f"{'contrast':22s} {'skew':>6s} {'kurt':>6s} | {'t 2sided':>9s} {'t up':>6s} {'t lo':>6s} | "
      f"{'boot2s':>7s} {'boott2s':>8s} | {'n500 t2s':>9s} {'n500 up':>8s} {'n500 lo':>8s} | GATE@50")
for lab, R, a, b in CON:
    if lab not in ("13 m0.40-m0.00", "13 m0.20-m0.00", "13 M=1920 mrg-prn", "13 M=1440 mrg-prn",
                   "14 m0.40-m0.00", "14 SABOTAGE ckb-rnkp", "13 NEGATED ctl"):
        continue
    d = rec(R[a]) - rec(R[b])
    d0 = d - d.mean()
    n = len(d0)
    sk = float(stats.skew(d0)); ku = float(stats.kurtosis(d0))
    # ---- n=50
    idx = rng.integers(0, n, size=(M_OUT, 50))
    samp = d0[idx]
    mb = samp.mean(axis=1); sb = samp.std(axis=1, ddof=1); seb = sb / math.sqrt(50)
    up = mb - t50 * seb > 0
    lo_ = mb + t50 * seb < 0
    t2 = float((up | lo_).mean()); tu = float(up.mean()); tl = float(lo_.mean())
    # percentile bootstrap + bootstrap-t on a subset of outer samples
    SUB = 1200
    bex = 0; btex = 0
    for j in range(SUB):
        s0 = samp[j]
        ii = rng.integers(0, 50, size=(B_IN, 50))
        bm = s0[ii].mean(axis=1)
        blo, bhi = np.percentile(bm, [2.5, 97.5])
        if blo > 0 or bhi < 0:
            bex += 1
        bs = s0[ii].std(axis=1, ddof=1) / math.sqrt(50)
        tstars = np.sort((bm - s0.mean()) / np.where(bs > 0, bs, 1e-12))
        qlo, qhi = np.percentile(tstars, [2.5, 97.5])
        m0 = s0.mean(); se0 = s0.std(ddof=1) / math.sqrt(50)
        clo, chi = m0 - qhi * se0, m0 - qlo * se0
        if clo > 0 or chi < 0:
            btex += 1
    # ---- n=500
    t500 = stats.t.ppf(0.975, 499)
    idx5 = rng.integers(0, n, size=(M_OUT, 500))
    s5 = d0[idx5]
    m5 = s5.mean(axis=1); se5 = s5.std(axis=1, ddof=1) / math.sqrt(500)
    up5 = m5 - t500 * se5 > 0
    lo5 = m5 + t500 * se5 < 0
    gate = "PASS" if (t2 <= 0.060 and tu <= 0.035 and tl <= 0.035) else "**FAIL**"
    print(f"{lab:22s} {sk:6.2f} {ku:6.2f} | {t2*100:8.2f}% {tu*100:5.2f}% {tl*100:5.2f}% | "
          f"{bex/SUB*100:6.2f}% {btex/SUB*100:7.2f}% | {float((up5|lo5).mean())*100:8.2f}% "
          f"{float(up5.mean())*100:7.2f}% {float(lo5.mean())*100:7.2f}% | {gate}")

print()
print("=" * 124)
print("G. n=500 (10x replicate of the same per-doc distribution): does mean vs trim ever RESOLVE OPPOSITE?")
print("=" * 124)
print(f"{'contrast':22s} {'mean':>7s} {'t_h@500':>8s} {'mean sig':>9s} | {'trim':>7s} "
      f"{'TMres@500':>10s} {'trim sig':>9s} | {'CLASH':>7s}")
for lab, R, a, b in CON:
    d = rec(R[a]) - rec(R[b])
    d5 = np.tile(d, 10)
    m, s, se, h, lo, hi, p = tci(d5)
    tm = tmean(d5); th = res_tm(d5)
    msig = "SIG" if (lo > 0 or hi < 0) else "null"
    tsig = "SIG" if abs(tm) > th else "null"
    clash = "**YES**" if (msig == "SIG" and tsig == "SIG" and (m > 0) != (tm > 0)) else (
        "signflip" if (m > 0) != (tm > 0) else "")
    print(f"{lab:22s} {m:+7.2f} {h:8.2f} {msig:>9s} | {tm:+7.2f} {th:10.2f} {tsig:>9s} | {clash:>7s}")

print()
print("=" * 124)
print("H. HOLM half-width inflation: does res<=delta*=2.0 survive a Bonferroni-level interval?")
print("=" * 124)
for n in (50, 125, 500):
    tu = stats.t.ppf(0.975, n - 1); tb = stats.t.ppf(1 - 0.05 / 6, n - 1)
    for sd in (11.28, 12.94, 12.81):
        print(f"  n={n:3d} sd={sd:5.2f}  unadj h={tu*sd/math.sqrt(n):5.2f}  "
              f"alpha/3 h={tb*sd/math.sqrt(n):5.2f}  inflation {tb/tu:.3f}  "
              f"unadj{'<=' if tu*sd/math.sqrt(n)<=2 else '> '}2.0  "
              f"adj{'<=' if tb*sd/math.sqrt(n)<=2 else '> '}2.0")

print()
print("=" * 124)
print("I. RUN-17 SPECIFICITY: the merge gain minus the random-selection gain (run14-run13, paired)")
print("=" * 124)
for nm, cfg in (("m=0.40 trained", "keep=0.50 m=0.40 router"), ("random (no merge)", "keep=0.50 random"),
                ("ink oracle (no merge)", "keep=0.50 ink ORACLE"), ("keep=1.00 CONTROL", "keep=1.00 router CONTROL")):
    g = rec(r14[cfg]) - rec(r13[cfg])
    m, s, se, h, lo, hi, p = tci(g)
    print(f"  {nm:24s} gain {m:+6.2f}  t CI [{lo:+6.2f},{hi:+6.2f}]  t_p {p:.4f}")
gm = rec(r14["keep=0.50 m=0.40 router"]) - rec(r13["keep=0.50 m=0.40 router"])
gr = rec(r14["keep=0.50 random"]) - rec(r13["keep=0.50 random"])
m, s, se, h, lo, hi, p = tci(gm - gr)
print(f"  {'SPECIFICITY (merge-random)':24s} {m:+6.2f}  t CI [{lo:+6.2f},{hi:+6.2f}]  t_p {p:.4f}  "
      f"half-width {h:.2f}")
