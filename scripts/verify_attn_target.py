"""Verify Pending 13(b): the cross-attention target actually RUNS, not merely parses.

The standing rule in this repo is that `ast.parse` is necessary and not sufficient -- the
`test_ds` NameError shipped through a parse-clean patcher and only surfaced on Kaggle. So
every claim below is checked by EXECUTING the generated notebook's own cell sources, not by
grepping them.

What is checked, and why each one exists:

  1. cell 7 parses AND `attn_topk_target` / `patch_ink` / `AdaptiveDonutOCR` are all defined
     by executing it. A helper that is defined inside the wrong scope would pass a grep.
  2. `attn_topk_target` returns (B, N) with EXACTLY K positives at K = round(N*keep_ratio).
     The BCE term's gradient scale depends on the positive rate, so an off-by-one K is a
     silent rescaling of the whole auxiliary loss.
  3. It RAISES when handed the student's PRUNED tokens instead of the full grid. This is the
     failure that would quietly undo the entire point of 13(b): D7 measured the STE handing
     zero gradient to the N-K dropped tokens, so a target defined only on the kept set
     teaches nothing new, while still training and still looking fine.
  4. It RAISES when cross_attentions comes back empty. transformers 5.4.0 defaults to SDPA
     on BOTH the decoder config and the inner model config; with output_attentions=True it
     logs a warning and returns an EMPTY TUPLE -- it does not raise. Measured, not assumed:
     `dec.config._attn_implementation == 'sdpa'` and `cross_attentions == ()`. Without a
     guard the target would be all-zero and the 4-hour run would finish looking normal. All
     three shapes are tested (`()`, `None`, `(None, None)`) because a natural `if ca is None`
     would miss the one that actually happens. The load-bearing control is a REAL decoder
     left at its default config: it must raise, and must then succeed once cell 11's OWN
     config lines are applied to it -- so it is cell 11's code under test, not a paraphrase.
  5. Pad masking is not a no-op: masking must CHANGE the target. decoder_input_ids is padded
     to 512 while a real FUNSD target is ~310 tokens, so an inert mask means ~40% of the
     text positions are pad noise. A masking bug is invisible in the output shape.
  6. The attention target is not equal to the ink target on the same input. Careful with the
     null on this one: D8's r(attn, ink) = +0.083 is the CONTINUOUS maps, and binarizing to
     top-K roughly triples the association (r_bin +0.265, overlap 0.632 over 4 train pages,
     measured 2026-09-02). Most of that is page geometry, not shared content -- a content-free
     interior prior overlaps ink top-K at 0.667, higher than attention does -- so `--real`
     prints that floor next to the number instead of comparing against 0.500.
  7. `forward()` really returns 'visual_tokens', with N matching 'scores', by CALLING it.
     The teacher reads that key; if it were missing or pruned, check 3 would fire on Kaggle
     four hours into a run instead of here.
  8. ATTN_TARGET defaults to False, so SUPERVISE_SALIENCY alone still reproduces run 9.

Usage:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. HF_HUB_OFFLINE=1 python -u scripts/verify_attn_target.py
Read-only. CPU. Exit 0 = all checks pass.
"""
import copy
import gc
import json
import os
import sys
import textwrap

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "kaggle_pruning_run.ipynb")

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def cell_src(nb, i):
    return "".join(nb["cells"][i]["source"])


def extract_eager_block(c11):
    """Pull cell 11's real eager-config lines out so the control below tests THAT code.

    Writing the same four lines again in this file would verify my paraphrase and leave the
    notebook's copy unexercised -- the shape of decorative check this repo keeps hitting.
    """
    start = c11.index("for _cfg in (getattr(_teacher_dec")
    end = c11.index("print('13(b): frozen teacher", start)
    return textwrap.dedent(c11[start:end].rstrip())


def real_weights_section(ns, nb, apply_eager, attn_topk_target):
    """--real: run 5 weights, one real FUNSD page, the full 4800-token grid.

    Two questions only the real scale answers. (1) How big is the cross-attention tensor
    really -- I estimated ~314 MB in AGENTS.md from arithmetic and never measured it.
    (2) Is the run-5 teacher's attention degenerate on a real page? `torch.topk` on a
    near-constant map returns essentially the first K indices, which is exactly what a
    collapsed router looked like in D-A, and it would produce a target that trains fine and
    teaches a raster scan. So the baselines are reported next to the result, not instead of
    it: overlap against the first-K positional map, and against ink top-K (D8 measured
    r = +0.083, so ~chance is the PASS -- a high overlap here means the plumbing is wrong).
    """
    import time

    from datasets import load_dataset
    from transformers import DonutProcessor

    print("\n[10] REAL: run 5 weights, real FUNSD page, N=4800")
    ckpt = os.path.join(ROOT, "run 5", "checkpoints", "adaptive_donut_funsd.pt")
    if not os.path.exists(ckpt):
        check("run 5 checkpoint present", False, ckpt)
        return
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from diagnose_ste_signal import MAX_LEN, MAX_WORDS, build_target_text

    proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    ds = load_dataset("nielsr/funsd", split="train")
    pv = proc(ds[0]["image"].convert("RGB"), return_tensors="pt").pixel_values

    model = ns["AdaptiveDonutOCR"](keep_ratio=0.50, merge_ratio=0.0, freeze_encoder=True)
    sd = torch.load(ckpt, map_location="cpu", weights_only=True)
    miss, unexp = model.load_state_dict(sd, strict=False)
    check("run 5 loads with no unexpected keys", len(unexp) == 0, f"missing={len(miss)}")
    model.eval()

    # Labels exactly as cell 9 builds them: padded to 512, pad -> -100.
    text = build_target_text(ds[0])
    lab = proc.tokenizer([text], add_special_tokens=False, max_length=MAX_LEN,
                        padding="max_length", truncation=True,
                        return_tensors="pt").input_ids
    lab[lab == proc.tokenizer.pad_token_id] = -100
    dec_in = lab.clone()
    dec_in[dec_in == -100] = proc.tokenizer.pad_token_id
    t_real = int((lab != -100).sum())
    check("real labels are mostly pad (truncation matters)", t_real < MAX_LEN,
          f"{t_real}/{MAX_LEN} real tokens -> {100 * (1 - t_real / MAX_LEN):.0f}% is pad")

    with torch.no_grad():
        out = model(pixel_values=pv, decoder_input_ids=dec_in, labels=None)
    vt, N = out["visual_tokens"], out["visual_tokens"].shape[1]
    check("real grid is 4800 tokens", N == 4800, f"N={N}")

    teach = copy.deepcopy(model.model.decoder).eval()
    exec(compile(apply_eager, "<cell11-eager>", "exec"), {"_teacher_dec": teach})

    t0 = time.time()
    tgt = attn_topk_target(teach, vt, dec_in, lab, N, 0.50)
    dt = time.time() - t0
    K = int(round(N * 0.50))
    check("exactly K=2400 positives on the real grid", int(tgt.sum()) == K,
          f"{int(tgt.sum())}")
    print(f"      teacher forward + target: {dt:.1f}s  (per optimiser step, CPU)")

    # Measure the tensor I estimated. n_layers x heads x T_real x N x 4 bytes.
    nl = len(teach.model.decoder.layers) if hasattr(teach, "model") else \
        len(teach.decoder.layers)
    heads = teach.config.decoder_attention_heads
    mb = nl * heads * t_real * N * 4 / 1e6
    print(f"      cross-attention tensors: {nl} layers x {heads} heads x {t_real} x {N} "
          f"fp32 = {mb:.0f} MB (AGENTS.md estimated ~314 MB at full T)")

    # Baselines in the same table as the result, per this repo's standing lesson.
    # NOTE the null here is NOT 0.500. Top-K overlap between two spatially structured maps
    # has an inflated floor: both attention and ink avoid the page margins, so they agree
    # well above chance without sharing any content. Measured 2026-09-02, 4 FUNSD train
    # pages: an interior prior (distance from page edge, no content at all) overlaps ink
    # top-K at 0.667 -- HIGHER than attention's 0.632. So the interior row is printed on
    # every run; reading ov_ink against 0.500 would be the cosine-inflation mistake again.
    first_k = torch.zeros_like(tgt)
    first_k[:, :K] = 1.0
    ov_pos = float((tgt * first_k).sum() / K)
    ink = ns["patch_ink"](pv, N)
    ink_k = torch.zeros_like(ink)
    ink_k.scatter_(1, ink.topk(K, dim=1).indices, 1.0)
    ov_ink = float((tgt * ink_k).sum() / K)
    r_, c_ = torch.arange(80).view(-1, 1).float(), torch.arange(60).view(1, -1).float()
    interior = torch.minimum(torch.minimum(r_, 79 - r_).expand(80, 60),
                             torch.minimum(c_, 59 - c_).expand(80, 60)).flatten()
    int_k = torch.zeros_like(tgt)
    int_k[:, interior.topk(K).indices] = 1.0
    ov_int_ink = float((int_k * ink_k).sum() / K)
    rows = (tgt.view(80, 60).sum(dim=1) > 0).sum().item()
    print(f"      overlap vs first-K positional : {ov_pos:.3f}   (chance 0.500)")
    print(f"      overlap vs ink top-K          : {ov_ink:.3f}")
    print(f"        ^ null for that row, interior-prior vs ink: {ov_int_ink:.3f} "
          f"-- a content-free map scores this, so ov_ink is only meaningful ABOVE it")
    print(f"      grid rows touched             : {rows}/80")
    check("target is not the first-K positional map", ov_pos < 0.80, f"{ov_pos:.3f}")
    check("target is not ink in disguise", ov_ink < 0.80,
          f"{ov_ink:.3f} vs content-free floor {ov_int_ink:.3f}")
    check("target spans the page, not one band", rows >= 20, f"{rows}/80 rows")


def main():
    nb = json.loads(open(NB, encoding="utf-8").read())

    # ---------------------------------------------------------------- 1. exec cell 7
    # Cell 4 first: cell 7's AdaptiveDonutOCR.__init__ constructs PatchSaliencyRouter and
    # BipartiteTokenMerger from there. Executing 7 alone got a NameError at construction --
    # a real dependency the parse check cannot see, since the names resolve at call time.
    print("\n[1] executing cells 4 + 7 (modules, model, target helpers)")
    from transformers import VisionEncoderDecoderModel
    from transformers.modeling_outputs import BaseModelOutput
    ns = {"torch": torch, "nn": nn, "F": F, "gc": gc, "os": os, "json": json,
          "VisionEncoderDecoderModel": VisionEncoderDecoderModel,
          "BaseModelOutput": BaseModelOutput, "__name__": "nbcell7"}
    exec(compile(cell_src(nb, 4), "<cell4>", "exec"), ns)
    for fn in ("PatchSaliencyRouter", "BipartiteTokenMerger"):
        check(f"cell 4 defines {fn}", fn in ns)
    exec(compile(cell_src(nb, 7), "<cell7>", "exec"), ns)
    for fn in ("attn_topk_target", "patch_ink", "stratified_scores", "AdaptiveDonutOCR"):
        check(f"cell 7 defines {fn}", fn in ns)
    attn_topk_target = ns["attn_topk_target"]

    # A real decoder, because a hand-rolled stub cannot tell us whether
    # output_attentions=True actually yields cross_attentions on this transformers build.
    print("\n[2] loading a real donut decoder, eager applied by CELL 11's OWN code")
    base = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base",
                                                     low_cpu_mem_usage=True)
    dec = base.decoder.eval()
    check("real decoder defaults to sdpa (the trap is live)",
          getattr(dec.config, "_attn_implementation", None) == "sdpa",
          f"impl={getattr(dec.config, '_attn_implementation', None)!r}")
    apply_eager = extract_eager_block(cell_src(nb, 11))
    check("extracted cell 11's eager-config block", "eager" in apply_eager,
          f"{len(apply_eager.splitlines())} lines")
    exec(compile(apply_eager, "<cell11-eager>", "exec"), {"_teacher_dec": dec})
    check("cell 11's block sets eager on BOTH configs",
          getattr(dec.config, "_attn_implementation", None) == "eager"
          and getattr(dec.model.config, "_attn_implementation", None) == "eager")
    D = base.config.encoder.hidden_size
    # N is small on purpose: the helper only requires visual_tokens.shape[1] == num_tokens,
    # so a 300-token grid exercises identical code at a fraction of the attention memory.
    N, T, KEEP = 300, 24, 0.50
    torch.manual_seed(0)
    vt = torch.randn(1, N, D) * 0.02
    ids = torch.full((1, T), 5, dtype=torch.long)

    # ------------------------------------------------------- 2. shape and exact K
    print("\n[3] target shape / positive count")
    tgt = attn_topk_target(dec, vt, ids, None, N, KEEP)
    K = max(1, int(round(N * KEEP)))
    check("returns (B, N)", tuple(tgt.shape) == (1, N), f"got {tuple(tgt.shape)}")
    check("exactly K positives", int(tgt.sum()) == K, f"{int(tgt.sum())} vs K={K}")
    check("target is binary", set(tgt.unique().tolist()) <= {0.0, 1.0},
          f"values {sorted(set(tgt.unique().tolist()))[:4]}")

    # ------------------------------------------- 3. pruned tokens must be rejected
    print("\n[4] pruned-input guard (the failure that would silently gut 13(b))")
    try:
        attn_topk_target(dec, vt[:, :K, :], ids, None, N, KEEP)
        check("raises when given PRUNED tokens", False, "no exception")
    except ValueError as e:
        check("raises when given PRUNED tokens", "FULL grid" in str(e), str(e)[:60])

    # ------------------------------------------------- 4. the SDPA silent-empty trap
    print("\n[5] SDPA silent-empty guard")

    class _NoAttn:
        def __init__(self, val):
            self.val = val

        def __call__(self, **kw):
            return type("O", (), {"cross_attentions": self.val})()

    # () is the shape transformers 5.4.0 actually returns; the other two are defensive.
    for label, val in (("empty tuple (the real one)", ()),
                       ("None", None),
                       ("tuple of Nones", (None, None))):
        try:
            attn_topk_target(_NoAttn(val), vt, ids, None, N, KEEP)
            check(f"raises when cross_attentions is {label}", False, "NO EXCEPTION")
        except RuntimeError as e:
            check(f"raises when cross_attentions is {label}",
                  "cross_attentions" in str(e), str(e)[:44])

    # The control that makes the three above meaningful: a REAL decoder at its default
    # config must raise, and must succeed after cell 11's block runs. If the first half
    # passed, the guard is dead code protecting nothing; if the second half failed,
    # cell 11 would raise on every step of a real run.
    print("      control: real decoder, default config vs cell 11's config")
    dec_sdpa = VisionEncoderDecoderModel.from_pretrained(
        "naver-clova-ix/donut-base", low_cpu_mem_usage=True).decoder.eval()
    try:
        attn_topk_target(dec_sdpa, vt, ids, None, N, KEEP)
        check("REAL sdpa decoder raises (guard is load-bearing)", False,
              "no exception -- guard protects nothing on this build")
    except RuntimeError as e:
        check("REAL sdpa decoder raises (guard is load-bearing)",
              "cross_attentions" in str(e), str(e)[:44])
    exec(compile(apply_eager, "<cell11-eager>", "exec"), {"_teacher_dec": dec_sdpa})
    t_fixed = attn_topk_target(dec_sdpa, vt, ids, None, N, KEEP)
    check("same decoder succeeds after cell 11's block", int(t_fixed.sum()) == K,
          f"{int(t_fixed.sum())} positives")
    del dec_sdpa
    gc.collect()

    # --------------------------------------------------- 5. pad masking is not inert
    print("\n[6] pad masking actually changes the target")
    labels = torch.full((1, T), 7, dtype=torch.long)
    labels[:, T // 2:] = -100          # second half is pad
    tgt_masked = attn_topk_target(dec, vt, ids, labels, N, KEEP)
    same = torch.equal(tgt_masked, tgt)
    check("masked target differs from unmasked", not same,
          "identical -- mask is a no-op" if same else "differs, as it must")
    check("masked target still has exactly K positives", int(tgt_masked.sum()) == K,
          f"{int(tgt_masked.sum())}")

    # ------------------------------------------------ 6. it is not the ink target
    print("\n[7] attention target is not the ink target (D8: r = +0.083)")
    pv = torch.rand(1, 3, 320, 320)     # 10x10 grid at stride 32 -> 100 tokens
    ink = ns["patch_ink"](pv, 100)
    vt2 = torch.randn(1, 100, D) * 0.02
    a2 = attn_topk_target(dec, vt2, ids, None, 100, KEEP)
    i2 = torch.zeros_like(ink)
    i2.scatter_(1, ink.topk(50, dim=1).indices, 1.0)
    overlap = float((a2 * i2).sum() / 50.0)
    check("attention target != ink target", not torch.equal(a2, i2),
          f"top-K overlap {overlap:.2f}")

    # --------------------------------------- 7. forward() really exposes visual_tokens
    print("\n[8] forward() returns 'visual_tokens' (called, not grepped)")

    class _StubEnc(nn.Module):
        """Stands in for Swin so forward() runs in milliseconds. The return dict, the
        router call and the prune are all the real code."""

        def __init__(self, n, d):
            super().__init__()
            self.n, self.d = n, d
            self.p = nn.Parameter(torch.zeros(1))

        def parameters(self, recurse=True):
            return iter([self.p])

        def forward(self, pixel_values):
            b = pixel_values.shape[0]
            return BaseModelOutput(last_hidden_state=torch.randn(b, self.n, self.d) * 0.02)

    model = ns["AdaptiveDonutOCR"](keep_ratio=KEEP, merge_ratio=0.0, freeze_encoder=True)
    model.model.encoder = _StubEnc(N, D)
    model.eval()
    with torch.no_grad():
        out = model(pixel_values=torch.rand(1, 3, 64, 64),
                    decoder_input_ids=ids, labels=None)
    check("'visual_tokens' in forward() output", "visual_tokens" in out)
    if "visual_tokens" in out:
        vtk = out["visual_tokens"]
        check("visual_tokens is (B, N, D) PRE-prune",
              tuple(vtk.shape) == (1, N, D), f"got {tuple(vtk.shape)}")
        check("visual_tokens N matches scores N",
              vtk.shape[1] == out["scores"].shape[1],
              f"{vtk.shape[1]} vs {out['scores'].shape[1]}")
        check("visual_tokens is NOT the pruned set",
              vtk.shape[1] != out["compressed_tokens"],
              f"N={vtk.shape[1]}, kept={out['compressed_tokens']}")
        # End to end: the real forward output feeding the real helper.
        t_e2e = attn_topk_target(dec, out["visual_tokens"], ids, None,
                                 out["scores"].shape[1], KEEP)
        check("end-to-end forward -> attn_topk_target", int(t_e2e.sum()) == K,
              f"{int(t_e2e.sum())} positives")

    # ------------------------------------------------------------ 8. defaults / guards
    print("\n[9] config defaults and guards")
    c2, c11 = cell_src(nb, 2), cell_src(nb, 11)
    check("ATTN_TARGET defined in cell 2", "ATTN_TARGET" in c2)
    check("ATTN_TARGET defaults False (run 9 reproducible)",
          "ATTN_TARGET = False" in c2)
    check("cell 11 asserts SUPERVISE_SALIENCY when ATTN_TARGET",
          "assert SUPERVISE_SALIENCY" in c11)
    check("cell 11 asserts RESUME_CKPT when ATTN_TARGET",
          "ATTN_TARGET needs RESUME_CKPT" in c11)
    check("teacher snapshotted before the epoch loop",
          c11.index("_teacher_dec = copy.deepcopy") < c11.index("for epoch in range("))
    check("BCE call left untouched (autocast-safe form)",
          "F.binary_cross_entropy_with_logits(" in c11
          and "torch.logit(_sc.squeeze(-1).clamp(1e-6, 1 - 1e-6))" in c11)
    # Keyed to the CONDITION, not the prose. The first version of this check looked for the
    # string "degenerate saliency target" and went stale the moment the guard was tightened
    # from `0 < rate < 1` to the per-branch form -- the same mistake as the D5 guard that
    # kept firing after its bug was fixed. Execution coverage for both states of this guard
    # lives in verify_saliency_loss_cell.py case F; these two are structural only.
    check("ATTN branch asserts rate == K/N exactly",
          "abs(_rate - _want) < 1e-4" in c11)
    check("INK branch warns instead of asserting (no new fatal path in run 9's branch)",
          "WARNING: first batch ink target is degenerate" in c11
          and "assert 0.0 < _rate < 1.0" not in c11)

    # ---------------------------------------------------- 10. real weights, real page
    # Off by default: N=4800 on CPU takes minutes and the suite has to stay fast. But
    # everything above ran at N=300 on donut-base, and the two things most likely to break
    # at the real scale are the ones a small case cannot show -- the attention tensor's
    # actual size, and whether the run-5 teacher's attention is degenerate on a real page.
    if "--real" in sys.argv:
        real_weights_section(ns, nb, apply_eager, attn_topk_target)

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print(f"\n{'=' * 70}\n{len(CHECKS) - n_fail}/{len(CHECKS)} checks passed")
    if n_fail:
        print("FAILED:")
        for nm, ok, d in CHECKS:
            if not ok:
                print(f"  - {nm}  {d}")
        raise SystemExit(1)
    print("13(b) target path verified BY EXECUTION.")
    print("REMINDER: this proves the code runs and the guards fire. It says NOTHING about")
    print("whether the target helps -- D6 is the standing case of a proxy fitted harder")
    print("and accuracy falling. Acceptance is recall at keep=0.50/0.35 vs run 9.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
