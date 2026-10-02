#!/usr/bin/env python
"""T1 (2026-09-23) -- EXECUTABLE DRAFT of Pending 18's rule, run against D13's own
control set before any run-17 number exists.

This is the enforceability check, not the deliverable. It answers: can the rule as
worded be computed by a script, does it behave as claimed on the ten contrasts D13
already pinned, and is every free parameter load-bearing (mutation test)?
"""
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagnose_merge_power import (  # noqa: E402
    load_rows, RUN13, RUN14, build_contrasts, trimmed_mean, res_trimmed,
    res_trimmed_naive, arr, paired,
)

# ------------------------------------------------------------ FROZEN CONSTANTS
TRIM_G        = 0.10     # trim fraction each tail (diagnose_merge_power.TRIM_G)
TAU_PTS       = 10.0     # tail radius, POINTS, inclusive both sides
HE_BAR        = 0.10     # harm-excess rate bar (fraction of documents)
DELTA_STAR    = 1.5      # materiality AND tight-null bar, POINTS
ALPHA         = 0.05
BOOT_B        = 20_000
BOOT_SEED     = 0
RES_AGREE_TOL = 0.50     # |res_tm - bootstrap half-width| must stay under this


def boot_mat(d, b=BOOT_B, seed=BOOT_SEED):
    rng = np.random.default_rng(seed)
    a = np.asarray(d, dtype=float)
    return a[rng.integers(0, a.size, size=(b, a.size))]


def boot_ci_trim(d, b=BOOT_B, seed=BOOT_SEED):
    m = boot_mat(d, b, seed)
    k = int(math.floor(m.shape[1] * TRIM_G))
    s = np.sort(m, axis=1)[:, k:m.shape[1] - k]
    vals = s.mean(axis=1)
    return float(np.percentile(vals, 100 * ALPHA / 2)), float(np.percentile(vals, 100 * (1 - ALPHA / 2))), vals


def asl(vals):
    """Achieved significance level -- the dual of zero-exclusion. Two-sided."""
    n = vals.size
    return min(1.0, 2.0 * min((vals <= 0).sum(), (vals >= 0).sum()) / n)


def tail_counts(d, tau=TAU_PTS, inclusive=True):
    if inclusive:
        return sum(1 for x in d if x <= -tau), sum(1 for x in d if x >= tau)
    return sum(1 for x in d if x < -tau), sum(1 for x in d if x > tau)


def harm_excess(d, tau=TAU_PTS, inclusive=True):
    h, g = tail_counts(d, tau, inclusive)
    return (h - g) / len(d)


def he_lower_bound(d, b=BOOT_B, seed=BOOT_SEED, tau=TAU_PTS, inclusive=True):
    m = boot_mat(d, b, seed)
    if inclusive:
        he = ((m <= -tau).sum(axis=1) - (m >= tau).sum(axis=1)) / m.shape[1]
    else:
        he = ((m < -tau).sum(axis=1) - (m > tau).sum(axis=1)) / m.shape[1]
    return float(np.percentile(he, 100 * ALPHA))       # one-sided 95% lower bound


def holm(ps):
    """Holm-Bonferroni adjusted p-values, order preserved."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, (len(ps) - r) * ps[i])
        out[i] = min(1.0, run)
    return out


# ------------------------------------------------------------------- decide()
SEVERITY = ["HARNESS FAULT", "TAIL-HARM", "COSTS", "GAINS (NOT SPECIFIC)",
            "UNDERPOWERED", "TIGHT NULL", "GAINS (MERGE-SPECIFIC)"]


def decide_quantity(d, *, res_fn=res_trimmed, inclusive=True, delta_star=DELTA_STAR,
                    he_bar=HE_BAR, claim_side_p=None, specific=None, faults=()):
    """Verdict for ONE quantity of the ONE primary contrast. First match wins."""
    n = len(d)
    tm = trimmed_mean(d, TRIM_G)
    res_tm = res_fn(d, TRIM_G)
    lo, hi, vals = boot_ci_trim(d)
    boot_half = (hi - lo) / 2.0
    h, g = tail_counts(d, TAU_PTS, inclusive)
    he = harm_excess(d, TAU_PTS, inclusive)
    he_lo = he_lower_bound(d, inclusive=inclusive)
    p = asl(vals) if claim_side_p is None else claim_side_p

    disclosure = dict(n=n, trim=tm, res_tm=res_tm, lo=lo, hi=hi, boot_half=boot_half,
                      worst=min(d), p10=sorted(d)[int(0.10 * n)], H=h, G=g, he=he,
                      he_lo=he_lo, asl=p, zeros=sum(1 for x in d if abs(x) < 1e-9))

    # 1. HARNESS FAULT -- suppresses the verdict, never adjudicates
    if faults or abs(res_tm - boot_half) > RES_AGREE_TOL:
        return "HARNESS FAULT", disclosure

    excl = lo * hi > 0.0
    material = abs(tm) >= delta_star

    # The tail gate is a MODIFIER, not a terminal branch. Making it terminal swallowed
    # the -64 pt control's COSTS verdict (measured 2026-09-23) and threw away the
    # location information on every contrast where both resolve.
    tail_fires = (he >= he_bar) and (he_lo > 0.0)
    disclosure["tail_fires"] = tail_fires

    # 2. COSTS -- harm side, UNCORRECTED, but must be material
    if excl and material and tm < 0:
        return ("COSTS (+TAIL-HARM)" if tail_fires else "COSTS"), disclosure
    # 3. TAIL-HARM -- the gate fired and the location did NOT resolve. This is the
    #    branch that makes fact 6 unpublishable as a null.
    if tail_fires:
        return "TAIL-HARM", disclosure
    # 4. GAINS -- claim side, Holm-corrected, merging-specific, tail gate silent
    if excl and material and tm > 0 and p <= ALPHA:
        return ("GAINS (MERGE-SPECIFIC)" if specific else "GAINS (NOT SPECIFIC)"), disclosure
    # 5. TIGHT NULL -- an equivalence statement, needs the resolution to back it.
    #    Annotated when zero is excluded, so "tight null" can never be read as "no effect".
    if not material and res_tm <= delta_star:
        return ("TIGHT NULL (sign resolved)" if excl else "TIGHT NULL"), disclosure
    # 6. UNDERPOWERED -- the default branch, the else
    return "UNDERPOWERED", disclosure


# -------------------------------------------------------------------- harness
r13, r14 = load_rows(RUN13), load_rows(RUN14)
contrasts = build_contrasts(r13, r14)

_c = _f = 0


def say(ok, msg):
    global _c, _f
    _c += 1
    if not ok:
        _f += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    return ok


def run_all(scale=1, **kw):
    out = {}
    for label, d, kind in contrasts:
        out[label] = (decide_quantity(list(d) * scale, **kw), kind)
    return out


for scale, nlbl in ((1, "n=50"), (10, "n=500 (D13 s4 same-variance model)")):
    print(f"\n=== VERDICTS, {nlbl} " + "=" * 40)
    print(f"{'contrast':34s} {'kind':9s} {'trim':>7s} {'res_tm':>6s} {'bhalf':>6s} "
          f"{'CI':>17s} {'H':>3s} {'G':>3s} {'HE%':>6s} {'lo%':>6s} {'worst':>7s} -> verdict")
    res = run_all(scale, specific=True)
    for label, ((v, D), kind) in res.items():
        print(f"{label:34s} {kind:9s} {D['trim']:+7.2f} {D['res_tm']:6.2f} {D['boot_half']:6.2f} "
              f"[{D['lo']:+7.2f},{D['hi']:+7.2f}] {D['H']:3d} {D['G']:3d} {100*D['he']:+6.1f} "
              f"{100*D['he_lo']:+6.1f} {D['worst']:+7.2f} -> {v}")

    print()
    nulls = [v for (v, _), k in res.values() if k == "null_ctl"]
    huge = [v for (v, _), k in res.values() if k == "huge_ctl"]
    say(all(v.startswith("TIGHT NULL") or v == "UNDERPOWERED" for v in nulls),
        f"3 published nulls stay null ({nulls})")
    say(all(v.startswith("COSTS") for v in huge),
        f"-64 pt NEGATED control resolves as COSTS, UNDERPOWERED does NOT preempt it ({huge})")
    say(all(decide_quantity(list(d) * scale, specific=True)[0] != "HARNESS FAULT"
            for _, d, _ in contrasts),
        f"res_tm agrees with the bootstrap half-width to <={RES_AGREE_TOL} pts on 10/10")
    fired = [l.strip() for l, ((v, D), _) in res.items() if D["tail_fires"]]
    silent = [l for l, ((v, D), _) in res.items() if not D["tail_fires"]]
    say(len(fired) >= 1 and len(silent) >= 1,
        f"tail gate is non-vacuous: fires on {len(fired)} ({fired}), silent on {len(silent)}")
    say(all(not D["tail_fires"] for (v, D), k in res.values() if k == "null_ctl"),
        "tail gate is SILENT on all three published nulls")

print("\n=== THE TAIL IS DISCLOSED, NOT TRIMMED " + "=" * 30)
for label, d, kind in contrasts:
    if "14 m=0.40" in label:
        (v, D), _ = (decide_quantity(d, specific=True), kind)
        say(D["worst"] < -50.0 and abs(D["trim"]) < 1.0,
            f"run 14's null still carries its {D['worst']:+.2f} pt document in the verdict "
            f"string (trim {D['trim']:+.2f}, H={D['H']}, G={D['G']}, p10={D['p10']:+.2f})")

print("\n=== UNIT CONTROL -- the hole that would have been silent " + "=" * 13)
ra, rb = r14["keep=0.50 m=0.40 router"], r14["keep=0.50 router"]
frac = [a - b for a, b in zip([p["ned"] for p in ra["per_image"]],
                              [p["ned"] for p in rb["per_image"]])]
ned_pts = paired(arr(ra, "ned"), arr(rb, "ned"))
cha_pts = [-x for x in ned_pts]
say(tail_counts(frac) == (0, 0),
    f"on the NATIVE ned fraction scale the tail gate is vacuous: H,G = {tail_counts(frac)}")
say(tail_counts(cha_pts) != (0, 0),
    f"on charAcc POINTS it is not: H,G = {tail_counts(cha_pts)}, worst {min(cha_pts):+.2f}")
say(abs(trimmed_mean(cha_pts) + trimmed_mean(ned_pts)) < 1e-9,
    f"charAcc identity holds ON THE POINTS SCALE: trim(charAcc)={trimmed_mean(cha_pts):+.4f} "
    f"== -trim(ned_pts)={-trimmed_mean(ned_pts):+.4f}  (NOT 100x out)")

print("\n=== MUTATION TESTS -- every frozen parameter must be load-bearing " + "=" * 5)
base50 = {l: v for l, ((v, _), _) in run_all(1, specific=True).items()}
base500 = {l: v for l, ((v, _), _) in run_all(10, specific=True).items()}

def mutate(name, scale, **kw):
    kw.setdefault("specific", True)
    mut = {l: v for l, ((v, _), _) in run_all(scale, **kw).items()}
    base = base50 if scale == 1 else base500
    diff = {l: (base[l], mut[l]) for l in base if base[l] != mut[l]}
    say(bool(diff), f"{name}: changes >=1 control verdict -> {list(diff.items())[:2]}")

# tau's comparator is asserted at the level it actually moves -- the COUNT. On this
# control set the +-1 document never crosses the HE bar, so asserting "the verdict
# changes" would be a control that cannot pass; it is pinned because an ambiguous
# comparator is not enforceable, NOT because it is verdict-critical here.
ties = {l: (tail_counts(d, TAU_PTS, True), tail_counts(d, TAU_PTS, False))
        for l, d, _ in contrasts}
moved = {l: v for l, v in ties.items() if v[0] != v[1]}
say(bool(moved), f"tau boundary `<=` vs `<` moves H(tau) on {len(moved)}/10 contrasts "
                 f"-> {list(moved.items())[:2]} (pinned; NOT verdict-critical at n=50)")
mutate("res_trimmed -> res_trimmed_naive    ", 1, res_fn=res_trimmed_naive)
mutate("materiality bar 1.5 -> 0.0          ", 10, delta_star=0.0)
mutate("tight-null bar 1.5 -> 3.0 (Q6 bar)  ", 1, delta_star=3.0)
# the HE bar is INERT at n=50 (the lower bound binds there) and BINDING at n=500,
# where dropping it vetoes a published null. Measured, not assumed.
mutate("HE bar 0.10 -> 0.02, at n=500       ", 10, he_bar=0.02)
mutate("specificity gate removed            ", 10, specific=False)
he_inert = {l: v for l, ((v, _), _) in run_all(1, he_bar=0.02, specific=True).items()
            if v != base50[l]}
say(not he_inert, f"...and that same mutation is INERT at n=50 ({len(he_inert)} changes) "
                  f"-- so the bar and the lower bound each bind at a different n")

print("\n=== TAIL-HARM REACHABILITY -- an unreachable branch is decorative " + "=" * 4)
# SYNTHETIC fixture, not data: a contrast that is FLAT on location and asymmetric in
# the tail. This is the case fact 6 describes, and the branch exists for it.
synth = [0.0] * 30 + [-12.0] * 10 + [+2.0] * 10
v_s, D_s = decide_quantity(synth, specific=True)
say(v_s == "TAIL-HARM",
    f"synthetic flat-but-harm-asymmetric contrast (trim {D_s['trim']:+.2f}, "
    f"H={D_s['H']}, G={D_s['G']}, HE {100*D_s['he']:+.0f}%) -> {v_s}")
v_f, D_f = decide_quantity([0.0] * 30 + [-12.0] * 10 + [+12.0] * 10, specific=True)
say(v_f != "TAIL-HARM",
    f"...and its symmetric twin (H={D_f['H']}, G={D_f['G']}) does NOT fire -> {v_f} "
    f"-- the gate is directional, not a heavy-tail detector")

print("\n=== HOLM ON THE CLAIM SIDE ONLY " + "=" * 38)
d1340 = next(d for l, d, _ in contrasts if "m=0.40" in l and l.startswith("13"))
_, _, v1 = boot_ci_trim(d1340)
p_raw = asl(v1)
print(f"  run 13 m=0.40 (a COST): raw ASL {p_raw:.4f}; Holm over 3 -> {holm([p_raw]*1+[0.5,0.9])[0]:.4f}")
say(decide_quantity(d1340, specific=True)[0].startswith("COSTS"),
    "a COST verdict is not Holm-corrected, so run 13's -3.86 is not deleted by multiplicity")

print("\n" + "=" * 96)
print(f"CONTROLS: {_c - _f}/{_c} PASS")
print("=" * 96)
sys.exit(1 if _f else 0)
