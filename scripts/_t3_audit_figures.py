"""One-shot audit: does every figure T3 wrote into the prose resolve to the scorer's log?

The rule this implements is [[correct-numbers-by-grepping-digits]] applied to my own new prose:
search the literal number, not the topic. T3 transcribed ~60 figures into AGENTS.md and
README.md from `results/score_preregistered_local.log`; a transcription error would read as a
measurement and would outlive the section it sits in.

NORMALISATION IS LOAD-BEARING. The docs use U+2212 MINUS SIGN, the log uses ASCII hyphen. The
existing `check_writeup_numbers.py` had exactly this bug in section 6 -- it folded U+2212 on the
writeup side only and read AGENTS.md raw, so every signed figure was STRUCTURALLY unable to match
and would have reported "NOT IN THE LOG" for a number plainly there. Both sides are folded here.

Output is a WORKLIST, not a verdict. Many figures in these regions legitimately come from
elsewhere (M1's byte table, D13, D14, T1's simulations, T2's corpus counts), so a miss is a thing
to classify, not automatically an error. What matters is that no figure I claimed as T3-derived
is missing.

Delete this file once read (T8 tracks the scratch probes).
"""
import io
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # cp1252 would kill this mid-run; see Gotchas

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = os.path.join(HERE, "AGENTS.md")
README = os.path.join(HERE, "README.md")
LOG = os.path.join(HERE, "results", "score_preregistered_local.log")

# (label, start-line, end-line) 1-indexed inclusive -- the regions T3 wrote or rewrote.
REGIONS = [
    ("claim 3 (merge para)", 440, 510),
    ("M1 SUPERSEDED block", 3335, 3360),
    ("T1 s3 AMENDMENT", 4331, 4365),
    ("T3 section", 4631, 4806),
    ("file-map row", 605, 605),
]


def fold(s):
    """Normalise both sides identically: unicode minus -> ascii, strip thousands commas."""
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = re.sub(r"(?<=\d),(?=\d\d\d\b)", "", s)
    return s


# Figures that are legitimately NOT from this log, with the source they do come from.
# Anything here is asserted to be non-T3 -- if one of these ever *should* have come from the
# scorer, that is the interesting failure and it belongs in the miss list instead.
KNOWN_ELSEWHERE = {
    # M1's byte table (results/kv_memory_*.json)
    "150.00", "60.00", "52.50", "45.00", "42.00", "120.00", "30.00", "75.00", "19.46",
    "771", "65.0", "0.26", "0.18", "3.33", "3.57", "1.25", "2.50", "4800", "2400", "1920",
    "1440", "1344", "3840", "1680", "960", "3600", "1200",
    # D13 / D14 / T1 / T2 figures quoted as context
    "5.08", "75.6", "1.49", "2.15", "2.33", "3.47", "11.30", "12.81", "11.28", "10.55",
    "11.40", "12.94", "0.10", "0.05", "0.15", "1.96", "0.375", "0.25", "20260924", "40",
    "397", "347", "100", "50", "307", "185", "0.57", "0.92", "5.00", "8.82", "1.62",
    "12.6", "87.4", "82.2", "39", "78", "1.0", "2.0", "3.0", "0.0", "10.0", "28", "21",
    "13", "14", "17", "12", "6", "3", "2", "1", "0", "5", "4", "7", "8", "9", "10", "11",
    # run-table / claim-3 legacy figures being struck
    "79.63", "80.17", "77.30", "77.74", "64.70", "53.05", "0.353", "0.352", "64.81",
    "54.08", "78.87", "61.76", "50.13", "0.382", "78.25", "2026", "2.05", "1.20",
    # section refs and dates
    "0.05", "45", "89", "35", "181", "26", "42", "16",
}


def numbers_in(text):
    """Every numeric token, signed/decimal aware, as it appears after folding."""
    return set(re.findall(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?", fold(text), flags=re.I))


def main():
    with io.open(LOG, encoding="utf-8") as fh:
        log = fold(fh.read())
    log_nums = numbers_in(log)

    with io.open(AGENTS, encoding="utf-8") as fh:
        agents_lines = fh.readlines()
    with io.open(README, encoding="utf-8") as fh:
        readme = fh.read()

    regions = []
    for label, a, b in REGIONS:
        regions.append((label, "".join(agents_lines[a - 1:b])))
    regions.append(("README.md (whole file)", readme))

    print("LOG: %d distinct numeric tokens in %s" % (len(log_nums), os.path.basename(LOG)))
    print()

    total_missing = 0
    for label, text in regions:
        nums = numbers_in(text)
        missing = sorted(n for n in nums
                         if n not in log_nums
                         and n.lstrip("-") not in KNOWN_ELSEWHERE
                         and n not in KNOWN_ELSEWHERE)
        hit = len(nums) - len(missing)
        print("=" * 78)
        print("%-24s  %3d figures, %3d resolve to the log, %3d to classify"
              % (label, len(nums), hit, len(missing)))
        if missing:
            print("  to classify: %s" % ", ".join(missing))
        total_missing += len(missing)

    print("=" * 78)
    print("TOTAL to classify: %d" % total_missing)
    print()
    print("A figure in the 'to classify' list is NOT automatically wrong -- it is a figure whose")
    print("source is not this log. Read each one in context and confirm it has a source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
