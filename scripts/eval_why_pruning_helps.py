#!/usr/bin/env python
"""Why does discarding visual tokens *raise* recall? Two hypotheses, one discriminating test.

The surviving deliverable is that post-encoder pruning is close to free and can help: run 9
scores 80.46 at keep=0.50 and 79.25 at keep=0.35 against its own 77.62 unpruned ceiling
(D11, n=50 local). Nothing in AGENTS.md explains *why*, and the two available explanations
have very different consequences for what can be claimed:

  H1  TRAIN/TEST MATCHING (mundane).  Runs 9 and 10 were trained with pruning ON at
      TRAIN_KEEP_RATIO=0.50. So keep=1.00 at eval time is OFF-DISTRIBUTION for those
      weights -- the decoder never saw 4800 tokens during the retrain. Under H1 "pruning
      helps" is an artifact of evaluating at the budget the model was trained for, the
      77.62 ceiling is artificially depressed, and 80.46 is a RECOVERY rather than a gain.

  H2  INFERENCE-TIME DENOISING (interesting).  Most of a FUNSD page is blank paper. Under
      H2, dropping those tokens genuinely helps by reducing cross-attention dilution, and
      it should help a model that was NEVER trained with pruning too.

**The discriminating test is run 5.** Run 5 is the pre-pruning checkpoint: trained AND
evaluated at keep=1.00, no pruning anywhere. The two hypotheses make opposite predictions
about its accuracy-vs-budget curve:

    H1 predicts run 5 PEAKS at keep=1.00 and falls monotonically as tokens are removed.
    H2 predicts run 5 IMPROVES when tokens are removed, same as run 9 does.

**What makes this a controlled comparison rather than another sweep: `select_mode="ink"`.**
Ink ranks patches by pixel contrast, computed from the image alone, so it is
**weight-independent** -- both checkpoints keep the *identical* token set at every budget.
Kaggle already demonstrated this incidentally: its ink-ORACLE rows report retained_ink
0.994 / 0.950 at keep=0.50 / 0.35 for run 9 and run 10 *alike*. So every difference in the
curves below is attributable to the weights, never to which tokens were dropped -- and that
is checkable, not assumed (control 1). Using the routers instead would confound "what budget
was this trained for" with "how good is this checkpoint's router", and run 5's router is
known-inverted (D1), which would guarantee a misleading answer.

    PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
        python -u scripts/eval_why_pruning_helps.py [--n 50] [--pair run5_run9]

Cost: ~12.5 s/image/config on CPU. 2 checkpoints x 5 configs x n images. n=50 is ~1.8 h.

RUN 11 (added 2026-09-15). Run 11 is the missing arm: run 5's base + 5 epochs at
TRAIN_KEEP_RATIO=1.00, i.e. run 9's epochs WITHOUT the pruning. It turns the two-checkpoint
comparison above into the three-way one that can attribute the gain:

    run 9 - run 5   =  pruning-aware training + 5 epochs   <- confounded (what D12 measured)
    run 11 - run 5  =                           5 epochs   <- the confound, alone
    run 9 - run 11  =  pruning-aware training              <- THE ISOLATION

`--pair` selects which two checkpoints load; the file still holds exactly two at a time,
because AGENTS.md records that a third element runs clean and is then silently omitted from
every delta (line 360 indexes, it does not unpack). Each pair also declares which slot is
the FOCUS and which is the REFERENCE, which fixes the sign of ISO (below) rather than
leaving it to be inferred from the print order.

SCOPE LIMIT, stated before any output: run 9 differs from run 5 by pruning-aware training
AND by five more epochs of it. A finding that run 9 beats run 5 therefore does NOT isolate
pruning as the cause, and this script does not claim otherwise. What it *can* settle is the
shape of each checkpoint's own curve, which is what H1 and H2 disagree about.
"""
import argparse
import ast
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Same notebook D11 read: the one that produced runs 9/10.
NOTEBOOK = os.path.join(ROOT, "kaggle_pruning_run.ipynb")

CK_RUN5 = ("run 5  (no pruning in training)",
           os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt"))
CK_RUN9 = ("run 9  (trained at keep=0.50)",
           os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt"))
CK_RUN11 = ("run 11 (5 epochs at keep=1.00)",
            os.path.join(ROOT, "run 11", "adaptive_donut_pruned.pt"))

# name -> (A, B, focus_slot, reference_slot, out_basename). A/B keep the checklist's stated
# order because the DiD table prints B - A and decide() reads A; focus/reference are separate
# so ISO's sign is declared, not inherited from that order.
PAIRS = {
    "run5_run9":  (CK_RUN5,  CK_RUN9,  "B", "A", "why_pruning_helps_local.json"),
    "run11_run9": (CK_RUN11, CK_RUN9,  "A", "B", "why_pruning_helps_iso_run11_run9.json"),
    "run5_run11": (CK_RUN5,  CK_RUN11, "B", "A", "why_pruning_helps_iso_run5_run11.json"),
}
DEFAULT_PAIR = "run5_run9"

MAX_LEN = 512
TASK_PROMPT = "<s_doc>"
BUDGETS = (0.50, 0.35, 0.25, 0.20)
SELECT_MODE = "ink"          # weight-independent: identical tokens for both checkpoints

# ----------------------------------------------------------------- PRE-REGISTERED
# Run 6's measured ceiling for run 5's weights at keep=1.00 (Kaggle, transformers 4.x).
# The harness anchor: if local run 5 at keep=1.00 does not land near this, nothing else
# in this run is interpretable. D11 measured the local-vs-Kaggle drift at keep=1.00 as
# +0.32 pts, so 1.5 is loose enough to pass on a sound harness and tight enough to fail
# on a wrong checkpoint (run 9's weights would read ~77.6 too, so this is NOT a
# checkpoint-identity check -- control 1 is).
RUN6_REFERENCE_RECALL = 77.74
HARNESS_TOL = 1.5

# Ink-ORACLE retained_ink from Kaggle's run-9/run-10 sweep. Identical across the two
# checkpoints there, which is the premise of this whole design; near-deterministic given
# the image, so this is the sharp checkpoint/selection gate (D11's lesson).
KAGGLE_INK_ORACLE = {0.50: 0.994, 0.35: 0.950}
INK_TOL = 0.10

# H2 is confirmed only if removing tokens helps run 5 by more than this AND the paired
# delta is significant. A margin alone is not enough -- D11's power lesson.
DENOISE_MARGIN = 1.0
T_SIGNIF = 2.0
# Smallest curve-shape difference worth acting on. Below this the test reports
# UNDERPOWERED rather than claiming a flat curve.
MIN_EFFECT_PTS = 3.0
# Below this many images an SE is estimated from too few paired differences to be worth
# quoting, so the power table refuses to print OK. Found by the n=2 smoke, which happily
# certified "detectable >= 1.02 pts OK" off two images.
MIN_N_FOR_POWER = 10
# ISO -- the run-11 isolation statistic, pre-registered in AGENTS.md's run-11 checklist
# BEFORE run 11 was analysed:
#     ISO(k) = delta_focus(k) - delta_reference(k),   delta_c(k) = recall_c(k) - recall_c(1.00)
# H1 ISOLATED requires ISO(k) <= -ISO_EFFECT_PTS with |t| >= T_SIGNIF at >= 1 of ISO_KEY_BUDGETS
# AND ISO <= 0 at every budget. Anything failing the resolution test is UNDERPOWERED, which is
# the DEFAULT outcome here, not a fallback.
ISO_EFFECT_PTS = 3.0
ISO_KEY_BUDGETS = (0.35, 0.20)
# --------------------------------------------------------------------------------

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=50, help="FUNSD test images (50 = full protocol)")
p.add_argument("--pair", choices=sorted(PAIRS), default=DEFAULT_PAIR,
               help="which two checkpoints to compare (default: %(default)s, D12's pair)")
p.add_argument("--selftest", action="store_true",
               help="execute every verdict branch against injected numbers and exit")
p.add_argument("--rescore", metavar="JSON", default=None,
               help="re-derive controls+verdict from a saved run's per-image recalls "
                    "(no model, no generation); writes why_pruning_helps_rescored.json")
args = p.parse_args()
RESCORE = os.path.abspath(args.rescore) if args.rescore else None
FUNSD_TEST_SIZE = 50          # fallback only, for JSONs written before test_set_size existed

_a, _b, FOCUS_SLOT, REF_SLOT, _out = PAIRS[args.pair]
CKPTS = [_a, _b]
# One output file per pair. Not a cosmetic choice: the default path holds D12's saved run and
# --rescore reads it, so writing run 11's numbers there would destroy the only local record of
# the comparison run 11 is differenced against.
OUT = os.path.join(ROOT, "results", _out)


def decide(d50, se50, t50):
    """The H1-vs-H2 verdict for run 5's keep=0.50 delta. Returns (tag, text).

    Factored out for one reason: the real path reaches this only if every control passes,
    so on any smoke run these branches are DEAD CODE. --selftest calls THIS function --
    not a copy of its logic -- with injected numbers, so all four branches are executed
    before a 1.8 h run depends on them. D11 shipped a verdict branch that had never run
    and it printed a confident null at SE 8.88; this is that lesson wired into the file.
    """
    mde50 = T_SIGNIF * se50
    if d50 > DENOISE_MARGIN and abs(t50) >= T_SIGNIF:
        return "H2", (
            f"H2 SUPPORTED. Run 5 was never trained with pruning, and removing half its "
            f"visual tokens still gains {d50:+.2f} pts (SE {se50:.2f}, t {t50:+.2f}). "
            f"Pruning is doing real work at inference, not just matching the training "
            f"budget. The deliverable's 'pruning helps' claim survives.")
    if d50 < -DENOISE_MARGIN and abs(t50) >= T_SIGNIF:
        return "H1", (
            f"H1 SUPPORTED, H2 REJECTED. Run 5 LOSES {d50:+.2f} pts when half its tokens "
            f"are removed (SE {se50:.2f}, t {t50:+.2f}), while run 9 -- trained at "
            f"keep=0.50 -- gains. So 'pruning helps' is train/test matching, NOT a "
            f"property of pruning. RESTATE THE DELIVERABLE: run 9's 77.62 unpruned score "
            f"is depressed because keep=1.00 is off-distribution for it, and its 80.46 at "
            f"keep=0.50 is a recovery, not a free lunch. The defensible claim becomes "
            f"'pruning to half the tokens costs nothing IF you train for it', which is "
            f"weaker and still worth having.")
    if mde50 > MIN_EFFECT_PTS:
        return "UNDERPOWERED", (
            f"UNDERPOWERED, not flat. Run 5's keep=0.50 delta is {d50:+.2f} pts with SE "
            f"{se50:.2f}, so nothing below {mde50:.2f} pts is detectable and neither "
            f"hypothesis is excluded. Do not report this as 'pruning is neutral'.")
    return "NEITHER", (
        f"NEITHER. Run 5's keep=0.50 delta is {d50:+.2f} pts (SE {se50:.2f}, t {t50:+.2f}) "
        f"-- inside the {DENOISE_MARGIN:.1f} pt margin with enough resolution "
        f"({mde50:.2f} pts) to have seen a real effect. Pruning is genuinely NEUTRAL for a "
        f"model not trained for it, which supports neither denoising nor a train/test "
        f"artifact as the explanation of run 9's gain.")


def decide_iso(rows, n_images):
    """Run 11's pre-registered verdict. `rows` = [(keep, iso_pts, se_pts, t), ...].

    Same discipline as decide() and for the same reason: on a smoke run every branch here is
    dead code, so --selftest executes THIS function with injected numbers before a 110-minute
    run depends on it. AGENTS.md records a verdict branch that shipped unexecuted and printed
    a confident null at SE 8.88.

    Branch order follows the checklist's acceptance table, which is deliberately NOT
    "significance first": UNDERPOWERED is the default outcome, and a flat ISO column is only
    evidence of no effect on rows that could have shown one. The one place significance wins
    over the power gate is a row that IS resolved at the key budgets -- a significant
    ISO <= -3.0 there cannot also be underpowered at that row.
    """
    if not rows:
        return "NO DATA", "no ISO rows were computed -- nothing to decide."
    unreliable = n_images < MIN_N_FOR_POWER
    powered = {k: (not unreliable) and T_SIGNIF * se <= ISO_EFFECT_PTS for k, _, se, _ in rows}
    hits = [(k, iso, se, t) for k, iso, se, t in rows
            if k in ISO_KEY_BUDGETS and iso <= -ISO_EFFECT_PTS and abs(t) >= T_SIGNIF]
    all_nonpos = all(iso <= 0.0 for _, iso, _, _ in rows)
    all_flat = all(abs(iso) < ISO_EFFECT_PTS for _, iso, _, _ in rows)

    if hits and all_nonpos and not unreliable:
        worst = min(hits, key=lambda r: r[1])
        return "H1 ISOLATED", (
            f"H1 ISOLATED. ISO is {worst[1]:+.2f} pts at keep={worst[0]:.2f} "
            f"(SE {worst[2]:.2f}, t {worst[3]:+.2f}) and <= 0 at every budget, so identical "
            f"pruning costs the FOCUS checkpoint more than the REFERENCE one with the epoch "
            f"count held constant. Pruning-aware training causes the robustness; Claim 1 may "
            f"say 'because it was trained for it'.")
    if all_flat and all(powered.values()):
        return "CONFOUNDED", (
            f"CONFOUNDED -- THE EPOCHS DID IT. |ISO| < {ISO_EFFECT_PTS:.1f} pts at every "
            f"budget and every row is resolved to better than that, so the focus checkpoint "
            f"got the reference checkpoint's budget-robustness WITHOUT the pruning. Claim 1's "
            f"attribution is wrong: 'if you train for it' has to become 'if you train longer'.")
    if unreliable or not all(powered.values()):
        blind = [f"keep={k:.2f} (>= {T_SIGNIF * se:.2f} pts)"
                 for k, _, se, _ in rows if not powered[k]]
        why = (f"n={n_images} < {MIN_N_FOR_POWER}, so every SE is itself noise"
               if unreliable else "rows that could not have seen a 3-pt effect: "
               + ", ".join(blind))
        return "UNDERPOWERED", (
            f"UNDERPOWERED, not flat -- {why}. Neither outcome is excluded. Report the ISO "
            f"table with resolution_pts and choose nothing.")
    return "MIXED", (
        f"MIXED -- the ISO column is resolved but matches no pre-registered outcome: it is "
        f"neither flat within {ISO_EFFECT_PTS:.1f} pts nor a significant <= "
        f"-{ISO_EFFECT_PTS:.1f} at keep in {ISO_KEY_BUDGETS} with ISO <= 0 throughout. "
        f"Read the table; do not force it into H1 ISOLATED or CONFOUNDED.")


if args.selftest:
    # (d50, se50, t50, expected tag). Each row is chosen to land in exactly one branch,
    # and the last two are the pair that actually matters: same near-zero delta, but one
    # measured precisely and one not. If both returned the same tag the power logic would
    # be decorative.
    CASES = [
        (+4.50, 1.20, +3.75, "H2"),            # clear gain, well resolved
        (-4.50, 1.20, -3.75, "H1"),            # clear loss, well resolved
        (+8.00, 9.00, +0.89, "UNDERPOWERED"),  # big delta, no resolution -> NOT a verdict
        (-0.30, 5.00, -0.06, "UNDERPOWERED"),  # flat but blind
        (-0.30, 0.40, -0.75, "NEITHER"),       # flat AND sharp -> a real null
        (+1.00, 0.40, +2.50, "NEITHER"),       # exactly ON the margin -> must not fire H2
    ]
    bad = 0
    print("verdict-branch selftest (executing decide(), not a copy):")
    for d, se, t, want in CASES:
        tag, text = decide(d, se, t)
        ok = tag == want
        bad += not ok
        print(f"  [{'ok  ' if ok else 'FAIL'}] d={d:+6.2f} se={se:5.2f} t={t:+6.2f} "
              f"-> {tag:13s} (want {want})")
        if not ok:
            print(f"         text was: {text[:100]}")
    hit = {decide(d, se, t)[0] for d, se, t, _ in CASES}
    for tag in ("H2", "H1", "UNDERPOWERED", "NEITHER"):
        if tag not in hit:
            print(f"  [FAIL] branch {tag} was never executed by any case")
            bad += 1

    # ISO branches. Each case is a full four-budget column, because decide_iso() reads the
    # column as a whole -- "all budgets <= 0" and "every row powered" cannot be exercised by a
    # single row. Budgets match BUDGETS so the key-budget filter is live.
    ISO_CASES = [
        # (label, n, [(keep, iso, se, t)], want)
        ("run-11 prediction: hurt more at tight budgets", 50, [
            (0.50, -1.10, 0.80, -1.38), (0.35, -5.20, 1.10, -4.73),
            (0.25, -7.40, 1.20, -6.17), (0.20, -9.10, 1.30, -7.00)], "H1 ISOLATED"),
        ("epochs did it: flat and resolved", 50, [
            (0.50, +0.40, 0.90, +0.44), (0.35, -0.80, 1.00, -0.80),
            (0.25, +1.20, 1.10, +1.09), (0.20, -1.50, 1.20, -1.25)], "CONFOUNDED"),
        ("flat but blind: one wide row", 50, [
            (0.50, +0.40, 0.90, +0.44), (0.35, -0.80, 1.00, -0.80),
            (0.25, +1.20, 1.10, +1.09), (0.20, -1.50, 2.60, -0.58)], "UNDERPOWERED"),
        ("big effect, no resolution", 50, [
            (0.50, -6.00, 8.00, -0.75), (0.35, -7.00, 9.00, -0.78),
            (0.25, -8.00, 9.50, -0.84), (0.20, -9.00, 9.90, -0.91)], "UNDERPOWERED"),
        ("n too small for any SE to mean anything", 2, [
            (0.50, -5.00, 0.10, -50.0), (0.35, -6.00, 0.10, -60.0),
            (0.25, -7.00, 0.10, -70.0), (0.20, -8.00, 0.10, -80.0)], "UNDERPOWERED"),
        ("significant at 0.35 but ISO POSITIVE at 0.50 -> not H1", 50, [
            (0.50, +4.00, 1.00, +4.00), (0.35, -5.00, 1.00, -5.00),
            (0.25, -5.50, 1.10, -5.00), (0.20, -6.00, 1.20, -5.00)], "MIXED"),
        ("big only at keep=0.50, which is NOT a key budget", 50, [
            (0.50, -4.00, 1.00, -4.00), (0.35, -1.00, 1.00, -1.00),
            (0.25, -0.50, 1.00, -0.50), (0.20, -0.20, 1.00, -0.20)], "MIXED"),
        ("exactly ON the -3.0 margin at a key budget -> must fire H1", 50, [
            (0.50, -1.00, 0.80, -1.25), (0.35, -3.00, 1.00, -3.00),
            (0.25, -3.10, 1.00, -3.10), (0.20, -3.20, 1.00, -3.20)], "H1 ISOLATED"),
    ]
    print("\nISO-branch selftest (executing decide_iso(), not a copy):")
    for lbl, ncase, rows, want in ISO_CASES:
        tag, text = decide_iso(rows, ncase)
        ok = tag == want
        bad += not ok
        print(f"  [{'ok  ' if ok else 'FAIL'}] {lbl[:52]:52s} -> {tag:13s} (want {want})")
        if not ok:
            print(f"         text was: {text[:120]}")
    hit_iso = {decide_iso(r, nc)[0] for _, nc, r, _ in ISO_CASES}
    for tag in ("H1 ISOLATED", "CONFOUNDED", "UNDERPOWERED", "MIXED"):
        if tag not in hit_iso:
            print(f"  [FAIL] ISO branch {tag} was never executed by any case")
            bad += 1
    if decide_iso([], 50)[0] != "NO DATA":
        print("  [FAIL] empty-rows guard did not fire")
        bad += 1

    # The arithmetic identity every ISO row is asserted against at run time, checked here on
    # numbers instead of trusting the assert to be reached: mean of per-image ISO must equal
    # the difference of the two separately-computed delta means.
    _rng = np.random.default_rng(11)
    _f1, _f0, _r1, _r0 = (_rng.normal(size=50) for _ in range(4))
    _iso_direct = float(np.mean((_f1 - _f0) - (_r1 - _r0)))
    _iso_diff = float(np.mean(_f1 - _f0)) - float(np.mean(_r1 - _r0))
    if abs(_iso_direct - _iso_diff) > 1e-9:
        print(f"  [FAIL] ISO identity broke: {_iso_direct} vs {_iso_diff}")
        bad += 1
    else:
        print(f"  [ok  ] ISO identity holds on random data "
              f"(|gap| {abs(_iso_direct - _iso_diff):.2e})")

    print(f"\n  {'PASS -- all branches executed and separated' if not bad else f'{bad} PROBLEM(S)'}")
    raise SystemExit(1 if bad else 0)

for _lbl, _pth in CKPTS:
    if not os.path.exists(_pth):
        raise SystemExit(f"missing checkpoint for {_lbl}: {_pth}")

try:
    import editdistance  # noqa: F401
except ImportError:
    raise SystemExit(
        "editdistance is MISSING -- compute_word_metrics/compute_ned would fall back to a "
        "length-difference approximation and the harness anchor against run 6 would be "
        "meaningless. Install it before running."
    )


def load_notebook_metrics():
    """exec the REAL metric defs out of the notebook so they cannot drift."""
    nb = json.loads(open(NOTEBOOK, encoding="utf-8").read())
    cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    ns, found = {}, set()
    wanted = {"reading_order_words", "compute_word_metrics", "compute_ned"}
    for src in cells:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue                       # the pip cell is never valid Python
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add(node.name)
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MAX_WORDS" for t in node.targets
            ):
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add("MAX_WORDS")
    missing = (wanted | {"MAX_WORDS"}) - found
    if missing:
        raise SystemExit(f"could not extract {sorted(missing)} from {NOTEBOOK}")
    return ns


NB = load_notebook_metrics()
reading_order_words = NB["reading_order_words"]
compute_word_metrics = NB["compute_word_metrics"]
compute_ned = NB["compute_ned"]
MAX_WORDS = NB["MAX_WORDS"]

from datasets import load_dataset            # noqa: E402
from transformers import DonutProcessor      # noqa: E402
import transformers                          # noqa: E402

from src.model import AdaptiveDonutOCR       # noqa: E402

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("=" * 78)
print("WHY DOES PRUNING HELP? -- H1 train/test matching vs H2 inference-time denoising")
print("=" * 78)
print(f"  device {device} | transformers {transformers.__version__} | "
      f"MAX_WORDS={MAX_WORDS} MAX_LEN={MAX_LEN}")
print(f"  selector '{SELECT_MODE}' (weight-independent -> identical tokens for both "
      f"checkpoints)")
print(f"  budgets keep=1.00 + {BUDGETS}")
print("  H1 predicts run 5 PEAKS at keep=1.00.  H2 predicts run 5 IMPROVES under pruning.")

if RESCORE:
    # Re-derive controls + verdict from a saved run's per-image recalls, without paying the
    # 1.8 h of generation again. This exists because the harness-anchor gate only executes
    # at n == len(ds): a smoke run takes the SKIP branch, so the branch that actually gates
    # the verdict would otherwise never run before I depended on it. Same `analyse` code as
    # the live path -- not a reimplementation, which is the whole point.
    _blob = json.load(open(RESCORE, encoding="utf-8"))
    RESULTS = {}
    for _row in _blob["rows"]:
        RESULTS.setdefault(_row["checkpoint"], {})[
            (_row["keep_ratio"], _row["select_mode"])] = _row
    n = _blob["meta"]["num_eval_samples"]
    N_TOTAL = _blob["meta"].get("test_set_size")
    if N_TOTAL is None:
        N_TOTAL = FUNSD_TEST_SIZE
        print(f"  NOTE: {os.path.basename(RESCORE)} predates the `test_set_size` field; "
              f"falling back to the known FUNSD test size {FUNSD_TEST_SIZE}.")
    print(f"  RESCORE from {os.path.relpath(RESCORE, ROOT)} -- n={n} of {N_TOTAL}, "
          f"written {_blob['meta'].get('written', '?')}. No model, no generation.")
    # --rescore used to ignore --pair, so rescoring anything but the default pair's artifact
    # died on a bare `KeyError: 'run 5 (no pruning in training)'` 200 lines in. The saved
    # blob names its own pair, so adopt it: the file, not the flag, is the authority on which
    # checkpoints produced these rows.
    _saved_pair = _blob["meta"].get("pair")
    if _saved_pair and _saved_pair in PAIRS and _saved_pair != args.pair:
        _a, _b, FOCUS_SLOT, REF_SLOT, _out = PAIRS[_saved_pair]
        CKPTS = [_a, _b]
        print(f"  pair taken from the file: {_saved_pair} (overriding --pair {args.pair})")
    _have, _want = set(RESULTS), {lbl for lbl, _ in CKPTS}
    if _have != _want:
        raise SystemExit(
            f"rescore pair mismatch: {os.path.basename(RESCORE)} holds {sorted(_have)} but "
            f"the selected pair is {sorted(_want)}. Pass --pair for the pair that produced "
            f"this file (choices: {', '.join(sorted(PAIRS))})."
        )
    # One rescore output per pair, for the same reason the live path has one per pair: the
    # default name holds D12's rescored artifact.
    OUT = os.path.join(ROOT, "results", (
        "why_pruning_helps_rescored.json" if (_saved_pair or args.pair) == DEFAULT_PAIR
        else f"why_pruning_helps_rescored_{_saved_pair or args.pair}.json"))
else:
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
    model.eval()

    ds = load_dataset("nielsr/funsd", split="test")
    n = min(args.n, len(ds))
    N_TOTAL = len(ds)
    prompt_ids = processor.tokenizer(
        TASK_PROMPT, add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)

    # PIL images, not pixel tensors: 1x3x2560x1920 fp32 is 56 MB, so caching 50 would cost
    # ~2.8 GB alongside the model. Re-preprocessing is deterministic and costs ~0.2 s.
    GOLD = []
    for i in range(n):
        s = ds[i]
        words = s.get("words", [])
        boxes = s.get("bboxes") or s.get("boxes")
        gt = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
        GOLD.append((s["image"].convert("RGB"), gt, json.dumps({"text": " ".join(gt)})))
    print(f"  {n} FUNSD test images, gold capped at MAX_WORDS={MAX_WORDS}")


def run_eval(keep_ratio, select_mode):
    """One (budget, mode) row. Keeps per-image recall so every delta gets an SE."""
    per_recall, per_ned, inks, lats, gen_toks = [], [], [], [], []
    kept = None
    for img, gt_words, gt_str in GOLD:
        pv = processor(img, return_tensors="pt").pixel_values.to(device)
        t0 = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,
                merge_ratio=0.0, max_length=MAX_LEN, select_mode=select_mode,
            )
        lats.append((time.perf_counter() - t0) * 1000.0)
        kept = meta["compressed_tokens"]
        if meta.get("retained_ink") is not None:
            inks.append(float(meta["retained_ink"]))
        gen_toks.append(int(gen_ids.shape[-1]))
        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()
        r, _o = compute_word_metrics(pred, gt_words)
        per_recall.append(float(r))
        per_ned.append(float(compute_ned(pred, gt_str)))
    return {
        "keep_ratio": keep_ratio,
        "select_mode": select_mode,
        "visual_tokens": kept,
        "word_recall_pct": float(np.mean(per_recall) * 100.0),
        "mean_ned": float(np.mean(per_ned)),
        "retained_ink": float(np.mean(inks)) if inks else None,
        "mean_gen_tokens": float(np.mean(gen_toks)),
        "avg_latency_ms": float(np.mean(lats)),
        "num_eval_samples": n,
        "per_image_recall": per_recall,
    }


CONFIGS = [(1.00, "router")] + [(k, SELECT_MODE) for k in BUDGETS]

t_start = time.time()
if not RESCORE:
    RESULTS = {}                       # NOT unconditional: RESCORE already populated it
for ci, (label, path) in enumerate([] if RESCORE else CKPTS):
    sd = torch.load(path, map_location=device, weights_only=True)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing or unexpected:
        raise SystemExit(
            f"refusing to eval a partially-loaded model for {label}: "
            f"missing={len(missing)} unexpected={len(unexpected)}"
        )
    model.eval()
    print(f"\n{'-' * 78}\n{label}  <- {os.path.relpath(path, ROOT)}  "
          f"(missing=0, unexpected=0)\n{'-' * 78}")
    RESULTS[label] = {}
    for keep, mode in CONFIGS:
        row = run_eval(keep, mode)
        RESULTS[label][(keep, mode)] = row
        ink = "  -  " if row["retained_ink"] is None else f"{row['retained_ink']:.3f}"
        done = ci * len(CONFIGS) + len(RESULTS[label])
        eta = (time.time() - t_start) / done * (2 * len(CONFIGS) - done) / 60.0
        print(f"  keep={keep:.2f} {mode:6s} recall {row['word_recall_pct']:6.2f}  "
              f"ink {ink}  tok {row['visual_tokens']:4d}  "
              f"{row['avg_latency_ms'] / 1000:5.1f}s/img   ETA {eta:5.1f} min", flush=True)

A, B = CKPTS[0][0], CKPTS[1][0]          # A = run 5, B = run 9

# Every significance star in this file is computed from a paired SE, so all of them inherit
# the small-n problem the power table guards against -- the n=2 smoke starred t=+25.55 off
# an SE of 0.21, two images that happened to move together. One flag, read by every star
# site, rather than a guard on one of the three readers.
STAR_OK = None                            # set once n is known, below


def star(t):
    if not STAR_OK:
        return ""
    return " *" if abs(t) >= T_SIGNIF else ""


def paired(recalls_a, recalls_b):
    """mean(b - a) in points, its SE, and t. Both lists are the same images in order."""
    a = np.asarray(recalls_a) * 100.0
    b = np.asarray(recalls_b) * 100.0
    d = b - a
    se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else float("nan")
    t = float(d.mean() / se) if se and se == se and se > 0 else float("nan")
    return float(d.mean()), se, t


def vs_unpruned(label, keep):
    """recall(keep) - recall(1.00) on ONE checkpoint. The curve-shape quantity."""
    return paired(RESULTS[label][(1.00, "router")]["per_image_recall"],
                  RESULTS[label][(keep, SELECT_MODE)]["per_image_recall"])


STAR_OK = n >= MIN_N_FOR_POWER

print("\n" + "=" * 78)
print("THE CURVES -- recall vs budget, identical ink-selected tokens, paired per image")
print("=" * 78)
for label in (A, B):
    ceil = RESULTS[label][(1.00, "router")]["word_recall_pct"]
    print(f"\n  {label}   unpruned ceiling {ceil:.2f}")
    print(f"    {'keep':>5s} {'tok':>5s} {'recall':>7s} {'vs 1.00':>8s} {'SE':>5s} "
          f"{'t':>6s}  {'ink':>5s}")
    print(f"    {1.00:5.2f} {4800:5d} {ceil:7.2f} {'--':>8s} {'--':>5s} {'--':>6s}  "
          f"{'1.000':>5s}")
    for keep in BUDGETS:
        r = RESULTS[label][(keep, SELECT_MODE)]
        d, se, t = vs_unpruned(label, keep)
        print(f"    {keep:5.2f} {r['visual_tokens']:5d} {r['word_recall_pct']:7.2f} "
              f"{d:+8.2f} {se:5.2f} {t:+6.2f}{star(t):2s} {r['retained_ink']:5.3f}")
if STAR_OK:
    print(f"\n  (* = |t| >= {T_SIGNIF}, pre-registered. 'vs 1.00' is paired within a "
          f"checkpoint: same images, same weights, only the budget differs.)")
else:
    print(f"\n  (stars SUPPRESSED: n={n} < {MIN_N_FOR_POWER}, so every SE above is itself "
          f"noise and no t is quotable. 'vs 1.00' is paired within a checkpoint.)")

verdicts = []


def say(ok, title, detail):
    """ok=True PASS, ok=False FAIL (blocks the verdict), ok=None SKIP.

    SKIP exists because one control below is only *meaningful* on the full test set, and a
    control that cannot pass on the data at hand is not a control -- it is a guaranteed
    red light that would hide every real failure behind it. SKIP is deliberately NOT a
    pass: it is recorded as skipped in the JSON and printed with the reason it could not
    run, so a green sheet can never silently contain one.
    """
    tag = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    verdicts.append({"check": title, "pass": None if ok is None else bool(ok),
                     "skipped": ok is None, "detail": detail})
    print(f"  [{tag}] {title}: {detail}")


print("\n" + "=" * 78)
print("CONTROLS")
print("=" * 78)
controls_ok = True

# (1) SELECTION HELD FIXED. Ink ranks patches by pixel contrast, so retained_ink must be
# identical across the two checkpoints at each budget. If it is not, the selector is
# reading the weights somehow and the whole weights-only interpretation collapses.
for keep in BUDGETS:
    ia = RESULTS[A][(keep, SELECT_MODE)]["retained_ink"]
    ib = RESULTS[B][(keep, SELECT_MODE)]["retained_ink"]
    if ia is None or ib is None:
        say(False, f"selection fixed keep={keep:.2f}",
            "retained_ink is None -- cannot verify the token set was held fixed")
        controls_ok = False
        continue
    gap = abs(ia - ib)
    ok = gap < 1e-6
    controls_ok &= ok
    say(ok, f"selection fixed keep={keep:.2f}",
        f"ink {ia:.6f} vs {ib:.6f} -> |gap| {gap:.2e} (must be ~0: same tokens)")

# (2) The ink selection is the same one Kaggle measured.
for keep, kag in sorted(KAGGLE_INK_ORACLE.items(), reverse=True):
    got = RESULTS[A][(keep, SELECT_MODE)]["retained_ink"]
    gap = abs(got - kag)
    ok = gap <= INK_TOL
    controls_ok &= ok
    say(ok, f"ink oracle keep={keep:.2f}",
        f"local {got:.3f} vs Kaggle {kag:.3f} -> |gap| {gap:.3f} (tol {INK_TOL:.2f})")

# (3) HARNESS ANCHOR. The local harness (metrics, prompt, decoding, data) must be sound or
# nothing here is interpretable. This originally compared local run 5 @ keep=1.00 to run 6's
# Kaggle 77.74 within 1.5 pts, and that was the wrong anchor twice over:
#   - The n=2 smoke made it an automatic FAIL (local 82.61, gap 4.87) by comparing a 2-image
#     mean to a 50-image one -- a tolerance narrower than the sampling noise it bounds.
#   - At n=50 it STILL failed (local 74.72, gap 3.02), and that one is not a sample-size
#     artifact: D11 established that generation does NOT reproduce across environments while
#     selection does (up to 3.4 pts on bit-identical token sets). The 1.5-pt tolerance came
#     from a +0.32 drift measured on run 9's weights and was applied to run 5's. This very
#     file's JSON says `not_comparable_to_kaggle_in_level` and then gated on the level.
# So the gate moves to a LIKE-FOR-LIKE reproduction with no environment change: run 9 at
# keep=1.00 was measured by D11 at 77.62 on this device, this transformers, these 50 images,
# greedy decode -- so re-measuring it here must reproduce. Pre-registered before the number
# existed (see AGENTS.md). The Kaggle comparison stays, printed but informational.
D11_LOCAL_RUN9_KEEP1 = 77.62
REPRO_TOL = 0.5

# The gate is a LIKE-FOR-LIKE local reproduction, so it is keyed to the checkpoint, not to a
# slot. It used to read RESULTS[B] on the assumption that slot B is always run 9; run 11's
# second pair is (run 5, run 11) and neither slot is run 9, so that assumption would have
# compared run 11's first-ever measurement against run 9's 77.62 and FAILED the whole sheet --
# a control that fires on the wrong thing, which is worse than no control. Both numbers below
# were measured locally on this device / transformers / these 50 images (D11 and D12).
# Run 11 has no anchor by construction: nothing has measured it locally before now.
LOCAL_ANCHORS = {
    CK_RUN9[0]: (D11_LOCAL_RUN9_KEEP1, "D11/D12"),
    CK_RUN5[0]: (74.72, "D12"),
}
_anchored = [lbl for lbl in (A, B) if lbl in LOCAL_ANCHORS]
if not _anchored:
    # Not a SKIP: a pair with no local anchor at all has no harness check, and that must be
    # loud rather than absent. No configured pair reaches this, which is why it is asserted.
    say(False, "harness anchor",
        f"neither {A!r} nor {B!r} has a pre-registered local keep=1.00 anchor, so the "
        f"measurement itself is unchecked and no row here is interpretable")
    controls_ok = False
for _lbl in _anchored:
    _ref, _src = LOCAL_ANCHORS[_lbl]
    _got = RESULTS[_lbl][(1.00, "router")]["word_recall_pct"]
    _gap = abs(_got - _ref)
    if n < N_TOTAL:
        say(None, f"harness anchor ({_lbl.strip()} @ keep=1.00 reproduces {_src})",
            f"local {_got:.2f} over n={n} vs {_src} {_ref:.2f} over {N_TOTAL} -- "
            f"|gap| {_gap:.2f}, NOT COMPARABLE (different image sets). Needs --n {N_TOTAL}.")
    else:
        ok = _gap <= REPRO_TOL
        controls_ok &= ok
        say(ok, f"harness anchor ({_lbl.strip()} @ keep=1.00 reproduces {_src})",
            f"local {_got:.2f} vs {_src} local {_ref:.2f} -> |gap| {_gap:.2f} "
            f"(tol {REPRO_TOL:.1f}; same device/transformers/images, so this must reproduce)")
for _lbl in (A, B):
    if _lbl not in LOCAL_ANCHORS:
        print(f"  [INFO] {_lbl.strip()} @ keep=1.00 = "
              f"{RESULTS[_lbl][(1.00, 'router')]['word_recall_pct']:.2f}: no prior local "
              f"measurement exists to reproduce, so this is a first reading, not a check.")

got = RESULTS[A][(1.00, "router")]["word_recall_pct"]
gap = abs(got - RUN6_REFERENCE_RECALL)
print(f"  [INFO] {A.strip()} @ keep=1.00: local {got:.2f} vs Kaggle run 6 "
      f"{RUN6_REFERENCE_RECALL:.2f} -> |gap| {gap:.2f}. INFORMATIONAL ONLY -- D11 showed "
      f"generation does not reproduce across environments (levels drift up to 3.4 pts on "
      f"bit-identical selections), and the reference is run-5-specific. Gates nothing.")

# (4) POWER. Same discipline as D11: a flat curve is only evidence of flatness if the
# test could have seen a MIN_EFFECT_PTS bend in it. With one addition the smoke forced --
# at n=2 this loop printed "SE 0.51 detectable >= 1.02 OK" for run 9 at keep=0.25, i.e. it
# certified resolution off two images that happened to move together. An SE estimated from
# a handful of points is itself mostly noise, so below MIN_N_FOR_POWER no row may read OK.
print(f"\n  resolution -- smallest detectable 'vs 1.00' delta at |t|={T_SIGNIF:.0f} "
      f"(want <= {MIN_EFFECT_PTS:.1f} pts):")
POWER = {}
for label in (A, B):
    for keep in BUDGETS:
        _, se, _ = vs_unpruned(label, keep)
        POWER[(label, keep)] = T_SIGNIF * se
        if n < MIN_N_FOR_POWER:
            tag = f"SE UNRELIABLE (n={n} < {MIN_N_FOR_POWER})"
        else:
            tag = "OK" if T_SIGNIF * se <= MIN_EFFECT_PTS else "UNDERPOWERED"
        print(f"    {label[:6]} keep={keep:.2f}  SE {se:5.2f}  "
              f"detectable >= {T_SIGNIF * se:5.2f} pts  {tag}")

# ------------------------------------------------------------------- ISO (run 11)
# The isolation statistic. Printed OUTSIDE the controls gate on purpose: this table costs 110
# minutes of generation to produce, and suppressing it on a control failure would mean paying
# that and learning nothing. The banner says what a failed control does to its readability --
# it does not turn a red light green.
FOCUS = {"A": A, "B": B}[FOCUS_SLOT]
REF = {"A": A, "B": B}[REF_SLOT]


def per_image_delta(label, keep):
    """delta_c(k) per image, in points: recall_c(k) - recall_c(1.00). Same images, same order."""
    base = np.asarray(RESULTS[label][(1.00, "router")]["per_image_recall"]) * 100.0
    cur = np.asarray(RESULTS[label][(keep, SELECT_MODE)]["per_image_recall"]) * 100.0
    return cur - base


ISO_ROWS = []
for keep in BUDGETS:
    _df, _dr = per_image_delta(FOCUS, keep), per_image_delta(REF, keep)
    _per = _df - _dr
    _m = float(_per.mean())
    _se = (float(_per.std(ddof=1) / np.sqrt(len(_per))) if len(_per) > 1 else float("nan"))
    _t = float(_m / _se) if _se == _se and _se > 0 else float("nan")
    # Why the correlation is reported and not just the SE: Var(ISO) = Var(d_f) + Var(d_r)
    # - 2*Cov, so ISO's resolution is set by how similarly the two checkpoints move
    # IMAGE BY IMAGE, not by their means. On D12's run-5/run-9 pair rho was 0.14-0.57 and
    # every ISO row came out UNDERPOWERED at n=50; reaching resolution <= 3.0 pts on these
    # per-image spreads needs rho ~ 0.78-0.89. n cannot be raised -- 50 IS the FUNSD test
    # split -- so this column is the only thing that decides whether a flat ISO here can
    # ever be read as CONFOUNDED rather than as blind.
    _rho = (float(np.corrcoef(_df, _dr)[0, 1]) if len(_per) > 2 and _df.std() > 0
            and _dr.std() > 0 else float("nan"))
    # Pre-registered control: "every DiD mean asserted equal to the difference of the two
    # separately-computed deltas". The paired route (mean of per-image ISO) and the unpaired
    # route (difference of the two delta means) are algebraically identical, so a mismatch
    # means the two checkpoints' per-image lists are not the same images in the same order --
    # which is the one failure mode that would make every ISO row silently meaningless.
    _mf, _mr = vs_unpruned(FOCUS, keep)[0], vs_unpruned(REF, keep)[0]
    _gap = abs(_m - (_mf - _mr))
    if not (_gap <= 1e-9):
        raise SystemExit(
            f"ISO arithmetic FAILED at keep={keep:.2f}: paired mean {_m:.6f} != "
            f"delta_focus - delta_ref {_mf - _mr:.6f} (|gap| {_gap:.2e}). The per-image lists "
            f"are not aligned across checkpoints; every ISO row would be meaningless."
        )
    ISO_ROWS.append({"keep_ratio": keep, "iso_pts": _m, "se_pts": _se, "t": _t,
                     "resolution_pts": T_SIGNIF * _se,
                     "delta_focus_pts": _mf, "delta_reference_pts": _mr,
                     "per_image_corr": _rho,
                     "sd_delta_focus": float(_df.std(ddof=1)),
                     "sd_delta_reference": float(_dr.std(ddof=1)),
                     "identity_gap": _gap})

print("\n" + "=" * 78)
print(f"ISO -- the isolation statistic:  ISO(k) = delta[{FOCUS.strip()}](k) - "
      f"delta[{REF.strip()}](k)")
print("=" * 78)
if not controls_ok:
    print("  !! A CONTROL FAILED ABOVE. These rows are printed so the 110 minutes are not")
    print("  !! wasted, but they are NOT a weights-only comparison until that control passes.")
print(f"  delta_c(k) = recall_c(k) - recall_c(1.00), paired per image, {SELECT_MODE} tokens.")
print(f"  Negative ISO = the focus checkpoint is hurt MORE by identical pruning.")
print(f"    {'keep':>5s} {'d_focus':>8s} {'d_ref':>8s} {'ISO':>8s} {'SE':>5s} {'t':>6s} "
      f"{'resolution':>11s} {'rho':>5s}  power")
for r in ISO_ROWS:
    _pw = ("SE UNRELIABLE" if n < MIN_N_FOR_POWER else
           ("OK" if r["resolution_pts"] <= ISO_EFFECT_PTS else "UNDERPOWERED"))
    print(f"    {r['keep_ratio']:5.2f} {r['delta_focus_pts']:+8.2f} "
          f"{r['delta_reference_pts']:+8.2f} {r['iso_pts']:+8.2f} {r['se_pts']:5.2f} "
          f"{r['t']:+6.2f}{star(r['t']):2s}{r['resolution_pts']:9.2f} pts "
          f"{r['per_image_corr']:5.2f}  {_pw}")
print(f"  rho = per-image correlation of the two delta columns. It, not the means, sets the")
print(f"  resolution: on D12's run-5/run-9 pair rho was 0.14-0.57 and all four rows were")
print(f"  UNDERPOWERED. n cannot be raised; {N_TOTAL} IS the FUNSD test split.")
print(f"  identity check: max |paired ISO - (d_focus - d_ref)| = "
      f"{max(r['identity_gap'] for r in ISO_ROWS):.2e}  (asserted <= 1e-09)")

ISO_TAG, ISO_TEXT = decide_iso(
    [(r["keep_ratio"], r["iso_pts"], r["se_pts"], r["t"]) for r in ISO_ROWS], n)
print(f"\n  => {ISO_TAG}: {ISO_TEXT}")
if not controls_ok:
    ISO_TAG = f"WITHHELD ({ISO_TAG} on unverified rows)"
    print(f"  => recorded as {ISO_TAG!r}: a control failed, so the tag above is not a finding.")
if n < N_TOTAL:
    print(f"  (n={n} of {N_TOTAL} -- SUBSAMPLE. This is the ISO code path being exercised, "
          f"not a result.)")

print("\n" + "=" * 78)
print("THE ANSWER")
print("=" * 78)
VERDICT_TAG = "WITHHELD"
if not controls_ok:
    print("  WITHHELD. A control failed, so the curves above cannot be read as a "
          "weights-only comparison. Do not use them to choose between H1 and H2.")
else:
    # Where does each checkpoint peak?
    peaks = {}
    for label in (A, B):
        scores = {1.00: RESULTS[label][(1.00, "router")]["word_recall_pct"]}
        scores.update({k: RESULTS[label][(k, SELECT_MODE)]["word_recall_pct"]
                       for k in BUDGETS})
        peaks[label] = max(scores, key=scores.get)
        print(f"  {label}: peaks at keep={peaks[label]:.2f} "
              f"({scores[peaks[label]]:.2f})")

    d50, se50, t50 = vs_unpruned(A, 0.50)
    if A == CK_RUN5[0]:
        tag, text = decide(d50, se50, t50)
    else:
        # decide() is not a general verdict: every branch's prose is a claim about RUN 5 --
        # "a model that was never trained with pruning" is what makes it discriminate H1 from
        # H2. Applied to slot A of the run-11 pair it printed "Run 5's keep=0.50 delta is
        # +0.21" about run 11's delta, which is a false sentence in a saved artifact. So it is
        # suppressed rather than relabelled: H2 is not what this pair tests.
        tag = "N/A (H2 verdict is run-5-specific)"
        text = (f"H2 VERDICT SUPPRESSED. This pair's slot A is {A.strip()}, not run 5. H1-vs-H2 "
                f"turns on the curve of a checkpoint never trained with pruning, so decide() "
                f"has nothing to say here; its {d50:+.2f}-pt input is reported in the curve and "
                f"ISO tables instead. Read the ISO table -- that is this pair's question.")

    print()
    if n < N_TOTAL:
        print(f"  (n={n} of {N_TOTAL} -- SUBSAMPLE. The harness anchor was skipped and the "
              f"verdict below is a code path being exercised, not a result.)")
    print(f"  => {text}")
    VERDICT_TAG = tag

    print(f"\n  Did the retrain help, holding the token set fixed? "
          f"({B.strip()} - {A.strip()}, identical ink tokens)")
    for keep in BUDGETS:
        d, se, t = paired(RESULTS[A][(keep, SELECT_MODE)]["per_image_recall"],
                          RESULTS[B][(keep, SELECT_MODE)]["per_image_recall"])
        print(f"    keep={keep:.2f}  {d:+6.2f} pts  SE {se:5.2f}  t {t:+6.2f}{star(t)}")
    print("    SCOPE: these are LEVEL differences at a budget, not curve shapes -- they do "
          "NOT\n    subtract each checkpoint's own keep=1.00, so they are not ISO. Read the "
          "ISO table\n    above for the attribution; these rows only say a difference exists.")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "meta": {
            "purpose": "H1 train/test matching vs H2 inference-time denoising, via run 5",
            "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checkpoints": {lbl: os.path.relpath(pth, ROOT) for lbl, pth in CKPTS},
            "pair": args.pair,
            "focus": FOCUS,
            "reference": REF,
            "select_mode": SELECT_MODE,
            "select_mode_why": (
                "ink ranks patches by pixel contrast, so it is weight-independent and both "
                "checkpoints keep the identical token set -- every curve difference is "
                "attributable to the weights. Verified by control 1, not assumed."
            ),
            "num_eval_samples": n,
            "test_set_size": N_TOTAL,
            "device": str(device),
            "transformers": transformers.__version__,
            "torch": torch.__version__,
            "max_len": MAX_LEN,
            "max_words": MAX_WORDS,
            "notebook_metrics_from": os.path.basename(NOTEBOOK),
            "preregistered": {
                "run6_reference_recall": RUN6_REFERENCE_RECALL,
                "harness_tol_pts": HARNESS_TOL,
                "kaggle_ink_oracle": {str(k): v for k, v in KAGGLE_INK_ORACLE.items()},
                "ink_tol": INK_TOL,
                "denoise_margin_pts": DENOISE_MARGIN,
                "t_signif": T_SIGNIF,
                "min_effect_pts": MIN_EFFECT_PTS,
                "iso_effect_pts": ISO_EFFECT_PTS,
                "iso_key_budgets": list(ISO_KEY_BUDGETS),
                "local_anchors": {k: v[0] for k, v in LOCAL_ANCHORS.items()},
            },
            "controls_passed": controls_ok,
            "iso_verdict": ISO_TAG,
            "iso_verdict_text": ISO_TEXT,
            "controls_skipped": [v["check"] for v in verdicts if v.get("skipped")],
            "controls_passed_note": (
                "controls_passed reflects only the checks that RAN; read it together with "
                "controls_skipped, which is non-empty on any subsample run"
            ),
            "verdict": VERDICT_TAG,
            "is_full_protocol": n == N_TOTAL,
            "resolution_pts": {f"{lbl}|{k}": v for (lbl, k), v in POWER.items()},
            "min_n_for_power": MIN_N_FOR_POWER,
            "scope_limit": (
                "run 9 differs from run 5 by pruning-aware training AND 5 more epochs; "
                "cross-checkpoint rows do not isolate pruning as the cause"
            ),
            "not_comparable_to_kaggle_in_level": (
                "D11 measured local generation drifting up to 3.4 pts from Kaggle at tight "
                "budgets on bit-identical selections; within-checkpoint deltas are the "
                "comparable quantity"
            ),
        },
        "verdicts": verdicts,
        "rows": [{"checkpoint": lbl, **row}
                 for lbl in RESULTS for row in RESULTS[lbl].values()],
        "curve_vs_unpruned": [
            {"checkpoint": lbl, "keep_ratio": keep,
             "delta_pts": vs_unpruned(lbl, keep)[0],
             "se_pts": vs_unpruned(lbl, keep)[1],
             "t": vs_unpruned(lbl, keep)[2]}
            for lbl in (A, B) for keep in BUDGETS
        ],
        "iso": ISO_ROWS,
    }, f, indent=1)
print(f"\nwrote {os.path.relpath(OUT, ROOT)}   ({(time.time() - t_start) / 60:.1f} min)")
