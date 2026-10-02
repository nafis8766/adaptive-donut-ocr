#!/usr/bin/env python
"""Execute cell 2's checkpoint-identity guards under four scenarios, two of which MUST raise.

WHY THIS FILE EXISTS
--------------------
PATCH A's comment block promised an eval-only checkpoint guard in the present tense --
"they must not merely be disabled -- they are replaced by the eval-only guard added
below, or T4 repeats run 12 exactly" -- and did not write it. For two days (2026-09-30 to
2026-10-02) the generator shipped `DO_TRAIN = False` with BOTH `_VS_RUN9` identity asserts
dormant (they are gated on `_VS_RUN9`, which is False whenever DO_TRAIN is False) and no
replacement. The only live guard was `assert DO_TRAIN or RESUME_CKPT`, which demands *a*
checkpoint and never the RIGHT one.

That gap is the run-12 failure mode exactly: attach run 5's merge-naive, pruning-naive
weights, every existence check passes, the identity line prints "run 5 (pre-pruning)",
no assert fires, 29 rows sweep on an anti-selective router, and the headline is an
artifact. Run 12 cost a GPU session to learn this once.

So the guard is written -- and this file is the reason to believe it works. It is NOT a
restatement of the guard: it locates the shipped `if RESUME_CKPT:` statement in the
GENERATED notebook by `ast` and `exec`s it, so a future regeneration that drops or
weakens the assert turns this red. (The diagnose_tome_parity lesson: a checker that
declares its own copy of the logic under test cannot fail.)

THE FOUR SCENARIOS, and why two must raise
------------------------------------------
The two guards point in OPPOSITE directions, which is the whole reason one assert cannot
serve both and why this matrix is the minimum that distinguishes them:

  DO_TRAIN  checkpoint      must    because
  --------  --------------  ------  -------------------------------------------------
  False     pruning-era     PASS    T4: pooled rows extend runs 13/14 (run 9's wts)
  False     run 5           RAISE   run 12 reproduced -- the defect this guard closes
  False     unrecognised    RAISE   a checkpoint nobody characterised
  True      run 5           PASS    run 14/18: retrains, so it must START from run 5

A guard verified only in the state it was written in is half-tested, and the half you
cannot see is the one that matters. Rows 2 and 3 are that half.

Usage:  PYTHONPATH=. python -u scripts/verify_eval_only_ckpt_gate.py [notebook.ipynb]
"""
import ast
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")  # cp1252 would kill this on the arrows below

NB = sys.argv[1] if len(sys.argv) > 1 else "kaggle_pruning_run.ipynb"

RUN5_BYTES = 1045901275
PRUNED_BYTES = 1045901771
WEIRD_BYTES = 999999999

_passed = 0
_failed = 0


def check(label, ok, detail=""):
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


# ---------------------------------------------------------------- extract the shipped code
# Select the cell by a UNIQUE MARKER, not by index. Two reasons, both already in AGENTS.md:
# (1) the tracker numbers cells by their index in the .ipynb JSON, which includes markdown
#     cells, and past cell splits have desynchronised that from the notebook's own
#     "# Cell N:" headers -- the config cell is JSON index 2 but CODE index 1, so a
#     `[c for c in cells if code][2]` filter silently lands on a different cell entirely.
#     That is exactly the mistake this file made on its first run (found 0 guard blocks).
# (2) `RESUME_CKPT` alone is NOT a usable marker -- the Phase 2c hotfix moved it into cell 2
#     and broke verify_decode_ablation.py's `next(c for c in cells if "RESUME_CKPT" in c)`
#     the same way. Key on the pair that only the config cell has: the DO_TRAIN assignment
#     and the byte constants.
_MARKER = "RUN5_CKPT_BYTES = "
_hits = [i for i, c in enumerate(json.load(open(NB, encoding="utf-8"))["cells"])
         if c["cell_type"] == "code" and _MARKER in "".join(c["source"])]
check(f"exactly one cell defines {_MARKER.strip()} (config cell located by marker, not index)",
      len(_hits) == 1, f"matched JSON cell indices {_hits}")
if len(_hits) != 1:
    raise SystemExit(f"\ncannot proceed: {_MARKER.strip()} matched {len(_hits)} cells")

c2 = "".join(json.load(open(NB, encoding="utf-8"))["cells"][_hits[0]]["source"])
print(f"  [info] config cell is JSON index {_hits[0]}")
tree = ast.parse(c2)

# The guard block is the `if RESUME_CKPT:` statement. Anchor on the TEST, not on a line
# number or a substring of the body -- the body is what we are testing and will change.
guards = [n for n in tree.body
          if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
          and n.test.id == "RESUME_CKPT"]
check("the config cell contains exactly one `if RESUME_CKPT:` guard block",
      len(guards) == 1, f"found {len(guards)}")
if len(guards) != 1:
    raise SystemExit(f"\ncannot proceed: expected 1 guard block, found {len(guards)}")
GUARD = guards[0]

# The size constants must come from the notebook too, or this file would be asserting
# against its own idea of what a run-5 checkpoint weighs.
consts = {}
for n in tree.body:
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("RUN5_CKPT_BYTES", "PRUNED_CKPT_BYTES")
            for t in n.targets):
        exec(compile(ast.Module([n], []), "<nb>", "exec"), {}, consts)
check("the notebook's RUN5_CKPT_BYTES matches this file's expectation",
      consts.get("RUN5_CKPT_BYTES") == RUN5_BYTES,
      f"notebook {consts.get('RUN5_CKPT_BYTES')}, here {RUN5_BYTES}")
check("the notebook's PRUNED_CKPT_BYTES matches this file's expectation",
      consts.get("PRUNED_CKPT_BYTES") == PRUNED_BYTES,
      f"notebook {consts.get('PRUNED_CKPT_BYTES')}, here {PRUNED_BYTES}")

# NON-VACUITY: the guard body must actually contain an assert keyed on DO_TRAIN. Without
# this, a regeneration that deleted the new assert would leave every "must PASS" row green
# and both "must RAISE" rows red -- readable, but only if someone reads the matrix. This
# says it in one line.
body_src = ast.dump(GUARD)
check("the guard body contains an assert mentioning DO_TRAIN (the eval-only gate exists)",
      any(isinstance(n, ast.Assert) and "DO_TRAIN" in ast.dump(n)
          for n in ast.walk(GUARD)),
      "else the two RAISE rows below are failing for the wrong reason")
check("the guard body still contains the _VS_RUN9 assert (the train-side gate survives)",
      "_VS_RUN9" in body_src)


# ---------------------------------------------------------------- run it
class _StubOS:
    """Only getsize is reachable from the guard; anything else is a defect worth raising."""

    def __init__(self, size):
        self._size = size
        self.path = self

    def getsize(self, _p):
        return self._size


def run_guard(do_train, size):
    """exec the SHIPPED guard statement. Returns (raised, message)."""
    ns = {
        "RESUME_CKPT": "/kaggle/input/whatever/adaptive_donut.pt",
        "DO_TRAIN": do_train,
        "os": _StubOS(size),
        "RUN5_CKPT_BYTES": consts["RUN5_CKPT_BYTES"],
        "PRUNED_CKPT_BYTES": consts["PRUNED_CKPT_BYTES"],
        # _VS_RUN9 mirrors cell 2: True only when DO_TRAIN and a one-variable knob is set.
        # For the DO_TRAIN=True row we set it True so the train-side assert is LIVE, which
        # is what makes that row a real test of "run 14 still works" rather than a vacuous
        # pass through a dormant branch.
        "_VS_RUN9": bool(do_train),
        "_VS_RUN9_WHY": "TRAIN_MERGE_RATIO=0.4 (run 14)",
        "print": lambda *a, **k: None,
    }
    try:
        exec(compile(ast.Module([GUARD], []), "<nb>", "exec"), ns, ns)
        return False, ""
    except AssertionError as e:
        return True, str(e)
    except Exception as e:                                            # noqa: BLE001
        return True, f"UNEXPECTED {type(e).__name__}: {e}"


print("\n" + "=" * 74)
print("the four scenarios -- two must raise")
print("=" * 74)

SCENARIOS = [
    (False, PRUNED_BYTES, False,
     "DO_TRAIN=False + pruning-era  -> PASS (T4: extends runs 13/14)"),
    (False, RUN5_BYTES, True,
     "DO_TRAIN=False + run 5        -> RAISE (run 12 reproduced)"),
    (False, WEIRD_BYTES, True,
     "DO_TRAIN=False + unrecognised -> RAISE (uncharacterised weights)"),
    (True, RUN5_BYTES, False,
     "DO_TRAIN=True  + run 5        -> PASS (run 14/18 starts from run 5)"),
]

for do_train, size, must_raise, label in SCENARIOS:
    raised, msg = run_guard(do_train, size)
    ok = raised == must_raise
    detail = ""
    if raised and msg.startswith("UNEXPECTED"):
        ok = False
        detail = msg
    elif raised != must_raise:
        detail = f"raised={raised}, expected raise={must_raise}"
    check(label, ok, detail)

# The two RAISE rows must raise for DIFFERENT, NAMED reasons -- not merely both raise.
# A guard that rejected everything would score 2/2 on them.
_, m_run5 = run_guard(False, RUN5_BYTES)
_, m_weird = run_guard(False, WEIRD_BYTES)
check("the run-5 rejection names run 5 and run 12, not a generic size complaint",
      "run 5" in m_run5 and "run 12" in m_run5,
      m_run5[:70] + "...")
check("the unrecognised rejection reports the actual byte count it saw",
      str(WEIRD_BYTES) in m_weird,
      m_weird[:70] + "...")

# DISCRIMINATING CONTROL: the gate must be the reason row 2 raises. Flip ONLY DO_TRAIN on
# the identical checkpoint and the verdict must flip -- that is what "eval-only gate"
# means. If both raise or neither does, the assert is keyed on something else.
r_false, _ = run_guard(False, RUN5_BYTES)
r_true, _ = run_guard(True, RUN5_BYTES)
check("DO_TRAIN is the ONLY thing separating those two verdicts on identical weights",
      r_false is True and r_true is False,
      f"DO_TRAIN=False raised={r_false}, DO_TRAIN=True raised={r_true}")

# ...and the mirror, so neither direction is vacuous: on PRUNING-ERA weights the verdicts
# invert, because run 14 must NOT start from a pruning-era checkpoint.
r_pf, _ = run_guard(False, PRUNED_BYTES)
r_pt, _ = run_guard(True, PRUNED_BYTES)
check("on pruning-era weights the two verdicts INVERT (the guards oppose each other)",
      r_pf is False and r_pt is True,
      f"DO_TRAIN=False raised={r_pf}, DO_TRAIN=True raised={r_pt}")

print("\n" + "=" * 74)
print(f"CONTROLS: {_passed}/{_passed + _failed} PASS"
      + (f"   |   {_failed} FAILED" if _failed else "")
      + f"   |   notebook: {NB}")
print("=" * 74)
if _failed:
    raise SystemExit(1)
