# Pruning two thirds of a document's visual tokens, for free — if you train for it

*Writeup, 2026-09-09. Every number below is traceable to an artifact in this repository;
`AGENTS.md` is the source of truth and carries the full run history, the diagnostics that
produced these figures, and the approaches that failed.*

> **⛔ READ FIRST — FINAL STATE, 2026-10-05**
>
> **The project is closed.** Two of its three results stand as written below. The **merging**
> result does not: both *"20% merge is free"* and *"40% costs −3.86 [−7.45, −0.30]"* are
> **RETIRED**, and the honest terminal verdict on the merge axis is **`UNDERPOWERED`**,
> requiring **n ≳ 307** documents that were never collected.
>
> The retirement is **not** an arithmetic correction — both figures still reproduce exactly
> from run 13's artifacts. A pre-registration written before the deciding run existed was
> applied backwards to runs 13 and 14, and the **verdicts** did not survive it: the
> token-matched primary at M=1920 is **+1.66 [−0.81, +4.14]** and **+0.02 [−1.90, +1.94]**,
> with **0 of 3 confirmatory quantities surviving Holm in either run.**
>
> **Everything below is preserved as written, with corrections marked in place** — nothing is
> deleted, because the reason a claim was wrong is the more useful half of the record. The
> three dated correction blocks are the document's actual argument. **The full final
> accounting is §5's third correction; `AGENTS.md` → `## Project closed 2026-10-05` is the
> source of truth.**

> **Correction, 2026-09-18 — the merging gap this writeup declares open has since been
> closed.** Four statements below said `BipartiteTokenMerger` "has never executed" and that
> the merge sweep was "blocked on an ordering fix". The ordering fix (`checkerboard_color`,
> deriving A/B colour from the original raster index rather than from score rank) landed, and
> the merger ran end to end on a Kaggle T4 as **run 13** (2026-09-17, 28-row token-matched
> grid). The four sites are corrected in place and marked. Result: ~~**merging away 20% of the
> router's kept set is free at four budgets under both the router and the ink oracle; 40%
> costs −3.86 pts [−7.45, −0.30]**~~ — **both verdicts retired 2026-09-24; see the banner
> above and §5's third correction.** Nothing else in this writeup changes — §2's scope limits
> apply to the merger unchanged, because it also runs *after* the frozen Swin.

> **Second correction, 2026-09-21 — run 14 has now run, and it does not settle the question.**
> Where the text below says run 14 will decide whether the 40% cost is train/test mismatch,
> read this instead. Training with `TRAIN_MERGE_RATIO=0.40` took that contrast from
> −3.86 (p=0.005) to **−0.28 [−4.46, +3.44] (p=0.92)** — flat, but at resolution **3.95 pts
> against a pre-registered 3.6 bar**, so the verdict is **UNDERPOWERED** and the confidence
> interval still contains the original −3.86. Three further findings keep it from being read
> as a quiet success: (i) the same checkpoint improved **just as much on a random, unmerged
> selection** (+3.43) as on the merged row (+3.11), difference −0.32 (p=0.60), so no
> merging-specific component is measurable; (ii) on the same contrast **NED degrades
> significantly** (p=0.029) and charAcc/word-order each drop ~3 pts, so "free" holds on recall
> alone; (iii) the router's margin over random selection **fell** +17.07 → +13.16. **The
> operative claim is unchanged: 2.5× cross-attention KV at M=1920 is the measured limit, and
> 3.33× at M=1440 is not licensed.** See "Run 14 — result" in `AGENTS.md`.

---

## Summary

Donut turns a document page into **4800 visual tokens**, most of which are blank paper. We
train a lightweight scoring head to rank those tokens and discard the low-ranked ones before
the decoder ever sees them, and ask two questions: **how few can you keep**, and **does
learning which ones to keep beat not learning it**.

Three results, in the order of how much they are worth:

1. **Discarding 65% of the visual tokens frees 65% of the decoder's cross-attention KV for
   −0.26 pts of word recall (t −0.18, n=50 paired)** — a measured null, not an absence of
   measurement. The condition is load-bearing: this holds **only for a checkpoint trained
   with pruning on**. The same pruning applied to a model trained unpruned costs 6.03 pts at
   the same budget.
2. **Learned selection is worth +17.7 to +34.0 pts** of word recall over random selection at
   an identical token budget, widening as the budget tightens.
3. **The gain is train/test matching, not denoising.** A hypothesis that pruning removes
   distracting whitespace predicts an unpruned-trained model should also improve under
   pruning. It does not — it declines monotonically. This was tested and rejected rather
   than assumed either way.

What this work does **not** show: any latency or throughput win; any encoder-side saving; any
**conclusive** result for token merging on a checkpoint trained with merging on.
~~any result for the token-merging half of the architecture, which has never executed.~~
*(Corrected 2026-09-18: the token-merging half does now have a result — run 13, §5. What it
does not have is an in-distribution one; run 14 is that run.)* *(Corrected again 2026-09-21:
run 14 ran. Its in-distribution contrast is **flat but UNDERPOWERED** — −0.28 at res 3.95
against a 3.6 bar — and its gain is not distinguishable from a general robustness lift, so
the in-distribution question is **attempted and unresolved**, not answered.)*

---

## 1. Setup

```
frozen Swin-B encoder → PatchSaliencyRouter → BipartiteTokenMerger → mBART decoder
   (4800 patch tokens)    MLP score + STE top-k    ToMe cosine soft-merge    seq2seq
```

**Model.** `naver-clova-ix/donut-base`. The Swin-B encoder emits an 80×60 token grid at
2560×1920 input (stride 32) = 4800 tokens. The decoder is 4 layers × 16 heads × 64 head-dim,
`d_model` 1024. Parameters are 771 MiB at fp32.

**Router.** A 2-layer MLP scoring head with a straight-through estimator,
`M_ste = TopK(s) + s − detach(s)`: hard discrete filtering in the forward pass, end-to-end
gradients from the decoder loss back into the scorer. The router sits **after** the frozen
encoder, which is what bounds the efficiency story to the decoder side (§5).

**Task and data.** Full-page OCR into a single `{"text": ...}` target. FUNSD
(`nielsr/funsd`, 149 train / 50 test) plus 500 SynthDoG-en pages. SROIE is deliberately
excluded — its key-information-extraction schema would pollute the single-field target.

**Evaluation protocol,** held constant since run 2: FUNSD test × 50 images · word recall,
character accuracy, word-order, mean NED · `MAX_WORDS=128` · `max_length=512` · prompt
`<s_doc>` · `repetition_penalty=1.0`, `no_repeat_ngram_size=3`.

**Selection modes.** Evaluation can swap the *ranking signal* while holding the token budget
fixed: `router` (learned scores), `random` (uniform), `ink` (pixel contrast, no learning),
`negated` (the router's scores inverted), and two per-grid-row stratified variants. Because
only the ranking changes, rows are comparable at equal cost. `ink` is additionally
**weight-independent** — it depends on the image alone — which is what makes it usable for
cross-checkpoint comparison (§4).

**Two venues, and they do not mix.** Training runs on Kaggle T4s; diagnostics run locally on
CPU against cached checkpoints. The same weights on the same 50 images score 77.74 on Kaggle
and 74.72 locally — different device, different `transformers` version. Token *selection*
reproduces across the two to three decimals; *generation* does not, and the gap widens as
the budget tightens. **Every claim below is therefore a within-checkpoint, within-venue
paired delta.** No number here compares a local level to a Kaggle one.

---

## 2. Result 1 — the budget claim

Run 9 is trained with pruning active at `keep_ratio=0.50` for 5 epochs, resumed from a
checkpoint trained unpruned. Evaluated at four budgets against its own unpruned ceiling, on
the same 50 images, paired per image:

| keep | visual tokens | cross-attn KV | word recall | Δ vs unpruned | t | verdict |
|---|---|---|---|---|---|---|
| 1.00 | 4800 | 150.00 MiB | 77.62 | — | — | ceiling |
| 0.50 | 2400 | 75.00 MiB (−50.0%) | 78.22 | **+0.60** | 0.43 | free (powered ≥ 2.76) |
| **0.35** | **1680** | **52.50 MiB (−65.0%)** | **77.37** | **−0.26** | **−0.18** | **free (powered ≥ 2.81)** |
| 0.25 | 1200 | 37.50 MiB (−75.0%) | 70.67 | −6.96 | −2.82 | costly |
| 0.20 | 960 | 30.00 MiB (−80.0%) | 64.61 | −13.01 | −5.42 | costly |

*Recall from D12, `select_mode="ink"`, local CPU, n=50 paired. KV from M1.*

**The headline is the keep=0.35 row: 65% of the tokens gone, 65% of the cross-attention KV
freed, and no detectable accuracy cost.** The two 65%s are the same 65% — cross-attention KV
is linear in kept tokens — which is why the claim can be stated as a single sentence rather
than as a rate and a price that have to be traded off by the reader.

Three things make this a result rather than a hope:

**It is powered.** A flat row means nothing if the experiment could not have seen a real
effect. The paired standard error puts the smallest detectable effect at **2.76 and 2.81 pts**
for the two free rows, against a pre-registered floor of 3.0. So "we looked and saw nothing"
is distinguishable from "we could not have seen it", and this is the former. The tight rows
(0.25, 0.20) are reported as costs, not quietly dropped.

**The memory figure is measured twice.** M1 computes cross-attention KV analytically
(`2 × layers × heads × head_dim × tokens × 4 B`) *and* captures the real `past_key_values`
through a forward hook on the decoder. The two agree to **relative gap 0.0000** at all five
budgets, with a control asserting the captured tensor's `seq_len` equals `generate()`'s own
reported `compressed_tokens`. Self-attention KV — which pruning does not touch — is asserted
to be a function of generated length only, and is **non-monotone in keep** (0.25 → 10.19 MiB
exceeds 0.35 → 9.56 MiB while cross-KV moves the other way), so a self/cross mix-up cannot
be mistaken for a pruning win. 25 of 25 controls pass.

**The headline budget was chosen by a rule, not by inspection.** keep=0.20 gives a larger
memory cut (−80.0%) and would have made a better-sounding number; it costs 13.01 pts. The
script fixes the headline at the tightest budget that is *free* and fails a control if that
budget turns out not to be free, so the framing cannot drift toward the biggest available
percentage.

**Scope.** Cross-attention KV only. Not total memory, not peak, **not the encoder** — the
frozen Swin computes all 4800 tokens at every budget — and not latency. Unpruned cross-KV is
**19.46% of the model's 771 MiB**, so this is a large cut in a real quantity, but it is one
quantity. All byte figures halve at fp16 and scale with batch size; the *percentage* is
invariant to both.

**Selection caveat.** The rows above use `ink` selection, which is the conservative choice —
the same checkpoint at keep=0.35 with its own `router` scores **79.25**, i.e. +1.62 *above*
the unpruned ceiling. We report the ink row as the headline because it is the one that is
paired against run 5 in §4 on bit-identical token sets.

---

## 3. Result 2 — selection value

Random selection at the same budget is the floor a router has to clear. Paired on the same
50 images, with `random` reseeded per configuration so every comparison sees identical masks:

| keep | visual tokens | router | random | margin |
|---|---|---|---|---|
| 0.50 | 2400 | 80.46 | 62.77 | **+17.7** |
| 0.35 | 1680 | 79.25 | 51.84 | **+27.4** |
| 0.25 | 1200 | 71.15 | 37.20 | **+34.0** |
| 0.20 | 960 | 63.10 | 33.80 | **+29.3** |

*D11, local CPU, n=50 paired.*

The margin **grows** as the budget tightens, up to keep=0.25, then falls back slightly at
keep=0.20 where both arms are badly degraded. That shape is the expected one: at a slack
budget a random subset still catches most of the text, and there is little for a selector to
add; at a tight budget every retained token has to carry glyphs.

This margin was not free to obtain. The router was an **inverted** saliency detector for five
runs — it ranked blank paper *above* text — because training at `keep_ratio=1.0` makes the
STE multiplier exactly 1.0, so the only gradient the scorer ever received asked *"does
scaling this token help"* rather than *"is this token informative"*. Those two anti-align. The
symptom was that inverting the router's own scores at eval time scored 73.09 while the forward
router scored 18.80, i.e. the ranking carried strong signal with the wrong sign. The fix was
an explicit sign-correct supervision term on the scoring head; the confirmation was a role
flip — after the fix, `negated` collapsed from 73.09 to 2.70.

---

## 4. Result 3 — why it works, tested rather than assumed

For a week this project recorded that pruning *helped* at some budgets and that why was
unknown, with "some regularisation-like effect" as the standing guess. Two hypotheses were
written down before the test:

- **H1, train/test matching (mundane).** Run 9 trains at keep=0.50, so evaluating it at
  keep=1.00 is off-distribution. Its unpruned "ceiling" is depressed, and the apparent gain
  from pruning is a *recovery* toward its own operating point.
- **H2, inference-time denoising (interesting).** Most of a page is blank paper, which
  dilutes cross-attention. If that is the mechanism, pruning should help a model that never
  trained with it.

**Run 5 discriminates** — trained *and* evaluated unpruned. H2 predicts its curve improves
under pruning; H1 predicts it peaks unpruned and falls. Both checkpoints were evaluated with
`select_mode="ink"`, which is weight-independent, so **both keep bit-identical token sets**
(verified at `0.00e+00` gap on all four budgets). Every difference between the curves is
therefore attributable to the weights.

**This diagnostic's control status, stated rather than summarised away.** D12 records
`controls_passed: false` and a verdict of `WITHHELD`. One of its seven controls fails — the
harness anchor, which compares run 5's *local* keep=1.00 recall (74.72) against run 6's
*Kaggle* reference (77.74) and reads a 3.02 pt gap against a 1.5 pt tolerance. That is the
cross-venue divergence of §1 firing on the one control that spans two venues, which is what it
is for. The four controls the difference-in-differences actually rests on — identical token
sets at each budget — pass at `0.00e+00`, as do both ink-oracle gates. It is reported here
rather than dropped because it is the reason everything below is a delta and never a level.

| keep | run 5 Δ (trained unpruned) | run 9 Δ (trained at 0.50) | difference-in-differences | t |
|---|---|---|---|---|
| 0.50 | −1.57 | +0.60 | −2.17 | −0.81 |
| 0.35 | −6.03 | −0.26 | **−5.77** | **−2.28** |
| 0.25 | −11.47 | −6.96 | −4.52 | −1.52 |
| 0.20 | −20.34 | −13.01 | **−7.33** | **−3.00** |

**H2 is rejected.** Run 5 declines monotonically where H2 predicted improvement, and run 9
peaks at exactly the budget it was trained for. H2 was moreover given its *most favourable*
condition and still failed: the ink oracle retains **0.994** of the page's ink at keep=0.50,
so what was discarded really was blank paper — precisely what H2 says should help.

**So the deliverable requires the word "if".** Pruning to a third of the visual tokens costs
nothing *if you train for it*. It is not a property of the pruner.

**The one thing this does not settle, stated before the run produced any output:** run 9
differs from run 5 by pruning-aware training **and by five more epochs of it**. The
cross-checkpoint gaps (+5.07 / +8.67 / +7.42 / +10.23, all significant) establish that a
difference exists, not that pruning-aware training caused it. ~~**H1 is supported, not
isolated.** The missing arm is a run-5-length checkpoint trained without pruning; it is the
next experiment, and until it runs this claim is not upgraded.~~

**✅ CLOSED by run 11 (2026-09-14) — this paragraph's "next experiment" ran, and the claim is
upgraded.** *(Correction 2026-10-05: the struck text had been stale for three weeks, and so had
the guard enforcing it — see the note below.)* Run 11 is run 9 with `TRAIN_KEEP_RATIO` 0.50 →
1.00 and **nothing else changed**, verified by diffing the executed notebooks: the five epochs
*without* the pruning. Measured paired on n=50:

- **`ISO(0.35) = −10.49 pts` (t −3.74)** — removing the pruning while keeping the epochs costs
  ten points.
- Run 11's budget curve **peaks unpruned and declines monotonically**, where run 9's is flat.
- Five unpruned epochs moved the ceiling by **+0.52 pts (t 0.24)** — i.e. the epochs alone buy
  nothing.
- Closed locally too: `ISO ≤ 0` at all four budgets, clearing the pre-registered `ISO ≤ −3.0`
  with `|t| ≥ 2.0` at keep=0.35 (−8.15), 0.25 (−7.35) and 0.20 (−7.92).

So the gain is attributable to **pruning-aware training**, not to the extra epochs, and §1 may
say *"because it was trained for it."*

⚠ **One limit stands, and it is the reason the wording is precise.** The loose budgets (Kaggle
keep=0.75/0.50, local keep=0.50) are **underpowered, not null** — no isolation is claimed there.
Write **"H1 isolated at keep=0.35/0.25/0.20"**, never "H1 proven".

⚠ **Worth recording because it is this project's own documented failure mode.** The struck
sentence survived three weeks past its refutation *and the numeric auditor was enforcing it*:
`scripts/check_writeup_numbers.py` §7 banned the phrase "H1 is isolated" on the stated
rationale *"the control has not run"* — while requiring the phrase "not isolated" to be
present. The control had run. `README.md` already carried the corrected version, so the repo's
two main documents contradicted each other and the check mandated the wrong side. A guard keyed
on the state it was written in does not merely fail to notice its own fix; it can make the fix
look like the defect. Both the ban and the needle were re-pointed on 2026-10-05.

**A methodological note we are keeping.** The pre-registered acceptance criterion returned
**UNDERPOWERED** and it still stands: it keyed on keep=0.50 alone — the flattest point on the
curve, and the budget run 9 was trained for — where nothing under 5.20 pts was detectable.
The pre-registered *prose* prediction was about the **shape** of the curve, and that is
resolved decisively. The lesson is not that the verdict was wrong; it is that a criterion
written in code tested a narrower proxy than the hypothesis it stood in for, and this was only
noticeable because the two disagreed. Both readings are reported with their power. Neither is
quietly promoted.

---

## 5. What this work does not claim

**No latency win.** Cutting 4800 → 960 visual tokens (5×) buys **1.04×** wall-clock; across
D11's ten `router` rows the maximum is 1.05×. The largest speed-up anywhere in D11 is 1.19×,
on a *random*-selection row at keep=0.20 — quoted because it is the strongest measured evidence
against this very disclaimer, and 1.19× for 5× fewer tokens is still not a win. The router runs
*after* the frozen encoder, so all 4800 tokens are computed at every budget, and generation is
decoder-bound at 243–280 autoregressive steps against an encoder that runs once. Any latency or
throughput claim from this architecture is false, and an earlier framing of this project that
leaned on one has been retracted.

**No encoder-side saving,** for the same reason.

**No claim that the router beats a hand-crafted ink heuristic.** At keep=0.50 the router
scores 2.24 pts *above* ink-oracle selection (80.46 vs 78.22) while retaining **0.072 less**
of the page's ink — so it is not merely rediscovering ink — but the paired margin is
t **+1.62** on n=50, under the pre-registered t ≥ 2.0. Directional, not significant, and the
two rows come from different diagnostics (D11 and D12) albeit the same checkpoint, venue and
protocol. The defensible comparison is against random, in §3.

**The merging result is off-distribution.** ~~`BipartiteTokenMerger` is in the architecture
diagram and has never executed: `merge_ratio=0.0` in all ten runs short-circuits it. A parity
diagnostic further indicates it *cannot* work as documented while the router sorts by score
(roughly 49% of the redundancy it should find goes unmerged), so the merge sweep is blocked on
an ordering fix rather than on GPU time.~~

*Corrected 2026-09-18.* The ordering fix landed and the merger ran as **run 13** (Kaggle T4,
2026-09-17, run 9's pruning-aware weights, 28-row grid in which every merge row is paired with
a prune-only row at the identical final token count M). ~~**Merging away 20% of the router's kept
set is free** to this harness's resolution, at four budgets and under both the router and the
ink oracle; **merging away 40% costs −3.86 pts [−7.45, −0.30]**.~~ *(Both sentences retired
2026-09-24 — see the third correction below. The **figures** still reproduce exactly; the
**verdicts** did not survive the pre-registered estimator.)* What remains a limitation is
the *condition*, and it is the same word this writeup's title turns on: every checkpoint in the
project was trained at `merge_ratio=0.0`, so run 13 measured merging **strictly off-distribution**.
By §4's own logic the 40% cost is therefore the train/test-matching lesson a second time until
shown otherwise — which is what run 14 (training with `TRAIN_MERGE_RATIO=0.40`) is for.

*Updated 2026-09-21 — run 14 ran and did not resolve it.* The contrast moved −3.86 → **−0.28
[−4.46, +3.44]**, but at resolution 3.95 against a pre-registered 3.6 bar, so it reads
**UNDERPOWERED** and its interval still contains −3.86. Two results argue against reading the
move as a merging effect at all: the same checkpoint gained **+3.43 on a random, unmerged
selection** versus **+3.11** on the merged row (difference −0.32, p=0.60), and on the same
contrast **NED is significantly worse** (p=0.029) while charAcc and word order each fall ~3 pts
— so the recall null is the only metric on which "free" holds. Against run 13 those two metrics
moved to about *half* their previous cost rather than to zero, which is the signature of a
**partial** recovery: exactly the case the pre-registration said this design could not
distinguish from a full one. **2.5× at M=1920 therefore remains the measured limit.**

### Third correction, 2026-10-05 — the merging claim is retired, and the axis is closed

**This is the final position.** Both struck sentences above were retired on 2026-09-24, and
**not for an arithmetic reason** — run 13's plain means reproduce **+0.54** and **−3.86**
exactly. What was wrong was the *words*. A pre-registration written before any run-17 number
existed (estimator, SE, interval, tail statistic, multiplicity, verdict table — fixed on the
variance structure of the paired deltas, never on the sign of a contrast) was then applied
*backwards* to runs 13 and 14, and it did not return what the headline said.

The pre-registered primary is **token-matched**, because that is the only estimand the merger
has a reason to exist for: at an equal budget of **M=1920**, does merging preserve more word
recall than pruning harder? That is `keep=0.50 m=0.20 ink` against `keep=0.40 ink TWIN`, with
token-matching asserted from disk in both runs.

| | run 13 | run 14 |
|---|---|---|
| **pre-registered primary**, M=1920 matched | **+1.66 [−0.81, +4.14]** | **+0.02 [−1.90, +1.94]** |
| resolution (CI half-width) | 2.48 pts | 1.92 pts |
| verdict | **UNDERPOWERED** | **UNDERPOWERED** |
| confirmatory quantities surviving Holm | **0 of 3** | **0 of 3** |

**`UNDERPOWERED` licenses nothing** — not "merging is free", not "no measured cost", not even
"merging changes nothing". The required resolution needs **n ≳ 307 documents**. FUNSD test is
**50, and that is the entire split**, so `n` was never a knob to turn.

Three findings make this stronger than a null, and each cuts against the claim being replaced:

1. **"Free" is robust to neither the estimator nor the replicate.** Claim 3's own row
   (`keep=0.50 m=0.20 router` vs `keep=0.50 router`, M=1920 vs M=2400) is **+0.54** as a plain
   mean, **−0.65** under the pre-registered trimmed mean, and **+0.16** in run 14. Every one is
   a null, so "no measured cost" survives — but the *sign* flips both ways, and only the
   estimator direction was on record before.
2. **The −3.86 price is unreplicated, which is a different defect from being wrong.** The
   pre-registered estimator gives **−3.23 [−5.70, −0.76]** in run 13 (excludes zero) and
   **−0.17 [−2.40, +2.06]** in run 14 (includes zero). The old sentence called *resolved*
   something one of two runs denies.
3. **The corpus-average null is not a statement about an arbitrary page, and both location
   estimators hide that.** Run 14's M=1440 row contains a document that lost **72.34 points**.
   The plain mean hides it because 72/50 ≈ 1.4 pts sits inside the resolution; the trimmed mean
   is blind to it **to the last bit** — pushing that page 25 pts further moves the estimate by
   exactly `0.0e+00`, while the plain mean moves −0.50, which is **181% of the row's own
   effect**. A pre-registered *tail* gate surfaces it (worst-document ratio 5.01 against a
   matched-null p95 of 1.74); the harmed-count gate does not (4 against p95 6). So **one** gate
   catches it, not both — and surfacing is not attributing: the same gate fires on **13 of 21**
   contrasts where **nothing is merged at all**, and the worst per-document loss in the whole
   sweep (**−80.85 pts**) belongs to a row with `merge_ratio=0`.

**Scope of this restatement: 2 of the 3 confirmatory quantities.** Recall and NED≡charAcc are
scored; **`word_order` is not on disk for runs 13/14 and is not derivable** — `per_image` stores
only the row-level aggregate, while the metric needs the raw predicted and gold word
*sequences*, and neither recall (set-valued, order-blind) nor NED (character-level) determines
it. Holm is still run over a family of **three**, so the thresholds are the conservative ones.
This is a limit of the back-scoring, not of the rule.

**The axis is now closed.** The experiment that would have reached n ≳ 307 was built and
verified — a 29-row pooled sweep with the structure-matched `random` arm at M=1920 that runs
13/14 could not supply, five verifiers green, cost measured at 5.92 h against a 9 h cap — and
**never ran, for want of a corpus with a licence anyone could read.** The official ICDAR SROIE
archive is on disk and measured (pooled **n=410**, grain 0.75 pt/word), and contains no licence,
terms or citation file in any of its 4,226 entries; the terms exist only on a host that serves a
certificate for a different domain. Of the alternatives, the one with clean first-party
licensing annotates only a key-value subset of each page rather than the page (grain 4.24
pt/word, 4.2× coarser than the effect being resolved), and the one with the right annotations
carries a bare uploader-asserted licence with no attribution to the competition that produced
the scans — and was later found to match the official ground truth exactly on only 52 of 347
documents.

So the honest terminal result is the one the pre-registration named in advance for this exact
case: **`UNDERPOWERED`, with the required `n` quoted beside it.** The memory claim in §1 is
unaffected and stands; note only that of the 2.50× at M=1920, **pruning supplies 2.0× and the
merge step alone is 1.25×**, so the headline ratio is not a merging result.

Two things this result is **not**. It is not a latency or encoder-side win: the merger runs
*after* the frozen Swin, exactly like the router, so every scope limit in §2 applies to it
unchanged. And the ordering fix must not be quoted as an accuracy improvement — its
`49.2%/50.5% → 0.0%/0.0%` missed-redundancy figure is a claim about the *partition*, and the
head-to-head against the old score-rank split is **null on three checkpoints**, with the old
split numerically higher all three times (run 12 on run-5 weights: −1.51 [−3.22, +0.19],
resolution 1.7 pts; run 13 on run-9 weights: −0.29 [−3.10, +2.76], resolution 2.9 pts; run 14
on merge-trained weights: −0.88 [−5.26, +3.37], resolution 4.3 pts, Wilcoxon p=0.85). The fix
is correct about the partition and unproven about recall; it stays because merging spatial
neighbours is the defensible design, not because it was measured to help. *(Third checkpoint
added 2026-09-21; run 14 was the pre-registered closing test and it closed as a null.)*

**No cross-venue absolute comparison,** per §1.

**Two auxiliary objectives were tried and both are closed.** Supervising the router on
retained ink harder made accuracy *worse* (three independent lines agree). Supervising it on
a frozen decoder's cross-attention had the best *pre-run* evidence of any auxiliary tried
here — a held-out probe of the router's own architecture recovered **0.896** of the teacher's
attention mass at K, against the teacher's own ceiling of 0.910 — and that evidence was
labelled **reachability, not merit** before the run, precisely because it was scored against
the teacher. The run then moved accuracy not at all at slack budgets and **lost** at tight
ones (−5.63 at keep=0.25, −12.81 at keep=0.20). The
mechanism is legible: that router retains 0.257 of the page's ink against random's 0.201, so
it is near-ink-agnostic — harmless while the budget is slack, ruinous once every token must
carry text.

---

## 6. How these claims are defended

The verification layer is a deliberate part of this project, and several of its best findings
came from there rather than from GPU time.

**Diagnostics re-derive their numbers from cached artifacts,** so any claim can be rechecked
on a CPU without a training run. Several falsified the hypothesis they were built to support:
the first inverted the plan it was meant to enable, the second overturned the first's
recommendation in under a second, and the "why does pruning help" run rejected the guess this
project had carried for a week. The KV-memory script's pre-written framing — "a large cut in a
small quantity" — was falsified by its own output at 19.46%, and the script now derives that
sentence from the measurement instead of asserting it.

**Patches must be shown to run, not to parse.** Every notebook edit goes through a patcher
that backs up first, asserts each anchor matches exactly once, and `ast.parse`s the result;
every patcher has a companion that **executes the real cell** against stubs. The training
loop, the loss block, the mid-run weight-swap control, and the results writer are all covered
this way. Three correctness defects were found here rather than by a run failing: a decoding
setting that capped output at 71% of gold length, the `keep_ratio=1.0` STE trap, and a loss
that fed a probability to a logits-expecting BCE.

**Controls are chosen so they can fail.** One acceptance gate was moved off a recall delta —
which passed on two images, where the estimate is noise — and onto retained ink, which is
near-deterministic given the weights; it then matched the reference to three decimals on six
gates. When a mid-flight anchor was found to be comparing a local level to a remote one, its
replacement was pinned to **a number that did not yet exist** (run 9 at keep=1.00 must
reproduce 77.62 within 0.5 pts) and came back at gap 0.00. The weight-swap control asserts a
full-state-dict fingerprint before and after, because a silently failed restore would put
every subsequent row on the wrong checkpoint while producing a table that looks ordinary.

**Green checks get the same suspicion as red ones.** Before a passing check is trusted, the
question asked is what a *failing* system would score on it; if the answer is "about the
same", the check is decorative and gets rebuilt. The results writer's provenance stamp is the
most recent example: its verifier stamps a file, mutates that file, re-stamps it, and requires
the two stamps to differ — an implementation that echoed its argument instead of reading disk
passes every "is the field present" check and still permits the misattribution the stamp
exists to prevent.

---

## 7. Limitations, and what would close them

| limitation | status | what would close it |
|---|---|---|
| ~~H1 is supported but **not isolated** — five extra epochs are confounded with pruning-aware training~~ **H1 WAS ISOLATED by run 11** *(row corrected 2026-10-05; it had been stale since 2026-09-14)* | ~~known before the run; stated in the script's docstring~~ **Closed.** Run 11 is run 9 with `TRAIN_KEEP_RATIO` 0.50 → 1.00 and nothing else changed (verified by notebook diff) — i.e. the five epochs *without* the pruning. `ISO(0.35) = −10.49 pts` (t −3.74, n=50 paired): run 11's curve peaks unpruned and declines monotonically where run 9's is flat, and five unpruned epochs moved the ceiling by only **+0.52 pts** (t 0.24). So the gain is attributable to pruning-aware training, **not** to the extra epochs | **Nothing — it ran.** ⚠ One limit stands: isolated at keep=0.35/0.25/0.20 (−8.15 / −7.35 / −7.92, every t at or beyond −2.70 locally); the **loose** budgets are **underpowered, not null**. Write "H1 isolated at keep=0.35/0.25/0.20", never "H1 proven" |
| ~~Token merging has never executed~~ **Token merging was measured off-distribution** *(row corrected 2026-09-18)*, ~~**and the in-distribution re-measure came back underpowered** *(2026-09-21)*~~ **and under the pre-registration it is UNDERPOWERED in both runs — axis CLOSED 2026-10-05** | ~~the parity diagnostic says it cannot work as documented under score-order~~ the ordering was fixed and the merger ran as **run 13**: ~~20% merge is free at four budgets, 40% costs **−3.86 pts [−7.45, −0.30]**~~ *(both verdicts retired 2026-09-24 — the figures reproduce, the words did not survive the estimator)*. ~~But every checkpoint was trained at `merge_ratio=0.0`, so this is the off-distribution case~~ **Run 14 trained at `TRAIN_MERGE_RATIO=0.40` and took that contrast to −0.28 [−4.46, +3.44] — flat, but res 3.95 vs a 3.6 bar, so UNDERPOWERED, and the interval still contains −3.86. The same checkpoint gained as much on a random unmerged selection (+3.43 vs +3.11, diff −0.32 p=0.60), and NED degraded significantly (p=0.029) while recall did not.** Re-scored under the pre-registered estimator the **token-matched** primary at M=1920 is **+1.66 [−0.81, +4.14]** (run 13) and **+0.02 [−1.90, +1.94]** (run 14), **0 of 3 quantities surviving Holm in either** — see §5's third correction | ~~Not run 14 again at n=50~~ **`n ≳ 307` documents, and it was never collected.** `n` is not a knob — 50 *is* FUNSD test. The pooled 29-row sweep that would have reached it (with the structure-matched `random` arm at M=1920 that runs 13/14 lack) was **built, verified green, and never run: no corpus with a licence anyone could read.** **2.5× at M=1920 stays the measured limit**, of which pruning supplies 2.0× and merging 1.25× |
| Local and Kaggle generation diverge, widening with tightness | characterised, and the reason every claim here is a paired within-venue delta | not chased; recorded as a limitation |
| ~18% of predictions are still not valid JSON | measured as a rate only, never characterised | error analysis. Predictions are deliberately never repaired before scoring |
| The unpruned ceiling moves between retrains — 1.09 and 1.30 pts on two runs, **10.93** on a third — and on runs 7–8 that drift cannot be separated from a harness fault | why every comparison here is within-checkpoint; run 9 onward re-evaluates the unchanged run-5 weights through the same harness first, which makes the question decidable | more seeds; runs 7–8 stay ambiguous retroactively — no control can be added to a run that already happened |
| n = 50 test images | drives the ≈2.8 pt resolution on the free rows | a larger eval set; the current n is enough for the effects claimed and is stated wherever it is not |

**One number to take away.** At keep=0.35, a checkpoint trained for it gives up 65% of its
visual tokens and 65% of its decoder cross-attention KV for −0.26 ± 1.41 pts of word recall.
The same operation on a checkpoint not trained for it costs 6.03 pts. The difference between
those two sentences is the result.
