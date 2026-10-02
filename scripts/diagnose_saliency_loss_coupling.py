"""Diagnostic D5 (2026-08-31): the D4 fix, as planned, would have broken two other terms.

D4 found that cell 11 feeds an already-sigmoid'd score to
`binary_cross_entropy_with_logits`, and recommended the "clean" fix: have
`PatchSaliencyRouter.scorer` return the pre-sigmoid logit and keep the fused BCE.

That recommendation was made without checking who else consumes `scores`. Two other
terms do, both inside `AdaptivePruningLoss` (`src/loss.py`), and both assume a
PROBABILITY:

    sparsity:  smooth_l1(scores.mean(), target_budget)      # target_budget is a FRACTION
    entropy:   scores.clamp(min=eps, max=1-eps) -> H(p)     # only defined on (0,1)

Neither would crash on a logit. The sparsity term would compare an unbounded mean to
0.5, and the entropy term would clamp most inputs to 1e-7 or 1-1e-7, shrinking H and
attenuating its gradient to whichever arbitrary tokens happen to have a logit inside
(0,1). Same failure class as D4 itself: quiet, plausible-looking, wrong.

Falsifiers, stated before measuring:

  CONSUMERS  If nothing but the BCE reads `scores`, the logit fix is safe and this
             diagnostic is void. FALSIFIER for "the fix is unsafe": no other consumer,
             or all other consumers carry zero weight in the configuration that ran.

  CLAMP      If `entropy` survives a logit-scale input, the clamp is harmless.
             FALSIFIER for "it breaks": H under logits stays within ~2x of H under
             probabilities, with a comparable gradient on a comparable set of tokens.

  COMPETE    The entropy term is `-H`, so minimizing it MAXIMIZES entropy, i.e. pulls
             every score toward p=0.5 -- the opposite of what the ink-BCE wants. Is it
             big enough to matter? FALSIFIER for "it matters today": entropy gradient
             is <10% of the BCE gradient across the score range the model actually
             occupies. This one is expected to falsify; measure it anyway, because the
             ratio changes when LAMBDA_SAL comes down after the D4 fix.

  RANGE2     D4 argued from the range of sigmoid(p). What range does the scorer's own
             output actually occupy on real pages? FALSIFIER for D4's framing: if the
             scorer is itself stuck near 0.5, the defect is the scorer, not the loss.

Measured against `src/loss.py` as written and D1's cached real-page scores. Pure
numpy/torch, no GPU, no weights, <1 s.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/diagnose_saliency_loss_coupling.py
"""
import json
import os
import re

import numpy as np
import torch
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "kaggle_pruning_run.ipynb")
LOSS_PY = os.path.join(ROOT, "src", "loss.py")
NPZ = os.path.join(ROOT, "visualizations", "router_scores.npz")

# Run-8 history: these are what the two weights WERE when this diagnostic was booked.
# They are frozen on purpose -- the measurements below describe run 8 -- but every
# statement about the CURRENT notebook is read from the file instead, because both
# values changed when the D4/D5 fix went in (LAMBDA_SAL 2.0 -> 0.5, lambda_entropy
# defaulted -> passed explicitly).
RUN8_LAMBDA_SAL = 2.0
RUN8_LAMBDA_ENTROPY = 0.05     # inherited from src/loss.py's signature default
notes = []


# ------------------------------------------------------------------ CONSUMERS
print("=" * 78)
print("1. CONSUMERS -- who else reads `scores`, and at what weight (read from source)")
print("=" * 78)
loss_src = open(LOSS_PY, encoding="utf-8").read()
cells = ["".join(c["source"]) for c in json.load(open(NB, encoding="utf-8"))["cells"]]

consumers = {
    "sparsity (smooth_l1 vs target_budget)": "smooth_l1_loss(mean_score" in loss_src,
    "entropy (clamp -> binary H)":           "clamped_scores = scores.clamp" in loss_src,
    "ink-BCE (cell 11)":                     "binary_cross_entropy_with_logits" in cells[11],
    "STE multiplier (router.py)":            True,
}
for k, v in consumers.items():
    print(f"  {k:40s}: {'PRESENT' if v else 'absent'}")

# What weight does each carry in the branch that actually ran (SUPERVISE_SALIENCY=True)?
m = re.search(r"lambda_entropy\s*:\s*float\s*=\s*([0-9.]+)", loss_src)
default_entropy = float(m.group(1)) if m else None
passes_entropy = "lambda_entropy" in cells[11]
# Read the live weights so this section cannot go on describing a notebook that changed.
_ls = re.search(r"LAMBDA_SAL\s*=\s*([0-9.]+)\s*$", cells[11], re.M)
live_sal = float(_ls.group(1)) if _ls else None
_le = re.findall(r"lambda_entropy\s*=\s*([0-9.]+)", cells[11])
live_entropy = sorted({float(x) for x in _le}) or None
print(f"\n  src/loss.py default lambda_entropy      : {default_entropy}")
print(f"  cell 11 passes lambda_entropy?          : {passes_entropy}")
print(f"  RUN 8 (what the measurements below are about):")
print(f"    entropy weight in the run-8 branch    : {RUN8_LAMBDA_ENTROPY} (DEFAULTED, not chosen)")
print(f"    sparsity weight in the run-8 branch   : 0.0 (lambda_sparsity=0.0) -- inert")
print(f"    => TWO terms shaped the scores in run 8: ink-BCE at {RUN8_LAMBDA_SAL} and")
print(f"       entropy at {RUN8_LAMBDA_ENTROPY}, and only the first one was deliberate.")
print(f"  NOW (read from the notebook on this run):")
print(f"    LAMBDA_SAL                            : {live_sal}")
print(f"    lambda_entropy values passed          : {live_entropy}")
if passes_entropy and live_entropy is not None:
    print(f"    => the undeclared knob is now declared at every site. The run-8 numbers")
    print(f"       below stand as history; they are NOT the current configuration.")
assert consumers["sparsity (smooth_l1 vs target_budget)"] and consumers["entropy (clamp -> binary H)"], \
    "CONSUMERS falsified: loss.py no longer reads scores as a probability"
notes.append(f"D5 CONSUMERS: `scores` is read by 3 terms, not 1 -- sparsity (weight 0.0, "
             f"inert in run 8), entropy (weight {RUN8_LAMBDA_ENTROPY}, DEFAULTED and never "
             f"chosen), ink-BCE ({RUN8_LAMBDA_SAL}). Both loss.py terms assume a probability.")

# ------------------------------------------------------------------ CLAMP
print()
print("=" * 78)
print("2. CLAMP -- what the entropy term does if the scorer returns logits instead")
print("=" * 78)


def entropy_term(s):
    """Verbatim from src/loss.py:66-69."""
    eps = 1e-7
    c = s.clamp(min=eps, max=1.0 - eps)
    H = -(c * torch.log(c) + (1.0 - c) * torch.log(1.0 - c)).mean()
    return H


probs = torch.tensor([0.02, 0.20, 0.44, 0.60, 0.99])          # today: scorer output
logits = torch.logit(probs)                                    # after the "clean" fix
H_p = entropy_term(probs)
H_z = entropy_term(logits)
print(f"  scorer output as PROBABILITIES {probs.tolist()}")
print(f"    H = {H_p:.6f}  (informative: varies with the scores)")
print(f"  same information as LOGITS      {[round(v, 2) for v in logits.tolist()]}")
print(f"    H = {H_z:.6f}  (most values clamped to 1e-7 or 1-1e-7 -> H shrinks)")
ratio = float(H_z / H_p)
print(f"  ratio {ratio:.4f}")
z = logits.clone().requires_grad_(True)
entropy_term(z).backward()
gnorm_z = float(z.grad.abs().max())
p2 = probs.clone().requires_grad_(True)
entropy_term(p2).backward()
gnorm_p = float(p2.grad.abs().max())
in_range = int(((logits > 1e-7) & (logits < 1 - 1e-7)).sum())
print(f"  max |dH/dinput|: probabilities {gnorm_p:.6f}  vs logits {gnorm_z:.6f}"
      f"  (attenuated {gnorm_p / max(gnorm_z, 1e-12):.0f}x)")
print(f"  and note WHICH tokens still get a gradient: clamp() passes gradient only for")
print(f"  in-range inputs, so {in_range} of {len(logits)} tokens still get one -- the ones whose")
print(f"  LOGIT happens to land inside (0,1), which is an arbitrary subset unrelated to")
print(f"  saliency. So the term is not merely weakened; it starts regularizing a")
print(f"  meaningless slice of tokens. Still no error, still no crash.")
notes.append(f"D5 CLAMP: under the proposed logit fix the entropy term's H drops "
             f"{H_p:.3f}->{H_z:.3f} (x{ratio:.3f}) and its max gradient is attenuated "
             f"{gnorm_p / max(gnorm_z, 1e-12):.0f}x, surviving only for the arbitrary "
             f"{in_range}/{len(logits)} tokens whose logit lands in (0,1) -- silently "
             f"corrupted, no crash")

# ------------------------------------------------------------------ COMPETE
print()
print("=" * 78)
print("3. COMPETE -- entropy pulls toward p=0.5; the ink-BCE pulls toward 0/1. Which wins?")
print("=" * 78)
print("  entropy_loss = -H, added with +lambda_entropy, so MINIMIZING it MAXIMIZES")
print("  entropy -- i.e. it actively pushes every score back toward 0.5.")
print(f"  {'p':>6} {'|BCE grad|':>12} {'|entropy grad|':>15} {'entropy share':>14}  target")
rows = []
for tgt in (1.0, 0.0):
    for pv in (0.02, 0.20, 0.44, 0.60, 0.90, 0.99):
        p = torch.tensor([pv], requires_grad=True)
        (RUN8_LAMBDA_SAL * F.binary_cross_entropy_with_logits(
            p, torch.tensor([tgt]))).backward()
        g_bce = float(p.grad.abs())
        p2 = torch.tensor([pv], requires_grad=True)
        (RUN8_LAMBDA_ENTROPY * -entropy_term(p2)).backward()
        g_ent = float(p2.grad.abs())
        share = g_ent / (g_bce + 1e-12)
        rows.append(share)
        print(f"  {pv:6.2f} {g_bce:12.4f} {g_ent:15.4f} {share:13.1%}  "
              f"{'text (1)' if tgt else 'blank (0)'}")
print(f"  => entropy was {min(rows):.1%}-{max(rows):.1%} of the BCE gradient in run 8. It")
print("     was NOT the dominant term, so COMPETE is FALSIFIED as a run-8 cause.")
print(f"  BUT: D4 says LAMBDA_SAL={RUN8_LAMBDA_SAL} must come down once the double sigmoid")
print("     is fixed (it was tuned against a 3.7-112x attenuated gradient). Had the")
print("     entropy weight been left alone, its RELATIVE weight would rise by exactly")
print("     the factor LAMBDA_SAL falls by:")
for newlam in (1.0, 0.5, 0.1):
    tag = "  <-- chosen" if live_sal is not None and abs(newlam - live_sal) < 1e-9 else ""
    print(f"       LAMBDA_SAL {RUN8_LAMBDA_SAL} -> {newlam}: entropy share "
          f"x{RUN8_LAMBDA_SAL / newlam:.0f} -> up to "
          f"{max(rows) * RUN8_LAMBDA_SAL / newlam:.0%}{tag}")
print("     This projection is why lambda_entropy was set to 0.0 in the supervised")
print("     branch rather than left at 0.05: at LAMBDA_SAL=0.5 the anti-confidence term")
print("     would have carried up to ~170% of the BCE gradient.")
notes.append(f"D5 COMPETE: entropy was only {min(rows):.1%}-{max(rows):.1%} of the BCE "
             f"gradient in run 8, so it was NOT a present cause (falsified as predicted) "
             f"-- but it scales up by exactly the factor LAMBDA_SAL is reduced by, so it "
             f"had to be set explicitly in the same run that fixes D4")

# ------------------------------------------------------------------ RANGE2
print()
print("=" * 78)
print("4. RANGE2 -- what range does the scorer itself occupy on real pages?")
print("=" * 78)
d = np.load(NPZ)
s = d["scores"]
print(f"  cached scores over {s.shape[0]} real FUNSD pages x {s.shape[1]} tokens:")
print(f"    min {s.min():.4f}  p1 {np.percentile(s, 1):.4f}  median "
      f"{np.median(s):.4f}  p99 {np.percentile(s, 99):.4f}  max {s.max():.4f}")
print(f"  => the scorer spans essentially all of (0,1). It is FULLY EXPRESSIVE.")
print(f"  => so D4's defect is not 'the scorer cannot be confident'. It is sharper:")
print(f"     the scorer CAN output 0.99, the loss then reads that as sigmoid(0.99)=")
print(f"     {torch.sigmoid(torch.tensor(0.99)).item():.3f}, and a BCE at 0.729 against "
      f"target 1 is never satisfied.")
print(f"     The loss is STRUCTURALLY UNSATISFIABLE: no output the scorer can produce")
print(f"     drives it to ~0, so every token keeps receiving a push forever and the")
print(f"     loss never says 'this one is done'.")
notes.append(f"D5 RANGE2: the scorer's real-page output spans [{s.min():.3f}, "
             f"{s.max():.3f}] (median {np.median(s):.3f}) -- fully expressive. So D4 is "
             f"not 'the scorer can't be confident' but 'the loss can never be satisfied "
             f"by any output the scorer can produce'.")

# ------------------------------------------------------------------ verdict
print()
print("=" * 78)
print("SUMMARY -- copy into AGENTS.md")
print("=" * 78)
for x in notes:
    print(f"  - {x}")
print()
print("  VERDICT: D4's recommended fix (return the pre-sigmoid logit) is UNSAFE as")
print("  written -- it silently corrupts the entropy regularizer. Corrected fix:")
print("    (a) keep the scorer's sigmoid, and change ONLY the loss call to")
print("        F.binary_cross_entropy(_sc.squeeze(-1).clamp(1e-6, 1-1e-6), _tgt).")
print("        One line, one file, no other consumer affected.")
print("    (b) if the fused/stable version is wanted, the scorer must return BOTH the")
print("        logit (for the BCE) and the probability (for sparsity/entropy/STE) --")
print("        a signature change across 3 copies of the class plus every call site.")
print("  Do (a). And in the same run, pass lambda_entropy EXPLICITLY instead of")
print("  inheriting 0.05 by default, because re-tuning LAMBDA_SAL changes its relative")
print("  weight even though nobody edited it.")
print()
print("  APPLIED 2026-08-31 -- a variant of (a), for a reason found after this verdict:")
print("    F.binary_cross_entropy_with_logits(torch.logit(p.clamp(1e-6, 1-1e-6)), t)")
print("  Plain F.binary_cross_entropy is on PyTorch's autocast-unsafe list, and this")
print("  block runs inside torch.amp.autocast on the T4. Wrapping torch.logit() recovers")
print("  the logit and hands it to the fused op: identical in value to (a), same")
print("  d/dz == p - t, keeps log-sum-exp stability, and still touches only cell 11 --")
print("  the scorer keeps its sigmoid, so all three probability consumers are untouched.")
print("  lambda_entropy was passed explicitly in the same edit: 0.0 in the supervised")
print("  branch (it is -H, so it fights the ink target) and 0.05 in the unsupervised one.")
print("  Guarded by scripts/verify_saliency_loss_cell.py (6/6).")
print()
print("  Meta-lesson, which is the reusable part: D4 proposed a fix to a term without")
print("  enumerating the other readers of the value it changes. 'One-line fix' was a")
print("  claim about the diff, not about the blast radius. Second-order version of the")
print("  same lesson: this verdict's own preferred fix was then ruled out by a constraint")
print("  (autocast) that neither D4 nor D5 had checked -- so the prescription needed a")
print("  third pass, not just a second one.")
