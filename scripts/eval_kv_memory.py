#!/usr/bin/env python
"""Pending 8(c): the ONE efficiency claim this project can actually make.

D11 settled Pending 8 against latency: pruning 4800 -> 960 visual tokens (5x) buys 1.04x
wall-clock, 1.05x at best, because generation is decoder-bound (243-280 autoregressive steps,
encoder runs once regardless). Option (a) -- drop "efficiency", keep accuracy-vs-token-count --
was taken, which left the writeup with no efficiency claim at all.

Option (c) is still available and honest: pruning shrinks the **decoder cross-attention KV
cache**, and that reduction is real, exact, and proportional to the token count. This script
measures it. It is not a benchmark -- there is nothing noisy to average. Cross-attention K and
V are computed ONCE from the encoder output and cached for every subsequent decoder step, so
their size is a deterministic function of (layers, heads, head_dim, kept_tokens, dtype).

**Two independent measurements, and they must agree.** The whole point of this file is that a
"memory saving" is trivially easy to overstate:
  1. ANALYTIC -- 2 (K and V) x layers x heads x head_dim x tokens x bytes_per_element.
  2. OBSERVED -- walk the real `past_key_values` returned by a real generate() call and sum
     `.numel() * .element_size()` over the cross-attention entries only.
If these disagree, the analytic model is wrong about the architecture and its numbers are
fiction. Asserting them equal is what makes the reported figure evidence rather than algebra.

**What this deliberately does NOT claim.** Three things, stated before any output:
  - This is decoder cross-attention KV only. It is NOT total memory, NOT peak memory, and NOT
    encoder activations -- the frozen Swin still computes all 4800 tokens at every budget
    (that is Pending 7's correction), so pruning cannot reduce encoder cost at all.
  - A large *relative* reduction in a small absolute quantity would still be small, so the
    script prints the model's own parameter bytes alongside and picks its framing from the
    measured share rather than from prose written in advance. (As it turns out the share is
    19.5% at fp32, so the "small quantity" caution does NOT survive the measurement -- but
    that was the data's call to make, not the docstring's.)
  - fp32 on CPU. Every byte figure halves at fp16/bf16 and scales linearly with batch size.
    Reported, not hidden, because it is the main thing that moves these numbers.
  - Self-attention KV grows with generated length and is NOT reduced by pruning; it is
    reported separately so the two are never conflated.

**The merge rows (added 2026-09-18).** The table now also measures `merge_ratio > 0`, because
AGENTS.md had begun quoting "2.5x KV at M=1920 at no measured accuracy cost" from arithmetic
done by hand in a prose paragraph, while this file -- the artifact whose entire job is to stop
KV claims being prose -- ran every row at `merge_ratio=0.0`. Three things about them:
  - The bytes are the same cache and the same proportionality. Control (2) is what establishes
    that a token removed by MERGING frees exactly as many cache bytes as one removed by
    PRUNING, which is the premise of comparing the two at equal M at all.
  - The bytes are NOT evidence that merging is cheap. That evidence is run 13's, it is read
    off `run 13/ablation_selection.json` rather than typed in, and it uses the
    selection-held-fixed contrast rather than run 13's own Q6 pairs (which vary the selection
    AND the merging, so a Q6 delta is not the cost of the merger).
  - The headline is the FREE row, not the biggest number -- and both directions are asserted,
    so "free" is a finding rather than a label: m=0.20 must come back unresolved, and m=0.40
    must come back resolved and negative. If the second ever stops failing, the first has
    stopped meaning anything.
  - Merging also has NO encoder-side saving. It runs strictly after the full Swin.

    PYTHONPATH=. HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -u scripts/eval_kv_memory.py

Cost: one generate() per row on one image, ~13 s each; 9 rows, ~2 min total.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "kv_memory_local.json")

CKPT = os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")
BUDGETS = (1.00, 0.50, 0.35, 0.25, 0.20)

# 2026-09-18: the merge rows. Added because AGENTS.md had started quoting "2.5x KV at M=1920
# at no measured accuracy cost" off MY ARITHMETIC -- 4800/1920 done by hand in a prose
# paragraph -- while this file, the artifact that exists precisely so KV claims are measured,
# knew nothing about merging and ran every row at merge_ratio=0.0. A claim that lives only in
# prose is the thing this script was written to prevent.
#
# `BUDGETS` above is deliberately NOT touched: those five rows are in the published
# `kv_memory_local.json` and in WRITEUP.md's audited numbers, so they are appended to rather
# than retyped (the same convention PATCH G uses for cell 15's SELECTION_CONFIGS).
#
# (keep, merge). Chosen to be exactly the rows run 13 measured an accuracy cost for, so every
# byte figure below can be paired with a number from an artifact instead of a guess.
MERGE_BUDGETS = ((1.00, 0.20), (0.50, 0.20), (0.50, 0.40), (0.35, 0.20))

# The headline merge row must be the one that is FREE, not the one with the biggest number --
# the same rule FREE_KEEP follows below, and for the same reason. run 13 (selection held
# fixed, n=50 paired) found m=0.20 flat at every budget and m=0.40 costing
# -3.86 [-7.54, -0.35], so:
FREE_MERGE = (0.50, 0.20)        # M=1920, 2.5x vs 4800 -- the row that may be headlined
COSTLY_MERGE = (0.50, 0.40)      # M=1440, 3.33x -- the row that may NOT be, and the control
#                                  that proves the "free" label has teeth rather than being
#                                  a label this script applies to whatever it measured.
SELECT_MODE = "ink"          # weight-independent; irrelevant to KV size but keeps it reproducible
MAX_LEN = 512
TASK_PROMPT = "<s_doc>"

# Pre-registered: analytic and observed cross-attention KV bytes must agree to within this
# fraction. Not a "close enough" tolerance -- they should be EXACTLY equal, and the only
# reason this is not 0.0 is to survive an implementation that pads or stores a fused tensor.
AGREE_TOL = 0.01

print("=" * 78)
print("DECODER CROSS-ATTENTION KV MEMORY vs VISUAL TOKEN BUDGET (Pending 8c)")
print("=" * 78)
print("  Scope, stated first: cross-attention KV ONLY. Not total, not peak, not encoder.")
print("  The frozen Swin computes all 4800 tokens at every budget (Pending 7), so there is")
print("  NO encoder-side saving to report. Self-attention KV is unaffected by pruning and is")
print("  listed separately. Latency is already settled: 1.04x (D11), not reported here.")

from datasets import load_dataset            # noqa: E402
from transformers import DonutProcessor      # noqa: E402
import transformers                          # noqa: E402

from src.model import AdaptiveDonutOCR       # noqa: E402

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)

sd = torch.load(CKPT, map_location=device, weights_only=True)
missing, unexpected = model.load_state_dict(sd, strict=False)
if missing or unexpected:
    raise SystemExit(f"refusing to measure a partially-loaded model: "
                     f"missing={len(missing)} unexpected={len(unexpected)}")
model.eval()

dcfg = model.model.config.decoder
LAYERS = dcfg.decoder_layers
HEADS = dcfg.decoder_attention_heads
D_MODEL = dcfg.d_model
HEAD_DIM = D_MODEL // HEADS
param_bytes = sum(p.numel() * p.element_size() for p in model.parameters())
dtype_bytes = next(model.parameters()).element_size()

print(f"\n  decoder: {LAYERS} layers x {HEADS} heads x {HEAD_DIM} head_dim "
      f"(d_model {D_MODEL}), {dtype_bytes} bytes/element")
print(f"  model parameters: {param_bytes / 2**20:,.0f} MiB  <- the scale to read KV against")
print(f"  checkpoint: {os.path.relpath(CKPT, ROOT)}")


def analytic_cross_kv_bytes(tokens):
    """2 (K and V) x layers x heads x head_dim x tokens x bytes. Exact, not an estimate."""
    return 2 * LAYERS * HEADS * HEAD_DIM * tokens * dtype_bytes


def walk_cache(past):
    """Sum bytes in a past_key_values structure, split self vs cross.

    Returns (self_bytes, cross_bytes, note). transformers 5.x may hand back an EncoderDecoder
    Cache object rather than the legacy tuple-of-tuples, so both shapes are handled and the
    one actually seen is recorded in the JSON -- a silent change here would quietly turn the
    cross figure into a self figure, which is the error this split exists to prevent.
    """
    # Legacy: tuple of per-layer tuples (self_k, self_v, cross_k, cross_v)
    if isinstance(past, (tuple, list)):
        s = c = 0
        for layer in past:
            for i, t in enumerate(layer):
                if not torch.is_tensor(t):
                    continue
                b = t.numel() * t.element_size()
                if i < 2:
                    s += b
                else:
                    c += b
        return s, c, "legacy tuple-of-tuples"
    # transformers 5.x: EncoderDecoderCache with .self_attention_cache / .cross_attention_cache
    s = c = 0
    for attr, tgt in (("self_attention_cache", "s"), ("cross_attention_cache", "c")):
        sub = getattr(past, attr, None)
        if sub is None:
            continue
        tot = 0
        for name in ("key_cache", "value_cache", "layers"):
            seq = getattr(sub, name, None)
            if seq is None:
                continue
            for item in seq:
                for t in (item if isinstance(item, (tuple, list)) else [item]):
                    for tt in ([t] if torch.is_tensor(t) else
                               [getattr(t, a, None) for a in ("keys", "values")]):
                        if torch.is_tensor(tt):
                            tot += tt.numel() * tt.element_size()
        if tgt == "s":
            s = tot
        else:
            c = tot
    return s, c, f"{type(past).__name__} object"


ds = load_dataset("nielsr/funsd", split="test")
img = ds[0]["image"].convert("RGB")
pv = processor(img, return_tensors="pt").pixel_values.to(device)
prompt_ids = processor.tokenizer(
    TASK_PROMPT, add_special_tokens=False, return_tensors="pt").input_ids.to(device)

# The tensor whose KV we measure must be the tensor generate() actually decoded against --
# NOT a re-derivation of the pruning path. Re-implementing selection here would be a second
# copy of src/model.py's logic that could silently diverge from it, and then the "observed"
# figure would describe code that never runs in an eval. So: hook the decoder, capture the
# encoder_hidden_states it is handed on the first step of the real generate(), and measure
# that exact tensor. Control (4) below asserts its length equals generate()'s own reported
# compressed_tokens, which is what makes "the same tensor" a checked claim rather than a
# comment.
CAPTURED = {}


def _grab(module, args, kwargs, output):
    if "ehs" in CAPTURED:
        return
    ehs = kwargs.get("encoder_hidden_states")
    if ehs is None:
        for a in args:
            if torch.is_tensor(a) and a.dim() == 3 and a.shape[-1] == D_MODEL:
                ehs = a
                break
    if torch.is_tensor(ehs):
        CAPTURED["ehs"] = ehs.detach()


handle = model.model.decoder.register_forward_hook(_grab, with_kwargs=True)

ROWS = []
cache_kind = None
t0 = time.time()
# Prune-only rows first, then the merge rows. Order matters to two things below and both are
# now explicit rather than relying on it: `base`/`free`/`tight` select on (keep, merge)
# instead of on position, and the self-KV monotonicity control filters to prune-only rows.
GRID = [(k, 0.0) for k in BUDGETS] + [tuple(c) for c in MERGE_BUDGETS]
for keep, merge in GRID:
    CAPTURED.clear()
    with torch.no_grad():
        gen_ids, meta = model.generate(
            pv, decoder_input_ids=prompt_ids, keep_ratio=keep, merge_ratio=merge,
            max_length=MAX_LEN, select_mode=SELECT_MODE,
        )
    tokens = int(meta["compressed_tokens"])
    gen_len = int(gen_ids.shape[-1])
    if "ehs" not in CAPTURED:
        handle.remove()
        raise SystemExit("hook never fired: cannot identify the tensor generate() decoded "
                         "against, so no observed measurement is possible. Refusing to fall "
                         "back on a re-derived pruning path.")
    hidden = CAPTURED["ehs"]

    # Observed: ONE forward pass with use_cache on that captured tensor, to get a real cache
    # back and read its bytes. Cross-attention K/V are built once from encoder_hidden_states
    # and reused for every decoder step, so this single pass holds the same cross cache the
    # whole 243-280 step generation carried.
    with torch.no_grad():
        out = model.model.decoder(
            input_ids=gen_ids[:, :-1], encoder_hidden_states=hidden, use_cache=True)
    self_b, cross_b, kind = walk_cache(out.past_key_values)
    cache_kind = kind
    obs_tokens = hidden.shape[1]
    ana = analytic_cross_kv_bytes(obs_tokens)
    ROWS.append({
        "keep_ratio": keep, "merge_ratio": merge,
        "visual_tokens": tokens, "cache_tokens": int(obs_tokens),
        "gen_tokens": gen_len, "cross_kv_bytes_analytic": ana,
        "cross_kv_bytes_observed": cross_b, "self_kv_bytes_observed": self_b,
        "cache_kind": kind,
    })
    print(f"  keep={keep:.2f} m={merge:.2f}  tok {tokens:4d}  cross-KV analytic "
          f"{ana / 2**20:7.2f} MiB  observed {cross_b / 2**20:7.2f} MiB  "
          f"self-KV {self_b / 2**20:6.2f} MiB (gen {gen_len})", flush=True)

handle.remove()

print("\n" + "=" * 78)
print("THE TABLE -- cross-attention KV only")
print("=" * 78)


def row_at(keep, merge=0.0):
    """The one row at this (keep, merge). Explicit rather than positional: with merge rows in
    the table, `next(r for r in ROWS if r['keep_ratio'] == 1.00)` would silently return
    whichever of the two keep=1.00 rows came first. That is the same key-collision defect the
    cell-15 harness had to be fixed for, and it is silent in exactly the same way."""
    hits = [r for r in ROWS if r["keep_ratio"] == keep and r["merge_ratio"] == merge]
    if len(hits) != 1:
        raise SystemExit(f"row_at({keep}, {merge}) matched {len(hits)} rows, expected 1")
    return hits[0]


base = row_at(1.00, 0.0)
PRUNE_ROWS = [r for r in ROWS if r["merge_ratio"] == 0.0]
MERGE_ROWS = [r for r in ROWS if r["merge_ratio"] > 0.0]
print(f"  {'keep':>5} {'m':>5} {'tok':>5} {'cross-KV MiB':>13} {'vs keep=1.00':>13} "
      f"{'% of params':>12} {'self-KV MiB':>12}")
for r in ROWS:
    mib = r["cross_kv_bytes_observed"] / 2**20
    red = 100.0 * (1 - r["cross_kv_bytes_observed"] / base["cross_kv_bytes_observed"])
    is_base = r is base
    print(f"  {r['keep_ratio']:5.2f} {r['merge_ratio']:5.2f} {r['visual_tokens']:5d} "
          f"{mib:13.2f} "
          f"{('-' if is_base else f'-{red:.1f}%'):>13} "
          f"{100.0 * r['cross_kv_bytes_observed'] / param_bytes:11.2f}% "
          f"{r['self_kv_bytes_observed'] / 2**20:12.2f}")

# The headline budget must be one that is FREE, not the tightest one. keep=0.20 gives the
# biggest percentage but D12 measured it costing 13 pts of word recall -- quoting 80% without
# that is selling a memory win funded by an accuracy loss. keep=0.35 is where D12 found run 9
# at no detectable cost.
#
# The accuracy numbers are READ FROM D12's JSON, not typed in here. A hardcoded "-0.26 pts"
# is a claim about another file that silently rots the moment D12 is re-run; reading it means
# the pairing either holds against the current data or the script says it cannot find it.
FREE_KEEP = 0.35
D12_JSON = os.path.join(ROOT, "results", "why_pruning_helps_local.json")


def d12_row(keep):
    """(delta_pts, t, n) for run 9 at this budget, from D12's own output. None if absent."""
    try:
        with open(D12_JSON, encoding="utf-8") as fh:
            d12 = json.load(fh)
    except (OSError, ValueError):
        return None
    ck = [r["checkpoint"] for r in d12.get("rows", []) if "9" in str(r.get("checkpoint", ""))]
    if not ck:
        return None
    want = ck[0]
    for r in d12.get("curve_vs_unpruned", []):
        if r.get("checkpoint") == want and abs(r.get("keep_ratio", -1) - keep) < 1e-9:
            n = next((x.get("num_eval_samples") for x in d12["rows"]
                      if x.get("checkpoint") == want), None)
            return r.get("delta_pts"), r.get("t"), n
    return None


# The merge rows' accuracy cost comes from run 13, and for the same reason d12_row() exists:
# a hardcoded "-3.86 pts" is a claim about another file that rots silently the moment that
# file is re-run or re-filed.
#
# It deliberately does NOT read run 13's own `meta.q6_token_matched`, even though those entries
# already carry deltas and CIs. Q6's pairs vary TWO things -- how many tokens the router picks
# AND whether the remainder is merged (keep=0.50 m=0.20 vs keep=0.40 m=0.00) -- so a Q6 delta
# is not the accuracy cost of the merger, which is the quantity a KV-vs-merging table has to
# pair its bytes with. The contrast computed here holds selection fixed (same keep, same
# select_mode) and switches only the merger, which is the matched comparison for these rows.
RUN13_JSON = os.path.join(ROOT, "run 13", "ablation_selection.json")
BOOT = 20000
BOOT_SEED = 0


def run13_merge_cost(keep, merge, select_mode="router"):
    """(delta_pts, ci_lo, ci_hi, res_pts, n) for merging at this budget with SELECTION HELD
    FIXED, recomputed from run 13's per-image arrays. None if either row is absent.

    Note the key asymmetry that has bitten this project before: the per-image key is `recall`
    and it is a FRACTION, while the row-level key is `word_recall_pct` and is already points.
    """
    try:
        with open(RUN13_JSON, encoding="utf-8") as fh:
            d13 = json.load(fh)
    except (OSError, ValueError):
        return None

    def pick(m):
        for r in d13.get("rows", []):
            if (abs(r.get("keep_ratio", -1) - keep) < 1e-9
                    and r.get("select_mode") == select_mode
                    and abs(r.get("merge_ratio", 0.0) - m) < 1e-9
                    and r.get("tome_split", "checkerboard") == "checkerboard"):
                return r
        return None

    hi_row, lo_row = pick(merge), pick(0.0)
    if hi_row is None or lo_row is None:
        return None
    a = [p["recall"] for p in hi_row.get("per_image", [])]
    b = [p["recall"] for p in lo_row.get("per_image", [])]
    if not a or len(a) != len(b):
        return None
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(d)
    rng = np.random.default_rng(BOOT_SEED)
    bs = d[rng.integers(0, n, size=(BOOT, n))].mean(axis=1)
    lo, hi = (float(x) * 100.0 for x in np.percentile(bs, [2.5, 97.5]))
    return float(d.mean()) * 100.0, lo, hi, (hi - lo) / 2.0, n


def resolved(cost):
    """True iff the CI excludes zero. `cost` is a run13_merge_cost() tuple."""
    return cost is not None and (cost[1] > 0) == (cost[2] > 0)


print("\n" + "=" * 78)
print("CONTROLS")
print("=" * 78)
ok_all = True
# 2026-09-18: `ok_all` is a boolean AND, so it says "nothing failed" and nothing about how much
# ran. That is why every "17 of 17 controls" in AGENTS.md was counted by eye off the log once and
# then copied three times, and why it was wrong (the real figure was 25). A boolean cannot
# distinguish 38 passing controls from 1 passing control and 37 that were skipped by a `continue`
# -- and several controls here ARE conditional (the run-13 and D12 pairings return None when a row
# is absent, and most of the rest live in `for` loops over a grid whose length is a constant this
# script edits). So the script counts itself and writes the count into the JSON, where a reader
# can compare it against the log instead of trusting a number typed into prose.
n_controls = 0
n_failed = 0


def say(ok, title, detail):
    global ok_all, n_controls, n_failed
    ok_all &= bool(ok)
    n_controls += 1
    if not ok:
        n_failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {title}: {detail}")


# (1) The two independent measurements must agree. If they do not, the analytic model does not
# describe this architecture and every number above is algebra rather than measurement.
for r in ROWS:
    a, o = r["cross_kv_bytes_analytic"], r["cross_kv_bytes_observed"]
    rel = abs(a - o) / max(a, 1)
    say(rel <= AGREE_TOL,
        f"analytic == observed at keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
        f"{a / 2**20:.2f} vs {o / 2**20:.2f} MiB -> rel gap {rel:.4f} (tol {AGREE_TOL})")

# (2) The reduction must be PROPORTIONAL to the token count -- that is the entire mechanism.
# A saving that is not proportional means something else is being measured. This is also what
# carries the merge rows: it says a token removed by MERGING frees exactly as many cache bytes
# as a token removed by PRUNING, which is the premise of comparing them at equal M at all.
for r in ROWS:
    exp = r["cache_tokens"] / base["cache_tokens"]
    got = r["cross_kv_bytes_observed"] / base["cross_kv_bytes_observed"]
    say(abs(exp - got) <= AGREE_TOL,
        f"proportional to tokens at keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
        f"token ratio {exp:.4f} vs byte ratio {got:.4f}")

# (4) The hooked tensor must be the one generate() reported. Without this the "observed"
# column could be measuring some other tensor of the right rank and width, and the whole
# same-tensor-as-the-real-eval argument would be a comment rather than a fact.
for r in ROWS:
    say(r["cache_tokens"] == r["visual_tokens"],
        f"hooked tensor is generate()'s own at keep={r['keep_ratio']:.2f} "
        f"m={r['merge_ratio']:.2f}",
        f"cache seq_len {r['cache_tokens']} == meta['compressed_tokens'] {r['visual_tokens']}")

# (5) keep=1.00 must actually be 4800 tokens, and the budgets must land where the project
# says they do. If the grid changed, every MiB above is for a different architecture.
say(base["cache_tokens"] == 4800, "unpruned baseline is the documented 4800-token grid",
    f"got {base['cache_tokens']} (80x60 at stride 32)")

# ---------------------------------------------------------------- the merge rows
# (7) Token arithmetic, checked by EXECUTION rather than restated. M = K - min(round(K*m),
# K//2). "M=1920" is the number the 2.5x claim is built on, so it is derived from the grid
# here and compared against what generate() actually returned.
for r in MERGE_ROWS:
    K = max(1, round(4800 * r["keep_ratio"]))
    want = K - min(round(K * r["merge_ratio"]), K // 2)
    say(r["visual_tokens"] == want,
        f"token arithmetic at keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
        f"K={K} -> M={want} expected, generate() reported {r['visual_tokens']}")

# (8) NON-VACUITY, and the most important check in this block: the merger must actually have
# RUN. Every byte figure on a merge row is identical to its keep's prune-only row if
# `merge_ratio` was ignored -- and `merge_ratio` being silently ignored or silently inherited
# is this project's single most repeated defect (twelve callers once inherited merge_ratio=0.20
# from a constructor default, and nothing failed). Without this check the merge half of the
# table could be a verbatim copy of the prune half and every control above would still pass.
for r in MERGE_ROWS:
    twin = row_at(r["keep_ratio"], 0.0) if any(
        p["keep_ratio"] == r["keep_ratio"] for p in PRUNE_ROWS) else None
    if twin is None:
        say(False, f"merger ran at keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
            "no prune-only row at this keep to compare against -- check is vacuous, so it fails")
        continue
    say(r["visual_tokens"] < twin["visual_tokens"]
        and r["cross_kv_bytes_observed"] < twin["cross_kv_bytes_observed"],
        f"merger ran at keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
        f"{twin['visual_tokens']} tok / {twin['cross_kv_bytes_observed'] / 2**20:.2f} MiB "
        f"unmerged -> {r['visual_tokens']} tok / "
        f"{r['cross_kv_bytes_observed'] / 2**20:.2f} MiB merged")

# (9) The merge rows' accuracy pairing must resolve from run 13, exactly as (6) demands of D12.
# A silent None here would let the headline degrade to a hedge with nothing failing, which is
# how a memory number ends up quoted without its cost.
_free_m = run13_merge_cost(*FREE_MERGE)
_costly_m = run13_merge_cost(*COSTLY_MERGE)
say(_free_m is not None and _costly_m is not None,
    "run 13 accuracy pairing resolved from disk (not hardcoded)",
    (f"keep={FREE_MERGE[0]:.2f} m={FREE_MERGE[1]:.2f} -> {_free_m[0]:+.2f} "
     f"[{_free_m[1]:+.2f}, {_free_m[2]:+.2f}] n={_free_m[4]}; "
     f"m={COSTLY_MERGE[1]:.2f} -> {_costly_m[0]:+.2f} "
     f"[{_costly_m[1]:+.2f}, {_costly_m[2]:+.2f}]")
    if _free_m and _costly_m else
    f"missing: free={_free_m} costly={_costly_m} (is 'run 13/ablation_selection.json' present?)")

# (10) PAIRED non-vacuity for the "free" label. Saying the headline row is free is worth
# nothing unless the same test would have REJECTED a row that is not -- otherwise "free" is a
# word this script applies to whatever it happened to measure. So both directions are asserted
# against the same criterion: FREE_MERGE must be unresolved, COSTLY_MERGE must be resolved and
# negative. If the second ever stops failing its CI, the first stops meaning anything.
if _free_m is not None:
    say(not resolved(_free_m),
        f"the headline merge row keep={FREE_MERGE[0]:.2f} m={FREE_MERGE[1]:.2f} really is free",
        f"{_free_m[0]:+.2f} pts, 95% CI [{_free_m[1]:+.2f}, {_free_m[2]:+.2f}] includes 0 "
        f"(res {_free_m[3]:.2f}, n={_free_m[4]}) -- run 13, selection held fixed")
if _costly_m is not None:
    say(resolved(_costly_m) and _costly_m[0] < 0,
        "...and the criterion has teeth: the rejected row IS resolved and negative",
        f"keep={COSTLY_MERGE[0]:.2f} m={COSTLY_MERGE[1]:.2f} -> {_costly_m[0]:+.2f} pts, "
        f"95% CI [{_costly_m[1]:+.2f}, {_costly_m[2]:+.2f}] excludes 0. This is why the "
        f"3.33x figure at M=1440 is NOT the headline")

# (6) The accuracy pairing must actually resolve. Without this the D12 lookup could silently
# return None, the headline would quietly degrade to a hedge, and nothing would have failed --
# which is exactly how a memory claim ends up detached from its accuracy cost.
_f, _t = d12_row(FREE_KEEP), d12_row(BUDGETS[-1])
say(_f is not None and _t is not None,
    "D12 accuracy pairing resolved from disk (not hardcoded)",
    (f"keep={FREE_KEEP:.2f} -> {_f[0]:+.3f} pts t {_f[1]:+.2f} n={_f[2]}; "
     f"keep={BUDGETS[-1]:.2f} -> {_t[0]:+.3f} pts t {_t[1]:+.2f}")
    if _f and _t else f"missing: free={_f} tight={_t} (is {os.path.basename(D12_JSON)} present?)")
if _f is not None:
    say(abs(_f[1]) < 2.0, f"the headline budget keep={FREE_KEEP:.2f} really is free",
        f"|t| {abs(_f[1]):.2f} < 2.0, i.e. D12 found no detectable accuracy cost there")

# (3) Self-attention KV must NOT be driven by the budget. If it were, the self/cross split
# would be wrong and the cross figure contaminated -- this is the control that stops a
# self/cross mix-up from being reported as a pruning benefit.
#
# "range is smallish" would be a weak way to say this, and weaker than the data allows: self
# KV is 2 x layers x heads x head_dim x GENERATED length, so it should be *exactly*
# proportional to gen_tokens and only incidentally related to keep. Asserting the exact
# relationship is a real control; asserting a loose range is close to asserting nothing.
sb = [r["self_kv_bytes_observed"] for r in ROWS]
say(min(sb) > 0, "self-KV is non-zero (something was actually measured)",
    f"range {min(sb) / 2**20:.2f}-{max(sb) / 2**20:.2f} MiB")
for r in ROWS:
    exp = 2 * LAYERS * HEADS * HEAD_DIM * (r["gen_tokens"] - 1) * dtype_bytes
    rel = abs(exp - r["self_kv_bytes_observed"]) / max(exp, 1)
    say(rel <= AGREE_TOL, f"self-KV tracks GENERATED length, not budget, at "
        f"keep={r['keep_ratio']:.2f} m={r['merge_ratio']:.2f}",
        f"gen {r['gen_tokens'] - 1} tok predicts {exp / 2**20:.2f} MiB, observed "
        f"{r['self_kv_bytes_observed'] / 2**20:.2f} MiB -> rel gap {rel:.4f}")
# ...and the decisive half: self-KV must NOT be monotone in keep the way cross-KV is. On this
# image keep=0.25 generates MORE tokens than keep=0.35, so its self-KV is larger while its
# cross-KV is smaller -- the two quantities are demonstrably not the same thing.
#
# Restricted to the PRUNE-ONLY rows on purpose. `ROWS` is now ordered prune-then-merge, so its
# keep column is no longer monotone at all, and a non-monotonicity test over the full list
# would pass because of the row ORDER rather than because of the physics. That would be a
# control that still prints PASS after the thing it guards has stopped being true.
ranks_keep = [r["self_kv_bytes_observed"] for r in PRUNE_ROWS]
say(ranks_keep != sorted(ranks_keep, reverse=True),
    "self-KV is NOT monotone in keep (while cross-KV is)",
    "at least one lower budget has larger self-KV than a higher one -- "
    f"the budget is not what drives it (over the {len(PRUNE_ROWS)} prune-only rows, whose "
    "keep column IS descending, so the test is about the physics and not the row order)")

# The count, printed where a reader will see it next to the verdict rather than having to
# `grep -c` the log. A LOWER number than the last recorded run means controls stopped running,
# which `ok_all` alone would report as success.
print(f"\n  {n_controls - n_failed}/{n_controls} controls passed"
      + ("" if not n_failed else f" -- {n_failed} FAILED"))
print(f"  (grid: {len(PRUNE_ROWS)} prune-only + {len(MERGE_ROWS)} merge rows. If this count "
      f"dropped, a control was skipped, not satisfied.)")

print("\n" + "=" * 78)
print("THE CLAIM")
print("=" * 78)
tight = PRUNE_ROWS[-1]
red = 100.0 * (1 - tight["cross_kv_bytes_observed"] / base["cross_kv_bytes_observed"])
free = row_at(FREE_KEEP, 0.0)
d12_free = d12_row(FREE_KEEP)
d12_tight = d12_row(tight["keep_ratio"])
red_free = 100.0 * (1 - free["cross_kv_bytes_observed"] / base["cross_kv_bytes_observed"])
if not ok_all:
    print("  WITHHELD -- a control failed, so these bytes are not trustworthy.")
else:
    cost_free = (f"{d12_free[0]:+.2f} pts of word recall (t {d12_free[1]:+.2f}, n="
                 f"{d12_free[2]} paired -- D12)" if d12_free else
                 "an accuracy cost D12's JSON could not be read for -- do NOT quote the "
                 "percentage without re-deriving it")
    print(f"  HEADLINE, at the budget that costs nothing: keep={FREE_KEEP:.2f} cuts the "
          f"decoder cross-attention KV cache from "
          f"{base['cross_kv_bytes_observed'] / 2**20:.2f} MiB to "
          f"{free['cross_kv_bytes_observed'] / 2**20:.2f} MiB, a **{red_free:.1f}% "
          f"reduction**, for {cost_free}. That pairing is the claim; the percentage alone "
          f"is not.")
    cost_tight = (f"costs {abs(d12_tight[0]):.2f} pts (t {d12_tight[1]:+.2f}, D12)"
                  if d12_tight else "carries an accuracy cost that must be quoted with it")
    print(f"\n  The tightest budget goes further but is NOT free: keep="
          f"{tight['keep_ratio']:.2f} reaches {tight['cross_kv_bytes_observed'] / 2**20:.2f} "
          f"MiB ({red:.1f}%) and {cost_tight}. Quote it only with that cost attached.")
    print(f"  Both figures are exactly proportional to the token count and confirmed by two "
          f"independent measurements.")
    # The docstring warned that a large relative cut in a small absolute quantity is still
    # small. Whether the quantity IS small is a question for the data, not for prose written
    # in advance, so the framing is chosen from the measured share rather than asserted.
    saved = base["cross_kv_bytes_observed"] - free["cross_kv_bytes_observed"]
    share = 100.0 * base["cross_kv_bytes_observed"] / param_bytes
    print(f"\n  READ IT IN PROPORTION: at keep=1.00 the cross-KV cache is "
          f"{share:.2f}% of the model's own {param_bytes / 2**20:,.0f} MiB of parameters, "
          f"falling to {100.0 * free['cross_kv_bytes_observed'] / param_bytes:.2f}% at the "
          f"free budget. The absolute saving there is {saved / 2**20:.0f} MiB.")
    if share >= 10.0:
        print(f"  That share is NOT negligible -- the docstring's caution that this might be "
              f"'a large cut in a small quantity' does not survive the measurement. At fp32 "
              f"the unpruned cross-KV is a fifth of the weights, and the {saved / 2**20:.0f} "
              f"MiB freed is real working memory.")
    else:
        print(f"  That share is small, so the large percentage is a large cut in a small "
              f"quantity; both halves belong in any sentence using this number.")
    print(f"  BUT the honest qualifier is dtype and batch, not size: this is fp32 on CPU. At "
          f"fp16/bf16 every figure halves ({base['cross_kv_bytes_observed'] / 2**21:.0f} -> "
          f"{free['cross_kv_bytes_observed'] / 2**21:.0f} MiB at the free budget), while at "
          f"batch>1 it scales linearly with batch and the saving grows in absolute terms. "
          f"The PERCENTAGE is invariant to both.")
    print(f"  NOT a latency claim (D11: 1.04x). NOT an encoder saving (there is none). NOT "
          f"peak or total memory. Self-attention KV is unchanged by pruning.")

    # ------------------------------------------------------------ the merge claim
    # Reported separately from the pruning claim because it rests on a DIFFERENT artifact
    # (run 13, not D12) and a different contrast, and because the two compress by different
    # mechanisms. Merging them into one paragraph is how "2.5x at no cost" would end up
    # inheriting D12's evidence, which never measured a merged token.
    print("\n" + "-" * 78)
    print("  AND THE MERGE STAGE -- same cache, same proportionality, different evidence")
    print("-" * 78)
    fm = row_at(*FREE_MERGE)
    cm = row_at(*COSTLY_MERGE)
    fm_x = base["cross_kv_bytes_observed"] / fm["cross_kv_bytes_observed"]
    cm_x = base["cross_kv_bytes_observed"] / cm["cross_kv_bytes_observed"]
    if _free_m is None or _costly_m is None:
        print("  WITHHELD -- run 13's contrast could not be read, so these bytes have no "
              "accuracy cost attached and must not be quoted.")
    else:
        print(f"  HEADLINE: prune to keep={FREE_MERGE[0]:.2f} and merge "
              f"m={FREE_MERGE[1]:.2f} -> M={fm['visual_tokens']} tokens, cutting cross-KV "
              f"from {base['cross_kv_bytes_observed'] / 2**20:.2f} MiB to "
              f"{fm['cross_kv_bytes_observed'] / 2**20:.2f} MiB (**{fm_x:.2f}x**), for "
              f"{_free_m[0]:+.2f} pts of word recall, 95% CI "
              f"[{_free_m[1]:+.2f}, {_free_m[2]:+.2f}], n={_free_m[4]} paired (run 13, "
              f"selection held fixed). The CI includes 0: no measured cost.")
        print(f"\n  NOT the headline: m={COSTLY_MERGE[1]:.2f} reaches "
              f"M={cm['visual_tokens']} and {cm_x:.2f}x, but costs {_costly_m[0]:+.2f} pts "
              f"[{_costly_m[1]:+.2f}, {_costly_m[2]:+.2f}] -- resolved, and negative. "
              f"{cm_x:.2f}x is available only with that cost quoted beside it.")
        # The reason a merge row is interesting AT ALL is that it beats the prune-only row
        # needing the same M. Stating the equivalent keep makes the alternative explicit
        # instead of leaving the reader to compute it.
        eq_keep = fm["visual_tokens"] / 4800.0
        print(f"\n  WHY MERGE RATHER THAN JUST PRUNE HARDER: M={fm['visual_tokens']} by "
              f"pruning alone means keep={eq_keep:.2f}. The bytes are identical -- control "
              f"(2) says a merged token frees exactly what a pruned one does -- so the whole "
              f"question is which path costs less recall, and that is run 13's Q6, not this "
              f"file's measurement.")
        print(f"  Every scope limit above applies unchanged: cross-attention KV only, fp32, "
              f"no encoder saving, not a latency claim.")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({
        "meta": {
            "purpose": ("Pending 8c -- decoder cross-attention KV memory vs visual token "
                        "budget, for both compression stages (pruning, and pruning+merging)"),
            "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checkpoint": os.path.relpath(CKPT, ROOT),
            "device": str(device), "transformers": transformers.__version__,
            "torch": torch.__version__, "cache_kind": cache_kind,
            "decoder": {"layers": LAYERS, "heads": HEADS, "head_dim": HEAD_DIM,
                        "d_model": D_MODEL, "bytes_per_element": dtype_bytes},
            "param_bytes": param_bytes,
            "controls_passed": ok_all,
            # The COUNT beside the boolean, on purpose: `controls_passed: true` is equally true
            # of a run where 38 controls passed and one where 37 were skipped. AGENTS.md's
            # "17 of 17" was eyeballed off a log and stayed wrong for three copies because this
            # key did not exist.
            "controls_run": n_controls,
            "controls_failed": n_failed,
            "agree_tol": AGREE_TOL,
            "dtype_caveat": (
                "fp32 on CPU. All byte figures halve at fp16/bf16 and scale linearly with "
                "batch size; the PERCENTAGE reduction is invariant to both."
            ),
            "scope_limit": (
                "decoder cross-attention KV only; NOT total, NOT peak, NOT encoder "
                "activations (the frozen Swin computes all 4800 tokens at every budget). "
                "Self-attention KV is unaffected by pruning. Latency is settled separately "
                "at 1.04x by D11 and is not an efficiency claim. This applies identically to "
                "the merge rows: merging happens strictly AFTER the full encoder, so it also "
                "has no encoder-side saving, and the token reduction it buys is decoder "
                "cross-attention KV length and nothing else."
            ),
            "n_images": 1,
            "n_images_note": (
                "one image is sufficient and not a sample-size weakness: cross-attention KV "
                "size is a deterministic function of (layers, heads, head_dim, kept tokens, "
                "dtype) and does not vary with content. The analytic==observed control is "
                "what establishes that, rather than an average over images."
            ),
            # The merge rows' accuracy evidence goes in the artifact, not just the log, so the
            # bytes and their cost cannot be separated by whoever quotes them next.
            "merge_rows_note": (
                "rows with merge_ratio > 0 measure the SAME decoder cross-attention cache; "
                "control (2) establishes that a token removed by merging frees exactly as "
                "many cache bytes as one removed by pruning, which is what makes equal-M "
                "comparison meaningful. The bytes here are NOT evidence that merging is "
                "cheap in accuracy -- that comes from run 13 and is recorded in "
                "merge_accuracy_cost below."
            ),
            "merge_accuracy_cost": {
                "source": "run 13/ablation_selection.json",
                "contrast": (
                    "selection held fixed: same keep_ratio, same select_mode='router', same "
                    "tome_split='checkerboard', merge on vs off. Deliberately NOT run 13's "
                    "meta.q6_token_matched, whose pairs vary both the selection and the "
                    "merging and so do not isolate the merger."
                ),
                "bootstrap": {"resamples": BOOT, "seed": BOOT_SEED, "unit": "document"},
                "free": (
                    None if _free_m is None else
                    {"keep_ratio": FREE_MERGE[0], "merge_ratio": FREE_MERGE[1],
                     "delta_pts": _free_m[0], "ci95_lo": _free_m[1], "ci95_hi": _free_m[2],
                     "resolution_pts": _free_m[3], "n_paired": _free_m[4],
                     "resolved": resolved(_free_m)}
                ),
                "costly": (
                    None if _costly_m is None else
                    {"keep_ratio": COSTLY_MERGE[0], "merge_ratio": COSTLY_MERGE[1],
                     "delta_pts": _costly_m[0], "ci95_lo": _costly_m[1],
                     "ci95_hi": _costly_m[2], "resolution_pts": _costly_m[3],
                     "n_paired": _costly_m[4], "resolved": resolved(_costly_m)}
                ),
            },
        },
        "rows": ROWS,
    }, f, indent=1)
print(f"\nwrote {os.path.relpath(OUT, ROOT)}   ({time.time() - t0:.0f} s)")
