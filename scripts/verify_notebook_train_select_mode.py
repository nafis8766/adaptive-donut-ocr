"""Execution gate for run 18's one variable, IN THE NOTEBOOK. RUNS notebook code.

WHY A SECOND VERIFIER
---------------------
`scripts/verify_train_select_mode.py` already covers `src/model.py`'s
`_selection_signal` (33/33 checks, 5/5 sabotages, max|diff| = 0.000e+00 against the
inline dispatch it replaced). That is not enough, and the reason is the standing
duplication gotcha in AGENTS.md: **the notebook duplicates the model classes and
imports nothing from `src/`.** Kaggle trains from `kaggle_pruning_run.ipynb` cell 7,
not from `src/model.py`. PATCH H splices the helper from `src/`, so the helper's BODY
is shared -- but three surfaces are notebook-only and are exactly the run-18 ones:

  * cell 7's `forward()` signature and its call into the router (the helper is only
    reached if `forward()` actually takes and forwards `select_mode`);
  * cell 11's training call and its step-0 assert;
  * cell 2's `_TRAIN_SELECT_MODES` / `_VS_RUN9` guards.

WHAT THE FAILURE LOOKS LIKE IF THIS IS NOT CHECKED
--------------------------------------------------
If `select_mode` does not reach `forward()`, run 18 trains on ROUTER selection while
every log line says `ink`: the PLAN line prints 'ink', cell 11's header prints 'ink',
five epochs run, the checkpoint saves, 28 rows tabulate, a Q1-Q6 block prints, and the
run-18-minus-run-9 delta is exactly zero-variable -- i.e. it measures nothing, and
nothing in 4.5 GPU-hours of output says so. That is this project's recurring shape
(D5's undeclared `lambda_entropy`, run 12's wrong checkpoint), so it gets executed
rather than read.

WHAT WOULD MAKE THESE CHECKS VACUOUS, AND WHAT STOPS IT
-------------------------------------------------------
Every check below is paired, because each half passes trivially on its own:

  * "forward() returns select_mode" passes on a `forward()` that echoes the kwarg and
    ignores it. Paired with "the KEPT SET differs between router and ink", measured
    against this config's own re-run noise floor so 'differs' cannot be reporting
    nondeterminism. The echo proves the kwarg arrived; the kept set proves it was used.
    Neither is sufficient.
  * "the kept set differs" passes if `ink` resolves to anything at all, including
    garbage. Paired with a DIRECTED check: patch-ink top-K maximises retained ink by
    construction, so the ink arm must sit at the ceiling and above router, random and
    negated. A broken ink branch would differ from router and fail this.
  * "the scorer gets zero task gradient under ink" passes if the backward never ran.
    Paired with nonzero under `router` on the same weights, inputs and seed.
  * that zero is ALSO trivially true for `ink` for a reason unrelated to the guard it
    is usually credited to: `patch_ink(pixel_values, N)` has no autograd graph, so
    router.py's `select_scores is None` clause is a NO-OP on this mode. The clause is
    load-bearing only for `stratified*`, whose override IS a differentiable function of
    `self.router.scorer(...)`. Section 3 therefore tests the guard where it can fail,
    and sabotages the clause to prove the test can fail.
  * cell 2's and cell 11's asserts are exec'd both ways -- each must raise on the
    mismatch it exists to catch and must NOT raise on the shipped config.

Nothing here restates notebook logic. Every assert and the saliency block are pulled
out of the notebook by `ast` and exec'd verbatim (AGENTS.md: a diagnostic that declares
its own copy of the algorithm it is checking cannot fail -- `diagnose_tome_parity.py`
printed 10/10 under total sabotage for exactly that reason).

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python -u scripts/verify_notebook_train_select_mode.py
"""
import ast
import json
import os
import sys
import textwrap

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.stdout.reconfigure(encoding="utf-8")          # AGENTS.md: cp1252 kills a checker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
NB_PATH = os.path.join(ROOT, "kaggle_pruning_run.ipynb")

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


def find_cell(marker):
    hits = [i for i, s in enumerate(CELLS) if s and marker in s]
    assert len(hits) == 1, f"{marker!r} matched {len(hits)} cells, want exactly 1"
    return hits[0]


def node_src(cell_src, pred, what):
    """Return the verbatim source of the ONE top-or-nested node matching `pred`.

    Anchored on the shipped text via ast, not on a line range, so a patch that moves
    the statement does not silently start testing a different one. Exactly-one is
    asserted for the same reason the patchers assert `n == 1`.

    `padded=True` then dedent, and that pair is load-bearing rather than tidy.
    Unpadded, `get_source_segment` returns the FIRST line starting at the node's
    col_offset while every continuation line keeps its original absolute indent -- so
    the common prefix is "" and dedent is a no-op. A single `if body:` still compiles
    that way (its body is merely indented a lot), which is why the saliency block
    happened to work; an `if/else` does NOT, because `else:` has to align with `if` and
    sits 8 columns right of it. That surfaced as `IndentationError` on cell 11's F3
    telemetry block, i.e. the first extracted node whose shape depended on the padding.
    Fixed here rather than at the call site so the next extraction does not re-learn it.
    """
    tree = ast.parse(cell_src)
    hits = [n for n in ast.walk(tree) if pred(n)]
    assert len(hits) == 1, f"{what}: matched {len(hits)} nodes in the cell, want 1"
    seg = ast.get_source_segment(cell_src, hits[0], padded=True)
    assert seg, f"{what}: ast could not recover the source segment"
    return textwrap.dedent(seg)


I2 = find_cell("_TRAIN_SELECT_MODES = (")   # the ASSIGNMENT, not the bare name: cell 11's
                                            # drift-assert message also names the tuple, and
                                            # a substring selector matched both (gotcha:
                                            # "select cells by a unique marker").
I4 = find_cell("class PatchSaliencyRouter")
I7 = find_cell("class AdaptiveDonutOCR")
I11 = find_cell("TRAINING WITH PRUNING ON")
C2, C4, C7, C11 = CELLS[I2], CELLS[I4], CELLS[I7], CELLS[I11]

GH, GW = 80, 60          # the real grid, so _token_grid/_tome_partition resolve exactly
N = GH * GW
D = 8                    # small so this is a CPU-seconds script; grid shape is what matters
VOCAB = 11
TGT = 6
KEEP = 0.50
K = max(1, int(round(N * KEEP)))

print("=" * 78)
print(f"0. exec the notebook's own cells  (cell 2={I2} 4={I4} 7={I7} 11={I11})")
print("=" * 78)

from transformers.modeling_outputs import BaseModelOutput      # noqa: E402

NBNS = {
    "torch": torch, "nn": nn, "F": F, "np": np, "json": json,
    "gc": __import__("gc"), "BaseModelOutput": BaseModelOutput,
    "VisionEncoderDecoderModel": None,
}
# Seed the namespace from CELL 2'S OWN import statements rather than a hand-written
# list of names I happen to remember. AGENTS.md: cells 7 and 11 call gc.collect()
# without importing gc, and the NameError fires inside __init__ AFTER a 200M-parameter
# backbone loads -- invisible to ast.parse and to grep. Same reason the typing imports
# the helper's annotations need are taken from the cell instead of restated.
_seeded = []
_seeded_consts = []
for _n in ast.parse(C2).body:
    if isinstance(_n, (ast.Import, ast.ImportFrom)):
        mod = getattr(_n, "module", None) or ""
        if mod in ("typing",) or (isinstance(_n, ast.Import) and
                                  any(a.name in ("os", "gc", "time", "json") for a in _n.names)):
            exec(compile(ast.Module([_n], []), f"<nb cell {I2}>", "exec"), NBNS)
            _seeded.append(ast.dump(_n)[:24])
    elif (isinstance(_n, ast.Assign) and len(_n.targets) == 1
          and isinstance(_n.targets[0], ast.Name)):
        # Cell 2's CONFIG CONSTANTS, same argument as the imports above: cell 11's
        # extracted blocks read TRAIN_KEEP_RATIO / LAMBDA_SAL-adjacent names that cell 2
        # defines, and a NameError here fires deep inside an exec'd block rather than at
        # parse time. Restricted to `literal_eval`-able values so the six side-effecting
        # assignments (device, PRUNED_CKPT, EVAL_CKPT, EVAL_ONLY, _VS_RUN9*) are skipped
        # -- those resolve mount paths and assert on the accelerator. Taking the VALUE
        # from the cell (not restating it) is what makes a config drift show up here.
        try:
            ast.literal_eval(_n.value)
        except Exception:
            continue
        exec(compile(ast.Module([_n], []), f"<nb cell {I2}>", "exec"), NBNS)
        _seeded_consts.append(_n.targets[0].id)
check("cell 2 still imports the typing names the helper's annotations need",
      all(k in NBNS for k in ("Tuple", "Optional")), f"{len(_seeded)} import stmts exec'd")
check("cell 2's config constants are seeded FROM THE CELL (cell 11's blocks read them)",
      "TRAIN_KEEP_RATIO" in NBNS and "TRAIN_SELECT_MODE" in NBNS,
      f"{len(_seeded_consts)} consts: " + ", ".join(_seeded_consts[:6]) + " ...")
check("the seeded TRAIN_KEEP_RATIO is the notebook's own value, not a restatement",
      isinstance(NBNS.get("TRAIN_KEEP_RATIO"), float) and 0.0 < NBNS["TRAIN_KEEP_RATIO"] <= 1.0,
      f"TRAIN_KEEP_RATIO={NBNS.get('TRAIN_KEEP_RATIO')!r}, "
      f"TRAIN_SELECT_MODE={NBNS.get('TRAIN_SELECT_MODE')!r}, "
      f"TRAIN_MERGE_RATIO={NBNS.get('TRAIN_MERGE_RATIO')!r}")
check("cell 2 still imports gc (cells 7/11 use it without importing it)",
      "import gc" in C2)

exec(compile(C4, f"<nb cell {I4}>", "exec"), NBNS)
exec(compile(C7, f"<nb cell {I7}>", "exec"), NBNS)
check("cells 4 + 7 exec", all(k in NBNS for k in (
    "PatchSaliencyRouter", "BipartiteTokenMerger", "checkerboard_color",
    "AdaptiveDonutOCR", "patch_ink", "SELECT_MODES", "stratified_scores")))
SELECT_MODES = NBNS["SELECT_MODES"]
check("cell 7 defines _selection_signal on the notebook's OWN model class",
      hasattr(NBNS["AdaptiveDonutOCR"], "_selection_signal"))
check("cell 7's forward() takes select_mode (not **kwargs)",
      "select_mode" in NBNS["AdaptiveDonutOCR"].forward.__code__.co_varnames,
      str(NBNS["AdaptiveDonutOCR"].forward.__code__.co_varnames[:8]))


# ----------------------------------------------------------------- stub inner model
class _StubEncoder(nn.Module):
    """Deterministic tokens. `trainable` models UNFREEZE_STAGES=1's encoder tail.

    The real run unfreezes the top Swin stage at lr 1e-5, and forward() branches on
    `any(p.requires_grad ...)` to decide whether to wrap the encoder in no_grad. Both
    states are needed: section 4's claim is specifically that the saliency term reaches
    the SHARED encoder tail, which is only true on the unfrozen branch.
    """

    def __init__(self, trainable=False):
        super().__init__()
        self.tail = nn.Linear(D, D)
        for p in self.tail.parameters():
            p.requires_grad_(trainable)

    def forward(self, pixel_values):
        g = torch.Generator().manual_seed(1234)
        base = torch.randn(pixel_values.shape[0], N, D, generator=g)
        # Make the tokens depend on the pixels so `ink`-selected and `router`-selected
        # sets are not interchangeable by accident, and on `tail` so gradient has a path
        # to the encoder when it is unfrozen.
        pooled = pixel_values.mean(dim=1).unfold(1, 32, 32).unfold(2, 32, 32)
        pooled = pooled.reshape(pixel_values.shape[0], N, -1).std(dim=-1, keepdim=True)
        return BaseModelOutput(last_hidden_state=self.tail(base + pooled))


class _StubDecoderMod(nn.Module):
    """Reads EVERY encoder position, so partial gradient coverage would be visible."""

    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(D, D)
        self.head = nn.Linear(D, VOCAB)

    def forward(self, input_ids=None, encoder_hidden_states=None, return_dict=True):
        ctx = self.proj(encoder_hidden_states).mean(dim=1)
        T = input_ids.shape[1]
        return type("O", (), {"logits": self.head(ctx.unsqueeze(1).expand(-1, T, -1))})()


class _StubInner(nn.Module):
    def __init__(self, enc_trainable=False):
        super().__init__()
        self.encoder = _StubEncoder(enc_trainable)
        self.decoder = _StubDecoderMod()
        self.config = type("C", (), {"decoder_start_token_id": 0})()


def build(router_cls=None, enc_trainable=False, seed=0, merge_ratio=0.0):
    torch.manual_seed(seed)
    m = object.__new__(NBNS["AdaptiveDonutOCR"])
    nn.Module.__init__(m)
    m.base_model_name = "stub"
    m.keep_ratio = KEEP
    m.merge_ratio = merge_ratio
    m.router = (router_cls or NBNS["PatchSaliencyRouter"])(hidden_dim=D, reduction_dim=4)
    m.tome_merger = NBNS["BipartiteTokenMerger"](hidden_dim=D)
    m.model = _StubInner(enc_trainable)
    return m


def inputs(B=2, seed=99):
    """A DOCUMENT-shaped fixture, not uniform noise -- and the distinction is load-bearing.

    `patch_ink` scores a patch by its WITHIN-PATCH std, so `torch.rand(B,3,H,W)` gives
    every one of the 4800 patches std ~= 0.289 and the ink signal carries no structure at
    all. That fixture was the first version of this function and it made two checks read
    green for the wrong reason:

      * section 1's "ink retains the MOST page ink" passed on a margin of 0.0079
        (ink 0.5079 vs random 0.5000) where the real property is ink ~0.994 vs random
        ~0.50 at keep=0.50. An ink branch resolved to the wrong tensor entirely would
        have scored about the same -- the decorative-check test in AGENTS.md ("ask what
        a FAILING system would score on this same check").
      * section 4's ink target saturated: `(_inkn > 0.15)` was ALL-ONES, so the epoch
        accumulator `ch` came out at exactly 1.0000 and the block was exercised against
        a degenerate target. That is what the failing check caught, and the check was
        right -- the fixture was wrong.

    So: a light page (uniform -> std ~0, i.e. genuine blank margins), a minority of grid
    rows carrying high-contrast vertical strokes over part of their width (-> genuine
    text lines with genuine left/right margins), and a low-amplitude noise floor
    everywhere so no patch is exactly zero. Pages differ with `seed`, which is what lets
    section 4 accumulate `ch` over two DIFFERENT batches.

    Not tuned to hit a target rate: the stroke geometry is stated here, and the resulting
    positive rate is whatever it is. (It lands near run 11's measured per-epoch `ch` of
    0.289, which is corroboration after the fact and not a design input.)
    """
    g = torch.Generator().manual_seed(seed)
    H, W = GH * 32, GW * 32
    pv = torch.ones(B, 3, H, W) + 0.02 * torch.randn(B, 3, H, W, generator=g)
    for b in range(B):
        # ~1 in 4 grid rows is a text line, offset per image so the two pages differ.
        for gr in range((b + 1) % 4, GH, 4):
            y0 = gr * 32 + 8
            x_lo = int(GW * 0.10) * 32                      # left margin stays blank
            x_hi = int(GW * (0.75 + 0.15 * ((b + gr) % 2))) * 32   # ragged right edge
            for x in range(x_lo, x_hi, 7):                  # strokes, not a solid bar
                pv[b, :, y0:y0 + 16, x:x + 3] = -1.0
    return (pv,
            torch.randint(0, VOCAB, (B, TGT), generator=g),
            torch.randint(0, VOCAB, (B, TGT), generator=g))


class _UNREACHED:
    """A name the ATTN_TARGET branch needs and that this verifier does NOT cover.

    `ATTN_TARGET` ships False (section 7 asserts it), so the 13(b) branch inside the
    saliency block is dead on run 18's config. Seeding those two names with working
    stubs would silently extend this file's claimed coverage to a path it never
    exercises -- the `verify_select_modes.py` failure in AGENTS.md, where a silent
    fall-through turned an untested path into a green check. Any touch raises instead,
    so the day ATTN_TARGET flips this file reports that it is out of scope rather than
    passing.
    """

    def __init__(self, name):
        self._n = name

    def __getattr__(self, k):
        raise AssertionError(
            f"the ATTN_TARGET branch read {self._n}.{k} -- this verifier does not cover "
            f"13(b)'s attention target and must not be read as if it did")

    def __call__(self, *a, **k):
        raise AssertionError(
            f"the ATTN_TARGET branch called {self._n}(...) -- not covered here")


def step(mode, router_cls=None, enc_trainable=False, seed=0, lam_sal=0.0, B=2,
         pages=(99,), acc0=None, step_no=1):
    """One train-mode forward+backward through the NOTEBOOK's forward().

    lam_sal > 0 adds the saliency term using cell 11's OWN block, exec'd verbatim inside
    a reconstruction of the scope it lives in -- the DO_TRAIN branch's step loop. The
    accumulators come from ACC_INIT, i.e. from the epoch loop's own preamble; the free
    names the block reads from the step loop (`pixel_values`, `labels`,
    `decoder_input_ids`, `step`, `epoch`) are supplied here, and the two the 13(b)
    branch would read are `_UNREACHED` sentinels rather than stubs.

    `pages` is one page-seed per step, so the block can be run over SEVERAL batches with
    different content and the accumulators carry across them the way the real epoch loop's
    do -- which is the only way to exercise the header-vs-`ch` scope difference. With the
    default single seed this is one step and `acc` is that step's own reading.
    """
    m = build(router_cls, enc_trainable, seed)
    m.train()                                    # use_ste = self.training
    acc = dict(acc0) if acc0 else {}
    first = None
    for i, pg in enumerate(pages):
        pv, dii, lab = inputs(B, seed=pg)
        out = m(pixel_values=pv, labels=lab, decoder_input_ids=dii, select_mode=mode)
        loss = out["loss"]
        if lam_sal > 0:
            ns = dict(NBNS)
            exec(compile(ACC_INIT, "<nb cell 11 epoch preamble>", "exec"), ns)
            ns.update(acc)                       # carry the running epoch totals in
            ns.update(dict(LAMBDA_SAL=lam_sal, outputs=out, ATTN_TARGET=False,
                           SALIENCY_THRESHOLD=0.15, pixel_values=pv, labels=lab,
                           decoder_input_ids=dii, step=step_no + i, epoch=1,
                           loss=loss, GRAD_ACCUM=1, torch=torch, F=F,
                           _teacher_dec=_UNREACHED("_teacher_dec"),
                           attn_topk_target=_UNREACHED("attn_topk_target")))
            exec(compile(SAL_BLOCK, "<nb cell 11 saliency>", "exec"), ns)
            loss = ns["loss"]
            acc = {a: ns[a] for a in _ACC_NAMES}
        loss.backward()
        if first is None:
            first = dict(out=out, loss=float(loss.detach()),
                         idx=out["topk_indices"].detach().clone(), pv=pv)

    def gvec(mod):
        gs = [p.grad.reshape(-1) for _, p in sorted(mod.named_parameters())
              if p.grad is not None]
        return torch.cat(gs) if gs else torch.zeros(0)

    return dict(model=m, acc=acc,
                g_scorer=gvec(m.router), g_enc=gvec(m.model.encoder), **first)


def gmax(t):
    """max|t|, with the EMPTY case reading as 0.0 instead of raising.

    `gvec` returns a 0-element tensor when no parameter has a `.grad` at all, which is
    exactly the state sections 3 and 4 are written to CONFIRM (the STE guard keeps the
    scorer out of the CE graph, so `p.grad is None`). `torch.max()` on 0 elements raises
    `RuntimeError: Expected reduction dim ...`, so reducing directly made the verifier
    crash on its own expected PASS -- indistinguishable from a verifier nobody ran.
    `gvec` deliberately still returns empty, because `.numel() == 0` is itself the
    assertion in section 4 ("the encoder got no grads at all").
    """
    return float(t.abs().max()) if t.numel() else 0.0


def retained_ink(pv, idx):
    ink = NBNS["patch_ink"](pv, N).float()
    return float((ink.gather(1, idx).sum(1) / (ink.sum(1) + 1e-9)).mean())


# Pull cell 11's saliency block out verbatim (the `if LAMBDA_SAL > 0:` statement), so
# section 4 exercises the SHIPPED BCE -- including F1's torch.logit recovery -- rather
# than a restatement of it that could quietly diverge.
def _is_sal(n):
    return (isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
            and isinstance(n.test.left, ast.Name) and n.test.left.id == "LAMBDA_SAL")


SAL_BLOCK = node_src(C11, _is_sal, "cell 11's `if LAMBDA_SAL > 0:` block")
check("cell 11's saliency block extracted verbatim from the notebook",
      "binary_cross_entropy_with_logits" in SAL_BLOCK and "torch.logit" in SAL_BLOCK,
      f"{len(SAL_BLOCK.splitlines())} lines")


def _lit(node):
    try:
        ast.literal_eval(node.value)
        return True
    except Exception:                                                  # noqa: BLE001
        return False


# ---- WHICH loop section 4 reconstructs. Decided by the artifact, then pinned here.
#
# Cell 11 holds TWO training loops -- the DO_TRAIN branch's and the canonical `else`
# branch's, each with its own `for epoch` / `for step` pair -- so "cell 11's step loop"
# is ambiguous in prose, and seeding a scope for the wrong one would produce a green
# check about a loop run 18 never enters. It is NOT ambiguous in the notebook: the
# saliency block occurs exactly once (node_src asserts that) and lives in the DO_TRAIN
# branch. Asserting it means a patch that ever moves the block fails HERE rather than
# leaving section 4 rebuilding a scope the block has left.
_T11 = ast.parse(C11)
_TOP11 = [n for n in _T11.body if isinstance(n, ast.If)]
assert len(_TOP11) == 1 and "DO_TRAIN" in ast.dump(_TOP11[0].test), (
    "cell 11 is no longer a single top-level `if DO_TRAIN: ... else: ...` -- re-derive "
    "the scope below before trusting section 4")
_TOP11 = _TOP11[0]
_SAL_NODE = [n for n in ast.walk(_T11) if _is_sal(n)][0]
_ELSE_LO, _ELSE_HI = _TOP11.orelse[0].lineno, _TOP11.orelse[-1].end_lineno
check("the saliency block is in cell 11's DO_TRAIN branch, not the canonical `else` "
      "branch -- THIS is the loop scope section 4 reconstructs",
      _TOP11.body[0].lineno <= _SAL_NODE.lineno <= _TOP11.body[-1].end_lineno
      and not (_ELSE_LO <= _SAL_NODE.lineno <= _ELSE_HI),
      f"block L{_SAL_NODE.lineno}; DO_TRAIN body "
      f"L{_TOP11.body[0].lineno}-{_TOP11.body[-1].end_lineno}, "
      f"else L{_ELSE_LO}-{_ELSE_HI}")

_STEP_LOOP = max((n for n in ast.walk(_TOP11) if isinstance(n, ast.For)
                  and n.lineno < _SAL_NODE.lineno <= n.end_lineno),
                 key=lambda n: n.lineno)
_EPOCH_LOOP = max((n for n in ast.walk(_TOP11) if isinstance(n, ast.For)
                   and n.lineno < _STEP_LOOP.lineno <= n.end_lineno),
                  key=lambda n: n.lineno)
check("its two enclosing loops are `for step, batch` inside `for epoch`",
      isinstance(_STEP_LOOP.target, ast.Tuple)
      and [e.id for e in _STEP_LOOP.target.elts] == ["step", "batch"]
      and getattr(_EPOCH_LOOP.target, "id", None) == "epoch",
      f"step loop L{_STEP_LOOP.lineno}-{_STEP_LOOP.end_lineno} inside epoch loop "
      f"L{_EPOCH_LOOP.lineno}-{_EPOCH_LOOP.end_lineno}")

# The accumulators the block read-modify-writes, taken FROM THE BLOCK rather than from a
# list I typed -- so a new epoch_* is inherited instead of missed. These are F3's
# telemetry: the fields that let an epoch line distinguish LAMBDA_SAL=0.5 from 0, which
# is the property whose absence made run 9's log uninterpretable. Not incidental.
_ACC_NAMES = sorted({n.target.id for n in ast.walk(ast.parse(SAL_BLOCK))
                     if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)})

# Their initialisation, lifted verbatim out of the EPOCH loop's own preamble. Typing
# `epoch_sal = 0.0` here would have worked and would have been a restatement of notebook
# logic, which this file does not do anywhere else.
ACC_INIT = "\n".join(ast.get_source_segment(C11, n) for n in _EPOCH_LOOP.body
                     if isinstance(n, ast.Assign) and _lit(n))
_acc_probe = {}
exec(compile(ACC_INIT, "<nb cell 11 epoch preamble>", "exec"), _acc_probe)
check("every accumulator the saliency block writes is initialised by cell 11's own "
      "epoch preamble (extracted, not restated)",
      all(a in _acc_probe for a in _ACC_NAMES) and len(_ACC_NAMES) >= 5,
      f"{len(_ACC_NAMES)} of them: {', '.join(_ACC_NAMES)}")
check("and all start at zero, so any nonzero reading in section 4 is the term firing",
      all(_acc_probe.get(a) == 0 for a in _ACC_NAMES),
      "; ".join(f"{a}={_acc_probe.get(a)!r}" for a in _ACC_NAMES))

# F3's epoch-summary if/else, also verbatim. Section 4 execs it in both states and
# asserts the two print DIFFERENT lines -- the exact property AGENTS.md records F3 as
# having been written to establish.
SAL_MSG = node_src(C11, lambda n: isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                   and n.test.id == "n_sal", "cell 11's F3 epoch-telemetry if/else")
check("cell 11's F3 epoch-telemetry if/else extracted verbatim",
      "sal OFF" in SAL_MSG and "lift" in SAL_MSG, f"{len(SAL_MSG.splitlines())} lines")

# ===================================================== 1. the kept set really changes
print()
print("=" * 78)
print("1. select_mode reaches forward() AND changes which tokens the decoder sees")
print("=" * 78)

R = step("router")
R2 = step("router")
Ink = step("ink")
Rnd = step("random")
Neg = step("negated")
Str = step("stratified")

noise = int((R["idx"] != R2["idx"]).sum())
check("re-running select_mode='router' is bit-identical (the noise floor is 0)",
      noise == 0, f"{noise} differing indices")
check(f"forward() selects K={K} tokens", tuple(R["idx"].shape) == (2, K),
      str(tuple(R["idx"].shape)))

d_ink = int((set(R["idx"][0].tolist()) ^ set(Ink["idx"][0].tolist())).__len__())
check("select_mode='ink' changes the kept set vs 'router' (not just the return dict)",
      d_ink > 0 and d_ink > noise, f"{d_ink} indices differ symmetrically, noise {noise}")
sets = {m: frozenset(s["idx"][0].tolist())
        for m, s in (("router", R), ("ink", Ink), ("random", Rnd),
                     ("negated", Neg), ("stratified", Str))}
check("all five exercised modes produce DISTINCT kept sets",
      len(set(sets.values())) == 5, f"{len(set(sets.values()))} distinct of 5")

# Directed, not merely different. patch-ink top-K maximises retained ink BY
# CONSTRUCTION, so a correct ink branch must sit at the ceiling. A branch that
# resolved to noise, to the wrong tensor, or to a transposed grid would pass the
# 'differs' check above and fail this one.
#
# The BAR matters as much as the direction. On the uniform-noise fixture this check
# started with, every patch had the same within-patch std, ink scored 0.5079 against
# random's 0.5000, and "ink is the max" passed on a margin of 0.008 -- a check a badly
# broken ink branch would also pass. On a document-shaped page the real property is the
# one run 9 measured on FUNSD: the ink oracle retains ~0.994 of the page's ink at
# keep=0.50 against random's ~0.50. So the threshold is stated absolutely, at a level
# only a genuine top-K-of-ink can reach.
ri = {m: retained_ink(s["pv"], s["idx"]) for m, s in
      (("router", R), ("ink", Ink), ("random", Rnd), ("negated", Neg))}
print(f"  retained ink at keep={KEEP}: " +
      "  ".join(f"{m}={v:.4f}" for m, v in ri.items()))
check("ink retains the MOST page ink of any mode (it is the top-K of ink itself)",
      ri["ink"] == max(ri.values()) and ri["ink"] > ri["random"],
      f"ink {ri['ink']:.4f} vs random {ri['random']:.4f}")
check("and it sits at the CEILING, not a hair above random -- >= 0.95 of the page's ink, "
      "the property run 9 measured on FUNSD (0.994 vs random 0.50)",
      ri["ink"] >= 0.95 and ri["ink"] - ri["random"] > 0.30,
      f"ink {ri['ink']:.4f}, margin over random {ri['ink'] - ri['random']:+.4f}")
check("'random' lands near 0.50 of the ink (the structure-free baseline)",
      0.40 < ri["random"] < 0.60, f"{ri['random']:.4f}")
check("'negated' is the complement direction of 'router' (guard against a no-op)",
      sets["negated"] != sets["router"] and
      abs(ri["negated"] - ri["router"]) > 1e-6,
      f"negated {ri['negated']:.4f} vs router {ri['router']:.4f}")

# ================================================================ 2. the echo is live
print()
print("=" * 78)
print("2. forward() echoes the mode it USED (what cell 11's step-0 assert reads)")
print("=" * 78)

for mode in SELECT_MODES:
    s = step(mode)
    check(f"forward() returns select_mode={mode!r}", s["out"].get("select_mode") == mode,
          repr(s["out"].get("select_mode")))
check("the echo tracks the argument rather than a hardcoded default",
      len({step(m)["out"]["select_mode"] for m in SELECT_MODES}) == len(SELECT_MODES))
try:
    step("inkk")
    check("an unknown mode raises instead of falling through", False, "no raise")
except ValueError as e:
    check("an unknown mode raises instead of falling through", "inkk" in str(e),
          str(e)[:70])

# ====================================================== 3. the STE guard, where it can fail
print()
print("=" * 78)
print("3. the router head gets NO task gradient under an external ranking")
print("=" * 78)

g = {m: gmax(step(m)["g_scorer"]) for m in SELECT_MODES}
for m in SELECT_MODES:
    print(f"  max|d(CE)/d(scorer)|  {m:<20s} {g[m]:.3e}")
check("select_mode='router' DOES send task gradient to the scorer (the pairing)",
      g["router"] > 0, f"{g['router']:.3e}")
check("select_mode='negated' does too (it still ranks BY the scorer)",
      g["negated"] > 0, f"{g['negated']:.3e}")
for m in ("ink", "random", "stratified", "stratified_negated"):
    check(f"select_mode={m!r} sends EXACTLY zero task gradient to the scorer",
          g[m] == 0.0, f"{g[m]:.3e}")

# Which of those zeros the guard is actually responsible for. `patch_ink` and
# `torch.rand` have no autograd graph, so for ink/random the STE's
# `select_scores is None` clause is a NO-OP -- the zero is free. For stratified* the
# override IS a differentiable function of self.router.scorer(...), so there the clause
# is the only thing standing between the scorer and a gradient it did not earn.
m_probe = build()
m_probe.train()
pv, _, _ = inputs()
vt = m_probe.model.encoder(pv).last_hidden_state
for mode, want in (("ink", False), ("random", False),
                   ("stratified", True), ("stratified_negated", True)):
    ss, _inv = m_probe._selection_signal(pv, vt, mode)
    check(f"_selection_signal({mode!r}) override requires_grad is {want} "
          f"(so the guard is {'load-bearing' if want else 'a no-op'} on this mode)",
          bool(ss.requires_grad) == want, f"requires_grad={bool(ss.requires_grad)}")

# Sabotage: delete the `and select_scores is None` clause from the notebook's OWN
# router source and re-exec it. If the clause were decorative, this would change
# nothing. It must turn the stratified zeros above into a live gradient.
_CLAUSE = "self.training and use_ste and select_scores is None"
check("the STE guard clause is present in cell 4 exactly once (anchor for the sabotage)",
      C4.count(_CLAUSE) == 1, f"{C4.count(_CLAUSE)} hits")
_sab_ns = dict(NBNS)
exec(compile(C4.replace(_CLAUSE, "self.training and use_ste", 1),
             "<nb cell 4 SABOTAGED>", "exec"), _sab_ns)
_SabRouter = _sab_ns["PatchSaliencyRouter"]
g_sab = {m: gmax(step(m, router_cls=_SabRouter)["g_scorer"])
         for m in ("router", "ink", "stratified")}
check("SABOTAGE (guard clause removed) leaks gradient into the scorer under "
      "'stratified' -- so the PASS above is a real property, not a free zero",
      g_sab["stratified"] > 0, f"sabotaged {g_sab['stratified']:.3e} vs shipped "
      f"{g['stratified']:.3e}")
check("SABOTAGE leaves 'router' unchanged (it isolates the clause, not the STE)",
      g_sab["router"] == g["router"], f"{g_sab['router']:.3e} vs {g['router']:.3e}")
check("SABOTAGE still reads 0.0 under 'ink' -- confirming ink's zero comes from the "
      "MISSING GRAPH, not from the guard",
      g_sab["ink"] == 0.0, f"{g_sab['ink']:.3e}")

# ============================================ 4. why SUPERVISE_SALIENCY must stay ON
print()
print("=" * 78)
print("4. under 'ink' the saliency term is the scorer's ONLY gradient -- and it")
print("   reaches the UNFROZEN encoder tail the decoder reads")
print("=" * 78)

s_off = step("ink", enc_trainable=True, lam_sal=0.0)
s_on = step("ink", enc_trainable=True, lam_sal=0.5)
s_on2 = step("ink", enc_trainable=True, lam_sal=0.5)
check("cell 11 ships LAMBDA_SAL = 0.5 on the supervised branch",
      "LAMBDA_SAL = 0.5" in C11)
check("with the saliency term OFF, 'ink' gives the scorer zero gradient "
      "(the head is inert -- run 18's stated consequence)",
      gmax(s_off["g_scorer"]) == 0.0,
      f"{gmax(s_off['g_scorer']):.3e}")
check("with the saliency term ON, 'ink' DOES train the scorer (so it is not dead code)",
      gmax(s_on["g_scorer"]) > 0,
      f"{gmax(s_on['g_scorer']):.3e}")


# F3's property, exercised on the notebook's OWN summary block rather than asserted of
# it: an epoch line must be able to tell LAMBDA_SAL=0.5 from LAMBDA_SAL=0. Run 9 printed
# five epochs of `Avg Loss 0.3091 | CE 0.3091`, and AGENTS.md records that as saying
# nothing in either direction -- the term was unlogged whether or not it fired, so the
# log could not distinguish the branch that ran. This is the check that the fix holds.
def _msg(acc, lam, n_steps=1):
    ns = dict(_acc_probe, LAMBDA_SAL=lam, _n=n_steps)
    ns.update(acc)
    exec(compile(SAL_MSG, "<nb cell 11 F3 summary>", "exec"), ns)
    return ns["_sal_msg"]


m_on, m_off = _msg(s_on["acc"], 0.5), _msg({}, 0.0)
print(f"  F3 epoch line, term ON : {m_on}")
print(f"  F3 epoch line, term OFF: {m_off}")
check("the saliency term moves cell 11's own epoch telemetry -- F3's property, that the "
      "log distinguishes LAMBDA_SAL=0.5 from 0, which run 9's log could not",
      m_on != m_off and "sal OFF" in m_off and "sal OFF" not in m_on,
      f"n_sal={s_on['acc'].get('n_sal')} on vs 0 off")
check("the block does not execute at LAMBDA_SAL=0, so the accumulators stay at the "
      "zeros cell 11 initialised them to -- which is what 'sal OFF' reports",
      s_off["acc"] == {} and all(_acc_probe[a] == 0 for a in _ACC_NAMES))

# `ch` is the ink target's positive rate, and the reason it gets its own checks is the
# AGENTS.md gotcha: cell 11 ALSO prints a positive rate in its step-0 header, the two are
# computed over different scopes, and in run 11 they disagreed by 46% (header 0.420 vs
# `ch` 0.289). A pre-run reproduction that matched `ch` to 0.006 therefore looked 32% off
# against the header. So two separate things are worth asserting: that the target is
# non-degenerate at all, and that `ch` really is the multi-step mean rather than a second
# copy of the header's single-batch number.
_ch1 = s_on["acc"]["epoch_ch"] / max(s_on["acc"]["n_sal"], 1)
check("the ink target is NON-DEGENERATE on a document-shaped page: `ch` is a rate "
      "strictly inside (0, 1), not the saturated 1.0 a uniform-noise fixture gives",
      0.0 < _ch1 < 1.0,
      f"ch={_ch1:.4f} over {s_on['acc']['n_sal']} step(s), "
      f"ov={s_on['acc']['epoch_ov'] / max(s_on['acc']['n_sal'], 1):.4f}")

# Two steps on DIFFERENT pages, accumulators carried across them exactly as the epoch
# loop carries them. `ch` must move away from step 0's own rate -- that difference IS the
# header-vs-`ch` discrepancy, reproduced rather than taken on faith from run 11's log.
s_two = step("ink", enc_trainable=True, lam_sal=0.5, pages=(99, 17), step_no=0)
_ch2 = s_two["acc"]["epoch_ch"] / max(s_two["acc"]["n_sal"], 1)
_hdr = _ch1                      # step 0's rate = what the header print reports
check("`ch` is the mean over STEPS, so two pages give a different figure from the "
      "step-0 header print -- the 46% disagreement AGENTS.md says to trust `ch` over",
      s_two["acc"]["n_sal"] == 2 and abs(_ch2 - _hdr) > 1e-6,
      f"header (step 0) {_hdr:.4f} vs ch over 2 steps {_ch2:.4f} "
      f"-- {abs(_ch2 - _hdr) / _hdr * 100:.1f}% apart")
check("and `ov` must be read as lift over `ch`, not as an absolute -- cell 11's own "
      "comment says so, and on an UNTRAINED scorer the lift is ~0 by construction",
      abs(s_two["acc"]["epoch_ov"] / 2 - _ch2) < 0.15,
      f"ov {s_two['acc']['epoch_ov'] / 2:.4f} vs ch {_ch2:.4f} "
      f"(lift {s_two['acc']['epoch_ov'] / 2 - _ch2:+.4f})")

enc_noise = gmax((s_on["g_enc"] - s_on2["g_enc"]))
enc_delta = gmax((s_on["g_enc"] - s_off["g_enc"]))
check("re-running the same config is bit-identical (so 'differs' below is not noise)",
      enc_noise == 0.0, f"noise floor {enc_noise:.3e}")
check("the saliency term CHANGES the gradient on the unfrozen encoder tail -- "
      "so turning SUPERVISE_SALIENCY off would move two knobs, not one",
      enc_delta > enc_noise, f"max|delta| {enc_delta:.3e} vs noise {enc_noise:.3e}")
check("cell 11 ships UNFREEZE_STAGES = 1 (the premise of the check above)",
      "UNFREEZE_STAGES = 1" in C11)

# And the claim is scoped to the UNFROZEN branch. With a frozen encoder, forward()
# takes the no_grad path, so the same term reaches the scorer and NOT the encoder.
s_frozen = step("ink", enc_trainable=False, lam_sal=0.5)
check("with the encoder FROZEN the same term reaches the scorer but not the encoder "
      "(so section 4's claim is about UNFREEZE_STAGES, not about the loss)",
      gmax(s_frozen["g_scorer"]) > 0 and s_frozen["g_enc"].numel() == 0,
      f"scorer {gmax(s_frozen['g_scorer']):.3e}, "
      f"encoder grads {s_frozen['g_enc'].numel()}")

# ================================== 5. cell 11's guards fire on the mismatch they name
print()
print("=" * 78)
print("5. cell 11's step-0 assert and SELECT_MODES cross-check are NON-VACUOUS")
print("=" * 78)

A_ECHO = node_src(C11, lambda n: isinstance(n, ast.Assert) and
                  "did not reach forward()" in ast.dump(n), "cell 11's step-0 echo assert")
A_MODES = node_src(C11, lambda n: isinstance(n, ast.Assert) and
                   "_TRAIN_SELECT_MODES" in ast.dump(n),
                   "cell 11's SELECT_MODES cross-check")
print(f"  extracted: {A_ECHO.splitlines()[0].strip()[:66]}...")


def runs_clean(src, ns):
    try:
        exec(compile(src, "<nb assert>", "exec"), ns)
        return True, ""
    except AssertionError as e:
        return False, str(e).replace("\n", " ")[:90]


ok, _ = runs_clean(A_ECHO, {"outputs": {"select_mode": "ink"}, "TRAIN_SELECT_MODE": "ink"})
check("echo assert passes when the model used the requested mode", ok)
ok, msg = runs_clean(A_ECHO, {"outputs": {"select_mode": "router"},
                              "TRAIN_SELECT_MODE": "ink"})
check("echo assert RAISES when the model used 'router' but the config said 'ink' "
      "(the silent-4-hour-run failure)", not ok, msg)
ok, msg = runs_clean(A_ECHO, {"outputs": {}, "TRAIN_SELECT_MODE": "ink"})
check("echo assert RAISES when forward() does not echo at all (un-regenerated "
      "notebook / **kwargs)", not ok, msg)

ok, _ = runs_clean(A_MODES, {"TRAIN_SELECT_MODE": "ink", "SELECT_MODES": SELECT_MODES})
check("cell 11's cross-check passes for the shipped mode", ok)
ok, msg = runs_clean(A_MODES, {"TRAIN_SELECT_MODE": "ink",
                               "SELECT_MODES": ("router", "random")})
check("cell 11's cross-check RAISES when cell 2's list has drifted from cell 7's",
      not ok, msg)

# The two lists must actually agree today, or the cross-check is only latent.
c2_modes = None
for nd in ast.walk(ast.parse(C2)):
    if isinstance(nd, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_TRAIN_SELECT_MODES" for t in nd.targets):
        c2_modes = ast.literal_eval(nd.value)
check("cell 2's _TRAIN_SELECT_MODES equals cell 7's SELECT_MODES today",
      tuple(c2_modes or ()) == tuple(SELECT_MODES),
      f"{c2_modes} vs {SELECT_MODES}")

# ======================================== 6. cell 2's run-18 guards, scenario by scenario
print()
print("=" * 78)
print("6. cell 2's _VS_RUN9 guard chain -- run 18 flipped TRAIN_MERGE_RATIO back to 0")
print("=" * 78)

GUARD_SRC = []
for nd in ast.parse(C2).body:
    seg = ast.get_source_segment(C2, nd) or ""
    if isinstance(nd, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("_VS_RUN9", "_VS_RUN9_WHY", "RUN5_CKPT_BYTES",
                                                 "PRUNED_CKPT_BYTES") for t in nd.targets):
        GUARD_SRC.append(seg)
    elif isinstance(nd, ast.Assert) and "_VS_RUN9" in ast.dump(nd):
        GUARD_SRC.append(seg)
    elif isinstance(nd, ast.If) and "CKPT IDENTITY" in seg:
        GUARD_SRC.append(seg)
    elif isinstance(nd, ast.Assert) and "_TRAIN_SELECT_MODES" in ast.dump(nd):
        GUARD_SRC.append(seg)
    elif isinstance(nd, ast.Assert) and "changes TWO things against run 9" in ast.dump(nd):
        GUARD_SRC.append(seg)
check("extracted cell 2's guard chain (both asserts, _VS_RUN9, the size block)",
      len(GUARD_SRC) >= 6, f"{len(GUARD_SRC)} statements")
GUARD = "\n".join(GUARD_SRC)
check("the guard chain still keys on TRAIN_SELECT_MODE, not on TRAIN_MERGE_RATIO alone",
      "TRAIN_SELECT_MODE != 'router'" in GUARD)

TMP = os.path.join(ROOT, "results", "_tmp_ckpt_probe")
os.makedirs(TMP, exist_ok=True)
paths = {}
for tag, nbytes in (("run5", 1045901275), ("pruned", 1045901771), ("odd", 12345)):
    p = os.path.join(TMP, f"{tag}.bin")
    if not os.path.exists(p) or os.path.getsize(p) != nbytes:
        with open(p, "wb") as fh:
            fh.truncate(nbytes)       # sparse -- no 1 GB written
    paths[tag] = p


def scenario(mode, merge, ckpt, train=True):
    ns = {"os": os, "TRAIN_SELECT_MODE": mode, "TRAIN_MERGE_RATIO": merge,
          "RESUME_CKPT": ckpt, "DO_TRAIN": train,
          "_TRAIN_SELECT_MODES": tuple(SELECT_MODES), "print": lambda *a, **k: None}
    try:
        exec(compile(GUARD, "<nb cell 2 guards>", "exec"), ns)
        return None
    except AssertionError as e:
        return str(e).replace("\n", " ")[:80]


TABLE = [
    ("ink", 0.0, None, True, True,
     "run 18 with no checkpoint -- the guard run 14's knob would have silenced"),
    ("ink", 0.0, paths["run5"], True, False,
     "run 18 as it ships: ink, no merging, run-5 weights"),
    ("ink", 0.0, paths["pruned"], True, True,
     "run 18 pointed at a pruning-era checkpoint (run 12's exact failure)"),
    ("ink", 0.0, paths["odd"], True, True,
     "run 18 pointed at an unrecognised checkpoint"),
    ("ink", 0.40, paths["run5"], True, True,
     "ink AND merging -- two knobs against run 9 at once"),
    ("router", 0.40, paths["run5"], True, False, "run 14 as it shipped (still passes)"),
    ("router", 0.0, None, True, False, "run 9's own config -- guard correctly dormant"),
    ("inkk", 0.0, paths["run5"], True, True, "a typo'd mode"),
]
for mode, merge, ckpt, train, want_raise, why in TABLE:
    msg = scenario(mode, merge, ckpt, train)
    got_raise = msg is not None
    check(f"{'RAISES' if want_raise else 'passes':>7}: {why}",
          got_raise == want_raise,
          msg if got_raise else "no raise")

# =============================================== 7. the notebook ships run 18's config
print()
print("=" * 78)
print("7. the shipped config is T4's EVAL-ONLY sweep (run 18 cancelled 2026-10-02)")
print("=" * 78)

ns2 = {}
for nd in ast.parse(C2).body:
    if isinstance(nd, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in
            ("DO_TRAIN", "TRAIN_KEEP_RATIO", "TRAIN_MERGE_RATIO", "TRAIN_SELECT_MODE",
             "TRAIN_EPOCHS", "SUPERVISE_SALIENCY", "ATTN_TARGET", "SALIENCY_THRESHOLD",
             "ALLOW_CPU") for t in nd.targets):
        try:
            exec(compile(ast.Module([nd], []), "<nb>", "exec"), {}, ns2)
        except Exception:                                            # noqa: BLE001
            pass
print(f"  shipped: {ns2}")

# ---- REWRITTEN 2026-10-02. This section used to assert the shipped config IS run 18:
# `TRAIN_SELECT_MODE == 'ink'` and `DO_TRAIN == True`. Run 18 is now CANCELLED by user
# ruling (it was staged by a session whose chat was lost and authorised by nothing in
# AGENTS.md), and the generator ships T4's eval-only config instead. Left unchanged, this
# section would have gone red for asserting a cancelled run's values -- a staleness guard
# keyed on the state it was written in rather than on the condition it cares about, which
# is the D4 defect this project already has on record. So it checks the CURRENT intent.
check("DO_TRAIN ships False -- T4 is EVAL-ONLY, no training",
      ns2.get("DO_TRAIN") is False, f"shipped {ns2.get('DO_TRAIN')!r}")
check("TRAIN_SELECT_MODE ships 'router' -- run 18's 'ink' arm is reverted, not staged",
      ns2.get("TRAIN_SELECT_MODE") == "router", repr(ns2.get("TRAIN_SELECT_MODE")))

# The train-time knobs are INERT at DO_TRAIN=False (cell 9 skips the train set, cell 11
# takes the `else` branch). They are still checked, and the reason is not habit: they are
# the values a future DO_TRAIN=True run INHERITS. A drift here is invisible today and
# decides a 4-hour run later -- which is exactly how run 18's 'ink' came to sit in a
# shipped config that nobody had authorised.
print("  [info] the knobs below are inert at DO_TRAIN=False; they are what a future "
      "DO_TRAIN=True run would inherit, so drift here is latent, not harmless")
for k, v in (("TRAIN_KEEP_RATIO", 0.50), ("TRAIN_MERGE_RATIO", 0.0),
             ("TRAIN_EPOCHS", 5), ("SUPERVISE_SALIENCY", True), ("ATTN_TARGET", False),
             ("SALIENCY_THRESHOLD", 0.15), ("ALLOW_CPU", False)):
    check(f"{k} still matches run 9 ({v!r}) -- inherited by any future train run",
          ns2.get(k) == v, f"shipped {ns2.get(k)!r}")
check("cell 11 passes the config knob, not a literal, into forward()",
      "select_mode=TRAIN_SELECT_MODE" in C11)
check("cell 11's header prints the selection regime (D5: an unlogged knob shaped 2 runs)",
      "select_mode={TRAIN_SELECT_MODE!r}" in C11)
check("cell 2's PLAN line states the selection regime too",
      "selection={TRAIN_SELECT_MODE!r}" in C2)
check("the EVAL sweep still builds at merge_ratio=0.0 and sets it per row",
      "AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0" in C11)

print()
print("=" * 78)
if fails:
    print(f"{len(fails)} FAIL")
    for f in fails:
        print(f"  FAILED: {f}")
else:
    print("ALL CHECKS PASS")
sys.exit(1 if fails else 0)
