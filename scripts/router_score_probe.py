"""Step 0 diagnostic: can run 5's router actually RANK tokens?

Runs locally on CPU. No GPU, no training, no Kaggle session.

WHY THIS EXISTS. Every run so far trained at keep_ratio=1.0, where K = N: top-k
keeps every token and nothing is ever dropped. The STE multiplier
`1.0 + (w - w.detach())` has value exactly 1.0, so the forward pass is unaffected
by the scores while gradient still reaches the scorer. The router therefore
learned a "does scaling this token's magnitude help" proxy and has never once
received feedback about the consequence of REMOVING a token. Before spending
~16 GPU-hours on a trained-with-pruning sweep, find out whether its scores can
rank anything at all.

Three ways the router could be useless, each checked separately:

  A. NEVER TRAINED. The scorer's init is distinctive (LayerNorm weight 1.0 /
     bias 0.0, final Linear bias constant 0.5). If those are untouched in the
     checkpoint, no gradient ever moved them.
  B. FLAT / SATURATED. Sigmoid-bounded scores with nothing in the objective
     rewarding separation. If std is ~0 or everything pins to 0/1, top-k is
     decided by float noise and index order, i.e. arbitrary.
  C. CONTENT-BLIND POSITIONAL PRIOR. The subtle one, and the most likely.
     If the router assigns roughly the same score to position i on EVERY image,
     it is a fixed mask, not adaptive routing -- it would drop the same regions
     regardless of what is on the page. Measured as rank correlation between
     different images' score vectors, plus overlap of their top-k selections.
     A fixed mask can still beat random (page margins really are emptier), so
     this must be distinguished from genuine saliency, not lumped in with it.

D and E add the controls those three miss: a random-init router scored on the
same features (B and C look identical for a trained router and an arbitrary
projection), and a clustering baseline (Swin features are spatially smooth, so
ANY smooth function of them looks contiguous).

F is the test that actually decides it, and the reason A-E are not enough:
every one of A-E is a property a BAD router shares with a good one. Trained,
well-spread, content-dependent and spatially clustered are all true of a router
that ranks blank paper above text -- blank regions are contiguous too. F asks
the only question that matters: does the kept half of the tokens contain more
than half of the page's ink?

Output: per-image stats, cross-image agreement, ink-retention vs random and vs
an ink oracle, a 4-panel overlay PNG per image, scores cached to .npz, and an
explicit verdict.

Usage:
    PYTHONPATH=. HF_HUB_OFFLINE=1 python scripts/router_score_probe.py [--n 4]
"""
import argparse
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import AdaptiveDonutOCR  # noqa: E402
from src.router import PatchSaliencyRouter  # noqa: E402

CKPT = r"c:\Users\Nafis\Desktop\Project\run 5\checkpoints\adaptive_donut_funsd.pt"
OUTDIR = r"c:\Users\Nafis\Desktop\Project\visualizations"

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=4, help="how many FUNSD test images to probe")
p.add_argument("--keep-ratio", type=float, default=0.5, help="ratio to evaluate top-k behaviour at")
args = p.parse_args()

concerns = []


def rankdata(x):
    """Average-rank transform (ties shared), so Spearman is exact without scipy."""
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=np.float64)
    ranks[order] = np.arange(len(x), dtype=np.float64)
    # average ties
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d else float("nan")


def pearson(a, b):
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    return float((a * b).sum() / d) if d else float("nan")


# =============================================================== A. did it train?
print("=" * 74)
print("A. Did the router train at all?")
print("=" * 74)

sd = torch.load(CKPT, map_location="cpu", weights_only=True)
router_keys = sorted(k for k in sd if k.startswith("router."))
print(f"checkpoint: {os.path.basename(CKPT)}  ({len(sd)} tensors, {len(router_keys)} router)")
if not router_keys:
    print("  FAIL: no router.* tensors in the checkpoint at all")
    concerns.append("router weights absent from checkpoint")

# The init is distinctive, so deviation from it is proof of gradient, without
# needing to diff against another run's checkpoint.
fresh = PatchSaliencyRouter(hidden_dim=1024, reduction_dim=256)
init_probes = [
    ("scorer.1.weight", 1.0, "LayerNorm weight (init 1.0)"),
    ("scorer.1.bias", 0.0, "LayerNorm bias (init 0.0)"),
    ("scorer.3.bias", 0.5, "final Linear bias (init const 0.5)"),
]
moved_any = False
for key, init_val, label in init_probes:
    full = f"router.{key}"
    if full not in sd:
        print(f"  {label}: MISSING from checkpoint")
        continue
    t = sd[full].float()
    delta = (t - init_val).abs().max().item()
    moved = delta > 1e-6
    moved_any |= moved
    print(f"  {label}: max|w - init| = {delta:.6g}  -> {'MOVED' if moved else 'UNCHANGED'}")

# also: how far did the scorer move overall, relative to its own scale
tot = sum(sd[f"router.{k}"].numel() for k, _, _ in init_probes if f"router.{k}" in sd)
print(f"  verdict: router {'DID train' if moved_any else 'did NOT train'} "
      f"({tot} params inspected of {sum(sd[k].numel() for k in router_keys)} total)")
if not moved_any:
    concerns.append("router weights never moved from init")

# =========================================================== build model + encode
print()
print("=" * 74)
print(f"B. Score distribution over {args.n} FUNSD test images")
print("=" * 74)

from datasets import load_dataset  # noqa: E402
from transformers import DonutProcessor  # noqa: E402

t0 = time.perf_counter()
processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True)
missing, unexpected = model.load_state_dict(sd, strict=False)
print(f"loaded (missing={len(missing)}, unexpected={len(unexpected)}) in {time.perf_counter()-t0:.1f}s")
if any(k.startswith("router.") for k in missing):
    concerns.append("router keys missing on load")
model.eval()

ds = load_dataset("nielsr/funsd", split="test")
n = min(args.n, len(ds))

# A randomly-initialized router, scored on the SAME encoder outputs. This is the
# control that separates "learned saliency" from "an arbitrary projection that
# happens to vary per image" -- the two hypotheses that produce identical
# distribution stats. Seeded so the comparison is reproducible.
torch.manual_seed(0)
rand_router = PatchSaliencyRouter(hidden_dim=1024, reduction_dim=256).eval()

all_scores, all_norms, all_rand, all_contrast, all_dark = [], [], [], [], []
PVHW = None
for i in range(n):
    img = ds[i]["image"].convert("RGB")
    pv = processor(img, return_tensors="pt").pixel_values
    PVHW = (pv.shape[-2], pv.shape[-1])       # authoritative grid source
    t1 = time.perf_counter()
    with torch.no_grad():
        vis = model.model.encoder(pv).last_hidden_state       # (1, N, D)
        scores = model.router.scorer(vis).squeeze(-1).squeeze(0)  # (N,)
        rscores = rand_router.scorer(vis).squeeze(-1).squeeze(0)
    s = scores.numpy().astype(np.float64)
    norms = vis.squeeze(0).norm(dim=-1).numpy().astype(np.float64)
    all_scores.append(s)
    all_norms.append(norms)
    all_rand.append(rscores.numpy().astype(np.float64))

    # Ink map on the SAME grid the tokens live on. Swin-B's total stride is 32
    # (patch 4, three downsamples), so token t covers a 32x32 block of the
    # PREPROCESSED tensor -- which is what the encoder saw, unlike the raw PIL
    # image, whose aspect and padding differ.
    im_mean = torch.tensor(processor.image_processor.image_mean).view(3, 1, 1)
    im_std = torch.tensor(processor.image_processor.image_std).view(3, 1, 1)
    rgb = (pv[0] * im_std + im_mean).clamp(0, 1)
    gray = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    blocks = gray.unfold(0, 32, 32).unfold(1, 32, 32).reshape(
        pv.shape[-2] // 32, pv.shape[-1] // 32, -1)
    # Two proxies, because they fail differently: within-patch std is high only
    # for glyph edges and is blind to whether padding is black or white, while
    # darkness is the more literal "how much toner" but would score black
    # padding as maximum ink. Agreement between them is the check.
    all_contrast.append(blocks.std(dim=-1).flatten().numpy().astype(np.float64))
    all_dark.append((1.0 - blocks.mean(dim=-1)).flatten().numpy().astype(np.float64))

    N = len(s)
    K = max(1, int(round(N * args.keep_ratio)))
    srt = np.sort(s)[::-1]
    boundary_gap = float(srt[K - 1] - srt[K]) if K < N else float("nan")
    print(f"  img {i}: N={N}  mean={s.mean():.4f} std={s.std():.4f} "
          f"min={s.min():.4f} max={s.max():.4f}")
    print(f"          unique={len(np.unique(s))}/{N}  "
          f">0.99: {100*(s>0.99).mean():.1f}%  <0.01: {100*(s<0.01).mean():.1f}%  "
          f"top-k boundary gap @keep={args.keep_ratio}: {boundary_gap:.3g}  "
          f"({time.perf_counter()-t1:.1f}s)")

S = np.stack(all_scores)          # (n, N)
NRM = np.stack(all_norms)
RND = np.stack(all_rand)
CON = np.stack(all_contrast)
DRK = np.stack(all_dark)

flat = S.std(axis=1).mean() < 1e-3
sat = ((S > 0.99).mean() + (S < 0.01).mean()) > 0.9
gapless = np.mean([np.sort(s)[::-1][max(1, int(round(len(s)*args.keep_ratio)))-1]
                   - np.sort(s)[::-1][max(1, int(round(len(s)*args.keep_ratio)))]
                   for s in all_scores]) < 1e-6
print(f"\n  mean per-image std = {S.std(axis=1).mean():.5f} -> "
      f"{'FLAT (cannot rank)' if flat else 'has spread'}")
if flat:
    concerns.append("scores are flat; top-k is arbitrary")
if sat:
    concerns.append("scores saturated at sigmoid extremes")
if gapless:
    concerns.append("no gap at the top-k boundary; selection decided by ties")

# ================================================= C. content-blind positional prior?
print()
print("=" * 74)
print("C. Is the ranking content-dependent, or a fixed positional mask?")
print("=" * 74)

if n < 2:
    print("  need >=2 images; skipped")
else:
    rhos, jacs = [], []
    N = S.shape[1]
    K = max(1, int(round(N * args.keep_ratio)))
    topk_sets = [set(np.argsort(s)[::-1][:K].tolist()) for s in all_scores]
    for a in range(n):
        for b in range(a + 1, n):
            rhos.append(spearman(S[a], S[b]))
            inter = len(topk_sets[a] & topk_sets[b])
            jacs.append(inter / len(topk_sets[a] | topk_sets[b]))
    rho = float(np.mean(rhos))
    jac = float(np.mean(jacs))
    # a random top-K selection of the same size overlaps by chance at this rate
    chance_jac = (K / N) / (2 - K / N)
    print(f"  cross-image Spearman rho (score vs position): {rho:.3f}")
    print(f"  top-{args.keep_ratio:.0%} selection Jaccard between images: {jac:.3f} "
          f"(chance {chance_jac:.3f})")
    if rho > 0.9:
        print("  -> NEARLY IDENTICAL across images: this is a FIXED POSITIONAL MASK.")
        print("     It may still beat random (margins are genuinely emptier), but it")
        print("     is not adaptive routing and will not improve with harder pages.")
        concerns.append("router is a content-blind positional prior")
    elif rho > 0.6:
        print("  -> strong positional component, some content sensitivity")
    else:
        print("  -> content-dependent ranking (differs substantially per image)")

    r_norm = float(np.mean([pearson(S[i], NRM[i]) for i in range(n)]))
    print(f"  score vs token L2-norm correlation: {r_norm:.3f} "
          f"({'learned a magnitude proxy' if abs(r_norm) > 0.5 else 'not just magnitude'})")

# ============================== D. trained router vs a randomly-initialized one
print()
print("=" * 74)
print("D. Did training actually reorient the ranking, or is it a random projection?")
print("=" * 74)
print("  Sections B and C cannot tell these apart: an untrained random projection of")
print("  encoder features is ALSO well-spread, content-varying and position-blind.")

N = S.shape[1]
K = max(1, int(round(N * args.keep_ratio)))
rho_tr = float(np.mean([spearman(S[i], RND[i]) for i in range(n)]))
jac_tr = float(np.mean([
    len(set(np.argsort(S[i])[::-1][:K].tolist()) & set(np.argsort(RND[i])[::-1][:K].tolist()))
    / len(set(np.argsort(S[i])[::-1][:K].tolist()) | set(np.argsort(RND[i])[::-1][:K].tolist()))
    for i in range(n)]))
chance_jac = (K / N) / (2 - K / N)
print(f"  Spearman(trained, random-init) per image: {rho_tr:.3f}")
print(f"  top-{args.keep_ratio:.0%} selection Jaccard vs random-init: {jac_tr:.3f} "
      f"(chance {chance_jac:.3f}, identical 1.000)")
if abs(rho_tr) > 0.5:
    print("  -> the trained ranking largely AGREES with an untrained projection:")
    print("     training barely reoriented it, so expect it to track random pruning.")
    concerns.append("trained ranking ~= untrained random projection")
else:
    print("  -> training genuinely reoriented the ranking away from its init.")
    print("     Necessary but NOT sufficient: different-from-random is not the same")
    print("     as better-than-random. Only the sweep's random control settles that.")

# ==================== E. does the selection track spatial structure (i.e. text)?
print()
print("=" * 74)
print("E. Is the kept set spatially clustered, as text regions would be?")
print("=" * 74)

gh, gw = (PVHW[0] // 32, PVHW[1] // 32) if PVHW else (0, 0)
if gh * gw != N:
    gh = int(round(np.sqrt(N * PVHW[0] / PVHW[1]))) if PVHW else 0
    gw = N // max(gh, 1)


def neighbour_agreement(mask2d):
    """Fraction of 4-adjacent pairs where both ends are kept, among pairs with a kept end."""
    keep = mask2d
    pairs = both = 0
    for sh in ((0, 1), (1, 0)):
        a = keep[: keep.shape[0] - sh[0], : keep.shape[1] - sh[1]]
        b = keep[sh[0]:, sh[1]:]
        pairs += int((a | b).sum())
        both += int((a & b).sum())
    return both / pairs if pairs else float("nan")


if gh * gw == N:
    clus, rclus, initclus = [], [], []
    rng = np.random.default_rng(0)
    for i in range(n):
        m = np.zeros(N, dtype=bool)
        m[np.argsort(S[i])[::-1][:K]] = True
        clus.append(neighbour_agreement(m.reshape(gh, gw)))
        rm = np.zeros(N, dtype=bool)
        rm[rng.choice(N, size=K, replace=False)] = True
        rclus.append(neighbour_agreement(rm.reshape(gh, gw)))
        # The control that matters: Swin features are spatially SMOOTH, so any
        # smooth function of them clusters -- including an untrained projection.
        # Beating a random *mask* therefore proves nothing on its own.
        im_ = np.zeros(N, dtype=bool)
        im_[np.argsort(RND[i])[::-1][:K]] = True
        initclus.append(neighbour_agreement(im_.reshape(gh, gw)))
    c, rc, ic = float(np.mean(clus)), float(np.mean(rclus)), float(np.mean(initclus))
    print(f"  grid {gh}x{gw}, keeping top {K}/{N}")
    print(f"  neighbour agreement -- router: {c:.3f}   random-INIT router: {ic:.3f}   "
          f"random mask: {rc:.3f}")
    if c <= rc * 1.05:
        print("  -> salt-and-pepper: no more clustered than a random mask. The router")
        print("     is not tracking text regions, whatever else it is scoring.")
        concerns.append("kept set no more spatially clustered than random")
    elif c <= ic * 1.05:
        print("  -> clustered, but NO MORE THAN AN UNTRAINED ROUTER. The clustering is")
        print("     inherited from the smoothness of Swin features, not learned. This")
        print("     is weak evidence, not the text-tracking it looks like.")
        concerns.append("clustering matches an untrained projection (feature smoothness)")
    else:
        print("  -> clustered ABOVE the untrained projection: the contiguity is learned,")
        print("     not merely inherited from feature smoothness.")
else:
    print(f"  skipped: N={N} does not factor into a grid from {PVHW}")

# =============== F. does the kept set actually contain the page's ink (=text)?
print()
print("=" * 74)
print("F. Does pruning preserve the TEXT, or throw it away?")
print("=" * 74)
print("  The decisive test, and the one all of A-E only circle around. Keeping 50%")
print("  of tokens is only useful if those tokens hold well over 50% of the page's")
print("  ink. At ~50% the router is ink-blind; below, it is actively wrong.")

rng2 = np.random.default_rng(1)


def retained(weight, order):
    """Fraction of total `weight` captured by the top-K under `order` (desc)."""
    keep = np.argsort(order)[::-1][:K]
    return float(weight[keep].sum() / weight.sum()) if weight.sum() else float("nan")


for label, W in (("within-patch contrast", CON), ("darkness", DRK)):
    r_router = float(np.mean([retained(W[i], S[i]) for i in range(n)]))
    r_neg = float(np.mean([retained(W[i], -S[i]) for i in range(n)]))
    r_init = float(np.mean([retained(W[i], RND[i]) for i in range(n)]))
    r_rand = float(np.mean([retained(W[i], rng2.random(N)) for i in range(n)]))
    r_oracle = float(np.mean([retained(W[i], W[i]) for i in range(n)]))
    corr = float(np.mean([pearson(S[i], W[i]) for i in range(n)]))
    print(f"\n  {label}:")
    print(f"    Pearson(score, {label}) = {corr:+.3f}")
    print(f"    retained by top-{args.keep_ratio:.0%} -- router: {r_router:.3f}   "
          f"NEGATED: {r_neg:.3f}   random-init: {r_init:.3f}   "
          f"random: {r_rand:.3f}   oracle: {r_oracle:.3f}")
    if r_router < r_rand:
        print(f"    -> WORSE THAN RANDOM: the router preferentially discards {label}.")
        concerns.append(f"router retains less {label} than random pruning")
        # An inverted ranking is not a dead ranking. If negating it beats random by
        # about as much as the forward direction loses, the scorer found real
        # structure and merely assigned it the wrong sign -- a different, and much
        # more fixable, failure than having learned nothing.
        if r_neg > r_rand * 1.05:
            gap = (r_neg - r_rand) / max(r_oracle - r_rand, 1e-9)
            print(f"    -> but NEGATING it beats random ({r_neg:.3f} vs {r_rand:.3f}), "
                  f"closing {gap:.0%} of the gap to oracle.")
            print(f"       The ranking carries real signal with an inverted sign.")
    elif r_router < r_rand * 1.05:
        print(f"    -> INK-BLIND: indistinguishable from random pruning on {label}.")
        concerns.append(f"router no better than random at retaining {label}")
    else:
        head = (r_router - r_rand) / max(r_oracle - r_rand, 1e-9)
        print(f"    -> retains more than random, closing {head:.0%} of the gap to oracle.")


# ======================================================================= overlays
print()
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(OUTDIR, exist_ok=True)
    # Grid comes from the real pixel_values shape, not processor.image_processor.size
    # -- that attribute is a SizeDict in transformers 5.x and raises TypeError on
    # integer indexing.
    if gh * gw == N:
        for i in range(n):
            fig, ax = plt.subplots(1, 4, figsize=(20, 5))
            ax[0].imshow(ds[i]["image"].convert("RGB"))
            ax[0].set_title(f"FUNSD test #{i}")
            ax[1].imshow(CON[i].reshape(gh, gw), cmap="bone_r")
            ax[1].set_title("where the ink is (patch contrast)")
            im = ax[2].imshow(S[i].reshape(gh, gw), cmap="inferno")
            ax[2].set_title(f"router saliency ({gh}x{gw})")
            fig.colorbar(im, ax=ax[2], fraction=0.046)
            m = np.zeros(N, dtype=bool)
            m[np.argsort(S[i])[::-1][:K]] = True
            ax[3].imshow(m.reshape(gh, gw), cmap="gray")
            ax[3].set_title(f"kept at keep_ratio={args.keep_ratio}")
            for a in ax:
                a.axis("off")
            out = os.path.join(OUTDIR, f"router_saliency_{i}.png")
            fig.tight_layout()
            fig.savefig(out, dpi=110)
            plt.close(fig)
        print(f"overlays: {OUTDIR}\\router_saliency_0..{n-1}.png  (grid {gh}x{gw})")
    else:
        print(f"overlay skipped: N={N} does not factor into a grid from {PVHW}")
except ImportError:
    print("overlay skipped: matplotlib not installed")

np.savez(os.path.join(OUTDIR, "router_scores.npz"), scores=S, norms=NRM,
         rand_scores=RND, contrast=CON, darkness=DRK)
print(f"scores cached: {OUTDIR}\\router_scores.npz")

# ======================================================================== verdict
print()
print("=" * 74)
if not concerns:
    print("VERDICT: router produces a content-dependent, well-spread ranking.")
    print("  The eval-only sweep is worth booking a GPU for, and the random-pruning")
    print("  control row is what will show whether that ranking is actually useful.")
else:
    print("VERDICT: the router is unlikely to prune meaningfully. Concerns:")
    for c in concerns:
        print(f"  - {c}")
    print("  Training WITH pruning is mandatory, not optional: an eval-only sweep on")
    print("  these weights would measure a broken ranking and invite the wrong")
    print("  conclusion ('pruning ruins OCR') instead of the right one ('this router")
    print("  was never trained to prune'). Run one keep_ratio=0.5 row to pin the")
    print("  floor, then spend the GPU budget on training WITH pruning on.")
print("=" * 74)
