"""Pending 4: give cell 15 a control that holds the WEIGHTS fixed, not just the harness.

Runs 7 and 8 retrained the router before cell 15's `keep=1.00 router CONTROL` row ran, so
that row's drift from run 6 (-10.93 then +0.51) had two possible causes at once -- a broken
harness, or a changed checkpoint -- and could not separate them. This patch inserts one
extra row, evaluated on the run-5 weights that PRODUCED 77.74/64.70/53.05, through the
identical run_selection_eval(). Nothing varies vs run 6 there, so its drift is purely
harness / library version / sampling; row 0's drift then isolates the retrain's effect.

Three safety properties, in decreasing obviousness:
  * the control checkpoint must load with zero missing/unexpected keys -- cell 11 resumes
    with strict=False, and a partial load would evaluate a partly-random model and report
    the result as a control.
  * the retrained weights must be provably back before the sweep. If the restore silently
    failed, all 15 rows would measure the control checkpoint while looking entirely
    plausible, which is worse than having no control at all. Full-state-dict fingerprint,
    asserted equal after the swap back.
  * a failed control warns and stamps harness_verified=false; it does not halt. The
    row-to-row comparisons are what Q1/Q2/Q4 test and they survive a harness offset;
    aborting would spend a GPU session to learn that absolute numbers are unquotable.

Patches the CANONICAL notebook. The generator (scripts/make_kaggle_pruning_notebook.py)
rewrites only cells 2, 9 and 11, so cell 15 is copied byte-identically to the run
notebook -- editing the generated file directly would be reverted on the next regenerate.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/patch_notebook_harness_control.py
Idempotent: exits 0 with 'already applied' if the block is present.
"""
import ast
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")

BLOCK = '''
# ---------------------------------------------------------------- HARNESS CONTROL
# The row-0 CONTROL below re-runs a known SETTING; this block re-runs a known
# CHECKPOINT. Runs 7-8 retrained before row 0 ran, so row 0's drift from run 6
# conflated "the harness moved" with "the weights moved". Evaluating the run-5
# weights -- the ones that produced RUN6_REFERENCE -- through this exact function
# varies nothing vs run 6, so any drift HERE is harness/version/sampling, and row
# 0's drift is then the retrain alone. keep_ratio=1.0 prunes nothing, so this row
# is also independent of every selection code path under test.
HARNESS_CONTROL_TOL = 0.5
_ctrl_ckpt = globals().get('RESUME_CKPT') or None
_eval_ckpt = globals().get('EVAL_CKPT') or _ctrl_ckpt
_retrained = bool(globals().get('DO_TRAIN', False))
harness_row, harness_verified, harness_note = None, None, ''


def _weight_fingerprint(m):
    """Deterministic checksum over EVERY parameter, not a sample of them.

    A sample can miss the swap: the first/middle/last keys of a Donut state dict are
    frozen encoder tensors that training never touches, so a 3-key fingerprint would
    compare equal across two genuinely different checkpoints. Cost is one .sum() per
    tensor, milliseconds on GPU, and only precision-stable equality is needed here.
    """
    return tuple(float(v.detach().float().sum()) for _, v in sorted(m.state_dict().items()))


if not _retrained:
    harness_note = ('skipped: DO_TRAIN is off, so `model` still holds the control weights '
                    'and row 0 below already IS the harness control.')
    print(f'\\nHARNESS CONTROL {harness_note}')
elif not (_ctrl_ckpt and os.path.exists(_ctrl_ckpt)):
    harness_note = f'skipped: control checkpoint not found ({_ctrl_ckpt!r})'
    print(f'\\nHARNESS CONTROL {harness_note}')
else:
    print(f'\\n--- HARNESS CONTROL: run-5 weights through this harness')
    print(f'    control  {_ctrl_ckpt}')
    print(f'    restore  {_eval_ckpt}')
    _fp_swept = _weight_fingerprint(model)
    _sd = torch.load(_ctrl_ckpt, map_location='cpu', weights_only=True)
    _miss, _unex = model.load_state_dict(_sd, strict=False)
    assert not _miss and not _unex, (
        f'control checkpoint does not match this architecture: {len(_miss)} missing, '
        f'{len(_unex)} unexpected (missing {_miss[:3]}, unexpected {_unex[:3]}). A partial '
        f'load would evaluate a partly-random model and call the drift a control.')
    assert _weight_fingerprint(model) != _fp_swept, (
        'control load changed nothing -- RESUME_CKPT and the swept weights are the same '
        'tensors, so this row would not be a control.')

    harness_row = run_selection_eval('HARNESS CONTROL run-5 wts', 1.00, 'router')

    # Restore BEFORE reporting, so a restore failure cannot be mistaken for a
    # reporting failure and so the assert below fires while the cause is on screen.
    _sd2 = torch.load(_eval_ckpt, map_location='cpu', weights_only=True)
    _m2, _u2 = model.load_state_dict(_sd2, strict=False)
    assert not _m2 and not _u2, (
        f'restore checkpoint does not match: {len(_m2)} missing, {len(_u2)} unexpected')
    assert _weight_fingerprint(model) == _fp_swept, (
        'FAILED TO RESTORE the swept weights. Every row below would measure the control '
        'checkpoint instead, and the table would look entirely plausible. Refusing to '
        'produce it.')
    del _sd, _sd2
    print('    weights restored and fingerprint-verified')

    _hgot = (harness_row['word_recall_pct'], harness_row['character_accuracy_pct'],
             harness_row['word_order_pct'])
    _hdrift = max(abs(g - e) for g, e in zip(_hgot, RUN6_REFERENCE))
    harness_verified = bool(_hdrift < HARNESS_CONTROL_TOL)
    print(f'    got ({_hgot[0]:.2f}, {_hgot[1]:.2f}, {_hgot[2]:.2f})  vs run 6 '
          f'{RUN6_REFERENCE}  max drift {_hdrift:.2f} pts')
    if harness_verified:
        harness_note = f'verified: run-5 weights reproduce run 6 within {_hdrift:.2f} pts'
        print('    HARNESS OK - the same weights reproduce run 6 through this code, so '
              'row 0\\'s')
        print('    drift below is the RETRAIN, not the measurement.')
    else:
        harness_note = (f'FAILED: run-5 weights drift {_hdrift:.2f} pts from run 6 through '
                        f'this harness')
        print('    ' + '!' * 70)
        print('    HARNESS CONTROL FAILED. The weights that produced run 6 do NOT')
        print('    reproduce it here, so nothing below is quotable against run 6 or any')
        print('    earlier run in absolute terms. Rows stay comparable TO EACH OTHER')
        print('    (same harness, same weights, only the ranking signal varies), which')
        print('    is what Q1/Q2/Q4 ask -- so the sweep continues instead of discarding')
        print('    the session. Results are stamped harness_verified=false.')
        print('    ' + '!' * 70)
'''.rstrip("\n")

OLD_DRIVER = "rows = []\n_t0 = time.perf_counter()\n"
NEW_DRIVER = "_t0 = time.perf_counter()\n" + BLOCK + "\n\nrows = []\n"

OLD_CTRL = """# --- CONTROL: does keep_ratio=1.0 reproduce run 6? ---
ctrl = rows[0]
got = (ctrl['word_recall_pct'], ctrl['character_accuracy_pct'], ctrl['word_order_pct'])
drift = max(abs(g - e) for g, e in zip(got, RUN6_REFERENCE))
print(f'\\nCONTROL vs run 6 {RUN6_REFERENCE}')
print(f'  got ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts')
if drift < 0.5:
    print('  OK - harness reproduces run 6, so every other row is comparable.')
else:
    print('  WARNING - harness does NOT match run 6 (different weights, sampling, or '
          'transformers version). Rows are still comparable TO EACH OTHER and to this '
          'control, but do not quote them against run 6 absolutely.')
"""

NEW_CTRL = """# --- CONTROL: does keep_ratio=1.0 on the SWEPT weights reproduce run 6? ---
# Read this together with the HARNESS CONTROL above. That block fixed the weights and
# varied nothing; this one fixes the setting and varies the weights. The pair is what
# makes a drift attributable: harness verified + row 0 drifting = the retrain moved the
# ceiling. Both drifting = measurement problem, and the retrain's effect is unreadable.
ctrl = rows[0]
got = (ctrl['word_recall_pct'], ctrl['character_accuracy_pct'], ctrl['word_order_pct'])
drift = max(abs(g - e) for g, e in zip(got, RUN6_REFERENCE))
print(f'\\nCONTROL vs run 6 {RUN6_REFERENCE}')
print(f'  got ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts')
if drift < 0.5:
    print('  OK - this checkpoint matches run 6 at keep=1.0, so every other row is '
          'comparable.')
elif harness_verified:
    print(f'  DIFFERENT CEILING - and the harness was verified above, so this '
          f'{drift:.2f} pt gap')
    print('  is what the retrain did to unpruned accuracy, not measurement noise. Compare '
          'rows to THIS row, not to run 6.')
else:
    print('  WARNING - harness does NOT match run 6 (different weights, sampling, or '
          'transformers version). Rows are still comparable TO EACH OTHER and to this '
          'control, but do not quote them against run 6 absolutely.')
    if harness_verified is False:
        print('  The HARNESS CONTROL above also failed, so this gap cannot be attributed '
              'to the retrain.')
"""

OLD_META_PARTIAL = """                            'max_len': SELECTION_MAX_LEN,
                            'complete': False}, 'rows': rows}, f, indent=2)"""
NEW_META_PARTIAL = """                            'max_len': SELECTION_MAX_LEN,
                            'harness_verified': harness_verified,
                            'harness_note': harness_note,
                            'harness_control': harness_row,
                            'complete': False}, 'rows': rows}, f, indent=2)"""

OLD_META_FINAL = """                        'max_words': MAX_WORDS,
                        'complete': True}, 'rows': rows}, f, indent=2)"""
NEW_META_FINAL = """                        'max_words': MAX_WORDS,
                        'harness_verified': harness_verified,
                        'harness_note': harness_note,
                        'harness_control': harness_row,
                        'control_ckpt': _ctrl_ckpt,
                        'complete': True}, 'rows': rows}, f, indent=2)"""

OLD_HEADER = """# Row 0 is a CONTROL at keep_ratio=1.0 (pruning OFF) and must reproduce run 6. If it
# does not, this harness differs from the eval cell and NO other row is trustworthy.
"""

NEW_HEADER = """# Two controls run at keep_ratio=1.0 (pruning OFF), and they are not the same check:
#   HARNESS CONTROL loads the run-5 weights that PRODUCED RUN6_REFERENCE and must
#     reproduce it. Nothing varies vs run 6, so drift here is the measurement --
#     harness, library version or sampling -- and nothing else is trustworthy.
#   Row 0 uses the weights actually being swept. Once the harness is verified, its
#     drift from run 6 is what the retrain did to unpruned accuracy.
# Runs 7-8 had only row 0, which retraining had turned into a two-variable test: its
# drift could not distinguish a broken harness from a changed checkpoint.
"""

EDITS = [
    ("cell header", OLD_HEADER, NEW_HEADER),
    ("driver", OLD_DRIVER, NEW_DRIVER),
    ("row-0 control interpretation", OLD_CTRL, NEW_CTRL),
    ("meta (partial write)", OLD_META_PARTIAL, NEW_META_PARTIAL),
    ("meta (final write)", OLD_META_FINAL, NEW_META_FINAL),
]

nb = json.load(open(NB, encoding="utf-8"))
cell = nb["cells"][15]
src = "".join(cell["source"])

if "HARNESS CONTROL" in src:
    print("already applied -- cell 15 contains the harness control block")
    raise SystemExit(0)

# Preconditions the block relies on at runtime. Cheaper to fail here than on Kaggle.
# Note torch: cell 15 has no `import torch` of its own, it uses the ambient one from
# cell 2 (torch.manual_seed, torch.no_grad). The new block follows that convention --
# the cell cannot run standalone anyway, since `model` also comes from an earlier cell.
for need, why in (("import os", "os.path.exists on the checkpoint"),
                  ("torch.no_grad", "ambient torch from cell 2, needed for torch.load"),
                  ("def run_selection_eval", "the shared eval path"),
                  ("RUN6_REFERENCE", "the reference triple")):
    assert need in src, f"cell 15 lacks {need!r}, needed for {why}"
print("preconditions      : ok (os, ambient torch, run_selection_eval, RUN6_REFERENCE)")

for name, old, new in EDITS:
    n = src.count(old)
    assert n == 1, f"anchor {name!r} matched {n} times, expected exactly 1"
    src = src.replace(old, new)
    print(f"patched            : {name}")

# The control row must NOT join `rows`: `by = {(keep_ratio, select_mode): r}` is keyed on
# (1.00, 'router'), which row 0 already owns, so appending would silently overwrite it.
assert "rows.append(run_selection_eval('HARNESS" not in src
assert src.count("harness_row = run_selection_eval") == 1

ast.parse(src)
print("ast.parse          : ok")

cell["source"] = src.splitlines(keepends=True)
json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
open(NB, "a", encoding="utf-8").write("\n")
print(f"\nwrote {os.path.relpath(NB, ROOT)}  (cell 15: {len(cell['source'])} lines)")
print("next: regenerate the run notebook, then run scripts/verify_harness_control.py")
