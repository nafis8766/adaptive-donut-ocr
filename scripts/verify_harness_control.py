"""Verify cell 15's HARNESS CONTROL (Pending 4) -- statically AND by executing it.

The block swaps the model's weights out and back in the middle of a 40-minute GPU run.
The failure that matters is not "the control reports a wrong number" but "the restore
silently didn't happen", because then all 15 sweep rows measure the control checkpoint
while producing a table that looks completely ordinary. A grep cannot tell you whether
the block prevents that, so this script extracts the source text out of the notebook and
runs it against a stub model under seven scenarios, including two that must raise.

Sections:
  1. static shape -- the asserts and the meta stamps are present, and the control row is
     kept OUT of `rows` (it shares (1.00, 'router') with row 0, so appending it would
     silently overwrite the real control in the `by` lookup)
  2. execution -- happy path, drifted path, partial load, broken restore, both skip paths
  3. fingerprint -- proves it covers every parameter, not a sample that a router-only
     change would slip past

Usage:
    PYTHONIOENCODING=utf-8 python scripts/verify_harness_control.py [notebook]
Defaults to the canonical notebook; pass kaggle_pruning_run.ipynb to check the file that
actually runs on Kaggle (the generator copies cell 15 verbatim, but verify, don't assume).
Exit 0 iff every check passes.
"""
import json
import os
import sys
import tempfile
import types

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")
RUN6 = (77.74, 64.70, 53.05)

npass = nfail = 0


def check(ok, label, detail=""):
    global npass, nfail
    if ok:
        npass += 1
    else:
        nfail += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""))
    return ok


src = "".join(json.load(open(NB, encoding="utf-8"))["cells"][15]["source"])

print("=" * 74)
print(f"1. STATIC SHAPE  ({os.path.basename(NB)})")
print("=" * 74)

has_block = check("HARNESS CONTROL" in src, "cell 15 has a HARNESS CONTROL block")
if not has_block:
    print("\n  block absent -- nothing to execute. This is the expected state BEFORE the")
    print("  patch; run scripts/patch_notebook_harness_control.py.")
    print(f"\n{npass} passed, {nfail} failed")
    raise SystemExit(1)

BEGIN = "# ---------------------------------------------------------------- HARNESS CONTROL"
END = "\nrows = []"
i, j = src.index(BEGIN), src.index(END)
block = src[i:j]

check("assert not _miss and not _unex" in block,
      "control load asserts zero missing/unexpected keys",
      "cell 11 resumes with strict=False, so a silent partial load is live")
check("assert not _m2 and not _u2" in block,
      "restore load asserts zero missing/unexpected keys")
check("assert _weight_fingerprint(model) == _fp_swept" in block,
      "restore is fingerprint-asserted",
      "the catastrophic case: 15 rows on the wrong weights")
check("assert _weight_fingerprint(model) != _fp_swept" in block,
      "control load is asserted to actually CHANGE the weights")
check(block.index("_sd2 = torch.load") < block.index("_hdrift ="),
      "restore happens BEFORE the drift report",
      "so a restore failure cannot masquerade as a reporting failure")
check("rows.append(run_selection_eval('HARNESS" not in src
      and src.count("harness_row = run_selection_eval") == 1,
      "control row is kept out of `rows`",
      "it shares the (1.00, 'router') key with row 0")
check(src.count("'harness_verified': harness_verified") == 2,
      "harness_verified reaches BOTH json writes", "partial and final")
check("harness_verified" in src[src.index("# --- CONTROL:"):],
      "row-0 control interpretation reads harness_verified")
for tok in ("raise SystemExit", "sys.exit", "assert harness_verified"):
    check(tok not in block, f"metric drift does not halt the run ({tok!r} absent)",
          "structural failures DO raise; a drifted number only warns")

print()
print("=" * 74)
print("2. EXECUTION")
print("=" * 74)


class Tiny(torch.nn.Module):
    """Keys sort to a_encoder.{bias,weight}, m_router.{bias,weight}, z_decoder.{...}."""

    def __init__(self, fill=0.0):
        super().__init__()
        self.a_encoder = torch.nn.Linear(4, 4)
        self.m_router = torch.nn.Linear(4, 4)
        self.z_decoder = torch.nn.Linear(4, 4)
        with torch.no_grad():
            for p in self.parameters():
                p.fill_(fill)


TMP = tempfile.mkdtemp(prefix="harness_ctrl_")
CTRL_PATH = os.path.join(TMP, "run5.pt")
EVAL_PATH = os.path.join(TMP, "pruned.pt")
for p in (CTRL_PATH, EVAL_PATH):
    open(p, "wb").close()          # real files, so os.path.exists is the real thing


def run_block(*, do_train=True, ctrl=CTRL_PATH, metrics=RUN6, ctrl_sd=None,
              restore_sd=None):
    """Exec the extracted block against stubs. Returns the namespace, or raises."""
    model = Tiny(fill=1.0)                     # the "swept" (retrained) weights
    swept = {k: v.clone() for k, v in model.state_dict().items()}
    loads = []

    def fake_load(path, **kw):
        loads.append(path)
        if path == ctrl:
            return ctrl_sd if ctrl_sd is not None else Tiny(fill=2.0).state_dict()
        return restore_sd if restore_sd is not None else swept

    def fake_eval(label, kr, mode):
        assert kr == 1.00 and mode == "router", (kr, mode)
        return {"config": label, "keep_ratio": kr, "select_mode": mode,
                "word_recall_pct": metrics[0], "character_accuracy_pct": metrics[1],
                "word_order_pct": metrics[2], "num_eval_samples": 50}

    ns = {"os": os, "torch": types.SimpleNamespace(load=fake_load), "model": model,
          "run_selection_eval": fake_eval, "RUN6_REFERENCE": RUN6,
          "RESUME_CKPT": ctrl, "EVAL_CKPT": EVAL_PATH, "DO_TRAIN": do_train}
    exec(compile(block, "<cell15-harness-control>", "exec"), ns)
    ns["_loads"], ns["_swept"] = loads, swept
    return ns


def expect_raise(label, needle, **kw):
    try:
        run_block(**kw)
    except AssertionError as e:
        return check(needle in str(e), label, f"msg mentions {needle!r}")
    except Exception as e:                                    # noqa: BLE001
        return check(False, label, f"raised {type(e).__name__} not AssertionError: {e}")
    return check(False, label, "did NOT raise")


print("\n  A. happy path (run-5 weights reproduce run 6)")
ns = run_block(metrics=RUN6)
check(ns["harness_verified"] is True, "harness_verified is True")
check(ns["harness_row"]["word_recall_pct"] == RUN6[0], "control row captured")
check(all(torch.equal(ns["model"].state_dict()[k], v) for k, v in ns["_swept"].items()),
      "swept weights are back on the model", "byte-equal to the pre-swap tensors")
check(ns["_loads"] == [CTRL_PATH, EVAL_PATH], "loaded control then restore",
      f"{[os.path.basename(p) for p in ns['_loads']]}")

print("\n  B. drifted control (harness moved) -- must warn, not raise")
ns = run_block(metrics=(74.10, 61.0, 50.0))
check(ns["harness_verified"] is False, "harness_verified is False")
check("FAILED" in ns["harness_note"], "note records the failure", repr(ns["harness_note"]))
check(all(torch.equal(ns["model"].state_dict()[k], v) for k, v in ns["_swept"].items()),
      "weights STILL restored on the failure path",
      "the sweep continues, so it must continue on the right weights")

print("\n  C. borderline drift is judged against the stated tolerance")
check(run_block(metrics=(78.13, 64.70, 53.05))["harness_verified"] is True,
      "0.39 pts passes")
check(run_block(metrics=(78.30, 64.70, 53.05))["harness_verified"] is False,
      "0.56 pts fails")

print("\n  D. partial load of the control checkpoint")
_short = {k: v for k, v in Tiny(fill=2.0).state_dict().items() if k != "m_router.weight"}
expect_raise("missing key raises before any eval", "missing", ctrl_sd=_short)
_extra = dict(Tiny(fill=2.0).state_dict())
_extra["ghost.weight"] = torch.zeros(2)
expect_raise("unexpected key raises", "unexpected", ctrl_sd=_extra)

print("\n  E. control checkpoint identical to the swept weights is not a control")
expect_raise("no-op load raises", "changed nothing", ctrl_sd=Tiny(fill=1.0).state_dict())

print("\n  F. broken restore -- the failure that would poison all 15 rows")
expect_raise("restore to WRONG values raises", "FAILED TO RESTORE",
             restore_sd=Tiny(fill=3.0).state_dict())
expect_raise("restore with a missing key raises",
             "restore checkpoint does not match",
             restore_sd={k: v for k, v in Tiny(fill=1.0).state_dict().items()
                         if k != "z_decoder.bias"})

print("\n  G. skip paths (canonical notebook has no DO_TRAIN / no checkpoint)")
ns = run_block(do_train=False)
check(ns["harness_verified"] is None and ns["harness_row"] is None,
      "DO_TRAIN off -> skipped, harness_verified stays None")
check(ns["_loads"] == [], "no checkpoint touched when skipped")
check("skipped" in ns["harness_note"], "skip is recorded in the note")
ns = run_block(ctrl=os.path.join(TMP, "nope.pt"))
check(ns["harness_verified"] is None and "not found" in ns["harness_note"],
      "absent checkpoint -> skipped with a reason", repr(ns["harness_note"]))

print()
print("=" * 74)
print("3. FINGERPRINT COVERS EVERY PARAMETER")
print("=" * 74)
fp = run_block()["_weight_fingerprint"]
m = Tiny(fill=1.0)
base = fp(m)
keys = sorted(m.state_dict().keys())
check(len(base) == len(keys), f"fingerprint has one entry per parameter ({len(keys)})")
sampled = {keys[0], keys[len(keys) // 2], keys[-1]}
missed = [k for k in keys if k not in sampled]
check(bool(missed), "a first/middle/last sample would ignore some keys", f"{missed}")
nblind = 0
for k in missed:
    m2 = Tiny(fill=1.0)
    with torch.no_grad():
        dict(m2.named_parameters())[k].fill_(9.0)
    if fp(m2) == base:
        nblind += 1
check(nblind == 0, "changing ANY single unsampled parameter changes the fingerprint",
      f"{len(missed)} tested, {nblind} blind spots")

print()
print("=" * 74)
print("4. CROSS-CELL CONTRACT (the run-9 launch configuration)")
print("=" * 74)
print("  The block reads RESUME_CKPT / EVAL_CKPT / DO_TRAIN, none of which it sets. If")
print("  cells 2 and 11 do not leave them as expected, the control SKIPS silently and")
print("  the run looks normal. Checked statically because it spans three cells.")

cells = ["".join(c["source"]) for c in json.load(open(NB, encoding="utf-8"))["cells"]]
c2, c9, c11 = cells[2], cells[9], cells[15 - 4]

is_gen = "DO_TRAIN" in c2
print(f"\n  notebook kind: {'GENERATED (has DO_TRAIN)' if is_gen else 'CANONICAL (no DO_TRAIN)'}")

check("RESUME_CKPT = None" in c2,
      "cell 2 ships RESUME_CKPT = None",
      "so run 9 MUST set it or the control skips -- this is the launch step")
check("EVAL_ONLY = bool(RESUME_CKPT)" in c2, "cell 2 derives EVAL_ONLY from RESUME_CKPT")

if is_gen:
    check("if EVAL_ONLY and not DO_TRAIN:" in c9,
          "cell 6 skips the train set only when NOT training",
          "setting RESUME_CKPT must not starve a DO_TRAIN run of data")
    check("EVAL_CKPT = PRUNED_CKPT" in c11 and "torch.save(model.state_dict(), PRUNED_CKPT)" in c11,
          "cell 7's DO_TRAIN branch saves PRUNED_CKPT and repoints EVAL_CKPT at it",
          "so the block restores the RETRAINED weights, not the control ones")
    check(c11.index("torch.save(model.state_dict(), PRUNED_CKPT)") < c11.index("EVAL_CKPT = PRUNED_CKPT"),
          "the file exists before EVAL_CKPT names it")
    check("if RESUME_CKPT and os.path.exists(RESUME_CKPT):" in c11,
          "cell 7 resumes training FROM RESUME_CKPT when set",
          "runs 7-8 trained from run-5 weights, so run 9 matches only if this fires")
    print("\n  => with RESUME_CKPT=<run5> and DO_TRAIN=True the block receives:")
    print("     _ctrl_ckpt=<run5 .pt>   _eval_ckpt=PRUNED_CKPT   _retrained=True  -> RUNS")
    print("     with RESUME_CKPT=None (as shipped):")
    print("     _ctrl_ckpt=None -> SKIPS with 'control checkpoint not found (None)'")
else:
    check("DO_TRAIN" not in c2, "canonical notebook has no DO_TRAIN, so the block skips",
          "correct: `model` there already holds the control weights")

print()
print("=" * 74)
print(f"{npass} passed, {nfail} failed")
print("=" * 74)
raise SystemExit(1 if nfail else 0)
