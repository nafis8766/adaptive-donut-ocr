"""Diagnostic D8 -- is decoder cross-attention a target DIFFERENT from retained ink?

Pending 13 asks for a training target that is not retained ink. D6 ruled ink out as an
objective (optimising it harder cost accuracy at two of three budgets), and D7 ruled out
candidate 13(a) (train on task CE through the STE alone). That leaves 13(b): distil a
per-token target from the decoder's own cross-attention on the run-5 ceiling model.

Before building 13(b) there is one cheap way for it to be dead on arrival, and it must be
checked first: **if cross-attention mass is just ink, then 13(b) IS 13(c) with extra steps,
and D6 has already ruled it out.** Ink is a within-patch contrast statistic, and a document
decoder plausibly attends to exactly the high-contrast (i.e. inked) patches -- in which case
the "new" target is the old one and the whole line of work is a repeat.

Falsifiable, pre-registered:

  If r(attn, ink) >= 0.8 AND top-K overlap >= 0.90, 13(b) is ink in disguise -> DROP it and
  go to 13(c) (line-weighted ink, which at least changes the loss's SHAPE rather than its
  content).
  If r(attn, ink) <= 0.5 and the overlap is well under 0.90, 13(b) is a genuinely different
  target and is worth building.
  In between: report the numbers and decide explicitly rather than by preference.

BLIND SPOT IN THE ABOVE, found after the first run and closed by Part 2 below. Those two
thresholds are NECESSARY but not SUFFICIENT. "Not ink" has two causes and they have opposite
implications:

  (i) attention tracks something else about the CONTENT of this page  -> 13(b) is worth building
  (ii) attention is largely PAGE-INDEPENDENT (positional bias / attention sink) -> 13(b) is
       dead, because a target that is the same mask on every document teaches the router a
       constant. It would be learnable in one step, carry no information about where THIS
       page's text is, and score like run 7.

Cause (ii) passes the pre-registered test with flying colours -- a fixed mask is maximally
"different from ink". The first run's two pages returned r(attn,ink) 0.097/0.088, overlap
0.621/0.620, mass-in-top-K 0.898/0.911: agreement to three digits across two unrelated forms,
which is what (ii) looks like. So Part 2 measures cross-page consistency directly, with ink as
the calibration baseline (two mostly-white forms share some ink layout, so ink's own cross-page
overlap is the floor that "content-dependent" has to beat, not 0.50).

  Pre-registered for Part 2: if attn's cross-page top-K overlap is >= ink's AND cos(attn_p0,
  attn_p1) >= 0.95, the map is page-independent -> 13(b) is dead. If attn's cross-page overlap
  is at or below ink's, attention varies with content at least as much as ink does and (i)
  stands.

Second question, same cost: how does attention mass compare to what the ROUTER currently
scores? r(attn, score) on run-5 weights says how far the router would have to move. Run 5's
r(score, ink) is -0.237 (D1: -0.226/-0.248; D7 reproduced -0.237), so if attention is
positively ink-correlated the router is currently anti-correlated with it too.

CAVEAT, stated up front because it limits what a positive result buys: attention mass is not
causal importance. The rigorous target is the leave-one-out effect of dropping each token on
CE, which is 4800 forward passes per image -- infeasible. Attention is the tractable proxy,
and a proxy is exactly what D6 punished. What makes it a better proxy than ink is that it is
derived from the model's own use of the tokens rather than from the pixels; that is an
argument, not a proof, and 13(b) must be evaluated on accuracy like everything else.

No `src/` change is needed: `model.model.decoder` is an MBartForCausalLM and accepts
`output_attentions=True` directly, so the target can be extracted without touching the
training path.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 \
        python scripts/diagnose_attn_target.py [--n 2]
Read-only. CPU. Prints numbers; interpretation goes in AGENTS.md.
"""
import argparse
import json
import os
import sys

import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.diagnose_ste_signal import (MAX_LEN, MAX_WORDS, SALIENCY_THRESHOLD,  # noqa: E402
                                         build_target_text, patch_ink)

RUN5 = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
KEEP = 0.50          # only used for the top-K overlap, matching runs 7-9


def hr(c="="):
    print(c * 78)


def pearson(a, b):
    a = a.float() - a.float().mean()
    b = b.float() - b.float().mean()
    return float((a * b).sum() / (a.norm() * b.norm()).clamp_min(1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2)
    args = ap.parse_args()

    from datasets import load_dataset
    from transformers import DonutProcessor

    from src.model import AdaptiveDonutOCR

    torch.manual_seed(0)
    device = torch.device("cpu")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split="test")

    # keep_ratio=1.0: the ceiling model. The target must be defined over ALL N tokens --
    # that is the point. D7's Part C showed the STE gives gradient to only the K kept
    # tokens, so a dense target over all N is what a distillation target has to supply.
    model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
    sd = torch.load(RUN5, map_location=device, weights_only=True)
    m, u = model.load_state_dict(sd, strict=False)
    print(f"loaded run 5 (missing={len(m)}, unexpected={len(u)})")
    model.eval()

    # transformers 5.x defaults to SDPA, which does not materialise attention weights --
    # `output_attentions=True` then either raises or returns cross_attentions=None. Force
    # eager on the decoder so the weights actually exist. Asserted below rather than
    # trusted: a silent None here would make every number in this script vacuous.
    try:
        model.model.decoder.config._attn_implementation = "eager"
    except Exception as e:                                    # noqa: BLE001
        print(f"  note: could not set eager attention ({e}); continuing and asserting below")

    rows = []
    keep = []            # per-page vectors, retained for the cross-page test in Part 2
    for i in range(args.n):
        img = ds[i]["image"].convert("RGB")
        pv = processor(img, return_tensors="pt").pixel_values
        prompt = f"<s_doc>{json.dumps({'text': build_target_text(ds[i])})}</s>"
        # NOT padded to MAX_LEN. Padding positions are ignored by the training CE, so their
        # cross-attention is noise, and keeping them would hold 4 x (1,16,512,4800) float32
        # = ~630 MB of attention weights alive at once instead of ~380 MB. Truncation to
        # MAX_LEN is kept because training truncates there too.
        ids = processor.tokenizer(prompt, add_special_tokens=False, max_length=MAX_LEN,
                                  truncation=True, return_tensors="pt").input_ids

        with torch.no_grad():
            enc = model.model.encoder(pv).last_hidden_state        # (1, N, 1024)
            N = enc.shape[1]
            out = model.model.decoder(input_ids=ids, encoder_hidden_states=enc,
                                      output_attentions=True, return_dict=True)
            ca = getattr(out, "cross_attentions", None)
            if not ca or ca[0] is None:
                raise SystemExit(
                    "decoder returned no cross_attentions -- the attention implementation is "
                    "not materialising weights (SDPA/flash). Every number below would be "
                    "vacuous, so stopping instead of reporting zeros. Fix: construct the "
                    "backbone with attn_implementation='eager'.")
            # cross_attentions: tuple(layers) of (B, heads, tgt, src). Mean over heads, sum
            # over target positions, mean over layers -> one mass per visual token.
            per_layer = [a[0].mean(0).sum(0) for a in ca]                    # [(N,)] x layers
            layer_attn = torch.stack(per_layer)                              # (L, N)
            attn = layer_attn.mean(0)                                        # (N,)
            score = model.router.scorer(enc).squeeze(-1)[0]                  # (N,)
        print(f"    (target {ids.shape[1]} tokens, {len(ca)} decoder layers, "
              f"{ca[0].shape[1]} heads)")
        del out, ca

        ink = patch_ink(pv, N)[0]
        inkn = ink / (ink.amax() + 1e-9)
        ink_tgt = (inkn > SALIENCY_THRESHOLD).float()

        K = max(1, int(round(N * KEEP)))
        top_a = set(torch.topk(attn, K).indices.tolist())
        top_i = set(torch.topk(ink, K).indices.tolist())
        top_s = set(torch.topk(score, K).indices.tolist())

        r_ai, r_as, r_si = pearson(attn, ink), pearson(attn, score), pearson(score, ink)
        ov_ai = len(top_a & top_i) / K
        ov_as = len(top_a & top_s) / K
        # How concentrated is the attention target? If a handful of tokens hold most of the
        # mass, a BCE against a thresholded version is nearly all-negative and the loss can
        # be minimised by predicting ~0 everywhere -- worth knowing before choosing the form.
        srt = torch.sort(attn, descending=True).values
        frac_topK = float(srt[:K].sum() / srt.sum())
        frac_top5 = float(srt[:max(1, N // 20)].sum() / srt.sum())
        # Where does the ink-thresholded positive set sit? This is the class balance the
        # ink-BCE actually saw in run 9.
        pos_rate = float(ink_tgt.mean())

        rows.append((i, N, r_ai, r_as, r_si, ov_ai, ov_as, frac_topK, frac_top5, pos_rate))
        keep.append({"attn": attn, "ink": ink, "score": score, "layer_attn": layer_attn,
                     "top_a": top_a, "top_i": top_i, "K": K, "N": N,
                     # stride 32 matches patch_ink / cell 7; asserted so a grid change
                     # surfaces here instead of silently scrambling the centroid readout.
                     "gh": pv.shape[-2] // 32, "gw": pv.shape[-1] // 32})
        assert keep[-1]["gh"] * keep[-1]["gw"] == N, (
            f"grid {keep[-1]['gh']}x{keep[-1]['gw']} does not match N={N}")
        print(f"  page {i}: N={N}  r(attn,ink) {r_ai:+.3f}  r(attn,score) {r_as:+.3f}  "
              f"r(score,ink) {r_si:+.3f}  overlap(attn,ink)@K {ov_ai:.3f}  "
              f"overlap(attn,score)@K {ov_as:.3f}  attn mass in top-K {frac_topK:.3f}  "
              f"in top-5% {frac_top5:.3f}  ink pos-rate {pos_rate:.3f}")

    hr()
    print("D8 SUMMARY (mean over pages)")
    hr()
    n = len(rows)
    mr = [sum(r[k] for r in rows) / n for k in range(2, 10)]
    r_ai, r_as, r_si, ov_ai, ov_as, f_k, f_5, pos = mr
    print(f"  | quantity | value |")
    print(f"  |---|---|")
    print(f"  | r(attn, ink) | {r_ai:+.3f} |")
    print(f"  | r(attn, router score) | {r_as:+.3f} |")
    print(f"  | r(router score, ink) | {r_si:+.3f} |")
    print(f"  | top-K overlap attn vs ink | {ov_ai:.3f} |")
    print(f"  | top-K overlap attn vs score | {ov_as:.3f} |")
    print(f"  | attn mass inside top-K | {f_k:.3f} |")
    print(f"  | attn mass inside top-5% | {f_5:.3f} |")
    print(f"  | ink positive rate at thr {SALIENCY_THRESHOLD} | {pos:.3f} |")
    print()
    if r_ai >= 0.8 and ov_ai >= 0.90:
        print("  VERDICT (test 1 of 2): attention IS ink (pre-registered thresholds met).")
        print("  13(b) is 13(c) with extra steps -- D6 already ruled that target out. Drop it.")
        hr()
        return
    elif r_ai <= 0.5 and ov_ai < 0.90:
        print("  Test 1 of 2 PASSED: attention is not ink. This is necessary, NOT sufficient --")
        print("  a page-independent mask would also pass it. Part 2 is the sufficient test.")
    else:
        print("  VERDICT: in between the pre-registered thresholds. Do not round to the")
        print("  preferred answer -- record the numbers and decide explicitly in AGENTS.md.")

    if len(keep) < 2:
        hr()
        print("  Part 2 needs >= 2 pages to compare; re-run with --n 2 or more. Until then")
        print("  test 1's pass is NOT a green light for 13(b).")
        hr()
        return

    hr()
    print("PART 2. IS THE ATTENTION MAP PAGE-DEPENDENT AT ALL?")
    hr()
    print("  A target that is the same mask on every document is maximally 'not ink' and")
    print("  useless: the router would learn a constant, in one step, carrying no information")
    print("  about where THIS page's text is. Ink is the calibration baseline -- two")
    print("  mostly-white forms do share real layout, so ink's own cross-page agreement is")
    print("  the floor that 'content-dependent' must not exceed. Router score is a second")
    print("  baseline: it is a function of encoder features, so it is content-driven by")
    print("  construction even though it is currently anti-correlated with ink.")
    print()

    P = len(keep)
    pairs = [(x, y) for x in range(P) for y in range(x + 1, P)]
    Kx = min(k["K"] for k in keep)

    def cosine(v0, v1):
        v0, v1 = v0.float(), v1.float()
        return float((v0 * v1).sum() / (v0.norm() * v1.norm()).clamp_min(1e-12))

    def mean(z):
        return sum(z) / len(z)

    def topset(v):
        return set(torch.topk(v, Kx).indices.tolist())

    def xpage(name, key):
        """Averaged over all C(P,2) page pairs. The overlap RANGE is printed too: the
        attn-vs-ink gap is small, so a mean that hides its spread would be the same mistake
        as quoting a one-sample ratio."""
        cs, rs, ovs = [], [], []
        for x, y in pairs:
            v0, v1 = keep[x][key], keep[y][key]
            cs.append(cosine(v0, v1))
            rs.append(pearson(v0, v1))
            ovs.append(len(topset(v0) & topset(v1)) / Kx)
        print(f"  | {name} | {mean(cs):+.4f} | {mean(rs):+.4f} | {mean(ovs):.3f} | "
              f"{min(ovs):.3f}-{max(ovs):.3f} |")
        return mean(cs), mean(rs), mean(ovs)

    print(f"  averaged over {len(pairs)} page pair(s) from {P} page(s)")
    print("  | quantity across pages | cosine | pearson r | top-K overlap | overlap range |")
    print("  |---|---|---|---|---|")
    a_cos, a_r, a_ov = xpage("ATTENTION mass", "attn")
    i_cos, i_r, i_ov = xpage("ink (baseline)", "ink")
    xpage("router score (baseline)", "score")
    print(f"  (chance top-K overlap at K/N = {Kx / keep[0]['N']:.2f} is "
          f"{Kx / keep[0]['N']:.3f})")
    print()

    # Where does the mass physically sit? If attention's centre of mass is pinned to the same
    # place on every page while ink's moves, the map is positional. A fixed mask has spread ~0.
    print("  centre of mass of the top-5% tokens, in grid cells (row, col):")
    for tag, key in (("attention", "attn"), ("ink", "ink")):
        rc = []
        for p in range(P):
            v, gh, gw, N = keep[p][key], keep[p]["gh"], keep[p]["gw"], keep[p]["N"]
            idx = torch.topk(v, max(1, N // 20)).indices
            r_m, c_m = float((idx // gw).float().mean()), float((idx % gw).float().mean())
            rc.append((r_m, c_m))
            print(f"    {tag:<10} page{p}: grid {gh}x{gw}  centroid row {r_m:6.2f}  "
                  f"col {c_m:6.2f}")

        def sd(z):
            mu = mean(z)
            return (sum((q - mu) ** 2 for q in z) / len(z)) ** 0.5

        print(f"    {tag:<10} across-page spread: row sd {sd([a for a, _ in rc]):5.2f}  "
              f"col sd {sd([b for _, b in rc]):5.2f}   (~0 would mean a pinned, "
              f"page-independent map)")
    print()

    # Per-layer: the L-layer mean could be averaging an informative layer together with several
    # positional ones. If any single layer has a much higher r(attn, ink) or a much lower
    # cross-page overlap than the mean, the aggregation is the problem, not the signal.
    print("  per-layer breakdown (the mean over layers may be hiding structure):")
    print("  | layer | mean r(attn,ink) | cross-page overlap@K | cross-page cos |")
    print("  |---|---|---|---|")
    L = keep[0]["layer_attn"].shape[0]
    for l in range(L):
        r_l = mean([pearson(keep[p]["layer_attn"][l], keep[p]["ink"]) for p in range(P)])
        ov_l = mean([len(topset(keep[x]["layer_attn"][l]) & topset(keep[y]["layer_attn"][l]))
                     / Kx for x, y in pairs])
        cos_l = mean([cosine(keep[x]["layer_attn"][l], keep[y]["layer_attn"][l])
                      for x, y in pairs])
        print(f"  | {l} | {r_l:+.3f} | {ov_l:.3f} | {cos_l:+.4f} |")
    print()

    hr()
    if a_ov >= i_ov and a_cos >= 0.95:
        print("  VERDICT: the attention map is PAGE-INDEPENDENT (agrees across unrelated")
        print("  documents at least as much as ink does, cosine >= 0.95). It is a positional")
        print("  mask, not a content signal. 13(b) is DEAD -- and for a different reason than")
        print("  D6 killed ink: not 'wrong content' but 'no content'. Do not build it.")
    elif a_ov <= i_ov:
        print("  VERDICT: attention varies with content at least as much as ink does, so it is")
        print("  not a fixed mask. 13(b) survives BOTH tests and is worth building.")
    else:
        print("  VERDICT: attention is more page-invariant than ink but not a constant mask.")
        print("  Partial. Record both numbers in AGENTS.md and decide explicitly -- the")
        print("  informative quantity is the GAP between attn and ink cross-page overlap.")
    hr()


if __name__ == "__main__":
    main()
