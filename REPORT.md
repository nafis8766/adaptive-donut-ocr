# AdaptiveDonutOCR — project report

*Written 2026-09-04, reconciled against D12 and M1 on 2026-09-09. Derived entirely from
`AGENTS.md`, which remains the single source of truth; where this file and `AGENTS.md` disagree,
`AGENTS.md` is right and this file is stale.*

> ⚠️ **STALE AS OF 2026-09-17 — this file predates runs 11 and 12.** Two figures were corrected
> in place on 2026-09-17 (the router-vs-ink sign, and M1's control count); they are marked where
> they appear. **Three statements below are now outright wrong and are NOT corrected here**,
> because reconciling them properly belongs with the run-12 analysis:
> - *"H1 is supported, not isolated"* / *"Pending 14 open"* — **H1 was isolated by run 11**
>   (2026-09-14), `ISO(0.35) = −10.49`, t −3.74.
> - *"ToMe has never executed"* / *"Pending 15 open"* — the checkerboard split landed
>   2026-09-09 and the merge sweep ran as **run 12** (2026-09-16). **Correction 2026-09-18:
>   run 12 attached the wrong checkpoint (run 5's, not run 9's), so the real pre-registered
>   merge run is **run 13** (2026-09-17). Result: merging away 20% of the router's kept set is
>   free, 40% costs −3.86 pts [−7.45, −0.30]. See AGENTS.md.**
> - The run table stops at run 10.
>
> Read `AGENTS.md` for current state, [STORY.md](STORY.md) for the chronology.

---

## What this project is

Token-pruning research on **Donut** (`naver-clova-ix/donut-base`) for full-page document OCR,
evaluated on **FUNSD**. The pipeline:

```
frozen Swin-B encoder → PatchSaliencyRouter → BipartiteTokenMerger → mBART decoder
   (4800 patch tokens)    MLP score + STE top-k    ToMe cosine soft-merge    seq2seq
```

A CV research project with no deadline. Training runs on Kaggle free-tier T4s; diagnostics run
locally on CPU between runs, off cached artifacts.

## The problem

A document page becomes **4800 visual tokens**, most of them margin and whitespace. The question
is: **how few visual tokens can you keep and still transcribe the page?** The deliverable is an
accuracy-vs-token-count curve, plus a learned router that picks *which* tokens to keep better
than random selection or a hand-crafted ink heuristic.

Two scoping facts that constrain every claim made from this work:

- **It is not a latency result.** D11 measured wall-clock across five budgets: cutting
  4800 → 960 visual tokens (5×) buys **1.04×** (max 1.05× over ten rows). The router sits
  *after* the frozen encoder, so all 4800 tokens are computed at every `keep_ratio`, and
  generation is decoder-bound (243–280 autoregressive steps, encoder runs once). Pruning shrinks
  only the cross-attention KV. **Any latency or throughput claim from this work is false.** The
  defensible axes are visual-token count and the cross-attention KV memory that scales with it,
  which M1 has now measured.
- ~~**`BipartiteTokenMerger` has never executed.** `merge_ratio=0.0` in all ten runs
  short-circuits it, so half the headline architecture is untested.~~ *(Corrected 2026-09-18:
  it executed on runs 12–13. **Merging 20% of the router's kept set is free at four budgets
  under both the router and the ink oracle; 40% costs −3.86 pts [−7.45, −0.30]** — measured on
  merge-naive weights, which is the standing limitation run 14 addresses — **attempted
  2026-09-18 and left unresolved; see the "Live weaknesses" row below.** The merger also sits
  after the frozen encoder, so it adds no encoder-side or latency saving either.)*

## Evaluation protocol

Held constant since run 2; decoding deliberately changed at run 6.

FUNSD test × 50 images · word recall / char accuracy / word-order · mean NED ·
`MAX_WORDS=128` · `max_length=512` · task prompt `<s_doc>` · `repetition_penalty=1.0`,
`no_repeat_ngram_size=3` (since run 6).

Data is `nielsr/funsd` (149 train / 50 test) plus `naver-clova-ix/synthdog-en`. SROIE is
deliberately excluded — its KIE schema would pollute the single `{"text": ...}` target.
Changing any of the above breaks comparability across the whole run table.

## Standing results — the four claims this project can make

**1. Pruning to a third of the visual tokens costs nothing — *if you train for it*.** The
condition is load-bearing and was absent from every phrasing of this claim before D12. Run 9,
trained at `TRAIN_KEEP_RATIO=0.50`, gives up 65% of its tokens at keep=0.35 for **−0.26 pts
(t −0.18)** against its own unpruned ceiling, a *measured* null (detectable ≥ 2.81 pts). Run 5,
trained and evaluated unpruned, loses monotonically on the **identical** token sets:
**−1.57 / −6.03 / −11.47 / −20.34** at keep=0.50/0.35/0.25/0.20, significant at the last three.
Pruning is not a property of the pruner.

*Attribution limit:* run 9 differs from run 5 by pruning-aware training **and by five more
epochs of it**. H1 is *supported, not isolated*. Do not upgrade "H1 supported" to "H1 proven" —
the missing control is Pending 14.

**2. The router's selection value is real and large.** Against random selection at the same
token budget, on the same 50 images (D11 rows):

| keep | tokens | router | random | margin |
|---|---|---|---|---|
| 0.50 | 2400 | 80.46 | 62.77 | **+17.7** |
| 0.35 | 1680 | 79.25 | 51.84 | **+27.4** |
| 0.25 | 1200 | 71.15 | 37.20 | **+34.0** |
| 0.20 | 960 | 63.10 | 33.80 | **+29.3** |

This supersedes the "+14 to +28" range quoted in earlier drafts, which understated the top end.
Do **not** cite "beats the ink oracle" — the router-vs-ink comparison at keep=0.50 is **+2.24 pts
(80.46 vs 78.22) for 0.072 LESS retained ink**, at t +1.62, under the pre-registered t ≥ 2.0.
Directional, not significant. *(Corrected 2026-09-17: this paragraph previously read "−2.24 pts
for +0.072 more ink ... (t −1.62)" — the double sign inversion `check_writeup_numbers.py` caught
in `WRITEUP.md` on 2026-09-09 was never propagated here.)*

**3. One measured efficiency claim, with its price attached.** M1 measured decoder
cross-attention KV bytes at five budgets: keep=0.35 takes it from **150.00 → 52.50 MiB
(−65.0%) for −0.26 pts (t −0.18, n=50 paired)**. Unpruned cross-KV is **19.46% of the model's
771 MiB**, so the cut is a large fraction of a non-trivial quantity — a framing the script
derives from its own output after its pre-written hedge ("a large cut in a small quantity") was
falsified. **25/25** controls pass *(corrected 2026-09-17 from "17/17", which was eyeballed once
and copied three times; `eval_kv_memory.py` has no control counter — `ok_all` is a boolean AND —
so the count has to be read off the `[PASS]` lines in `results/kv_memory_local.log`)*, including
analytic-vs-observed agreement at rel gap 0.0000 on
all five budgets. **Scope:** cross-attention KV only — not total, not peak, **not encoder**
(the frozen Swin computes all 4800 tokens at every budget), and **not latency**. The headline
is deliberately not keep=0.20's −80.0%, which costs 13.01 pts (t −5.42).

**4. The methodological layer is a first-class result.** See below.

## Why pruning helps — settled

D12 tested the standing guess and rejected it. Two hypotheses:

- **H1 train/test matching** (mundane): runs 9/10 trained with pruning ON at keep=0.50, so
  keep=1.00 is off-distribution, the 77.62 ceiling is depressed, and the "gain" is a recovery.
- **H2 inference-time denoising** (interesting): blank paper dilutes cross-attention, so pruning
  should help a model that never trained with it.

Run 5 discriminates — trained *and* evaluated unpruned. **H2 predicted run 5 would improve
under pruning; it falls monotonically.** Run 9 peaks at exactly the budget it was trained for.
H2 was given its most favourable selection (`select_mode="ink"`, ink oracle retaining 0.994 of
the page's ink at keep=0.50, bit-identical token sets across checkpoints, verified `0.00e+00`
at all four budgets) and still failed. Difference-in-differences is negative at all four
budgets (−2.17 / −5.77 / −4.52 / −7.33), significant at two.

The pre-registered `decide()` returned **UNDERPOWERED** and that stands — but it keyed on
keep=0.50 alone, the flattest point on the curve. The docstring's pre-registered *prose*
prediction was about curve **shape**, and that is resolved decisively. Both readings are
reported with their power; neither is quietly promoted. The lesson: when a hypothesis is about
the shape of a curve, the statistic must be about the shape.

## Live weaknesses, all on the record

- H1 is supported, not isolated (Pending 14 is the control that would close it).
- ~~ToMe has never executed, so half the described architecture is untested (Pending 15).~~
  **Merging is measured (runs 12–13) but only off-distribution** — every checkpoint was trained
  at `merge_ratio=0.0`, so the one measured cost (40% merge, −3.86 pts) cannot yet be told apart
  from H1's train/test-matching effect. ~~Run 14 is that test.~~ **Run 14 ran it (2026-09-18)
  and came back UNDERPOWERED** — the contrast went to −0.28 [−4.46, +3.44] at resolution 3.95
  against a 3.6 bar, so its interval still contains −3.86. Worse for the merging reading: the
  same checkpoint gained as much on a *random, unmerged* selection as on the merged row
  (+3.43 vs +3.11, difference −0.32 p=0.60), and NED degraded significantly (p=0.029) where
  recall did not. **2.5× at M=1920 remains the measured limit.** *(Row corrected 2026-09-18,
  updated 2026-09-21.)*
- The unpruned ceiling itself moves with each retrain — **1.09 and 1.30 pts on two runs, 10.93 on
  a third**, and on runs 7–8 inseparable from a harness fault. *(Corrected 2026-09-17 from
  "≈1 pt", which was an average taken over a set containing the 10.93.)*
- **Local-vs-Kaggle generation drift**, widening as the budget tightens: run 5 reads 74.72
  locally vs 77.74 on Kaggle on identical weights and images. Selection reproduces to three
  decimals; generation does not. This is a limitations paragraph, not an experiment — and it is
  why nothing in D11/D12 compares a local level to a Kaggle one. **Within-checkpoint deltas are
  the comparable quantity.**
- ~18% of outputs are still not valid JSON.

---

## Techniques per run, and why

| Run | Technique introduced | Why it was tried | What it returned |
|---|---|---|---|
| **2** | Baseline, pruning OFF | Pin a floor and prove the pipeline runs | 54.07 recall (n=20) |
| **3** | Augmentation, 40 epochs, no synthetic | Assumed accuracy was data-bound | Train CE 0.32 → 0.13, test recall **flat**. Diagnosis: "data-bound" |
| **4** | SynthDoG synthetic mix (63% synth) | Direct test of the data-bound theory | **Negative, −2.14 recall.** CE collapsed 0.40 → 0.049 = memorisation. A frozen Swin cannot separate FUNSD's degraded glyphs, and clean synthetic pulled the priors off-domain. Killed the planned scale-up to 4000–6000 synth |
| **5** | Unfreeze top Swin stage @ lr 1e-5, rebalance data (`SYNTH_N=500`) | Run 4 said the *encoder* was the bottleneck, not decoder-side data | Mixed: char acc +2.09, word order +3.66, recall −1.16. Unfreeze verified by tensor diff — stage 3: 34/34 changed, stages 0–2 + embeddings: 0/315 |
| **6** | **Decoding ablation, eval-only** — `repetition_penalty` 1.3 → 1.0 | Output was capped at 71% of gold length; suspected under-generation | **Biggest result in the project, zero training cost.** 50.56 → **77.74** recall on unchanged run-5 weights; valid JSON 0% → 82%. The *suspected* knob (`no_repeat_ngram_size=3`) was a bit-exact no-op at rp=1.3. CONTROL row reproduced run 5 at 0.00 pt drift |
| **7** | First **pruning-ON retrain** (keep=0.5, STE active, sparsity loss) + 15-row selection sweep | D1 found the router was an *inverted* saliency detector: trained at keep=1.0, where the STE multiplier is exactly 1.0, so its only gradient asked "does scaling this token help", not "is this token informative" | STE alone **did not fix the sign** — forward router 18.80 recall, below the random floor of 62.31. The *negated* score worked (73.09), so the ranking carried real signal with the wrong sign. Cost 5.2 pts of full-page recall |
| **8** | **ink-BCE saliency loss** — supervise the router against a free text proxy (`patch_ink` contrast → binary target) | Give the router a sign-correct objective rather than relying on the CE-through-STE gradient | **Sign fix decisive.** 80.17 @ keep=0.50, 77.80 @ 0.35. Confirmed by role-flip: `negated` collapsed 73.09 → 2.70. Caveats: three loss knobs moved in one `if/else`, and the loss fed a probability to `binary_cross_entropy_with_logits` (D4) |
| **9** | **F1** loss fix + **F2** harness control (re-evaluate run-5 weights through the same harness *before* the sweep) | Runs 7–8's control drift conflated "the harness is sound" with "the retrain moved the ceiling" and could not separate them | F2 passed at **0.00 pts** — the first anchored numbers in the project. F1's mechanism worked (retained ink 0.790 → 0.922) and **accuracy fell**. → **D6**: optimising the ink proxy *harder* actively costs accuracy |
| **10** | **Attention target** — supervise the router on the top-K of a frozen run-5 decoder's cross-attention instead of ink | D8/D9/D10 established the attention target is a *different*, page-specific signal (r = +0.083 vs ink), *reachable* by the existing MLP (held-out AUC 0.976), *stationary* under encoder drift, and that the router was uninformed about it (r = −0.045) | **The mechanism fit better than any auxiliary in the project** (router's top-2400 contained 93% of the teacher's; lift +0.430) and **accuracy did not move**. Also collapsed retained ink 25–32 pts at flat recall — a third independent line killing ink as the objective |
| **D11** | Re-ask run 10's question at budgets that **bind** — paired on the same 50 images, local CPU, eval only | Run 10's null was structurally guaranteed: at keep=0.50 pruning *beat* not pruning by +2.1, so no selection objective could win there | **The attention target does not tie — it loses**: −5.63 @ keep=0.25 (t −2.40) and −12.81 @ keep=0.20 (t −6.23), monotone in tightness. Mechanism: run 10's router retains ink 0.257 against random's 0.201 — a **near-ink-agnostic selector**, harmless while the budget is slack, ruinous once every token must carry text. Also killed the latency framing (1.04× at 5× fewer tokens) |
| **D12** | Run 5 as the discriminating arm — trained *and* evaluated unpruned, `select_mode="ink"` so both checkpoints keep bit-identical tokens | "Why pruning helps" had stood unexplained since D11, with a regularisation-like effect as the obvious guess and nothing testing it | **H2 REJECTED.** Run 5 declines monotonically where H2 predicted improvement; run 9 peaks at its trained budget. **The deliverable requires the word "if".** H1 supported but *not isolated* — the five-extra-epochs confound was stated in the docstring before any output |
| **M1** | Decoder cross-attention KV bytes at five budgets, analytic vs hook-observed | D11 killed the latency claim, leaving the writeup with **no** efficiency claim | **Pending 8(c) closed.** keep=0.35: 150.00 → 52.50 MiB (−65.0%) for −0.26 pts. 25/25 controls; two independent measurements agree to rel gap 0.0000. Self-KV asserted non-monotone in keep, so a self/cross mix-up cannot pass as a pruning win. **Extended 2026-09-18 to prune+merge, 52/52 controls:** keep=0.50 + merge 0.20 → M=1920 gives 2.50× (60.00 MiB) for **+0.54 pts, CI [−2.36, +3.83]** — no measured cost; 3.33× at M=1440 costs **−3.86 pts [−7.45, −0.30]** |

### Run table

| Run | Phase | Config | n | Recall | CharAcc | Order | NED |
|---|---|---|---|---|---|---|---|
| 2 | 1 (baseline) | pruning OFF | 20 | 54.07 | 36.00 | 21.40 | 0.640 |
| 3 | 1.5 (augmentation) | 40 ep, no synth | 50 | 53.86 | 38.42 | 22.61 | 0.616 |
| 4 | 2-data (SynthDoG) | synth 63% | 50 | 51.72 | 38.88 | 22.83 | 0.611 |
| 5 | 2b (encoder unfreeze) | top Swin stage @ 1e-5 | 50 | 50.56 | 40.97 | 26.49 | 0.590 |
| **6** | 2c (decoding fix) | eval-only on run-5 weights | 50 | **77.74** | **64.70** | **53.05** | **0.353** |
| 7 | 2e (pruning-ON retrain) | keep=0.5, STE | 50 | 72.55 | 55.11 | 42.12 | 0.449 |
| 8 | 2f (sign-fix) | + ink-BCE | 50 | 78.25 | 64.53 | 54.35 | 0.355 |
| **9** | 2g (F1 + F2) | + fixed loss, verified harness | 50 | **79.63** | 64.81 | 54.08 | 0.352 |
| 10 | 13(b) | attention target | 50 | 79.41 | 64.81 | 53.97 | 0.352 |

Rows 2–5 are `repetition_penalty=1.3` numbers — an artifact — and are internally comparable to
each other and to nothing else. **Comparability restarts at run 6.** Rows 7–8 are the
`keep=1.00` row of a 15-row sweep; rows 9–10 are the `keep=0.50` trained operating point. Do not
read the column vertically without checking which is which. All of these are **Kaggle** levels;
D11/D12/M1 numbers are **local** and comparable to each other, not to this table.

---

## The methodological layer

A substantial and deliberate part of the project. Several of its best findings came from this
rather than from GPU time:

- **Diagnostics D1–D12** are standalone scripts that re-derive their numbers from cached
  artifacts, so any claim can be rechecked without a GPU. Several falsified the hypothesis they
  were built to support: D1 inverted the plan it was meant to enable, D2 overturned D1's own
  recommendation in under a second, D7 falsified its author's collapse hypothesis twice, and
  D12 rejected the guess this file had carried for a week. M1's pre-written docstring framing
  was falsified by its own output.
- **`verify_*.py` execution checks** *exec* the real notebook cells rather than lint them — the
  training loop, the loss block, the weight-swap control, and the full 13(b) composition against
  a real decoder. The standing rule is that a patch must be shown to **run**, not just parse.
- **Pre-registered acceptance criteria**, including a `MIN_EFFECT_PTS` power floor added after a
  smoke run showed the verdict path could not distinguish *"we looked and saw nothing"* from
  *"we could not have seen it"* and defaulted to reporting the first. D12 reports a code verdict
  that **disagrees** with its shape finding rather than dropping either.
- **Controls chosen so they can fail.** D11's gate was moved off a recall delta (which passed on
  two images, where the estimate is noise) and onto `retained_ink`, which is near-deterministic
  given the weights — it then matched Kaggle exactly to three decimals on six gates. D12
  replaced a broken anchor mid-flight with one pinned to a number that **did not yet exist**
  (run 9 @ keep=1.00 must reproduce D11's local 77.62 within 0.5); it came back gap 0.00.
- **Diffing executed notebooks**, so a "we changed one variable" claim is demonstrated rather
  than asserted. Run 10's diff shows exactly three removed target lines plus two logging lines.

Three separate correctness defects — the decoding cap, the keep=1.0 STE trap, and the
probability-fed-to-BCEWithLogits loss — were found this way rather than by a run failing.

## Where it stands

**Closed:** ink as a training objective (three independent lines: D2 correlational, D6/run 9
interventional, run 10's collapse at flat recall); the attention target (D11); the latency
framing (D11); the KV-memory question (M1, Pending 8c); "why does pruning help" (D12 — H2
rejected, H1 supported); stratified selection; `repetition_penalty > 1.0`. Run 11 as sketched
under the old Pending 13 is cancelled — the mechanism D11 found is not specific to which target
is used.

**Open, in priority order:** **Pending 14** — isolate H1 with a run-5-length control trained
without pruning (~4 h Kaggle T4, the highest-value remaining experiment, since claim 1 rests on
the attribution D12 explicitly did not make). ~~**Pending 15** — ToMe has never run; settle the
merge-after-prune ordering or scope it out of the writeup.~~ **Pending 15 closed 2026-09-17**
(ordering settled, merger measured on runs 12–13); ~~**run 14** replaces it — train with
`TRAIN_MERGE_RATIO=0.40` to test whether run 13's 40% cost is train/test mismatch or the
merger.~~ **Run 14 ran 2026-09-18 → UNDERPOWERED** (−0.28 [−4.46, +3.44], res 3.95 vs a 3.6
bar; gain not distinguishable from a general robustness lift; NED significantly worse where
recall was flat). **2.5× at M=1920 stays the limit.** What replaces *it* is a **redesigned**
merge-training run — not a rerun at n=50, since 50 is the whole test split — plus the
symmetric missing control, a `keep=0.30, merge=0.0` checkpoint. Then the ~18% invalid-JSON
rate, the
co-adaptation 2×2 (old Pending 5, now optional), and recording the local-vs-Kaggle drift as a
limitations paragraph.
