# AGENTS-ARCHIVE-RUNS.md — corpus decision, re-scoring, Pending history, runs 11–14

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**.
This archive has **no numeric audit** — when a figure is corrected in `AGENTS.md`, grep here
for the old value.

Holds: the **corpus decision (T2)**, the **runs 13/14 re-scoring under the run-17 rule (T3)**,
the whole `## Pending` item history (items 1–19, almost all closed, kept because the *reasons*
they closed are the content), the **run 11/12/13/14 launch checklists and results**, and
Phase 2c / Phase 2d.

⚠ The live queue is **not** here. `AGENTS.md`'s `▶ TODO` section (T1–T8) is the execution
order; the `OPEN ITEMS` table in this file is the *detail* behind those items and its priority
ordering was superseded by D13. Do not start work from this file.

---

## Corpus decision (T2) — 2026-09-24, every number below confirmed by loading

**The second corpus is `sizhkhy/SROIE`, test split, `n = 347`. Pooled with FUNSD's 50 that
is 397, which clears T1 §6's `n ≳ 307`. CORD is verified, licensed, and excluded.**

D13 guessed "~100 CORD, ~347 SROIE" from general knowledge. Both guesses were right. Both
were still guesses, and **the thing that decided this task was in neither number.**

### 1. What was checked, and why file-counting was not enough

T2's DONE-WHEN says *confirmed by loading*. That wording earned its keep three times:

| candidate | licence | test split | images? | `words` field | verdict |
|---|---|---|---|---|---|
| `buthaya/sroie` | `mit` | 347 annotation files | **0 images in the whole repo** | line segments | **unusable** |
| `haocf/SROIE2019` | `mit` | 6066 rows | none — `text` only | — | unusable |
| `jsdnrs/ICDAR2019-SROIE` | `cc-by-4.0` | 361 | ✅ | **57% multi-word** | line-level |
| `vishu12121/ICDAR2019-SROIE` | `cc-by-4.0` | 361 | ✅ | byte-identical to `jsdnrs` | duplicate |
| **`sizhkhy/SROIE`** | `mit` | **347** | ✅ | **0/40411 multi-word** | **chosen** |
| `naver-clova-ix/cord-v2` | `cc-by-4.0` | **100** | ✅ | true word-level | excluded, §3 |

Three separate near-misses, each of which would have passed a shallower check:

- **`buthaya/sroie` has 347 test annotation files and zero images.** 974 JSONs, 3.6 MB, no
  `.jpg` anywhere in the repo tree. A file count says 347 — the canonical SROIE test size —
  and the pipeline is *image* → encoder → prune → merge → decoder, so there is nothing to
  run it on. **Counting files that match the expected number is not confirming a split.**
- **`buthaya` and `jsdnrs` both have a field literally named `words` that holds lines.**
  `['TAN CHAY YEE', 'OJC MARKETING SDN BHD', 'TEL:07-388 2218 FAX:07-388 8218', ...]` —
  57% of units are multi-word, and `bboxes` are per-*segment* (347/347 docs have
  `len(words)==len(boxes)`, which is exactly what makes the mismatch invisible). Scoring
  word recall on this silently shrinks the denominator ~2.1× and inflates the value of every
  unit by the same factor. **This is D14 §1b's denotation check, and the field name lies.**
- **`jsdnrs` and `vishu12121` report byte-identical split sizes** (354,338,486 train /
  214,928,929 test). Same upload twice. Two "independent" mirrors agreeing is not corroboration.

`sizhkhy/SROIE` was then loaded for real: **n=347**, `words` = `['R','KEDAI','PAPAN','YEW',
'CHUAN',...]`, **0 of 40,411 units contain whitespace**, **347/347 docs** have
`len(words)==len(bboxes)`, `images` present (doc0 932×2212), `ner_tags` present.

⚠ Note the mirrors **disagree about the test set**: 347 (`sizhkhy`, `buthaya`) vs 361
(`jsdnrs`/`vishu12121`). 347 is the canonical ICDAR-2019 task-1/2 test size. Recorded because
a 14-document discrepancy between re-uploads of "the same" corpus is a provenance signal.

### 2. The licence, stated at the right strength

`sizhkhy/SROIE` carries `license:mit`. **That tag is asserted by a third-party uploader, not
by the ICDAR 2019 competition organisers who hold the original terms.** The same is true of
`buthaya` (`mit`) and `jsdnrs` (`cc-by-4.0`) — three re-uploads of one corpus, three
uploader-asserted licences, and they do not agree with each other.

Across all 100 SROIE-matching datasets on HuggingFace: **77 carry no licence field at all**,
12 `other`, 5 `mit`, 3 `cc-by-4.0`, 2 `unknown`, 1 `openrail`.

**CORD is the only candidate whose licence comes from the original authors** —
`naver-clova-ix` is the publishing lab, and `cc-by-4.0` is theirs to grant.

So: T2's DONE-WHEN ("licence is checked") is met, and the honest finding is that **SROIE's
licence is checked and found to be second-hand.** That is a publication question, not a
measurement question, and it is **the user's call, not mine.** Nothing downstream is blocked;
if the answer is "not acceptable", the fallback is CORD at n=100 — which by §3 cannot be
pooled, so the pool would be FUNSD-only at n=50 and T1 §7's `UNDERPOWERED` becomes permanent.

### 3. Why CORD is excluded — denotation, not size

The tempting reason to drop CORD is that FUNSD+CORD = 150 < 307. **That reason is wrong, or
at least not the operative one**, and recording the wrong reason would leave the real hazard
live for anyone who later finds 200 more receipts.

**CORD's ground truth covers only the annotated key-value fields, not the page.** Every
`valid_line` carries a `category`: doc0's are `menu.nm`, `menu.num`, `menu.price`,
`sub_total.tax_price`, `total.total_price`, … The store name, address, and phone number are
on the receipt and **not in the ground truth**. FUNSD and SROIE transcribe the whole page.

So `recall` on CORD and `recall` on FUNSD/SROIE are **different quantities wearing one name**:
recall-over-annotated-fields vs recall-over-page. Pooling them averages two metrics.

The grain follows from that, and it is severe:

| corpus | n | GT scope | words/doc (median) | one word = | docs where 1 word > 10 pt |
|---|---|---|---|---|---|
| FUNSD | 50 | whole page | 177 | 0.57 pt | 0/50 |
| **SROIE** | **347** | whole page | **109** | **0.92 pt** | **0/347** |
| CORD | 100 | annotated fields | **20** | **5.00 pt** | **4/100** |

CORD's smallest possible non-zero move is **5.00 pts median (max 12.50)** against T1's
**1.0 pt MDE** — the metric cannot resolve the effect being measured, because it cannot
*express* it. And **4/100 CORD documents trip T1 §3's −10.0 pt harm threshold on a single
wrong word.**

SROIE, by contrast, sits next to FUNSD: 0.92 vs 0.57 pt per word, **1.62×** apart, and
**0/347** one-word-over-threshold. CORD is **8.82×** FUNSD. **T1's point-denominated
thresholds are portable across FUNSD+SROIE and are not portable to CORD.** That is the
finding; the size shortfall was a coincidence.

⚠ **A sharper-sounding version of this was wrong and is recorded rather than deleted.** The
first draft said *"13/100 CORD documents can land exactly on −10.000000, vs 9/50 FUNSD"* —
implying the tie convention (D14 §6) is a CORD-specific hazard. Both counts were wrong, and
the framing was worse than the counts. Measured: **CORD 17/100, FUNSD 7/50, SROIE 27/347** —
exact ties exist everywhere, because they only require `n ≡ 0 (mod 10)`. (The first draft's
test asked whether `1000/n` is an integer, which tests whether *n divides 1000* — a different
and much rarer condition that happens to be satisfiable, so it returned a plausible number.)
**What is genuinely CORD-specific is how many words it takes to reach the tie:** on a 20-word
receipt, exactly **2 wrong words** land on −10.000000; on a 180-word form it takes **18**. The
tie is reachable by an ordinary single-document event on CORD and effectively unreachable on
FUNSD. That is the real asymmetry, and the count never showed it.


⚠ Both CORD and SROIE are **receipts** and they differ 5.4× in words/doc (20 vs 109). Same
domain, opposite grain. The difference is the annotation scope, not the imagery — which is
the cleanest possible demonstration that *"is it the same kind of document"* is the wrong
question to ask about corpus compatibility, and *"does the metric denote the same thing"* is
the right one. D14 §6 item 2 (thresholds carry units) extends to: **thresholds carry a
denominator, and the denominator is a property of the annotation, not of the images.**

### 4. What this obliges, and what it does not

- **T4 pools FUNSD + SROIE = 397 only.** CORD may be reported as a **separate row with its
  own thresholds**, never inside the pool. Keep FUNSD-only rows so runs 2–14 stay comparable.
- **The distribution-shift caveat T2 was required to record:** receipts are not forms. FUNSD
  is 50 forms at 177 words/doc; SROIE is 347 receipts at 109. The pool is **87.4% receipts by
  document count and 82.2% by word count** (49,140 words total) — so a "pooled" result is
  substantially a receipt result, and FUNSD is a **12.6%** minority in its own successor
  corpus. Report per-corpus **and** pooled, and never let the pooled number stand alone.
- ⚠ **This collides with D14 §4 / T1 §5.** At pooled n=397 a g=0.10 trim discards **39 per
  tail**; FUNSD's entire contribution is 50 documents. The discard set is now *smaller* than
  FUNSD rather than equal to it, so the "T1 × T4 can delete FUNSD" hazard is **reduced but
  not eliminated** — 39 of 50 is still 78% of the only corpus measured to date. T1 §5's
  per-corpus constraint is what prevents it and must actually be implemented in T4's scorer,
  not just written here.
- ⚠ **T1 §3's null p95 at `n=397` (=1.51) was simulated before this task confirmed 397.**
  The pre-registration assumed this answer. It was right, but re-derive the p95 against the
  loaded pool before run 17 scores anything, rather than inheriting a number that was written
  against an unverified size.
- **Not obliged:** nothing here licenses re-opening T1's primary contrast or its thresholds
  in points. The thresholds are portable to the corpus actually chosen. They are recorded as
  non-portable to CORD so that a future "let's add CORD for more n" is caught at design time.

**Artifacts:** `scripts/verify_corpus_grain.py` — **21/21 controls, exit 0**,
`results/corpus_grain_local.log`. Every number in this section is printed by that script
from a loaded dataset object; nothing here is prose-only. Section 4 of the script audits
this section's own first draft and its two controls assert the draft was wrong.
Reproduce with `python scripts/verify_corpus_grain.py`.

⚠ **One loose claim, corrected here rather than in the script:** CORD's `words` is *mostly*
word-level but not perfectly — **35/2356 units (1.49%)** contain whitespace, and FUNSD has
**19/8707 (0.22%)**. Only SROIE is exactly **0/40411**. Immaterial to the decision (CORD is
excluded on denotation regardless) but "true word-level" was too strong for CORD.

## Runs 13/14 re-scored under the run-17 rule (T3) — 2026-09-24, local, 45/45 controls

**Artifacts:** `scripts/score_preregistered.py` — **45/45 controls, exit 0**,
`results/score_preregistered_local.log`. This is the **executable** form of T1 §§2–7, which
existed only as prose until now. Reproduce with `python scripts/score_preregistered.py`;
`--selftest` runs the same controls and is what CI should call.

**The headline: the pre-registered primary scores `UNDERPOWERED` in both runs, and the three
things T3 was asked to file are all confirmed — plus three that were not on the list.**

### 1. Calibration — the scorer reproduces figures T1 wrote before it existed

T1 §3 quoted observed numbers from an ad-hoc probe. Those are the calibration targets, and
they are checked **before** anything new is computed, because a scorer that disagrees with the
rule it implements is the failure that matters:

| target (from T1, pre-dating this file) | reproduced |
|---|---|
| run 14 contrast-A trimmed mean **+0.02** | **+0.0176** |
| worst document **−40.00** | −40.00 |
| matched-null expectation **−12.43** | −12.43 |
| worst-document ratio **3.22** | 3.219 |
| harmed counts **5** (run 14) / **4** (run 13) | 5 / 4 |
| `res` **2.48** (run 13) / **1.92** (run 14) | 2.477 / 1.919 |
| ratio null at n=50: median **1.20**, p95 **1.74** | 1.20 / 1.74 |
| ratio null p95 at n=307 **1.52**, n=397 **1.51** | 1.530 / 1.512 |
| `n` required for `res ≤ 1.0` = **307** | 307 |

The last three matter more than the rest: the bar **tightens** as `n` grows, which a constant
threshold could not do. That is the check that distinguishes a simulated null from a number
typed in and called one (D14 §10).

### 2. Eight discriminating controls — does each pinned choice change the answer?

A rule is only worth pinning if unpinning it moves something. Each of T1's choices was
re-measured against its plausible alternative:

| pinned choice | the alternative | measured gap |
|---|---|---|
| Tukey–McLaughlin SE | `stdev(trimmed)/√n_trimmed` | naive SE is **35% smaller** (0.6383 vs 0.9792) |
| difference-then-trim | trim-then-difference | **+0.2555 pts** apart… |
| …and the same comparison on the **plain** mean | — | **−8.55e-15**, i.e. identically zero — so the non-additivity is a property of *trimming*, not of the data |
| `ned` sign-flipped | as stored | worst flips **−23.50 → −29.66**, mean **+1.70 → −1.70** |
| thresholds in **points** | on the stored `[0,1]` field | harm rule counts **0** vs **5** — D14 §1d's unfalsifiable gate cannot recur here |
| matched null per row | one constant bar | harmed-count p95 is **7** on run 13 and **4** on run 14 *for the same rule*, because run 13's spread is wider |

Two further controls exist so the gate itself is not decorative: the ratio gate **fires on run
14 (3.22 > 1.74) and does not on run 13 (1.11 < 1.74)** — a gate that fired on both or neither
would be untested by this pair — and **run 14's contrast A is flat on location (CI [−1.90,
+1.94]) yet fails a tail gate**, which is the exact case T1 §3 was written to catch.

> **Consequence for reporting: harmed counts are not comparable across rows.** The bar depends
> on the row's own `winsorized_sd`, so "5 harmed" is worse than "10 harmed" if the first row is
> tighter. Always quote the count with its null.

### 3. The pre-registered primary — `keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN`, M=1920

| run | quantity | trimmed | 95% CI | res | worst / null (ratio vs p95 1.74) | harmed / p95 | verdict |
|---|---|---|---|---|---|---|---|
| 13 | recall | **+1.66** | [−0.81, +4.14] | 2.48 | −17.78 / −16.03 (**1.11** ✅) | 4 / 7 ✅ | **UNDERPOWERED** |
| 13 | ned | +0.61 | [−2.02, +3.23] | 2.62 | −18.20 / −16.98 (**1.07** ✅) | 6 / 8 ✅ | |
| 14 | recall | **+0.02** | [−1.90, +1.94] | 1.92 | −40.00 / −12.43 (**3.22** ❌) | 5 / 4 ❌ | **UNDERPOWERED** |
| 14 | ned | −1.70 | [−4.98, +1.58] | 3.28 | −29.66 / −21.23 (**1.40** ✅) | 10 / 12 ✅ | |

**Run 14 is not scored `FREE` despite the cleanest imaginable null (+0.02 pts).** Both of its
recall tail gates fail. That single behaviour is the whole reason T1 §3 exists, and it is now
demonstrated rather than asserted. **Zero confirmatory quantities survive Holm in either
run** — independently consistent with D14 §1d's finding of zero survivors over the wider
12-test family.

`UNDERPOWERED` **licenses nothing**: not "merging is free", not "no measured cost". T1 §7 says
to report the required `n` instead, which is **307**; T2's pooled 397 clears it.

### 4. Claim 3's own rows — scored apart, never pooled

Claim 3's figures are **same-keep-fraction router** rows (merge vs *no* merge). The
pre-registered primary is a **token-matched ink** pair (merge vs *prune harder*). Different
questions; pooling them is D14 §1b's 5.08 pt hazard:

| row | run | plain | trimmed | res | 95% CI | worst | ratio |
|---|---|---|---|---|---|---|---|
| m=0.20 vs no-merge | 13 | **+0.54** | **−0.65** | 1.72 | [−2.36, +1.07] | −22.45 | 2.02 |
| m=0.20 vs no-merge | 14 | −1.12 | **+0.16** | 1.55 | [−1.38, +1.71] | −53.06 | 5.29 |
| m=0.40 vs no-merge | 13 | **−3.86** | **−3.23** | 2.47 | [−5.70, −0.76] | −56.98 | 3.56 |
| m=0.40 vs no-merge | 14 | −0.28 | **−0.17** | 2.23 | [−2.40, +2.06] | −72.34 | 5.01 |

**Caveat (i), as T3 required it — and one direction more.** +0.54 is the plain mean; T1's
estimator gives −0.65 on the same row. Both are nulls, so "no measured cost" **survives** the
estimator change. **Not in T3's caveat list:** the same row is **+0.16 in run 14**, so the sign
is not *run*-robust either. "Free" is fragile in two directions and only one was on record.

**Caveat (ii), as T3 required it.** The −72.34 pt page is in **run 14's m=0.40 row** — claim
3's own M=1440 contrast, not contrast A. The plain mean hides it (−0.28 against res 2.23) and
the trimmed mean is blind **to the last bit**: pushing that page 25 pts further moves the
trimmed mean by exactly `0.0e+00`, while the plain mean moves −0.50 — **181% of the row's own
effect**. T1 §3's worst-document gate **does surface it** (5.01 vs 1.74). Its **harmed-count
gate does not** (4 vs p95 6). So **do not write "the tail gates catch it" plural**, and read
the one that fires as *"the page is visible"*, not *"merging caused it"* — see §6.

### 5. Two findings T3 did not ask for

**(a) "Resolved and negative" does not replicate.** Claim 3 forbids quoting 3.33× without its
price, "−3.86 pts [−7.45, −0.30], resolved and negative". Run 13 does give **−3.23
[−5.70, −0.76]** (excludes zero) and its plain mean reproduces **−3.86 exactly** — so this is
not an artifact of re-deriving. But **run 14 gives −0.17 [−2.40, +2.06]**, which includes zero.
The sentence stated as *resolved* something one of two runs denies. 3.33× stays unlicensed;
the reason changes from "resolved and negative" to **"unreplicated"**.

**(b) The sentence pairs two baselines.** Token counts on disk: keep=1.00 → M=4800, keep=0.50
→ M=2400, keep=0.50+m=0.20 → M=1920.

- `150.00 → 60.00 MiB (2.50×)` is `4800/1920 = 2.5000` → baseline **keep=1.00**
- the `+0.54`'s control row is `M=2400` → baseline **keep=0.50**; `2400/1920 = 1.25×`
- `3.33×` is `4800/1440` → also keep=1.00

So a **prune+merge memory ratio** was quoted with a **merge-only accuracy delta**. The merge
step alone buys **1.25×**; the remaining 2.0× is pruning, whose accuracy delta is a separate
measurement. On a consistent keep=1.00 baseline:

| contrast | run 13 | run 14 |
|---|---|---|
| prune+merge vs keep=1.00 | **+2.29** [−0.44, +5.01], res 2.72 | +0.09 [−2.21, +2.39], res 2.30 |
| prune only vs keep=1.00 | +1.35 [−0.61, +3.31], res 1.96 | +0.19 [−2.20, +2.59], res 2.40 |

> **The direction is asserted as a control so this cannot be filed as a flattering finding.**
> Fixing the mismatch makes the number **better** (+2.29 vs +0.54), so it is a **consistency
> defect, not an inflated result** — and it changes **no verdict**: both runs stay null on the
> consistent baseline. The fix is to the *sentence*; no downstream number moves.

### 6. The tail gate is not specific to merging — D13 §5's untreated control, finally run

D13 §5 established that both location estimators hide the −72 pt page, and T1 §3 answered with
the tail gates. **Nobody ever checked whether the gates fire on rows with no merging.** They
do. Scored as a checkpoint DiD (run 14 − run 13, the direction the design forces), against the
same n=50 normal-null p95 of 1.74:

| config | worst | wsd | ratio | merge |
|---|---|---|---|---|
| `keep=0.75 ink ORACLE` | **−80.85** | 6.63 | **5.43** | **NONE** |
| `keep=0.75 random` | −80.85 | 6.75 | 5.34 | **NONE** |
| `keep=0.50 m=0.40 router` | −74.47 | 7.18 | 4.62 | m=0.40 |
| `keep=1.00 m=0.20 router` | −45.26 | 4.43 | 4.56 | m=0.20 |
| `keep=0.50 m=0.20 router` | −50.00 | 6.53 | 3.41 | m=0.20 |
| `keep=0.80 router TWIN` | −33.68 | 4.53 | 3.32 | **NONE** |

**Rows with no merging: 13 of 21 fire. Rows with merging: 6 of 7.** And the **single worst
per-document loss in the entire sweep is −80.85 pts on `keep=0.75 ink ORACLE` — keep=0.75,
m=0, nothing merged — carrying the highest ratio in the sweep (5.43), above every merge row
(max 4.62)**. It is not a small-denominator artifact: its winsorized sd is 6.63, in line with
the sweep, so the ratio is driven by a real 81 pt loss.

Three things keep this from being an indictment of the gate:

1. **The failure is specificity, not sensitivity.** The one comparator with *neither* pruning
   nor merging (`keep=1.00 router CONTROL`) **passes at 1.47** — the gate is not firing on
   literally everything.
2. **There is no zero-treatment null on disk to calibrate against.** No config is evaluated
   twice within either run (28 and 28 rows, all distinct), and decoding is **bit-identical on
   re-run** (noise floor `0.000e+00`), so a same-config replicate would be degenerate anyway.
   Runs 13 and 14 differ by a **retrained checkpoint**, so cross-run pairs carry a real
   treatment and are not a null either.
3. **The gate is not reversal-invariant.** `min(d)` is one-sided, so swapping which arm is
   "treatment" **flips the verdict on 10 of 28 configs**. T1 §3 pins direction per *quantity*
   and leaves the direction of the *contrast* unwritten — a genuine remaining DoF.

> **What this costs run 17.** As written, run 17 would **fail this gate on rows where nothing
> is merged**, and clearing 1.74 would not be evidence about merging. The bar has to come from
> an **active non-merge comparator** — the `random` arm at the trained budget that run 17
> already requires and that **D14 measured as absent from both runs**. **T3's fix and T4's
> missing arm are the same row.** Amendment filed into T1 §3.

**What T3 does not license.** It does not overturn claim 3's corpus-average null, which is
true. It does not attribute the −72.34 or the −80.85 page to merging — §6 is precisely the
reason it cannot. And it does not turn `UNDERPOWERED` into a negative result: the instrument is
too coarse at n=50, which is T4's job, not evidence about the merger.

## Pending


### OPEN ITEMS AS OF 2026-09-22 — read this before the item history below

Items 1–13 below are **almost entirely closed**, and their text is a long record of *how*
they closed rather than a list of work to do. What is actually open:

> ⚠ **The priority order in this table is superseded.** It was written before D13, which
> found that items 16 and 17 are blocked by a problem neither of them addresses — the
> measurement instrument, not the merger. **The execution order lives in the TODO queue at
> the top of this file**; this table is the *detail* behind those items, not the order they
> run in. Mapping: **18 → T1**, **16 → T6**, **17 → T7**, `REPORT.md`/`README.md` → **T8**.
> Items 3 and 5 are not in the queue because neither is on the ToMe critical path.
> Do not start 16 or 17 from this table. Start from T1.

| # | item | venue / cost | why it is where it is in the order |
|---|---|---|---|
| **19** | **Raise eval `n` past 50 — pooled second corpus** | free (CPU), the unblock | **NEW 2026-09-22, = T2 + T4, and it is what everything else waits on.** Filed by D13: per-document sd is 11–13 pts, so n=50 gives res 2.9–4.3 against effects of 0.5–3.1. `n` was correctly recorded as "not a knob" *within FUNSD* — 50 **is** FUNSD test — but that was read as "not a knob at all" for three runs. It is a knob if the corpus changes. **n ≈ 500 → res ≈ 0.9–1.3**, which resolves every question ToMe can pose, including the m=0.20 "free" claim as a tight null. No GPU: the 28-row sweep is eval-only |
| **16** | **Train the symmetric checkpoint: `keep=0.30, merge=0.0`** | Kaggle T4, ≈4–4.5 h | **= T6. BLOCKED BY T4 (D13) — do not run this next.** At n=50 this fixes the confound and leaves the power untouched, so the predicted outcome of 4–4.5 GPU-hours is a correctly-designed fourth UNDERPOWERED. **The blocker for every M=1440 claim.** Run 14 trained at keep=0.50/merge=0.40, so in the M=1440 token-matched pair the merge arm is on-distribution and the prune arm is not — and the prune twin's own cross-run delta (**−3.96, p=0.0499**) says the pair widened partly because the comparison arm got *worse*. Until this checkpoint exists, "merging beats pruning at matched M" has exactly one trained arm and cannot be claimed in either direction. Symmetric to the old Pending 14 (H1), and the same logic applies |
| **17** | **The redesigned merge run — a new design, not a re-run of 14** | Kaggle T4, eval-only ≈2–3 h once 16 exists | **= T7. BLOCKED BY T4 and T6.** D13 adds a fifth requirement to the four below: **(e)** the eval corpus must be the pooled one from T4, because at n=50 the design cannot resolve a 2-pt effect no matter how clean it is. Four requirements, all forced by run 14's scoring: **(a)** both checkpoints contrasted **in one session** — run 14's honest lever was never `n` (50 *is* FUNSD test) but the effect, i.e. the DiD that had to be computed across runs afterwards; **(b)** the primary pre-registered across **all three** testable quantities (recall, NED≡charAcc, word order) — *three*, not four, see the 2026-09-22 correction; **(c)** a **"did this checkpoint just improve at everything"** control — the cheapest is already in the sweep, the `random` row at the trained budget, whose absence is why run 14's +3.11 gain could not be shown to be merging-specific; **(d)** checkpoints for the DiD are **already on disk** — merge-naive is `run 9/adaptive_donut_pruned.pt` (what run 13 evaluated), merge-trained is `run14/adaptive_donut_pruned.pt` — so (a) needs **no training**, only item 16 does. **Cleared 2026-09-22:** this item presupposes ToMe stays in, which is the branch of Pending 15 that was never explicitly decided; it is now decided *keep*, on run 13's two uncontaminated token-matched wins rather than run 14's contaminated +5.78. Carry the caveat that came with it — `tome_split='checkerboard'` is the default at both call sites and has **never** beaten `rank_parity` on recall (−1.51 / −0.29 / −0.88 across runs 12/13/14), so the split is a free parameter in whatever run 17 reports, not a validated setting. Do **not** spend run-17 budget re-running that sabotage row: three nulls closed it |
| **18** | **Decide the bootstrap-vs-Wilcoxon rule *before* writing item 17's pre-registration** | free, but must precede 17 | **= T1, and it is now first in the queue.** D13 adds a third candidate — a 10% trimmed mean with a Tukey–McLaughlin SE, ~30% tighter for zero GPU time — and the rule must name one of the three. **Write it before run 17 sees a number**; the justification on record is D13's variance structure (5 of 50 docs = 75.6% of SS), never the sign of a contrast. Run 14 adjudicated the same disagreement two opposite ways eleven lines apart (see the 2026-09-22 correction): bootstrap governs on the DiD, Wilcoxon quietly governs in the four-metric table. With a three-quantity primary this stops being cosmetic — it decides the verdict. Write the rule, including the multiplicity treatment, into the checklist **before** any number is seen |
| — | ~~**per-image `char_acc` / `word_order` for a multi-metric primary**~~ | — | **DONE 2026-09-22.** Only `word_order` was a real gap; `char_acc` is `(1 − mean(ned)) × 100` and was always derivable. Generator patch **G3b**; `verify_tome_merge_port.py` **89/89** with four new controls, two of them mutation-tested. Also repaired `verify_results_provenance.py`, which had silently stopped covering the generated notebook — see the 2026-09-22 changelog entry |
| **3** | `nrns ∈ {3,4,6}` × `rp ∈ {1.0,1.05}` micro-sweep | local, ~76 min CPU | **RAN 2026-09-09, provenance settled 2026-09-14, default NOT changed — see the 2026-09-14 changelog entry.** One config survives everything: **rp=1.05/nrns=6, +4.74 pts recall, +2.06 charAcc, Holm p 0.0044**. Held back because the script's own monotonicity test fires and the measurement is on **run-5** weights. **Next step: re-measure the two rp=1.05 rows on the run-11 checkpoint**, then decide. `results/nrns_rp_sweep_aggregates_run2.json` is a **dead file** from a superseded script version — do not quote it |
| **5** | **The co-adaptation 2×2** | Kaggle T4, ~4 h | **Now optional.** It defends only the "beats the ink oracle" claim, and this file already instructs nobody to cite that claim. Dropping it costs one sentence of scope; testing it costs a GPU session and D6 suggests the margin may not survive. Full item text below |
| — | the unexplained **18% invalid JSON** | local | Measured only as a percentage; never characterised. Predictions are deliberately never repaired. (The sweep incidentally spreads 74–92% valid JSON across configs, which is a wider range than the recall effect it was testing — nobody has looked at why) |
| — | **local-vs-Kaggle generation drift** that widens as the budget tightens | — | **Not an experiment: a limitations paragraph.** It is why nothing in D11/D12 compares a local level to a Kaggle one. Record it in the writeup rather than chasing it |
| — | **Reconcile `REPORT.md` and `README.md` against runs 11–14** | local, ~30 min | **Filed 2026-09-17, still not done, and now one run staler.** `REPORT.md` carries a stale-as-of banner naming three wrong statements (H1 "not isolated" / Pending 14 open, "ToMe has never executed" / Pending 15 open, run table stopping at run 10); `README.md` is unchecked against any of runs 11–14. Do this in the same pass that propagates any figure corrected here into all four prose files — `WRITEUP.md` is the only one with an audit, and the 2026-09-17 entry records what that asymmetry already cost |

**Closed and needing no further action:** 1a, 1b, 1c (accuracy axis), 1d, 2, 4, 6, 7,
8 (all three options settled: (a) taken, (c) measured as M1, (b) untested and unattractive),
9, 10, 11, 12, 13(a) (dead, D7), 13(b) (dead, D11). Item 2 (reconcile `README.md`) was
done 2026-09-04 and re-done 2026-09-09; item 6 (provenance) was done 2026-09-09.

Also closed, and dropped from the table above on 2026-09-22 because their text had become a
record rather than a task — headline figures kept here, full detail in the run sections:

- **14 — isolate H1 (a run-5-length control trained WITHOUT pruning). DONE 2026-09-14, filed
  2026-09-15.** H1 **ISOLATED at keep=0.35**, `CONFOUNDED` rejected: `ISO(0.35) = −10.49`
  (t −3.74, n=50 paired); run 11's curve peaks at keep=1.00 and declines monotonically where
  run 9's is flat; five unpruned epochs bought **+0.52 pts (t 0.24)** at the ceiling. The
  statistic came out of the shipped `ablation_selection.json` `per_image` arrays — the two
  `eval_why_pruning_helps.py` invocations were **not** needed for the verdict, though they
  remain worth running at keep=0.25/0.20, which the Kaggle grid does not cover. See "Run 11 —
  result". **Item 16 above is this item's unbuilt mirror image**, on the merge axis.
- **15 — ToMe: settle the ordering question, *or scope ToMe out*. Option (b) DONE 2026-09-09,
  verified 2026-09-14; the scope-out branch answered 2026-09-22.** The checkerboard split
  landed in `src/tome.py` + `src/model.py`; vertical redundancy **100% → 0.0% missed**, holding
  under router sort; 13/13 tests, 10/10 parity properties. Accepted cost: diagonal redundancy
  now 100% missed. The merge sweep it was blocking has since executed three times (runs 12, 13,
  14). **The second branch of this item's title was never explicitly decided, so it is decided
  here: do NOT scope ToMe out.** The reason is run 13's token-matched table, and it is the one
  merge result in this project that is *not* contaminated by train/test matching — run 13 ran
  on run 9's weights, a checkpoint trained at `keep=0.50, merge=0.0` that had **never seen a
  merged token**, so every merge arm was off-distribution and the comparison was biased
  *against* merging. It still produced two significant wins: **M=3840 router +3.12 [+0.21,
  +6.05]** and **M=1344 ink +4.06 [+0.43, +8.05]**. Contrast run 14's M=1440 **+5.78**, which is
  contaminated in merging's favour and must not be quoted. Merging earns its place on run 13's
  evidence, not run 14's.
  > **What "scope ToMe out" would actually mean — written down because the natural reading of
  > it is wrong.** ToMe does **not** recombine pruned tokens; nothing in this architecture does.
  > `router.py` does `topk` + `gather` and the N−K losers are dereferenced on the spot; the
  > decoder receives `encoder_hidden_states=compressed_tokens` only, with no skip path. ToMe's
  > operand is the **survivor** tensor — both `A` and `B_set` are slices of it, and
  > `B_merged = (B_set + Tᵀ·A) / W_B` averages survivors into survivors. So removing ToMe
  > orphans nothing; it deletes the **second compression stage**, and any given decoder budget
  > M must then be reached by pruning harder.
  >
  > **Which is exactly what the Q6 token-matched pairs measure** — the reason this item could be
  > decided with no new run. Each pair is two routes to one M, and the prune-only twin *is* the
  > scoped-out architecture. At M=3840: the merge route `keep=1.00, m=0.20` carries content from
  > all **4800** patches, the prune route `keep=0.80` carries **3840** and discards 960 outright.
  > Same decoder cost, more of the page represented — the mechanism by which merging can win.
  > Note that winning row has `keep_ratio = 1.00`: it is **merge-only**, a configuration that
  > cannot exist once ToMe is gone.
  >
  > **And the bound — stated with its own counterexample, because the clean version is false.**
  > Merging averages two spatially adjacent patches into one embedding at one centroid coord,
  > which can smear fine text detail. In **router** mode run 13 decays monotonically with the
  > budget: M=3840 **+3.12 SIG**, M=1920 **+2.86** (ns), M=1440 **−1.29**, M=1344 **−0.22**. But
  > the **ink** row at the same M=1344 is **+4.06 SIG** — the largest win in the table sits at
  > the tightest budget. So the bound is not "merging stops helping when M is small"; it is
  > budget-**and**-selector dependent, and the one clean statement is that *router*-mode merging
  > has never been shown to help below M≈1920. This matters for Pending 16/17, whose whole
  > comparison is router mode at **M=1440** — the corner where run 13's merge arm was
  > numerically *worse*. Run 17 should expect a small or negative effect there and be powered
  > for it, not be surprised by one.
  > **The live residue, kept visible rather than buried in a closed item: the fix this item
  > delivered has never beaten the thing it replaced.** checkerboard − rank_parity at M=1920 is
  > **−1.51 / −0.29 / −0.88** across runs 12/13/14 — three checkpoints, three nulls, and
  > `rank_parity` numerically **higher all three times**. `tome_split='checkerboard'` is
  > nonetheless the default at both call sites of the generated notebook. So the default is
  > chosen on a **synthetic partition statistic** (missed-redundancy 49.2%/50.5% → 0.0%/0.0%)
  > and has never been shown to help recall. That is a defensible engineering choice — provably
  > correct partition, and the sabotage arm is closed as pre-registered — but it is **not** an
  > accuracy result, and nothing downstream should cite it as one.

**Explicitly do not do:** run 11 in the form sketched under item 13 (D11: the failure mode
is not specific to which target is used); tune `LAMBDA_SAL` (D6 invalidated that axis);
promote any proxy — retained ink, min line coverage, retained attention mass — to an
acceptance gate. There is **no validated cheap gate** for a router checkpoint; the gate is
an actual accuracy row against a random floor and an ink ceiling at the same budget.

---

**Run 7 (2026-08-30) + Run 8 (2026-08-31) completed 1a + 1b + 1d, and 1c only in part.**
Run 7 retrained the router with pruning ON (still sign-inverted; `strat_negated` worked as a
hack). Run 8 added an **ink-BCE saliency loss** that supervises the router with a free text proxy, and
the **forward `router` is now correctly signed** (80.17 recall at keep=0.50, 77.80 at keep=0.35) —
the accuracy-vs-tokens curve now uses the forward router directly.

**Revised by D3 (2026-08-31).** Three things above were overstated and are corrected here:
- ~~"beats the ink oracle at every keep_ratio"~~ — it out-*scores* the oracle, but the
  most likely cause is decoder co-adaptation to the trained `keep_ratio`, not better
  selection. See run 8's ADA table. Do not cite this as a selection-quality result.
- 1c is **not** complete: it asked for accuracy *and cost*. Cost was measured and the
  cost half fails — ~~`−65%` tokens is `−7%` wall-clock~~ **run 9 measures it as `−4.1%`,
  and `−50%` tokens as `−3.0%`** — because pruning is post-encoder. See Pending 8.
- The `keep=1.00` row of runs 7–8 is **not** a control (the weights changed), so 1c's
  "must reproduce 77.74 / 64.70 / 53.05" requirement is currently unmet, not met.
  **Met at run 9** by F2's second control: 77.74 / 64.70 / 53.05, drift 0.00 pts.

Remaining after D3: an **unchanged-weights control row**; the `merge_ratio` (ToMe) rows;
the unexplained `keep=0.50 > keep=0.75` bump; the co-adaptation test; provenance fields;
and one wrong note printed by cell 15's Q5. Items 4–8 below.

**Revised again by Run 9 + D6 (2026-09-01).** The control row is now **done and passing**
(item 4). Two further corrections:
- The `keep=0.50 > keep=0.75` bump **persists** in run 9 (79.63 vs 79.41) but has shrunk
  from run 8's 4.98 pts to 0.22 pts — within what a 50-image sample plausibly moves, so it
  is no longer clearly an anomaly needing explanation. It was never a robust effect; it was
  a 4.98 pt gap in a single run that a loss-config change collapsed.
- The item-5 co-adaptation test is **still required but its motivation has shifted**: D6
  shows the router's margin over the ink oracle moves ±5 pts on a loss-config change alone,
  so that margin cannot be read as selection quality in either direction.

1. **Fix the router's training signal, then run the sweep.** Diagnostic D1 changed
   the order of operations: the deliverable is no longer blocked on GPU time, it is
   blocked on the fact that the router ranks blank paper above text. Sweeping it
   as-is would produce a curve that is worse than random pruning and invite the
   wrong conclusion. Do these in order:

   **1a. Train with pruning ON — now mandatory, not optional.** This was an open
   design decision until D1; it is settled. The router has never once received
   gradient about the *consequence of removing* a token (`keep_ratio=1.0` ⇒ K=N ⇒
   STE multiplier is exactly 1.0), and what it learned instead is anti-correlated
   with ink at r ≈ −0.24. No amount of eval-only sweeping fixes a scorer that was
   optimised for the wrong question. Train at `keep_ratio` 0.5 (single config
   first, ~4 h — do **not** book 4 configs × 4 h before one works).
   **Do 1d first** (below): if a per-row budget rescues the *existing* scorer, this
   run is aimed at the wrong component. And per D2, if an auxiliary router loss is
   added at all it must **not** reward summed retained saliency — that is the exact
   statistic which ranks the negated router above random, i.e. which gets the
   measured ordering backwards. Worst-case coverage is the quantity to protect.

   **1b. Before that training run, spend 15 minutes on the free experiments D1
   opened up.** — **ANSWERED QUALITATIVELY (n=2/n=4, local CPU); n=50 MOVED TO KAGGLE
   (2026-08-29).** Mechanism landed as `select_mode` on `generate()`
   (`router` / `negated` / `random` / `ink`), which swaps the *ranking signal only* —
   K, architecture and decoder untouched, so rows are comparable at equal token
   budget. Verified by execution (`scripts/verify_select_modes.py`, all checks pass).
   Local harness is `scripts/eval_select_modes.py`; the n=50 run was **killed at
   30/50 of row 1** in favour of the Kaggle port (see Phase 2d and the venue decision
   under Current state). Both questions are already answered in *direction* — what
   n=50 buys is precision, not a different verdict.
   - **Negate the score** — n=2/n=4 say it beats the forward router (+4.2 / +26.0
     recall) but **loses to random by 21.3 / 14.4 pts** despite retaining more ink.
     D1's premise that ink-retention predicts accuracy is **falsified**; see
     Diagnostic D2. So negation is *not* the cheap fix D1 advertised.
   - **Ink-oracle upper bound row.** n=4: **83.66** recall at half the tokens vs
     **83.67** for the full page (−0.01; n=2 was 81.04 vs 82.61). The premise holds
     strongly — half these tokens really are droppable, and the headroom a trained
     router could reach is real. This was the row that could have killed 1a; it does
     the opposite.
   - Re-run `scripts/router_score_probe.py` on any new checkpoint. Section F is the
     acceptance test — but **D2 supersedes its threshold**: retained ink above
     random's ~0.50 is now known to be necessary-but-not-sufficient. ~~The gate a
     router must pass is **worst-case line coverage**, not summed ink.~~
     **D3 withdraws that replacement too (2026-08-31)**: min line coverage is the
     *weakest* of the four predictors on file, and two run-8 rows at equal min coverage
     differ by 29 pts of recall. There is no validated cheap gate right now — the probe
     is a smoke test for "is the scorer inverted", nothing more.

   **1d. NEW (from D2, do before 1a). Test whether the fix is architectural rather
   than a training-signal problem.** — **RUN AND ANSWERED: NO (runs 7–8).** A per-row
   budget is not the fix. On run 8's weights `stratified` loses to plain `router` by
   4.42 pts at keep=0.50 *while holding strictly better worst-case coverage* — which is
   simultaneously the answer to 1d and half of the evidence that retired the
   min-coverage gate. The mechanism is sound and verified (17/17); it just is not what
   was limiting recall. Keep the modes: they are the cheapest available probe of
   "selection rule vs scorer" and they earned their keep by answering in the negative.
   Original reasoning, retained because the *test* was right even though the hypothesis
   was wrong: D2 found the router's *minimum* line coverage is 0.000 — at least
   one text line loses all its ink — and that a single global top-k has no mechanism
   preventing that. If a per-row budget alone lifts the router row substantially, the
   bug is the **selection rule**, not the scorer, and 4 GPU-hours of retraining a
   per-token scorer is aimed at the wrong component.

   Landed as two more `select_mode` values, `stratified` and `stratified_negated`,
   via `stratified_scores()` in `src/model.py`. **No change to `router.py`**: a
   per-row top-k is expressed as a monotone rewrite of the ranking signal —
   `key = (gw − within_row_rank) + normalized_score`, where the integer rank
   dominates and the score only breaks ties inside a band — so a *global* top-K on
   the key is exactly a *per-row* top-k, and it reuses the already-verified
   `select_scores` path rather than adding a second selection code path that could
   drift from the first. Stratification and sign are deliberately orthogonal, so
   "coverage" and "the scorer is inverted" can be attributed separately.

   `scripts/verify_stratified.py`, 17/17 pass, checked against an **independent
   reference implementation** (an explicit per-row `topk` loop) rather than a
   restatement of the same arithmetic — this is a claim that would fail by one rank
   band and still produce a plausible mask. Also confirmed on an adversarial fixture
   that a global top-k really does hand one hot row the entire budget (6/6 of its
   tokens) while stratification holds every row to exactly k, and that min row
   coverage goes **0.000 → 0.492** where a global top-k starves a line.
   Caveat recorded in the script: that fixture's ink is column-uniform, so it tests
   the coverage guarantee only and *cannot* say whether the sign matters — the
   near-tie between `stratified` (0.492) and `stratified_negated` (0.503) is a
   fixture artifact, not a finding.

   **Bound on when 1d can possibly help, found by getting a verifier fixture wrong.**
   A global top-k can only drive a row to *zero* coverage when the region it prefers
   is **at least as large as the budget**. A first fixture made 5 of 80 grid rows
   hot — 300 tokens against a budget of K=2400 — and no row starved (the emptiest kept
   21), because 2100 tokens still had to land somewhere. So stratification is not a
   general win: at `keep_ratio=0.5` it can only help if the router is concentrating
   ~half the page into a sub-region. D2 measured exactly that (min line coverage
   0.000 on real pages), so the condition *is* met here — but this is the thing to
   re-check first if the 1d rows come back flat, and the reason the fixture now uses a
   45-row hot band (2700 > K).

   To run: **the notebook** — Phase 2d's cell 15 covers 1b, 1c and 1d in one session.
   Local alternative if a GPU is unavailable: add both modes to `CONFIGS` in
   `scripts/eval_select_modes.py`, ~38 min per row on local CPU.

   **1c. Then sweep** `keep_ratio ∈ {1.0, 0.75, 0.5, 0.35}` and plot accuracy vs
   visual tokens. — **RUN (runs 7–8, 15 rows each) BUT ONLY HALF SATISFIED. The
   accuracy axis exists; the cost axis fails and the control is missing.**
   Requirements learned the hard way, and how each is met:
   - Use the **new** decoding defaults (rp=1.0, nrns=3). The `keep_ratio=1.0` row
     must reproduce **77.74 / 64.70 / 53.05** — that is the sweep's CONTROL, same
     role row 0 played in the ablation. If it does not, fix that before reading any
     other row. **STILL UNMET.** Runs 7–8 read 66.81 and 78.25 on that row, i.e.
     −10.93 and +0.51. Because both runs also *changed the weights*, that row is no
     longer a control at all: drift and retrain effect are inseparable in it. See
     item 4 below for the fix.
   - `generate()` already takes `keep_ratio` / `merge_ratio` per call, so an
     eval-only sweep needs no retraining and can resume from a `.pt` exactly as run
     6 did. This is why 1b is cheap.
   - Record `hit_max_length_pct` per row (see the open question above) and
     **latency and token count per row** — the deliverable is an *efficiency*
     curve, so cost has to be measured, not assumed. Run 6 did not record
     per-config latency; the sweep must. **DONE, AND THE ANSWER IS BAD.** Both runs
     record `avg_latency_ms`, and D3 read it: latency tracks *generated* tokens
     (r = +0.93 / +0.98), not visual tokens (r = −0.10 / +0.15), and −65% of visual
     tokens buys −7.1% of wall-clock. This is the requirement doing its job — it was
     written precisely so cost could not be assumed, and the assumption was wrong.
   - **Keep the RANDOM-PRUNING CONTROL row at every keep_ratio** — same budget,
     tokens chosen uniformly at random instead of by router score. D1 makes this
     non-negotiable rather than merely advisable: random pruning is now known to be
     the *stronger* baseline on run-5 weights, so a router row without a random row
     beside it is uninterpretable. Same instinct as the ablation's CONTROL row,
     which is the only reason run 6's +27 pts was believable rather than suspect.
   - **Include `merge_ratio` rows.** It has never executed on a recorded result
     (see gotchas) and is training-free by design, so it is untested free
     compression sitting in the repo. Resolve the score-order/bipartite-parity
     interaction first. ~~**BUILT AND GATED, NOT YET MEASURED (2026-09-16).**~~
     **MEASURED 2026-09-17 (run 13).** The
     ordering interaction is settled (Pending 15 → the `checkerboard_color` fix,
     ported into `kaggle_pruning_run.ipynb` by generator PATCH E/F/G) and the sweep
     now carries 13 new rows in **token-matched pairs** plus a `rank_parity`
     sabotage row. `scripts/verify_tome_merge_port.py` is green (82 checks) and is
     the gate. ~~What remains is GPU time: see **Run 12's launch checklist** below.~~
     GPU time was spent twice: run 12 attached the wrong checkpoint, **run 13** is the
     result. The bounded question is no longer "does merging work" but "at the same final
     token count M, does merging cost less than pruning on a merge-naive
     checkpoint" — and by D12's logic a negative answer is the *predicted* outcome,
     not a verdict on ToMe. **Answer: at 20% merge, yes — free at four budgets under
     both selectors; at 40%, no — −3.86 pts [−7.45, −0.30].** One ink pair at keep=0.35
     had merging *winning* (+4.06 [+0.43, +8.05]), which is the falsifier the plan wrote
     for itself and the reason run 14 exists.
   - ~~Cheap step 0, local, no GPU: dump the router's score distribution.~~
     **DONE — see Diagnostic D1.** Scores are well-spread and unsaturated (so
     top-k *can* rank), but anti-correlated with ink (so it ranks the wrong way).
     Worth the 15 minutes: it inverted the recommendation it was booked to support.
2. Reconcile the stale `README.md`.
3. Optional, low priority: micro-sweep `nrns ∈ {3, 4, 6}` and `rp ∈ {1.0, 1.05}`.
   Expected to be small — length calibration is already at 99.0% of gold with 0%
   cap-hits, so there is little headroom. Not worth delaying the sweep for.

### Added by D3 and D4 (2026-08-31) — ordered by what they unblock

Items 4–8 come from D3, 9–10 from D4, and 9 was corrected by D5. **4, 9 and 10 are now DONE
in code (F2, F1); the highest-priority open item is 5.** All three of the done ones are
unrun — F1 and F2 are verified in value, gradient, range and control-swap safety, and
none has touched a GPU. **Run 9 is now the gate on all three at once**, which is itself
worth noting: it will carry a loss change *and* a new control in the same session, so if
its numbers are surprising, F2's control row is the thing that tells you whether to
believe them.

4. ~~**Restore a real control row: one row per sweep on UNCHANGED run-5 weights.**~~
   **DONE 2026-08-31 (code) — see Fix F2. Unmeasured until run 9 executes it.**
   Highest priority of the five, because everything else is read through it. A control
   re-runs a *known* setting and must reproduce a *known* number; once runs 7/8 changed
   the weights, the `keep=1.00` row stopped doing that, and its 10.93-pt drift can be
   read as either a broken harness or a successful retrain with no way to tell which.
   Cheap fix: load the run-5/run-6 checkpoint, eval one `keep=1.00` row, assert
   77.74 / 64.70 / 53.05, *then* load the new checkpoint for the sweep. ~4 min of GPU
   for a row that makes the other 15 interpretable. Note the run-6 control cost the same
   and is the only reason its +27 pts was believable.
   **Measured cost, not estimated: `run 7`/`run 8` row 0 ran 3240 / 3082 ms/img
   at n=50 ⇒ 2.6 min on a ~37-min sweep (+7%).** What remains open is only the *result*:
   nothing has run this block on a GPU, so whether run-5 weights actually reproduce
   77.74 / 64.70 / 53.05 through today's harness is still unknown. That is the question
   F2 makes askable; it does not answer it.

5. **Test the co-adaptation hypothesis, since it decides what run 8 actually showed.**
   Fine-tune a decoder with `select_mode="ink"` selection at `keep_ratio=0.50` for the
   same 5 epochs, then eval both decoders under both selection rules — a 2×2. If the
   ink-trained decoder prefers ink selection by a similar margin, the ranking at
   keep=0.50 is measuring train/eval match and "beats the oracle" is withdrawn. If the
   router still wins on the ink-trained decoder, it is a real selection result and
   should be stated as one. Either outcome is worth a GPU session; the current state
   (a headline claim with a plausible confound and no test) is not.
   Cheaper partial: eval run 8's checkpoint at a keep_ratio it never trained on and see
   whether the router's *advantage over ink* shrinks. Run 7 already hints it does —
   there the router loses to ink at keep=0.50 — so the effect is at least not unconditional.
   **Run 9 delivered a different cheap partial for free, and it half-answers this (D6).**
   Seven rows had byte-identical selection across runs 8 and 9, so they isolate the weight
   change: keep=1.00 went **down** 0.94 while every pruned row went **up** 0.64–3.36,
   whatever rule produced the tokens. So the decoder demonstrably specialises to
   reduced-token input. What that does *not* show is specialisation to the **router's
   particular** distribution, which is what "beats the oracle" would require — the gain
   transfers to random and ink equally. **The 2×2 is still the test.** What has changed is
   that the cheaper partial is no longer worth doing: run 9 already shows the margin over
   ink is unstable (+5.38 → +2.74 at keep=0.50, +3.56 → **−1.75** at keep=0.35 on a
   loss-config change alone), so "does the margin shrink off-budget" no longer discriminates.
   Go straight to the 2×2.

6. ~~**Fix provenance in the results writer.**~~ **DONE 2026-09-09.** `meta` had no
   `checkpoint` key at all in either `run 7/` or `run 8/`, and neither file recorded the
   transformers version or the device. Two 15-row tables that cannot name the weights that
   produced them are one filename mix-up away from being worthless, and the local/Kaggle
   transformers split (5.4.0 vs 4.x) is exactly the kind of difference that shows up as an
   unexplained drift later — as it then did, twice (D11, D12). Fixed by
   `scripts/patch_notebook_provenance.py`: cell 15 now builds a `PROVENANCE` dict —
   `eval_ckpt` and `control_ckpt` as `{path, mtime, size_bytes}`, plus `transformers`,
   `torch`, `device`, `device_name`, `written` — and stamps it into **both** `json.dump`
   sites. `scripts/verify_results_provenance.py` executes it: **35/35** on both notebooks.
   Three design points worth keeping:
   - **mtime + size, not just the path.** Run directories get renamed (`results_2/` →
     `run 7/`), at which point a bare path stops identifying the file.
   - **failures return a dict with an `error` key, never `None`.** A *missing* JSON key
     means "written before provenance existed"; a *present* key carrying `error` means "we
     looked and it was not there". Collapsing both to `None` discards exactly the
     distinction that matters when reading a stale artifact.
   - **nothing in the block may raise**, and the verifier asserts `raise`/`assert`/
     `sys.exit` are absent from it. Bookkeeping must not be able to cost a GPU session.
     `json.dumps(PROVENANCE)` runs at build time so a non-serialisable value fails at the
     top of the cell rather than at the first write, which lands minutes of GPU in.
   **Retroactive mitigation still stands** (2026-08-31): checkpoint hashes and mtimes for
   runs 5/7/8 are recorded in the file map, so the *pre-fix* tables can still be tied to
   weights. Runs from here on carry it themselves.

7. **Fix the wrong note printed by cell 15's Q5.** It tells the reader the token column
   implies an encoder-side saving. It does not: the router runs *after* the frozen Swin,
   so all 4800 tokens are computed at every `keep_ratio` and the only saving is decoder
   cross-attention KV length. The note is wrong in the direction that flatters the
   project, which is the direction to be most suspicious of. Either delete it or replace
   it with the measured 0.18–0.22× ratio.

8. **Decide what the efficiency claim is, and scope the title to it.** Given item 7,
   the honest options are: (a) call the deliverable an accuracy-vs-token-count curve and
   drop "efficiency"; (b) move pruning to *before* or *inside* the encoder (a real
   architecture change — Swin's windowed attention makes mid-encoder pruning awkward but
   not impossible, and a coarse pre-encoder mask over 32×32 pixel blocks is tractable);
   or (c) keep post-encoder pruning and re-target the claim at decoder KV memory, which
   *is* genuinely reduced 65% and is measurable. (a) is free and true today; (c) is cheap
   and needs a memory measurement the sweep does not currently take; (b) is the only one
   that delivers the original framing.
   **Updated by run 9 (2026-09-01):** the number to scope is **−3.0% at keep=0.50 and
   −4.1% at keep=0.35**, not −7%. And option (b) is now less attractive than it looked:
   run 9 shows generation *lengthens* under pruning (251 → 271 mean tokens), so a
   pre-encoder router would recover the encoder saving and still be partly eaten by extra
   decoder steps. Whichever option is taken, **(a) remains free and true and should be
   done now** rather than held hostage to (b) or (c).
   **SETTLED 2026-09-04 by D11 — take option (a), and the number is worse than any figure
   above.** Measured at five budgets on both checkpoints, n=50, same harness: pruning
   4800 → 960 visual tokens (**5×**) buys **1.04×** wall-clock; the maximum over all ten
   rows is **1.05×**. Generation is decoder-bound (243–280 autoregressive steps, encoder
   runs once regardless), so pruning shrinks only the cross-attention KV. The
   "−3.0% / −4.1%" figures above were latency *increases* read off a single budget pair;
   the correct statement is that latency is **flat to within noise at every budget**. So
   **(a) is now not merely the free option, it is the only true one** — any latency or
   throughput claim in the writeup is false. (c) remains available and honest (KV memory
   *is* reduced ~80% at keep=0.20) but still needs the memory measurement nobody has taken.
   (b) is unaffected by this and untested.
   **CLOSED 2026-09-06 — (c) is now MEASURED, and it is the project's one true efficiency
   claim.** `scripts/eval_kv_memory.py`, **25** controls, all PASS (this read "17" until
   2026-09-09; corrected against `results/kv_memory_local.log`, which carries 25 `[PASS]`
   lines and 0 `[FAIL]` — the script has no counter, so the original count was eyeballed).
   At **keep=0.35 the decoder
   cross-attention KV cache falls 150.00 → 52.50 MiB, −65.0%, for −0.26 pts of word recall
   (t −0.18, n=50 paired, read out of D12's JSON at runtime rather than typed in).** The
   headline is deliberately *not* keep=0.20's −80.0%: that budget costs 13.01 pts (t −5.42),
   so the bigger percentage is a memory win funded by an accuracy loss. Two independent
   measurements agree exactly (analytic `2 × 4 layers × 16 heads × 64 head_dim × tokens × 4 B`
   vs walking the real `past_key_values`, rel gap 0.0000 at all five budgets), and the
   measured tensor is the one `generate()` itself decoded against — captured by a forward
   hook, with a control asserting its `seq_len` equals `meta["compressed_tokens"]`, because
   re-deriving the pruning path in the eval script would have been a second copy of
   `src/model.py` free to diverge from it. **The docstring's own caution did not survive the
   data**: it warned this might be "a large cut in a small quantity", but unpruned cross-KV is
   **19.46% of the model's 771 MiB of parameters**, so 98 MiB of real working memory is freed
   at the free budget. Honest qualifiers: fp32 CPU (every byte figure halves at fp16/bf16,
   scales linearly with batch; the *percentage* is invariant to both), and it is cross-KV
   only — not total, not peak, and **not** encoder, since the frozen Swin computes all 4800
   tokens at every budget. Self-attention KV is unaffected and reported separately;
   controls assert it is predicted exactly by *generated* length and is **non-monotone in
   `keep`** (keep=0.25 generates 327 tokens vs keep=0.35's 307, so its self-KV is *larger*
   while its cross-KV is smaller — the two quantities are demonstrably not the same thing).
   See `results/kv_memory_local.json` and the "Pending 8c" section below.

9. ~~**Fix the ink-BCE double sigmoid (D4), the way D5 says and not the way D4 said.**~~
   **DONE 2026-08-31 — see Fix F1.** Applied in `scripts/make_kaggle_pruning_notebook.py`
   (the generator, not the generated notebook) as
   `F.binary_cross_entropy_with_logits(torch.logit(_sc.squeeze(-1).clamp(1e-6, 1-1e-6)), _tgt)`
   — a variant of D5's prescription, because plain `F.binary_cross_entropy` is
   autocast-unsafe and this block runs under `torch.amp.autocast`. `PatchSaliencyRouter` was
   **not** touched. Both knobs set explicitly: `LAMBDA_SAL` 2.0 → 0.5 (reasoned, untuned)
   and `lambda_entropy` 0.0 supervised / 0.05 unsupervised. Verified by execution:
   `verify_saliency_loss_cell.py` 3/6 → **6/6**. ~~**Still unmeasured on GPU** — the
   predicted metric gain is a prediction until run 9.~~ **Measured at run 9: the code fix is
   correct and the predicted metric gain did not materialise.** Retained ink rose at every
   budget (the fix works) and recall fell at two of three (the objective is wrong). See D6.
   The item stays DONE — it fixed the bug it named — but it did not buy what it promised.

10. ~~**Write an execution check for the training cell.**~~ **DONE 2026-08-31 — see Fix F1.**
    `scripts/verify_saliency_loss_cell.py`, six assertions, **6/6 PASS**, and it failed 3/6
    on the unfixed code first — A SOLVED, C PROPORTIONAL and D EXPLICIT, exactly the three
    D4 and D5 predicted. Assertion B passes *with* the bug present, which is the useful
    negative result here: the obvious check (inverted costs more than matched) would have
    found nothing, because sigmoid is monotone. Cell 11 now has coverage; runs 7–8's
    unverified-cell gap is closed.

11. ~~**Log the saliency loss. It is the one number F1 exists to move and no run has ever
    recorded it.**~~ **DONE 2026-09-01 — see Fix F3.** `epoch_loss += loss_dict['loss'].item()`
    accumulated the *criterion's* loss; `LAMBDA_SAL * _sal` was added to the separate `loss`
    variable that goes to `backward()`. So the printed `Avg Loss` never included the saliency
    term in any run, and with `lambda_sparsity=lambda_entropy=0.0` (the supervised branch)
    `Avg Loss` and `CE` were *identical by construction* — run 9 printed both to 4 dp for five
    epochs and they matched every time. That looks exactly like "the saliency term never ran",
    which is why it was worth fixing: **the log could not distinguish `LAMBDA_SAL=0.5` from
    `LAMBDA_SAL=0`**, and `scripts/verify_training_telemetry.py` proved that by failing on the
    old code with the two λ values printing byte-identical lines. Now six columns, each one
    justified by a past failure; F1's central claim is checkable from the log instead of
    inferred from downstream metrics. **This was the blocker on item 5's 2×2 and item 13(a);
    both are now unblocked.**

12. ~~**Rename `results/`, `results_2/`, `results_3/` to `run 6/`, `run 7/`, `run 8/`.**
    The old names were off-by-one against the run numbers used everywhere in this file
    (`results_2` was run 7, `results_3` was run 8) — a trap for anyone who assumes the
    digits line up.~~ **DONE 2026-09-06.** `results_2/` → `run 7/`, `results_3/` → `run 8/`.

    **But the item's own instruction for `results/` was wrong, and the grep it demanded is
    what showed it.** `results/` was never a run directory: it held run 6's seven Kaggle
    artifacts (all mtime `2026-08-29 12:35`, and `ablation_decoding.json` **byte-identical
    to the copy inside its own zip** — that is what settled the split, rather than a guess
    from filenames) *mixed with* every local diagnostic since, including D11's, D12's and
    M1's JSONs and logs. Renaming it wholesale to `run 6/` would have filed three 2026-09
    diagnostics under a 2026-08-29 Kaggle run. So the seven were **moved** into `run 6/` and
    `results/` survives as local-diagnostics-only, documented as such in the file map. The
    item already flagged `ablation_selection_local.json` as needing a different home; the
    correct reading was that *it* stays put and run 6's files leave.

    **Fallout worth more than the rename.** Grepping the paths first (as the item said) found
    `scripts/diagnose_decoder.py`'s `CKPT_CANDIDATES` list — documented "newest-run-first" —
    **missing `run 9/` and `run 10/` entirely**. An unqualified invocation had been silently
    resolving to run 8's weights for five days while claiming to diagnose the newest
    checkpoint. A resolver that falls through to an older path is worse than one that fails:
    it answers the question about the wrong artifact and says nothing. Both runs are now
    listed ahead of run 8. `diagnose_selection_statistics.py` had the same shape of defect —
    it defaulted to runs 7 and 8, the two *oldest* pruning runs — and adding 9 and 10 was
    immediately informative: **run 10 flips Q3 to `D2 FALSIFIED (aggregate predicts better)`**
    where runs 7/8/9 all read `INCONCLUSIVE`. Also patched: `_curve_data.py`,
    `_summarize_ablation{,3}.py`, `geom_probe.py`, `infer.py`. One surviving match for the
    old names is correct and was left alone: inside `run 7/efficiency_curve_data.json`'s
    `"source"` field, which records its own historical provenance; rewriting that would
    falsify the record.

    ~~Three surviving matches ... two name `pruned_ocr_results_2/`/`_3/` (real,
    still-present directories) and were left alone.~~ **FALSE — struck 2026-09-06 the same
    day.** Those two were *not* left alone. `results_2` is a substring of
    `pruned_ocr_results_2/`, so the bulk regex rewrote `pruned_ocr_results_2/checkpoints/...`
    into `pruned_ocr_run 7/checkpoints/...` — a directory that never existed — in
    `geom_probe.py:20` and `infer.py:182`. Both now restored to `pruned_ocr_results_2/` with
    an inline comment naming the collision so a future rewrite does not repeat it, and both
    verified to `torch.load` (490 state-dict keys each). **The lesson is not "be careful with
    regex": it is that I wrote the reassuring sentence from the grep output without opening
    the two files it was about.** A bulk edit's own report is not evidence; the substring that
    made the match is exactly the substring that makes the rewrite wrong.

    **Gotcha created and fixed in the same session — see Gotchas.** The bulk path rewrite used
    `Set-Content -Encoding utf8` on AGENTS.md, which round-tripped every non-ASCII character
    through CP1252 and produced **1117 mojibake sequences** (em dashes 936 → 179). Reversed
    exactly by re-encoding to CP1252 bytes and decoding as UTF-8: 0 mojibake, 936 em dashes,
    0 U+FFFD, line count unchanged, 28 fences balanced, 0 ragged table rows. It also corrupted
    this item's own text into the tautology "`run 7` is run 7", which is how it was noticed.

13. **Find a training target that is not retained ink.**
    **STATUS 2026-09-03: (a) dead (D7). (b) BUILT, RUN, and NULL — run 10 executed
    2026-09-03. The auxiliary fit to `ov 0.930 / lift +0.430` (the strongest in the project)
    and recall moved −0.22 / +0.49 / −0.06 at keep=0.50 / 0.35 / 0.75, all inside the
    pre-registered ±1 pt noise floor. See "Run 10 — result". The question is NOT settled,
    because the test was run at a budget where it could not be won: `keep=1.00` scores 77.32
    while `keep=0.50` scores 79.41, so at keep=0.50 the budget is not binding and no
    selection objective can help. Re-ask at keep=0.20–0.35.**
    **RESOLVED 2026-09-04 by D11 — (b) is DEAD, and not by a null.** `eval_budget_binding.py
    --n 50` (182 min local CPU, all 10 controls pass, 6 ink gates exact to 3 decimals) found
    the attention target **loses to ink by −5.63 pts at keep=0.25 (t −2.40) and −12.81 at
    keep=0.20 (t −6.23)**, monotone in tightness. Mechanism: run 10's router retains ink
    0.355 / 0.257 against a random floor of 0.251 / 0.201 — at binding budgets it selects
    barely better than randomly. **Do not run run 11 in the form sketched below**; both
    remaining candidates are "supervise the router on a better per-token target" and the
    failure mode found is not specific to the target. The pruned-grid teacher-attention idea
    is retired too — the target was not measured on the wrong grid, it is the wrong thing to
    select on. Correction to the paragraph above: keep=0.35 was **also** non-binding
    (79.25 vs a 77.62 ceiling), so both of run 10's headline rows were unwinnable, and the
    budget first binds at keep=0.25. See the D11 section.**
    What run 10 *did* settle: retained ink is finished as an objective on a third independent
    line of evidence — the router's retained ink collapsed 0.922 → **0.675** at keep=0.50 and
    0.826 → **0.511** at keep=0.35 with recall flat. This is what D6 left open and it
    is now the project's central question, ahead of everything except item 5. Ink
    supervision is *ruled out* as the objective, not merely suspected: D2 showed retained
    ink does not imply accuracy, and run 9 showed optimising it harder costs accuracy
    (−2.5 pts of selection effect at keep=0.50, −3.9 at 0.35, both on *increased* retained
    ink). Do not respond by tuning `LAMBDA_SAL` — that moves along the axis D6 just
    invalidated. Candidates, cheapest first: (a) **drop the auxiliary term entirely** and
    train the router on task CE through the STE alone, now that the sign inversion is fixed
    and cannot recur from a bad initialisation — ~~this is a *subtraction*, needs no new code,
    and~~ D6 predicts it beats run 9 at keep≤0.50; (b) distil from a per-token attribution the
    decoder itself provides (decoder cross-attention mass per visual token on the run-5
    ceiling model) — expensive to compute once, then a fixed target like ink is; (c) keep ink
    but weight it by line, so the loss cannot buy a high score by over-covering dense
    regions while dropping a whole line — this is the surviving half of D2's insight, and
    run 9's `mean_min_line_cov` 0.601-while-winning at keep=0.50 versus 0.392-while-losing
    at 0.35 suggests a floor near 0.4 rather than a maximisation target.
    ~~Note (a) is nearly free and directly falsifiable, so it should go first.~~

    **Two corrections to (a), established 2026-09-01 before writing any code** (both were
    wrong in the text above, struck in place):

    - **(a) is NOT a subtraction and DOES need new code.** Cell 11 has exactly two reachable
      loss configurations, and neither has all three weights at zero:
      `SUPERVISE_SALIENCY=True` → `lambda_sparsity=0.0, lambda_entropy=0.0, LAMBDA_SAL=0.5`;
      `else` → `lambda_sparsity=2.0, lambda_entropy=0.05, LAMBDA_SAL=0.0`. So flipping the
      existing knob does not *remove* an auxiliary, it **swaps one auxiliary for two others**.
      "Train on CE alone" requires a third config path. Anyone who reads "needs no new code",
      flips `SUPERVISE_SALIENCY=False` and books a GPU has silently run a different
      experiment — the same class of mistake as D5's undeclared `lambda_entropy`.
    - **Run 7 was not (a).** Cell 11's comment says "the STE-only retrain kept the router
      sign-inverted (Run 7 follow-up)", which reads as "(a) was already tried and failed".
      Run 7 took the `else` branch, i.e. STE **plus** sparsity 2.0 **plus** entropy 0.05.
      It was never STE-alone. (a) is therefore still an unrun experiment, and the notebook
      comment's "STE-only" is a misnomer — see Gotchas.

    Whether (a) is worth GPU time turns on how strong CE-through-STE actually is; that is
    Diagnostic D7 below, which was built to answer it locally before booking a run.

    **VERDICT 2026-09-01 (D7): (a) is DROPPED. (b) is next, and D7 sets the bar it must clear.**
    Run 7's two auxiliaries were a minority of the router's gradient at every weight point and
    split measured (**2.5–17.2%**), so run 7 was predominantly STE-driven — and its forward
    router scored **18.80 recall, min-cov 0.003** at keep=0.50. (a) deletes that minority and
    keeps the rest, i.e. it is that run again. D7 also shows why no amount of task loss fixes
    this: CE-through-STE's per-page gradients barely agree (cos **0.21**) where ink-BCE's agree
    strongly (cos **0.90**), and the STE reaches only the K kept tokens, never the N−K dropped
    ones. So the replacement target must be **dense** (all N tokens), **coherent** (accumulates
    across documents) and **free** — those three properties, not correctness, are what the ink
    term was actually contributing. D6's "(a) beats run 9" prediction extrapolated a local
    negative slope to zero and run 7 is the zero endpoint that contradicts it; the relationship
    is non-monotonic.

    **(b) has one cheap way to be dead on arrival, checked first:** if decoder cross-attention
    mass is just ink, (b) is (c) with extra steps and D6 already ruled it out. That is
    Diagnostic D8, `scripts/diagnose_attn_target.py`, with thresholds pre-registered in its
    docstring (`r ≥ 0.8` and top-K overlap `≥ 0.90` ⇒ drop).

    **VERDICT 2026-09-01 (D8 + D9): (b) SURVIVES three pre-registered falsification tests and is
    cleared to build. Nothing about its *merit* has been established.** What was ruled out:

    | ruled out | test | measured | threshold |
    |---|---|---|---|
    | (b) is ink in disguise | D8 Test 1 | r(attn,ink) **+0.083**, overlap 0.62 | drop if r ≥ 0.8 **and** overlap ≥ 0.90 |
    | (b) is a fixed positional mask | D8 Test 2 | centroid spread **6.12** rows vs ink's 1.81; cross-page r +0.38 | drop if more page-invariant than ink |
    | (b) is unreachable by this scorer | D9 | held-out AUC **0.976** vs shuffled floor 0.498 | drop if within 0.02 of floor |
    | (b) is only the page-invariant part | D9 control | lift **+0.212** over a constant map (ink's own lift: +0.151) | drop if lift ≤ 0.03 |

    Against D7's three requirements the target is **dense** (defined on all N tokens, including
    the N−K the STE cannot reach), **coherent** (a fixed per-image target, so perfectly
    consistent across steps), and **free at train time** — see the precompute note below. It
    changes only the *content*, which is exactly what D7 asked for.

    Two extra findings that motivate (b) more strongly than the ink correlation does:
    **`r(attn, router score) = −0.045`** — the router is not merely anti-correlated with ink, it
    is *uninformed* about what the decoder actually looks at, so there is real headroom. And the
    deepest decoder layer is both the most ink-aligned (r +0.201 vs +0.083 for the 4-layer mean)
    and the most page-varying, so **layer choice is a live untested knob**; default to the mean
    over layers, because that is the aggregation whose properties D8/D9 actually measured.

    **Build plan for (b) — the disk-cache design is SUPERSEDED. Read the revised design below.**
    ~~The target is a function of (image, target text) only, both fixed per training example, so
    it can be **precomputed once for the whole dataset and cached**, making it exactly as free at
    train time as ink.~~ That premise is false for 70% of the training set, and the reason is in
    the data cell, not the model: **`funsd_train` is built with `augment=True`**, and
    `train_ds = ConcatDataset([funsd_train] * FUNSD_REPEAT + [synth_train])` means each of the 149
    FUNSD pages is drawn 8 times *with a fresh random augmentation each time* (`DOC_AUG`: ±2°
    rotation, 0.9–1.05 affine scale, jitter, blur). A cached target is a **positional** label on
    an 80×60 grid, so rotation and scale move the content out from under it — ~1.05 grid cells of
    vertical shear at the page edge from 2° alone, up to ~4 rows from 0.9 scale, against text lines
    that are 1–2 grid rows tall. The label noise is the same order as the feature being labelled.
    What makes that disqualifying rather than merely unfortunate: `patch_ink` is computed at train
    time from the **augmented** `pixel_values` and so stays perfectly aligned, while a cached
    attention target would not. The comparison against run 9 would then be biased *against* the
    new target by an amount unrelated to the target's quality — a confound built into the
    experiment, which is exactly what D6's "fitting the proxy harder made it worse" result is
    already too easy to misread as.

    The BCE call stays untouched either way: the target is fed to **the call already in cell 11**
    (`binary_cross_entropy_with_logits(logit(p), t)` — see the corrected bullet below, it is right
    as written and for a non-obvious reason).

    **Three preconditions I checked for the cache design before writing any code. The augmentation
    finding above is the fourth, and it is the one that killed it** — recorded because the first
    three are still true and still constrain the replacement:

    | precondition | status | evidence |
    |---|---|---|
    | train set is index-deterministic, so a cache keyed by index is stable | **holds** | `SYNTH_N, FUNSD_REPEAT = 500, 8` — synthdog `split='train[:500]'` is a deterministic slice and `augment=False`; FUNSD is a fixed 149-page split repeated. ~1692 examples ⇒ 4800 floats each ⇒ **~32 MB fp32**, trivial to cache |
    | teacher's encoder == student's encoder, so cached targets are scored against the features the router actually sees | **FALSE — I got this wrong once already, see below** | ~~holds: run 5 trained Swin stage 3 and the retrain sets `freeze_encoder=True`~~ **Corrected within the hour, 2026-09-02.** The DO_TRAIN branch sets `freeze_encoder=True` and then **immediately unfreezes the top Swin stage** (`UNFREEZE_STAGES = 1`, generator lines 128–133, mirroring run 5). So the student's encoder *does* drift during training and the cached target is computed from features that no longer exist by epoch 2. I asserted the opposite after reading the constructor flag and not the six lines that override it — the exact shape of [[verify-the-prescription-not-just-the-diagnosis]]. **Why it is survivable anyway:** the cached target is a *positional label* ("grid token 1234 is worth keeping"), not a feature vector. Feature drift changes the representation the router maps *from*, not the correctness of the label it maps *to* — this is ordinary supervised learning with fixed labels under a slowly-adapting trunk. What it does kill is the stronger claim that D9's held-out AUC transfers directly to the training run; D9 measured run-5-features → run-5-attention, and the run will be drifting-features → run-5-attention. Record the gap, do not paper over it. **BOUNDED BY MEASUREMENT, 2026-09-02 — the gap is real but small.** I had only reasoned about the drift; run 5 → run 9 is a *completed* training run under the identical `UNFREEZE_STAGES = 1` config, so the drift run 10 will experience is already on disk and measurable. Relative weight drift ‖Δ‖/‖w‖ per component: **Swin stages 0/1/2 exactly 0.000000 on all 315 tensors** (frozen as configured), **stage 3 moved on 34/34 tensors, max 0.0120**; decoder median 0.0081 / max 0.0208; router median **0.298**, max **1.232**. So three of four encoder stages are bit-identical and the fourth moves ~1%, while the router — the thing being trained — moves two orders of magnitude more. That is the opposite of the regime I was worried about. It does **not** license the AUC-transfer claim (weight drift is not feature drift, and 1% of weights can move representations further than 1%), but it makes the remaining question cheap and well-posed: recompute the teacher's top-K target from run-9 features and see how many of the 2400 positives change. That is D10, minutes on CPU, and it is the check to run before spending 4 GPU hours. **ANSWERED — D10, 2026-09-02, and it PASSES on both pre-registered thresholds.** Features move **7.6× further than the weights** (median rel-L2 **0.0918** vs 0.0120), which is exactly the reason the weight numbers above were not an argument — but the recomputed target still keeps **S = 0.9613** of its positives across a whole 5-epoch retrain (~93 of 2400 change), against a different-pages floor of **X = 0.6246**, gap **+0.3367**. So the precondition holds, the "positional label under a slowly-adapting trunk" reasoning above is now measured rather than asserted, and the residual risk (run 10's objective differs from run 9's, so its drift need not be identical) is **observable at runtime** in the new `ov` column instead of being argued about. Full tables in the D10 section |
    | target stays fixed while the student's decoder trains | **holds by construction, deliberately** | the student's decoder *is* trainable, so it drifts away from the teacher during the run. The target does not follow it. This is distillation from a frozen teacher — chosen because D7's requirement was **coherence**, and an online target that moves with the student would reintroduce exactly the incoherence (cos 0.21) that killed 13(a). The cost is that late in training the target no longer describes where the *current* decoder looks; that is the trade, and it is not a bug to be fixed |

    **REVISED DESIGN (2026-09-02): frozen teacher decoder, on the fly, no cache.** Compute the
    target inside the training step from the *current* augmented view, using a frozen copy of run
    5's decoder. This is the smallest design that has no alignment confound:

    - **Alignment is exact by construction.** The target is derived from the same
      `pixel_values` the student just saw, so augmentation cannot desynchronise it. This is the
      whole reason for the redesign.
    - **Still coherent, which is what D7 actually required.** The *teacher weights are frozen*, so
      the map features→attention is fixed. The target drifts only as slowly as the encoder's
      stage-3 features drift at lr 1e-5 — nothing like CE-through-STE's cos 0.21 incoherence that
      killed 13(a).
    - **Still dense.** The teacher decoder must attend over the **full N=4800** encoder features,
      not the student's pruned K, or the target cannot cover the N−K tokens the STE never reaches
      — which was the entire point. `forward()` does not currently expose the pre-prune features,
      so it needs one additive return key (`visual_tokens`), detached before use.
    - **Not free, and I am not going to call it free.** Cost is one extra decoder forward per step
      (no extra *encoder* forward, which is the expensive half) plus a transient
      4 layers × 16 heads × T × 4800 attention tensor, ~314 MB fp16 at the full T=512 and less
      once truncated to the real non-pad length. Ballpark +15–20% step time; run 9 was ~4 h, so
      budget ~40 min. Plus one frozen decoder copy resident (~116 MB fp16 — the 57k×1024 embedding
      dominates, not the 4 layers).
    - **Rejected alternative: cache the ink target the same broken way** so both arms suffer
      identical misalignment. It does equalise the confound, and it is cheaper. Rejected because
      the ink arm would then no longer *be* run 9 — it would need re-running, doubling GPU cost,
      to compare against a number already measured.
    - **Rejected alternative: turn augmentation off.** Changes a second variable versus run 9 for
      the sake of the first.

    Diff, in full — three edits, all in `scripts/make_kaggle_pruning_notebook.py` so
    `kaggle_pruning_run.ipynb` regenerates clean (the project has already been bitten by patching
    the notebook without mirroring the generator):
    1. cell 7 `AdaptiveDonutOCR.forward` — add `'visual_tokens': visual_tokens` to the return dict.
       Additive; no existing reader is affected.
    2. cell 2 — `ATTN_TARGET` flag, off by default, so `SUPERVISE_SALIENCY` alone still reproduces
       run 9 exactly.
    3. cell 11 — build the frozen teacher decoder once before the epoch loop (eager attention,
       `.eval()`, `requires_grad_(False)`, asserted non-empty `cross_attentions`); in the step,
       swap only the `_tgt = ...` line.

    **Do not skip these when building it:**
    - Force `attn_implementation="eager"` on the teacher and **assert `cross_attentions` is
      non-empty**. transformers 5.x defaults to SDPA, which does not materialise attention
      weights, and the failure is a silent `None` → an all-zero target that trains without
      complaint. See Gotchas.
    - **Do not touch the BCE call. Swap only `_tgt`.** ~~`F.binary_cross_entropy`, **not**
      `..._with_logits`: the scorer already ends in `Sigmoid` (D4/D5 — the double-sigmoid bug).~~
      **CORRECTED 2026-09-02, before any code was written, by reading the actual swap site**
      (`kaggle_pruning_run.ipynb` cell 11, lines 854–872). The diagnosis was right and the
      prescription was wrong: the notebook already solves the double-sigmoid problem the *other*
      way — `binary_cross_entropy_with_logits(torch.logit(_sc.clamp(1e-6, 1-1e-6)), _tgt)`, which
      is numerically identical to plain BCE but stays autocast-safe. Its own comment says why:
      **`F.binary_cross_entropy` is on PyTorch's autocast-unsafe list and this block runs inside
      `torch.amp.autocast` on the T4.** So my instruction would have introduced a crash on Kaggle
      in the name of fixing a bug that was already fixed. D9's probe *does* use plain BCE
      correctly — it is local CPU with no autocast — and generalising from the probe to the
      notebook is what produced the error. The correct diff is one line: replace
      `_tgt = (_inkn > SALIENCY_THRESHOLD).float()` with the cached attention top-K lookup, and
      leave lines 858–872 untouched.
    - Pass `lambda_sparsity` and `lambda_entropy` **explicitly**, whatever the intent. D5's
      lesson: `lambda_entropy=0.05` shaped runs 7–8 while appearing in no config cell.
    - The acceptance criterion is **recall at keep=0.50 and 0.35 against run 9**, not retained
      attention mass. D9's retained-mass column is scored against the teacher's own attention
      and is close to tautological; D6 is the standing proof that fitting a proxy harder can
      cost accuracy. Promoting the proxy to a gate is the mistake D2's withdrawn gate already
      made once.

    **BUILT AND VERIFIED BY EXECUTION — 2026-09-02.** 13(b) is in the generator
    (`scripts/make_kaggle_pruning_notebook.py`, four edits: `ATTN_TARGET` in cell 2 CFG;
    `attn_topk_target()` + a `visual_tokens` key on `forward()`'s return in cell 7 as PATCH D;
    a frozen-teacher snapshot in cell 11 after the `RESUME_CKPT` load and before the unfreeze;
    the target branch + first-step telemetry in the training loop). `ATTN_TARGET = False` by
    default, so `SUPERVISE_SALIENCY` alone still reproduces run 9 exactly and this stays a
    one-variable experiment.

    New verifier `scripts/verify_attn_target.py` — **41 checks, all passing** (34 fast + 7 more
    under `--real`). The generator only proves cells *parse*; this one **executes** them, which
    is the whole point of [[verify-patches-actually-run]] and which caught four real defects that
    a parse check and a grep both pass. Suite is **18/18 green** (13 `verify_*.py` + 5 `tests/*.py`)
    since `verify_attn_train_step.py` joined it 2026-09-02.

    | what execution caught | how it would have shown up otherwise |
    |---|---|
    | `AdaptiveDonutOCR.__init__` NameErrors on `PatchSaliencyRouter` if cell 7 runs without cell 4 | resolves at call time, so `ast.parse` and any grep are clean |
    | `verify_saliency_loss_cell.py` and `verify_training_telemetry.py` both `exec` cell 11's saliency block in their own namespace; `if ATTN_TARGET:` made it a free variable → **NameError, 2 suite failures** | the notebook itself is fine (cell 2 binds it), so only running the *other* verifiers reveals it. Fixed by binding `ATTN_TARGET`/`TRAIN_KEEP_RATIO`/`step`/`epoch` in both harnesses |
    | **my degeneracy assert was wrong in both directions** — see below | would have fired at step 0 of a real run, or never |
    | my own check `"degenerate saliency target" in c11` went stale the moment I rewrote that line | it *failed* loudly rather than passing — the right direction, but it was keyed to the line's **prose**, the same mistake as the D5 guard. Re-keyed to the condition `abs(_rate - _want) < 1e-4` |

    **The assert was wrong in both directions, and a pre-existing test found it.** I wrote
    `assert 0.0 < _rate < 1.0` on the shared path. `verify_saliency_loss_cell.py` case C drives
    the block with single-element targets (`t = 1.0`), which are legally rate 1.0 — it crashed.
    Chasing that surfaced the real problem: the check was **too weak** for the attention branch,
    where top-K makes the rate *exactly* K/N and so `rate == K/N` to 1e-4 is available and
    catches an all-zero target immediately; and **too strict** for ink, where one all-blank or
    all-ink first page is legal and the assert would have killed a 4-hour run at step 0 —
    adding a new fatal path to the branch that already produced run 9. Now per-branch: ATTN
    asserts exactly, INK prints a `WARNING` and cannot die. The failing test improved the design
    rather than being worked around; case **H** now runs the guard against **both** states plus a
    valid target, and case **G** asserts the ATTN and INK branches produce **bit-identical `_sal`**
    on the same target — i.e. 13(b) changed the target's content and not the loss, which is
    literally what D7 required.

    **Measured, replacing two numbers I had estimated.** `--real` mode: run 5 weights, one real
    FUNSD train page, the full 4800-token grid, real labels padded to 512.

    | quantity | recorded before | measured 2026-09-02 |
    |---|---|---|
    | cross-attention tensor | "~314 MB at full T" (arithmetic) | **294 MB** — 4 layers × 16 heads × 239 × 4800 fp32. The pad truncation is load-bearing: real labels are **239/512 tokens, 53% pad**, so masking first shrinks this by about half |
    | teacher forward + target | "+15–20% per step" (estimate) | **0.3–0.4 s per step on CPU**; the GPU figure is still unmeasured, so the +15–20% claim stands as an estimate and is labelled as one |
    | K on the real grid | — | exactly **2400** positives, target spans **78/80** grid rows |

    **A correction to how this section justified 13(b).** The premise recorded above is
    "r(attn, ink) = +0.083, so the target is genuinely new information." D8's number
    **reproduces** (+0.107 mean over 4 FUNSD train pages, per-page +0.183/+0.080/+0.184/−0.019)
    — but it is the correlation of the **continuous** maps, and the target that actually gets
    used is the **binarised top-K**. Binarising roughly triples the association: **r_bin =
    +0.265, top-K overlap 0.632**. So "nearly uncorrelated with ink" is true of the map and
    misleading about the target: ~63% of the new target's positives are also ink positives.
    **And the overlap statistic has an inflated floor, so 0.500 is the wrong null.** Both maps
    avoid the page margins, so they agree well above chance while sharing no content: a
    **content-free interior prior** (distance from the page edge, no pixels read at all)
    overlaps ink top-K at **0.667 — higher than attention's 0.632**. This is the cosine
    inflation of D-A recurring on a different statistic; `--real` now prints the interior-prior
    floor on every run so the number cannot be read against 0.500. **The sign of that
    comparison is page-dependent, so do not quote it as a fact about the target.** On the
    single page `--real` uses, the ordering *reverses*: attention-vs-ink **0.678** against an
    interior-prior floor of **0.654** — a margin of **+0.024**, which is that check passing by
    almost nothing. The defensible statement is the weaker one: *on this grid a structured but
    content-free map already scores ≈0.65, so this statistic cannot separate the attention
    target from ink in either direction.* D10 later produced a third estimate of the same
    inflated floor from an unrelated construction (cross-page attention targets, **X =
    0.6246**), so ≈0.63 is now the working null for any top-K overlap in this file.
    Page 3 is nearly independent
    of ink (r −0.019, overlap 0.522) while page 1 is at 0.680, so per-page variance is large and
    4 pages is not a basis for a tighter claim. **None of this kills 13(b)** — ~37% of the
    target's positives are still non-ink, and D9's learnability result (0.976 held-out AUC vs
    0.764 for a constant map) is untouched — but the "genuinely new information" framing is
    weaker than `r = +0.083` made it sound, and the honest version is: *substantially but not
    entirely overlapping with ink, by an amount this statistic cannot measure cleanly.*

    **TELEMETRY ADDED 2026-09-02 — so a null result on run 10 is readable.** The single worst
    outcome for run 10 is not "recall drops"; it is "recall drops and the log cannot say why."
    That is exactly what happened at run 9: D6 could see recall fall and the mechanism improve,
    but nothing in the log separated *the router never learned the target* from *the router
    learned the target and the target is wrong*. F3 fixed that for the loss value; it does not
    cover **selection**, and selection is what the deliverable is made of. So the epoch line
    now carries three more columns, computed inside the existing single `.tolist()` device sync
    (no new GPU→CPU stall):

    | column | quantity | why it is here |
    |---|---|---|
    | `ov` | fraction of the target's positives that the **router's own top-K** keeps | the mechanism. This is the thing the auxiliary is supposed to move, measured directly on the selection rather than inferred from a loss value |
    | `ch` | the target's positive rate = what a **random** top-K scores | the null. Without it `ov ≈ 0.5` reads like a coin flip when it *is* the coin flip; the 0.500-vs-0.65 floor error in this very section is the reason a printed null is not optional |
    | `lift` | `ov − ch` | the reportable number, so the log states the score against its own baseline |

    Example line: `Epoch 1 | Obj 2.7395 | CE 2.6054 | aux 0.0000 | sal 0.2681 x0.5 [3/3] |
    dev 0.2186 | p 0.515+-0.342 | ov 1.000 ch 0.500 lift +0.500`.

    **Reading run 10 with these:** `lift` climbing while recall falls ⇒ the router learned the
    attention target and attention is the wrong objective (the D6 verdict, transferred from ink
    to attention — a *real result*, and the one 13(b) exists to test). `lift` flat near 0.000 ⇒
    the auxiliary never took, and recall is uninformative about the hypothesis. These two demand
    opposite responses, and run 9 could not tell them apart. This also makes D10's residual risk
    observable: a target drifting out from under the router shows as `ov` stalling or
    oscillating near `ch`.

    **Verified by execution, and the assertion is the differential one.** `ov 1.000 ch 0.500
    lift +0.500` is also exactly what a column hard-wired to 1.000 would print, so
    `verify_training_telemetry.py` gained case **M**: re-run the loop with the target inverted
    and `ov` must **move**. It goes 1.000 → 0.000. Plus `lift == ov − ch` to 2e-3, so the log
    cannot silently report the raw score. **8/8** (was 6/6). Two things this caught that a
    green line would not have: the harness's epoch-line parser used `-?\d+\.\d+`, which
    **silently dropped `lift +0.500`** because of the explicit `+` sign — the check would have
    passed on its `.get()` default instead of on the log — and `L PARITY`'s pattern did not name
    the new `_tgf`/`_rk`/`_st` lines, so a regeneration could have reverted the new telemetry
    while parity still reported green on the old columns. Both fixed; parity now covers 26
    lines. The notebook was regenerated and is **byte-identical** to the generator's output.

    **Still not established:** whether the target *helps*. Every check above is a plumbing and
    guard check. D6 remains the standing case of a proxy fitted harder while accuracy fell.
    Acceptance is unchanged: recall at keep=0.50 and 0.35 against run 9.

**Explicitly rejected — do not retry:** raising `SYNTH_N` to 4000–6000 (see run 4);
`.eval()` on the frozen encoder prefix (would change drop_path behaviour vs runs
2–4 and break comparability); `repetition_penalty > 1.0` (run 6: costs 27 pts of
recall — `no_repeat_ngram_size` provides the collapse guard at no cost);
`min_new_tokens` (run 6: never binds, mean generation is 328 tokens).

## Run 11 — launch checklist (written 2026-09-09; **EXECUTED 2026-09-14, see "Run 11 — result" below**) — isolate H1

This is Pending **14**, the run that section points at with "Launch checklist below".

**One variable: `TRAIN_KEEP_RATIO = 1.00`.** Everything else is run 9's configuration byte
for byte, which is the only reason a run-9 → run-11 delta means anything.

### The design, in one table

| checkpoint | epochs past run 5's base | pruning during training | what it supplies |
|---|---|---|---|
| **run 5** | 0 | no | the pre-pruning arm — D12 already has its full local curve |
| **run 9** | 5 @ keep=0.50 | **yes** | the pruning arm — D12 already has its full local curve |
| **run 11** | **5 @ keep=1.00** | **no** | **the missing cell: the epochs without the pruning** |

```
run 9  −  run 5   =  pruning-aware training  +  5 epochs     <- what D12 measured (confounded)
run 11 −  run 5   =                             5 epochs     <- the confound, measured alone
run 9  −  run 11  =  pruning-aware training                  <- THE ISOLATION
```

D12's own closing sentence is the reason this exists: run 9 differs from run 5 "by
pruning-aware training **and by five more epochs of it**", and Claim 1 at the top of this
file attributes the whole gain to the first term. Run 11 is the arm that lets that
attribution be wrong.

### What `TRAIN_KEEP_RATIO = 1.00` actually changes — traced through the generator, not assumed

The constant appears five times in `scripts/make_kaggle_pruning_notebook.py`. On run 9's
branch (`SUPERVISE_SALIENCY=True`, `ATTN_TARGET=False`) exactly **one** of them is live:

| generator line | use | live on this branch? |
|---|---|---|
| 168 | `AdaptiveDonutOCR(keep_ratio=TRAIN_KEEP_RATIO, …)` | **YES — this is the variable.** K goes 2400 → 4800 |
| 251 | `AdaptivePruningLoss(target_budget=TRAIN_KEEP_RATIO)` | **no** — that is the `else` branch; the supervised branch hardcodes `target_budget=1.0` with `lambda_sparsity=0.0` |
| 283, 302 | `attn_topk_target(…, TRAIN_KEEP_RATIO)`, `_K` | **no** — both are inside `if ATTN_TARGET:` |
| 358 | `_rk` top-K, telemetry only | yes, and **degenerately** — Trap 2 below |

And the supervision target itself is **threshold**-based, not budget-based:
`_tgt = (_inkn > SALIENCY_THRESHOLD).float()`. So the label the router is fitted to is
**bit-identical to run 9's**. The only thing that changes is whether the model prunes. That
is what makes this one variable rather than two, and it is worth stating because the obvious
reading of "train without pruning" — turn the router's supervision off too — is a different
experiment that answers nothing (Trap 1).

### Two traps, both of which produce a *green-looking* run

**Trap 1 — do NOT set `SUPERVISE_SALIENCY = False`.** "Trained without pruning" is a
statement about `keep_ratio`, not about the auxiliary. Cell 11 has exactly two reachable loss
configurations and **neither of them is "CE alone"**:

| `SUPERVISE_SALIENCY` | `LAMBDA_SAL` | `lambda_sparsity` | `lambda_entropy` |
|---|---|---|---|
| `True` (run 9, run 11) | 0.5 (ink BCE) | 0.0 | 0.0 |
| `False` | 0.0 | **2.0** | **0.05** |

Flipping it does not *remove* a term; it **swaps one auxiliary for a different and stronger
one** — including D5's `lambda_entropy = 0.05`, this project's standing case of a knob that
shaped two runs while appearing nowhere in the log. Run 11 would then differ from run 9 in
two ways at once and isolate nothing. Leave it `True`. Do **not** add a third all-zero branch
for this run either: that is a code change to the training loop on the very run whose value
depends on the loop being byte-identical.

**Trap 2 — `ov` and `lift` go dead, and they go dead GREEN.** At `TRAIN_KEEP_RATIO = 1.00`,
`max(1, int(round(N * 1.0)))` is `N`, so line 358's `_rk` is **all ones**. Therefore, for any
router at any step, including an untrained one at step 0:

- `ov = (_rk * _tgf).sum() / _tgf.sum()` ≡ **1.000**
- `lift = ov − ch` = **1.000 − ch**, a positive constant fixed entirely by the images

Run 10's watch row — "`lift` should already be **well above 0.000** after epoch 1" — is
therefore **satisfied trivially by a router that learned nothing**. Do not reuse that row.

**Executed, not reasoned (2026-09-09).** Running lines 356–363 verbatim on N=4800 with a
~28%-positive ink target, at both ratios:

| keep | `_rk` all-ones | `ov` | `ch` | `lift` |
|---|---|---|---|---|
| 0.50 | no | 0.502 | 0.283 | +0.220 |
| **1.00** | **yes** | **1.000** | 0.283 | **+0.717** |

and at keep=1.00 a **random** router and a **perfect** one (scores set equal to the target)
print the *identical* `ov 1.000 lift +0.717`. Note the magnitude: +0.717 is not a marginal
pass, it is **larger than run 10's healthy +0.298 / +0.398**. The degenerate column looks
better than the real one.

This is D1's STE trap (K = N ⇒ the multiplier is exactly 1.0) resurfacing in the telemetry
instead of in the gradient, and here it is *expected*: it is what "no pruning" means, and it
is the condition run 5 itself trained under. It must not be "fixed" for this run.

Corollary: **`verify_training_telemetry.py`'s case M** (invert the target and `ov` must move
1.000 → 0.000) also goes dead at keep=1.00. It is a keep=0.50 check. Do not run it against a
keep=1.00 config and read the pass as evidence of anything.

The live columns for run 11 are **`sal`**, **`dev`** and **`p …±std`**.

### Preconditions

| precondition | status |
|---|---|
| the run-5 checkpoint is attachable as a Kaggle dataset | **yes** — runs 9 and 10 both used it |
| run 5's local curve exists at all four budgets | **D12** — 74.72 / 73.16 / 68.70 / 63.25 / 54.39 |
| run 9's ditto | **D12** — 77.62 / 78.22 / 77.37 / 70.67 / 64.61 |
| token sets are comparable across checkpoints | **D12** — `select_mode="ink"` is weight-independent; verified `0.00e+00` at all four budgets. Run 11 must reuse it, not the router |
| the results file will say which checkpoint produced it | **new 2026-09-06** — cell 15's `PROVENANCE` block; `verify_results_provenance.py` passes by *execution*, including the mutate-and-re-stamp check |
| no code change is needed to launch | **yes** — the run is one constant in cell 2. Confirmed 2026-09-09 by reading cell 2 of `kaggle_pruning_run.ipynb` itself: it stands at `DO_TRAIN=True`, `TRAIN_KEEP_RATIO=0.50`, `TRAIN_EPOCHS=5`, `SUPERVISE_SALIENCY=True`, `SALIENCY_THRESHOLD=0.15`, `ATTN_TARGET=False`, `ALLOW_CPU=False` — i.e. run 9's configuration exactly, with `TRAIN_KEEP_RATIO` the only line to touch |
| the resume-train-save chain is verified **on the notebook that will run** | **yes, and only there** — `verify_harness_control.py` scores **39/39** on `kaggle_pruning_run.ipynb` against 36/36 on the canonical one, and the four extra checks are precisely this chain: cell 6 must not starve a `DO_TRAIN` run of training data, cell 7 must resume *from* `RESUME_CKPT`, and cell 7 must save `PRUNED_CKPT` and repoint `EVAL_CKPT` at it before cell 15 restores anything. The canonical notebook has no `DO_TRAIN` branch to check. **Run the verifiers with `argv[1] = kaggle_pruning_run.ipynb`; the default target does not exercise run 11's path.** `verify_results_provenance.py` is 35/35 on both |
| the analysis path exists | **partly.** `eval_why_pruning_helps.py` hardcodes a two-element `CKPTS` and indexes elements 0 and 1 at line 360. Run it **twice on retargeted pairs** — see Analysis for why widening the list is worse than it looks |

**None of these say H1 is right.** They say the run is readable. D12 is the standing reminder
that a well-controlled run can reject the file's own standing guess.

### Configuration

1. **Kaggle → Add Input → the run-5 checkpoint dataset** (the same one runs 9 and 10 used).
2. **Cell 2 `RESUME_CKPT`** → that path. The basename glob resolves it and prints where it
   landed; note it only fires when the variable is already truthy, so leaving it `None` gets
   no help from it.
3. **Cell 2 `TRAIN_KEEP_RATIO = 1.00`.** This is the run's only edit beyond step 2.
4. **Touch nothing else**: `DO_TRAIN=True`, `TRAIN_EPOCHS=5`, `SUPERVISE_SALIENCY=True`,
   `ATTN_TARGET=False`, `SALIENCY_THRESHOLD=0.15`, `ALLOW_CPU=False`. `ATTN_TARGET` staying
   `False` is load-bearing: with it on this becomes run 10's variable stacked on top of this
   one, and cell 2's assert would fire first anyway.
5. **Session options → Accelerator → GPU.**
6. **Run All**, watch the table below, then download
   `/kaggle/working/pruned_ocr_results.zip` and file it as **`run 11/`**.

### What to watch, in order

| stage | expect | if wrong |
|---|---|---|
| cell 2 `PLAN:` line | `retrain router WITH pruning ON (keep_ratio=1.0)` | **read the number, not the sentence** — the branch text is keyed on `DO_TRAIN`, so it says "WITH pruning ON" even at keep=1.00. `keep_ratio=0.5` means step 3 was missed and this is a duplicate of run 9; kill it in the first minute rather than the fifth hour. A literal `{TRAIN_KEEP_RATIO}` with braces means a stale notebook (the missing `f`-prefix was fixed after run 9) |
| cell 7 start | `Resumed /kaggle/input/… (missing=0, unexpected=0)` | nonzero ⇒ not starting where run 9 did, and the entire three-way comparison is void |
| cell 7 header | `TRAINING WITH PRUNING ON: keep_ratio=1.0, epochs=5` | second and last chance to catch a missed step 3 before four-plus hours of GPU |
| epoch lines, `sal` | falls across epochs 1→5, with `[n/N]` nonzero and `x0.5` | flat ⇒ the ink BCE is not training. Check `LAMBDA_SAL` printed as 0.5 |
| epoch lines, `dev` | falls | `dev` is mean \|p − t\|, and after the D4 fix it **is** the gradient magnitude on this term. Flat means no learning signal reaches the router |
| epoch lines, `p …±std` | std stays **> 0** | std → 0 is score collapse — every patch scored alike, which makes `torch.topk` return the first K indices. At keep=1.00 **nothing downstream would notice**, because K = N; this column is the only place it is visible, which is exactly why it is watched here instead of inferred from recall |
| epoch lines, `ov` / `lift` | `ov 1.000`, `lift` a positive constant ≈ `1.000 − ch` | **expected and meaningless — Trap 2, verified by execution.** A random router and a perfect one print the same thing, and the value (+0.717 in the reproduction) is *larger* than run 10's healthy +0.298. Do not read it as the auxiliary working. If `ov` is anything other than 1.000, `TRAIN_KEEP_RATIO` is not 1.00 and step 3 was missed |
| cell 15 `keep=1.00 router CONTROL` | ≈77–80 on the Kaggle venue (run 5 read 77.74 there, run 9 read 77.30) | a number in that band is the **expected** outcome, not a failure. This is run 11's own ceiling and it is not the statistic the run turns on |
| cell 15 provenance | `meta.provenance.eval_ckpt.{path,size_bytes,mtime}` present and naming the newly written checkpoint | absent ⇒ stale notebook; the block landed 2026-09-06. A path pointing at anything but run 11's own file is the `diagnose_decoder.py` silent-fall-through failure this stamp exists to catch |

### Cost — expect **more** than run 9, not the same

Run 9's shape was ≈19 min dataset download + ≈4 h training + ≈3 min cell 13 + ≈42 min cell
15. Run 11 doubles the decoder's cross-attention sequence length for **every training step**
(4800 kept tokens instead of 2400). The encoder is frozen and computes all 4800 either way,
so this is not a 2× on the whole run, but budget **≈5–5.5 h training, ≈6–6.5 h total** and
check it against the session GPU quota before starting.

If it is tight, drop **cell 14** (the merge sweep — never executed, and blocked on Pending 15
regardless) and cell 13 if needed. Do **not** cut `TRAIN_EPOCHS`: it is the controlled
variable, and a 4-epoch run 11 answers a question nobody asked.

### Analysis — two local invocations, no restructuring of the script

The primary readout is **not** cell 15's Kaggle numbers. D11 measured up to 3.4 pts of
local-vs-Kaggle generation drift on bit-identical selections, and D12's run-5/run-9 curves
are local CPU; a Kaggle level cannot be differenced against them. So:

1. Retarget `CKPTS` in `eval_why_pruning_helps.py` to **`[run 11, run 9]`**, `--n 50`.
   → the isolation.
2. Retarget to **`[run 5, run 11]`**, `--n 50`. → the epochs-alone arm, and the first direct
   measurement of the confound D12 could not remove.

Both are two-element lists, so line 360's `A, B = CKPTS[0][0], CKPTS[1][0]` is untouched.

> **Do not add a third element to `CKPTS`, and note that it will not stop you.** Line 360 is
> *indexing*, not tuple-unpacking — verified by execution 2026-09-09, and my first draft of
> this checklist claimed it raised `ValueError`, which is wrong. A three-element `CKPTS`
> runs cleanly: the existence check (line 187) validates all three, the generation loop
> (line 338) sweeps all three at a cost of **≈55 extra minutes**, and the JSON's
> `checkpoints` map (line 564) **records all three** — while every delta, DiD and control
> silently uses only the first two. The output would advertise a three-way comparison and
> contain a two-way one. That is the [[green-checks-need-the-same-suspicion]] failure with
> no check involved at all, and it is why the instruction is two runs on retargeted pairs
> rather than one run on a widened list.

Two things carry over from D12 and must be read the same way:

- `RUN6_REFERENCE_RECALL` is run-5-specific and is already **`[INFO]`, gating nothing**
  (D12's anchor swap). It will read as a mismatch on a run-11 pair. Expected.
- `decide()`'s verdict prose is H2-specific and keys on **keep=0.50 alone**. D12 already
  recorded that this is a narrower proxy than the hypothesis it stands in for. **Read the DiD
  table; do not quote the printed verdict as run 11's answer.**

Each invocation costs ≈110 min local CPU — D12's measured time for the same 2 × 5 × 50
generation grid.

### Acceptance — pre-registered, with the power caveat stated first

**D12's four run-5 rows were all underpowered for a 3-pt effect** (SE 2.31–2.80 ⇒ resolution
4.6–5.6 pts). Run 11 is a third checkpoint measured the same way on the same 50 images, so
its SEs will be comparable. Therefore, written now so it cannot be relaxed later:

> **Report `resolution_pts = 2.0 × SE` on every row. Any row whose resolution exceeds
> `MIN_EFFECT_PTS = 3.0` is UNDERPOWERED, not a null.** A flat `ISO` column is only evidence
> of "no effect" on rows that could have shown one.

Definitions — all paired per image, `select_mode="ink"`, local CPU:

- `Δ_c(k) = recall_c(k) − recall_c(1.00)` — a **within-checkpoint** delta, the only quantity
  that survives the venue problem
- **`ISO(k) = Δ_11(k) − Δ_9(k)`** — the isolation statistic. Negative means run 11 is hurt
  *more* by identical pruning than run 9 is, i.e. pruning-aware training is doing the work.

| outcome | criterion | reading |
|---|---|---|
| **H1 ISOLATED** | `ISO(k) ≤ −3.0` with `\|t\| ≥ 2.0` at **≥ 1** of keep ∈ {0.35, 0.20}, **and** `ISO ≤ 0` at all four budgets | pruning-aware training causes the robustness with epochs held constant. Claim 1 may then say "because it was trained for it", and only then |
| **CONFOUNDED — the epochs did it** | `\|ISO(k)\| < 3.0` at every budget **and** every row powered | run 11 got run 9's robustness *without* pruning. **Claim 1's attribution is wrong**, and the writeup's "if you train for it" has to become "if you train longer" |
| **UNDERPOWERED** | any row failing the resolution test above | the default outcome, not a fallback. Report it and choose nothing |
| **HARNESS FAULT** | run 9 @ keep=1.00 does not reproduce D12's **77.62** within 0.5 pts | nothing else in the run is interpretable. This is D12's replacement anchor — the one pinned to a number that did not yet exist and came back at gap **0.00** |

Controls that must ship with the numbers, mirroring D12 exactly:

- retained ink **identical across checkpoints at all four budgets**, expected `0.00e+00` —
  this is what makes the token sets bit-identical and the DiD readable at all
- every DiD mean **asserted equal** to the difference of the two separately-computed deltas,
  so the arithmetic is checked rather than eyeballed
- run 11's `ablation_selection.json` provenance stamp names **run 11's own checkpoint**

### The prediction, recorded before the run so it can be wrong

**Run 11 will look like run 5, not like run 9**: its curve peaks at keep=1.00 and declines
monotonically, and `ISO` will be negative at all four budgets, significantly so at keep=0.35
and 0.20.

Reasoning: D12 rejected H2, so the decline is a property of unpruned-trained *weights* rather
than of the images — and five more *unpruned* epochs give the router no gradient about
removing a token, because at K = N the STE multiplier is exactly 1.0. That is D1's trap, and
it is the exact condition run 5 was already trained under. Five more epochs of the same
degenerate signal should not manufacture pruning robustness.

**The honest alternative, and why the run is still worth six hours.** Run 5's base checkpoint
was trained on the *other* loss branch — no ink BCE at all, `lambda_entropy = 0.05` instead.
So run 11 gives the router a text-shaped target that run 5 never had. If run 9's advantage is
mostly "five more epochs with a text-shaped auxiliary" rather than "pruning-aware", run 11
inherits it and `ISO` collapses toward zero. That would not be a null; it would **falsify
this project's headline attribution**. I do not expect it, and the prediction above is what
gets checked against the table.

One number I have no calibrated prior for, quoted here so that whatever it is, it was not
chosen after the fact: **`Δ_11(1.00)` against run 5's local 74.72** — the ceiling gain from
five unpruned epochs alone. Retrain drift in this project has been **1.09** and **1.30** pts
on two runs and **10.93** on a third, and on runs 7–8 it cannot be separated from a harness
fault. Any of those magnitudes would be unsurprising.

## Run 11 — result (Kaggle T4, executed 2026-09-14, filed 2026-09-15) — H1 is **ISOLATED at keep=0.35**, the prediction above held, and the statistic did not need the 110-min local runs

**Verdict: `CONFOUNDED` is REJECTED; `H1 ISOLATED` is met at keep=0.35 on the Kaggle venue,
and the pre-registration is now CLOSED LOCALLY (2026-09-16).** The `run11_run9` local pair
(n=50, `is_full_protocol: true`) returns `ISO ≤ 0` at all four budgets and clears
`ISO ≤ −3.0` with `|t| ≥ 2.0` at keep=0.35, 0.25 **and** 0.20 — see "Local pair" below.
Claim 1's attribution survives. The recorded prediction — "run 11 will look like run 5,
not like run 9" — is **confirmed on both of its clauses**.

### Every watch-row passed, including the two that were written to look green when broken

| stage | expected | observed |
|---|---|---|
| cell 2 `PLAN:` | `keep_ratio=1.0` | `keep_ratio=1.0` — and the value interpolated, so the missing-`f` fix is live (run 9's log printed the literal `{TRAIN_KEEP_RATIO}`) |
| cell 2 `CFG:` | `SUPERVISE_SALIENCY=True ATTN_TARGET=False` | exactly that, self-labelled `(target = patch ink > 0.15 -- run 9 config)`. **Trap 1 avoided** |
| cell 7 resume | `missing=0, unexpected=0` | `missing=0, unexpected=0` off the run-5 dataset checkpoint |
| cell 7 header | `keep_ratio=1.0, epochs=5` | `keep_ratio=1.0, epochs=5` |
| `sal` | falls, `[n/N]` nonzero, `x0.5` | 0.4753 → 0.3011, `[1692/1692]`, `x0.5` |
| `dev` | falls | 0.2958 → 0.1926 |
| `p …±std` | std stays > 0 | 0.228 → 0.305, **rising** — no score collapse |
| `ov` / `lift` | `1.000` / positive constant, **meaningless** | `ov 1.000 ch 0.289 lift +0.711` at all five epochs. **Trap 2, exactly as predicted by execution (+0.717).** Read nothing into it |
| cell 15 CONTROL | ≈77–80 | **78.25** — inside the band, as expected, and not the statistic the run turns on |
| cell 15 provenance | names run 11's own checkpoint | `/kaggle/working/adaptive_donut_pruned.pt`, `size_bytes` 1045901771 — **byte-identical to the shipped `run 11/adaptive_donut_pruned.pt`** |

`meta.complete: true`. Decoding untouched at run 9's baked `rp=1.0 / nrns=3`:
`metrics.json` matches that row of `ablation_decoding.json` to 14 significant figures, so
the "this must not touch run 11" constraint held.

### "One variable" is verified by diff, not by trusting the checklist

Same method as run 10. Diffing the executed `__notebook__.ipynb` inside each
`pruned_ocr_results.zip`, **run 10 → run 11 removes exactly two functional lines**:

```
- TRAIN_KEEP_RATIO = 0.50     <- the variable
- ATTN_TARGET = True          <- reverts 13(b), i.e. back to run 9's target
```

Every one of the 81 added lines is the provenance patch, a comment, or `print` text.
Against **run 9** the diff is larger (9 removed / 342 added) but entirely accounted for:
the F3 telemetry block, the provenance patch, and the dead `attn_topk_target` function
sitting behind `if ATTN_TARGET:` — which is `False`. The three ink-target lines are
**unchanged**, merely indented into the `else:` branch:

```
_ink  = patch_ink(pixel_values, _sc.shape[1]).to(_sc.dtype)
_inkn = _ink / (_ink.amax(dim=1, keepdim=True) + 1e-9)
_tgt  = (_inkn > SALIENCY_THRESHOLD).float()
```

and the telemetry reads `_sc.detach()`, so it cannot enter the gradient. **The training
math between run 9 and run 11 differs by `keep_ratio` alone.**

### The isolation statistic — computable from the shipped artifacts, at n=50 paired

**`ablation_selection.json` stores `per_image` recall on all 15 rows, and has since run 9.**
So `ISO` did not need the two 110-minute local runs: runs 9 and 11 were evaluated on the
same 50 images, at the same venue, in the same cell. The controls the checklist demands
both pass **by execution**:

- **token sets bit-identical across checkpoints** — per-image `retained_ink` agrees at
  `0.00e+00` on every `ink` and `random` row. Router rows differ (1.7–3.3e-02), as they
  must, which is what makes the `0.00e+00` a measurement rather than a tautology
- **every DiD mean asserted equal** to the difference of the two separately-computed
  deltas — `assert abs(mean(ISO) − (mean(Δ11) − mean(Δ9))) < 1e-9`, passed at all three
  budgets

| keep | Δ₁₁ | Δ₉ | **ISO** | SE | t | resolution | powered? |
|---|---|---|---|---|---|---|---|
| 0.75 | −1.44 | +0.54 | −1.97 | 2.11 | −0.93 | 4.22 | **UNDERPOWERED** |
| 0.50 | −2.79 | −0.42 | −2.37 | 2.41 | −0.98 | 4.82 | **UNDERPOWERED** |
| 0.35 | −10.19 | +0.30 | **−10.49** | 2.80 | **−3.74** | 5.61 | clears its bar |

**`CONFOUNDED` required `|ISO| < 3.0` at every budget. keep=0.35 breaks it by 3.5×.**

On keep=0.35 versus the power rule: the `resolution_pts = 2 × SE` rule exists to stop a
*flat* row being read as a null. It is not a two-sided gag — −10.49 is nearly **2× its own
resolution floor** and carries `|t| = 3.74 ≥ 2.0`, so it satisfies the `H1 ISOLATED` row as
written. The 0.75 and 0.50 rows are genuinely underpowered and are **"choose nothing"**,
not nulls, exactly as pre-registered.

### Local pair — `run11_run9`, n=50 full protocol, executed 2026-09-16

The venue the pre-registration was written for, including the two tight budgets the Kaggle
grid omits (`results/why_pruning_helps_iso_run11_run9.json`, 116.3 min):

| keep | Δ₁₁ | Δ₉ | **ISO** | SE | t | resolution | ρ |
|---|---|---|---|---|---|---|---|
| 0.50 | −1.45 | +0.60 | −2.05 | 2.22 | −0.92 | 4.44 | −0.06 |
| 0.35 | −8.40 | −0.26 | **−8.15** | 2.71 | **−3.01** | 5.42 | −0.02 |
| 0.25 | −14.31 | −6.96 | **−7.35** | 2.72 | **−2.70** | 5.45 | +0.48 |
| 0.20 | −20.93 | −13.01 | **−7.92** | 2.48 | **−3.19** | 4.97 | +0.56 |

Both pre-registered clauses pass: `ISO ≤ −3.0` with `|t| ≥ 2.0` at keep=0.35 and 0.20 (and
0.25), and `ISO ≤ 0` at all four budgets — Kaggle's keep=0.75 (−1.97) is ≤ 0 as well, so
every budget measured in either venue is negative. Recomputed from `per_image_recall`
independently of the script's own printed table; all four rows reproduce. Where the venues
overlap they agree in sign and ordering (Kaggle −2.37 / −10.49 at keep 0.50 / 0.35 against
local −2.05 / −8.15, gaps inside the SEs).

ρ rises from ≈0 at the loose budgets to **+0.48 / +0.56** at keep=0.25 / 0.20, which is
what lets those rows clear their bars at SEs no worse than the loose rows'.

### The curve shape, which needs no cross-checkpoint arithmetic at all

`select_mode="ink"`, weight-independent, identical token sets:

| keep | run 9 | run 11 |
|---|---|---|
| 1.00 | 77.30 | **78.25** |
| 0.75 | 77.84 | 76.82 |
| 0.50 | 76.89 | 75.47 |
| 0.35 | 77.60 | **68.06** |

**Run 11 peaks at keep=1.00 and declines monotonically. Run 9 does neither — it is flat.**
That is D12's run-5 signature reproduced on a checkpoint that had run 9's epochs, run 9's
loss, run 9's auxiliary and run 9's data, and differed only in whether it pruned while
training.

### The confound, measured alone for the first time

`Δ_11(1.00)` against the **run-5 harness control in run 11's own file** (paired, same 50
images, same session — not a cross-venue comparison):

> **+0.52 pts, SE 2.15, t +0.24** — five unpruned epochs bought **nothing** at the ceiling.

This is the number the checklist said it had no calibrated prior for. It lands at the low
end of the 1.09 / 1.30 / 10.93 retrain-drift range, and it kills the "honest alternative"
that run 9's advantage was mostly *five more epochs with a text-shaped auxiliary*: run 11
had that auxiliary, on that schedule, and inherited none of the robustness.

### Two cautions, so this is not over-read

1. **This is the Kaggle venue; the pre-registration was written for local CPU, and the
   Kaggle grid has no keep=0.25 or keep=0.20** — the two tightest budgets, where the
   prediction says the effect is *largest*. So `ISO ≤ 0 at all four budgets` cannot be
   formally evaluated here, and the two local invocations remain worth running. What makes
   the cross-session comparison trustworthy anyway: **the run-5 harness control reads
   `77.73756569694308` in runs 9, 10 and 11 — identical to all 14 digits**, so these three
   sessions are not drifting against each other the way local drifts against Kaggle.
2. **Cell 15's own prose overstates its case.** It prints `DIFFERENT CEILING - ... this
   1.90 pt gap is what the retrain did to unpruned accuracy, not measurement noise`. That
   1.90 is `max|drift|` over three metrics against run 6, and the metric supplying it is
   **word order**, not recall; recall drifted **0.51**. No SE is computed anywhere in that
   block, and the paired test above puts the recall gap at +0.52 with **t = 0.24**. Same
   genre as `decide()`'s verdict prose — [[green-checks-need-the-same-suspicion]]. **Do not
   quote the 1.90 as an effect.** `meta.control_drift_pts` carries the same quantity
   (1.9038 = run 11's control word-order 54.9538 − run 6's 53.05) and inherits the caveat.

### The acceptance table is asymmetric at n=50, and ρ — not either mean — is why

Reproduced independently of the table above, straight from the `per_image` arrays in the two
`ablation_selection.json` files (separate code path, image ids asserted equal on `i`, the DiD
identity re-asserted to 1e-9): **ISO −1.97 / −2.37 / −10.49, SE 2.11 / 2.41 / 2.80,
t −0.93 / −0.98 / −3.74** at keep 0.75 / 0.50 / 0.35, and Δ₁₁ / Δ₉ as recorded. The two
computations agree to the last printed digit, so the headline row is not an artifact of one
implementation.

`ISO` is a *paired* difference of differences, so

```
Var(ISO) = s_f² + s_r² − 2 ρ s_f s_r        (ρ = per-image corr of the two delta columns)
```

Its resolution is therefore set by ρ, not by the size of either delta. And ρ here is
**essentially zero**:

| keep | s(Δ₁₁) | s(Δ₉) | **ρ** | sd(ISO) | SE | ρ needed for resolution ≤ 3.0 | n needed at this sd |
|---|---|---|---|---|---|---|---|
| 0.75 | 11.52 | 9.86 | **0.03** | 14.93 | 2.11 | 0.52 | 100 |
| 0.50 | 12.64 | 11.51 | **0.00** | 17.06 | 2.41 | 0.62 | 130 |
| 0.35 | 18.22 | 9.28 | **0.08** | 19.82 | 2.80 | 0.90 | 175 |

(`resolution_pts = 2 × SE ≤ 3.0` ⇔ `SE ≤ 1.5` ⇔ `Var(ISO) ≤ 2.25 n`. The last column holds sd
fixed and solves for n, which is the optimistic direction.)

**So `CONFOUNDED` was unreachable before a single image was decoded.** That verdict requires
`|ISO| < 3.0` at every budget **and** every row powered, and no arrangement of these images
could have powered these rows: it needs ρ ≈ 0.5–0.9 against an observed ~0.05, or 100–175
images against a test split that **is** 50. `MAX_EVAL_SAMPLES=50` is not a subsample of FUNSD
test — it is the whole split, so **n is not a knob**.

Two consequences for how the rows above must be read:

1. **The rejection of `CONFOUNDED` is sound; a hypothetical absence of `H1` would not have
   been evidence for it.** A rejection needs one budget to break the `|ISO| < 3.0` bound, and
   keep=0.35 breaks it with `|t| = 3.74` — that argument never touches power. But the two arms
   are not symmetric: at n=50 `H1 ISOLATED` is reachable and `CONFOUNDED` is not. A flat ISO
   row means **"choose nothing"**, and must never be written up as "the effect is a confound".
   This is the `UNDERPOWERED`-is-the-default rule restated as a property of the **design**
   rather than of the data.
2. **The pre-registration set a threshold without checking that it could be cleared.** The rule
   was written as `resolution_pts = 2 × SE` with no prior on SE — yet D12's own artifact, on
   disk since 2026-09-05, carries ISO SEs of **2.67 (keep=0.50) / 2.53 (0.35) / 2.98 (0.25) /
   2.45 (0.20)** — descending keep, this file's convention — i.e. resolution **4.9–6.0**,
   double `MIN_EFFECT_PTS = 3.0`. Any true effect below ~5 pts was going to print
   `UNDERPOWERED` no matter what run 11 did, and that was a ten-second calculation available
   before launch. **Future checklists should carry a predicted resolution beside every
   acceptance threshold**; a bar that cannot be cleared is a decorative gate
   ([[green-checks-need-the-same-suspicion]]).

**ρ is pair- and budget-specific, which is why the two local invocations are still worth their
110 minutes each.** D12's local `run 5 ↔ run 9` pair — same statistic, same 50 images — runs
ρ **0.14–0.57** and clears `|t| ≥ 2` at the two tight budgets the Kaggle grid does not contain:
keep=0.20 `ISO +7.33, t 3.00`; keep=0.35 `+5.77, t 2.28` (positive because run 9 is the focus
in that direction). Tight budgets are where the deltas are both large *and* correlated, which
is exactly the regime paired ISO was chosen for. The Kaggle grid's underpowered 0.75/0.50 rows
are a property of *loose* budgets, not of the statistic.

### The analysis harness that produced it — `scripts/eval_why_pruning_helps.py`, extended 2026-09-15

Was a two-element `CKPTS` list with element 0/1 indexing (the File map's note on why widening
that list is worse than it looks still applies). Now carries a `--pair` selector over three
named checkpoints, and the ISO statistic itself:

| added | what it does |
|---|---|
| `PAIRS` / `--pair` | `run5_run9` (D12, default — reproduces the old behaviour byte-for-byte), `run11_run9`, `run5_run11`. Each pair names its own focus, reference and output path, so no invocation can overwrite another's artifact |
| `per_image_delta()` + ISO block | paired `Δ_c(k) = recall_c(k) − recall_c(1.00)` per image, then `ISO = Δ_focus − Δ_ref`, with `SE`, `t`, `resolution_pts`, and a **hard identity assertion** — `abs(mean(ISO) − (mean Δ_f − mean Δ_r)) ≤ 1e-9` or `SystemExit` |
| `decide_iso()` | the pre-registered table as code: `H1 ISOLATED` / `CONFOUNDED` / `MIXED` / `UNDERPOWERED` / `NO DATA`, branch order following the table so **`UNDERPOWERED` is the default, not a fallback**. `--selftest` executes every branch |
| `LOCAL_ANCHORS` | **replaces a control that was firing on the wrong thing.** The harness anchor read `RESULTS[B]` against run 9's local 77.62, assuming slot B is always run 9. The pre-registered `[run 5, run 11]` invocation puts run 11 in slot B, so it would have compared run 11's *first ever* local measurement against run 9's anchor and failed the whole sheet. Now keyed by checkpoint label, and a pair with no pre-registered anchor **says so and fails its controls** rather than inventing one |
| `decide()` suppression | H2's verdict prose is hardcoded "Run 5". On `run11_run9` it printed *"Run 5's keep=0.50 delta is +0.21"* about run 11 — a false sentence in a saved artifact. Suppressed to `N/A (H2 verdict is run-5-specific)` when slot A is not run 5, because H2 is a claim about a checkpoint never trained with pruning; relabelling it would have been worse |
| `--rescore` pair adoption | `--rescore` ignored `--pair` and died ~200 lines in with a bare `KeyError`. It now adopts the pair recorded in `_blob["meta"]["pair"]` and errors clearly on mismatch |

JSON gains `pair`, `focus`, `reference`, `iso`, `iso_verdict`, `iso_verdict_text`,
`local_anchors`. Regenerating `results/why_pruning_helps_rescored.json` under the new code
changes its bytes; the substantive numbers are unchanged (−1.57 / −6.03 / −11.47 / −20.34 vs
D12's recorded −1.56 / −6.02 / −11.47 / −20.33, rounding only) and the source
`results/why_pruning_helps_local.json` was verified untouched.

### What this changes

- **Claim 1's "Attribution limit" can be downgraded but not deleted.** "H1 supported, not
  isolated" becomes **"H1 isolated at keep=0.35 (Kaggle, n=50 paired); the local
  pre-registration is not yet closed."** Do not write "H1 proven".
- **Pending 3** wanted the two `rp=1.05` rows re-measured on "the run-11 checkpoint once it
  lands". It has landed: `run 11/adaptive_donut_pruned.pt`, provenance-stamped.
- **Pending 15**'s merge sweep was queued "behind run 11". Run 11 is no longer the blocker.

## Run 12 — launch checklist (written 2026-09-16, **before launching**) — the first measurement of the merge stage

This is Pending **1c**'s last unbuilt piece and Pending **15**'s sweep. Run 11 was the
stated blocker and it has landed, so the only thing left between the repo and a measured
`BipartiteTokenMerger` is GPU time.

**One variable: `merge_ratio > 0`.** Same checkpoint, same 50 FUNSD test documents, same
decoding, same seed, and — the point of the design — **the same final token count** as the
row it is compared against.

### The design, in one table

Every merge row is paired with a prune-only row at the identical post-compression token
count `M`, so the delta cannot be a budget effect. `K = max(1, round(4800 · keep))`,
`r = min(round(K · merge), K // 2)`, `M = K − r` — all 13 rows verified by **execution**,
including `model.last_enc_len`, i.e. what the decoder actually received:

| pair | merge row | prune twin | **M** | what it isolates |
|---|---|---|---|---|
| ceiling | keep=1.00, m=0.20 | keep=0.80 | 3840 | merging alone, no pruning at all |
| main | keep=0.50, m=0.20 | keep=0.40 | 1920 | the deployed configuration |
| tight | keep=0.35, m=0.20 | keep=0.28 | 1344 | the budget where run 11 isolated H1 |
| heavy | keep=0.50, m=0.40 | keep=0.30 | 1440 | twice the merge ratio |
| **mechanism** | keep=0.50 **ink**, m=0.20 | keep=0.40 ink | 1920 | merging with the router's weakness removed |
| **mechanism** | keep=0.35 **ink**, m=0.20 | keep=0.28 ink | 1344 | ditto at the tight budget |
| **sabotage** | keep=0.50, m=0.20, `checkerboard` | same row, `rank_parity` | 1920 | does the ordering fix move *recall* |

13 new rows, **28 total**. The `ink` arm is not decoration: the router is the known-weak
selector (D1 — anti-correlated with patch ink), so a loss on router rows alone cannot
separate "merging is bad" from "the router's kept set is already too degraded to compress
further". The ink pair is the mechanism test; the router pair is the deployed-system test.

`rank_parity` reproduces the pre-fix `arange(0, K, 2)` split **exactly** — `grid_w = 1`
makes `((i // 1) + (i % 1)) % 2 == i % 2` — so the sabotage arm is a call-site argument
with zero merger changes, and it is verified bit-for-bit against the old merger extracted
from the canonical notebook at runtime. Without it the sweep cannot say whether the
checkerboard fix bought a reader anything, only that it changed a partition statistic.

Rows are **interleaved merge/twin** and the sabotage row is last, so a dying Kaggle session
leaves whole pairs rather than orphaned merge rows; `ablation_selection.json` is rewritten
after every row.

### What this run can and cannot answer — stated before the numbers

Every checkpoint in this project was trained at `merge_ratio = 0.0`, so a merged token is an
input the decoder's cross-attention has **never seen**. By D12's own logic — and by run 11's
isolation of H1 — a negative result is the **predicted** outcome and is *not* evidence that
ToMe is worthless. The bounded question is exactly:

> On a merge-naive checkpoint, does compressing to `M` tokens by *merging* cost less than
> compressing to the same `M` by *pruning*?

and, from the sabotage row:

> Does the checkerboard fix change recall, or only the synthetic missed-redundancy number?

Training with merging on is the follow-up a competitive or near-competitive result would
license. It is **not** in this run.

### Three traps, all of which produce a *green-looking* run

**Trap 1 — the canonical notebook still carries the broken split.**
`kaggle_token_pruning_ocr.ipynb` has the old `forward(self, tokens, merge_ratio=0.20,
coords=None)` with no `orig_idx`, and neither of its call sites passes one. Upload the
**generated** `kaggle_pruning_run.ipynb`. A stale copy would run every merge row through
rank-parity and print a perfectly plausible "merging costs a couple of points" table.
Check at runtime: cell 4 must define `checkerboard_color`, and exactly **one** row may
report `tome_split='rank_parity'` — the last one.

**Trap 2 — the `tok` column reports the LAST image's M, not the row's.** `visual_tokens` is
overwritten each image. That is why per-image `tokens` exists and why
`assert_token_matched()` is a hard assert checked **per image** *and* absolutely against
`EXPECTED_M`. Two rows agreeing on a *wrong* M would pass a match-only check.

**Trap 3 — row 0's drift from `RUN6_REFERENCE` is expected, and the harness control is
silent.** With `DO_TRAIN = False`, cell 15 prints `HARNESS CONTROL skipped: DO_TRAIN is off,
so row 0 below already IS the harness control` — there is no second checkpoint to compare
against. These are **run-9** weights, not the run-5 weights that produced
`RUN6_REFERENCE = (77.74, 64.70, 53.05)`; run 9 read **77.30** at this row on Kaggle. A
value in the 77–78 band is the expected outcome, not a fault. A collapse below ~70 is the
real failure signal (that is what a wrong `keep_ratio` or a broken prompt looks like — see
`run_nrns_rp_sweep.py`'s 23.49 incident).

### Preconditions

| precondition | status |
|---|---|
| the notebook runs the **real** merger | **yes, by execution** — `scripts/verify_tome_merge_port.py`, **85 checks, exit 0**, including merger output equal to `src/tome.py` bit-for-bit at B ∈ {1,2} × four `(keep, merge)` configs |
| that equality is not vacuous | **checked** — code spliced from `src/` and compared against `src/` passes no matter what, so every equality check is paired with a non-vacuity check: checkerboard vs rank_parity must *disagree* (max \|diff\| ≈ 5.6), merging must compact rather than pass through, and missed horizontal/vertical redundancy is re-measured on the **shipped** notebook code against its own null: **49.7% / 46.5% → 0.0% / 0.0%** |
| the pre-fix split is reproducible as a control | **yes** — `rank_parity` equals the old merger **bit-for-bit** at 6 configs, and the old merger is extracted from the canonical notebook *at runtime* rather than hand-copied, so it cannot drift into agreeing with the new one |
| token-match arithmetic | **verified by execution** on all 13 rows, against `meta['compressed_tokens']` **and** `model.last_enc_len` |
| the 28-row harness completes | **yes** — the whole cell 15 runs end to end against stubs: row counts, `by`/`by_all` with no collision, Q3 pool exclusion, all 6 Q6 pairs, the sabotage row, the JSON write |
| the token-match assert can fail | **yes** — fed a deliberately mismatched pair (M=1920 vs M=1680) and required to raise. An assert nobody has seen trip is a comment |
| every knob is in the artifact | **yes** (D5) — every row records `merge_ratio` and `tome_split`; `tome_split` is `None` when merging is off, so it cannot imply a split that never ran |
| run 9's checkpoint is attachable as a Kaggle dataset | **MANUAL STEP, not verified from here.** `run 9/adaptive_donut_pruned.pt` exists locally; it must be uploaded as a dataset and attached |
| the existing 15 rows are unchanged | **yes** — `verify_selection_ablation.py` still exit 0, all Q1–Q5 verdicts; `SELECTION_CONFIGS` was appended to, never retyped |

**None of these say merging will work.** They say the run is readable.

### Configuration

1. **Kaggle → Add Input →** the **run-9** checkpoint dataset (`adaptive_donut_pruned.pt`).
   Run 9 trained at keep=0.50, which is where four of the six pairs sit.
2. **Cell 2 `RESUME_CKPT`** → that path. This also flips `EVAL_ONLY = bool(RESUME_CKPT)`.
   **This is the only edit the run needs, and it is the one that cannot be shipped:** the
   path does not exist until the dataset is uploaded, and `verify_harness_control.py` +
   `verify_phase2c_fixes.py` both assert cell 2 ships `RESUME_CKPT = None`, so the generator
   is not allowed to guess it.
3. ~~Cell 2 `DO_TRAIN = False`~~ — **no longer an edit; the generator now ships it False**
   (2026-09-16). It was a manual step in the first draft of this checklist, which was a
   mistake of the kind this file exists to catch: a hand-edit that has to be remembered is a
   hand-edit that gets missed, and missing this one silently spends five hours retraining and
   moves the checkpoint out from under the token-matched pairs. Flipping the default created
   a *new* silent failure in exchange — `DO_TRAIN=False` with `RESUME_CKPT=None` sweeps a
   **randomly initialised router** and still prints all 28 rows, Q1–Q6 and a results JSON —
   so the flip ships with `assert DO_TRAIN or RESUME_CKPT` beside it, and
   `verify_attn_train_step.py`'s gate table drives **both** directions of it (6/6 → **8/8**).
4. **Touch nothing else**: `ALLOW_CPU=False`, `ATTN_TARGET=False`, `SELECTION_MAX_LEN=512`,
   `SELECTION_SEED=0`, `MAX_EVAL_SAMPLES=50`.
5. **Session options → Accelerator → GPU.**
6. **Run All**, watch the table below, then download
   `/kaggle/working/pruned_ocr_results.zip` and file it as **`run 12/`**.

### What to watch, in order

| stage | expect | if wrong |
|---|---|---|
| cell 2 `PLAN:` line | `DO_TRAIN=False -> sweep only on RESUME_CKPT` and `RESUME_CKPT=set` | `RESUME_CKPT=None` now **raises in cell 2** rather than sweeping an untrained router, so the failure is loud and costs a minute. `DO_TRAIN=True` would mean someone edited the shipped default back — kill it in the first minute rather than spend five hours retraining |
| cell 6 | `EVAL-ONLY mode: skipped train set` | if SynthDoG starts downloading, `RESUME_CKPT` did not take and `EVAL_ONLY` is False |
| cell 11 | `Loaded /kaggle/input/… (missing=0, unexpected=0)` | nonzero ⇒ wrong checkpoint or wrong architecture; every row below is void |
| cell 15 harness control | `skipped: DO_TRAIN is off, so row 0 below already IS the harness control` | expected — Trap 3 |
| row 0 `keep=1.00 router CONTROL` | **77–78** (run 9 read 77.30 here); drift vs `RUN6_REFERENCE` is `[INFO]` | below ~70 is a wiring failure, not a retrain effect |
| the 13 new rows | each merge row prints its `tome_split`; exactly one says `rank_parity` | more than one ⇒ a call-site bug; zero ⇒ Trap 1, you uploaded the wrong notebook |
| Q6 table | 6 pairs, no `MISSING --`, and **no `AssertionError`** | an assertion here is the design working: the pair did not land on the same M, so its delta would have been a budget effect in a merging costume. Do not relax it — fix the arithmetic |
| Q6 `res` column | printed per row, and the verdict reads **UNDERPOWERED** rather than "indistinguishable" when it exceeds 3.0 | a flat row with no `res` beside it is the run-11 failure repeating |
| `SABOTAGE CONTROL` | `M=1920`, both rows present, `res` printed | skipped ⇒ the session died before the last row; the six pairs are still readable |

### Cost — ≈1.5–2 h, and nothing is lost if it dies

No training. Run 11's cell 15 took ≈42 min for 15 rows ⇒ ≈2.8 min/row ⇒ **≈78 min for 28
rows**. Merge rows are *not* cheaper in wall-clock: D3 measured latency tracking **generated**
tokens (r = +0.93 / +0.98), not visual tokens, and −65% of visual tokens bought −7.1% of
wall-clock. Add ≈10 min for the HF model plus the FUNSD test split and ≈3 min for cell 13.
Budget **≈1.5–2 h**, comfortably inside the session quota. Per-row JSON means a session
death costs at most one row — and because rows are interleaved, whole pairs survive.

### Acceptance — pre-registered, with a **predicted resolution** beside every threshold

`Δ = recall(merge row) − recall(prune twin)`, paired per document at the same `M`, n=50,
10 000 bootstrap resamples over **documents**. `res` = that pair's own 95% CI half-width,
printed per row, and `Q6_RESOLUTION_PTS = 3.0` is the pre-registered **bar** — a bar, not a
measurement, and the cell keeps the two separate.

**Predicted resolution, derived from run 11's own artifact rather than guessed.** Run 11's
per-image delta columns carry `sd` **9.28–18.22** at n=50 ⇒ `SE` 1.31–2.58 ⇒ **res 2.6–5.2
pts**. Those were deltas against keep=1.00, i.e. large budget changes; Q6's pairs hold `M`
fixed and vary only *how* the tokens were obtained, so their delta columns should sit at the
low end of that band — but that is a reasoned expectation, not a measurement. **Predicted
res: 2.5–4.5 pts, straddling the 3.0 bar.** Consequence, written now so it cannot be
explained away later:

| outcome | criterion | is it reachable at the predicted res? | reading |
|---|---|---|---|
| **MERGING LOSES** | CI excludes 0 with `Δ < 0` on **≥1 router pair and ≥1 ink pair** | **yes** — the losses this project has seen when compression exceeds what a checkpoint was trained for are −6 to −20 pts, far above any plausible `res` | merging is not a drop-in at inference on merge-naive weights. **This is the predicted outcome.** It licenses *training* with `merge_ratio > 0`; it does **not** license dropping the stage |
| **MERGING WINS** | CI excludes 0 with `Δ > 0` on **≥1 ink pair** | yes if the effect is ≳4 pts | stronger than this run was designed to find. Read the ink pair, which isolates the mechanism from the router's weakness |
| **INDISTINGUISHABLE** | every pair's CI includes 0 **and** every pair's `res ≤ 3.0` | **AT RISK — this is the verdict the predicted resolution most likely blocks.** If the pairs come in at 4–5 pts the cell prints UNDERPOWERED and this verdict is unreachable | "merging is free to within this harness's resolution" — the *good* outcome for the architecture, and the one power is most likely to deny |
| **UNDERPOWERED** | any flat pair with `res > 3.0` | the default, not a fallback | choose nothing from that row. **n is not a knob**: `MAX_EVAL_SAMPLES = 50` **is** the whole FUNSD test split |

Sabotage row, judged separately and on its own `res`:

| outcome | criterion | reading |
|---|---|---|
| **fix is real in recall** | CI excludes 0, `Δ > 0` | the 49.7%/46.5% → 0.0%/0.0% partition numbers correspond to something a reader cares about |
| **fix hurt** | CI excludes 0, `Δ < 0` | adjacent-patch similarity was information the decoder was using. Stop quoting the parity statistic as an improvement and re-open the split design |
| **unproven in recall** | flat, `res ≤ 3.0` | **most likely.** The fix is *correct about the partition* and *unproven about the outcome*. Write it that way |
| **underpowered** | flat, `res > 3.0` | licenses nothing at all — not even "the fix changes nothing" |

**Seven uncorrected comparisons** run in this cell (6 pairs + sabotage). A single marginal
row is the least interesting thing in the table; the evidence is the **pattern** — the two
ink pairs agreeing with the two router pairs at the same merge ratio, and the tight budgets
agreeing with the loose ones. The cell prints this reminder above its own verdict.

### The prediction, recorded before the run so it can be wrong

> **FALSIFIED by run 13 (2026-09-17). Left unedited below; the correction is here, not in the
> text.** The prediction was wrong in direction, not just in magnitude: **0 of 6 pairs favoured
> pruning, 2 favoured merging, 3 were underpowered, 1 was indistinguishable.** Nor did the
> ordering hold — the *smallest*-loss row I named (the ceiling, M=3840) produced the largest
> merge *win* (+3.12), and the largest-loss rows I named came back underpowered. What the run
> actually resolved, on the sharper selection-held-fixed contrast rather than Q6's
> differently-selected pairs: **merging away 20% of the kept set is free (five nulls); merging
> away 40% costs −3.86 [−7.47, −0.38].** See "Run 14 — launch checklist" for the table. The
> standing lesson is that this project's merge results keep coming back *less* negative than
> D12's off-distribution logic predicts, so a pre-registration reasoned purely from D12 will
> over-predict harm.

**Merging will lose at equal `M`, on every pair, and lose most at the tight budgets.**
Ordering: the ceiling row (keep=1.00, m=0.20, M=3840) is the *smallest* loss, because 80% of
its tokens pass through untouched; keep=0.35/m=0.20 (M=1344) and keep=0.50/m=0.40 (M=1440)
are the largest.

Reasoning: D12 rejected H2, so the accuracy decline under compression is a property of the
**weights** rather than of the images, and run 11 isolated H1 — run 9's robustness comes from
having been *trained* for the compression it faces. Merging is a compression no checkpoint in
this repo was ever trained for. A merged token is a convex combination of two patch
embeddings, which is not a point the frozen encoder ever emits, so the decoder's
cross-attention is being fed off-manifold inputs.

**The sabotage row is where I have no calibrated prior**, and it is the reason the row exists.
Merging spatial neighbours is *more* defensible a priori than merging score-rank neighbours,
but "defensible" is not "measurable at n=50". I expect it flat. If it is flat **and powered**,
the honest write-up sentence becomes "the checkerboard fix is correct about the partition and
makes no measurable difference to recall on a merge-naive checkpoint" — a narrower claim than
this file currently implies, which is exactly what the row is for.

**What would falsify the framing above:** merging *winning* at equal `M` on an ink pair. That
would mean off-distribution inputs are costing less than D12's logic predicts and that the
merge stage is close to free — which would make training with merging on the immediate next
run rather than a speculative follow-up.

One number quoted here so that whatever it is, it was not chosen after the fact: **row 0's
drift from 77.74 on run-9 weights.** Run 9 read 77.30 at this row on Kaggle, so ≈−0.4;
anything inside ±1.5 would be unsurprising.

## Run 12 — result (Kaggle T4, executed 2026-09-16, filed 2026-09-18) — **the wrong checkpoint was attached**, so this is a run-5 merge study; its Q6 table measures the router, not the merger

The architecture ran end to end for the first time here: frozen Swin-B → router prune →
`BipartiteTokenMerger` → mBART decoder, 28 rows, Q1–Q6 and the sabotage row all printed,
60.2 min. **The mechanism worked. The experiment did not answer the question it was
launched to ask**, and the reason is a single line of the launch checklist that was not
followed.

### What it actually evaluated — read the provenance stamp, not the plan

The checklist above says `RESUME_CKPT` = **run 9's** `adaptive_donut_pruned.pt`. The
provenance block in `run 12/ablation_selection.json` says otherwise:

```
eval_ckpt: /kaggle/input/datasets/nafis8766/token-pruning-dataset/adaptive_donut_funsd.pt
           size_bytes 1045901275   mtime 2026-09-16T17:37:26Z
```

That is **run 5's** checkpoint — the `adaptive_donut_funsd.pt` that runs 9/10/11 all *resumed
from*, not the pruning-aware weights run 9 *produced*. Two independent facts confirm it by
execution rather than by filename:

- `control_drift_pts = 0.0037` against `RUN6_REFERENCE = (77.74, 64.70, 53.05)`. Run 6 is
  run 5's own eval. A near-exact reproduction of run 6's control is only possible on run 5's
  weights; the checklist itself predicted ≈−0.4 drift for run-9 weights, and run 13 (which
  *did* attach run 9's) came back at **1.087**.
- `size_bytes 1045901275` vs run 9's `1045901771` — a 496-byte difference, the pruning-era
  keys run 5 predates.

**This is the provenance stamp earning its place.** It was added in run 9 (F2) precisely so a
results file could name its own weights, and it is the only reason this is a *finding* rather
than a table of numbers that quietly disagreed with run 13 for eighteen months. The stamp is
now the first thing to read in any results JSON, before any row.

### Why that makes the Q6 table uninterpretable as a merge result

Run 5's router head was never trained with pruning on. On these weights it is not merely weak
— it is **anti-selective**, the run-7 sign-inversion signature:

| keep=0.50, M=2400 | recall |
|---|---|
| `router` | **24.97** |
| `stratified` | 30.07 |
| `stratified_negated` | 46.71 |
| **`negated`** (the router's own scores, inverted) | **51.65** |
| `random` | 59.06 |
| `ink` (oracle) | 73.69 |

The router scores **worse than its own negation and less than half of random.** Every Q6 pair
that compares a *lightly-selected merge row* against a *heavily-selected prune twin* is
therefore measuring how bad the run-5 router is, wearing a merging costume:

| pair | M | merge | prune | Δ | printed verdict | what it actually measures |
|---|---|---|---|---|---|---|
| keep1.00 m0.20 vs keep0.80 | 3840 | 77.53 | **40.71** | **+36.83** | MERGING WINS | at keep=1.00 the router selects *nothing*; the twin must discard 20% **using the broken router** and loses 37 pts. Nothing about merging is in this number |
| keep0.50 m0.20 vs keep0.40 | 1920 | 26.23 | 22.78 | +3.45 | MERGING WINS | both rows already collapsed; a 3.45-pt gap between 26 and 23 is noise on a floor |
| keep0.35 m0.20 vs keep0.28 | 1344 | 23.57 | 21.91 | +1.66 | indistinguishable | same |
| keep0.50 m0.40 vs keep0.30 | 1440 | 26.00 | 21.29 | +4.70 | MERGING WINS | same |
| **ink** keep0.50 m0.20 vs 0.40 | 1920 | 72.47 | 73.41 | −0.94 [−4.20, +2.41] | UNDERPOWERED | **interpretable** — selection is the oracle, so only the merger differs in kind |
| **ink** keep0.35 m0.20 vs 0.28 | 1344 | 68.27 | 62.87 | **+5.39** [+0.82, +10.11] | MERGING WINS | **interpretable** |

**Only the two `ink` pairs survive.** This is exactly what the launch checklist said the ink
arm was for — "if merging only looks bad under the router we cannot separate *merging is bad*
from *the router's kept set is already so degraded that any further compression is fatal*" —
and the arm did its job in the opposite direction from the one anticipated: it is the *router*
pairs that had to be discarded, not the ink ones.

### The contrast that is safe on any checkpoint — hold selection fixed

Q6's pairs vary **two** things at once (how many tokens the router picks, and whether the rest
are merged). A contrast that holds `keep` and `select_mode` fixed and switches only the merger
isolates the stage. Recomputed from `run 12/ablation_selection.json` per-image arrays, paired
by document, n=50, 20 000 resamples:

| keep | mode | m | K→M | merged | unmerged | Δ | 95% CI | res | |
|---|---|---|---|---|---|---|---|---|---|
| 1.00 | router | 0.20 | 4800→3840 | 77.53 | 77.74 | −0.20 | [−3.05, +2.73] | 2.89 | null |
| 0.50 | router | 0.20 | 2400→1920 | 26.23 | 24.97 | +1.26 | [−0.72, +3.39] | 2.06 | null |
| 0.50 | router | 0.40 | 2400→1440 | 26.00 | 24.97 | +1.03 | [−0.98, +3.00] | 1.99 | null |
| 0.35 | router | 0.20 | 1680→1344 | 23.57 | 25.05 | −1.48 | [−3.33, +0.36] | 1.84 | null |
| 0.50 | ink | 0.20 | 2400→1920 | 72.47 | 73.69 | −1.22 | [−4.02, +1.61] | 2.81 | null |
| 0.35 | ink | 0.20 | 1680→1344 | 68.27 | 65.28 | +2.99 | [−0.85, +6.68] | 3.77 | underpowered |

Five nulls and one underpowered row. The tight `res` on the collapsed router rows is not
power — it is three rows agreeing that they are all on the same floor.

### Verdict

**Run 12 licenses one claim: the four-stage pipeline executes correctly on a GPU and its token
arithmetic holds** (Q6's hard assert passed on all 50 images of all 6 pairs — every merge row
and its twin landed on identical `M`). Its accuracy table is a run-5 study and is superseded
by run 13 in every respect. Do **not** quote `+36.83`, and do not quote run 12's printed
aggregate verdict.

## Run 13 — result (Kaggle T4, executed 2026-09-17, filed 2026-09-18) — the real pre-registered run; **merging 20% of the kept set is free, merging 40% costs −3.86 pts**

Same 28 rows, same code, 64.0 min, on the checkpoint the plan named:

```
eval_ckpt: /kaggle/input/datasets/nafis8766/adaptive-donut-run9/adaptive_donut_pruned.pt
           size_bytes 1045901771   mtime 2026-09-17T08:48:22Z
control_drift_pts = 1.087
```

Row 0 read **77.30** against `RUN6_REFERENCE`'s 77.74 — the checklist pre-registered "≈−0.4,
anything inside ±1.5 would be unsurprising", and −0.44 is what it got. The router is healthy
here (keep=0.50 router **79.63**, above the keep=1.00 control and far above `negated` 15.65 and
`random` 62.56), which is what makes the router pairs readable in this run and not in run 12.

### Q6 as printed

| pair | M | merge | prune | Δ | 95% CI | res | verdict |
|---|---|---|---|---|---|---|---|
| keep1.00 m0.20 vs keep0.80 | 3840 | 79.70 | 76.58 | **+3.12** | [+0.21, +6.05] | 2.9 | MERGING WINS |
| keep0.50 m0.20 vs keep0.40 | 1920 | 80.17 | 77.31 | +2.86 | [−0.09, +6.16] | 3.1 | UNDERPOWERED |
| keep0.35 m0.20 vs keep0.28 | 1344 | 73.63 | 73.85 | −0.22 | [−3.42, +2.86] | 3.1 | UNDERPOWERED |
| keep0.50 m0.40 vs keep0.30 | 1440 | 75.77 | 77.05 | −1.29 | [−4.81, +2.26] | 3.5 | UNDERPOWERED |
| ink keep0.50 m0.20 vs 0.40 | 1920 | 78.79 | 76.51 | +2.28 | [−0.30, +5.05] | 2.7 | indistinguishable |
| ink keep0.35 m0.20 vs 0.28 | 1344 | 75.94 | 71.88 | **+4.06** | [+0.43, +8.05] | 3.8 | MERGING WINS |

**2 pairs favour merging, 0 favour pruning, 1 indistinguishable, 3 underpowered.** The
predicted resolution (2.5–4.5, straddling the 3.0 bar) was right, and the consequence the
checklist pre-registered — that UNDERPOWERED would be the modal verdict — is what happened.

### The printed aggregate verdict overstates its own table — in **both** runs

Cell 15 ends Q6 with `=> MERGING BEATS PRUNING AT EQUAL M, on weights that never saw a merged
token.` That line is emitted whenever `n_favour_merge > n_favour_prune`, **with no reference
to how many pairs were unresolved.** In run 13 it fires on 2-of-6 significant with 3
underpowered; in run 12 it fires on a table whose four router pairs are void. "Beats" is not
supported by either.

This is the same defect class already fixed twice this cycle — *prose that overstates the
statistic beneath it* — and it is the one that survived into two shipped runs because the
numbers above it were correct. The rows, CIs and `res` column are all sound and are what should
be quoted. **Pending: tighten the aggregate to require `favour_merge ≥ favour_prune + 2` and
`underpowered ≤ 1`, or drop the sentence and let the table speak.** ***Done 2026-09-18 — the bar
landed as ≥2 resolved one way AND ≤1 underpowered, applied to both directions. See changelog
(g)1.***

### The primary result — selection held fixed

Recomputed from `run 13/ablation_selection.json`, paired by document, n=50, 20 000 resamples:

> **Bootstrap endpoints below are one draw.** The m=0.40 row's CI appears in this file with three
> different endpoint pairs (all within ±0.05, all excluding zero) — see the table under "M1
> extended to the merge stage" before treating any difference as a discrepancy. The **mean** is
> deterministic; the endpoints are not.

| keep | mode | m | K→M | merged | unmerged | Δ | 95% CI | res | |
|---|---|---|---|---|---|---|---|---|---|
| 1.00 | router | 0.20 | 4800→3840 | 79.70 | 77.30 | +2.40 | [−0.70, +5.56] | 3.13 | underpowered |
| 0.50 | router | 0.20 | 2400→1920 | 80.17 | 79.63 | +0.54 | [−2.34, +3.80] | 3.07 | underpowered |
| **0.50** | **router** | **0.40** | **2400→1440** | **75.77** | **79.63** | **−3.86** | **[−7.54, −0.35]** | **3.59** | **RESOLVED** |
| 0.35 | router | 0.20 | 1680→1344 | 73.63 | 75.85 | −2.23 | [−6.37, +1.72] | 4.04 | underpowered |
| 0.50 | ink | 0.20 | 2400→1920 | 78.79 | 76.89 | +1.90 | [−0.69, +4.68] | 2.68 | null |
| 0.35 | ink | 0.20 | 1680→1344 | 75.94 | 77.60 | −1.67 | [−4.79, +1.23] | 3.01 | underpowered |

**One row resolves, and it is the only row where merging is doing real work** (40% of the kept
set, 2400→1440). Everything at m=0.20 is flat.

**The resolved row was checked against its own noise before being believed**, because its CI
upper bound sits only 0.35 pts from zero and a bootstrap endpoint that close is usually a seed
artifact. It is not:

- **12 of 12** bootstrap seeds (B=20 000 each) exclude zero; the endpoint moves by ±0.05 pts
  across seeds, so the 0.35-pt margin is ≈7× its own resampling noise.
- Two independent tests agree in sign and roughly in strength: paired *t* **p = 0.040**,
  Wilcoxon signed-rank **p = 0.0048**.
- Sign test: **29 of 50 documents worse under merging, 15 better, 6 tied.**

Honest limit: at *t* p = 0.040 this row would **not** survive a Bonferroni correction over the
six contrasts (α = 0.0083); on the rank test (p = 0.0048) it would. Quote it as a real but
single-row effect.

### The supported claim

> On a pruning-aware checkpoint, **merging away 20% of the kept set is free** to within this
> harness's resolution — at four different budgets, under both the router and the ink oracle.
> **Merging away 40% costs −3.86 [−7.54, −0.35] pts.**

Which, via M1 (`results/kv_memory_local.json`, 32 768 B/token of decoder cross-attention KV at
fp32), licenses **2.5× KV reduction at M=1920 at no measured accuracy cost**, and makes 3.33× at
M=1440 the thing run 14 is trying to buy. Note what this is *not*: D3/D11 stand, there is no
encoder-side saving, and wall-clock barely moves.

> **2026-09-18: that "via M1" is now literally true.** When this was written it was not — M1's
> JSON held five prune-only rows and the 2.5× was arithmetic I did in prose (4800/1920) beside
> an accuracy number from a different file. `eval_kv_memory.py` now **measures** the M=1920 row:
> 150.00 → **60.00 MiB, 2.50×**, and re-derives the accuracy pairing from run 13's per-image
> arrays at runtime. See "M1 extended to the merge stage". The figures did not change; the
> evidence behind them did.

### The sabotage row is now closed on two checkpoints — **and on a third, run 14 (2026-09-21): CLOSED**

| run | weights | checkerboard | rank_parity | Δ | 95% CI | res |
|---|---|---|---|---|---|---|
| 12 | run 5 | 26.23 | 27.74 | −1.51 | [−3.22, +0.19] | 1.7 |
| 13 | run 9 | 80.17 | 80.46 | −0.29 | [−3.10, +2.76] | 2.9 |

Null twice, on two very different checkpoints, with `rank_parity` numerically **higher** both
times. Run 12's row is the *powered* one (res 1.7 at n=50) — an accident of both rows sitting
on the collapsed floor, but a real bound nonetheless.

**Write it exactly this way:** the checkerboard fix is **correct about the partition and
unproven about recall.** `49.2%/50.5% → 0.0%/0.0%` missed-redundancy is a claim about the
split, not about OCR accuracy, and `scripts/diagnose_tome_parity.py` measures the former only.
The fix stays — merging spatial neighbours is the defensible design and the port is what let
`src/tome.py` become the single source — but it must not be quoted as an accuracy improvement.

### What run 13 changed about the plan

The launch checklist's framing paragraph said a negative result was *expected* and that
training with `merge_ratio > 0` was "a speculative follow-up… not in this plan". It also named
its own falsifier: *"merging **winning** at equal M on an ink pair … would make training with
merging on the immediate next run."* That happened (ink keep=0.35, +4.06 [+0.43, +8.05]), so
**run 14 is that run**, launched under the falsifier the plan wrote for itself rather than
under a preference formed after seeing the numbers.

## Run 14 — launch checklist (written 2026-09-18, **before launching**) — put merging INTO training

> **EXECUTED 2026-09-18; result filed below as "Run 14 — result".** Verdict on the primary was
> **UNDERPOWERED** (flat at −0.28 but res 3.95 > the 3.6 bar), which is what the prediction at
> the end of this checklist said would happen. **3.33× at M=1440 is not licensed; 2.5× at
> M=1920 remains the measured limit.** Read this checklist as pre-registration only — the
> scoring is in the result section.

Run 13 measured merging on weights that had never seen a merged token. This run removes that
condition, and it is the first run in this project whose training graph contains all four
stages of the architecture: frozen Swin-B → router prune → **ToMe merge** → mBART decoder.

### The question, and why run 13 forced it

Run 13's own rows, re-derived here with **selection held fixed** — the merge row and its
base row use the *identical* `topk_indices`, so the only difference is that the merger ran.
This is a sharper contrast than the notebook's Q6 table, which pairs a merge row against a
*differently selected* prune row at the same `M`:

> **Same caveat as the run-13 table: these endpoints are one bootstrap draw** and differ by
> ≤0.05 from the ones filed two sections above. See the three-way table under "M1 extended to
> the merge stage". Acceptance for run 14 is written against `res ≤ 3.6`, which is satisfied by
> all three draws, so no criterion in this checklist turns on which one is read.

| contrast (run 13, run-9 weights, n=50 paired) | base | merged | Δ | 95% CI | res |
|---|---|---|---|---|---|
| keep=1.00 router 4800→3840 (m=0.20) | 77.30 | 79.70 | +2.40 | [−0.76, +5.55] | 3.15 |
| keep=0.50 router 2400→1920 (m=0.20) | 79.63 | 80.17 | +0.54 | [−2.38, +3.75] | 3.06 |
| keep=0.35 router 1680→1344 (m=0.20) | 75.85 | 73.63 | −2.23 | [−6.37, +1.71] | 4.04 |
| keep=0.50 **ink** 2400→1920 (m=0.20) | 76.89 | 78.79 | +1.90 | [−0.72, +4.64] | 2.68 |
| keep=0.35 **ink** 1680→1344 (m=0.20) | 77.60 | 75.94 | −1.67 | [−4.80, +1.20] | 3.00 |
| **keep=0.50 router 2400→1440 (m=0.40)** | **79.63** | **75.77** | **−3.86** | **[−7.47, −0.38]** | **3.55** |

Five nulls and one resolved negative. **Merging away 20% of the kept set is free; merging
away 40% costs 3.86 points.** That last row is the only statistically resolved merge effect
anywhere in run 13, and D12/H1 say it is exactly the condition under which a cost is
expected — every checkpoint in this repo was trained at `merge_ratio=0.0`, so run 13
measured merging strictly off-distribution. Run 14 asks whether that one cost is an artifact
of the train/test mismatch or a property of the merger.

It matters because of what the 40% row buys. Decoder cross-attention KV is linear in token
count (**M1**, `results/kv_memory_local.json`, analytic == observed exactly): M=1920 is a
**2.5×** cut against the full 4800, M=1440 is **3.33×**. Run 13 already licenses the 2.5×
claim at no measurable cost. The 40% row is what would license 3.33×.

Both of those cuts are now **measured rows** rather than a linearity argument applied to a token
count: 60.00 MiB at M=1920 and 45.00 MiB at M=1440, token-ratio == byte-ratio to 4 dp, with a
control asserting each merge row falls strictly below its prune-only twin (so a silently-ignored
`merge_ratio` cannot produce this table). That control matters for run 14 specifically: the
merger being silently skipped is the failure mode this run is least able to notice on its own.

### One variable

Run 14 is a **one-variable change from run 9**, and run 9 is the comparison. Everything below
is asserted by `scripts/verify_train_with_merge.py` section 5, which reads the shipped cell 2
rather than trusting this table:

| knob | run 9 | run 14 |
|---|---|---|
| `RESUME_CKPT` | run 5's `adaptive_donut_funsd.pt` | **same file** |
| `DO_TRAIN` / `TRAIN_KEEP_RATIO` / `TRAIN_EPOCHS` | True / 0.50 / 5 | same |
| `SUPERVISE_SALIENCY` / `SALIENCY_THRESHOLD` / `ATTN_TARGET` | True / 0.15 / False | same |
| **`TRAIN_MERGE_RATIO`** | **0.0** (hardcoded literal in cell 11) | **0.40** |

The sweep grid is run 13's 28 rows unchanged — `merge_ratio` is passed per row and the
sweep never reads `TRAIN_MERGE_RATIO`, so run 14's table is row-for-row comparable to run
13's.

### Why 0.40 and not 0.20

0.20 is **already free** on merge-naive weights (three of the nulls above), so training it
could only make a null more null — five hours to confirm what run 13 showed. 0.40 is where
the measurable cost sits, it is the row whose recovery changes the headline compression from
2.5× to 3.33×, and H1 predicts a router trained at 0.40 does best *at* 0.40. The sweep
measures the 0.20 rows regardless, so a 0.40-trained checkpoint that damages them will say
so rather than hide it — see the trade-off watch below.

### The mechanism was proven by execution, not by reading

The change is one constructor argument, and the risk is not the argument but whether
gradient survives `BipartiteTokenMerger`. If it does not, the router trains on a signal that
no longer describes what the decoder sees, every loss term still falls, the checkpoint still
saves, the 28 rows still tabulate, and the run means nothing.
`scripts/verify_train_with_merge.py` settles it by running it:

```
[PASS] re-running merge=0.00 is bit-identical (so 'differs' below is not noise) -- noise floor 0.000e+00
[PASS] merge=0.20 changes the router gradient vs merge=0.00 -- max|delta| 2.067e-04 vs noise 0.000e+00
[PASS] merge=0.40 changes it further than merge=0.20 does -- 0.40: 4.424e-04 > 0.20: 2.067e-04
```

The pairing is the point: the router receives gradient from the **prune** path whether or not
the merger is differentiable, so "grads are non-zero" would have passed on a dead end. The
non-vacuity check is that merging *changes* the gradient, measured against the same config's
own bit-identical re-run.

### Watch-points — the printed lines, and what a wrong value means

| where | expect | if not |
|---|---|---|
| cell 2 | `PLAN: DO_TRAIN=True -> retrain router WITH pruning ON (keep_ratio=0.5) AND merging ON (merge_ratio=0.4), then sweep` | this is the one line that states run 14's variable. Anything else and you are running a different experiment |
| cell 2 | `CFG: … TRAIN_EPOCHS=5 TRAIN_MERGE_RATIO=0.4 RESUME_CKPT=set` | `RESUME_CKPT=None` cannot happen — cell 2's run-14 guard raises first — but `TRAIN_MERGE_RATIO=0.0` would make this run 9 again |
| cell 2 | `CHECKPOINT ATTACHED: will load /kaggle/input/…` | **not** `EVAL-ONLY mode … training skipped`. That older wording was wrong on every run since 9 and was fixed in the generator on 2026-09-18; seeing it means a stale notebook was uploaded |
| cell 11 | `Resumed /kaggle/input/…/adaptive_donut_funsd.pt (missing=…, unexpected=0)` | `unexpected≠0` ⇒ wrong checkpoint. Missing keys are the pruning-era keys run 5 predates and are expected |
| cell 11, every epoch | `enc 1440` | **the run's one variable, made visible.** `enc 2400` means the merger did not run and the whole run is void. This column is new in run 14 — `ch 0.500` reports the *prune* fraction and reads 0.500 either way |
| cell 11, every epoch | `ch 0.500`, `p` std not → 0 | `ch` off 0.500 ⇒ the STE budget moved; `p` std → 0 is constant-collapse, which makes `topk` return the first K indices |
| cell 13 / harness | `HARNESS OK … max drift 0.00 pts` vs `(77.74, 64.70, 53.05)` | run 14 resumes run 5, so this should read **exactly 0.00** as run 9 did. Nonzero ⇒ the venue moved, and every cross-run delta below is suspect |
| cell 15 provenance | `eval_ckpt.path` = `/kaggle/working/adaptive_donut_pruned.pt` | a `/kaggle/input/…` path ⇒ the sweep evaluated the *old* checkpoint and measured nothing |
| cell 15 Q6 | no `AssertionError` | an assertion is the design working: a pair missed its shared `M`, so its delta would be a budget effect in a merging costume |

### Cost — ≈5.5–6 h, and the merger is not the reason

Run 9's shape: ≈19 min dataset download + ≈4 h training + ≈3 min cell 13 + ≈42 min cell 15
(15 rows). Run 14 changes two things in opposite directions: the merger adds per-step work
(`torch.nonzero` and boolean-mask indexing, both device syncs), while the decoder's
cross-attention sequence **shrinks from 2400 to 1440** for every training step. Measured
merger overhead is **+2.0% / +3.5%** of an unmerged step at merge 0.20/0.40 — but that is
CPU with a stub decoder, so it bounds the *arithmetic*, not the GPU sync cost, and the
denominator on a T4 is far larger. Cell 15 is 28 rows now: run 13 took **64 min**. Budget
**≈4–4.5 h training + ≈64 min sweep ≈ 5.5–6 h total** and check the weekly GPU quota first.

**Abort condition, stated before the run:** if epoch 1 takes more than **1.3×** run 9's
epoch time, stop and re-plan rather than letting a 4 h run become a 9 h one. The CPU
measurement above cannot see GPU sync cost, so this is the check that actually tests it.

### Acceptance — pre-registered, with a **measured** predicted resolution

The primary statistic is run 14's **own** selection-held-fixed contrast at m=0.40 — the same
quantity that read **−3.86 [−7.47, −0.38]** on run 13. It is internally controlled: one
checkpoint, one selection, the merger the only difference. Paired by document, n=50, 20 000
bootstrap resamples over documents.

**Predicted resolution is measured, not guessed.** Two sources, both from artifacts already
on disk:

- *within-run* contrasts of this exact shape, on run 13: **res 2.68–4.04 pts** (table above);
- *cross-run* paired deltas at the same row on the same 50 documents, from run 11 − run 9:
  **res 2.83–4.91 pts** across the 11 non-degenerate rows, median 3.85.

So: **predicted res ≈ 3.0–3.6 pts on the primary (within-run) contrast, and ≈ 3.1–4.2 on any
run-14-minus-run-13 comparison.** The consequence has to be written down now, because it is
uncomfortable:

> **The effect to be recovered is 3.86 pts and the resolution is ≈3.5 pts. This design can
> resolve a FULL recovery and cannot resolve a PARTIAL one.** A half recovery (≈+1.9) will
> come back as an underpowered null and licenses nothing. **n is not a knob** —
> `MAX_EVAL_SAMPLES = 50` *is* the whole FUNSD test split.

| outcome | criterion | reading |
|---|---|---|
| **RECOVERED** | run 14's m=0.40 contrast is flat (CI includes 0) **and** `res ≤ 3.6`, **and** the cross-run delta on that row is `> 0` | training with merging on removes the only measured merge cost. Licenses the **3.33× KV** claim at M=1440 and makes `TRAIN_MERGE_RATIO` a real knob |
| **NOT RECOVERED** | run 14's m=0.40 contrast still excludes 0 with Δ < 0, at `res ≤ 3.6` | the 40% cost is a property of the merger, not of train/test mismatch. Stop at **2.5× (M=1920)**, which run 13 already licenses, and write the 40% row up as the measured limit |
| **TRADED, NOT RECOVERED** | the m=0.40 contrast improves **while** run 14's `keep=0.50` (unmerged) row falls vs run 13's 79.63 by more than its own res | merging-in-training bought the merged row by giving up the unmerged one. Report both numbers; do not quote the merged row alone |
| **UNDERPOWERED** | anything flat with `res > 3.6` | the default, not a fallback. Choose nothing from that row |

Judged separately, on its own resolution:

| secondary | why it is here |
|---|---|
| the **m=0.20** rows (`keep=1.00`, `keep=0.50`, `keep=0.35`) | H1 predicts a router trained at 0.40 is best *at* 0.40. If the 0.20 rows fall, run 14 has specialised rather than improved, and that is the honest headline |
| row 0 (`keep=1.00` CONTROL) | run 14 trains at keep=0.50 like run 9, so this stays off-distribution for the same reason. Run 9 read **77.30**; a similar value is the expected outcome, not a failure |
| the sabotage row (checkerboard vs rank_parity at M=1920) | **null twice already**, on two different checkpoints, with rank_parity numerically *higher* both times (run 12: −1.51, run 13: −0.29). A third null on merge-aware weights closes it: the checkerboard fix is correct about the partition and unproven about recall. Record it as closed either way |

### The prediction, recorded before the run so it can be wrong

**Run 14's m=0.40 contrast comes back flat, and the run reads UNDERPOWERED-or-RECOVERED
rather than cleanly RECOVERED.** Reasoning: H1 is real and isolated (run 11), so training
with merging should move this row in the right direction; but the effect to recover (3.86)
sits within one resolution-width of the bar, so a genuine recovery and a genuine
half-recovery produce the same printed verdict. I also expect **the m=0.20 rows to hold**
rather than fall, because 0.20-merging is a subset of what a 0.40-trained router has learned
to tolerate.

*Note on the last prediction I made:* before run 13 I pre-registered "merging will lose at
equal M, on every pair, and lose most at the tight budgets." **That was falsified** — 0 pairs
favoured pruning, 2 favoured merging, 3 were underpowered. It is left in place above, struck
rather than edited. The lesson carried into the prediction here is that this project's merge
results keep coming back *less* negative than D12's off-distribution logic suggests.

**What would falsify the framing:** run 14's unmerged `keep=0.50` row falling well below run
13's 79.63. That would mean merging-in-training is not adding robustness but simply moving
the operating point, and "train with merging on" becomes a trade to be argued rather than an
improvement to be adopted.

### Launching it — the one edit

The generated `kaggle_pruning_run.ipynb` ships run 14's configuration already. **One line
needs changing**, and cell 2's guard raises within a minute if it is forgotten:

1. Kaggle → **Add Input** → the dataset holding **run 5's** `adaptive_donut_funsd.pt`
   (this is `nafis8766/token-pruning-dataset`; runs 9/10/11 all resumed from it). Attach
   **only** that one — the basename resolver needs a unique match.
2. Cell 2, line ~48: `RESUME_CKPT = None` →
   `RESUME_CKPT = '/kaggle/input/datasets/nafis8766/token-pruning-dataset/adaptive_donut_funsd.pt'`
   (if the mount path differs, any path with the right *basename* works — the resolver walks
   `/kaggle/input` and reports every `.pt` it finds when it cannot resolve).
3. Accelerator → **GPU T4**. `ALLOW_CPU=False`, so cell 2 asserts on a CPU session rather
   than quietly producing different numerics for six hours.
4. Run All. Check the `PLAN:`/`CFG:` lines and `enc 1440` on epoch 1 before walking away.

Do **not** run `kaggle_token_pruning_ocr.ipynb` — the canonical notebook still carries the
pre-checkerboard merger and would silently measure the broken split.

## Run 14 — result (Kaggle T4, executed 2026-09-18, filed 2026-09-21) — primary reads **UNDERPOWERED**; the recall null does not survive contact with the other three metrics, and the gain is **not distinguishable from a general robustness lift**

Output in `run14/` (note: no space in the directory name, unlike `run 9/`…`run 13/`).

```
eval_ckpt:    /kaggle/working/adaptive_donut_pruned.pt
              size_bytes 1045901771   mtime 2026-09-18T13:45:08Z     (pruning-era size ✓)
control_ckpt: .../adaptive-donut-run5/adaptive_donut_funsd.pt
              size_bytes 1045901275   mtime 2026-09-18T11:31:14Z     (run-5 size ✓)
harness_verified: True — "run-5 weights reproduce run 6 within 0.00 pts"  (77.7376 vs 77.74)
control_drift_pts = 3.107        transformers 5.0.0 / torch 2.10.0+cu128 / Tesla T4
```

**Run 12's failure mode did not recur.** Both byte-size identities match, and the F2 harness
control reproduced run 6 at **0.00 pts** — so run 14's levels are comparable to the run table
and its cross-run deltas against run 13 are legitimate. Runs 13 and 14 scored the **same 50
documents in the same order** (`i` and `n_text_rows` identical elementwise; recall arrays
*not* identical, max|Δ| 0.387 — so this is two checkpoints, not one file compared to itself).
That makes every run-14-minus-run-13 quantity below **paired by document**.

Training confirmed live from the epoch log: `enc 1440` on every epoch = K − r = 2400 − 960.

### The pre-registered primary — UNDERPOWERED

Selection held at keep=0.50; the merger is the only difference. Bootstrap 20 000 resamples
over documents, seed 0; Wilcoxon added because the bootstrap endpoints here sit near zero.

| | Δ | 95% CI | res | Wilcoxon p |
|---|---|---|---|---|
| run 13 (merge-naive, run-9 wts) | −3.86 | [−7.45, −0.30] | 3.57 | **0.0049** |
| **run 14 (merge-trained wts)** | **−0.28** | **[−4.46, +3.44]** | **3.95** | 0.9197 |
| cross-run DiD (14 − 13) | +3.58 | [−1.43, +8.25] | 4.84 | **0.0099** |

**Verdict: UNDERPOWERED.** The contrast is flat, but `res 3.95 > 3.6`, and the pre-registered
table says of that cell: *"the default, not a fallback. Choose nothing from that row."*
Concretely — **run 14's CI still contains run 13's −3.86**, so "the cost is gone" and "the cost
is unchanged" both survive this run.

> **The prediction written before the run was right.** It said: *"Run 14's m=0.40 contrast
> comes back flat, and the run reads UNDERPOWERED-or-RECOVERED rather than cleanly
> RECOVERED"*, because a 3.86-pt effect measured at ≈3.5-pt resolution cannot separate full
> from partial recovery. That is exactly what happened. `n` is not a knob: 50 **is** FUNSD test.

> **Two tests disagree on the DiD and both are recorded.** The pre-registered statistic is the
> bootstrap, whose CI includes 0. Wilcoxon — draw-invariant, added because the endpoints move
> with the seed — gives p=0.0099. Filed side by side per the D12 convention of reporting a
> verdict that disagrees with the finding rather than dropping either. **The pre-registered
> bootstrap governs what this run licenses**, which is nothing.

### The finding that actually matters — the gain is not merging-specific

Run 14 improved on the trained merge row by +3.11 (p=0.0052). It also improved by about the
same amount on rows that **contain no merging at all**:

| row (run 14 − run 13, same 50 docs) | Δ | Wilcoxon p |
|---|---|---|
| `keep=0.50 m=0.40 router` (the trained config) | **+3.11** | 0.0052 |
| `keep=0.50 random` — no merge, not even the router | **+3.43** | 0.0293 |
| `keep=0.50 ink ORACLE` — no merge | **+3.21** | 0.0489 |
| `keep=1.00 router CONTROL` — no merge, no prune | +1.98 | 0.3756 |

Differencing those directly:

| | Δ | 95% CI | res | p |
|---|---|---|---|---|
| m=0.40 gain **minus** `random` gain | −0.32 | [−5.35, +4.22] | 4.79 | 0.5980 |
| m=0.40 gain **minus** `ink ORACLE` gain | −0.10 | [−4.82, +4.13] | 4.47 | 0.7509 |

**There is no measurable merging-specific component.** Whatever run 14 gained, it gained
roughly equally on a random 2400-token selection that the merger never touched. The plausible
reading is that `TRAIN_MERGE_RATIO=0.40` acted as a **robustness augmentation on the decoder**,
not as training the model to consume merged tokens.

> **This null is itself underpowered and must not be over-read.** Its resolution is 4.79 pts,
> so a merging-specific effect smaller than ≈4.8 pts would be invisible to it. The correct
> statement is *"this run found no merging-specific component and could not have found a small
> one"* — not *"there is none"*.

### "Free" is true of recall only — the other three metrics disagree

The primary contrast was pre-registered **on word recall**, and on recall it is a clean null
(−0.28, p=0.9197). Run the identical contrast on every other metric the artifact carries:

| metric (run 14, m=0.40 vs m=0.00 @ keep=0.50, paired n=50) | Δ | 95% CI | res | Wilcoxon p |
|---|---|---|---|---|
| word recall (higher better) | −0.28 | [−4.46, +3.44] | 3.95 | 0.9197 |
| **mean NED (LOWER better)** | **+0.0285** | [−0.0109, +0.0704] | 0.0406 | **0.0290** |
| character accuracy ~~(no per-image array)~~ | **−2.85** | **[−7.04, +1.09]** | **4.06** | **0.0290** |
| word order (no per-image array) | **−3.33** | — | — | — |

> **Correction, 2026-09-22 — charAcc was never untestable, and the row above is why it looked
> that way.** `character_accuracy_pct` is `(1 − mean(ned)) × 100` in cell 15, and `ned` **is**
> stored per image, so charAcc is an affine transform of an array that has been on disk since
> run 9. Verified against the shipped artifact: `|charAcc − (1 − mean(per-image ned))·100| ≤
> 2.1e-14` across **all 28 rows** of `run14/ablation_selection.json`. Bootstrapping it is the
> row above; the method was validated by reproducing every published recall and NED figure in
> this section to 4 decimals before the new cell was filled in. Two consequences, and the
> second is the one that matters for the next design:
>
> 1. **charAcc's p is *identically* NED's p** (0.0290 here, 0.0002 on run 13) — not
>    coincidence: a strictly decreasing affine map leaves the paired Wilcoxon two-sided p
>    invariant. So **"all four metrics" is three quantities**: recall, NED≡charAcc, word order.
>    A primary pre-registered across four, with any multiplicity correction applied over four,
>    double-counts the exact quantity that carries the effect — and double-counts it in the
>    direction of declaring one. Pre-register over **three**.
> 2. **The harness gap is one metric, not two.** Only `word_order` was genuinely unstored.
>    Fixed generator-side 2026-09-22 (patch G3b) — and *not retroactively*: runs 13 and 14
>    carry no per-image order array, so the −5.82 / −3.33 order figures stay untestable
>    forever. word order is testable from **run 15 onward**.

**Merging away 40% is free on recall, and what "not free" rests on needs naming.** On the
pre-registered statistic — the bootstrap — **NED and charAcc are nulls too**: their CIs
([−0.0109, +0.0704] and [−7.04, +1.09]) both contain zero. Only Wilcoxon calls them
significant. ~~NED degrades significantly on the same 50 documents where recall cannot tell
the two apart.~~ That sentence quietly took Wilcoxon's verdict on NED while the same run
explicitly ruled that **the pre-registered bootstrap governs** on the DiD, where Wilcoxon was
the one saying "significant" — the same two tests, disagreeing the same way, adjudicated
oppositely eleven lines apart. Corrected reading: **three of three testable metrics are
bootstrap-nulls at this resolution**, and the partial-recovery signal below is carried by
point estimates and by a draw-invariant side-check, not by the binding statistic. `word_order`
drops ~3 pts with no per-image values stored, so it cannot be tested at all — a gap in the
harness, not evidence of a null.

Now compare the same three quantities against run 13, and a different picture appears:

| | run 13 (merge-naive) | run 14 (merge-trained) | cost roughly |
|---|---|---|---|
| recall | −3.86 (p=0.005) | −0.28 (p=0.920) | eliminated |
| charAcc ≡ NED | −5.79 [−9.29, −2.53] | **−2.85 [−7.04, +1.09]** | **halved — and run 13's CI excluded 0, run 14's does not** |
| word order | −5.82 | **−3.33** | **halved** (point estimates only — untestable in both runs) |

> **Read together, this looks like a PARTIAL recovery — the exact case the checklist said in
> advance this design could not resolve.** All three quantities moved to roughly half their
> run-13 cost rather than to zero. Recall is the one where the remaining cost is small
> enough to vanish into ±3.95 pts of resolution, and recall is the metric the verdict keys on.
> So "UNDERPOWERED" is not just a formality here: the multi-metric view says there is probably
> a real residual effect that the pre-registered statistic is too blunt to see.
>
> **What the charAcc CI adds (2026-09-22).** On charAcc the two runs are on *opposite sides of
> zero-exclusion*: run 13 **[−9.29, −2.53]** excludes zero, run 14 **[−7.04, +1.09]** does not.
> That is the strongest bootstrap-grade evidence in the run for "the cost got smaller" — and
> it is still not evidence for "it went away", because run 14's charAcc CI comfortably contains
> run 13's −5.79, exactly as its recall CI contains run 13's −3.86. **Same verdict, now on two
> quantities instead of one: partial recovery is the live reading and this design cannot
> resolve it.**
>
> This is **not** a licence to switch to NED or charAcc as the headline — that would be
> choosing the metric after seeing the data. It is a reason to distrust the recall null, and a
> concrete design fix for next time: ~~**store per-image `char_acc` and `word_order`**~~
> **store per-image `word_order`** (done 2026-09-22, generator patch G3b) — `char_acc` needed
> no storing, it was derivable from `ned` all along, which is the correction above. So the
> primary can be pre-registered over **three** quantities and scored on all of them.

### Token-matched Q6 as printed — and why the headline pair is contaminated

| pair | M | merge | prune | Δ | 95% CI | res | verdict |
|---|---|---|---|---|---|---|---|
| keep1.00 m0.20 vs keep0.80 | 3840 | 78.88 | 78.07 | +0.81 | [−2.39, +3.80] | 3.1 | UNDERPOWERED |
| keep0.50 m0.20 vs keep0.40 | 1920 | 78.03 | 76.57 | +1.46 | [−2.86, +5.80] | 4.3 | UNDERPOWERED |
| keep0.35 m0.20 vs keep0.28 | 1344 | 73.46 | 69.24 | **+4.22** | [+0.20, +8.40] | 4.1 | MERGING WINS |
| **keep0.50 m0.40 vs keep0.30** | **1440** | **78.87** | **73.09** | **+5.78** | [+0.69, +10.39] | 4.8 | MERGING WINS |
| ink keep0.50 m0.20 vs 0.40 | 1920 | 79.65 | 79.78 | −0.13 | [−3.02, +2.80] | 2.9 | indistinguishable |
| ink keep0.35 m0.20 vs 0.28 | 1344 | 77.17 | 75.74 | +1.43 | [−2.69, +5.13] | 3.9 | UNDERPOWERED |

Token match **hard-asserted and independently re-checked**: all 50 per-image `tokens` values
equal within every pair.

The M=1440 pair flips from run 13's −1.29 to **+5.78** (p=0.0017), DiD +7.07 (p=0.0072). **Do
not quote this as "merging beats pruning."** Run 14 trained at keep=0.50 + merge=0.40, so the
merge member of that pair is the *only* on-distribution row in the sweep and its prune twin is
off-distribution. The twin's own cross-run delta says so directly: `keep=0.30 router TWIN`
**fell −3.96** (p=0.0499) from run 13 to run 14. So the pair widened partly because the
comparison arm got worse. This is H1 again, now pointing the other way: run 13 penalised the
merge row, run 14 penalises the prune row.

Within-run, against run 14's **own** unpruned ceiling (79.28 @ 4800):

| reaching M=1440 | Δ vs own ceiling | 95% CI | Wilcoxon p |
|---|---|---|---|
| by **merging** (keep=0.50, m=0.40) | **−0.41** | [−4.56, +3.07] | 0.8279 |
| by **pruning** (keep=0.30, m=0.00) | **−6.19** | [−9.91, −2.57] | 0.0134 |

Same caveat: the first is the trained configuration and the second is not.

Note the ordering is **non-monotone in M** and monotone in *distance from the trained config*:
−0.13 @ 2400, −0.41 @ 1440 (trained), −1.25 @ 1920, −2.71 @ 1920 (prune), −5.82 @ 1344,
−6.19 @ 1440 (prune). Fewer tokens beat more tokens whenever the smaller set matched training.

### Secondaries, scored against the pre-registration

- **`m=0.20` rows held** — keep=1.00 −0.82, keep=0.50 −2.14, keep=0.35 −0.17, **all
  non-significant**. The pre-registered prediction ("the 0.20 rows hold rather than fall,
  because 0.20-merging is a subset of what a 0.40-trained router tolerates") was right on the
  data, though the specificity result above removes its stated *reason*.
- **TRADED, NOT RECOVERED did not fire.** Run 14's unmerged `keep=0.50` row is **79.15** vs run
  13's 79.63 — Δ −0.47, far inside its own res 3.30. The pre-registered framing falsifier
  ("run 14's unmerged keep=0.50 row falling well below 79.63") did **not** trigger.
- **Row 0 CONTROL 79.28**, vs the pre-registered expectation of "≈77.30, a similar value is the
  expected outcome, not a failure". It came in 1.98 *above* run 13 (p=0.38, ns). Not a failure.
- **Sabotage row: third consecutive null → CLOSED**, exactly as pre-registered ("record it as
  closed either way"). checkerboard − rank_parity at M=1920: run 12 **−1.51** [−3.22, +0.19],
  run 13 **−0.29** [−3.10, +2.78] p=0.40, run 14 **−0.88** [−5.26, +3.37] p=0.8468. Three
  checkpoints, three nulls, and `rank_parity` numerically **higher all three times**. The
  checkerboard fix is **correct about the partition and unproven about recall** — it moves a
  synthetic missed-redundancy percentage (49.2%/50.5% → 0.0%/0.0%) and has never moved recall.

### New, not pre-registered: the router got worse as a *selector*

Nothing in the checklist looked here, and it is the clearest negative signal in the run.

| statistic @ keep=0.50, 2400 tokens | run 13 | run 14 | change | p on the change |
|---|---|---|---|---|
| router − random | +17.07 | +13.16 | **−3.90** [−8.63, +1.07] | 0.0500 |
| router − ink oracle | +2.74 (p=0.0073) | −0.94 (p=0.37) | — | — |

The router's margin over random **shrank by 3.90 pts** (borderline, p exactly 0.0500), and its
edge over the ink oracle went from significantly positive on run 13 to indistinguishable from
zero on run 14. The sign is still correct (`negated` 15.15), so this is degradation, not the D1
inversion. Read with the specificity result, the coherent story is: **merge-augmented training
made the decoder more robust and the router slightly worse at choosing** — the "specialised
rather than improved" worry, showing up in a place the pre-registration did not check.

> Standing caution this reinforces: run 13's `router − ink` of **+2.74 at p=0.0073** is the
> first *significant* router-beats-ink reading in the project, and run 14 erases it. Do **not**
> promote "the router beats the ink oracle" on the strength of one run.

### What run 14 licenses

**Nothing new on the KV axis.** The pre-registered gate for the **3.33× at M=1440** claim was
RECOVERED, and the run read UNDERPOWERED. **2.5× at M=1920 remains the measured limit**, on
run 13's evidence, unchanged by this run.

What run 14 *does* establish: the 40% merge cost is **not stable across checkpoints** (−3.86
significant on run 13, −0.28 null on run 14), so it is not a fixed property of the merger; and
whatever moves it is **not demonstrably about merging**, because the same checkpoint moved a
random-selection unmerged row just as far.

**The missing control is symmetric to Pending 14.** To claim merging beats pruning at matched
M you need a checkpoint trained at `keep=0.30, merge=0.0` — the prune-only twin's own
on-distribution arm — which does not exist. Until then every M=1440 comparison has exactly one
trained arm.

### Corrections this run forced

- **−3.86 is the merge-vs-no-merge contrast at fixed `keep` (75.77 vs 79.63), not the
  token-matched pair.** The token-matched M=1440 pair on run 13 was **−1.29 [−4.81, +2.26],
  not significant**. Both numbers are real and answer different questions; the run-13 section
  above states this correctly, but the one-line summary "40% costs −3.86" invites reading it
  as the token-matched result. Anywhere the two appear together, say which is which.

## Phase 2c: decoding ablation — DONE (run 2026-08-29, results above)

Applied by `scripts/patch_notebook_phase2c_decode_ablation.py`. Eval-only — same
weights, no retraining. Attempt 1 failed to launch; attempt 2 succeeded on a
Tesla T4 and produced run 6.

```python
DECODE_CONFIGS = [
    ('baseline (run5)',   dict(repetition_penalty=1.3, no_repeat_ngram_size=3)),
    ('no ngram block',    dict(repetition_penalty=1.3, no_repeat_ngram_size=0)),
    ('no rep penalty',    dict(repetition_penalty=1.0, no_repeat_ngram_size=3)),
    ('both off',          dict(repetition_penalty=1.0, no_repeat_ngram_size=0)),
    ('both off + minlen', dict(repetition_penalty=1.0, no_repeat_ngram_size=0,
                               min_new_tokens=64)),
]
RUN5_REFERENCE = (50.56, 40.97, 26.49)
```

**Three design choices did the actual work — reuse them in the pruning sweep:**

- **Row 0 was a CONTROL** using run 5's exact settings, required to reproduce
  50.56 / 40.97 / 26.49 or invalidate every other row. It came back at 0.00 pt
  drift, which is why a +27 pt jump is believable rather than suspicious. A
  27-point improvement with no control row would have looked like a bug.
- **Length was measured, not inferred** (`mean_pred_words`, `len_ratio_pct`,
  `mean_gen_tokens`, `hit_max_length_pct`). Under-generation was the hypothesis, so
  reading it off recall would have been circular. This is also what caught
  `both off` over-generating — recall alone would have just said "worse".
- **Both knobs varied independently**, not just the suspect. The suspect was the
  no-op; the confound was the cause. A one-variable "fix the obvious thing" patch
  would have changed nothing at all and the project would have moved on to blaming
  the 128-word cap or the encoder.

`RESUME_CKPT` works by setting `EPOCHS = 0`, making `range(1, EPOCHS+1)` empty —
the loop body never executes, so no re-indentation was needed. `torch.save` is
guarded by `if EPOCHS > 0:`. Confirmed in the log: `EVAL-ONLY mode: training loop
skipped (EPOCHS=0)` and `skipped checkpoint save`.

## Phase 2d: selection ablation (Kaggle) — RUN TWICE (runs 7 and 8), from a *derived* notebook

> **Status corrected 2026-08-31 (was "BUILT AND VERIFIED, NOT YET RUN", dated
> 2026-08-29).** The cell has run twice and produced `run 7/` and `run 8/`.
> It did **not** run from the notebook described below: runs 7–8 came from
> `kaggle_pruning_run.ipynb`, which `scripts/make_kaggle_pruning_notebook.py` generates
> *from* the canonical notebook and then extends.
>
> **How much of the 44/44 transfers — measured, not assumed (2026-08-31).** Cell-by-cell
> hash comparison of the two notebooks: 17 cells each, and **exactly three differ** —
> cell 2 (+23 config lines: `DO_TRAIN`, `TRAIN_KEEP_RATIO=0.50`, `TRAIN_EPOCHS=5`,
> `SUPERVISE_SALIENCY`, `SALIENCY_THRESHOLD=0.15`), cell 9 (**one line**:
> `if EVAL_ONLY:` → `if EVAL_ONLY and not DO_TRAIN:`, which re-enables the train-set
> download), and cell 11 (+178/−85: the retrain). Cells 4 (router), 5 (loss), 7 (model),
> 13, **14, 15 (the ablation cells)** and 16 are **byte-identical**. So the verified
> mechanism *is* the code that ran — the 44/44 transfers in full, and the only unverified
> code in runs 7–8 is the new training path. Which is where D4 then found a real defect.
> Reproduce with a hash diff of `''.join(cell['source'])` per cell; `verify_selection_ablation.py`
> hard-codes `NB_PATH` to the canonical notebook, so it cannot be pointed at the derived
> one without an edit — the hash diff is the cheaper check and is sufficient here.

Answers Pending **1b**, **1c** and **1d** in one GPU session. Applied by
`scripts/patch_notebook_selection_ablation.py`, verified by
`scripts/verify_selection_ablation.py` (**44/44 pass**). Eval-only — same run-5
weights, no retraining. (Runs 7–8 broke that last property: they retrained first and
then ran this cell, which is why their `keep=1.00` row is not a control.)

**The port's scope was bigger than "add an eval cell", and that is the thing to
remember.** The notebook is **self-contained**: it carries its own copies of
`PatchSaliencyRouter` (cell 4) and `AdaptiveDonutOCR` (cell 7) and never imports
`src/`. So *none* of the `select_mode` / `patch_ink` / `stratified_scores` work from
D1/D2 existed there — an eval cell alone would have called a `select_mode=` argument
that does not exist. Three patches, seven asserted substitutions:

| # | cell | change |
|---|------|--------|
| A | 4 | `PatchSaliencyRouter.forward` gains `select_scores` / `invert`; STE gated off when an external ranking is supplied |
| B | 7 | `SELECT_MODES`, `TOKEN_GRID`, `patch_ink()`, `stratified_scores()` added; `generate()` gains `select_mode=`; meta reports `select_mode` + `retained_ink` |
| C | new cell 15 | the ablation harness itself, inserted after the decoding ablation and before the zip cell |

**15 rows**, all at `merge_ratio=0.0` so the selection question stays clean:

```python
('keep=1.00 router CONTROL', 1.00, 'router'),                      # must reproduce run 6
# 1b
(0.50, 'router'), (0.50, 'negated'), (0.50, 'random'), (0.50, 'ink'),
# 1d
(0.50, 'stratified'), (0.50, 'stratified_negated'),
# 1c
(0.75, {'router','random','ink','stratified_negated'}),
(0.35, {'router','random','ink','stratified_negated'}),
```

`keep_ratio` values were chosen so the per-row budget is **integral at every one of
them** — with GW=60 that is 60 / 45 / 30 / 21 — so the stratified rows are exact
per-row top-k rather than the graceful-degradation path. Verified per ratio.

**Design choices carried over from Phase 2c** (they are the reason run 6 was
believable): row 0 is a CONTROL that must reproduce 77.74 / 64.70 / 53.05 at the
0.5 pt threshold or invalidate everything; length is measured not inferred; `pred` is
never repaired; `random` is present at every pruned ratio as the floor and `ink` as
the ceiling. Plus one addition: **per-image** coverage records (`min`/`p10`/`mean`
line coverage, `retained_ink`), which turn D2's 4-row ordering into an ~2100-point
Spearman test that can actually fail.

**New: results are written after EVERY row**, not at the end. Directly because the
killed local run lost 30 images of completed work to a `json.dump` that only ran on
completion. `meta.complete` distinguishes a partial file from a finished one.

The cell prints five verdicts, each with its falsifying branch written *before* the
run: **Q1** negation vs router vs random, **Q2** the oracle-vs-full-page premise check
(the row that can kill 1a), **Q3** which statistic family predicts per-image recall
(D2's claim, pooled *and* within-mode), **Q4** whether the bug is the selection rule
or the scorer (1d), **Q5** the accuracy/cost curve (1c).

**The verifier executes the notebook's code rather than parsing it**, because every
failure mode that matters here is a runtime one. It: exec's cells 4 and 7 for real;
compares the ported `patch_ink` / `stratified_scores` / router selection **numerically
against `src/`** on the real 80×60 grid with weights copied between the two routers
(bit-identical, 0 index mismatches — this is the drift that would silently make Kaggle
rows non-comparable to local ones); calls the real `generate()` through all six modes
on a real 80×60 input; and finally exec's the whole harness cell end to end against a
stub processor/dataset with the notebook's **real** metric functions, checking all 15
rows complete, every verdict section prints, and the JSON round-trips.

Two checks failed on the first run. **Both were bugs in the verifier's fixtures, not
in the notebook** — and one of them produced a real finding (the region-≥-budget bound
on when stratification can help, now recorded under Pending 1d):

1. *"a plain global top-k starves rows"* — fixture made only 5 of 80 rows hot, 300
   tokens against K=2400, so nothing starved. Fixed to a 45-row band.
2. *"non-standard grid ⇒ `retained_ink` is None"* — fixture used 96×50 patches, which
   is 4800, the same as the token count, so `patch_ink`'s guard correctly did **not**
   fire. The fixture was not non-standard at all. Fixed to 96×60 (5760), and a
   companion check added that a *stratified* row on a mismatched grid **raises**
   rather than silently stratifying over the wrong axis.

To run: open the notebook on a T4, set `RESUME_CKPT` to run 5's `.pt` with
`EPOCHS = 0` (the Phase 2c eval-only mechanism), and execute through cell 15.

