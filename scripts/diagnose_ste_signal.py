"""Diagnostic D7 — is CE-through-STE a usable training signal for the router, and does
run 7 already answer Pending 13(a)?

Pending 13(a) proposes: drop the auxiliary loss entirely and train the router on task CE
through the straight-through estimator alone. Before booking a GPU session, two things need
settling, and both are measurable locally on real weights and real FUNSD pages.

**1. Has it already been run?** Cell 11 carries the comment "Sign-fix (Run 7 follow-up): the
STE-only retrain kept the router sign-inverted", which reads as "13(a) was run 7 and it
failed". It is not the same experiment. Run 7 took the UNSUPERVISED branch, which is
`lambda_sparsity=2.0, lambda_entropy=0.05` — so run 7 was STE **plus two auxiliary terms**,
not STE alone. Both of those terms pull scores toward 0.5:

  - sparsity is `smooth_l1(mean(score), target_budget)` with target_budget=TRAIN_KEEP_RATIO
    =0.50, i.e. an explicit pull of the mean onto 0.5, weighted 2.0;
  - entropy is `-H` (see F3), so minimising it MAXIMISES entropy, which pushes every
    individual score toward 0.5, weighted 0.05.

So the hypothesis this script tests is: **run 7's STE-only retrain did not fail because STE
is a weak signal, it failed because two collapse pressures outweighed it.** If true, 13(a) is
well-motivated and is *not* a repeat of run 7. If false, 13(a) is a repeat and should be
dropped in favour of 13(b)/(c).

**2. Is the STE signal strong enough to matter at all?** If CE-through-STE is orders of
magnitude weaker than the ink-BCE term it replaces, then run 10 produces a router that barely
moved, D6's prediction ("13(a) beats run 9 at keep<=0.50") gets confirmed for the wrong
reason, and nobody can tell the difference from the metrics. Measuring the per-term gradient
magnitude now is what makes that distinguishable later.

Structure of the STE, which is what both questions turn on (`src/router.py:92-96`):

    if self.training and use_ste and select_scores is None:
        ste_weights = topk_scores.unsqueeze(-1)          # scores of the SELECTED tokens
        ste_multiplier = 1.0 + (ste_weights - ste_weights.detach())
        selected_tokens = selected_tokens * ste_multiplier

`topk_scores` covers K of N tokens, so the N-K dropped tokens receive **exactly zero**
gradient. The router can learn "this kept token was worth keeping" but never "that dropped
token would have been better" — a dropped token can only re-enter the budget by a kept
token's score falling below it. Part C measures that this is really what happens rather than
assuming it from the source.

Parts:
  A. Router score distribution across runs 5/7/8/9 — did run 7 collapse toward 0.5?
     This is the decisive test of hypothesis 1, and it is nearly free.
  B. Per-term gradient magnitude at the router scorer on run-5 weights: CE-through-STE
     vs sparsity(2.0) vs entropy(0.05) vs ink-BCE(0.5). Answers question 2, and quantifies
     how badly run 7's auxiliaries outweighed its STE signal.
  C. STE gradient coverage — how many of N tokens receive score gradient, and how far the
     K/K+1 boundary is from being crossed.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/diagnose_ste_signal.py [--n 2]
Read-only: loads checkpoints, never writes one. CPU, no GPU needed.
"""
import argparse
import json
import os
import sys

import torch
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The results_N/ -> run N mapping is off by one; see Pending 12. Spelled out so this
# script cannot silently mislabel a checkpoint.
CKPTS = [
    ("run 5", os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt"),
     "base; STE at keep=1.0 (K=N, so STE multiplier is exactly 1.0 -> router never "
     "received routing gradient)"),
    ("run 7", os.path.join(ROOT, "run 7", "adaptive_donut_pruned.pt"),
     "STE + sparsity 2.0 + entropy 0.05, no ink supervision  <-- the 'STE-only' run"),
    ("run 8", os.path.join(ROOT, "run 8", "adaptive_donut_pruned.pt"),
     "STE + ink-BCE (double-sigmoid bug live, D4)"),
    ("run 9", os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt"),
     "STE + ink-BCE 0.5 (D4 fixed), sparsity 0.0, entropy 0.0"),
]

KEEP = 0.50           # TRAIN_KEEP_RATIO used by runs 7-9
LAMBDA_SPARSITY = 2.0     # run 7's value
LAMBDA_ENTROPY = 0.05     # run 7's value
LAMBDA_SAL = 0.5          # run 9's value
SALIENCY_THRESHOLD = 0.15
ROUTER_LR = 1e-4          # cell 11's router param group
MAX_WORDS = 128           # cell 9
MAX_LEN = 512             # cell 9's tokenizer max_length


def hr(c="="):
    print(c * 78)


# --------------------------------------------------------------------------------
# Copied VERBATIM from notebook cell 9. Part B's whole point is a gradient RATIO on
# the real objective, so the targets have to be the real training targets -- a
# paraphrase here would measure a different loss surface than the one Kaggle runs.
# --------------------------------------------------------------------------------
def reading_order_words(words, bboxes):
    """Sort words top-to-bottom, left-to-right using boxes [x0,y0,x1,y1].
    FUNSD stores words in form-annotation order, not reading order, so a naive
    join yields a scrambled target the decoder cannot learn or be scored on."""
    if not bboxes or len(bboxes) != len(words):
        return list(words)
    hs = sorted(b[3] - b[1] for b in bboxes if b[3] > b[1])
    tol = max(1.0, (hs[len(hs) // 2] * 0.6) if hs else 10.0)
    lines = []
    for i in sorted(range(len(words)), key=lambda k: bboxes[k][1]):
        top = bboxes[i][1]
        for anchor, idxs in lines:
            if abs(top - anchor) <= tol:
                idxs.append(i)
                break
        else:
            lines.append((top, [i]))
    out = []
    for _, idxs in lines:
        out.extend(sorted(idxs, key=lambda k: bboxes[k][0]))
    return [words[i] for i in out]


def build_target_text(sample):
    '''Unified target across mixed sources -> the words for {"text": ...}, capped
    at MAX_WORDS. FUNSD: reading-ordered words. SynthDoG-en: gt_parse.text_sequence.
    Keeps the decoder on ONE output schema.'''
    words = sample.get('words')
    if words:
        boxes = sample.get('bboxes') or sample.get('boxes')
        if boxes:
            words = reading_order_words(words, boxes)
        return ' '.join(words[:MAX_WORDS])
    gt = sample.get('ground_truth')
    if gt:
        try:
            obj = json.loads(gt) if isinstance(gt, str) else gt
            parse = obj.get('gt_parse', obj) if isinstance(obj, dict) else {}
            seq = parse.get('text_sequence', '') if isinstance(parse, dict) else str(parse)
        except Exception:
            seq = gt if isinstance(gt, str) else ''
        return ' '.join(seq.split()[:MAX_WORDS])
    return 'sample document'


def patch_ink(pixel_values, num_tokens, stride=32):
    """Per-token within-patch contrast on the encoder's own token grid -> (B, N).

    Copied VERBATIM from the notebook's cell 7 so this diagnostic measures the same
    statistic the training target uses. Do not re-derive it: a first version of this
    script inferred the grid by decrementing `side` until `side**2 == num_tokens`, which
    never holds (4800 = 80x60, not a square), so it silently pooled the page into a
    1x4800 strip and reported r(ink) ~ 0 for every checkpoint. The real function raises
    on a grid mismatch instead of degrading, which is the whole difference.
    """
    B, _, H, W = pixel_values.shape
    gh, gw = H // stride, W // stride
    if gh * gw != num_tokens:
        raise ValueError(
            f'token grid mismatch: pixel_values {H}x{W} at stride {stride} gives '
            f'{gh}x{gw}={gh * gw} patches but the encoder emitted {num_tokens} tokens')
    gray = pixel_values.mean(dim=1)                                    # (B, H, W)
    blocks = gray.unfold(1, stride, stride).unfold(2, stride, stride)   # (B,gh,gw,s,s)
    return blocks.reshape(B, gh * gw, -1).std(dim=-1)                  # (B, N)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="FUNSD images to use")
    ap.add_argument("--split", default="test", choices=["train", "test"],
                    help="FUNSD split. Use train for the in-distribution ratio: on test "
                         "pages the model's CE is ~3.15 vs run 9's 0.309 final TRAINING CE, "
                         "and the CE gradient scales with that error -- so a test-split "
                         "measurement inflates CE relative to every auxiliary and thereby "
                         "flatters the 'auxiliaries are negligible' conclusion. Measure both.")
    args = ap.parse_args()

    from datasets import load_dataset
    from transformers import DonutProcessor

    from src.loss import AdaptivePruningLoss
    from src.model import AdaptiveDonutOCR

    torch.manual_seed(0)
    device = torch.device("cpu")

    # Interpolate args.split rather than hardcoding "test": a saved log that says "test split"
    # at the top and "split=train" four lines down is exactly how a split gets misattributed
    # when the numbers are read back weeks later.
    print(f"loading donut processor + FUNSD {args.split} split (both cached locally)...")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split=args.split)
    imgs = [ds[i]["image"].convert("RGB") for i in range(args.n)]
    pixel_values = torch.cat(
        [processor(im, return_tensors="pt").pixel_values for im in imgs], dim=0)
    print(f"  split={args.split}  pixel_values {tuple(pixel_values.shape)}  "
          f"({args.n} page(s))")

    print("building AdaptiveDonutOCR (keep_ratio=%.2f, merge_ratio=0.0)..." % KEEP)
    model = AdaptiveDonutOCR(keep_ratio=KEEP, merge_ratio=0.0, freeze_encoder=True).to(device)
    model.eval()

    # ---------------------------------------------------------------- A. score spread
    hr()
    print("A. ROUTER SCORE DISTRIBUTION PER CHECKPOINT")
    hr()
    print("Hypothesis: run 7's sparsity(2.0)+entropy(0.05) collapsed the scores toward 0.5,")
    print("so its null result is about those terms, not about STE being a weak signal.")
    print("A collapsed router has small std and mean ~0.50; `torch.topk` on near-constant")
    print("scores returns essentially the first K indices, i.e. selection stops being learned.")
    print()
    rows = []
    for label, path, note in CKPTS:
        if not os.path.exists(path):
            print(f"  {label}: MISSING ({path}) -- skipped")
            continue
        sd = torch.load(path, map_location=device, weights_only=True)
        miss, unexp = model.load_state_dict(sd, strict=False)
        with torch.no_grad():
            enc = model.model.encoder(pixel_values).last_hidden_state
            sc = model.router.scorer(enc).squeeze(-1)          # (B, N)
        n = sc.shape[1]
        ink_n = patch_ink(pixel_values, n)
        # correlation with ink, per page then averaged (D1's statistic)
        cors = []
        for b in range(sc.shape[0]):
            a, c = sc[b].float(), ink_n[b].float()
            a = a - a.mean()
            c = c - c.mean()
            denom = (a.norm() * c.norm()).clamp_min(1e-12)
            cors.append(float((a * c).sum() / denom))
        r = sum(cors) / len(cors)
        rows.append((label, n, float(sc.mean()), float(sc.std()),
                     float(sc.min()), float(sc.max()), r, len(miss), len(unexp), note))
        print(f"  {label:6s} N={n:5d}  mean {float(sc.mean()):.4f}  std {float(sc.std()):.4f}  "
              f"min {float(sc.min()):.4f}  max {float(sc.max()):.4f}  r(ink) {r:+.3f}   "
              f"(missing={len(miss)}, unexpected={len(unexp)})")
        print(f"          {note}")

    if rows:
        print()
        print("  | run | mean | std | min | max | r(ink) |")
        print("  |---|---|---|---|---|---|")
        for label, n, mu, sd_, lo, hi, r, *_ in rows:
            print(f"  | {label} | {mu:.4f} | {sd_:.4f} | {lo:.4f} | {hi:.4f} | {r:+.3f} |")
        base = next((x for x in rows if x[0] == "run 5"), None)
        r7 = next((x for x in rows if x[0] == "run 7"), None)
        if base and r7:
            print()
            print(f"  run 7 std / run 5 std = {r7[3] / max(base[3], 1e-12):.3f}"
                  f"   (<<1 would be collapse; ~1 or more is not)")
            print(f"  run 7 |mean - 0.5|     = {abs(r7[2] - 0.5):.4f}"
                  f"   (~0 would be the sparsity pull landing)")

    # -------------------------------------------------- B. per-term gradient magnitude
    hr()
    print("B. PER-TERM GRADIENT MAGNITUDE AT THE ROUTER SCORER (run-5 weights)")
    hr()
    print("Each term is backwarded ALONE with grads zeroed between, so the numbers are")
    print("attributable. Reported as the L2 norm over router.scorer parameters only --")
    print("that is the tensor 13(a) is about. keep_ratio=%.2f, training mode (STE live)." % KEEP)
    print()
    sd5 = torch.load(CKPTS[0][1], map_location=device, weights_only=True)
    model.load_state_dict(sd5, strict=False)
    model.train()                       # STE is gated on self.training
    for p in model.parameters():
        p.requires_grad_(False)
    for p in model.router.parameters():
        p.requires_grad_(True)          # isolate: only the scorer can accumulate grad

    # Real FUNSD targets, not placeholder tokens. This matters for the ratio being
    # measured: with arbitrary labels the model is badly wrong, CE is large, and the
    # CE-through-STE gradient is correspondingly inflated -- i.e. the error would bias
    # toward the conclusion "13(a) has a strong signal", which is the direction to be
    # most suspicious of. Same prompt schema, same tokenization and the same two
    # helpers as cell 9's DocumentDataset, so this is the real loss surface.
    prompts = [f"<s_doc>{json.dumps({'text': build_target_text(ds[i])})}</s>"
               for i in range(args.n)]
    labels = processor.tokenizer(prompts, add_special_tokens=False, max_length=MAX_LEN,
                                 padding="max_length", truncation=True,
                                 return_tensors="pt").input_ids
    dec_in = labels.clone()                      # cell 9 clones BEFORE masking
    labels[labels == processor.tokenizer.pad_token_id] = -100
    n_real = int((labels != -100).sum())
    print(f"  targets: {n_real} non-ignored label positions over {args.n} page(s) "
          f"(max_len={MAX_LEN}, max_words={MAX_WORDS}, ignore_index=-100)")
    print(f"  first target: {prompts[0][:96]}...")

    crit = AdaptivePruningLoss(lambda_sparsity=LAMBDA_SPARSITY,
                               lambda_entropy=LAMBDA_ENTROPY,
                               target_budget=KEEP,
                               pad_token_id=processor.tokenizer.pad_token_id)

    def scorer_grad_norm(build_term):
        model.zero_grad(set_to_none=True)
        out = model(pixel_values=pixel_values, labels=labels, decoder_input_ids=dec_in,
                    keep_ratio=KEEP)
        d = crit(out["logits"], labels, out["scores"], out["loss"])
        term = build_term(out, d)
        if term is None:
            return None, None, out
        term.backward()
        sq = sum(float((p.grad ** 2).sum()) for p in model.router.parameters()
                 if p.grad is not None)
        return sq ** 0.5, float(term.detach()), out

    def ink_term(out):
        sc = out["scores"]
        ink_n = patch_ink(pixel_values, sc.shape[1]).to(sc.dtype)
        inkn = ink_n / (ink_n.amax(dim=1, keepdim=True) + 1e-9)
        tgt = (inkn > SALIENCY_THRESHOLD).float()
        return F.binary_cross_entropy_with_logits(
            torch.logit(sc.squeeze(-1).clamp(1e-6, 1 - 1e-6)), tgt)

    terms = [
        ("CE through STE      (13a's ONLY signal)", lambda o, d: d["ce_loss"]),
        (f"sparsity x{LAMBDA_SPARSITY}         (run 7 had this)",
         lambda o, d: LAMBDA_SPARSITY * d["sparsity_loss"]),
        (f"entropy  x{LAMBDA_ENTROPY}        (run 7 had this)",
         lambda o, d: LAMBDA_ENTROPY * d["entropy_loss"]),
        (f"ink-BCE  x{LAMBDA_SAL}         (run 9 had this)",
         lambda o, d: LAMBDA_SAL * ink_term(o)),
    ]

    # Measured at BOTH run-5 and run-7 weights. One point in weight space is not enough
    # for the central claim: the sparsity gradient is `lambda * smooth_l1'(mean, 0.50)`,
    # which GROWS as the mean departs from the target. Run 5's mean is 0.4508 (|dev| 0.049)
    # but run 7 ENDED at 0.3249 (|dev| 0.175), ~3.6x further out -- so a ratio measured only
    # at run 5 could understate sparsity by that factor over run 7's own trajectory. If the
    # ratio is small at both ends, the claim holds across the path between them.
    for wlabel, wpath in (("run 5 (start of run 7)", CKPTS[0][1]),
                          ("run 7 (end of run 7)", CKPTS[1][1])):
        if not os.path.exists(wpath):
            print(f"  {wlabel}: MISSING -- skipped")
            continue
        model.load_state_dict(torch.load(wpath, map_location=device, weights_only=True),
                              strict=False)
        model.train()
        print(f"  --- at {wlabel} weights ---")
        mags = {}
        for name, fn in terms:
            g, val, out = scorer_grad_norm(fn)
            mags[name] = g
            print(f"    ||grad|| {g:.6e}   term value {val:+.6f}   {name}")
        ce_key = terms[0][0]
        if mags.get(ce_key):
            print("    ratio to CE-through-STE (>1 means the term OUTWEIGHS 13a's signal):")
            for name, _ in terms[1:]:
                if mags.get(name) is not None:
                    print(f"      {mags[name] / mags[ce_key]:9.4f}x   {name}")
            r7_total = sum(mags[n] for n, _ in terms[1:3] if mags.get(n) is not None)
            print(f"      {r7_total / mags[ce_key]:9.4f}x   run 7's two auxiliaries COMBINED")
        print()

    # Part C runs on run-5 weights (the state 13(a) would start from).
    model.load_state_dict(torch.load(CKPTS[0][1], map_location=device, weights_only=True),
                          strict=False)
    model.train()

    # ------------------------------------------------------------- C. STE grad coverage
    hr()
    print("C. STE GRADIENT COVERAGE AND THE SELECTION BOUNDARY")
    hr()
    model.zero_grad(set_to_none=True)
    out = model(pixel_values=pixel_values, labels=labels, decoder_input_ids=dec_in,
                keep_ratio=KEEP)
    scores = out["scores"]
    scores.retain_grad()
    d = crit(out["logits"], labels, out["scores"], out["loss"])
    d["ce_loss"].backward()
    sg = scores.grad.detach().squeeze(-1)          # (B, N)
    B, N = sg.shape
    K = max(1, int(round(N * KEEP)))
    nz = int((sg.abs() > 0).sum(dim=1).float().mean())
    print(f"  N = {N}, K = round(N*{KEEP}) = {K}")
    print(f"  tokens with NONZERO score gradient: {nz} of {N}  "
          f"(= K? {'YES' if nz == K else 'NO'})")
    print("  -> the N-K dropped tokens are stationary: they receive no gradient, so a")
    print("     dropped token can only enter the budget when a KEPT token's score falls")
    print("     below it. This is the exploration limit of hard top-k + STE.")
    print()
    srt, _ = torch.sort(scores.detach().squeeze(-1), dim=1, descending=True)
    gap = (srt[:, K - 1] - srt[:, K]).mean()
    print(f"  score at the K/K+1 boundary: {float(srt[:, K-1].mean()):.6f} / "
          f"{float(srt[:, K].mean()):.6f}   gap {float(gap):.3e}")
    band = ((scores.detach().squeeze(-1) - srt[:, K - 1:K]).abs() < 1e-3).sum(dim=1).float().mean()
    print(f"  tokens within 1e-3 of the boundary: {float(band):.0f}  "
          f"(how many are one nudge from flipping)")
    print(f"  mean |d(CE)/d(score)| over the K kept: "
          f"{float(sg.abs().sum() / max(nz * B, 1)):.3e}")
    print(f"  one AdamW step at lr={ROUTER_LR:g} moves a parameter ~{ROUTER_LR:g}; the score")
    print("     change per step is that times d(score)/d(param), so compare the boundary")
    print("     gap above against it to judge whether selection can reorder in 5 epochs.")

    def ink_fn(out, b):
        sc = out["scores"]
        ink_n = patch_ink(pixel_values[b:b + 1], sc.shape[1]).to(sc.dtype)
        inkn = ink_n / (ink_n.amax(dim=1, keepdim=True) + 1e-9)
        tgt = (inkn > SALIENCY_THRESHOLD).float()
        return LAMBDA_SAL * F.binary_cross_entropy_with_logits(
            torch.logit(sc.squeeze(-1).clamp(1e-6, 1 - 1e-6)), tgt)

    part_d(model, pixel_values, labels, dec_in, crit, processor, ink_fn)

    hr()
    print("D7 done. Interpretation belongs in AGENTS.md, not here.")
    hr()


def part_d(model, pixel_values, labels, dec_in, crit, processor, ink_fn):
    """Cross-page gradient AGREEMENT -- magnitude is not displacement.

    Part B measures instantaneous norm. That is not what moves weights over 5 epochs:
    a small gradient pointing the SAME way every step accumulates, while a large one
    whose direction resamples every batch partly cancels. This matters because run 9's
    ink-BCE was only ~0.1x of CE by norm yet flipped r(ink) from -0.237 to +0.725, which
    norm alone cannot explain. Cosine between the per-page gradients is the missing
    number: ~1 means a systematic direction, ~0 means batch-specific and self-cancelling.
    Needs --n >= 2.
    """
    hr()
    print("D. CROSS-PAGE GRADIENT AGREEMENT (direction, not magnitude)")
    hr()
    B = pixel_values.shape[0]
    if B < 2:
        print("  SKIPPED: needs --n >= 2 to compare two pages.")
        return
    print("  Norm says how hard a term pushes; cosine says whether the pushes agree.")
    print("  A term with small norm and cosine ~1 can out-displace a large incoherent one.")
    print()
    for tname, build in (("CE through STE", "ce"), ("ink-BCE", "ink")):
        gs = []
        for b in range(B):
            model.zero_grad(set_to_none=True)
            out = model(pixel_values=pixel_values[b:b + 1], labels=labels[b:b + 1],
                        decoder_input_ids=dec_in[b:b + 1], keep_ratio=KEEP)
            d = crit(out["logits"], labels[b:b + 1], out["scores"], out["loss"])
            term = d["ce_loss"] if build == "ce" else ink_fn(out, b)
            term.backward()
            gs.append(torch.cat([p.grad.detach().flatten()
                                 for p in model.router.parameters() if p.grad is not None]))
        cos = float(F.cosine_similarity(gs[0], gs[1], dim=0))
        print(f"  {tname:16s} cos(page0, page1) = {cos:+.4f}   "
              f"|g0| {float(gs[0].norm()):.4e}  |g1| {float(gs[1].norm()):.4e}")
    print()
    print("  Read together with Part B: displacement over training scales roughly as")
    print("  norm x coherence, so compare the PRODUCTS, not the norms.")


if __name__ == "__main__":
    main()
