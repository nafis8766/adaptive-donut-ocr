"""Diagnostic D3 (2026-08-31): re-derive runs 7/8's own verdicts from their JSON.

Booked because the Phase 2d harness printed five verdicts per run and only the ones
agreeing with the existing narrative reached AGENTS.md. In particular Q3 -- the test
built specifically so D2 *could* fail -- printed "INCONCLUSIVE" on run 7 and
"D2 FALSIFIED" on run 8, and neither was transcribed, while D2's conclusion stayed
enshrined as the acceptance gate in Conventions, Gotchas and Pending 1b.

So this script recomputes the contested numbers from the artifacts rather than
quoting the log, and states its falsifiers in advance:

  Q3  Which statistic family predicts per-image recall?
      D2 claims WORST-CASE (min/p10 line coverage) beats AGGREGATE (retained ink,
      mean coverage). FALSIFIER: aggregate rho >= worst-case rho by >0.05, in which
      case D2's 4-row ordering was luck and the min-coverage gate must be withdrawn.
      Computed two ways because the pooling choice is itself a judgement call:
      over ALL pruned rows (what the notebook did) and over the four equal-budget
      keep=0.5 modes only (a fairer contrast -- equal K, ranking signal the only
      difference, which is the comparison D2 actually made).

  COV Is worst-case coverage even sufficient? FALSIFIER: two rows with essentially
      equal min line coverage whose recall differs by more than a few points. One
      such pair retires the statistic as a gate regardless of any correlation.

  EFF Does pruning buy wall-clock? The deliverable is an *efficiency* curve, so
      cost has to be measured. FALSIFIER for the efficiency framing: latency tracks
      generated-token count rather than visual-token count, i.e. corr(gen, ms) >
      corr(visual, ms), and the measured saving is a small fraction of the token
      saving.

  ADA Is "the router beats the ink oracle" a selection-quality result or a
      train/eval distribution-match result? Run 8 trained at keep_ratio=0.50, so
      exactly one cell of its table has eval config == train config. FALSIFIER for
      the co-adaptation reading: some OFF-distribution rule beats the trained rule
      at the trained ratio, or the router's curve does not peak at that ratio.

Pure stdlib + numpy on the two result files. No model, no GPU, runs in under a
second, so it can be re-run after any future sweep.

Usage:
    PYTHONIOENCODING=utf-8 python scripts/diagnose_selection_statistics.py
"""
import argparse
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

p = argparse.ArgumentParser()
# Pending 12 (2026-09-06): results_2/ -> "run 7/", results_3/ -> "run 8/". Runs 9 and 10
# added because this defaulted to the two oldest pruning runs in the project.
p.add_argument("--runs", nargs="*", default=[
    "7:run 7/ablation_selection.json",
    "8:run 8/ablation_selection.json",
    "9:run 9/ablation_selection.json",
    "10:run 10/ablation_selection.json",
], help="label:path pairs")
p.add_argument("--trained-keep", type=float, default=0.50,
               help="keep_ratio the router was trained at (generator: TRAIN_KEEP_RATIO)")
args = p.parse_args()

EQUAL_BUDGET_MODES = ("router", "negated", "random", "ink")
AGG = (("retained_ink", "aggregate"), ("mean_line_cov", "aggregate"))
WORST = (("p10_line_cov", "worst-case"), ("min_line_cov", "worst-case"))

notes = []


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def load(spec):
    label, path = spec.split(":", 1)
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return label, path, json.load(f)


RUNS = [load(s) for s in args.runs]


# ------------------------------------------------------------------ Q3
def q3(rows, pool_label, keep_filter=None):
    sel = [r for r in rows if r["keep_ratio"] < 1.0
           and (keep_filter is None or (r["keep_ratio"] == keep_filter
                                        and r["select_mode"] in EQUAL_BUDGET_MODES))]
    pooled = [(pi, r["select_mode"]) for r in sel for pi in r.get("per_image", [])
              if pi.get("min_line_cov") is not None]
    if len(pooled) < 12:
        print(f"  {pool_label}: too few per-image records ({len(pooled)})")
        return None
    rec = [pi["recall"] for pi, _ in pooled]
    print(f"  {pool_label} (n={len(pooled)})")
    rhos = {}
    for key, fam in AGG + WORST:
        rhos[key] = spearman([pi[key] for pi, _ in pooled], rec)
        print(f"    {key:16s} {fam:11s} rho vs recall = {rhos[key]:+.3f}")
    best_agg = max(rhos[k] for k, _ in AGG)
    best_wst = max(rhos[k] for k, _ in WORST)
    if best_wst > best_agg + 0.05:
        v = "D2 SUPPORTED (worst-case predicts better)"
    elif best_agg > best_wst + 0.05:
        v = "D2 FALSIFIED (aggregate predicts better)"
    else:
        v = "INCONCLUSIVE (families tie; D2 unconfirmed, not refuted)"
    print(f"    => {v}   [best aggregate {best_agg:+.3f} vs best worst-case {best_wst:+.3f}]")
    return v


# ------------------------------------------------------------------ COV
def coverage_counterexample(rows, tol=0.02):
    """Row pairs at the same budget with ~equal min coverage but different recall."""
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["keep_ratio"] != b["keep_ratio"]:
                continue
            ca, cb = a.get("mean_min_line_cov"), b.get("mean_min_line_cov")
            if ca is None or cb is None or abs(ca - cb) > tol:
                continue
            gap = abs(a["word_recall_pct"] - b["word_recall_pct"])
            out.append((gap, a, b, ca, cb))
    return sorted(out, key=lambda t: -t[0])


# ------------------------------------------------------------------ EFF
def efficiency(rows):
    vt = [r["visual_tokens"] for r in rows]
    gt = [r["mean_gen_tokens"] for r in rows]
    ms = [r["avg_latency_ms"] for r in rows]
    r_vis = float(np.corrcoef(vt, ms)[0, 1])
    r_gen = float(np.corrcoef(gt, ms)[0, 1])
    print(f"    corr(visual_tokens, latency) = {r_vis:+.3f}")
    print(f"    corr(gen_tokens,    latency) = {r_gen:+.3f}   <- what actually sets the clock")
    ctrl = next(r for r in rows if r["keep_ratio"] == 1.0)
    print(f"    {'row':26s} {'tokens':>7s} {'genTok':>7s} {'ms':>7s} {'d(tok)':>8s} {'d(ms)':>8s}")
    ratios = []
    for r in rows:
        if r["select_mode"] != "router":
            continue
        dtok = 100.0 * (r["visual_tokens"] - ctrl["visual_tokens"]) / ctrl["visual_tokens"]
        dms = 100.0 * (r["avg_latency_ms"] - ctrl["avg_latency_ms"]) / ctrl["avg_latency_ms"]
        print(f"    {r['config'][:26]:26s} {r['visual_tokens']:7d} {r['mean_gen_tokens']:7.0f} "
              f"{r['avg_latency_ms']:7.0f} {dtok:+7.1f}% {dms:+7.1f}%")
        if dtok < 0:
            ratios.append(dms / dtok)
    if ratios:
        print(f"    latency saved per token saved: {np.mean(ratios):.2f}x "
              f"(1.00 would mean pruning is a proportional speedup)")
    return r_vis, r_gen, (np.mean(ratios) if ratios else float("nan"))


# ------------------------------------------------------------------ ADA
def coadaptation(rows, trained_keep):
    at = [r for r in rows if r["keep_ratio"] == trained_keep]
    if not at:
        print(f"    no rows at trained keep_ratio={trained_keep}")
        return None
    print(f"    all selection rules at the TRAINED ratio keep={trained_keep} "
          f"(only 'router' is the rule training used):")
    print(f"    {'mode':20s} {'recall':>7s} {'ink':>6s} {'minCov':>7s}  {'on-distribution?':>17s}")
    for r in sorted(at, key=lambda x: -x["word_recall_pct"]):
        tag = "TRAINED RULE" if r["select_mode"] == "router" else "off-distribution"
        print(f"    {r['select_mode']:20s} {r['word_recall_pct']:7.2f} "
              f"{(r['retained_ink'] or 0):6.3f} {(r['mean_min_line_cov'] or 0):7.3f}  {tag:>17s}")
    trained = next((r for r in at if r["select_mode"] == "router"), None)
    others = [r for r in at if r["select_mode"] != "router"]
    dominated = [r for r in others
                 if (r["retained_ink"] or 0) > (trained["retained_ink"] or 0)
                 and (r["mean_min_line_cov"] or 0) > (trained["mean_min_line_cov"] or 0)
                 and r["word_recall_pct"] < trained["word_recall_pct"]]
    beat = [r for r in others if r["word_recall_pct"] > trained["word_recall_pct"]]
    curve = {r["keep_ratio"]: r["word_recall_pct"]
             for r in rows if r["select_mode"] == "router"}
    peak = max(curve, key=curve.get)
    print(f"    router curve by keep_ratio: "
          + "  ".join(f"{k:.2f}->{v:.2f}" for k, v in sorted(curve.items())))
    print(f"    peak at keep={peak:.2f}; trained at keep={trained_keep:.2f} "
          f"-> {'MATCH' if peak == trained_keep else 'NO MATCH'}")
    for r in dominated:
        print(f"    '{r['select_mode']}' has MORE ink AND better worst-case coverage "
              f"than the trained rule and still loses by "
              f"{trained['word_recall_pct'] - r['word_recall_pct']:.2f} pts")
    if not beat and peak == trained_keep:
        return ("CO-ADAPTATION: no off-distribution rule beats the trained rule at its "
                "own ratio, and the curve peaks there. 'Beats the oracle' is not a "
                "selection-quality claim.")
    return ("co-adaptation reading NOT clean: "
            + (f"{[r['select_mode'] for r in beat]} beat the trained rule; " if beat else "")
            + (f"curve peaks at {peak:.2f} not {trained_keep:.2f}" if peak != trained_keep else ""))


for label, path, d in RUNS:
    rows = d["rows"]
    meta = d.get("meta", {})
    print("=" * 78)
    print(f"RUN {label}  ({path})")
    print(f"  n={meta.get('num_eval_samples')}  control_drift={meta.get('control_drift_pts')}  "
          f"checkpoint={meta.get('checkpoint')!r}")
    if meta.get("checkpoint") is None:
        notes.append(f"run {label}: meta.checkpoint is None -- the file cannot say which "
                     f"weights produced it")
    print("-" * 78)
    print("Q3. which statistic family predicts per-image recall?")
    v_all = q3(rows, "all pruned rows (notebook's own pooling)")
    v_eq = q3(rows, f"equal-budget keep={args.trained_keep} x {EQUAL_BUDGET_MODES}",
              keep_filter=args.trained_keep)
    notes.append(f"run {label} Q3: {v_all} [all pruned]; {v_eq} [equal-budget]")

    print("\nCOV. is worst-case coverage sufficient? (equal coverage, unequal recall)")
    ce = coverage_counterexample(rows)
    if ce:
        gap, a, b, ca, cb = ce[0]
        print(f"    '{a['select_mode']}' minCov {ca:.3f} -> recall {a['word_recall_pct']:.2f}")
        print(f"    '{b['select_mode']}' minCov {cb:.3f} -> recall {b['word_recall_pct']:.2f}")
        print(f"    => same worst-case coverage, {gap:.2f} pts of recall apart "
              f"at keep={a['keep_ratio']}")
        notes.append(f"run {label} COV: {a['select_mode']} vs {b['select_mode']} at equal "
                     f"minCov (~{ca:.3f}) differ by {gap:.2f} pts recall")
    else:
        print("    no equal-coverage pair found at this tolerance")

    print("\nEFF. does pruning buy wall-clock?")
    r_vis, r_gen, ratio = efficiency(rows)
    notes.append(f"run {label} EFF: corr(visual,ms)={r_vis:+.3f} vs corr(gen,ms)={r_gen:+.3f}; "
                 f"{ratio:.2f}x latency-per-token saved")

    print("\nADA. selection quality, or train/eval distribution match?")
    v_ada = coadaptation(rows, args.trained_keep)
    if v_ada:
        print(f"    => {v_ada}")
        notes.append(f"run {label} ADA: {v_ada}")
    print()

print("=" * 78)
print("SUMMARY -- copy into AGENTS.md")
print("=" * 78)
for n in notes:
    print(f"  - {n}")
print()
print("  Architectural note: pruning happens AFTER the frozen Swin encoder, so the")
print("  4800 tokens are computed regardless of keep_ratio. The only saving is decoder")
print("  cross-attention KV length -- there is no encoder-side saving to read off the")
print("  token column, contrary to the note the Q5 verdict prints. A real efficiency")
print("  curve needs pruning at or before the encoder.")
