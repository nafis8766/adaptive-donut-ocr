# AGENTS-ARCHIVE-CHANGELOG.md — the dated changelog

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**.

Append new entries here, newest-last, in the existing format. `AGENTS.md` keeps a short
`## Changelog` stub pointing at this file plus the entry for the split itself.

⚠ **That sentence is wrong about this file, found 2026-09-30.** The entries below are
**newest-FIRST**: the three 2026-09-24 entries are at the top and 2026-09-03/04 is ~2,200
lines down. The instruction was inherited from `AGENTS.md`'s stub and describes neither the
order the split produced nor the order sessions have used since. **Match what you see —
prepend — and do not "fix" the order by reversing 2,300 lines**, which would be a bulk
rewrite of exactly the kind the 2026-09-06 mojibake incident warns about, for no gain.

Also holds the **Kilo (tencent/hy3:free) contributions** section at the end, which is attributed
separately on purpose so those changes stay distinguishable.

---

## Changelog

- **2026-09-30 — T4 BUILT, NOT RUN: PATCH I ports the sweep to the pooled corpus (FUNSD 50 +
  SROIE 347 = 397), the sweep grows to 29 rows, and T1 §§3/5 stop being prose.** Full record
  in `AGENTS.md`'s `## The pooled-corpus port (T4)`; this is the index entry.
  **Shipped:** PATCH I in `scripts/make_kaggle_pruning_notebook.py` (cells 2/9/13/15) —
  `PooledTestSet`, a `doc_image()` schema adapter, a per-document `corpus` label,
  `word_order` in `per_image`, per-corpus strata on every row, and a **29th** sweep row
  **`keep=0.40 random TWIN` at M=1920**. That row is the blocker T3 §6 promoted: runs 13/14's
  merge and random budgets have an **empty** intersection, so *"merging beats random at
  matched M"* was not computable from either, and T1 §3's amendment needs an active non-merge
  comparator before a firing tail gate can be attributed to merging.
  **Scorer:** `score_preregistered.py` **45/45 → 64/64**. T1 §5's per-corpus discard
  constraint is executable (`discard_composition`, `choose_g`, `corpora_of`), and it is
  tested against a **corpus-aligned synthetic that fires** and a **SROIE-aligned one that
  does not** — runs 13/14 are single-corpus, so a green resting on them alone would have been
  the "treated row with no untreated control" defect T3 found in the tail gates, recurring in
  the fix for it. T1 §3's direction pin is executable too (`assert_direction`, ordering arms
  off `merge_ratio` read from the rows; equal `merge_ratio` raises rather than defaulting to
  argument order).
  **Three findings, each an instance of a gotcha already in this project:**
  (a) `doc_boxes()` shipped **dead** — never called once, because `words`/`bboxes` are named
  identically on both corpora and the image column is the pool's only schema divergence. That
  fact is now asserted instead. `final_coords` in miniature.
  (b) `verify_pooled_corpus_port.py` **crashed at 19 PASS / 0 FAIL**, exit 1 with no failure
  printed — caught only by reading exit code and counts together. The 13-day silent raise in
  `verify_results_provenance.py`, recurring in a file written after that lesson was recorded.
  (c) The obvious test for (a), `"doc_boxes" not in cell9`, **fails** — the generator now
  carries a *comment* naming `doc_boxes` to record why it is gone. Switched to `ast.walk` over
  `FunctionDef` names. A test keyed on the shape of the text reads its own documentation as
  the defect; same root cause as D4's staleness guard.
  **A claim of mine failed its own control and is filed rather than dropped:** I asserted the
  arm swap would flip contrast A's tail verdict. It does not — ratio **3.22 → 3.18**, both
  clearing p95 1.74 — so run 14's gate failure is **not** an orientation artifact. T3's 10-of-28
  flip is real and belongs to the cross-run family.
  **Executed against the regenerated notebook (not cited):** `verify_tome_merge_port.py`
  **96/96** (was 89/89; a new cell-15 → cell-9 `doc_image` coupling broke it with the
  documented `gc.collect()` NameError, fixed by extracting the *shipped* adapter rather than
  stubbing it, plus a mixed-schema fixture and six per-corpus checks),
  `verify_results_provenance.py` **35/35**, `verify_pooled_corpus_port.py` **62/62**,
  `score_preregistered.py` **64/64** — exit 0 each.
  **Cost measured, not assumed:** SROIE/FUNSD generated-token ratio **0.66**, moving the
  projection **8.06 h → 5.63 h**, and **5.92 h** with run 13's 1.05× overhead. Inside the 9 h
  cap.
  ⚠ **The eval is NOT booked, and two decisions block it:** SROIE's uploader-asserted licence
  (a ruling against it collapses the pool to FUNSD-only at n=50 and makes `UNDERPOWERED`
  permanent), and whether the staged, unauthorised run 18 precedes T4. Both must be settled in
  writing first. T4's box stays **unticked** — DONE-WHEN requires the sweep to have *run*.

- **2026-09-24 — T3 DONE: runs 13/14 re-scored under the run-17 pre-registration. The
  pre-registered primary is `UNDERPOWERED` in both runs, claim 3 is restated, and T1 §3 is
  amended by what the scoring found.** New section `## Runs 13/14 re-scored under the run-17
  rule (T3)`, new artifact `scripts/score_preregistered.py` (**45/45 controls, exit 0**,
  `results/score_preregistered_local.log`). No new data — every number re-derived from runs
  13/14 on disk. T4 gains a blocker.
  **The rule became executable, and building it is what found the defects.** T1 §§2–7 existed
  only as prose; the scorer reproduces all nine figures T1 had recorded before the file existed
  (trimmed **+0.0176** vs +0.02, worst **−40.00**, matched null **−12.43**, ratio **3.219**,
  harmed **5/4**, res **2.477/1.919**, required **n=307**) and — the check that matters — the
  null p95 **tightens** 1.74 → 1.52 → 1.51 as n goes 50 → 307 → 397, which a constant typed in
  and called a null could not do (D14 §10's failure mode). Eight further controls confirm each
  pinned choice is load-bearing: the naive SE is **35% smaller** than Tukey–McLaughlin (0.6383
  vs 0.9792), difference-then-trim moves the estimate **0.2555 pts** while **the same
  comparison on the plain mean is identically zero (−8.55e-15)** — so the non-additivity is a
  property of trimming, not of the data — and in points the harm rule counts **5** where on the
  stored `[0,1]` field it counts **0**.
  **Both DONE-WHEN caveats filed, and each gained something.** (i) The sign flip reproduces
  (+0.54 plain → **−0.65** trimmed, both nulls, so "no measured cost" *survives*) — **and the
  same row is +0.16 in run 14**, so "free" is fragile in **two** directions, estimator *and*
  replicate, only one of which was on the caveat list. (ii) The **−72.34 pt page** is in run
  14's **m=0.40** row — claim 3's own M=1440 contrast, *not* the pre-registered primary; the
  plain mean hides it (−0.28 against res 2.23) and the trimmed mean is blind **to the last
  bit** (`0.0e+00` under a 25 pt mutation, vs the plain mean's −0.50 = **181%** of the row's
  own effect). ⚠ **"Both tail gates catch it" would have been false**: the worst-document gate
  fires (5.01 vs 1.74), the **harmed-count gate does not** (4 vs p95 6). Filed singular.
  **Run 14 is not scored `FREE` despite a +0.02 pt trimmed mean** — the cleanest imaginable
  null — because both its recall tail gates fail. That is the single behaviour T1 §3 exists to
  produce, now demonstrated rather than asserted. **Zero confirmatory quantities survive Holm
  in either run**, independently agreeing with D14 §1d over the wider 12-test family.
  **THREE findings that were not on the list.** (1) **Claim 3's "resolved and negative" M=1440
  price does not replicate** — run 13 gives −3.23 [−5.70, −0.76] (excluding zero, and its plain
  mean reproduces **−3.86 exactly**, so this is not a re-derivation artifact) but run 14 gives
  **−0.17 [−2.40, +2.06]**, including zero. The sentence stated as *resolved* what one of two
  runs denies; 3.33× stays unlicensed, now for being **unreplicated**. (2) **Claim 3 paired two
  baselines in one sentence** — `2.50×` is `4800/1920`, against **keep=1.00**, while the
  +0.54's control row is **M=2400** (keep=0.50), so a *prune+merge* memory ratio was quoted
  with a *merge-only* accuracy delta; the merge step alone is **1.25×**. ⚠ **The direction is
  asserted as a control so this cannot be filed as flattering:** on a consistent keep=1.00
  baseline run 13's delta is **+2.29 [−0.44, +5.01]**, *better* than the +0.54 it replaces — a
  **consistency defect, not an inflated result** — and **no verdict moves** (both runs stay
  null either way). (3) **the one that matters most, below.**
  ⚠⚠ **T1 §3's tail gate is not specific to merging, and D13 §5's untreated control had never
  run.** T3 ran it: in the direction the design forces, **13 of 21** contrasts containing **no
  merging at all** clear the 1.74 bar, and the **single worst per-document loss in the entire
  sweep is −80.85 pts on `keep=0.75 ink ORACLE` — keep=0.75, m=0, nothing merged — carrying the
  highest ratio in the sweep (5.43), above every merge row (max 4.62)**, with winsorized sd
  6.63 so it is not a small-denominator artifact. Three things bound the damage: the failure is
  **specificity, not sensitivity** (`keep=1.00 router CONTROL`, neither pruned nor merged,
  **passes at 1.47**); there is **no zero-treatment null on disk** to recalibrate against (no
  config repeats within either run, decode is **bit-identical on re-run** at noise floor
  `0.000e+00`, and runs 13/14 differ by a **retrained checkpoint** so cross-run pairs carry a
  real treatment); and the gate is **not reversal-invariant** — `min(d)` is one-sided, so
  swapping which arm is "treatment" **flips the verdict on 10 of 28 configs**, a DoF T1 §3
  left unwritten because it pinned direction per *quantity* and never per *contrast*.
  **Consequence: run 17 as specified would fail its own tail gate on rows where nothing is
  merged.** The bar must come from an **active non-merge comparator at matched budget** — the
  `random` arm that run 17 already requires and that **D14 measured as absent from both runs**.
  **T3's fix and T4's missing arm are the same row**, so T4's `random`-twin check is promoted
  from a check to a **blocker**, and T1 §3 gains an amendment pinning both the comparator and
  `d = treatment − control`.
  **What T3 does NOT license.** Claim 3's corpus-average null is **true** and is untouched. The
  −72.34 and −80.85 pt pages are **not attributed to merging** — §6 is precisely why they
  cannot be. And `UNDERPOWERED` is **not** a negative result: at n=50 `res` is ~2.5 pts against
  a 1.0 pt MDE, so this is a statement about the instrument, which is T4's job. **Retired
  wording: "merging 20% is free", "no measured cost" unqualified, and "resolved and
  negative"** — all three struck at claim 3, in the run-13 quote block, and in M1.
  ⚠ **Propagation is incomplete by design and tracked in T8.** Claim 3, its M1 detail copy, the
  run-13 headline quote block and `README.md`'s claim-3 copy are updated. The dated **run-13
  and run-14 result sections are deliberately NOT rewritten** — they record what was filed on
  the day, and this file's convention is to strike and supersede rather than edit history.
  `REPORT.md`, `WRITEUP.md` and `STORY.md` still carry the retired wording; `WRITEUP.md`'s
  numeric audit (`scripts/check_writeup_numbers.py`) will need re-running when they are fixed.

- **2026-09-24 — T2 DONE: the second corpus is `sizhkhy/SROIE` test, n=347 confirmed by
  loading; pooled FUNSD+SROIE = 397, which clears T1's `n ≳ 307`. CORD is verified, licensed,
  and excluded on DENOTATION rather than on size.** New section `## Corpus decision (T2)`,
  new artifact `scripts/verify_corpus_grain.py` (**21/21 controls, exit 0**,
  `results/corpus_grain_local.log`). T4 unblocked.
  **D13's guesses (~100 CORD, ~347 SROIE) were both right, and neither number decided
  anything.** What decided it: **CORD's ground truth covers only the annotated key-value
  fields, not the page** — all **1309/1309** `valid_line` entries carry a `category`
  (`menu.nm`, `total.total_price`), so a receipt's store name, address and phone are simply
  absent from the GT, while FUNSD and SROIE transcribe the whole page. `recall` on CORD and
  `recall` on FUNSD/SROIE are **different quantities wearing one name**; pooling averages two
  metrics. The grain follows and is severe: **CORD 20 words/doc (one word = 5.00 pt, 8.82×
  FUNSD's grain) against T1's 1.0 pt MDE** — the metric cannot *express* the effect being
  measured — and **4/100 CORD docs trip the −10 pt harm threshold on a single wrong word**.
  SROIE sits next to FUNSD (0.92 vs 0.57 pt, **1.62×**, 0/347 one-word-over-threshold), so
  T1's point-denominated thresholds **port to SROIE and not to CORD**. Recording the size
  shortfall (FUNSD+CORD = 150 < 307) as the reason would have left the real hazard live for
  anyone who later finds 200 more receipts.
  **"Confirmed by loading" earned its keep three times, and each near-miss would have passed
  a shallower check.** (i) **`buthaya/sroie` has exactly 347 test annotation files — the
  canonical size — and ZERO images in the entire repo** (974 JSONs, 3.6 MB); the pipeline is
  *image* → encoder → prune → merge → decoder, so there is nothing to run. A file count
  matching the expected number is not a confirmed split. (ii) **`buthaya` and
  `jsdnrs/ICDAR2019-SROIE` both store LINE segments in a field named `words`** —
  `'TEL:07-388 2218 FAX:07-388 8218'` as one unit, **57%** multi-word — which shrinks the
  recall denominator ~2.1× and inflates every unit by the same factor, silently; and both are
  **347/347 aligned** `words`↔`boxes`, because the boxes are per-*segment*. **Alignment is
  necessary, not sufficient — it is exactly what hides the mismatch** (D14 §1b's denotation
  check, on a field whose name lies). (iii) **`jsdnrs` and `vishu12121` report byte-identical
  split sizes** (354,338,486 / 214,928,929) — the same upload twice, so two "independent"
  mirrors agreeing is not corroboration. The chosen mirror was then loaded: **0 of 40,411
  units contain whitespace**, 347/347 per-word boxes, images decode (doc0 932×2212).
  ⚠ **The mirrors disagree about the test set: 347 vs 361.** 347 is canonical; a 14-document
  discrepancy between re-uploads of "the same" corpus is a provenance signal, recorded.
  ⚠ **SROIE's licence is checked and found second-hand.** The `mit` tag is asserted by a
  third-party uploader, **not** by the ICDAR 2019 organisers who hold the original terms —
  and three re-uploads of one corpus carry `mit` (sizhkhy, buthaya) and `cc-by-4.0` (jsdnrs)
  without agreeing. Of **100** SROIE-matching HF datasets, **77 carry no licence field at
  all**. CORD's `cc-by-4.0`, by contrast, comes from `naver-clova-ix` — the publishing lab
  itself, the one candidate whose licence is first-hand. This is a **publication question for
  the user to decide, not a measurement question**; nothing downstream is blocked. If the
  answer is "not acceptable", the fallback is CORD at n=100, which by the above cannot be
  pooled — so the pool would be FUNSD-only at n=50 and T1 §7's `UNDERPOWERED` becomes
  permanent.
  ⚠ **The pool is 87.4% receipts by document and 82.2% by word** (49,140 words) — a "pooled"
  result is substantially a *receipt* result and **FUNSD is a 12.6% minority in its own
  successor corpus**. Report per-corpus and pooled; never let the pooled number stand alone.
  ⚠ **T1 §3 simulated its null p95 at `n=397` before T2 confirmed 397** — the
  pre-registration assumed this answer and happened to be right. Re-derive against the loaded
  pool before run 17 scores anything, rather than inheriting a number written against an
  unverified size.
  ⚠ **D14 §4's "trim can delete FUNSD" is reduced, not eliminated:** g=0.10 at n=397 discards
  **39 per tail** against FUNSD's 50 documents — 78% of the only corpus measured to date, no
  longer 100%. T1 §5's per-corpus constraint is what prevents it and must be **implemented in
  T4's scorer**, not merely written down.
  **The script audits its own first draft and two controls assert that draft was wrong.**
  It had claimed *"13/100 CORD docs land exactly on −10.000000 vs 9/50 FUNSD"*, framing the
  tie convention as a CORD-specific hazard. Both counts were wrong (**measured 17/100 and
  7/50**; SROIE 27/347) and **the framing was worse than the counts** — an exact tie needs
  only `n ≡ 0 (mod 10)`, which happens everywhere, so ties are *not* CORD-specific at all
  (17% vs 14%). The draft's test asked whether `1000/n` is an integer, i.e. whether *n
  divides 1000* — a rarer and different condition that is still satisfiable, so it returned a
  **plausible wrong number rather than an error**. **The real asymmetry is one the count
  never showed:** on a median 20-word receipt **2** wrong words land exactly on the threshold;
  on a median 177-word form it takes **18** — an ordinary single-document event versus an
  effectively unreachable one. Also corrected: FUNSD's median is **177** words/doc, not the
  167 carried in the first draft of the T2 note, and CORD's `words` is *mostly* but not
  perfectly word-level (**35/2356 = 1.49%** multi-word; FUNSD 19/8707) — immaterial to the
  decision, but "true word-level" was too strong for CORD.

- **2026-09-24 — T1 DONE: run 17's pre-registration is written, before any run-17 number
  exists.** New section `## Run 17 pre-registration (T1)`. D14 was the specification; this is
  the rule. T3 and T7 unblocked. **The contrast is named first**, because D14 §1b showed the
  estimator questions are not well-posed until it is: **`keep=0.50 m=0.20 ink` vs
  `keep=0.40 ink TWIN` at M=1920** (token-matched, verified equal on disk in both runs),
  estimand *"at an equal token budget of 1920, does merging preserve more word recall than
  pruning alone?"*. Chosen on three sign-blind grounds — T5's statement that ToMe exists to
  win *at matched M*; `keep=0.50 m=0.20` being the canonical operating point D13 already
  calibrated on; and the Q6 table's own instruction to *"read the ink pair, which isolates
  the mechanism from the router's weakness"*. **It lands on a pair that has never been a
  declared winner** (+2.28 / −0.13 plain; +1.66 / +0.02 trimmed) — recorded as evidence the
  choice was not effect-shopping, explicitly *not* as a reason for it.
  **What the rule pins:** 10% trimmed mean of per-document differences with
  **difference-then-trim** ordering (D14 §3 measured the orderings 0.8081 pts apart);
  **Tukey–McLaughlin** SE, not `stdev(trimmed)/√n_trimmed` which is ~33% too small;
  deterministic `±1.96·SE` rather than a bootstrap, because a bootstrap endpoint is one draw
  and D14 §1c is about verdicts turning on noise; **units and direction per quantity** with
  every threshold in points (D14 §1d: on the stored [0,1] fields a bare `res ≤ 2.0` cannot
  fail); Holm over **three** quantities, not four, since charAcc is an affine map of NED;
  discard set in documents with a per-corpus constraint (D14 §4); and **equal arity on both
  verdicts**, which is structurally guaranteed here because there is one named pair and so no
  N to take the best of (D14 §1c).
  **The tail gates are the part that cuts hardest against merging, which is why they are
  written before the run.** Two statistics — worst-document ratio `min(d)/(Blom(n)·wsd)` and
  the harmed count at −10.0 points with a **strict `<`** tie convention — each gated at the
  **p95 of a matched-normal null simulated from the row's own n and winsorized sd**, not a
  constant. The bar therefore tightens with n (p95 **1.74** at n=50, **1.52** at n=307,
  **1.51** at n=397) and has a 5% false-alarm rate by construction. **On the named primary,
  run 14 scores a trimmed mean of +0.02 pts — the cleanest imaginable "no measured cost" —
  and fails both gates**: worst document **−40.00 pts** against a null expectation of −12.43
  (ratio **3.22**, above the n=50 p99 of 2.05) and **5** harmed documents against a null p95
  of 4. Run 13 on the same contrast is clean on both (1.11 and 1.07, *below* the null median
  of 1.20). A rule without a tail statistic reports run 14's primary as a perfect null.
  **And the rule hands T2 a number instead of a direction:** `res ≤ 1.0 pt` needs **n ≳ 307**
  (run 13's wsd; run 14's gives 185), so FUNSD+CORD (~150, unverified) does not reach it and
  FUNSD+SROIE (~397, unverified) does. At n=50 the MDE is **~2.5 pts**, so `FREE` is
  unreachable on FUNSD alone and `UNDERPOWERED` is the expected outcome — reported with the
  required n rather than as a null.
  Also fixed while in the file: **T1 contained a byte-identical duplicated block** (the
  "location estimator alone is not sufficient" and "word order is not scorable" warnings
  appeared twice), now deduplicated.

- **2026-09-23 — D14: T1 was scoped as an estimator choice; the estimator is the smallest of
  seven unpinned degrees of freedom, and T1 is rescoped.** `scripts/diagnose_analysis_dof.py`,
  **20/20 controls**, exit 0, `results/analysis_dof_local.log`. No GPU, <10 s. Every figure
  recomputed from the raw `per_image` arrays in `run 13/ablation_selection.json` and
  `run14/ablation_selection.json`; section 0 reproduces D13's published +2.86 / res 3.16
  before anything new is read off them. Continuing T1 from D13 §5: before writing a rule that
  adopts a trimmed mean, I asked what *else* the rule leaves unwritten. The answer is most of
  the analysis.

  **(a) "Run 14, m=0.40" names two contrasts, 5.08 pts apart — and I found it by accident.**
  I measured (c) and (d) below with an ad-hoc probe, then wrote the script to make them
  reproducible, and **the script disagreed with the probe.** Neither was wrong: they had
  silently picked different control rows for the same named contrast. Against
  `keep=0.50 router` (same keep fraction, run 14's *published primary*) the trimmed estimate
  is **−0.17** — a null, the "merging is free" row. Against `keep=0.30 router TWIN`
  (token-matched, equal M) it is **+4.91**. Both are legitimate estimands; the
  pre-registration names neither; this file's own prose has used the phrase both ways. A
  degrees-of-freedom hazard that produced a contradiction between two of my own measurements
  inside one session is not hypothetical.

  **(a2) The escalation of (a), and the strongest item in D14: runs 13 and 14 both declared
  `MERGING WINS` — on *disjoint* rows.** (a) shows the rule leaves latitude; this shows the
  latitude was **already spent**, twice, by this project. Script §9 reconstructs the
  pre-registered Q6 criterion from the raw arrays (`mean ± res` reproduces the shipped CI
  column to ~0.01) and scores all six pairs in both runs. Run 13 certifies
  **`M=3840 router` +3.12 [+0.19, +6.04]** and **`M=1344 ink` +4.06 [+0.24, +7.87]**; run 14
  certifies **`M=1344 router` +4.22 [+0.06, +8.37]** and **`M=1440 router` +5.78
  [+0.88, +10.69]**. **Intersection: ∅.** Every run-13 winner regressed toward zero in run 14
  (+3.12 → +0.81, +4.06 → +1.43) and both run-14 winners had been *negative* in run 13
  (−0.22 → +4.22; **−1.29 → +5.78, a +7.07 swing**). **The arity is the mechanism:**
  `MERGING WINS` needs **1 of 6** pairs, while `INDISTINGUISHABLE` — which the same table
  calls *"the **good** outcome for the architecture"* — needs **all 6** flat **and** all 6
  under `res ≤ 3.0`, so one wide pair vetoes it. Measured: **4/6** pairs exceeded 3.0 in run
  13 and **5/6** in run 14, so the null verdict was arithmetically unreachable in *both* runs
  while the positive one fired on a single pair each time. That is a ratchet, not a
  tie-breaker — and the design predicted it, annotating that row **"AT RISK"** before shipping
  the rule anyway, twice. The rule's prose sets a better standard than its criterion column
  (*"the evidence is the **pattern** — the two ink pairs agreeing with the two router pairs at
  the same merge ratio"*) and **that standard fails too, with the roles swapped between runs**:
  at m=0.20 M=1344 run 13 reads router −0.22 vs ink +4.06, run 14 reads router +4.22 vs ink
  +1.43. Consequence, and it is a constraint rather than a preference: **no rule that takes
  the best of N pairs is admissible**, because best-of-N has now been shown uncorrelated
  across runs. See D14 §1c.

  **(a3) And no declared winner survives the family it was drawn from — nor does my own
  prescription survive its own audit.** Script §10 runs Holm step-down at α=0.05 over the
  family using **z-tests at 1.96**, i.e. the instrument the published criterion already uses,
  so this isolates multiplicity rather than smuggling in an estimator change. **The family is
  6×2=12, not 6×3=18:** only `recall` and `ned` are stored per image, `charAcc = (1−mean(ned))
  ×100` is an affine transform of `ned` and so not an independent witness, and `word_order` is
  not on disk for either run — and 12 is the *weaker* correction, which is the honest one.
  Result: run 13 has **3 of 12** nominally significant (smallest p **0.0240**), run 14 has
  **2 of 12** (smallest p **0.0208**), first Holm threshold **0.05/12 = 0.00417**, **zero
  survivors in either run**. Both miss by ~5×, so the finding is insensitive to the choice of
  correction — even a recall-only family of 6 puts the threshold at 0.00833, still ~2.5× below
  both. **Neither published `MERGING WINS` verdict survives any correction at all.** Filed
  alongside it, and deliberately not promoted: run 13's smallest p in the family is
  `M=1920 router` on **`ned`** (+3.66, p=0.0240) — the pair the recall-only rule scored *flat*
  (+2.86, CI [−0.30, +6.02]), so the pre-registered quantity was the less sensitive one **on
  the row D13 headlined**. That is a reason to distrust that row's null, **not** a licence to
  re-headline on `ned`. **And §10's last control is aimed at (a2)'s own closing advice:** §1c
  tells T1 to *"set the `res` gate from the observed `sd`"*, and on the stored [0,1] fields a
  bare `res ≤ 2.0` **cannot fail** — native res is **0.0264–0.0381**, the arithmetic ceiling
  for a paired delta of a [0,1] field at n=50 is **0.280** (7.1× inside the gate, 52× for the
  observed values), and `count(d < −10)` can never fire because native deltas lie in [−1,1].
  Any run scored on the arrays as-stored returns *"powered, no harmed documents"* by
  arithmetic, with the auditable defence *"I used the stored field."* So the rule must pin
  **units per quantity and units on every threshold**, not only direction — §2's hole, one
  level up. §6 gains three requirements from this: units on thresholds, **equal arity for the
  positive and null verdicts**, and the correction family named and sized before scoring.
  See D14 §1d.

  **(b) Seven choices are unpinned and each swings ≥ the ~1.0 pt target effect.** Which
  contrast is primary (**5.08 pts**, above; run 13 has 7 selection-matched and 12
  budget-matched (merge, non-merge) pairs); which split is "the merge arm" (**+1.12 pts** —
  checkerboard trim +1.35 vs rank_parity +2.47 at M=1920, *both already on disk*); direction
  per quantity; the trim fraction g; the DiD ordering; the tie convention; corpus composition.

  **(c) `ned`'s worst-case delta is +7.64 where recall's is −96.61 — on the sabotage arm.**
  `diagnose_merge_power.py:arr()` scales every key ×100 and encodes **no direction**,
  survivable only because all five `PUBLISHED` calibration tuples are recall. `ned` is an
  error rate. So a tail statistic phrased "worst per-document delta" — the obvious phrasing,
  and the one D13 §5 invites — would rank the **deliberately-broken** arm as the safest row in
  the sweep. Direction must be pinned per quantity, not once globally.

  **(d) Adopting the trimmed mean *creates* a degree of freedom.** The mean is linear, so a
  DiD is order-invariant (**+3.5822** both ways, gap identically zero). The trimmed mean is
  not: trim(per-doc DiD) **+3.8696** vs trim(d14) − trim(d13) **+3.0615**, a gap of **+0.8081
  pts** — 26% of the effect, 16× the ±0.05 pt seed-noise floor, and **42%** of the resolution
  the trim buys on that contrast. Naming "10% trimmed mean" does not determine the estimate.
  On the same contrast g picks the sign: **+0.22 / −0.17 / −0.24** at g ∈ {0.05, 0.10, 0.15},
  all null (so D13's "zero verdict flips" is honest and beside the point) — and the sign does
  *not* flip on the token-matched pairing, so even "pin g" depends on (a).

  **(e) T1 × T4: at pooled n=500, g=0.10 discards exactly FUNSD.** k=50 per tail; FUNSD's
  whole contribution is 50 documents; run 13 m=0.40 has 10 harmed documents (6 on the other
  pairing) — all of which fit inside the discard set either way. The power fix and the
  robustness fix are individually correct and jointly capable of deleting the only corpus the
  project has measured. Recorded in **both** T1 and T4, where it was missing from both.

  **(f) There is no token-matched `random` arm in either run.** Merge-row budgets are
  `[1344, 1440, 1920, 3840]`, random-row budgets `[1680, 2400, 3600]`, overlap **empty**. So
  "merging beats random at matched M" is not a weak control — it is **not computable** from
  runs 13/14. Now a build requirement on T4.

  **(g) A correction to T1's own rationale.** It read *"the −64 pt control still resolves."*
  Its Tukey–McLaughlin half-width is **6.09 at n=50** (≈1.92 at n=500), so it satisfies no
  absolute-width gate; it excludes zero by ~10σ and always will. The clause conflated two
  meanings of "resolves" and is rewritten, not deleted. D13's own summary carried the same
  clause and is annotated in place, along with its "stable across g with zero flips" line —
  true of *verdicts*, and not of signs.

  **Two errors of my own, both caught by this script's controls, both recorded in D14.**
  (i) The first draft of §3 claimed the DiD ordering gap was *larger* than the resolution the
  trim buys; it is 42% of it. The control asserting "larger" **failed**, which is how it
  surfaced — and the overstatement was in the direction that flattered the argument.
  (ii) The first draft filed the merge-minus-random control as **unverified** because my probe
  used row names that do not exist. Enumerating the budgets showed the names do not exist
  *because no such pairing does* — a stronger result than the one I had failed to reproduce.
  "I could not reproduce it" was concealing a finding.

  **What did not change:** D13 §§2–4 stand. Heavy tails still argue for a robust location
  statistic; D14 says a location statistic is not an analysis. Nothing here licenses picking
  the flattering side of any of the seven — the swings measure analyst freedom, not effects,
  and §1b in particular does not license preferring the +4.91 reading.

- **2026-09-23 — D13 §5: the trimmed mean is exactly blind to the tail, which changes T1's
  answer; and `word_order` is blocked on a stored field.** No GPU, <60 s,
  **36/36 controls** (was 30/30), `results/merge_power_local.log`. Executing T1 (top of the
  queue) started with measuring what D13's recommended estimator *discards*, before writing
  a rule that adopts it. Three results:

  **(a) The ~30% resolution gain is paid for with exactly the documents the claim is about.**
  Section 5 measures the tail directly: |z|max is 3.47–5.01 on all nine contrasts against a
  deterministic matched-normal null's 2.33, excess kurtosis 3.13–11.30. The decisive row is
  run 14's published primary — **"no measured cost", trimmed mean −0.17 pts, containing a
  page that lost 72.34 points.** Pushing the single worst document 25 pts further leaves the
  trimmed mean unchanged **to the last bit on 6/6 merge contrasts**, while it moves the plain
  mean by 225% of its own effect at M=1344. So the trim does not merely down-weight the tail,
  it is *insensitive* to it — and an accuracy-**preservation** claim is precisely a claim
  about that tail.
  **Consequence for T1:** the rule must pin a **tail statistic alongside** the location
  statistic, not choose between mean and trimmed mean and stop. Noted at the time that this
  cuts *harder* on merging than the current rule does — which is why it is written before
  run 17 exists, not after.

  **(b) Two of the six new controls were decorative on first write, and were replaced.**
  Recorded because the failure mode is the reusable part, not the fix. (i) *"worst document
  exceeds 3.5 sd on 8/9 contrasts"* — threshold chosen after seeing the numbers, plus a
  one-miss allowance, i.e. fitted to the data it was checking. Replaced with a ratio against
  each contrast's **own** matched-normal null (every contrast's worst doc must sit >1.4×
  further out; min observed 1.49), which has a null that can fail. (ii) *"the plain mean DOES
  move under the same push"* — the shift is `push/n = 25/50 = −0.50` on every contrast **by
  construction**, so a completely broken estimator scores identically. Replaced with the
  material version: the move must be large **relative to the contrast's own effect** (225% at
  M=1344). Both are the same error — a check whose pass is guaranteed by arithmetic rather
  than by the property being claimed.

  **(c) `word_order` cannot be back-scored, and is not derivable — the inverse of the charAcc
  result.** charAcc collapsed into NED because it is an affine map of a stored field.
  Word order is *not* stored per image in runs 13/14 (`per_image` holds `gen_tokens, i,
  mean_line_cov, min_line_cov, n_text_rows, ned, p10_line_cov, recall, retained_ink,
  tokens`) and cannot be reconstructed: `compute_word_metrics` (`src/evaluate.py:44`) needs
  the raw predicted and gold word *sequences*, neither is written to disk, and `recall`
  (order-blind by design) and `ned` (character-level) do not determine it. So **T3 delivers
  two of three quantities**, and the three-quantity primary is first *exercised* at run 17 —
  the multiplicity rule is still written over three now, so that run 17 does not quietly drop
  to two because two is what the back-scoring could manage.
  The run-17 guarantee was then checked **by executing the generator, not by grepping the
  committed notebook** — the distinction matters because T4 mandates re-verifying against a
  *regenerated* notebook, so a field present only in the committed copy would vanish with no
  symptom. `scripts/make_kaggle_pruning_notebook.py` injects it as G3b (`:1061`) behind an
  asserted anchor; regenerating gives exit 0, the field present, and a file **byte-identical**
  to the committed one (sha `2d35b7e0bc14e207` before and after) — so there is no drift, and
  the backup restored to that same hash. T4's `word_order` clause therefore needs verifying,
  not building.

- **2026-09-22 (later, same day) — D13: the ToMe blocker is the instrument, and the queue is
  reordered around that.** No GPU, <10 s, 30/30 controls, `results/merge_power_local.log`.
  The session opened on the premise that "the ToMe architecture is not working properly."
  **It is working.** It executes (`enc 1440` = 2400 − 960 on every run-14 epoch), it is correct
  (`verify_tome_merge_port.py` 89/89 with non-vacuity controls, 13/13 correctness, 10/10
  parity), and m=0.20 is free at four budgets under both router and ink selection. What is not
  working is the **instrument**: per-document sd 11–13 pts at n=50 gives res 2.9–4.3 against
  effects of 0.5–3.1, so UNDERPOWERED was structurally guaranteed for runs 12, 13 and 14
  regardless of what the merger did. Four things:

  **(a) The diagnosis was one row away from being obvious for three runs.** M=1920
  merge-vs-prune — the *one* question ToMe exists to answer — observed **+2.86 at res 3.16**,
  needed **n ≥ 62**, had **50**. Twelve documents and 0.08 pts of CI. It was filed as
  UNDERPOWERED alongside everything else and never singled out.

  **(b) `n` was mis-generalised from a true statement.** This file's own line — *"`n` is not a
  knob: 50 **is** FUNSD test"* — is correct **within FUNSD** and was read as "not a knob at
  all." It is a knob if the corpus changes, and the 28-row sweep is eval-only, so widening it
  costs CPU, not GPU. Filed as Pending 19 / T2+T4.

  **(c) A ~30% resolution gain was sitting unclaimed in the estimator.** Variance is
  concentrated, not length-driven: **5 of 50 docs carry 75.6% of the sum-of-squares**; CUPED on
  `n_text_rows` buys +0.0–3.7%. That makes bootstrap-on-means the *least* powerful choice
  available. This is now an input to Pending 18 / T1 and **must be written before run 17 sees a
  number** — see the D13 section for why it does not license a post-hoc switch, and note it
  cuts against claim 3 (the trimmed estimate flips m=0.20 from +0.54 to **−0.65**).

  **(d) The top of this file now carries a serial TODO queue (T1–T8).** Added at the user's
  request: *"make a section for to do tasks that will be checked everytime i ask to resume
  work."* Every item has a venue, a blocked-by, and a **DONE-WHEN** criterion, because this
  project has already shipped a 13-day silent verifier crash that read exactly like a passing
  check. Pending 16/17 are **not** first: at n=50 they fix the confound and leave the power
  untouched, so 4–4.5 GPU-hours buys a correctly-designed fourth UNDERPOWERED.

  *Two self-corrections inside the diagnostic itself* — a trimmed-mean SE that was 33% too
  small and manufactured a RESOLVED verdict, and a control that failed 9/10 and was right to —
  are written up in the D13 section rather than here, because they are the reusable part.

  **Also found, unrelated to power:** `src/model.py:248` computes merged coordinate centroids
  into `final_coords` and never reads them (the `generate()` path at `:372` already discards
  them as `_`). The architecture diagram's *"w/ 2D coord centroids"* describes a path that is
  not wired. Filed as T8.

- **2026-09-22 — the harness gap run 14 booked was half real, the other half was a verifier
  that had been crashing silently for 13 days.** No GPU. Five things:

  **(a) `char_acc` was never unbootstrappable.** Cell 15 computes
  `character_accuracy_pct = (1 − mean(ned)) × 100`, and `ned` has been stored per image since
  run 9 — so charAcc is an affine transform of an array already on disk. Verified against the
  shipped artifact at **≤2.1e-14 across all 28 rows** of `run14/ablation_selection.json`. The
  run-14 table's "—" cells are now filled: charAcc **−2.85 [−7.04, +1.09], res 4.06**. Method
  validated first by reproducing every published recall/NED figure in that section to four
  decimals. *The generalisable point:* "the harness does not store X" was true of the **field**
  and false of the **quantity**, and nobody checked whether X was a function of something
  already stored. Before booking a measurement as blocked, ask what it is arithmetically.

  **(b) The correction changes the design, not just the table.** charAcc's Wilcoxon p is
  *identically* NED's (0.0290 here, 0.0002 on run 13) — a strictly decreasing affine map leaves
  the paired two-sided p invariant. So **"pre-register across all four metrics" is across three
  quantities**: recall, NED≡charAcc, word order. Correcting for multiplicity over four would
  double-count the one quantity carrying the effect, in the direction of declaring one. Filed
  as Pending 17(b).

  **(c) Run 14 adjudicated the same test disagreement two opposite ways, eleven lines apart.**
  On the DiD it wrote that "the pre-registered bootstrap governs" and declined Wilcoxon's
  p=0.0099. In the four-metric table it called NED "significantly worse" on Wilcoxon's p=0.0290
  while printing, in the same row, a bootstrap CI **[−0.0109, +0.0704] that contains zero**.
  Both cannot be the rule. Corrected reading: **all three testable quantities are
  bootstrap-nulls at this resolution**, and the partial-recovery signal rests on point
  estimates plus a side-check. The strongest bootstrap-grade statement available is narrower
  and still worth having: on charAcc, run 13's CI **excludes** zero and run 14's **does not**.
  Deciding this rule is now Pending 18, and it must be written **before** item 17 sees a
  number — the file already knows what choosing a statistic after the data looks like.

  **(d) The real gap was one metric, and fixing it exposed a decayed control.** `word_order`
  genuinely was not stored, though `o` sat two lines above the append — generator patch
  **G3b**, four new controls in `verify_tome_merge_port.py` (**85 → 89**), both identities
  **mutation-tested**: storing `recall` instead of `o` FAILs, computing charAcc from the median
  NED FAILs. Not retroactive — runs 13/14 have no per-image order array, so those −5.82/−3.33
  figures stay untestable permanently; word order is testable from run 15 on. Then, re-running
  the gates against the regenerated notebook: **`verify_results_provenance.py` raised a
  `ValueError` on `kaggle_pruning_run.ipynb` after its first check, and had been doing so since
  G4 renamed the sweep loop.** This file recorded it as "35/35 on both notebooks" throughout.
  It is the check that closed Pending 6 and the only reason run 12's wrong-checkpoint attach
  was ever detected — and it was not running on the notebook that produced runs 12, 13 and 14.
  Repaired; now genuinely 35/35 on both. *[[controls-decay-silently]], with a sharper edge than
  usual: this control did not weaken, it **crashed**, and a crash reads exactly like a check
  nobody ran. The lesson is to re-run the whole gate set after regenerating an artifact, and to
  distrust any "N/N on both X" claim that no one has re-executed since X diverged.*

  **(e) Closing Pending 15 needed a second look, because I first closed half of it.** Item 15
  read "settle the ordering question, **or scope ToMe out**", and the first close cited only the
  engineering half (checkerboard landed, verified, sweep has run three times). The `or` branch
  was never explicitly decided, and it sits *upstream* of Pending 16 and 17 — if ToMe were
  scoped out, the `keep=0.30, merge=0.0` checkpoint has nothing to be symmetric to and item 17
  has no contrast to draw. Decided here as **do not scope out**, on run 13 rather than run 14:
  run 13 evaluated on run 9's `keep=0.50, merge=0.0` weights, which had **never seen a merged
  token**, so every merge arm was off-distribution and biased *against* merging, and it still
  returned two significant token-matched wins (**M=3840 +3.12 [+0.21, +6.05]**, **ink M=1344
  +4.06 [+0.43, +8.05]**). Run 14's larger **+5.78** at M=1440 is the *contaminated* one and
  must not be the reason. The residue now recorded with the closed item: **the checkerboard fix
  has never beaten what it replaced on recall** — checkerboard − rank_parity at M=1920 is
  −1.51 / −0.29 / −0.88 across runs 12/13/14, rank_parity numerically higher all three times,
  and checkerboard is still the default at both call sites. The split is justified by a
  **partition** statistic (missed vertical redundancy → 0.0%), never by an accuracy one.
  *[[measure-mechanism-and-goal-separately]] — the mechanism moved exactly as designed and the
  goal never followed; both belong in the record, and a closed item is the easiest place to
  lose the second one.*

- **2026-09-21 — run 14 filed. The primary read UNDERPOWERED, and the interesting result is a
  control I had not pre-registered.** Full scoring in "Run 14 — result". Four things worth
  carrying forward:

  **(a) The pre-registered prediction was right, and being right did not help.** The checklist
  said a 3.86-pt effect measured at ≈3.5-pt resolution "can resolve a FULL recovery and cannot
  resolve a PARTIAL one", and predicted UNDERPOWERED-or-RECOVERED. It came back flat (−0.28)
  at res 3.95, so: UNDERPOWERED, licenses nothing, and **run 14's CI still contains run 13's
  −3.86**. Correctly forecasting that a design cannot answer its question does not make the
  answer available. The design should have been changed, not just annotated — and the one
  honest lever was never `n` (50 *is* FUNSD test) but the *effect*: contrast m=0.40 against
  m=0.00 across **two** checkpoints in one run, which is the DiD I had to compute afterwards.

  **(b) The control that mattered was not in the checklist.** Run 14 improved on the trained
  merge row by +3.11 (p=0.0052) — and by **+3.43 on `keep=0.50 random`** (p=0.0293) and
  **+3.21 on `keep=0.50 ink ORACLE`** (p=0.0489), rows containing no merging at all. Merge-row
  gain minus random-row gain is **−0.32 (p=0.60)**. So the gain is not distinguishable from a
  general robustness lift, and `TRAIN_MERGE_RATIO` may simply be acting as decoder
  augmentation. *The generalisable point:* the checklist pre-registered the treatment row, its
  token-matched twin, and a sabotage arm — but no **"did this checkpoint just get better at
  everything"** control. Every future train-side change needs one, and the cheapest one is
  already in the sweep: the `random` row at the trained budget.

  **(c) A number in the summary line was doing double duty.** "40% costs −3.86" is the
  merge-vs-no-merge contrast at fixed `keep` (75.77 vs 79.63). The **token-matched** M=1440
  pair on run 13 was **−1.29 [−4.81, +2.26], not significant**. Both are real; they answer
  different questions; the one-liner reads as the second. Fixed by naming the contrast
  wherever the figure appears. This is [[correct-numbers-by-grepping-digits]] in its other
  form — not a wrong digit, a right digit with the wrong referent attached.

  **(d) Bootstrap and Wilcoxon disagreed on the DiD, and both are filed.** Bootstrap CI
  [−1.43, +8.25] includes 0; Wilcoxon p=0.0099. The bootstrap was the pre-registered
  statistic, so it governs. Wilcoxon was run because the DiD endpoints moved with the seed
  (0.47–0.72 across five seeds on the paired contrast) — the draw-invariant check the
  resampled-statistics rule calls for. Recorded side by side per the D12 convention, with the
  pre-registered one explicitly named as binding, rather than quietly adopting the one that
  says what I wanted.

  **(e) Sabotage row closed after a third null.** checkerboard − rank_parity at M=1920:
  run 12 −1.51, run 13 −0.29 (p=0.40), run 14 −0.88 (p=0.85). Three checkpoints, three nulls,
  `rank_parity` numerically higher **all three times**. The checkerboard fix moves the
  synthetic missed-redundancy number (49.2%/50.5% → 0.0%/0.0%) and has **never moved recall**.
  Closed as pre-registered. A partition being provably correct is not evidence it is
  measurably better.

  **(f) New and unprompted: the router degraded as a selector.** Margin over random
  +17.07 → +13.16 (change −3.90, p=0.0500); edge over the ink oracle +2.74 (p=0.0073) → −0.94
  (ns). Sign still correct (`negated` 15.15), so this is not the D1 inversion. Also means run
  13's +2.74 — the project's first *significant* router-beats-ink reading — is erased by run
  14 and must not be promoted.

  **(g) The recall null is contradicted by the other three metrics, and the harness cannot
  test two of them.** On the identical contrast: recall −0.28 (p=0.9197), **NED +0.0285
  (p=0.0290, significantly worse)**, charAcc −2.85, word order −3.33. Against run 13, charAcc
  and order both moved to roughly *half* their previous cost (−5.79 → −2.85, −5.82 → −3.33)
  rather than to zero. That is the signature of a **partial recovery** — precisely the case
  the checklist stated in advance it could not resolve. Recall is simply the metric where the
  residual is smallest relative to its noise. *Two concrete consequences:* (1) do **not**
  re-headline on NED or charAcc, which would be picking the metric after seeing the data;
  (2) `per_image` stores only `recall` and `ned`, so `char_acc` and `word_order` cannot be
  bootstrapped at all — **add them to the per-image record** so a future primary can be
  pre-registered across metrics instead of resting on the one that happens to be noisiest.

- **2026-09-18 — runs 12 and 13 filed; my pre-registered prediction was falsified; run 14
  launched.** Both runs sat on disk unfiled for two days while the notebook work continued,
  which is the gap that let two of their findings stay invisible.

  **(a) Run 12 evaluated the wrong checkpoint, and the provenance stamp is the only reason
  anyone knows.** The launch checklist named run 9's `adaptive_donut_pruned.pt`; the session
  attached run 5's `adaptive_donut_funsd.pt`. Nothing in the run *looked* wrong — 28 rows, all
  verdicts printed, the token-match assert passing on all 50 images of all 6 pairs — and the
  control drift of **0.0037** would read as a *pristine* harness to anyone who did not know
  that near-zero drift against `RUN6_REFERENCE` is only achievable on the weights run 6 itself
  evaluated. The F2 provenance stamp (added in run 9 so a results file could name its own
  weights) caught it by `size_bytes` and path. **Convention, now standing: read
  `meta.provenance.eval_ckpt` before reading any row.** The consequence is that run 12's four
  router pairs measure a router that scores *below its own negation* (24.97 vs 51.65 at
  keep=0.50) and its headline `+36.83` is a selector artifact, not a merge result.

  **(b) My pre-registered prediction for run 13 was falsified, in direction.** I wrote
  "merging will lose at equal M, on every pair, and lose most at the tight budgets." Result:
  **0 of 6 pairs favoured pruning, 2 favoured merging, 3 underpowered, 1 indistinguishable**,
  and the pair I named as the *smallest* loss produced the largest merge *win*. Left struck
  rather than edited, per this file's convention. The transferable part: the prediction was
  reasoned purely from D12's off-distribution logic, and **this project's merge results have
  now come back less negative than that logic predicts three times running.**

  **(c) The one real merge cost, and the check that it is not a seed artifact.** Holding
  selection fixed (the contrast Q6 does *not* compute — Q6's pairs vary both the selection and
  the merging), run 13 gives five nulls at m=0.20 and one resolved negative at m=0.40:
  **−3.86 [−7.54, −0.35], res 3.59.** Its CI endpoint sits 0.35 pts from zero, which is
  normally where a bootstrap result turns out to be noise, so it was checked against its own
  noise: **12/12 seeds exclude zero** (endpoint moves ±0.05), Wilcoxon **p = 0.0048**, paired
  *t* **p = 0.040**, sign 29/15/6. It survives Bonferroni over the six contrasts on the rank
  test and not on the *t* test; quote it as a real single-row effect. Supported claim:
  **merging away 20% of the kept set is free; 40% is not** — which licenses **2.5× decoder
  cross-attention KV at M=1920 at no measured cost** via M1, and makes 3.33× at M=1440 run
  14's target.

  **(d) A verdict string that overstates its own table, shipped in two runs.** Cell 15 prints
  `=> MERGING BEATS PRUNING AT EQUAL M` whenever `favour_merge > favour_prune`, **with no
  reference to how many pairs were unresolved** — so it fired on run 13's 2-of-6-with-3-
  underpowered and on run 12's void table. Same defect class as the two already fixed this
  cycle (prose overstating the statistic beneath it); it survived because every number *above*
  it was correct. Pending: require `favour_merge ≥ favour_prune + 2` and `underpowered ≤ 1`,
  or delete the sentence. ***Done the same day — see (g); the bar landed as ≥2 resolved pairs
  one way AND ≤1 underpowered, applied to BOTH directions.***

  **(e) The sabotage row is closed: null on both checkpoints** (run 12 −1.51 [−3.22, +0.19]
  res 1.7; run 13 −0.29 [−3.10, +2.76] res 2.9), with `rank_parity` numerically *higher* both
  times. **The checkerboard fix is correct about the partition and unproven about recall.**
  `diagnose_tome_parity.py`'s 49.2%/50.5% → 0.0%/0.0% is a claim about the split only.

  **(f) Two log defects fixed in the generator**, both the D5 shape (a thing that shapes or
  describes a run while being invisible or wrong in the log): every run since 9 opened by
  printing `training skipped` while then training for four hours (`EVAL_ONLY` predates
  `DO_TRAIN`; the *behaviour* was right, the *log* lied), and run 14's single variable would
  have had no per-epoch evidence at all — `ch` reads 0.500 whether or not the merger ran, and
  the merged length lived only in a tqdm postfix. New **`enc`** column reports what the decoder
  actually received per epoch (2400 = merging did not run, 1440 = it did at 0.40), and
  `verify_attn_train_step.py` check **5b** proves the column tracks the real number rather than
  a literal. `TRAIN_MERGE_RATIO` also became the **third** knob to be inherited into that
  verifier's scenario table instead of pinned — after `lambda_entropy` and `DO_TRAIN` — so
  every literal the shipped asserts touch is now pinned there (~~11/11 fast~~ **13/13 fast after
  (g)3 added two more scenarios**; ~~the `--full` execution gate is the launch blocker and its
  result is recorded below when it lands~~ **`--full` landed 2026-09-18: 24/24, exit 0** — the
  13 fast gate scenarios plus 3 setup and 8 core execution assertions, `/tmp/attn_full4.log`).

  > **The `--full` gate, read rather than skimmed (2026-09-18).** 24/24 and exit 0, but two
  > lines in it are worth transcribing because neither is a pass/fail:
  >
  > - **`ov 0.376 ch 0.500 lift -0.124`** — the router's top-K held *less* of the teacher's
  >   top-K than chance. That is the `ATTN_TARGET=True` scenario, two steps from a checkpoint
  >   whose router never saw an attention target, on a path D11 already closed; the harness
  >   prints its own disclaimer that it "says NOTHING about whether the target helps". Run 14
  >   ships `ATTN_TARGET=False`, so this does not touch it. Recorded so the negative number is
  >   not rediscovered later as news.
  > - **`enc 2400`, i.e. check 5b at `merge_ratio=0.0`.** This gate proved the 13 merge-*scoped*
  >   gate scenarios, but it executed the training **body** unmerged. It is therefore *not* the
  >   gate for run 14's distinguishing variable, and reading 24/24 as covering
  >   `TRAIN_MERGE_RATIO=0.40` would be exactly the mistake check 5b's own wording warns about
  >   ("reading 2400 there would mean the merger never ran"). The body at 0.40 is covered by
  >   `scripts/verify_train_with_merge.py` — **32/32, exit 0, same day** — which executes a real
  >   step at 0.00/0.20/0.40 and asserts M=2400/1920/1440, that the router gradient is finite
  >   and non-zero at each, and — the load-bearing pair — that re-running 0.00 is **bit-identical
  >   (noise floor 0.000e+00)** while 0.20 shifts the router gradient 2.067e-04 and 0.40 shifts
  >   it **further** (4.424e-04). A silently-skipped merger reads delta == noise == 0, so that
  >   monotone pair is what rules it out. Also green: autocast fwd+bwd finite (loss 2.4325, the
  >   T4's actual path), scores still `(B, N, 1)` and grad-requiring pre-merge so the saliency
  >   BCE survives, cell 11 building from `TRAIN_MERGE_RATIO` rather than a literal `0.0` while
  >   the eval branch stays at 0.0, and the shipped cell-2 config read back as run 14's
  >   one-variable change. **Two gates, not one** — and the second is the one that matters here.

  **(g) Three fixes shipped into the notebook the same day, and one claim converted from prose
  into an artifact.** All four are the same underlying complaint: *a statement in this project
  was outrunning the thing that was supposed to back it.*

  1. **(d)'s verdict fix, applied symmetrically.** The aggregate now needs **≥2 resolved pairs
     in the leading direction AND ≤1 underpowered pair** before it prints a verdict; short of
     that it prints `LEANS TOWARD` / `LEANS AGAINST` and names the shortfall. Applied to
     **both** directions deliberately — qualifying only the direction that had contradicted my
     prediction would have been a worse bias than not qualifying at all.
  2. **A checkpoint-identity assert in cell 2, because run 12's failure was caught only
     post-mortem.** The provenance stamp tells you which weights you measured *after* you have
     spent the GPU time; run 14 is a 5–6 h run, so the question is now asked before the run.
     The guard's reach is stated in the code rather than assumed: `1045901275` = run 5,
     `1045901771` = **every** pruning-era checkpoint, and runs 7/8/9/10/11 are byte-identical
     in length so **size cannot tell them apart**. It therefore rejects the exact confusion
     that happened and nothing finer.
  3. **…and that assert is not decorative, which took two verifier rows, not one.**
     `verify_attn_train_step.py` now feeds it run 9's real checkpoint and requires a **raise**
     under `DO_TRAIN + TRAIN_MERGE_RATIO>0`, *and* requires the **same file to be accepted**
     when merging is off (runs 12/13's sweep-only config is legitimately built on those
     weights). Without the second row the guard could be rejecting run 9 for an unrelated
     reason, or rejecting it always, and both would still print PASS. A startup check also
     asserts the two checkpoints exist **and differ in size** — otherwise a missing file would
     silently turn both rows into a test of the not-found branch. Gate table 9 → 11 scenarios;
     **13/13 fast**.
  4. **M1 extended to the merge stage, retiring an arithmetic claim.** "2.5× KV at M=1920 at no
     measured cost" was **cited to M1 by name three times, twice with `kv_memory_local.json`
     beside it, while that JSON held only prune-only rows** (six occurrences of the literal
     across five sections) — it was
     4800/1920 done in prose, married to an accuracy number from a different file. Both halves
     were right, which is the hazard: right-by-luck and right-by-measurement read identically.
     `eval_kv_memory.py` now measures four merge rows (M=3840/1920/1440/1344), re-derives the
     accuracy pairing from run 13's per-image arrays at runtime, and asserts **in both
     directions** that "free" has teeth. **52/52 controls**, `results/kv_memory_merge.log`.
     *(The "four times" first written here and in the M1 section was itself an uncounted
     guess, corrected the same day by grepping the literal — see (g)6.)*
  5. **The Q6 `MIXED` branch was reviewed and deliberately left alone.** It prints no verdict
     word — it names the split and tells the reader to compare the ink pairs against the router
     pairs — and the new `NOTE:` block fires *ahead* of it whenever the table is underpowered,
     because that block keys on `(_wins or _loss) and not _decisive`, which `MIXED` satisfies.
     Adding a decisiveness qualifier to a branch that makes no claim would be the decorative
     version of the fix. Recorded so the next reader does not re-open it.
  6. **The "four times" in (g)4 was itself an uncounted number — and it was wrong.** Having just
     written the rule *"grep the literal, not the topic"*, I applied it to my own new prose and
     found **14 lines** carrying `2.5×`/`2.50×` in this file, nine of them written the same day
     by me. Stripping mine leaves **six occurrences on five lines** across five sections, of
     which **three cite M1 by name** and two name `kv_memory_local.json` outright. So the
     defect was both narrower and sharper than "appeared four times": not repetition, but a
     *named citation to a file that did not contain the row*. Both the M1 section and (g)4 now
     say that instead. The general form: **a count you did not run a command to get is a
     guess, including when you are writing about the hazard of guessed counts.**
  7. **"`BipartiteTokenMerger` has never executed" was still live in eleven places**, two days
     after run 12 and one after run 13. Found by the same method as (g)6, immediately after
     writing it down: grep the literal string, not the topic. The distribution is the lesson —
     I had already corrected this claim where each file *argues* about the merger (README's
     "before quoting a number" block, REPORT's stale banner, AGENTS' claim 3) and left it
     standing in every place each file *summarises*: README's **Architecture notes** ("Implemented,
     never exercised") and **What's open**; REPORT's **scoping facts**, **live weaknesses** and
     **where it stands**; AGENTS' own architecture note and its open-items recommendation, whose
     "BUILT AND GATED, NOT YET MEASURED (2026-09-16)" annotation had itself gone stale; and all
     four sites in `WRITEUP.md`, which had no correction banner at all and whose §5 still called
     the sweep "blocked on an ordering fix rather than on GPU time". All eleven corrected in place
     with the claim struck rather than deleted, because the *reason* it was wrong differs by site
     and is worth keeping: in AGENTS it was wrong twice over, first as false-of-the-repo (the
     inherited `merge_ratio=0.20` default) and then as false-of-the-run-log. `WRITEUP.md` also
     gained a dated correction banner and now carries the standing limitation — merging is
     measured **off-distribution**, so run 13's 40% cost cannot yet be separated from H1.
     The breakdown, from the grep rather than from memory: **4 in `WRITEUP.md`, 3 in `REPORT.md`,
     2 in `README.md`, 2 in `AGENTS.md`.** And for the third time in one session I first typed an
     uncounted figure here ("nine"), then counted, then corrected it — which is (g)6's rule
     earning its place: **the count is the last thing to write, after the command that produces it.**
  8. **`check_writeup_numbers.py` caught (g)7 mid-edit, and had a structural blind spot.**
     Renaming `WRITEUP.md` §5's heading from "No merging result" to "The merging result is
     off-distribution" **failed** the script's disclaimer-presence check — the paired non-vacuity
     guard for its banned-phrase list, whose whole point is that banning affirmative phrasings is
     worthless if the section can be deleted and still score green. It did exactly its job: it
     refused to let a rename silently remove a scope disclaimer. The needle is **re-pointed at the
     new scope limit** (merging measured off-distribution) rather than deleted, because the
     writeup still owes the reader a merging caveat — just a different one.
     Then the blind spot: section 6 compares figures against `AGENTS.md`, but folded U+2212 to
     ASCII in the *writeup* only and read `AGENTS.md` raw, so **any signed figure was structurally
     unable to match** and would report "NOT IN AGENTS.md" on a number plainly there. Every figure
     in that list was unsigned — the list had been quietly restricted to what the comparison could
     handle, a *limit of the tool* mistaken for a *choice about what to verify*. Both sides are now
     normalised, and run 13's eight merge figures are covered (`-3.86`, `-7.45`, `49.2%`, `50.5%`,
     and the four sabotage-row values) — the numbers that replaced "token merging has never
     executed", i.e. the ones a reader will actually quote. **142/142, exit 0.** Non-vacuity is
     not inferred: a probe figure present in `AGENTS.md` and deliberately absent from the writeup
     was added, the script went to **142 passed / 1 failed, exit 1** with the correct diagnosis
     ("MISSING FROM THE WRITEUP"), and the probe's removal was verified by re-running to
     142/142 **and** grepping the probe string back to zero occurrences.

  And a miss worth recording, since it is the exact failure this file has a section about:
  **I typed "38 controls" into the M1 extension from memory before counting, and the real
  figure is 52.** That is the same shape as the "17 of 17" that survived three copies before
  the 2026-09-09 audit. The durable fix is not care, it is a counter: `eval_kv_memory.py` had
  only `controls_passed: true` — a boolean AND, equally true of 52 passing and of 1 passing
  with 51 skipped — and now writes `controls_run` / `controls_failed`, cross-checked against
  an independent `grep -c '\[PASS\]'` over its own log.

  **Two more things that grep found, both of the same shape — a number corrected in the places
  that discuss it and left standing in the places that summarise it.**

  - **`17/17` was still in `THE FOUR CLAIMS THIS PROJECT CAN MAKE`**, nine days after the
    2026-09-09 audit recorded fixing it "in three places". The audit searched the sections that
    *discuss* M1 and missed the block at the top of the file — the one most likely to be quoted
    by someone who reads no further. Corrected to 25/25. **Rule: when correcting a number, grep
    for the number, not for the topic.**
  - **The m=0.40 result is filed with three different bootstrap CIs** — [−7.54, −0.35],
    [−7.47, −0.38] and [−7.45, −0.30] — two of which were written on 2026-09-18 with no note
    that the endpoints are draw-dependent. All three agree to ±0.05, all exclude zero, and all
    satisfy run 14's `res ≤ 3.6` criterion, so nothing downstream turns on the difference; the
    defect is leaving a reader to find a three-way discrepancy in a headline number unexplained.
    A comparison table and a pointer at each site now exist. **Rule: when a CI endpoint lands
    within its own resampling noise of zero, quote the seed with it or quote the rank test
    (Wilcoxon p = 0.0048), which does not move with the draw.**

- **2026-09-17 — `STORY.md`: the project told chronologically, for a reader with no ML
  background.** User request, made while a parallel session was analysing run 12: *"make the
  report describing our work from in every stage and why we did that. Like we started with x
  in mind then we had y problem and to fix it we implemented z solution ... so that everyone
  can understand it."* Every existing document is organised by **result** — `WRITEUP.md` by
  claim, `REPORT.md` by claim plus a run table, this file by topic. None of them answers "how
  did the project get here", and that ordering is the thing a newcomer needs, because most of
  what happened is causal: run 4's negative result is why run 5 unfroze the encoder, D1's
  inverted router is why run 7 exists, D6 is why run 10 changed target, D11's binding-budget
  argument is why run 10's null was structurally guaranteed.

  Sixteen chapters: chapter 0 builds the vocabulary from nothing (4800 tokens, encoder/decoder,
  keep ratio) and states the five facts that constrain every later claim; chapters 1–15 walk
  runs 2–12 with D1–D12, M1, F1–F3 and the ToMe parity fix folded in at the point where each
  was *provoked*, each in the requested three-part shape. Closes with the four standing claims,
  a what-died-and-what-killed-it table, the open items, eight transferable lessons lifted from
  Gotchas/Conventions, and a glossary that defines `t`, SE, "paired" and "underpowered" —
  because a general reader cannot otherwise tell a **measured** null (run 9's −0.26, t −0.18)
  from an **unmeasured** one, and that distinction carries claim 1.

  **Three deliberate constraints on it, all of which are maintenance burden:**
  - **No numeric audit.** `check_writeup_numbers.py` re-derives `WRITEUP.md` from
    `results/*.json`; `STORY.md` has no equivalent, so its figures were transcribed from this
    file and **go stale silently** when one is corrected here. Registered as such at the top
    and in the file map rather than left implicit. Writing an audit for it is not queued — the
    cheaper contract is: fix a number here, grep `STORY.md` for it.
  - **Run 12 is reported as in-flight and is not adjudicated.** The chapter states the printed
    merge verdicts *and* the provenance observation — the run's stamp names run 5's checkpoint,
    `metrics.json` reads `77.73756569694308` (the run-5 harness-control value to all 14 digits),
    and the router rows reproduce the D1 inversion (router 24.97 / random 59.06 / ink 73.69) —
    then says explicitly that the conclusion belongs to the session that owns the run. A
    narrative document is exactly where an unvetted number would get laundered into a fact.
  - **Costs are stated next to fixes.** The checkerboard chapter carries "diagonal redundancy
    now 100% missed" in the same breath as "vertical 100% → 0.0%", the KV chapter carries its
    `scope_limit`, and claim 2 carries the "do not cite beats-the-ink-oracle" caveat. The
    failure mode for a stage-by-stage story is that it reads as a march of successes; the
    corrective is that **five of the sixteen chapters end in something not working**, and they
    are labelled that way.

  **What writing it turned up: `check_writeup_numbers.py`'s six corrections were applied to
  `WRITEUP.md` and to this file, and never propagated to `REPORT.md`.** Drafting `STORY.md`
  off `REPORT.md` reproduced two of them verbatim before a spot-check against this file caught
  them — which is the audit working one hop downstream of where it was aimed. Fixed in place in
  `REPORT.md` on 2026-09-17, each marked with what it previously said:
  - **the router-vs-ink double sign inversion** — it read `−2.24 pts for +0.072 MORE ink
    (t −1.62)`; correct is **+2.24 (80.46 vs 78.22) for 0.072 LESS ink, t +1.62**, still under
    the pre-registered t ≥ 2.0 and so still not citable as "beats the ink oracle";
  - **M1's control count** — `17/17` → **25/25**;
  - **retrain drift** — `≈1 pt` → **1.09 / 1.30 / 10.93**, the average having been taken over a
    set containing the 10.93.

  `REPORT.md` also now carries a **stale-as-of banner**, because three of its statements are
  wrong post-run-11/12 and were deliberately left uncorrected: "H1 is supported, not isolated"
  and Pending 14 open (**run 11 isolated it**), "ToMe has never executed" and Pending 15 open
  (**the checkerboard landed and run 12 swept it**), and a run table that stops at run 10.
  Reconciling those belongs with the run-12 analysis and would have collided with the session
  that owns it, so it is filed rather than done.

  **The generalisable point, and the reason this is in the changelog rather than a commit
  message:** an audit that re-derives one document from `results/*.json` protects *that*
  document. It does nothing for the three prose files that copied from it before the fix, and
  a wrong number in a derived doc is *more* dangerous than in an audited one precisely because
  nothing is watching it. Four prose documents now exist and only one is audited; when
  correcting a figure here, grep the other three for the old value. Closest existing gotcha:
  [[green-checks-need-the-same-suspicion]] — "a green count is scoped to whatever the sweep
  globbed", of which this is the prose-document case.

- **2026-09-16 (later) — `DO_TRAIN` now ships False, and the flip carries its own guard.**
  Prompted by a fair question from the user: the run-12 checklist listed "set
  `DO_TRAIN = False`" as a manual cell-2 edit, and there was no reason a *generated* notebook
  should ask a human to remember a constant. A hand-edit that has to be remembered is one
  that gets missed, and missing this one spends five hours retraining and moves the
  checkpoint out from under the token-matched pairs — the pairing is the whole design.

  The flip is in the generator's PATCH A (`DO_TRAIN = False`), so it is regenerated, not
  hand-applied. **But flipping a default creates the mirror failure**, and that is the part
  worth recording: with `DO_TRAIN=False` and `RESUME_CKPT=None`, cell 11's else branch loads
  nothing (`if RESUME_CKPT:` is its only load), so "Run All" on an unedited notebook would
  sweep **donut-base with a randomly initialised router** and still print 28 rows, a full
  Q1–Q6 verdict block and a results JSON — with nothing in the output saying the weights were
  never trained. Before the flip that state was unreachable by inaction; after it, it *is*
  inaction. So `assert DO_TRAIN or RESUME_CKPT` ships beside the flip, and
  `verify_attn_train_step.py`'s gate table drives **both** directions (**6/6 → 8/8**): run
  12's config must pass, and sweep-with-no-checkpoint must raise. A guard only tested against
  states it rejects is half-tested.

  That verifier's four existing scenarios **inherited** `DO_TRAIN` from the shipped literal
  rather than naming it, which worked only while the literal was True — the same D5 shape
  (a knob that shapes a result while appearing nowhere in its own log) that this file keeps
  re-learning. All six scenarios now set it explicitly.

  `RESUME_CKPT` stays the one genuine manual step, and that is not an oversight: the path
  does not exist until the dataset is uploaded, and **two** verifiers
  (`verify_harness_control.py:242`, `verify_phase2c_fixes.py:37`) assert cell 2 ships
  `RESUME_CKPT = None`. Suite re-run green after the change: generator A–G, merge-port
  **85/0**, selection ablation exit 0, harness control **39/39**, parity 10/10, unittest 16
  OK, pipeline tests pass.

- **2026-09-16 — the merge stage is BUILT, GATED AND PRE-REGISTERED; the whole architecture
  now executes together, and three quiet contaminations were found on the way in.** Full
  section: "Run 12 — launch checklist". Nothing has been *measured* yet — this entry is about
  code and controls, not results.

  **The checkerboard fix reached the notebook that produces every run.** `src/tome.py`'s
  `checkerboard_color` + `BipartiteTokenMerger` are now **spliced from disk** into
  `kaggle_pruning_run.ipynb` cell 4 by `make_kaggle_pruning_notebook.py` PATCH E (176 lines),
  with PATCH F rewiring both merger call sites to pass `orig_idx=topk_indices` and a
  `_token_grid()`-derived grid, and PATCH G adding 13 rows. Splicing rather than retyping is
  the point: the generator is already the *third* copy of the model, and a hand-typed merger
  would have made it a fourth. The asserts anchor on the **old, broken** `arange(0, K, 2)`
  lines, so an independent fix to the canonical notebook fails the generator loudly instead
  of double-applying.

  **The sabotage arm costs zero merger code.** `tome_split='rank_parity'` passes
  `orig_idx=arange(K)` with `token_grid=(K, 1)`; since `((i // 1) + (i % 1)) % 2 == i % 2`
  that reproduces the deleted parity split **exactly**, so `src/tome.py` stays unmodified (it
  deliberately raises rather than falling back) and the negative control is a call-site
  argument. Verified by execution, not argued: it matches the pre-fix merger **bit-for-bit**
  at B ∈ {1,2} × three configs, with the old merger *extracted from the canonical notebook at
  runtime* rather than hand-copied — a local copy could drift into agreeing with the new
  implementation and go green for the wrong reason.

  **`scripts/verify_tome_merge_port.py` — 85 checks, exit 0**, and every equality check is
  paired with a non-vacuity check, because code spliced from `src/` and compared against
  `src/` passes no matter what: checkerboard vs rank_parity must *disagree* (max \|diff\|
  ≈ 5.6), merging must compact rather than pass through, the token-match assert is fed a
  deliberately mismatched pair and required to raise, and the fix's targeted quantity is
  re-measured **on the shipped notebook code against its own null** — missed
  horizontal/vertical redundancy **49.7% / 46.5% → 0.0% / 0.0%**. All 13 new rows' token
  arithmetic is checked against `model.last_enc_len`, i.e. what the decoder actually received,
  not just what the meta dict claimed.

  **Run 11's power lesson applied to the new cell, immediately.** The Q6 verdict originally
  printed "indistinguishable (<3 pts is invisible at n=50)" — prose asserting a resolution it
  never measured, which is the same shape of error the 2026-09-15 audit caught. Now every
  pair prints its **own** CI half-width and a flat row whose resolution exceeds the 3.0 pt bar
  reads **UNDERPOWERED, not a null**; the verifier checks that the flag is derived from the CI
  rather than pasted on. The checklist states a **predicted** resolution of 2.5–4.5 pts —
  derived from run 11's own per-image spreads (sd 9.28–18.22 ⇒ res 2.6–5.2) — and says out
  loud which verdict that most likely blocks: `INDISTINGUISHABLE`, the one that would be good
  news for the architecture.

  **Three contaminations found by tracing the default instead of the log.**
  `AdaptiveDonutOCR`'s `merge_ratio` default was **0.20**, and twelve callers never passed it.
  So `results/nrns_rp_sweep.json` — the local file behind the "+4.74 pts" decoding figure —
  and every pre-2026-09-16 `determinism_probe_*.json` were produced with **merging on, through
  the broken split**, while being read as merge-free. The default is now `0.0`, both scripts
  name it explicitly, and the meta reads `model.merge_ratio` off the object so the line cannot
  drift from what ran. The *adopted* decoding defaults are clean (cell 14 builds at 0.0).
  Corollary: this file's claim that the merger **"has never executed"** was false of the repo
  and true only of the recorded runs — corrected at the top. All three are now gotchas.

  **Also recorded as gotchas:** the canonical notebook must never be run with
  `merge_ratio > 0`; merged `final_coords` are dead code on both paths (bound at
  `src/model.py:248`, never read); `tests/test_model_pipeline.py` collects **zero** tests
  under `unittest discover` and must be run directly; and `src/tome.py`'s per-image loop
  differs from a batched `bmm` by ~2e-07 at B=2, which is why the verifier matches the
  computation shape instead of widening a tolerance over the effect under test.

  Full suite green: generator all patches assert-pass and every code cell parses;
  `verify_tome_merge_port.py` 85/85; `verify_selection_ablation.py` exit 0 (the 15 published
  rows and Q1–Q5 unchanged — `SELECTION_CONFIGS` was appended to, never retyped);
  `diagnose_tome_parity.py` 10/10; `unittest discover tests` 16 OK; `test_model_pipeline.py`
  direct run passes.

- **2026-09-15 (second session, same day — power audit of run 11's verdict, plus the harness
  that computes it) — the verdict stands, and the run's real limitation is that its *other*
  verdict was never reachable.** Full sections: "The acceptance table is asymmetric at n=50"
  and "The analysis harness that produced it", both under "Run 11 — result".

  **Reproduced the headline ISO table independently** from the `per_image` arrays, separate
  code path, image ids asserted aligned and the DiD identity re-asserted to 1e-9 — agrees to
  the last printed digit. **Then decomposed its variance:** `ISO` is paired, so
  `Var = s_f² + s_r² − 2ρ s_f s_r`, and the per-image ρ between the two delta columns is
  **0.03 / 0.00 / 0.08** (keep 0.75 / 0.50 / 0.35, descending as elsewhere in this file).
  Clearing `resolution ≤ 3.0` would need ρ of **0.52 / 0.62 / 0.90**,
  or **100 / 130 / 175** images at the observed spread. FUNSD test **is** 50 images, so
  **`CONFOUNDED` was unreachable before a single image was decoded** — the acceptance table's
  two arms are not symmetric at this n. The rejection of `CONFOUNDED` is untouched by this (it
  needs one row to break the bound, and keep=0.35 does so at `|t| = 3.74`), but a flat ISO row
  in this design means "choose nothing" and can never mean "confound". **The transferable
  lesson: D12's own artifact already carried ISO SEs of 2.45–2.98, i.e. resolution 4.9–6.0
  against `MIN_EFFECT_PTS = 3.0`** — the pre-registration set a bar and never checked whether
  it could be cleared. Pre-register a *predicted* resolution next to every threshold.

  **The two local invocations survive this and are running** — D12's local pair reaches
  ρ 0.14–0.57 and clears `|t| ≥ 2` at keep=0.20 and 0.35, the tight budgets the Kaggle grid
  lacks. Underpowered *loose* budgets are a property of the budget, not of the statistic.

  **`scripts/eval_why_pruning_helps.py` gained `--pair` over three checkpoints, the ISO
  statistic with a hard `1e-9` identity assertion, and `decide_iso()` with `UNDERPOWERED` as
  the default branch.** Four defects fixed on the way in, one of which was load-bearing: the
  harness anchor read `RESULTS[B]` assuming slot B is always run 9, so the pre-registered
  `[run 5, run 11]` invocation would have measured run 11 against run 9's anchor and failed the
  entire sheet — **a control firing on the wrong thing**, caught before it cost 2.2 h
  ([[controls-decay-silently]]). Also: `decide()`'s hardcoded "Run 5" prose was writing a false
  sentence about run 11 into a saved artifact, now suppressed rather than relabelled, since H2
  is a claim about a checkpoint never trained with pruning.

  **Two Gotchas filed**, both instances of a log field that is true of a narrower scope than it
  appears: cell 2's `EVAL_ONLY = bool(RESUME_CKPT)` makes every resume run announce
  `training skipped` two lines above `PLAN: DO_TRAIN=True` (the guard is correct; only the
  print is unguarded), and the training header's `positive rate 0.420` is **one batch** while
  the epoch line's `ch 0.289` is the epoch mean of the same quantity — the checklist's
  pre-run reproduction of 0.283 matched `ch`, not the header.

- **2026-09-15 (run 11 filed and analysed) — Pending 14 is CLOSED: H1 is isolated at
  keep=0.35, and the verdict came out of artifacts that had been sitting in the results zip
  since run 9.** Full section: "Run 11 — result".

  **The run itself is clean on every pre-registered watch-row**, including the two written
  to look green when broken: `ov 1.000 / lift +0.711` is Trap 2 firing exactly as the
  reproduction predicted (+0.717) and means nothing, and `SUPERVISE_SALIENCY` stayed `True`
  so Trap 1 was avoided. Provenance names run 11's own checkpoint with `size_bytes` matching
  the shipped `.pt` byte for byte. "One variable" is verified **by diffing the executed
  notebooks**, run 10's method: run 10 → run 11 removes exactly `TRAIN_KEEP_RATIO = 0.50`
  and `ATTN_TARGET = True`, every added line is provenance, comment or `print`, and against
  run 9 the ink-target lines are unchanged and merely indented into an `else:` branch of a
  dead `if ATTN_TARGET:`.

  **The analysis did not need the GPU-free 110-minute local runs the checklist scheduled.**
  `ablation_selection.json` has stored `per_image` recall on all 15 rows since run 9, so runs
  9 and 11 are paired on the same 50 images at the same venue in the same cell.
  `ISO(0.35) = −10.49` (t −3.74), `CONFOUNDED` rejected by 3.5×, both controls passing by
  execution (`0.00e+00` retained-ink identity on weight-independent modes; DiD arithmetic
  asserted to 1e-9). **The lesson worth keeping: the checklist specified a 220-minute
  analysis path without checking whether the shipped artifacts already contained the
  statistic.** Before scheduling a measurement, grep the existing JSON for a per-image array.

  **Two things were deliberately not over-read.** keep=0.75 and 0.50 are **underpowered
  (resolution 4.2 / 4.8), not null** — the pre-registration's own rule, applied to rows that
  would otherwise have looked like supporting evidence. And this is the **Kaggle** venue
  while the pre-registration was written for local CPU; the Kaggle grid has no keep=0.25 or
  0.20, the two budgets where the effect was predicted to be largest. So the local
  invocations remain worth running, and Claim 1 now says "isolated at keep=0.35", not
  "proven".

  **A decorative verdict found in passing.** Cell 15 prints `DIFFERENT CEILING — this
  1.90 pt gap is what the retrain did to unpruned accuracy, not measurement noise`. The 1.90
  is `max|drift|` across three metrics and comes from **word order**, not recall; recall
  drifted 0.51, and the paired test puts it at +0.52 with **t = 0.24**. No SE is computed
  anywhere in that block. `meta.control_drift_pts` carries the same quantity and the same
  caveat. Same species as `decide()`'s prose — [[green-checks-need-the-same-suspicion]].

- **2026-09-14 (session-gap audit) — the 2026-09-09 session stopped without writing its last
  80 minutes to this file, and two of the things it left behind were a broken test pair and a
  decorative diagnostic.** Run 11 was launched at the top of this session and is on Kaggle now;
  everything below is local work done while it trains.

  **What was missing.** This file's last write was 19:33 on 2026-09-09. `src/tome.py` (19:40),
  `src/model.py` (19:46), `tests/test_tome_correctness.py` (19:47), `scripts/diagnose_tome_parity.py`
  (19:54) and `results/nrns_rp_sweep.json` (**20:50**) are all later, and the string
  `nrns_rp_sweep` appeared **zero** times in this file. So Pending 15's option (b) was
  implemented and Pending 3's sweep was run twice, and neither was recorded.

  **Pending 15 option (b) is DONE and it works.** `checkerboard_color()` in `src/tome.py` splits
  on `(row + col) % 2` of the ORIGINAL raster index, `src/model.py` derives the grid from
  `pixel_values` at both call sites (`:241-246` forward, `:365-370` generate) via `_token_grid`,
  and the merger now *raises* rather than falling back to the old parity split when `orig_idx`
  is absent. Re-verified this session by execution: `tests/test_tome_correctness.py` **13/13**,
  `scripts/diagnose_tome_parity.py` **10/10**. The vertical-redundancy hole is closed —
  **100% → 0.0% missed**, and it holds under the router's score-sort, which was the whole point.
  Newly-accepted cost, stated because it is real: **diagonal redundancy is now 100% missed**
  (inherent to a checkerboard — diagonal neighbours share a colour). Horizontal and vertical
  were the document-relevant cases; diagonal is the price.

  **Two stale callers had been left failing, and they are the reason "19/19" was no longer true.**
  The new `ValueError` is correct, but two older callers never learned about it:
  `tests/test_modules.py::test_tome_merger` and `tests/test_model_pipeline.py` both called the
  merger with `merge_ratio=0.20` and no `orig_idx`. Both now pass. Two notes on the fixtures,
  because both are the kind of thing that passes for the wrong reason:
  - `test_modules.py` uses a 30×40 grid over its N=1200 and a **shuffled** `orig_idx`, not a
    raster one. A raster fixture would have hidden the exact order-dependence the checkerboard
    exists to remove — this file already records one fixture that "could only exhibit the
    favourable case", and that was avoidable by construction.
  - `test_model_pipeline.py`'s `MiniAdaptiveOCR` uses a **ViT** encoder, which emits a CLS token;
    the real model uses Swin, which does not. Its forward now drops CLS so `gh*gw` equals the
    token count, and asserts it. Keeping CLS would have made the grid width off by one token —
    and per `_token_grid`'s own docstring, a wrong width is silent: **any** width still yields a
    valid two-colour partition, just one that no longer tracks spatial adjacency.

  **`scripts/diagnose_tome_parity.py` was decorative, and only a sabotage run said so.** It
  defined its **own** `checkerboard_color` at `:102-104` instead of importing `src.tome`'s. So
  it validated a *restatement* of the algorithm. Corrupting `src/tome.py`'s real function to
  column-only parity (`(orig_idx % grid_w) % 2`, which by construction strands 100% of vertical
  redundancy) left the diagnostic printing **10/10 PASS and "Safe to queue the merge sweep"**.
  It now imports the shipped function; re-tested under the same sabotage it reports **3 FAILs
  and exits 1**, and clean it is back to 10/10. `parity_color` stays local **on purpose** — it
  models the deleted split, so it is a guard that this harness can still detect breakage.
  Same species as the rule that `check_writeup_numbers.py` does not read `AGENTS.md`: prose
  checked against prose proves nothing, and an algorithm checked against its own restatement
  proves nothing either. See [[green-checks-need-the-same-suspicion]].

  **What the sabotage also showed, in the other direction:** `tests/test_tome_correctness.py`
  **does** catch it (3 failures), so the correctness guard is real. And
  `test_modules.py::test_tome_merger` passes under sabotage — correctly, because it is a
  **shape** test and shape is invariant to *which* tokens merge. That is fine as long as nobody
  reads it as a correctness check; it is recorded here so nobody does.

  **`scripts/check_writeup_numbers.py` crashed on a default Windows console.** It prints `≥`
  and cp1252 cannot encode it, so without `PYTHONIOENCODING=utf-8` it died with
  `UnicodeEncodeError` and **exit code 1 — identical to a real numeric failure** — after roughly
  50 of 134 checks, leaving 84 unrun. The docstring documented the env-var workaround, which is
  a checker whose correct invocation is easy to forget. It now calls
  `sys.stdout.reconfigure(encoding="utf-8")` itself. Verified both ways: clean run is **134/134,
  exit 0** with no env var, and a one-digit edit to a figure *after* the old crash point still
  gives **133/1, exit 1**.

- **2026-09-14 (Pending 3 — the nrns/rp sweep RAN on 2026-09-09 and its headline is NOT
  adoptable as it stands).** `results/nrns_rp_sweep.json` reports **rp=1.05 / nrns=6 at +4.74 pts**
  recall over the current default, paired-bootstrap 95% CI **[+1.49, +8.11]**, and the script
  printed "at least one config separates from the default". Four reasons that is not yet a
  result, three of which are the script's own instruments disagreeing with its headline:

  | check | reading |
  |---|---|
  | the script's own monotonicity test | **fires on both rp rows.** rp=1.0: 76.65 / 78.37 / 78.29; rp=1.05: 79.88 / 79.26 / 81.38. It was written to flag exactly this as "what noise looks like" |
  | the script's own `resolution_pts` | **4.05 pts.** It states effects under ~4 pts are invisible at n=50. The second "significant" row (rp=1.05/nrns=3, +3.24) is **below its own floor** |
  | multiple comparisons | **5 configs against one control, uncorrected.** Family-wise error 1 − 0.95⁵ = **0.226**. Under Holm: only rp=1.05/nrns=6 survives (raw p 0.0044 < 0.0100); rp=1.05/nrns=3 does not (p 0.0454 vs α 0.0125) |
  | charAcc, the anti-cherry-pick column | **disagrees across the two files.** The winning row reads **+2.06** charAcc vs its control in one and **−2.33** in the other. A recall-only win is not a win |

  **A second file, `results/nrns_rp_sweep_aggregates_run2.json`, cannot be reconciled with it.**
  Same checkpoint, same six configs, and the **identical CONTROL row differs by 2.73 pts**
  (79.37 vs 76.645). That matters because the deltas invert: rp=1.0/nrns=4 is **−3.19** against
  its own control in one file and **+1.73** in the other. The two files have different meta
  schemas (run2 has no `per_image`, no `resolution_pts`, no `keep_ratio`), so they came from
  different script versions and are **not** a clean replication — and run2 stored no per-image
  rows, so the gap cannot be diagnosed from the artifacts.

  **The determinism assumption underneath every CI was unverified, so it was tested.**
  `run_nrns_rp_sweep.py:263` asserts "generation is greedy, so re-running a config is
  bit-identical", and that sentence is the *entire* justification for bootstrapping over
  documents only. New `scripts/probe_generation_determinism.py` checks it by execution, mirroring
  the sweep's exact conditions and **deliberately not seeding** (the sweep did not seed either;
  seeding here would mask the effect under test — a green check that cannot fail).
  **Result: bit-identical, 6/6 images within-process and 6/6 across two separate processes.**
  So the claim holds and the document-only bootstrap is the right uncertainty model — which
  *narrows* the mystery rather than solving it: the 2.73 pt gap must be a **code difference
  between the two script versions**, not run-to-run noise.

  **Most likely cause, and it is now prevented.** The script wrote its fixed `OUT` path
  unconditionally, so any re-run silently overwrote the filed result and its script version was
  lost. `SWEEP_ONLY` (row filter, always forces the CONTROL row in — otherwise `ctrl` silently
  becomes whichever row sorted first) and `SWEEP_OUT` (destination) now make replication possible
  without clobbering. Defaults unchanged, so a bare invocation behaves exactly as before.

  **Status: the replication landed, and it is decisive.** Re-running the CONTROL row under the
  *current* script reproduces `results/nrns_rp_sweep.json` **exactly** — recall 76.6452,
  charAcc 62.9868, order 50.7516, NED 0.3701, gen-tokens 257.46, valid-JSON 84.0, and **all 50
  per-image recall values identical**. Combined with the determinism probe, that settles
  provenance: **`nrns_rp_sweep.json` is the live file and `nrns_rp_sweep_aggregates_run2.json`
  is a superseded artifact from a script version that no longer exists.** Its 79.37 control was
  produced by different code, so its rows must not be quoted or averaged with the current ones;
  it is left on disk rather than deleted, because deleting the only evidence of a discrepancy is
  how the discrepancy comes back. Saved as `results/nrns_rp_sweep_replication.json`.

  **What that does and does not buy.** It removes the *provenance* objection to the +4.74 pt
  headline — that number is real and reproducible. It removes none of the other three:
  the monotonicity test still fires on both rp rows, rp=1.05/nrns=3 still sits under the
  script's own 4.05 pt resolution floor, and the 5 comparisons are still uncorrected (only
  rp=1.05/nrns=6 survives Holm). The charAcc contradiction **is** resolved by the provenance
  finding — the −2.33 came from the dead file; the live file reads **+2.06**, so the winning
  row improves recall *and* charAcc rather than trading one for the other.

  **So Pending 3's honest status is: rp=1.05/nrns=6 is the one config with a real,
  multiplicity-surviving, charAcc-corroborated effect (+4.74 pts recall, +2.06 charAcc, Holm
  p 0.0044), on run-5 weights at keep_ratio=1.0, at n=50.** The remaining caution is the
  non-monotonicity, which is the script's own noise signature firing on a grid where the
  adopted point is a corner rather than part of a trend. **Recommendation: do not change the
  default off this.** Re-measure the two rp=1.05 rows on the run-11 checkpoint once it lands —
  a decoding default should be set on the weights it will ship with, not on a superseded
  baseline, and that costs ~76 min of CPU rather than a GPU session.

  **This must not touch run 11.** `kaggle_pruning_run.ipynb` bakes `repetition_penalty=1.0` /
  `no_repeat_ngram_size=3` — run 9's decoding. Run 11's whole value is being byte-identical to
  run 9 apart from `TRAIN_KEEP_RATIO`, so changing decoding there would fold in a second
  variable and void the H1 isolation, whatever the sweep eventually concludes.

- **2026-09-09 (ToMe parity, second look) — Pending 15's option (b) was a half-fix, and the
  number that hid it was a fixture artifact.** Walking the pipeline step by step to explain
  where the ToMe blocker sits surfaced two things the existing write-up did not have.

  **1. The blocker is narrower and worse than "ToMe partitions by score-rank".** ToMe's
  similarity search is *global* (every A against every B, `src/tome.py:63`) and the coords it
  carries are **never used in the matching** — only averaged into centroids afterwards, and
  then **discarded**: `final_coords` at `src/model.py:214` is unused and `generate()` throws
  its copy away at `src/model.py:331`. So the A/B parity split is the **only** consumer of
  sequence order anywhere in the model, and decoder cross-attention is permutation-invariant.
  That is the precise reason ten runs never tripped over it: the router's permutation is inert
  everywhere *except* inside the component `merge_ratio=0.0` short-circuits.

  **2. `diagnose_tome_parity.py`'s "spatial ⇒ 0.0% missed" only covers horizontal
  redundancy.** Its `redundant_neighbour_pairs()` declares pairs `(0,1), (2,3), (4,5), …`,
  every one straddling an even/odd boundary by construction. The grid is **80 × 60** and
  **60 is even**, so token `i` and the token directly below it (`i+60`) share parity always.
  Re-running the script's own `merged_pairs()` with vertically-adjacent pairs:

  | ordering / redundancy type | missed |
  |---|---|
  | spatial, horizontal duplicates | 0.0% |
  | spatial, **vertical** duplicates | **100.0%** |

  On a document task, inter-line whitespace and multi-row strokes are exactly where the
  vertical redundancy is. **Option (b) as written would have been implemented, swept, and the
  flat rows read as "merging does not help this model."** Revised option (b) now also replaces
  the parity split with a checkerboard on `(row+col)%2`. This is
  [[green-checks-need-the-same-suspicion]] again, in the specific form *a control whose
  fixture can only exhibit the favourable case* — the 0.0% was not measured, it was
  constructed.

- **2026-09-09 (no new data) — the head-to-head "is the current model better than the
  previous one" table, derived from D12's existing JSON in seconds.** Asked in session and
  worth having written down, because every cross-checkpoint number in this file up to now is
  a *within*-checkpoint delta or a Kaggle row, and neither answers it directly.
  `results/why_pruning_helps_local.json` already stores `per_image_recall` (n=50) for **both**
  checkpoints at all five budgets under `select_mode="ink"`, so the run 9 − run 5 difference
  is **paired on identical images and identical token sets** and its SE is computable without
  a GPU:

  | keep | tok | run 5 | run 9 | Δ (run 9 − run 5) | SE | t |
  |---|---|---|---|---|---|---|
  | 1.00 | 4800 | 74.72 | 77.62 | +2.90 | 2.17 | +1.34 |
  | 0.50 | 2400 | 73.16 | 78.22 | **+5.07** | 2.22 | **+2.28** |
  | 0.35 | 1680 | 68.70 | 77.37 | **+8.67** | 1.87 | **+4.63** |
  | 0.25 | 1200 | 63.25 | 70.67 | **+7.42** | 2.47 | **+3.01** |
  | 0.20 | 960 | 54.39 | 64.61 | **+10.23** | 1.84 | **+5.56** |

  **Run 9 beats run 5 at every budget, and the margin grows as the budget tightens** — which
  is the same shape D12 reported, seen from the other axis. Three caveats, none of them new:
  the **keep=1.00 row is not significant** (t 1.34), so "the unpruned ceiling improved" is
  *not* supported by this table; the rows do **not** isolate pruning-aware training from five
  extra epochs (`meta.scope_limit` says so, and it is exactly what run 11 exists to fix); and
  these are **local** levels, which sit ~3 pts under Kaggle's for run 5 (the 3.02-vs-1.5
  cross-venue anchor that makes D12's `controls_passed: false`), so do not put them beside a
  run-table row. On Kaggle the same comparison at keep=1.00 points the *other* way — run 9
  reads **77.30** against run 6's **77.74** — which is the venue effect, not a contradiction,
  and is why the paired local table is the one to quote.

- **2026-09-09 (writeup audit + Run 11 prepared) — every figure in `WRITEUP.md` is now
  re-derived from JSON rather than transcribed, and the H1-isolation run is launch-ready.**

  **The writeup is the only document here with no execution behind it.** Everything else is
  checked by something: notebooks by the `verify_*` suite, results by their own controls,
  this file by `check_agents_md_format.py`. The writeup was checked by reading it — and this
  file already records one incident where "the write-up had kept the [stale numbers]". So
  `scripts/check_writeup_numbers.py` re-derives all of it from `results/*.json`: **134
  checks, 134 pass.** It deliberately does **not** read AGENTS.md for the numeric sections,
  because prose checked against prose proves nothing.

  **Six real errors, found by the checker, not by re-reading:**

  | § | was | is | how it was caught |
  |---|---|---|---|
  | 5 | the router "scores 2.24 pts **below** ink-oracle selection" | **above** — 80.46 vs 78.22, at **0.072 less** retained ink | recomputed from the per-image arrays instead of trusting the transcription. **A double sign inversion**: the direction was wrong *and* the ink comparison was wrong, which cancelled into a sentence that read plausibly |
  | 2 | `17 of 17 controls pass` | **25 of 25** | counted the `[PASS]` lines in `results/kv_memory_local.log`. `eval_kv_memory.py` has **no control counter** — `ok_all` is a boolean AND — so every "17" in this project was eyeballed once and copied three times |
  | 5 | a bare `93% of the teacher's` attention mass | **0.896** against the teacher's own ceiling of **0.910**, and labelled *reachability, not merit* — as it was before the run | the figure did not resolve to any value in any results file |
  | 5 | latency disclaimer quoted only the friendliest row | the max over D11's ten `router` rows is **1.05×**, and the largest speed-up **anywhere** in D11 is **1.19×** on a *random* row at keep=0.20 — quoted **because** it is the strongest measured evidence against the disclaimer it sits under | the checker asked for the max, not for a max |
  | 7 | retrain drift "≈1 pt per retrain" | **1.09 and 1.30 pts on two runs, 10.93 on a third**, and on runs 7–8 inseparable from a harness fault | the ≈1 was an average over a set containing a 10.93 |
  | 4 | D12's control status summarised away | **stated**: D12 records `controls_passed: false` and `WITHHELD`; the failing control is the cross-venue harness anchor (3.02 vs 1.5 tol), and the four the DiD actually rests on pass at `0.00e+00` | — |

  **The two checks that were decorative, and only a sabotage harness said so.** A 15-case
  harness corrupts one figure at a time and requires the checker to fail. Thirteen were
  caught; two were not, and both misses are the same species:
  - Section 6 asked `not in_doc or in_src`. Corrupting `0.896 → 0.936` **passed**, because
    once the searched string is gone the condition is vacuously true. A check that only fires
    when the correct value is already present tests nothing. Now `in_doc and in_src`.
  - `"under 5.20 pts"` → `"under 2.76 pts"` **passed**, because the JSON value had been
    verified but the document was never asserted to *quote* it. Now pinned by regex.

  A third, caught before the sabotage run: the banned-phrase regex `faster|speed-?up` fired
  on the writeup's own **disclaimer**. Narrowing it to affirmative constructions alone would
  have left a ban that passes trivially on a file containing no disclaimers at all, so the
  section now **also** asserts each disclaimer is present. This is
  [[green-checks-need-the-same-suspicion]] three times in one file.

  **The miscount propagated into this file too.** "17/17" was corrected in three places here
  — the `eval_kv_memory.py` verifier-index row, the Pending 8(c) closure note, and the
  2026-09-06 changelog entry — each against the log rather than against each other. Worth
  recording that the audit of the *downstream* document is what exposed the error in the
  *upstream* one.

  > **2026-09-18: there was a fourth, and it was the worst-placed one.** `THE FOUR CLAIMS
  > THIS PROJECT CAN MAKE` — the block at the top of this file, the one most likely to be
  > quoted without reading further — still said `17/17` nine days later. The audit searched
  > the places that *discuss* M1 and missed the place that *summarises* it. Transferable:
  > when correcting a number, grep for the number, not for the topic.

  **Run 11 prepared (Pending 14, not executed).** Full launch checklist added above Phase 2c:
  one variable (`TRAIN_KEEP_RATIO = 1.00`), everything else run 9 byte for byte, so run 9
  minus run 11 isolates pruning-aware training with epochs held constant — the arm D12
  explicitly lacked. Three things established by reading the generator rather than assuming:
  - `TRAIN_KEEP_RATIO` appears five times, but on run 9's branch **exactly one use is live**
    (the model constructor). `target_budget` is on the other loss branch; the two attention
    uses are behind `ATTN_TARGET`. And the ink target is **threshold**-based, so the
    supervision signal stays bit-identical to run 9's. It really is one variable.
  - **`SUPERVISE_SALIENCY` must stay `True`.** Flipping it does not remove an auxiliary; it
    swaps ink-BCE (`LAMBDA_SAL=0.5`) for `lambda_sparsity=2.0` + `lambda_entropy=0.05`. There
    is no "CE alone" path, and the intuitive reading of "train without pruning" would have
    made run 11 differ from run 9 in two ways.
  - **`ov` and `lift` degenerate at keep=1.00 and degenerate *green*.** K = N makes `_rk`
    all-ones, so `ov ≡ 1.000` and `lift = 1.000 − ch` from step 0. **Executed rather than
    reasoned**: a random router and a perfect one print the identical `ov 1.000 lift +0.717`,
    and +0.717 is *larger* than run 10's healthy +0.298 — the dead column looks better than
    the live one. Run 10's watch row "`lift` well above 0.000" would be satisfied by a router
    that learned nothing, and `verify_training_telemetry.py`'s case M goes dead the same way.
    The checklist says to watch `sal`, `dev` and `p ±std` instead. This is D1's STE trap
    surfacing in the telemetry rather than the gradient — and here it is not a bug, it is the
    definition of the control arm.

  **One claim in the first draft of that checklist was wrong, and the correction is the
  useful part.** I wrote that adding a third element to `eval_why_pruning_helps.py`'s `CKPTS`
  raises `ValueError`. It does not: line 360 is `A, B = CKPTS[0][0], CKPTS[1][0]`, which is
  *indexing*, not unpacking. A three-element list runs cleanly, sweeps the third checkpoint
  for ≈55 extra minutes, **records it in the JSON's `checkpoints` map**, and then silently
  omits it from every delta, DiD and control — an output that advertises a three-way
  comparison and contains a two-way one. I had asserted the exception from reading; one line
  of execution said otherwise. [[verify-patches-actually-run]], applied to a claim *about*
  code in a document rather than to code itself.

  **A third eyeballed count, found while checking run-11 readiness.** The
  `verify_harness_control.py` index row claimed "**36/36** on both notebooks". Actually
  measured: **36 on `kaggle_token_pruning_ocr.ipynb`, 39 on `kaggle_pruning_run.ipynb`.** The
  gap is not noise — the canonical notebook has no `DO_TRAIN` branch, so the generated one
  gets four extra checks covering *resume from `RESUME_CKPT`, don't starve cell 6 of training
  data, save `PRUNED_CKPT`, repoint `EVAL_CKPT`*. Those four are exactly what a
  retrain-then-sweep run stands on, so **the notebook that matters for runs 9/10/11 is the one
  with the higher count**, and "both pass" was concealing which. Same species as the 17→25
  miscount and found the same way: by running the thing instead of reading its summary. Both
  the index row and Run 11's preconditions now say which file to pass as `argv[1]`.

  The acceptance criteria are pre-registered with the **power caveat first** (D12's run-5 rows
  were all underpowered for a 3-pt effect), and one of the four outcomes is *"Claim 1's
  attribution is wrong"* — the run is set up to be able to falsify this project's headline,
  not only to confirm it.

  Full suite **19/19** after all edits. (**Superseded 2026-09-14:** this entry said
  `tests/test_modules.py` and `tests/test_tome_correctness.py` "need `PYTHONPATH=.`" because
  running them as `python tests/x.py` puts `tests/` on `sys.path` instead of the root and raises
  `ModuleNotFoundError: src`. That was a real harness artifact, and it is now fixed at the
  source: both files insert the repo root into `sys.path` themselves, the way
  `tests/test_model_pipeline.py` always did. All five test files now run clean with **no
  environment variables at all**. A test that needs a remembered env prefix is a test people
  stop running.)

- **2026-09-09 (summary reconcile + Pending 6 DONE) — the three standing documents now agree
  with D12 and M1, and the results writer names its own environment.**

  **Reconcile (old Pending 2, second pass).** `REPORT.md` and `README.md` both predate D12
  (2026-09-05) and M1 (2026-09-06) and were stale in three ways each: both still said *"why
  pruning helps is unexplained — a regularisation-like effect is the obvious guess and nothing
  tests it"*, which D12 tested and rejected; neither carried the word **"if"** that D12 says
  the deliverable requires; and neither mentioned the KV claim, so both read as *"no efficiency
  claim at all"*. Also corrected in both: the router-vs-random margin was quoted as **+14 to
  +28**, which **understates the top end** — D11's own rows give **+17.7 / +27.4 / +34.0 /
  +29.3** at keep=0.50/0.35/0.25/0.20 (the +34.0 at keep=0.25 was outside the quoted range).
  `REPORT.md` gained a "Why pruning helps — settled" section, D12 and M1 rows in the
  per-run table, and the local-vs-Kaggle drift as a named limitation; `README.md` gained the
  M1 bullet, the drift warning, and a "What's open" section pointing at items 14 and 15.
  This file's top block, the historical marker on "Where the project actually is", and the new
  OPEN ITEMS table were done in the same pass; `check_agents_md_format.py` clean afterwards
  (28 balanced fences, 0 ragged rows over 65 tables, 0 debris).

  **Pending 6 DONE.** Cell 15's `meta` recorded a run's *settings* and nothing about the
  *environment* they ran in — the exact axis every cross-run comparison here has broken on.
  `scripts/patch_notebook_provenance.py` (3 anchors, each asserted to match exactly once,
  `ast.parse`d, backed up first) adds a `PROVENANCE` dict stamped into **both** `json.dump`
  sites: `eval_ckpt` / `control_ckpt` as `{path, mtime, size_bytes}`, plus `transformers`,
  `torch`, `device`, `device_name`, `written`. Regenerated `kaggle_pruning_run.ipynb`; cell 15
  verified byte-identical across the two notebooks.

  Three things this pass is worth remembering for:
  - **The check was built so a decorative implementation fails it.** A `_ckpt_stamp` that
    echoed its argument instead of calling `os.stat` would satisfy every "is the key present"
    check and still permit the misattribution the stamp exists to prevent. So
    `verify_results_provenance.py` §2B stamps a file, **mutates it**, re-stamps, and requires
    the two to differ. Confirmed by sabotage: a constant-returning stamp scores **4 FAILs**
    and exit 1, against 35/35 and exit 0 for the real one.
  - **Placement was chosen to protect another verifier.** `verify_harness_control.py` extracts
    its block as `src[BEGIN : index("\nrows = []")]`. Inserting provenance *before* `rows = []`
    would have silently pulled it into that extraction and changed what that verifier tests —
    a green suite hiding a weakened member. The block goes *after* `rows = []`, the patcher
    asserts that ordering, and the verifier re-asserts it plus `"PROVENANCE" not in` the
    harness block.
  - **Bookkeeping must not be able to cost a session.** Every lookup in the block degrades to a
    recorded string; the verifier asserts `raise` / `assert` / `sys.exit` are absent from it,
    and `json.dumps(PROVENANCE)` runs at build time so a non-serialisable value fails at the
    top of the cell rather than at the first write — which lands after row 0, minutes of GPU in.

  Suite **19/19** after the pass (14 `verify_*.py` + 5 `tests/*.py`), against an 18/18 baseline
  taken *before* any edit precisely so a regression would be attributable.

- **2026-09-06 (Pending 7, 8, 9–11, 12 — the "items 7 through 12" pass) — the project now has
  exactly one efficiency claim, and it is measured.**

  **Pending 7 DONE.** Cell 15's Q5 note told the reader the token column implies an
  encoder-side saving. It does not — the router runs *after* the frozen Swin, so all 4800
  tokens are computed at every `keep_ratio`. Replaced in **both** notebooks with eight
  escape-free `print()` lines stating there is no encoder-side saving and that latency is
  decoder-bound at 1.04× (D11). The note was wrong *in the direction that flatters the
  project*, which is the direction to distrust first. My first patch produced JSON-valid but
  **Python-invalid** source (embedded `\n` split string literals across notebook source lines,
  `SyntaxError` at line 411) and was caught only by re-verifying with `ast.parse` instead of
  trusting the "patched" message. Whole verifier suite re-run green afterwards (39/39, 36/36,
  11/11, 8/8, 34/34, 6/6) because a shared notebook cell's source list had been rewritten.

  **Pending 8(c) DONE — Measurement M1, and it is the item's whole point.** D11 killed the
  latency claim and option (a) was taken, leaving the writeup with **no efficiency claim at
  all**; this file had recorded for two days that (c) "still needs the memory measurement
  nobody has taken". Built `scripts/eval_kv_memory.py` (72 s, **25/25** controls PASS — this
  entry read "17/17" until 2026-09-09, see the 2026-09-09 changelog entry):
  **keep=0.35 cuts decoder cross-attention KV 150.00 → 52.50 MiB (−65.0%) for −0.26 pts of
  word recall (t −0.18, n=50 paired)**. Five things make it a measurement rather than algebra,
  and each was a decision to *not* take the easier route:
  (a) **Two independent measurements asserted equal** — analytic geometry vs walking the real
  `past_key_values` — rel gap **0.0000** at all five budgets.
  (b) **The measured tensor is the one `generate()` decoded against.** My first draft
  re-derived the pruning path inside the eval script; that is a second copy of `src/model.py`
  free to diverge, and it was *already wrong* (`router()` returns a 4-tuple, not scores).
  Replaced with a forward hook plus a control asserting the captured `seq_len` equals
  `meta["compressed_tokens"]`. If the hook misses, the script raises rather than falling back.
  (c) **The headline is not the biggest number.** keep=0.20 reaches −80.0% but costs 13.01 pts
  (t −5.42); quoting it bare would sell a memory win funded by an accuracy loss. Both accuracy
  figures are **read out of D12's JSON at runtime**, with a control that FAILS if the lookup
  does not resolve — a hardcoded "−0.26" is a claim about another file that rots silently.
  (d) **The self/cross split is proven, not commented.** Self-KV asserted exactly
  `f(gen_tokens)` and asserted **non-monotone in keep** (keep=0.25 → 10.19 MiB > keep=0.35 →
  9.56 while cross-KV goes the other way), so a self/cross mix-up cannot pass as a pruning win.
  (e) **My own pre-written hedge was falsified by the output.** The docstring warned this might
  be "a large cut in a small quantity"; unpruned cross-KV is **19.46% of the model's 771 MiB of
  parameters**. The script now derives that framing from the measured share instead of printing
  the guess. *This file's usual failure is over-claiming; here a pre-registered expectation was
  too pessimistic and would have understated a real result.* Before the real run, a scratch
  selftest executed the two pure helpers against **three** different cache layouts (asserting
  all three yield identical numbers, so a `transformers` upgrade cannot silently turn the cross
  figure into a self figure) and required **every** control to FAIL on a deliberately broken
  row. Scratch files removed.

  **Pending 9, 10, 11 — confirmed still closed, not skipped.** Re-executed
  `verify_saliency_loss_cell.py` (**11/11**) and `verify_training_telemetry.py` (**8/8**)
  rather than trusting the strikethroughs, since both are struck as DONE on the strength of
  execution counts that a later edit could have invalidated.

  **Pending 12 DONE, and the grep it demanded was worth more than the rename.**
  `results_2/` → `run 7/`, `results_3/` → `run 8/`, run 6's seven Kaggle artifacts split out
  of `results/` into `run 6/` (decided by identical mtimes plus `ablation_decoding.json` being
  byte-identical to the copy inside its own zip). **The item's own instruction to rename
  `results/` wholesale was wrong** — it was never a run directory, and obeying it would have
  filed D11, D12 and M1 under a 2026-08-29 Kaggle run; it survives as local-diagnostics-only.
  The grep then found `diagnose_decoder.py`'s documented "newest-run-first" resolver **missing
  `run 9/` and `run 10/`**, so unqualified invocations had silently diagnosed run 8's weights
  for five days — *a resolver that falls through to an older path is worse than one that
  fails.* `diagnose_selection_statistics.py` had the same shape of defect (defaulted to the two
  oldest pruning runs); adding 9 and 10 immediately showed **run 10 flips Q3 to `D2 FALSIFIED`**
  where 7/8/9 read `INCONCLUSIVE`. **New Gotcha, created and fixed in the same session:**
  `Set-Content -Encoding utf8` round-tripped AGENTS.md through CP1252 and produced **1117
  mojibake sequences** (em dashes 936 → 179), silently and while the requested path edits were
  all correct. Reversed exactly; verified 0 mojibake, 0 `U+FFFD`, line count unchanged, 28
  fences balanced, 0 ragged rows. *A bulk operation needs a check on what it was **not**
  supposed to change.*

  **Pending 12 blast-radius sweep — three more defects, and all three had already passed a
  green check.** Per the standing "run the whole suite after touching shared code" rule I
  finally ran the deferred parse sweep (`scripts/_final_check.py`, scratch, deleted after) over
  all 59 scripts, both notebooks' code cells, and every run-ish path literal in the tree. It was
  not a formality — it failed three times before going green, and each failure was a thing I had
  *already reported as verified*:
  1. **UTF-8 BOM on all five rewritten files** (`_curve_data.py`, `_summarize_ablation{,3}.py`,
     `geom_probe.py`, `infer.py`) — the same `Set-Content -Encoding utf8` that caused the
     mojibake. `ast.parse` → `invalid non-printable character U+FEFF`. I had written that these
     four scripts were "executed afterward and confirmed working", and they were: CPython reads
     source as `utf-8-sig`, so running a file cannot detect a BOM. **Execution is not a superset
     of parsing** — the previous session's lesson was "parse is not enough", and the converse is
     equally true. Stripped byte-level with `raw[3:] == new` asserted so nothing else moved.
  2. **The rewrite corrupted two live paths by substring collision.** `results_2` occurs inside
     `pruned_ocr_results_2/`, a *different* directory that still exists, so
     `pruned_ocr_results_2/checkpoints/...` became `pruned_ocr_run 7/checkpoints/...` in
     `geom_probe.py` and `infer.py` — surfaced by `geom_probe.py` dying on
     `FileNotFoundError: 'pruned_ocr_run 7/...'`. I had explicitly written the opposite above
     ("two name `pruned_ocr_results_2/`/`_3/` … and were left alone"); that sentence came from
     reading grep's match list, never the files. Both restored and `torch.load`-verified (490
     keys each). **The substring that produces the match is the substring that makes the
     rewrite wrong.**
  3. **Five files still held `pruned_ocr_results/`**, dead since the Kaggle move and
     "fixed" on 2026-08-31 — in `diagnose_decoder.py` only. `benchmark_summary.py`,
     `plot_corrected_overlay.py`, `test_prompt_generation.py`, `test_start_tokens.py` and
     `src/evaluate.py` kept it for six days behind that day's "**8/8 verifiers exit 0**",
     which globbed `verify_*`/`diagnose_*` and so never looked at any of them. Repointed at
     `run 5/checkpoints/`.
  The curated path list I wrote first would have caught **none** of these — it checked the
  paths I already had in mind. What caught them was enumerating *every* string constant in
  *every* script via `ast` and existence-checking the run-ish ones, which is now the shape to
  reuse: **for a defect in a literal, enumerate by grepping the tree, not by running the
  scripts you can name.** Final state: 0 syntax errors / 59 files, 20/20 notebook code cells,
  15/15 path literals resolve, 0 BOMs, M1's JSON re-asserted against the numbers written into
  this file, D12's pairing re-confirmed present. Two Gotchas added; the 2026-08-31 entry and
  Pending 12's own "left alone" sentence corrected in place rather than quietly overwritten.

- **2026-09-05 (Diagnostic D12) — the standing guess about *why* pruning helps was wrong, and
  the deliverable gains a load-bearing "if".** Built `scripts/eval_why_pruning_helps.py` and
  ran it at `--n 50` (110 min, local CPU). This file had carried "a regularisation-like effect
  is the obvious guess and nothing in this file tests it" since D11. **Tested it; H2 is
  rejected.** Run 5 — the checkpoint trained *and* evaluated unpruned — peaks at keep=1.00 and
  falls **monotonically** (−1.57 / −6.03 / −11.47 / −20.34, significant at the last three),
  while run 9 peaks at exactly the keep=0.50 it was trained for. Difference-in-differences is
  negative at all four budgets (−2.17 / −5.77 / −4.52 / −7.33, significant at two). H2 was
  handed its most favourable condition — the ink oracle retains **0.994** of the page's ink at
  keep=0.50, i.e. blank paper is what got dropped — and run 5 declined anyway. **Consequence
  for the writeup: "pruning to a third of the tokens costs nothing IF you train for it." Every
  earlier phrasing in this file omitted the "if".** H1 is *supported, not isolated* — run 9 has
  five more epochs as well as pruning-aware training, stated in the docstring before any output
  and not upgradeable without a control run that does not exist.
  Four methodological items, all of which cost something to learn:
  (a) **The smoke runs found three defects, all one error**: a tolerance never compared to the
  noise of what it bounds. A harness anchor that compared a 2-image mean to a 50-image one
  (automatic FAIL, and since it *gated the verdict*, all four H1/H2 branches were dead code); a
  power check certifying "detectable ≥ 1.02 pts OK" off two images; and — after I fixed the
  power table — **two other readers of that same SE still printing significance stars**
  (`t = +25.55` off `SE 0.21`). D11 saw this error produce a decorative PASS; here it produced
  two spurious FAILs and a spurious star. *Enumerate every reader of a quantity before changing
  how it may be used.*
  (b) **A control was replaced mid-flight, pinned to a number that did not yet exist.** The
  first n=50 row (run 5 @ keep=1.00 = 74.72 vs Kaggle's 77.74, gap 3.02) failed the anchor. The
  control was wrong, and the evidence predated the failure: D11 had shown generation does not
  reproduce across environments while selection does, and this script's own JSON says
  `not_comparable_to_kaggle_in_level` — then gated on exactly that level. Rather than widen the
  tolerance after seeing the number, pre-registered a replacement in AGENTS.md before the data
  arrived: **run 9 @ keep=1.00 must reproduce D11's local 77.62 within 0.5 pts.** It came back
  **77.62, gap 0.00.** Also recorded plainly that I only noticed the contradiction *because* the
  control failed.
  (c) **The pre-registered code verdict and the pre-registered prose prediction disagreed, and
  both are reported.** `decide()` returned **UNDERPOWERED** (correctly — keep=0.50's SE 2.60
  resolves nothing under 5.20 pts) because I had keyed it on the keep=0.50 delta alone: the
  flattest point on the curve and the budget run 9 was trained for. The docstring's prediction
  was about curve **shape**, and that resolved decisively. *When a hypothesis is about the shape
  of a curve, the statistic must be about the shape; a single point on it is a proxy.* Neither
  reading was quietly promoted over the other.
  (d) Added `--rescore` (re-derives controls and verdict from saved per-image recalls in 0.0
  min, calling the same code as the live path) and `--selftest` (executes all four verdict
  branches against six injected cases, including the pair that separates UNDERPOWERED from a
  real null at identical delta). Forced the n=50 gate branch to execute against a forged JSON
  before trusting it. Every code path in the file is now executed, not parsed.
  Also: retained ink is contradicted a **fourth** time — router selection scores 80.46 at ink
  0.922 while the ink oracle scores 78.22 at ink 0.994, i.e. **−2.24 pts for +0.072 more ink**
  (SE 1.38, t −1.62 — directional, not a claim). Updated the deliverable section, the D12
  section, the verifier index, the results index, and `results/why_pruning_helps_*`.
- **2026-08-29** — Evaluated run 4 (negative result); prepared and verified Phase 2b
  unfreeze; evaluated run 5 (mixed); diagnosed under-generation and identified the
  stale decode config; prepared and verified the Phase 2c decoding ablation.
  Created this file.
- **2026-08-29 (later)** — Phase 2c attempt 1 failed to launch (bad checkpoint path
  + CPU session). Wrote `scripts/patch_notebook_phase2c_fixes.py`: hard GPU assert,
  self-diagnosing checkpoint-path resolver moved to cell 2, and eval-only mode now
  skips the ~19 min train-set download. Verified by
  `scripts/verify_phase2c_fixes.py` (12/12 PASS). Fixed an ambiguous cell selector
  in `verify_decode_ablation.py` that the move had broken; it passes again.
  **Ablation still not run — nothing measured yet.**
- **2026-08-29 (run 6)** — **Ablation ran. Decoding was the cap, and the fix is
  large: 50.56 → 77.74 recall (+27.18), 40.97 → 64.70 char acc, 26.49 → 53.05 word
  order, NED 0.590 → 0.353, valid JSON 0% → 82%, all on unchanged run-5 weights.**
  Cause was `repetition_penalty=1.3`, not the suspected trigram block (which was
  bit-exactly inert). CONTROL row reproduced run 5 at 0.00 pt drift. Adopted
  rp=1.0 + nrns=3 as the notebook default via
  `scripts/patch_notebook_decode_default.py`, verified by
  `scripts/verify_decode_default.py` (all checks PASS, including that the
  ablation's explicit 1.3 still overrides the new default). Marked rows 2–5 of the
  run table as artifact-contaminated; rewrote "Current state"; struck the falsified
  trigram hypothesis; closed the malformed-JSON issue as the same root cause.
  Then swept the stale default out of the **three other places it was hiding** —
  `src/model.py:241` (library mirror), `infer.py` (function default, CLI default,
  and a help string that claimed "1.3 works well for this model"), and
  `scripts/geom_probe.py` — so the bug no longer ships to anyone running inference.
  Verified: all 4 test suites pass, including `test_end_to_end.py` exercising real
  generation through the patched `src/model.py`.
  **Next: the Phase 2 pruning sweep, which is what all of this was blocking.**
- **2026-08-29 (Diagnostic D1)** — Built `scripts/router_score_probe.py`, the
  "cheap step 0" from Pending 1, and it **inverted the plan it was meant to
  support**. The router trained (weights moved off their init), its scores are
  well-spread and unsaturated (std 0.209, 0% saturation, 4799/4800 unique),
  content-dependent rather than a fixed positional mask (cross-image Spearman
  0.125), and genuinely reoriented away from a random-init projection (Spearman
  0.019) — and **none of that matters**, because the kept top-50% retains only
  **34–38% of the page's ink where random pruning retains 50%** (Pearson(score,
  ink) = −0.226 / −0.248). The router is a whitespace detector; the saliency map is
  a near photographic negative of the ink map. Root cause is the already-logged
  `keep_ratio=1.0` STE trap: with K=N the multiplier is exactly 1.0, so the only
  gradient the scorer ever saw asked "does scaling this token help", which
  anti-aligns with "is this token informative". Two methodological catches on the
  way: the section-E clustering result (0.503 vs a random mask's 0.333) was mostly
  **inherited from Swin feature smoothness** — an untrained router scores 0.455 —
  and the probe printed "VERDICT: no concerns" across five sections before the
  sixth reversed it. Silver lining, measured: **negating the score beats random**
  (0.619 contrast / 0.657 darkness vs 0.500), better on all 4 images, so the
  learned ranking carries real signal with an inverted sign.
  Consequences recorded: training with pruning ON moved from "open design decision"
  to **required**; the eval-only sweep was demoted from deliverable to a single
  floor-pinning row, since sweeping this ranking would have produced a catastrophic
  curve inviting the wrong conclusion ("pruning ruins OCR") over the right one
  ("this router was never trained to prune"); two free experiments now precede any
  GPU booking (negate the score; ink-oracle upper bound to check the premise that
  half these tokens are droppable at all). ~~Section F is now the acceptance gate for
  any future router.~~ *(Struck 2026-08-31: D2 replaced this gate, then D3 withdrew
  D2's replacement too. See Conventions — there is no validated cheap gate.)* Cost:
  ~15 min local CPU, against the ~16 GPU-hours it
  redirected.
- **2026-08-29 (Pending 1b built; Diagnostic D2)** — Built the mechanism for D1's
  two free experiments as one orthogonal knob: `select_mode` on `generate()`
  (`router`/`negated`/`random`/`ink`), implemented as `select_scores` + `invert` on
  `PatchSaliencyRouter.forward` plus a learning-free `patch_ink()` in `src/model.py`.
  Swaps the ranking signal only — K, architecture and decoder untouched — and
  `meta` now reports `select_mode` and `retained_ink` per call so an accuracy row
  always carries the number that explains it. STE is skipped under an external
  ranking (gradient for a selection the scorer did not make is meaningless).
  Verified by execution: `scripts/verify_select_modes.py`, all checks pass against
  the real router and real `patch_ink` — including that the four modes select
  genuinely different tokens, which is the failure that would have printed four
  rows of one config and "proved" the router fine. Two of its own checks failed
  first and **both were the verifier's fault, not the code's** (a synthetic fixture
  with 36 patches tied at exactly 0.0 contrast, where top-k `largest=True/False` are
  not complementary; and an arbitrary `> 0.999` threshold on an oracle that cannot
  reach 1.0 under paper grain) — per the standing convention, suspect the verifier
  first. Eval harness `scripts/eval_select_modes.py` **extracts** the notebook's
  real `compute_word_metrics`/`compute_ned`/`reading_order_words`/`MAX_WORDS` by AST
  rather than restating them, and warns loudly if `editdistance` is absent (its
  silent fallback would change every number without erroring).
  **n=2 smoke inverted D1's recommendation.** Negation beats the forward router
  (+4.2 recall) but **loses to random by 21 pts** while retaining *more* ink —
  so D1's premise that ink-retention predicts accuracy is false. Booked **Diagnostic
  D2** (pure numpy on D1's cached npz, <1 s) to explain it: the discriminating
  quantity is **worst-case line coverage**, not summed ink. Every aggregate
  statistic mis-orders those two rows; every worst-case statistic reproduces the
  recall order exactly. *(Both sentences struck by D3 on 2026-08-31 — the family-level
  split does not exist at n=50. Kept here as the historical record of what was believed;
  do not read it as current.)* Falsified H2 (contiguous gaps) in the informative direction
  — the oracle has the *longest* drop-runs and the best accuracy, so clumpiness is
  a virtue here and "spatial spread" must not enter a router loss. Good news from
  the same table: the **ink oracle reads a half-token page at 81.04 vs 82.61 for the
  full page**, so the droppability premise holds strongly and 1a is not wasted.
  New Pending **1d** (before 1a): test a per-row stratified budget, since a single
  global top-k cannot bound worst-case coverage and the router's minimum line
  coverage is 0.000. n=50 confirmation run in flight.
- **2026-08-29 (Pending 1d built; Phase 2d ported to Kaggle)** — Built the stratified
  selection mechanism and then moved the whole eval to the notebook.
  `stratified_scores()` in `src/model.py` expresses a **per-grid-row top-k as a
  monotone rewrite of the ranking signal** (`key = (gw − within_row_rank) +
  normalized_score`), so a *global* top-K on the key is exactly a *per-row* top-k and
  **`router.py` needed no change** — no second selection path to drift from the first.
  `scripts/verify_stratified.py` (17/17) checks it against an **independent** per-row
  `topk` loop rather than a restatement, because this is a claim that fails by one
  rank band and still yields a plausible-looking mask.
  **Venue changed.** Local CPU generation measured at **~45 s/image**, not the ~15 s
  I had inferred from a single short FUNSD doc — my own estimate was wrong by 3×, so
  1c's sweep was 12+ hours rather than an evening. Killed the local n=50 run (it had
  reached 30/50 of row 1 of 5, and lost all of it, because its `json.dump` only ran on
  completion) and ported everything to Kaggle instead.
  **Phase 2d.** `scripts/patch_notebook_selection_ablation.py` — 7 asserted
  substitutions across cells 4 and 7 plus a new 15-row ablation cell covering 1b, 1c
  and 1d in one GPU session. The port's real scope was the discovery that **the
  notebook duplicates the model classes and imports nothing from `src/`**, so none of
  the D1/D2 mechanism existed there. `scripts/verify_selection_ablation.py` (**44/44**)
  execs the patched cells, compares the ported functions **numerically** against
  `src/` with weights copied between routers (bit-identical), drives the real
  `generate()` through all six modes on a real 80×60 grid, and runs the whole harness
  cell end to end on stub data with the notebook's real metric functions. Two of its
  checks failed first and, per the standing convention, **both were the verifier's
  fixtures rather than the code** — and one paid for itself: a global top-k only
  starves a region when the preferred region is **at least as large as the budget**
  (5 hot rows out of 80 starved nothing against K=2400), which bounds when 1d can help
  and is the first thing to re-check if the stratified rows come back flat. The new
  cell writes results **after every row**, which is the lesson from the killed run.
  Still not built: `merge_ratio` rows — Phase 2d pins it to 0.0 to keep the selection
  question clean, so ToMe remains the one part of 1c unexercised.
- **2026-08-30 / 08-31 (runs 7 and 8 — entry added retroactively on 2026-08-31)** —
  Phase 2d ran twice on Kaggle T4s and produced `run 7/` and `run 8/`, 15 rows
  each. Run 7 retrained the router with pruning ON at `keep_ratio=0.50`; the scorer was
  still sign-inverted, so `stratified_negated` carried the sweep. Run 8 added an
  **ink-BCE saliency loss** and the forward `router` came out correctly signed — the
  single largest change in the project's history on that axis (`negated` collapsing
  73.09 → 2.70 is the cleanest confirmation available that the sign genuinely flipped,
  since it is the same weights read backwards). Details in the run table and the
  per-run sections above. **These runs happened under a different agent and were written
  up in the sections but never entered here**; the gap is why D3 exists, and the
  convention it produced is under Conventions ("transcribe the verdict").
- **2026-08-31 (Diagnostic D3 — three answered questions nobody read, and one retraction
  that had already been printed)** — Asked for an honest review of runs 7–8, checked the
  claims against the artifacts instead of the prose, and found the write-up had kept the
  confirmations and dropped the contradictions. Built
  `scripts/diagnose_selection_statistics.py` (pure numpy over the two result JSONs, <1 s,
  falsifiers stated in the docstring) so the critique is reproducible rather than a set
  of hand-pasted numbers.
  - **D2's min-coverage acceptance gate is withdrawn.** Run 8's own notebook printed
    `=> D2 FALSIFIED per-image` and run 7 printed `INCONCLUSIVE`; neither was
    transcribed, while the gate propagated into Conventions, Gotchas, Pending 1b and a
    cross-session memory. At n=50 min coverage is the *weakest* of the four predictors
    and the aggregate/worst-case "family split" does not exist. Retired on a second,
    independent ground as well: at keep=0.35, `router` (minCov 0.127) reads 77.80 and
    `random` (minCov 0.137) reads 48.37 — **equal coverage, 29.42 pts apart**.
  - **The efficiency half of the deliverable fails.** −65% visual tokens → **−7.1%**
    wall-clock (0.18–0.22× proportional). Latency tracks *generated* tokens
    (r = +0.93/+0.98), not visual tokens (r = −0.10/+0.15), because **pruning is
    post-encoder** — all 4800 tokens are computed at every `keep_ratio`. Cell 15's Q5
    note asserts the opposite and is now Pending item 7.
  - **"Beats the ink oracle" is probably co-adaptation.** Run 8 trained at
    `keep_ratio=0.50`, so exactly one cell of its table has eval config == train config —
    and that is the peak (80.17, above the 78.25 full-page row). Every off-distribution
    rule pays, including ones with better proxies (ink: 0.994 retained ink and 0.955 min
    coverage, loses by 5.38; `stratified`: same scores, better coverage, loses by 4.42).
    Recorded as a bounded **hypothesis with a falsifier**, not a conclusion, because run 7
    does *not* show it (there ink wins at keep=0.50) — so the effect is not unconditional.
    Test is Pending item 5.
  - **The `keep=1.00` row is no longer a control.** Runs 7–8 changed the weights, so its
    drift (−10.93, +0.51) conflates harness soundness with the retrain's effect and can be
    told as either story. Pending item 4 restores a real one.
  - **Promoted from run 7's log: the ceiling itself dropped.** The ink oracle lost 5.19
    recall, 9.59 char acc and **11.23 word order** vs run 5's weights on identical pages —
    so pruning-ON training cost the *decoder*, and `Q2 PREMISE HOLDS` (run 8) vs
    `PREMISE IS WEAK` (run 7) on identical ink masks makes droppability a property of the
    weights, not the dataset.
  - **Fixed `scripts/verify_select_modes.py`** (3 failures, and worse than 3). `SELECT_MODES`
    grew to six entries while the verifier's inline dispatch handled three, so
    `stratified`/`stratified_negated` were tested as plain-`router` duplicates — and
    "stratified: selected exactly K=24" **reported PASS on a router selection**. Replaced
    with an exhaustive `mode_kwargs()` that **raises** on an unknown mode (verified the
    guard fires), and added the per-row budget checks nothing previously tested: both
    stratified modes now assert exactly k=3 per grid row, plain `router` is asserted *not*
    to (measured [2,2,4,1,3,4,4,4]), and the two variants are exact per-row complements
    (overlap 0/24). All checks pass. Confirmed the staleness predated the notebook port.
  - Rewrote across this file: the deliverable paragraph, the file map (runs 7–8 came from
    `kaggle_pruning_run.ipynb`, **not** the canonical notebook — a third copy of the model,
    and the BCE mechanism exists only there), the run table, both run sections, D2's
    header, Current state, Conventions (gate struck; "transcribe the verdict" added),
    Gotchas (+5), and Pending (items 4–8).
- **2026-08-31 (Diagnostic D4 — the loss behind the headline result is mis-specified, and
  the result is a floor rather than a ceiling)** — Booked while *verifying* D3's "runs 7→8
  moved two knobs at once" claim against cell 11 rather than restating it. The two-knob
  claim confirmed exactly (`SUPERVISE_SALIENCY` toggles `lambda_sparsity` 2.0→0.0,
  `target_budget` 0.50→1.0 **and** `LAMBDA_SAL` 0.0→2.0 in one `if/else`,
  cell 11 lines 41–48). Then found something bigger in the same block:
  `binary_cross_entropy_with_logits` is fed `outputs['scores']`, which is already
  sigmoid'd (`src/router.py:25`) — **a double sigmoid**. Quantified in
  `scripts/diagnose_saliency_loss.py` (runs clean, <1 s, reads both halves out of the
  notebook so it goes stale loudly if fixed): attainable probability **[0.500, 0.731]**,
  loss floors **0.313 / 0.693** instead of ~0, and gradient attenuation that **grows with
  the error — 3.7× on already-correct tokens, 112× on a text patch the scorer confidently
  calls blank**. So no loss weight can absorb it, and `LAMBDA_SAL = 2.0` is the symptom of
  tuning against it. The run is *not* invalidated (monotonicity preserved the ranking, and
  `negated` collapsing 73.09 → 2.70 is unambiguous); the conclusion is that **77.80 is a
  floor on ink supervision, with unclaimed headroom above it**. Checked the *target* too,
  on real FUNSD pages via D1's cached npz rather than a fixture: 37.1% positive and only
  0.037 drift across `T ∈ [0.05, 0.30]` because patch ink is bimodal — so
  `SALIENCY_THRESHOLD` is sound and **not worth sweeping**. Also measured, rather than
  hedged, how much of Phase 2d's 44/44 transfers to the derived notebook: a per-cell hash
  diff shows **exactly three cells differ** (2, 9, 11) and cells 4/5/7/13/14/15/16 are
  byte-identical — so the verified selection mechanism *is* what ran, and cell 11, the one
  new and unverified cell, is where the defect is. New Pending items **9** (one-line fix,
  then re-tune `LAMBDA_SAL`) and **10** (an execution check for the training cell), plus
  two Gotchas.
- **2026-08-31 (housekeeping, all execution-verified)** — Ran **every** `verify_*.py` and
  `diagnose_*.py` in `scripts/` rather than trusting their recorded status. **8/8 verifiers
  exit 0**; 4/5 diagnostics run clean. The fifth, `diagnose_decoder.py`, died on
  `FileNotFoundError: pruned_ocr_results/checkpoints/adaptive_donut_funsd.pt` — a
  directory that has not existed since the Kaggle outputs were moved in under per-run
  names, i.e. the "inconsistent naming" file-map note biting a script nobody had re-run.
  Fixed with a newest-run-first candidate resolver plus a `<path>.pt` argv override that
  **lists every path it tried** instead of raising a bare error; verified by executing the
  resolver (resolves to run 8's checkpoint; a bad explicit path exits with a message).
  **Amended 2026-09-06: this fix was narrower than the entry implies.** The dead
  `pruned_ocr_results/` default was repaired only in `diagnose_decoder.py` — the file that
  happened to be the one running. Five other files kept it and were still broken six days
  later: `benchmark_summary.py:25`, `plot_corrected_overlay.py:24`,
  `test_prompt_generation.py:17`, `test_start_tokens.py:17`, `src/evaluate.py:239`. All five
  now point at `run 5/checkpoints/adaptive_donut_funsd.pt`. "8/8 verifiers exit 0" is what
  hid them: none of these five is a `verify_*` or `diagnose_*` script, so the sweep that
  produced that green count never touched them. **A shared-path bug is not fixed at the
  call site that surfaced it — grep for the literal across the whole tree.**
  Marked the script LEGACY in its docstring — its question (next-token vs copy) was
  settled before run 6.
  **Recorded checkpoint fingerprints** for runs 5/7/8 (size, mtime, sha256 of head+tail
  8 MB) in the file map, which retroactively ties the existing result tables to specific
  weights despite the missing `meta.checkpoint` — mtimes corroborate the run dates. Also
  corrected a detail of my own D3 write-up: `meta.checkpoint` is not `None`, the **key is
  absent entirely**; D3 prints `None` because `.get()` does.
  **Added a diagnostics index** to the top of this file (D1–D4 + Kilo's ToMe probe, one
  line each) — four diagnostics had accumulated with no way to see what existed short of
  reading 1600 lines.
  **Closed one more open question from existing data**, in the same spirit as D3: the
  inherited "aggressive pruning induces repetition collapse" claim is **falsified**.
  `hit_max_length_pct` across all 30 swept rows peaks at 4.0% with a median of 0.0 and no
  row above 10%, vs 22% when collapse was real in run 6. Trend with budget exists
  (1.00→0.0%, 0.35→1.0%) and is ~20× too small to act on. So the `repetition_penalty`
  ban stands and `no_repeat_ngram_size=3` is carrying it alone, as designed. That claim
  had been sitting unanswered as "open question for the sweep" while the sweep's own
  output answered it twice.
  **Ran the full local test suite too, and it looked red.** `pytest` turned out not to be
  installed at all; all 5 tests pass as plain scripts. The "not installed" half was
  already in Gotchas — amended it with the part that was missing, namely that the failure
  mode is indistinguishable from 5 broken tests if you only read exit statuses, plus a
  dated 5/5 confirmation on the current tree. Per the standing rule, a green check and a
  red one get the same suspicion.
  **Then actually ran the repaired `diagnose_decoder.py` end to end** rather than
  stopping at the resolver — the standing "did you check that it *runs*" rule applied to
  my own fix, and it paid for itself. It confirmed at the logit level that run 8 has no
  copy failure (COPY 0.0% / NEXT 74.5%, CE 3.02, the whole `<s_doc>{"text": "` prefix
  exact) and produced the **first legible sample of run-8 output** recorded anywhere in
  this file: `'{"text": "ATT. GEN. ADMIN. OFFICE Fax: 614-466- 5087 Dec 10 .98 17 :46 P.
  01 ATT.'`. Right content, wrong reading order — which is the 77.74-recall /
  53.05-word-order split made concrete instead of aggregate.
  Its C1/C2 divergence (unprompted output is garbage, `<s_doc>`-prompted output is
  correct) was chased down and is **not** a run-8 defect: the real eval always prompts
  (cell 15:111 `decoder_input_ids=prompt_ids`; cell 13 `TASK_PROMPT = '<s_doc>'`), so C1
  exercises a path nothing uses. Two Gotchas came out of it — the checkpoint is
  prompt-dependent and `generate()` silently falls back to `<s>`, and `<s_doc>` is not a
  special token in this tokenizer (5 subwords, vocab never extended; harmless because
  train and eval agree, but unfixable without invalidating every checkpoint).
- **2026-08-31 (D5 — `scripts/diagnose_saliency_loss_coupling.py`)** — Asked "what next?",
  answered "Pending 9, it's one line," then checked it before recommending it. **D4's
  prescribed fix was unsafe.** `scores` has three consumers, not one: `AdaptivePruningLoss`
  reads it for the sparsity term (a fraction vs `target_budget`) and the entropy term
  (`clamp(1e-7, 1-1e-7)` → binary H), and both require a probability. Returning the
  pre-sigmoid logit as D4 advised would not crash — it drops the entropy term's `H`
  0.403 → 0.135, attenuates its max gradient **12×**, and (worse) leaves it regularizing
  only the tokens whose *logit* happens to land in (0,1), an arbitrary slice unrelated to
  saliency. Corrected fix recorded in Pending 9: keep the sigmoid, change only cell 11's
  call to `F.binary_cross_entropy(..., clamp(1e-6, 1-1e-6))` — one line, one file, no
  other consumer touched.
  **Second finding, arguably the more useful one: `lambda_entropy = 0.05` was never
  chosen.** Cell 11 never passes it, so both branches inherit `src/loss.py`'s default. Two
  terms shaped run 8's scores and only one was deliberate — and the undeclared one pushes
  scores *toward* p=0.5, opposing the ink-BCE. Measured at **1.0–42.4%** of the BCE
  gradient, so the "they fight each other" hypothesis is **falsified as a present cause**
  (as predicted before measuring). But it goes live at the moment of the D4 fix: entropy's
  share rises to 85% at `LAMBDA_SAL=1.0` and **170% at 0.5**, so re-tuning `LAMBDA_SAL`
  while leaving `lambda_entropy` defaulted is the runs-7→8 two-knob mistake repeating
  itself through a default instead of an edit. Both must now be passed explicitly.
  **Also sharpened D4 with a measurement it had only reasoned about**: the scorer's own
  output on real pages spans **[0.010, 0.990]** (median 0.459), so it is fully expressive
  and the defect is not "it cannot express confidence" — it is that **the loss is
  structurally unsatisfiable**: `sigmoid(0.99) = 0.729` against target 1 is never
  satisfied, so no attainable output ever lets the loss say "this token is done."
  Two Gotchas added (a defaulted hyperparameter is an undeclared one; enumerate a value's
  readers before changing its range) and Pending 10 gained two concrete assertions,
  including a range contract that makes the D4 fix fail loudly if anyone re-introduces
  logits later. One narration line in the script contradicted its own numbers on first run
  ("the gradient would vanish" — it is attenuated 12×, not deleted); corrected before
  transcribing, per the standing rule about reading what a diagnostic actually printed.
- **2026-08-31 (Fix F1 — Pending 9 and 10 both DONE, test-first, `verify_saliency_loss_cell.py`
  3/6 → 6/6)** — Wrote the check **before** the fix so it had to earn its keep by failing,
  and it did: **3/6 on the unfixed code, failing exactly the three assertions D4 and D5
  predicted** (A SOLVED 0.5032, C PROPORTIONAL spread 50.0×, D EXPLICIT `lambda_entropy`
  defaulted), then **6/6** after (A **0.0000**, B 13.8089 > 0.0000, C **1.0000 at every
  score**, D 3 sites all explicit, E scores ⊂ (0,1), F generator/notebook parity). The
  verifier **execs the notebook's own saliency block** — extracted between
  `_sc = outputs['scores']` and `loss = loss +`, with `patch_ink` stubbed so the block's own
  `_tgt` construction is exercised and *asserted*, not bypassed — because a paraphrase would
  verify the verifier. C is the load-bearing one and needs no tolerance: a correctly
  specified BCE satisfies `|d_sal/dz| / |p−t| == 1.0` identically, so it is a closed-form
  target. B is the useful **negative** result: it passes *with* the bug present, so the
  obvious check ("inverted costs more than matched") would have found nothing.
  **The fix is not the one D5 prescribed.** D5 said plain `F.binary_cross_entropy`; that is
  right in value (1.956011 vs the buggy 0.919646) but is on PyTorch's autocast-unsafe list,
  and the block runs inside `torch.amp.autocast` on the T4. Shipped instead:
  `F.binary_cross_entropy_with_logits(torch.logit(_sc.squeeze(-1).clamp(1e-6, 1-1e-6)), _tgt)`
  — same value, `d/dz == p − t` exactly, log-sum-exp stability kept, scorer untouched so all
  three probability consumers are safe. *I could not reproduce the autocast restriction
  locally* (CPU autocast uses bf16 and did not raise); the chosen form makes the question
  moot rather than answered. **Two knobs, both explicit:** `LAMBDA_SAL` 2.0 → **0.5**
  (reasoned, **not** tuned — no run behind it) and `lambda_entropy` **0.0 supervised /
  0.05 unsupervised**, 0.0 because the term is `-H` and after the fix the BCE gradient
  vanishes at `p == t` while entropy's does not, which would make an anti-confidence term the
  binding constraint at convergence. **That makes run 9 a two-knob run, the same thing D3
  criticized in runs 7→8** — written down in advance this time, and `lambda_entropy` is the
  first thing to revert if run 9 disappoints.
  **The fix went into `scripts/make_kaggle_pruning_notebook.py`, not the notebook** — the
  generated file would have been overwritten (new Gotcha, plus F PARITY to enforce it). The
  canonical `kaggle_token_pruning_ocr.ipynb` got one behaviour-preserving visibility edit
  (`lambda_entropy=0.05` passed explicitly in the `else` branch it supplies), applied with an
  asserted `count(old) == 1` and `ast.parse` before writing. Compared all **three** copies of
  `AdaptivePruningLoss.__init__`: **identical**, no defaults drift, and assertion D now fails
  if that changes. **Regression: 9/9 verifiers, 6/6 no-GPU diagnostics, 5/5 tests.**
  **Caught a false positive I had introduced myself.** D4 was built to "go stale loudly" by
  grepping for `binary_cross_entropy_with_logits` — which the fix *keeps* — so it did not
  trip and went on printing `a probability is passed where a logit is expected` against fixed
  code. Rewritten to test the condition (is the argument wrapped in `torch.logit(`?) and to
  exit 0 with a `SUPERSEDED` banner; the new detector was then **falsification-tested against
  four line variants** and flags only the genuinely buggy one. D5 got the same treatment: its
  run-8 weights are frozen as `RUN8_*` constants with the live values read from the notebook
  beside them, since it had been asserting "cell 11 never passes `lambda_entropy`" (no longer
  true) and recommending a fix that was not the one applied. Third Gotcha out of this:
  a staleness guard keyed on a symptom cannot detect its own fix — and a guard tested only
  against the state it was written in is half-tested.
  **Not established: anything about metrics.** No GPU ran. F1 is verified in value, gradient
  and range only; "run 8's numbers are a floor" remains a prediction, and Pending 4's control
  row is now the gate on believing any of it.
  **Housekeeping:** added `scripts/check_agents_md_format.py` — this file is the project's
  source of truth and is hand-edited constantly, so it now has a lint: balanced code fences,
  no ragged tables (escaped `\|` inside cells correctly ignored, fenced blocks skipped), no
  paste debris. Currently **18 fences balanced, 20 tables, 0 ragged, 0 debris** (line count
  omitted on purpose — it goes stale on every edit, which is the kind of claim this file
  should not carry). *Those counts are a snapshot at F1, not a running total — the table
  count has grown since; only the three zeros are invariants.*
  Falsification-tested against a deliberately broken file rather than trusted for exiting 0.

- **2026-08-31 (Fix F2 — Pending 4 DONE in code, test-first again, `verify_harness_control.py`
  33/33 after 0/1).** Gave cell 15 a control that holds the **weights** fixed rather than the
  setting: load `RESUME_CKPT` (the run-5 weights that produced 77.74/64.70/53.05), eval one
  `keep=1.00` row through the identical `run_selection_eval`, compare to `RUN6_REFERENCE`,
  restore the swept weights, then sweep. Runs 7–8's `keep=1.00 router CONTROL` had quietly
  become a two-variable test — retraining before it ran meant its drift could not separate a
  broken harness from a changed checkpoint, so +0.51 was *read* as "the retrain raised the
  ceiling" without being able to show it. Now the pair is diagnostic: harness verified + row 0
  drifting = the retrain moved the ceiling; both drifting = measurement, retrain effect
  unreadable. `keep_ratio=1.0` prunes nothing, so the control is independent of every
  selection path it validates.
  **The interesting engineering is in the failure the change itself introduces.** If the
  restore of the retrained weights silently failed, all 15 sweep rows would measure the
  control checkpoint and produce a table with no symptom at all — plausible latencies,
  plausible ordering, wrong weights. So: full-state-dict fingerprint before the swap,
  asserted equal after; both `load_state_dict` calls assert zero missing/unexpected keys (cell
  11 resumes with `strict=False`, so a partial load is a live risk, and it would present as a
  *control reading* from a partly-random model); and the restore is ordered **before** the
  drift report so its assert fires while the cause is still on screen. Also asserted: the
  control load must actually *change* the weights, or it is not a control.
  **The fingerprint covers every parameter on purpose** — first/middle/last of a sorted Donut
  state dict are frozen Swin tensors, so the cheap sampled version would compare equal across
  two different checkpoints and pass vacuously. Proven by mutating each unsampled parameter in
  turn: 0 blind spots. New Gotcha.
  **One judgment call, recorded so it can be reversed:** a *drifted metric* **warns and
  continues**, stamping `harness_verified: false` into the JSON at both write sites, because a
  harness offset kills absolute quotes but not row-to-row comparisons — and rows-to-each-other
  is what Q1/Q2/Q4 ask. Halting would spend a scarce GPU session to learn one column is
  unquotable. A *structural* failure (bad keys, no-op load, wrong restore) does raise: warning
  is for "this number is not comparable", raising is for "I do not know what I just measured."
  The verifier asserts `assert harness_verified` is *absent*, so flipping metric drift to
  fail-fast trips it and forces the decision back into this file.
  **Verifier written first and observed failing** (`0 passed, 1 failed`) before the patch:
  12 static + 18 execution + 3 fingerprint checks, and the execution half `exec`s the block's
  source straight out of the notebook JSON against a stub `nn.Module` with a faked
  `torch.load` — seven scenarios including five that must raise. Run against **both**
  notebooks, 33/33 each.
  **Applied to the canonical notebook** via `scripts/patch_notebook_harness_control.py`
  (5 anchors, each asserted to match exactly once, `ast.parse` before write, idempotent),
  because the generator rewrites only cells 2/9/11 — confirmed post-regeneration that cells
  differing = `[2, 9, 11]` and cell 15 is string-equal across the two files. Guarded with
  `globals().get(...)` so the canonical notebook, which has no `DO_TRAIN`/`EVAL_CKPT`, skips
  the block (correctly — `model` there still holds run-5 weights) and records why in
  `harness_note`. My first patch attempt asserted `import torch` in cell 15 and failed: the
  cell uses cell 2's ambient torch, so the precondition was wrong, not the notebook.
  **Cost is measured, not estimated:** `run 7`/`run 8` row 0 ran 3240/3082 ms/img at
  n=50 ⇒ **2.6 min on a ~37-min sweep (+7%)**.
  **Not established: anything about metrics.** No GPU ran. Whether run-5 weights *do*
  reproduce 77.74/64.70/53.05 under today's transformers is the open question F2 makes
  askable — a failing control on run 9 would be a finding, not a bug in F2. The 0.5-pt
  tolerance is inherited from the old row-0 check and has never been calibrated against
  measured run-to-run variance; it is a convention, not a gate.
  **Corrected a false claim in this file while regressing F2:** the Gotcha on running tests
  said all five exit 0 when invoked directly and named only `test_modules.py` as needing
  `PYTHONPATH`. Measured: bare invocation is **3 pass / 2 fail** (`test_tome_correctness.py`
  imports `src.tome` too); `PYTHONPATH=.` gives 5/5. The two reds surfaced right after a
  notebook edit and read as breakage from it — before believing that, check the test was green
  under the *same invocation*, since "it passed last time" is not a control if last time used a
  different command.
  **Regression: 10/10 verifiers, 6/6 diagnostics, `check_agents_md_format.py` clean, 5/5 tests.**
  **Then, writing the run-9 launch steps, found F2 would have been inert on the run it was
  built for.** Cell 2 ships `RESUME_CKPT = None`, which makes `_ctrl_ckpt` `None` and sends
  the block down its "checkpoint not found" branch — one skip line in a log with hundreds,
  no failure, no control. Setting `RESUME_CKPT` is step 1 of run 9, not a convenience. Found
  by tracing the flags across cells 2 → 6 → 7 → 8c instead of reading the block alone, which
  also surfaced a near-miss worth recording: `EVAL_ONLY = bool(RESUME_CKPT)`, and cell 6
  skips building the train set when `EVAL_ONLY` — so setting the path *could* have starved
  the training run of data. It does not, because the guard is `EVAL_ONLY and not DO_TRAIN`;
  the generator had already handled it. Verifier gained section 4 (cross-cell contract,
  39/39 generated / 36/36 canonical) and this file gained a **Run 9 launch checklist** with
  the four log checkpoints to watch and a written-down prediction that can be falsified.
  **General form: a block that reads its config from `globals().get(...)` cannot fail loudly
  when the config is missing — skip-safe and fail-loud are in tension, and choosing
  skip-safe makes the launch procedure load-bearing.**

- **2026-09-01 (Run 9 executed; F2 passes at 0.00 pts; F1's prediction falsified; new
  Diagnostic D6)** — Analysed `run 9/`. **F2 worked**: the harness control reproduced run 6
  bit-for-bit (77.74 / 64.70 / 53.05, drift 0.00), printed `weights restored and
  fingerprint-verified`, and stamped `harness_verified: true`. Row 0's 1.09-pt drift is
  therefore the retrain and nothing else — the first anchored absolute numbers in this
  project, and Pending 4 is now DONE *and verified*, not just DONE in code. The launch
  checklist's six watch-points all printed as written, including `Resumed … (missing=0,
  unexpected=0)`.
  **My pre-registered prediction is falsified and left in place, struck rather than edited.**
  I predicted `keep=0.50 router` ≥ 80.17 with the oracle gap narrowing; measured **79.63
  (−0.54)**, gap narrowing only because the oracle *rose* 2.10. Instructive shape of the
  error: the first clause was right (retained ink 0.790 → **0.922**, so the double sigmoid
  *was* binding on how well the router fits its objective) and the second did not follow
  from it. The unstated assumption was that fitting the ink objective better makes the OCR
  better. **D4's "run 8's 80.17 is a floor" is now falsified — it was near the ceiling of
  what ink supervision can reach.**
  **New Diagnostic D6, and the most valuable thing in the run, obtained for free by
  re-reading it against run 8.** Seven of 15 rows had `Δretained_ink = 0.000` — byte-identical
  selection — because `ink`/`random` derive their ranking from the image or a fixed seed, and
  `src/router.py:92` gates STE score-scaling on `self.training and use_ste and select_scores
  is None`, so at eval the kept tokens are a bare `gather` and scores never scale them. Those
  rows vary the *weights* alone. They went **−0.94 at keep=1.00 and +0.64…+3.36 at every
  pruned budget**: the decoder specialised further to reduced-token input, regardless of the
  rule producing the tokens. Netting that ≈+2-pt baseline out of the router rows **reverses
  the sign of F1's effect on selection**: +1.9 at keep=0.75, **−2.5** at 0.50, **−3.9** at
  0.35 — worst where retained ink moved most. **This upgrades D2 from a broken correlation to
  an intervention: optimising the ink proxy harder actively costs accuracy.** Corroborated by
  the ink oracle now *beating* the router at keep=0.35 (77.60 vs 75.85; run 8 had the router
  +3.56 there). Caveat recorded: the subtraction assumes additivity, which the ink/random
  rows support at keep=0.50 and 0.75 (within ~0.3 pt) but not at 0.35 (2.7 pt apart), so
  −3.9 is the softest figure; the *signs* do not depend on it.
  **Corrected two numbers this file had been asserting.** The efficiency claim: −65% tokens
  buys **−4.1%** wall-clock and −50% buys **−3.0%**, not the −7% recorded since D3. Run 9
  also supplies a second mechanism beyond post-encoder pruning — `mean_gen_tokens` *rises*
  as the budget falls (251 → 270 → 271), so pruning cuts cost per decoder step while adding
  steps. That one would survive moving the router before the encoder, which makes Pending
  8(b) less attractive than it looked.
  **Caught myself about to report a falsification I had not verified.** `Avg Loss 0.3091 |
  CE 0.3091`, identical for five epochs, looks exactly like "the saliency term never ran".
  Reading cell 11 showed `epoch_loss` accumulates `loss_dict['loss']` while
  `LAMBDA_SAL * _sal` goes to a different variable, and both aux lambdas are 0.0 in the
  supervised branch — so the columns are identical **by construction** and say nothing
  either way. `SUPERVISE_SALIENCY=True` ⇒ `LAMBDA_SAL=0.5` in the executed notebook, so the
  term did run. **The log cannot distinguish `LAMBDA_SAL=0.5` from `LAMBDA_SAL=0`**, which
  means F1's central claim has never been observed directly in any run → **new Pending 11**
  (log `_sal`; do it before item 5's 2×2 or that run inherits the blind spot).
  Also: my earlier "Q3 was skipped, `min_line_cov` is None on every row" was **wrong** — the
  row key is `mean_min_line_cov` and the data is complete. Both mistakes are now Gotchas.
  Q3 answered incidentally: coverage does not order the rows (router wins at keep=0.50 with
  0.601 vs the oracle's 0.955, loses at 0.35 with 0.392 vs 0.739), so D2's retracted second
  half stays retracted — but the 0.4 neighbourhood looks like a *floor* worth respecting.
  **Two more pendings opened:** 12 (rename `results{,_2,_3}/` → `run 6/7/8/`; run 9 settled
  the convention and the current digits are off by one against the run numbers) and **13
  (find a training target that is not retained ink — now the central open question,
  with "drop the auxiliary term entirely" as the cheapest falsifiable first move)**.
  Settled cheaply from the same artifacts: stratified selection is not the answer (73.13,
  *down* from run 8's 75.80); the sign fix holds decisively (79.63 vs negated 15.65);
  `repetition_penalty=1.3` costs 24 pts for the third independent time; `min_new_tokens`
  is inert to every decimal. The `keep=0.50 > keep=0.75` anomaly collapsed from 4.98 pts to
  0.22 and no longer needs an explanation — it was never a robust effect.

- **2026-09-01 (Fix F3 — Pending 11 DONE, test-first, `scripts/verify_training_telemetry.py`
  1/6 → 6/6).** The training log can now distinguish `LAMBDA_SAL=0.5` from `LAMBDA_SAL=0`.
  Wrote the verifier first and it failed for exactly the intended reason: `I DISCRIMINATING`
  printed byte-identical epoch lines at the two λ values — run 9's defect stated by the check
  rather than by me. It **extracts cell 11's epoch loop from the notebook and executes it**
  against a real `AdaptivePruningLoss`, a real `torch.amp.GradScaler`, and an AdamW subclass
  that snapshots the scorer gradient before the loop zeroes it, so the assertions are about
  the code that runs on Kaggle, not a paraphrase. The one pre-patch pass was `K GRAD INTACT`
  (|grad| 0.109 at λ=0.5, exactly 0 at λ=0) — the term always reached `backward()`, and that
  assertion is the one that matters *after* the patch, because "make the number visible" is
  the kind of change that gets written with a `.detach()` in the wrong place and silently
  switches the term off. Patched the **generator only** (cell 11's `DO_TRAIN` branch is
  generator-created; the canonical notebook has no such branch), regenerated, 6/6, then the
  full suite: 11/11 `verify_*.py` and 5/5 `tests/*.py` exit 0, format check clean.
  New line: `Epoch n | Obj … | CE … | aux … | sal S x<λ> [n/N] | dev … | p M+-S`, with an
  unmistakable `sal OFF (LAMBDA_SAL=0)`. Six columns, each traceable to a specific past
  failure — `Obj` because no printed number equalled what `backward()` minimises (Pending 11
  itself), `aux` because D5's `lambda_entropy=0.05` shaped runs 7–8 while appearing in no
  config cell, `sal` with λ *and* the step count so the knob and the branch firing are both
  in the log, `dev` because after D4 `d(sal)/dz == p − t` exactly so it **is** the gradient
  magnitude, `p ±std` because std → 0 makes `torch.topk` return the first K indices and look
  structured while learning nothing.
  **My own checker was wrong before the code was.** `L PARITY` reported a divergence that did
  not exist because cell 11 contains **two** epoch loops — the generator wraps the original
  body as the `else` branch — so a whole-cell regex compared the else branch's print against
  the generator's `DO_TRAIN` branch. Fixed by extracting both sides the same way, not by
  loosening the assertion until it passed. Worth remembering that when a parity check fires
  the instinct is "the files diverged", and here it was the check.
  **Found while verifying, unplanned:** `aux` came out **negative**, which sent me to
  `src/loss.py:69` — `entropy_loss = -entropy`, so `lambda_entropy`'s contribution is ≤ 0
  always and *lowers* the reported loss. Measured its gradient across five score values: it
  pushes scores **toward 0.5 from both sides**, i.e. toward the constant-collapse state the
  new `p ±std` column exists to detect. Small (|d/dz| ≈ 0.0014) and competing with
  `lambda_sparsity=2.0` in runs 7–8, so *not* a claim those runs collapsed — but a pressure
  that was invisible twice over: missing from the config cells and loss-*reducing* in the log.
  Both facts are now Gotchas so a future reader does not "fix" the negative `aux`.
  **Unblocks Pending 5 (co-adaptation 2×2) and Pending 13(a) (drop the auxiliary term
  entirely)** — both need to read the saliency loss during training and neither was runnable
  before this.
- **2026-09-01 (D7 + D8 + D9 — Pending 13 resolved: (a) dead, (b) cleared to build).** Three CPU
  diagnostics, all built to kill a candidate cheaply rather than to justify one.
  **D7 killed 13(a).** Run 7's two auxiliaries were a minority of the router's gradient at every
  weight point and split measured (2.5–17.2%), so run 7 was already predominantly STE-driven —
  and its forward router scored 18.80 recall. Deleting a ≤17% minority does not turn that into a
  good router. The reframe matters more than the verdict: CE-through-STE is *large* (8–30× the
  auxiliaries by norm) but **incoherent** across pages (cos 0.21) while ink-BCE is smaller-to-
  larger but **systematic** (0.85–0.90), and displacement scales as norm × coherence. Plus the
  STE reaches exactly K of N tokens — measured, 2400 of 4800 — so the dropped half is
  structurally unreachable by *any* task loss. What ink supplied was never correctness (D6
  refuted that) but three properties the task loss cannot supply: **dense, coherent, free**.
  **D8 then D9 cleared 13(b)** against four pre-registered thresholds: attention is not ink
  (r **+0.083**), not a fixed positional mask (top-5% centroid spread 6.12 grid rows vs ink's
  1.81), reachable by the existing scorer (held-out AUC 0.976 vs a shuffled floor of 0.498), and
  not merely its own page-invariant component (**lift +0.212** over a constant map, against
  ink's +0.151). Best single motivator found along the way: **`r(attn, router score) = −0.045`**
  — the router is not just anti-correlated with ink, it is *uninformed* about what the decoder
  looks at.
  **Both green results needed a second test I had not pre-registered, and I nearly shipped both
  on the first number.** D8's Test 1 thresholds ("not ink") are passed *perfectly* by a constant
  mask — the tell was two unrelated forms agreeing to three decimals — so Test 2 had to measure
  cross-page variation with ink as the calibration floor. Then D9's held-out AUC of 0.979 turned
  out to be three-quarters available from a **constant map with no features at all (0.764)**, so
  the reportable quantity became the lift, not the AUC. Same failure mode, one level down, twice.
  **Four self-corrections logged in place**: I published "auxiliaries never exceed 8%" from the
  test split alone and the train split says 17.2% (ink-BCE there is 1.07× CE, so ink was never
  the small term); my split-bias prediction was wrong in *direction*; my run-7-collapse
  hypothesis was falsified twice by my own script (std nearly doubled rather than shrank); and
  `cosine` was the wrong statistic to pre-register a threshold on — it is inflated for
  non-negative vectors, as the router-score row proves at cos +0.83 / r +0.10. Future cross-page
  thresholds go on pearson r.
  **Two independent cross-validations worth trusting**: D8 reproduced D1's `r(score,ink) =
  −0.226` to three decimals from a different script and a different ink implementation, and
  D9's constant-map controls independently confirmed D8's centroid finding that **ink is the more
  page-invariant of the two targets** (constant ink map 0.775 > constant attn map 0.764).
  **Nothing here establishes that 13(b) works** — every number is scored against the teacher's
  own attention, which is close to tautological. D6 remains the standing warning that fitting a
  proxy harder cost accuracy at two of three budgets. The acceptance criterion is recall at
  keep=0.50/0.35 against run 9, and the build plan in Pending 13 says so explicitly.
  Also: a Gotcha for the way this build is most likely to fail silently — under transformers 5.x
  SDPA, `output_attentions=True` returns `None` rather than raising, so an all-zero target
  trains without complaint. Both scripts assert instead of trusting.
  **Regression suite after the edits: 16/16 green** (11 `scripts/verify_*.py` + 5 `tests/*.py`,
  exit 0). Run because D8 and D9 both `import` from `scripts/diagnose_ste_signal.py` and I edited
  it (the split-label fix) — a shared-import edit is exactly the change whose blast radius is
  wider than the diff.
- **2026-09-02 (Pending 13(b) BUILT and verified BY EXECUTION; suite 17/17).** Four generator
  edits put the cross-attention target in the notebook behind `ATTN_TARGET = False`, so run 9
  still reproduces exactly. New `scripts/verify_attn_target.py`: **41 checks green** (34 fast,
  +7 under `--real` on run 5 weights and a real 4800-token FUNSD page). Details in Pending 13.
  The point worth carrying forward is that **the generator reported "all code cells parse" and
  four real defects were still present** — the parse pass is what [[verify-patches-actually-run]]
  says it is, necessary and not sufficient. Executing found: cell 7 NameErrors without cell 4
  (resolves at call time, invisible to `ast.parse`); `if ATTN_TARGET:` turned a bound name into
  a free variable in **two other verifiers** that `exec` cell 11's saliency block, breaking a
  suite that had been 16/16 (fixed by binding it in both harnesses); and my new degeneracy
  assert was wrong in **both** directions at once — too weak for the ATTN branch, where top-K
  makes `rate == K/N` exactly, and too strict for INK, where a legal all-blank first page would
  have killed a 4-hour run at step 0. A **pre-existing test found that** by driving the block
  with a single-element target, so the fix is a better guard rather than a worked-around test.
  Two estimates in this file were replaced by measurements: the attention tensor is **294 MB**
  (not ~314 MB) and pad truncation halves it, since real labels are **239/512 tokens**.
  **And one recorded premise needed correcting:** D8's r(attn, ink) = +0.083 reproduces
  (+0.107 over 4 pages) but describes the *continuous* maps — the binarised target that actually
  gets used overlaps ink top-K at **0.632** (r_bin +0.265), and the correct null for that
  statistic is not 0.500 but **0.667**, which is what a content-free interior prior scores
  against ink. Cosine inflation from D-A, on a new statistic. 13(b) survives; the "genuinely new
  information" framing does not survive intact, and the file now says so where it made the claim.
- **2026-09-02 (D10 + selection telemetry + run 10 prepared; suite 17/17, 41/41 on `--real`).**
  Three things, all pointed at making run 10 *interpretable* rather than merely runnable.
  **(1) D10 — `scripts/diagnose_target_drift.py`** closes the last open precondition for 13(b),
  which I had flagged as unverified and had explicitly noted the weight-drift numbers did
  **not** bound. Run 5 → run 9 is a completed 5-epoch retrain under the identical
  `UNFREEZE_STAGES = 1` config, so the drift was already on disk: encoder *features* move
  **7.6× further than the weights** (median rel-L2 **0.0918** vs 0.0120 — the gap that made
  measuring necessary), yet the recomputed top-K target keeps **S = 0.9613** of its positives
  against a different-pages floor of **X = 0.6246**, gap **+0.3367**, with both thresholds
  written into the script before any output was read. `X = 0.6246` is also a **third
  independent estimate of the ≈0.63 inflated null** for top-K overlaps on this grid, from a
  construction unrelated to the interior prior — so any overlap in this file read against
  0.500 is overstated by ≈0.13. **(2) Selection telemetry.** The epoch line gained `ov` /
  `ch` / `lift`: the fraction of the target's positives the router's own top-K keeps, the
  random baseline for it, and the difference — computed inside the existing single `.tolist()`
  sync. This exists because run 9's worst outcome was not "recall fell" but "recall fell and
  the log could not say why": F3 made the loss *value* readable and left **selection**
  unobservable, which is the ambiguity D6 had to be reconstructed around. `verify_training_telemetry.py`
  is now **8/8** — case M inverts the target and requires `ov` to move (1.000 → 0.000),
  because `ov 1.000 ch 0.500 lift +0.500` is exactly what a hard-wired column would print.
  Two defects that a green line would have hidden: the harness's parser silently dropped
  `lift +0.500` (its value pattern was `-?\d+\.\d+`, so the check would have passed on a
  `.get()` default instead of on the log), and `L PARITY` did not name the new `_tgf`/`_rk`/`_st`
  lines, so a regeneration could have reverted the telemetry with parity still green.
  **(3) Run 10 is specified** — see its launch checklist, one variable (`ATTN_TARGET = True`),
  pre-registered acceptance with the noise caveat stated up front (**nobody has run this config
  twice, so |Δ| < 1 pt at a single budget is not a result**), and a prediction that is
  deliberately not optimistic. While writing it: cell 2's `PLAN:` line had a **missing `f`
  prefix** and printed the literal `keep_ratio={TRAIN_KEEP_RATIO}` through run 9, and
  `ATTN_TARGET` — the entire variable of run 10 — **appeared in no cell-2 output at all**,
  which is D5's invisible-knob failure waiting to repeat. Both fixed; there is now a `CFG:`
  line naming every knob that shapes the run. Two stale counts in the verifier index were
  corrected against actual runs (harness control 33 → **36**, attn target 33/40 → **34/41**),
  and one of those 41 passes is now labelled as nearly non-discriminating: *"target is not ink
  in disguise"* clears its own content-free floor by only **0.678 vs 0.654** on one page, and
  the sign of that comparison **reverses** between pages — so the count is not 41 equally
  strong claims.
- **2026-09-02 (run-10 pre-flight: the composition EXECUTED, 10/10; suite 18/18).** Before
  spending ~6 GPU hours I closed the one thing nothing had run. Every 13(b) check tested a
  *piece* — `verify_attn_target` the target function alone, `verify_saliency_loss_cell` the
  loss with a **lambda** teacher, `verify_training_telemetry` the loop on the **ink** branch
  with a **stub** model, D10 the target outside any loop — and **no check had ever run model
  fwd → `visual_tokens` → real frozen teacher → top-K target → BCE → scaled backward →
  optimizer step.** That is precisely the defect shape "verify it *runs*, not that it parses"
  exists for. `scripts/verify_attn_train_step.py` slices cell 11's DO_TRAIN **prologue (40
  lines)** and **training body (181 lines) verbatim** out of the generator — so the optimizer,
  criterion, `LAMBDA_SAL`, scaler and loop are the shipped lines, not a paraphrase I'd have
  written to agree with itself — and runs them on 2 real FUNSD pages with run-5 weights and
  `ATTN_TARGET=True`. **10/10 in ~25 min CPU:** teacher's 110 params bit-identical after
  training, all 6 router tensors moved (so the update was *applied*, not scaler-skipped),
  `ch == K/N` exactly, Swin drift `[0,0,0,33]` (so `UNFREEZE_STAGES=1` is *executed*, not read
  off a flag), and the target still exact-K when recomputed from the **drifted** encoder.
  **Three defects, none visible to a parse or a grep. (1) Cross-cell name coupling:** cell 2
  does `import gc`; cells 7 and 11 call `gc.collect()` without importing it. Harmless on
  Kaggle (one namespace) but it fires *inside* `AdaptiveDonutOCR.__init__`, i.e. after a 200M
  backbone loads. Fixed in the harness by seeding the namespace from cell 2's own
  `Import`/`ImportFrom` **nodes** rather than a list of names I remembered, with an assert so
  the day cell 2 drops `gc` is reported as a real defect — see the Gotcha, and do **not**
  "fix" it by adding `import gc` to cells 7/11. **(2) `python foo.py | tee log` reports
  *tee's* exit status:** the first attempt died on that `NameError` and was reported as
  **"exited with code 0"**. A suite loop keyed on `$?` would have scored the crash as a pass.
  **(3) Run 10's most likely misconfiguration cost 20 minutes instead of 1:**
  `ATTN_TARGET=True` with `RESUME_CKPT=None` was caught only by cell 11's assert — *after*
  Cell 6's ~19-minute download — while cell 2 already validates `RESUME_CKPT`'s path for
  exactly that reason. Moved both pairing asserts (`RESUME_CKPT` present, `SUPERVISE_SALIENCY`
  on) into cell 2; regenerated with the diff confined to those **+15 lines**, all 16 other
  cells byte-identical. The gate is driven against **all four** states — run 9's config must
  still pass untouched, both misconfigurations must raise, `ATTN_TARGET=True` + a real
  checkpoint must pass. Two harness bugs found by the same standard: `re.sub` with a **string**
  replacement interpreted `repr()`'s Windows-path `\U` as an escape (`SyntaxError`), and a
  silent no-substitution would have run every scenario against the **shipped defaults** and
  passed — now `re.subn` with `n != 1` fatal. Also corrected an overstatement of my own:
  `fingerprint` summed `|p|` in float32, and I claimed that would report bit-identical. I
  measured it instead — one AdamW step at lr=1e-5 shifts `sum|p|` by only **2.2e-7 / 4.8e-7 /
  5.2e-7 relative** on three representative shapes, i.e. **2–5 ULPs**, and float32 **did**
  resolve all three. So the check was not broken, it was *lucky*; float64 now removes the
  dependence on which way the sum rounds. The fast path (6/6: anchor resolution, the cell-2
  import contract, the 4-way gate) stays in the suite because string anchors into generated
  code are exactly what rots; `--full` is opt-in. **What this does not say:** the pre-flight's
  one step on two pages printed `ov 0.404 ch 0.500 lift −0.096` — *negative* lift, which is
  what one step should look like and is **no evidence either way** about run 10's outcome.
  Acceptance is still recall at keep=0.50/0.35 vs run 9.
- **2026-09-03 (RUN 10 EXECUTED — 13(b) is a null, and the null is explained).** Full readout
  in "Run 10 — result". **The auxiliary fit better than anything in this project** (`ov` 0.798
  → **0.930** against chance 0.500, `lift +0.430`, `p` std *rising* 0.330 → 0.428 so no
  constant collapse, router weights median rel-L2 **0.3245** from run 9's) **and recall did not
  move**: −0.22 at keep=0.50, +0.49 at 0.35, −0.06 at 0.75, every one inside the ±1 pt floor
  pre-registered before the run, with inconsistent signs. D6's pattern, sharper — D6 was
  "fitted harder, accuracy fell"; run 10 is "fitted *much* harder, accuracy flat".
  **The result that matters is not the delta.** The router's `retained_ink` collapsed **0.922 →
  0.675** at keep=0.50 and **0.826 → 0.511** at keep=0.35 — it now keeps barely more ink than
  *random* (0.349) — with recall flat. That is a **third independent line** killing retained ink
  as an objective (D2 correlational → D6 interventional → run 10 with a wholly different
  objective), and it means ink-coverage numbers must never again be quoted as evidence a
  selection is good. **And the null was structurally guaranteed:** `keep=1.00` scores **77.32**
  while `keep=0.50` scores **79.41** — pruning to half the tokens *beats* not pruning by +2.1 pts,
  reproduced independently in run 9 (+2.3). At keep=0.50 the budget is **not binding**, so no
  selection objective could have won there; this was visible in run 9's own rows before run 10
  was launched. The `router − random` gap locates where selection actually pays: +5.8 at
  keep=0.75, +14.0 at 0.50, **+27.8 at 0.35** — so keep=0.20–0.35 is the only regime where the
  question is well-posed, and it is the only budget where 13(b) was positive. **Verified the
  "one variable" claim by diff rather than by trust** (new practice, do it every run): both
  runs' executed notebooks live in their own zips, and the *only* removed lines in the entire
  notebook are the three ink-target lines plus two logging lines — loss, all three LRs,
  `GRAD_ACCUM`, epochs and the data pipeline byte-identical, cell 4 purely additive. That diff
  also **cleared a scare that would have voided the comparison**: run 9's log reads `Avg Loss
  0.3091 | CE 0.3091` with no `sal` column, which reads exactly like an unsupervised baseline —
  but run 9's *executed source* has `SUPERVISE_SALIENCY=True`, `LAMBDA_SAL=0.5`,
  `_tgt = (_inkn > SALIENCY_THRESHOLD)` and the term added to `loss`. Run 9 ran the **pre-F3**
  notebook whose `epoch_loss` accumulated CE only — the exact defect F3 fixed, resurfacing as a
  false alarm one run later. **Two things logged as open rather than explained away:** the ink
  ORACLE row fell **8.93 pts** at keep=0.35 (77.60 → 68.67) on a *bit-identical* token selection
  (`retained_ink` 0.950 both runs), monotone in pruning aggressiveness — but `random` at
  keep=0.50 *improved* +2.86 on an equally identical selection, so "run 10 co-adapted and is
  more specialised" does not predict both signs and is not adopted. Harness anchored
  (`harness_verified: true`, run-5 weights reproduce run 6 within 0.00 pts); `control_drift_pts
  0.98` is by cell 16's design the *retrain's* effect on the unpruned ceiling, not measurement
  error (run 9's was 1.09). Both runs are training-saturated (CE → 0.0414 and 0.0383 over 1692
  steps/epoch × 5), which caps what any objective tweak can do. **The pre-flight's scope limit
  held up exactly:** its one-step `lift −0.096` was recorded as "no evidence either way", and
  the real run's `+0.430` confirms it measured mechanism-liveness, not outcome —
  [[measure-mechanism-and-goal-separately]] in its purest form yet.
- **2026-09-04 (D11 — 13(b) is DEAD, selection objectives are closed, and Pending 8 is settled
  against the deliverable).** Built `scripts/eval_budget_binding.py` and ran it at `--n 50`
  (182 min local CPU, EXIT=0, all 10 controls pass). It re-asks 13(b) at budgets that *bind*,
  **paired** on the same 50 images so the answer carries a real SE instead of the eyeballed
  ±1 pt floor. **The attention target does not tie — it LOSES: −5.63 pts at keep=0.25
  (SE 2.35, t −2.40) and −12.81 at keep=0.20 (SE 2.06, t −6.23)**, monotone in tightness
  (+0.20 → −3.84 → −5.63 → −12.81). **Mechanism, and it is the whole result:** run 10's router
  retains ink **0.355** at keep=0.25 and **0.257** at keep=0.20 against a `random` floor of
  0.251 / 0.201 — supervising on the frozen decoder's cross-attention produced a
  **near-ink-agnostic** selector, harmless while the budget is slack and ruinous once every
  token must carry text. Its `router − random` headroom *shrinks* exactly where it should not
  (+33.95 → +23.24 at keep=0.25). So **selection objectives are finished on this setup**: ink
  supervision was already dead on three lines, attention supervision is now actively worse,
  and both remaining Pending-13 candidates were variants of "supervise on a better per-token
  target". Run 11 as sketched is cancelled; the pruned-grid teacher-attention idea is retired
  with it (the target was not measured on the wrong grid, it is the wrong thing to select on).
  **Corrects the run-10 diagnosis:** keep=0.35 is *also* non-binding on run 9 (79.25 vs a 77.62
  ceiling, **+1.62**), so **both** of run 10's headline rows were unwinnable, not just
  keep=0.50 — the budget first binds at keep=0.25. **Pending 8 settled, and worse than any
  earlier figure:** 4800 → 960 visual tokens (**5×**) buys **1.04×** wall-clock, max 1.05×
  across ten rows; generation is decoder-bound (243–280 steps, encoder runs once) so pruning
  shrinks only the cross-attention KV. The old "−3.0% / −4.1%" numbers were single-budget
  latency *increases*; latency is in fact flat to within noise at every budget, so **any
  latency or throughput claim is false** and option (a) is the only true one.
  **The two controls this script shipped with were unsound and were rebuilt before the real
  run — the reusable lesson, written up under the verifier index.** The n=2 smoke run exited 0
  with a green control and a confident verdict, and both were misleading: (i) the gate compared
  the local recall delta to Kaggle's within 2.0 pts and *passed on two images*, because
  Kaggle's own delta has an unknown SE so "agrees within 2 pts" decodes to "both consistent
  with zero" — replaced by `retained_ink`, which is near-deterministic given the weights and
  came back **exact to three decimals on all six gates**; (ii) the verdict branch printed
  "INDISTINGUISHABLE … a null" while the paired SE was 8.88 and 14.34 pts, i.e. it could not
  tell *"we looked and saw nothing"* from *"we could not have seen it"* — fixed with a
  pre-registered `MIN_EFFECT_PTS` and a printed `t_crit × SE`, so a flat result now reports
  **UNDERPOWERED**. A third control was added because the smoke run showed it was free:
  `random`-mode ink must be identical across checkpoints, and it came back `0.00e+00` at all
  four budgets, upgrading "paired" from intention to measured fact. **An unplanned payoff:**
  the ink gates being exact while recall drifts *separates selection from generation* —
  keep=0.35 has bit-identical ink to Kaggle yet 3.40 pts more recall, so selection reproduces
  across device/transformers version and generation does not, with the drift widening as the
  budget tightens (+0.32 / +0.83 / +3.40). **Three caveats kept on the record, not waved
  away:** the pre-registered power criterion (3.0 pts) was met at *no* budget (SEs 1.58–2.35,
  detectable 3.15–4.70), so this run could not have returned a trustworthy *null* — the two
  verdicts stand only because a detected effect at |t| ≥ 2 is detected regardless; local and
  Kaggle **disagree on the sign at keep=0.35** (−3.84 vs +0.49, gap 4.33) on identical ink, the
  one result here that does not reproduce, which matters because keep=0.25/0.20 were never
  measured on Kaggle; and the keep=0.25 row (t −2.40, barely over 2.0) is the weak member and
  must not be quoted without keep=0.20 beside it. **What the deliverable now is:** not the
  router. At keep=0.35 run 9 discards **65% of visual tokens and scores +1.62 over its own
  unpruned ceiling** — a larger claim than the keep=0.50 version quoted elsewhere in this file,
  and the one to lead with, with the efficiency framing restricted to token count and the
  "why does pruning help" question still open and untested.
- **2026-09-04 (later) — `REPORT.md` written and `README.md` reconciled.** The README had
  been flagged stale at the top of this file since it was created; it is now rewritten
  against the current state. Four things in it were not merely out of date but **actively
  false**, and are worth listing because three of them would have been believed:
  (i) it documented training on **SROIE**, which this project deliberately excludes — the
  `src/` CLI defaults had already moved to `nielsr/funsd`, so the docs and the code
  disagreed and only the docs were read; (ii) it advertised a `--freeze_backbone` flag for
  low-VRAM machines that **does not exist** in `src/train.py` (grep: no match) — a
  copy-pasteable command that fails on argparse; (iii) it sold "**reduce visual token
  redundancy by 70–80%**" as the headline, which is the exact efficiency framing D3 and D11
  retired; (iv) it presented `src/` as the thing that produces the results. That last one is
  the most misleading of the four now: `src/loss.py` has **no saliency term at all**, so
  `src/train.py` cannot reproduce runs 8–10 — the mechanism behind every current number
  lives only in `kaggle_pruning_run.ipynb` and its generator. The rewrite states all four
  corrections up front, and carries the ToMe-never-ran and 1.04×-wall-clock caveats above
  the results table rather than below it. **Both new files state that this file wins on any
  disagreement** — a summary that outranks nothing cannot go stale dangerously, which is the
  failure mode the old README demonstrated for ten runs.

---

## Kilo (tencent/hy3:free) — contributions (2026-08-29)

Local-CPU work only (no GPU/checkpoint needed). Two additive changes; both run green.
Attributed so changes are distinguishable from Claude's: **Kilo (tencent/hy3:free)**.

- **`tests/test_tome_correctness.py`** — 4 tests, all pass. `test_modules.py::test_tome_merger`
  only asserted output *shapes*; because every real run sets `merge_ratio=0.0`, ToMe's
  actual merge logic had never been exercised (the "has NEVER EXECUTED" gotcha). New
  tests cover: merges near-identical pairs into one coherent vector; leaves
  well-separated clusters intact (M == K - r); computes coordinate centroids inside
  the input bounds; and is order-sensitive (the property the parity gotcha rests on).
- **`scripts/diagnose_tome_parity.py`** — D1/D2-style diagnostic that *quantifies* the
  ToMe parity gotcha (Gotchas: "partitions by score-rank parity, not spatial
  adjacency"). Builds features with one identical vector per declared redundant pair
  and measures the **missed-redundancy rate** — the fraction of genuinely-redundant
  token pairs ToMe fails to merge because both endpoints land in the same bipartite
  set (ToMe only merges A→B):

  | ordering | missed redundancy |
  |---|---|
  | spatial (docstring assumption) | 0.0% |
  | router-sorted (actual pipeline) | 49.2% |
  | random permute (control) | 49.6% |

  **Finding.** Once the router scores and `topk(sorted=True)` reorders the sequence,
  ~half of all truly-redundant tokens strand in the same A/B half and can *never* be
  merged. So ToMe, as wired, does not "compact continuous text regions" — it merges
  by score-rank neighbourhood. This is directly relevant to **Pending 1c's still-
  outstanding `merge_ratio` rows**: the merge sweep cannot be read honestly until
  this is resolved.

  **Recommendation (NOT applied — architecture change, needs a GPU/Kaggle patch like
  Phase 2d).** Either (a) pass `sorted=False` from the router and re-sort the kept
  indices by original position before ToMe, or (b) deliberately accept score-rank
  merging and document it. Must be ported to the notebook via a patcher, since the
  notebook duplicates `AdaptiveDonutOCR` and imports nothing from `src/`.

- **`kaggle_pruning_run.ipynb`** (generated by `scripts/make_kaggle_pruning_notebook.py`) — a
  single runnable Kaggle notebook that does **Pending 1a** (retrain the router WITH
  pruning ON) and then the **Phase 2d** selection-sweep in one Run-All. It copies the
  existing Phase-2d-patched `kaggle_token_pruning_ocr.ipynb` and adds three asserted,
  `ast`-checked edits: a `DO_TRAIN` / `TRAIN_KEEP_RATIO` / `TRAIN_EPOCHS` / `PRUNED_CKPT`
  config (cell 2); a `train_loader` gate so the data cell builds the train set when
  `DO_TRAIN` (cell 9); and a `DO_TRAIN` branch in the training cell (cell 11) that
  builds `AdaptiveDonutOCR(keep_ratio=TRAIN_KEEP_RATIO)`, trains with STE active +
  sparsity loss targeting the real budget, and saves `PRUNED_CKPT`. The downstream eval
  + selection-ablation cells reuse the in-memory `model`, so no further edits are
  needed. Decode defaults verified `rp=1.0 / nrns=3`, so the `keep=1.00` CONTROL
  reproduces run 6 (77.74/64.70/53.05). Set `DO_TRAIN=False` to reproduce just the
  Phase 2d sweep on run-5 weights. The original notebook is left untouched.

- **Bug fix — data cell `test_ds` NameError.** `kaggle_token_pruning_ocr.ipynb`'s
  data-pipeline cell printed `Test samples: {len(test_ds)}` *inside* its `else`
  branch, but `test_ds = DocumentDataset(...)` is defined *after* the `if/else`
  block. So any non-eval-only run (incl. the new `DO_TRAIN` pruning-ON retrain)
  raised `NameError: name 'test_ds' is not defined`. Eval-only runs (run 6) hid it
  by skipping that branch. Fixed in the canonical notebook via
  `scripts/patch_notebook_datacell_testds.py` (drops the forward reference; the
  module-level test-count print remains) and mirrored in the generator, so
  `kaggle_pruning_run.ipynb` regenerates clean. **Lesson applied:** `ast.parse` is
  necessary but not sufficient — patches must be *executed* against stubs, not just
  parsed (the project's standing rule, which I had under-applied here).

- **Sign-fix notebook variant (Run 7 follow-up).** Run 7 showed the STE-only pruning-ON
  retrain left the router **sign-inverted** (forward `router` 18.80 recall at keep=0.5; the
  learned ranking only works when *negated*). Prepared `kaggle_pruning_run.ipynb` (regenerated
  via `scripts/make_kaggle_pruning_notebook.py`) with a `SUPERVISE_SALIENCY` flag that adds a
  **free text-proxy BCE loss**: `F.binary_cross_entropy_with_logits(scores, ink_target)` where
  `ink_target = (patch_ink/std > SALIENCY_THRESHOLD).float()`. The router is now told "text =
  high score" directly, instead of hoping STE discovers it. `SUPERVISE_SALIENCY=True` turns off
  the sparsity-budget loss (BCE handles which tokens; top-k still enforces the count). **Not yet
  run on Kaggle** — the test is whether the ablation's forward `router` rows rise from ~18 to
  competitive with `strat_negated`. If they do, negation-at-inference is no longer needed.

**Why this and not the GPU runs:** Pending 1a (retrain router with pruning ON) and
the Phase 2d sweep both need a GPU/Kaggle session unavailable locally. The ToMe gap
was the one untested component that *is* locally runnable (the diagnostic above), and
the runnable notebook is the artifact that turns the two planned GPU steps into one
Kaggle Run-All. I did **not** modify `src/tome.py` or the original notebook — the
diagnostic and tests are additive, and the runnable notebook is a new file, so the
existing Kaggle workflow is untouched.
