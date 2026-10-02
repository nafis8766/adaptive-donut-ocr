"""Pending 6: stamp cell 15's results JSON with what produced it.

`ablation_selection.json` currently records the settings of a run (seed, max_len, budgets)
but nothing about the *environment* those settings ran in. Every cross-run comparison in
this project that went wrong went wrong on exactly that axis:

  * D11/D12 found local generation drifting up to 3.4 pts from Kaggle on bit-identical
    token selections -- different device and different transformers version, neither of
    which any results file named. It took a purpose-built control to establish that, and
    a stamped `torch` / `transformers` / `device` would have said it for free.
  * `diagnose_decoder.py`'s checkpoint resolver silently fell through to an older run for
    five days. A results file that names its own checkpoint cannot be mis-attributed that
    way after the fact.
  * run directories get renamed (`results_2/` -> `run 7/`), so a bare path is not enough:
    mtime and size identify the *file*, not the name it happened to have that week.

So the block below stamps, at BOTH json.dump sites:
    eval_ckpt     {path, mtime, size_bytes}   -- the weights the rows were swept on
    control_ckpt  {path, mtime, size_bytes}   -- the run-5 weights the harness control used
    transformers, torch, device, device_name, written

Design notes worth keeping:
  * `_ckpt_stamp` returns a dict with an `error` key rather than None when the file is
    missing. A missing JSON key means "this file predates the provenance writer"; a
    present key with `error` means "we looked and it was not there". Collapsing those two
    into None throws away the distinction that matters when reading an old artifact.
  * nothing in the block may raise. Provenance failing must never cost a 40-minute GPU
    session, so every lookup is guarded and degrades to a string.
  * placement is deliberate: AFTER the harness-control block, because `_eval_ckpt` and
    `_ctrl_ckpt` are defined there, and after `rows = []` specifically so that
    verify_harness_control.py's block extraction (BEGIN..'\\nrows = []') stays
    byte-identical and that verifier keeps testing what it was written to test.

Patches the CANONICAL notebook. The generator (scripts/make_kaggle_pruning_notebook.py)
rewrites only cells 2, 7, 9 and 11, so cell 15 is copied byte-identically to the run
notebook -- editing the generated file directly would be reverted on the next regenerate.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/patch_notebook_provenance.py
Idempotent: exits 0 with 'already applied' if the block is present.
"""
import ast
import json
import os
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")

BLOCK = '''
# ------------------------------------------------------------------- PROVENANCE
# What produced the rows below, stamped into the JSON at BOTH write sites. The
# settings of a run were already recorded; the ENVIRONMENT was not, and that is the
# axis every cross-run comparison in this project has broken on (D11/D12: local
# generation drifts up to 3.4 pts from Kaggle on bit-identical selections, different
# device and transformers version). mtime+size as well as the path, because run
# directories get renamed and a bare path stops identifying the file.
#
# Nothing here may raise: provenance is bookkeeping, and bookkeeping must not be able
# to cost a 40-minute GPU session. Every lookup degrades to a string instead.
try:
    import transformers as _tfm_prov
    _tfm_ver = _tfm_prov.__version__
except Exception as _e:                       # noqa: BLE001 - report, never raise
    _tfm_ver = f'unavailable ({type(_e).__name__})'


def _ckpt_stamp(p):
    """Path + mtime + size for a checkpoint, or an explicit reason there is none.

    Returns a dict on every path, including failure. A MISSING key in the JSON means
    "written before provenance existed"; a PRESENT key carrying 'error' means "we
    looked and it was not there". Collapsing both to None discards exactly the
    distinction that matters when reading a stale artifact months later.
    """
    if not p:
        return {'path': None,
                'error': 'no checkpoint variable set (EVAL_CKPT / RESUME_CKPT)'}
    try:
        _st = os.stat(p)
    except OSError as e:
        return {'path': str(p), 'error': f'{type(e).__name__}: {e}'}
    return {'path': str(p),
            'mtime': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(_st.st_mtime)),
            'size_bytes': int(_st.st_size)}


try:
    _dev_prov = str(next(model.parameters()).device)
except Exception:                             # noqa: BLE001 - NameError / StopIteration
    _dev_prov = 'unknown'
if _dev_prov.startswith('cuda'):
    try:
        _devname_prov = torch.cuda.get_device_name(_dev_prov)
    except Exception:                         # noqa: BLE001
        _devname_prov = 'cuda (name unavailable)'
elif _dev_prov == 'unknown':
    _devname_prov = 'unknown'
else:
    _devname_prov = 'cpu'

PROVENANCE = {
    'eval_ckpt': _ckpt_stamp(_eval_ckpt),
    'control_ckpt': _ckpt_stamp(_ctrl_ckpt),
    'transformers': _tfm_ver,
    'torch': getattr(torch, '__version__', 'unknown'),
    'device': _dev_prov,
    'device_name': _devname_prov,
    'written': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
}
# Serialise once HERE rather than discovering at the first write that something in the
# dict is not JSON-able -- that write lands after row 0, i.e. minutes of GPU in.
json.dumps(PROVENANCE)
print(f"\\nPROVENANCE  torch {PROVENANCE['torch']}  transformers "
      f"{PROVENANCE['transformers']}  {PROVENANCE['device']} ({PROVENANCE['device_name']})")
print(f"    eval ckpt     {PROVENANCE['eval_ckpt']}")
print(f"    control ckpt  {PROVENANCE['control_ckpt']}")
'''.rstrip("\n")

OLD_DRIVER = "rows = []\nfor _name, _kr, _mode in SELECTION_CONFIGS:"
NEW_DRIVER = "rows = []\n" + BLOCK + "\n\nfor _name, _kr, _mode in SELECTION_CONFIGS:"

OLD_META_PARTIAL = """                            'harness_control': harness_row,
                            'complete': False}, 'rows': rows}, f, indent=2)"""
NEW_META_PARTIAL = """                            'harness_control': harness_row,
                            'provenance': PROVENANCE,
                            'complete': False}, 'rows': rows}, f, indent=2)"""

OLD_META_FINAL = """                        'control_ckpt': _ctrl_ckpt,
                        'complete': True}, 'rows': rows}, f, indent=2)"""
NEW_META_FINAL = """                        'control_ckpt': _ctrl_ckpt,
                        'provenance': PROVENANCE,
                        'complete': True}, 'rows': rows}, f, indent=2)"""

EDITS = [
    ("provenance block", OLD_DRIVER, NEW_DRIVER),
    ("meta (partial write)", OLD_META_PARTIAL, NEW_META_PARTIAL),
    ("meta (final write)", OLD_META_FINAL, NEW_META_FINAL),
]

nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][15]
src = "".join(cell["source"])

if "PROVENANCE" in src:
    print("already applied -- cell 15 contains the provenance block")
    raise SystemExit(0)

# Preconditions the block relies on at runtime. Cheaper to fail here than on Kaggle.
# `torch` and `json` are ambient from earlier cells (cell 15 imports only os/re/time),
# which is the convention the harness-control block already follows.
for need, why in (("import os", "os.stat on the checkpoints"),
                  ("import time", "time.strftime / time.gmtime for the stamps"),
                  ("torch.no_grad", "ambient torch from cell 2, needed for torch.__version__"),
                  ("json.dump(", "ambient json from cell 2, needed for the write sites"),
                  ("_eval_ckpt = ", "the swept checkpoint variable"),
                  ("_ctrl_ckpt = ", "the control checkpoint variable")):
    assert need in src, f"cell 15 lacks {need!r}, needed for {why}"
print("preconditions      : ok (os, time, ambient torch/json, _eval_ckpt, _ctrl_ckpt)")

# The block must land AFTER both checkpoint variables exist, or it stamps a NameError.
assert src.index("_ctrl_ckpt = ") < src.index(OLD_DRIVER), (
    "the anchor precedes _ctrl_ckpt's definition -- the block would raise NameError")

shutil.copyfile(NB, NB + time.strftime(".bak-%Y%m%d-%H%M%S"))

for name, old, new in EDITS:
    n = src.count(old)
    assert n == 1, f"anchor {name!r} matched {n} times, expected exactly 1"
    src = src.replace(old, new)
    print(f"patched            : {name}")

# verify_harness_control.py extracts its block as src[BEGIN : index('\nrows = []')].
# Inserting before `rows = []` would silently pull the provenance block into that
# extraction and change what that verifier tests. Assert the boundary is untouched.
# The marker is taken from BLOCK itself so a reworded banner cannot make this check
# vacuous by simply never matching.
MARK = BLOCK.strip().splitlines()[0]
assert MARK.endswith("PROVENANCE"), f"unexpected block banner: {MARK!r}"
assert src.index("\nrows = []") < src.index(MARK), (
    "provenance block landed BEFORE `rows = []` -- verify_harness_control.py's block "
    "extraction would now include it")

assert src.count("'provenance': PROVENANCE") == 2, "provenance must reach BOTH writes"

ast.parse(src)
print("ast.parse          : ok")

cell["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
open(NB, "a", encoding="utf-8").write("\n")
print(f"\nwrote {os.path.relpath(NB, ROOT)}  (cell 15: {len(cell['source'])} lines)")
print("next: python scripts/verify_results_provenance.py")
print("      python scripts/make_kaggle_pruning_notebook.py   # propagate to the run nb")
