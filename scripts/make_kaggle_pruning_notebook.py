"""Generate kaggle_pruning_run.ipynb -- a single runnable Kaggle notebook that does
Pending 1a (retrain the router WITH pruning ON) and then the Phase 2d selection
ablation sweep, in one Run-All.

It starts from the existing, already-Phase-2d-patched kaggle_token_pruning_ocr.ipynb
(which carries the verified model/router/tome/loss/dataset/ablation code inline)
and adds a series of small, asserted edits:
  A. cell 2  -- DO_TRAIN / TRAIN_KEEP_RATIO / TRAIN_EPOCHS / PRUNED_CKPT config,
                plus the `typing` import that E and F's spliced code needs.
  B. cell 9  -- build train_loader when DO_TRAIN (currently skipped in EVAL_ONLY).
  C. cell 11 -- branch: DO_TRAIN retrains with pruning ON (keep_ratio<1, STE active,
                sparsity loss targeting the real budget); else keeps the original
                pruning-OFF / eval-only behaviour. The downstream eval + ablation
                cells use the in-memory `model`, so no other edits are required.
  D. cell 7  -- attn_topk_target teacher helper + expose pre-prune visual_tokens.
  E. cell 4  -- replace the notebook's OLD BipartiteTokenMerger with src/tome.py.
                The canonical notebook still carries the pre-2026-09-14 split
                (`arange(0, K, 2)`), which partitions by the router's SCORE RANK
                rather than by page position and strands ~half of all genuinely
                redundant pairs in the same set. Spliced from disk, not retyped.
  F. cell 7  -- `_token_grid` + `_tome_partition` from src/model.py, both merger
                call sites rewired to pass orig_idx/token_grid, and a
                `tome_split='checkerboard'|'rank_parity'` knob on generate() so the
                pre-fix split is available as a negative control.
  G. cell 15 -- token-matched merge rows: every merge row paired with a prune-only
                row at the identical final token count M, plus the Q6 verdict block.
                Also stores per-image `word_order` (G3b), without which a primary
                cannot be pre-registered on anything but recall and NED.

Patches E/F/G are what make the four-stage architecture (prune -> merge -> decode)
actually execute; every recorded run so far is prune-only at merge_ratio=0.0.

Convention: every edited cell is ast.parse-checked before writing, and the final
notebook is validated cell-by-cell. The original notebook is NOT modified.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/make_kaggle_pruning_notebook.py
"""
import ast
import json
import os
import textwrap

SRC = "kaggle_token_pruning_ocr.ipynb"
OUT = "kaggle_pruning_run.ipynb"

# Read the canonical notebook and patch it IN MEMORY. OUT is written once, at the very
# bottom, after every patch has applied and every cell has been ast.parse'd.
#
# This used to be `shutil.copyfile(SRC, OUT)` here at import time, and that was a
# destructive failure mode rather than a stylistic one: any assert in any patch below
# left OUT as a BARE COPY OF THE CANONICAL NOTEBOOK -- which carries the broken parity
# split (see AGENTS.md gotcha) and none of the merge rows -- under the filename that
# promises the fixed merger. A failed regeneration did not leave the previous generated
# notebook stale; it deleted it, silently, and `git status` is no help because this repo
# is not a git repository. Found 2026-09-26 when three failed runs on PATCH H4's anchor
# reduced kaggle_pruning_run.ipynb to the canonical cells, and a dump of "the generated
# notebook" was in fact reading the canonical one -- which is what made the anchor
# mismatch look impossible for as long as it did.
#
# `BAK` was defined next to these and never referenced by anything, so it was removed
# rather than left looking like a safety net that exists.
nb = json.loads(open(SRC, encoding="utf-8").read())
cells = nb["cells"]


def src(i):
    return "".join(cells[i]["source"])


def put(i, s):
    cells[i]["source"] = s.splitlines(keepends=True)
    ast.parse(s)  # a cell that cannot parse must never be written


def indent(block, n=4):
    pad = " " * n
    return "\n".join(pad + ln if ln.strip() else ln for ln in block.splitlines())


HERE = os.path.dirname(os.path.abspath(__file__))


def read_from_src(relpath):
    return open(os.path.join(HERE, "..", relpath), encoding="utf-8").read()


def read_method(relpath, name, cls_indent=4):
    """Extract a `    def <name>(...)` method block VERBATIM from a src/ file.

    Patches E and F splice real code out of src/ rather than carrying a retyped
    copy, and that is the entire point of them: the reason ToMe never ran on a
    recorded result is that the notebook held a SECOND, older copy of the merger
    while src/ held the fixed one, and nothing compared them. A hand-maintained
    third copy in this generator would recreate exactly that failure one level up.
    Reading from disk makes the divergence impossible instead of merely unlikely.

    The "first line at or above cls_indent ends the method" rule is correct for a
    BODY and wrong for a multi-line SIGNATURE, whose closing `) -> T:` sits at
    exactly cls_indent. Written for single-line defs, it silently returned the
    first 5 lines of `_selection_signal` -- a signature with no body, which is
    still valid-looking text. So the signature is consumed by paren depth first,
    and the extracted block is then parsed: a truncation that leaves a def with no
    body is a SyntaxError or an empty-body FunctionDef, and both raise here rather
    than reaching the notebook. Found 2026-09-26 by a content assert at the call
    site; the parse check is what makes the next one impossible to ship quietly.
    """
    text = read_from_src(relpath)
    head = "\n" + " " * cls_indent + f"def {name}("
    assert text.count(head) == 1, (
        f"{relpath}: `def {name}(` at indent {cls_indent} appears "
        f"{text.count(head)} times, expected 1")
    lines = text[text.index(head) + 1:].splitlines(keepends=True)
    out = [lines[0]]
    depth = lines[0].count("(") - lines[0].count(")")
    i = 1
    while depth > 0:                     # still inside the parameter list
        assert i < len(lines), f"{relpath}: unterminated signature for {name}"
        out.append(lines[i])
        depth += lines[i].count("(") - lines[i].count(")")
        i += 1
    for ln in lines[i:]:
        # First non-blank line at or above the class-body indent ends the method.
        if ln.strip() and (len(ln) - len(ln.lstrip(" "))) <= cls_indent:
            break
        out.append(ln)
    block = "".join(out).rstrip("\n")
    tree = ast.parse(textwrap.dedent(block))
    assert (len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
            and tree.body[0].name == name), (
        f"{relpath}: extracted block for {name} is not a single function def")
    body = tree.body[0].body
    stripped = [n for n in body if not (isinstance(n, ast.Expr)
                                        and isinstance(n.value, ast.Constant))]
    assert stripped, (
        f"{relpath}: extracted {name} has a docstring and NO statements -- the "
        f"extraction truncated. Splicing this would ship a method that silently "
        f"returns None.")
    return block


# ======================================================================= PATCH A
print("A. cell 2 -- DO_TRAIN config")
c2 = src(2)
assert "RESUME_CKPT" in c2, "cell 2 did not contain RESUME_CKPT"

# The canonical cell 2 sets `EVAL_ONLY = bool(RESUME_CKPT)` and then prints "training
# skipped" -- written before DO_TRAIN existed, when a checkpoint could only mean eval-only.
# Cell 9's gate is correctly `EVAL_ONLY and not DO_TRAIN`, so the BEHAVIOUR is right; it is
# the LOG that lies. Every run since 9 has attached a checkpoint AND trained, so every one
# of those logs opens by announcing that the thing it then spent four hours doing was
# skipped. Run 14 is a ~5 h run whose whole point is that training happened, so a reader
# checking "did it train?" must not find "training skipped" as the first answer. DO_TRAIN
# is not defined yet at this point in the cell, so the print defers to the PLAN line
# instead of guessing.
_EO_OLD = ("if EVAL_ONLY:\n"
           "    print(f'EVAL-ONLY mode: will load {RESUME_CKPT}')\n"
           "    print('  -> training skipped, and Cell 6 will skip building the train set')")
_EO_NEW = ("if EVAL_ONLY:\n"
           "    print(f'CHECKPOINT ATTACHED: will load {RESUME_CKPT}')\n"
           "    print('  -> whether this is eval-only depends on DO_TRAIN below; the PLAN '\n"
           "          'line is authoritative. Cell 6 skips the train set only if DO_TRAIN '\n"
           "          'is False.')")
assert c2.count(_EO_OLD) == 1, (
    f"cell 2 EVAL_ONLY print block: expected 1 hit, found {c2.count(_EO_OLD)}")
c2 = c2.replace(_EO_OLD, _EO_NEW, 1)

CFG = '''

# ---- Pending 1a: train the router WITH pruning ON (set False to reproduce the
# Phase 2d selection ablation on run-5 weights instead of retraining) ----
# Runs 2-5 trained at keep_ratio=1.0, so the STE multiplier was exactly 1.0 and the
# router never got gradient about REMOVING a token -- Diagnostic D1 showed it then
# ranks blank paper above text. Training at keep_ratio<1 makes K<N, so the kept
# set actually changes and the router finally learns which tokens matter.
# Flipped True -> False for run 12 (2026-09-16). True was right while Pending 1a was open:
# runs 9/10/11 each retrained, and the notebook's job was to produce a checkpoint and then
# sweep it. Run 12 asks a different question -- does compressing to M tokens by MERGING cost
# less than compressing to the same M by PRUNING -- and every token-matched pair has to sit
# on the SAME weights for that question to mean anything. Retraining here would move the
# checkpoint under the pairs.
# Flipped BACK to True for run 14 (2026-09-17), because runs 12/13 answered that question
# and the answer moved the next one. Run 13 (run-9 weights, 28 rows): merging away 20% of
# the kept set is FREE -- five selection-held-fixed contrasts, all null -- while merging
# away 40% costs -3.86 pts [-7.44, -0.35], the ONLY statistically resolved merge effect in
# the run and the only confirmed cost. D12/H1 say that is exactly the condition under which
# a cost is expected: every checkpoint in this project was trained at merge_ratio=0.0, so
# run 13 measured merging strictly off-distribution. Run 14 puts merging INTO training and
# asks whether the 40% row is recoverable -- which is what would take the KV budget from
# 2.5x (M=1920) to 3.33x (M=1440).
# ---- SET TO False FOR T4 (2026-09-30), BY AN EXPLICIT RULING, NOT BY DRIFT. ---------
# The user's decision on this date, recorded because AGENTS.md's standing instruction was
# "decide in writing whether run 18 precedes T4 -- do not discover the answer by launching
# it": T4 GOES FIRST. T4 is the next unchecked queue item, it is eval-only, and it unblocks
# T5/T6/T7; run 18 is off-queue and was authorised by nothing in the tracker.
#
# Run 18's config below is DELIBERATELY LEFT STAGED, not reverted -- TRAIN_SELECT_MODE
# stays 'ink'. With DO_TRAIN=False every train-time knob in this block is INERT: cell 9
# skips the train set, cell 11 takes the `else` branch, and `_VS_RUN9` (below) is False by
# construction. Run 18 can therefore be launched later by flipping this one flag back,
# which is the whole reason for not deleting its block.
#
# ---- SUPERSEDED 2026-10-02: RUN 18 IS CANCELLED, NOT DEFERRED. ----------------------
# User ruling on that date, on the ground that it "is not logged in" -- it was staged into
# this generator by a session whose chat was lost to compaction, authorised by nothing in
# AGENTS.md, and off the serial queue. So the paragraph above is now WRONG in its premise:
# "launchable later by flipping one flag" was a feature while run 18 was pending and is a
# HAZARD once it is cancelled. A one-flag path to an unauthorised 4-hour training run,
# sitting in the shipped config, is the `lambda_entropy=0.05` shape exactly -- a knob
# nobody chose that a future reader inherits.
# TRAIN_SELECT_MODE is therefore reverted to 'router', the value that makes `_VS_RUN9`
# False on its own merits rather than only because DO_TRAIN is False. If the ink-oracle
# training arm is ever wanted it needs a NEW queue item with its own rationale, addressing
# D3's co-adaptation finding and the "ink/random rows are router-independent at eval"
# gotcha -- neither of which the staged config addressed.
# ⚠ Do NOT read this revert as a finding about select_mode='ink' training. Nothing was
# measured. PATCH H (the `_selection_signal` splice) is a correctness fix and STAYS; only
# the staged CONFIG is cancelled.
#
# ⚠ THIS FLIP MOVES TWO GUARDS IN OPPOSITE DIRECTIONS -- see the asserts below.
#   LIVE:    `assert DO_TRAIN or RESUME_CKPT` fires for the first time in this project's
#            history, because an eval-only sweep with no checkpoint is 29 rows of noise
#            that still tabulates. That guard was written FOR this default and called
#            DORMANT in its own comment; it is now the load-bearing one.
#   DORMANT: both `_VS_RUN9` checkpoint asserts switch OFF, and that is the hazard, not
#            the relief. They were the only thing standing between a sweep and the wrong
#            weights. T4 needs run 9's PRUNING-ERA checkpoint (run 13's, so the pooled
#            rows extend runs 13/14); the run-5 demand those asserts encode is correct for
#            run 14/18 and WRONG for T4. So they must not merely be disabled -- they are
#            replaced by the eval-only guard added below, or T4 repeats run 12 exactly:
#            a checkpoint whose path existed, 28 rows swept, headline an artifact.
#            ⚠ THAT GUARD DID NOT EXIST UNTIL 2026-10-02. This paragraph described it in
#            the present tense ("they are replaced by") while nothing implemented it, so
#            for two days the T4 default shipped with BOTH identity asserts dormant and
#            no replacement -- i.e. the exact hazard the paragraph warns about, created by
#            the paragraph's own change and hidden by its own reassurance. It is written
#            now, search `THE EVAL-ONLY GUARD`. A comment that says a guard exists reads
#            identically whether or not it does; the only way to tell is to run it.
DO_TRAIN = False                 # True: retrain-with-pruning-ON then sweep; False: sweep only
TRAIN_KEEP_RATIO = 0.50          # budget the router is trained to honor (Pending 1a)
# ---- Run 14's ONE VARIABLE. Everything else in this block matches run 9 exactly, so
# run 14 - run 9 isolates "was merging present during training".
#
# Why 0.40 and not 0.20: 0.20 is already free on merge-naive weights, so training it can
# only make a null more null -- the run would cost 5 h to confirm something run 13 already
# showed. 0.40 is where the measurable cost sits, it is the row whose recovery changes the
# headline compression, and H1 predicts a trained-at-0.40 router does best AT 0.40. The
# sweep measures both 0.20 and 0.40 rows regardless, so a 0.40-trained checkpoint that
# hurts the 0.20 row will say so rather than hide it.
#
# This is a TRAIN-time knob only. The cell-15 sweep passes merge_ratio per row and never
# reads this, so the 28-row grid stays identical to run 13's and the two are comparable.
#
# ---- SET BACK TO 0.0 FOR RUN 18 (2026-09-26). Run 14's 0.40 is kept above as history,
# not deleted. Run 18's one variable is TRAIN_SELECT_MODE, measured against run 9, and
# run 9 trained at merge_ratio=0.0 -- so merging has to go back off or run 18 differs
# from its own baseline by two knobs at once. See the TRAIN_SELECT_MODE block below.
TRAIN_MERGE_RATIO = 0.0

# ---- RUN 18's ONE VARIABLE: which tokens the decoder is trained on. ----------------
# Everything else in this block matches run 9 exactly, so run 18 - run 9 isolates
# "was the kept set chosen by the learned router or by patch ink".
#
# WHY THIS RUN EXISTS. Claim 2 of AGENTS.md says the router's selection value is real
# and large (+17.7 to +34.0 pts over a random mask at matched budget). Every one of
# those numbers is measured on a decoder that was TRAINED alongside the router, and the
# ink/random/negated rows are evaluated on that same decoder -- so they are scored
# off-distribution while the router is scored on it. D15 measured how big that confound
# is rather than arguing about it: corr(router retained_ink, router-minus-ink margin) =
# -0.702 pooled (permutation p = 0.0098), strengthening as the budget tightens
# (-0.107 / -0.614 / -0.990 at keep 0.75 / 0.50 / 0.35), and decomposing onto the INK
# arm (+0.634) rather than the ROUTER arm (+0.083) -- i.e. the margin moves because the
# non-router rows move. At keep=0.35 a BYTE-IDENTICAL ink token set is read 9.54 points
# differently by four different decoders, against a mean claimed router margin of 2.15
# points. The confound is 4.4x the effect it is used to support.
#
# The only fix is to give ink its own decoder. Then each selector is evaluated in the
# regime it was trained for and neither is off-distribution:
#     arm R = run 9        (router-trained, router-eval)   <- already on disk
#     arm I = run 18       (ink-trained,    ink-eval)      <- this run
# The 2x2 (each checkpoint x each selector) is what separates "the router selects
# better" from "the decoder was bent toward whatever selected during training".
#
# BOTH OUTCOMES ARE PUBLISHABLE, which is why this is worth 4-4.5 GPU-hours and why the
# pre-registration is written before the run: arm R > arm I makes claim 2 a real result
# for the first time; arm I >= arm R is a stronger NEGATIVE result -- that a learning-
# free contrast statistic matches a trained router on document OCR, so the learned
# selector is unnecessary. What is NOT publishable is the current state, where the
# comparison is confounded by 4.4x its own effect size.
#
# MECHANISM, and why it is one knob and not a new code path: select_mode swaps the
# RANKING SIGNAL only. K, the architecture, the loss and the decoder are untouched, so
# both arms cost the same and the rows stay comparable. It is the same lever the eval
# sweep has used since run 7 -- this run is the first to put it in TRAINING.
#
# CONSEQUENCE, stated so it is not discovered in a post-mortem: under any non-router
# mode the router's scorer receives NO task gradient. src/router.py:92 gates the STE on
# `self.training and use_ste and select_scores is None`, and an external ranking makes
# the third term false. That is CORRECT for this arm -- ink is a learning-free selector
# and the run is asking what the DECODER can do with it, not training a second router --
# but it means arm I's router head is inert, so do not read arm I's `router` sweep rows
# as a trained router. Verified by execution, not by reading: 0.000e+00 scorer gradient
# under ink, 1.915e-01 under router (scripts/verify_train_select_mode.py).
#
# DO NOT "SIMPLIFY" THIS ARM BY TURNING SUPERVISE_SALIENCY OFF. It looks dead -- the
# ink-BCE term trains a scorer that no longer chooses anything -- and it is not. The top
# Swin stage is UNFROZEN (UNFREEZE_STAGES=1, lr 1e-5), so that term's gradient reaches
# the encoder tail, which the decoder reads. Dropping it would change two knobs and put
# a different pressure on shared weights, and nothing in the output would say so.
#
# ---- REVERTED TO 'router' 2026-10-02 (run 18 cancelled -- see the block above). -------
# Everything from "CONSEQUENCE" down to here describes the 'ink' ARM and is kept verbatim
# because it is the analysis a future ink-mode queue item would need, and re-deriving it
# costs more than carrying it. It documents a mode this config no longer selects.
# 'router' is the run-9/run-14 value: it is what makes `_VS_RUN9` False on its own merits
# rather than only via DO_TRAIN=False, so the guard below is not load-bearing-by-accident.
TRAIN_SELECT_MODE = 'router'
_TRAIN_SELECT_MODES = ('router', 'negated', 'random', 'ink', 'stratified',
                       'stratified_negated')
# Checked against a literal tuple because cell 7 (which defines SELECT_MODES) has not
# run yet. Cell 11 re-checks against the REAL SELECT_MODES once it exists, so a mode
# that this tuple allows and the model does not still fails -- before the dataset
# download, and with the two lists visibly disagreeing rather than one silently winning.
assert TRAIN_SELECT_MODE in _TRAIN_SELECT_MODES, (
    f'TRAIN_SELECT_MODE={TRAIN_SELECT_MODE!r} is not one of {_TRAIN_SELECT_MODES}. '
    f'A typo here does not fail fast: the model raises on an unknown mode, but only at '
    f'the first training step, which is after Cell 6 spends ~19 min downloading data.')
# One variable at a time. Run 18 is measured against run 9, and run 9 trained at
# merge_ratio=0.0, so a non-router selection regime and merging cannot both be on --
# the run would still train, still save, still sweep 28 rows and still print a Q6
# verdict, and the run-18-vs-run-9 delta would be uninterpretable with nothing saying so.
assert TRAIN_SELECT_MODE == 'router' or TRAIN_MERGE_RATIO == 0.0, (
    f'TRAIN_SELECT_MODE={TRAIN_SELECT_MODE!r} with TRAIN_MERGE_RATIO='
    f'{TRAIN_MERGE_RATIO} changes TWO things against run 9 at once, so the resulting '
    f'checkpoint cannot attribute its delta to either. Set TRAIN_MERGE_RATIO=0.0 for '
    f'run 18, or run the merge arm separately.')
TRAIN_EPOCHS = 5
PRUNED_CKPT = os.path.join('/kaggle/working' if os.path.isdir('/kaggle/working') else '.',
                           'adaptive_donut_pruned.pt')
# Sign-fix (Run 7 follow-up): supervise the router with a FREE text proxy (patch-ink
# contrast) via BCE so it learns to rank TEXT high, instead of the blank-paper-above-text
# inversion seen after STE-only training. When True, the ablation's forward `router`
# rows should jump from broken (~18 recall) to competitive -- that is the test.
SUPERVISE_SALIENCY = True
SALIENCY_THRESHOLD = 0.15     # keep patches whose within-patch std exceeds 15% of the image max

# ---- Pending 13(b): supervise the router with the DECODER'S OWN cross-attention
# instead of patch ink. Off by default, so SUPERVISE_SALIENCY alone still reproduces
# run 9 exactly and this stays a one-variable experiment.
#
# Why a different target at all: D6 showed that fitting the INK proxy harder cost
# accuracy at two of three budgets, so ink is not merely imperfect, it is the wrong
# thing to fit. D7 then showed what ink was actually supplying -- not correctness but
# three structural properties the task loss cannot supply (dense / coherent / free),
# because the STE reaches exactly K of N tokens and hands the other N-K exactly zero
# gradient. So the fix is to keep the SHAPE of the ink term and change its CONTENT.
# D8: attention is a genuinely different target (r(attn, ink) = +0.083) and not a fixed
# positional mask. D9: it is reachable by this very scorer (held-out AUC 0.976 vs a
# 0.498 shuffled floor, and +0.212 over a constant map). Best single motivator:
# r(attn, router score) = -0.045 -- the router is not just anti-correlated with ink, it
# is UNINFORMED about where the decoder looks.
#
# NOTHING above establishes that this WORKS. Every D8/D9 number is scored against the
# teacher's own attention and is close to tautological. The acceptance criterion is
# recall at keep=0.50 and 0.35 against run 9 -- NOT retained attention mass. Promoting
# a proxy to an acceptance gate is the mistake D2's withdrawn gate already made once.
ATTN_TARGET = False

# Both pairings are asserted HERE as well as in cell 11, for the reason stated above
# RESUME_CKPT: cell 2 runs before Cell 6's ~19-minute dataset download and cell 11 does
# not, so a config mistake caught here costs a minute instead of twenty. The most likely
# run-10 mistake is exactly this one -- flip ATTN_TARGET, forget to attach the run-5
# dataset -- and note that RESUME_CKPT's auto-resolution above only fires when it is
# already truthy, so leaving it None gets no help from it.
assert not ATTN_TARGET or (RESUME_CKPT and os.path.exists(RESUME_CKPT)), (
    f'ATTN_TARGET=True needs RESUME_CKPT pointing at run 5: the teacher has to be the '
    f'checkpoint D8/D9/D10 characterised, not donut-base\\'s untuned decoder. Attach the '
    f'run-5 dataset and set RESUME_CKPT (currently {RESUME_CKPT!r}).')
assert not ATTN_TARGET or SUPERVISE_SALIENCY, (
    'ATTN_TARGET replaces the CONTENT of the saliency term, so the term has to be on. '
    'With SUPERVISE_SALIENCY=False, LAMBDA_SAL is 0 and this would be a silent no-op -- '
    'an all-STE run mislabelled as 13(b).')

# DO_TRAIN=False is only meaningful WITH a checkpoint. On the else branch,
# `if RESUME_CKPT:` is the ONLY load -- so with RESUME_CKPT=None the sweep runs
# donut-base with a RANDOMLY INITIALISED router and still prints 28 rows, a full Q1-Q6
# verdict block and a results JSON. Nothing in that output says the weights were never
# trained. That is this project's recurring failure shape (a run that looks green and
# measures nothing). Run 14 ships DO_TRAIN=True so this guard is currently DORMANT --
# it is kept, not deleted, because flipping a default back is exactly how a guard
# written for the other default gets quietly lost.
assert DO_TRAIN or RESUME_CKPT, (
    'DO_TRAIN=False means "sweep only", but RESUME_CKPT is None -- there is nothing to '
    'sweep. The router would be randomly initialised and all 28 rows would be noise that '
    'still tabulates. Attach the checkpoint dataset and set RESUME_CKPT above, or set '
    'DO_TRAIN=True to train one first.')

# Run 14's guard, and the mirror of the one above. DO_TRAIN=True with RESUME_CKPT=None is
# a perfectly valid run -- it trains from donut-base -- and that is precisely the problem:
# run 14's entire claim is "run 9's recipe plus merging", which requires starting where
# run 9 started (run 5's weights). Train from donut-base instead and the run still trains,
# still saves a checkpoint, still sweeps 28 rows and still prints a Q6 verdict, but the
# run-14-vs-run-9 comparison is void and NOTHING in the output says so. Run 9's own
# checklist said leaving this None "costs the harness control and nothing will fail" --
# true then, and the reason it must fail now.
#
# ---- EXTENDED FOR RUN 18 (2026-09-26), and this is the exact failure the comment on the
# DORMANT guard above predicts. This assert was gated on TRAIN_MERGE_RATIO > 0 alone.
# Run 18 sets TRAIN_MERGE_RATIO back to 0.0 -- so as written it would have gone SILENT on
# a run that needs run 5's weights for the identical reason run 14 did: run 18 is also
# "run 9's recipe plus one change", also measured against run 9, and also void if it
# starts from donut-base. A guard whose trigger is one run's knob expires when the next
# run flips that knob back. The condition is therefore "this run is a one-variable
# comparison against run 9", of which TRAIN_MERGE_RATIO and TRAIN_SELECT_MODE are two
# instances; add the third here rather than writing a third assert.
_VS_RUN9 = DO_TRAIN and (TRAIN_MERGE_RATIO > 0 or TRAIN_SELECT_MODE != 'router')
_VS_RUN9_WHY = ('TRAIN_MERGE_RATIO=%s (run 14)' % TRAIN_MERGE_RATIO
                if TRAIN_MERGE_RATIO > 0 else
                'TRAIN_SELECT_MODE=%r (run 18)' % TRAIN_SELECT_MODE)
assert not _VS_RUN9 or (RESUME_CKPT and os.path.exists(RESUME_CKPT)), (
    f'{_VS_RUN9_WHY} makes this a ONE-VARIABLE run measured against run 9. That '
    f'comparison needs this run to start from the SAME weights run 9 started from: '
    f'run 5\\'s adaptive_donut_funsd.pt. With RESUME_CKPT={RESUME_CKPT!r} this would '
    f'train from donut-base, confounding the variable under test with a different '
    f'initialisation, and would still produce a complete-looking 28-row table. Attach '
    f'the run-5 dataset and set RESUME_CKPT above.')

# ...and the guard above is still not enough, which run 12 proved the expensive way.
#
# Run 12's checklist named run 9's `adaptive_donut_pruned.pt`; the session attached run 5's
# `adaptive_donut_funsd.pt`. The path EXISTED, so every existence check passed, the run
# produced 28 rows and a full Q1-Q6 block, and its headline read `+36.83 MERGING WINS` --
# which was really "the run-5 router scores below its own negation". Nothing in the log said
# so. It was caught only afterwards, by the provenance stamp's `size_bytes`, which is a
# post-mortem tool: it tells you which checkpoint you measured AFTER you have spent the GPU
# time. Run 14 is a ~5-6 h run, so the same question has to be asked in cell 2 instead.
#
# What size can and cannot do, stated plainly so this is not trusted beyond its reach:
#   1045901275 = run 5's adaptive_donut_funsd.pt  (predates the pruning-era keys)
#   1045901771 = EVERY pruning-era checkpoint -- runs 7, 8, 9, 10 and 11 are byte-identical
#                in length and this check CANNOT tell them apart.
# That is enough here and only here, because run 14's requirement is exactly the coarse
# distinction size can make: start from run 5, not from anything pruning-era. For any finer
# question (run 9 vs run 11) read the provenance stamp in the results JSON -- and do not
# extend this assert to pretend otherwise.
RUN5_CKPT_BYTES = 1045901275
PRUNED_CKPT_BYTES = 1045901771
if RESUME_CKPT:
    _sz = os.path.getsize(RESUME_CKPT)
    _who = ('run 5 (pre-pruning, adaptive_donut_funsd.pt)' if _sz == RUN5_CKPT_BYTES else
            'a PRUNING-ERA checkpoint (one of runs 7/8/9/10/11 -- size cannot say which)'
            if _sz == PRUNED_CKPT_BYTES else 'UNRECOGNISED')
    print(f'CKPT IDENTITY: {_sz} bytes -> {_who}')
    assert not _VS_RUN9 or _sz == RUN5_CKPT_BYTES, (
        f'RESUME_CKPT is {_who} ({_sz} bytes), but {_VS_RUN9_WHY} must start from run 5 '
        f'({RUN5_CKPT_BYTES} bytes) or the one-variable comparison against run 9 is void. '
        f'This is run 12\\'s failure exactly: that run attached a checkpoint whose path '
        f'existed, swept 28 rows, and printed a headline that was an artifact of the wrong '
        f'weights. Fix the path, or -- if you have deliberately re-saved run 5 and the size '
        f'moved -- set RUN5_CKPT_BYTES above to the new size and say so in AGENTS.md.')

    # ---- THE EVAL-ONLY GUARD, WRITTEN 2026-10-02. ---------------------------------
    # PATCH A's own comment block (above, at the DO_TRAIN default) promised this guard --
    # "they must not merely be disabled -- they are replaced by the eval-only guard added
    # below, or T4 repeats run 12 exactly" -- and then DID NOT WRITE IT. Found by reading
    # the two asserts above against DO_TRAIN=False rather than by reading the comment:
    # both are gated on `_VS_RUN9`, which is False whenever DO_TRAIN is False, so with
    # the T4 default BOTH checkpoint-identity asserts are dormant and the only live guard
    # is `assert DO_TRAIN or RESUME_CKPT` -- which demands *a* checkpoint, never the RIGHT
    # one. Attach run 5's weights to T4 and: the path exists, the identity line prints
    # "run 5 (pre-pruning)", no assert fires, 29 rows sweep on an anti-selective router.
    # That is run 12 reproduced exactly, which is the outcome the comment predicted.
    #
    # The DIRECTION is inverted from the `_VS_RUN9` assert above, which is the whole point
    # and the reason one guard cannot serve both: run 14/18 must START from run 5
    # (pre-pruning) because they retrain; T4 must EVALUATE a pruning-era checkpoint,
    # because its pooled rows have to extend runs 13/14, and run 13 swept run 9's
    # `adaptive_donut_pruned.pt`. A single assert demanding run 5 is correct for one and
    # exactly backwards for the other.
    #
    # Size resolves precisely the distinction needed here and no finer: it separates run 5
    # from the pruning era and CANNOT tell runs 7/8/9/10/11 apart. For "is this run 9
    # rather than run 11" read the provenance stamp -- do not extend this assert to
    # pretend otherwise (the same limit the block above states).
    assert DO_TRAIN or _sz == PRUNED_CKPT_BYTES, (
        f'DO_TRAIN=False means this is an EVAL-ONLY sweep, and RESUME_CKPT is {_who} '
        f'({_sz} bytes). An eval-only sweep must run a PRUNING-ERA checkpoint '
        f'({PRUNED_CKPT_BYTES} bytes) -- T4 extends runs 13/14, which swept run 9\\'s '
        f'adaptive_donut_pruned.pt. Run 5\\'s weights are merge-naive AND pruning-naive: '
        f'run 12 attached them by mistake, every existence check passed, 28 rows swept, '
        f'and its headline `+36.83 MERGING WINS` was really "the run-5 router scores '
        f'below its own negation". Nothing in that log said so. Attach the run-9 '
        f'checkpoint dataset, or -- if you deliberately mean to sweep run 5 -- say so in '
        f'AGENTS.md and set PRUNED_CKPT_BYTES, because this assert is the only thing '
        f'between an eval-only sweep and the wrong weights.')
    print(f'EVAL-ONLY CKPT GATE: {"n/a (DO_TRAIN=True)" if DO_TRAIN else "PASS -- pruning-era weights"}')

EVAL_CKPT = RESUME_CKPT          # set by the training cell; used for clarity/logging
# One line that states every knob that shapes the run, because D5 is the standing case in
# this project of a knob (lambda_entropy=0.05) that shaped two runs while appearing nowhere
# in the log. ATTN_TARGET is the whole variable of run 10, so it goes here rather than only
# in cell 11's teacher-snapshot line.
# (The keep_ratio branch below was missing its `f` prefix through run 9, so the log read
# literally `keep_ratio={TRAIN_KEEP_RATIO}`. Harmless to the run, but it is the one line a
# reader checks the configuration against before an hour of training.)
#
# The merging clause is now CONDITIONAL. Through run 14 it read "AND merging ON
# (merge_ratio=...)" unconditionally, which was true of run 14 and is false of run 18 --
# a line whose job is to state the configuration must not assert a stage is on when the
# knob says 0.0. Same for selection: the regime is run 18's whole variable, so it goes on
# the PLAN line, not only in cell 11.
print(f'PLAN: DO_TRAIN={DO_TRAIN} -> '
      + (f'retrain router WITH pruning ON (keep_ratio={TRAIN_KEEP_RATIO}), '
         + (f'merging ON (merge_ratio={TRAIN_MERGE_RATIO})'
            if TRAIN_MERGE_RATIO > 0 else 'merging OFF')
         + f', selection={TRAIN_SELECT_MODE!r}'
         + ('' if TRAIN_SELECT_MODE == 'router' else
            ' (RUN 18: the decoder trains on an EXTERNALLY chosen kept set, so its '
            'router head gets no task gradient -- by design)')
         + ', then sweep'
         if DO_TRAIN else 'sweep only on RESUME_CKPT'))
print(f'CFG: SUPERVISE_SALIENCY={SUPERVISE_SALIENCY} ATTN_TARGET={ATTN_TARGET} '
      + ('(target = FROZEN run-5 decoder cross-attention top-K -- Pending 13(b))'
         if ATTN_TARGET else f'(target = patch ink > {SALIENCY_THRESHOLD:g} -- run 9 config)')
      + f' | TRAIN_EPOCHS={TRAIN_EPOCHS} TRAIN_MERGE_RATIO={TRAIN_MERGE_RATIO} '
      + f'TRAIN_SELECT_MODE={TRAIN_SELECT_MODE!r} '
      + f'RESUME_CKPT={"set" if RESUME_CKPT else "None"}')
'''
c2 = c2.rstrip("\n") + CFG
put(2, c2)

# ======================================================================= PATCH B
print("B. cell 9 -- build train_loader when DO_TRAIN")
c9 = src(9)
old = "if EVAL_ONLY:\n    train_ds = train_loader = funsd_train = synth_train = None"
new = ("if EVAL_ONLY and not DO_TRAIN:\n"
       "    train_ds = train_loader = funsd_train = synth_train = None")
assert c9.count(old) == 1, f"cell 9 train_loader gate: expected 1 hit, found {c9.count(old)}"
c9 = c9.replace(old, new)
# Fix a latent NameError: the else branch printed test_ds before it was defined
# (test_ds = DocumentDataset(...) sits after the if/else block). Dropping the
# forward reference; the module-level print already reports the test count.
_OLD_PRINT = "    print(f'Train samples: {len(train_ds)}, Test samples: {len(test_ds)}')"
_NEW_PRINT = "    print(f'Train samples: {len(train_ds)}')"
_hits = c9.count(_OLD_PRINT)
if _hits == 1:
    c9 = c9.replace(_OLD_PRINT, _NEW_PRINT)
elif _hits != 0:
    raise AssertionError(f"data-cell print: expected 0 or 1 hit, found {_hits}")
put(9, c9)

# ======================================================================= PATCH C
print("C. cell 11 -- DO_TRAIN branch (retrain with pruning ON)")
c11 = src(11)
assert "model = AdaptiveDonutOCR(keep_ratio=1.0" in c11, "cell 11 missing model build"

DO_TRAIN_BRANCH = '''# Cell 7: Model Training
# ---------------------------------------------------------------------------
# Pending 1a: TRAIN THE ROUTER WITH PRUNING ON
# keep_ratio<1 => K<N => the STE multiplier (1 + score - score.detach()) is no
# longer exactly 1.0, so gradient finally reaches the router head about which
# tokens to KEEP. Sparsity loss now targets the real budget. Diagnostic D2 says
# do NOT reward summed retained saliency (that ranks negated above random); this
# loss only pulls mean(score) toward TRAIN_KEEP_RATIO, a soft budget without the
# inverted incentive. Worst-case line coverage is bounded separately by Pending
# 1d's stratified selection, not by this loss.
# ---------------------------------------------------------------------------
if DO_TRAIN:
    TRAIN_KEEP_RATIO = float(TRAIN_KEEP_RATIO)
    TRAIN_MERGE_RATIO = float(TRAIN_MERGE_RATIO)
    # Run 14: merging is now IN the training graph, not just at inference. `forward()`
    # falls back to self.merge_ratio when its merge_ratio argument is None, and the
    # training loop below never passes one -- so this constructor argument is the whole
    # mechanism. It was a hardcoded 0.0 through run 13.
    #
    # Verified by execution (scripts/verify_train_with_merge.py), not by reading: the
    # router still receives gradient THROUGH the merger, and the gradient it receives
    # actually differs from the merge-off one (2.07e-04 at 0.20, 4.42e-04 at 0.40,
    # against a bit-identical re-run noise floor of 0.0). That pairing matters -- the
    # router gets gradient from the prune path whether or not the merger is
    # differentiable, so "grads are non-zero" alone would have passed on a dead end.
    model = AdaptiveDonutOCR(keep_ratio=TRAIN_KEEP_RATIO, merge_ratio=TRAIN_MERGE_RATIO,
                              freeze_encoder=True).to(device)
    # Start from run-5 weights if supplied, then retrain the routing under pruning.
    if RESUME_CKPT and os.path.exists(RESUME_CKPT):
        _sd = torch.load(RESUME_CKPT, map_location=device, weights_only=True)
        _m, _u = model.load_state_dict(_sd, strict=False)
        print(f'Resumed {RESUME_CKPT} (missing={len(_m)}, unexpected={len(_u)}) '
              f'for pruning-ON retrain')
    # Pending 13(b): snapshot a FROZEN teacher decoder for the cross-attention target.
    # Built HERE, immediately after the run-5 load and BEFORE any training step, because
    # the teacher must be run 5 -- the ceiling model D8 and D9 measured. Once the loop
    # starts, model.model.decoder is the student and drifts away from it.
    #
    # Freezing is what makes this target COHERENT, which is the property D7 identified as
    # the one ink was really supplying. An online target that moved with the student would
    # reintroduce exactly the incoherence (cos 0.21 across pages) that made
    # CE-through-STE useless despite being 8-30x larger by gradient norm.
    _teacher_dec = None
    if ATTN_TARGET:
        import copy
        assert RESUME_CKPT and os.path.exists(RESUME_CKPT), (
            'ATTN_TARGET needs RESUME_CKPT: the teacher must be the run-5 checkpoint that '
            'D8/D9 characterised. Without it the "teacher" is donut-base\\'s untuned '
            'decoder, which was never measured and is not the ceiling model.')
        assert SUPERVISE_SALIENCY, (
            'ATTN_TARGET replaces the CONTENT of the saliency term, so the term has to be '
            'on. With SUPERVISE_SALIENCY=False, LAMBDA_SAL is 0 and this would be a silent '
            'no-op -- an all-STE run mislabelled as 13(b).')
        _teacher_dec = copy.deepcopy(model.model.decoder).eval()
        for _p in _teacher_dec.parameters():
            _p.requires_grad = False
        # transformers 5.x defaults to SDPA, which does not materialise attention weights
        # and then returns cross_attentions=None rather than raising. Set eager here;
        # attn_topk_target asserts non-empty every step in case this did not take.
        for _cfg in (getattr(_teacher_dec, 'config', None),
                     getattr(getattr(_teacher_dec, 'model', None), 'config', None)):
            if _cfg is not None:
                _cfg._attn_implementation = 'eager'
                _cfg.output_attentions = True
        print('13(b): frozen teacher decoder snapshotted from run 5 (eager attention). '
              'Target = top-K of its cross-attention, NOT patch ink.')
    # Unfreeze top Swin stage (mirrors run 5) so features adapt to FUNSD glyphs.
    UNFREEZE_STAGES = 1
    _stages = model.model.encoder.encoder.layers
    for _st in _stages[-UNFREEZE_STAGES:]:
        for _p in _st.parameters():
            _p.requires_grad = True
    _fn = getattr(model.model.encoder, 'layernorm', None)
    if _fn is not None:
        for _p in _fn.parameters():
            _p.requires_grad = True
    _enc_params = [p for p in model.model.encoder.parameters() if p.requires_grad]
    trainable_params = [
        {'params': model.router.parameters(), 'lr': 1e-4},
        {'params': model.model.decoder.parameters(), 'lr': 2e-5},
        {'params': _enc_params, 'lr': 1e-5},
    ]
    optimizer = torch.optim.AdamW(trainable_params, weight_decay=0.01)
    # Sign-fix (Run 7 follow-up): the STE-only retrain kept the router sign-inverted
    # (forward router ranked blank paper above text). Supervise the scorer with a FREE
    # text proxy -- patch-ink contrast -- via BCE, so it learns to rank TEXT high.
    #
    # Every lambda_* is passed EXPLICITLY. Diagnostic D5: lambda_entropy defaulted to
    # 0.05 from AdaptivePruningLoss's signature and so shaped runs 7-8 while appearing
    # in no config cell -- an undeclared second knob. lambda_entropy is now 0.0 in the
    # supervised branch on purpose: the entropy term is -H, so minimising it MAXIMISES
    # entropy, i.e. it pushes every score back toward 0.5. Its stated job ("prevent
    # early bimodal collapse") is a stand-in for supervision, and once the ink target
    # tells each token what it should be, an anti-confidence term works directly against
    # that target -- with the D4 fix below the BCE gradient vanishes at p==t while the
    # entropy gradient does not, so entropy would become the binding constraint at
    # convergence and hold scores off 0/1 permanently. Kept at 0.05 (explicitly) in the
    # UNSUPERVISED branch, where it retains its original purpose.
    if SUPERVISE_SALIENCY:
        criterion = AdaptivePruningLoss(lambda_sparsity=0.0, lambda_entropy=0.0,
                                         target_budget=1.0,
                                         pad_token_id=processor.tokenizer.pad_token_id)
        # 2.0 was tuned against a gradient the D4 bug attenuated 10-50x. The corrected
        # loss has d(sal)/dz == p - t exactly, so the same effective pressure needs a
        # much smaller weight. 0.5 is a reasoned starting point, NOT a tuned value.
        LAMBDA_SAL = 0.5
    else:
        criterion = AdaptivePruningLoss(lambda_sparsity=2.0, lambda_entropy=0.05,
                                         target_budget=TRAIN_KEEP_RATIO,
                                         pad_token_id=processor.tokenizer.pad_token_id)
        LAMBDA_SAL = 0.0
    scaler = torch.amp.GradScaler('cuda' if device.type == 'cuda' else 'cpu')
    EPOCHS = int(TRAIN_EPOCHS)
    GRAD_ACCUM = 8
    # Cell 2 checked TRAIN_SELECT_MODE against a hardcoded tuple because SELECT_MODES did
    # not exist yet. It does now, so check against the REAL one -- the model raises on an
    # unknown mode, but only at the first training step, and the two lists disagreeing is
    # itself the thing worth reporting (it means cell 2's copy has drifted from cell 7's).
    assert TRAIN_SELECT_MODE in SELECT_MODES, (
        f'TRAIN_SELECT_MODE={TRAIN_SELECT_MODE!r} is not in SELECT_MODES={SELECT_MODES}. '
        f'Cell 2 accepted it against its own hardcoded copy of this list, so the two '
        f'have drifted -- fix cell 2s _TRAIN_SELECT_MODES, not this assert.')
    print(f'TRAINING WITH PRUNING ON: keep_ratio={TRAIN_KEEP_RATIO}, '
          f'merge_ratio={TRAIN_MERGE_RATIO}, select_mode={TRAIN_SELECT_MODE!r}, '
          f'epochs={EPOCHS}')
    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss, epoch_ce = 0.0, 0.0
        epoch_sal, epoch_gap, epoch_pm, epoch_ps, n_sal = 0.0, 0.0, 0.0, 0.0, 0
        epoch_ov, epoch_ch = 0.0, 0.0
        epoch_enc = 0
        optimizer.zero_grad()
        pbar = tqdm(train_loader, desc=f'Epoch {epoch}/{EPOCHS}')
        for step, batch in enumerate(pbar):
            pixel_values = batch['pixel_values'].to(device)
            labels = batch['labels'].to(device)
            decoder_input_ids = batch['decoder_input_ids'].to(device)
            with torch.amp.autocast('cuda' if device.type == 'cuda' else 'cpu'):
                outputs = model(pixel_values=pixel_values, labels=labels,
                                decoder_input_ids=decoder_input_ids,
                                select_mode=TRAIN_SELECT_MODE)
                # Run 18's variable, verified BY EXECUTION at step 0 rather than trusted
                # from the config line above. Two distinct failures this catches, both of
                # which otherwise produce a complete-looking 4-hour run:
                #   1. the kwarg silently not reaching the model (a forward() that still
                #      takes **kwargs, or an un-regenerated notebook). `select_mode` is
                #      echoed from INSIDE forward(), so it reports what the model used.
                #   2. the mode reaching it and changing nothing. retained_ink is the
                #      measured discriminator: patch-ink top-K maximises it by
                #      construction, so `ink` must sit at the ceiling and `router` must
                #      not. D1 measured the trained router at 0.34-0.38 against random's
                #      0.50, so these two are far apart on real pages -- if they print
                #      the same number, selection is not being overridden.
                # Telemetry, NOT an assert, on the ink branch: this is the project's
                # standing rule that a first-batch statistic must not be given a new way
                # to kill a 4-hour run (see the ink-target rate check below).
                if step == 0 and epoch == 1:
                    assert outputs.get('select_mode') == TRAIN_SELECT_MODE, (
                        f'model used select_mode={outputs.get("select_mode")!r} but '
                        f'TRAIN_SELECT_MODE is {TRAIN_SELECT_MODE!r}. The kwarg did not '
                        f'reach forward() -- regenerate the notebook.')
                    _dbg_ink = patch_ink(pixel_values, outputs['scores'].shape[1]).float()
                    _dbg_ret = float((_dbg_ink.gather(1, outputs['topk_indices']).sum(1)
                                      / (_dbg_ink.sum(1) + 1e-9)).mean())
                    print(f'  SELECTION: mode={TRAIN_SELECT_MODE!r} retains '
                          f'{_dbg_ret:.4f} of first-batch page ink '
                          f'(ink top-K is the ceiling by construction; D1 measured the '
                          f'trained router at 0.34-0.38 and random at ~0.50)')
                loss_dict = criterion(outputs['logits'], labels, outputs['scores'], outputs['loss'])
                loss = loss_dict['loss'] / GRAD_ACCUM
                if LAMBDA_SAL > 0:
                    _sc = outputs['scores']
                    if ATTN_TARGET:
                        # Pending 13(b). ONLY the target's content changes; the BCE call,
                        # LAMBDA_SAL, F1's fix and F3's telemetry below are all untouched,
                        # which is precisely what D7 asked for -- keep the shape of the ink
                        # term (dense / coherent / free) and replace what it points at.
                        _tgt = attn_topk_target(
                            _teacher_dec, outputs['visual_tokens'], decoder_input_ids,
                            labels, _sc.shape[1], TRAIN_KEEP_RATIO).to(_sc.dtype)
                    else:
                        _ink = patch_ink(pixel_values, _sc.shape[1]).to(_sc.dtype)
                        _inkn = _ink / (_ink.amax(dim=1, keepdim=True) + 1e-9)
                        _tgt = (_inkn > SALIENCY_THRESHOLD).float()
                    if step == 0 and epoch == 1:
                        # The two targets have very different positive rates, and that
                        # difference silently rescales the BCE gradient -- so print it
                        # rather than discover it in a post-mortem.
                        #
                        # The check is per-branch on purpose. `assert 0 < rate < 1` was the
                        # first version and it was wrong in both directions: far too weak
                        # for the attention branch, where top-K makes the rate exactly
                        # K/N, and too STRICT for ink, where one all-blank or all-ink first
                        # page is legal and would have killed a 4-hour run at step 0 --
                        # adding a new fatal path to the branch that already produced run 9.
                        # So: ATTN gets the exact check it can actually satisfy, INK gets
                        # loud telemetry and no new way to die.
                        _rate = float(_tgt.float().mean())
                        _K = max(1, int(round(_sc.shape[1] * TRAIN_KEEP_RATIO)))
                        if ATTN_TARGET:
                            _want = _K / _sc.shape[1]
                            print(f'  target: ATTN top-K | positive rate {_rate:.4f} '
                                  f'(expected {_want:.4f} = {_K}/{_sc.shape[1]})')
                            assert abs(_rate - _want) < 1e-4, (
                                f'attention target positive rate {_rate:.4f} != K/N '
                                f'{_want:.4f}. top-K guarantees this exactly, so a '
                                f'mismatch means the target is not the top-K mask it '
                                f'claims to be -- an all-zero target would train the '
                                f'router toward a constant and void the run.')
                        else:
                            print(f'  target: INK | positive rate {_rate:.3f} '
                                  f'(threshold {SALIENCY_THRESHOLD:g})')
                            if not 0.0 < _rate < 1.0:
                                print(f'  WARNING: first batch ink target is degenerate '
                                      f'(rate {_rate}). Legal for a blank page; if the '
                                      f'saliency loss also flatlines, suspect patch_ink.')
                    # D4: `_sc` is ALREADY a probability -- PatchSaliencyRouter.scorer
                    # ends in nn.Sigmoid() -- so passing it straight to
                    # binary_cross_entropy_with_logits squashed it twice. The loss then
                    # bottomed out at 0.31/0.69 instead of ~0 and its gradient was
                    # weakest exactly where the error was largest (50x spread; strongest
                    # on an already-correct blank patch). Recover the logit instead:
                    # bce_with_logits(logit(p), t) == bce(p, t) numerically, and gives
                    # d/dz == p - t exactly.
                    # NOT F.binary_cross_entropy(p, t): that is identical in value but
                    # is on PyTorch's autocast-unsafe list, and this block runs inside
                    # torch.amp.autocast on the T4. NOT "make the scorer return a logit"
                    # either -- D5: AdaptivePruningLoss reads the same tensor as a
                    # probability twice (mean vs target_budget; clamp(0,1) -> entropy).
                    _sal = F.binary_cross_entropy_with_logits(
                        torch.logit(_sc.squeeze(-1).clamp(1e-6, 1 - 1e-6)), _tgt)
                    loss = loss + (LAMBDA_SAL * _sal) / GRAD_ACCUM
                    # Pending 11: run 9 printed `Avg Loss 0.3091 | CE 0.3091` for five
                    # epochs, because epoch_loss accumulates loss_dict['loss'] while the
                    # saliency term is added to `loss`. The number this fix exists to
                    # move was therefore never observed in ANY run -- the log could not
                    # distinguish LAMBDA_SAL=0.5 from LAMBDA_SAL=0. Detached, so the
                    # telemetry cannot alter the gradient. One .tolist() = one device
                    # sync (the loop below already syncs 3x per step).
                    _p = _sc.detach().squeeze(-1).float()
                    # Pending 13(b): log the MECHANISM separately from the goal. `sal` is a
                    # BCE over probabilities; it can fall while the router's actual top-K
                    # SELECTION still disagrees with the teacher, and selection is the only
                    # thing that reaches the decoder. Without this column a null result
                    # cannot distinguish "the router never learned the target" from "it
                    # learned the target and recall did not improve anyway" -- which is
                    # exactly the ambiguity D6 left behind. `ov` is the fraction of the
                    # target's positives that the router's own top-K keeps, so it is
                    # comparable across both targets and against run 9.
                    # `ch` is what a RANDOM top-K would score (= the target's positive
                    # rate): ov must be read as lift over ch, not as an absolute.
                    _tgf = _tgt.float()
                    _rk = torch.zeros_like(_p)
                    _rk.scatter_(1, _p.topk(max(1, int(round(
                        _p.shape[1] * TRAIN_KEEP_RATIO))), dim=1).indices, 1.0)
                    _st = torch.stack([_sal.detach().float(),
                                       (_p - _tgf).abs().mean(),
                                       _p.mean(), _p.std(),
                                       (_rk * _tgf).sum() / _tgf.sum().clamp_min(1.0),
                                       _tgf.mean()]).tolist()
                    epoch_sal += _st[0]
                    epoch_gap += _st[1]
                    epoch_pm += _st[2]
                    epoch_ps += _st[3]
                    epoch_ov += _st[4]
                    epoch_ch += _st[5]
                    n_sal += 1
            scaler.scale(loss).backward()
            if (step + 1) % GRAD_ACCUM == 0 or (step + 1) == len(train_loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
            epoch_loss += loss_dict['loss'].item()
            epoch_ce += loss_dict['ce_loss'].item()
            epoch_enc += int(outputs['compressed_tokens'])
            pbar.set_postfix({'Loss': f'{loss_dict["loss"].item():.3f}',
                              'Tokens': f'{outputs["compressed_tokens"]}/{outputs["original_tokens"]}'})
        # Every column here is present because a specific past failure was invisible
        # without it. Obj is what backward() minimises (Pending 11 -- no printed number
        # was). aux is lambda_sparsity+lambda_entropy's contribution: D5 found
        # lambda_entropy=0.05 defaulting in and shaping runs 7-8 while appearing in no
        # config cell, so a nonzero aux now says so the epoch it happens. sal carries
        # LAMBDA_SAL and the step count, so the knob AND the fact that the branch fired
        # are both in the log. dev is mean |p - t|, which after the D4 fix IS the
        # gradient magnitude (d(sal)/dz == p - t), separating "loss is low" from "router
        # agrees with the target". p's std going to 0 is constant-collapse, which makes
        # torch.topk silently return the first K indices -- structured-looking output
        # that is not learned at all.
        #
        # `enc` is run 14's column, and it is here for the same reason as `aux`. Run 14's
        # ONE variable is TRAIN_MERGE_RATIO, and until this line the training loop
        # reported no evidence that merging occurred: `ch` is the STE's kept FRACTION
        # (0.500 at keep=0.50 whether or not the merger ran), and the merged length
        # appeared only in a tqdm postfix that a saved notebook keeps for one line of one
        # bar. So a run in which the constructor argument failed to reach the merger --
        # this project's recurring failure shape, and the exact thing
        # scripts/verify_train_with_merge.py had to prove by execution rather than by
        # reading -- would have produced a log indistinguishable from a correct one.
        # `enc` is what the decoder actually received, averaged over the epoch's steps:
        # 2400 means merging did not happen, 1440 means it did at merge_ratio=0.40.
        _n = len(train_loader)
        _obj = (epoch_loss + LAMBDA_SAL * epoch_sal) / _n
        _aux = (epoch_loss - epoch_ce) / _n
        if n_sal:
            _sal_msg = (f'sal {epoch_sal/n_sal:.4f} x{LAMBDA_SAL:g} [{n_sal}/{_n}] | '
                        f'dev {epoch_gap/n_sal:.4f} | '
                        f'p {epoch_pm/n_sal:.3f}+-{epoch_ps/n_sal:.3f} | '
                        f'ov {epoch_ov/n_sal:.3f} ch {epoch_ch/n_sal:.3f} '
                        f'lift {epoch_ov/n_sal - epoch_ch/n_sal:+.3f}')
        else:
            _sal_msg = f'sal OFF (LAMBDA_SAL={LAMBDA_SAL:g})'
        print(f'Epoch {epoch} | Obj {_obj:.4f} | CE {epoch_ce/_n:.4f} | '
              f'aux {_aux:.4f} | enc {epoch_enc/_n:.0f} | {_sal_msg}')
    os.makedirs('/kaggle/working/checkpoints', exist_ok=True)
    torch.save(model.state_dict(), PRUNED_CKPT)
    print(f'SAVED pruning-ON checkpoint -> {PRUNED_CKPT}')
    EVAL_CKPT = PRUNED_CKPT
else:
'''

# Wrap the original cell 11 body as the `else` branch.
c11_new = DO_TRAIN_BRANCH + indent(c11).rstrip("\n") + "\n    EVAL_CKPT = RESUME_CKPT\n"
put(11, c11_new)

# ======================================================================= PATCH D
print("D. cell 7 -- attn_topk_target helper + expose pre-prune visual_tokens")
c7 = src(7)
assert "def stratified_scores(" in c7, "cell 7 missing stratified_scores"

ATTN_HELPER = '''

def attn_topk_target(teacher_decoder, visual_tokens, decoder_input_ids, labels,
                     num_tokens, keep_ratio):
    """Dense binary target from a FROZEN teacher decoder's cross-attention -> (B, N).

    Pending 13(b). patch_ink is a proxy for "there is text here"; this is a proxy for
    "the decoder actually looks here". D8 measured those to be DIFFERENT targets
    (r(attn, ink) = +0.083, and attention is not a fixed positional mask: its top-5%
    centroid moves 6.12 grid rows across pages where ink's moves 1.81). D9 measured this
    target to be reachable by this very scorer (held-out AUC 0.976 against a 0.498
    shuffled floor, and +0.212 over the best page-INDEPENDENT constant map).

    Computed on the fly rather than cached, which is NOT the obvious choice -- the target
    is a function of (image, text) and both are fixed per example, so caching looks free.
    It is not: funsd_train is built with augment=True and repeated FUNSD_REPEAT times, so
    each page is drawn 8 times under a fresh random DOC_AUG (+-2 deg rotation, 0.9-1.05
    scale). This target is a POSITIONAL label on an 80x60 grid, so a cached one would sit
    1-4 grid cells off the content it labels -- the same order as the text lines being
    labelled -- while patch_ink, computed from the same augmented pixel_values, stays
    perfectly aligned. That asymmetry would bias the experiment AGAINST this target for a
    reason unrelated to its quality. See AGENTS.md Pending 13.

    Attends over the FULL num_tokens visual tokens, never the student's pruned K. That is
    the entire point of a dense target: D7 measured the STE handing exactly zero gradient
    to the N-K dropped tokens (2400 of 4800 at keep=0.50), so a target defined only on the
    kept set could not reach the half that needs teaching.
    """
    if visual_tokens.shape[1] != num_tokens:
        raise ValueError(
            f'teacher must attend over the FULL grid: got {visual_tokens.shape[1]} '
            f'visual tokens but the router scored {num_tokens}. Passing the PRUNED '
            f'tokens here would silently produce a target defined only on the kept set.')
    # Pads carry attention mass too, and decoder_input_ids is padded to 512 while a real
    # FUNSD target is ~310 tokens -- so ~40% of the text positions would contribute noise
    # to every token's score. Mask them, and truncate to the longest real prefix in the
    # batch, which also shrinks the (B, heads, T, N) attention tensor by the same ~40%.
    # (D8/D9 did not need this: they tokenized without padding.)
    mask = None
    ids = decoder_input_ids
    if labels is not None:
        mask = (labels != -100)
        t_real = max(1, int(mask.sum(dim=1).max().item()))
        ids, mask = ids[:, :t_real], mask[:, :t_real].to(visual_tokens.dtype)
    with torch.no_grad():
        out = teacher_decoder(input_ids=ids,
                             encoder_hidden_states=visual_tokens.detach(),
                             output_attentions=True, return_dict=True)
        ca = getattr(out, 'cross_attentions', None)
        # transformers 5.x defaults to SDPA, which does not materialise attention weights
        # and returns None here INSTEAD OF RAISING. The target would then be all-zero and
        # would train perfectly quietly, so this is checked every step rather than trusted.
        if not ca or ca[0] is None:
            raise RuntimeError(
                'teacher decoder returned no cross_attentions -- attention weights are '
                'not being materialised (SDPA/flash). The target would be silently '
                "all-zero. Fix: config._attn_implementation = 'eager' on the teacher.")
        # Mean over heads, sum over text positions, mean over layers. Mean over layers is
        # deliberate and is a LIVE UNTESTED KNOB: D8 found the deepest layer both the most
        # ink-aligned (r +0.201 vs +0.083 for the mean) and the most page-varying, so a
        # per-layer choice may well be better. The mean is used because it is the
        # aggregation whose properties D8 and D9 actually measured.
        acc = None
        for a in ca:
            w = a.mean(dim=1)                                    # (B, T, N)
            if mask is not None:
                w = w * mask[:, :w.shape[1], None]
            s = w.sum(dim=1)                                     # (B, N)
            acc = s if acc is None else acc + s
        attn = (acc / len(ca)).float()
    K = max(1, int(round(num_tokens * keep_ratio)))
    tgt = torch.zeros_like(attn)
    tgt.scatter_(1, attn.topk(K, dim=1).indices, 1.0)
    return tgt


def stratified_scores('''
assert c7.count("\n\ndef stratified_scores(") == 1, "stratified_scores anchor not unique"
c7 = c7.replace("\n\ndef stratified_scores(", ATTN_HELPER, 1)

# Expose the PRE-PRUNE encoder features so the teacher can attend over all N tokens.
# Additive key; every existing reader indexes by name, so nothing else changes.
_OLD_RET = ("        return {\n"
            "            'loss': loss,\n"
            "            'logits': logits,\n"
            "            'scores': scores,\n")
_NEW_RET = ("        return {\n"
            "            'loss': loss,\n"
            "            'logits': logits,\n"
            "            'scores': scores,\n"
            "            'visual_tokens': visual_tokens,\n")
assert c7.count(_OLD_RET) == 1, (
    f"forward() return dict: expected 1 hit, found {c7.count(_OLD_RET)}")
c7 = c7.replace(_OLD_RET, _NEW_RET)
put(7, c7)

# ======================================================================= PATCH E
# The notebook carries its own copy of the merger, and it is the PRE-FIX one:
#   idx_A = torch.arange(0, K, 2)   /   idx_B = torch.arange(1, K, 2)
# The router hands tokens over via torch.topk(..., sorted=True), i.e. in DESCENDING
# SCORE ORDER, so a token's index in that sequence means "rank", not "place on the
# page". That split therefore partitions by score-rank parity: measured, it strands
# 49.2% of horizontally-adjacent and 50.5% of vertically-adjacent redundant pairs in
# the SAME set, where ToMe's A->B merge can never reach them. It produces a perfectly
# plausible merged tensor the whole time, which is why nothing caught it.
# src/tome.py replaces it with a checkerboard over ORIGINAL raster position.
print("E. cell 4 -- real BipartiteTokenMerger (checkerboard split) from src/tome.py")

_tome_file = read_from_src("src/tome.py")
_tome_anchor = "def checkerboard_color("
assert _tome_anchor in _tome_file, "src/tome.py no longer defines checkerboard_color"
TOME_BODY = _tome_file[_tome_file.index(_tome_anchor):].rstrip("\n")

# src/tome.py's own header (torch / nn / F / typing) is dropped -- cell 2 already
# imports torch, nn and F, and PATCH E1 below adds typing there. If src/tome.py ever
# grows an import BELOW checkerboard_color, this slice would silently drop it.
assert not any(ln.startswith(("import ", "from ")) for ln in TOME_BODY.splitlines()), (
    "src/tome.py has a top-level import below checkerboard_color; the splice would "
    "drop it and the notebook would fail at cell-run time")
# Guard that we are splicing the FIXED merger, not some other revision of it.
assert "checkerboard_color(orig_idx, grid_w)" in TOME_BODY, (
    "spliced merger does not call checkerboard_color(orig_idx, grid_w) -- is "
    "src/tome.py still the checkerboard version?")

# -- E1: typing into cell 2, the notebook's own import cell -------------------
# src/tome.py annotates its signature (Tuple / Optional / Sequence) and those
# annotations are evaluated when the `def` executes, so a missing import is a
# NameError the moment cell 4 runs -- not a deferred one. Cell 2 rather than cell 4
# because PATCH F splices `-> Tuple[int, int]` into cell 7 as well, and one import in
# the cell whose job is imports beats two copies in the cells that happen to need it.
c2b = src(2)
_IMP_ANCHOR = "from transformers.modeling_outputs import BaseModelOutput\n"
assert c2b.count(_IMP_ANCHOR) == 1, (
    f"cell 2 import anchor: expected 1 hit, found {c2b.count(_IMP_ANCHOR)}")
c2b = c2b.replace(
    _IMP_ANCHOR,
    _IMP_ANCHOR + "from typing import Tuple, Optional, Sequence\n", 1)
put(2, c2b)

# -- E2: swap the merger -------------------------------------------------------
c4 = src(4)
_MERGER_HEAD = "class BipartiteTokenMerger(nn.Module):\n"
assert c4.count(_MERGER_HEAD) == 1, (
    f"cell 4 merger anchor: expected 1 hit, found {c4.count(_MERGER_HEAD)}")

# Assert on the OLD, BROKEN text. This is a live guard, not decoration: if anyone
# ever ports the fix into the canonical notebook directly, this generator would
# otherwise splice a correct merger over an already-correct one and say nothing --
# and the next reader would have no way to tell which copy actually ran.
for _broken in ("idx_A = torch.arange(0, K, 2, device=tokens.device)",
                "idx_B = torch.arange(1, K, 2, device=tokens.device)"):
    assert c4.count(_broken) == 1, (
        f"expected the OLD rank-parity split line {_broken!r} exactly once in cell 4, "
        f"found {c4.count(_broken)}. Has {SRC} already been fixed independently? "
        f"Reconcile the two copies before regenerating.")

# This patch replaces cell 4 from `class BipartiteTokenMerger` to END OF CELL, so it
# must in fact be the last statement there or the replacement eats its successor.
_cut4 = c4.index(_MERGER_HEAD)
assert c4[_cut4:].rstrip().endswith("return out_tokens, out_coords"), (
    "the old merger is no longer the last statement in cell 4; this patch would "
    "delete whatever now follows it")
c4 = c4[:_cut4].rstrip("\n") + "\n\n\n" + TOME_BODY + "\n"
put(4, c4)
print(f"   spliced {len(TOME_BODY.splitlines())} lines from src/tome.py "
      f"(checkerboard_color + BipartiteTokenMerger)")

# ======================================================================= PATCH F
print("F. cell 7 -- _token_grid/_tome_partition, both merger call sites, tome_split")
c7 = src(7)

# -- F1: the merger now needs the token grid, so give the model a way to get it --
TOKEN_GRID_METHOD = read_method("src/model.py", "_token_grid")
assert "TOKEN_GRID" in TOKEN_GRID_METHOD, (
    "src/model.py:_token_grid no longer references TOKEN_GRID; cell 7 defines that "
    "constant and the spliced method is expected to quote it in its error message")

TOME_PARTITION_METHOD = '''    def _tome_partition(self, pixel_values, num_tokens, topk_indices, merge_ratio,
                        tome_split='checkerboard'):
        """(orig_idx, token_grid) for ToMe's A/B split, or (None, None) when off.

        checkerboard -- the shipped behaviour. Colour comes from each token's
            ORIGINAL raster position (`topk_indices`), so the split does not depend
            on the descending-score order the router delivers tokens in.
        rank_parity -- the NEGATIVE CONTROL, and the only reason this argument
            exists. grid_w=1 makes ((i // 1) + (i % 1)) % 2 == i % 2, so a sequential
            orig_idx reproduces the pre-2026-09-14 `arange(0, K, 2)` /
            `arange(1, K, 2)` split EXACTLY -- bit for bit, with no change to the
            merger and no fallback path inside it. The checkerboard fix has so far
            only been shown to move a synthetic missed-redundancy percentage
            (49.2%/50.5% -> 0.0%/0.0%, scripts/diagnose_tome_parity.py); nobody has
            shown it moves RECALL. This arm is what lets a real number say so.

        Resolved only when merging is actually on, so a non-standard input still
        runs fine at merge_ratio=0.
        """
        if merge_ratio <= 0.0:
            return None, None
        if tome_split == 'checkerboard':
            return topk_indices, self._token_grid(pixel_values, num_tokens)
        if tome_split == 'rank_parity':
            B_, K_ = topk_indices.shape
            seq = torch.arange(K_, device=topk_indices.device).unsqueeze(0).expand(B_, K_)
            return seq, (K_, 1)
        raise ValueError(
            f"tome_split must be 'checkerboard' or 'rank_parity', got {tome_split!r}")'''

_FWD = "    def forward(self, pixel_values,"
assert c7.count(_FWD) == 1, (
    f"cell 7 forward() anchor: expected 1 hit, found {c7.count(_FWD)}")
_cutf = c7.index(_FWD)
c7 = (c7[:_cutf] + TOKEN_GRID_METHOD + "\n\n" + TOME_PARTITION_METHOD + "\n\n"
      + c7[_cutf:])

# -- F2: TOME_SPLITS constant, next to SELECT_MODES -----------------------------
_MODES = ("SELECT_MODES = ('router', 'negated', 'random', 'ink', 'stratified', "
          "'stratified_negated')\n")
assert c7.count(_MODES) == 1, "SELECT_MODES anchor not unique"
c7 = c7.replace(_MODES, _MODES + "TOME_SPLITS = ('checkerboard', 'rank_parity')\n", 1)

# -- F3: generate() gains tome_split ------------------------------------------
_GEN_SIG = ("                 keep_ratio=None, merge_ratio=None, select_mode='router', "
            "**kwargs):\n")
assert c7.count(_GEN_SIG) == 1, (
    f"generate() signature anchor: expected 1 hit, found {c7.count(_GEN_SIG)}")
c7 = c7.replace(
    _GEN_SIG,
    "                 keep_ratio=None, merge_ratio=None, select_mode='router',\n"
    "                 tome_split='checkerboard', **kwargs):\n", 1)

_OLD_VALID = ("        if select_mode not in SELECT_MODES:\n"
              "            raise ValueError(f'select_mode must be one of {SELECT_MODES}, "
              "got {select_mode!r}')\n")
assert c7.count(_OLD_VALID) == 1, (
    f"select_mode validation anchor: expected 1 hit, found {c7.count(_OLD_VALID)}")
c7 = c7.replace(_OLD_VALID, _OLD_VALID + (
    "        # Validated HERE and not only inside _tome_partition, which returns early\n"
    "        # when merge_ratio == 0: a typo'd split would otherwise pass silently on\n"
    "        # every prune-only row and then surface as a merge row that looks like it\n"
    "        # ran the arm its label names.\n"
    "        if tome_split not in TOME_SPLITS:\n"
    "            raise ValueError(f'tome_split must be one of {TOME_SPLITS}, "
    "got {tome_split!r}')\n"), 1)

# -- F4: rewire both merger call sites ----------------------------------------
# The two sites are byte-identical, so generate()'s is located by its PRECEDING
# router call (use_ste=False + select_scores + invert, unique to generate) and
# rewritten first; forward()'s is then the only remaining occurrence.
OLD_CALL = ("        compressed_tokens, _ = self.tome_merger(\n"
            "            selected_tokens, merge_ratio=m_ratio, coords=pruned_coords\n"
            "        )\n")
assert c7.count(OLD_CALL) == 2, (
    f"merger call site: expected 2 byte-identical hits (forward + generate), found "
    f"{c7.count(OLD_CALL)}")
_GEN_ROUTER = "            visual_tokens, keep_ratio=k_ratio, coords=coords, use_ste=False,\n"
assert c7.count(_GEN_ROUTER) == 1, "generate()'s router call is not a unique anchor"
_gpos = c7.index(_GEN_ROUTER)
assert c7.index(OLD_CALL) < _gpos, (
    "expected forward()'s merger call to precede generate()'s router call; cell 7 has "
    "been reordered and this patch's site identification is no longer sound")

_NEW_CALL_TAIL = ("        compressed_tokens, _ = self.tome_merger(\n"
                  "            selected_tokens, merge_ratio=m_ratio, coords=pruned_coords,\n"
                  "            orig_idx=tome_orig_idx, token_grid=tome_grid\n"
                  "        )\n")
NEW_CALL_GENERATE = ("        tome_orig_idx, tome_grid = self._tome_partition(\n"
                     "            pixel_values, N, topk_indices, m_ratio, "
                     "tome_split=tome_split)\n") + _NEW_CALL_TAIL
NEW_CALL_FORWARD = (
    "        # `topk_indices` is not optional. The router returns tokens sorted by\n"
    "        # DESCENDING SCORE, so a token's position in `selected_tokens` says nothing\n"
    "        # about where it sits on the page; ToMe splits A/B by the checkerboard\n"
    "        # colour of the ORIGINAL raster position, which is what topk_indices carries.\n"
    "        tome_orig_idx, tome_grid = self._tome_partition(\n"
    "            pixel_values, N, topk_indices, m_ratio)\n") + _NEW_CALL_TAIL

_gcall = c7.index(OLD_CALL, _gpos)
c7 = c7[:_gcall] + NEW_CALL_GENERATE + c7[_gcall + len(OLD_CALL):]
assert c7.count(OLD_CALL) == 1, (
    "after rewriting generate()'s call site exactly one (forward's) should remain, "
    f"found {c7.count(OLD_CALL)}")
c7 = c7.replace(OLD_CALL, NEW_CALL_FORWARD, 1)

# -- F5: record the knobs in generate()'s meta --------------------------------
# D5: `lambda_entropy=0.05` shaped two runs while appearing nowhere in either log.
# merge_ratio and tome_split are exactly that kind of knob, so they are stamped into
# every meta dict the eval cells read. tome_split is reported as None when merging is
# off, because recording 'checkerboard' for a row that never merged would assert a
# split was used when none was.
_OLD_META = "            'select_mode': select_mode,\n"
assert c7.count(_OLD_META) == 1, (
    f"generate() meta anchor: expected 1 hit, found {c7.count(_OLD_META)}")
c7 = c7.replace(_OLD_META, _OLD_META + (
    "            'merge_ratio': m_ratio,\n"
    "            'tome_split': tome_split if m_ratio > 0.0 else None,\n"), 1)

# -- F6: class default merge_ratio 0.20 -> 0.0 --------------------------------
# Same change as src/model.py. Both construction sites in this notebook pass
# merge_ratio explicitly, so this is latent rather than active -- but a default that
# turns an EXPERIMENT on for any caller who forgets to mention it is how
# results/nrns_rp_sweep.json came to be a merged sweep that reads as a pruning-free
# one. Merging has to be asked for.
_OLD_INIT = ("    def __init__(self, base_model_name='naver-clova-ix/donut-base', "
             "keep_ratio=0.35, merge_ratio=0.20, freeze_encoder=True):\n")
assert c7.count(_OLD_INIT) == 1, (
    f"AdaptiveDonutOCR.__init__ anchor: expected 1 hit, found {c7.count(_OLD_INIT)}")
c7 = c7.replace(_OLD_INIT, _OLD_INIT.replace("merge_ratio=0.20", "merge_ratio=0.0"), 1)
put(7, c7)

# ======================================================================= PATCH G
print("G. cell 15 -- token-matched merge rows + Q6 verdict")
c15 = src(15)

# -- G1: the new rows. The existing 15-row literal is left untouched: those rows
# produced published numbers and retyping them is pure risk for zero gain.
_CFG_END = "    ('keep=0.35 strat NEGATED',  0.35, 'stratified_negated'),\n]\n"
assert c15.count(_CFG_END) == 1, (
    f"SELECTION_CONFIGS terminator: expected 1 hit, found {c15.count(_CFG_END)}")
MERGE_BLOCK = '''
# ---------------------------------------------------------------- MERGE ROWS (1e)
# The four-stage architecture (frozen Swin -> router prune -> ToMe merge -> decoder)
# running whole for the first time on a recorded result. Every previous run is
# prune-only at merge_ratio=0.0.
#
# Each merge row is paired with a PRUNE-ONLY TWIN at the identical final token count
# M, because "merging costs N points" is uninterpretable on its own: a merge row
# spends fewer tokens than its keep_ratio suggests, so an unpaired comparison charges
# merging for a budget cut. With M held fixed the question becomes answerable and
# bounded -- is merging to M cheaper in accuracy than pruning to the same M?
#
#   K = max(1, round(4800 * keep)),  r = min(round(K * merge), K // 2),  M = K - r
#
#   keep 1.00 m 0.20 -> K 4800  r 960  M 3840   == keep 0.80 prune-only
#   keep 0.50 m 0.20 -> K 2400  r 480  M 1920   == keep 0.40 prune-only
#   keep 0.35 m 0.20 -> K 1680  r 336  M 1344   == keep 0.28 prune-only
#   keep 0.50 m 0.40 -> K 2400  r 960  M 1440   == keep 0.30 prune-only
#
# BOTH router and ink arms, deliberately. The router is the known-weak selector -- it
# sits between the random floor and the ink ceiling -- so if merging only looks bad
# under the router we cannot separate "merging is destructive" from "the router's kept
# set is already so degraded that any further compression finishes it off". The ink
# pair is the clean mechanism test; the router pair is the deployed-system test.
#
# Ordering is not cosmetic: the JSON is rewritten after EVERY row, so pairing each
# merge row with its twin immediately means a session that dies mid-sweep leaves whole
# PAIRS behind. A merge row whose twin never ran answers nothing.
MERGE_CONFIGS = [
    # label                      keep  mode      merge  split
    ('keep=1.00 m=0.20 router',  1.00, 'router', 0.20, 'checkerboard'),
    ('keep=0.80 router TWIN',    0.80, 'router', 0.00, 'checkerboard'),
    ('keep=0.50 m=0.20 router',  0.50, 'router', 0.20, 'checkerboard'),
    ('keep=0.40 router TWIN',    0.40, 'router', 0.00, 'checkerboard'),
    ('keep=0.35 m=0.20 router',  0.35, 'router', 0.20, 'checkerboard'),
    ('keep=0.28 router TWIN',    0.28, 'router', 0.00, 'checkerboard'),
    ('keep=0.50 m=0.40 router',  0.50, 'router', 0.40, 'checkerboard'),
    ('keep=0.30 router TWIN',    0.30, 'router', 0.00, 'checkerboard'),
    ('keep=0.50 m=0.20 ink',     0.50, 'ink',    0.20, 'checkerboard'),
    ('keep=0.40 ink TWIN',       0.40, 'ink',    0.00, 'checkerboard'),
    ('keep=0.35 m=0.20 ink',     0.35, 'ink',    0.20, 'checkerboard'),
    ('keep=0.28 ink TWIN',       0.28, 'ink',    0.00, 'checkerboard'),
    # SABOTAGE / negative control, last: its comparison partner is the
    # keep=0.50 m=0.20 checkerboard row above, which by here has already run.
    # rank_parity reproduces the pre-2026-09-14 split exactly (grid_w=1 collapses the
    # checkerboard to sequence-position parity), at the same M and the same weights.
    ('keep=0.50 m=0.20 RANKPAR', 0.50, 'router', 0.20, 'rank_parity'),
]

# The 15 published selection rows are all prune-only and all checkerboard-by-default,
# so they widen to 5-tuples mechanically rather than being retyped.
ALL_CONFIGS = ([(n, k, m, 0.0, 'checkerboard') for n, k, m in SELECTION_CONFIGS]
               + MERGE_CONFIGS)

# (label, MERGE row key, PRUNE twin key). Keys are (keep, mode, merge, split) and
# (keep, mode) respectively; declared here beside the table above so the Q6 verdict
# and the row list cannot drift apart.
MERGE_PAIRS = [
    ('keep1.00 m0.20 vs keep0.80', (1.00, 'router', 0.20, 'checkerboard'), (0.80, 'router')),
    ('keep0.50 m0.20 vs keep0.40', (0.50, 'router', 0.20, 'checkerboard'), (0.40, 'router')),
    ('keep0.35 m0.20 vs keep0.28', (0.35, 'router', 0.20, 'checkerboard'), (0.28, 'router')),
    ('keep0.50 m0.40 vs keep0.30', (0.50, 'router', 0.40, 'checkerboard'), (0.30, 'router')),
    ('ink keep0.50 m0.20 vs 0.40', (0.50, 'ink', 0.20, 'checkerboard'), (0.40, 'ink')),
    ('ink keep0.35 m0.20 vs 0.28', (0.35, 'ink', 0.20, 'checkerboard'), (0.28, 'ink')),
]
SABOTAGE_PAIR = ('checkerboard vs rank_parity',
                 (0.50, 'router', 0.20, 'checkerboard'),
                 (0.50, 'router', 0.20, 'rank_parity'))

# Predicted M for every new row, from the arithmetic in the comment above. Checked
# against what ACTUALLY ran, because "the two rows of a pair agree on M" would still
# pass if both were wrong in the same way -- a processor change that altered N, say.
EXPECTED_M = {
    (1.00, 'router', 0.20, 'checkerboard'): 3840,
    (0.80, 'router', 0.00, 'checkerboard'): 3840,
    (0.50, 'router', 0.20, 'checkerboard'): 1920,
    (0.40, 'router', 0.00, 'checkerboard'): 1920,
    (0.35, 'router', 0.20, 'checkerboard'): 1344,
    (0.28, 'router', 0.00, 'checkerboard'): 1344,
    (0.50, 'router', 0.40, 'checkerboard'): 1440,
    (0.30, 'router', 0.00, 'checkerboard'): 1440,
    (0.50, 'ink', 0.20, 'checkerboard'): 1920,
    (0.40, 'ink', 0.00, 'checkerboard'): 1920,
    (0.35, 'ink', 0.20, 'checkerboard'): 1344,
    (0.28, 'ink', 0.00, 'checkerboard'): 1344,
    (0.50, 'router', 0.20, 'rank_parity'): 1920,
}
'''
c15 = c15.replace(_CFG_END, _CFG_END + MERGE_BLOCK, 1)

# -- G2: thread merge_ratio / tome_split through the eval function ------------
_OLD_DEF = "def run_selection_eval(label, keep_ratio, select_mode):\n"
assert c15.count(_OLD_DEF) == 1, (
    f"run_selection_eval def: expected 1 hit, found {c15.count(_OLD_DEF)}")
c15 = c15.replace(_OLD_DEF, (
    "def run_selection_eval(label, keep_ratio, select_mode, merge_ratio=0.0,\n"
    "                       tome_split='checkerboard'):\n"), 1)

_OLD_GEN = ("            gen_ids, meta = model.generate(\n"
            "                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,\n"
            "                merge_ratio=0.0, max_length=SELECTION_MAX_LEN, "
            "select_mode=select_mode\n"
            "            )\n")
assert c15.count(_OLD_GEN) == 1, (
    f"run_selection_eval generate() call: expected 1 hit, found {c15.count(_OLD_GEN)}")
c15 = c15.replace(_OLD_GEN, (
    "            gen_ids, meta = model.generate(\n"
    "                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,\n"
    "                merge_ratio=merge_ratio, max_length=SELECTION_MAX_LEN,\n"
    "                select_mode=select_mode, tome_split=tome_split\n"
    "            )\n"), 1)

# -- G3: per-image token count -------------------------------------------------
# `kept_tokens` is assigned inside the image loop, so the aggregate 'visual_tokens'
# field reports only the LAST image's M. Fine as a display value, useless as evidence:
# the entire token-matched claim is that two rows spent the same M on the same 50
# pages, and that has to be checked per image or it is an assumption.
_OLD_PI = ("        per_image.append({\n"
           "            'i': i,\n"
           "            'recall': float(r),\n")
assert c15.count(_OLD_PI) == 1, (
    f"per_image.append anchor: expected 1 hit, found {c15.count(_OLD_PI)}")
c15 = c15.replace(_OLD_PI, ("        per_image.append({\n"
                            "            'i': i,\n"
                            "            'tokens': int(meta['compressed_tokens']),\n"
                            "            'recall': float(r),\n"), 1)

# -- G3b: per-image word_order -------------------------------------------------
# Run 14's four-metric table had to print "-" for word_order because `per_image`
# stored only `recall` and `ned`, so the one metric that disagreed with the primary
# could not be bootstrapped. `o` is already in scope here -- it is the second return
# of compute_word_metrics, two lines above the append -- so the aggregate
# 'word_order_pct' was being computed from a per-image quantity that was then thrown
# away. This stores it.
#
# NOT stored: char_acc. It is `(1 - mean(ned)) * 100` exactly, and `ned` is already
# per-image, so charAcc is an affine transform of a stored array and was always
# bootstrappable -- verified to 2.1e-14 across all 28 rows of run 14. Duplicating it
# would create two numbers that can drift apart. verify_tome_merge_port.py asserts
# the identity instead, which is the part that can actually rot.
_OLD_PI2 = ("            'tokens': int(meta['compressed_tokens']),\n"
            "            'recall': float(r),\n")
assert c15.count(_OLD_PI2) == 1, (
    f"word_order anchor: expected 1 hit, found {c15.count(_OLD_PI2)}")
c15 = c15.replace(_OLD_PI2, (
    "            'tokens': int(meta['compressed_tokens']),\n"
    "            'recall': float(r),\n"
    "            'word_order': float(o),\n"), 1)

_OLD_AGG = ("    n = max(len(recs), 1)\n"
            "    mp, mg = float(np.mean(pred_words)), float(np.mean(gold_words))\n")
assert c15.count(_OLD_AGG) == 1, (
    f"aggregate block anchor: expected 1 hit, found {c15.count(_OLD_AGG)}")
c15 = c15.replace(_OLD_AGG, _OLD_AGG + (
    "    # Every distinct M this row actually produced. 'visual_tokens' below is the\n"
    "    # last image's value and is kept as-is so the published rows stay comparable;\n"
    "    # this is the field that makes a non-constant M visible instead of hidden.\n"
    "    tok_distinct = sorted({p['tokens'] for p in per_image})\n"), 1)

_OLD_ROW = ("        'select_mode': select_mode,\n"
            "        'visual_tokens': kept_tokens,\n")
assert c15.count(_OLD_ROW) == 1, (
    f"row dict anchor: expected 1 hit, found {c15.count(_OLD_ROW)}")
c15 = c15.replace(_OLD_ROW, ("        'select_mode': select_mode,\n"
                             "        'merge_ratio': merge_ratio,\n"
                             "        'tome_split': tome_split,\n"
                             "        'visual_tokens': kept_tokens,\n"
                             "        'visual_tokens_distinct': tok_distinct,\n"), 1)

# -- G4: run all 28 rows -------------------------------------------------------
_OLD_LOOP = ("for _name, _kr, _mode in SELECTION_CONFIGS:\n"
             "    print(f'--- {_name}')\n"
             "    rows.append(run_selection_eval(_name, _kr, _mode))\n")
assert c15.count(_OLD_LOOP) == 1, (
    f"sweep loop anchor: expected 1 hit, found {c15.count(_OLD_LOOP)}")
c15 = c15.replace(_OLD_LOOP, (
    "for _name, _kr, _mode, _mr, _split in ALL_CONFIGS:\n"
    "    print(f'--- {_name}')\n"
    "    rows.append(run_selection_eval(_name, _kr, _mode, _mr, _split))\n"), 1)

# -- G5: keep `by` pointing at the PRUNE-ONLY rows ----------------------------
# This was `{(keep_ratio, select_mode): r for r in rows}` over every row. Harmless
# while every row had merge_ratio=0.0; a silent overwrite now that each merge row
# shares a (keep, mode) pair with a prune twin -- `by[(0.50, 'router')]` would have
# become the MERGED row and all ~14 readers below (Q1, Q2, Q4, Q5 and rec()) would
# have quietly changed meaning while still printing plausible numbers. Filtering at
# the single point of construction keeps every one of those readers correct without
# touching one of them.
_OLD_BY = "by = {(r['keep_ratio'], r['select_mode']): r for r in rows}\n"
assert c15.count(_OLD_BY) == 1, (
    f"`by` dict anchor: expected 1 hit, found {c15.count(_OLD_BY)}")
c15 = c15.replace(_OLD_BY, (
    "by = {(r['keep_ratio'], r['select_mode']): r\n"
    "      for r in rows if r.get('merge_ratio', 0.0) == 0.0}\n"
    "# Q6 needs the merge rows, so it gets its own index on the full four-part key.\n"
    "by_all = {(r['keep_ratio'], r['select_mode'], r.get('merge_ratio', 0.0),\n"
    "           r.get('tome_split', 'checkerboard')): r for r in rows}\n"
    "assert len(by_all) == len(rows), (\n"
    "    f'duplicate (keep, mode, merge, split) key among {len(rows)} rows -- a row is\\n'\n"
    "    f'shadowing another and Q6 would compare the wrong pair: '\\\n"
    "    f'{len(rows) - len(by_all)} collision(s)')\n"), 1)

# -- G6: keep merge rows out of Q3 --------------------------------------------
_OLD_POOL = ("pooled = [(p, r['select_mode']) for r in rows if r['keep_ratio'] < 1.0\n"
             "          for p in r['per_image'] if p['min_line_cov'] is not None]\n")
assert c15.count(_OLD_POOL) == 1, (
    f"Q3 pooled anchor: expected 1 hit, found {c15.count(_OLD_POOL)}")
c15 = c15.replace(_OLD_POOL, (
    "# Merge rows are EXCLUDED, not merely unfiltered. Both predictors here\n"
    "# (`retained_ink`, `min_line_cov`) are computed PRE-merge -- gathered on\n"
    "# topk_indices -- while `recall` is post-merge, so a merge row contributes a record\n"
    "# whose predictor is identical to its prune twin's and whose outcome is not. That is\n"
    "# pure noise injected exactly where the D2 verdict turns on a 0.05 rho gap.\n"
    "# NOTE the prune-only TWIN rows (keep 0.80/0.40/0.30/0.28) DO enter the pool and\n"
    "# legitimately so -- they are ordinary pruned rows at new budgets -- which means\n"
    "# Q3's numbers are not directly comparable to run 9/10's 15-row pool.\n"
    "pooled = [(p, r['select_mode']) for r in rows\n"
    "          if r['keep_ratio'] < 1.0 and r.get('merge_ratio', 0.0) == 0.0\n"
    "          for p in r['per_image'] if p['min_line_cov'] is not None]\n"), 1)

# -- G7: the Q6 verdict block, before the final JSON write --------------------
_FINAL_WRITE = ("with open(SELECTION_OUT, 'w') as f:\n"
                "    json.dump({'meta': {'run6_reference': RUN6_REFERENCE,\n"
                "                        'seed': SELECTION_SEED,\n"
                "                        'max_len': SELECTION_MAX_LEN,\n"
                "                        'control_drift_pts': drift,\n")
assert c15.count(_FINAL_WRITE) == 1, (
    f"final JSON write anchor: expected 1 hit, found {c15.count(_FINAL_WRITE)}")

Q6_BLOCK = '''# --- Q6 (1e): token-matched merge vs prune -- the whole architecture at equal cost ---
# The question this sweep exists to answer, stated so it can fail: on a merge-naive
# checkpoint, does compressing to M tokens by MERGING cost less accuracy than
# compressing to the same M by PRUNING? Holding M fixed is what makes it answerable;
# an unpaired "merging costs N points" charges merging for a budget cut it did not ask
# for.
#
# FRAMING, stated BEFORE the numbers so it cannot be fitted to them: every checkpoint
# in this project was trained at merge_ratio=0.0, so inference-time merging is
# OFF-DISTRIBUTION. By D12's own logic a negative result is EXPECTED and is NOT
# evidence that ToMe is worthless -- it is the H1 train/test-matching lesson a second
# time. What a negative result does license is refusing to adopt merging as a drop-in
# at inference; what a positive or near-neutral result licenses is training with
# merging on, which is the follow-up and is not in this run.
#
# RESOLUTION, also stated before the numbers: runs 9-11 put this harness's paired 95%
# half-width at roughly 2-4 pts on n=50 FUNSD documents. A |delta| under ~3 pts is
# BELOW WHAT THIS SWEEP CAN SEE and must be read as indistinguishable -- not as a
# small win, and not as a small loss.
#
# This constant is a PRE-REGISTERED BAR, not a measurement, and the two must not be
# confused: every row below also prints its OWN half-width, and a flat row whose own
# resolution exceeds this bar is reported UNDERPOWERED rather than null. Run 11's
# post-mortem is the reason -- its pre-registration set MIN_EFFECT_PTS = 3.0 against
# rows whose actual resolution was 4.6-5.6, so one verdict was unreachable before a
# single image was decoded, and the prose would have called it a null.
Q6_RESOLUTION_PTS = 3.0


def paired_recall_delta(row_a, row_b, n_boot=10000, seed=0):
    """mean(recall_a - recall_b) over the SAME documents + 95% bootstrap CI.

    Paired by document index: both rows saw the identical 50 FUNSD pages, and
    between-document variance dwarfs the effect under test, so an unpaired CI would be
    several times too wide to resolve anything. Resamples DOCUMENTS, which is the
    population the conclusion generalises over.

    Returns (mean, lo, hi, n, resolution) where resolution is the CI HALF-WIDTH -- the
    smallest effect this pair could have resolved. It is returned rather than assumed
    so no verdict string can claim a precision the data does not have.
    """
    a = {p['i']: p['recall'] for p in row_a['per_image']}
    b = {p['i']: p['recall'] for p in row_b['per_image']}
    shared = sorted(set(a) & set(b))
    d = np.array([a[i] - b[i] for i in shared], dtype=float) * 100.0
    if d.size < 3:
        return (float('nan'),) * 3 + (int(d.size), float('nan'))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    boots = d[idx].mean(axis=1)
    lo = float(np.percentile(boots, 2.5))
    hi = float(np.percentile(boots, 97.5))
    return float(d.mean()), lo, hi, int(d.size), (hi - lo) / 2.0


def assert_token_matched(label, row_m, row_p):
    """Hard stop if the two rows did not actually land on the same M.

    An assert, not a warning. The whole Q6 comparison is "same token count, different
    way of getting there"; if M differs then the delta is a budget effect wearing a
    merging costume, and a table that prints it anyway is worse than no table -- it
    reads exactly like the real thing. Checked PER IMAGE because 'visual_tokens'
    records only the last one, and absolutely against EXPECTED_M because two rows can
    agree on an M that is wrong for both.
    """
    tm = [p['tokens'] for p in row_m['per_image']]
    tp = [p['tokens'] for p in row_p['per_image']]
    assert tm and tm == tp, (
        f'{label}: NOT token-matched. merge row M {sorted(set(tm))} (n={len(tm)}) vs '
        f'prune row M {sorted(set(tp))} (n={len(tp)}). The delta would measure the '
        f'token budget, not merging.')
    for _r in (row_m, row_p):
        _exp = EXPECTED_M.get((_r['keep_ratio'], _r['select_mode'],
                               _r.get('merge_ratio', 0.0),
                               _r.get('tome_split', 'checkerboard')))
        _got = sorted({p['tokens'] for p in _r['per_image']})
        assert _exp is None or _got == [_exp], (
            f"{label}: row {_r['config']!r} ran at M={_got}, predicted {_exp}. Both "
            f'rows of a pair agreeing on a WRONG M passes the match check above, so '
            f'the arithmetic is checked absolutely too.')
    return tm[0]


q6_rows = []
_q6_hdr = (f"  {'pair':28s} {'M':>5s} {'merge':>7s} {'prune':>7s} {'delta':>7s} "
           f"{'95% CI':>18s} {'res':>5s}  verdict")
print('\\n' + '=' * 112)
print('Q6. TOKEN-MATCHED: merge to M vs prune to the same M   (paired by document, '
      '95% bootstrap CI)')
print('=' * 112)
print(_q6_hdr)
print('  ' + '-' * 108)
for _lbl, _mkey, _pkey in MERGE_PAIRS:
    _rm = by_all.get(_mkey)
    _rp = by_all.get(_pkey + (0.0, 'checkerboard'))
    if _rm is None or _rp is None:
        print(f"  {_lbl:28s} MISSING -- merge row "
              f"{'ran' if _rm is not None else 'ABSENT'}, twin "
              f"{'ran' if _rp is not None else 'ABSENT'} (session ended before both)")
        continue
    _M = assert_token_matched(_lbl, _rm, _rp)
    _d, _lo, _hi, _n, _res = paired_recall_delta(_rm, _rp)
    _sig = (_lo > 0) or (_hi < 0)
    # A flat row is only a null if it COULD have shown the effect. _res is this pair's
    # own measured half-width, so the two flat cases are separated by data rather than
    # by the bar: below the bar the row genuinely says "no difference this large",
    # above it the row says nothing at all.
    _under = (not _sig) and _res > Q6_RESOLUTION_PTS
    if _under:
        _v = (f'UNDERPOWERED (res {_res:.1f} > {Q6_RESOLUTION_PTS:.1f} pts bar) '
              f'-- not a null')
    elif not _sig:
        _v = f'indistinguishable (res {_res:.1f} pts at n={_n})'
    elif _d > 0:
        _v = 'MERGING WINS at equal M'
    else:
        _v = 'merging LOSES at equal M'
    print(f"  {_lbl:28s} {_M:5d} {_rm['word_recall_pct']:7.2f} "
          f"{_rp['word_recall_pct']:7.2f} {_d:+7.2f} "
          f"{f'[{_lo:+.2f}, {_hi:+.2f}]':>18s} {_res:5.1f}  {_v}")
    q6_rows.append({'pair': _lbl, 'tokens': _M,
                    'merge_config': _rm['config'], 'prune_config': _rp['config'],
                    'merge_recall_pct': _rm['word_recall_pct'],
                    'prune_recall_pct': _rp['word_recall_pct'],
                    'delta_pts': _d, 'ci95_lo': _lo, 'ci95_hi': _hi,
                    'resolution_pts': _res, 'n_paired': _n,
                    'significant': bool(_sig), 'underpowered': bool(_under)})
print('=' * 112)

if q6_rows:
    _wins = [q for q in q6_rows if q['significant'] and q['delta_pts'] > 0]
    _loss = [q for q in q6_rows if q['significant'] and q['delta_pts'] < 0]
    _und = [q for q in q6_rows if q['underpowered']]
    _flat = [q for q in q6_rows if not q['significant'] and not q['underpowered']]
    print(f'  {len(_wins)} pair(s) favour merging, {len(_loss)} favour pruning, '
          f'{len(_flat)} indistinguishable, {len(_und)} underpowered, '
          f'of {len(q6_rows)} measured.')
    # Seven uncorrected comparisons run in this cell (6 pairs + the sabotage row), so a
    # single marginal row is the least interesting thing here. The PATTERN is the
    # evidence: the two ink pairs agreeing with the two router pairs at the same merge
    # ratio is worth more than any one CI that just clears zero.
    print(f'  {len(q6_rows)} pairs + 1 sabotage row = {len(q6_rows) + 1} uncorrected '
          f'comparisons; read the pattern across')
    print('  the router/ink pairs, not a single row that just clears zero.')
    # 2026-09-18: the aggregate below used to be decided by `_wins`/`_loss` alone, with no
    # reference to how many pairs FAILED TO RESOLVE. So `=> MERGING BEATS PRUNING AT EQUAL M`
    # printed on run 13's 2-significant-with-3-underpowered table, and again on run 12's
    # table whose four router pairs were void. Every number above the line was correct; the
    # SENTENCE overstated them. That is this project's most repeated defect and its hardest
    # to catch, because nothing is numerically wrong.
    #
    # A direction now needs a majority AND a mostly-resolved table before it gets to be a
    # verdict, and the bar is applied to BOTH directions. Qualifying only the direction that
    # happened to contradict a previous prediction would be a worse bias than not qualifying
    # at all -- the same reason the sabotage row is judged on its own resolution.
    _DECISIVE_MIN = 2      # a direction needs at least this many RESOLVED pairs...
    _UND_MAX = 1           # ...and the table at most this many that could not resolve
    _lead_n = max(len(_wins), len(_loss))
    _decisive = _lead_n >= _DECISIVE_MIN and len(_und) <= _UND_MAX
    if (_wins or _loss) and not _decisive:
        print(f'  NOTE: the leading direction has {_lead_n} of {len(q6_rows)} pairs and '
              f'{len(_und)} pair(s) could not resolve.')
        print(f'        Bar for a verdict: >={_DECISIVE_MIN} resolved pairs one way AND '
              f'<={_UND_MAX} underpowered. NOT MET here, so the')
        print('        line below is a DIRECTION, not a finding. Quote the per-pair table '
              'above it, never this line.')
    if _loss and not _wins:
        print(f'  => {"MERGING IS NOT A DROP-IN" if _decisive else "LEANS AGAINST MERGING"} '
              f'at inference on a merge-naive checkpoint.')
        print('     This is the predicted outcome (D12/H1), so it is not a verdict on '
              'ToMe:')
        print('     it says the checkpoint was never taught to read merged tokens. The '
              'licensed')
        print('     follow-up is TRAINING with merge_ratio>0, not abandoning the stage.')
    elif _wins and not _loss:
        print(f'  => {"MERGING BEATS PRUNING AT EQUAL M" if _decisive else "LEANS TOWARD MERGING AT EQUAL M"}, '
              f'on weights that never saw a merged token.')
        print('     That is a stronger result than this run was designed to find; check '
              'the ink')
        print('     pair specifically, since it isolates the mechanism from the router\\'s '
              'weakness.')
    elif _wins and _loss:
        print('  => MIXED. Read the ink pairs against the router pairs: agreement means a '
              'real')
        print('     budget-dependent effect, disagreement means the router\\'s kept set is '
              'the')
        print('     confound and only the ink rows speak to merging itself.')
    elif _flat and not _und:
        print('  => NO PAIR SEPARATES, and every pair could have. Merging to M and '
              'pruning to M')
        print(f'     cost the same within each row\\'s own resolution (worst '
              f"{max(q['resolution_pts'] for q in _flat):.1f} pts),")
        print('     which is a genuine null and not a win for either -- do not report it '
              'as')
        print('     "merging is free".')
    else:
        print(f'  => NOTHING SEPARATES AND {len(_und)} PAIR(S) COULD NOT HAVE. This is '
              f'not a null;')
        print(f'     the flat rows carry half-widths up to '
              f"{max(q['resolution_pts'] for q in _und):.1f} pts against a "
              f'{Q6_RESOLUTION_PTS:.1f} pt bar.')
        print('     n is not a knob -- MAX_EVAL_SAMPLES=50 IS the whole FUNSD test '
              'split -- so')
        print('     choose nothing from these rows and say why (run 11\\'s power lesson).')
else:
    print('  Q6 produced no comparable pairs: no merge row found its twin.')

# --- SABOTAGE: does the checkerboard fix move RECALL, or only the parity statistic? ---
# scripts/diagnose_tome_parity.py measured missed horizontal/vertical redundancy going
# 49.2%/50.5% -> 0.0%/0.0%. That is a statistic about the PARTITION, not about OCR, and
# it has been quoted as though the two were the same thing. rank_parity reproduces the
# pre-fix split exactly, at the same M, same weights, same decoder -- so this is the
# only row in the project that can say whether the fix bought a reader anything.
_sl, _ckey, _rkey = SABOTAGE_PAIR
_rc, _rr = by_all.get(_ckey), by_all.get(_rkey)
sabotage_row = None
print('\\nSABOTAGE CONTROL: the pre-fix rank-parity split, same M, same weights')
if _rc is None or _rr is None:
    print(f"  skipped: needs both rows -- checkerboard "
          f"{'ran' if _rc is not None else 'ABSENT'}, rank_parity "
          f"{'ran' if _rr is not None else 'ABSENT'}")
else:
    _M = assert_token_matched(_sl, _rc, _rr)
    _d, _lo, _hi, _n, _res = paired_recall_delta(_rc, _rr)
    _sig = (_lo > 0) or (_hi < 0)
    print(f"  M={_M}   checkerboard {_rc['word_recall_pct']:.2f}   rank_parity "
          f"{_rr['word_recall_pct']:.2f}   delta {_d:+.2f} pts   "
          f"[{_lo:+.2f}, {_hi:+.2f}]   res {_res:.1f} pts  (n={_n})")
    if _sig and _d > 0:
        print('  => THE FIX IS REAL IN RECALL, not just in the partition statistic. The')
        print('     49.2%/50.5% -> 0.0%/0.0% numbers correspond to something a reader '
              'cares about.')
    elif _sig and _d < 0:
        print('  => THE FIX MADE RECALL WORSE. Merging spatial neighbours is more '
              'damaging than')
        print('     merging score-rank neighbours here, which would mean the similarity '
              'ToMe finds')
        print('     between adjacent patches is information the decoder was using. Stop '
              'quoting')
        print('     the parity statistic as an improvement and re-open the split design.')
    elif _res > Q6_RESOLUTION_PTS:
        print(f'  => UNDERPOWERED, NOT NULL. This contrast could only have seen an '
              f'effect of')
        print(f'     {_res:.1f} pts or larger, against a {Q6_RESOLUTION_PTS:.1f} pt bar. '
              f'It does not license')
        print('     "the fix changes nothing"; it licenses nothing at all.')
    else:
        print(f'  => NO MEASURABLE RECALL DIFFERENCE: |delta| {abs(_d):.2f} against this '
              f'row\\'s own')
        print(f'     resolution of {_res:.1f} pts at n={_n}.')
        print('     The checkerboard fix is CORRECT about the partition and UNPROVEN '
              'about the')
        print('     outcome. Report it that way: 49.2%/50.5% -> 0.0%/0.0% is a claim '
              'about the')
        print('     split, not about OCR accuracy.')
    sabotage_row = {'pair': _sl, 'tokens': _M,
                    'checkerboard_config': _rc['config'],
                    'rank_parity_config': _rr['config'],
                    'checkerboard_recall_pct': _rc['word_recall_pct'],
                    'rank_parity_recall_pct': _rr['word_recall_pct'],
                    'resolution_pts': _res,
                    'delta_pts': _d, 'ci95_lo': _lo, 'ci95_hi': _hi,
                    'n_paired': _n, 'significant': bool(_sig)}

'''
c15 = c15.replace(_FINAL_WRITE, Q6_BLOCK + _FINAL_WRITE, 1)

# Q6's output has to reach the artifact, not just the log: a Kaggle session's stdout
# is the first thing lost when the notebook is reopened.
_META_TAIL = "                        'max_words': MAX_WORDS,\n"
assert c15.count(_META_TAIL) == 1, (
    f"final meta anchor: expected 1 hit, found {c15.count(_META_TAIL)}")
c15 = c15.replace(_META_TAIL, _META_TAIL + (
    "                        'q6_resolution_pts': Q6_RESOLUTION_PTS,\n"
    "                        'q6_token_matched': q6_rows,\n"
    "                        'q6_sabotage': sabotage_row,\n"), 1)
put(15, c15)

# ======================================================================= PATCH H
print("H. cell 7 -- _selection_signal spliced from src/model.py; select_mode in forward()")
c7 = src(7)

# Run 18 trains on an externally chosen kept set, so `select_mode` has to exist on the
# TRAINING path. Through run 14 it existed only on `generate()`, as ~20 lines of inline
# if/elif. Copying that block into forward() is the one thing that must not happen here:
# two copies of a mode dispatch is exactly the shape of the bug that kept ToMe from ever
# running (notebook held an old merger, src/ held the fixed one, nothing compared them),
# and the failure mode is worse in this case -- if training and eval ever resolve 'ink'
# differently, every arm of run 18 is uninterpretable and NOTHING fails loudly. The
# tables would still print.
#
# So: splice the ONE implementation out of src/model.py, exactly as patches E and F do,
# and route both callers through it. Reading from disk makes divergence impossible
# rather than merely unlikely, and it means scripts/verify_train_select_mode.py -- which
# executes src/model.py's helper against the pre-refactor inline dispatch and gets
# max|diff| = 0.000e+00 across all six modes -- is also a check on this notebook's copy.
SEL_SIGNAL = read_method("src/model.py", "_selection_signal")
assert "if select_mode not in SELECT_MODES:" in SEL_SIGNAL, (
    "spliced _selection_signal does not raise on an unknown mode. AGENTS.md records a "
    "verifier whose silent else-fallthrough reported PASS for two modes that never ran; "
    "a silent fallthrough HERE would train on router selection while the log said 'ink'.")
for _need in ("patch_ink(pixel_values, N)", "stratified_scores(", "invert = True"):
    assert _need in SEL_SIGNAL, f"spliced _selection_signal is missing {_need!r}"
# The annotations are evaluated when the `def` runs, so the names must be imported.
# PATCH E1 puts `Tuple, Optional, Sequence` in cell 2; assert rather than assume, because
# E1 is keyed on a different anchor and could be reordered away from this.
assert "from typing import Tuple, Optional, Sequence" in src(2), (
    "cell 2 lacks the typing import (PATCH E1); _selection_signal's annotations would "
    "raise NameError the moment cell 7 runs")

# -- H1: replace generate()'s inline dispatch with the helper ------------------
# DONE FIRST, BEFORE the helper is inserted, and that ordering is load-bearing rather
# than cosmetic. src/model.py's copy of this dispatch is textually similar to the
# notebook's (it is the same logic, refactored out of it), so once the helper is spliced
# into the cell there are TWO dispatches present and any anchor that matches one risks
# matching the other. Replacing while the notebook's is still the only one makes
# uniqueness structural. The alternative -- relying on src/ using double quotes where
# the notebook uses single ones -- would make this patch depend on a formatting accident
# in a file it does not own.
#
# The anchor starts at `select_scores = None`, NOT at the `select_mode not in
# SELECT_MODES` raise above it, because PATCH F inserts a `tome_split` validation
# BETWEEN those two lines. Anchoring across F's insertion point is what made the first
# version of this patch fail with "expected 1 hit, found 0" -- a correct failure, and
# the anchor was the thing that was wrong. Consequences of starting lower, both
# deliberate:
#   * generate() keeps its own `select_mode` raise. That is now a duplicate of the one
#     inside the helper, but both read the same module-level SELECT_MODES so they cannot
#     disagree, and keeping it preserves the exact error path runs 7-14 produced. The
#     honest reason not to delete it: removing it would make tome_split validate FIRST,
#     reordering two error messages for no gain.
#   * F's tome_split block is untouched, so this patch does not have to restate F's text
#     and the two cannot drift.
_OLD_GEN_DISPATCH = (
    "        select_scores = None\n"
    "        invert = False\n"
    "        if select_mode == 'negated':\n"
    "            invert = True\n"
    "        elif select_mode == 'random':\n"
    "            select_scores = torch.rand(B, N, device=device, dtype=visual_tokens.dtype)\n"
    "        elif select_mode == 'ink':\n"
    "            select_scores = patch_ink(pixel_values, N).to(visual_tokens.dtype)\n"
    "        elif select_mode in ('stratified', 'stratified_negated'):\n"
    "            # Grid derived from pixel_values, not assumed, so a non-standard input\n"
    "            # raises here instead of silently stratifying over the wrong axis.\n"
    "            grid = (pixel_values.shape[-2] // 32, pixel_values.shape[-1] // 32)\n"
    "            raw = self.router.scorer(visual_tokens).squeeze(-1)\n"
    "            select_scores = stratified_scores(\n"
    "                raw, grid=grid, negate=(select_mode == 'stratified_negated')\n"
    "            ).to(visual_tokens.dtype)\n")
assert c7.count(_OLD_GEN_DISPATCH) == 1, (
    f"generate() inline-dispatch anchor: expected 1 hit, found "
    f"{c7.count(_OLD_GEN_DISPATCH)}. This block produced runs 7-14, D11, D12 and M1 -- "
    f"if it has moved, STOP and re-verify the replacement against it rather than "
    f"loosening this anchor.")
assert "if select_mode not in SELECT_MODES:" in c7, (
    "generate() lost its select_mode validation before this patch ran")
c7 = c7.replace(_OLD_GEN_DISPATCH, (
    "        # Resolved by the same helper forward() uses -- see _selection_signal above.\n"
    "        # This replaced ~20 lines of inline if/elif that were byte-equivalent;\n"
    "        # scripts/verify_train_select_mode.py executes both forms on all six modes\n"
    "        # and asserts max|diff| = 0, which is what keeps runs 7-14 comparable.\n"
    "        select_scores, invert = self._selection_signal(\n"
    "            pixel_values, visual_tokens, select_mode)\n"), 1)

# -- H2: insert the helper immediately before forward() ------------------------
_FWD_DEF = ("    def forward(self, pixel_values, labels=None, decoder_input_ids=None, "
            "keep_ratio=None, merge_ratio=None):\n")
assert c7.count(_FWD_DEF) == 1, (
    f"forward() signature anchor: expected 1 hit, found {c7.count(_FWD_DEF)}")
_FWD_NEW = ("    def forward(self, pixel_values, labels=None, decoder_input_ids=None, "
            "keep_ratio=None, merge_ratio=None, select_mode='router'):\n")
c7 = c7.replace(_FWD_DEF, SEL_SIGNAL + "\n\n" + _FWD_NEW, 1)

# -- H3: route forward()'s router call through the helper ----------------------
# `use_ste=self.training` is left EXACTLY as it was. Under an external ranking the STE
# is skipped anyway (src/router.py:92 gates on `select_scores is None`), so hardcoding
# use_ste=False here would be a second, redundant expression of the same rule in a second
# place -- and would silently change the router arm if that gate ever moved.
_OLD_FWD_ROUTE = ("        coords = self._generate_2d_coords(B, N, device, dtype=visual_tokens.dtype)\n"
                  "        selected_tokens, scores, topk_indices, pruned_coords = self.router(\n"
                  "            visual_tokens, keep_ratio=k_ratio, coords=coords, use_ste=self.training\n"
                  "        )\n")
assert c7.count(_OLD_FWD_ROUTE) == 1, (
    f"forward() router-call anchor: expected 1 hit, found {c7.count(_OLD_FWD_ROUTE)}")
c7 = c7.replace(_OLD_FWD_ROUTE, (
    "        # Run 18: the kept set may be chosen by something other than the router.\n"
    "        # Resolved by the SAME helper generate() uses, so train and eval cannot\n"
    "        # disagree about what 'ink' means.\n"
    "        select_scores, invert = self._selection_signal(\n"
    "            pixel_values, visual_tokens, select_mode)\n"
    "        coords = self._generate_2d_coords(B, N, device, dtype=visual_tokens.dtype)\n"
    "        selected_tokens, scores, topk_indices, pruned_coords = self.router(\n"
    "            visual_tokens, keep_ratio=k_ratio, coords=coords, use_ste=self.training,\n"
    "            select_scores=select_scores, invert=invert\n"
    "        )\n"), 1)

# -- H4: echo the mode out of forward() ---------------------------------------
# From INSIDE forward(), so cell 11's step-0 assert reports what the model USED rather
# than what the config said. D5 is the standing case in this project of a knob that
# shaped two runs while appearing nowhere in their own artifacts; run 18's whole variable
# must not be a third.
_OLD_RET_TK = "            'topk_indices': topk_indices,\n"
assert c7.count(_OLD_RET_TK) == 1, (
    f"forward() return-dict anchor: expected 1 hit, found {c7.count(_OLD_RET_TK)}")
c7 = c7.replace(_OLD_RET_TK, _OLD_RET_TK + "            'select_mode': select_mode,\n", 1)

# Non-vacuity: the dispatch must now exist exactly ONCE in the cell, inside the helper.
# Without this, a future anchor drift that deleted the helper insertion would still pass
# every assert above and produce a notebook where generate() calls a method that does not
# exist -- at eval time, four hours in.
assert c7.count("    def _selection_signal(") == 1, "helper not inserted exactly once"
assert c7.count("self._selection_signal(") == 2, (
    f"expected exactly 2 callers of _selection_signal (forward + generate), found "
    f"{c7.count('self._selection_signal(')}")
assert c7.count("select_scores = patch_ink(pixel_values, N)") == 1, (
    "the ink branch should now exist exactly once, inside the helper")
# H1 anchored BELOW PATCH F's tome_split insertion precisely so it would not have to
# restate it. Assert F's block survived, or the narrow anchor silently becomes a way to
# delete a validation this patch does not own.
assert c7.count("if tome_split not in TOME_SPLITS:") == 1, (
    "PATCH F's tome_split validation is gone -- H1's anchor swallowed it")
assert c7.count("if select_mode not in SELECT_MODES:") == 2, (
    f"expected 2 select_mode validations (generate's own + the helper's), found "
    f"{c7.count('if select_mode not in SELECT_MODES:')}. Both read the same "
    f"module-level SELECT_MODES so they cannot disagree; a count of 1 means one of the "
    f"two error paths was deleted.")
put(7, c7)
print(f"   spliced {len(SEL_SIGNAL.splitlines())} lines from src/model.py "
      f"(_selection_signal); forward() and generate() now share it")

# ======================================================================= PATCH I
# T4: evaluate on the POOLED corpus (FUNSD + SROIE = 397) instead of FUNSD alone.
#
# T1 s6 fixed the requirement as a number, not a direction: res <= 1.0 pt needs
# n >~ 307, and FUNSD test IS 50 documents -- the whole split, so n was never a knob
# there. T2 settled the pool at FUNSD + sizhkhy/SROIE = 397 and excluded CORD on
# DENOTATION (its GT is the annotated key-value subset, not the page), which is a
# reason size could not have supplied and which must never be relaxed by adding
# "more receipts".
#
# The corpus enters the pipeline through exactly THREE lines, and they are all in the
# CANONICAL notebook, which is why this is the first patch here to touch cells 9/13 at
# all: cell 9's DocumentDataset.__getitem__, cell 13's `test_raw = load_dataset(...)`,
# and cell 15's sweep loop (which inherits `test_raw` from cell 13's namespace rather
# than loading its own). Patching the GENERATOR rather than the canonical notebook is
# what keeps runs 2-6 reproducible: the canonical notebook stays FUNSD-only, so
# re-running it still reproduces the published rows.
#
# THE SCHEMA IS NOT SHARED, and the failure is loud rather than silent -- which is the
# good case, but only if the adapter exists:
#     nielsr/funsd   columns: ['bboxes', 'id', 'image',  'ner_tags', 'words']
#     sizhkhy/SROIE  columns: ['bboxes', 'fields', 'images', 'ner_tags', 'words']
# `sample['image']` raises KeyError on every SROIE row.
# Measured by scripts/preflight_pooled_corpus.py (23/23), whose section 1c asserts the
# naive access RAISES -- so this adapter is provably load-bearing and cannot later be
# deleted as defensive clutter.
print("I. cells 2/9/13/15 -- pooled eval corpus (FUNSD+SROIE), corpus labels, random arm")

# -- I1: the corpus list is a DECLARED config, in cell 2 with every other knob ------
# D5's lesson, applied before the fact: `lambda_entropy=0.05` shaped two runs from a
# signature default and appeared in no config cell. A corpus is a far larger knob than
# a loss weight, so it is named where a reader looks for knobs, not buried in cell 13.
c2 = src(2)
# Anchored on the ASSIGNMENT, not on the line including its VALUE.
#
# This anchor carried `DO_TRAIN = True                  # True: retrain-with-...` verbatim
# until 2026-10-02. When PATCH A's default flipped True -> False for T4 on 2026-09-30 the
# two drifted, and this assert raised `expected 1 hit, found 0` -- correct behaviour, and
# then latent for two days because nothing regenerated. The notebook on disk stayed the
# PREVIOUS generation (run 18's armed config) while the generator said T4, and all four of
# T4's verifiers certified that stale notebook.
#
# An anchor that embeds a value it does not control expires every time that value changes.
# `DO_TRAIN` is a knob PATCH A owns and T4/T6/T18 each want set differently; the thing
# PATCH I actually needs is "insert the corpus block immediately above the DO_TRAIN
# assignment", which is what this now says. Same lesson as the `_TRAIN_SELECT_MODES = (`
# anchor in verify_notebook_train_select_mode.py: key on the assignment, not the value.
#
# NOTE the absence of a leading "\n": CORPUS_CFG is inserted BEFORE this anchor, and it
# ends with a blank line. Anchoring on "\nDO_TRAIN = " would consume the newline that
# terminates the preceding comment line and splice the block's first line onto it.
_ANCHOR_I1 = "DO_TRAIN = "
assert c2.count(_ANCHOR_I1) == 1, (
    f"cell 2 DO_TRAIN anchor: expected 1 hit, found {c2.count(_ANCHOR_I1)}")
CORPUS_CFG = '''
# ---- T4: THE EVAL CORPUS (2026-09-29) ---------------------------------------------
# (label, hf_path, split). The label is stored on every per-image record, so a pooled
# artifact can always be sliced back to FUNSD-only and compared against runs 2-14.
# Set to just the FUNSD entry to reproduce any historical row exactly.
#
# CORD IS DELIBERATELY EXCLUDED AND MUST NOT BE ADDED (T2). Its ground truth annotates
# key-value fields, not the page, so `recall` on CORD denotes a different quantity;
# pooling would average two metrics under one name. Its grain (one word = 5.00 pts)
# cannot even express T1's 1.0 pt MDE. This is a denotation argument, not a size one --
# adding 200 more CORD receipts would not fix it.
EVAL_CORPORA = [
    ('funsd', 'nielsr/funsd', 'test'),     # 50 -- every run from 2 to 14 was measured here
    ('sroie', 'sizhkhy/SROIE', 'test'),    # 347 -- T2's second corpus, word-level GT
]
POOLED_N_EXPECTED = 397   # asserted at load time in cell 13; T1 s6 needs n >~ 307

'''
c2 = c2.replace(_ANCHOR_I1, CORPUS_CFG.lstrip("\n") + _ANCHOR_I1, 1)
put(2, c2)

# -- I2: the adapter and the lazy pooled set, in cell 9 ----------------------------
c9 = src(9)
_ANCHOR_I2 = "class DocumentDataset(Dataset):"
assert c9.count(_ANCHOR_I2) == 1, (
    f"cell 9 DocumentDataset anchor: expected 1 hit, found {c9.count(_ANCHOR_I2)}")
POOL_HELPERS = '''def doc_image(sample):
    """The image column is `image` on FUNSD and `images` on SROIE.

    Raising on neither is deliberate. A `.get('image') or .get('images')` would
    return None for a corpus with a third name and hand the None to .convert(),
    producing an AttributeError several frames away from the cause.
    """
    for _k in ('image', 'images'):
        if _k in sample:
            return sample[_k]
    raise KeyError(f'no image column in {sorted(sample.keys())}')


# No box adapter here, deliberately. `words` and `bboxes` are named IDENTICALLY on
# both corpora -- FUNSD ['bboxes','id','image','ner_tags','words'], SROIE
# ['bboxes','fields','images','ner_tags','words'] -- so the image column is the only
# schema divergence in the pool. A doc_boxes() helper shipped here until 2026-09-30
# and was never called once: cell 15 already reads
# `sample.get('bboxes') or sample.get('boxes')`, which resolves on both. It adapted a
# divergence that does not exist, which is the `final_coords` defect in miniature --
# code that makes a reader believe a path is wired when nothing reaches it.
class PooledTestSet:
    """Several HF splits indexed as one, LAZILY, each sample tagged with its corpus.

    Lazy on purpose. datasets.concatenate_datasets refuses these two splits outright
    (their Features differ), and the obvious workaround -- materialise a list of dicts
    -- decodes 397 images eagerly; SROIE's are ~932x2212, so that is ~2 GB of PIL
    objects resident for the whole sweep, on a box that also holds a 771 MiB model.
    This holds only the (part, index) pairs and decodes one image at a time, which is
    what the eval loop does anyway.

    Supports len/iter/getitem because that is the whole interface cell 13 and cell 15
    use on `test_raw`: `len()`, `enumerate(tqdm(...))` and `sample[key]`.
    """

    def __init__(self, specs):
        self.parts, self.index = [], []
        for _name, _path, _split in specs:
            _ds = load_dataset(_path, split=_split)
            self.parts.append((_name, _ds))
            self.index += [(len(self.parts) - 1, _j) for _j in range(len(_ds))]

    def __len__(self):
        return len(self.index)

    def __getitem__(self, k):
        _p, _j = self.index[k]
        _name, _ds = self.parts[_p]
        _r = dict(_ds[_j])
        _r['corpus'] = _name
        return _r

    def __iter__(self):
        for _k in range(len(self)):
            yield self[_k]

    def counts(self):
        return {_name: len(_ds) for _name, _ds in self.parts}


'''
c9 = c9.replace(_ANCHOR_I2, POOL_HELPERS + _ANCHOR_I2, 1)

_OLD_IMG9 = "        img = sample['image'].convert('RGB')"
assert c9.count(_OLD_IMG9) == 1, (
    f"cell 9 image access: expected 1 hit, found {c9.count(_OLD_IMG9)}")
c9 = c9.replace(_OLD_IMG9, "        img = doc_image(sample).convert('RGB')", 1)

# `test_ds` (cell 9's DocumentDataset over FUNSD test) is left FUNSD-ONLY on purpose.
# It is the TRAINING-side test set; T4 is eval-only, and pooling it would change what a
# future DO_TRAIN run validates against without that being anyone's decision. Asserted
# rather than merely left alone, so "the pooled patch missed a call site" and "the
# pooled patch deliberately skipped this one" stay distinguishable.
assert c9.count("test_ds = DocumentDataset(dataset_name='nielsr/funsd'") == 1, (
    "cell 9's training-side test_ds is not the expected FUNSD-only build -- if this "
    "moved, decide explicitly whether it should pool, do not let PATCH I answer it")
put(9, c9)

# -- I3: cell 13 builds the pooled set; every downstream cell inherits it ----------
c13 = src(13)
_OLD_RAW = ("test_raw = load_dataset('nielsr/funsd', split='test')  "
            "# all 50 test samples for stable metrics")
assert c13.count(_OLD_RAW) == 1, (
    f"cell 13 test_raw load: expected 1 hit, found {c13.count(_OLD_RAW)}")
_NEW_RAW = '''test_raw = PooledTestSet(EVAL_CORPORA)   # T4: FUNSD 50 + SROIE 347 = 397
_counts = test_raw.counts()
print(f'EVAL CORPUS: n={len(test_raw)}  {_counts}')
# T2 verified these sizes BY LOADING; asserting them here means a mirror that silently
# reshards is a crash at minute one rather than a pooled number with the wrong
# denominator six hours in. The same assert is what would catch CORD being added.
assert len(test_raw) == POOLED_N_EXPECTED, (
    f'pooled eval corpus is n={len(test_raw)}, expected {POOLED_N_EXPECTED}: {_counts}')
if len(test_raw) < 307:
    print('  WARNING: n < 307, so T1 s6 res <= 1.0 pt is UNREACHABLE and the FREE '
          'verdict cannot be returned no matter what the point estimate is.')'''
c13 = c13.replace(_OLD_RAW, _NEW_RAW, 1)

_OLD_IMG13 = "    img = sample['image'].convert('RGB')"
assert c13.count(_OLD_IMG13) == 1, (
    f"cell 13 image access: expected 1 hit, found {c13.count(_OLD_IMG13)}")
c13 = c13.replace(_OLD_IMG13, "    img = doc_image(sample).convert('RGB')", 1)
put(13, c13)

# -- I4: cell 15 -- adapter in the sweep loop, corpus on every per-image record ----
c15 = src(15)
_OLD_IMG15 = "        img = sample['image'].convert('RGB')"
assert c15.count(_OLD_IMG15) == 1, (
    f"cell 15 image access: expected 1 hit, found {c15.count(_OLD_IMG15)}")
c15 = c15.replace(_OLD_IMG15, "        img = doc_image(sample).convert('RGB')", 1)

# The corpus label is what makes T1 s5's per-corpus discard constraint COMPUTABLE.
# That constraint -- "the trimmed-away set must not contain more than half of any one
# corpus's contribution" -- exists only as prose in AGENTS.md, and it cannot be
# implemented at all unless the scorer can tell which corpus a discarded document came
# from. At n=397 a g=0.10 trim discards 39 per tail against FUNSD's entire 50, i.e. up
# to 78% of the only corpus this project has ever measured, so the check is not
# hypothetical.
_OLD_PI_I = ("        per_image.append({\n"
             "            'i': i,\n"
             "            'tokens': int(meta['compressed_tokens']),\n")
assert c15.count(_OLD_PI_I) == 1, (
    f"per_image corpus anchor: expected 1 hit, found {c15.count(_OLD_PI_I)}. PATCH G3 "
    f"owns the two lines above; if G3 moved, this insert must move with it")
c15 = c15.replace(_OLD_PI_I, ("        per_image.append({\n"
                              "            'i': i,\n"
                              "            'corpus': sample.get('corpus', 'funsd'),\n"
                              "            'tokens': int(meta['compressed_tokens']),\n"), 1)

# -- I5: per-corpus row aggregates ------------------------------------------------
# T4: "report the pooled result stratified by corpus, and keep FUNSD-only rows so the
# historical rows stay comparable." Storing the breakdown per row is what makes the
# second half true WITHOUT a second run: the FUNSD slice of a pooled row is directly
# comparable to runs 13/14's rows, because it is the same 50 documents under the same
# config. Computed from per_image rather than accumulated separately, so it cannot
# disagree with the pooled figure it decomposes.
_OLD_AGG = ("    covs = [p['min_line_cov'] for p in per_image "
            "if p['min_line_cov'] is not None]\n")
assert c15.count(_OLD_AGG) == 1, (
    f"row-aggregate anchor: expected 1 hit, found {c15.count(_OLD_AGG)}")
PER_CORPUS_AGG = '''    _by_corpus = {}
    for _p in per_image:
        _by_corpus.setdefault(_p.get('corpus', 'funsd'), []).append(_p)
    per_corpus = {
        _cn: {
            'n': len(_ps),
            'word_recall_pct': float(np.mean([_p['recall'] for _p in _ps]) * 100.0),
            'character_accuracy_pct': float(
                (1.0 - np.mean([_p['ned'] for _p in _ps])) * 100.0),
            'word_order_pct': float(np.mean([_p['word_order'] for _p in _ps]) * 100.0),
            'mean_ned': float(np.mean([_p['ned'] for _p in _ps])),
            'mean_gen_tokens': float(np.mean([_p['gen_tokens'] for _p in _ps])),
        }
        for _cn, _ps in sorted(_by_corpus.items())
    }
'''
c15 = c15.replace(_OLD_AGG, _OLD_AGG + PER_CORPUS_AGG, 1)

_OLD_RET = ("        'num_eval_samples': len(recs),\n"
            "        'per_image': per_image,\n")
assert c15.count(_OLD_RET) == 1, (
    f"row return anchor: expected 1 hit, found {c15.count(_OLD_RET)}")
c15 = c15.replace(_OLD_RET, ("        'num_eval_samples': len(recs),\n"
                             "        'per_corpus': per_corpus,\n"
                             "        'per_image': per_image,\n"), 1)

# -- I6: THE TOKEN-MATCHED RANDOM ARM ---------------------------------------------
# Promoted from "check" to BLOCKER by T3 s6. Two independent requirements land on this
# one row:
#
#   (a) T1 s8: "merging beats random at matched M" is NOT COMPUTABLE from runs 13/14 --
#       merge budgets are [1344, 1440, 1920, 3840], random budgets [1680, 2400, 3600],
#       and the overlap is EMPTY (verified from the artifact, not cited). Any past
#       statement of that form was comparing across budgets.
#   (b) T1 s3's amendment: the matched-NORMAL null is sensitive but NOT SPECIFIC to
#       merging. 13 of 21 contrasts containing no merging at all clear its 1.74 bar, and
#       the sweep's worst per-document loss (-80.85 pts) and highest ratio (5.43) both
#       belong to `keep=0.75 ink ORACLE`, where nothing is merged. So a firing tail gate
#       licenses "this page is visible", not "merging did it". The reportable bar has to
#       come from an ACTIVE NON-MERGE COMPARATOR AT THE SAME BUDGET -- this row.
#
# keep=0.40 -> K = round(4800*0.40) = 1920, merge 0.0 -> M = 1920. Same budget as the
# pre-registered primary's BOTH arms (`keep=0.50 m=0.20 ink` and `keep=0.40 ink TWIN`).
#
# Appended to MERGE_CONFIGS, not to SELECTION_CONFIGS: the 15 published selection rows
# produced numbers that are already cited, and PATCH G left that literal untouched for
# exactly that reason. Row count goes 28 -> 29.
#
# Anchored on the last INK row rather than on the sabotage row, so the arm lands ABOVE
# the sabotage block's comment. Anchoring below it would have put this row inside the
# scope of a comment that describes rank_parity, which reads as if the random arm were
# the negative control -- it is the opposite, an ACTIVE comparator.
_OLD_INKTWIN = ("    ('keep=0.28 ink TWIN',       0.28, 'ink',    0.00, 'checkerboard'),\n")
assert c15.count(_OLD_INKTWIN) == 1, (
    f"last-ink-row anchor: expected 1 hit, found {c15.count(_OLD_INKTWIN)}")
RANDOM_ARM = ("    # T1 s8 / T3 s6: the structure-matched degenerate baseline at the\n"
              "    # primary's own budget. `random` reseeds per row from SELECTION_SEED,\n"
              "    # so it draws the same masks on every re-run.\n"
              "    ('keep=0.40 random TWIN',    0.40, 'random', 0.00, 'checkerboard'),\n")
c15 = c15.replace(_OLD_INKTWIN, _OLD_INKTWIN + RANDOM_ARM, 1)

_OLD_EXPM = ("    (0.28, 'ink', 0.00, 'checkerboard'): 1344,\n")
assert c15.count(_OLD_EXPM) == 1, (
    f"EXPECTED_M last-ink entry: expected 1 hit, found {c15.count(_OLD_EXPM)}")
c15 = c15.replace(_OLD_EXPM,
                  _OLD_EXPM + "    (0.40, 'random', 0.00, 'checkerboard'): 1920,\n", 1)

# Non-vacuity: the new row must actually sit at the primary's budget, or it is a
# comparator for a different question. Checked against EXPECTED_M's own literals --
# the table the run verifies itself against -- rather than against this patch's
# arithmetic, so a wrong keep_ratio here is caught by the same table the notebook
# asserts on at runtime.
for _need in ("    (0.40, 'random', 0.00, 'checkerboard'): 1920,\n",   # the new arm
              "    (0.50, 'ink', 0.20, 'checkerboard'): 1920,\n",      # primary treatment
              "    (0.40, 'ink', 0.00, 'checkerboard'): 1920,\n"):     # primary control
    assert c15.count(_need) == 1, (
        f"EXPECTED_M must place the random arm at the pre-registered primary's own "
        f"budget; missing or duplicated: {_need.strip()}")
assert c15.count(": 1920,\n") == 6, (
    f"expected 6 EXPECTED_M rows at M=1920 after adding the random arm (router m=0.20, "
    f"router TWIN, ink m=0.20, ink TWIN, rank_parity sabotage, random TWIN), found "
    f"{c15.count(': 1920,')}")
put(15, c15)
print("   pooled corpus wired through cells 2/9/13/15; per-image `corpus` label added; "
      "random arm at M=1920 appended (28 -> 29 rows)")

# ============================================================================ write
for i, c in enumerate(cells):
    if c["cell_type"] != "code":
        continue
    s = "".join(c["source"])
    if any(ln.lstrip().startswith(("!", "%")) for ln in s.splitlines()):
        continue  # IPython magics are not pure Python
    try:
        ast.parse(s)
    except SyntaxError as e:
        raise SystemExit(f"cell {i} does not parse after patching: {e}")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")

print(f"\nwrote {OUT} -- all code cells parse; original notebook untouched")
