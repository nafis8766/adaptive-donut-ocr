#!/usr/bin/env python
"""D13 (2026-09-22, local, <10 s) — the ToMe blocker is the instrument, not the merger.

Re-derives, from the per-image arrays already on disk in `run 13/` and `run14/`:

  1. CALIBRATION  — reproduces five published (mean, res) pairs from the raw arrays,
                    so the variance estimates below are checked against the file
                    before anything new is read off them. If this section fails,
                    every number underneath it is void and the script exits 1.
  2. VARIANCE     — where the per-document variance actually lives. It is not
                    document length (CUPED on `n_text_rows` buys ~0%); it is a
                    handful of documents with enormous paired deltas.
  3. ESTIMATOR    — a 10% trimmed mean with a *Tukey-McLaughlin* standard error
                    against the pre-registered bootstrap-on-means, on every merge
                    contrast plus the controls that must stay null.
  4. REQUIRED n   — the n at which each contrast's CI half-width reaches a target,
                    under both estimators. This is the number that decides whether
                    Pending 16/17 can answer their questions.
  5. TAIL         — what BOTH location estimators hide. Every merge contrast contains
                    a catastrophically degraded document (-38 to -72 pts), a 10%
                    trim discards exactly those, and the trimmed mean is provably
                    INSENSITIVE to making them worse. Section 3's ~30% resolution
                    gain is real and it is bought with blindness to the tail, which
                    is the thing an accuracy-PRESERVATION claim is about.

Why this exists: runs 12, 13 and 14 each returned UNDERPOWERED as the modal verdict
on the merge axis, and three sessions read that as a fact about ToMe. It is a fact
about n=50 against a per-document sd of 11-13 pts. See AGENTS.md "Diagnostic D13".

No GPU, no model load, no network. Reads only cached run artifacts.

Usage:
    python scripts/diagnose_merge_power.py            # full report
    python scripts/diagnose_merge_power.py --selftest # controls only, fast
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics as st
import sys
from typing import Callable, Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN13 = os.path.join(HERE, "run 13", "ablation_selection.json")
RUN14 = os.path.join(HERE, "run14", "ablation_selection.json")

TRIM_G = 0.10          # trim fraction, each tail
BOOT_B = 20_000        # resamples, matching the notebook's cell 15
BOOT_SEED = 0

_n_controls = 0
_n_failed = 0


def say(ok: bool, msg: str) -> bool:
    """Record a control. Mirrors eval_kv_memory.py's counter so N/N is measured."""
    global _n_controls, _n_failed
    _n_controls += 1
    if not ok:
        _n_failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    return ok


# ---------------------------------------------------------------- data access

def load_rows(path: str) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        return {r["config"]: r for r in json.load(fh)["rows"]}


def arr(row: dict, key: str = "recall") -> List[float]:
    """Per-image metric as percentage points."""
    return [pi[key] * 100.0 for pi in row["per_image"]]


def covariate(row: dict, key: str) -> List[float]:
    return [float(pi[key]) for pi in row["per_image"]]


def paired(a: Sequence[float], b: Sequence[float]) -> List[float]:
    if len(a) != len(b):
        raise ValueError(f"unpaired arrays: {len(a)} vs {len(b)}")
    return [x - y for x, y in zip(a, b)]


# ------------------------------------------------------------- the estimators

def res_mean(d: Sequence[float]) -> float:
    """95% CI half-width of the plain mean -- the project's `res` column."""
    return 1.96 * st.stdev(d) / math.sqrt(len(d))


def trimmed_mean(d: Sequence[float], g: float = TRIM_G) -> float:
    s = sorted(d)
    k = int(math.floor(len(s) * g))
    return st.mean(s[k:len(s) - k])


def winsorized_sd(d: Sequence[float], g: float = TRIM_G) -> float:
    s = sorted(d)
    n = len(s)
    k = int(math.floor(n * g))
    if k == 0:
        return st.stdev(s)
    return st.stdev([s[k]] * k + s[k:n - k] + [s[n - k - 1]] * k)


def res_trimmed(d: Sequence[float], g: float = TRIM_G) -> float:
    """Tukey-McLaughlin 95% half-width for a trimmed mean.

    NOT stdev(trimmed values)/sqrt(len(trimmed)) -- that is the natural thing to
    write, it understates the SE by ~35% here, and it manufactured a resolved
    verdict on the M=1440 pair the first time this was computed. Control (4)
    below asserts the two disagree in that direction so the wrong formula cannot
    quietly come back.
    """
    return 1.96 * winsorized_sd(d, g) / ((1.0 - 2.0 * g) * math.sqrt(len(d)))


def res_trimmed_naive(d: Sequence[float], g: float = TRIM_G) -> float:
    """The WRONG formula, kept only so control (4) can measure the gap."""
    s = sorted(d)
    k = int(math.floor(len(s) * g))
    t = s[k:len(s) - k]
    return 1.96 * st.stdev(t) / math.sqrt(len(t))


def boot_ci(d: Sequence[float], stat: Callable[[Sequence[float]], float],
            b: int = BOOT_B, seed: int = BOOT_SEED) -> Tuple[float, float]:
    """Percentile bootstrap over documents. Endpoints are ONE DRAW -- the mean is
    deterministic, the endpoints move by ~+-0.05 pts across seeds (AGENTS.md)."""
    rnd = random.Random(seed)
    n = len(d)
    vals = sorted(stat([d[rnd.randrange(n)] for _ in range(n)]) for _ in range(b))
    return vals[int(0.025 * b)], vals[int(0.975 * b)]


def excludes_zero(lo: float, hi: float) -> bool:
    return lo * hi > 0.0


def required_n(d: Sequence[float], target: float, trimmed: bool) -> int:
    """n at which the 95% CI half-width reaches `target` pts, same variance."""
    if trimmed:
        sd_eff = winsorized_sd(d) / (1.0 - 2.0 * TRIM_G)
    else:
        sd_eff = st.stdev(d)
    return math.ceil((1.96 * sd_eff / target) ** 2)


def cuped(d: Sequence[float], x: Sequence[float]) -> Tuple[List[float], float]:
    """Variance reduction by regressing the paired delta on a document covariate."""
    mx, md = st.mean(x), st.mean(d)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0.0:
        return list(d), 0.0
    theta = sum((xi - mx) * (di - md) for xi, di in zip(x, d)) / sxx
    return [di - theta * (xi - mx) for di, xi in zip(d, x)], theta


# ------------------------------------------------------------------ contrasts

def build_contrasts(r13: Dict[str, dict], r14: Dict[str, dict]):
    """(label, deltas, kind) -- `kind` drives the controls, not the reporting.

    merge      : a real merge contrast, no pre-registered expectation here
    null_ctl   : MUST stay null under any estimator (three published nulls)
    huge_ctl   : MUST resolve under any estimator (a -64 pt effect)
    """
    def P(R, a, b):
        return paired(arr(R[a]), arr(R[b]))

    return [
        ("13 m=0.40 vs m=0.00 @keep0.50", P(r13, "keep=0.50 m=0.40 router", "keep=0.50 router"), "merge"),
        ("13 m=0.20 vs m=0.00 @keep0.50", P(r13, "keep=0.50 m=0.20 router", "keep=0.50 router"), "merge"),
        ("13 M=3840 merge vs prune",      P(r13, "keep=1.00 m=0.20 router", "keep=0.80 router TWIN"), "merge"),
        ("13 M=1920 merge vs prune",      P(r13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN"), "merge"),
        ("13 M=1344 merge vs prune",      P(r13, "keep=0.35 m=0.20 router", "keep=0.28 router TWIN"), "merge"),
        ("13 M=1440 merge vs prune",      P(r13, "keep=0.50 m=0.40 router", "keep=0.30 router TWIN"), "merge"),
        ("14 m=0.40 vs m=0.00 @keep0.50", P(r14, "keep=0.50 m=0.40 router", "keep=0.50 router"), "null_ctl"),
        ("13 SABOTAGE ckb - rank_parity", P(r13, "keep=0.50 m=0.20 router", "keep=0.50 m=0.20 RANKPAR"), "null_ctl"),
        ("14 SABOTAGE ckb - rank_parity", P(r14, "keep=0.50 m=0.20 router", "keep=0.50 m=0.20 RANKPAR"), "null_ctl"),
        ("13 NEGATED - router @keep0.50", P(r13, "keep=0.50 NEGATED", "keep=0.50 router"), "huge_ctl"),
    ]


# -------------------------------------------------------------------- section 1

# (label, row_a, row_b, published_mean, published_res) straight out of AGENTS.md
PUBLISHED = [
    ("run13 m0.40-m0.00", 13, "keep=0.50 m=0.40 router", "keep=0.50 router", -3.86, 3.57),
    ("run13 m0.20-m0.00", 13, "keep=0.50 m=0.20 router", "keep=0.50 router", +0.54, 3.07),
    ("run14 m0.40-m0.00", 14, "keep=0.50 m=0.40 router", "keep=0.50 router", -0.28, 3.95),
    ("run13 M=1920 mrg-prn", 13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN", +2.86, 3.10),
    ("run13 M=3840 mrg-prn", 13, "keep=1.00 m=0.20 router", "keep=0.80 router TWIN", +3.12, 2.90),
]

MEAN_TOL = 0.02   # the mean is deterministic; this is a transcription check
RES_TOL = 0.10    # normal-approx vs bootstrap, so a small gap is expected


def section_calibration(r13, r14) -> bool:
    print("\n[1] CALIBRATION -- reproduce published figures from the raw arrays")
    print("    If this fails, nothing below it is usable.\n")
    print(f"    {'contrast':26s} {'mean':>7s} {'pub':>7s} | {'res':>6s} {'pub':>6s}")
    ok_all = True
    for label, run, a, b, pub_m, pub_r in PUBLISHED:
        R = r13 if run == 13 else r14
        d = paired(arr(R[a]), arr(R[b]))
        m, r_ = st.mean(d), res_mean(d)
        print(f"    {label:26s} {m:+7.2f} {pub_m:+7.2f} | {r_:6.2f} {pub_r:6.2f}")
        ok_all &= say(abs(m - pub_m) <= MEAN_TOL,
                      f"{label}: mean reproduces to <={MEAN_TOL} (|d|={abs(m - pub_m):.3f})")
        ok_all &= say(abs(r_ - pub_r) <= RES_TOL,
                      f"{label}: res reproduces to <={RES_TOL} (|d|={abs(r_ - pub_r):.3f})")
    return ok_all


# -------------------------------------------------------------------- section 2

def section_variance(r13) -> bool:
    print("\n[2] VARIANCE -- where the per-document noise actually lives")
    d = paired(arr(r13["keep=0.50 m=0.40 router"]), arr(r13["keep=0.50 router"]))
    n = len(d)
    mu = st.mean(d)
    ss_tot = sum((x - mu) ** 2 for x in d)
    top5 = sorted(d, key=lambda x: -abs(x - mu))[:5]
    share = 100.0 * sum((x - mu) ** 2 for x in top5) / ss_tot

    print(f"\n    run 13, m=0.40 vs m=0.00 @ keep=0.50, n={n}")
    print(f"    mean {mu:+.2f}   median {st.median(d):+.2f}   sd {st.stdev(d):.2f}")
    print(f"    5 most extreme deltas: {['%+.1f' % x for x in top5]}")
    print(f"    their share of total sum-of-squares: {share:.1f}%")
    print(f"    documents with exactly zero change: {sum(1 for x in d if abs(x) < 1e-9)}/{n}")
    print(f"    documents moving >10 pts either way: {sum(1 for x in d if abs(x) > 10)}/{n}")

    print("\n    Is it document length? CUPED on `n_text_rows`:")
    ok_all = True
    gains = []
    for label, a, b in [("m=0.40 vs m=0.00", "keep=0.50 m=0.40 router", "keep=0.50 router"),
                        ("m=0.20 vs m=0.00", "keep=0.50 m=0.20 router", "keep=0.50 router"),
                        ("M=1920 mrg-prn", "keep=0.50 m=0.20 router", "keep=0.40 router TWIN")]:
        dd = paired(arr(r13[a]), arr(r13[b]))
        adj, theta = cuped(dd, covariate(r13[a], "n_text_rows"))
        gain = 100.0 * (1.0 - res_mean(adj) / res_mean(dd))
        gains.append(gain)
        print(f"      {label:20s} res {res_mean(dd):.2f} -> {res_mean(adj):.2f}  ({gain:+.1f}%)")

    ok_all &= say(share > 50.0,
                  f"variance is concentrated: top 5 of {n} docs carry {share:.1f}% of SS (>50%)")
    ok_all &= say(max(gains) < 10.0,
                  f"document length is NOT the driver: best CUPED gain {max(gains):+.1f}% (<10%)")
    return ok_all


# -------------------------------------------------------------------- section 3

def section_estimator(contrasts, fast: bool) -> bool:
    print("\n[3] ESTIMATOR -- bootstrap-on-means vs a 10% trimmed mean (TM standard error)")
    print("    Bootstrap endpoints are ONE DRAW (seed 0).\n")
    b = 2000 if fast else BOOT_B
    hdr = (f"    {'contrast':32s} | {'mean':>6s} {'res':>5s} {'CI':>16s} {'x0':>3s}"
           f" | {'trim':>6s} {'res':>5s} {'CI':>16s} {'x0':>3s}")
    print(hdr)
    print("    " + "-" * (len(hdr) - 4))

    ok_all = True
    rows = []
    for label, d, kind in contrasts:
        m, r_ = st.mean(d), res_mean(d)
        lo, hi = boot_ci(d, st.mean, b=b)
        tm, tr = trimmed_mean(d), res_trimmed(d)
        tlo, thi = boot_ci(d, trimmed_mean, b=b)
        x0, tx0 = excludes_zero(lo, hi), excludes_zero(tlo, thi)
        rows.append((label, kind, r_, tr, x0, tx0))
        print(f"    {label:32s} | {m:+6.2f} {r_:5.2f} [{lo:+6.2f},{hi:+6.2f}] {'YES' if x0 else 'no':>3s}"
              f" | {tm:+6.2f} {tr:5.2f} [{tlo:+6.2f},{thi:+6.2f}] {'YES' if tx0 else 'no':>3s}")

    print()
    # (1) the trimmed estimator must be tighter WHERE THE TAILS ARE HEAVY -- i.e. on
    #     the merge contrasts. It is NOT uniformly better and must not be sold as
    #     such: on the `negated` control it is WIDER (res 5.31 -> 6.09), because that
    #     contrast's deltas are a compact bulk near -64 with no outliers, and for a
    #     light-tailed sample the (1-2g) divisor costs more than Winsorizing saves.
    #     That is textbook behaviour for a trimmed mean and it is the reason this
    #     control is scoped to `merge` rather than asserted over every row -- an
    #     estimator that were tighter everywhere would be measuring nothing.
    merge_rows = [r for r in rows if r[1] == "merge"]
    tighter = sum(1 for _, _, r_, tr, _, _ in merge_rows if tr < r_)
    ok_all &= say(tighter == len(merge_rows),
                  f"trimmed res is tighter on {tighter}/{len(merge_rows)} MERGE contrasts "
                  f"(heavy-tailed, which is the case it is for)")
    wide = [(lbl, r_, tr) for lbl, kind, r_, tr, _, _ in rows if kind == "huge_ctl" and tr > r_]
    ok_all &= say(bool(wide),
                  "trimming is NOT uniformly tighter -- it is wider on the light-tailed "
                  f"control ({', '.join(f'{l}: {a:.2f}->{b:.2f}' for l, a, b in wide) or 'none'}), "
                  "which is what makes the gain above a measurement and not an artifact")

    # (2) ... and not by manufacturing significance on the published nulls
    for label, kind, _, _, x0, tx0 in rows:
        if kind == "null_ctl":
            ok_all &= say(not tx0, f"null control stays null under trimming: {label}")
            ok_all &= say(not x0, f"null control stays null under the mean:   {label}")

    # (3) ... and it must still see a real effect when there is one
    for label, kind, _, _, x0, tx0 in rows:
        if kind == "huge_ctl":
            ok_all &= say(x0 and tx0, f"huge control resolves under BOTH estimators: {label}")

    # (4) the naive trimmed SE is wrong in the permissive direction -- pin it
    d0 = contrasts[0][1]
    naive, proper = res_trimmed_naive(d0), res_trimmed(d0)
    ok_all &= say(naive < proper,
                  f"naive trimmed SE understates: {naive:.2f} < TM {proper:.2f} "
                  f"({100 * (1 - naive / proper):.0f}% too small)")

    # (5) the verdict must not be a knob -- stable across the trim fraction
    flips = 0
    for label, d, kind in contrasts:
        base = excludes_zero(*boot_ci(d, trimmed_mean, b=b))
        for g in (0.05, 0.15):
            alt = excludes_zero(*boot_ci(d, lambda s, _g=g: trimmed_mean(s, _g), b=b))
            if alt != base:
                flips += 1
                print(f"      note: {label} flips verdict at g={g}")
    ok_all &= say(flips == 0, f"verdicts stable across trim g in {{0.05,0.10,0.15}} ({flips} flips)")
    return ok_all


# -------------------------------------------------------------------- section 4

TARGETS = (3.0, 2.0, 1.5, 1.0)


def section_required_n(contrasts) -> bool:
    print("\n[4] REQUIRED n -- the n at which each contrast's CI half-width reaches a target")
    print("    Same variance, more documents. FUNSD test = 50 and is exhausted.\n")
    print(f"    {'contrast':32s} {'sd':>6s} | " + " ".join(f"{t:>11.1f}" for t in TARGETS))
    print(f"    {'':32s} {'':>6s} | " + " ".join(f"{'mean/trim':>11s}" for _ in TARGETS))
    ok_all = True
    for label, d, kind in contrasts:
        if kind != "merge":
            continue
        cells = []
        for t in TARGETS:
            cells.append(f"{required_n(d, t, False):5d}/{required_n(d, t, True):<5d}")
        print(f"    {label:32s} {st.stdev(d):6.2f} | " + " ".join(f"{c:>11s}" for c in cells))
        # monotonicity: a looser target cannot need more documents
        ns = [required_n(d, t, False) for t in TARGETS]
        ok_all &= say(all(ns[i] <= ns[i + 1] for i in range(len(ns) - 1)),
                      f"required n is monotone in target: {label}")

    # the number that decides Pending 16/17
    m1920 = next(d for lbl, d, _ in contrasts if "M=1920" in lbl)
    need = required_n(m1920, abs(st.mean(m1920)), False)
    print(f"\n    The single most consequential number in this table:")
    print(f"      M=1920 merge-vs-prune -- the question ToMe exists to answer -- observed")
    print(f"      {st.mean(m1920):+.2f} pts at res {res_mean(m1920):.2f}. To resolve its OWN effect")
    print(f"      it needed n >= {need}, and run 13 had {len(m1920)}. It missed by {need - len(m1920)} documents.")
    ok_all &= say(need > len(m1920),
                  f"M=1920 was underpowered for its own effect (needed {need}, had {len(m1920)})")
    return ok_all


# -------------------------------------------------------------------- section 5

WORST_Z = 3.5          # |z| beyond which a document is "catastrophic" for its own contrast
NORMAL_Z_CEILING = 3.0  # a light-tailed sample of this n must stay under this
TAIL_RATIO = 1.4        # how far past its own matched null a contrast's worst doc must sit


def normal_like(d: Sequence[float]) -> List[float]:
    """A DETERMINISTIC light-tailed sample with the same n, mean and sd as `d`.

    This is the null for section 5. Without it, "the worst document is 4.1 sd out"
    is unreadable -- some value is always the most extreme one. The question is
    whether it is further out than a well-behaved sample of the same size and
    spread would put it, and this is what answers that.

    Evenly-spaced normal quantiles, so there is no RNG and no seed to tune. Its
    sd is slightly below the target (quantile sampling underdisperses), which
    makes it a CONSERVATIVE null: it inflates the synthetic's own z-scores, so
    the discrimination controls below are harder to pass, not easier.
    """
    n = len(d)
    nd = st.NormalDist(st.mean(d), st.stdev(d))
    return [nd.inv_cdf((i + 0.5) / n) for i in range(n)]


def worst_z(d: Sequence[float]) -> float:
    """How many sd the most extreme document sits from the mean."""
    return max(abs(x - st.mean(d)) for x in d) / st.stdev(d)


def excess_kurtosis(d: Sequence[float]) -> float:
    n, mu, sd = len(d), st.mean(d), st.stdev(d)
    return sum(((x - mu) / sd) ** 4 for x in d) / n - 3.0


def worst_case_sensitivity(d: Sequence[float], push: float = 25.0):
    """Make the single worst document worse by `push` pts; report what each estimator does.

    This is the whole argument in one number. A trimmed mean is not merely *less*
    influenced by the tail -- for a perturbation that keeps the worst document
    worst, it is EXACTLY unchanged, because that document was never in the
    average. An estimator that cannot move when a page degrades further is the
    wrong primary for a claim that no page degrades.
    """
    i = min(range(len(d)), key=lambda j: d[j])
    d2 = list(d)
    d2[i] = d2[i] - push
    return (st.mean(d) , st.mean(d2), trimmed_mean(d), trimmed_mean(d2))


def section_tail(contrasts) -> bool:
    print("\n[5] TAIL -- what both location estimators hide")
    print("    A location statistic answers 'what happened on average'. The claim is")
    print("    'merging is free', which is a claim about EVERY document.\n")
    print(f"    {'contrast':32s} | {'mean':>6s} {'trim':>6s} {'p10':>7s} {'min':>7s}"
          f" | {'|z|max':>6s} {'kurt':>6s} | {'null |z|':>8s}")
    print("    " + "-" * 94)

    ok_all = True
    merge_rows = []
    for label, d, kind in contrasts:
        if kind == "huge_ctl":
            continue
        s = sorted(d)
        p10 = s[int(0.10 * len(s))]
        wz, kt = worst_z(d), excess_kurtosis(d)
        nz = worst_z(normal_like(d))
        merge_rows.append((label, d, wz, kt, nz))
        print(f"    {label:32s} | {st.mean(d):+6.2f} {trimmed_mean(d):+6.2f} {p10:+7.2f} {min(d):+7.2f}"
              f" | {wz:6.2f} {kt:6.2f} | {nz:8.2f}")

    # (1) the extremity is real, and it is stated RELATIVE TO ITS OWN NULL rather than
    #     against a threshold I chose after seeing the numbers. Every contrast's worst
    #     document must sit materially further out than the matched light-tailed sample
    #     of the same n, mean and sd puts its own worst document.
    ratios = [(r[0], r[2] / r[4]) for r in merge_rows]
    worst_ratio = min(x for _, x in ratios)
    ok_all &= say(worst_ratio > TAIL_RATIO,
                  f"every contrast's worst document is >{TAIL_RATIO}x further out than its "
                  f"matched-normal null's worst (min ratio {worst_ratio:.2f}, "
                  f"{min(ratios, key=lambda t: t[1])[0].strip()})")

    # (2) ... and the null itself stays put, on every contrast. Without this, (1) is
    #     decorative: the largest of n draws is always the largest, so a ratio near 1
    #     would mean nothing at all. This is what makes (1) a statement about the
    #     DISTRIBUTION rather than about the sample size.
    worst_null = max(r[4] for r in merge_rows)
    ok_all &= say(worst_null < NORMAL_Z_CEILING,
                  f"matched normal null never exceeds {NORMAL_Z_CEILING} sd "
                  f"(max {worst_null:.2f}) -- so (1) is about the tail, not about n")

    # (3) a PUBLISHED NULL hides a catastrophe. This is the finding, not a caveat.
    for label, d, kind in contrasts:
        if kind == "null_ctl" and "14 m=0.40" in label:
            ok_all &= say(abs(trimmed_mean(d)) < 1.0 and min(d) < -50.0,
                          f"'no measured cost' coexists with a {min(d):+.2f} pt document: {label} "
                          f"(trimmed mean {trimmed_mean(d):+.2f})")

    # (4) the trimmed mean is EXACTLY blind to the worst document getting worse,
    #     and the plain mean is not. Perturbation, not assertion.
    print()
    n_blind = 0
    for label, d, kind in contrasts:
        if kind != "merge":
            continue
        m0, m1, t0, t1 = worst_case_sensitivity(d)
        if abs(t1 - t0) < 1e-12:
            n_blind += 1
        print(f"    push worst doc -25 pts: {label:32s} mean {m0:+6.2f}->{m1:+6.2f} "
              f"({m1 - m0:+.2f})   trim {t0:+6.2f}->{t1:+6.2f} ({t1 - t0:+.2f})")
    n_merge = sum(1 for _, _, k in contrasts if k == "merge")
    ok_all &= say(n_blind == n_merge,
                  f"trimmed mean is EXACTLY unchanged by a -25 pt push on the worst "
                  f"document, on {n_blind}/{n_merge} merge contrasts")
    # (4b) the non-vacuity partner to (4). NOTE the plain mean's ABSOLUTE shift here is
    #      push/n = 25/50 = -0.50 on every contrast by construction, so asserting "the
    #      mean moved" would be arithmetic, not evidence -- a broken estimator scores
    #      the same -0.50. The question that is not forced is whether that shift is
    #      MATERIAL against the effect being claimed. On at least one contrast a single
    #      document degrading further must move the headline by more than half its size,
    #      while the trimmed mean does not move at all.
    shares = [(lbl, abs(worst_case_sensitivity(d)[1] - worst_case_sensitivity(d)[0])
               / max(abs(st.mean(d)), 1e-9))
              for lbl, d, k in contrasts if k == "merge"]
    top_lbl, top_share = max(shares, key=lambda t: t[1])
    ok_all &= say(top_share > 0.5,
                  f"one further-degraded document moves the plain mean by {100 * top_share:.0f}% "
                  f"of its own effect ({top_lbl.strip()}) while the trimmed mean is unmoved "
                  f"-- so (4) is a property of trimming, not of a push too small to matter")

    # (5) the tail carries information the location statistic does not. If ranking by
    #     worst-case reproduced ranking by mean, a tail rule would be redundant.
    by_mean = sorted(merge_rows, key=lambda r: st.mean(r[1]))
    by_worst = sorted(merge_rows, key=lambda r: min(r[1]))
    ok_all &= say([r[0] for r in by_mean] != [r[0] for r in by_worst],
                  "ranking contrasts by worst-case differs from ranking by mean "
                  "-- the tail is not a restatement of the location")
    return ok_all


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="controls only, smaller bootstrap (fast)")
    args = ap.parse_args()

    for p in (RUN13, RUN14):
        if not os.path.exists(p):
            print(f"FATAL: missing artifact {p}", file=sys.stderr)
            return 2

    r13, r14 = load_rows(RUN13), load_rows(RUN14)
    print("=" * 96)
    print("D13 -- the ToMe blocker is the instrument, not the merger")
    print(f"     run 13: {os.path.relpath(RUN13, HERE)}   run 14: {os.path.relpath(RUN14, HERE)}")
    print("=" * 96)

    calibrated = section_calibration(r13, r14)
    if not calibrated:
        print("\nCALIBRATION FAILED -- the arrays do not reproduce the published figures.")
        print("Every number below would be unsafe to read. Stopping.")
        return 1

    contrasts = build_contrasts(r13, r14)
    section_variance(r13)
    section_estimator(contrasts, fast=args.selftest)
    section_required_n(contrasts)
    section_tail(contrasts)

    print("\n" + "=" * 96)
    print(f"CONTROLS: {_n_controls - _n_failed}/{_n_controls} PASS")
    print("=" * 96)
    print("""
WHAT THIS LICENSES

  - "UNDERPOWERED" on the merge axis is a property of n=50 against a per-document
    sd of 11-13 pts, not a property of ToMe. The merger executes and is correct
    (verify_tome_merge_port.py 89/89); its effects are simply the same size as the
    instrument's resolution.
  - A 10% trimmed mean with a Tukey-McLaughlin SE buys ~30% of resolution for zero
    GPU time, and it is discriminating rather than permissive: every published null
    stays null, and the -64 pt control still resolves.
  - It does NOT rescue the merge axis on its own. Resolving a 2-pt effect still needs
    n ~ 55-90 documents even trimmed, and the m=0.20 "free" claim as a TIGHT null
    (+-1 pt) needs n ~ 150-360.

WHAT IT DOES NOT LICENSE

  - Switching estimator after seeing an effect. This is filed as an input to Pending
    18 and must be written into run 17's pre-registration BEFORE any run-17 number
    exists. The justification on record is the variance structure in section 2, not
    the sign of any contrast.
  - Reading the trimmed point estimate as "the" effect. It is a different estimand.
    Note it flips m=0.20's sign from +0.54 to -0.65 -- both nulls, but "free" is not
    sign-robust, which cuts against this project's own claim 3 rather than for it.
""")
    return 1 if _n_failed else 0


if __name__ == "__main__":
    sys.exit(main())
