"""One-shot: insert T3's file-map row into AGENTS.md immediately after T2's.

Why a script rather than an Edit: T2's row is a single ~2,800-char line and the anchor has to
be matched exactly. Anchoring on the short, unique `scripts/verify_corpus_grain.py` cell prefix
and inserting *after* that whole line is safer than reproducing the line to match on.

Asserts before and after, because an insert that silently no-ops or fires twice is the failure
mode that looks like success. Delete this file once run (T8 tracks the scratch probes).
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(HERE, "AGENTS.md")

ANCHOR = "| — | `scripts/verify_corpus_grain.py` |"
NEW_KEY = "`scripts/score_preregistered.py`"

ROW = (
    "| — | `scripts/score_preregistered.py` | **T3's artifact (2026-09-24, local, 45/45 "
    "controls, exit 0, `results/score_preregistered_local.log`).** The **executable** form of "
    "T1 §§2–7, which existed only as prose until this file. Scores runs 13/14 on the "
    "pre-registered primary (`keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN`, token-matching at "
    "M=1920 asserted **from disk**), on claim 3's own same-keep rows **in a separate section "
    "that never pools with it** (D14 §1b's 5.08 pt hazard), and on a consistent keep=1.00 "
    "baseline. **Calibrated against the nine figures T1 recorded before this file existed** — "
    "all reproduce, and the load-bearing one is that the matched-null p95 **tightens** 1.74 → "
    "1.52 → 1.51 as n goes 50 → 307 → 397, which a constant typed in and called a null could "
    "not do (D14 §10's failure mode). **Eight discriminating controls show each pinned choice "
    "is load-bearing:** the naive SE is **35% smaller** than Tukey–McLaughlin (0.6383 vs "
    "0.9792); difference-then-trim moves the estimate **0.2555 pts** while **the same "
    "comparison on the plain mean is identically zero (−8.55e-15)**, so the non-additivity is a "
    "property of *trimming*, not of the data; sign-flipping `ned` changes the tail it reports "
    "(−23.50 → −29.66); in **points** the harm rule counts **5** where on the stored `[0,1]` "
    "field it counts **0**; and the harmed-count p95 is **7** on run 13 but **4** on run 14 "
    "*under the same rule*, because the bar is matched per row — **so counts are not comparable "
    "across rows and must be quoted with their null**. The gate also **fires on run 14 (3.22) "
    "and not on run 13 (1.11)**, so it is not a gate that fires on everything or nothing. "
    "**Result: `UNDERPOWERED` in both runs, zero Holm survivors, and run 14 is not scored "
    "`FREE` despite a +0.02 pt trimmed mean because both its recall tail gates fail** — the one "
    "behaviour T1 §3 exists to produce. **§5 is the section to read:** it runs D13 §5's "
    "untreated control, which had never run, and finds T1 §3's tail gate **is not specific to "
    "merging** — **13 of 21** contrasts with no merging clear 1.74, and the sweep's worst "
    "per-document loss (**−80.85 pts**) and highest ratio (**5.43**) both belong to "
    "`keep=0.75 ink ORACLE`, where nothing is merged. The failure is **specificity, not "
    "sensitivity** (`keep=1.00 router CONTROL` passes at 1.47); there is **no zero-treatment "
    "null on disk** (no config repeats within a run, decode is bit-identical on re-run, and "
    "runs 13/14 differ by a retrained checkpoint); and the gate is **not reversal-invariant** — "
    "swapping arms flips **10 of 28** verdicts. `--selftest` runs the same controls and is what "
    "CI should call. See `## Runs 13/14 re-scored under the run-17 rule (T3)`. |\n"
)


def main():
    with io.open(PATH, encoding="utf-8") as fh:
        lines = fh.readlines()

    # Idempotence: refuse to run twice rather than quietly duplicating the row.
    already = [i for i, ln in enumerate(lines) if NEW_KEY in ln and ln.startswith("| — |")]
    if already:
        print("ALREADY PRESENT at line %d -- nothing to do" % (already[0] + 1))
        return 0

    hits = [i for i, ln in enumerate(lines) if ln.startswith(ANCHOR)]
    if len(hits) != 1:
        print("FAIL: expected exactly 1 anchor, found %d" % len(hits))
        return 1

    at = hits[0]
    lines.insert(at + 1, ROW)

    with io.open(PATH, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(lines)

    # Verify by re-reading, not by trusting the in-memory list.
    with io.open(PATH, encoding="utf-8") as fh:
        after = fh.readlines()
    got = [i for i, ln in enumerate(after) if NEW_KEY in ln and ln.startswith("| — |")]
    assert len(got) == 1, "expected exactly one new row, got %d" % len(got)
    assert len(after) == len(lines), "line count drifted"
    assert after[at].startswith(ANCHOR), "anchor moved"
    print("OK: inserted at line %d, immediately after T2's row at %d" % (got[0] + 1, at + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
