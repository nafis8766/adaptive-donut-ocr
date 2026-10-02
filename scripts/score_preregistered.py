"""T3: score runs 13/14 under T1's pre-registered rule, and re-derive claim 3's own rows.

AGENTS.md `## Run 17 pre-registration (T1)` is prose. D14 s10 showed what happens to a
threshold that exists only as prose: `res <= 2.0` written without units cannot fail on the
stored [0,1] fields, and any run scored that way returns "powered, no harmed documents" by
arithmetic while looking like a measurement. So the rule gets an implementation before it
gets used, and the implementation is calibrated against figures the rule recorded BEFORE
this file existed.

THREE DIFFERENT CONTRASTS, KEPT APART ON PURPOSE (T3's own warning, D14 s1b's 5.08 pt hazard):

  A  T1 s1's PRE-REGISTERED primary   keep=0.50 m=0.20 ink  vs  keep=0.40 ink TWIN
                                      M=1920 vs M=1920 -- merge vs PRUNE HARDER, token-matched
  B  claim 3's own +0.54 row          keep=0.50 m=0.20 router  vs  keep=0.50 router
                                      M=1920 vs M=2400 -- merge vs NO MERGE, same keep
  C  claim 3's M=1440 row             keep=0.50 m=0.40 router  vs  keep=0.50 router
                                      M=1440 vs M=2400 -- the row holding the -72.34 page

A is what run 17 will be judged on. B and C are what claim 3's published sentence rests on.
They answer different questions and section 2 scores A alone; sections 3 and 4 score B and C
and are labelled throughout as NOT the pre-registered primary. Merging them is the error
this file is structured to make impossible.

What it implements (T1 s2-s7): 10% trimmed mean of per-document differences with
DIFFERENCE-THEN-TRIM; Tukey-McLaughlin SE = winsorized_sd/((1-2g)*sqrt(n)); deterministic
res = 1.96*SE; two tail statistics -- worst-document ratio and harmed count, each gated at
the p95 of a matched normal null simulated at scoring time (seed 20260924, 40000 draws);
Holm over 3 quantities; discard set in documents; the four-verdict table.

Sections 3, 4 and 5 are where the findings are. Three of them are not in T3's DONE-WHEN:
claim 3's "resolved and negative" M=1440 price does not replicate in run 14; claim 3's
memory ratio and its accuracy figure are measured against DIFFERENT baselines (this one
corrects in the claim's FAVOUR, stated explicitly so it is not filed as a flattering error);
and T1 s3's tail gate is **not specific to merging** -- it fires on 13 of 21 contrasts with
no merging in them, and the worst per-document loss in the whole sweep (-80.85 pts) is on an
unmerged row. That last one is a defect in the rule T1 just wrote, found by running the
untreated control D13 s5 never ran, and it is the most consequential thing in this file.

Run:  python scripts/score_preregistered.py
      python scripts/score_preregistered.py --selftest   (controls only, skips the reports)
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import random
import statistics as st
import sys
from typing import Dict, List, Sequence, Tuple

# Repo root, not results/ -- the run directories live at the top level, and their names
# are inconsistent ("run 13" with a space, "run14" without). Same resolution as
# diagnose_analysis_dof.py so the two scripts cannot read different files.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN13 = os.path.join(HERE, "run 13", "ablation_selection.json")
RUN14 = os.path.join(HERE, "run14", "ablation_selection.json")

# ---- the pre-registration's constants, in the units s3 pins them in -------
TRIM_G = 0.10
MDE = 1.0            # pts -- res must be <= this for FREE (s6)
HARM_THR = -10.0     # pts -- strict <, per s3's tie convention
NULL_SEED = 20260924
NULL_DRAWS = 40000
ALPHA = 0.05
FUNSD_N = 50
POOLED_N = 397       # FUNSD 50 + sizhkhy/SROIE 347, confirmed by loading (T2)

# contrast A -- T1 s1's pre-registered primary, token-matched
TREAT = "keep=0.50 m=0.20 ink"
CTRL = "keep=0.40 ink TWIN"
# contrasts B and C -- claim 3's own rows, same keep fraction
C3_M20 = "keep=0.50 m=0.20 router"
C3_M40 = "keep=0.50 m=0.40 router"
C3_BASE = "keep=0.50 router"
FULL = "keep=1.00 router CONTROL"

# s4: three quantities, direction pinned PER QUANTITY (s3). `ned` is an error rate.
QUANTS: Tuple[Tuple[str, float, str], ...] = (
    ("recall", +1.0, "primary"),
    ("ned", -1.0, "co-primary"),
    # ("word_order", +1.0, "co-primary")  -- not on disk for runs 13/14; see s4
)

_n_controls = 0
_n_failed = 0


def say(ok: bool, msg: str) -> bool:
    global _n_controls, _n_failed
    _n_controls += 1
    if not ok:
        _n_failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    return ok


def note(msg: str) -> None:
    """Informational. Deliberately NOT a control."""
    print(f"  [info] {msg}")


# ------------------------------------------------------------- data access

def load(path: str) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        return {r["config"]: r for r in json.load(fh)["rows"]}


def deltas(rows: Dict[str, dict], treat: str, ctrl: str,
           key: str = "recall", sign: float = +1.0) -> List[float]:
    """Per-document differences in POINTS, with direction applied.

    s3: scoring MUST convert to points first and MUST sign-flip `ned` before any tail
    statistic touches it. Both happen here, together, because doing one without the other
    is the failure mode -- an error rate in points still ranks a broken arm safest.
    """
    a, b = rows[treat]["per_image"], rows[ctrl]["per_image"]
    if len(a) != len(b):
        raise ValueError(f"unpaired: {len(a)} vs {len(b)}")
    return [sign * (x[key] - y[key]) * 100.0 for x, y in zip(a, b)]


def assert_direction(rows: Dict[str, dict], treat: str, ctrl: str,
                     kind: str = "merge") -> str:
    """s3's AMENDMENT: `d = treatment - control`, treatment being the arm carrying more of
    the intervention under test. Returns the reason, which the caller prints.

    Why this is a check and not a comment. `min(d)` is one-sided, so the tail gate is not
    reversal-invariant: T3 measured the verdict flipping on **10 of 28** configs when the
    arms are swapped, and nothing in the artifact says which arm is which. s3 pins the
    convention in prose; until now nothing enforced it, and a swapped pair produces a
    complete, plausible, silently one-sided result -- the shape this project keeps hitting.

    Mechanical in both directions it can be. The check is read off the ROWS, never inferred
    from the config strings, because a string is a label and `merge_ratio` is the thing.
      - kind='merge'      -- the merge step is the intervention, so merge_ratio orders the
                             arms, and equal merge_ratio is an ERROR rather than a default:
                             if the field cannot order them, this is not the kind of
                             contrast the caller said it was.
      - kind='checkpoint' -- the retrained checkpoint is the intervention (s5's cross-run
                             comparator). merge_ratio CANNOT order these, and that is the
                             positive criterion: the two arms must be the same config, so
                             the only thing differing is the weights. The caller passes the
                             later run as `treat`; sameness is what is checkable here, and
                             asserting it is what stops this branch becoming an escape
                             hatch for a pair that merely failed the merge test.
    """
    mt = rows[treat].get("merge_ratio", 0.0)
    mc = rows[ctrl].get("merge_ratio", 0.0)
    if kind == "merge":
        if mt > mc:
            return f"treatment merges more (m={mt:.2f} vs {mc:.2f})"
        if mt < mc:
            raise ValueError(
                f"s3 direction violated: '{treat}' merges LESS than '{ctrl}' "
                f"(m={mt:.2f} vs {mc:.2f}), so it is the control. Swap the arms.")
        raise ValueError(
            f"s3 direction undeclared: '{treat}' and '{ctrl}' merge equally (m={mt:.2f}), "
            f"so merge_ratio cannot order them and this is not a merge contrast.")
    if kind == "checkpoint":
        if treat != ctrl:
            raise ValueError(
                f"s3 direction undeclared: a checkpoint contrast holds the config fixed "
                f"and varies the weights, but '{treat}' != '{ctrl}'.")
        return f"treatment is the later checkpoint at a fixed config (m={mt:.2f} both arms)"
    raise ValueError(f"unknown intervention kind {kind!r}")


# ------------------------------------------------- s2: location, SE, interval

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


def tm_se(d: Sequence[float], g: float = TRIM_G) -> float:
    """Tukey-McLaughlin. NOT stdev(trimmed)/sqrt(n_trimmed), which is ~33% too small."""
    return winsorized_sd(d, g) / ((1.0 - 2.0 * g) * math.sqrt(len(d)))


def naive_se(d: Sequence[float], g: float = TRIM_G) -> float:
    """The error D13 documented. Here ONLY so a control can assert the gap is real."""
    s = sorted(d)
    k = int(math.floor(len(s) * g))
    t = s[k:len(s) - k]
    return st.stdev(t) / math.sqrt(len(t))


# ------------------------------------ s5: the discard set, IN DOCUMENTS, PER CORPUS
#
# T1 s5 is the one part of the pre-registration that was never anything but prose, and
# T4 says to implement it here. It is a CONSTRAINT, not a warning: "the trimmed-away set
# must not contain more than half of any single corpus's contribution", and "if it would
# be violated, reduce g until it is not, and report the g actually used."
#
# Why it binds. At the pooled n=397 a g=0.10 trim discards 39 documents per tail against
# FUNSD's entire 50. That is smaller than FUNSD -- when T1 was written against an assumed
# n=500 the two were exactly equal, 50 vs 50 -- so the hazard got SMALLER and less
# obvious, which is the direction that invites under-reacting. 39 of 50 is still 78% of
# the only corpus this project has ever measured, and the trimmed mean would report a
# clean number with FUNSD almost entirely absent from it.

def corpora_of(rows: Dict[str, dict], treat: str, ctrl: str) -> List[str]:
    """The per-document corpus label, ASSERTED aligned across the two arms.

    `deltas()` pairs by POSITION. That is correct by design -- both rows iterate the same
    `test_raw` in the same order -- but it is an assumption, and a reordering would pair
    document i of one corpus against document i of another while every summary statistic
    stayed plausible. Comparing the labels position-by-position turns the assumption into
    a check. Runs 13/14 predate the label, so `.get` defaults to 'funsd': their artifacts
    stay readable by this same code path rather than needing a second one.
    """
    a = [p.get("corpus", "funsd") for p in rows[treat]["per_image"]]
    b = [p.get("corpus", "funsd") for p in rows[ctrl]["per_image"]]
    if a != b:
        bad = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y][:3]
        raise ValueError(
            f"arms are not aligned by corpus, so pairing by position is comparing "
            f"different documents: first mismatches {bad}")
    return a


def discard_composition(d: Sequence[float], corpora: Sequence[str],
                        g: float = TRIM_G) -> dict:
    """Which documents the trim throws away, broken down by corpus."""
    n = len(d)
    k = int(math.floor(n * g))
    order = sorted(range(n), key=lambda i: d[i])
    lo, hi = order[:k], order[n - k:]
    tot: Dict[str, int] = {}
    for c in corpora:
        tot[c] = tot.get(c, 0) + 1
    per = {}
    for c in sorted(tot):
        dl = sum(1 for i in lo if corpora[i] == c)
        dh = sum(1 for i in hi if corpora[i] == c)
        per[c] = dict(n=tot[c], lo=dl, hi=dh, discarded=dl + dh,
                      frac=(dl + dh) / tot[c])
    worst = max((v["frac"] for v in per.values()), default=0.0)
    return dict(g=g, k_per_tail=k, n=n, n_discarded=2 * k, per_corpus=per,
                worst_frac=worst, violates=worst > 0.5,
                worst_corpus=max(per, key=lambda c: per[c]["frac"]) if per else None)


def choose_g(d: Sequence[float], corpora: Sequence[str],
             g0: float = TRIM_G) -> Tuple[float, dict]:
    """Reduce g until s5's constraint holds, and return the g actually used.

    Stepping down by 0.01 rather than jumping to 0 keeps as much of the robustness the
    trim buys as the constraint allows. g=0 is a legitimate terminal value: it discards
    nothing, so it cannot over-discard any corpus, and it means the estimator degrades to
    the plain mean -- which must then be REPORTED, because the plain mean is the estimator
    D13 rejected and a silent fallback to it would undo s2.
    """
    g = g0
    while g > 0.0:
        comp = discard_composition(d, corpora, g)
        if not comp["violates"]:
            return g, comp
        g = round(g - 0.01, 2)
    return 0.0, discard_composition(d, corpora, 0.0)


def fmt_composition(comp: dict) -> str:
    """One line, for printing beside every estimate as s5 requires."""
    parts = ", ".join(
        f"{c} {v['discarded']}/{v['n']} ({100.0 * v['frac']:.0f}%)"
        for c, v in sorted(comp["per_corpus"].items()))
    flag = "  <<< VIOLATES s5" if comp["violates"] else ""
    return (f"g={comp['g']:.2f}  discards {comp['k_per_tail']}/tail "
            f"= {comp['n_discarded']}/{comp['n']} docs  [{parts}]{flag}")


# ----------------------------------------------------- s3: the tail statistics

def blom(n: int) -> float:
    """Expected smallest of n standard normals, Blom's approximation."""
    return st.NormalDist().inv_cdf((1.0 - 0.375) / (n + 0.25))


def null_ratio(n: int, draws: int = NULL_DRAWS, seed: int = NULL_SEED) -> List[float]:
    """Matched-normal null for the worst-document ratio.

    Scale cancels (numerator and denominator are both linear in the scale), so this
    depends on n ALONE -- which is why s3 can quote p95 as a function of n. Drawn at
    unit scale for that reason, not as a shortcut.
    """
    rng = random.Random(seed)
    b = blom(n)
    return sorted(min(x) / (b * winsorized_sd(x))
                  for x in ([rng.gauss(0.0, 1.0) for _ in range(n)] for _ in range(draws)))


def null_count(n: int, wsd: float, draws: int = NULL_DRAWS,
               seed: int = NULL_SEED) -> List[int]:
    """Matched-normal null for the harmed count. Depends on n AND the row's own wsd."""
    rng = random.Random(seed + 1)
    return sorted(sum(1 for _ in range(n) if rng.gauss(0.0, wsd) < HARM_THR)
                  for _ in range(draws))


def pctl(xs: Sequence[float], p: float) -> float:
    return xs[min(len(xs) - 1, int(p * len(xs)))]


# ------------------------------------------------------------------ scoring

_NULL_CACHE: Dict[int, List[float]] = {}


def score_d(d: Sequence[float]) -> dict:
    n = len(d)
    m = trimmed_mean(d)
    se = tm_se(d)
    res = 1.96 * se
    wsd = winsorized_sd(d)
    if n not in _NULL_CACHE:
        _NULL_CACHE[n] = null_ratio(n)
    nr = _NULL_CACHE[n]
    nc = null_count(n, wsd)
    ratio = min(d) / (blom(n) * wsd)
    cnt = sum(1 for x in d if x < HARM_THR)
    z = m / se if se else 0.0
    return dict(d=list(d), n=n, m=m, plain=st.mean(d), se=se, res=res, wsd=wsd,
                ratio=ratio, count=cnt, lo=m - res, hi=m + res,
                p=2.0 * (1.0 - st.NormalDist().cdf(abs(z))),
                ratio_p95=pctl(nr, 0.95), ratio_med=pctl(nr, 0.50),
                count_p95=pctl(nc, 0.95), count_exp=st.mean(nc),
                worst=min(d), worst_exp=blom(n) * wsd,
                ratio_ok=ratio <= pctl(nr, 0.95), count_ok=cnt <= pctl(nc, 0.95),
                flat=(m - res) <= 0.0 <= (m + res))


def score(rows, treat, ctrl, key="recall", sign=+1.0) -> dict:
    return score_d(deltas(rows, treat, ctrl, key, sign))


def holm(ps: Dict[str, float], alpha: float = ALPHA) -> Dict[str, Tuple[float, bool]]:
    """s4: Holm step-down over the confirmatory family.

    The family is sized at THREE even though two are scorable -- s4 says not to drop to
    the number the back-scoring happens to support.
    """
    k = 3
    out, prev = {}, True
    for i, (name, p) in enumerate(sorted(ps.items(), key=lambda kv: kv[1])):
        thr = alpha / (k - i)
        rej = prev and p <= thr
        prev = rej
        out[name] = (thr, rej)
    return out


def verdict(by: Dict[str, dict], hl: Dict[str, Tuple[float, bool]]) -> str:
    """s7. One named pair, so N=1 on every branch -- equal arity by construction."""
    for name, r in by.items():
        if hl[name][1] and r["m"] < 0:
            return "DEGRADED"
    if hl["recall"][1] and by["recall"]["m"] > 0:
        return "IMPROVED"
    flat = all(r["flat"] for r in by.values())
    tight = all(r["res"] <= MDE for r in by.values())
    tails = all(r["ratio_ok"] and r["count_ok"] for r in by.values())
    if flat and tight and tails:
        return "FREE"
    return "UNDERPOWERED"


# --------------------------------------------------------------- sections

def section_calibration(runs) -> Dict[str, Dict[str, dict]]:
    print("\n" + "=" * 78)
    print("0. CALIBRATION -- reproduce figures T1 recorded BEFORE this file existed")
    print("=" * 78)

    for tag, rows in runs.items():
        say(rows[TREAT]["visual_tokens"] == rows[CTRL]["visual_tokens"] == 1920,
            f"run {tag}: contrast A is token-matched at M=1920 on disk "
            f"({rows[TREAT]['visual_tokens']} vs {rows[CTRL]['visual_tokens']})")
        say(True, f"run {tag}: contrast A direction pinned per s3's amendment -- "
                  f"{assert_direction(rows, TREAT, CTRL, 'merge')}")
    say("word_order" not in runs["13"][TREAT]["per_image"][0],
        "`word_order` is absent from per_image, so the family is scorable on 2 of 3 "
        "quantities -- s4's premise, checked rather than assumed")

    out = {t: {k: score(r, TREAT, CTRL, k, s) for k, s, _ in QUANTS}
           for t, r in runs.items()}
    r13, r14 = out["13"]["recall"], out["14"]["recall"]

    say(abs(r14["m"] - 0.02) < 0.01,
        f"run 14 contrast-A trimmed mean reproduces T1's +0.02 pts (got {r14['m']:+.4f})")
    say(abs(r14["worst"] - (-40.00)) < 0.01,
        f"run 14 worst document reproduces T1's -40.00 pts (got {r14['worst']:+.2f})")
    say(abs(r14["worst_exp"] - (-12.43)) < 0.05,
        f"run 14 matched-null expectation reproduces T1's -12.43 (got {r14['worst_exp']:+.2f})")
    say(abs(r14["ratio"] - 3.22) < 0.01,
        f"run 14 worst-document ratio reproduces T1's 3.22 (got {r14['ratio']:.3f})")
    say(r14["count"] == 5 and r13["count"] == 4,
        f"harmed counts reproduce T1's 5 (run 14) and 4 (run 13) "
        f"(got {r14['count']} and {r13['count']})")
    say(abs(r13["res"] - 2.48) < 0.01 and abs(r14["res"] - 1.92) < 0.01,
        f"res reproduces T1 s6's 2.48 (run 13) and 1.92 (run 14) "
        f"(got {r13['res']:.3f} / {r14['res']:.3f})")

    nr = null_ratio(50)
    say(abs(pctl(nr, 0.95) - 1.74) < 0.02 and abs(pctl(nr, 0.50) - 1.20) < 0.02,
        f"the n=50 ratio null reproduces T1's median 1.20 / p95 1.74 "
        f"(got {pctl(nr, 0.50):.2f} / {pctl(nr, 0.95):.2f})")
    for nn, want in ((307, 1.52), (397, 1.51)):
        got = pctl(null_ratio(nn, draws=8000), 0.95)
        say(abs(got - want) < 0.04,
            f"the n={nn} ratio null reproduces T1's p95 of {want} (got {got:.3f}) -- the "
            f"bar TIGHTENS with n, which a constant could not do")

    # T4: "re-derive s3's matched-null p95 against the LOADED pool -- T1 simulated it at
    # n=397 before T2 confirmed 397, and a threshold inherited from an unverified size
    # should not be the one run 17 is scored against."
    #
    # The structural answer is stronger than a re-simulation: score_d takes n from
    # `len(d)`, i.e. from the artifact's own paired documents, so the bar is re-derived
    # from whatever actually loads and CANNOT inherit 397. Asserted two ways, because
    # "it reads len(d)" is exactly the sort of thing that stays true in prose after it
    # stops being true in code.
    half = score_d(deltas(runs["14"], TREAT, CTRL)[:25])
    full = out["14"]["recall"]
    say(half["n"] == 25 and full["n"] == 50 and half["ratio_p95"] > full["ratio_p95"],
        f"score_d derives the bar from the data's own n: the same contrast truncated to "
        f"25 documents moves p95 {full['ratio_p95']:.2f} -> {half['ratio_p95']:.2f}. "
        f"Nothing is inherited -- when the pooled artifact lands, its n sets its own bar")
    _src = ast.parse(open(__file__, encoding="utf-8").read())
    _leaks = [n.lineno for n in ast.walk(_src)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", "") in ("null_ratio", "null_count", "blom")
              and any(isinstance(a, ast.Name) and a.id in ("POOLED_N", "FUNSD_N")
                      for a in n.args)]
    say(not _leaks,
        f"POOLED_N/FUNSD_N are never passed to null_ratio/null_count/blom (by ast, not by "
        f"grep -- a comment naming them is not a use). They size the REPORT, never a "
        f"threshold, so the 397 on line 69 cannot become a bar run 17 is scored against")
    return out


def section_discriminating(runs, out) -> None:
    print("\n" + "=" * 78)
    print("1. DISCRIMINATING CONTROLS -- does each pinned choice change the result?")
    print("=" * 78)

    d = deltas(runs["14"], TREAT, CTRL)
    tm, nv = tm_se(d), naive_se(d)
    say(nv < tm * 0.80,
        f"the naive SE is {100 * (1 - nv / tm):.0f}% smaller than Tukey-McLaughlin "
        f"({nv:.4f} vs {tm:.4f}) -- pinning the SE formula is not cosmetic")

    a = [p["recall"] * 100.0 for p in runs["14"][TREAT]["per_image"]]
    b = [p["recall"] * 100.0 for p in runs["14"][CTRL]["per_image"]]
    gap = trimmed_mean(d) - (trimmed_mean(a) - trimmed_mean(b))
    say(abs(gap) > 0.01,
        f"difference-then-trim and trim-then-difference differ by {gap:+.4f} pts here -- "
        f"naming 'trimmed mean' alone does not determine the estimate")
    say(abs(st.mean(d) - (st.mean(a) - st.mean(b))) < 1e-9,
        f"...and the PLAIN mean's gap is identically zero "
        f"({st.mean(d) - (st.mean(a) - st.mean(b)):+.2e}), so the non-additivity is a "
        f"property of trimming, not of the data")

    fl = score(runs["14"], TREAT, CTRL, "ned", -1.0)
    un = score(runs["14"], TREAT, CTRL, "ned", +1.0)
    say(fl["worst"] != un["worst"] and fl["m"] * un["m"] < 0,
        f"sign-flipping `ned` changes the tail it reports (worst {un['worst']:+.2f} -> "
        f"{fl['worst']:+.2f}, mean {un['m']:+.2f} -> {fl['m']:+.2f}) -- load-bearing, "
        f"not decorative")

    # s3's amendment, as a guard rather than as prose. Three probes: it must ACCEPT the
    # pinned orientation, REJECT the swap, and REJECT a pair it cannot order at all. A
    # guard that only ever sees the case it was written for is the decorative kind.
    try:
        assert_direction(runs["14"], CTRL, TREAT, "merge")
        swapped_caught = False
    except ValueError:
        swapped_caught = True
    say(swapped_caught,
        "assert_direction REJECTS contrast A with the arms swapped -- the orientation "
        "whose absence s3's amendment was filed to fix")
    try:
        assert_direction(runs["14"], CTRL, CTRL, "merge")
        tie_caught = False
    except ValueError:
        tie_caught = True
    say(tie_caught,
        "...and REJECTS a pair merge_ratio cannot order, rather than defaulting to the "
        "caller's argument order -- an unorderable pair is an unanswered question, not a "
        "direction of zero")
    swap = [-x for x in deltas(runs["14"], TREAT, CTRL)]
    sw_ratio = min(swap) / (blom(len(swap)) * winsorized_sd(swap))
    pin_ratio = out["14"]["recall"]["ratio"]
    p95_50 = pctl(_NULL_CACHE.setdefault(50, null_ratio(50)), 0.95)
    say(abs(sw_ratio - pin_ratio) > 1e-6 and (sw_ratio > p95_50) == (pin_ratio > p95_50),
        f"CONTRAST A DOES NOT FLIP, and that is reported rather than assumed: the ratio "
        f"moves {pin_ratio:.2f} -> {sw_ratio:.2f} under the swap (so the statistic is not "
        f"reversal-invariant) but both clear p95 {p95_50:.2f}, so run 14's gate failure is "
        f"NOT an artifact of the orientation. The 10-of-28 flip is real and is measured in "
        f"s5 on the cross-run family -- it is not a property of every pair, and asserting "
        f"it here would have been asserting it where it happens not to hold")

    native = sum(1 for x in d if x / 100.0 < HARM_THR)
    say(native == 0 and out["14"]["recall"]["count"] > 0,
        f"on the stored [0,1] field the harm rule counts {native} and in points it counts "
        f"{out['14']['recall']['count']} -- this scorer converts first, so D14 s1d's "
        f"unfalsifiable gate cannot recur here")

    say(out["14"]["recall"]["ratio"] > out["14"]["recall"]["ratio_p95"]
        and out["13"]["recall"]["ratio"] < out["13"]["recall"]["ratio_p95"],
        f"the ratio gate FIRES on run 14 ({out['14']['recall']['ratio']:.2f} > "
        f"{out['14']['recall']['ratio_p95']:.2f}) and does NOT on run 13 "
        f"({out['13']['recall']['ratio']:.2f} < {out['13']['recall']['ratio_p95']:.2f}) -- "
        f"a gate firing on both or neither would be untested by this pair")

    r14 = out["14"]["recall"]
    say(r14["flat"] and not (r14["ratio_ok"] and r14["count_ok"]),
        f"run 14's contrast A is FLAT on location (CI [{r14['lo']:+.2f}, {r14['hi']:+.2f}] "
        f"includes 0) yet FAILS a tail gate -- the exact case s3 was written to catch")

    # The count gate is scale-relative: it is NOT a constant bar across rows.
    say(out["13"]["recall"]["count_p95"] != out["14"]["recall"]["count_p95"],
        f"the harmed-count bar is matched per row, not fixed: p95 is "
        f"{out['13']['recall']['count_p95']:.0f} on run 13 and "
        f"{out['14']['recall']['count_p95']:.0f} on run 14, because run 13's spread is "
        f"wider -- so counts are NOT comparable across rows and must be quoted with their null")


def section_primary(out, hl, v) -> None:
    print("\n" + "=" * 78)
    print("2. CONTRAST A -- T1 s1's PRE-REGISTERED primary (this is what run 17 is judged on)")
    print("=" * 78)
    print(f"   {TREAT}  vs  {CTRL}   (M=1920 vs M=1920, token-matched)")
    for tag in ("13", "14"):
        print(f"\n   --- run {tag} " + "-" * 56)
        for key, sign, role in QUANTS:
            r = out[tag][key]
            print(f"   {key:7s} [{role:10s}] trimmed {r['m']:+6.2f} pts"
                  f"{' (sign-flipped)' if sign < 0 else '               '}   "
                  f"95% CI [{r['lo']:+6.2f}, {r['hi']:+6.2f}]   res {r['res']:.2f}")
            print(f"           worst doc {r['worst']:+7.2f} vs matched-null "
                  f"{r['worst_exp']:+6.2f}  ratio {r['ratio']:.2f} vs p95 "
                  f"{r['ratio_p95']:.2f}  [{'PASS' if r['ratio_ok'] else 'FAIL'}]")
            print(f"           harmed    {r['count']:3d}     vs null p95 "
                  f"{r['count_p95']:.0f} (exp {r['count_exp']:.2f})"
                  f"                 [{'PASS' if r['count_ok'] else 'FAIL'}]")
        n = out[tag]["recall"]["n"]
        print(f"   s5 discard set: {int(n * TRIM_G)} documents per tail of {n} "
              f"(at pooled n={POOLED_N} it is {int(POOLED_N * TRIM_G)} vs FUNSD's {FUNSD_N})")
        print("   s4 Holm: " + ", ".join(
            f"{k} p={out[tag][k]['p']:.4f} vs {hl[tag][k][0]:.5f} "
            f"{'REJECT' if hl[tag][k][1] else 'retain'}" for k, _, _ in QUANTS))
        print(f"   s7 VERDICT: **{v[tag]}**")


def section_claim3(runs) -> Dict[str, dict]:
    print("\n" + "=" * 78)
    print("3. CONTRASTS B and C -- claim 3's OWN rows.  NOT the pre-registered primary.")
    print("=" * 78)
    print("   Claim 3 says: 'prune to keep=0.50 then merge m=0.20 -> M=1920 tokens,")
    print("   cross-KV 150.00 -> 60.00 MiB (2.50x), for +0.54 pts of word recall,")
    print("   95% CI [-2.36, +3.83], n=50 paired (run 13) -- the CI includes zero, so")
    print("   there is no measured cost.  Do not quote the deeper 3.33x at M=1440 without")
    print("   its price: -3.86 pts [-7.45, -0.30], resolved and negative.'")
    print("   Those figures are SAME-KEEP-FRACTION router rows. Contrast A above is a")
    print("   token-matched ink pair. Different questions; scored apart, never pooled.")

    b = {t: score(runs[t], C3_M20, C3_BASE) for t in ("13", "14")}
    c = {t: score(runs[t], C3_M40, C3_BASE) for t in ("13", "14")}

    print(f"\n   {'row':26s} {'run':4s} {'plain':>7s} {'trim':>7s} {'res':>6s} "
          f"{'95% CI':>18s} {'worst':>8s} {'ratio':>6s} {'gate':>6s}")
    for lbl, grp in (("B  m=0.20 vs no-merge", b), ("C  m=0.40 vs no-merge", c)):
        for t in ("13", "14"):
            r = grp[t]
            print(f"   {lbl:26s} {t:4s} {r['plain']:+7.2f} {r['m']:+7.2f} {r['res']:6.2f} "
                  f"[{r['lo']:+7.2f},{r['hi']:+7.2f}] {r['worst']:+8.2f} {r['ratio']:6.2f} "
                  f"{'FIRES' if not r['ratio_ok'] else 'pass':>6s}")

    print("\n   caveat (i) -- the sign flip, re-derived:")
    say(abs(b["13"]["plain"] - 0.54) < 0.01 and abs(b["13"]["m"] - (-0.65)) < 0.01,
        f"claim 3's +0.54 reproduces as the PLAIN mean and T1's estimator gives "
        f"{b['13']['m']:+.2f} on the same row -- the sign flips, exactly as D13 recorded")
    say(b["13"]["flat"],
        f"both are nulls: T1's CI [{b['13']['lo']:+.2f}, {b['13']['hi']:+.2f}] includes zero, "
        f"so 'no measured cost' SURVIVES the estimator change")
    say(b["13"]["m"] * b["14"]["m"] < 0,
        f"but the sign is not run-robust either: the SAME row is {b['13']['m']:+.2f} in run 13 "
        f"and {b['14']['m']:+.2f} in run 14 -- so 'free' is fragile in TWO directions, "
        f"estimator and replicate, and only one of those is in T3's caveat list")

    print("\n   caveat (ii) -- the tail, re-derived on the row that holds it:")
    c14 = c["14"]
    say(abs(c14["worst"] - (-72.34)) < 0.01,
        f"the -72.34 pt page is in run 14's m=0.40 row (got {c14['worst']:+.2f}) -- "
        f"claim 3's own M=1440 contrast, not contrast A")
    say(abs(c14["plain"]) < c14["res"],
        f"the PLAIN mean hides it: {c14['plain']:+.2f} pts against res {c14['res']:.2f}, so "
        f"a {abs(c14['worst']):.0f} pt page fits inside the resolution")
    i = c14["d"].index(min(c14["d"]))
    mut = list(c14["d"])
    mut[i] -= 25.0
    say(trimmed_mean(mut) == trimmed_mean(c14["d"]),
        f"and the TRIMMED mean is blind to the last bit: pushing that page 25 pts further "
        f"down moves it by {trimmed_mean(mut) - trimmed_mean(c14['d']):.1e} "
        f"(the plain mean moves {st.mean(mut) - st.mean(c14['d']):+.2f}, "
        f"{abs((st.mean(mut) - st.mean(c14['d'])) / c14['plain']) * 100:.0f}% of the effect)")
    say(not c14["ratio_ok"],
        f"T1's WORST-DOCUMENT gate does SURFACE what both estimators hide: ratio "
        f"{c14['ratio']:.2f} vs null p95 {c14['ratio_p95']:.2f}. Surfacing is not attributing "
        f"-- section 5 shows the same gate fires on unmerged rows, so read this as 'the page "
        f"is visible', not 'merging caused it'")
    say(c14["count_ok"],
        f"but T1's HARMED-COUNT gate does NOT catch it ({c14['count']} vs p95 "
        f"{c14['count_p95']:.0f}) -- one page at -72 is one document, and the count gate "
        f"scales with the row's own spread; do not report 'the tail gates catch it' plural")

    print("\n   NOT in T3's caveat list -- found while re-deriving:")
    say(not c["13"]["flat"] and c["14"]["flat"],
        f"claim 3's 'resolved and negative' M=1440 price does NOT replicate: run 13 gives "
        f"{c['13']['m']:+.2f} [{c['13']['lo']:+.2f}, {c['13']['hi']:+.2f}] (excludes zero) "
        f"but run 14 gives {c['14']['m']:+.2f} [{c['14']['lo']:+.2f}, {c['14']['hi']:+.2f}] "
        f"(includes zero) -- the sentence states a resolved fact that one of two runs denies")
    say(abs(c["13"]["plain"] - (-3.86)) < 0.01,
        f"run 13's plain mean does reproduce claim 3's -3.86 exactly "
        f"({c['13']['plain']:+.2f}), so the non-replication is between RUNS, not an "
        f"artifact of re-deriving with a different estimator")
    return {"B": b, "C": c}


def section_baseline(runs) -> None:
    print("\n" + "=" * 78)
    print("4. BASELINE CONSISTENCY -- claim 3's two halves are measured against two baselines")
    print("=" * 78)
    R = runs["13"]
    m_full, m_prune, m_merge = (R[FULL]["visual_tokens"], R[C3_BASE]["visual_tokens"],
                                R[C3_M20]["visual_tokens"])
    print(f"   token counts on disk: keep=1.00 M={m_full}, keep=0.50 M={m_prune}, "
          f"keep=0.50+m=0.20 M={m_merge}")

    say(abs(m_full / m_merge - 2.50) < 1e-9,
        f"claim 3's '150.00 -> 60.00 MiB (2.50x)' is M={m_full}/M={m_merge} = "
        f"{m_full / m_merge:.4f} -- so the MEMORY figure's baseline is keep=1.00")
    say(abs(m_prune / m_merge - 1.25) < 1e-9,
        f"but the +0.54's control row is M={m_prune}, and M={m_prune}/M={m_merge} = "
        f"{m_prune / m_merge:.2f}x -- the ACCURACY figure's baseline is keep=0.50")
    say(abs(m_full / R[C3_M40]["visual_tokens"] - 10.0 / 3.0) < 1e-9,
        f"the 3.33x at M=1440 is also vs keep=1.00 ({m_full}/{R[C3_M40]['visual_tokens']} = "
        f"{m_full / R[C3_M40]['visual_tokens']:.4f}), so both memory ratios share a baseline "
        f"that neither accuracy figure uses")

    print("   => the sentence pairs a PRUNE+MERGE memory ratio with a MERGE-ONLY accuracy")
    print("      delta. Read as one intervention it overstates what +0.54 pts bought: the")
    print("      merge step alone is 1.25x, and the remaining 2.0x is the pruning step,")
    print("      whose accuracy delta is a separate measurement.")

    cons = {t: score(runs[t], C3_M20, FULL) for t in ("13", "14")}
    half = {t: score(runs[t], C3_BASE, FULL) for t in ("13", "14")}
    for lbl, g in (("prune+merge vs keep=1.00", cons), ("prune only  vs keep=1.00", half)):
        for t in ("13", "14"):
            r = g[t]
            print(f"      {lbl}  run {t}: trimmed {r['m']:+6.2f} "
                  f"[{r['lo']:+6.2f}, {r['hi']:+6.2f}]  res {r['res']:.2f}  "
                  f"worst {r['worst']:+7.2f}")

    say(cons["13"]["m"] > 0.54,
        f"the direction matters and it is NOT the flattering one: on a CONSISTENT keep=1.00 "
        f"baseline run 13's accuracy delta is {cons['13']['m']:+.2f} pts, BETTER than the "
        f"{0.54:+.2f} claim 3 quotes -- fixing the mismatch improves the number, so this is "
        f"a consistency defect, not an inflated result, and must be filed as such")
    say(cons["13"]["flat"] and cons["14"]["flat"],
        f"it changes no verdict either: both runs stay null on the consistent baseline "
        f"([{cons['13']['lo']:+.2f}, {cons['13']['hi']:+.2f}] and "
        f"[{cons['14']['lo']:+.2f}, {cons['14']['hi']:+.2f}]) -- so the fix is to the "
        f"SENTENCE, and no downstream number moves")


def section_gate_specificity(runs) -> None:
    """Does T1 s3's tail gate identify MERGING, or does it identify this corpus?

    D13 s5 measured the worst document on 6/6 merge contrasts against a simulated normal
    null and concluded the tail must be gated. The gate is right. What was never measured
    is the same statistic on contrasts with NO merging in them -- a treated row with no
    untreated control. This section supplies the untreated control, and it does not say
    what the treated row alone said.

    The available non-merge intervention is the checkpoint: run 13 evaluates the merge-naive
    router, run 14 the router retrained with pruning and merging on (AGENTS.md run-17 item
    (a)). So the same config across the two runs is an ACTIVE comparator -- not a null, which
    is the point: there is no null on disk at all, because re-running a config is bit-
    identical (noise floor 0.000e+00, AGENTS.md:6283). Every delta here is a real difference
    in model output, and 21 of the 28 shared configs contain no merging.
    """
    print("\n" + "=" * 78)
    print("5. IS THE TAIL GATE SPECIFIC TO MERGING?  (the control D13 s5 did not run)")
    print("=" * 78)

    A, B = runs["13"], runs["14"]
    shared = [c for c in A if c in B]
    # Read the RAW row lists, not the dict-keyed views: load() collapses duplicate configs
    # silently, and a duplicated config is precisely the zero-treatment replicate this
    # section needs. Asserting uniqueness on the dict would be vacuous -- keys are unique.
    raw = {t: [r["config"] for r in json.load(open(p, encoding="utf-8"))["rows"]]
           for t, p in (("13", RUN13), ("14", RUN14))}
    say(all(len(v) == len(set(v)) for v in raw.values()),
        f"no config is evaluated twice within either run ({len(raw['13'])} and "
        f"{len(raw['14'])} rows, all distinct) -- so there is NO zero-treatment replicate "
        f"on disk to calibrate the gate against, and decoding is bit-identical on re-run "
        f"anyway (noise floor 0.000e+00), so one would be degenerate")

    p95 = pctl(_NULL_CACHE.setdefault(50, null_ratio(50)), 0.95)

    def ratio(d):
        return min(d) / (blom(len(d)) * winsorized_sd(d))

    rows = []
    for c in shared:
        # Every pair, not a sample: s3's amendment is per ROW, and the property being
        # asserted (same config, so only the weights differ) is per row too.
        assert_direction({c: B[c]}, c, c, "checkpoint")
        d = deltas({"t": B[c], "c": A[c]}, "t", "c")           # run14 - run13 = treat - ctrl
        rows.append((ratio(d), c, min(d), winsorized_sd(d), A[c]["merge_ratio"],
                     ratio([-x for x in d])))                  # same pair, arms swapped
    say(True, f"all {len(shared)} cross-run pairs hold the config fixed and vary only the "
              f"checkpoint, so s3's amendment orders them by run -- treatment is run 14")
    merged = [r for r in rows if r[4]]
    plain = [r for r in rows if not r[4]]

    print(f"   checkpoint DiD (run 14 - run 13), the direction the design forces;"
          f" normal-null p95 = {p95:.2f}")
    print(f"   {'config':28s} {'worst':>8s} {'wsd':>6s} {'ratio':>6s}  merge")
    for r, c, mn, w, mr, _ in sorted(rows, reverse=True)[:6]:
        print(f"   {c:28s} {mn:+8.2f} {w:6.2f} {r:6.2f}  {('m=%.2f' % mr) if mr else 'NONE':>6s}")

    n_p_fire = sum(1 for r in plain if r[0] > p95)
    n_m_fire = sum(1 for r in merged if r[0] > p95)
    print(f"\n   rows with NO merging: {n_p_fire}/{len(plain)} fire the gate"
          f"   |   rows WITH merging: {n_m_fire}/{len(merged)} fire")

    say(n_p_fire > 0,
        f"the gate fires on {n_p_fire} of {len(plain)} contrasts that contain NO merging at "
        f"all -- so clearing 1.74 is not evidence about merging")
    top = max(rows)
    say(not top[4],
        f"the single worst per-document loss in the whole sweep is {top[2]:+.2f} pts on "
        f"`{top[1]}` -- keep={A[top[1]]['keep_ratio']:.2f}, m=0, no merging -- and it has the "
        f"highest ratio ({top[0]:.2f}), above every merge row "
        f"(max {max(r[0] for r in merged):.2f})")
    say(top[3] > 5.0,
        f"and it is not a small-denominator artifact: its winsorized sd is {top[3]:.2f} pts, "
        f"in line with the sweep, so the ratio is driven by a real {abs(top[2]):.0f} pt loss")

    # Direction of the CONTRAST is a separate DoF from direction of the QUANTITY (s3).
    flips = sum(1 for r in rows if (r[0] > p95) != (r[5] > p95))
    say(flips > 0,
        f"the gate is not reversal-invariant: swapping which arm is 'treatment' flips the "
        f"verdict on {flips} of {len(rows)} configs (min(d) is one-sided) -- s3 pins "
        f"direction per QUANTITY and leaves direction of the CONTRAST unwritten")

    ctl = [r for r in rows if r[1] == FULL][0]
    say(ctl[0] <= p95,
        f"the one comparator with neither pruning nor merging (`{FULL}`, keep=1.00 m=0) does "
        f"pass at {ctl[0]:.2f} -- so the gate is not firing on literally everything, and the "
        f"failure is one of SPECIFICITY, not of sensitivity")
    print("   => the -72.34 page is real and both location estimators still hide it. But at")
    print("      the normal-null bar the gate cannot attribute it to merging, and run 17")
    print("      would fail this gate on rows where nothing is merged. The bar has to come")
    print("      from an active non-merge comparator, which is the `random` arm at the")
    print("      trained budget that run 17 already requires -- and that D14 measured as")
    print("      ABSENT from both runs. T3's fix and T4's missing arm are the same row.")


def section_verdicts(out, hl, v) -> None:
    print("\n" + "=" * 78)
    print("7. WHAT THE VERDICTS LICENSE")
    print("=" * 78)
    say(v["13"] == v["14"] == "UNDERPOWERED",
        f"contrast A scores UNDERPOWERED in both runs (13: {v['13']}, 14: {v['14']}) -- s6 "
        f"predicted exactly this at n=50, where res is ~2.5 pts against a 1.0 pt MDE")
    say(not any(h[1] for h in hl["13"].values())
        and not any(h[1] for h in hl["14"].values()),
        "no confirmatory quantity survives Holm in either run -- consistent with D14 s1d's "
        "independent finding of zero survivors over the wider 12-test family")
    say(v["14"] != "FREE",
        "run 14 is NOT scored FREE despite a +0.02 pt trimmed mean -- the tail gates block "
        "it, which is the single behaviour s3 exists to produce")
    n_req = math.ceil((1.96 * out["13"]["recall"]["wsd"]
                       / ((1 - 2 * TRIM_G) * MDE)) ** 2)
    say(abs(n_req - 307) <= 2,
        f"n required for res <= {MDE:.1f} pt reproduces T1 s6's 307 (got {n_req}), and T2's "
        f"pool of {POOLED_N} clears it")
    print(f"\n   UNDERPOWERED licenses NOTHING -- not 'merging is free', not 'no measured")
    print(f"   cost'. Quote the required n ({n_req}) with it. Claim 3's corpus-average null")
    print(f"   is TRUE and is not a sentence about an arbitrary document.")


def section_discard(runs) -> None:
    """T1 s5 made executable, plus the control that stops it being a decorative green.

    FALSIFIER, stated before the numbers: if the corpus-aligned synthetic below does NOT
    trip `violates`, or `choose_g` does not reduce g in response, then this constraint is
    unimplemented no matter what it prints on runs 13/14 -- because those are
    single-corpus, where at g=0.10 the discard set is 20% of the only corpus present and
    the 50% bar can never be reached. A green here that rests only on runs 13/14 is the
    "untreated control had never run" defect T3 found in the tail gates, repeated.
    """
    print("\n" + "=" * 78)
    print("6. THE DISCARD SET, IN DOCUMENTS, PER CORPUS (T1 s5 -- prose until now)")
    print("=" * 78)

    for t in ("13", "14"):
        d = deltas(runs[t], TREAT, CTRL)
        corp = corpora_of(runs[t], TREAT, CTRL)
        g_used, comp = choose_g(d, corp)
        print(f"   run {t}  {fmt_composition(comp)}")
        say(g_used == TRIM_G and not comp["violates"],
            f"run {t}: g stays at {TRIM_G} -- FUNSD-only at n=50 discards "
            f"{comp['n_discarded']}/{comp['n']} = "
            f"{100.0 * comp['worst_frac']:.0f}% of the one corpus present, under the 50% bar")
        say(set(comp["per_corpus"]) == {"funsd"},
            f"run {t}: the unlabelled artifacts read as single-corpus 'funsd', so runs "
            f"13/14 need no second code path ({sorted(comp['per_corpus'])})")

    # ---- the control that matters: a tail that IS corpus-aligned ------------------
    # Build the pool T4 will actually produce -- 50 FUNSD + 347 SROIE -- and put FUNSD
    # at the extremes. This is not a strawman: FUNSD is forms and SROIE is receipts, they
    # are 87.4%/12.6% of the pool, and a systematic per-corpus difference in how merging
    # hurts is exactly the thing a stratified report exists to surface. If the effect is
    # corpus-aligned at all, FUNSD lands in the tails.
    n_f, n_s = FUNSD_N, POOLED_N - FUNSD_N
    say(n_f + n_s == POOLED_N and n_s == 347,
        f"the synthetic pool is the real one: {n_f} FUNSD + {n_s} SROIE = {POOLED_N}")
    corp = ["funsd"] * n_f + ["sroie"] * n_s
    # FUNSD spread across both tails: 25 at the bottom, 25 at the top.
    d = ([-40.0 - i for i in range(n_f // 2)]          # 25 worst docs, all FUNSD
         + [+40.0 + i for i in range(n_f - n_f // 2)]  # 25 best docs, all FUNSD
         + [0.05 * ((i % 7) - 3) for i in range(n_s)])  # SROIE, all near zero
    comp0 = discard_composition(d, corp, TRIM_G)
    print(f"\n   corpus-aligned synthetic  {fmt_composition(comp0)}")
    say(comp0["k_per_tail"] == int(math.floor(POOLED_N * TRIM_G)) == 39,
        f"at n={POOLED_N}, g={TRIM_G} discards {comp0['k_per_tail']} per tail -- derived "
        f"here, not quoted: 39 against FUNSD's {FUNSD_N} is "
        f"{100.0 * 39 / FUNSD_N:.0f}% of it")
    say(comp0["violates"] and comp0["worst_corpus"] == "funsd",
        f"NON-VACUITY: a corpus-aligned tail TRIPS s5 -- FUNSD loses "
        f"{100.0 * comp0['per_corpus']['funsd']['frac']:.0f}% of its documents while "
        f"SROIE loses {100.0 * comp0['per_corpus']['sroie']['frac']:.0f}%")
    g_used, comp1 = choose_g(d, corp)
    print(f"   after choose_g            {fmt_composition(comp1)}")
    say(g_used < TRIM_G and not comp1["violates"],
        f"s5 is a CONSTRAINT, not a warning: g reduced {TRIM_G} -> {g_used:.2f}, "
        f"FUNSD's loss {100.0 * comp0['per_corpus']['funsd']['frac']:.0f}% -> "
        f"{100.0 * comp1['per_corpus']['funsd']['frac']:.0f}%")
    say(comp1["k_per_tail"] < comp0["k_per_tail"],
        f"and the reduction is in DOCUMENTS, which is the unit s5 specifies: "
        f"{comp0['k_per_tail']} -> {comp1['k_per_tail']} per tail")

    # ---- and the specificity counterpart -----------------------------------------
    # T3 s6's lesson applied to this check rather than to the tail gates: a constraint
    # that fires on the pooled shape REGARDLESS of whether the tail is corpus-aligned
    # would force g down on every pooled run and quietly retire the trim.
    d2 = [0.05 * ((i % 11) - 5) for i in range(n_f)] + \
         [-40.0 - i for i in range(39)] + \
         [+40.0 + i for i in range(39)] + \
         [0.05 * ((i % 7) - 3) for i in range(n_s - 78)]
    comp2 = discard_composition(d2, corp, TRIM_G)
    print(f"   SROIE-aligned synthetic   {fmt_composition(comp2)}")
    say(not comp2["violates"],
        f"SPECIFICITY: the same n and the same g do NOT trip s5 when the tail is SROIE's "
        f"-- FUNSD {100.0 * comp2['per_corpus']['funsd']['frac']:.0f}%, SROIE "
        f"{100.0 * comp2['per_corpus']['sroie']['frac']:.0f}%, so the constraint tracks "
        f"corpus alignment and not pooling as such")

    # ---- the pairing guard --------------------------------------------------------
    # corpora_of() asserts label alignment because deltas() pairs by POSITION. Sabotage
    # one label and require the raise: without this, the guard is a comment.
    import copy as _copy
    sab = {k: _copy.deepcopy(v) for k, v in runs["13"].items() if k in (TREAT, CTRL)}
    sab[TREAT]["per_image"][7]["corpus"] = "sroie"
    raised = False
    try:
        corpora_of(sab, TREAT, CTRL)
    except ValueError:
        raised = True
    say(raised,
        "a single mislabelled document RAISES rather than pairing FUNSD against SROIE -- "
        "by-position pairing is now checked, not assumed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="controls only; skips sections 2's report (which has no controls)")
    args = ap.parse_args()

    print("=" * 78)
    print("T3 -- RUNS 13/14 UNDER THE RUN-17 PRE-REGISTRATION, AND CLAIM 3's OWN ROWS")
    print("=" * 78)
    runs = {"13": load(RUN13), "14": load(RUN14)}

    out = section_calibration(runs)
    section_discriminating(runs, out)
    hl = {t: holm({k: out[t][k]["p"] for k, _, _ in QUANTS}) for t in out}
    v = {t: verdict(out[t], hl[t]) for t in out}
    if not args.selftest:
        section_primary(out, hl, v)
    else:
        print("\n(--selftest: section 2 is a report with no controls in it; skipped. "
              "Sections 0, 1, 3, 4 and 5 hold every control and all of them ran.)")
    section_claim3(runs)
    section_baseline(runs)
    section_gate_specificity(runs)
    section_discard(runs)
    section_verdicts(out, hl, v)

    print("\n" + "=" * 78)
    print(f"CONTROLS: {_n_controls - _n_failed}/{_n_controls} PASS")
    print("=" * 78)
    return 1 if _n_failed else 0


if __name__ == "__main__":
    sys.exit(main())
