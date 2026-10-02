"""Execution check for the Kaggle selection-ablation port. RUNS the notebook's code.

`ast.parse` in the patcher only proves the cells are syntactically Python. The failures
that actually matter here are all runtime ones:

  * the notebook's PORTED copies of `patch_ink` / `stratified_scores` / the router's
    `select_scores` path silently DIVERGING from `src/`'s already-verified originals,
    which would make the Kaggle rows non-comparable to the local ones without any
    error being raised;
  * a `select_mode` that reaches the dispatch but dies inside `generate()` -- e.g. a
    dtype/device mismatch, or `retained_ink` raising on the real 80x60 grid;
  * the new harness cell referencing a name the notebook does not define, or a
    `by[(keep_ratio, mode)]` key its own `SELECTION_CONFIGS` never produces. That
    would only surface at the END of a paid GPU session, after all 15 rows had run.

So: cells 4 and 7 are exec'd for real, the ported functions are compared NUMERICALLY
against `src/`, `generate()` is called through every one of the six modes on a real
80x60 grid, and finally the whole harness cell is exec'd end to end against a stub
processor/dataset with the notebook's REAL metric functions and the REAL patched
model object.

THE HARNESS RUN PRODUCES MEANINGLESS ACCURACY NUMBERS ON PURPOSE. Predictions come
from a canned table so recall varies enough to exercise every verdict branch and the
Spearman path. Nothing about the printed table is evidence of anything -- the only
claim being checked is that all 15 rows, the CONTROL drift check, Q1-Q5 and the JSON
write execute without raising.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/verify_selection_ablation.py
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
NB_PATH = os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")

fails = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        fails.append(name)


nb = json.loads(open(NB_PATH, encoding="utf-8").read())
CELLS = ["".join(c["source"]) if c["cell_type"] == "code" else None for c in nb["cells"]]


def find_cell(marker):
    for i, src in enumerate(CELLS):
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


# ===================================================================== exec the cells
print("=" * 74)
print("0. the patched cells EXECUTE (not just parse)")
print("=" * 74)

from transformers.modeling_outputs import BaseModelOutput  # noqa: E402

NBNS = {
    "torch": torch, "nn": nn, "F": F, "np": np, "json": json,
    "gc": __import__("gc"), "BaseModelOutput": BaseModelOutput,
    "VisionEncoderDecoderModel": None,     # only touched in __init__, which we skip
}
i4, i7 = find_cell("class PatchSaliencyRouter"), find_cell("class AdaptiveDonutOCR")
exec(compile(CELLS[i4], f"<nb cell {i4}>", "exec"), NBNS)
check(f"cell {i4} (router + ToMe) execs", "PatchSaliencyRouter" in NBNS)
exec(compile(CELLS[i7], f"<nb cell {i7}>", "exec"), NBNS)
check(f"cell {i7} (helpers + model) execs",
      all(k in NBNS for k in ("SELECT_MODES", "patch_ink", "stratified_scores",
                              "AdaptiveDonutOCR")))

nb_router_cls = NBNS["PatchSaliencyRouter"]
nb_patch_ink = NBNS["patch_ink"]
nb_strat = NBNS["stratified_scores"]
check("SELECT_MODES lists all six modes",
      set(NBNS["SELECT_MODES"]) == {"router", "negated", "random", "ink",
                                    "stratified", "stratified_negated"},
      str(NBNS["SELECT_MODES"]))
check("TOKEN_GRID is the real Swin-B grid", NBNS["TOKEN_GRID"] == (80, 60),
      str(NBNS["TOKEN_GRID"]))

# ============================================== 1. notebook copies == src/ originals
print()
print("=" * 74)
print("1. the ported functions AGREE NUMERICALLY with src/ (the real drift risk)")
print("=" * 74)

from src.model import patch_ink as src_patch_ink  # noqa: E402
from src.model import stratified_scores as src_strat  # noqa: E402
from src.router import PatchSaliencyRouter as SrcRouter  # noqa: E402

GH, GW = 80, 60
N = GH * GW
torch.manual_seed(0)

pv_real = torch.rand(2, 3, GH * 32, GW * 32)
a, b = nb_patch_ink(pv_real, N), src_patch_ink(pv_real, N)
check("patch_ink: notebook == src on the real 80x60 grid",
      torch.equal(a, b), f"max |diff| {float((a - b).abs().max()):.3e}")

sc = torch.rand(2, N)
for neg in (False, True):
    a = nb_strat(sc, grid=(GH, GW), negate=neg)
    b = src_strat(sc, grid=(GH, GW), negate=neg)
    check(f"stratified_scores(negate={neg}): notebook == src", torch.equal(a, b),
          f"max |diff| {float((a - b).abs().max()):.3e}")

# Same weights in both routers, then every mode's selection must be bit-identical.
nb_r = nb_router_cls(hidden_dim=16, reduction_dim=8).eval()
src_r = SrcRouter(hidden_dim=16, reduction_dim=8).eval()
src_r.load_state_dict(nb_r.state_dict())
tok = torch.randn(2, N, 16)
raw = nb_r.scorer(tok).squeeze(-1)
cases = {
    "router": (None, False),
    "negated": (None, True),
    "ink": (nb_patch_ink(pv_real, N), False),
    "stratified": (nb_strat(raw, grid=(GH, GW)), False),
    "stratified_negated": (nb_strat(raw, grid=(GH, GW), negate=True), False),
}
for mode, (ss, inv) in cases.items():
    with torch.no_grad():
        _, s_a, i_a, _ = nb_r(tok, keep_ratio=0.5, use_ste=False,
                              select_scores=ss, invert=inv)
        _, s_b, i_b, _ = src_r(tok, keep_ratio=0.5, use_ste=False,
                               select_scores=ss, invert=inv)
    check(f"router.forward[{mode}]: identical indices and scores",
          torch.equal(i_a, i_b) and torch.equal(s_a, s_b),
          f"{int((i_a != i_b).sum())} index mismatches")

# ============================================ 2. the per-row guarantee at real scale
print()
print("=" * 74)
print("2. stratification's per-row guarantee HOLDS at 80x60 (D2's actual fix)")
print("=" * 74)

for keep in (1.00, 0.75, 0.50, 0.35):
    K = max(1, int(round(N * keep)))
    k, rem = divmod(K, GH)
    check(f"keep={keep:.2f}: K={K} is an exact multiple of {GH} rows (k={k}/row)",
          rem == 0, f"remainder {rem} -- rows would differ by 1")
    key = nb_strat(raw, grid=(GH, GW))
    m = torch.zeros(2, N, dtype=torch.bool)
    for bi in range(2):
        m[bi, torch.topk(key[bi], k=K).indices] = True
    counts = m.reshape(2, GH, GW).sum(dim=-1)
    check(f"keep={keep:.2f}: every one of the {GH} grid rows keeps exactly {k}",
          bool((counts == k).all()),
          f"min {int(counts.min())} max {int(counts.max())}")

# And the failure it fixes must be REPRODUCIBLE with a plain global top-k, or the
# whole of 1d is testing a problem that does not exist at this scale.
#
# NOTE, learned by getting this fixture wrong first: starvation is NOT automatic. A
# first attempt made 5 of the 80 rows hot -- only 300 tokens against a budget of
# K=2400 -- so 2100 tokens still had to land somewhere and the emptiest row kept 21.
# A global top-k can only zero a row when the region it prefers is AT LEAST AS LARGE
# AS THE BUDGET. That is a real bound on when 1d can help: at keep=0.5 the router must
# be concentrating half the page into a sub-region for a line to hit zero coverage --
# and D2 measured exactly that (min line coverage 0.000). So the hot band here spans
# 45 of 80 rows (2700 tokens > K), which is that condition, minimally.
hot = torch.rand(1, N) * 0.01
hot.reshape(1, GH, GW)[0, 20:65, :] = torch.rand(45, GW) * 100.0
K = N // 2
plain = torch.zeros(N, dtype=torch.bool)
plain[torch.topk(hot[0], k=K).indices] = True
pc = plain.reshape(GH, GW).sum(dim=-1)
check("a plain global top-k DOES starve rows at this scale (the bug 1d tests)",
      int(pc.min()) == 0, f"min row keeps {int(pc.min())} tokens; "
      f"{int((pc == 0).sum())} of {GH} rows get nothing")
strat = torch.zeros(N, dtype=torch.bool)
strat[torch.topk(nb_strat(hot, grid=(GH, GW))[0], k=K).indices] = True
check("stratified starves nothing on the same input",
      int(strat.reshape(GH, GW).sum(dim=-1).min()) == GW // 2,
      f"min row keeps {int(strat.reshape(GH, GW).sum(dim=-1).min())}")

# ================================================= 3. generate() runs in every mode
print()
print("=" * 74)
print("3. the notebook's REAL generate() runs through all six select_modes")
print("=" * 74)

D = 8
GEN_LEN = 24


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
    m.tome_merger = NBNS["BipartiteTokenMerger"](hidden_dim=D).eval()
    m.model = _StubInner()
    m.eval()
    return m


mdl = build_model()
pv1 = torch.rand(1, 3, GH * 32, GW * 32)
seen = {}
for mode in NBNS["SELECT_MODES"]:
    with torch.no_grad():
        ids, meta = mdl.generate(pv1, decoder_input_ids=torch.zeros(1, 1, dtype=torch.long),
                                 keep_ratio=0.5, merge_ratio=0.0, max_length=512,
                                 select_mode=mode)
    ok = (meta["select_mode"] == mode
          and meta["compressed_tokens"] == N // 2
          and meta["retained_ink"] is not None
          and meta["topk_indices"].shape == (1, N // 2))
    check(f"select_mode={mode!r}: runs, keeps {N // 2} tokens, reports retained_ink",
          ok, f"tokens={meta['compressed_tokens']} ink={meta['retained_ink']}")
    seen[mode] = (set(meta["topk_indices"][0].tolist()), meta["retained_ink"])

check("keep_ratio=1.00 keeps ALL tokens (the CONTROL is really pruning-off)",
      mdl.generate(pv1, keep_ratio=1.0, merge_ratio=0.0, max_length=64,
                   select_mode="router")[1]["compressed_tokens"] == N)
check("router and negated select disjoint halves",
      not (seen["router"][0] & seen["negated"][0]),
      f"overlap {len(seen['router'][0] & seen['negated'][0])}")
check("the ink oracle retains the most ink of any mode",
      seen["ink"][1] == max(v[1] for v in seen.values()),
      "  ".join(f"{m} {v[1]:.3f}" for m, v in seen.items()))
try:
    mdl.generate(pv1, keep_ratio=0.5, merge_ratio=0.0, max_length=64,
                 select_mode="nonsense")
    check("an unknown select_mode raises", False, "silently accepted")
except ValueError as e:
    check("an unknown select_mode raises ValueError", "select_mode must be" in str(e))

# A non-standard grid must degrade, not crash: accuracy rows stay valid without the
# ink diagnostic. 96x60 = 5760 patches against 4800 tokens -- note that the guard is on
# the token COUNT, so a shape must actually change the product to trip it (96x50 also
# gives 4800 and is correctly accepted, which is how this fixture was wrong at first).
pv_odd = torch.rand(1, 3, 96 * 32, GW * 32)
try:
    _, meta_odd = mdl.generate(pv_odd, keep_ratio=0.5, merge_ratio=0.0, max_length=64,
                               select_mode="router")
    check("non-standard grid: generate() still works, retained_ink is None",
          meta_odd["retained_ink"] is None, f"got {meta_odd['retained_ink']}")
except Exception as e:
    check("non-standard grid: generate() still works", False, f"{type(e).__name__}: {e}")

# But a stratified row on a mismatched grid must RAISE, not silently stratify over the
# wrong axis -- a quietly-wrong row is worse than no row.
try:
    mdl.generate(pv_odd, keep_ratio=0.5, merge_ratio=0.0, max_length=64,
                 select_mode="stratified")
    check("non-standard grid + stratified raises instead of guessing", False,
          "silently stratified over a mismatched grid")
except ValueError as e:
    check("non-standard grid + stratified raises ValueError",
          "token grid mismatch" in str(e), str(e)[:70])

check("decoding defaults survive the patch (rp=1.0, nrns=3)",
      mdl.model.last_kwargs.get("repetition_penalty") == 1.0
      and mdl.model.last_kwargs.get("no_repeat_ngram_size") == 3,
      str({k: v for k, v in mdl.model.last_kwargs.items()
           if k in ("repetition_penalty", "no_repeat_ngram_size")}))

# ================================================ 4. the harness cell runs, in full
print()
print("=" * 74)
print("4. the ablation cell EXECUTES END TO END (all 15 rows, every verdict branch)")
print("=" * 74)
print("  accuracy numbers below are SYNTHETIC and mean nothing -- only execution is")
print("  being checked. Predictions come from a canned table.")

i_ab = find_cell("Cell 8c: SELECTION ablation")
check(f"ablation cell found at index {i_ab}, after the decoding ablation",
      i_ab > find_cell("run_decode_eval"))

METRICS = extract({"reading_order_words", "compute_word_metrics", "compute_ned",
                   "MAX_WORDS"})
try:
    import editdistance  # noqa: F401
except ImportError:
    print("  NOTE: editdistance missing; the notebook metrics take their crude "
          "fallback path. Execution is still what is being checked.")

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
    with (mode, keep_ratio, image) so recall is not constant and Spearman/ptp and the
    verdict branches all execute."""

    def __init__(self, inner):
        self.inner = inner
        self.i = 0

    def eval(self):
        return self

    def generate(self, pv, **kw):
        ids, meta = self.inner.generate(pv, **kw)
        pick = (self.i * 7 + hash((kw["select_mode"], kw["keep_ratio"])) // 97) % len(PREDS)
        self.i += 1
        n = 512 if pick == 4 else GEN_LEN + pick    # exercise the hit_max_length path
        return torch.full((1, n), int(pick), dtype=torch.long), meta


HARNESS_NS = {
    "torch": torch, "np": np, "json": json, "nn": nn, "F": F,
    "tqdm": __import__("tqdm").tqdm,
    "patch_ink": nb_patch_ink,
    "model": _HarnessModel(build_model()),
    "processor": _StubProcessor(),
    "device": torch.device("cpu"),
    "prompt_ids": torch.zeros(1, 1, dtype=torch.long),
    "TASK_PROMPT": "<s_doc>",
    "test_raw": [{"image": _StubImage(s), "words": GOLD,
                  "bboxes": [[i * 10, i * 10, i * 10 + 8, i * 10 + 8]
                             for i in range(len(GOLD))]} for s in (1, 2, 3)],
    "reading_order_words": METRICS["reading_order_words"],
    "compute_word_metrics": METRICS["compute_word_metrics"],
    "compute_ned": METRICS["compute_ned"],
    "MAX_WORDS": METRICS["MAX_WORDS"],
}

buf = io.StringIO()
tmp = tempfile.mkdtemp(prefix="verify_sel_")
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
    print("\n".join("  " + ln for ln in out.strip().splitlines()[-25:]))
else:
    rows = HARNESS_NS.get("rows", [])
    cfgs = HARNESS_NS.get("SELECTION_CONFIGS", [])
    check(f"all {len(cfgs)} configured rows completed", len(rows) == len(cfgs),
          f"{len(rows)} of {len(cfgs)}")
    check("every keep_ratio in the sweep is represented",
          {r["keep_ratio"] for r in rows} == {1.0, 0.75, 0.5, 0.35},
          str(sorted({r["keep_ratio"] for r in rows})))
    check("every select_mode is represented",
          {r["select_mode"] for r in rows} == set(NBNS["SELECT_MODES"]),
          str(sorted({r["select_mode"] for r in rows})))
    check("row 0 is the keep_ratio=1.0 CONTROL and kept all tokens",
          rows[0]["keep_ratio"] == 1.0 and rows[0]["visual_tokens"] == N,
          f"{rows[0]['config']} -> {rows[0]['visual_tokens']} tokens")
    bad = [r["config"] for r in rows if r["retained_ink"] is None
           or r["mean_min_line_cov"] is None]
    check("every row reports retained_ink AND mean_min_line_cov", not bad, str(bad[:3]))
    npi = {len(r["per_image"]) for r in rows}
    check("per-image records written for every image of every row", npi == {3}, str(npi))
    keys = {"i", "recall", "ned", "retained_ink", "gen_tokens", "min_line_cov",
            "p10_line_cov", "mean_line_cov", "n_text_rows"}
    check("per-image records carry the full coverage set",
          keys <= set(rows[0]["per_image"][0]),
          str(sorted(keys - set(rows[0]["per_image"][0]))))
    check("line_coverage actually measured text rows (not silently None)",
          rows[0]["per_image"][0]["n_text_rows"] == GH // 2,
          f"n_text_rows={rows[0]['per_image'][0]['n_text_rows']}, expected {GH // 2}")

    # The sections that only run at the very end of a paid GPU session.
    for marker in ("CONTROL vs run 6", "Q1. Does negating", "Q2. Are half these",
                   "Q3. Which statistic", "Q4. Is the bug the selection",
                   "Q5. keep_ratio curve", "within-mode"):
        check(f"printed section: {marker!r}", marker in out)
    check("Q3 was not skipped for want of coverage records",
          "Q3 skipped" not in out)
    check("the hit_max_length path was exercised",
          any(r["hit_max_length_pct"] > 0 for r in rows))
    check("the valid-JSON counter was exercised in both directions",
          any(0 < r["valid_json_pct"] < 100 for r in rows),
          str(sorted({round(r["valid_json_pct"]) for r in rows})))

    written = os.path.join(tmp, "ablation_selection.json")
    check("results JSON written", os.path.exists(written), written)
    if os.path.exists(written):
        blob = json.loads(open(written, encoding="utf-8").read())
        check("results JSON is complete and carries meta + rows",
              blob["meta"]["complete"] is True and len(blob["rows"]) == len(cfgs)
              and "control_drift_pts" in blob["meta"],
              f"{len(blob['rows'])} rows, meta keys {sorted(blob['meta'])}")

print()
print("=" * 74)
if fails:
    print(f"{len(fails)} CHECK(S) FAILED:")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED -- the notebook's ported selection path runs, matches src/")
print("numerically, and the ablation cell completes all 15 rows plus every verdict.")
print("=" * 74)
