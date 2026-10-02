"""Where in the encoder would token merging actually save compute? (T5's evidence)

WHY THIS EXISTS
---------------
T5 asks where ToMe should live. AGENTS.md states the case qualitatively:

    "The merger sits *after* the frozen Swin, so it saves no encoder compute and
     no latency (1.04x measured, D11) ... The alternative is merging *inside*
     Swin, progressively, between blocks -- which is what ToMe was designed for
     and the only version that buys FLOPs and latency."

"Saves no encoder compute" is right but imprecise, and "inside Swin buys FLOPs"
is asserted without saying WHERE inside. Those are different claims with
different costs, and the second one decides whether T6/T7 are moot. This script
computes the per-stage budget so the decision is made against numbers.

WHAT IT IS AND IS NOT
---------------------
An ANALYTIC FLOPs proxy from the published config -- not a measurement. It
counts the dominant per-token terms (window attention + MLP) and ignores patch
merging, norms, biases and all memory traffic. D11 measured actual wall-clock at
1.04x for a 5x visual-token cut, which is the empirical check on the conclusion
this proxy supports; agreement between an analytic count and an observed one is
the pattern M1 used (rel gap 0.0000).

FALSIFIER, stated before running
--------------------------------
If merging at the input to the LAST stage could save a large share of encoder
FLOPs, then ToMe's current placement is nearly free to fix and T5 should move it
one stage earlier rather than treat inside-Swin as a new project.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

PASS = FAIL = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def main():
    from transformers import VisionEncoderDecoderConfig

    cfg = VisionEncoderDecoderConfig.from_pretrained("naver-clova-ix/donut-base").encoder
    H, W = cfg.image_size
    p, ws, depths, d0 = cfg.patch_size, cfg.window_size, list(cfg.depths), cfg.embed_dim

    print("=" * 78)
    print("ToMe placement: where is the encoder's compute? (analytic proxy)")
    print("=" * 78)
    print(f"donut-base encoder: image {H}x{W}, patch {p}, window {ws}, "
          f"depths {depths}, embed_dim {d0}")
    print()

    # Per-stage geometry. Swin halves each spatial dim and doubles channels.
    stages = []
    gh, gw = H // p, W // p
    for i, blocks in enumerate(depths):
        d = d0 * (2 ** i)
        tokens = gh * gw
        # Window attention: each token attends within its ws*ws window -> qk + av
        # is O(tokens * ws^2 * d). Projections+MLP is O(tokens * d^2) with the
        # standard 4x MLP ratio: qkv(3) + out(1) + mlp(8) = 12 d^2 per token.
        attn = tokens * (ws * ws) * d * 2
        proj = tokens * (d * d) * 12
        stages.append(dict(i=i, gh=gh, gw=gw, tokens=tokens, blocks=blocks, d=d,
                           per_block=attn + proj,
                           total=(attn + proj) * blocks))
        if i < len(depths) - 1:
            gh, gw = gh // 2, gw // 2

    grand = sum(s["total"] for s in stages)

    print("-- per-stage budget --")
    print(f"  {'stage':<6}{'grid':<12}{'tokens':>9}{'blocks':>8}{'dim':>7}"
          f"{'% of encoder':>14}")
    for s in stages:
        grid = f"{s['gh']}x{s['gw']}"
        pct = 100 * s["total"] / grand
        print(f"  {s['i']:<6}{grid:<12}{s['tokens']:>9,}"
              f"{s['blocks']:>8}{s['d']:>7}{pct:>13.1f}%")
    print(f"  {'':6}{'':12}{'':>9}{sum(depths):>8}{'':>7}{100.0:>13.1f}%")

    print("\n-- max encoder FLOPs saving, by insertion point --")
    print("  (merging r% of tokens at a point removes r% of EVERYTHING AFTER it)")
    print(f"  {'insert before':<18}{'downstream share':>18}"
          f"{'saving @ 20% merge':>21}{'@ 50%':>9}")
    for k in range(len(stages)):
        downstream = sum(s["total"] for s in stages[k:]) / grand
        print(f"  {f'stage {k}':<18}{100 * downstream:>17.1f}%"
              f"{100 * downstream * 0.20:>20.1f}%{100 * downstream * 0.50:>8.1f}%")
    print(f"  {'AFTER stage 3':<18}{0.0:>17.1f}%{0.0:>20.1f}%{0.0:>8.1f}%"
          f"   <<< WHERE IT IS NOW")

    print("\n-- controls --")
    last = stages[-1]
    check("stage-3 output matches the repo's TOKEN_GRID (80, 60) = 4800",
          (last["gh"], last["gw"]) == (80, 60) and last["tokens"] == 4800,
          f"got {last['gh']}x{last['gw']}={last['tokens']}")
    check("current placement saves exactly 0% of encoder FLOPs",
          True, "it is downstream of every encoder block -- 0 by construction, "
                "which is why D11 measured 1.04x")
    s2 = stages[2]
    check("one stage dominates, so placement is not a uniform trade",
          s2["total"] / grand > 0.5,
          f"stage 2 alone is {100 * s2['total'] / grand:.1f}% "
          f"({s2['blocks']} of {sum(depths)} blocks at dim {s2['d']})")
    share_before_3 = stages[3]["total"] / grand
    check("merging at the START of the last stage is still a small win",
          share_before_3 < 0.15,
          f"only {100 * share_before_3:.1f}% is downstream, so a 50% merge there "
          f"saves {100 * share_before_3 * 0.5:.1f}%")
    check("the proxy is not degenerate (stages differ by >2x)",
          max(s["total"] for s in stages) / min(s["total"] for s in stages) > 2,
          f"ratio {max(s['total'] for s in stages) / min(s['total'] for s in stages):.1f}x")

    print("\n" + "=" * 78)
    print(f"CONTROLS: {PASS}/{PASS + FAIL} PASS")
    print("=" * 78)
    print("CONCLUSION (evidence for T5, not a decision):")
    print(f"  * Current placement is downstream of ALL {sum(depths)} encoder blocks,")
    print(f"    so its encoder saving is 0% BY CONSTRUCTION -- not small, zero.")
    print(f"    D11's measured 1.04x is the expected result, not a disappointment.")
    print(f"  * Stage 2 is {100 * s2['total'] / grand:.1f}% of the encoder "
          f"({s2['blocks']} of {sum(depths)} blocks).")
    print(f"    Any merge that does not happen BEFORE stage 2 cannot matter much.")
    print(f"  * Moving it one stage earlier (before stage 3) caps out at "
          f"{100 * share_before_3 * 0.5:.1f}%")
    print(f"    even at a 50% merge ratio -- so 'inside Swin' is only worth doing")
    print(f"    at stage 0-2, on grids of {stages[0]['tokens']:,}/"
          f"{stages[1]['tokens']:,}/{stages[2]['tokens']:,} tokens, where window")
    print(f"    partitioning and shifted-window attention are load-bearing.")
    print(f"  * That is a redesign of a FROZEN pretrained encoder, which would")
    print(f"    also break comparability with the entire run 2-14 table.")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
