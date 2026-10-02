"""Phase 2c hotfix: make the eval-only ablation actually launchable.

The first Kaggle attempt (2026-08-29) failed after 20 minutes with

    AssertionError: RESUME_CKPT not found: /kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt

and, more quietly, logged `Using device: cpu`. Three separate problems, fixed here.

1. NO ACCELERATOR (the dangerous one -- it does NOT raise).
   The run was on CPU. Nothing in the notebook objected; it printed one line and
   carried on. Had the checkpoint path been correct, the ablation would have run
   5 configs x 50 samples on CPU -- hours instead of ~11 minutes -- and its
   CONTROL row would likely have tripped the 0.5pt drift check anyway, because
   run 5's reference numbers were produced on GPU and greedy decoding is not
   bit-identical across devices. A wrong-but-plausible table is worse than a
   crash. Now a hard assert, with ALLOW_CPU as a deliberate opt-out.

2. UNHELPFUL PATH ERROR.
   The old assert reported what was missing but not what was PRESENT, so it gave
   the user nothing to correct with. The likely causes are all path-shape
   mistakes: dataset uploaded with its `checkpoints/` folder (file one level
   deeper), a slug that differs from the dataset title, or the dataset not
   attached at all. Now the check searches /kaggle/input recursively for the
   basename: exactly one hit resolves and prints loudly; zero or several assert
   with a full listing of every .pt actually mounted.

3. 20 MINUTES SPENT BUILDING DATA THE RUN NEVER USES.
   Cell 6 downloads FUNSD x8 + 500 SynthDoG (~19 min of the 20) and cell 7 then
   discarded it via EPOCHS=0. `train_loader` is referenced ONLY inside the epoch
   loop body (verified: cell 7 lines 69/81/95), so in eval-only mode it can be
   skipped entirely. A failed attempt now costs ~1 minute, and a successful
   eval-only run skips straight to decoding.

Consequence for the operator: RESUME_CKPT now lives in Cell 2, not Cell 7.
That is deliberate -- validating it before the 20-minute download is the entire
point of the change.
"""
import ast
import json
import os
import shutil

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
BAK = NB + ".bak-phase2c-hotfix"

if not os.path.exists(BAK):
    shutil.copyfile(NB, BAK)
    print(f"backup written: {os.path.basename(BAK)}")
else:
    print(f"backup already exists, left as-is: {os.path.basename(BAK)}")

nb = json.load(open(NB, encoding="utf-8"))


def sub(text, old, new, label):
    n = text.count(old)
    assert n == 1, f"[{label}] expected 1 match, found {n}"
    return text.replace(old, new)


def get(i):
    return "".join(nb["cells"][i]["source"])


def put(i, text):
    ast.parse(text)  # guard: edited cell must still be valid Python
    nb["cells"][i]["source"] = text.splitlines(keepends=True)


# ---------------- Cell 2: GPU guard + early RESUME_CKPT resolution ----------------
c = get(2)

c = sub(c,
r"""device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Using device: {device}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    free_mem, total_mem = torch.cuda.mem_get_info()
    print(f'Available VRAM: {free_mem / (1024**3):.2f} GB / {total_mem / (1024**3):.2f} GB')""",
r"""device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Using device: {device}')

# A CPU session is always a mistake here, and it does not announce itself: the
# 2026-08-29 attempt printed "Using device: cpu" and kept going. Training would
# take weeks; even eval-only decoding is hours instead of ~11 min, and CPU/GPU
# numerics differ enough to trip the ablation's 0.5pt CONTROL check against
# run 5's GPU-produced reference. Fail immediately instead.
ALLOW_CPU = False  # set True only for a deliberate no-GPU smoke test
assert ALLOW_CPU or device.type == 'cuda', (
    'No GPU: Kaggle sidebar -> Session options -> Accelerator -> GPU T4 x2, '
    'then Run All. (Set ALLOW_CPU=True to override, expect hours not minutes.)')

if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    free_mem, total_mem = torch.cuda.mem_get_info()
    print(f'Available VRAM: {free_mem / (1024**3):.2f} GB / {total_mem / (1024**3):.2f} GB')

# ---- Phase 2c: eval-only resume (set this to skip the ~4h retrain) ----
# Point RESUME_CKPT at run 5's uploaded checkpoint to go straight to eval + the
# decoding ablation; leave it None to train normally. Validated HERE, before the
# ~19-minute dataset download in Cell 6, so a wrong path costs a minute.
RESUME_CKPT = None  # e.g. '/kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt'

if RESUME_CKPT and not os.path.exists(RESUME_CKPT):
    # The path is wrong in one of three ordinary ways: the dataset was uploaded
    # with its checkpoints/ folder (file sits one level deeper), the slug differs
    # from the dataset title, or the dataset was never attached. Resolve by
    # searching for the basename instead of guessing the shape.
    _want = os.path.basename(RESUME_CKPT)
    _found = [os.path.join(r, f)
              for r, _d, fs in os.walk('/kaggle/input') for f in fs if f == _want]
    if len(_found) == 1:
        print(f'RESUME_CKPT not at {RESUME_CKPT}\n  -> resolved to {_found[0]}')
        RESUME_CKPT = _found[0]
    else:
        _all_pt = [os.path.join(r, f)
                   for r, _d, fs in os.walk('/kaggle/input') for f in fs if f.endswith('.pt')]
        raise AssertionError(
            f'RESUME_CKPT not found: {RESUME_CKPT}\n'
            f'  matches for {_want!r}: {_found or "none"}\n'
            f'  .pt files mounted under /kaggle/input: {_all_pt or "NONE -- dataset not attached?"}\n'
            f'  top level of /kaggle/input: {sorted(os.listdir("/kaggle/input")) if os.path.isdir("/kaggle/input") else "MISSING"}\n'
            '  Fix: Add Input -> your dataset, then copy the path it shows.')

EVAL_ONLY = bool(RESUME_CKPT)
if EVAL_ONLY:
    print(f'EVAL-ONLY mode: will load {RESUME_CKPT}')
    print('  -> training skipped, and Cell 6 will skip building the train set')""",
"c2-gpu-and-ckpt")
put(2, c)


# ---------------- Cell 9 (Cell 6): skip the train set in eval-only mode ----------------
c = get(9)

c = sub(c,
r"""SYNTH_N, FUNSD_REPEAT = 500, 8
funsd_train = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor, augment=True)
synth_train = DocumentDataset(dataset_name='naver-clova-ix/synthdog-en', split=f'train[:{SYNTH_N}]', processor=processor, augment=False)
train_ds = ConcatDataset([funsd_train] * FUNSD_REPEAT + [synth_train])
test_ds = DocumentDataset(dataset_name='nielsr/funsd', split='test', processor=processor)
print(f'Mixed train set: {len(funsd_train)} FUNSD x{FUNSD_REPEAT} + {len(synth_train)} SynthDoG = {len(train_ds)} samples')

# batch_size = 1 with gradient accumulation = 8 ensures no OOM
train_loader = DataLoader(train_ds, batch_size=1, shuffle=True, collate_fn=collate_fn)
print(f'Train samples: {len(train_ds)}, Test samples: {len(test_ds)}')""",
r"""SYNTH_N, FUNSD_REPEAT = 500, 8

# In eval-only mode none of this is used: the training loop never runs, and
# train_loader is referenced ONLY inside the epoch loop body. Building it anyway
# cost ~19 minutes of SynthDoG download on the 2026-08-29 attempt before the run
# failed on an unrelated path error, so skip it outright.
if EVAL_ONLY:
    train_ds = train_loader = funsd_train = synth_train = None
    print('EVAL-ONLY mode: skipped train set (no FUNSD-aug / SynthDoG download)')
else:
    funsd_train = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor, augment=True)
    synth_train = DocumentDataset(dataset_name='naver-clova-ix/synthdog-en', split=f'train[:{SYNTH_N}]', processor=processor, augment=False)
    train_ds = ConcatDataset([funsd_train] * FUNSD_REPEAT + [synth_train])
    print(f'Mixed train set: {len(funsd_train)} FUNSD x{FUNSD_REPEAT} + {len(synth_train)} SynthDoG = {len(train_ds)} samples')
    # batch_size = 1 with gradient accumulation = 8 ensures no OOM
    train_loader = DataLoader(train_ds, batch_size=1, shuffle=True, collate_fn=collate_fn)
    print(f'Train samples: {len(train_ds)}, Test samples: {len(test_ds)}')

test_ds = DocumentDataset(dataset_name='nielsr/funsd', split='test', processor=processor)
print(f'Test samples: {len(test_ds)}')""",
"c9-skip-train-build")
put(9, c)


# ---------------- Cell 11 (Cell 7): consume the already-validated RESUME_CKPT ----------------
c = get(11)

c = sub(c,
r"""# Phase 2c: eval-only resume. Point RESUME_CKPT at an uploaded checkpoint (Kaggle:
# "Add Input" -> your dataset holding run 5's adaptive_donut_funsd.pt) to SKIP the
# ~4h retrain and go straight to eval + the decoding ablation. Leave it None to
# train normally. EPOCHS=0 makes range(1, EPOCHS+1) empty, so the training loop
# body never executes -- no re-indentation of the loop required.
RESUME_CKPT = None  # e.g. '/kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt'
if RESUME_CKPT:
    assert os.path.exists(RESUME_CKPT), f'RESUME_CKPT not found: {RESUME_CKPT}'
    _sd = torch.load(RESUME_CKPT, map_location=device, weights_only=True)""",
r"""# Phase 2c: eval-only resume. RESUME_CKPT is set and validated in CELL 2 (before
# the dataset download), so by here the path is known to exist. EPOCHS=0 makes
# range(1, EPOCHS+1) empty, so the training loop body never executes -- no
# re-indentation of the loop required.
if RESUME_CKPT:
    _sd = torch.load(RESUME_CKPT, map_location=device, weights_only=True)""",
"c11-consume-ckpt")
put(11, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: patched cell 2 (GPU assert + early RESUME_CKPT resolution), "
      "cell 9 (skip train build when eval-only), cell 11 (consume validated path); "
      "all edited cells parse as valid Python.")
print("\nNOTE: RESUME_CKPT now lives in CELL 2, not cell 7.")
