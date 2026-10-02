"""Execution check for the `select_mode`-in-training change (run 18's mechanism).

Runs the REAL `AdaptiveDonutOCR.forward`, `.generate` dispatch and
`._selection_signal` against stub backbones -- no GPU, no weight download. Per
AGENTS.md: "Verify that patches RUN, not just parse."

WHAT IS ACTUALLY AT RISK HERE, in order:

  1. `generate()` was REFACTORED. Its inline select_mode dispatch was replaced by
     a call to the shared `_selection_signal`. Every recorded result in this
     project (runs 7-14, D11, D12, M1) came through that inline code. If the
     extraction changed ANY mode by so much as one index, every historical row
     silently stops being comparable and nothing errors. So section 2 pins the
     new helper against a verbatim restatement of the OLD inline block and
     demands bit-identical indices on all six modes.

     The restatement in `_OLD_INLINE_DISPATCH` is deliberate here and is the one
     place this repo's "never restate the logic under test" rule inverts: the
     thing under test is the NEW helper, and the OLD code is the reference. A
     restatement is the only available oracle because there is no VCS in this
     working tree.

  2. `forward(select_mode="router")` must reproduce the pre-change forward()
     exactly, or runs 2-14 stop being reproducible.

  3. Under an override, `PatchSaliencyRouter` skips the STE (router.py:92). That
     means the SCORER gets no task gradient -- correct, and the definition of a
     "free selector" arm. But the DECODER must still get gradient, or arm I
     trains nothing at all and would produce a plausible, meaningless checkpoint.
     Section 4 asserts both halves. This is the single most important check in
     the file: a silently-untrained arm is exactly the failure that reads as a
     real result.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import torch
import torch.nn as nn

from src.model import AdaptiveDonutOCR, SELECT_MODES, patch_ink, stratified_scores
from src.router import PatchSaliencyRouter
from src.tome import BipartiteTokenMerger

PASS = 0
FAIL = 0
FAILED = []

GH, GW = 8, 6           # small token grid; 8*6 = 48 tokens
N = GH * GW
D = 32
STRIDE = 32
H, W = GH * STRIDE, GW * STRIDE


def check(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s%s" % (label, (" -- " + detail) if detail else ""))
    else:
        FAIL += 1
        FAILED.append(label)
        print("  [FAIL] %s%s" % (label, (" -- " + detail) if detail else ""))


# ---------------------------------------------------------------------------
# The OLD inline dispatch, restated verbatim from generate() as it stood before
# the extraction. Reference oracle only -- see the module docstring.
# ---------------------------------------------------------------------------
def _OLD_INLINE_DISPATCH(model, pixel_values, visual_tokens, select_mode):
    B = pixel_values.shape[0]
    device = pixel_values.device
    n = visual_tokens.shape[1]
    if select_mode not in SELECT_MODES:
        raise ValueError(f"select_mode must be one of {SELECT_MODES}, got {select_mode!r}")
    select_scores = None
    invert = False
    if select_mode == "negated":
        invert = True
    elif select_mode == "random":
        select_scores = torch.rand(B, n, device=device, dtype=visual_tokens.dtype)
    elif select_mode == "ink":
        select_scores = patch_ink(pixel_values, n).to(visual_tokens.dtype)
    elif select_mode in ("stratified", "stratified_negated"):
        grid = (pixel_values.shape[-2] // 32, pixel_values.shape[-1] // 32)
        raw = model.router.scorer(visual_tokens).squeeze(-1)
        select_scores = stratified_scores(
            raw, grid=grid, negate=(select_mode == "stratified_negated")
        ).to(visual_tokens.dtype)
    return select_scores, invert


# ---------------------------------------------------------------------------
class _StubEncoder(nn.Module):
    """Deterministic content-dependent tokens, with a real trainable flag."""

    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(STRIDE * STRIDE, D)
        for p in self.parameters():
            p.requires_grad = False

    def forward(self, pixel_values):
        g = pixel_values.mean(dim=1)
        blocks = g.unfold(1, STRIDE, STRIDE).unfold(2, STRIDE, STRIDE)
        flat = blocks.reshape(pixel_values.shape[0], GH * GW, -1)
        out = self.proj(flat)
        return type("Enc", (), {"last_hidden_state": out})()


class _StubDecoder(nn.Module):
    VOCAB = 23

    def __init__(self):
        super().__init__()
        self.read = nn.Linear(D, D)          # consumes encoder_hidden_states
        self.emb = nn.Embedding(self.VOCAB, D)
        self.head = nn.Linear(D, self.VOCAB)

    def forward(self, input_ids=None, encoder_hidden_states=None, return_dict=True):
        ctx = self.read(encoder_hidden_states).mean(dim=1, keepdim=True)
        h = self.emb(input_ids) + ctx
        return type("Dec", (), {"logits": self.head(h)})()


class _StubBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = _StubEncoder()
        self.decoder = _StubDecoder()


def build():
    m = object.__new__(AdaptiveDonutOCR)
    nn.Module.__init__(m)
    m.base_model_name = "stub"
    m.keep_ratio = 0.5
    m.merge_ratio = 0.0
    m.freeze_encoder = True
    m.encoder_hidden_dim = D
    m.model = _StubBackbone()
    m.router = PatchSaliencyRouter(hidden_dim=D, reduction_dim=8)
    m.tome_merger = BipartiteTokenMerger(hidden_dim=D)
    return m


def make_page(B=2, seed=0):
    g = torch.Generator().manual_seed(seed)
    px = torch.rand(B, 3, H, W, generator=g)
    # Stamp high-contrast "text" rows so patch_ink has real structure to find.
    for b in range(B):
        for row in range(1 + b, GH, 3):
            px[b, :, row * STRIDE:row * STRIDE + STRIDE, :] = torch.rand(
                3, STRIDE, W, generator=g) * 4.0 - 2.0
    return px


def run_checks():
    torch.manual_seed(0)
    print("=" * 78)
    print("verify_train_select_mode -- select_mode threaded into the TRAINING path")
    print("=" * 78)
    m = build()
    px = make_page()
    vt = m.model.encoder(px).last_hidden_state

    # -- 1 ------------------------------------------------------------------
    print("\n[1] The knob exists on BOTH paths, with the safe default.")
    import inspect
    fsig = inspect.signature(AdaptiveDonutOCR.forward).parameters
    gsig = inspect.signature(AdaptiveDonutOCR.generate).parameters
    check("select_mode" in fsig, "forward() accepts select_mode")
    check("select_mode" in gsig, "generate() accepts select_mode")
    check(fsig["select_mode"].default == "router",
          "forward() defaults to 'router' (preserves runs 2-14)",
          "default=%r" % fsig["select_mode"].default)
    check(gsig["select_mode"].default == "router", "generate() default unchanged")

    # -- 2 ------------------------------------------------------------------
    print("\n[2] REFACTOR SAFETY: new shared helper == old inline dispatch, bit-for-bit.")
    print("    (generate() is the path every recorded result came through.)")
    for mode in SELECT_MODES:
        torch.manual_seed(1234)
        new_s, new_i = m._selection_signal(px, vt, mode)
        torch.manual_seed(1234)
        old_s, old_i = _OLD_INLINE_DISPATCH(m, px, vt, mode)
        if old_s is None:
            same = new_s is None
            det = "both None"
        else:
            same = (new_s is not None
                    and new_s.shape == old_s.shape
                    and torch.equal(new_s, old_s))
            det = "max|diff|=%.3e" % (
                (new_s - old_s).abs().max().item() if new_s is not None else float("nan"))
        check(same and new_i == old_i, "mode %-19s identical to old inline code" % mode, det)

    print("\n    NON-VACUITY: the six modes must not all be the same selection,")
    print("    or the equality checks above would be trivially satisfiable.")
    sel = {}
    for mode in SELECT_MODES:
        torch.manual_seed(7)
        s, inv = m._selection_signal(px, vt, mode)
        _, _, idx, _ = m.router(vt, keep_ratio=0.5, coords=None,
                                use_ste=False, select_scores=s, invert=inv)
        sel[mode] = set(idx[0].tolist())
    distinct = len({frozenset(v) for v in sel.values()})
    check(distinct >= 5, "at least 5 of 6 modes select a distinct token set",
          "%d distinct sets from %d modes" % (distinct, len(SELECT_MODES)))

    # -- 3 ------------------------------------------------------------------
    print("\n[3] forward() honours the mode, and 'ink' really means ink.")
    out_r = m(px, labels=None, decoder_input_ids=torch.zeros(2, 4, dtype=torch.long),
              keep_ratio=0.5, select_mode="router")
    out_i = m(px, labels=None, decoder_input_ids=torch.zeros(2, 4, dtype=torch.long),
              keep_ratio=0.5, select_mode="ink")
    check(out_r["select_mode"] == "router" and out_i["select_mode"] == "ink",
          "forward() REPORTS the mode it ran (telemetry, not transcription)")
    ri = set(out_r["topk_indices"][0].tolist())
    ii = set(out_i["topk_indices"][0].tolist())
    check(ri != ii, "router and ink select different tokens in forward()",
          "overlap %d/%d" % (len(ri & ii), len(ri)))

    ink = patch_ink(px, N)
    K = out_i["topk_indices"].shape[1]
    want = set(torch.topk(ink[0], K).indices.tolist())
    check(ii == want, "forward(select_mode='ink') == exact top-K of patch_ink",
          "%d/%d match" % (len(ii & want), K))

    # The ORACLE property, asserted as a strict maximum rather than as a
    # pairwise win. An earlier version of this check compared ink against the
    # router and passed 0.741 vs 0.740 -- a 0.001 margin, i.e. a coin flip on
    # this fixture, because the stub encoder is a linear map of raw pixels so an
    # untrained router already correlates with patch contrast. That check was
    # decorative: a fall-through bug would have passed it roughly half the time.
    # Top-K of ink MAXIMIZES summed retained ink by construction, so ink must be
    # the strict argmax over every other mode. That cannot pass by luck.
    ret = {}
    for mode in SELECT_MODES:
        torch.manual_seed(5)
        o = m(px, decoder_input_ids=torch.zeros(2, 3, dtype=torch.long),
              keep_ratio=0.5, select_mode=mode)
        ret[mode] = float((ink.gather(1, o["topk_indices"]).sum(1) / ink.sum(1)).mean())
    others = {k: v for k, v in ret.items() if k != "ink"}
    best_other = max(others, key=lambda k: others[k])
    check(all(ret["ink"] > v for v in others.values()),
          "ink is the STRICT argmax of retained ink over all 6 modes",
          "ink %.4f vs best other (%s) %.4f, margin %+.4f"
          % (ret["ink"], best_other, others[best_other], ret["ink"] - others[best_other]))
    check(ret["negated"] < ret["router"],
          "'negated' retains LESS ink than 'router' (invert flag is wired)",
          "negated %.4f < router %.4f" % (ret["negated"], ret["router"]))

    # -- 4 ------------------------------------------------------------------
    print("\n[4] GRADIENT ROUTING -- the check that stops a silently-untrained arm.")
    print("    Under an override the STE is skipped (router.py:92), so the SCORER")
    print("    gets no task gradient. The DECODER must still get one.")

    def grads(mode):
        mm = build()
        mm.train()
        ids = torch.randint(0, _StubDecoder.VOCAB, (2, 5))
        o = mm(px, labels=ids, decoder_input_ids=ids, keep_ratio=0.5, select_mode=mode)
        o["loss"].backward()
        sc = sum(p.grad.abs().sum().item() for p in mm.router.scorer.parameters()
                 if p.grad is not None)
        de = sum(p.grad.abs().sum().item() for p in mm.model.decoder.parameters()
                 if p.grad is not None)
        return sc, de

    torch.manual_seed(3)
    sc_r, de_r = grads("router")
    torch.manual_seed(3)
    sc_i, de_i = grads("ink")
    torch.manual_seed(3)
    sc_s, de_s = grads("stratified")
    print("      router     mode: scorer grad %.6e | decoder grad %.6e" % (sc_r, de_r))
    print("      ink        mode: scorer grad %.6e | decoder grad %.6e" % (sc_i, de_i))
    print("      stratified mode: scorer grad %.6e | decoder grad %.6e" % (sc_s, de_s))
    check(de_i > 0, "DECODER receives gradient under 'ink' (the arm actually trains)",
          "%.3e" % de_i)
    check(sc_r > 0, "scorer receives gradient under 'router' (STE alive on default path)",
          "%.3e" % sc_r)
    check(sc_i == 0.0, "scorer receives NO task gradient under 'ink'", "%.3e" % sc_i)

    # WHY ink's zero is NOT evidence that the STE guard works, and why the
    # stratified row below is the check that is.
    #
    # The sabotage suite caught this: deleting `select_scores is None` from
    # router.py:92 leaves ink's scorer gradient at EXACTLY zero anyway, because
    # `patch_ink` is a pure function of pixels with no autograd graph, so the STE
    # multiplier `1 + (w - w.detach())` is identically 1 with nothing to
    # backpropagate. The check above therefore passes for a reason unrelated to
    # the guard, and on its own it is decorative.
    #
    # `stratified` is the discriminating case: its override IS derived from
    # `self.router.scorer(...)`, so it carries a live graph. There the guard is
    # the only thing standing between the scorer and a gradient through a
    # ranking it did not choose.
    ink_sig, _ = m._selection_signal(px, vt, "ink")
    check(ink_sig is not None and not ink_sig.requires_grad,
          "patch_ink carries NO autograd graph (so ink's zero above is structural)",
          "requires_grad=%s" % (ink_sig.requires_grad if ink_sig is not None else "n/a"))
    strat_sig, _ = m._selection_signal(px, vt, "stratified")
    check(strat_sig is not None and strat_sig.requires_grad,
          "stratified's override DOES carry a graph (so the guard is load-bearing there)",
          "requires_grad=%s" % (strat_sig.requires_grad if strat_sig is not None else "n/a"))
    check(sc_s == 0.0,
          "scorer receives NO task gradient under 'stratified' (STE truly skipped)",
          "%.3e" % sc_s)
    check(de_s > 0, "DECODER still receives gradient under 'stratified'", "%.3e" % de_s)

    # -- 5 ------------------------------------------------------------------
    print("\n[5] Unknown modes RAISE on both paths (no silent fallthrough).")
    for bad in ["oracle", "Router", "", "ink "]:
        try:
            m(px, decoder_input_ids=torch.zeros(2, 3, dtype=torch.long), select_mode=bad)
            check(False, "forward() rejects %r" % bad, "no exception raised")
        except ValueError:
            check(True, "forward() rejects %r" % bad)
        except Exception as e:
            check(False, "forward() rejects %r" % bad, "wrong type: %r" % e)
    try:
        m._selection_signal(px, vt, "nonsense")
        check(False, "_selection_signal rejects unknown mode", "no exception")
    except ValueError:
        check(True, "_selection_signal rejects unknown mode")

    # -- 6 ------------------------------------------------------------------
    print("\n[6] TRAIN/EVAL AGREEMENT -- the property the shared helper exists for.")
    print("    A mode must mean the same thing in training as at eval, or run 18's")
    print("    arms are trained on one distribution and scored on another.")
    for mode in ("router", "ink", "negated", "stratified"):
        mm = build()
        mm.eval()
        with torch.no_grad():
            v = mm.model.encoder(px).last_hidden_state
            torch.manual_seed(99)
            s1, i1 = mm._selection_signal(px, v, mode)
            _, _, idx_eval, _ = mm.router(v, keep_ratio=0.5, coords=None,
                                          use_ste=False, select_scores=s1, invert=i1)
        mm.train()
        o = mm(px, decoder_input_ids=torch.zeros(2, 3, dtype=torch.long),
               keep_ratio=0.5, select_mode=mode)
        same = torch.equal(idx_eval, o["topk_indices"])
        check(same, "mode %-11s selects identically in train() and eval()" % mode,
              "" if same else "train/eval disagree")

    # -- 7 ------------------------------------------------------------------
    print("\n[7] The default path is untouched (runs 2-14 reproducibility).")
    torch.manual_seed(11)
    a = m(px, decoder_input_ids=torch.zeros(2, 3, dtype=torch.long), keep_ratio=0.5)
    torch.manual_seed(11)
    b = m(px, decoder_input_ids=torch.zeros(2, 3, dtype=torch.long), keep_ratio=0.5,
          select_mode="router")
    check(torch.equal(a["topk_indices"], b["topk_indices"])
          and torch.equal(a["logits"], b["logits"]),
          "forward() with no select_mode == forward(select_mode='router')")

    print("\n" + "=" * 78)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    if FAILED:
        for f in FAILED:
            print("  FAILED: %s" % f)
    print("=" * 78)
    return 1 if FAIL else 0


# ===========================================================================
# SABOTAGE SUITE -- falsify the verifier itself.
#
# AGENTS.md, Conventions: "before trusting a pass, ask what a FAILING system
# would score on this same check -- if the answer is 'about the same', the check
# is decorative." And: "falsify the guard itself against both the buggy and the
# fixed form -- a guard verified only against the state it was written in is
# half-tested, and the half that matters is the one you cannot see yet."
#
# Each sabotage below is a defect that would produce a PLAUSIBLE run 18 --
# arms that train, checkpoints that load, tables that print -- and a meaningless
# result. Every one must turn this file red.
# ===========================================================================
_REAL_SIGNAL = AdaptiveDonutOCR._selection_signal
_REAL_ROUTER_FWD = PatchSaliencyRouter.forward


def _sab_ink_falls_through(self, pixel_values, visual_tokens, select_mode):
    """S1: `ink` silently resolves to the router's own scores.

    The most dangerous defect available: run 18's ink arm would be a second
    copy of the router arm. It would train, converge, and produce a clean null
    that reads as 'selection does not matter'.
    """
    if select_mode == "ink":
        return None, False
    return _REAL_SIGNAL(self, pixel_values, visual_tokens, select_mode)


def _sab_train_eval_drift(self, pixel_values, visual_tokens, select_mode):
    """S2: `ink` means something different in training than at eval."""
    s, inv = _REAL_SIGNAL(self, pixel_values, visual_tokens, select_mode)
    if select_mode == "ink" and self.training:
        s = -s
    return s, inv


def _sab_unknown_mode_ok(self, pixel_values, visual_tokens, select_mode):
    """S3: a typo'd mode falls through to router instead of raising."""
    if select_mode not in SELECT_MODES:
        return None, False
    return _REAL_SIGNAL(self, pixel_values, visual_tokens, select_mode)


def _sab_stratified_ignores_negate(self, pixel_values, visual_tokens, select_mode):
    """S4: the extraction dropped the `negate` argument."""
    if select_mode == "stratified_negated":
        return _REAL_SIGNAL(self, pixel_values, visual_tokens, "stratified")
    return _REAL_SIGNAL(self, pixel_values, visual_tokens, select_mode)


def _sab_ste_not_skipped(self, tokens, keep_ratio=0.35, coords=None, use_ste=True,
                         select_scores=None, invert=False):
    """S5: the STE guard loses its `select_scores is None` clause.

    Restated from router.py with ONE clause weakened -- a fixture, not a
    reimplementation under test.

    NOTE ON WHAT THIS SABOTAGE ACTUALLY BREAKS, because the first version of
    this file got it wrong and the suite is what said so: removing the guard is
    a NO-OP for `ink` and `random`. Their override scores carry no autograd
    graph, so the STE multiplier is identically 1 and the scorer's gradient
    stays exactly zero. The guard is load-bearing only for `stratified` and
    `stratified_negated`, whose ranking IS a differentiable function of
    `self.router.scorer(...)` -- there, dropping it sends the scorer a gradient
    through a ranking it did not produce. Section 4 must therefore test
    `stratified`, not just `ink`; testing only `ink` was decorative.
    """
    B, N, Dd = tokens.shape
    K = max(1, int(round(N * keep_ratio)))
    scores = self.scorer(tokens)
    rank_by = select_scores.reshape(B, N).to(scores.dtype) \
        if select_scores is not None else scores.squeeze(-1)
    topk_scores, topk_indices = torch.topk(
        rank_by, k=K, dim=1, largest=not invert, sorted=True)
    sel = torch.gather(tokens, 1, topk_indices.unsqueeze(-1).expand(-1, -1, Dd))
    if self.training and use_ste:                      # <-- sabotage
        w = topk_scores.unsqueeze(-1)
        sel = sel * (1.0 + (w - w.detach()))
    pc = None
    if coords is not None:
        pc = torch.gather(coords, 1,
                          topk_indices.unsqueeze(-1).expand(-1, -1, coords.shape[-1]))
    return sel, scores, topk_indices, pc


SABOTAGES = [
    ("S1 ink silently falls through to router", "sig", _sab_ink_falls_through),
    ("S2 ink differs between train() and eval()", "sig", _sab_train_eval_drift),
    ("S3 unknown mode falls through instead of raising", "sig", _sab_unknown_mode_ok),
    ("S4 stratified_negated loses its negate flag", "sig", _sab_stratified_ignores_negate),
    ("S5 STE not skipped under an external ranking", "router", _sab_ste_not_skipped),
]


def sabotage_suite():
    global PASS, FAIL, FAILED
    import contextlib
    import io

    print("\n" + "=" * 78)
    print("SABOTAGE SUITE -- can this verifier actually fail?")
    print("=" * 78)
    print("Each row breaks the code under test in a way that would still produce a")
    print("plausible run 18. A green row means THIS FILE CAUGHT IT.\n")

    results = []
    for name, target, fn in SABOTAGES:
        if target == "sig":
            AdaptiveDonutOCR._selection_signal = fn
        else:
            PatchSaliencyRouter.forward = fn
        keep = (PASS, FAIL, list(FAILED))
        PASS, FAIL, FAILED[:] = 0, 0, []
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                run_checks()
            caught, n_fail, which = FAIL > 0, FAIL, list(FAILED)
        except Exception as e:
            caught, n_fail, which = True, -1, ["raised %s" % type(e).__name__]
        finally:
            AdaptiveDonutOCR._selection_signal = _REAL_SIGNAL
            PatchSaliencyRouter.forward = _REAL_ROUTER_FWD
            PASS, FAIL, FAILED[:] = keep[0], keep[1], keep[2]
        results.append((name, caught, n_fail, which))
        print("  [%s] %-48s -> %s" % (
            "PASS" if caught else "FAIL", name,
            ("caught by %d check(s): %s" % (n_fail, which[0]))
            if caught and n_fail > 0 else
            ("caught: %s" % which[0]) if caught else "NOT CAUGHT -- check is decorative"))

    missed = [n for n, c, _, _ in results if not c]
    print()
    if missed:
        print("  %d of %d sabotages went UNDETECTED:" % (len(missed), len(results)))
        for n in missed:
            print("    - %s" % n)
        print("  The green run above does not license trusting this change.")
    else:
        print("  %d of %d sabotages detected. The checks above are load-bearing." % (
            len(results), len(results)))
    return 0 if not missed else 1


def main():
    rc = run_checks()
    rc |= sabotage_suite()
    print("\nOVERALL: %s" % ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
