"""Pending 11: prove the training loop's epoch line actually reports the saliency term.

Run 9 printed five epochs of `Avg Loss 0.3091 | CE 0.3091` -- identical to 4 dp -- which
reads exactly like "the saliency loss never ran". It is not: `epoch_loss` accumulates
`loss_dict['loss']` (the criterion's output) while `LAMBDA_SAL * _sal` is added to a
different variable, the `loss` that reaches `backward()`. With `lambda_sparsity` and
`lambda_entropy` both 0.0 in the supervised branch, the two printed columns are identical
BY CONSTRUCTION. The consequence is the defect this verifier exists to close: **the log
cannot distinguish LAMBDA_SAL=0.5 from LAMBDA_SAL=0**, so F1's central claim (the corrected
BCE descends where the double-sigmoid version floored at 0.313) has never been observed
directly in any run -- only inferred from downstream metrics, which D6 then showed move in
the opposite direction from the mechanism.

Every number the patched line prints is here because a specific past failure in this
project was invisible without it:

  Obj    no printed number equalled the objective `backward()` minimises   (Pending 11)
  CE     already printed                                                   --
  aux    D5: lambda_entropy=0.05 defaulted in and shaped runs 7-8 while appearing in no
         config cell. Nonzero `aux` makes that visible the epoch it happens.
  sal    Pending 11. Printed with LAMBDA_SAL and the step count, so the knob and the fact
         that the branch fired are both in the log (D5's lesson about invisible knobs).
  dev    mean |p - t|. After the D4 fix d(sal)/dz == p - t exactly, so this IS the
         gradient magnitude. Separates "loss is low" from "router agrees with targets".
  p      mean +- std of the scores. std -> 0 is constant-collapse, which makes `torch.topk`
         return the first K indices -- a structured-looking selection that is not learned
         at all, and silent. Mean drifting to 0.5 is D5's entropy concern.
  ov/ch  13(b). `ov` = the fraction of the target's positives that the router's OWN top-K
         keeps; `ch` = what a random top-K scores (i.e. the target's positive rate); `lift`
         = ov - ch. This exists because D6 left an ambiguity that cost a whole run: recall
         went DOWN and the log could not say whether the router had failed to learn the
         target or had learned it and the target was wrong. `ov` is the mechanism, recall is
         the goal, and they have to be measured separately.

Convention (as in every verifier here): assert a value the CORRECT implementation must
produce, not that the code runs. The epoch loop is EXTRACTED FROM THE NOTEBOOK AND
EXECUTED against a real AdaptivePruningLoss, a real GradScaler and a real AdamW -- never
paraphrased, or this file would verify itself instead of the thing that runs on Kaggle.

Eight assertions:

  G LOGGED        the epoch line reports a saliency value, and it matches an independently
                  computed BCE on the same scores and target.
  H IDENTITY      Obj == CE + aux + LAMBDA_SAL * sal, on a run where `aux` is nonzero so
                  the identity is not trivially satisfiable. Some printed number must
                  equal what backward() actually minimises.
  I DISCRIMINATING  LAMBDA_SAL=0.5 and LAMBDA_SAL=0.0 must print DIFFERENT lines. This is
                  the property whose absence made run 9's log uninterpretable, and the one
                  assertion that must fail on the pre-patch code.
  J LIVE          change the ink target, the reported sal must move. Guards against
                  logging a constant, a placeholder, or the wrong tensor.
  M SELECTION AGREEMENT  same differential test for `ov`. A column that is 1.000 by
                  construction prints the same 1.000 on a broken run, so inverting the
                  target must drive ov to ~0. Plus: `lift` must equal ov - ch, so the log
                  reports the score against its own baseline and not the raw number that
                  0.667-style inflated floors already made unreadable once here.
  K GRAD INTACT   telemetry must not detach the term: with LAMBDA_SAL>0 the scorer
                  parameter receives nonzero gradient, with LAMBDA_SAL=0 it does not.
                  This is the regression the patch itself could introduce.
  L PARITY        notebook and generator agree on the telemetry lines, or the next
                  regeneration silently reverts them.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_training_telemetry.py
Exit code 0 iff all of them pass.
"""
import ast
import io
import json
import os
import re
import sys
import textwrap
from contextlib import redirect_stdout

import torch
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

NB = os.path.join(ROOT, "kaggle_pruning_run.ipynb")
GEN = os.path.join(ROOT, "scripts", "make_kaggle_pruning_notebook.py")

B, N, T, V = 1, 8, 5, 11            # batch, visual tokens, target len, vocab
SALIENCY_THRESHOLD = 0.15           # cell 2
NSTEPS = 3
# The loop runs under torch.amp.autocast('cpu'), which is bfloat16 -- ~3 decimal digits.
# So G/J compare against a float32 expectation with a tolerance that reflects bf16, not
# a tolerance chosen to make the test pass. Measured discrepancy is ~1e-3; 0.02 leaves
# room without letting a wrong *quantity* through (logging CE instead of sal is off by
# whole tenths, and J's differential check is tighter than this bound anyway).
TOL_BF16 = 0.02

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# ------------------------------------------------------- extract the loop, verbatim
def extract_epoch_loop(src):
    """Everything from `for epoch in ...` up to the checkpoint save, dedented.

    Raises rather than silently checking nothing if the loop's shape changed.
    """
    lines = src.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if l.strip().startswith("for epoch in range(1, EPOCHS + 1):")), None)
    if start is None:
        raise SystemExit("could not find `for epoch in range(1, EPOCHS + 1):` in cell 11 "
                         "-- the training loop moved; re-derive this verifier")
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and (len(lines[i]) - len(lines[i].lstrip())) <= indent), None)
    if end is None:
        raise SystemExit("found the loop but not the statement after it")
    block = textwrap.dedent("\n".join(lines[start:end]))
    ast.parse(block)
    return block


cell11 = "".join(json.load(open(NB, encoding="utf-8"))["cells"][11]["source"])
loop = extract_epoch_loop(cell11)
print("=" * 78)
print("epoch loop EXTRACTED FROM kaggle_pruning_run.ipynb cell 11 (executed as-is)")
print("=" * 78)
for l in loop.splitlines():
    print(f"  | {l}")
print()


# ------------------------------------------------------------------------- stubs
class Tiny(torch.nn.Module):
    """Scores come from a real Parameter so K can read its gradient.

    `w` is the stand-in for the scorer's pre-sigmoid activation, so `sigmoid(w)` is what
    PatchSaliencyRouter returns and `d(sal)/dw` is the quantity D4 was about.
    """

    def __init__(self, score_logits):
        super().__init__()
        self.w = torch.nn.Parameter(torch.tensor(score_logits).reshape(1, N, 1))
        self.head = torch.nn.Linear(4, V)

    def forward(self, pixel_values=None, labels=None, decoder_input_ids=None):
        logits = self.head(torch.ones(B, T, 4))
        return {"logits": logits,
                "scores": torch.sigmoid(self.w),
                "loss": F.cross_entropy(logits.reshape(-1, V), labels.reshape(-1),
                                        ignore_index=-100),
                "compressed_tokens": N // 2, "original_tokens": N}


class RecordingAdamW(torch.optim.AdamW):
    """A real optimizer -- GradScaler.step/unscale_ touch internals -- that snapshots the
    scorer gradient before the loop zeroes it, so K can see it after the fact."""

    def __init__(self, params, watch, **kw):
        super().__init__(params, **kw)
        self.watch, self.trace = watch, []

    def zero_grad(self, *a, **kw):
        g = self.watch.grad
        self.trace.append(0.0 if g is None else float(g.abs().sum()))
        return super().zero_grad(*a, **kw)


class FakeBar(list):
    def set_postfix(self, *a, **kw):
        pass


SCORE_LOGITS = [3.0, 2.0, 1.0, 0.0, -1.0, -2.0, -3.0, 0.5]
INK_A = [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]     # roughly agrees with the scores
INK_B = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0]     # the inverse: sal must jump


def expected_sal(ink):
    """The BCE the block should be reporting, computed in float32 and independently."""
    p = torch.sigmoid(torch.tensor(SCORE_LOGITS)).reshape(1, N)
    t = (torch.tensor(ink).reshape(1, N) > SALIENCY_THRESHOLD).float()
    return float(F.binary_cross_entropy_with_logits(
        torch.logit(p.clamp(1e-6, 1 - 1e-6)), t))


def run_loop(lambda_sal, ink, lambda_entropy=0.0, epochs=1):
    """Execute the extracted loop and return (printed lines, parsed numbers, grad trace)."""
    from src.loss import AdaptivePruningLoss

    torch.manual_seed(0)
    model = Tiny(SCORE_LOGITS)
    opt = RecordingAdamW(model.parameters(), watch=model.w, lr=0.0)   # lr=0: scores fixed
    labels = torch.randint(0, V, (B, T))
    batch = {"pixel_values": torch.zeros(B, 3, 8, 8), "labels": labels,
             "decoder_input_ids": labels}
    ns = {
        "torch": torch, "F": F, "os": os,
        "EPOCHS": epochs, "train_loader": [batch] * NSTEPS,
        "device": torch.device("cpu"), "model": model, "optimizer": opt,
        "scaler": torch.amp.GradScaler("cpu"),
        "criterion": AdaptivePruningLoss(lambda_sparsity=0.0, lambda_entropy=lambda_entropy,
                                         target_budget=1.0, pad_token_id=-100),
        "patch_ink": lambda pv, n: torch.tensor(ink).reshape(1, N),
        "SALIENCY_THRESHOLD": SALIENCY_THRESHOLD,
        "LAMBDA_SAL": lambda_sal, "GRAD_ACCUM": 2,
        "tqdm": lambda it, **kw: FakeBar(it),
        # 13(b) put `if ATTN_TARGET:` in the saliency block this loop contains, so these
        # names are now free variables here. Bound to the ink path: this file's subject is
        # the telemetry and the accumulate/step arithmetic, both target-agnostic, and
        # verify_attn_target.py + verify_saliency_loss_cell.py cover the ATTN branch.
        "ATTN_TARGET": False,
        "TRAIN_KEEP_RATIO": 0.50,
        "attn_topk_target": None, "_teacher_dec": None,
    }
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(compile(loop, "<cell11-epoch-loop>", "exec"), ns)
    lines = [l for l in buf.getvalue().splitlines() if l.strip()]
    return lines, [parse(l) for l in lines], opt.trace


def parse(line):
    """Pull `key value` pairs out of an epoch line without pinning the exact format.

    The value pattern accepts a leading `+`: 13(b)'s `lift` is printed with an explicit
    sign (`lift +0.500`), and a `-?`-only pattern silently dropped that key -- which would
    have made M's `lift` check pass its `.get(default)` instead of reading the log.
    """
    return {k: float(v) for k, v in
            re.findall(r"\b([A-Za-z][A-Za-z_|+-]*)\s+([-+]?\d+\.\d+)", line)}


print("=" * 78)
print("ASSERTIONS")
print("=" * 78)

on_lines, on, on_grad = run_loop(0.5, INK_A)
off_lines, off, off_grad = run_loop(0.0, INK_A)
print(f"  LAMBDA_SAL=0.5 -> {on_lines[-1]}")
print(f"  LAMBDA_SAL=0.0 -> {off_lines[-1]}")
print()

# ------------------------------------------------------------------------ G  LOGGED
want = expected_sal(INK_A)
got = on[-1].get("sal")
check("G LOGGED", got is not None and abs(got - want) < TOL_BF16,
      f"line reports sal={got} vs independently computed {want:.4f} "
      f"(tol {TOL_BF16}, bf16 autocast)" if got is not None else
      f"NO saliency value in the epoch line -- expected ~{want:.4f}. "
      f"Line: {on_lines[-1]!r}")

# ---------------------------------------------------------------------- H  IDENTITY
# lambda_entropy=0.05 on purpose: `aux` is then nonzero, so the identity has to actually
# hold rather than collapsing to Obj == CE. This doubles as D5's regression guard.
aux_lines, aux, _ = run_loop(0.5, INK_A, lambda_entropy=0.05)
a = aux[-1]
have = {"Obj", "CE", "aux", "sal"} <= a.keys()
if have:
    lhs = a["Obj"]
    rhs = a["CE"] + a["aux"] + 0.5 * a["sal"]
    ok = abs(lhs - rhs) < 5e-4 and abs(a["aux"]) > 1e-6
    detail = (f"Obj {lhs:.4f} == CE {a['CE']:.4f} + aux {a['aux']:.4f} + 0.5*sal "
              f"{a['sal']:.4f} -> {rhs:.4f} (aux nonzero, so not trivial)")
else:
    ok, detail = False, (f"epoch line lacks {sorted({'Obj','CE','aux','sal'} - a.keys())}; "
                         f"no printed number equals the minimised objective. "
                         f"Line: {aux_lines[-1]!r}")
check("H IDENTITY", ok, detail)

# ----------------------------------------------------------------- I  DISCRIMINATING
same = on_lines[-1] == off_lines[-1]
check("I DISCRIMINATING", not same,
      "LAMBDA_SAL=0.5 and 0.0 print different lines"
      if not same else
      f"IDENTICAL lines at LAMBDA_SAL=0.5 and 0.0 -- this is the run-9 defect: the log "
      f"cannot tell whether the saliency term ran. {on_lines[-1]!r}")

# -------------------------------------------------------------------------- J  LIVE
b_lines, b, _ = run_loop(0.5, INK_B)
sa, sb = on[-1].get("sal"), b[-1].get("sal")
if sa is None or sb is None:
    check("J LIVE", False, "no sal value to compare across targets")
else:
    d_got, d_want = sb - sa, expected_sal(INK_B) - expected_sal(INK_A)
    check("J LIVE", abs(d_got - d_want) < TOL_BF16 and abs(d_want) > 0.1,
          f"inverting the ink target moves sal by {d_got:+.4f}; independently "
          f"{d_want:+.4f}. Not a constant.")

# ------------------------------------------------------- M  SELECTION AGREEMENT LIVE
# 13(b) added `ov`/`ch`/`lift`: the fraction of the target's positives the router's own
# top-K keeps, and what a random top-K would score. `ov` exists to make a null result
# readable -- it separates "the router never learned the target" from "it learned the
# target and recall did not improve". A column that is constant by construction would
# print the same 1.000 on a broken run, so assert it MOVES with the target, the same way
# J does for sal. INK_B is INK_A inverted, so a router that scored 1.000 on A must score
# near 0 on B; anything else means `ov` is reading the wrong tensor.
ov_a, ov_b = on[-1].get("ov"), b[-1].get("ov")
ch_a = on[-1].get("ch")
if ov_a is None or ov_b is None or ch_a is None:
    check("M SELECTION AGREEMENT", False,
          f"epoch line is missing ov/ch: {on_lines[-1]!r}")
else:
    check("M SELECTION AGREEMENT", abs(ov_a - ov_b) > 0.5 and 0.0 <= ov_b <= 1.0,
          f"inverting the target moves ov {ov_a:.3f} -> {ov_b:.3f} "
          f"(chance {ch_a:.3f}). Not a constant.")
    check("M LIFT IS ov MINUS ch",
          abs(on[-1].get("lift", 1e9) - (ov_a - ch_a)) < 2e-3,
          f"lift {on[-1].get('lift')} == ov {ov_a:.3f} - ch {ch_a:.3f}; the log reports "
          f"the number over its own random baseline, not the raw score "
          f"(tol 2e-3: three values each rounded to 3 dp)")

# ------------------------------------------------------------------- K  GRAD INTACT
gon, goff = max(on_grad or [0.0]), max(off_grad or [0.0])
check("K GRAD INTACT", gon > 1e-6 and goff < 1e-9,
      f"scorer |grad| sum: LAMBDA_SAL=0.5 -> {gon:.6f} (nonzero, term still reaches "
      f"backward), LAMBDA_SAL=0.0 -> {goff:.2e} (nothing else drives it)")

# ------------------------------------------------------------------------ L  PARITY
# Compare like with like: cell 11 holds TWO epoch loops (the DO_TRAIN branch the generator
# writes, and the original cell wrapped as the `else` branch), and the generator source
# holds only the first. Extracting both sides the same way scopes the comparison to the
# DO_TRAIN branch instead of matching the else branch's own print and reporting a phantom
# divergence -- which is what a whole-file regex did on the first attempt here.
gen_src = open(GEN, encoding="utf-8").read()
gen_loop = extract_epoch_loop(gen_src)


def telemetry_lines(s):
    """Accumulator and epoch-print statements, whitespace-normalised.

    Extended for 13(b): the `ov`/`ch` columns are computed by `_tgf`/`_rk`/`_st` lines that
    the original pattern did not name, so a regeneration could have reverted the new
    telemetry while L still reported parity on the old columns.
    """
    return [re.sub(r"\s+", " ", l).strip() for l in s.splitlines()
            if re.search(r"epoch_(sal|gap|pm|ps|ov|ch)|n_sal|_sal_msg|_tgf|_rk|\b_st\b", l)
            or l.strip().startswith("print(f'Epoch")]


nb_t, gen_t = telemetry_lines(loop), telemetry_lines(gen_loop)
check("L PARITY", bool(nb_t) and nb_t == gen_t,
      f"{len(nb_t)} telemetry line(s) identical in notebook and generator"
      if nb_t == gen_t else
      f"DIVERGED -- regenerating would revert the telemetry.\n"
      f"           notebook ({len(nb_t)}): {nb_t}\n"
      f"           generator ({len(gen_t)}): {gen_t}")

print()
print("=" * 78)
failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed"
      + (f" -- FAILING: {', '.join(failed)}" if failed else " -- all clear"))
print("=" * 78)
raise SystemExit(1 if failed else 0)
