"""Diagnostic D4 (2026-08-31): the ink-BCE saliency loss is fed a probability, not a logit.

Booked while checking a *different* claim. D3 recorded that runs 7 -> 8 moved two knobs
at once (BCE on, sparsity off). Verifying that against `kaggle_pruning_run.ipynb` cell 11
turned up something else: the loss reads

    _sal = F.binary_cross_entropy_with_logits(_sc.squeeze(-1), _tgt)

where `_sc` is `outputs['scores']` -- and `PatchSaliencyRouter.scorer` ends in
`nn.Sigmoid()` (`src/router.py:25`, identical in the notebook's own copy). So an
already-squashed probability in (0, 1) is being passed to a function whose first act is
to squash it again. A double sigmoid.

This is not a crash and not a silent no-op, which is why it survived: sigmoid is
monotone, so the gradient SIGN is right and the ranking is still learnable. Run 8's
sign-fix is real (`negated` collapsing 73.09 -> 2.70 cannot happen by accident). The
defect is in magnitude and calibration, and it is worst exactly where a BCE is supposed
to be strongest.

Falsifiers, stated before measuring:

  RANGE  If the attainable predicted probability spans most of (0, 1), the double
         sigmoid is cosmetic and this diagnostic is void. FALSIFIER for "it matters":
         attainable range wider than, say, [0.2, 0.8].

  GRAD   If the as-written gradient is within ~2x of the correct one across the logit
         range, the extra squash is a nuisance rather than a defect. FALSIFIER for
         "it matters": ratio bounded near 1. The interesting case is the opposite --
         attenuation that GROWS as the prediction gets more wrong, which would mean the
         loss is quietest about its worst errors.

  TGT    Is the BCE *target* well-posed? `_tgt = (ink / ink.max() > SALIENCY_THRESHOLD)`.
         FALSIFIER for the target being sound: a positive rate near 0 or near 1 (a
         near-constant target teaches nothing), or strong sensitivity to the arbitrary
         0.15 threshold (which would make it a knob nobody has swept).

Measured on real FUNSD pages via D1's cached `visualizations/router_scores.npz`, so TGT
is not a synthetic claim. Pure numpy/torch, no GPU, no weights, <1 s.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/diagnose_saliency_loss.py
"""
import json
import os
import re

import numpy as np
import torch
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "kaggle_pruning_run.ipynb")   # the notebook that ran 7 and 8
NPZ = os.path.join(ROOT, "visualizations", "router_scores.npz")
SALIENCY_THRESHOLD = 0.15   # kaggle_pruning_run.ipynb cell 2

notes = []


# ---------------------------------------------------------------- provenance
# Read the offending lines out of the notebook rather than quoting them, so this
# diagnostic goes stale loudly if someone fixes the loss.
print("=" * 78)
print("0. PROVENANCE -- both halves of the mismatch, read from the notebook")
print("=" * 78)
with open(NB, encoding="utf-8") as f:
    cells = ["".join(c["source"]) for c in json.load(f)["cells"]]

scorer_src, loss_src = cells[4], cells[11]
has_sigmoid = "nn.Sigmoid()" in scorer_src.split("def forward")[0]
uses_logits = "binary_cross_entropy_with_logits" in loss_src
# The staleness guard used to be `has_sigmoid and uses_logits`, which was WRONG: it
# greps for two symptoms rather than testing the condition, so the applied fix -- which
# keeps BOTH strings and inserts torch.logit() to undo the scorer's sigmoid -- did not
# trip it, and this script went on asserting a defect that no longer existed. Test the
# actual mismatch: is the tensor handed to the fused BCE the raw score, or a recovered
# logit? (See AGENTS.md: a check that greps for symptoms passes on any equivalent
# rewrite of the bug.)
recovers_logit = re.search(r"binary_cross_entropy_with_logits\(\s*(?:\n\s*)?torch\.logit\(",
                           loss_src) is not None
print(f"  cell 4  scorer ends in nn.Sigmoid()            : {has_sigmoid}")
print(f"  cell 11 saliency loss uses ..._with_logits()   : {uses_logits}")
print(f"  cell 11 input is wrapped in torch.logit()      : {recovers_logit}")
if not (has_sigmoid and uses_logits) or recovers_logit:
    print("\n  SUPERSEDED -- the mismatch this diagnostic described has been FIXED.")
    print("  Applied 2026-08-31: bce_with_logits(torch.logit(p.clamp(1e-6, 1-1e-6)), t),")
    print("  which is numerically identical to bce(p, t) but stays autocast-safe. The")
    print("  invariant is now guarded by scripts/verify_saliency_loss_cell.py (assertions")
    print("  A SOLVED and C PROPORTIONAL). Kept for provenance; the sections below")
    print("  describe the defect as it stood in runs 7-8, which is what produced the")
    print("  numbers still in AGENTS.md. Do not read them as current.")
    raise SystemExit(0)
for line in loss_src.splitlines():
    if "binary_cross_entropy" in line or "_tgt = " in line or "LAMBDA_SAL = " in line:
        print(f"    | {line.strip()}")
print("  => a probability in (0,1) is passed where a logit in (-inf, inf) is expected")
notes.append("D4: scorer ends in nn.Sigmoid (router.py:25) but cell 11 uses "
             "binary_cross_entropy_with_logits -> double sigmoid")

# ---------------------------------------------------------------- RANGE
print()
print("=" * 78)
print("1. RANGE -- what the model can even express")
print("=" * 78)
p = torch.tensor([0.0, 0.25, 0.5, 0.75, 1.0])
print("  score p (what the scorer outputs) -> sigmoid(p) (what the loss believes)")
for v in p:
    print(f"    {v.item():.2f} -> {torch.sigmoid(v).item():.4f}")
lo, hi = torch.sigmoid(torch.tensor([0.0, 1.0])).tolist()
print(f"  attainable predicted probability: [{lo:.3f}, {hi:.3f}]")
print(f"  => the model cannot say 'blank' below p={lo:.2f}. 'Confidently not text' is "
      f"unreachable.")
for tgt, name in ((1.0, "positive (text)"), (0.0, "negative (blank)")):
    l = F.binary_cross_entropy_with_logits(p, torch.full_like(p, tgt), reduction="none")
    print(f"  {name:17s}: loss floor {l.min():.4f}, ceiling {l.max():.4f}")
print("  => a correct BCE reaches ~0 on a solved example; this one bottoms out at "
      "0.313 / 0.693")
notes.append(f"D4 RANGE: attainable prob is [{lo:.3f}, {hi:.3f}]; loss floors at "
             f"0.313 (pos) / 0.693 (neg), never ~0")

# ---------------------------------------------------------------- GRAD
print()
print("=" * 78)
print("2. GRAD -- attenuation vs the correctly-specified loss")
print("=" * 78)
z = torch.linspace(-4, 4, 9)
tgt = torch.ones_like(z)                      # a TEXT patch
z1 = z.clone().requires_grad_(True)
F.binary_cross_entropy_with_logits(z1, tgt, reduction="sum").backward()
z2 = z.clone().requires_grad_(True)
F.binary_cross_entropy_with_logits(torch.sigmoid(z2), tgt, reduction="sum").backward()
print("  gradient w.r.t. the PRE-sigmoid logit z, on a text patch (target 1):")
print(f"  {'z':>6} {'prediction':>11} {'|grad| correct':>15} {'|grad| as-written':>18} "
      f"{'attenuation':>12}")
ratios = []
for a, b, c in zip(z, z1.grad, z2.grad):
    r = float(abs(c / b))
    ratios.append((float(a), r))
    print(f"  {a:6.1f} {torch.sigmoid(a).item():11.4f} {abs(b):15.4f} {abs(c):18.4f} "
          f"{1 / r:11.1f}x")
worst = min(ratios, key=lambda t: t[1])
print(f"  => attenuation is WORST where the error is LARGEST: at z={worst[0]:.0f} "
      f"(model says 'blank' about text) the")
print(f"     gradient is {1 / worst[1]:.0f}x too small, vs ~{1 / max(r for _, r in ratios):.0f}x "
      f"on already-correct tokens.")
print("     A BCE exists to punish confident mistakes hardest. This one does the reverse.")
notes.append(f"D4 GRAD: gradient attenuated {1 / worst[1]:.0f}x at z={worst[0]:.0f} "
             f"(confidently-wrong) vs {1 / max(r for _, r in ratios):.1f}x when already "
             f"correct -- weakest where the error is biggest")

# ---------------------------------------------------------------- TGT
print()
print("=" * 78)
print("3. TGT -- is the target itself well-posed? (real FUNSD pages, D1's cache)")
print("=" * 78)
d = np.load(NPZ)
c = d["contrast"]                              # == patch_ink, 4 real pages x 4800 tokens
n = c / (c.max(axis=1, keepdims=True) + 1e-9)
print(f"  positive rate of _tgt over {c.shape[0]} pages x {c.shape[1]} tokens:")
print(f"  {'T':>6} " + " ".join(f"{'img' + str(i):>6}" for i in range(c.shape[0]))
      + f" {'mean':>7}")
rate_at = {}
for T in (0.05, 0.10, SALIENCY_THRESHOLD, 0.20, 0.30, 0.50):
    rates = (n > T).mean(axis=1)
    rate_at[T] = float(rates.mean())
    tag = "  <-- SALIENCY_THRESHOLD" if T == SALIENCY_THRESHOLD else ""
    print(f"  {T:6.2f} " + " ".join(f"{r:6.3f}" for r in rates)
          + f" {rates.mean():7.3f}{tag}")
spread = max(rate_at[t] for t in (0.05, 0.10, 0.15, 0.20, 0.30)) \
    - min(rate_at[t] for t in (0.05, 0.10, 0.15, 0.20, 0.30))
print(f"  => positive rate {rate_at[SALIENCY_THRESHOLD]:.3f} at T={SALIENCY_THRESHOLD}: "
      f"balanced, so the target is NOT degenerate.")
print(f"  => and it moves only {spread:.3f} across T in [0.05, 0.30] -- patch ink is "
      f"bimodal (blank vs text),")
print(f"     so SALIENCY_THRESHOLD is not a knob worth sweeping. One fewer thing to tune.")
notes.append(f"D4 TGT: BCE target is sound -- {rate_at[SALIENCY_THRESHOLD]:.3f} positive "
             f"at T=0.15 and only {spread:.3f} drift across T in [0.05,0.30] (ink is "
             f"bimodal); SALIENCY_THRESHOLD is not worth sweeping")

# ---------------------------------------------------------------- verdict
print()
print("=" * 78)
print("SUMMARY -- copy into AGENTS.md")
print("=" * 78)
for x in notes:
    print(f"  - {x}")
print()
print("  VERDICT: the sign-fix worked THROUGH a mis-specified loss, not because of a")
print("  well-specified one. Monotonicity saved it; calibration and gradient scale did")
print("  not. So run 8's numbers are a FLOOR on what ink supervision can do, and the")
print("  fix is one line. Two options, in order of preference:")
print("    (a) return the pre-sigmoid logit from the scorer and keep")
print("        binary_cross_entropy_with_logits (numerically stable, correct scale);")
print("    (b) leave the scorer alone and call F.binary_cross_entropy (no _with_logits)")
print("        -- correct, but loses the log-sum-exp stability the fused version has.")
print("  (a) also removes the sigmoid from the ranking path, which changes nothing:")
print("  top-k is invariant under a monotone transform of the score.")
print()
print("  Do NOT read this as 'run 8 was invalid'. It is the opposite claim: the result")
print("  stands, and there is unclaimed headroom above it. Re-check LAMBDA_SAL=2.0 after")
print("  fixing -- it was tuned against an attenuated gradient and will now be too big.")
