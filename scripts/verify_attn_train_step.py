"""Run 10 pre-flight: execute cell 11's REAL DO_TRAIN body with ATTN_TARGET=True, on CPU.

Every other check written for 13(b) tests a PIECE:

  verify_attn_target.py         attn_topk_target against a real decoder, in isolation
  verify_saliency_loss_cell.py  the saliency block, with a lambda for the teacher
  verify_training_telemetry.py  the epoch loop, on the INK branch with a stub model
  diagnose_target_drift.py      the target, outside any training loop

None of them runs the COMPOSITION: real model forward -> real `visual_tokens` -> real
frozen teacher -> real target -> BCE -> backward -> optimizer step, in the code that
ships. That is where this project's expensive defects have lived -- a name defined in a
different cell (resolves at call time, so both `ast.parse` and grep stay clean), and a
`lambda_*` that defaulted in and shaped two runs while appearing in no config cell.
Neither was visible until something executed the whole path. Run 10 costs ~6 GPU hours,
so the path gets executed once on CPU first.

Deliberately not a stub test, and deliberately not a paraphrase. The ENTIRE DO_TRAIN body
is sliced out of the notebook and exec'd in two pieces (prologue, then optimizer onward),
split only so parameters can be fingerprinted between snapshot and training. The teacher
snapshot, the unfreeze, `trainable_params`, the criterion branch, LAMBDA_SAL, the scaler,
GRAD_ACCUM and the epoch loop are all the shipped lines. This harness supplies only what
cells 2 and 9 supply on Kaggle: the model, a loader, `device`, and the config constants.

Deviations from the Kaggle run, both forced by CPU: TRAIN_EPOCHS=1, and a 2-page loader
instead of 200. GRAD_ACCUM stays at the shipped 8 -- the loop's
`or (step + 1) == len(train_loader)` clause means the last batch still triggers a real
optimizer step, so the update path is exercised rather than stubbed around.

What it asserts, and the silent failure each one would catch:

  1 LOOP RUNS        the composition completes. The only test of it that exists.
  2 STEP-0 GUARD     the real assert prints `positive rate 0.5000 (expected 0.5000 =
                     2400/4800)` on the real grid. verify_attn_target checks the guard on
                     a small stub; this is the number a reader sees in run 10's log.
  3 TEACHER FROZEN   the teacher's parameters are bit-identical after training. If that
                     deepcopy ever became a reference, the teacher would drift with the
                     student and the target would lose the COHERENCE that D7 identified as
                     the one property ink was really supplying -- with no other symptom.
  4 ROUTER LEARNS    gradient reaches the router AND its weights move. Separates "the loop
                     ran" from "the attention target reached the thing it supervises".
  5 ch == K/N        on this branch the telemetry's chance column must read exactly 0.5000,
                     because top-K pins the target's positive rate. A different value means
                     `ov` is being compared against the wrong null.
  5b enc             the epoch line's `enc` column reports the length the decoder actually
                     received. Added for run 14, whose ONE variable is that merging is in
                     the training graph -- and which `ch` cannot show, since the prune
                     fraction is 0.5000 whether or not the merger ran. Asserted against a
                     value derived from the grid, so a hardcoded `enc` fails.
  6 ENCODER DRIFTS   Swin stage 3 moves, stages 0-2 do not. D10's entire premise is that
                     `UNFREEZE_STAGES = 1` is live; this executes it instead of reading it
                     off a constructor flag, which is a mistake already made once here.
  7 TARGET SURVIVES  recompute the target from the DRIFTED encoder: still exactly K
                     positives. D10 measured stability across a run; this checks the
                     mechanism inside the loop.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
        python -u scripts/verify_attn_train_step.py --full [--steps 2]

WITHOUT `--full` only the two cheap staleness checks run (do the slice anchors still
resolve, does cell 2 still supply the shared imports) and it exits in under a second --
so the `verify_*.py` suite can include this file without becoming slow, while the anchors
that would silently rot are still checked on every suite run. `--full` executes the
training path: minutes, because a Swin-B forward/backward at 2560x1920 plus an
eager-attention teacher pass on CPU is genuinely expensive. Run `--full` by hand before a
GPU run; do not pipe it into `tee` (see Gotchas -- that launders the exit code).
"""
import argparse
import ast
import io
import json
import os
import re
import sys
import textwrap
from contextlib import redirect_stdout

import torch
from transformers import DonutProcessor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

NB = os.path.join(ROOT, "kaggle_pruning_run.ipynb")
RUN5 = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
# A real pruning-era checkpoint, for the identity guard's rejection scenario. Runs 7/8/9/10/11
# are all byte-identical in length, so any of them serves; run 9's is the one run 12 was
# supposed to have attached, which makes it the honest choice for reproducing that failure.
RUN9 = os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")
KEEP = 0.50                     # cell 2 TRAIN_KEEP_RATIO
# cell 2 TRAIN_MERGE_RATIO. Deliberately 0.0 and NOT run 14's shipped 0.40: this file's
# execution scenario is run 10's composition (ATTN_TARGET=True), and merging on top of it
# would make it a two-variable test. Run 14's merge-on TRAINING graph -- gradient survives
# the merger, non-vacuously -- is gated by scripts/verify_train_with_merge.py instead.
# The name is bound to ONE constant that feeds both the model built below and the `pns`
# injection, because those two drifting apart is how a verifier ends up printing
# `merge_ratio=0.4` over a model built at 0.0.
MERGE = 0.0
SAL_THRESH = 0.15               # cell 2 SALIENCY_THRESHOLD
N_EXPECT = 4800                 # 80x60 token grid
K_EXPECT = 2400

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def cell2_imports(src):
    """Every import statement in cell 2, at any nesting depth, as source.

    The notebook's cells share ONE global namespace on Kaggle: cell 2 imports `gc`, and
    cells 7 and 11 use it without importing it. A harness that hand-lists the names it
    remembers will keep discovering that the hard way -- the first version of this file
    died on `gc` after loading a 200M-parameter model. Inheriting cell 2's own import
    block means any name it adds later is here automatically.
    """
    stmts = [ast.unparse(n) for n in ast.walk(ast.parse(src))
             if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not any("import gc" in s for s in stmts):
        raise SystemExit("cell 2 no longer imports gc, but cells 7/11 still call gc."
                         "collect() -- that is now a real defect, not a harness gap")
    return "\n".join(stmts)


def cell2_config(src):
    """Cell 2's config region -- from the resume block to the end, dedented.

    Sliced rather than exec'ing all of cell 2 so this stays fast: everything above it is
    imports and a CUDA probe. The region needs only `os` and `print`.
    """
    a = src.index("# ---- Phase 2c: eval-only resume")
    return src[a:]


def run_cell2_config(src, **overrides):
    """Exec the config region with config literals rewritten, and report what happened.

    Rewrites the ASSIGNMENT lines only (anchored with `^NAME = `), so the asserts and the
    `CFG:` print below them are the shipped ones. Returns (raised_message_or_None, ns).
    """
    for k, v in overrides.items():
        # A function replacement, NOT a string: re.sub interprets escapes in a string
        # repl, so a Windows path's `\U` in repr(...) becomes a truncated \UXXXXXXXX
        # escape and the rewritten cell fails to compile.
        src, n = re.subn(rf"^{k} = [^\n]*$", lambda m, k=k, v=v: f"{k} = {v!r}", src,
                         count=1, flags=re.M)
        if n != 1:
            # Silently substituting nothing would run every scenario against the DEFAULT
            # config and pass -- the exact shape of a decorative check.
            raise SystemExit(f"cell 2 no longer has a top-level `{k} = ...` line, so the "
                             f"gate scenarios would all have silently tested the shipped "
                             f"defaults instead. Re-derive this check.")
    ns = {"os": os, "__name__": "cfg"}
    try:
        with redirect_stdout(io.StringIO()):
            exec(compile(src, "<cell2-config>", "exec"), ns)
        return None, ns
    except AssertionError as e:
        return str(e), ns


def slice_cell(src, first, last, label):
    """The shipped lines from `first` up to (not including) `last`, dedented.

    Raises rather than silently checking nothing if either anchor moved.
    """
    try:
        a = src.index(first)
        b = src.index(last, a)
    except ValueError:
        raise SystemExit(f"could not locate the {label} slice in cell 11 "
                         f"({first.strip()!r} .. {last.strip()!r}) -- cell 11 changed "
                         f"shape; re-derive this pre-flight before trusting it")
    return textwrap.dedent(src[a:b])


def fingerprint(module):
    """Sum of |p| per parameter, in float64.

    The dtype is load-bearing. One AdamW step at lr=1e-5 moves each weight by ~1e-5 with
    near-random sign, so on a 1e6-element tensor `sum|p|` shifts by only ~2e-7 to 5e-7
    RELATIVE (measured on three representative shapes). Against float32's eps of 1.2e-7
    that is 2-5 ULPs: a float32 accumulation does usually resolve it -- it did on all
    three -- but whether it does at all is a matter of which way the sum rounds, not of
    whether the tensor trained. Since checks 4 and 6 read "the value did not change" as
    "the parameter did not train", that coin flip would surface as a confident wrong
    verdict with nothing in the output pointing at arithmetic. float64 removes the
    dependence for the cost of one cast.
    """
    return {k: float(v.detach().double().abs().sum()) for k, v in module.named_parameters()}


class FakeBar(list):
    """tqdm stand-in: the loop only ever iterates it and calls set_postfix."""

    def set_postfix(self, *a, **kw):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--full", action="store_true",
                    help="execute the training path (minutes). Without it, only the "
                         "cheap staleness checks run, so the fast suite stays fast.")
    args = ap.parse_args()

    if not os.path.exists(RUN5):
        raise SystemExit(f"missing run 5 checkpoint: {RUN5}")
    # The identity-guard scenarios are only meaningful if this file is really there and
    # really the pruning-era size. A missing RUN9 would turn "a PRUNING-ERA ckpt must RAISE"
    # into a test of the not-found branch, which already has its own scenario -- it would
    # still print PASS while testing nothing new.
    if not os.path.exists(RUN9):
        raise SystemExit(f"missing pruning-era checkpoint: {RUN9}")
    _r9 = os.path.getsize(RUN9)
    if _r9 == os.path.getsize(RUN5):
        raise SystemExit(f"RUN9 and RUN5 are the same size ({_r9}), so the identity-guard "
                         f"scenarios cannot distinguish them and would pass vacuously.")

    print("=" * 78)
    print("RUN 10 PRE-FLIGHT -- cell 11's real DO_TRAIN body, ATTN_TARGET=True, CPU"
          + ("" if args.full else "  [STALENESS CHECK ONLY]"))
    print("=" * 78)

    # ---------------------------------------------------- the notebook's own cells 4/5/7
    cells = ["".join(c["source"]) for c in
             json.load(open(NB, encoding="utf-8"))["cells"]]
    ns = {"__name__": "nb"}
    imports = cell2_imports(cells[2])
    exec(compile(imports, "<cell2-imports>", "exec"), ns)
    for i in (4, 5, 7):
        exec(compile(cells[i], f"<cell{i}>", "exec"), ns)
    cell11 = cells[11]
    prologue = slice_cell(cell11, "    _teacher_dec = None",
                          "    optimizer = torch.optim.AdamW", "prologue")
    body = slice_cell(cell11, "    optimizer = torch.optim.AdamW",
                      "    os.makedirs('/kaggle/working/checkpoints'", "training body")
    print(f"  namespace seeded from cell 2's own {len(imports.splitlines())} import "
          f"statements; cells 4/5/7 exec'd")
    print(f"  sliced from cell 11: prologue {len(prologue.splitlines())} lines, "
          f"training body {len(body.splitlines())} lines (both verbatim)")

    # ------------------------------------------------------------- staleness assertions
    # These run in the fast suite. They are cheap and they are the ones that rot: every
    # anchor above is a string match into generated code, and a slice that silently
    # relocates turns this whole file into a test of nothing. Asserting the SHAPE of what
    # was sliced (not just that .index() found something) is what makes it fail loudly.
    check("S1 ANCHORS RESOLVE",
          "attn_topk_target(" in body and "_teacher_dec = copy.deepcopy" in prologue
          and "scaler.step(optimizer)" in body and "epoch_ov" in body,
          f"the sliced prologue still snapshots the teacher, and the sliced body still "
          f"contains the ATTN target call, the optimizer step and the ov/ch telemetry")
    check("S2 CELL 2 STILL SUPPLIES THE SHARED IMPORTS",
          "AdaptiveDonutOCR" in ns and "attn_topk_target" in ns
          and "AdaptivePruningLoss" in ns and "patch_ink" in ns,
          "cells 4/5/7 exec'd cleanly under cell 2's import block alone -- the cross-cell "
          "`gc` coupling (see Gotchas) is still covered")

    # ------------------------------------------- S3  cell 2's early config gate, executed
    # The gate exists so the most likely run-10 mistake -- ATTN_TARGET=True with no run-5
    # checkpoint attached -- costs a minute in cell 2 instead of twenty minutes waiting for
    # Cell 6's dataset download to finish before cell 11 says the same thing. A guard is
    # half-tested until it has been driven against the states it must REJECT *and* the ones
    # it must ACCEPT, so all four combinations run here: run 9's config must still pass
    # untouched, and the two misconfigurations must raise with a message that names the fix.
    #
    # DO_TRAIN is now set EXPLICITLY in every scenario. It used to be inherited from the
    # shipped literal, which was fine only while that literal was True: run 12 flipped it to
    # False, and an inherited False would have made the first scenario raise on the new
    # sweep-with-no-checkpoint guard -- a green suite turning red for a reason that has
    # nothing to do with ATTN_TARGET. Inheriting a config literal into a scenario table is
    # the same D5 shape the rest of this file argues against; naming it fixes that too.
    #
    # 2026-09-17: it happened AGAIN, with TRAIN_MERGE_RATIO, which run 14 added. Naming
    # DO_TRAIN did not inoculate the table -- it fixed one instance of the pattern, and the
    # pattern recurs every time cell 2 gains a knob that any guard reads. So every literal
    # the shipped asserts touch is now pinned here, and the first scenario's DEFECT is worth
    # recording rather than quietly fixing: it was labelled "train from run 5" while passing
    # RESUME_CKPT=None, and had been since it was written. Nothing caught it because no
    # guard distinguished those two states until run 14's did.
    cfgsrc = cell2_config(cells[2])
    NOMERGE = dict(TRAIN_MERGE_RATIO=0.0)      # runs 9-13: merging was never in training
    scen = {
        # Run 9's ACTUAL gate-relevant config. The name now matches the dict: what this
        # asserts is that ATTN_TARGET=False needs no checkpoint, not that run 9 had none.
        "run 9 config (ATTN off, no ckpt required) must PASS":
            (dict(ATTN_TARGET=False, RESUME_CKPT=None, DO_TRAIN=True, **NOMERGE), False),
        "ATTN on + RESUME_CKPT=None must RAISE":
            (dict(ATTN_TARGET=True, RESUME_CKPT=None, DO_TRAIN=True, **NOMERGE), True),
        "ATTN on + real run-5 ckpt must PASS":
            (dict(ATTN_TARGET=True, RESUME_CKPT=RUN5, DO_TRAIN=True, **NOMERGE), False),
        "ATTN on + SUPERVISE_SALIENCY off must RAISE":
            (dict(ATTN_TARGET=True, RESUME_CKPT=RUN5, SUPERVISE_SALIENCY=False,
                  DO_TRAIN=True, **NOMERGE), True),
        # Run 12's config and its negation. The second is the state that guard exists
        # for: it is what "Run All" did on an unedited notebook while DO_TRAIN shipped
        # False, and without the guard it sweeps an untrained router into a full results
        # table. Both directions run, so the guard cannot pass by rejecting everything.
        "run 12 config (sweep only, ckpt attached) must PASS":
            (dict(ATTN_TARGET=False, RESUME_CKPT=RUN5, DO_TRAIN=False, **NOMERGE), False),
        "sweep only + RESUME_CKPT=None must RAISE (untrained router)":
            (dict(ATTN_TARGET=False, RESUME_CKPT=None, DO_TRAIN=False, **NOMERGE), True),
        # Run 14's config and its negation. Training WITH merging is only interpretable
        # against run 9, which started from run 5's weights; starting from donut-base
        # instead still trains, still sweeps, still prints Q6, and voids the comparison
        # silently. Note the contrast with scenario 1: merge-free training from no
        # checkpoint is allowed, merge-on training from no checkpoint is not, which is
        # what makes this guard narrower than "DO_TRAIN needs a checkpoint".
        "run 14 config (train WITH merging, run-5 ckpt) must PASS":
            (dict(ATTN_TARGET=False, RESUME_CKPT=RUN5, DO_TRAIN=True,
                  TRAIN_MERGE_RATIO=0.40), False),
        "train WITH merging + RESUME_CKPT=None must RAISE (voids the run-9 contrast)":
            (dict(ATTN_TARGET=False, RESUME_CKPT=None, DO_TRAIN=True,
                  TRAIN_MERGE_RATIO=0.40), True),
        "train WITH merging + a ckpt path that does not exist must RAISE":
            (dict(ATTN_TARGET=False, RESUME_CKPT=RUN5 + ".missing", DO_TRAIN=True,
                  TRAIN_MERGE_RATIO=0.40), True),
        # 2026-09-18: the identity guard run 12 paid for. Every scenario above satisfies the
        # run-14 guard by pointing at a file that EXISTS, which is exactly the state run 12
        # was in -- it attached a real checkpoint at a real path and measured the wrong
        # weights for an hour. So the new cell-2 assert checks the file's SIZE, and this
        # scenario is what stops that assert from being decorative: a pruning-era checkpoint
        # is a perfectly valid file, satisfies every earlier guard, and must still be
        # refused under TRAIN_MERGE_RATIO>0.
        #
        # RUN9 is used rather than a fabricated file on purpose -- a synthetic wrong-sized
        # file would prove only that the assert reads `os.path.getsize`, not that it rejects
        # the specific confusion that actually happened.
        "train WITH merging + a PRUNING-ERA ckpt must RAISE (run 12's failure)":
            (dict(ATTN_TARGET=False, RESUME_CKPT=RUN9, DO_TRAIN=True,
                  TRAIN_MERGE_RATIO=0.40), True),
        # ...and the paired non-vacuity: the SAME pruning-era checkpoint must be ACCEPTED
        # when merging is off, because runs 12/13's sweep-only config is legitimately built
        # on exactly those weights. Without this row the guard could be rejecting run 9 for
        # some unrelated reason, or rejecting it always, and both would still print PASS
        # above.
        "sweep only + the same PRUNING-ERA ckpt must PASS (guard is merge-scoped)":
            (dict(ATTN_TARGET=False, RESUME_CKPT=RUN9, DO_TRAIN=False,
                  TRAIN_MERGE_RATIO=0.0), False),
    }
    for desc, (over, want_raise) in scen.items():
        msg, _ = run_cell2_config(cfgsrc, **over)
        ok = (msg is not None) == want_raise
        check(f"S3 GATE -- {desc}", ok,
              (f"raises: {msg[:64]}..." if msg else "runs clean") if ok else
              (f"did NOT raise (the gate is decorative for this state)" if want_raise
               else f"raises on a state it must accept -- this would block the run: {msg[:64]}"))

    if not args.full:
        print()
        print("=" * 78)
        failed = [n for n, ok, _ in results if not ok]
        print(f"{len(results) - len(failed)}/{len(results)} staleness check(s) passed"
              + (f" -- FAILING: {', '.join(failed)}" if failed else ""))
        print("The 11 execution assertions (3 setup + the 8 core ones) did NOT run. "
              "Before a GPU run:")
        print("  python -u scripts/verify_attn_train_step.py --full")
        print("=" * 78)
        raise SystemExit(1 if failed else 0)

    # ------------------------------------------------ real data, cell 9's exact schema
    from datasets import load_dataset
    from diagnose_ste_signal import MAX_LEN, build_target_text

    proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split="train")
    batches = []
    for i in range(args.steps):
        pv = proc(ds[i]["image"].convert("RGB"), return_tensors="pt").pixel_values
        prompt = f"<s_doc>{json.dumps({'text': build_target_text(ds[i])})}</s>"
        lab = proc.tokenizer([prompt], add_special_tokens=False, max_length=MAX_LEN,
                             padding="max_length", truncation=True,
                             return_tensors="pt").input_ids
        din = lab.clone()                       # cell 9 clones BEFORE masking
        lab = lab.clone()
        lab[lab == proc.tokenizer.pad_token_id] = -100
        batches.append({"pixel_values": pv, "labels": lab, "decoder_input_ids": din})
    print(f"  {len(batches)} real FUNSD page(s), pixel_values "
          f"{tuple(batches[0]['pixel_values'].shape)}, "
          f"{int((batches[0]['labels'] != -100).sum())} real label positions on page 0")

    # ------------------------------------------------------------ model, at run 5's weights
    # Constructed via a check, not bare, because a name cell 7 borrows from cell 2 fails
    # HERE at call time -- the exact shape of defect this pre-flight exists to catch. A
    # bare traceback after a 200M-parameter load is a worse report than a named FAIL.
    try:
        model = ns["AdaptiveDonutOCR"](keep_ratio=KEEP, merge_ratio=MERGE,
                                       freeze_encoder=True)
        build_err = None
    except Exception as e:                      # noqa: BLE001
        model, build_err = None, e
    check("0 MODEL BUILDS", build_err is None,
          "cell 7's AdaptiveDonutOCR constructed under cell 2's namespace"
          if build_err is None else
          f"{type(build_err).__name__}: {build_err} -- if this is a NameError, cell 7 is "
          f"borrowing a name from another cell")
    if build_err is not None:
        raise SystemExit(1)
    sd = torch.load(RUN5, map_location="cpu", weights_only=True)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    check("0 RUN 5 LOADS", not unexpected,
          f"unexpected={len(unexpected)} missing={len(missing)} "
          f"(missing are pruning-era keys run 5 predates)")

    # Only what cells 2 and 9 supply on Kaggle. Everything else is already in `ns`,
    # inherited from cell 2's imports -- do not re-inject names here.
    pns = dict(ns)
    pns.update({"model": model, "ATTN_TARGET": True, "RESUME_CKPT": RUN5,
                "SUPERVISE_SALIENCY": True, "TRAIN_KEEP_RATIO": KEEP,
                "TRAIN_MERGE_RATIO": MERGE,
                "SALIENCY_THRESHOLD": SAL_THRESH, "TRAIN_EPOCHS": 1,
                "device": torch.device("cpu"), "processor": proc,
                "train_loader": batches, "tqdm": lambda it, **kw: FakeBar(it)})

    # ---- prologue: teacher snapshot + unfreeze + trainable_params, as shipped
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(compile(prologue, "<cell11-prologue>", "exec"), pns)
    for l in buf.getvalue().splitlines():
        if l.strip():
            print(f"    | {l}")
    teacher = pns["_teacher_dec"]
    check("0 TEACHER SNAPSHOTTED",
          teacher is not None and not any(p.requires_grad for p in teacher.parameters()),
          f"cell 11's own prologue built a frozen teacher and {len(pns['trainable_params'])} "
          f"param groups -- its asserts on RESUME_CKPT and SUPERVISE_SALIENCY ran too")

    stages = model.model.encoder.encoder.layers
    before = {"teacher": fingerprint(teacher),
              "router": fingerprint(model.router),
              "stages": [fingerprint(s) for s in stages]}

    # Gradient reaching the router, recorded at backward time so this does not depend on
    # the optimizer (which the shipped body constructs itself, below).
    seen = []
    for p in model.router.parameters():
        p.register_hook(lambda g: seen.append(float(g.abs().sum())) or g)

    # ---- training body: optimizer, criterion, LAMBDA_SAL, scaler, GRAD_ACCUM, the loop
    print(f"\n  executing cell 11's training body over {len(batches)} step(s)"
          f" -- MINUTES on CPU (Swin-B fwd+bwd at 2560x1920 + eager-attention teacher)...",
          flush=True)
    buf = io.StringIO()
    err = None
    try:
        with redirect_stdout(buf):
            exec(compile(body, "<cell11-training-body>", "exec"), pns)
    except BaseException as e:                  # noqa: BLE001 -- reporting it IS the test
        err = e
    out = buf.getvalue()
    for l in out.splitlines():
        if l.strip():
            print(f"    | {l}")
    print()

    check("1 LOOP RUNS", err is None,
          "the full composition completed: model fwd -> visual_tokens -> frozen teacher "
          "-> attn top-K target -> BCE -> scaled backward -> optimizer step"
          if err is None else f"{type(err).__name__}: {err}")

    # ------------------------------------------------- 2  the step-0 guard, real grid
    m = re.search(r"target: ATTN top-K \| positive rate ([\d.]+) "
                  r"\(expected ([\d.]+) = (\d+)/(\d+)\)", out)
    if m:
        rate, want, K, N = (float(m.group(1)), float(m.group(2)),
                            int(m.group(3)), int(m.group(4)))
        check("2 STEP-0 GUARD",
              abs(rate - want) < 1e-4 and N == N_EXPECT and K == K_EXPECT,
              f"rate {rate:.4f} == expected {want:.4f} = {K}/{N} on the real grid "
              f"(the line to read in run 10's log)")
    else:
        check("2 STEP-0 GUARD", False,
              "the ATTN step-0 line never printed: the branch did not run, or its format "
              f"changed. Captured output began {out[:160]!r}")

    # ------------------------------------------------------- 3  teacher bit-identical
    after_t = fingerprint(teacher)
    moved = [k for k, v in after_t.items() if v != before["teacher"].get(k)]
    check("3 TEACHER FROZEN", not moved,
          f"all {len(after_t)} teacher parameters bit-identical after training -- the "
          f"target stays COHERENT (D7's load-bearing property)" if not moved else
          f"{len(moved)} teacher params MOVED, e.g. {moved[:3]} -- the deepcopy is not "
          f"isolating the teacher, so the target drifts with the student")

    # -------------------------------------------- 4  did the target reach the router
    after_r = fingerprint(model.router)
    r_moved = sum(1 for k, v in after_r.items() if v != before["router"][k])
    gsum = max(seen) if seen else 0.0
    check("4 ROUTER LEARNS", gsum > 1e-9 and r_moved > 0,
          f"max per-tensor |grad| sum {gsum:.4e} over {len(seen)} backward hook call(s), "
          f"and {r_moved}/{len(after_r)} router tensors changed value -- the attention "
          f"target reached the router AND the update was applied (not scaler-skipped)")

    # ------------------------------------------------------------ 5  ch must be K/N
    ep = [l for l in out.splitlines() if l.strip().startswith("Epoch ")]
    ch = re.search(r"\bch ([\d.]+)", ep[-1]) if ep else None
    if ch:
        check("5 ch == K/N", abs(float(ch.group(1)) - KEEP) < 5e-4,
              f"chance column reads {ch.group(1)} == K/N {KEEP:.4f}, as top-K forces. "
              f"Epoch line: {ep[-1].strip()}")
    else:
        check("5 ch == K/N", False,
              f"no `ch` in the epoch line: {ep[-1].strip() if ep else '(none printed)'}")

    # ------------------------------------------- 5b  `enc` must report the REAL length
    # Run 14's `enc` column is the ONLY evidence in a Kaggle log that merging actually
    # ran during training -- `ch` is the prune fraction and reads 0.5000 either way. A
    # column that exists to prove a thing happened has to be shown to track that thing,
    # not merely to be present: with MERGE=0.0 it must read K (2400), and the check is
    # written against `K_EXPECT` computed from the grid rather than against the literal
    # in the print, so a hardcoded `enc` would fail here.
    enc = re.search(r"\benc (\d+)", ep[-1]) if ep else None
    want_enc = K_EXPECT - min(round(K_EXPECT * MERGE), K_EXPECT // 2)
    if enc:
        check("5b enc == what the decoder received",
              int(enc.group(1)) == want_enc,
              f"enc reads {enc.group(1)}, want {want_enc} (K={K_EXPECT} at "
              f"merge_ratio={MERGE}). At run 14's shipped 0.40 this column reads 1440; "
              f"reading 2400 there would mean the merger never ran")
    else:
        check("5b enc == what the decoder received", False,
              f"no `enc` in the epoch line -- run 14 would have no per-epoch evidence "
              f"that merging happened: {ep[-1].strip() if ep else '(none printed)'}")

    # --------------------------------------------- 6  UNFREEZE_STAGES = 1, executed
    after_s = [fingerprint(s) for s in stages]
    per_stage = [sum(1 for k, v in after_s[i].items() if v != before["stages"][i][k])
                 for i in range(len(stages))]
    check("6 ENCODER DRIFTS (top stage only)",
          per_stage[-1] > 0 and all(n == 0 for n in per_stage[:-1]),
          f"tensors changed per Swin stage: {per_stage} -- top stage trains, the rest are "
          f"bit-identical. UNFREEZE_STAGES=1 executed, not read off a flag")

    # ----------------------------------------- 7  target well-posed on drifted features
    with torch.no_grad():
        vt = model.model.encoder(batches[0]["pixel_values"]).last_hidden_state
        tgt = ns["attn_topk_target"](teacher, vt, batches[0]["decoder_input_ids"],
                                     batches[0]["labels"], vt.shape[1], KEEP)
    pos = int(tgt.sum())
    check("7 TARGET SURVIVES DRIFT", pos == K_EXPECT and vt.shape[1] == N_EXPECT,
          f"recomputed from the DRIFTED encoder: {pos} positives over {vt.shape[1]} "
          f"tokens (want {K_EXPECT}/{N_EXPECT})")

    print()
    print("=" * 78)
    failed = [n for n, ok, _ in results if not ok]
    print(f"{len(results) - len(failed)}/{len(results)} passed"
          + (f" -- FAILING: {', '.join(failed)}" if failed else " -- all clear"))
    if not failed:
        print("Run 10's training path has now been EXECUTED end to end, not assembled from")
        print("separately-tested pieces. This says NOTHING about whether the target helps;")
        print("acceptance is still recall at keep=0.50/0.35 vs run 9.")
    print("=" * 78)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
