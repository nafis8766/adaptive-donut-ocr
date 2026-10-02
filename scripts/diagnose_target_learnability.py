"""Diagnostic D9 -- can THIS router architecture actually learn the attention target?

D8 established that decoder cross-attention is a different target from retained ink
(r(attn,ink) = +0.09) and that it is content-bearing rather than a fixed positional mask
(cross-page cosine 0.56, and its top-5% centroid moves across pages while ink's does not).
Neither of those makes it *learnable*.

The gap D8 leaves open is the one that matters before booking a GPU session. `PatchSaliencyRouter`
scores each token with `Linear(1024,256) -> LayerNorm -> GELU -> Linear(256,1) -> Sigmoid`
applied to that token's own encoder feature. No coordinates, no neighbourhood, no global pooling.
So the router can only represent targets that are a per-token function of the Swin feature.

  - Ink is such a function almost by construction: it is local contrast, and Swin's late-stage
    features encode local texture. Ink is the known-learnable reference.
  - Attention mass may not be. The decoder decides where to look using the whole page and the
    text it has generated so far; if that decision depends on context a single token's feature
    does not carry, the router cannot fit it no matter how dense, coherent and free the target is.

A target can therefore satisfy every requirement D7 laid out and still be unreachable by the
model that has to predict it. That is a structural refutation, independent of D6's accuracy
argument, and it costs one CPU run to check instead of a GPU session to discover.

Method: freeze run 5, extract per-page encoder features + teacher attention + ink, then fit a
FRESH scorer of the identical architecture on a train split of pages and evaluate on held-out
pages. Three targets, same init seed, same optimiser, same steps -- so the only thing that
varies is what is being predicted:

    attn      the proposed 13(b) target (top-K of teacher cross-attention mass)
    ink       known-learnable reference (top-K of patch ink)
    shuffled  known-unlearnable floor (attn target permuted across tokens within each page,
              which destroys the feature->target relation while preserving the marginal)

Held-out pages, not held-out tokens: the router has to generalise across documents, and an MLP
fitting 4800 tokens of one page proves nothing about that.

Metrics. AUC is the ranking metric that matches a top-k selection rule. Retained teacher mass
at K is the more interpretable one and is directly comparable to the retained-ink numbers used
elsewhere in this project: select K tokens by predicted score, report the fraction of the
teacher's total attention mass captured. Reference points are printed alongside -- the teacher's
own top-K (the ceiling, 0.90 from D8) and random selection (the floor, ~K/N).

Falsifiable, pre-registered BEFORE running:

  If AUC(attn) is within ~0.02 of AUC(shuffled) (i.e. ~0.5), the target is not learnable by this
  architecture -> 13(b) is DEAD as specified. The escape hatch would be giving the router
  context it currently lacks (coords, a conv/neighbourhood, or a wider receptive field), which
  is a model change and a separate decision -- record it, do not silently fold it in.

  If AUC(attn) clears the shuffled floor decisively and lands within striking distance of
  AUC(ink), the target is learnable -> build 13(b).

  In between: report both numbers and the retained-mass figures, and decide explicitly. Do not
  round toward the answer that keeps the plan alive.

THIRD THRESHOLD, added after the first run returned held-out AUC 0.979 -- suspiciously high, and
high for a reason the two thresholds above cannot distinguish. A probe can earn a large held-out
AUC by predicting only the component of the target that is IDENTICAL on every page; D8 measured
attention's cross-page pearson r at +0.38, so that component is substantial. Predicting it is
worth nothing for routing -- it is a constant mask, the exact failure D8 Part 2 was built to
catch, one level down.

  The control is the best possible page-INDEPENDENT predictor: the mean teacher map over the
  training pages, no features and no fitting. If the trained probe beats it by <= 0.03 AUC, the
  probe is not reading page-specific content -> treat 13(b) as DEAD. The reportable quantity is
  the LIFT (probe AUC - constant-map AUC), not the probe AUC, and ink's own lift is printed
  beside it for calibration.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 \
        python -u scripts/diagnose_target_learnability.py [--n 8] [--holdout 2]
Read-only w.r.t. the repo. CPU. Prints numbers; interpretation goes in AGENTS.md.
"""
import argparse
import json
import os
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.diagnose_ste_signal import (MAX_LEN, SALIENCY_THRESHOLD,  # noqa: E402,F401
                                         build_target_text, patch_ink)

RUN5 = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
KEEP = 0.50


def hr(c="="):
    print(c * 78)


def auc(scores, labels):
    """Mann-Whitney U / rank AUC. sklearn is not installed in this env, so compute it
    directly. Ties get average ranks, which matters because a saturated sigmoid produces
    plenty of them."""
    scores, labels = scores.flatten().float(), labels.flatten().float()
    n_pos, n_neg = float(labels.sum()), float((1 - labels).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = torch.argsort(scores)
    s_sorted = scores[order]
    ranks = torch.empty_like(s_sorted)
    i = 0
    while i < len(s_sorted):
        j = i
        while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2.0 + 1.0        # 1-based average rank for the tie group
        i = j + 1
    pos_rank_sum = float(ranks[labels[order] == 1].sum())
    return (pos_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def make_scorer(seed):
    """Identical architecture to PatchSaliencyRouter.scorer, including the 0.5 bias init.
    Rebuilt here rather than deep-copied so every target starts from the same fresh weights."""
    torch.manual_seed(seed)
    m = nn.Sequential(
        nn.Linear(1024, 256), nn.LayerNorm(256), nn.GELU(), nn.Linear(256, 1), nn.Sigmoid())
    nn.init.constant_(m[-2].bias, 0.5)
    return m


def fit_probe(feats_tr, tgt_tr, steps, lr, seed):
    """BCE on the sigmoid OUTPUT (a probability), matching what the real saliency loss does --
    see D4/D5: this scorer already ends in Sigmoid, so binary_cross_entropy_with_logits would
    be the double-sigmoid bug all over again."""
    m = make_scorer(seed)
    opt = torch.optim.Adam(m.parameters(), lr=lr)
    for _ in range(steps):
        opt.zero_grad()
        p = m(feats_tr).squeeze(-1).clamp(1e-6, 1 - 1e-6)
        loss = F.binary_cross_entropy(p, tgt_tr)
        loss.backward()
        opt.step()
    return m, float(loss.detach())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="total FUNSD pages to extract")
    ap.add_argument("--holdout", type=int, default=2, help="pages reserved for evaluation")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--split", default="test", choices=["train", "test"])
    args = ap.parse_args()
    assert args.n > args.holdout >= 1, "need at least one train page and one held-out page"

    from datasets import load_dataset
    from transformers import DonutProcessor

    from src.model import AdaptiveDonutOCR

    torch.manual_seed(0)
    device = torch.device("cpu")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split=args.split)

    model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
    sd = torch.load(RUN5, map_location=device, weights_only=True)
    m_, u_ = model.load_state_dict(sd, strict=False)
    print(f"loaded run 5 (missing={len(m_)}, unexpected={len(u_)})  split={args.split}")
    model.eval()
    try:
        model.model.decoder.config._attn_implementation = "eager"
    except Exception as e:                                        # noqa: BLE001
        print(f"  note: could not set eager attention ({e}); asserted below")

    hr()
    print(f"EXTRACTING {args.n} PAGES (encoder features, teacher attention, ink)")
    hr()
    pages = []
    for i in range(args.n):
        img = ds[i]["image"].convert("RGB")
        pv = processor(img, return_tensors="pt").pixel_values
        prompt = f"<s_doc>{json.dumps({'text': build_target_text(ds[i])})}</s>"
        ids = processor.tokenizer(prompt, add_special_tokens=False, max_length=MAX_LEN,
                                 truncation=True, return_tensors="pt").input_ids
        with torch.no_grad():
            enc = model.model.encoder(pv).last_hidden_state
            N = enc.shape[1]
            out = model.model.decoder(input_ids=ids, encoder_hidden_states=enc,
                                      output_attentions=True, return_dict=True)
            ca = getattr(out, "cross_attentions", None)
            if not ca or ca[0] is None:
                raise SystemExit(
                    "decoder returned no cross_attentions -- attention weights are not being "
                    "materialised (SDPA/flash). Every number below would be vacuous, so "
                    "stopping. Fix: build the backbone with attn_implementation='eager'.")
            attn = torch.stack([a[0].mean(0).sum(0) for a in ca]).mean(0)
        del out, ca
        ink = patch_ink(pv, N)[0]
        pages.append({"enc": enc[0], "attn": attn, "ink": ink, "N": N})
        print(f"  page {i}: N={N}, target {ids.shape[1]} tokens")

    N = pages[0]["N"]
    K = max(1, int(round(N * KEEP)))
    assert all(p["N"] == N for p in pages), "pages disagree on N; the probe assumes one grid"
    n_tr = args.n - args.holdout
    print(f"\n  K = {K} of N = {N}  |  {n_tr} train page(s), {args.holdout} held-out page(s)")

    def topk_target(v):
        t = torch.zeros_like(v)
        t[torch.topk(v, K).indices] = 1.0
        return t

    # Build the three target sets. `shuffled` permutes the attention target WITHIN each page,
    # so the class balance is identical and only the feature->target relation is destroyed.
    targets = {}
    for name in ("attn", "ink", "shuffled"):
        per_page = []
        for pi, p in enumerate(pages):
            if name == "shuffled":
                g = torch.Generator().manual_seed(1234 + pi)
                per_page.append(topk_target(p["attn"])[torch.randperm(N, generator=g)])
            else:
                per_page.append(topk_target(p[name]))
        targets[name] = per_page

    feats_tr = torch.cat([p["enc"] for p in pages[:n_tr]], 0)
    hr()
    print("PROBE RESULTS (held-out pages; same init seed and optimiser for every target)")
    hr()
    print("  | target | final BCE | AUC train | AUC held-out | retained teacher-attn mass @K |")
    print("  |---|---|---|---|---|")

    res = {}
    for name in ("attn", "ink", "shuffled"):
        tgt_tr = torch.cat(targets[name][:n_tr], 0)
        probe, final_loss = fit_probe(feats_tr, tgt_tr, args.steps, args.lr, seed=7)
        with torch.no_grad():
            a_tr = auc(probe(feats_tr).squeeze(-1), tgt_tr)
            aucs, masses = [], []
            for pi in range(n_tr, args.n):
                p = pages[pi]
                pred = probe(p["enc"]).squeeze(-1)
                aucs.append(auc(pred, targets[name][pi]))
                # Always scored against the TEACHER's attention mass, whatever the probe was
                # trained on -- that is what makes the three rows comparable.
                sel = torch.topk(pred, K).indices
                masses.append(float(p["attn"][sel].sum() / p["attn"].sum()))
        a_ho, mass = sum(aucs) / len(aucs), sum(masses) / len(masses)
        res[name] = (a_ho, mass)
        print(f"  | {name} | {final_loss:.4f} | {a_tr:.3f} | **{a_ho:.3f}** | {mass:.3f} |")

    # Reference points for the retained-mass column.
    ceil_mass = sum(float(p["attn"][torch.topk(p["attn"], K).indices].sum() / p["attn"].sum())
                    for p in pages[n_tr:]) / args.holdout
    rand_mass = []
    for pi in range(n_tr, args.n):
        g = torch.Generator().manual_seed(99 + pi)
        sel = torch.randperm(N, generator=g)[:K]
        rand_mass.append(float(pages[pi]["attn"][sel].sum() / pages[pi]["attn"].sum()))
    rand_mass = sum(rand_mass) / len(rand_mass)
    print(f"  | _teacher's own top-K (ceiling)_ | - | - | 1.000 | {ceil_mass:.3f} |")
    print(f"  | _random selection (floor)_ | - | - | 0.500 | {rand_mass:.3f} |")

    # NO-TRAINING CONTROL, and the one that decides whether the probe result means anything.
    # A high held-out AUC can be earned entirely by predicting the component of the target that
    # is the SAME on every page. D8 measured attention's cross-page pearson r at +0.38, so that
    # component is substantial. The best possible page-independent predictor is the mean teacher
    # map over the training pages -- no features, no fitting. If the trained probe scores barely
    # above this, it is not reading page-specific content, 13(b)'s target collapses toward a
    # constant mask after all, and D8's Part 2 conclusion would need revisiting.
    base = {}
    for name in ("attn", "ink"):
        mean_map = torch.stack([pages[p][name] for p in range(n_tr)]).mean(0)
        aucs, masses = [], []
        for pi in range(n_tr, args.n):
            aucs.append(auc(mean_map, targets[name][pi]))
            sel = torch.topk(mean_map, K).indices
            masses.append(float(pages[pi]["attn"][sel].sum() / pages[pi]["attn"].sum()))
        base[name] = sum(aucs) / len(aucs)
        print(f"  | _mean {name} map, no features (page-INDEPENDENT control)_ | - | - | "
              f"{base[name]:.3f} | {sum(masses) / len(masses):.3f} |")
    print()

    a_attn, a_ink, a_shuf = res["attn"][0], res["ink"][0], res["shuffled"][0]
    lift = a_attn - base["attn"]
    print(f"  page-specific lift for attn: probe {a_attn:.3f} - constant-map control "
          f"{base['attn']:.3f} = {lift:+.3f}")
    print(f"  page-specific lift for ink : probe {a_ink:.3f} - constant-map control "
          f"{base['ink']:.3f} = {a_ink - base['ink']:+.3f}")
    hr()
    if abs(a_attn - a_shuf) <= 0.02:
        print("  VERDICT: attention is NOT learnable by this router architecture -- held-out AUC")
        print(f"  {a_attn:.3f} is within 0.02 of the shuffled floor {a_shuf:.3f}. 13(b) is DEAD")
        print("  as specified, for a STRUCTURAL reason and not D6's accuracy reason: the target")
        print("  is not a per-token function of the encoder feature the scorer sees. Reviving it")
        print("  requires giving the router context it does not have (coords / neighbourhood),")
        print("  which is a MODEL change -- record it as a separate decision, do not fold it in.")
    elif lift <= 0.03:
        print(f"  VERDICT: the probe ({a_attn:.3f}) barely beats a CONSTANT MAP ({base['attn']:.3f},")
        print(f"  lift {lift:+.3f}). It is predicting the page-invariant part of attention, not")
        print("  page-specific content. 13(b) would teach the router a near-constant mask -- the")
        print("  failure mode D8 Part 2 was built to catch, showing up one level down. Treat")
        print("  13(b) as DEAD unless a target with real page-specific lift can be constructed.")
    elif a_attn > a_shuf + 0.02 and a_attn >= a_ink - 0.10:
        print("  VERDICT: attention is learnable -- held-out AUC clears the shuffled floor, beats")
        print(f"  the constant-map control by {lift:+.3f}, and is within 0.10 of ink's. 13(b)")
        print("  survives D8 and D9. Build it.")
    else:
        print("  VERDICT: partially learnable -- above the shuffled floor but materially below")
        print("  ink. Record both numbers in AGENTS.md and decide explicitly; the retained-mass")
        print("  column against the ceiling/floor rows is the number to judge it on, since that")
        print("  is what a top-k selection rule actually delivers.")
    print()
    print("  REMINDER, not optional: every number above is scored against the teacher's own")
    print("  attention. A probe trained on attention winning the retained-attention-mass column")
    print("  is close to tautological. D6 is the standing warning -- fitting the ink proxy")
    print("  HARDER cost accuracy at two of three budgets. 13(b) is only validated by recall on")
    print("  a real run, and D9 establishes reachability, not merit.")
    hr()


if __name__ == "__main__":
    main()
