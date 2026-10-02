"""Port the selection-ablation machinery into the Kaggle notebook (Pending 1b/1c/1d).

WHY A PATCH AND NOT A NEW CELL: the notebook is SELF-CONTAINED. It carries its own
copy of `PatchSaliencyRouter` (cell 4) and `AdaptiveDonutOCR` (cell 7) and never
imports `src/`. So none of the `select_mode` work exists there -- an eval cell alone
would call a `select_mode=` argument that does not exist. Three patches:

  A. cell 4  -- `PatchSaliencyRouter.forward` gains `select_scores` / `invert`, and
                the STE is gated off when an external ranking is supplied (gradient
                through a ranking the scorer did not produce is meaningless).
  B. cell 7  -- `SELECT_MODES`, `patch_ink()`, `stratified_scores()` added above the
                model; `generate()` gains `select_mode=` and reports `retained_ink`.
  C. new cell after 14 -- the ablation harness itself: 1b's 5 rows, 1d's 2 stratified
                rows, and 1c's keep_ratio sweep, with per-image line coverage.

The code in A and B is a port of the already-verified `src/router.py` and
`src/model.py`. `scripts/verify_selection_ablation.py` checks the notebook's copies
against those originals NUMERICALLY rather than by eye, because a divergence here
would silently make the Kaggle rows non-comparable to the local ones.

WHY THE ROWS ARE WHAT THEY ARE (evidence, AGENTS.md D1/D2 + the local n=2/n=4 rows):

  * `random` is the FLOOR, not a formality. D1 measured the trained router as
    anti-correlated with patch ink (r ~ -0.24), so uniform noise retains more text
    (0.50) than the learned scores (0.34-0.38). Local rows: random beats negated by
    14-21 pts of recall. A router that cannot beat noise is not a router.
  * `ink` is the CEILING and the row that could have killed the whole plan. Local
    n=4: oracle 83.66 vs full-page 83.67 -- half the tokens are genuinely droppable,
    so Pending 1a is not wasted effort.
  * `stratified*` tests whether the bug is the SELECTION RULE rather than the scorer.
    D2: the router's *minimum* text-line ink coverage is 0.000 while its total
    retained ink looks unremarkable, and recall is gated by the worst line. If a
    per-grid-row budget fixes it, 4 GPU-hours of retraining is the wrong fix.
  * keep_ratio in {1.0, 0.75, 0.5, 0.35} because 1c needs the accuracy/cost CURVE,
    and because GW=60 makes the per-row budget integral at every one of them
    (60/45/30/21), so the stratified rows are exact per-row top-k rather than the
    graceful-degradation path.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/patch_notebook_selection_ablation.py
"""
import ast
import json
import os
import shutil

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
BAK = NB + ".bak-selection-ablation"

if not os.path.exists(BAK):
    shutil.copyfile(NB, BAK)
    print(f"backup written: {os.path.basename(BAK)}")
else:
    print(f"backup already exists, left as-is: {os.path.basename(BAK)}")

nb = json.loads(open(NB, encoding="utf-8").read())
cells = nb["cells"]


def get(i):
    return "".join(cells[i]["source"])


def put(i, src):
    cells[i]["source"] = src.splitlines(keepends=True)
    ast.parse(src)          # a patched cell that cannot parse must never be written


def sub(src, old, new, what):
    """Replace exactly once. Assert, don't hope -- a 0-hit patch is a silent no-op
    and a 2-hit patch corrupts the second site."""
    n = src.count(old)
    assert n == 1, f"{what}: expected exactly 1 occurrence, found {n}"
    print(f"  patched: {what}")
    return src.replace(old, new)


# ======================================================================= PATCH A
print("\nA. cell 4 -- PatchSaliencyRouter.forward gains select_scores / invert")
c4 = get(4)
assert "class PatchSaliencyRouter" in c4, "cell 4 is not the router cell"

c4 = sub(
    c4,
    "    def forward(self, tokens, keep_ratio=0.35, coords=None, use_ste=True):",
    "    def forward(self, tokens, keep_ratio=0.35, coords=None, use_ste=True,\n"
    "                select_scores=None, invert=False):\n"
    "        \"\"\"select_scores: (B, N) ranking signal used INSTEAD of the learned scores\n"
    "        (uniform noise for a random control, patch ink for an oracle, a stratified\n"
    "        key for a per-row budget). The learned `scores` are still computed and\n"
    "        returned, so reporting is unaffected. invert: take the LOWEST-ranked\n"
    "        tokens. Both are eval-only; see AGENTS.md Diagnostic D1/D2.\"\"\"",
    "cell 4 forward signature",
)

c4 = sub(
    c4,
    "        topk_scores, topk_indices = torch.topk(scores.squeeze(-1), k=K, dim=1,"
    " largest=True, sorted=True)",
    "        if select_scores is not None:\n"
    "            if select_scores.shape[:2] != (B, N):\n"
    "                raise ValueError(\n"
    "                    f'select_scores must be (B, N) = {(B, N)}, got"
    " {tuple(select_scores.shape)}')\n"
    "            rank_by = select_scores.reshape(B, N).to(scores.dtype)\n"
    "        else:\n"
    "            rank_by = scores.squeeze(-1)\n"
    "        topk_scores, topk_indices = torch.topk(rank_by, k=K, dim=1,"
    " largest=not invert, sorted=True)",
    "cell 4 topk ranking signal",
)

c4 = sub(
    c4,
    "        if self.training and use_ste:",
    "        # STE is skipped under an external ranking: topk_scores would then hold the\n"
    "        # override's values, not the scorer's, so scaling tokens by them sends the\n"
    "        # router head a gradient it is not responsible for.\n"
    "        if self.training and use_ste and select_scores is None:",
    "cell 4 STE gate",
)
put(4, c4)

# ======================================================================= PATCH B
print("\nB. cell 7 -- selection helpers + generate(select_mode=...)")
c7 = get(7)
assert "class AdaptiveDonutOCR" in c7, "cell 7 is not the model cell"

HELPERS = '''# Cell 5: AdaptiveDonutOCR Model
SELECT_MODES = ('router', 'negated', 'random', 'ink', 'stratified', 'stratified_negated')

TOKEN_GRID = (80, 60)   # Swin-B at 2560x1920, total stride 32 -> 80*60 = 4800 tokens


def patch_ink(pixel_values, num_tokens, stride=32):
    """Per-token within-patch contrast on the encoder's own token grid -> (B, N).

    A learning-free proxy for 'there is text here', used as the ink oracle's ranking
    signal and as the retained-ink diagnostic.

    Within-patch std rather than mean darkness because std is blind to whether Donut
    padded with black or white -- uniform padding has zero contrast either way, while
    darkness would score black padding as maximum ink. No un-normalization is needed:
    donut-base uses image_mean = image_std = 0.5 on every channel, so pixel_values is
    a uniform affine image of luminance and a plain channel mean ranks identically to
    true grayscale.
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


def stratified_scores(scores, grid=TOKEN_GRID, negate=False):
    """Rewrite a ranking so a GLOBAL top-K becomes a PER-GRID-ROW top-k.

    Diagnostic D2: a single global top-k has no mechanism bounding worst-case
    coverage. It may spend the entire budget on one dense region, and the trained
    router does something like this -- its MINIMUM text-line ink coverage is 0.000,
    i.e. at least one line of the page loses all its ink, while total retained ink
    looks unremarkable. Recall is gated by the worst line, not the average.

    A per-row budget makes starving a line structurally impossible. Rather than add a
    second selection path to the router (a new path is a new place for the two to
    diverge), stratification is expressed purely as a monotone rewrite of the ranking
    signal, reusing the select_scores machinery unchanged:

        key = (gw - within_row_rank) + normalized_score

    within_row_rank is an integer in [0, gw), so the integer part dominates and the
    normalized score only breaks ties INSIDE a rank band; the bands cannot overlap
    because the score term is clamped strictly below 1.0. A global top-K with
    K = gh * k therefore selects exactly the top-k of every row. When K is not a
    multiple of gh it degrades gracefully -- whole bands fill first, the remainder
    goes to the best scores in the next band, and rows differ by at most 1.

    negate ranks by the negated score WITHIN each row, which is the fix for a
    sign-inverted scorer. Stratification and sign are orthogonal -- hence two modes.
    """
    B, N = scores.shape
    gh, gw = grid
    if gh * gw != N:
        raise ValueError(
            f'token grid mismatch: grid {gh}x{gw}={gh * gw} but got {N} tokens')
    s = (-scores if negate else scores).reshape(B, gh, gw)
    order = s.argsort(dim=-1, descending=True)
    rank = torch.empty_like(order)
    rank.scatter_(-1, order, torch.arange(gw, device=s.device).expand_as(order))
    lo = s.amin(dim=(1, 2), keepdim=True)
    hi = s.amax(dim=(1, 2), keepdim=True)
    s_norm = ((s - lo) / (hi - lo).clamp(min=1e-9)).clamp(0.0, 0.999)
    return ((gw - rank).to(s.dtype) + s_norm).reshape(B, N)


class AdaptiveDonutOCR(nn.Module):'''

c7 = sub(
    c7,
    "# Cell 5: AdaptiveDonutOCR Model\nclass AdaptiveDonutOCR(nn.Module):",
    HELPERS,
    "cell 7 selection helpers (SELECT_MODES / patch_ink / stratified_scores)",
)

c7 = sub(
    c7,
    "    def generate(self, pixel_values, decoder_input_ids=None, max_length=256,"
    " keep_ratio=None, merge_ratio=None, **kwargs):",
    "    def generate(self, pixel_values, decoder_input_ids=None, max_length=256,\n"
    "                 keep_ratio=None, merge_ratio=None, select_mode='router', **kwargs):",
    "cell 7 generate signature",
)

DISPATCH = '''        # select_mode swaps the RANKING SIGNAL only. K, the architecture and the
        # decoder are untouched, so every row costs the same and stays comparable.
        #   router  -- the learned scores (the actual model)
        #   negated -- the same scores, lowest-first. D1 found the trained router
        #              anti-correlated with ink, so this retains MORE text (0.62-0.66
        #              vs 0.34-0.38) -- yet loses to random, so ink is necessary and
        #              not sufficient.
        #   random  -- uniform noise: the floor the router must beat. Drawn fresh per
        #              image from the ambient RNG (one fixed mask is a positional
        #              prior, a different and easier target); seed in the eval loop.
        #   ink     -- patch contrast, no learning: an ORACLE bounding what any
        #              ink-seeking router could reach on this decoder.
        #   stratified / stratified_negated -- the SAME learned scores under a
        #              per-grid-row budget instead of one global top-k (D2). Tests
        #              whether the selection RULE is the bug rather than the scorer.
        if select_mode not in SELECT_MODES:
            raise ValueError(f'select_mode must be one of {SELECT_MODES}, got {select_mode!r}')
        select_scores = None
        invert = False
        if select_mode == 'negated':
            invert = True
        elif select_mode == 'random':
            select_scores = torch.rand(B, N, device=device, dtype=visual_tokens.dtype)
        elif select_mode == 'ink':
            select_scores = patch_ink(pixel_values, N).to(visual_tokens.dtype)
        elif select_mode in ('stratified', 'stratified_negated'):
            # Grid derived from pixel_values, not assumed, so a non-standard input
            # raises here instead of silently stratifying over the wrong axis.
            grid = (pixel_values.shape[-2] // 32, pixel_values.shape[-1] // 32)
            raw = self.router.scorer(visual_tokens).squeeze(-1)
            select_scores = stratified_scores(
                raw, grid=grid, negate=(select_mode == 'stratified_negated')
            ).to(visual_tokens.dtype)

        coords = self._generate_2d_coords(B, N, device, dtype=visual_tokens.dtype)
        selected_tokens, scores, topk_indices, pruned_coords = self.router(
            visual_tokens, keep_ratio=k_ratio, coords=coords, use_ste=False,
            select_scores=select_scores, invert=invert
        )'''

c7 = sub(
    c7,
    "        coords = self._generate_2d_coords(B, N, device, dtype=visual_tokens.dtype)\n"
    "        selected_tokens, scores, topk_indices, pruned_coords = self.router(\n"
    "            visual_tokens, keep_ratio=k_ratio, coords=coords, use_ste=False\n"
    "        )",
    DISPATCH,
    "cell 7 select_mode dispatch + router call",
)

c7 = sub(
    c7,
    "        return generated_ids, {\n"
    "            'original_tokens': N,\n"
    "            'compressed_tokens': M,\n"
    "            'compression_ratio': (1.0 - (M / N)) * 100.0,\n"
    "            'scores': scores,\n"
    "            'topk_indices': topk_indices\n"
    "        }",
    "        # Retained ink: what fraction of the page's contrast survived pruning.\n"
    "        # Logged per call because it is the number that EXPLAINS an accuracy row --\n"
    "        # without it a bad row reads as 'pruning hurts' rather than 'we pruned the\n"
    "        # text'. Guarded: a non-standard grid must not invalidate the accuracy row.\n"
    "        retained_ink = None\n"
    "        try:\n"
    "            ink = patch_ink(pixel_values, N)\n"
    "            kept = ink.gather(1, topk_indices).sum(dim=1)\n"
    "            retained_ink = float((kept / ink.sum(dim=1).clamp(min=1e-9)).mean())\n"
    "        except ValueError:\n"
    "            pass\n"
    "\n"
    "        return generated_ids, {\n"
    "            'original_tokens': N,\n"
    "            'compressed_tokens': M,\n"
    "            'compression_ratio': (1.0 - (M / N)) * 100.0,\n"
    "            'select_mode': select_mode,\n"
    "            'retained_ink': retained_ink,\n"
    "            'scores': scores,\n"
    "            'topk_indices': topk_indices\n"
    "        }",
    "cell 7 meta: select_mode + retained_ink",
)
put(7, c7)

# ======================================================================= PATCH C
print("\nC. new cell after 14 -- the selection ablation harness")
assert "run_decode_eval" in get(14), "cell 14 is not the decoding-ablation cell"

ABLATION_CELL = r'''# Cell 8c: SELECTION ablation (EVAL-ONLY -- no retraining)
# Answers Pending 1b / 1c / 1d from AGENTS.md in one GPU session. Same weights, same
# decoder, same token BUDGET within a keep_ratio -- only the RANKING SIGNAL moves, so
# rows are comparable at equal cost.
#
# Row 0 is a CONTROL at keep_ratio=1.0 (pruning OFF) and must reproduce run 6. If it
# does not, this harness differs from the eval cell and NO other row is trustworthy.
#
# 1b  keep=0.50 x {router, negated, random, ink}
#       random is the FLOOR: D1 measured the trained router as anti-correlated with
#       patch ink (r ~ -0.24), so uniform noise retains more text than the learned
#       scores. A router that cannot beat noise is not a router.
#       ink is the CEILING: patch contrast, no learning. It bounds what any
#       ink-seeking router could reach on this decoder. If it collapses, the premise
#       that half these tokens are droppable is wrong and Pending 1a is 4 wasted
#       GPU-hours. (Local CPU n=4: oracle 83.66 vs full page 83.67 -- premise holds.)
# 1d  keep=0.50 x {stratified, stratified_negated}
#       D2: the router's MINIMUM text-line ink coverage is 0.000 -- at least one line
#       loses all its ink -- while total retained ink looks unremarkable, and recall is
#       gated by the worst line. A per-grid-row budget makes that impossible. If these
#       rows fix the router, the bug is the SELECTION RULE, not the scorer, and
#       retraining is the wrong fix.
# 1c  keep in {1.00, 0.75, 0.50, 0.35}, each with its floor and ceiling
#       The accuracy/cost CURVE, with latency and token counts per row. GW=60 makes
#       the per-row budget integral at every ratio (60/45/30/21), so the stratified
#       rows are exact per-row top-k rather than the degradation path.
import os
import re
import time

RUN6_REFERENCE = (77.74, 64.70, 53.05)   # recall / charAcc / order, FUNSD test x50
SELECTION_MAX_LEN = 512
SELECTION_SEED = 0
GH, GW = 80, 60          # Swin-B token grid at 2560x1920, stride 32
ROW_INK_FRAC = 0.10     # a grid row counts as text if its ink >= 10% of the busiest
SELECTION_OUT = os.path.join(
    '/kaggle/working' if os.path.isdir('/kaggle/working') else '.',
    'ablation_selection.json')

SELECTION_CONFIGS = [
    ('keep=1.00 router CONTROL', 1.00, 'router'),
    # 1b
    ('keep=0.50 router',         0.50, 'router'),
    ('keep=0.50 NEGATED',        0.50, 'negated'),
    ('keep=0.50 random',         0.50, 'random'),
    ('keep=0.50 ink ORACLE',     0.50, 'ink'),
    # 1d
    ('keep=0.50 stratified',     0.50, 'stratified'),
    ('keep=0.50 strat NEGATED',  0.50, 'stratified_negated'),
    # 1c
    ('keep=0.75 router',         0.75, 'router'),
    ('keep=0.75 random',         0.75, 'random'),
    ('keep=0.75 ink ORACLE',     0.75, 'ink'),
    ('keep=0.75 strat NEGATED',  0.75, 'stratified_negated'),
    ('keep=0.35 router',         0.35, 'router'),
    ('keep=0.35 random',         0.35, 'random'),
    ('keep=0.35 ink ORACLE',     0.35, 'ink'),
    ('keep=0.35 strat NEGATED',  0.35, 'stratified_negated'),
]


def line_coverage(pv, topk_indices):
    """Per-text-row retained-ink fractions for one image -> 1-D array, or None.

    D2 found that summed retained ink ranks `negated` ABOVE `random` while accuracy
    does the opposite, and that the WORST-covered text line is what tracks recall.
    That was 4 cached images against 4 aggregate rows -- one statistic ordering 4 rows
    correctly is 1-in-24 by luck. Recorded per image here so it becomes a real
    correlation that can actually fail.
    """
    N = GH * GW
    if pv.shape[-2] // 32 != GH or pv.shape[-1] // 32 != GW:
        return None            # non-standard grid; the accuracy row is still valid
    ink = patch_ink(pv, N)[0].reshape(GH, GW).float().cpu().numpy()
    keep = np.zeros(N, dtype=bool)
    keep[topk_indices[0].cpu().numpy()] = True
    keep2d = keep.reshape(GH, GW)
    row_ink = ink.sum(axis=1)
    is_text = row_ink >= ROW_INK_FRAC * row_ink.max()
    if not is_text.any():
        return None
    return (ink * keep2d).sum(axis=1)[is_text] / np.maximum(row_ink[is_text], 1e-9)


def run_selection_eval(label, keep_ratio, select_mode):
    """Re-run the FUNSD test set under one (keep_ratio, ranking signal) pair.

    Metrics mirror the eval cell exactly (same compute_word_metrics / compute_ned /
    reading_order_words / MAX_WORDS) so rows stay comparable to runs 2-6.
    """
    model.eval()
    # Reseed per row so the random control draws the same sequence on every run while
    # still getting a FRESH mask per image.
    torch.manual_seed(SELECTION_SEED)
    recs, ords_, neds_, inks, lats = [], [], [], [], []
    pred_words, gold_words, gen_tokens = [], [], []
    json_ok, hit_cap = 0, 0
    kept_tokens = None
    per_image = []

    for i, sample in enumerate(tqdm(test_raw, desc=label, leave=False)):
        img = sample['image'].convert('RGB')
        pv = processor(img, return_tensors='pt').pixel_values.to(device)
        words = sample.get('words', [])
        boxes = sample.get('bboxes') or sample.get('boxes')
        gt_words = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
        gt_str = json.dumps({'text': ' '.join(gt_words)})

        t0 = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pv, decoder_input_ids=prompt_ids, keep_ratio=keep_ratio,
                merge_ratio=0.0, max_length=SELECTION_MAX_LEN, select_mode=select_mode
            )
        lats.append((time.perf_counter() - t0) * 1000.0)
        kept_tokens = meta['compressed_tokens']
        if meta['retained_ink'] is not None:
            inks.append(meta['retained_ink'])
        cov = line_coverage(pv, meta['topk_indices'])

        n_tok = int(gen_ids.shape[-1])
        gen_tokens.append(n_tok)
        if n_tok >= SELECTION_MAX_LEN:
            hit_cap += 1   # ran to the cap instead of emitting EOS

        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()

        # diagnostic only -- we never repair pred, that would score the fix
        try:
            json.loads(pred)
            json_ok += 1
        except Exception:
            pass

        r, o = compute_word_metrics(pred, gt_words)
        recs.append(r)
        ords_.append(o)
        neds_.append(compute_ned(pred, gt_str))
        pred_words.append(len(re.findall(r'\w+', pred.lower())))
        gold_words.append(len(re.findall(r'\w+', ' '.join(gt_words).lower())))
        per_image.append({
            'i': i,
            'recall': float(r),
            'ned': float(neds_[-1]),
            'retained_ink': meta['retained_ink'],
            'gen_tokens': n_tok,
            'min_line_cov': None if cov is None else float(cov.min()),
            'p10_line_cov': None if cov is None else float(np.percentile(cov, 10)),
            'mean_line_cov': None if cov is None else float(cov.mean()),
            'n_text_rows': None if cov is None else int(cov.size),
        })

    n = max(len(recs), 1)
    mp, mg = float(np.mean(pred_words)), float(np.mean(gold_words))
    covs = [p['min_line_cov'] for p in per_image if p['min_line_cov'] is not None]
    return {
        'config': label,
        'keep_ratio': keep_ratio,
        'select_mode': select_mode,
        'visual_tokens': kept_tokens,
        'retained_ink': float(np.mean(inks)) if inks else None,
        'mean_min_line_cov': float(np.mean(covs)) if covs else None,
        'word_recall_pct': float(np.mean(recs) * 100.0),
        'character_accuracy_pct': float((1.0 - np.mean(neds_)) * 100.0),
        'word_order_pct': float(np.mean(ords_) * 100.0),
        'mean_ned': float(np.mean(neds_)),
        'mean_pred_words': mp,
        'mean_gold_words': mg,
        'len_ratio_pct': 100.0 * mp / max(mg, 1e-9),
        'mean_gen_tokens': float(np.mean(gen_tokens)),
        'hit_max_length_pct': 100.0 * hit_cap / n,
        'valid_json_pct': 100.0 * json_ok / n,
        'avg_latency_ms': float(np.mean(lats)),
        'num_eval_samples': len(recs),
        'per_image': per_image,
    }


rows = []
_t0 = time.perf_counter()
for _name, _kr, _mode in SELECTION_CONFIGS:
    print(f'--- {_name}')
    rows.append(run_selection_eval(_name, _kr, _mode))
    _r = rows[-1]
    _ink = '  -  ' if _r['retained_ink'] is None else f"{_r['retained_ink']:.3f}"
    print(f"    -> recall {_r['word_recall_pct']:.2f}  charAcc "
          f"{_r['character_accuracy_pct']:.2f}  ink {_ink}  "
          f"{_r['avg_latency_ms']:.0f} ms/img  [{(time.perf_counter() - _t0) / 60:.1f} min]")
    # Written after EVERY row: a Kaggle session that dies at row 12 must not lose
    # rows 0-11 the way the local run did.
    with open(SELECTION_OUT, 'w') as f:
        json.dump({'meta': {'run6_reference': RUN6_REFERENCE,
                            'seed': SELECTION_SEED,
                            'max_len': SELECTION_MAX_LEN,
                            'complete': False}, 'rows': rows}, f, indent=2)

hdr = (f"{'config':26s} {'tok':>5s} {'ink':>5s} {'minCov':>6s} {'recall':>7s} "
       f"{'charAcc':>8s} {'order':>7s} {'NED':>6s} {'len%':>6s} {'cap%':>5s} "
       f"{'json%':>6s} {'ms':>7s}")
print('\n' + '=' * len(hdr))
print(hdr)
print('-' * len(hdr))
for r in rows:
    ink = '  -  ' if r['retained_ink'] is None else f"{r['retained_ink']:.3f}"
    mc = '  -  ' if r['mean_min_line_cov'] is None else f"{r['mean_min_line_cov']:.3f}"
    print(f"{r['config']:26s} {r['visual_tokens']:5d} {ink:>5s} {mc:>6s} "
          f"{r['word_recall_pct']:7.2f} {r['character_accuracy_pct']:8.2f} "
          f"{r['word_order_pct']:7.2f} {r['mean_ned']:6.3f} {r['len_ratio_pct']:6.1f} "
          f"{r['hit_max_length_pct']:5.0f} {r['valid_json_pct']:6.1f} "
          f"{r['avg_latency_ms']:7.0f}")
print('=' * len(hdr))

# --- CONTROL: does keep_ratio=1.0 reproduce run 6? ---
ctrl = rows[0]
got = (ctrl['word_recall_pct'], ctrl['character_accuracy_pct'], ctrl['word_order_pct'])
drift = max(abs(g - e) for g, e in zip(got, RUN6_REFERENCE))
print(f'\nCONTROL vs run 6 {RUN6_REFERENCE}')
print(f'  got ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts')
if drift < 0.5:
    print('  OK - harness reproduces run 6, so every other row is comparable.')
else:
    print('  WARNING - harness does NOT match run 6 (different weights, sampling, or '
          'transformers version). Rows are still comparable TO EACH OTHER and to this '
          'control, but do not quote them against run 6 absolutely.')

by = {(r['keep_ratio'], r['select_mode']): r for r in rows}


def rec(kr, mode):
    r = by.get((kr, mode))
    return None if r is None else r['word_recall_pct']


# --- Q1 (1b): does negating the router help? ---
print('\nQ1. Does negating the router help? (keep=0.50)')
for m in ('router', 'negated', 'random'):
    r = by[(0.50, m)]
    print(f"  {m:8s} {r['word_recall_pct']:6.2f} recall   ink {r['retained_ink']:.3f}"
          f"   minCov {r['mean_min_line_cov']:.3f}")
if rec(0.50, 'negated') > max(rec(0.50, 'router'), rec(0.50, 'random')):
    print('  => NEGATION IS A REAL FIX: it beats the forward router AND random, so '
          'flipping the sign makes the existing checkpoint usable.')
else:
    print('  => negation does not beat random: retaining ink is NECESSARY BUT NOT '
          'SUFFICIENT (D2). Do not adopt it as the fix.')

# --- Q2 (1b): is the premise sound at all? ---
print('\nQ2. Are half these tokens droppable at all? (the row that can kill 1a)')
print(f"  keep=1.00 CONTROL  {rec(1.00, 'router'):6.2f} recall  ({ctrl['visual_tokens']} tokens)")
_ik = by[(0.50, 'ink')]
print(f"  keep=0.50 ORACLE   {_ik['word_recall_pct']:6.2f} recall  "
      f"({_ik['visual_tokens']} tokens, ink {_ik['retained_ink']:.3f})   "
      f"{_ik['word_recall_pct'] - ctrl['word_recall_pct']:+.2f} vs control")
if _ik['word_recall_pct'] > ctrl['word_recall_pct'] - 5.0:
    print('  => PREMISE HOLDS: an ink-ranked half of the tokens nearly matches the '
          'full page, so the headroom a trained router could reach is real.')
else:
    print('  => PREMISE IS WEAK: even a perfect ink ranking loses accuracy at this '
          'budget. Cap expectations for ANY router and consider merge_ratio (which '
          'compresses rather than discards) before more pruning work.')
print(f"  at keep=0.50 the router sits at {rec(0.50, 'router'):.2f}, between a floor of "
      f"{rec(0.50, 'random'):.2f} (random) and a ceiling of {_ik['word_recall_pct']:.2f} (oracle).")

# --- Q4 (1d): is the SELECTION RULE the bug, or the scorer? ---
print('\nQ4. Is the bug the selection RULE or the scorer? (keep=0.50, D2/Pending 1d)')
for m in ('router', 'stratified', 'stratified_negated', 'random', 'ink'):
    r = by[(0.50, m)]
    print(f"  {m:19s} {r['word_recall_pct']:6.2f} recall   ink {r['retained_ink']:.3f}"
          f"   minCov {r['mean_min_line_cov']:.3f}")
_best_strat = max(rec(0.50, 'stratified'), rec(0.50, 'stratified_negated'))
if _best_strat >= rec(0.50, 'random'):
    print('  => THE SELECTION RULE WAS THE BUG. A per-row budget on the SAME scores '
          'reaches the random floor or better, so the scorer is salvageable and 1a '
          'should train WITH stratified selection rather than replace the scorer.')
elif _best_strat > rec(0.50, 'router') + 2.0:
    print('  => PARTIAL: stratification helps but does not reach random, so the rule '
          'is one cause and the scorer is another. 1a still needed; keep the per-row '
          'budget in it.')
else:
    print('  => NOT THE RULE. Bounding worst-case coverage does not rescue these '
          'scores, so the scorer itself is what is broken -- Pending 1a (train with '
          'pruning ON) is the fix, and D2 says its loss must NOT reward summed '
          'retained saliency.')

# --- Q5 (1c): the accuracy/cost curve ---
print('\nQ5. keep_ratio curve (Pending 1c) -- recall by ranking signal, cost per row')
print(f"  {'keep':>5s} {'tok':>5s} {'router':>7s} {'random':>7s} {'oracle':>7s} "
      f"{'stratN':>7s} {'ms/img':>7s}")
for kr in (1.00, 0.75, 0.50, 0.35):
    r0 = by.get((kr, 'router'))
    if r0 is None:
        continue
    cells_ = []
    for m in ('router', 'random', 'ink', 'stratified_negated'):
        v = rec(kr, m)
        cells_.append('      -' if v is None else f'{v:7.2f}')
    print(f"  {kr:5.2f} {r0['visual_tokens']:5d} " + ' '.join(cells_) +
          f" {r0['avg_latency_ms']:7.0f}")
print('  NOTE: latency here is generation-dominated, so it tracks OUTPUT length more '
      'than token count. Read the tok column for the actual encoder-side saving.')

# --- Q3 (D2): which statistic predicts recall? ---
# D2 claimed WORST-CASE line coverage discriminates where summed retained ink does
# not, but measured it on 4 cached images against 4 aggregate rows. Here it is a
# per-image test over every equal-budget row, so it can actually fail.
def spearman(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float('nan')
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


pooled = [(p, r['select_mode']) for r in rows if r['keep_ratio'] < 1.0
          for p in r['per_image'] if p['min_line_cov'] is not None]
if len(pooled) >= 12:
    _rec = [p['recall'] for p, _ in pooled]
    print(f'\nQ3. Which statistic predicts per-image recall? (all pruned rows, n={len(pooled)})')
    print(f"  {'statistic':22s} {'family':12s} {'Spearman vs recall':>19s}")
    print('  ' + '-' * 56)
    for key, fam in (('retained_ink', 'aggregate'), ('mean_line_cov', 'aggregate'),
                     ('p10_line_cov', 'worst-case'), ('min_line_cov', 'worst-case')):
        print(f'  {key:22s} {fam:12s} '
              f'{spearman([p[key] for p, _ in pooled], _rec):19.3f}')
    rho_ink = spearman([p['retained_ink'] for p, _ in pooled], _rec)
    rho_min = spearman([p['min_line_cov'] for p, _ in pooled], _rec)
    if rho_min > rho_ink + 0.05:
        print('  => D2 CONFIRMED per-image: worst-case coverage predicts recall better '
              'than summed ink. Do NOT build a router objective on total retained '
              'saliency.')
    elif rho_ink > rho_min + 0.05:
        print('  => D2 FALSIFIED per-image: summed ink is the better predictor after '
              'all. D2 was a 4-row coincidence; revise it and re-check 1a/1d.')
    else:
        print('  => INCONCLUSIVE: the two families predict about equally well here, so '
              "D2's claim stands unconfirmed rather than refuted.")
    # Within-mode is the harder test: it removes the between-mode contrast that could
    # carry the pooled correlation on its own.
    print('\n  within-mode (controls for the mode -- image-to-image variation only):')
    for mode in ('router', 'negated', 'random', 'ink', 'stratified', 'stratified_negated'):
        sub_ = [p for p, m in pooled if m == mode]
        if len(sub_) >= 5:
            print(f"    {mode:19s} ink "
                  f"{spearman([p['retained_ink'] for p in sub_], [p['recall'] for p in sub_]):6.3f}"
                  f"   min-cov "
                  f"{spearman([p['min_line_cov'] for p in sub_], [p['recall'] for p in sub_]):6.3f}"
                  f"   (n={len(sub_)})")
else:
    print('\nQ3 skipped: too few per-image coverage records to correlate.')

with open(SELECTION_OUT, 'w') as f:
    json.dump({'meta': {'run6_reference': RUN6_REFERENCE,
                        'seed': SELECTION_SEED,
                        'max_len': SELECTION_MAX_LEN,
                        'control_drift_pts': drift,
                        'num_eval_samples': ctrl['num_eval_samples'],
                        'max_words': MAX_WORDS,
                        'complete': True}, 'rows': rows}, f, indent=2)
print(f'\nWrote {SELECTION_OUT}  ({(time.perf_counter() - _t0) / 60:.1f} min total)')
'''

ast.parse(ABLATION_CELL)
if "Cell 8c: SELECTION ablation" in "".join(get(i) for i in range(len(cells))):
    print("  ablation cell already present, not inserting a second copy")
else:
    cells.insert(15, {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": ABLATION_CELL.splitlines(keepends=True),
    })
    print("  inserted: selection-ablation cell at index 15 "
          f"(notebook now has {len(cells)} cells)")

# ============================================================================ write
for i, c in enumerate(cells):
    if c["cell_type"] != "code":
        continue
    src = "".join(c["source"])
    # A cell holding IPython shell/magic lines (`!pip install ...`) is never valid
    # Python, so ast can only be applied to the pure-Python cells -- which is all of
    # them except cell 1, and cell 1 is not a patch target.
    if any(ln.lstrip().startswith(("!", "%")) for ln in src.splitlines()):
        print(f"  cell {i}: contains IPython magics, parse check skipped")
        continue
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise SystemExit(f"cell {i} does not parse after patching: {e}")

with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")

print(f"\nwrote {os.path.basename(NB)} -- all code cells parse")
print("NEXT: PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_selection_ablation.py")
