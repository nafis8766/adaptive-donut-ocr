"""Verify the Phase 2c hotfix RUNS -- especially the path resolver that has to
rescue the exact failure seen on Kaggle.

The 2026-08-29 attempt died on `RESUME_CKPT not found` after 20 minutes. The fix
is only worth anything if it handles the real path-shape mistakes, so the resolver
is exercised against a fake /kaggle/input tree covering all five cases. The code
under test is EXTRACTED from the notebook (with '/kaggle/input' redirected to a
temp dir) rather than restated here, so this check cannot drift from what ships.

Checks:
  1. resolver: nested file auto-resolves (the actual Kaggle failure)
  2. resolver: nothing mounted -> raises, and says the dataset may be unattached
  3. resolver: two matches -> raises rather than guessing
  4. resolver: correct path -> passes through, EVAL_ONLY True
  5. resolver: None -> EVAL_ONLY False, no error (normal training path)
  6. GPU guard fires on CPU, and ALLOW_CPU=True overrides it
  7. cell ordering: EVAL_ONLY is defined before the cell that consumes it
  8. cell 11 no longer defines RESUME_CKPT but still uses it
"""
import ast
import json
import os
import tempfile

import torch

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cells = ["".join(c["source"]) for c in nb["cells"]]
fails = []

# ---------------------------------------------------- extract the real resolver
cell2 = cells[2]
MARK = "# ---- Phase 2c: eval-only resume"
assert MARK in cell2, "resolver block not found in cell 2"
resolver_src = cell2[cell2.index(MARK):]
OLD_ASSIGN = "RESUME_CKPT = None  # e.g. '/kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt'"
assert resolver_src.count(OLD_ASSIGN) == 1, "cannot find the RESUME_CKPT assignment to parameterize"


def run_resolver(ckpt, root):
    """Exec the notebook's own resolver with /kaggle/input redirected to `root`."""
    src = resolver_src.replace(OLD_ASSIGN, "RESUME_CKPT = _TEST_CKPT")
    src = src.replace("'/kaggle/input'", "_TEST_ROOT").replace('"/kaggle/input"', "_TEST_ROOT")
    ns = {"os": os, "_TEST_CKPT": ckpt, "_TEST_ROOT": root, "print": lambda *a, **k: None}
    exec(compile(src, "<resolver>", "exec"), ns)
    return ns["RESUME_CKPT"], ns["EVAL_ONLY"]


def mktree(*rel_files):
    root = tempfile.mkdtemp()
    for rel in rel_files:
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(b"stub")
    return root


CKPT = "adaptive_donut_funsd.pt"
WANTED = "/kaggle/input/adaptive-donut-run5/" + CKPT

# 1. nested one level deeper (dataset uploaded with its checkpoints/ folder)
root = mktree(f"adaptive-donut-run5/checkpoints/{CKPT}")
try:
    got, ev = run_resolver(WANTED, root)
    ok1 = got.endswith(os.path.join("checkpoints", CKPT)) and os.path.exists(got) and ev is True
    print(f"1. nested file auto-resolves: {'PASS' if ok1 else 'FAIL'} -> {got}")
except Exception as e:
    ok1 = False
    print(f"1. nested file auto-resolves: FAIL -> {type(e).__name__}: {e}")
if not ok1:
    fails.append("nested resolve")

# 1b. wrong slug entirely (title -> slug mismatch) still resolves by basename
root = mktree(f"run5-ckpt/{CKPT}")
try:
    got, _ = run_resolver(WANTED, root)
    ok1b = got.endswith(CKPT) and "run5-ckpt" in got
except Exception:
    ok1b = False
print(f"   wrong-slug resolves by basename: {'PASS' if ok1b else 'FAIL'}")
if not ok1b:
    fails.append("slug resolve")

# 2. nothing mounted -> must raise AND point at the unattached-dataset cause
root = mktree("some-other-dataset/readme.txt")
try:
    run_resolver(WANTED, root)
    ok2, msg = False, "did not raise"
except AssertionError as e:
    msg = str(e)
    ok2 = "not attached" in msg
except Exception as e:
    ok2, msg = False, f"{type(e).__name__}: {e}"
print(f"2. nothing mounted raises w/ diagnosis: {'PASS' if ok2 else 'FAIL -> ' + msg[:80]}")
if not ok2:
    fails.append("unmounted diagnosis")

# 3. ambiguous (two candidates) -> refuse to guess
root = mktree(f"ds-a/{CKPT}", f"ds-b/{CKPT}")
try:
    run_resolver(WANTED, root)
    ok3 = False
except AssertionError as e:
    ok3 = "ds-a" in str(e) and "ds-b" in str(e)
except Exception:
    ok3 = False
print(f"3. ambiguous match refuses to guess: {'PASS' if ok3 else 'FAIL'}")
if not ok3:
    fails.append("ambiguity")

# 4. correct path -> untouched
root = mktree(f"adaptive-donut-run5/{CKPT}")
good = os.path.join(root, "adaptive-donut-run5", CKPT)
try:
    got, ev = run_resolver(good, root)
    ok4 = got == good and ev is True
except Exception:
    ok4 = False
print(f"4. correct path passes through: {'PASS' if ok4 else 'FAIL'}")
if not ok4:
    fails.append("passthrough")

# 5. None -> normal training path, no error
try:
    got, ev = run_resolver(None, mktree("x/y.txt"))
    ok5 = got is None and ev is False
except Exception as e:
    ok5 = False
    print(f"   (None raised {type(e).__name__}: {e})")
print(f"5. None -> EVAL_ONLY False, no error: {'PASS' if ok5 else 'FAIL'}")
if not ok5:
    fails.append("none path")

# ------------------------------------------------------------- 6. GPU guard
gpu_src = cell2[cell2.index("ALLOW_CPU = False"):cell2.index("if torch.cuda.is_available():\n    print(f'GPU:")]


def run_gpu_guard(allow_cpu, dev_type):
    src = gpu_src.replace("ALLOW_CPU = False", f"ALLOW_CPU = {allow_cpu}")
    ns = {"device": type("D", (), {"type": dev_type})()}
    exec(compile(src, "<gpu>", "exec"), ns)


try:
    run_gpu_guard(False, "cpu")
    ok6a, detail = False, "no assert on CPU"
except AssertionError as e:
    ok6a, detail = "Accelerator" in str(e), str(e)[:60]
print(f"6. GPU guard fires on CPU: {'PASS' if ok6a else 'FAIL -> ' + detail}")
try:
    run_gpu_guard(True, "cpu")
    ok6b = True
except AssertionError:
    ok6b = False
print(f"   ALLOW_CPU=True overrides: {'PASS' if ok6b else 'FAIL'}")
try:
    run_gpu_guard(False, "cuda")
    ok6c = True
except AssertionError:
    ok6c = False
print(f"   passes on cuda: {'PASS' if ok6c else 'FAIL'}")
for lbl, cond in (("gpu guard", ok6a), ("allow_cpu", ok6b), ("cuda pass", ok6c)):
    if not cond:
        fails.append(lbl)

# --------------------------------------------- 7. cell ordering for EVAL_ONLY
def_cell = next(i for i, s in enumerate(cells) if "EVAL_ONLY = bool(RESUME_CKPT)" in s)
use_cell = next(i for i, s in enumerate(cells) if "if EVAL_ONLY:" in s and "train_ds = train_loader" in s)
ok7 = def_cell < use_cell
print(f"7. EVAL_ONLY defined in cell {def_cell} before use in cell {use_cell}: {'PASS' if ok7 else 'FAIL'}")
if not ok7:
    fails.append("cell ordering")

# ------------------------------------- 8. cell 11 consumes, does not redefine
c11 = cells[11]
ok8 = "RESUME_CKPT = None" not in c11 and "if RESUME_CKPT:" in c11 and "torch.load(RESUME_CKPT" in c11
print(f"8. cell 11 consumes without redefining: {'PASS' if ok8 else 'FAIL'}")
if not ok8:
    fails.append("cell 11 consume")

# ---------------------------- bonus: train_loader only used inside epoch loop
c11_tree = ast.parse(c11)
loop = next(n for n in ast.walk(c11_tree)
            if isinstance(n, ast.For) and getattr(n.target, "id", None) == "epoch")
inside = {id(n) for n in ast.walk(loop)}
outside_refs = [n.lineno for n in ast.walk(c11_tree)
                if isinstance(n, ast.Name) and n.id == "train_loader" and id(n) not in inside]
ok9 = not outside_refs
print(f"9. train_loader referenced only inside the epoch loop: "
      f"{'PASS' if ok9 else 'FAIL at lines ' + str(outside_refs)}")
if not ok9:
    fails.append("train_loader escape")

# ------------------------------------------ all edited cells still parse
for i in (2, 9, 11):
    try:
        ast.parse(cells[i])
    except SyntaxError as e:
        fails.append(f"cell {i} syntax")
        print(f"   cell {i} SYNTAX ERROR: {e}")

print("\nRESULT:", "PASS - hotfix runs and handles every path-shape mistake"
      if not fails else f"FAIL: {fails}")
raise SystemExit(0 if not fails else 1)
