"""Execution gate for the ToMe merge port. RUNS the generated notebook's code.

WHY THIS EXISTS
---------------
`BipartiteTokenMerger` has never executed on a recorded result. The reason is a bug
that was fixed in `src/tome.py` and then never reached the notebook -- which is the
only thing that produces runs. Both copies drifted, nothing compared them, and the
divergence was invisible because the broken version returns a perfectly plausible
merged tensor:

    OLD (still in kaggle_token_pruning_ocr.ipynb):
        idx_A = torch.arange(0, K, 2)   idx_B = torch.arange(1, K, 2)
    The router hands tokens over via torch.topk(..., sorted=True), i.e. in DESCENDING
    SCORE ORDER, so those indices are RANKS, not page positions. The split partitions
    by score-rank parity and strands ~half of all genuinely redundant pairs in the
    same set, where ToMe's A->B merge can never reach them.

So `scripts/make_kaggle_pruning_notebook.py` now SPLICES `src/tome.py` into cell 4
rather than carrying a copy. This script is the check that the splice actually landed
and actually runs -- `ast.parse` in the patcher only proves the cell is syntactically
Python.

WHAT IS DELIBERATELY NOT VACUOUS HERE
-------------------------------------
Comparing the notebook's merger against `src/`'s when the former was spliced from the
latter would pass no matter what, so every equality check below is paired with a
check that the quantity CAN differ:

  * checkerboard vs rank_parity outputs must DIFFER under a score-sorted index, or
    the fix is a no-op and every equality above it proves nothing;
  * the missed-adjacency rate is measured against its own null (the old split), not
    just asserted to be zero;
  * the OLD merger is extracted FROM THE CANONICAL NOTEBOOK at runtime rather than
    retyped here, so the sabotage-equivalence check cannot quietly compare the new
    implementation against a hand-copy of itself.

`scripts/diagnose_tome_parity.py` already measured the parity statistic, but it did so
against a LOCAL RESTATEMENT of the partition. This script measures the shipped code.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_tome_merge_port.py
"""
import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import types

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The GENERATED notebook, not the canonical one. The fix lands only here, on purpose:
# the canonical notebook is the shared base that every generated variant is patched
# from, and it still carries the broken split (check 3 below depends on that).
NB_PATH = os.path.join(ROOT, "kaggle_pruning_run.ipynb")
CANON_PATH = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def cells_of(path):
    blob = json.loads(open(path, encoding="utf-8").read())
    return ["".join(c["source"]) if c["cell_type"] == "code" else None
            for c in blob["cells"]]


CELLS = cells_of(NB_PATH)


def find_cell(marker, cells=None):
    for i, src in enumerate(cells if cells is not None else CELLS):
        if src and marker in src:
            return i
    raise RuntimeError(f"no cell contains {marker!r}")


def extract(names):
    """Pull specific top-level defs/assigns out of the notebook and exec them."""
    ns = {"np": np, "torch": torch, "json": json}
    found = set()
    for src in CELLS:
        if not src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue                       # the pip cell, never valid Python
        for node in tree.body:
            hit = (isinstance(node, ast.FunctionDef) and node.name in names) or (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)
            )
            if hit:
                exec(compile(ast.Module([node], []), "<nb>", "exec"), ns)
                found.add(node.name if isinstance(node, ast.FunctionDef)
                          else node.targets[0].id)
    missing = set(names) - found
    if missing:
        raise RuntimeError(f"could not extract {sorted(missing)} from the notebook")
    return ns


GH, GW = 80, 60
N = GH * GW
D = 8
GEN_LEN = 24

# ===================================================================== 0. cells exec
print("=" * 78)
print("0. the patched cells EXECUTE (not just parse)")
print("=" * 78)

from transformers.modeling_outputs import BaseModelOutput  # noqa: E402

NBNS = {
    "torch": torch, "nn": nn, "F": F, "np": np, "json": json,
    "gc": __import__("gc"), "BaseModelOutput": BaseModelOutput,
    "VisionEncoderDecoderModel": None,     # only touched in __init__, which we skip
}
# src/tome.py's signature annotations are evaluated when the `def` executes, so a
# missing `typing` import is an immediate NameError, not a deferred one. PATCH E1 puts
# it in cell 2. Take it FROM cell 2 rather than injecting Tuple/Optional/Sequence here
# by hand -- injecting them would leave this verifier green even if that patch had
# silently stopped applying, and the failure would surface on Kaggle at cell 4.
i2 = find_cell("from transformers.modeling_outputs import BaseModelOutput")
_typing_imports = [n for n in ast.parse(CELLS[i2]).body
                   if isinstance(n, ast.ImportFrom) and n.module == "typing"]
check("cell 2 imports typing (cell 4's merger annotations need it at def time)",
      len(_typing_imports) == 1,
      f"{len(_typing_imports)} `from typing import` statements in cell 2")
for _n in _typing_imports:
    exec(compile(ast.Module([_n], []), f"<nb cell {i2}>", "exec"), NBNS)
check("cell 2 supplies every name src/tome.py annotates with",
      all(k in NBNS for k in ("Tuple", "Optional", "Sequence")),
      str(sorted(k for k in ("Tuple", "Optional", "Sequence") if k not in NBNS)))

i4 = find_cell("class PatchSaliencyRouter")
i7 = find_cell("class AdaptiveDonutOCR")
exec(compile(CELLS[i4], f"<nb cell {i4}>", "exec"), NBNS)
check(f"cell {i4} (router + ToMe) execs, checkerboard_color present",
      "checkerboard_color" in NBNS and "BipartiteTokenMerger" in NBNS)
exec(compile(CELLS[i7], f"<nb cell {i7}>", "exec"), NBNS)
check(f"cell {i7} (helpers + model) execs", "AdaptiveDonutOCR" in NBNS)

nb_cc = NBNS["checkerboard_color"]
nb_merger_cls = NBNS["BipartiteTokenMerger"]
nb_router_cls = NBNS["PatchSaliencyRouter"]
nb_patch_ink = NBNS["patch_ink"]

check("cell 4 no longer contains the rank-parity split",
      "arange(0, K, 2" not in CELLS[i4])
check("TOME_SPLITS exposes both arms",
      NBNS.get("TOME_SPLITS") == ("checkerboard", "rank_parity"),
      str(NBNS.get("TOME_SPLITS")))
# A default of 0.20 turns an EXPERIMENT on for every caller who forgets to mention
# it, which is how results/nrns_rp_sweep.json became a merged sweep that reads as a
# pruning-free one.
check("AdaptiveDonutOCR default merge_ratio is 0.0, not 0.20",
      "merge_ratio=0.0, freeze_encoder=True):" in CELLS[i7])

# ================================================ 1. checkerboard_color == src/tome
print()
print("=" * 78)
print("1. the spliced checkerboard_color AGREES NUMERICALLY with src/tome.py")
print("=" * 78)

from src.tome import checkerboard_color as src_cc          # noqa: E402
from src.tome import BipartiteTokenMerger as SrcMerger     # noqa: E402

torch.manual_seed(0)
raster = torch.arange(N).unsqueeze(0)
shuffled = torch.stack([torch.randperm(N), torch.randperm(N)])
for label, idx in (("raster arange(4800)", raster), ("shuffled, B=2", shuffled)):
    a, b = nb_cc(idx, GW), src_cc(idx, GW)
    check(f"checkerboard_color({label}): notebook == src", torch.equal(a, b),
          f"{int((a != b).sum())} mismatches")

# The property the whole fix rests on, checked on the SHIPPED function rather than
# assumed: every 4-neighbour lands in the opposite set.
col = nb_cc(raster, GW).reshape(GH, GW)
check("4-neighbours always get opposite colours (right)",
      bool((col[:, :-1] != col[:, 1:]).all()))
# The down case is the one plain raster order lost: GW=60 is even, so a token and the
# one directly below it share raster-index parity and 100% of vertical redundancy was
# unmergeable even before the score-sort problem.
check("4-neighbours always get opposite colours (down) -- the case raster order lost",
      bool((col[:-1, :] != col[1:, :]).all()))

# ============================================= 2. merger output == src, and not vacuous
print()
print("=" * 78)
print("2. the spliced merger produces BIT-IDENTICAL output to src/tome.py")
print("=" * 78)

nb_merge = nb_merger_cls(hidden_dim=D).eval()
src_merge = SrcMerger(hidden_dim=D).eval()


def score_sorted_idx(B, K, seed=7):
    """`topk_indices` as the router really emits it: a keep-K subset of the raster
    sequence, ORDERED BY DESCENDING SCORE. Using a sorted or arange index here would
    hide the exact bug under test."""
    g = torch.Generator().manual_seed(seed)
    out = []
    for _ in range(B):
        scores = torch.rand(N, generator=g)
        out.append(torch.topk(scores, k=K).indices)
    return torch.stack(out)


for B in (1, 2):
    for keep, mr in ((0.50, 0.20), (0.50, 0.40), (0.35, 0.20), (1.00, 0.20)):
        K = max(1, int(round(N * keep)))
        g = torch.Generator().manual_seed(11)
        toks = torch.randn(B, K, D, generator=g)
        crd = torch.rand(B, K, 2, generator=g)
        oi = score_sorted_idx(B, K)
        with torch.no_grad():
            ta, ca = nb_merge(toks, merge_ratio=mr, coords=crd,
                              orig_idx=oi, token_grid=(GH, GW))
            tb, cb = src_merge(toks, merge_ratio=mr, coords=crd,
                               orig_idx=oi, token_grid=(GH, GW))
        exp_M = K - min(int(round(K * mr)), K // 2)
        check(f"B={B} keep={keep:.2f} merge={mr:.2f}: notebook == src, M={exp_M}",
              torch.equal(ta, tb) and torch.equal(ca, cb)
              and ta.shape == (B, exp_M, D),
              f"shape {tuple(ta.shape)}, max |diff| {float((ta - tb).abs().max()):.3e}")

# Non-vacuity. Everything above compares code spliced from src/ against src/, so it
# would pass even if the splice had landed a no-op. These two say the fix CHANGES the
# answer, which is the only reason any of it matters.
K = 2400
g = torch.Generator().manual_seed(11)
toks = torch.randn(1, K, D, generator=g)
oi = score_sorted_idx(1, K)
seq = torch.arange(K).unsqueeze(0)
with torch.no_grad():
    t_cb, _ = nb_merge(toks, merge_ratio=0.20, orig_idx=oi, token_grid=(GH, GW))
    t_rp, _ = nb_merge(toks, merge_ratio=0.20, orig_idx=seq, token_grid=(K, 1))
check("checkerboard and rank_parity DISAGREE on real score-sorted input",
      not torch.equal(t_cb, t_rp),
      f"max |diff| {float((t_cb - t_rp).abs().max()):.3e} "
      f"(0.0 would mean the fix is a no-op and every check above is empty)")
check("merging actually compacts (M < K) and is not a pass-through",
      t_cb.shape[1] == K - 480 and not torch.equal(t_cb[:, :K - 480], toks[:, :K - 480]),
      f"K={K} -> M={t_cb.shape[1]}")

# The targeted quantity, measured against its own null on the SHIPPED function.
# diagnose_tome_parity.py measured this on a local restatement of the partition.
def missed_adjacency(color_fn, idx):
    """Fraction of kept 4-adjacent pairs that share a colour (= unmergeable)."""
    kept = set(idx[0].tolist())
    pos = {v: p for p, v in enumerate(idx[0].tolist())}
    same_h = tot_h = same_v = tot_v = 0
    for v in kept:
        r, c = divmod(v, GW)
        if c + 1 < GW and v + 1 in kept:
            tot_h += 1
            same_h += int(color_fn(v, pos[v]) == color_fn(v + 1, pos[v + 1]))
        if r + 1 < GH and v + GW in kept:
            tot_v += 1
            same_v += int(color_fn(v, pos[v]) == color_fn(v + GW, pos[v + GW]))
    return (100.0 * same_h / max(tot_h, 1), 100.0 * same_v / max(tot_v, 1),
            tot_h, tot_v)


_cb_lut = nb_cc(torch.arange(N).unsqueeze(0), GW)[0]
h_new, v_new, nh, nv = missed_adjacency(lambda v, p: int(_cb_lut[v]), oi)
h_old, v_old, _, _ = missed_adjacency(lambda v, p: p % 2, oi)
check(f"NULL: the old split really does strand ~half the redundancy "
      f"({nh} h-pairs, {nv} v-pairs kept)",
      h_old > 40.0 and v_old > 40.0, f"missed h {h_old:.1f}%  v {v_old:.1f}%")
check("FIX: the shipped split strands none of it",
      h_new == 0.0 and v_new == 0.0, f"missed h {h_new:.1f}%  v {v_new:.1f}%")

# ================================================ 3. sabotage arm == the OLD merger
print()
print("=" * 78)
print("3. rank_parity REPRODUCES the pre-fix merger exactly (a usable negative control)")
print("=" * 78)

# Extracted from the canonical notebook at runtime, not retyped: a hand-copy here
# could drift into agreeing with the new implementation and the check would go green
# for the wrong reason.
_canon = cells_of(CANON_PATH)
_ci = find_cell("class BipartiteTokenMerger", _canon)
_old_src = _canon[_ci][_canon[_ci].index("class BipartiteTokenMerger"):]
check("the canonical notebook still carries the OLD rank-parity merger",
      "torch.arange(0, K, 2" in _old_src,
      "if it was fixed independently, this control is comparing two copies of the "
      "SAME implementation and proves nothing -- reconcile the notebooks")
OLDNS = {"torch": torch, "nn": nn, "F": F}
exec(compile(_old_src, "<canonical old merger>", "exec"), OLDNS)
old_merge = OLDNS["BipartiteTokenMerger"](hidden_dim=D).eval()

for B in (1, 2):
    for K, mr in ((2400, 0.20), (1680, 0.20), (2400, 0.40)):
        g = torch.Generator().manual_seed(23)
        toks = torch.randn(B, K, D, generator=g)
        crd = torch.rand(B, K, 2, generator=g)
        seq = torch.arange(K).unsqueeze(0).expand(B, K)
        with torch.no_grad():
            t_new, c_new = nb_merge(toks, merge_ratio=mr, coords=crd,
                                    orig_idx=seq, token_grid=(K, 1))
            # The old merger processed the whole batch in one bmm; the new one loops
            # per image, because checkerboard membership depends on WHICH tokens the
            # router kept and so K_A varies down the batch. Driving the old one
            # per-image too isolates the algorithm from that difference, and the
            # result must then be EXACT -- a tolerance here would be hiding the only
            # thing this check exists to find.
            t_old = torch.cat([old_merge(toks[b:b + 1], merge_ratio=mr,
                                         coords=crd[b:b + 1])[0] for b in range(B)])
            c_old = torch.cat([old_merge(toks[b:b + 1], merge_ratio=mr,
                                         coords=crd[b:b + 1])[1] for b in range(B)])
            t_batch, _ = old_merge(toks, merge_ratio=mr, coords=crd)
            # What a REAL algorithmic difference looks like at this shape, so the
            # float32 bound below can be read against something instead of trusted.
            t_cbd, _ = nb_merge(toks, merge_ratio=mr, coords=crd,
                                orig_idx=score_sorted_idx(B, K), token_grid=(GH, GW))
        d_loop = float((t_new - t_old).abs().max())
        d_batch = float((t_new - t_batch).abs().max())
        d_real = float((t_new - t_cbd).abs().max())
        check(f"B={B} K={K} merge={mr:.2f}: rank_parity == the old merger, bit for bit",
              torch.equal(t_new, t_old) and torch.equal(c_new, c_old),
              f"max |diff| {d_loop:.3e}")
        # Batched-vs-looped BLAS accumulation only. Bounded at 1e-5, which is ~4
        # orders of magnitude below a genuine partition change (d_real), so the
        # tolerance cannot absorb the effect under test.
        check(f"B={B} K={K} merge={mr:.2f}: batched old merger agrees to float32 noise",
              d_batch < 1e-5 and (B == 1 or d_real > 1e-3),
              f"batched {d_batch:.3e} vs a real split change {d_real:.3e}")

# ===================================================== 4. the missing-argument guard
print()
print("=" * 78)
print("4. merging without a page position RAISES rather than guessing")
print("=" * 78)

toks = torch.randn(1, 2400, D)
try:
    nb_merge(toks, merge_ratio=0.20)
    check("merge_ratio>0 without orig_idx raises", False,
          "it silently merged -- a caller who has not thought about page position "
          "got a plausible, wrong answer")
except ValueError as e:
    check("merge_ratio>0 without orig_idx raises ValueError",
          "orig_idx" in str(e), str(e)[:60])
try:
    out, _ = nb_merge(toks, merge_ratio=0.0)
    check("merge_ratio=0 without orig_idx passes through untouched",
          torch.equal(out, toks))
except Exception as e:                                   # noqa: BLE001
    check("merge_ratio=0 without orig_idx passes through", False,
          f"{type(e).__name__}: {e}")

# ======================================== 5. generate() through both splits, real grid
print()
print("=" * 78)
print("5. generate() runs BOTH splits on a real 80x60 grid at every configured budget")
print("=" * 78)


class _StubInner:
    """Stands in for self.model (VisionEncoderDecoderModel) only."""

    def __init__(self):
        self.config = types.SimpleNamespace(decoder_start_token_id=0)

    def encoder(self, pixel_values):
        g = torch.Generator().manual_seed(1234)
        return BaseModelOutput(
            last_hidden_state=torch.randn(pixel_values.shape[0], N, D, generator=g))

    def generate(self, encoder_outputs=None, max_length=None, **kw):
        self.last_kwargs = kw
        self.last_enc_len = int(encoder_outputs.last_hidden_state.shape[1])
        n = min(GEN_LEN, max_length)
        return torch.zeros(1, n, dtype=torch.long)


def build_model():
    """The notebook's real AdaptiveDonutOCR, __init__ skipped, real router attached."""
    m = object.__new__(NBNS["AdaptiveDonutOCR"])
    nn.Module.__init__(m)
    m.base_model_name = "stub"
    m.keep_ratio = 1.0
    m.merge_ratio = 0.0
    m.router = nb_router_cls(hidden_dim=D, reduction_dim=4).eval()
    m.tome_merger = nb_merger_cls(hidden_dim=D).eval()
    m.model = _StubInner()
    m.eval()
    return m


mdl = build_model()
pv1 = torch.rand(1, 3, GH * 32, GW * 32)
prompt = torch.zeros(1, 1, dtype=torch.long)

CFG = extract({"SELECTION_CONFIGS", "MERGE_CONFIGS", "ALL_CONFIGS", "EXPECTED_M",
               "MERGE_PAIRS", "SABOTAGE_PAIR"})
MERGE_CONFIGS = CFG["MERGE_CONFIGS"]
EXPECTED_M = CFG["EXPECTED_M"]
check(f"cell 15 declares {len(CFG['ALL_CONFIGS'])} rows "
      f"({len(CFG['SELECTION_CONFIGS'])} published + {len(MERGE_CONFIGS)} new)",
      len(CFG["ALL_CONFIGS"]) == len(CFG["SELECTION_CONFIGS"]) + len(MERGE_CONFIGS))

# The token-match arithmetic is CHECKED BY EXECUTION here, not by hand. Every pair in
# the sweep rests on "these two rows spent the same M"; if the arithmetic in the
# generator's comment is wrong, every Q6 delta measures a budget difference instead.
for label, keep, mode, mr, split in MERGE_CONFIGS:
    with torch.no_grad():
        _, meta = mdl.generate(pv1, decoder_input_ids=prompt, keep_ratio=keep,
                               merge_ratio=mr, max_length=64, select_mode=mode,
                               tome_split=split)
    want = EXPECTED_M[(keep, mode, mr, split)]
    got = meta["compressed_tokens"]
    ok = (got == want
          and meta["merge_ratio"] == mr
          and meta["tome_split"] == (split if mr > 0 else None)
          and mdl.model.last_enc_len == want)
    check(f"{label:24s} -> M={got} (predicted {want}), meta records the knobs", ok,
          f"merge_ratio={meta['merge_ratio']} tome_split={meta['tome_split']} "
          f"decoder saw {mdl.model.last_enc_len}")

check("prune-only rows report tome_split=None rather than a split they never used",
      all(mdl.generate(pv1, decoder_input_ids=prompt, keep_ratio=k, merge_ratio=0.0,
                       max_length=64, select_mode='router')[1]["tome_split"] is None
          for k in (0.80, 0.40, 0.28)))

try:
    mdl.generate(pv1, decoder_input_ids=prompt, keep_ratio=0.5, merge_ratio=0.2,
                 max_length=64, select_mode="router", tome_split="raster")
    check("an unknown tome_split raises", False, "silently accepted")
except ValueError as e:
    check("an unknown tome_split raises ValueError", "tome_split must be" in str(e))
try:
    # The one that would really bite: a typo on a PRUNE-ONLY row, where
    # _tome_partition returns early and would never see it.
    mdl.generate(pv1, decoder_input_ids=prompt, keep_ratio=0.5, merge_ratio=0.0,
                 max_length=64, select_mode="router", tome_split="raster")
    check("an unknown tome_split raises even when merging is OFF", False,
          "a typo'd split would pass silently on every prune-only row")
except ValueError as e:
    check("an unknown tome_split raises even when merging is OFF",
          "tome_split must be" in str(e))

# ===================================================== 6. _token_grid refuses to guess
print()
print("=" * 78)
print("6. _token_grid derives the width and REFUSES a grid it cannot account for")
print("=" * 78)

check("_token_grid returns the real Swin-B grid", mdl._token_grid(pv1, N) == (GH, GW),
      str(mdl._token_grid(pv1, N)))
pv_odd = torch.rand(1, 3, 96 * 32, GW * 32)      # 5760 patches vs 4800 tokens
try:
    mdl._token_grid(pv_odd, N)
    check("_token_grid raises on a mismatched input", False, "returned a wrong width")
except ValueError as e:
    check("_token_grid raises ValueError on a mismatched input",
          "token grid mismatch" in str(e), str(e)[:60])
try:
    mdl.generate(pv_odd, decoder_input_ids=prompt, keep_ratio=0.5, merge_ratio=0.2,
                 max_length=64, select_mode="router")
    check("merging on a mismatched grid raises instead of merging by a wrong width",
          False, "a wrong grid_w still yields a valid-looking partition")
except ValueError as e:
    check("merging on a mismatched grid raises ValueError",
          "token grid mismatch" in str(e), str(e)[:60])
try:
    _, m_odd = mdl.generate(pv_odd, decoder_input_ids=prompt, keep_ratio=0.5,
                            merge_ratio=0.0, max_length=64, select_mode="router")
    check("but merge_ratio=0 on a mismatched grid still runs (grid resolved lazily)",
          m_odd["compressed_tokens"] == N // 2, str(m_odd["compressed_tokens"]))
except Exception as e:                                   # noqa: BLE001
    check("merge_ratio=0 on a mismatched grid still runs", False,
          f"{type(e).__name__}: {e}")

# ============================================ 7. the whole harness, end to end
print()
print("=" * 78)
print("7. the ablation cell EXECUTES END TO END (every row, Q6, the sabotage block)")
print("=" * 78)
print("  accuracy numbers inside are SYNTHETIC and mean nothing -- only execution and")
print("  the token-match asserts are being checked.")

i_ab = find_cell("Cell 8c: SELECTION ablation")
METRICS = extract({"reading_order_words", "compute_word_metrics", "compute_ned",
                   "MAX_WORDS", "doc_image"})

GOLD = ["invoice", "number", "12345", "date", "2024", "total", "amount", "due",
        "vendor", "acme", "corp", "billing", "address", "street", "city"]
PREDS = [
    json.dumps({"text": " ".join(GOLD)}),                    # perfect
    json.dumps({"text": " ".join(GOLD[:8])}),                # half the page
    json.dumps({"text": " ".join(GOLD[::-1])}),              # right words, wrong order
    json.dumps({"text": "invoice 999 total"}),               # mostly missing
    '{"text": "invoice number 12345 date',                   # malformed JSON
    json.dumps({"text": " ".join(GOLD[3:11])}),              # middle band only
]


class _StubImage:
    def __init__(self, seed):
        self.seed = seed

    def convert(self, mode):
        return self


def _page(seed):
    """A real 2560x1920 page: alternating textured bands, so patch_ink sees 40 text
    rows out of 80 and line_coverage has something to measure."""
    g = torch.Generator().manual_seed(seed)
    pv = torch.full((1, 3, GH * 32, GW * 32), 0.9)
    for r in range(0, GH, 2):
        y = r * 32 + 8
        pv[:, :, y:y + 16, 64:GW * 32 - 64] = torch.rand(
            (1, 3, 16, GW * 32 - 128), generator=g)
    return pv


class _StubProcessor:
    def __call__(self, img, return_tensors=None):
        return types.SimpleNamespace(pixel_values=_page(img.seed))

    def batch_decode(self, ids, skip_special_tokens=True):
        return [PREDS[int(ids[0, 0]) % len(PREDS)]]


class _HarnessModel:
    """Delegates to the notebook's REAL generate(), then varies the canned prediction
    so recall is not constant and the Spearman / bootstrap / verdict branches run."""

    def __init__(self, inner):
        self.inner = inner
        self.i = 0

    def eval(self):
        return self

    def generate(self, pv, **kw):
        _, meta = self.inner.generate(pv, **kw)
        pick = (self.i * 7 + hash((kw["select_mode"], kw["keep_ratio"],
                                   kw.get("merge_ratio", 0.0))) // 97) % len(PREDS)
        self.i += 1
        n = 512 if pick == 4 else GEN_LEN + pick    # exercise the hit_max_length path
        return torch.full((1, n), int(pick), dtype=torch.long), meta


# PATCH I made the pool FUNSD + SROIE, and the two name the image column
# DIFFERENTLY (`image` vs `images`). The fixture below is mixed on purpose: cell 15's
# doc_image() call is then exercised against both schemas in situ, and the per-corpus
# aggregate runs with more than one group. A FUNSD-only fixture would go green while a
# missed `sample['image']` call site waited to crash on document 51 of the real run.
# doc_image itself is EXTRACTED from cell 9, not restated here -- extract() raises if
# the notebook stops shipping it, so this cannot decay into testing a paraphrase.
_BOXES = [[i * 10, i * 10, i * 10 + 8, i * 10 + 8] for i in range(len(GOLD))]
POOLED_FIXTURE = [
    {"image":  _StubImage(1), "words": GOLD, "bboxes": _BOXES, "corpus": "funsd"},
    {"image":  _StubImage(2), "words": GOLD, "bboxes": _BOXES, "corpus": "funsd"},
    {"images": _StubImage(3), "words": GOLD, "bboxes": _BOXES, "corpus": "sroie"},
]

HARNESS_NS = {
    "torch": torch, "np": np, "json": json, "nn": nn, "F": F,
    "tqdm": __import__("tqdm").tqdm,
    "patch_ink": nb_patch_ink,
    "model": _HarnessModel(build_model()),
    "processor": _StubProcessor(),
    "device": torch.device("cpu"),
    "prompt_ids": prompt,
    "TASK_PROMPT": "<s_doc>",
    "test_raw": POOLED_FIXTURE,
    "doc_image": METRICS["doc_image"],
    "reading_order_words": METRICS["reading_order_words"],
    "compute_word_metrics": METRICS["compute_word_metrics"],
    "compute_ned": METRICS["compute_ned"],
    "MAX_WORDS": METRICS["MAX_WORDS"],
}

buf = io.StringIO()
tmp = tempfile.mkdtemp(prefix="verify_tome_")
cwd = os.getcwd()
err = None
try:
    os.chdir(tmp)                      # SELECTION_OUT falls back to '.' off Kaggle
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        exec(compile(CELLS[i_ab], f"<nb cell {i_ab}>", "exec"), HARNESS_NS)
except BaseException as e:             # noqa: BLE001 - report, do not mask
    err = e
finally:
    os.chdir(cwd)

out = buf.getvalue()
check("the whole ablation cell runs without raising", err is None,
      f"{type(err).__name__}: {err}" if err else "")
if err is not None:
    print("\n  --- captured output before the failure ---")
    print("\n".join("  " + ln for ln in out.strip().splitlines()[-30:]))
else:
    rows = HARNESS_NS.get("rows", [])
    allc = HARNESS_NS.get("ALL_CONFIGS", [])
    check(f"all {len(allc)} rows completed", len(rows) == len(allc),
          f"{len(rows)} of {len(allc)}")
    merged = [r for r in rows if r.get("merge_ratio", 0.0) > 0.0]
    # 13 new rows, but only 7 of them MERGE: 6 are the prune-only twins that make the
    # comparison token-matched, and the 7th merge row is the rank_parity control.
    check("7 rows actually ran with merging ON (6 checkerboard + 1 rank_parity)",
          len(merged) == 7
          and sum(r["tome_split"] == "rank_parity" for r in merged) == 1,
          f"{len(merged)} rows with merge_ratio>0, splits "
          f"{sorted({r['tome_split'] for r in merged})}")
    check("the 6 prune-only twins ran at the new budgets",
          {r["keep_ratio"] for r in rows if r.get("merge_ratio", 0.0) == 0.0}
          >= {0.80, 0.40, 0.30, 0.28},
          str(sorted({r["keep_ratio"] for r in rows
                      if r.get("merge_ratio", 0.0) == 0.0})))
    check("every row records merge_ratio and tome_split (D5: log the knob)",
          all("merge_ratio" in r and "tome_split" in r for r in rows))
    check("every row's M was constant across images",
          all(len(r["visual_tokens_distinct"]) == 1 for r in rows),
          str([r["config"] for r in rows if len(r["visual_tokens_distinct"]) != 1][:3]))

    # ---- the per-image metric record (G3b) ----------------------------------
    # Run 14 could not bootstrap word_order or char_acc because `per_image` stored
    # neither. Only ONE of those was a real gap: charAcc is (1 - mean(ned)) * 100 and
    # `ned` was always stored, so it was bootstrappable all along. These four checks
    # keep both facts true by execution rather than by comment.
    miss = [r["config"] for r in rows
            if not all("word_order" in p for p in r["per_image"])]
    check("every row stores per-image word_order for every image", not miss,
          str(miss[:3]))

    # The aggregate is built from `ords_`, the per-image field from `o`. If the append
    # had grabbed `r` (recall) instead -- the plausible typo, one letter, same scope --
    # these two would disagree. This is the check that makes the new field load-bearing.
    bad_ord = [(r["config"], r["word_order_pct"],
                100.0 * float(np.mean([p["word_order"] for p in r["per_image"]])))
               for r in rows
               if abs(r["word_order_pct"]
                      - 100.0 * float(np.mean([p["word_order"]
                                               for p in r["per_image"]]))) > 1e-9]
    check("word_order_pct == mean(per-image word_order) * 100, every row",
          not bad_ord, str(bad_ord[:2]))

    # ...and the identity above only has teeth if word_order is not a copy of recall.
    # Substitute recall and require the SAME check to fail, on some row, by a margin
    # wider than the 1e-9 tolerance. Without this, storing `r` would pass silently on
    # any harness where recall and order happen to coincide.
    as_recall = [abs(r["word_order_pct"]
                     - 100.0 * float(np.mean([p["recall"] for p in r["per_image"]])))
                 for r in rows]
    check("that identity is discriminating: recall would FAIL it",
          max(as_recall) > 1.0,
          f"max |word_order_pct - mean(recall)*100| = {max(as_recall):.4f} pts")

    # charAcc is an affine transform of the stored NED array, which is why run 14's
    # "-" for charAcc was wrong and its p-value is exactly NED's. Asserted here so a
    # future change to the aggregate formula breaks this instead of silently
    # invalidating every charAcc CI computed off `ned`.
    bad_ca = [(r["config"], r["character_accuracy_pct"],
               100.0 * (1.0 - float(np.mean([p["ned"] for p in r["per_image"]]))))
              for r in rows
              if abs(r["character_accuracy_pct"]
                     - 100.0 * (1.0 - float(np.mean([p["ned"]
                                                     for p in r["per_image"]])))) > 1e-9]
    check("character_accuracy_pct == (1 - mean(per-image ned)) * 100, every row",
          not bad_ca, str(bad_ca[:2]))

    # ---- the per-corpus stratification (PATCH I, for T1 s5 / T4) -------------
    # T1 s5 requires the estimate reported stratified by corpus, and without a label on
    # each per-image record the discard-set constraint is not merely unimplemented, it
    # is UNCOMPUTABLE. At n=397 a g=0.10 trim discards 39 per tail against FUNSD's
    # entire 50, so this is not a hypothetical.
    check("the fixture really was mixed-schema (2x `image` + 1x `images`)",
          sum("image" in s for s in POOLED_FIXTURE) == 2
          and sum("images" in s for s in POOLED_FIXTURE) == 1
          and sorted(s["corpus"] for s in POOLED_FIXTURE) == ["funsd", "funsd", "sroie"])
    check("every row carries a per_corpus block",
          all("per_corpus" in r for r in rows),
          str([r["config"] for r in rows if "per_corpus" not in r][:3]))
    check("every per-image record is tagged with its corpus",
          all(p.get("corpus") in ("funsd", "sroie")
              for r in rows for p in r["per_image"]))
    check("per_corpus names both corpora and its n's sum to the row's n",
          all(sorted(r["per_corpus"]) == ["funsd", "sroie"]
              and sum(v["n"] for v in r["per_corpus"].values()) == len(r["per_image"])
              for r in rows),
          str([(r["config"], {k: v["n"] for k, v in r["per_corpus"].items()})
               for r in rows][:2]))

    # The pooled figure must BE the n-weighted mean of its strata, re-derived rather
    # than trusted: a label attached to the wrong records would still produce a
    # plausible-looking per_corpus block.
    bad_strat = []
    for r in rows:
        n_tot = len(r["per_image"])
        recon = sum(v["n"] * v["word_recall_pct"]
                    for v in r["per_corpus"].values()) / n_tot
        if abs(recon - r["word_recall_pct"]) > 1e-9:
            bad_strat.append((r["config"], r["word_recall_pct"], recon))
    check("word_recall_pct == n-weighted mean of the per-corpus strata, every row",
          not bad_strat, str(bad_strat[:2]))

    # ...and that identity has teeth only if the strata differ: with equal strata ANY
    # labelling satisfies it. The plausible error here is an UNWEIGHTED mean (n=2 vs
    # n=1), so require that to be wrong somewhere by more than the tolerance. The
    # margin is printed either way -- a 0.0 here means the fixture cannot discriminate,
    # which is a fact about this check and not a pass.
    unw = [abs(r["word_recall_pct"]
               - float(np.mean([v["word_recall_pct"]
                                for v in r["per_corpus"].values()])))
           for r in rows]
    check("that identity is discriminating: an unweighted mean would FAIL it",
          max(unw) > 1e-6,
          f"max |pooled - unweighted stratum mean| = {max(unw):.6f} pts")

    # `by` must still point at the PRUNE-ONLY rows, or Q1-Q5 silently changed meaning
    # while continuing to print plausible numbers.
    by = HARNESS_NS["by"]
    check("`by` is prune-only: no merge row shadows a published row",
          all(r.get("merge_ratio", 0.0) == 0.0 for r in by.values()),
          str([k for k, r in by.items() if r.get("merge_ratio", 0.0) > 0.0]))
    check("`by` still resolves every (keep, mode) Q1-Q5 reads",
          all(k in by for k in [(0.50, "router"), (0.50, "ink"), (0.50, "negated"),
                                (0.35, "router"), (1.00, "router"), (0.75, "router")]))
    check(f"`by_all` separates all {len(rows)} rows (no silent collision)",
          len(HARNESS_NS["by_all"]) == len(rows))

    # Q3's pool must not have ingested merge rows: its predictors are PRE-merge while
    # recall is post-merge, and a 0.05 rho gap decides the D2 verdict.
    pooled_n = len(HARNESS_NS.get("pooled", []))
    prune_lt1 = [r for r in rows
                 if r["keep_ratio"] < 1.0 and r.get("merge_ratio", 0.0) == 0.0]
    check("Q3's pool excludes every merge row",
          pooled_n == sum(len([p for p in r["per_image"]
                               if p["min_line_cov"] is not None])
                          for r in prune_lt1),
          f"pooled {pooled_n} records from {len(prune_lt1)} prune-only rows")

    q6 = HARNESS_NS.get("q6_rows", [])
    check("Q6 measured all 6 token-matched pairs", len(q6) == 6, f"{len(q6)} pairs")
    check("every Q6 pair is genuinely token-matched at the predicted M",
          all(q["tokens"] == EXPECTED_M[k] for q, (_l, k, _p) in zip(q6, CFG["MERGE_PAIRS"])),
          str([(q["pair"], q["tokens"]) for q in q6]))
    check("every Q6 pair carries a paired CI, not just a delta",
          all(q["ci95_lo"] <= q["delta_pts"] <= q["ci95_hi"] for q in q6),
          str([(q["pair"], round(q["delta_pts"], 2)) for q in q6]))
    # The verdict prose used to assert "<3 pts is invisible at n=50" without measuring
    # anything -- the same shape of error run 11's post-mortem caught. Each row now
    # reports its OWN half-width, so check that it is the CI's and that the
    # underpowered flag is derived from it rather than pasted on.
    check("every Q6 row reports its own measured resolution (= CI half-width)",
          all(abs(q["resolution_pts"] - (q["ci95_hi"] - q["ci95_lo"]) / 2.0) < 1e-9
              for q in q6),
          str([(q["pair"], round(q["resolution_pts"], 2)) for q in q6]))
    _bar = HARNESS_NS.get("Q6_RESOLUTION_PTS")
    check("the underpowered flag tracks that resolution against the 3.0 pt bar",
          _bar == 3.0
          and all(q["underpowered"] == ((not q["significant"])
                                        and q["resolution_pts"] > _bar) for q in q6),
          f"bar {_bar}, flags {[(q['pair'], q['underpowered']) for q in q6]}")
    sab = HARNESS_NS.get("sabotage_row")
    check("the sabotage contrast ran (checkerboard vs rank_parity at the same M)",
          sab is not None and sab["tokens"] == 1920,
          str(sab["tokens"]) if sab else "None")
    check("the sabotage row reports its resolution too",
          sab is not None
          and abs(sab["resolution_pts"]
                  - (sab["ci95_hi"] - sab["ci95_lo"]) / 2.0) < 1e-9,
          f"res {sab['resolution_pts']:.2f}" if sab else "None")

    for marker in ("Q1. Does negating", "Q3. Which statistic", "Q5. keep_ratio curve",
                   "Q6. TOKEN-MATCHED", "SABOTAGE CONTROL"):
        check(f"printed section: {marker!r}", marker in out)
    check("no pair was skipped for a missing twin", "MISSING --" not in out)

    written = os.path.join(tmp, "ablation_selection.json")
    check("results JSON written", os.path.exists(written), written)
    if os.path.exists(written):
        blob = json.loads(open(written, encoding="utf-8").read())
        check("results JSON carries Q6 and the sabotage row, not just the table",
              blob["meta"]["complete"] is True
              and len(blob["meta"]["q6_token_matched"]) == 6
              and blob["meta"]["q6_sabotage"] is not None
              and len(blob["rows"]) == len(allc),
              f"{len(blob['rows'])} rows, meta keys {sorted(blob['meta'])}")

# The token-match asserts must be able to FAIL. A hard assert nobody has ever seen
# trip is indistinguishable from a comment.
print()
print("=" * 78)
print("8. the token-match assert is load-bearing (it fires on a mismatched pair)")
print("=" * 78)
if err is None:
    atm = HARNESS_NS["assert_token_matched"]
    good = HARNESS_NS["by_all"][(0.50, "router", 0.20, "checkerboard")]
    wrong = HARNESS_NS["by_all"][(0.35, "router", 0.00, "checkerboard")]   # M=1680
    try:
        atm("deliberate mismatch", good, wrong)
        check("assert_token_matched rejects a pair at different M", False,
              "it accepted M=1920 against M=1680 -- Q6 would report a budget effect "
              "as a merging effect")
    except AssertionError as e:
        check("assert_token_matched rejects a pair at different M",
              "NOT token-matched" in str(e), str(e)[:70])
else:
    check("assert_token_matched rejects a pair at different M", False,
          "harness did not complete, so the assert could not be exercised")

print()
print("=" * 78)
_n_rows = len(HARNESS_NS.get("rows", []))

if fails:
    print(f"{len(fails)} CHECK(S) FAILED:")
    for f in fails:
        print(f"  - {f}")
    print("Do NOT spend GPU time until these are green.")
    sys.exit(1)
print("ALL CHECKS PASSED -- the generated notebook runs the REAL checkerboard merger,")
print("matches src/tome.py bit for bit, reproduces the pre-fix split as a control, and")
print(f"completes all {_n_rows} rows with every token-matched pair verified by "
      "execution.")
print("=" * 78)
