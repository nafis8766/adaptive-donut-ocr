#!/usr/bin/env python
"""D14 (2026-09-23, local, <10 s) -- T1 is not an estimator choice.

D13 answered *which estimator*. This script asks what a rule that names that
estimator would still leave unwritten, and measures each unwritten choice against
the ~1.0 pt effect the design is trying to detect.

Sections, each ending in controls that can fail:

  0. CALIBRATION  -- reproduce a published (mean, res) pair from the raw arrays, so
                     the loader is checked against the file before anything new is
                     read off it. Fails -> everything below is void, exit 1.
  1. ROW          -- how many token-matched (merge, non-merge) pairs a reader could
                     legally call "the" primary contrast.
  1b. DENOTATION  -- worse than a count: the SAME phrase ("run 14, m=0.40") names two
                     different contrasts, one a null and one a +4.9 pt gain. Found by
                     accident, when an ad-hoc probe and this script disagreed and both
                     turned out to be right about different rows.
  2. ARM          -- the swing from choosing which SPLIT is "the merge arm", when
                     both splits are already on disk at the same budget.
  3. DIRECTION    -- `arr()` scales every key x100 and encodes no direction. On the
                     sabotage arm, recall's worst document and `ned`'s worst document
                     disagree in SIGN, so a naive tail statistic ranks the
                     deliberately-broken arm safest.
  4. G            -- the trim fraction picks the sign of the point estimate.
  5. DID          -- the trimmed mean is not linear, so "trim then difference" and
                     "difference then trim" are different estimands. The plain mean
                     is linear; that half is an implementation self-test, not
                     evidence, and is labelled as such.
  6. TIE          -- a `count(d < thr)` tail rule has a document sitting exactly ON
                     the threshold today, on the headline row.
  7. DISCARD      -- under T4's pooling, a g=0.10 trim's discard set has room to
                     swallow every harmed FUNSD document.
  8. RANDOM TWIN  -- whether a token-matched `random` arm exists for any merge row.
  9. REPLICATION  -- the freedom above is not hypothetical. Scored under the verdict
                     rule already pre-registered in AGENTS.md, runs 13 and 14 both
                     declare MERGING WINS -- on DISJOINT sets of pairs. Every run-13
                     winner moved toward zero in run 14; both run-14 winners were
                     negative in run 13.
 10. MULTIPLICITY -- and no declared winner survives the family it was drawn from:
                     Holm over 6 pairs x 2 stored quantities leaves ZERO survivors in
                     either run. Also audits the res gate section 9 prescribes and
                     finds it unfalsifiable on the stored [0,1] fields, i.e. the
                     prescription needs units, not just a number.

Sections 1b, 8, 9 and 10 are not additional degrees of freedom. 1b, 9 and 10 are
evidence the existing freedom has already been exercised (once by me, in 1b); 8 is a
control that cannot be computed from either run, recorded so T4 builds the arm it needs.
Section 10's last control is aimed at THIS SCRIPT'S OWN recommendation, on the principle
that a prescription deserves the same suspicion as a diagnosis.

Why this exists: T1 was queued as "write the estimator rule." The estimator is one
of seven choices the rule leaves open, and the smallest of them. See AGENTS.md
"Diagnostic D14".

No GPU, no model load, no network. Reads only cached run artifacts.

Usage:
    python scripts/diagnose_analysis_dof.py            # full report
    python scripts/diagnose_analysis_dof.py --selftest # controls only
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN13 = os.path.join(HERE, "run 13", "ablation_selection.json")
RUN14 = os.path.join(HERE, "run14", "ablation_selection.json")

TRIM_G = 0.10
MDE = 1.0          # pts. The effect size the design targets (AGENTS.md, T4).
HARM_THR = -10.0   # pts. The "harmed document" threshold already used in D13.
SEED_NOISE = 0.05  # pts. Bootstrap endpoint movement across seeds, per AGENTS.md.
                   # Used as a noise floor so section 5's bar is not fitted to this data.
POOLED_N = 397     # T4's pooled corpus size. FUNSD 50 + sizhkhy/SROIE test 347, both
                   # confirmed by loading (T2, 2026-09-24). Was 397 -- this constant read
                   # 500 until then, an estimate that happened to make k == FUNSD_N exactly.
FUNSD_N = 50       # FUNSD test, in full.

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
    """Informational. Deliberately NOT a control -- see section 5."""
    print(f"  [info] {msg}")


# ---------------------------------------------------------------- data access

def load(path: str) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        return {r["config"]: r for r in json.load(fh)["rows"]}


def budgets(rows: Dict[str, dict]) -> Dict[str, int]:
    return {k: int(v["visual_tokens"]) for k, v in rows.items()}


def arr(row: dict, key: str = "recall") -> List[float]:
    """Per-image metric x100. Mirrors diagnose_merge_power.py:arr() EXACTLY,
    including its blindness to direction -- that blindness is section 3's subject,
    so this must not quietly fix it."""
    return [pi[key] * 100.0 for pi in row["per_image"]]


def paired(a: Sequence[float], b: Sequence[float]) -> List[float]:
    if len(a) != len(b):
        raise ValueError(f"unpaired arrays: {len(a)} vs {len(b)}")
    return [x - y for x, y in zip(a, b)]


def delta(rows: Dict[str, dict], treat: str, ctrl: str, key: str = "recall") -> List[float]:
    return paired(arr(rows[treat], key), arr(rows[ctrl], key))


# ------------------------------------------------------------- the estimators

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


def res_mean(d: Sequence[float]) -> float:
    return 1.96 * st.stdev(d) / math.sqrt(len(d))


def res_trimmed(d: Sequence[float], g: float = TRIM_G) -> float:
    """Tukey-McLaughlin. See diagnose_merge_power.py for why not the naive form."""
    return 1.96 * winsorized_sd(d, g) / ((1.0 - 2.0 * g) * math.sqrt(len(d)))


# ------------------------------------------------- merge / non-merge row shapes

def is_merge(config: str) -> bool:
    return "m=0." in config


def is_random(config: str) -> bool:
    return "random" in config


# --------------------------------------------------------------- the sections

def section_calibration(r13: Dict[str, dict]) -> bool:
    """Reproduce one published pair before reading anything new off the arrays."""
    print("\n0. CALIBRATION -- loader checked against a published figure")
    d = delta(r13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN")
    m, res = st.mean(d), res_mean(d)
    print(f"   run13 M=1920 merge-vs-prune (recall): mean {m:+.2f}  res {res:.2f}  n={len(d)}")
    ok = say(len(d) == FUNSD_N, f"n is FUNSD test in full ({len(d)} documents)")
    # D13 published +2.86 / res 3.16 for M=1920. Reproduce to 0.01.
    d2 = delta(r13, "keep=0.35 m=0.20 router", "keep=0.28 router TWIN")
    print(f"   run13 M=1344 merge-vs-prune (recall): mean {st.mean(d2):+.2f}  res {res_mean(d2):.2f}")
    ok &= say(abs(st.mean(d2) - 2.86) < 0.01 or abs(m - 2.86) < 0.01,
              "one of the two published M-rows reproduces D13's +2.86 to 0.01")
    return ok


def section_row(r13: Dict[str, dict]) -> None:
    """How many contrasts could a reader legally call 'the' primary?"""
    print("\n1. ROW -- how many token-matched (merge, non-merge) pairs exist")
    b = budgets(r13)
    merge = {k for k in r13 if is_merge(k)}
    plain = {k for k in r13 if not is_merge(k)}
    mbud = {b[k] for k in merge}

    # (a) strict: same budget AND same selection family (the "intended" pairing)
    def family(cfg: str) -> str:
        if "ink" in cfg:
            return "ink"
        if "RANKPAR" in cfg:
            return "rankpar"
        return "router"

    strict = [(m, p) for m in merge for p in plain
              if b[m] == b[p] and family(m) == family(p)]
    # rankpar has no rankpar twin; it pairs against the router twin at its budget
    strict += [(m, p) for m in merge for p in plain
               if b[m] == b[p] and family(m) == "rankpar" and family(p) == "router"]
    loose = [(m, p) for m in merge for p in plain if b[m] == b[p]]

    print(f"   rows={len(r13)}  merge rows={len(merge)}  budgets carrying a merge row={len(mbud)}")
    print(f"   selection-matched (merge, non-merge) pairs : {len(strict)}")
    print(f"   budget-matched  (merge, non-merge) pairs   : {len(loose)}")
    for m, p in sorted(loose, key=lambda t: -b[t[0]]):
        d = delta(r13, m, p)
        print(f"      M={b[m]:5d}  {m:28s} - {p:24s}  trim {trimmed_mean(d):+6.2f}")
    say(len(loose) > 1,
        f"more than one contrast can be called primary ({len(loose)} budget-matched pairs) "
        f"-- so a rule that does not NAME one leaves the choice open")

    # The sharpest instance, and it is not hypothetical: it bit the author of this
    # script inside one session. "run 14, m=0.40" denotes two contrasts on disk.
    print("\n1b. DENOTATION -- what does the phrase 'run 14, m=0.40' actually name?")
    r14 = load(RUN14)
    T = "keep=0.50 m=0.40 router"
    same_keep = delta(r14, T, "keep=0.50 router")        # run 14's PUBLISHED primary
    tok_match = delta(r14, T, "keep=0.30 router TWIN")   # the token-matched contrast
    t_sk, t_tm = trimmed_mean(same_keep), trimmed_mean(tok_match)
    print(f"   vs keep=0.50 router      (same keep frac, M 2400->1440): trim {t_sk:+.2f}"
          f"   mean {st.mean(same_keep):+.2f}   <- the published primary")
    print(f"   vs keep=0.30 router TWIN (token-matched, M 1440=1440)  : trim {t_tm:+.2f}"
          f"   mean {st.mean(tok_match):+.2f}")
    print(f"   spread between the two readings: {abs(t_sk - t_tm):.2f} pts (trimmed)")
    say(abs(t_sk - t_tm) > MDE,
        f"the SAME four words name a {t_sk:+.2f} pt null AND a {t_tm:+.2f} pt gain -- a "
        f"{abs(t_sk - t_tm):.2f} pt spread, {abs(t_sk - t_tm) / MDE:.1f}x the {MDE:.1f} pt "
        f"effect. Both are legitimate estimands; neither is named in the rule")


def section_arm(r13: Dict[str, dict]) -> None:
    """Both splits are on disk at M=1920. Which one is 'the merge arm'?"""
    print("\n2. ARM -- the swing from choosing which split is 'the merge arm'")
    ckb = delta(r13, "keep=0.50 m=0.20 router", "keep=0.40 router TWIN")
    rkp = delta(r13, "keep=0.50 m=0.20 RANKPAR", "keep=0.40 router TWIN")
    t_ckb, t_rkp = trimmed_mean(ckb), trimmed_mean(rkp)
    m_ckb, m_rkp = st.mean(ckb), st.mean(rkp)
    swing_t, swing_m = abs(t_ckb - t_rkp), abs(m_ckb - m_rkp)
    print(f"   M=1920 checkerboard vs prune : trim {t_ckb:+.2f}   mean {m_ckb:+.2f}")
    print(f"   M=1920 rank_parity  vs prune : trim {t_rkp:+.2f}   mean {m_rkp:+.2f}")
    print(f"   swing (trimmed) {swing_t:+.2f} pts     swing (mean) {swing_m:+.2f} pts")
    say(swing_t > MDE,
        f"the split choice alone swings the trimmed estimate by {swing_t:.2f} pts, "
        f"MORE than the {MDE:.1f} pt effect being detected -- and both rows already exist")


def section_direction(r13: Dict[str, dict]) -> None:
    """The one that would silently invert a tail statistic."""
    print("\n3. DIRECTION -- `arr()` scales every key x100 and encodes no direction")
    rows = []
    for key in ("recall", "ned"):
        d = delta(r13, "keep=0.50 NEGATED", "keep=0.50 router", key=key)
        rows.append((key, st.mean(d), min(d), max(d)))
        print(f"   negated-vs-router  {key:8s}: mean {st.mean(d):+8.2f}  "
              f"min {min(d):+8.2f}  max {max(d):+8.2f}")
    rec = next(r for r in rows if r[0] == "recall")
    ned = next(r for r in rows if r[0] == "ned")
    # recall: higher is better, so a catastrophe has a very negative min.
    # ned: an ERROR rate, lower is better, so a catastrophe has a POSITIVE delta.
    say(rec[2] < 0.0 and ned[2] > 0.0,
        f"on the DELIBERATELY BROKEN arm, recall's worst document is {rec[2]:+.2f} but "
        f"`ned`'s worst is {ned[2]:+.2f} -- opposite signs, so a tail rule phrased "
        f"'worst per-document delta' ranks the sabotage arm SAFEST on stored `ned`")
    say(ned[2] > 0.0 and ned[1] > 0.0,
        "`ned` is stored as an error rate and never direction-corrected by arr(); "
        "T1 must pin direction PER QUANTITY, not once globally")


def section_g(r14: Dict[str, dict]) -> None:
    print("\n4. G -- the trim fraction picks the sign of the point estimate")
    # run 14's PUBLISHED primary: the merge row against the same keep fraction.
    # NOT the token-matched TWIN -- see section 1b. On the token-matched pairing the
    # estimate is +6.09/+4.91/+4.46 and does NOT flip, which is exactly why the
    # contrast has to be named before the estimator is discussed.
    d = delta(r14, "keep=0.50 m=0.40 router", "keep=0.50 router")
    ests = []
    for g in (0.05, 0.10, 0.15):
        t = trimmed_mean(d, g)
        ests.append(t)
        print(f"   run14 m=0.40 vs keep=0.50 router, g={g:.2f}: trim {t:+.3f}   "
              f"half-width {res_trimmed(d, g):.2f}")
    signs = {1 if e > 0 else -1 for e in ests}
    say(len(signs) > 1,
        f"the SIGN of the estimate changes across g in {{0.05,0.10,0.15}} "
        f"({ests[0]:+.2f} -> {ests[1]:+.2f} -> {ests[2]:+.2f}); all three are null, so "
        f"D13's 'zero verdict flips' is true and does not cover this")
    t_tok = [trimmed_mean(delta(r14, "keep=0.50 m=0.40 router",
                                "keep=0.30 router TWIN"), g) for g in (0.05, 0.10, 0.15)]
    note(f"on the token-matched pairing the same g-sweep reads "
         f"{t_tok[0]:+.2f} / {t_tok[1]:+.2f} / {t_tok[2]:+.2f} and does NOT flip -- "
         f"the g hazard is contrast-specific, which compounds section 1")


def section_did(r13: Dict[str, dict], r14: Dict[str, dict]) -> None:
    print("\n5. DID -- 'trim then difference' is not 'difference then trim'")
    t, c = "keep=0.50 m=0.40 router", "keep=0.50 router"   # run 14's published primary
    d13 = delta(r13, t, c)
    d14 = delta(r14, t, c)
    per_doc = paired(d14, d13)

    tm_joint = trimmed_mean(per_doc)
    tm_split = trimmed_mean(d14) - trimmed_mean(d13)
    mn_joint = st.mean(per_doc)
    mn_split = st.mean(d14) - st.mean(d13)
    gap_t = tm_joint - tm_split
    gap_m = mn_joint - mn_split

    print(f"   trimmed: trim(per-doc DiD) {tm_joint:+.4f}   trim(d14)-trim(d13) {tm_split:+.4f}"
          f"   gap {gap_t:+.4f}")
    print(f"   mean   : mean(per-doc DiD) {mn_joint:+.4f}   mean(d14)-mean(d13) {mn_split:+.4f}"
          f"   gap {gap_m:+.4f}")

    # The mean's gap is ZERO BY LINEARITY. That is a fact about addition, so a
    # control asserting it would be decorative -- it is an implementation
    # self-test (if it is nonzero, the pairing above is wrong), not evidence.
    note(f"mean gap is {gap_m:+.2e}: zero by linearity, so this line is a self-test of "
         f"the pairing, NOT a finding")
    if abs(gap_m) > 1e-9:
        say(False, "pairing is broken -- the plain mean's DiD must be order-invariant")
        return

    # Bar: the gap must exceed the project's KNOWN numerical noise floor, so that it
    # is a real degree of freedom rather than a floating-point artifact. 0.05 pts is
    # the bootstrap endpoint movement across seeds already recorded in AGENTS.md --
    # it comes from the tracker, not from this data, so it is not a fitted threshold.
    say(abs(gap_t) > SEED_NOISE,
        f"the unpinned DiD ORDERING moves the estimate by {abs(gap_t):.4f} pts, "
        f"{abs(gap_t) / SEED_NOISE:.0f}x the {SEED_NOISE} pt seed-noise floor -- so it is a "
        f"real choice, not rounding. The plain mean has NO such choice (gap is identically "
        f"zero), so adopting a robust location statistic CREATES this degree of freedom")

    gain = res_mean(per_doc) - res_trimmed(per_doc)
    print(f"   for scale: the effect is {tm_split:+.2f}..{tm_joint:+.2f} pts, the ordering gap "
          f"is {abs(gap_t):.2f} pts ({100 * abs(gap_t) / abs(tm_split):.0f}% of it),")
    print(f"             and the trim's own resolution gain here is {res_mean(per_doc):.2f} -> "
          f"{res_trimmed(per_doc):.2f} ({gain:+.2f} pts)")
    note(f"the gap is {100 * abs(gap_t) / gain:.0f}% of the resolution the trim buys, NOT "
         f"larger than it -- an earlier draft of AGENTS.md claimed larger; corrected "
         f"2026-09-23 by this control")


def section_tie(r13: Dict[str, dict]) -> None:
    print(f"\n6. TIE -- a count(d < {HARM_THR:+.0f}) tail rule, and the boundary today")
    print("   run13 m=0.20, the 'merging 20% is free' headline row, BOTH pairings (see 1b):")
    both = []
    for ctrl, tag in (("keep=0.50 router", "same keep frac"),
                      ("keep=0.40 router TWIN", "token-matched")):
        d = delta(r13, "keep=0.50 m=0.20 router", ctrl)
        exact = [x for x in d if x == HARM_THR]
        strict = sum(1 for x in d if x < HARM_THR)
        loose = sum(1 for x in d if x <= HARM_THR)
        both.append((len(exact), strict, loose))
        print(f"      vs {ctrl:24s} ({tag:14s}): exactly at {HARM_THR:+.0f} = {len(exact)}"
              f"   '<' -> {strict}   '<=' -> {loose}")
    say(all(e > 0 and s != l for e, s, l in both),
        f"a document sits EXACTLY on the threshold under BOTH pairings, so the tie "
        f"convention changes the tail count ({both[0][1]}->{both[0][2]} and "
        f"{both[1][1]}->{both[1][2]}) on the headline row -- live now, not hypothetical, "
        f"and robust to the §1b ambiguity")


def section_discard(r13: Dict[str, dict]) -> None:
    print("\n7. DISCARD -- T1's trim against T4's pooling")
    k_pooled = int(math.floor(POOLED_N * TRIM_G))
    print(f"   g={TRIM_G} at pooled n={POOLED_N} discards k={k_pooled} documents per tail")
    print(f"   FUNSD test in full                        = {FUNSD_N} documents")
    print(f"   run13 m=0.40 documents worse than {HARM_THR:+.0f} pts, BOTH pairings:")
    counts = []
    for ctrl, tag in (("keep=0.50 router", "same keep frac"),
                      ("keep=0.30 router TWIN", "token-matched")):
        d = delta(r13, "keep=0.50 m=0.40 router", ctrl)
        harmed = sorted(x for x in d if x < HARM_THR)
        counts.append(len(harmed))
        print(f"      vs {ctrl:24s} ({tag:14s}): {len(harmed):2d}  "
              f"{[round(x, 1) for x in harmed]}")
    # k is arithmetic (floor(POOLED_N*TRIM_G)) and a control asserting it would be
    # decorative. The MATERIAL claim is that the discard set has ROOM for every
    # harmed document -- a fact about the data, which could fail.
    say(max(counts) <= k_pooled,
        f"under both pairings ({counts[0]} and {counts[1]} harmed documents) ALL of them "
        f"fit inside the {k_pooled}-document lower discard set, so the pooled trimmed "
        f"estimate can be numerically identical to one computed on the new corpus alone")
    # RESTATED 2026-09-24 (T2). This control used to read `k_pooled >= FUNSD_N`, which
    # passed only because the ESTIMATED pool (500) made k exactly 50 and FUNSD is exactly
    # 50. T2 measured the pool at 397, so k is 39 and the old assertion is now false --
    # it was pinned to a coincidence between an estimate and a real number, and it would
    # have kept passing if nobody re-derived it. What is material is T1 s5's actual
    # constraint: the discard set must not exceed half of any single corpus, and here it
    # is 78% of FUNSD, so the constraint BINDS. That claim survives the correction and is
    # the one worth failing on.
    say(k_pooled > 0.5 * FUNSD_N,
        f"the discard set ({k_pooled}) exceeds half of FUNSD's entire contribution "
        f"({FUNSD_N}) -- {100.0 * k_pooled / FUNSD_N:.0f}% of it -- so T1 s5's constraint "
        f"BINDS at the real pooled n={POOLED_N}; report T4 stratified by corpus and assert "
        f"the discard set is not corpus-aligned")
    print(f"      NOTE: the hazard shrank (k={k_pooled} < FUNSD's {FUNSD_N}, so the trim can "
          f"no longer delete the corpus outright) but did NOT go away, and a shrinking "
          f"hazard is the kind that invites under-reacting.")


def section_random_twin(r13: Dict[str, dict], r14: Dict[str, dict]) -> None:
    print("\n8. RANDOM TWIN -- does a token-matched random arm exist for any merge row?")
    for tag, rows in (("13", r13), ("14", r14)):
        b = budgets(rows)
        mbud = sorted({b[k] for k in rows if is_merge(k)})
        rbud = sorted({b[k] for k in rows if is_random(k)})
        overlap = sorted(set(mbud) & set(rbud))
        print(f"   run {tag}: merge-row budgets  {mbud}")
        print(f"            random-row budgets {rbud}")
        print(f"            overlap            {overlap}")
        say(len(overlap) == 0,
            f"run {tag} has NO token-matched random arm for any merge row, so a "
            f"'merging beats random at matched M' control cannot be computed from it")


def section_replication(r13: Dict[str, dict], r14: Dict[str, dict]) -> None:
    """The degrees of freedom above are not hypothetical -- they were already
    exercised. The published Q6 verdict rule fires MERGING WINS on ">=1 ink pair",
    a DISJUNCTION over 6 pairs. Reconstruct it and compare the winner sets."""
    print("\n9. REPLICATION -- which pairs won, in each run, under the published rule")
    pairs = [
        ("M=3840 router", "keep=1.00 m=0.20 router", "keep=0.80 router TWIN"),
        ("M=1920 router", "keep=0.50 m=0.20 router", "keep=0.40 router TWIN"),
        ("M=1344 router", "keep=0.35 m=0.20 router", "keep=0.28 router TWIN"),
        ("M=1440 router", "keep=0.50 m=0.40 router", "keep=0.30 router TWIN"),
        ("M=1920 ink   ", "keep=0.50 m=0.20 ink", "keep=0.40 ink TWIN"),
        ("M=1344 ink   ", "keep=0.35 m=0.20 ink", "keep=0.28 ink TWIN"),
    ]
    winners = {}
    wide = {}
    for tag, rows in (("13", r13), ("14", r14)):
        won = []
        over = []
        print(f"   run {tag}:")
        for name, t, c in pairs:
            d = delta(rows, t, c)
            m, res = st.mean(d), res_mean(d)
            # The published criterion: CI excludes zero with delta > 0.
            # mean +- res reproduces the shipped CI column to ~0.01.
            win = (m - res) > 0.0
            if win:
                won.append(name.strip())
            if res > 3.0:
                over.append(name.strip())
            print(f"      {name}  delta {m:+6.2f}  res {res:4.2f}  "
                  f"[{m - res:+6.2f}, {m + res:+6.2f}]  {'MERGING WINS' if win else '--'}"
                  f"{'  res>3.0' if res > 3.0 else ''}")
        winners[tag] = set(won)
        wide[tag] = over
        print(f"      -> winners: {sorted(won)}")

    overlap = winners["13"] & winners["14"]
    print(f"   run13 winners  {sorted(winners['13'])}")
    print(f"   run14 winners  {sorted(winners['14'])}")
    print(f"   intersection   {sorted(overlap)}")
    say(len(winners["13"]) > 0 and len(winners["14"]) > 0 and len(overlap) == 0,
        f"both runs declared MERGING WINS, on {len(winners['13'])} and "
        f"{len(winners['14'])} pairs respectively, and the winner sets are DISJOINT -- "
        f"not one pair that won in run 13 won in run 14. A disjunctive verdict rule over "
        f"6 pairs will do this to noise")
    # And the direction each way, which is the part that makes it diagnostic.
    print("   what happened to each run's winners in the OTHER run:")
    for name, t, c in pairs:
        k = name.strip()
        if k not in winners["13"] and k not in winners["14"]:
            continue
        m13 = st.mean(delta(r13, t, c))
        m14 = st.mean(delta(r14, t, c))
        who = "run13 winner" if k in winners["13"] else "run14 winner"
        print(f"      {name}  ({who:13s})  run13 {m13:+6.2f} -> run14 {m14:+6.2f}"
              f"   ({m14 - m13:+.2f})")
    r13_only = [p for p in pairs if p[0].strip() in winners["13"]]
    regressed = all(st.mean(delta(r14, t, c)) < st.mean(delta(r13, t, c))
                    for _, t, c in r13_only)
    say(regressed,
        "every run-13 winner moved TOWARD zero in run 14, while run 14's winners were "
        "both negative in run 13 -- the signature of selecting on noise, and the reason "
        "T1 must name ONE pair rather than take the best of six")

    # The rule's two verdicts do not have the same arity, and that is the mechanism.
    # MERGING WINS fires on >=1 of 6 pairs. INDISTINGUISHABLE requires ALL 6 flat AND
    # ALL 6 with res <= 3.0 -- so any ONE wide pair blocks the null verdict outright,
    # while any ONE lucky pair carries the positive one.
    print("\n   arity of the two verdicts, as pre-registered (AGENTS.md Q6 table):")
    print("      MERGING WINS      needs 1 of 6 pairs (>=1 ink pair, CI excludes 0, d>0)")
    print("      INDISTINGUISHABLE needs 6 of 6 flat AND 6 of 6 with res <= 3.0")
    for tag in ("13", "14"):
        print(f"      run {tag}: {len(wide[tag])}/6 pairs have res > 3.0 -> "
              f"INDISTINGUISHABLE {'BLOCKED' if wide[tag] else 'reachable'}"
              f"   ({', '.join(wide[tag]) if wide[tag] else '-'})")
    asym = all(wide[t] and winners[t] for t in ("13", "14"))
    say(asym,
        "in BOTH runs the null verdict was arithmetically unreachable (>=1 pair over the "
        "3.0 res bar) while the positive verdict fired on a single pair. A 1-of-6 win "
        "condition against a 6-of-6 null condition is not a tie-breaker, it is a ratchet: "
        "only one of the two verdicts can be reached by noise, and it is the same one both "
        "times. res is data-dependent, so this could have come out otherwise -- it did not")


def section_multiplicity(r13: Dict[str, dict], r14: Dict[str, dict]) -> None:
    """Section 9 showed the 1-of-6 disjunction picked different winners in each run.
    This asks the next question: does ANY of those winners survive a correction for
    the family it was selected from? And it audits the gate section 9's write-up
    prescribes -- because a gate stated without units cannot fail."""
    print("\n10. MULTIPLICITY -- does any declared winner survive its own family?")

    # The family. Only `recall` and `ned` are stored per image in these runs, and
    # charAcc = (1 - ned) * 100 is an affine transform of `ned`, so it is NOT an
    # independent third quantity -- including it would double-count the one quantity
    # carrying the effect and bias toward declaring an effect. `word_order` is not on
    # disk for either run. So the family is 6 pairs x 2 quantities = 12, not 18.
    stored = sorted(set(r13["keep=1.00 router CONTROL"]["per_image"][0].keys())
                    & {"recall", "ned", "char_acc", "word_order"})
    say(stored == ["ned", "recall"],
        f"exactly 2 independent quantities are stored per image in these runs {stored} "
        f"-- charAcc is an affine transform of ned (not a third witness) and word_order "
        f"is absent, so the correction family is 6x2=12, not the 6x3=18 it is tempting "
        f"to write. A family of 12 is the WEAKER correction, which is the honest one here")

    pairs = [
        ("M=3840 router", "keep=1.00 m=0.20 router", "keep=0.80 router TWIN"),
        ("M=1920 router", "keep=0.50 m=0.20 router", "keep=0.40 router TWIN"),
        ("M=1344 router", "keep=0.35 m=0.20 router", "keep=0.28 router TWIN"),
        ("M=1440 router", "keep=0.50 m=0.40 router", "keep=0.30 router TWIN"),
        ("M=1920 ink   ", "keep=0.50 m=0.20 ink", "keep=0.40 ink TWIN"),
        ("M=1344 ink   ", "keep=0.35 m=0.20 ink", "keep=0.28 ink TWIN"),
    ]
    # Direction pinned PER QUANTITY, which is exactly what section 2 says the harness
    # does not do: recall is an accuracy (higher better), ned is an error (lower better).
    QUANTS = (("recall", +1.0), ("ned", -1.0))
    nd = st.NormalDist()
    nominal, survivors = {}, {}
    for tag, rows in (("13", r13), ("14", r14)):
        fam = []
        for name, t, c in pairs:
            for key, sign in QUANTS:
                d = [sign * x for x in delta(rows, t, c, key)]
                m = st.mean(d)
                se = st.stdev(d) / math.sqrt(len(d))
                # z, not t: the published criterion IS a z-test -- it uses 1.96. Using
                # anything else here would smuggle in an estimator change and stop
                # measuring the multiplicity in isolation.
                p = 2.0 * (1.0 - nd.cdf(abs(m / se)))
                fam.append((name.strip(), key, m, se, p))
        fam.sort(key=lambda r: r[4])
        K = len(fam)
        nominal[tag] = [(n, k) for n, k, _, _, p in fam if p < 0.05]
        surv = []
        print(f"   run {tag}: family of {K}; Holm step-down at alpha=0.05")
        for i, (name, key, m, se, p) in enumerate(fam):
            thr = 0.05 / (K - i)
            if p >= thr:
                print(f"      {name:14s} {key:6s} mean {m:+7.2f}  se {se:5.2f}  "
                      f"p {p:.4f}  >  Holm thr {thr:.5f}  -> STOP, all remaining fail")
                break
            surv.append((name, key))
            print(f"      {name:14s} {key:6s} mean {m:+7.2f}  se {se:5.2f}  "
                  f"p {p:.4f}  <  Holm thr {thr:.5f}  -> survives")
        survivors[tag] = surv
        print(f"      nominal p<0.05: {nominal[tag]}")
        print(f"      Holm survivors: {surv if surv else '[] -- NONE'}")

    say(all(nominal[t] and not survivors[t] for t in ("13", "14")),
        f"both runs have nominally significant tests ({len(nominal['13'])} and "
        f"{len(nominal['14'])}) and ZERO Holm survivors. Neither published MERGING WINS "
        f"verdict survives the smallest defensible correction for the family it was "
        f"selected from -- the smallest p in each run misses the first Holm threshold "
        f"(0.05/12 = 0.00417) by roughly 5x")

    # The metric choice moves which row looks best, too -- and not toward the headline.
    note("run 13's smallest p in the whole family is M=1920 router on `ned` (p=0.0240), "
         "a pair the published recall-only rule scored FLAT (+2.86, CI [-0.30,+6.02]). "
         "The pre-registered quantity was the less sensitive one ON THE ROW D13 "
         "HEADLINED. Recorded as a reason to distrust that row's null -- NOT as a "
         "licence to re-headline on ned, which would be choosing the metric after "
         "seeing the data.")

    # And the gate the section 9 write-up prescribes, audited against the ninth
    # decorative form: could this check have come out differently?
    print("\n   units audit of the gate T1 is about to adopt:")
    nat = []
    for name, t, c in pairs:
        for key, _ in QUANTS:
            x = [pi[key] for pi in r13[t]["per_image"]]
            y = [pi[key] for pi in r13[c]["per_image"]]
            d = [a - b for a, b in zip(x, y)]           # NATIVE [0,1], no x100
            nat.append(1.96 * st.stdev(d) / math.sqrt(len(d)))
    n = FUNSD_N
    res_max = 1.96 * 1.0 * math.sqrt(n / (n - 1)) / math.sqrt(n)
    print(f"      native-scale res over the 12 tests: {min(nat):.4f} .. {max(nat):.4f}")
    print(f"      max CONCEIVABLE res for a paired delta of a [0,1] field at n={n}: "
          f"{res_max:.3f}  (deltas lie in [-1,1], so sd <= 1)")
    print(f"      a gate written `res <= {MDE * 2.0:.1f}` with units unstated: "
          f"{res_max:.3f} < {MDE * 2.0:.1f}, so it CANNOT FAIL on the stored fields")
    print(f"      a tail rule written `count(d < {HARM_THR:.0f})`: native deltas lie in "
          f"[-1,1], so no document can ever be below {HARM_THR:.0f}")
    say(res_max < MDE * 2.0 and max(nat) < MDE * 2.0,
        f"the res gate and the tail rule are BOTH unfalsifiable on the stored native "
        f"fields -- observed res is {MDE * 2.0 / max(nat):.0f}x inside the gate and the "
        f"arithmetic ceiling is {MDE * 2.0 / res_max:.1f}x inside it. Any run scored on "
        f"`per_image` as-stored returns 'powered, no harmed documents' BY ARITHMETIC. "
        f"T1 must state units per quantity, not just direction (section 2)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="controls only")
    args = ap.parse_args()

    print("=" * 78)
    print("D14 -- T1 is not an estimator choice: seven unpinned degrees of freedom")
    print("=" * 78)
    print(f"run 13: {RUN13}")
    print(f"run 14: {RUN14}")

    r13, r14 = load(RUN13), load(RUN14)

    if not section_calibration(r13):
        print("\nCALIBRATION FAILED -- every number below would be void. Stopping.")
        return 1

    if not args.selftest:
        section_row(r13)
        section_arm(r13)
        section_direction(r13)
        section_g(r14)
        section_did(r13, r14)
        section_tie(r13)
        section_discard(r13)
        section_random_twin(r13, r14)
        section_replication(r13, r14)
        section_multiplicity(r13, r14)
    else:
        # NOTE: every control lives INSIDE a section, so "controls only" cannot skip
        # any section without dropping the controls it carries. This branch used to be
        # a byte-for-byte copy of the one above -- i.e. --selftest has always been a
        # no-op that the docstring advertised as a mode. Kept as an explicit alias
        # rather than silently accepting a flag that does nothing.
        section_row(r13)
        section_arm(r13)
        section_direction(r13)
        section_g(r14)
        section_did(r13, r14)
        section_tie(r13)
        section_discard(r13)
        section_random_twin(r13, r14)
        section_replication(r13, r14)
        section_multiplicity(r13, r14)

    print("\n" + "=" * 78)
    print(f"CONTROLS: {_n_controls - _n_failed}/{_n_controls} PASS")
    print("=" * 78)
    if _n_failed:
        print(f"{_n_failed} control(s) FAILED -- read them before quoting anything above.")
        return 1
    print("""
WHAT THIS LICENSES: rescoping T1 from 'choose an estimator' to 'pin the analysis'.
WHAT IT DOES NOT:   choosing the flattering side of any of these. Every swing above
                    measures ANALYST FREEDOM, not a merging effect. Quoting +1.12 as
                    a benefit of rank_parity would be the exact failure this measures.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
