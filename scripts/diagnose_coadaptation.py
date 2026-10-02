"""D15 -- Is the router's advantage over the ink oracle SELECTION QUALITY or DECODER CO-ADAPTATION?

Re-derives every number from cached artifacts (runs 8/9/10/11 `ablation_selection.json`).
No GPU, no generation, no model load.

------------------------------------------------------------------------------
WHY THIS EXISTS
------------------------------------------------------------------------------
Claim 2 in AGENTS.md says "the router's selection value is real and large", and
earns it against a RANDOM mask (+17.7 to +34.0 pts). Against the `ink` oracle --
a free, learning-free patch-contrast heuristic -- AGENTS.md says only "do not
cite it" (D3: co-adaptation; D6: the margin moves +-5 pts on a loss-config
change alone).

That instruction is correct but it is not a measurement. This script is the
measurement. The confound has a specific, testable signature, and the artifacts
on disk are already sufficient to look for it.

------------------------------------------------------------------------------
THE PREMISE THAT MAKES THIS POSSIBLE (and which is CONTROL 1)
------------------------------------------------------------------------------
`select_mode='ink'` ranks tokens by `patch_ink`, which is a pure function of
pixels. It does not read the router, the scorer, or any weight. So the `ink`
row's TOKEN SET is byte-identical across every checkpoint that ever ran the
sweep -- AGENTS.md's "the ink/random rows are router-independent at eval"
gotcha says so, and names `retained_ink` equal to 3 dp across runs as the way
to corroborate it.

Therefore: variation in the `ink` row's RECALL across checkpoints is
attributable to the DECODER and to nothing else. Selection is held literally
constant. That is an unusually clean lever and it is free.

------------------------------------------------------------------------------
HYPOTHESES, WITH FALSIFIERS STATED BEFORE THE NUMBERS (Conventions)
------------------------------------------------------------------------------
H_SELECT (the claim under test):
    The router's margin over ink reflects BETTER SELECTION.
    Predicts: a router that retains MORE of the page's ink should score better,
    so margin should rise with the router's `retained_ink`, i.e. corr >= 0.
    Predicts: the margin should be driven by the ROUTER side of the subtraction.

H_COADAPT (the alternative):
    The margin reflects how far the decoder has SPECIALIZED to the router's
    idiosyncratic token distribution.
    Predicts: the more idiosyncratic the router (LOWER retained_ink, i.e.
    further from ink's selection), the LARGER the margin -- corr < 0.
    Predicts: the margin is driven by the INK side degrading, not the router
    side improving, because it is the ink row that is out-of-distribution for a
    router-trained decoder.

FALSIFIER for H_COADAPT, fixed here in advance:
    (a) pooled corr(router retained_ink, margin) >= 0, OR
    (b) the permutation test does not reject at p < 0.05, OR
    (c) the decomposition shows |corr with ROUTER recall| > |corr with INK
        recall| -- i.e. the router side, not the ink side, carries the effect.
    Any one of those and H_COADAPT is not supported by the observational data,
    and this script says so.

NOTE ON WHAT THIS CAN AND CANNOT DO: this is OBSERVATIONAL. n = 4 checkpoints
x 3 budgets = 12 cells, and the four checkpoints are NOT independent -- all are
fine-tuned from run 5. A correlation here is a signature, not a proof. The
causal test is a decoder trained under ink selection (run 18); this script
exists to say whether that GPU booking is justified, which is exactly the role
AGENTS.md's "diagnostics before GPU bookings" convention assigns it.
"""
import json
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = ["run 8", "run 9", "run 10", "run 11"]
BUDGETS = [0.75, 0.50, 0.35]
SEED = 20260925
N_PERM = 20000

PASS = 0
FAIL = 0
CONCERNS = []


def check(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s%s" % (label, (" -- " + detail) if detail else ""))
    else:
        FAIL += 1
        print("  [FAIL] %s%s" % (label, (" -- " + detail) if detail else ""))
        CONCERNS.append(label)


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0] * len(v)
    for pos, i in enumerate(order):
        r[i] = pos
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def trimmed_mean(d, g=0.10):
    """T1's pinned location statistic: 10% trimmed mean, difference-then-trim."""
    n = len(d)
    k = int(math.floor(g * n))
    s = sorted(d)
    core = s[k:n - k]
    return sum(core) / len(core)


def load():
    out = {}
    for run in RUNS:
        p = os.path.join(REPO, run, "ablation_selection.json")
        if not os.path.exists(p):
            raise SystemExit("MISSING ARTIFACT: %s" % p)
        d = json.load(open(p, encoding="utf-8"))
        out[run] = {(round(r["keep_ratio"], 2), r["select_mode"]): r for r in d["rows"]}
    return out


def main():
    print("=" * 78)
    print("D15 -- CO-ADAPTATION vs SELECTION QUALITY")
    print("=" * 78)
    D = load()

    # ------------------------------------------------------------------
    print("\n[1] CONTROL: is `ink` selection really checkpoint-independent?")
    print("    (the premise the whole diagnostic rests on)")
    for k in BUDGETS:
        vals = [D[r][(k, "ink")]["retained_ink"] for r in RUNS if (k, "ink") in D[r]]
        spread = max(vals) - min(vals)
        check(spread < 5e-4,
              "keep=%.2f ink retained_ink identical across %d checkpoints" % (k, len(vals)),
              "values=%s spread=%.2e" % ([round(v, 4) for v in vals], spread))

    print("\n    CONTROL (non-vacuity): the ROUTER's retained_ink must actually vary,")
    print("    otherwise there is no variation to correlate and a null is meaningless.")
    for k in BUDGETS:
        vals = [D[r][(k, "router")]["retained_ink"] for r in RUNS if (k, "router") in D[r]]
        check(max(vals) - min(vals) > 0.02,
              "keep=%.2f router retained_ink varies across checkpoints" % k,
              "range=[%.3f, %.3f] spread=%.3f" % (min(vals), max(vals), max(vals) - min(vals)))

    # ------------------------------------------------------------------
    print("\n[2] THE HEADLINE NUMBER: how big is the decoder-only effect?")
    print("    `ink` selection is byte-identical across checkpoints (control 1),")
    print("    so the SPREAD in ink-row recall is pure decoder specialization.")
    print()
    print("    %-8s %12s %12s %12s" % ("keep", "ink recall range", "spread(pts)", "mean |margin|"))
    coadapt_spreads = {}
    margin_means = {}
    for k in BUDGETS:
        inks = [D[r][(k, "ink")]["word_recall_pct"] for r in RUNS]
        margins = []
        for r in RUNS:
            ro, ik = D[r][(k, "router")], D[r][(k, "ink")]
            margins.append(trimmed_mean(
                [(a["recall"] - b["recall"]) * 100.0
                 for a, b in zip(ro["per_image"], ik["per_image"])]))
        sp = max(inks) - min(inks)
        coadapt_spreads[k] = sp
        margin_means[k] = sum(margins) / len(margins)
        print("    %-8.2f %12s %12.2f %12.2f" % (
            k, "%.2f-%.2f" % (min(inks), max(inks)), sp, margin_means[k]))

    worst_k = max(coadapt_spreads, key=lambda kk: coadapt_spreads[kk])
    ratio = coadapt_spreads[worst_k] / abs(margin_means[worst_k]) if margin_means[worst_k] else float("inf")
    print()
    print("    >> At keep=%.2f the SAME token set is read %.2f pts differently by" % (
        worst_k, coadapt_spreads[worst_k]))
    print("       different decoders, while the router's mean claimed advantage there")
    print("       is %.2f pts. The confound is %.1fx the effect." % (margin_means[worst_k], ratio))
    check(coadapt_spreads[worst_k] > abs(margin_means[worst_k]),
          "decoder-only spread exceeds the router's mean margin at keep=%.2f" % worst_k,
          "%.2f pts vs %.2f pts" % (coadapt_spreads[worst_k], abs(margin_means[worst_k])))

    # ------------------------------------------------------------------
    print("\n[3] THE SIGNATURE: does the margin grow as the router drifts FROM ink?")
    print("    H_SELECT predicts corr >= 0 (more ink kept -> better).")
    print("    H_COADAPT predicts corr <  0 (more idiosyncratic -> bigger margin).")
    print()
    cells = []
    for k in BUDGETS:
        for r in RUNS:
            ro, ik = D[r][(k, "router")], D[r][(k, "ink")]
            m = trimmed_mean([(a["recall"] - b["recall"]) * 100.0
                              for a, b in zip(ro["per_image"], ik["per_image"])])
            cells.append(dict(run=r, keep=k, rink=ro["retained_ink"], margin=m,
                              rrec=ro["word_recall_pct"], irec=ik["word_recall_pct"]))

    print("    %-8s %-6s %14s %10s %11s %9s" % (
        "run", "keep", "router ink_ret", "margin", "router rec", "ink rec"))
    for c in sorted(cells, key=lambda c: c["rink"]):
        print("    %-8s %-6.2f %14.3f %+10.2f %11.2f %9.2f" % (
            c["run"], c["keep"], c["rink"], c["margin"], c["rrec"], c["irec"]))

    X = [c["rink"] for c in cells]
    Y = [c["margin"] for c in cells]
    r_pool = pearson(X, Y)
    rho_pool = spearman(X, Y)
    print()
    print("    POOLED n=%d:  Pearson r = %+.3f   Spearman rho = %+.3f" % (len(X), r_pool, rho_pool))
    check(r_pool < 0, "pooled correlation is NEGATIVE (H_SELECT predicts >= 0)",
          "r=%+.3f" % r_pool)

    print("\n    WITHIN-BUDGET (controls for the budget confound; n=4 each):")
    within = {}
    for k in BUDGETS:
        sub = [c for c in cells if c["keep"] == k]
        within[k] = pearson([c["rink"] for c in sub], [c["margin"] for c in sub])
        print("      keep=%.2f  r = %+.3f   (router ink_ret spread %.3f)" % (
            k, within[k], max(c["rink"] for c in sub) - min(c["rink"] for c in sub)))
    neg = sum(1 for k in BUDGETS if within[k] < 0)
    check(neg >= 2, "correlation stays negative within budget in >=2 of 3 budgets",
          "%d of 3 negative" % neg)

    # ------------------------------------------------------------------
    print("\n[4] PERMUTATION TEST (the n=12 correlation could be luck)")
    rng = random.Random(SEED)
    obs = abs(r_pool)
    hits = 0
    for _ in range(N_PERM):
        sh = Y[:]
        rng.shuffle(sh)
        rp = pearson(X, sh)
        if not math.isnan(rp) and abs(rp) >= obs:
            hits += 1
    p_two = (hits + 1) / (N_PERM + 1)
    print("    |r| = %.3f,  %d/%d permutations at least as extreme,  p = %.4f (two-sided)" % (
        obs, hits, N_PERM, p_two))
    check(p_two < 0.05, "permutation test rejects the null at p<0.05", "p=%.4f" % p_two)

    # ------------------------------------------------------------------
    print("\n[5] DECOMPOSITION -- the discriminating test between the two hypotheses.")
    print("    Which SIDE of (router - ink) carries the correlation?")
    print("    H_SELECT  => the ROUTER side (the router genuinely improves).")
    print("    H_COADAPT => the INK side (a fixed selection gets read worse).")
    print()
    r_router = pearson(X, [c["rrec"] for c in cells])
    r_ink = pearson(X, [c["irec"] for c in cells])
    print("    corr(router retained_ink, ROUTER recall) = %+.3f" % r_router)
    print("    corr(router retained_ink, INK    recall) = %+.3f   <- selection CONSTANT" % r_ink)
    print()
    for k in BUDGETS:
        sub = [c for c in cells if c["keep"] == k]
        xs = [c["rink"] for c in sub]
        print("      keep=%.2f   router-side %+.3f   ink-side %+.3f" % (
            k, pearson(xs, [c["rrec"] for c in sub]), pearson(xs, [c["irec"] for c in sub])))
    check(abs(r_ink) > abs(r_router),
          "the INK side carries the correlation, not the router side",
          "|%.3f| > |%.3f|" % (r_ink, r_router))

    # ------------------------------------------------------------------
    print("\n[6] PLACEBO -- a quantity that should NOT predict the margin.")
    print("    `random`'s retained_ink is ~0.50 by construction and carries no")
    print("    information about the router, so it must not correlate.")
    have_rand = all((k, "random") in D[r] for k in BUDGETS for r in RUNS)
    if have_rand:
        P = [D[c["run"]][(c["keep"], "random")]["retained_ink"] for c in cells]
        r_plac = pearson(P, Y)
        print("    corr(RANDOM retained_ink, margin) = %+.3f   (vs the real %+.3f)" % (r_plac, r_pool))
        check(abs(r_plac) < abs(r_pool),
              "placebo correlates more weakly than the real predictor",
              "|%.3f| < |%.3f|" % (r_plac, r_pool))
    else:
        print("    SKIPPED: not every (run, budget) has a `random` row.")
        CONCERNS.append("placebo skipped -- missing random rows")

    # ------------------------------------------------------------------
    print("\n[7] NATURAL CONTROL -- run 11 never trained under pruning.")
    print("    TRAIN_KEEP_RATIO=1.00, so its decoder was never exposed to ANY")
    print("    pruned distribution and has the least opportunity to co-adapt.")
    print("    H_COADAPT predicts its margins sit at the SMALL end.")
    print()
    for k in BUDGETS:
        sub = sorted([c for c in cells if c["keep"] == k], key=lambda c: abs(c["margin"]))
        pos = [c["run"] for c in sub].index("run 11") + 1
        print("      keep=%.2f  run 11 margin %+6.2f  -> rank %d of %d by |margin|" % (
            k, [c for c in sub if c["run"] == "run 11"][0]["margin"], pos, len(sub)))

    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    supported = (r_pool < 0) and (p_two < 0.05) and (abs(r_ink) > abs(r_router))
    if supported:
        print("H_COADAPT is SUPPORTED and H_SELECT's prediction is CONTRADICTED.")
        print()
        print("  - The router beats ink MORE when it keeps LESS of the page's text")
        print("    (pooled r = %+.3f, p = %.4f). H_SELECT predicts the opposite sign." % (r_pool, p_two))
        print("  - The correlation lives on the INK side (%+.3f) not the router side" % r_ink)
        print("    (%+.3f). Ink's selection is byte-identical across checkpoints, so" % r_router)
        print("    that variation is DECODER, not selection.")
        print("  - A fixed token set is read %.2f pts differently by different" % coadapt_spreads[worst_k])
        print("    decoders at keep=%.2f, against a mean claimed margin of %.2f pts." % (
            worst_k, margin_means[worst_k]))
        print()
        print("  => The router-vs-ink margin substantially measures DECODER")
        print("     SPECIALIZATION, not selection quality. Claim 2 must not be")
        print("     stated against `ink` without a decoder trained for `ink`.")
    else:
        print("H_COADAPT is NOT SUPPORTED by the observational data.")
        print("  pooled r=%+.3f  p=%.4f  ink-side=%+.3f  router-side=%+.3f" % (
            r_pool, p_two, r_ink, r_router))
        print("  The falsifier stated in this file's docstring has fired. Do not")
        print("  book the run 18 GPU session on this reasoning.")

    print()
    print("LIMITS (stated, not buried):")
    print("  - OBSERVATIONAL. n=12 cells from 4 checkpoints x 3 budgets.")
    print("  - The 4 checkpoints are NOT independent: all fine-tuned from run 5.")
    print("  - retained_ink is a PROXY for 'distance from ink selection'. It is the")
    print("    best one on disk, but it is a scalar summary of a set difference.")
    print("  - This CANNOT say how much of the margin is co-adaptation. Only a")
    print("    decoder trained under ink selection can (run 18).")
    print()
    print("CONTROLS: %d passed, %d failed" % (PASS, FAIL))
    if CONCERNS:
        print("CONCERNS:")
        for c in CONCERNS:
            print("  - %s" % c)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
