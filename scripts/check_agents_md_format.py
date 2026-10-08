"""Structural lint for AGENTS.md -- the file is the project's source of truth, and it is
edited by hand often enough that a broken table or an unclosed fence is a real risk.

Checks three things a reader would notice and a diff would not:
  1. code fences balance (an odd count swallows the rest of the file into a code block)
  2. no ragged tables (a row with a different column count than its header renders wrong)
  3. no unresolved edit-marker debris (stray '>>>>>>>', '<<<<<<<', or a leading '> #'
     from a botched paste)

Escaped pipes (\\|) inside table cells are literal text, not column separators, so they
are stripped before counting -- otherwise every cell containing |x| reads as ragged.

Usage:
    python scripts/check_agents_md_format.py [path]
Exit 0 iff clean.
"""
import os
import re
import sys

# 2026-10-05: this script PRINTS the offending lines, so it prints whatever non-ASCII
# AGENTS.md contains -- and that file is full of em dashes, arrows, x signs and (as of
# the project-closure banner) U+26D4. Windows' default console codec is cp1252, so
# without this the run died with UnicodeEncodeError and exit code 1 AFTER reporting
# "1 PROBLEM(S)" but BEFORE naming it: the crash masked the real finding, and the exit
# code was indistinguishable from the lint failing. Reconfigure rather than document a
# PYTHONIOENCODING prefix -- the docstring above used to carry one, and the failure mode
# is forgetting it. Same fix, and the same reason, as check_writeup_numbers.py.
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "AGENTS.md")
lines = open(path, encoding="utf-8").read().splitlines()

problems = []

# ------------------------------------------------------------------ 1. fences
fences = [i + 1 for i, l in enumerate(lines) if l.strip().startswith("```")]
if len(fences) % 2:
    problems.append(f"odd number of code fences ({len(fences)}); last at line {fences[-1]}")
print(f"code fences        : {len(fences)} ({'balanced' if len(fences) % 2 == 0 else 'ODD'})")

# Rows inside a fenced block are code, not tables.
in_fence = set()
open_at = None
for i, l in enumerate(lines, 1):
    if l.strip().startswith("```"):
        open_at = i if open_at is None else None
    elif open_at is not None:
        in_fence.add(i)


def ncols(line):
    body = re.sub(r"\\\|", "", line.strip())        # drop escaped pipes first
    return len(body.strip("|").split("|"))


# ------------------------------------------------------------------ 2. tables
ragged, tables = [], 0
hdr = start = None
for i, l in enumerate(lines, 1):
    s = l.strip()
    is_row = s.startswith("|") and s.endswith("|") and i not in in_fence and len(s) > 1
    if is_row and hdr is None:
        hdr, start, tables = ncols(l), i, tables + 1
    elif is_row:
        if ncols(l) != hdr:
            ragged.append((i, ncols(l), start, hdr))
    elif hdr is not None:
        hdr = start = None
print(f"tables             : {tables}, ragged rows: {len(ragged)}")
for i, got, hline, want in ragged:
    problems.append(f"line {i}: {got} columns, header at line {hline} has {want}")

# ------------------------------------------------------------------ 3. debris
DEBRIS = (">>>>>>>", "<<<<<<<", "=======" * 2)
for i, l in enumerate(lines, 1):
    if l.startswith(DEBRIS) or re.match(r"^>\s+#", l):
        problems.append(f"line {i}: edit debris -- {l[:60]!r}")
print(f"edit debris        : {sum(1 for p in problems if 'debris' in p)}")

print(f"total lines        : {len(lines)}")
print()
if problems:
    print(f"{len(problems)} PROBLEM(S):")
    for p in problems:
        print(f"  - {p}")
raise SystemExit(1 if problems else 0)
