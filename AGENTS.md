# AGENTS.md — AdaptiveDonutOCR working log

**This file is the single source of truth for project state.** Any agent working
in this repo must read it first and update it before finishing a task.

Everything goes here — not just code changes:

- **run results** → a row in the run table, plus a findings entry
- **decisions** → what was chosen and *why*, including the evidence
- **dead ends** → into "explicitly rejected", so nobody retries them
- **diagnostics run** → what was measured and what it showed, even if inconclusive
- **hypotheses** → stated as hypotheses, and struck out when falsified
- **anything surprising** → into Gotchas

If it was worth saying in chat, it is worth writing here; chat is lost at the end
of a session and this file is not. Keep the run table and "Current state" section
accurate — a stale entry here is worse than no entry, because the next session
will act on it.

---

> **Restructured 2026-09-24 — this file was 10,276 lines / 809,072 bytes, auto-loaded in full on
> every session, so its ≈230K tokens were being paid unconditionally.** The historical bulk now
> lives in three archives. **Nothing was deleted** — every line moved verbatim, per the
> strike-and-supersede convention, and a byte-accounting assertion checked it
> (`scripts/split_agents_md.py`). This file still wins on any disagreement with anything,
> including its own archives.
>
> ⚠ Those two figures read ~~8,945 lines~~ and ~~~202K tokens~~ until **2026-09-25**, when both
> were *measured* instead of estimated. Both were **low** — the line count by 15%, the token
> count by 12% — i.e. wrong in the direction that understates the problem. See the 2026-09-25
> changelog entry.
>
> | archive | holds | read it when |
> |---|---|---|
> | `AGENTS-ARCHIVE-DIAGNOSTICS.md` | the full diagnostics index, D1–D14, M1, fixes F1–F3, runs 7–10 sections and their launch checklists | citing any D-number, M1, or an F-fix |
> | `AGENTS-ARCHIVE-RUNS.md` | corpus decision (T2), the T3 re-scoring, the whole `## Pending` item history, runs 11–14 checklists + results, Phase 2c/2d | reading a run's result or a closed Pending item |
> | `AGENTS-ARCHIVE-CHANGELOG.md` | the dated changelog and the Kilo contributions section | reconstructing when and why something changed |
>
> **What stayed here, deliberately:** the TODO queue and resume protocol (two saved memories
> name this file and this section), the four claims, the file map, the eval protocol and run
> table, **the run-17 pre-registration** (the rule the next run is scored against), and
> Conventions + Gotchas (the two sections that are advice for *work about to happen* rather
> than a record of work already done).
>
> ⚠ **The archives are subordinate to this file and go stale the moment a run lands**, exactly
> like the four prose docs. When you correct a number here, grep the archives for the old value
> — `scripts/check_writeup_numbers.py` does not read them.

## ▶ TODO — THE SERIAL WORK QUEUE (read this first, every session)

**Resume protocol.** When the user says *"resume"*, *"what's next"*, *"continue"*, or
starts a session without naming a task: **read this section, report the first unchecked
item, and start there.** One at a time, in order. Do not re-plan from scratch, do not
skip ahead to a cheaper-looking item, and do not run two in parallel — the order encodes
blocking relationships that cost GPU sessions to get wrong. If an item turns out to be
blocked, wrong, or already done, say so and **edit this list**; do not silently skip it.

**Tick an item only when its DONE-WHEN is satisfied by something *executed*,** not by
something written. This file has twice recorded a check as green while the script behind
it was crashing — see `verify_results_provenance.py` (2026-09-22), which was logged as
"35/35 on both notebooks" for 13 days while raising on the notebook that actually
mattered. A verifier that crashes reads exactly like one nobody ran.

**Why this order, as of 2026-09-22.** The merge axis is blocked on the **measurement
instrument, not on ToMe** — see **Diagnostic D13**. ToMe executes and is correct
(`verify_tome_merge_port.py` 89/89, 13/13 correctness tests, token match hard-asserted);
its effects are simply the same size as the harness's resolution. That reorders
everything: Pending 16 and 17, which sat at the top of the Pending table, are now **T6
and T7**, behind four items that cost **no GPU time** and without which 16/17 produce a
fourth consecutive UNDERPOWERED.

| # | task | venue / cost | blocked by |
|---|---|---|---|
| T1 | Write Pending 18's estimator rule | free | — |
| T2 | ~~Confirm the second eval corpus exists and is usable~~ **DONE — SROIE n=347** | free | — |
| T3 | ~~Re-score runs 13/14 under T1's rule~~ **DONE — UNDERPOWERED both runs; claim 3 restated; T1 §3 amended** | free, local | T1 |
| T4 | Port the 28-row sweep to the pooled corpus (FUNSD+SROIE = 397) | local or Kaggle, eval-only | ~~T1, T2~~ **free** |
| T5 | Decide where ToMe lives in the architecture | free, but gates T6/T7 | D13 read |
| T6 | Pending 16 — train `keep=0.30, merge=0.0` | Kaggle T4, ≈4–4.5 h | T4, T5 |
| T7 | Pending 17 — the redesigned merge run | Kaggle T4, ≈2–3 h | T6 |
| T8 | Housekeeping: reconcile the prose docs; dead `final_coords` | local, ~40 min | — (fill gaps) |

---

- [x] **T1 — Write run 17's pre-registration.** *(Rescoped 2026-09-23 by D14: this was
  "write the estimator rule." The estimator is one of seven unpinned choices and the
  smallest of them. Read D14 before starting — it is the specification for this item.)*
  **DONE 2026-09-24 — the rule is `## Run 17 pre-registration (T1)`, written before any
  run-17 number exists. T3 and T7 are unblocked.** Summary of what it pins: primary
  contrast **named first** (`keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN` at **M=1920**,
  token-matched, chosen on T5's estimand + the canonical operating point + the Q6 table's
  own "read the ink pair", and landing on a pair that has **never** been a declared winner);
  10% trimmed mean of per-document differences, **difference-then-trim**; Tukey–McLaughlin
  SE; deterministic `±1.96·SE`, no bootstrap; **two tail statistics normalised against the
  row's own matched null** rather than a fitted constant; units and direction per quantity
  with every threshold in points; Holm over **three** quantities; discard set in documents
  with a per-corpus constraint; **equal arity on both verdicts**; and `res ≤ 1.0 pt`
  requiring **n ≳ 307**, which hands T2 a number instead of "more".
  *Free. Blocks T3 and T7.*
  Run 14 adjudicated the same bootstrap-vs-Wilcoxon disagreement two opposite ways
  eleven lines apart. D13 turns this from a coin-flip into a decision with a reason:
  the paired deltas are **heavy-tailed** (5 of 50 documents carry **75.6%** of the
  sum-of-squares), and a 10% trimmed mean with a **Tukey–McLaughlin** SE buys ~30% of
  resolution for nothing while staying discriminating — every published null stays
  null, and the −64 pt control still excludes zero (by ~10σ).
  ⚠ That last clause used to read "the −64 pt control still **resolves**", which is false
  in the sense a RESOLVED verdict needs: its own half-width is **6.09 at n=50** (≈1.92 even
  at n=500), so it satisfies no `h ≤ 1.5` tightness gate and must not be used to calibrate
  one. D14 §5.
  **DONE-WHEN:** this file contains the rule in writing — estimator, SE formula, CI
  method, **a tail statistic pinned alongside the location statistic**, the multiplicity
  treatment over **three** quantities (recall, NED≡charAcc, word order — *not* four,
  charAcc is an affine map of NED), and what each verdict licenses — **and it is written
  before any run-17 number exists.** The justification on record must be D13's variance
  structure, never the sign of a contrast.
  ⚠ **All six items in D14 §6 must be pinned, not just the estimator.** And **name the
  contrast first** — "run 14, m=0.40" denotes a **−0.17 pt null** and a **+4.91 pt gain** on
  disk, a 5.08 pt spread, so the estimator questions below are not even well-posed until the
  contrast and its control row are named (D14 §1b). Then: direction *per quantity* (`ned`'s
  worst-case delta is **+7.64** where recall's is −96.61, so a naive tail rule ranks the
  sabotage arm safest); location statistic **and g and DiD ordering** (g flips the sign on the
  published primary — though not on the token-matched pairing; the ordering is worth **+0.81
  pts**, 26% of the effect and 42% of the resolution the trim buys); the tail statistic with
  its tie convention (one document sits at *exactly* −10.000000 on the headline row, under
  both pairings); the discard set in documents; and the secondaries.
  ⚠ Do not let this become "pick the test that resolves". D13's own output says so. And do
  not let D14's measured swings become arguments for the flattering side of each choice —
  they are measurements of analyst freedom, not effects.
  ⚠ **A location estimator alone is not a sufficient rule — D13 §5.** The trimmed mean is
  *exactly* blind to the tail: pushing the single worst document 25 pts further leaves it
  unchanged to the last bit on 6/6 merge contrasts. Run 14's primary is published as "no
  measured cost" (trimmed −0.17 pts) and contains a page that lost **72.34 points**. The
  ~30% resolution the trim buys is paid for with precisely the documents an accuracy-
  *preservation* claim is about, so the rule must name a tail quantity and its threshold
  **in the same breath** as the location one. Note this cuts *harder* on merging than the
  current rule does — that is the point, and it is why it is written before the run.
  ⚠ **Word order is not scorable before run 17** — the field is not in runs 13/14's
  artifacts and is not derivable; see T3. The three-quantity multiplicity rule is
  therefore written now but first *exercised* at run 17. Do not silently drop to two
  quantities at run 17 because two is what the back-scoring could do.
  ⚠ **Coordinate the trim fraction with T4 before fixing it — D14 §4.** At pooled n=500,
  g=0.10 discards 50 documents per tail, which is exactly FUNSD's entire contribution.

- [x] **T2 — Confirm the second eval corpus exists, is licensed, and has usable word-level ground truth.**
  **DONE 2026-09-24 — the corpus is `sizhkhy/SROIE` test, `n=347` confirmed by loading.
  Pooled FUNSD+SROIE = 397, which clears T1's `n ≳ 307`. CORD is verified, licensed, and
  DELIBERATELY EXCLUDED — not on size, on denotation. See `## Corpus decision (T2)`.**
  *Free. Unblocks T4.*
  FUNSD test is **50 documents and is exhausted** — that is the whole blocker (D13).
  Candidates are CORD and SROIE, both document-OCR with word-level GT, both named in
  the original README plan. **The sizes quoted in D13 (~100 CORD test, ~347 SROIE test)
  were stated from general knowledge and are NOT verified against anything in this
  repo — verifying them is this task.** ✅ Both are now verified by loading: CORD test is
  **exactly 100**, SROIE test is **exactly 347**. D13's guesses were right; they were still
  guesses, and the thing that mattered was not in either number.
  **DONE-WHEN:** a corpus is chosen, its actual test-split size is confirmed by
  loading it, licence is checked, and a note in this file records the decision plus
  the distribution-shift caveat (receipts are not forms; report per-corpus *and*
  pooled, and keep FUNSD-only rows so runs 2–14 stay comparable). ✅ all four.
  ⚠ **T1 turned "more documents" into a number: `n ≳ 307`.** That is what a `res ≤ 1.0 pt`
  half-width costs on T1's named primary, derived from run 13's winsorized sd (the
  conservative of the two runs; run 14's gives 185). Against the *unverified* sizes quoted
  in D13, FUNSD+CORD (~150) **does not reach it** and FUNSD+SROIE (~397) **does** — so this
  task is now choosing against a threshold rather than a direction. Verify the sizes; if the
  chosen corpus lands under 307, the `FREE` verdict stays unreachable and T1 §7 says to
  report `UNDERPOWERED` with the required n rather than a null.
  ✅ **Resolved the way T1 assumed, but the size was never the binding constraint.** CORD is
  excluded because its ground truth **denotes a different quantity** — every `valid_line`
  carries a `category` (`menu.nm`, `total.total_price`), so CORD's recall denominator is the
  *annotated key-value subset*, not the page. FUNSD and SROIE transcribe the whole page.
  Pooling them would average two different metrics under one name. Size merely agreed.
  ⚠ **T1 §3 already simulated the matched-null p95 at `n=397`** (=1.51) before T2 ran — i.e.
  T1 assumed FUNSD+SROIE. That assumption is now confirmed rather than inherited, but note
  the direction: the pre-registration was written against an unverified corpus size. It
  happened to be right. Check `n=397` against the loaded pool before run 17 scores anything.


- [x] **T3 — Re-score runs 13 and 14 under T1's estimator and restate claim 3.**
  *Free, local. **Unblocked 2026-09-24 — T1's rule is written.*** **Scope is 2 of the 3 quantities — see below.**
  **DONE 2026-09-24 — the scorer is `scripts/score_preregistered.py` (45/45 controls, exit 0,
  `results/score_preregistered_local.log`); the restatement is in claim 3 and the record is
  `## Runs 13/14 re-scored under the run-17 rule (T3)`. T1 §3 is amended by what the scoring
  found. Nothing here is a new measurement — every number is re-derived from runs 13/14 on
  disk.** The pre-registered primary scores **UNDERPOWERED in both runs** (run 13 **+1.66
  [−0.81, +4.14]**, run 14 **+0.02 [−1.90, +1.94]**), zero Holm survivors in either, and
  **run 14 is not scored FREE despite a +0.02 pt null because both its recall tail gates
  fail** — the single behaviour T1 §3 exists to produce.
  *Free. Feeds T4 (the missing `random` arm) and T7.*
  No new data — `scripts/diagnose_merge_power.py` already computes this. The
  deliverable is the **claim**, not the number.
  ⚠ **T3's first step is now an executable scorer, not a restatement.** T1 §3's tail gates
  are simulated against a matched null at scoring time and nothing on disk implements them;
  D14 §10 showed a threshold written as a bare number passes by arithmetic. Build the scorer,
  self-test it against runs 13/14, *then* rewrite the claim. ✅ built first, calibrated against
  the nine figures T1 recorded before the file existed (all reproduce, incl. the null p95
  **tightening** 1.74 → 1.52 → 1.51 as n goes 50 → 307 → 397, which a constant could not do),
  and eight discriminating controls confirm each pinned choice is load-bearing — the naive SE
  is **35% smaller** than Tukey–McLaughlin, difference-then-trim moves the estimate **0.2555
  pts** while the same comparison on the plain mean is **identically zero**, and in points the
  harm rule counts **5** where on the stored `[0,1]` field it counts **0**.
  ⚠ **T1's primary is `keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN` at M=1920** — a
  *different* row from the m=0.20 figures quoted below, which are same-keep-fraction. Do not
  merge the two readings; that is exactly D14 §1b's 5.08 pt hazard. The caveats below stand,
  but re-derive the numbers on the named row before writing them into claim 3. ✅ scored in
  **separate sections** and labelled "NOT the pre-registered primary" throughout; token-matching
  at M=1920 is asserted **from disk** on both runs rather than assumed.
  **DONE-WHEN:** claim 3's merge sentence is rewritten with the pre-registered
  estimator's interval, **carrying two caveats, both of which cut against the headline:**
  (i) the trimmed point estimate **flips m=0.20's sign** from +0.54 to −0.65 — both are
  nulls so "no measured cost" survives, but *"free" is not sign-robust* and that must
  appear next to the claim; (ii) **the tail — D13 §5.** Run 14's merge null contains a page
  that lost **72.34 points**, and *both* candidate estimators hide it (the plain mean
  because 72/50 = 1.4 pts is inside the ±4 pt resolution, the trimmed mean because the page
  is discarded outright). So the corpus-average null is true and "merging 20% is free" is
  still not a supported sentence about an arbitrary document. File both anyway.
  ✅ **both filed, and caveat (i) gained a second direction:** the same row is **−0.65 in run
  13 and +0.16 in run 14**, so the sign is not *run*-robust either — fragility in two
  directions, only one of which was on this list. ✅ caveat (ii) re-derived **on the row that
  actually holds the page** (run 14's m=0.40, not contrast A): the trimmed mean is blind to it
  **to the last bit** (`0.0e+00` under a 25 pt mutation, against the plain mean's −0.50 =
  **181%** of the row's own effect). ⚠ **But "both tail gates catch it" would have been
  false** — the worst-document gate fires (5.01 vs 1.74) and the **harmed-count gate does
  not** (4 vs p95 6). Reported singular.
  ⚠ Caveat (ii) is **not** fixed by choosing between the two estimators, so do not let the
  T1 decision be mistaken for having addressed it. ✅ and §6 shows it is not fixed by the
  **tail gates** either — see the third finding below.
  **THREE findings beyond this DONE-WHEN, all filed:**
  1. **Claim 3's "resolved and negative" M=1440 price does not replicate.** Run 13 gives
     **−3.23 [−5.70, −0.76]** (excludes zero; its plain mean reproduces −3.86 exactly, so this
     is not a re-derivation artifact) but run 14 gives **−0.17 [−2.40, +2.06]** (includes
     zero). The sentence stated as *resolved* something one of two runs denies. 3.33× stays
     unlicensed — now for being **unreplicated**.
  2. **The sentence paired two baselines.** `2.50×` is `4800/1920`, measured against
     **keep=1.00**; the +0.54's control row is **M=2400** (keep=0.50). The merge step alone is
     **1.25×**. ⚠ **Direction asserted as a control so it cannot be filed as flattering:** on a
     consistent keep=1.00 baseline run 13's delta is **+2.29 [−0.44, +5.01]**, *better* than
     the +0.54 it replaces — a **consistency defect, not an inflated result** — and it changes
     **no verdict** (both runs stay null either way).
  3. **T1 §3's tail gate is not specific to merging — D13 §5's untreated control had never
     run.** It has now: **13 of 21** contrasts with **no merging at all** fire the gate, and
     the **worst per-document loss in the whole sweep (−80.85 pts) and the highest ratio
     (5.43) both belong to `keep=0.75 ink ORACLE` — keep=0.75, m=0** — above every merge row
     (max 4.62), wsd 6.63 so not a denominator artifact. `keep=1.00 router CONTROL` does pass
     at **1.47**, so the failure is **specificity, not sensitivity**; there is **no
     zero-treatment null on disk** to recalibrate against (no config repeats within a run;
     decode is bit-identical on re-run; runs 13/14 differ by a retrained checkpoint); and the
     gate is **not reversal-invariant** — swapping arms flips **10 of 28** verdicts, a DoF
     §3 left unwritten. **Run 17 would fail this gate on rows where nothing is merged.**
     **→ amendment filed into T1 §3, and the bar must come from the `random` arm at the
     trained budget — T3's fix and T4's missing arm are the same row.**
  ⚠ **`word_order` cannot be re-scored on runs 13/14 and is not a defect of this task.**
  Their `ablation_selection.json` `per_image` records carry
  `gen_tokens, i, mean_line_cov, min_line_cov, n_text_rows, ned, p10_line_cov, recall,
  retained_ink, tokens` — `word_order` exists only as the row-level aggregate
  `word_order_pct`. Unlike charAcc, it is **not recoverable** from what is stored:
  `compute_word_metrics` (`src/evaluate.py:44`) defines it as
  `1 − editdistance(pred_words, gold_words) / max(|pred|,|gold|)`, which needs the raw
  predicted and gold word *sequences*; neither is written to disk, and neither `recall`
  (set-valued, order-blind) nor `ned` (character-level, over the JSON string) determines
  it. So T3 delivers **recall and NED≡charAcc only**, and says so in the claim.
  ✅ the absence is **asserted from the artifact** rather than assumed, the claim records the
  2-of-3 scope, and **Holm still runs over a family of three** so the retained thresholds stay
  conservative.
  The generator injects the field as patch **G3b**
  (`scripts/make_kaggle_pruning_notebook.py:1061`, behind an asserted anchor), so the
  three-quantity primary becomes scorable **from run 17 onward** — not retroactively, and
  confirm it by *regenerating*, not by grepping the committed notebook. See D13's
  "Found while building this" for why that distinction is load-bearing.
  This is the same shape as the `n`-is-not-a-knob mistake: a quantity blocked on a
  *stored field*, not on an experiment.

- [ ] **T4 — Port the 28-row sweep to the pooled corpus.**
  *Eval-only, no training. ~~Blocked by T1, T2~~ **UNBLOCKED 2026-09-24 — both are done.**
  **This is the actual unblock.***
  **BUILT 2026-09-29/30, NOT RUN — see `## The pooled-corpus port (T4)`.** PATCH I ships
  (cells 2/9/13/15), the sweep is **29 rows** including the blocker arm
  **`keep=0.40 random TWIN` at M=1920**, `word_order` and a per-document `corpus` label are
  in `per_image`, T1 §5 and §3's direction pin are **executable** in the scorer, and all four
  checks are green against the regenerated notebook (**96/96 · 35/35 · 62/62 · 64/64**,
  exit 0 each, re-run not cited). Cost measured at **5.92 h** against a 9 h cap.
  ⚠ **Amended 2026-10-02:** three of those four were evidenced; `verify_pooled_corpus_port.py`'s
  only log **predated both the notebook it reads and its own script** and read `61/61`. Re-run
  on 2026-10-02: **62/62, exit 0** (`results/_v_T4b_verify_pooled_corpus_port.log`), so the
  number was right and the evidence was not. See the correction under
  `## The pooled-corpus port (T4)`.
  **The box stays unticked because the sweep has not run** — DONE-WHEN says *executed*.
  ⚠⚠ **BLOCKED 2026-10-02 ON A LICENSED CORPUS — this is now the binding constraint, and it
  is not "pick another dataset".** Both decisions that gated the booking are made: **run 18 is
  cancelled** and the **`sizhkhy/SROIE` mirror is rejected on licence provenance** (bare
  `license: mit`, zero attribution to ICDAR 2019 RRC, a software licence on competition scans
  the uploader did not create). Measured locally the same day: **CORD has the clean first-party
  `cc-by-4.0` and the wrong denotation** — 23.6 words/doc, KIE-categorised, `dontcare` yields
  **0 recoverable words across the whole split**, so it cannot be converted to a full-page
  target, and at **4.24 pts/word** its grain is 4.2× coarser than T1's 1.0 pt MDE.
  **SynthDoG-en's licence field is empty** and it is contaminated. **FUNSD train is
  contaminated and 199 < 307 anyway.** So no swap target exists among cached corpora, and
  nothing uncached was assessable — **no web access this session.** Full table and reasoning in
  `## Corpus re-examination after the SROIE ruling (2026-10-02)`.
  ⚠⚠ **AND the notebook ships `DO_TRAIN = True` with `TRAIN_SELECT_MODE = 'ink'`** (read off
  cell 2, 2026-10-02) — i.e. **the file T4's four verifiers were certified green against runs
  run 18, not T4's eval-only sweep.** Revert both in the generator, regenerate, and re-run all
  four verifiers *after* the regeneration before booking anything. See the cancellation block in
  `## Patch H, run 18's staged config, and two select-mode verifiers`.
  ✅ **DONE 2026-10-02.** Generator fixed (PATCH I's anchor re-keyed to the *assignment*, which
  is why it had drifted), `TRAIN_SELECT_MODE` reverted to `'router'`, **the eval-only checkpoint
  guard PATCH A's comment claimed to have added was found missing and written**, notebook
  regenerated at 18:57 (cell 2 only), and **five** verifiers green against it with mtimes
  confirmed newer: **14/14 · 96/96 · 35/35 · 62/62 · 64/64**, exit 0 each. The new guard is
  sabotage-tested (8/14, exit 1). **The corpus licence is now the only remaining blocker.**
  ~~**Two ways forward, both needing a user call:**~~ **✅ DECIDED 2026-10-02 — the user chose
  OPTION 1: re-source SROIE from the official ICDAR competition.** This was chosen *against* a
  recommendation to apply T1 §7 instead (the ground given for §7 was the ~10–12 week CV
  deadline, not the science); the ruling was reaffirmed when restated, so it stands and is not
  to be re-litigated. The rejected branch, for the record: apply **T1 §7 honestly**, report
  `UNDERPOWERED` with `n ≳ 307`, and rescope T4/T6/T7 instead of booking them.
  **What option 1 now requires, and the first step is NOT an agent's to take:**
  1. ⚠ **The user must register at the ICDAR RRC portal, read the terms, and download.** Two
     consecutive sessions failed to read those terms and the reasons are now known to be
     **structural, not transient**: `WebSearch` is **unsupported for this model** (the harness
     rejects the tool type outright, so retrying cannot help), and the RRC host serves a
     certificate for a **different domain** than the one requested, so the connection cannot be
     verified. **A licensing decision must not rest on an unauthenticatable source** — which is
     why this step is the user's, not a third agent attempt. Do not spend another session on it.
  2. ~~word GT may need re-deriving~~ **Measured and half-retired 2026-10-02** —
     `scripts/diagnose_gt_granularity.py`, 4/4 controls: **word recall is granularity-invariant**
     (denominator identical 50/50), **word order and NED are not**. See the amendment in
     `## Corpus re-examination after the SROIE ruling (2026-10-02)`. The primary quantity is
     safe; the co-primaries need T1 §5's per-corpus stratification to carry them.
  3. Once the corpus is on disk: re-run `verify_corpus_grain.py` and
     `diagnose_gt_granularity.py` **against the real annotations** (both are built to be
     re-pointed), then the `PooledTestSet` adapter in PATCH I cell 9 may need a schema change —
     it currently expects the mirror's `words`/`bboxes` naming, and `verify_pooled_corpus_port.py`
     **asserts** that the image column is the pool's only schema divergence, so a rename fails
     the check rather than surfacing at document 51.
  Same sweep, more documents. **The pool is FUNSD (50) + SROIE test (347) = 397**,
  fixed by T2; CORD is excluded on denotation and must never enter it (`## Corpus decision
  (T2)`). At n=397 the resolution drops ~2.8× to **≈1.0 pt**, which is finally smaller than
  the effects ToMe produces.
  ⚠ **The n≈500 figure below is superseded — the pool is 397, not 500.** Every number in
  this item that was derived from 500 is re-derived here; the *direction* of each hazard is
  unchanged but the magnitudes are not, and the trim hazard in particular got **smaller**,
  which is the direction that invites under-reacting.
  **DONE-WHEN:** the sweep runs end-to-end on the pooled set, `verify_tome_merge_port.py`
  and `verify_results_provenance.py` are **both re-run green against the regenerated
  notebook** (not assumed — see the resume protocol above), and the per-image arrays
  carry `word_order` so the three-quantity primary is scorable.
  ⚠ **The pooling interacts with T1's trim, and the interaction can delete FUNSD — D14 §4.**
  ~~At n=500, a g=0.10 trim discards **50 documents per tail**~~ **At the real n=397 it
  discards 39 per tail** against FUNSD's **50** — so the discard set is now *smaller* than
  FUNSD rather than exactly equal to it. The hazard is **reduced, not eliminated: 39 of 50 is
  still 78% of the only corpus measured to date.** Run 13 at m=0.40 has **10 documents worse
  than −10 pts**; those can still fall inside the discarded tail. Report the pooled result
  **stratified by corpus**, and assert that the discard set is not corpus-aligned — a check
  neither task had. **T1 §5's per-corpus constraint is what prevents this and it exists only
  as prose; implement it in the scorer.**
  ✅ **Implemented 2026-09-30** — `discard_composition`/`choose_g` in
  `scripts/score_preregistered.py`. A corpus-aligned synthetic **fires** (FUNSD 100%) and a
  SROIE-aligned one does **not**, so the constraint tracks corpus *alignment* rather than
  pooling as such; `choose_g` reduces g **0.10 → 0.03** on the violating shape. Runs 13/14
  alone could not have tested it — single-corpus, so the 50% bar is unreachable.
  ⚠ **The pool is 87.4% receipts by document and 82.2% by word.** A "pooled" number is
  substantially a *receipt* number, and FUNSD — the corpus every result from runs 2–14 was
  measured on — is a **12.6% minority** in its own successor. Keep FUNSD-only rows so the
  historical rows stay comparable, and never report the pooled figure alone.
  ⚠ **Re-derive T1 §3's matched-null p95 against the loaded pool.** T1 simulated it at
  `n=397` *before* T2 confirmed 397; the assumption was right, but a threshold inherited from
  an unverified size should not be the one run 17 is scored against.
  ✅ **Structurally answered 2026-09-30, which is stronger than re-simulating:** `score_d`
  takes `n` from **`len(d)`**, so the bar is re-derived from whatever loads and cannot
  inherit 397. Asserted twice — truncating to 25 documents moves p95 **1.74 → 1.80**, and an
  `ast` check confirms `POOLED_N`/`FUNSD_N` are never passed to `null_ratio`/`null_count`/
  `blom`. Still read the *number* off the pooled artifact when it lands.
  ⚠⚠ **The token-matched `random` arm is now a BLOCKER, not a check — T3 §6 promoted it.**
  ✅ **BUILT 2026-09-29 as the 29th sweep row, `keep=0.40 random TWIN` at M=1920** —
  token-matching verified on disk, not by arithmetic. Unrun until the sweep runs.
  **Runs 13 and 14 have none** — merge-row budgets are `[1344, 1440, 1920, 3840]`, random-row
  budgets are `[1680, 2400, 3600]`, and the overlap is **empty** (D14 §7). So "merging beats
  random at matched M" is not computable from either run, and any past statement of that form
  was comparing across budgets. **Build the matched arm in T4.**
  What changed on 2026-09-24: T3 ran D13 §5's missing untreated control and found that T1 §3's
  tail gate **is not specific to merging** — **13 of 21** contrasts with no merging at all
  clear the normal-null bar of 1.74, and the sweep's **worst per-document loss (−80.85 pts)
  and highest ratio (5.43) belong to `keep=0.75 ink ORACLE`, where nothing is merged**. There
  is **no zero-treatment null on disk** to recalibrate against: no config repeats within a run,
  decode is bit-identical on re-run (`0.000e+00`), and runs 13/14 differ by a retrained
  checkpoint. So the bar has to come from an **active non-merge comparator at the same budget**,
  which is exactly this arm. **Without it, run 17 fails its own tail gate on rows where nothing
  is merged, and a firing gate cannot be attributed to merging.** T3's fix and T4's missing arm
  are the same row — see T1 §3's amendment.
  ⚠ **SROIE's word GT is per-word with per-word boxes, but its licence is uploader-asserted**
  (T2). If the user rules that unacceptable, T4's pool collapses to FUNSD-only at n=50 and
  T1 §7's `UNDERPOWERED` becomes permanent — so raise it before spending the eval, not after.
  ✅ **RAISED AND RULED 2026-10-02: the mirror is rejected.** The warning was right that it had
  to be asked first, and **wrong about the remedy** — it assumed the fallback was FUNSD-only,
  but the ruling is against the *mirror*, not the corpus, and re-sourcing from the official
  ICDAR competition would preserve n=397 at zero code churn. What the warning did not
  anticipate is that **no swap target exists**: CORD is first-party `cc-by-4.0` and dead on
  denotation (measured — 4.24 pts/word, `dontcare` empty). See `## Corpus re-examination after
  the SROIE ruling (2026-10-02)`.
  ⚠ **Pin the contrast direction in the scorer — T1 §3's amendment.** `min(d)` is one-sided, so
  swapping which arm is "treatment" **flips the tail verdict on 10 of 28 configs**. T1 §3 now
  fixes `d = treatment − control`; T4's scorer must apply it per row rather than per quantity.
  ✅ **Implemented 2026-09-30** — `assert_direction()`, ordering the arms off `merge_ratio`
  read from the **rows** (equal `merge_ratio` raises rather than defaulting to argument
  order). ⚠ **And it corrected a claim of mine: contrast A does NOT flip** — ratio 3.22 →
  3.18 under the swap, both clearing p95 1.74. The 10-of-28 flip is real but belongs to the
  **cross-run family**, so run 14's gate failure is *not* an orientation artifact.
  *(The duplicate copy of the `random`-arm warning that stood here until 2026-09-24 has been
  folded into the block above — it was byte-identical and said twice by accident.)*

- [ ] **T5 — Decide explicitly where ToMe lives in the architecture.**
  *Free decision, large consequence. Gates T6 and T7.*
  The merger sits **after** the frozen Swin, so it saves no encoder compute and no
  latency (1.04× measured, D11) — its only benefit surface is decoder cross-attention
  KV, which pruning already delivers more simply. So ToMe's entire reason to exist here
  is one narrow ~2–3 pt claim: *at matched M, merging preserves more accuracy than
  pruning.* The alternative is merging **inside** Swin, progressively, between blocks —
  which is what ToMe was designed for and the only version that buys FLOPs and latency.
  That is a real engineering project (windowed attention assumes an intact spatial grid;
  merged tokens break window partitioning), so it is a next phase, not a fix.
  **DONE-WHEN:** the branch is decided *in writing with its reason*, the way Pending
  15's scope-out branch should have been. **If the answer is "move it inside the
  encoder", T6 and T7 as currently designed are moot** — which is exactly why this sits
  above them.

- [ ] **T6 — Pending 16: train the symmetric checkpoint `keep=0.30, merge=0.0`.**
  *Kaggle T4, ≈4–4.5 h. Blocked by T4 and T5.*
  Full rationale in the Pending table. The design is right and the confound is real —
  every M=1440 comparison currently has exactly one trained arm.
  ⚠ **Do not run this before T4.** M=1440 has sd 12.81, needing n≈71 for res 3.0 and
  n≈158 for res 2.0; run 14's DiD came in at res 4.84. Building the missing arm fixes
  the *confound* and leaves the *power* untouched, so at n=50 the predicted outcome is
  a correctly-designed fourth UNDERPOWERED. That is 4–4.5 GPU-hours for nothing.

- [ ] **T7 — Pending 17: the redesigned merge run.**
  *Kaggle T4, ≈2–3 h. Blocked by T6.* Four requirements unchanged — see the Pending
  table. Both checkpoints in one session; primary pre-registered over three quantities;
  the `random`-at-trained-budget control; DiD checkpoints already on disk.
  Do **not** re-run the sabotage row — three nulls closed it. See the standing
  constraints below and the Conventions entry *"A question closed by three nulls is closed."*

- [ ] **T8 — Housekeeping (no dependencies; fill gaps with this).**
  - ~~Reconcile `REPORT.md` and `README.md` against runs 11–14.~~ **`README.md` DONE
    2026-10-02** — rewritten visitor-first and reconciled against runs 2–14; the old
    caveat-first text is preserved verbatim as `NOTES.md` (`git mv`, history intact). Every
    figure in the new file was cross-checked against *this* file rather than carried over from
    the old one. **`REPORT.md` is still open** — its stale banner still names "ToMe has never
    executed" and a run table stopping at run 10.
  - `STORY.md` has **no numeric audit** and stops at run 12.
  - **Dead code found 2026-09-22:** `src/model.py:248` assigns `final_coords` from the
    merger and never reads it — only `compressed_tokens` reaches the decoder, and the
    `generate()` path at `:372` already discards it as `_`. So the merged 2D coordinate
    centroids are computed and thrown away, and *"w/ 2D coord centroids"* in the
    architecture diagram overstates what is wired. Either consume them or drop them
    from the diagram; do not leave the diagram claiming a path that does not exist.

### Standing constraints — not tasks, but they apply to every item above

These have no checkbox because there is nothing to execute; they are things that must
**not** happen. They are here rather than buried in Conventions because the queue is what
gets read on resume, and each of these has already cost a run once.

- **Do not buy the `tome_split` sabotage row a fourth time.** Runs 12/13/14 paid for it:
  −1.51 / −0.29 / −0.88 on recall, `rank_parity` numerically higher every time, still null
  under D13's trimmed estimator. `checkerboard` is kept on a **design** argument (it closes
  the vertical-redundancy hole raster parity leaves 100% open) and has **never** beaten what
  it replaced on accuracy — so it is a *free parameter* in whatever a run reports, never a
  validated setting. Full reasoning in Conventions, *"A question closed by three nulls is
  closed."*
- **Do not choose the estimator after seeing an effect.** T1's rule is written first, and
  its justification on record is D13's variance structure, never the sign of a contrast.
- **Do not tick an item on something written rather than executed.** See the resume
  protocol at the top of this section.

---

`README.md` was **reconciled against this file on 2026-09-04** and no longer documents
the abandoned SROIE CLI plan. It is a summary, not a second source of truth — this file
still wins on any disagreement. `REPORT.md` (same date) is a standing prose summary of
the project and of what each run established; it carries the same subordination notice.

**Five derived documents, none of them a source of truth.** All five are subordinate to
this file and all five go stale the moment a run lands:

| File | Organised by | Audience | Audit |
|---|---|---|---|
| `README.md` | results first, then scope limits | **someone arriving from a link, with 30 seconds** | — |
| **`NOTES.md`** | **caveat first — "read this before quoting a number"** | **a maintainer about to cite a figure** | — |
| `REPORT.md` | claims + per-run table | someone who knows the project | — |
| `WRITEUP.md` | results-first, claim by claim | a reviewer checking the claims | `scripts/check_writeup_numbers.py`, 134/134 |
| **`STORY.md`** | **chronology — stage by stage** | **a general reader, no ML background** | **none — see below** |

⚠ **`NOTES.md` IS the old `README.md`, renamed 2026-10-02, not a new document** — moved with
`git mv` so its history follows it. The split exists because one file was being asked to do two
incompatible jobs: it opened with *"Read this before quoting a number"*, which is correct
maintainer hygiene and a poor first impression for a visitor who has not yet been told what the
project is. The new `README.md` leads with the three scoped claims and keeps the negative
results as a named section rather than as a preamble. **Every caveat in `NOTES.md` still
applies** — nothing was dropped in the rewrite, and the figures in the new `README.md` were
cross-checked against this file rather than copied from the old one (11 of them by grepping the
literal digits, per the Conventions entry on correcting numbers).


`STORY.md` (2026-09-17) is the **only** document organised by time rather than by result:
each stage is "what we set out to do → what went wrong → what we did about it", covering
runs 2–12 plus D1–D12, M1, F1–F3 and the ToMe parity fix, with a glossary and a
"what we'd tell someone starting over" section drawn from the gotchas below. Written on
request so the project is legible to someone with no prior context. **It has no numeric
audit** — every figure in it was transcribed from this file, so if you correct a number
here, `STORY.md` is stale until someone fixes it by hand. Its run-12 chapter deliberately
states the checkpoint-provenance observation (see "Run 12") **without adjudicating it**,
because that analysis was owned by a parallel session at the time of writing.

---

## What this project is

Token-pruning research on Donut for document OCR. Architecture:

```
frozen Swin-B encoder  ->  PatchSaliencyRouter  ->  BipartiteTokenMerger  ->  mBART decoder
(naver-clova-ix/donut-base)   MLP score +            ToMe cosine soft-merge      seq2seq
                              straight-through        w/ 2D coord centroids
                              top-k prune
```

**THE FOUR CLAIMS THIS PROJECT CAN MAKE (current as of 2026-09-09; everything below
this block is history and several parts of it are superseded).** Each one names the
evidence that earns it and the scope limit that comes with it:

1. **Pruning to a third of the visual tokens costs nothing — *if you train for it*.**
   Run 9 at keep=0.35 discards 65% of visual tokens and scores **79.25 vs its own
   77.62 unpruned ceiling** (+1.62, D11, n=50 local paired). **The "if" is
   load-bearing and was absent from every phrasing in this file before D12**: run 5,
   which never trained with pruning, loses monotonically on the *identical* token sets
   (−1.57 / −6.03 / −11.47 / −20.34 at keep=0.50/0.35/0.25/0.20). Any framing that
   presents the gain as inference-time denoising, free-lunch regularisation, or a
   property of the pruner is contradicted by D12.
   **~~Attribution limit:~~ Attribution — ISOLATED 2026-09-14 (run 11).** Run 9 differs
   from run 5 by pruning-aware training **and by five more epochs of it**; run 11 is that
   second term measured alone (`TRAIN_KEEP_RATIO=1.00`, everything else run 9, verified by
   notebook diff). **`ISO(0.35) = −10.49 pts (t −3.74, n=50 paired)`**, run 11's curve
   peaks unpruned and declines monotonically where run 9's is flat, and five unpruned
   epochs moved the ceiling by **+0.52 pts (t 0.24)**. So the gain is attributable to
   pruning-aware training, **not** to the extra epochs, and Claim 1 may say "because it was
   trained for it". **Closed locally 2026-09-16:** the `run11_run9` local pair (n=50, full
   protocol) returns `ISO ≤ 0` at all four budgets and clears `ISO ≤ −3.0` with `|t| ≥ 2.0`
   at keep=0.35 (−8.15, t −3.01), 0.25 (−7.35, t −2.70) and 0.20 (−7.92, t −3.19), so the
   pre-registration is met in the venue it was written for. **One limit stands:** the loose
   budgets (Kaggle keep=0.75/0.50, local keep=0.50) are **underpowered, not null**. Write
   "H1 isolated at keep=0.35/0.25/0.20", never "H1 proven".
2. **The router's selection value is real and large.** Against a random mask at the
   same budget, run 9's router wins by **+17.7 / +27.4 / +34.0 / +29.3 pts** at
   keep=0.50 / 0.35 / 0.25 / 0.20 (D11 rows; supersedes the "+14 to +28" range quoted
   elsewhere in this file, which understated the top end). **It is not ink coverage**
   and it is not a better per-token target: that whole direction is closed (D11).
   Do **not** cite "beats the ink oracle" — D3 says co-adaptation, D6 says the margin
   moves ±5 pts on a loss-config change alone.
3. **One measured efficiency claim, with its price attached.** At keep=0.35 the decoder
   cross-attention KV cache falls **150.00 → 52.50 MiB (−65.0%) for −0.26 pts of word
   recall (t −0.18, n=50 paired)** — M1, ~~17/17~~ **25/25** controls, analytic and observed
   agreeing to rel gap 0.0000. Unpruned cross-KV is **19.46% of the model's 771 MiB of
   parameters**, so this is real working memory, not a rounding error.
   **Scope:** cross-attention KV only — not total, not peak, **not encoder** (the
   frozen Swin computes all 4800 tokens at every budget), and **not latency**.

   *(The `17/17` here was a **fourth** uncorrected copy, found 2026-09-18. The 2026-09-09
   audit records fixing it "in three places"; this block — the file's own headline claims —
   was not one of them. A miscount in the summary outlives the same miscount in the detail,
   because the summary is what gets quoted.)*

   **Extended 2026-09-18 to prune + merge (52/52 controls). RESTATED 2026-09-24 by T3** under
   the run-17 pre-registration — `scripts/score_preregistered.py`, **45/45 controls**, full
   derivation in `## Runs 13/14 re-scored under the run-17 rule (T3)`. The memory half is
   unchanged and still measured: prune to keep=0.50 then merge m=0.20 → M=1920 tokens,
   cross-KV **150.00 → 60.00 MiB (2.50×)**. The accuracy half is now this, under T1's pinned
   estimator (10% trimmed mean of per-document differences, difference-then-trim,
   Tukey–McLaughlin SE, deterministic ±1.96·SE):

   | contrast | run 13 | run 14 |
   |---|---|---|
   | **T1 §1's pre-registered primary** — `keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN`, **token-matched at M=1920** (merge vs prune-harder) | **+1.66 [−0.81, +4.14]** pts, res 2.48 | **+0.02 [−1.90, +1.94]** pts, res 1.92 |
   | claim 3's *own* row — `keep=0.50 m=0.20 router` vs `keep=0.50 router`, **M=1920 vs M=2400** (merge vs no merge) | ~~+0.54~~ **−0.65 [−2.36, +1.07]** pts, res 1.72 | **+0.16 [−1.38, +1.71]** pts, res 1.55 |

   **The pre-registered primary scores `UNDERPOWERED` in both runs, and UNDERPOWERED licenses
   neither "merging is free" nor "no measured cost" (T1 §7). Quote the required `n ≳ 307`
   beside it.** No confirmatory quantity survives Holm in either run. The corpus-average null
   is **true**; it is not a sentence about an arbitrary document. The two rows above are
   **different estimands and must never be pooled** — that is D14 §1b's 5.08 pt hazard.

   **Scope of the restatement:** **2 of T1's 3 confirmatory quantities.** Recall and
   NED≡charAcc are scored above; **`word_order` is not on disk for runs 13/14 and is not
   derivable** — `per_image` stores only the row-level aggregate `word_order_pct`, while
   `compute_word_metrics` (`src/evaluate.py:44`) needs the raw predicted and gold word
   *sequences*, and neither `recall` (set-valued, order-blind) nor `ned` (character-level)
   determines it. Holm is still run over a family of **three**, so the retained thresholds are
   the conservative ones. This is a limit of the back-scoring, not of the rule.

   ⚠ **Caveat (i) — "free" is not sign-robust, and not run-robust either.** Claim 3's +0.54 is
   the *plain* mean; T1's estimator gives **−0.65** on the identical row, and the same row is
   **+0.16** in run 14. Every one of those is a null, so "no measured cost" *survives* the
   estimator change — but the sign flips both with the estimator **and** with the replicate,
   and only the first of those was on record before T3.

   ⚠ **Caveat (ii) — the tail, and both location estimators hide it (D13 §5).** Claim 3's
   M=1440 row in run 14 contains a page that lost **72.34 pts**. The plain mean hides it
   (−0.28 against res 2.23 — a 72 pt page fits inside the resolution) and the trimmed mean is
   blind to it **to the last bit** (pushing that page 25 pts further moves the trimmed mean by
   exactly `0.0e+00`, while the plain mean moves −0.50, **181% of the row's own effect**).
   T1 §3's **worst-document gate does surface it** (ratio 5.01 vs null p95 1.74); its
   **harmed-count gate does not** (4 vs p95 6) — so *"the tail gates catch it"* plural is
   **false**, and surfacing is not attributing (see the specificity warning below).

   ⚠ **The deeper 3.33× at M=1440 does not have a replicated price.** ~~−3.86 pts
   [−7.45, −0.30], resolved and negative~~ is **run 13 only**: T1's estimator gives
   **−3.23 [−5.70, −0.76]** there (excludes zero, and run 13's plain mean reproduces −3.86
   exactly), but run 14 gives **−0.17 [−2.40, +2.06]** (includes zero). The old sentence stated
   as *resolved* something one of two runs denies. **3.33× is still not licensed** — but the
   reason is now "unreplicated", not "resolved and negative".

   ⚠ **The sentence used to pair two different baselines.** `150.00 → 60.00 MiB (2.50×)` is
   `M=4800/M=1920`, i.e. measured against **keep=1.00**; the +0.54's control row is **M=2400**
   (keep=0.50). So a *prune+merge* memory ratio was quoted with a *merge-only* accuracy delta.
   The merge step alone is **1.25×**; the remaining 2.0× is pruning, whose accuracy delta is a
   separate measurement. **Direction matters and it is not the flattering one:** on a
   consistent keep=1.00 baseline run 13's delta is **+2.29 [−0.44, +5.01]** — *better* than the
   +0.54 being replaced — so this is a **consistency defect, not an inflated result**, and it
   changes no verdict (both runs stay null either way).

   ⚠ **T1 §3's tail gate is not specific to merging** — the untreated control D13 §5 never
   ran, and T3 ran it. In the direction the design forces, **13 of 21** contrasts containing
   **no merging at all** fire the gate, and the single worst per-document loss in the whole
   sweep is **−80.85 pts on `keep=0.75 ink ORACLE` (keep=0.75, m=0)** with the **highest ratio,
   5.43** — above every merge row (max 4.62), and not a small-denominator artifact (wsd 6.63).
   So clearing 1.74 is not evidence about merging. See T1 §3's amendment.

   Every scope limit above applies unchanged; in particular the merger also runs *after* the
   frozen Swin, so it adds **no encoder-side saving** either.
4. **The methodological layer is a first-class result.** D1–D12 re-derive their numbers
   from cached artifacts; `verify_*.py` **executes** real notebook cells rather than
   linting them. Three correctness defects were found this way rather than by a run
   failing, and several diagnostics falsified the hypothesis they were built to support.

**~~But the cost axis was measured and it does not support the word "efficiency."~~
Diagnostic D3: cutting visual tokens by 65% buys ~~7–11% of wall-clock~~ (0.18–0.22×
proportional, consistent across runs 7 and 8).** **SUPERSEDED TWICE — do not quote the
struck figures.** D11 (2026-09-04) measured latency at five budgets on both
checkpoints: **4800 → 960 visual tokens (5×) buys 1.04×**, max 1.05× over ten rows, so
latency is **flat to within noise at every budget** and the "7–11%" figures were
single-budget latency *increases* misread as savings. **Any latency or throughput claim
from this work is false.** The reason is architectural and visible in the diagram above
— the router sits *after* the frozen Swin encoder, so all 4800 tokens are computed at
every `keep_ratio`, and generation is decoder-bound (243–280 autoregressive steps,
encoder runs once). Then M1 (2026-09-06) supplied the honest replacement: the saving is
**decoder cross-attention KV memory**, quantified in claim 3 above. Do not report a 65%
token cut as a 65% cost cut.

**Earlier headline, kept for the record:** runs 1–6 established the accuracy ceiling
(run 6: **77.74 recall / 64.70 char acc / 53.05 word order / NED 0.353**, after a
decoding artifact was found and fixed). Run 7 trained the router with pruning ON and
found it sign-inverted; run 8 added ink-BCE supervision and produced a genuine curve
(77.80 recall at 35% of visual tokens). Claim 1 above is the current, stronger, and
more heavily qualified version of that.

CV project, no deadline; sequence quality treated as first-class.

Also note: `BipartiteTokenMerger` in the diagram above ~~**has never executed on a recorded
result**~~ **executed and was measured on 2026-09-16/17 (runs 12 and 13)** — it was
`merge_ratio=0.0` in all eleven runs up to that point, which short-circuits it. The earlier wording here
said it had "never executed" full stop, and that was false of the repo: two local scripts
(`run_nrns_rp_sweep.py`, `probe_generation_determinism.py`) inherited the class default
`merge_ratio=0.20` and ran it dozens of times without saying so in their own artifacts —
through the *broken* split, at that. See the D5-shaped gotcha below. As of **2026-09-16**
the ordering question (Pending 15) is settled and ported: `kaggle_pruning_run.ipynb` now
carries the real `checkerboard_color` merger spliced from `src/tome.py`, and **Run 12's
launch checklist** below is the token-matched sweep that finally measures the stage.
~~Until that run lands, half the headline architecture is still unmeasured.~~

> **2026-09-18 — that run landed twice and this paragraph's tense is now history.** Run 12
> (2026-09-16) executed the full four-stage pipeline but attached the wrong checkpoint (run 5's
> merge-naive weights instead of run 9's), so **run 13** (2026-09-17) is the pre-registered
> merge result: ~~**20% merge is free at four budgets under both the router and the ink oracle;
> 40% costs −3.86 pts [−7.45, −0.30]**~~. Half the headline architecture is now measured — on
> merge-naive weights only, which is what run 14 addresses. This sentence is kept rather than
> deleted because "has never executed" was wrong twice here in two different ways (false of the
> repo, then false of the run log) and the shape of that mistake is worth keeping visible.
>
> **2026-09-24 — T3 struck the figures above, and for a third distinct reason: the words, not
> the arithmetic.** Both numbers reproduce (run 13's plain means are exactly +0.54 and −3.86).
> But under the run-17 pre-registration the m=0.20 row is a **null of the opposite sign**
> (−0.65) that is **+0.16** in run 14, and the −3.86 row is **not replicated** (−3.23
> [−5.70, −0.76] in run 13 vs **−0.17 [−2.40, +2.06]** in run 14). "Free" and "resolved" are
> both retired; the verdict on the pre-registered primary is **UNDERPOWERED at n=50, needing
> n ≳ 307**. See claim 3 and `## Runs 13/14 re-scored under the run-17 rule (T3)`. That is
> **three** ways one sentence in this paragraph has been wrong — twice about whether the run
> happened, once about what it showed.

**Diagnostics index — one line each. Full write-ups, with every table and every
self-correction, are in `AGENTS-ARCHIVE-DIAGNOSTICS.md`.** Each is a standalone script that
re-derives its numbers from cached artifacts, so any claim below can be rechecked without a
GPU. **The one-liners are pointers, not evidence** — read the archived section before citing
one, because in several cases the caveat is the finding.

| # | script | what it established |
| --- | --- | --- |
| D1 | `scripts/router_score_probe.py` | The trained router is an *inverted* saliency detector (r ≈ −0.24 vs ink), retaining 34–38% of a page's ink where random retains 50%. Its sections A–E were all clean and all decorative; only F asked the real question. |
| D2 | `scripts/diagnose_selection_geometry.py` | Retained ink is the wrong objective. Its own min-coverage acceptance gate is **withdrawn** — see D3. |
| D3 | `scripts/diagnose_selection_statistics.py` | Runs 7–8 had already answered three open questions nobody transcribed; min-coverage gate falsified; the efficiency claim fails; "beats the oracle" is probably co-adaptation. |
| D4 | `scripts/diagnose_saliency_loss.py` | The ink-BCE loss was fed a probability where it expects a logit, attenuating the gradient up to 112× on the tokens it was most wrong about. **FIXED by F1**; its own *recommended* fix was wrong — see D5. |
| D5 | `scripts/diagnose_saliency_loss_coupling.py` | D4's recommended fix was unsafe: `scores` has three consumers and two need a probability. Also found `lambda_entropy=0.05` was never chosen — it shaped two runs from a signature default. |
| D6 | (no script — re-read of run 9's own rows) | The weight change and the selection change point opposite ways: F1's mechanism worked *and* cost accuracy. Upgrades D2 from correlation to intervention. |
| D7 | `scripts/diagnose_ste_signal.py` | **Pending 13(a) is dead.** Run 7's auxiliaries were 2.5–17% of the router gradient, so it was already STE-driven — and scored 18.80 recall. CE-through-STE is large but incoherent (cos 0.21); ink-BCE is smaller and systematic (0.85–0.90). |
| D8 | `scripts/diagnose_attn_target.py` | Decoder cross-attention is a *different*, page-specific target from ink (r +0.083; top-5% centroid spread 6.12 grid rows vs ink's 1.81) and the router is **uninformed** about it (r −0.045). Cosine was the wrong statistic to pre-register. |
| D9 | `scripts/diagnose_target_learnability.py` | The attention target is reachable by the existing scorer — but the headline is the **lift over a featureless constant map (+0.212 vs ink's +0.151)**, not the 0.976 held-out AUC, three-quarters of which a constant map already earns. Reachability, not merit. |
| D10 | `scripts/diagnose_target_drift.py` | The on-the-fly target is effectively stationary and page-specific: S = 0.9613 across a full retrain against a different-pages floor of X = 0.6246. That floor is a second independent estimate of the ≈0.63 inflated null for top-K overlaps. |
| D11 | `scripts/eval_budget_binding.py` | **13(b) is DEAD, and this is the informative negative.** At budgets that *bind*, the attention target loses to ink by −5.63 at keep=0.25 and −12.81 at keep=0.20. Also settles Pending 8: 4800 → 960 tokens buys **1.04×** wall-clock. |
| D12 | `scripts/eval_why_pruning_helps.py` | **H2 is REJECTED — "pruning helps" is train/test matching, not denoising.** Run 5, never trained with pruning, falls monotonically on bit-identical token sets. This is where claim 1's load-bearing "if you train for it" comes from. |
| D13 | `scripts/diagnose_merge_power.py` | **The ToMe blocker is the instrument, not the merger.** n=50 against a per-document sd of 11–13 pts makes UNDERPOWERED structural. §5: both location estimators are blind to a −72 pt page, so a rule needs a **tail** statistic. 36/36 controls. |
| D14 | `scripts/diagnose_analysis_dof.py` | **T1 was scoped as an estimator choice; the estimator is the smallest of seven unpinned degrees of freedom.** "Run 14, m=0.40" names two contrasts 5.08 pts apart; runs 13/14 both declared MERGING WINS on **disjoint** rows; zero Holm survivors. 20/20 controls. |
| M1 | `scripts/eval_kv_memory.py` | **The project's one true efficiency claim.** Cross-attention KV 150.00 → 52.50 MiB (−65.0%) at keep=0.35 for −0.26 pts (t −0.18). Extended 2026-09-18 to the merge rows, **52/52 controls**. Cross-KV only — not total, not peak, not encoder, not latency. |
| — | `scripts/verify_saliency_loss_cell.py` | **Execs** cell 11's saliency block and asserts satisfiability, gradient proportionality (`\|d_sal/dz\|/\|p−t\| == 1.0`), explicit `lambda_*`, and the (0,1) range contract. **11/11**; 3/6 before F1. |
| — | `scripts/verify_harness_control.py` | **Execs** cell 15's weight-swap block under seven scenarios, two of which must raise. **36/36** canonical, **39/39** generated — and the higher count is the notebook that matters, because the four extra checks are the resume-train-save chain. |
| — | `scripts/verify_results_provenance.py` | **Execs** the `PROVENANCE` block and both real `json.dump`s, then reads the stamp back off disk. **35/35** on both notebooks — but it **raised silently on the generated notebook for 13 days** while this file recorded it as passing. A verifier that crashes reads exactly like one nobody ran. |
| — | `scripts/verify_training_telemetry.py` | **Extracts and executes** cell 11's epoch loop against a real loss/scaler/AdamW; asserts λ=0.5 and λ=0 print *different* lines — the property whose absence made run 9's log uninterpretable. **8/8**; 1/6 before F3. |
| — | `scripts/verify_attn_target.py` | **Execs** cells 4+7 against a real donut decoder. **34/34** fast, **41/41** with `--real`. One of those 41 clears its own content-free floor by 0.024 on one page — do not read the count as 41 equal claims. |
| — | `scripts/verify_attn_train_step.py` | The only check that executes the 13(b) *composition* rather than its pieces: cell 11's verbatim prologue + body on real pages. **13/13** fast, **24/24** with `--full`. Found three defects, incl. the `gc` cross-cell coupling. |
| — | `scripts/verify_tome_merge_port.py` | The gate that had to be green before run 12: merger output equal to `src/tome.py` **bit-for-bit**, every equality paired with a non-vacuity check. **96/96** (was 89/89 — T4 added `doc_image`, a mixed-schema fixture and six per-corpus checks). |
| — | `scripts/verify_corpus_grain.py` | **T2's artifact.** Confirms the second corpus **by loading it** and measures whether T1's point-denominated thresholds port. CORD excluded on **denotation**, not size. **21/21**. |
| — | `scripts/diagnose_gt_granularity.py` | **Does line-level GT change the metrics?** Aggregates FUNSD's per-word GT into reconstructed lines and re-scores through the **shipped** `reading_order_words`/`compute_word_metrics`. **Recall is granularity-invariant (denominator identical 50/50, recall moved in 0 of 35 mismatches); word order is not (sequence differs on 21/50).** Retires the "changes the recall denominator" cost on T4's option 1. **4/4** non-vacuity controls — one of which failed first time *as the probe's own fault*. Measured on reconstructed lines, so **re-run against official SROIE** before quoting it. |
| — | `scripts/score_preregistered.py` | **T3's artifact — the executable form of T1 §§2–7**, which existed only as prose. Runs 13/14 score `UNDERPOWERED`; §5 shows T1 §3's tail gate is **not specific to merging**. **64/64** (was 45/45 — T4 added T1 §5's per-corpus discard constraint and §3's direction pin). |
| — | `scripts/verify_pooled_corpus_port.py` | **T4's artifact.** Checks PATCH I by loading **both** corpora and reading the **generated** notebook by `ast`: pool size, schema divergence, the 29th row, token-matching of the new `random` arm, and the per-corpus stratification. **62/62**. |
| — | `scripts/verify_eval_only_ckpt_gate.py` | **The eval-only checkpoint gate (2026-10-02).** Execs the shipped `if RESUME_CKPT:` statement under **four scenarios, two of which must raise** — the verdicts **invert** on both `DO_TRAIN` and checkpoint era, which is what proves the train-side and eval-side guards oppose each other. Closes a gap PATCH A's comment claimed was closed. **14/14**; **8/14 exit 1 under sabotage**. |
| — | `scripts/verify_train_select_mode.py` | PATCH H's `src`-level check (2026-09-25). **Undocumented until 2026-09-27**; log `results/verify_train_select_mode.log`. |
| — | `scripts/verify_notebook_train_select_mode.py` | PATCH H's **notebook-level** check — execs cells 2/4/7/11 and the shipped saliency block. **Undocumented until 2026-09-27, and it had no log at all.** Run 2026-09-27: **37 passed, 0 failed through section 3, then exit 1 in section 4** (`NameError: epoch_sal`). Three of its own defects were found by running it — see `## Patch H, run 18's staged config, and two select-mode verifiers`. **Do not cite it as green.** |
| — | `scripts/check_writeup_numbers.py` | Re-derives every figure in `WRITEUP.md` from `results/*.json` — deliberately **not** from this file, because prose checked against prose proves nothing. **142/142**. Found six real errors incl. a double sign inversion. |
| — | `scripts/probe_generation_determinism.py` | Tests by execution the assumption that greedy generation is bit-identical across runs — the sole justification for bootstrapping over documents only. **6/6** within-process, **6/6** across two processes. |
| — | `scripts/diagnose_tome_parity.py` | Quantifies the ToMe score-order/parity gotcha (~49% missed redundancy). Imports the **shipped** `checkerboard_color`; a local restatement scored 10/10 under sabotage. |
| — | `scripts/diagnose_decoder.py` | LEGACY (copy-vs-next-token, settled before run 6). Re-run on run 8: no copy failure (COPY 0.0% / NEXT 74.5%), and the first legible sample of generated text recorded anywhere. |

## File map

| Path | Role |
| --- | --- |
| [README.md](README.md), [NOTES.md](NOTES.md), [REPORT.md](REPORT.md), [WRITEUP.md](WRITEUP.md), [STORY.md](STORY.md) | **Derived prose, none of them a source of truth** — see the subordination table at the top of this file. `WRITEUP.md` is the only one with a numeric audit (`scripts/check_writeup_numbers.py`, 134/134); `STORY.md` (2026-09-17) is the only one organised chronologically (stage → problem → fix, for a reader with no ML background). **`NOTES.md` is the old `README.md`, renamed 2026-10-02** when the visitor-facing and maintainer-facing jobs were split — it holds the caveat-first detail, the new `README.md` leads with results. Correcting a number in this file leaves all five stale until someone propagates it. |
| [kaggle_token_pruning_ocr.ipynb](kaggle_token_pruning_ocr.ipynb) | The **canonical** notebook, 17 cells, edited only via asserted patchers (below). Produced runs 2–6. **It did NOT produce runs 7–8.** |
| [kaggle_pruning_run.ipynb](kaggle_pruning_run.ipynb) | **The notebook that actually produced runs 7–11.** Generated by `scripts/make_kaggle_pruning_notebook.py`, which copies the canonical notebook and adds the `DO_TRAIN` pruning-ON retrain + `SUPERVISE_SALIENCY` ink-BCE loss, and since 2026-09-16 the **real checkerboard `BipartiteTokenMerger` spliced from `src/tome.py`** plus the 13 token-matched merge rows (PATCH E/F/G), and since 2026-09-26 **PATCH H** — `_selection_signal` spliced from `src/model.py` (59 lines) with `select_mode` threaded into `forward()` so `forward()` and `generate()` share one selection path — and since 2026-09-29 **PATCH I**, the pooled-corpus port (cells 2/9/13/15: FUNSD+SROIE = 397 behind a `PooledTestSet`, a per-document `corpus` label, `word_order` in `per_image`, per-corpus strata on every row, and a 29th sweep row `keep=0.40 random TWIN` at M=1920). ⚠ **This list read "E/F/G" until 2026-09-27, 11 days after H shipped** — see `## Patch H, run 18's staged config, and two select-mode verifiers`. **The mechanism behind the project's headline result lives only here and in its generator — not in `src/`, not in the canonical notebook.** That is a third copy of the model; see the duplication gotcha. Regenerate, never hand-edit. **The merge fix exists ONLY here** — the canonical notebook still carries the broken parity split (gotcha). |
| [src/](src/) | Library mirror: `model.py`, `router.py`, `tome.py`, `dataset.py`, `train.py`, `evaluate.py`, `loss.py` |
| [scripts/](scripts/) | `patch_notebook_*.py` (notebook edits), `verify_*.py` (execution checks), diagnostics |
| [tests/](tests/) | `test_modules.py`, `test_model_pipeline.py`, `test_end_to_end.py`, `test_amp_gradscaler.py`, `test_tome_correctness.py` — **five**, all run as plain scripts with `PYTHONPATH=.` (see Gotchas) |
| [infer.py](infer.py) | Standalone inference on arbitrary images |
| `pruned_ocr_results_2/`, `_3/`, `-4/`, `run 5/` | Kaggle outputs, moved here manually. **Note the inconsistent naming — `run 5` has a space.** These four keep their original names (they predate the `run <n>/` convention and are not the runs 6–10 sequence). ⚠️ **`results_2`/`results_3` are substrings of `pruned_ocr_results_2`/`_3`** — the 2026-09-06 bulk rename hit both of these by accident and produced a nonexistent `pruned_ocr_run 7/`. Anchor any future path regex to a line start or a leading separator. `pruned_ocr_results/` (unsuffixed) **no longer exists**; five scripts still referenced it until 2026-09-06. |
| `run 6/` | **Run 6** (Phase 2c ablation) Kaggle output, split out of the old `results/` on 2026-09-06 (Pending 12). Holds `ablation_decoding.json`, `metrics.json`, `token_pruning_overlay.png`, `__huggingface_repos__.json`, `__results___files/` and `pruned_ocr_results.zip` — the zip contains the **executed** `__notebook__.ipynb`, i.e. every printed log line from the run. Read it when a metrics file alone is ambiguous. All seven paths carry the identical mtime `2026-08-29 12:35` and `ablation_decoding.json` is **byte-identical to the copy inside its own zip**, which is how the split was decided rather than guessed. |
| [results/](results/) | **NOT a run directory — local diagnostics only**, and deliberately left un-renamed by Pending 12. Holds `ablation_selection_local.json` + `eval_select_modes.log` (the **local n=4** Pending 1b rows, from a *different* machine/library version than run 6 — `meta.control_drift_pts = 8.89`, so do not quote them against run 6), plus D11's, D12's and M1's JSON+logs. The `_local` suffix on the first is deliberate: Phase 2d's notebook writes `ablation_selection.json` to `/kaggle/working/`, and without the suffix downloading it would silently overwrite those rows. |
| [visualizations/](visualizations/) | Diagnostic D1 artifacts: `router_saliency_0..3.png` (4 panels each — image, ink map, router saliency, kept mask) and `router_scores.npz` (`scores`, `norms`, `rand_scores`, `contrast`, `darkness`) so D1's numbers can be recomputed without re-running the encoder. D2 runs entirely off this npz. |
| `run 7/` | **Run 7** (pruning-ON retrain, sign-inverted). `ablation_selection.json` (15 rows × 50 images, with `per_image` records), `adaptive_donut_pruned.pt`, and `pruned_ocr_results.zip` containing the **executed** `__notebook__.ipynb` — which holds the five printed Q1–Q5 verdicts. Read the zip, not just the JSON: the verdicts are only in the log. Also contains `efficiency_curve.html` / `efficiency_curve_data.json`, which are **misfiled** — they plot run *8* data (`"source": "run 8/..."`) and were written 2026-08-31; they also use token count as the cost axis, which D3 shows is not a cost axis. |
| `run 8/` | **Run 8** (sign-fix retrain, ink-BCE). Same layout. ~~This is the checkpoint the current curve comes from.~~ Superseded by `run 9/`. |
| `run 9/` | **Run 9** (F1 loss fix + F2 harness control, 2026-09-01). Same layout, plus the first `meta.harness_verified` / `harness_note` / `harness_control` / `control_ckpt` fields — so this is the **only** results file that can name the weights that produced it. `ablation_selection.json` holds 15 rows and the 16th (harness control) under `meta.harness_control`, not in `rows`. **The naming convention: `run <n>/`** — settled here, and `results{,_2,_3}/` are still misnamed runs 6/7/8 (Pending 12). |
| `run 10/` | **Run 10** (13(b) attention target, 2026-09-03). Same layout as `run 9/`. Its zip's `__notebook__.ipynb` is what makes run 10's "one variable" claim *checkable* — diff it against run 9's and the only removed lines are the three ink-target lines plus two logging lines (see "Run 10 — result"). **Do this diff for every future run.** |
| `run 11/` | **Run 11** (`TRAIN_KEEP_RATIO = 1.00`, the H1 isolation arm, 2026-09-14). Same layout as `run 9/`, and `ablation_selection.json` carries the `PROVENANCE` stamp naming its own checkpoint. `adaptive_donut_pruned.pt` here is the epochs-alone arm; `run 9/adaptive_donut_pruned.pt` is the pruning-aware one, and **run 9's is the checkpoint run 13 evaluates** (it trained at keep=0.50, where four of the six merge pairs sit). ~~run 12 evaluates~~ — run 12 attached run 5's by mistake; see "Run 12 — result". |
| `run 12/` | **Run 12** (first end-to-end prune+merge sweep, 2026-09-16, 60.2 min). 28 rows, Q1–Q6, sabotage row. `ablation_selection.json` is the first with `meta.q6_token_matched` (6 pairs, each with `delta_pts`/`ci95_lo`/`ci95_hi`/`resolution_pts`/`n_paired`) and `meta.q6_sabotage`. **Its `provenance.eval_ckpt` names `token-pruning-dataset/adaptive_donut_funsd.pt`, size `1045901275` — that is run 5's checkpoint, not run 9's**, so the four router pairs measure an anti-selective router and only the two `ink` pairs are interpretable. Read "Run 12 — result" before any row of it. `_cell15.txt` is the cell-15 log extracted from the zip and is where the printed Q1–Q6 verdicts live; no `adaptive_donut_pruned.pt` (eval-only run). |
| `run 13/` | **Run 13** (the pre-registered prune+merge sweep, 2026-09-17, 64.0 min). Identical layout and code to `run 12/`, on the intended weights — `provenance.eval_ckpt` = `adaptive-donut-run9/adaptive_donut_pruned.pt`, size `1045901771`, `control_drift_pts = 1.087`. **This is the merge result of record**, and the source of the −3.86 [−7.54, −0.35] figure at `keep=0.50 m=0.40` and of the five m=0.20 nulls. Its per-image `recall` arrays are what every recomputed contrast in this file is derived from — note the per-image key is **`recall`** (a *fraction*), while the row-level key is `word_recall_pct`. |
| `results/why_pruning_helps_local.json` + `why_pruning_helps_n50.log` + `why_pruning_helps_n50_rescored.log` | **D12** (2026-09-05, local CPU, n=50, 110 min). The run that rejected H2: run 5 and run 9 paired on the same 50 images at keep=1.00/0.50/0.35/0.25/0.20 with `select_mode="ink"`, so both checkpoints see **bit-identical token sets** (verified `0.00e+00` ×4). Carries per-image recall, all 7 control verdicts, `resolution_pts`, `controls_skipped`, `test_set_size` and `verdict`. **The `.log` prints `WITHHELD`** — it ran with the original Kaggle-level anchor, which failed for the reason D11 documented; `_rescored.log` is the same data re-derived through the corrected, pre-registered anchor (`--rescore`, 0.0 min, no generation) and is the file to read. `why_pruning_smoke_n2.log` is the n=2 pre-flight kept because it exposed three defects (see the note under the verifier index). **Absolute recall is not comparable to Kaggle** — run 5 reads 74.72 local vs 77.74 there on identical weights and images; within-checkpoint deltas are the comparable quantity. |
| `results/kv_memory_local.json` + `kv_memory_local.log` | **M1** (2026-09-06, local CPU, 72 s). The measurement that closed Pending 8(c). Per budget: `visual_tokens`, `cache_tokens`, `gen_tokens`, `cross_kv_bytes_analytic`, `cross_kv_bytes_observed`, `self_kv_bytes_observed`, `cache_kind`. `meta` carries the decoder geometry (4×16×64, d_model 1024, 4 B/elt), `param_bytes`, `controls_passed`, and three self-limiting fields written so the number cannot be quoted out of scope: `scope_limit` (cross-KV only, not total/peak/encoder), `dtype_caveat` (fp32 CPU; halves at fp16/bf16, scales with batch, **percentage invariant**), and `n_images_note` (n=1 is sufficient because cross-KV size is deterministic in geometry, not content — the analytic==observed control is what establishes that). `cache_kind` records which `past_key_values` layout `transformers` actually returned, so a library upgrade that silently reshaped the cache would be visible in the artifact rather than quietly changing what "cross" means. **The `.json` was re-written 2026-09-18 as a SUPERSET: the five prune-only rows are byte-identical to M1's published table, plus four `merge_ratio>0` rows, so every existing M1 citation still resolves. New `meta` keys: `merge_rows_note`, `merge_accuracy_cost` (run 13's per-image arrays re-bootstrapped at runtime, selection held fixed), `controls_run`/`controls_failed`. The `.log` is the ORIGINAL 2026-09-06 prune-only run and was deliberately NOT overwritten — it is what the 2026-09-09 audit cites for "25 of 25".** |
| `results/kv_memory_merge.log` | **M1 extended** (2026-09-18, local CPU, 154 s). The 9-row prune+merge run: `52/52 controls`, the self-reported count cross-checked against an independent `grep -c '\[PASS\]'` over this file. Read this for the merge-row byte figures and the "free"/"costly" paired verdict; read `kv_memory_local.log` for the prune-only history. Kept as a separate file rather than replacing the 2026-09-06 log, on purpose — see the row above. |

| `results/budget_binding_local.json` + `budget_binding_n50.log` | **D11** (2026-09-04, local CPU, n=50, 182 min). The run that killed 13(b): runs 9 and 10 paired on the same 50 images at keep=1.00/0.50/0.35/0.25/0.20 × router/random. Carries per-image recall (so the paired SE is recomputable), all 10 control verdicts, the pre-registered thresholds, and `resolution_pts` per budget. Also the project's only clean latency series across five budgets — the input to Pending 8. `budget_binding_smoke_n2.log` is the n=2 pre-flight kept because it is what exposed the two unsound controls (see the note under the verifier index). **Absolute recall here is not comparable to Kaggle at tight budgets** — the ink gates prove selection is bit-identical while generation drifts up to 3.4 pts; the run10−run9 delta is the comparable quantity. |

**Provenance gap in both run-7/8 JSONs:** `meta` has **no `checkpoint` key at all** (D3
prints `checkpoint=None` because `.get()` returns `None` for a missing key — the field was
never written, not written empty), and no `transformers` version and no device. The two
runs are distinguishable in the JSON only by directory name, and neither file can prove
which weights it evaluated. The local harness (`eval_select_modes.py`) records all three;
the notebook cell does not. Fix before the next sweep — Pending item 6. Full `meta` as
shipped, for reference:

```
run 7:  {run6_reference: [77.74, 64.7, 53.05], seed: 0, max_len: 512,
             control_drift_pts: 10.928, num_eval_samples: 50, max_words: 128, complete: true}
run 8:  {... control_drift_pts: 1.296 ...}          # otherwise identical
```

**Checkpoint fingerprints, taken 2026-08-31 so the tables can be re-tied to weights
later.** All three are 1045.9 MB (same architecture); the hash is sha256 over the first
and last 8 MB, which is enough to tell them apart without reading 1 GB three times:

| weights | mtime | sha256(head+tail 8 MB) | used by |
| --- | --- | --- | --- |
| `run 5/checkpoints/adaptive_donut_funsd.pt` | 2026-08-28 14:21 | `74706a530fd4ed1c` | runs 5 and 6 — **the 77.74 ceiling; this is the control's weights** |
| `run 7/adaptive_donut_pruned.pt` | 2026-08-30 08:46 | `488728538bf59e9b` | run 7 (pruning-ON, sign-inverted) |
| `run 8/adaptive_donut_pruned.pt` | 2026-08-31 06:55 | `abb2b29260aae9f5` | run 8 (sign-fix + ink-BCE) — **the current curve** |

mtimes line up with the run dates, which is the only independent corroboration available
that each directory holds the weights its name implies. Re-check these before quoting a
number against a checkpoint; if a hash has moved, the directory was overwritten.

Notebook cell indices after the Phase 2d patch: **2** = config (`ALLOW_CPU`,
**`RESUME_CKPT`**, and in the generated notebook the `typing` import the merger's
annotations need), **4** = router + ToMe (`select_scores` / `invert`; in the generated
notebook this is the **real** `checkerboard_color` + `BipartiteTokenMerger`, spliced from
`src/tome.py`), **7** = model class (`SELECT_MODES`, `TOME_SPLITS`, `patch_ink`,
`stratified_scores`, `_token_grid`, `_tome_partition`,
`generate(select_mode=..., tome_split=...)` + decoding defaults), **9** = data pipeline,
**11** = training, **13** = eval, **14** = decoding ablation ("Cell 8b"),
**15** = selection ablation ("Cell 8c" — 28 rows and Q1–Q6 in the generated notebook),
**16** = zip.
Backups: `.bak-phase2b`, `.bak-phase2c`, `.bak-phase2c-hotfix`,
`.bak-decode-default`, `.bak-selection-ablation` (patchers never clobber an existing
backup).

## Eval protocol — metrics held constant since run 2; decoding changed at run 6

FUNSD test ×50 · word recall / char accuracy / word-order · mean NED ·
`MAX_WORDS=128` · `max_length=512` · task prompt `<s_doc>`.
Changing any of these breaks comparability across the whole run table.

**Decoding is part of the protocol, and run 6 deliberately broke it**:
`repetition_penalty` 1.3 → 1.0 (`no_repeat_ngram_size` stays 3). This was a
knowing trade — the old setting was an artifact capping output at 71% of gold
length, so preserving comparability would have meant preserving the bug. The break
is *measured, not assumed*: run 6's CONTROL row re-ran the old decoding on the same
harness and reproduced run 5 to 0.00 pt, so the old and new numbers are related by
exactly one known change. **Comparability baseline restarts at run 6.** Rows 2–5
are a closed set; do not put a new run's numbers beside them.

Data: `nielsr/funsd` (only **149 train / 50 test** images) + `naver-clova-ix/synthdog-en`.
**SROIE is deliberately excluded** — its KIE schema would pollute the single
`{"text": ...}` target.

## Run history

| Run | Phase | Config | n | Recall | CharAcc | Order | NED | ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 1 (baseline) | pruning OFF | 20 | 54.07 | 36.00 | 21.40 | 0.640 | 3019 |
| 3 | 1.5 (augmentation) | 40 ep, no synth | 50 | 53.86 | 38.42 | 22.61 | 0.616 | 2954 |
| 4 | 2-data (SynthDoG) | 5 ep, `funsd*8 + synth[:2000]` (synth 63%) | 50 | 51.72 | 38.88 | 22.83 | 0.611 | 2713 |
| 5 | 2b (encoder unfreeze) | 5 ep, `SYNTH_N=500` (FUNSD ~70%), top Swin stage @ lr 1e-5 | 50 | 50.56 | 40.97 | 26.49 | 0.590 | 2612 |
| **6** | **2c (decoding fix)** | **eval-only on run-5 weights, `repetition_penalty` 1.3 → 1.0** | 50 | **77.74** | **64.70** | **53.05** | **0.353** | n/m |
| **7** | **2e (1a retrain + Phase 2d)** | 5 ep **pruning ON** (keep=0.5) from run-5 wts; 15-row selection sweep on retrained wts | 50 | 72.55 | 55.11 | 42.12 | 0.449 | 3240 |
| **8** | **2f (sign-fix retrain)** | 5 ep pruning ON + **ink-BCE supervision** from run-5 wts; sweep on retrained wts | 50 | 78.25 | 64.53 | 54.35 | 0.355 | 3082 |
| **9** | **2g (F1 loss fix + F2 control)** | 5 ep pruning ON + ink-BCE from run-5 wts; **first run with a verified harness control** | 50 | **79.63** | 64.81 | 54.08 | 0.352 | 2981 |
| **10** | **13(b) attention target** | identical to run 9 **except** `_tgt` = top-K of a frozen run-5 decoder's cross-attention instead of `ink > 0.15` | 50 | **79.41** | 64.81 | 53.97 | 0.352 | 2879 |
| **11** | **14 (isolate H1)** | identical to run 9 **except** `TRAIN_KEEP_RATIO` 0.50 → **1.00** — the epochs without the pruning; verified by notebook diff | 50 | **78.25** | **66.00** | **54.95** | **0.340** | 3205 |
| **14** | **train WITH merging** | identical to run 9 **except** `TRAIN_MERGE_RATIO` 0.00 → **0.40**; trained operating point is **M=1440** (keep=0.50 → K=2400, r=960), `avg_token_savings_pct: 70.0` | 50 | **78.87** | 61.76 | 50.13 | 0.382 | 2735 |

> **Runs 9–10's row is the `keep=0.50` cell-13 eval** (`metrics.json`), i.e. the trained
> operating point — *not* the `keep=1.00` sweep row that runs 7–8 use above. The two are
> not interchangeable: at keep=1.00 run 9 scores 77.30 and run 10 scores 77.32. Read the
> per-budget sweep rows in "Run 10 — result" for anything comparative.

> **Runs 12 and 13 are absent from this table on purpose** — both were `DO_TRAIN=False`
> eval-only sweeps on existing weights (run 5's and run 9's respectively), so neither
> produced a checkpoint or a trained operating point. The jump 11 → 14 is not an omission.

> **Run 14's row is M=1440, not 2400**, so it is not a like-for-like cell against run 9's.
> It reaches **recall 78.87 at 1440 tokens** where run 9 reads 79.63 at 2400 — but the other
> three metrics are **clearly worse**: charAcc **61.76** vs 64.81, order **50.13** vs 54.08,
> NED **0.382** vs 0.352. Recall is the headline metric and it barely moved; the rest of the
> row did. Anyone quoting "run 14 matches run 9 at 40% fewer tokens" is quoting one column
> of four. See "Run 14 — result" before using this row.

> **Run 11's row is `keep=1.00`, and that is not an inconsistency** — it trained at
> `TRAIN_KEEP_RATIO=1.00`, so its trained operating point *is* the full-page row, and
> `metrics.json` reports `avg_token_savings_pct: 0.0` accordingly. It is therefore the one
> row in this table that is simultaneously the operating point and the unpruned control.
> **Do not difference it against runs 9–10's cells** — those are keep=0.50. The like-for-like
> comparison is in "Run 11 — result", which is paired per image at a common budget.

> **Runs 7–8's row here is the `keep=1.00` full-page row of a 15-row sweep, not a
> single-config run.** It is also **not a control in the run-6 sense**: the weights
> changed, so its drift from run 6 (10.93 pts for run 7, 1.30 for run 8) conflates
> "the harness is sound" with "the retrain moved the ceiling" and cannot separate
> them. Run 7's drift was explained away as the fine-tune lowering the ceiling and
> run 8's as raising it; **neither explanation was tested**, and in that framing the
> check is unfalsifiable. Every sweep on new weights needs one extra row on the
> *unchanged* run-5 checkpoint. See Pending 2.

> **Rows 2–5 are all `repetition_penalty=1.3` numbers, and that setting was an
> artifact** (run 6 below). They are internally comparable to each other and to
> nothing else. Run 6 changed **no weights** — it is run 5's checkpoint decoded
> correctly. Do not quote rows 2–5 as this model's accuracy.

**The vertical story in rows 2–5 was largely a measurement artifact.** Recall
appeared to fall monotonically (54.07 → 50.56) while char accuracy (36.00 →
40.97) and word order (21.40 → 26.49) rose. Under correct decoding the *same
run-5 weights* score 77.74 / 64.70 / 53.05. The apparent "more faithful, less
complete" trade-off was a decoding cap, not a property of the training. Only
run 5 has been re-measured; runs 2–4 have not, so **whether the ranking among
them survives is unknown** — do not assume it does.

### Findings per run

- **Run 3 — augmentation didn't move recall.** Train CE 0.32 → 0.13 while test
  recall was flat. Diagnosed "data-bound": augmentation can't teach unseen glyphs.
- **Run 4 — NEGATIVE, falsified the data-bound theory.** Recall dropped 2.14 pts.
  Train CE collapsed 0.4004 → 0.0491 (near-memorized) while test recall regressed
  = overfit, same signature as run 3. Adding decoder-side data can't help when a
  frozen Swin can't separate FUNSD's degraded glyphs, and SynthDoG at 63% of the
  mix (clean synthetic vs noisy scans) pulled the priors off-domain.
  **Decision: cancelled the planned "raise SYNTH_N to 4000–6000" step** — more
  out-of-domain data + frozen encoder + CE already ~0.05 would only deepen it.
  Went straight to unfreezing.
- **Run 5 — MIXED: fidelity up, coverage down.** vs run 4: char acc **+2.09**,
  word order **+3.66** (biggest jump in the project), NED −0.021, recall **−1.16**.
  Train CE 0.7115 → 0.0954 (less memorization than run 4).
  Unfreeze *verified to have genuinely trained*, not just flag-flipped:
  `scripts/verify_run5_encoder_trained.py` diffs run4-vs-run5 encoder tensors by
  Swin stage → **stage 3: 34/34 CHANGED; stages 0–2 + embeddings: 0/315 changed.**
  Confound: unfreeze *and* data rebalance changed together. Unfreeze is the likely
  driver — run 3 had zero synth and 40 epochs, yet run 5 beat it by +2.55 char acc
  / +3.88 order in 5 epochs.
- **Run 6 — the decoding ablation. Biggest result in the project so far, and it
  cost zero training.** Full table in `results/ablation_decoding.json`; the
  printed table is in the executed notebook inside `results/pruned_ocr_results.zip`.

  | config | rp | nrns | recall | charAcc | order | NED | predW | len% | cap% | json% |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | baseline (run5) | 1.3 | 3 | 50.56 | 40.97 | 26.49 | 0.590 | 80.5 | 71.3 | 0 | 0.0 |
  | no ngram block | 1.3 | 0 | 50.56 | 40.97 | 26.49 | 0.590 | 80.5 | 71.3 | 0 | 0.0 |
  | **no rep penalty** | **1.0** | **3** | **77.74** | **64.70** | **53.05** | **0.353** | **111.9** | **99.0** | **0** | **82.0** |
  | both off | 1.0 | 0 | 71.03 | 59.16 | 51.30 | 0.408 | 140.8 | 124.6 | 22 | 70.0 |
  | both off + minlen | 1.0 | 0 | 71.03 | 59.16 | 51.30 | 0.408 | 140.8 | 124.6 | 22 | 70.0 |

  gold length = 113.0 words for all rows. **CONTROL row reproduced run 5 with
  0.00 pt drift** (50.5588491782227 / 40.97330691690949 / 26.493330101771,
  identical to 13 decimals), so the harness is sound and every row is comparable.
  Ran on a Tesla T4, `missing=0, unexpected=0` on the checkpoint load.

  1. **`repetition_penalty=1.3` was the entire cap.** Removing it: recall
     **+27.18**, char acc **+23.73**, word order **+26.55**, NED **−0.237**, and
     length 71.3% → **99.0%** of gold. The under-generation hypothesis is
     **confirmed**, and confirmed the right way: recall rose *together with*
     length, which is why length was instrumented instead of inferred.
  2. **The suspected knob was the wrong one.** Rows 1 and 2 are *bit-identical*,
     so `no_repeat_ngram_size=3` was a pure **no-op** at rp=1.3 — nothing ever
     repeated for it to block. The trigram-blocking theory was wrong.
  3. **But the two knobs interact, and the block earns its keep once rp is off.**
     `both off` over-generates to 124.6% of gold, drives **22%** of docs into
     `max_length`, and gives back 6.71 pts of recall vs keeping the block —
     textbook greedy repetition collapse. So the answer is **rp=1.0 with nrns=3**,
     *not* the tempting "turn both off".
  4. **`min_new_tokens=64` never bound** (mean generation is 328 tokens); rows 4
     and 5 are bit-identical. Not adopted — it would be dead configuration.
  5. **The malformed-JSON bug had the same single root cause.** Valid JSON
     0.0% → **82.0%**. `{"text": "` needs the `"` token twice in close
     succession; rp=1.3 penalized the second one out of existence, yielding
     `{"text `. It was logged here as a separate cosmetic issue for four runs. It
     was never separate.

  **Mechanism** (why a penalty this mild was this destructive): HF divides the
  logit of *every token already in the sequence*. A full-page form legitimately
  re-uses its whole vocabulary — field labels, digits, punctuation, common words —
  so after ~80 words nearly every plausible continuation has been downweighted,
  while EOS, never emitted, never is. EOS becomes top-1, the model closes the JSON
  and stops mid-page. The penalty does not make the model wrong; it makes the
  model *stop*. Note it is also a no-op on any logit of exactly 0.0 (positive
  scores are divided, negative ones multiplied).

## Run 17 pre-registration (T1) — written 2026-09-24, before any run-17 number exists

This is the rule. D14 is its specification; this section is the thing D14 said was still
unwritten. Every threshold below carries **units**, every choice carries a **reason that is
blind to the sign of any contrast**, and the reasons are D13's variance structure and the
project's own stated estimand — never "this is the test that resolves."

Numbers quoted as *(observed)* are from runs 13/14 and are here so the rule is checkable
**today**. They are not the justification for any choice; where a number could have driven a
choice, the choice is made on a different ground and that is said explicitly.

### 1. The primary contrast, named first

| | |
|---|---|
| **treatment row** | `keep=0.50 m=0.20 ink` |
| **control row** | `keep=0.40 ink TWIN` |
| **budget** | **M = 1920 visual tokens, both rows** *(verified equal on disk in both runs)* |
| **estimand, in words** | *"At an equal token budget of 1920, does merging preserve more word recall than pruning alone?"* |
| **primary quantity** | **word recall, in points (×100), higher is better** |

**Why this row, on three grounds none of which is its effect.** (a) T5 states ToMe's entire
reason to exist is *"at matched M, merging preserves more accuracy than pruning"* — so the
estimand is **token-matched**, not same-keep-fraction. D14 §1b showed those two readings of
"m=0.40" differ by 5.08 pts, so this sentence is the one doing the work. (b) `keep=0.50`
with `m=0.20` is already this project's canonical operating point — it is the row D13 used as
its calibration figure. (c) The **ink** split is the one the existing Q6 table itself says to
read, *"which isolates the mechanism from the router's weakness"* — a design reason recorded
before any of these numbers.

> **A property of this choice, stated rather than relied on:** this pair has **never** been
> declared a winner. Plain recall +2.28 (run 13) and −0.13 (run 14); trimmed +1.66 and +0.02.
> D14 §1c showed best-of-six selection is uncorrelated across runs, so the fact that the
> principled choice lands on a non-winner is the evidence that the choice was not effect-
> shopping. It is *not* a reason to prefer the row, and if the reasoning in (a)–(c) had
> pointed at a winner the rule would have named the winner.

Everything else in the sweep is **exploratory**: reported with CIs, never verdict-bearing,
and never promoted after the fact. D14 §1c is the reason this is a hard rule.

### 2. Estimator, SE, and interval

| | |
|---|---|
| **location statistic** | **10% trimmed mean** of the **per-document differences** |
| **g** | **0.10**, i.e. `k = floor(0.10·n)` discarded **per tail** — see §5 for the corpus constraint |
| **DiD ordering** | **difference first, then trim.** The document is the unit of analysis and the pairing is the design, so the per-document difference is the quantity being summarised. D14 §3 measured the two orderings **0.8081 pts** apart, so naming "trimmed mean" alone does not determine the estimate |
| **SE** | **Tukey–McLaughlin:** `SE = winsorized_sd(d, g) / ((1 − 2g) · √n)` |
| **NOT** | `stdev(trimmed_d) / √n_trimmed`, which is **~33% too small** and is the error D13 documented |
| **interval** | `trimmed_mean ± 1.96 · SE`, **deterministic** |
| **NOT** | a bootstrap interval. A bootstrap endpoint is **one draw, not a value** — endpoints move ±0.05 pts across seeds, and D14 §1c's whole subject is verdicts that turn on noise |

**Justification on record:** D13's variance structure — 5 of 50 documents carry **75.6%** of
the sum-of-squares. That is a statement about the tails of the *difference* distribution and
it was true before any verdict was computed.

### 3. The tail statistic, pinned in the same breath as the location statistic

D13 §5: the trimmed mean is **exactly** blind to the tail — pushing the worst document 25 pts
further leaves it unchanged to the last bit on 6/6 merge contrasts. So a location statistic
alone is not a rule. Two tail statistics, both **normalised against the row's own matched
null** rather than against a constant, because a constant chosen after seeing the data is not
a prediction (D14 §6.4):

| statistic | definition | gate |
|---|---|---|
| **worst-document ratio** | `min(d) / (Blom(n) · winsorized_sd(d, g))`, where `Blom(n) = Φ⁻¹((1−0.375)/(n+0.25))` is the expected smallest of `n` standard normals | `ratio ≤ p95` of the matched-normal null **at this n** |
| **harmed count** | `#{ docs : d < −10.0 points }`, **strict `<`** | `count ≤ p95` of the matched-normal null at this `n` and this `winsorized_sd` |

Both nulls are simulated at scoring time from the row's **own** `n` and `winsorized_sd`, seed
`20260924`, 40 000 draws. The bar is therefore **not a constant** — it tightens as `n` grows,
which is the correct behaviour, and its false-alarm rate is 5% by construction.

*(observed, n=50)* the ratio null has **median 1.20, p95 1.74, p99 2.05**; at n=307 p95 falls
to **1.52** and at n=397 to **1.51**.

**Units and direction are pinned per quantity, not once globally** (D14 §2, §1d). All
thresholds above are in **points (×100)**. On the stored `[0,1]` fields a bare `res ≤ 2.0`
cannot fail and `count(d < −10)` can never fire — so scoring MUST convert to points first,
and `ned` MUST be sign-flipped (it is an error rate; lower is better) before any tail
statistic touches it. The `−10.0` threshold means −10.0 **recall points**, and the same
number on sign-flipped `ned` points.

**Tie convention:** strict `<`. D14 §1.6 found a document at *exactly* −10.000000 on the
headline row, where `<` gives 4 and `≤` gives 5. *(observed: on the primary named here the
two conventions agree — 4 and 4 in run 13, 5 and 5 in run 14 — so the tie does not bite on
this row. It is pinned anyway, because the count is reported.)*

> **This is the part of the rule that cuts hardest against merging, and it is written before
> the run for that reason.** *(observed)* On the primary named above, **run 14 scores a
> trimmed mean of +0.02 pts — the cleanest imaginable "no measured cost" — and fails both
> tail gates**: worst document **−40.00 pts** against a matched-null expectation of −12.43
> (**ratio 3.22**, above even the n=50 p99 of 2.05), and **5 harmed documents** against a
> null p95 of 4. Run 13 on the same contrast is clean on both (ratios **1.11** and **1.07**,
> *below* the null median of 1.20; count 4 against an expected 4.05). A rule with no tail
> statistic reports run 14's primary as a perfect null.

#### AMENDMENT 2026-09-24 (T3) — the normal null is the wrong *bar*, and direction is unpinned

Written after this rule was fixed, so it amends rather than rewrites. The two gates above are
**sensitive** — T3 confirmed every observed figure in this section to 3 dp — but they are
**not specific to merging**, and the control that would have shown this (D13 §5) had never run.
T3 ran it: in the direction the design forces, **13 of 21 contrasts containing no merging at
all clear 1.74**, and the **worst per-document loss in the whole sweep (−80.85 pts) and the
highest ratio (5.43) both belong to `keep=0.75 ink ORACLE` — keep=0.75, m=0, nothing merged**,
above every merge row (max 4.62), with a winsorized sd of 6.63 so it is not a denominator
artifact. The `keep=1.00 router CONTROL` row *does* pass at 1.47, so this is a failure of
**specificity, not of sensitivity**.

Two changes to how these gates are read and scored at run 17:

1. **The matched-normal null stays, as a *floor*, and is not sufficient as the bar.** Clearing
   1.74 is not evidence about merging, because heavy per-document tails are a property of this
   corpus and checkpoint pair, not of the merge step. The reportable bar must come from an
   **active non-merge comparator at the same token budget** — the `random` arm at the trained
   budget that §1 already requires and that **D14 measured as absent from both runs**. Until
   that row exists, a firing gate licenses *"this page is visible"* and **not** *"merging did
   it"*. **T3's fix and T4's missing arm are the same row** — see T4.
2. **Pin the direction of the contrast, not just of the quantity.** §3 above pins units and
   direction *per quantity*; it says nothing about which arm is "treatment". `min(d)` is
   one-sided, so this is load-bearing: **swapping the arms flips the gate's verdict on 10 of
   28 configs**. The convention, fixed here: **`d = treatment − control`**, treatment being the
   arm carrying more of the intervention under test (more merging, or the retrained
   checkpoint), and the contrast's two arms are named in that order at scoring time. Report
   both orientations when the two arms differ by something other than the intervention.

⚠ **Do not read this amendment as grounds to drop the tail gates.** D13 §5's finding is
untouched: both location estimators still hide a −72.34 pt page, and run 14's primary still
reads as a perfect null without them. The gates are what make that page visible at all. What
changes is only the **inference** drawn from one firing, and the inference is the thing the
claim depends on.

### 4. Multiplicity

**Confirmatory family: 1 contrast × 3 quantities = 3 tests**, Holm step-down at α = 0.05.

| quantity | units | direction | status |
|---|---|---|---|
| **word recall** | points | higher better | **primary** |
| **NED ≡ charAcc** | points, sign-flipped | lower NED better | co-primary |
| **word order** | points | higher better | co-primary — **not scorable before run 17** |

**Three quantities, not four.** `character_accuracy_pct = (1 − mean(ned)) × 100` is an affine
transform of `ned`; entering it separately would double-count the one quantity carrying the
effect and bias *toward* declaring an effect, and a paired two-sided p is *identical* under a
strictly monotone map.

⚠ **`word_order` is not on disk for runs 13/14 and is not derivable** from `recall` (set-valued
and order-blind) or `ned` (character-level). The family is written over **three** now and first
*exercised* at run 17. **Do not silently drop to two at run 17 because two is what the
back-scoring could do.** When run 17 can score only two, say so explicitly and keep the
threshold at the three-test level.

Everything outside the confirmatory family is exploratory and carries no verdict. D14 §1d:
over the 6×2 = 12 family the historical runs actually support, **Holm leaves zero survivors in
either run** — both published `MERGING WINS` verdicts fail any correction, missing the first
threshold (0.00417) by ~5×.

### 5. The discard set, in documents

`k = floor(0.10·n)` per tail. **Stated in documents, per corpus, in the output.**

⚠ **Hard constraint (D14 §4):** the trimmed-away set must **not** contain more than half of
any single corpus's contribution. ~~At the pooled n=500 T4 contemplates, `k = 50` per tail and
FUNSD's entire contribution **is 50 documents**~~ — **2026-09-24, T2 settled the pool at
n=397, not 500: `k = 39` per tail against FUNSD's 50.** The discard set is therefore
*smaller* than FUNSD rather than exactly equal to it, so g=0.10 can no longer delete the only
corpus this project has ever measured **outright** — but **39 of 50 is 78% of it**, which
still violates the "not more than half" constraint above if the tail is corpus-aligned. The
constraint binds, and it binds *less obviously* than when the numbers were equal; that is the
direction that invites under-reacting. If it would be violated, **reduce g until it is not**,
and report the g actually used. The scorer must print the discard set's per-corpus
composition next to the estimate, every time.

### 6. Resolution, and what n is required

`res` = the 95% CI half-width = `1.96 · SE`, **in recall points**.

| | |
|---|---|
| *(observed)* `res` on the primary at n=50 | **2.48 pts** (run 13), **1.92 pts** (run 14) |
| ⇒ **MDE at n=50** | **~2.5 pts**, not the 1.0 pt the design targets |
| **n required for `res ≤ 1.0 pt`** | **307 documents** (from run 13's winsorized sd, the conservative of the two; run 14's gives 185) |

**Consequence for T2, which is a decision rather than a dead end:** a 1.0 pt MDE needs
**≳307 documents**. FUNSD+CORD (~150, unverified) **does not reach it**; FUNSD+SROIE (~397,
unverified) **does**. T2 must verify those sizes — but the target it is verifying against is
now a number rather than "more".

✅ **T2 verified both, 2026-09-24: CORD test is exactly 100, SROIE test exactly 347.** The
pool is **FUNSD+SROIE = 397**, clearing 307 with 90 documents of margin. But **the size was
not what decided it** — CORD is excluded because its ground truth denotes the *annotated
key-value subset* rather than the page, making its `recall` a different quantity; its grain
(one word = **5.00 pts**) cannot even express a 1.0 pt MDE. Had the reason been recorded as
"150 < 307", adding 200 more receipts would have looked like a fix. See
`## Corpus decision (T2)`.
⚠ **§3's null p95 at `n=397` was simulated before 397 was confirmed** — this rule assumed
T2's answer. It was right; re-derive it against the loaded pool anyway before run 17 is
scored, rather than inheriting a threshold written against an unverified size.

⚠ **n is not a knob at n=50.** `MAX_EVAL_SAMPLES = 50` **is** the whole FUNSD test split, so
at n=50 the gate is what must move, not the sample size — which is exactly why the `FREE`
verdict below is unreachable until T4 pools.

### 7. The verdict table — equal arity on both sides

**One named pair, so N=1 for every verdict.** D14 §1c: a 1-of-N positive condition against an
N-of-N null condition is a ratchet, and in both runs on disk only the positive verdict was
reachable. That asymmetry cannot recur here because there is no N to take the best of.

| verdict | criterion (all in points) | what it licenses |
|---|---|---|
| **DEGRADED** | Holm-adjusted CI excludes 0 with `Δ < 0` on **any** confirmatory quantity | merging costs accuracy at matched budget. Licenses *training* with `merge_ratio > 0`; does **not** license dropping the stage |
| **IMPROVED** | Holm-adjusted CI excludes 0 with `Δ > 0` on the **primary quantity** | merging beats pruning at equal M — ToMe's reason to exist, confirmed. Read with §3's tail gates: an `IMPROVED` that fails a tail gate is reported as **"improved on average, harmed the tail"** and licenses nothing about preservation |
| **FREE** | **all three** confirmatory CIs include 0, **and** `res ≤ 1.0 pt` on every one, **and both tail gates pass** | *"merging is free to within a 1.0 pt resolution."* The only verdict that licenses the word **free**. Requires n ≳ 307, i.e. **unreachable on FUNSD alone** |
| **UNDERPOWERED** | any confirmatory quantity flat with `res > 1.0 pt` | **the expected outcome at n=50.** Licenses nothing — not even "merging changes nothing". Report the required n (§6) alongside it |

**`DEGRADED` and `IMPROVED` are symmetric in arity but not in scope, deliberately:**
`DEGRADED` fires on any of the three quantities and `IMPROVED` only on the primary, because a
harm signal on a secondary is still harm, while a gain on a secondary is metric-shopping.
This is the one asymmetry in the rule and it points *against* the architecture, which is why
it is safe to write in advance.

⚠ **A tail-gate failure blocks `FREE` outright** and annotates `IMPROVED`. It does not create
a verdict of its own. The tail is a veto on preservation claims, not a licence for harm
claims — with n=50 the tail statistics are the noisiest things in the rule.

### 8. What is still open, so it is not mistaken for settled

- **The merge-vs-random control cannot be computed from runs 13/14 at all** (D14 §7): merge
  budgets are `[1344, 1440, 1920, 3840]`, random budgets `[1680, 2400, 3600]`, **overlap
  empty**. Run 17 must include a `random` arm at **M=1920** or this rule has no
  structure-matched degenerate baseline. This is a build requirement on T4/T7, not an
  analysis choice.
- **`word_order` at run 17 only** (§4).
- **g under pooling** is fixed at 0.10 *subject to* §5's constraint; T4 settles the final
  value and must record it.

**DONE-WHEN for T1 is satisfied by this section** — estimator (§2), SE formula (§2), CI
method (§2), tail statistic pinned alongside the location statistic (§3), multiplicity over
three quantities (§4), what each verdict licenses (§7), and all eight items of D14 §6 —
written before any run-17 number exists. ~~What it does **not** yet have is an executable
scorer; that is T3's first step, and T3 must exercise this rule on runs 13/14 rather than
restate it.~~ **The scorer exists as of 2026-09-24: `scripts/score_preregistered.py`, 45/45
controls, and it reproduces every observed figure in this section to 3 dp. It also found one
defect in the rule — §3's amendment. See `## Runs 13/14 re-scored under the run-17 rule
(T3)`.**

## The pooled-corpus port (T4) — built 2026-09-29/30, NOT YET RUN

**No run 19 exists and the run table is unchanged.** Everything below is code on disk plus
checks executed on 2026-09-30. T4's box stays unticked: its DONE-WHEN requires *"the sweep
runs end-to-end on the pooled set"*, and it has not.

### What shipped: PATCH I

`scripts/make_kaggle_pruning_notebook.py` gained a fifth patch, touching cells **2/9/13/15**:

| cell | change |
|---|---|
| 2 | `POOL_CORPORA`, `SROIE_SLUG`, pool config |
| 9 | `PooledTestSet` (FUNSD 50 + `sizhkhy/SROIE` 347 = **397**), `doc_image()` adapter, per-document `corpus` label |
| 13 | load-time assertion that the pool is the expected size and composition |
| 15 | per-document `corpus` written into `per_image`, **`word_order` written into `per_image`**, per-corpus strata on every row, and a **29th** sweep row |

**The 29th row is the blocker T4 promoted, not a nicety.** Runs 13/14 have merge budgets
`[1344, 1440, 1920, 3840]` and random budgets `[1680, 2400, 3600]` — intersection **empty**
(D14 §7) — so *"merging beats random at matched M"* was not computable from either run, and
T1 §3's amendment additionally needs an **active non-merge comparator at the trained budget**
before a firing tail gate can be attributed to merging at all. The new row is
**`keep=0.40 random TWIN` at M=1920**, token-matched to the pre-registered primary's control
and verified equal **on disk** rather than by arithmetic. T3's fix and T4's missing arm were
the same row, and this is it.

### Three findings, all from running things rather than reading them

**1. `doc_boxes` shipped dead — the `final_coords` defect in miniature.** PATCH I originally
carried a `doc_boxes()` schema adapter beside `doc_image()`. It was called **exactly zero
times**: cell 15 already reads `sample.get('bboxes') or sample.get('boxes')`, which resolves
on both corpora. The reason it was never needed is the fact that replaced it —
`words` and `bboxes` are named **identically** on both (`FUNSD ['bboxes','id','image',
'ner_tags','words']` vs `SROIE ['bboxes','fields','images','ner_tags','words']`), so **the
image column is the only schema divergence in the pool.** That fact is now *asserted* in
`verify_pooled_corpus_port.py`, so a future corpus that renames either field fails at the
check instead of at document 51 of a booked session. Same shape as `src/model.py:248`'s
`final_coords`: code that makes a reader believe a path is wired when nothing reaches it.

**2. A verifier crashed at 19 PASS / 0 FAIL — which is what the documented failure mode
looks like from outside.** Removing `doc_boxes` broke my own `verify_pooled_corpus_port.py`
(`KeyError: 'doc_boxes'`), and it exited **1 with zero failures printed**. Caught only by
reading the exit code and the PASS/FAIL counts *together*; the PASS count alone reads as
progress. This is `verify_results_provenance.py`'s 13-day silent raise recurring in a file
written after that lesson was on record.

**3. A substring check would have asserted the opposite of what it meant.** The natural test
for the removal is `"doc_boxes" not in cell9` — and it **fails**, because the generator now
carries a *comment* naming `doc_boxes` to record why it is gone. The check is an
`ast.walk` over `FunctionDef` names instead, which distinguishes a definition from the prose
documenting its removal. The general form is already in this file for D4's staleness guard:
a test keyed on the *shape of the text* rather than on the *condition* will read its own
documentation as the defect.

### What the verifiers do now, and why the fixture changed

`verify_tome_merge_port.py` went **89/89 → 96/96**, via a failure worth recording: PATCH I
introduced a new cross-cell dependency (cell 15 → cell 9's `doc_image`), harmless on Kaggle
— one namespace, cell 9's defs unconditional — and fatal to an extraction verifier whose
namespace is a hand-written dict. `NameError: name 'doc_image' is not defined`, exactly the
documented `gc.collect()` coupling. **Fixed by adding `doc_image` to `extract()`, not by
stubbing it**, so the *shipped* adapter is under test and the verifier raises if the notebook
stops shipping it.

The fixture is now **mixed-schema** — 2 documents keyed `image`, 1 keyed `images` — because
a FUNSD-only fixture would go green while a missed `sample['image']` call site waited to
crash on document 51 of the real run. Six per-corpus checks came with it, including the
decomposition identity `word_recall_pct == n-weighted mean of the per-corpus strata` on every
row, whose discriminating control (an *unweighted* mean) misses by **10.555556 pts**.

### T1 §5 is executable, and it does not rest on a green that cannot fail

T1 §5 — *"the trimmed-away set must not contain more than half of any single corpus's
contribution … reduce g until it is not, and report the g actually used"* — was **prose
only**. `scripts/score_preregistered.py` now implements it (`discard_composition`,
`choose_g`, `fmt_composition`, `corpora_of`), **45/45 → 64/64**.

**Runs 13/14 alone would have been a decorative green:** they are single-corpus, so at
g=0.10 the discard set is 20% of the only corpus present and the 50% bar is *unreachable*.
That is the "treated row with no untreated control" defect T3 found in the tail gates,
recurring. So the section carries a **corpus-aligned synthetic** (50 FUNSD + 347 SROIE, FUNSD
at both extremes) and its **specificity counterpart** (SROIE-aligned):

```
run 13  g=0.10  discards 5/tail = 10/50 docs  [funsd 10/50 (20%)]
run 14  g=0.10  discards 5/tail = 10/50 docs  [funsd 10/50 (20%)]
corpus-aligned synthetic  g=0.10  39/tail = 78/397  [funsd 50/50 (100%), sroie 28/347 (8%)]  <<< VIOLATES §5
after choose_g            g=0.03  11/tail = 22/397  [funsd 22/50 (44%), sroie 0/347 (0%)]
SROIE-aligned synthetic   g=0.10  39/tail = 78/397  [funsd 0/50 (0%), sroie 78/347 (22%)]
```

The constraint fires on corpus **alignment**, not on pooling as such — which is the property
that makes it a constraint rather than a tax. `k = floor(397 × 0.10) = 39` against FUNSD's 50
is **78%**, derived in the check rather than transcribed from this file. A fourth part
sabotages the pairing guard: `deltas()` pairs by **position**, which is correct by design,
and `corpora_of()` now *asserts* label alignment so a single mislabelled document raises
instead of silently comparing FUNSD document *i* against SROIE document *i*.

### T1 §3's amendment is enforced, and contrast A does not flip

`assert_direction()` pins **`d = treatment − control`** per row, read off `merge_ratio` on the
**rows** rather than inferred from config strings. Equal `merge_ratio` is an **error**, not a
default — if the field cannot order the arms, the contrast is not the kind the caller said it
was. The cross-run comparator (§5's checkpoint contrast) takes `kind='checkpoint'`, whose
positive criterion is that the two arms are the **same config**, so that branch cannot become
an escape hatch for a pair that merely failed the merge test. Three probes: accepts the pin,
rejects the swap, rejects an unorderable pair.

⚠ **A claim of mine failed its own control and is corrected here rather than quietly
dropped.** I asserted the swap would change contrast A's tail verdict. It does not: the
worst-document ratio moves **3.22 → 3.18**, both clearing p95 1.74. The statistic is not
reversal-invariant, but on *this* row the verdict survives — so **run 14's gate failure is not
an artifact of the orientation**, which is worth knowing and is the opposite of what I was
about to file. T3's **10 of 28** flip is real and belongs to the **cross-run family**, where
§5 measures it; it is not a property of every pair.

### T4's other scorer item: the null p95 is not inherited

T4 required re-deriving T1 §3's matched-null p95 *"against the loaded pool"*, because T1
simulated 1.51 at n=397 **before** T2 confirmed 397. The structural answer is stronger than a
re-simulation: `score_d` takes `n` from **`len(d)`**, i.e. from the artifact's own paired
documents, so the bar is re-derived from whatever loads and **cannot** inherit 397. Asserted
two ways, because *"it reads `len(d)`"* is exactly the sort of thing that stays true in prose
after it stops being true in code: (a) the same contrast truncated to 25 documents moves p95
**1.74 → 1.80**; (b) an `ast` check that `POOLED_N`/`FUNSD_N` are **never** passed to
`null_ratio`/`null_count`/`blom` — they size the *report*, never a threshold.

### Cost, measured rather than assumed

`results/preflight_pooled_gen.log` (2026-09-29, local CPU, n=4/corpus). **SROIE documents are
cheaper than FUNSD's** — generated-token ratio **0.66**, outside the ±10% band in which the
naive `397/50` arithmetic would have stood. Scaling run 13's own Kaggle anchor
(2609 ms/image × 28 rows × 50):

| estimate | hours |
|---|---|
| naive arithmetic | **8.06** |
| corrected by the measured 0.66 ratio | **5.63** (−30%) |
| × run 13's measured 1.05 overhead | **5.92** |

Inside Kaggle's 9 h cap, with margin. The prediction *"receipts are cheaper"* was stated in
the pre-flight **before** generation ran (SROIE targets 107.7 vs FUNSD's 112.8 words).

### Executed 2026-09-30, against the notebook as it now stands

| check | result |
|---|---|
| `verify_tome_merge_port.py` | **96/96**, exit 0 |
| `verify_results_provenance.py` | **35/35**, exit 0 |
| `verify_pooled_corpus_port.py` | **62/62**, exit 0 — ⚠ but see the correction below: the log evidencing this was only written **2026-10-02** |
| `score_preregistered.py` | **64/64**, exit 0 |

Logs: `results/_v_T4_verify_{tome_merge_port,results_provenance}.log`,
`results/score_preregistered_local.log`, `results/_v_T4b_verify_pooled_corpus_port.log`.
Notebook regenerated at 09:27 (`_gen_patchI_v2.log`, exit 0); ~~all four run **after** it~~ —
**three of four did; see the correction below.** The two named in T4's DONE-WHEN were re-run
rather than cited, per the resume protocol.

#### ⚠ CORRECTION 2026-10-02 — one row of the table above was not evidenced by any artifact

Found on resume, by comparing mtimes rather than by reading the table. **`62/62` is the right
number — it reproduces, exit 0 — but on 2026-09-30 nothing on disk supported it:**

| | mtime |
|---|---|
| `scripts/verify_pooled_corpus_port.py` | 2026-09-30 **09:30:49** |
| `kaggle_pruning_run.ipynb` (regenerated) | 2026-09-30 **09:27:30** |
| `results/verify_pooled_corpus_port.log` — the only log that existed | 2026-09-30 **09:20:12** |

So the single pooled-port log predated **both** the notebook it reads by `ast` *and* the script
that produced it, and it reads **`CONTROLS: 61/61 PASS`**, not 62 — the 62nd check was added in
the 09:30 edit. The log path the table named,
`results/_v_T4_verify_pooled_corpus_port.log`, **never existed.** Two layers of staleness and a
dangling citation, under a heading reading *"against the notebook as it now stands"*.

**Re-run 2026-10-02 against the current script and the current notebook: `62/62 PASS`, exit 0,
`results/_v_T4b_verify_pooled_corpus_port.log`.** The claim is now true in the sense the
sentence asserts. The other three were checked the same way and are clean — each log is newer
than both its script and the notebook (09:49, 09:49, 09:48 against the 09:27 regeneration), so
only this one row was affected and `96/96 · 35/35 · 64/64` stand as filed.

⚠ **This is `verify_results_provenance.py`'s 13-day silent raise in its third form, and the
third form is the cheapest to miss.** That one crashed; the 2026-09-29 one (finding 2 above)
exited 1 at 19 PASS / 0 FAIL. This one **passed, with the right number, from the wrong
artifact** — there is no red anywhere to notice, no crash, and the count in the prose is
correct. The only tell was that a file was older than its own input. **Standing consequence:
"re-run green against the regenerated notebook" is a claim about mtimes, so check them.** A
verifier whose log predates its target has not been run against that target, however green the
log is — and the resume protocol's *"executed, not written"* rule needs this corollary, because
a stale green satisfies the rule's letter.

### ✅ BOTH BLOCKING DECISIONS MADE 2026-10-02 (user ruling, in writing as required)

Both were raised as *"must be in writing first"*; both are now settled. Recorded verbatim in
substance, with the consequences worked out below.

1. **Run 18 is DITCHED.** User ruling: *"we ditch run 18 if possible cause its not logged in
   right?"* — correct, and that is the whole reason. It was staged into cell 2
   (`TRAIN_SELECT_MODE = 'ink'`) by the 2026-09-25/26 session whose chat was lost to
   compaction, **authorised by nothing in this file**, and off the serial queue: T4 is
   eval-only and next, the earliest training item is T6 and it is blocked on T4 and T5. It is
   not being deferred or re-ordered — it is **cancelled**, and anything wanting a
   `select_mode='ink'` *training* arm must be proposed as a new queue item with its own
   rationale, because the arm also interacts with D3's co-adaptation finding and with the
   "ink/random rows are router-independent at eval" gotcha, neither of which is addressed
   anywhere. See `## Patch H, run 18's staged config, and two select-mode verifiers`.
2. **The `sizhkhy/SROIE` mirror is REJECTED on licence provenance.** User ruling: *"i would
   rather switch datasets than get into copyright issues."* The decision is against **the
   mirror**, and the distinction turns out to be the whole finding — see the section below.

### Corpus re-examination after the SROIE ruling (2026-10-02)

The ruling appeared to collapse the pool to FUNSD-only and make T1 §7's `UNDERPOWERED`
permanent. It does not, but the reason is narrower than "pick another dataset": **every
measured alternative is dead on grounds that are not licence**, and the licence defect is a
property of the *mirror*, not of the corpus. Everything below was measured locally from the
HF cache on 2026-10-02 — **no web access was available this session, so no licence term is
asserted here that is not readable from a file on disk.**

| corpus | test n | words/doc (mean) | **1 word =** | denotation | licence as stated locally |
|---|---|---|---|---|---|
| **FUNSD** `nielsr/funsd` | 50 | 174.1 | **0.57 pt** | whole page — the reference | — |
| **SROIE** `sizhkhy/SROIE` | **347** | 116.5 | **0.86 pt** | **whole page** ✅ | `license: mit`, **uploader-asserted** |
| **CORD** `naver-clova-ix/cord-v2` | 100 | **23.6** | **4.24 pt** | **KV subset only** ❌ | `cc-by-4.0`, **first-party** |
| SynthDoG-en | — | — | — | whole page | **`"license": ""` — unstated** |

**The two defects are on opposite corpora, and neither is fixable by swapping.**

- **CORD has the clean licence and the wrong denotation.** It is **first-party** — published
  by `naver-clova-ix`, the dataset's actual creators, with `cc-by-4.0`, the full licence
  string and the `github.com/clovaai/cord` homepage in `dataset_infos.json`; the same org
  publishes `donut-base`, which this project already depends on. It is still unusable, and
  T2's exclusion is now **confirmed by measurement rather than by schema reading**: across the
  whole 100-document test split `valid_line` averages **23.6 words/doc**, every line carries a
  KIE `category` (`menu.nm`, `total.total_price`, …), and the page's remaining text — store
  name, address, phone, date, footer — is annotated **nowhere**. The `dontcare` field yields
  **0 recoverable words across the entire split**, so CORD *cannot be converted* into a
  full-page target. At **4.24 pts per word** its measurement grain is 4.2× coarser than T1's
  1.0 pt MDE: a single word's difference moves recall by more than four times the effect being
  resolved. Dead on denotation and dead on grain, independent of size.
- **SROIE has the right denotation and the unreliable licence.** Its `words[]` **is** a
  full-page transcription, now proven rather than assumed: **84.7% of its 40,411 test words
  carry tag `O`** (outside all four KIE fields), i.e. only 15.3% are the COMPANY/DATE/ADDRESS/
  TOTAL entities and the rest is everything else on the receipt. Denotation matches FUNSD, and
  at **0.86 pts/word** the grain can express a 1.0 pt MDE. The defect is provenance and it is
  textbook: the card is a bare auto-generated `dataset_info` block with `license: mit` and
  **zero attribution** — no citation, no homepage, no mention of ICDAR 2019 RRC — i.e. a
  *software* licence stamped on competition scan images by an uploader who did not create
  them. **The user's instinct is correct about the mirror.**
- **SynthDoG-en is worse than either on the axis in question:** licence is **empty** in both
  the README and `dataset_infos.json` — not permissive, not restrictive, *unstated* — and it
  is additionally **contaminated** (runs 4/5 trained on `synth[:2000]`/`SYNTH_N=500`) and
  synthetic-clean against FUNSD's degraded scans.
- **FUNSD's own 149-document train split is dead twice over.** Contaminated (runs 3–14 trained
  on it), which would bias the paired difference **toward null** — precisely the verdict T1 is
  trying to separate from `UNDERPOWERED` — and 50+149 = **199 < 307** regardless.

**Consequence: "switch datasets" has no target.** CORD is the only cached corpus with
first-party licensing and it fails on a ground licensing cannot fix. Any uncached candidate
(XFUND, DocVQA, WildReceipt …) is **unassessable this session** — no web access — and each
would need a fresh T2-style denotation-and-grain verification plus a new `PooledTestSet`
adapter, a PATCH I regeneration and all four verifiers re-run, with XFUND non-English against
an English-trained `donut-base`, and WildReceipt carrying CORD's KIE-annotation shape.

⚠ **What is NOT established, and must not be inferred from this section.** The original SROIE
is ICDAR 2019 Robust Reading Competition Task 3, which has its own terms from the actual
organisers. **This session could not read them** — `WebSearch` returned an API error and
`WebFetch` was content-blocked — so nothing here says what those terms permit, and no one
should act as though it does. Re-sourcing from the official competition would keep **every**
number in T1's pre-registration intact (n=397, §3's null p95 1.51, the 29-row sweep, the
5.92 h cost, all four green verifiers) at **zero code churn**, which is the only reason it is
worth checking at all. ⚠ One real cost if it is taken: official SROIE ships **line-level**
transcriptions while the mirror carries **per-word** boxes, so the mirror likely tokenised the
GT itself — re-sourcing may require re-deriving word-level ground truth, ~~which changes the
recall denominator and~~ and requires `verify_corpus_grain.py` to be re-run before any pooled
number is quoted.

#### ⚠ AMENDED 2026-10-02 — that cost is HALF WRONG, and the wrong half is the primary quantity

**User ruled for option 1 (re-source from official ICDAR) on 2026-10-02**, against the
recommendation to apply T1 §7. The sentence above was then tested rather than inherited:
`scripts/diagnose_gt_granularity.py` (**4/4 non-vacuity controls, exit 0**,
`results/_d_gt_granularity.log`) aggregates FUNSD's per-word GT into reconstructed lines and
re-scores through the **shipped** `reading_order_words` and `compute_word_metrics`.

| quantity | granularity-invariant? | measured |
|---|---|---|
| **word recall** (T1's **primary**) | **YES** | recall denominator `len(set(gold))` identical on **50/50** documents; of 35 metric mismatches, recall moved in **0** |
| **word order** (co-primary) | **NO** | gold sequence differs on **21/50** documents; word_order moved in **35/35** of the mismatches |
| **NED** (co-primary) | **NO** (inferred, not measured here) | character-level over the target string, so sequence-sensitive by the same mechanism |

**Why, and it is one line of code:** `compute_word_metrics` (`src/evaluate.py:54`) does
`gold = re.findall(r"\w+", " ".join(gt_words).lower())` — it **joins and re-tokenises** the
ground truth. So `["ABC","COMPANY"]` and `["ABC COMPANY"]` are indistinguishable downstream,
and **recall cannot see annotation granularity at all.** What *does* see it is
`reading_order_words`, which re-derives reading order by clustering **boxes** into rows: line
boxes cluster differently from word boxes, so the gold *sequence* moves even though the gold
*set* does not.

**Consequences, in the order they matter:**

1. **The blocking cost on T1's primary quantity is retired.** "Changes the recall denominator"
   is **false, measured 50/50**. Official SROIE's line-level transcriptions need **no word-box
   re-derivation** for word recall — which is the quantity the pre-registered primary contrast
   is stated in (T1 §1).
2. **The two co-primaries are on a different footing for a line-annotated corpus.** This is
   **not** a within-contrast defect: both arms of a contrast score against the same GT, so each
   per-document difference `d_i` stays internally valid, and T1's estimand is a trimmed mean of
   those differences. It **is** a cross-corpus comparability issue, and **T1 §5's per-corpus
   stratification is what must carry it** — report word_order and NED per corpus, never pooled
   alone, and say which granularity each stratum was annotated at.
3. ⚠ **`word_order` was already the weakest link in the family** — T3 could not score it on
   runs 13/14 at all (not on disk, not derivable), so the three-quantity family has been
   *written* since T1 and *exercised* never. Run 17 would be its first exercise, on a pool
   where one stratum is line-annotated. Do not let that pass silently.
4. ⚠ **Scope, stated because it limits the finding:** measured on FUNSD with **reconstructed**
   lines, because official SROIE is not on this machine. It establishes that *the pipeline's
   reading-order step is sensitive to box granularity*; it does **not** measure official
   SROIE's actual annotations. **Re-run it against the real corpus once downloaded** — the
   script takes the corpus as its only input and is built to be re-pointed.

⚠ **One control of this probe failed first time, and it was the probe's fault** — the
project's "suspect the verifier first" rule landing again. S1 originally sabotaged by reversing
the *list* (`lines[::-1]`), which `reading_order_words` **undoes by design** because it re-sorts
its input by bbox; the control read as a failure of the function. Replaced with a vertical flip
of the box geometry, which actually reverses reading order. **A sabotage that the code under
test is specified to repair is not a sabotage.**


**T4's status is therefore `BLOCKED — no licensed corpus`, not `ready to book`.** The fallback,
if the official terms are unacceptable or not pursued, is **T1 §7 applied honestly**: report
`UNDERPOWERED` with the required `n ≳ 307` and stop buying GPU for the merge axis. That is not
a failure mode — T3 already established it rigorously at n=50, and claim 4 (the methodological
layer) is a first-class result on its own. It does mean T4/T6/T7 need rescoping rather than
booking.

### ⚠⚠ THE GENERATOR DOES NOT RUN, AND THE NOTEBOOK IS A CANCELLED RUN'S CONFIG (2026-10-02)

Found while verifying the run-18 cancellation, **by running the generator rather than reading
it.** Three facts, each measured:

| artifact | mtime | state |
|---|---|---|
| `kaggle_pruning_run.ipynb` | 2026-09-30 **09:27** | ships `DO_TRAIN = True`, `TRAIN_SELECT_MODE = 'ink'` — **run 18's config** |
| `scripts/make_kaggle_pruning_notebook.py` | 2026-09-30 **17:58** | PATCH A writes `DO_TRAIN = False` — **T4's intent** |
| regeneration after 17:58 | — | **never happened** |

**The generator raises. Proven by execution** (copy with `OUT` redirected, so nothing was
mutated — the real `OUT` is written once at the very end, after every patch, so a failing
assert cannot produce a half-patched notebook):

```
I. cells 2/9/13/15 -- pooled eval corpus (FUNSD+SROIE), corpus labels, random arm
AssertionError: cell 2 DO_TRAIN anchor: expected 1 hit, found 0
```

PATCH I's `_ANCHOR_I1` (line ~1832) still anchors on the **old** line
`DO_TRAIN = True                  # True: retrain-with-pruning-ON then sweep; False: sweep only`,
while PATCH A (line ~215) now writes `DO_TRAIN = False`. The strings differ in both the value
*and* the padding, so the count is 0 and the exactly-once convention fires. **The convention
worked exactly as designed — it just had to be *run* to say so, and nothing ran it for two
days.**

**What this means for the four green verifiers, and it is not small.** `96/96 · 35/35 · 62/62 ·
64/64` — including the 62/62 re-run earlier today — **all certify the 09:27 notebook, i.e. the
armed run-18 config.** They are not evidence about a T4 notebook, because no T4 notebook has
ever been generated. The 17:58 edit is careful work (its comment block reasons through the
eval-only guard becoming load-bearing and the `_VS_RUN9` asserts going dormant) that **was
never executed even once**.

**So the order of operations before T4 can be booked is fixed, and the corpus question is not
first:**

1. Update PATCH I's `_ANCHOR_I1` to the `DO_TRAIN = False` line (and grep for any other patch
   anchored on the old text — this one was found by running, not by reading, so assume there
   are more).
2. Ratify `TRAIN_SELECT_MODE` deliberately. It is **inert at `DO_TRAIN=False`**, but line ~198's
   comment says it *"stays 'ink'"*, and leaving a cancelled run's value in a shipped config is
   the `lambda_entropy` shape again — a knob nobody chose, sitting where a future reader will
   inherit it. Set it to the queue-authorised value or assert it unreachable.
3. **Verify the `_VS_RUN9` replacement actually guards.** The 17:58 comments flag that disabling
   those checkpoint asserts is *"the hazard, not the relief"* — they were the only thing
   standing between a sweep and the wrong weights, and **T4 needs run 9's checkpoint** (run
   13's), not run 5's. Run 12 is exactly what happens when that is wrong: a path that existed,
   28 rows swept, headline an artifact. The new eval-only guard must be executed, not read.
4. Regenerate, then **re-run all four verifiers and check their mtimes against the new
   notebook** — per the mtime corollary above. The current greens are void the moment the
   notebook changes.
5. Add the assert that was missing: **`DO_TRAIN is False` whenever the run is declared
   eval-only.** This defect was latent precisely because nothing checked the one thing that
   distinguishes a 6 h eval from a 10 h train-then-eval.

#### ✅ ALL FIVE DONE 2026-10-02 — generator runs, notebook regenerated, five verifiers green

| | |
|---|---|
| notebook regenerated | **2026-10-02 18:57:31** (`results/_gen_T4_patchI_v3.log`, exit 0) |
| shipped config | `DO_TRAIN = False`, `TRAIN_SELECT_MODE = 'router'`, `TRAIN_MERGE_RATIO = 0.0`, `POOLED_N_EXPECTED = 397` |
| blast radius | **cell 2 only** — diffed against the pre-regeneration notebook, every other cell byte-identical |
| 29th row | intact (`keep=0.40 random TWIN`) |

**Verifiers, all five re-run *after* the 18:57 regeneration, all logs confirmed newer than the
notebook** (`results/_v_T4c_*.log`):

| check | result |
|---|---|
| `verify_eval_only_ckpt_gate.py` | **14/14**, exit 0 — **new, see below** |
| `verify_tome_merge_port.py` | **96/96**, exit 0 |
| `verify_results_provenance.py` | **35/35**, exit 0 |
| `verify_pooled_corpus_port.py` | **62/62**, exit 0 |
| `score_preregistered.py` | **64/64**, exit 0 |

⚠ **`score_preregistered.log` contains two `[FAIL]` lines and is still correct at 64/64.** They
are run 14's **recall tail-gate verdicts** — `worst doc −40.00, ratio 3.22 vs p95 1.74` and
`harmed 5 vs p95 4` — i.e. T1 §3's gates firing exactly as T3 documented, not control failures.
A `grep -c '\[FAIL\]'` over that log conflates *data verdicts* with *check failures* and reads
2 failures into a clean run. Count `CONTROLS:` and the exit code, not `[FAIL]`.

**What each of the five items turned out to be:**

1. **The anchor is now keyed on the ASSIGNMENT, not the value** — `_ANCHOR_I1 = "DO_TRAIN = "`.
   The old anchor embedded `DO_TRAIN = True` verbatim, so it expired the moment PATCH A's
   default changed. Re-keying it means T4/T6/T18 can each set the knob differently without
   breaking PATCH I, which is the actual requirement. ⚠ Note it must have **no leading `\n`**:
   `CORPUS_CFG` is inserted *before* the anchor, so `"\nDO_TRAIN = "` would consume the newline
   terminating the preceding comment and splice the block's first line onto it — verified by
   inspecting the insertion boundary after regenerating, not by assuming. A grep for other
   stale anchors found **only this one**; the file has exactly two `_ANCHOR_*` definitions and
   48 exactly-once asserts, and the other 47 key on structure rather than on a config value.
2. **`TRAIN_SELECT_MODE = 'router'`**, the run-9/run-14 value — chosen because it makes
   `_VS_RUN9` False *on its own merits* rather than only via `DO_TRAIN=False`, so the train-side
   guard is not load-bearing-by-accident. The ~25 lines of analysis describing the `'ink'` arm
   are **kept verbatim** above the reverted line: they document a mode this config no longer
   selects, and they are what a future ink-mode queue item would otherwise have to re-derive.
3. **The promised guard did not exist, and that is the finding.** PATCH A's comment said the
   dormant `_VS_RUN9` asserts *"are replaced by the eval-only guard added below"* — present
   tense — and **nothing implemented it.** Both identity asserts are gated on `_VS_RUN9`, which
   is False whenever `DO_TRAIN` is False, so the T4 default shipped with *both* dormant and no
   replacement; the only live guard was `assert DO_TRAIN or RESUME_CKPT`, which demands *a*
   checkpoint and never the right one. **Attach run 5's weights to T4 and nothing fires** —
   path exists, identity line prints "run 5 (pre-pruning)", 29 rows sweep on an anti-selective
   router. That is run 12 reproduced, created by the very change whose comment warned about it.
   The guard is now written (`assert DO_TRAIN or _sz == PRUNED_CKPT_BYTES`) and its **direction
   is inverted from the train-side assert**, which is why one assert cannot serve both: run
   14/18 must *start from* run 5 because they retrain, T4 must *evaluate* a pruning-era
   checkpoint because its pooled rows extend runs 13/14.
4. **Only cell 2 changed**, confirmed by diffing every cell against the archived
   pre-regeneration notebook — kept at
   `results/_ARCHIVED_run18_armed_notebook_2026-09-30.ipynb` because it is the artifact the
   four superseded greens actually certified, and deleting it would destroy the evidence for
   this entry.
5. **The new assert has a verifier, and the verifier is sabotage-tested.**
   `scripts/verify_eval_only_ckpt_gate.py` locates the config cell **by unique marker**
   (`RUN5_CKPT_BYTES = `, asserted to match exactly one cell), pulls the shipped
   `if RESUME_CKPT:` statement out by `ast` and **`exec`s it** — so it tests the notebook's
   code, not a restatement of it. Four scenarios, **two of which must raise**, and the two
   PASS/RAISE verdicts **invert in both directions**, which is what proves the two guards
   oppose each other rather than one being vacuous:

   | `DO_TRAIN` | checkpoint | verdict | why |
   |---|---|---|---|
   | False | pruning-era | PASS | T4 — extends runs 13/14 |
   | False | run 5 | **RAISE** | run 12 reproduced |
   | False | unrecognised | **RAISE** | uncharacterised weights |
   | True | run 5 | PASS | run 14/18 starts from run 5 |

   **Falsified against its own sabotage, per the D4 lesson:** deleting *only* the new assert
   from a copy of the notebook takes it to **8/14, exit 1, six named failures**
   (`results/_v_T4c_eval_only_gate_SABOTAGE.log`), including the non-vacuity check that the
   guard body contains a `DO_TRAIN` assert at all — so a future regeneration that drops the
   guard cannot go green. ⚠ **Its first run found a defect in itself**, worth recording because
   it is this file's own documented trap: it selected the config cell as `code_cells[2]`, but
   the tracker numbers cells by **JSON index including markdown**, and the config cell is JSON
   index 2 / *code* index 1 — so it reported `found 0 guard blocks` against a notebook that had
   one. Fixed by selecting on a marker, which is the convention that already exists here for
   exactly this reason.

⚠ **Also updated: `verify_notebook_train_select_mode.py` section 7 no longer certifies run 18.**
It asserted `TRAIN_SELECT_MODE == 'ink'` **and** `DO_TRAIN == True` — i.e. *"the shipped config
is run 18"* — which after the cancellation would have gone red for asserting a cancelled run's
values. That is the D4 staleness shape again: a guard keyed on the state it was written in
rather than on the condition it cares about. It now asserts T4's eval-only config, and keeps the
run-9 knob checks with an explicit note that they are **inert at `DO_TRAIN=False` but are what a
future `DO_TRAIN=True` run inherits** — which is precisely how run 18's `'ink'` came to sit in a
shipped config nobody had authorised. ⚠ **Sections 4–7 of that verifier still do not execute** —
it exits 1 in section 4 on `NameError: epoch_sal`, documented above and unchanged by this work.
Section 7's rewrite is therefore **unexercised**; do not cite it as green.


⚠ **Generalisation worth keeping: an edited generator is an unverified generator.** This file
already says *"verify that patches RUN, not just parse"* and *"the cell with no verifier is
where the bug was."* This is the same lesson one level up: the **patcher** was edited, carefully
and correctly in intent, and the thing that would have caught the anchor mismatch — running it
— is the step that distinguishes a two-day-latent crash from a five-second one. **Regenerating
is not a deployment step to be done when convenient; it is the test.**

### Still open in T4

- ~~⚠⚠ **A runnable generator and a regenerated notebook. This is the FIRST blocker**~~
  **✅ DONE 2026-10-02** — generator fixed, notebook regenerated at 18:57, five verifiers green
  against it with mtimes confirmed. See the section above.
- ⚠ **A licensed corpus. This is now the ONLY remaining blocker** — see the ruling above. The
  eval cannot be booked without one, and the three measured alternatives are dead on
  denotation / licence-silence / contamination respectively.
- The eval itself, and **recording the `g` actually used** (T1 §5 requires it in the output;
  the machinery reports it, no pooled artifact exists yet to report it *for*).
- Re-derive §3's null p95 against the pooled artifact's real `n` when it lands — the code
  does this by construction (above), but the *number* should be read off the run.



Found **on disk**, written by a session on 2026-09-25/26 whose chat was lost to compaction
before it updated this file. **Nothing here is a run result — no run 18 exists** and the run
table is unchanged. Everything below is either on disk or was executed on 2026-09-27.

**What was on disk and unrecorded.** Grepping every `.md` in the repo, including the three
archives, returned **zero** hits for `PATCH H`, `_selection_signal`,
`verify_train_select_mode` or `verify_notebook_train_select_mode`:

- **PATCH H** in `scripts/make_kaggle_pruning_notebook.py` — `_selection_signal` spliced from
  `src/model.py`, `select_mode` in `forward()`. The file-map entry said "E/F/G" for 11 days.
- `scripts/verify_train_select_mode.py` (2026-09-25, 23 KB) and
  `scripts/verify_notebook_train_select_mode.py` (2026-09-26, 28 KB) — ~51 KB of verifier
  absent from the index. **The second had no log**, so there was no evidence it had ever run.
- The regeneration itself was done **correctly**: generator and notebook share mtime
  `2026-09-26 18:26` (a regenerate, not a hand-edit), and `verify_tome_merge_port` (ALL
  CHECKS PASSED) and `verify_results_provenance` (35/35) were re-run green against it at
  18:27. So the *code* discipline held; only the *record* was missing — which is the half
  this file exists to keep.

**Run 18 is STAGED, NOT RUN, and nothing in this file authorised it.** Cell 2 of the
generated notebook ships `TRAIN_KEEP_RATIO = 0.50`, `TRAIN_MERGE_RATIO = 0.0`, and
**`TRAIN_SELECT_MODE = 'ink'`** — training the router while selecting by the *ink oracle*,
an arm that appears nowhere in the run table. `results/_gen18.log` names it "gen18".
⚠ **This is off the serial queue.** The next unchecked item is **T4** (pooled-corpus eval,
*no training*); the earliest training item is **T6**, and T6 is blocked on T4 and T5. Decide
in writing whether run 18 precedes T4 — do not discover the answer by launching it. Note also
that a `select_mode='ink'` training arm interacts with D3's co-adaptation finding and with
the "ink/random rows are router-independent at eval" gotcha; neither is addressed anywhere.

> **✅ CANCELLED 2026-10-02 — run 18 will not be launched**
>
> User ruling, on the ground stated above: it was **not logged**, i.e. staged into the shipped
> notebook by a session whose chat was lost, authorised by nothing in this file, and off the
> serial queue. **Cancelled, not deferred.**
>
> ⚠⚠ **AND THE STAGED CONFIG IS ARMED, NOT INERT — read off cell 2 of the generated notebook
> on 2026-10-02:**
> ```
> DO_TRAIN = True                  # <<< NOT False
> TRAIN_KEEP_RATIO = 0.50
> TRAIN_MERGE_RATIO = 0.0
> TRAIN_SELECT_MODE = 'ink'        # <<< the unauthorised arm
> ```
> **So `kaggle_pruning_run.ipynb` as it currently stands does not run T4 — it runs run 18.**
> `DO_TRAIN=True` plus the ink-oracle select mode *is* run 18's config, sitting in the notebook
> T4's four verifiers were just certified green against. T4 is specified as **eval-only**; the
> shipped notebook trains for ~4 h first and then sweeps on the checkpoint it just made, not on
> run 9's. **This must be reverted in the generator before T4 is booked** — `DO_TRAIN = False`
> and `TRAIN_SELECT_MODE` back to the queue-authorised value — and a regeneration plus all four
> verifiers re-run after it, per the mtime corollary below. An assert that `DO_TRAIN is False`
> whenever the run is declared eval-only would have made this loud instead of latent.
> ⚠ **An earlier draft of this very entry called the staged config "inert for T4 (eval-only,
> `DO_TRAIN=False`)". That was wrong — asserted from T4's specification rather than read off
> cell 2.** It is corrected here rather than quietly removed because it is the file's own
> recurring failure: a claim about what a run *will* do, taken from what it was *designed* to
> do. The same shape as `EVAL_ONLY` printing "training skipped" on three runs that trained.
>
> The staged mode is exactly the `lambda_entropy`/`merge_ratio` shape this file keeps
> relearning: *a knob that shapes a run while appearing nowhere in its log.* ⚠ Do **not** read
> this cancellation as a finding about `select_mode='ink'` training — nothing was measured. If
> that arm is ever wanted it needs a new queue item with its own rationale, addressing D3's
> co-adaptation finding and the "ink/random rows are router-independent at eval" gotcha, neither
> of which this staged config addressed.
> **PATCH H itself is unaffected and stays** — it is the `_selection_signal` splice that makes
> `forward()` and `generate()` share one selection path, which is a correctness fix independent
> of what any run trains with. Only the staged *config* is cancelled.

**Three defects in `verify_notebook_train_select_mode.py`, found by running it (2026-09-27).**
All three are instances of gotchas **already in this file**, which is the part worth keeping:

1. **The cell selector matched two cells** — exit 1 at check 0.
   `find_cell("_TRAIN_SELECT_MODES")`: cell 2 *defines* the tuple, and cell 11's drift-assert
   **error message** also names it. Fixed to anchor on the assignment
   `"_TRAIN_SELECT_MODES = ("`. Same shape as `RESUME_CKPT` breaking
   `verify_decode_ablation.py`. ⚠ The mechanism is worth stating: the *helpful*
   cross-reference in cell 11's message — `fix cell 2s _TRAIN_SELECT_MODES, not this assert`
   — is what broke the other file's selector. Good practice in one file defeated a loose
   selector in another.
2. **The verifier crashed on its own expected PASS.** `gvec` returns `torch.zeros(0)` when no
   parameter has a `.grad` — which is *exactly* what sections 3–4 assert for
   `ink`/`random`/`stratified*`, because the STE guard keeps the scorer out of the CE graph and
   `p.grad` stays `None`. `float(t.abs().max())` on 0 elements **raises** rather than reading
   `0.0`. Fixed with a `gmax()` helper across **10** call sites; `gvec` still returns empty on
   purpose, because §4 asserts `g_enc.numel() == 0`. **A verifier that crashes reads exactly
   like one nobody ran** — and this one crashed *because the property held*, which is the
   worst version of that failure.
3. **Cross-cell coupling on a config constant.** The extracted saliency block reads
   `TRAIN_KEEP_RATIO`, assigned in cell 2. The verifier already seeded cell 2's **imports**
   from the cell itself (the documented `gc` fix) but not its **assignments**. Fixed by also
   exec'ing cell-2 assignments whose value is `literal_eval`-able — **13 of 19**; the 6
   skipped are precisely the side-effecting ones (`device`, `EVAL_ONLY`, `PRUNED_CKPT`,
   `EVAL_CKPT`, `_VS_RUN9`, `_VS_RUN9_WHY`), which resolve mount paths and assert on the
   accelerator. Values come from the cell, so a config drift surfaces here.

**State as executed: `37 passed, 0 failed`, sections 0–3 complete, then `exit 1` in section 4**
(`NameError: epoch_sal`). Log: `results/_v_train_select.log`. Section 3 is the substantive part
and its controls **discriminate**: removing the STE guard clause moves `stratified` from
`0.000e+00` to `2.840e-02` while leaving `router` bit-identical at `1.502e-02`, and `ink` reads
`0.0` **under sabotage too** — so ink's zero is the missing graph, not the guard. That is a
non-vacuity argument of the kind this file asks for.

⚠ **Section 4 is unfinished. Do not tick it, and do not seed names one `NameError` at a time
until it goes green.** Its extraction lifts cell 11's `if LAMBDA_SAL > 0:` statement out of the
training loop, so it needs that loop's scope rebuilt: **11 free names** (`GRAD_ACCUM`,
`LAMBDA_SAL`, `_teacher_dec`, `attn_topk_target`, `decoder_input_ids`, `epoch`, `labels`,
`outputs`, `patch_ink`, `pixel_values`, `step`) **plus the `epoch_*` accumulators**, which `+=`
requires to pre-exist and which a Load-only scan does not report. And cell 11 holds **two**
loops — `GRAD_ACCUM = 8` at L114 *and* L367, `LAMBDA_SAL = 0.5` at L106 vs `0.0` at L111 — the
`DO_TRAIN` branch and the canonical `else` branch. Whoever finishes this must **name which
loop's scope is being reconstructed**, or the greenest possible section 4 is one measuring the
branch that did not run.

## Conventions

**The repo is under git as of 2026-10-02 — use it, and know what it does not cover.** Initial
commit: 262 files, 183,293 lines, 22 MB. `.gitignore` excludes ~9.4 GB that cannot be
versioned anywhere with a 100 MB per-file limit — 10 `*.pt` checkpoints (3.9 GB) and 7 per-run
`pruned_ocr_results.zip` archives (5.5 GB), each file ~1 GB. **The 12 `results/*.json` and 49
`*.log` artifacts every diagnostic re-derives from ARE versioned**, so the analyses reproduce
without the weights.

Three consequences, the first of which is immediately load-bearing:

1. **Concurrent sessions are now diffable.** This file's own gotcha about verifier logs
   predating their inputs was found by mtime archaeology; `git status` answers the same
   question directly. Within minutes of the initial commit it confirmed that a parallel
   session had changed nothing after its last write — a question that previously required
   comparing timestamps on four files and reasoning about which was newer than which.
   **Before assuming you know what state the tree is in, run `git status`.**
2. ⚠ **The excluded zips are the only place the printed Q1–Q6 verdicts live** — see the
   Conventions entry *"Transcribe the verdict"*, which says exactly that. So `git clone`
   does **not** reproduce the verdict logs. If a verdict needs to be readable from the repo,
   extract `__notebook__.ipynb` out of its zip and commit that file on its own, the pattern
   `run 12/_cell15.txt` already uses. **This is a known gap, recorded rather than fixed.**
3. **A commit is not a backup of the weights.** `run */adaptive_donut_pruned.pt` exists only
   on this machine and in whatever Kaggle still holds. The checkpoint fingerprint table in
   this file is the only thing tying a results table to the weights that produced it, and
   nothing versions those weights.

**Notebook edits go through asserted patchers in `scripts/`.** Never hand-edit the
notebook. Each patcher: backs up first (refusing to overwrite an existing backup),
replaces via a `sub()` helper that `assert n == 1` (exactly-once, so a silent
no-match or double-apply is impossible), and `ast.parse`s every edited cell before
writing.

**Verify that patches RUN, not just parse.** This is a standing requirement from
the user, and it has already caught a crash that `ast.parse` passed clean — see
the `.layernorm` gotcha below. Each patcher gets a `verify_*.py` companion that
executes the real code against stubs (no GPU, no weight download):

- `verify_unfreeze_paths.py` — builds donut-base from config, runs the actual
  unfreeze loop against the real module tree.
- `verify_decode_ablation.py` — extracts the **real** `gen_kwargs` block out of
  cell 7 and execs it, confirming explicit kwargs beat `setdefault`. Without this,
  the ablation would silently test one config five times and "prove" nothing.
- `verify_run5_encoder_trained.py` — differential checkpoint diff; distinguishes
  "the optimizer moved the weights" from "we only flipped a flag".
- `verify_phase2c_fixes.py` — exercises the checkpoint-path resolver against a fake
  `/kaggle/input` tree (nested file, wrong slug, unattached, ambiguous, correct,
  `None`) and both branches of the GPU guard.
- `verify_decode_default.py` — confirms the new rp=1.0 default, and specifically
  that the ablation's explicit rp=1.3 **still overrides it** — otherwise the
  CONTROL row would quietly become a duplicate of the default and the ablation
  would lose its reference point while still printing a plausible table. Also
  asserts against the installed `transformers` that rp=1.0 is an exact identity on
  the logits and that nrns=3 really does block a repeated trigram, rather than
  assuming either.

**When a verifier fails, suspect the verifier first.** Twice now a red check was
the check's own fault, not the notebook's: a cell selector that started matching
the wrong cell after a patch moved code, and a logits fixture that put its only
positive logit on a token that was never emitted — so `repetition_penalty` had
nothing to divide and correctly did nothing, which the test read as a failure.
Both would have been "fixed" destructively by trusting the red.

**A green diagnostic deserves the same suspicion as a red one.** The converse of
the rule above, and it cost more. `router_score_probe.py` printed "VERDICT: no
concerns" across five sections; adding a sixth that compared the router to the
*actual objective* reversed the verdict entirely (D1). The five clean sections were
all measuring proxies that a broken router satisfies. Before trusting a pass, ask
what a *failing* system would score on this same check — if the answer is "about
the same", the check is decorative.

**`kaggle_pruning_run.ipynb` is GENERATED. Never hand-edit it.**
`scripts/make_kaggle_pruning_notebook.py` copies `kaggle_token_pruning_ocr.ipynb` and
patches cells 2, 9 and 11; the canonical notebook supplies cell 11's `else` branch verbatim,
indented. So a fix typed into the generated file **survives until the next regeneration and
then silently vanishes** — and since regeneration is how every other change ships, that is
soon. Two consequences: (1) edit the **generator** for anything in the `DO_TRAIN` branch and
the **canonical notebook** for anything in the `else` branch; (2) any verifier that reads the
generated notebook must also assert **parity with its source**, or it will keep passing
against a file that is about to be overwritten. `verify_saliency_loss_cell.py`'s F PARITY
assertion exists for exactly this and is the cheapest kind of check in the file: one regex on
each side, compared.

**A staleness guard that greps for a symptom does not detect its own fix.** D4 was written
to "go stale loudly" by testing `"binary_cross_entropy_with_logits" in loss_src`. The fix
that closed D4 **kept that substring** — it wraps the argument in `torch.logit(...)` — so the
guard stayed silent and D4 went on reporting a live defect against fixed code. The guard was
testing the *shape of the buggy line*, not the condition the bug consisted of. Rewrite as:
does the argument arrive as a logit? Then **falsify the guard itself** against both the buggy
and the fixed form — a guard verified only against the state it was written in is half-tested,
and the half that matters is the one you cannot see yet. Same root cause as the green-check
rule above: ask what a *fixed* system would print, and if it is the same thing, the guard is
decorative.

**A question closed by three nulls is closed — stop buying rows for it.** The
`tome_split` sabotage row (`checkerboard` vs `rank_parity`) has now been paid for in runs
**12, 13 and 14**: −1.51, −0.29, −0.88 on recall, `rank_parity` numerically higher every
time, and D13's bootstrap keeps both run-13 and run-14 versions null under the trimmed
estimator too. That is three runs spent re-answering a question whose answer did not move.
**Do not buy it a fourth row.** The resolution here is *not* "checkerboard wins" — it is
that the split this project shipped has **never beaten the thing it replaced on accuracy**,
and it is kept on a *design* argument (it closes the vertical-redundancy hole that raster
parity leaves 100% open, measured) rather than an accuracy one. Two standing consequences:
(1) `tome_split='checkerboard'` is a **free parameter** in anything a run reports, not a
validated setting, and must be described that way; (2) a row that has returned the same
null three times is buying *precision on a null*, which is only worth GPU budget if the
tight null is itself the deliverable — and here it is not. The general form: before
re-running an arm, ask what a *fourth* identical result would change. If the answer is
"nothing", the cost is the whole price.

**Diagnostics before GPU bookings, and cheap ones can invert the plan.** D1 cost
~15 min of local CPU and flipped a decision about ~16 GPU-hours; D2 cost under a
second (pure numpy on D1's cached `.npz`) and overturned D1's own recommendation.
Diagnostics are `scripts/` citizens like the patchers: reproducible, seeded,
self-describing, cached to `.npz` and `visualizations/` so their numbers can be
re-read without re-running, and they print an explicit verdict with a concern list
rather than leaving the reader to interpret raw statistics. `--n` controls image
count so they stay 15-minute tools. ~~Section F is the acceptance gate: retained
ink above random's ~0.50.~~ ~~**Superseded by D2** — the gate is now **worst-case line
coverage**.~~ **Both superseded by D3 (2026-08-31): there is currently NO validated
cheap acceptance gate for a router checkpoint.** Retained ink is
necessary-but-not-sufficient; min line coverage is worse still (weakest of four
predictors, and two rows with equal coverage differ by 29 pts of recall). Within-mode,
*no* statistic on file correlates with per-image recall above ~0.25. Until something
better exists, **the gate is an actual accuracy row against a random floor and an ink
ceiling at the same budget** — which costs a GPU session, and that is the true price.
A diagnostic's own acceptance threshold is itself a hypothesis; this one has now been
falsified twice in a row, which is worth noticing as a pattern rather than a mishap:
both times the threshold was promoted off a handful of points because it was *cheap*,
not because it was validated.

**Transcribe the verdict — especially when it disagrees.** The most expensive failure
in this project so far was not a bad run; it was a good run whose falsifying output was
never copied out of the log. Phase 2d's cell printed `=> D2 FALSIFIED per-image` on
Kaggle and the claim stayed in this file as an acceptance gate for two more days,
propagating into Conventions, Gotchas, Pending 1b and a cross-session memory. Building
a harness that can falsify your hypothesis buys nothing if you only transcribe the
confirmations. **After every run: read every printed verdict, and write the ones that
contradict this file down first.** Corollary: a per-run results `.zip` contains the
executed notebook and is the only place the verdicts live — the `.json` has the rows
but not the conclusions.

**State a falsifier before running the diagnostic, and calibrate the metric on a
known-good case.** D2's docstring names, in advance, what result would kill each
hypothesis — which is why H2 could be reported as *falsified and inverted* rather
than quietly dropped. It also runs the ink oracle through the same metrics first:
if the oracle had looked bad on them, the metric was broken and every other row
uninterpretable. Without that calibration step a coverage metric that happened to
be miscomputed would have produced a confident, wrong story about the router.

**Select cells by a unique marker, not a loose substring.** The hotfix moved
`RESUME_CKPT` into cell 2, which silently broke
`next(c for c in cells if "RESUME_CKPT" in c)` in `verify_decode_ablation.py` — it
started inspecting the config cell and reported a failure the notebook did not
have. Selectors now key on `torch.load(RESUME_CKPT` and `assert` that exactly one
cell matches.

Discriminative learning rates: router **1e-4** / decoder **2e-5** / unfrozen
encoder tail **1e-5**.

## Gotchas

- **The canonical notebook still carries the BROKEN bipartite split, and it looks fine.**
  `kaggle_token_pruning_ocr.ipynb`'s `BipartiteTokenMerger` is still
  `forward(self, tokens, merge_ratio=0.20, coords=None)` splitting on
  `torch.arange(0, K, 2)`, and neither call site passes an `orig_idx`. The checkerboard fix
  lives in `src/tome.py` and reaches **only** the generated `kaggle_pruning_run.ipynb`, via
  `make_kaggle_pruning_notebook.py` PATCH E. So: **never run the canonical notebook with
  `merge_ratio > 0`.** It will not error, it will not warn, and it will produce a plausible
  "merging costs a couple of points" table measured on a split that strands ~half the
  redundant pairs it was supposed to merge. Runtime tell: cell 4 defines
  `checkerboard_color` in the generated notebook and does not in the canonical one.
  PATCH E asserts on the *old, broken* `arange` lines precisely so that a future
  independent fix to the canonical notebook makes the generator fail loudly instead of
  double-applying.

- **`results/nrns_rp_sweep.json` was produced with merging ON at 0.20, through that broken
  split, and says so nowhere in its own rows.** `run_nrns_rp_sweep.py` constructed
  `AdaptiveDonutOCR(...)` without naming `merge_ratio` while the class default was `0.20`,
  and never passed it to `generate()` either — so the file behind the local "+4.74 pts"
  decoding figure is a *merged* pipeline being read as a pruning-free decoding sweep. This is
  **D5 a second time**: a knob that shaped a run while appearing nowhere in its log. Fixed
  2026-09-16 in three places — the class default is now `0.0`, both local scripts name
  `merge_ratio=0.0` explicitly, and the meta block reads `model.merge_ratio` off the object
  rather than hardcoding it so the line cannot drift from what ran. The **adopted** decoding
  defaults are clean: they came from the notebook's cell-14 ablation, which builds the model
  at `merge_ratio=0.0`. Only the local script's stored rows are contaminated. Any
  `results/determinism_probe_*.json` written before 2026-09-16 has the same defect.

- **`merge_ratio` was the class default, so "has never executed" was false of the repo.**
  It is true only of the *recorded runs*: every filed result used `merge_ratio=0.0`. Two
  local scripts ran the merger dozens of times by inheritance and filed no metric about it.
  The lesson is not about ToMe — it is that "never executed" was inferred from the run log
  rather than from the call sites, and the call sites disagreed.

- **`src/tome.py` merges per image, not per batch, and that is deliberate.** Checkerboard
  membership depends on *which* tokens the router kept, so `K_A` varies down the batch and a
  single batched `bmm` is not available; the loop builds `out_tokens_list` and `torch.cat`s.
  Measured consequence: against a batched implementation the outputs differ by **~1.2e-07 to
  2.4e-07** at B=2 (bit-exact at B=1) — BLAS accumulating in a different order, irrelevant to
  any result. It matters only for verifiers: `verify_tome_merge_port.py` drives the *old*
  merger per image too when checking sabotage equivalence, which restores exact equality, and
  keeps a separate batched comparison bounded at `1e-5` — seven orders of magnitude below the
  ~5.6 that a genuine partition change produces at the same shape. **Widening a tolerance to
  swallow a float discrepancy would have hidden the effect under test**; matching the
  computation shape instead is what keeps the check able to fail.

- **Merged `final_coords` are dead code on both paths.** `BipartiteTokenMerger` returns
  `(out_tokens, out_coords)` and no caller reads the second element: `src/model.py:248`
  binds it as `final_coords` and never uses it, `src/model.py:372` discards it into `_`, and
  the notebook's two call sites discard it as well. Nothing downstream of the merger consumes
  coordinates — the decoder sees tokens only, and the overlay visualisation is built from
  pre-merge `topk_indices`. Keep the return value (it is what makes the merger testable in
  isolation, and `verify_tome_merge_port.py` compares it), but do not reason about a
  coordinate through the merge stage: no code reads it.

- **`tests/test_model_pipeline.py` collects ZERO tests under `unittest`.** It defines no
  `TestCase` — it is a top-level script with asserts and prints. `python -m unittest discover
  tests` reports **16 tests OK** and none of them are from that file, so a green discover run
  says nothing about the pipeline test. It must be run directly:
  `PYTHONPATH=. python tests/test_model_pipeline.py`. Both commands are in every
  verification list in this file for that reason.

- **The notebook prints `EVAL-ONLY mode ... training skipped` on every run that trains.**
  Cell 2 line 71 is `EVAL_ONLY = bool(RESUME_CKPT)` — set from the resume path alone, eleven
  lines *before* `DO_TRAIN` is defined — and the `if EVAL_ONLY:` print below it is not
  conditioned on `DO_TRAIN`. So runs 9, 10 and 11 each logged
  `EVAL-ONLY mode: will load .../adaptive_donut_funsd.pt` and
  `-> training skipped, and Cell 6 will skip building the train set`, then trained for five
  epochs. In run 11's log the contradiction is **two lines apart in the same cell's output**:
  the next line is `PLAN: DO_TRAIN=True -> retrain router WITH pruning ON (keep_ratio=1.0)`.
  **The logic is correct and only the announcement is wrong** — the one functional reader is
  `if EVAL_ONLY and not DO_TRAIN:` in the data cell, which conjoins the flag properly and
  therefore did *not* skip the train set. Do not "fix" the guard; it is the print that is
  unguarded. Consequence for reading logs: `EVAL_ONLY` names the *resume*, not the mode, so
  the only trustworthy statement of what a run did is the `PLAN:` line and the
  `TRAINING WITH PRUNING ON:` header. **Note on cell numbering:** this file numbers cells by
  their index in the `.ipynb` JSON, which past cell splits have desynchronised from the
  notebook's own `# Cell N:` headers — the tracker's "cell 11" is the notebook's
  *"Cell 7: Model Training"*, and the "Cell 6" in the print above is JSON cell 9. Check the
  header comment, not the ordinal.

- **`positive rate 0.420` in the training header is one batch; the number that matches a
  reproduction is `ch` in the epoch line.** The header print sits under
  `if step == 0 and epoch == 1`, so it is `_tgt.float().mean()` on the **first batch of the
  first epoch**. The `ch` field in each epoch summary is the same quantity accumulated over
  every step and divided by the step count — the epoch mean. In run 11 they disagree by 46%:
  header **0.420**, `ch` **0.289 / 0.289 / 0.288 / 0.289 / 0.289**. The run-11 checklist's
  pre-run reproduction predicted **0.283**, so it matched `ch` to 0.006 and looked 32% off
  against the header. **Verify a target's positive rate against `ch`, never against the
  header** — the header is a single-page sample of a quantity whose page-to-page spread is the
  whole point of the ink target. Same shape as the `ov`/`lift` trap in the same line: fields
  printed side by side, computed over different scopes.

- **A diagnostic that defines its own copy of the algorithm it is checking cannot fail.**
  `scripts/diagnose_tome_parity.py` declared its own `checkerboard_color` rather than importing
  `src.tome`'s. Corrupting the **shipped** function to column-only parity — which by construction
  strands 100% of vertical redundancy, the exact bug the fix exists to remove — left the
  diagnostic printing **10/10 PASS** and "Safe to queue the merge sweep". Fixed 2026-09-14 by
  importing the shipped function; it now reports 3 FAILs and exit 1 under that same sabotage.
  **The general rule:** before trusting any verifier, check what it *imports*. If it restates the
  logic under test, it is testing its own restatement. The project already applies this rule to
  documents — `check_writeup_numbers.py` deliberately does not read `AGENTS.md`, because prose
  checked against prose proves nothing — and it applies identically to code. The counterpart
  that stays local is `parity_color`: it models the **deleted** split on purpose, so it is the
  guard proving the harness can still detect breakage.

- **A shape assertion is not a correctness assertion, and ToMe makes the difference invisible.**
  `tests/test_modules.py::test_tome_merger` passes under a sabotaged checkerboard, correctly:
  `merged.shape == (B, K-r, D)` holds no matter *which* tokens were merged, because `M = K - r`
  by construction regardless of how the A/B split falls. Merging entirely the wrong pairs
  produces a perfectly-shaped tensor. Correctness lives in `tests/test_tome_correctness.py`
  (which does catch the sabotage, 3 failures). Do not read a green `test_modules` as evidence
  the split is right.

- **A checker that crashes on the console codec is indistinguishable from a checker that failed.**
  `check_writeup_numbers.py` printed `≥`, Windows' default cp1252 could not encode it, and the
  run died with `UnicodeEncodeError` and **exit code 1** — the same exit code a real numeric
  mismatch produces — after ~50 of 134 checks. The remaining 84 never ran. A documented
  `PYTHONIOENCODING=utf-8` prefix is not a fix, because the failure mode is *forgetting* it.
  Scripts that print non-ASCII should call `sys.stdout.reconfigure(encoding="utf-8")` themselves.

- **PowerShell's `Set-Content -Encoding utf8` corrupts every non-ASCII character in a UTF-8
  file it did not create.** Reading with `Get-Content -Raw` and writing back with
  `Set-Content -Encoding utf8` round-trips the text through the system ANSI codepage (CP1252
  here), so `—` becomes `â€"`, `→` becomes `â†'`, and so on. On 2026-09-06 a five-file bulk path
  rewrite (Pending 12) did this to AGENTS.md: **1117 mojibake sequences, em dashes 936 → 179**.
  It is silent — the file still parses as markdown, the line count is unchanged, and the diff
  looks like it only touched the paths you asked for. It was caught because the corruption
  landed inside Pending 12's own text and turned a sentence into the tautology "`run 7` is
  run 7".
  **Reversal is exact, if you catch it before editing further:** encode the current text to
  CP1252 bytes and decode those bytes as UTF-8 —
  `[Text.Encoding]::UTF8.GetString([Text.Encoding]::GetEncoding(1252).GetBytes($text))` — then
  write with `New-Object System.Text.UTF8Encoding($false)` (no BOM). Verified 0 mojibake, 936 em
  dashes, 0 `U+FFFD`, 5098 lines unchanged, 28 fences balanced, 0 ragged table rows.
  **Prevention:** use the Edit tool for text edits, or `[System.IO.File]::WriteAllText` with an
  explicit `UTF8Encoding($false)`. Never `Set-Content`/`Out-File` a file containing em dashes,
  arrows, `×`, `≥`, or struck-through prose. The wider lesson is the one this file keeps
  relearning: **a bulk operation needs a check on what it was NOT supposed to change.** The
  grep for `results_2` came back clean and the rename was correct — and the file was damaged
  anyway, in 1117 places the grep was not looking at.
  **Second defect from the same command, found 2026-09-06 after the mojibake repair:**
  `Set-Content -Encoding utf8` also prepends a **UTF-8 BOM** to every file it writes. All five
  rewritten scripts got one. This is invisible to `python file.py` — CPython decodes source as
  `utf-8-sig` and strips it — so all four patched scripts *ran green*, which is what let it
  through. It breaks anything reading the text itself: `ast.parse` fails with
  `invalid non-printable character U+FEFF (line 1)`, and `import infer` would too. **Execution
  is not a superset of parsing.** Strip with a byte-level rewrite asserting `raw[3:] == new`
  so nothing but the 3 leading bytes changes.

- **A green count is scoped to whatever the sweep globbed.** "8/8 verifiers exit 0" on
  2026-08-31 was true and still left five files holding a path that had not existed for days,
  because the sweep ran `verify_*.py` and `diagnose_*.py` and those five are named otherwise.
  Same shape as the BOM: the check passed on the members it enumerated. When a defect is in a
  *literal* rather than in behaviour, enumerate by grepping the literal across the whole tree,
  not by running the scripts you can name. `scripts/_final_check.py` (scratch) does this by
  walking every string constant in every script through `ast` and `os.path.exists`-ing the ones
  that look like run paths; a curated list of paths to check reproduces the original blind spot.

- **A verifier log that predates its own input is not evidence, and it is the one stale-green
  shape with no red anywhere.** Found 2026-10-02 on resume. `verify_pooled_corpus_port.py`
  reads the *generated* notebook by `ast`; AGENTS.md recorded it **62/62, exit 0, "against the
  notebook as it now stands"**, and the number was correct — but the only log on disk was
  written at `09:20:12`, against a notebook regenerated at `09:27:30` by a script last edited at
  `09:30:49`, and it said **`61/61`** (the 62nd check arrived in that 09:30 edit). The log path
  the record cited had never existed. **Check mtimes: a log older than the artifact it reads has
  not been run against it, however green it is.** This is the third distinct form of the
  `verify_results_provenance.py` failure and the cheapest to miss — the first *crashed*, the
  second *exited 1 at 19 PASS / 0 FAIL*, and this one **passed, with the right count, from the
  wrong artifact**, so there is no red and no wrong number to notice. Corollary to the resume
  protocol's *"executed, not written"*: a stale green satisfies that rule's letter, so the rule
  needs *"executed against the thing you are claiming it was executed against."* Cheap
  enforcement: have the verifier print the mtime and a hash of every file it reads, so the log
  carries its own provenance instead of relying on the filesystem to be interrogated later.

- **`output_attentions=True` returns `None` instead of raising, under transformers 5.x's default
  SDPA attention.** SDPA (and flash) never materialise the attention matrix, so asking for it
  yields `cross_attentions=None` — or a tuple whose entries are `None` — rather than an error.
  Anything that reduces it (`.mean()`, `.sum()`, a `for` over layers) then produces zeros or an
  empty aggregate, and a *target built from it trains perfectly happily against all-zeros*. Set
  `config._attn_implementation = "eager"` on the decoder **and assert the result is non-empty**
  before using it; D8 and D9 both `raise SystemExit` with an explanation rather than report the
  zeros. This is the single most likely way to build 13(b) and get a null result for a reason
  that has nothing to do with the hypothesis.

  **Measured exactly, 2026-09-02 (transformers 5.4.0, `naver-clova-ix/donut-base`).** The
  behaviour is more specific than "returns `None`" and the difference matters for how you write
  the guard. On a freshly loaded decoder, `_attn_implementation == 'sdpa'` on **both**
  `dec.config` and `dec.model.config`; calling it with `output_attentions=True` logs
  "`sdpa` attention does not support `output_attentions=True`. Please set your attention to
  `eager` ..." — a **warning, not an exception** — and returns `cross_attentions == ()`, an
  **empty tuple**. So the natural guard `if ca is None:` **does not fire**: the `for a in ca:`
  loop simply iterates zero times, and you get a `TypeError`/`ZeroDivisionError` several lines
  later with no hint of the cause. Write `if not ca or ca[0] is None:` — it catches `()`, `None`
  and `(None, None)` alike. `verify_attn_target.py` tests all three shapes, and its
  load-bearing control is a **real** decoder at its default config: it must raise, and must then
  succeed after cell 11's own eager-config lines run against it (the verifier `exec`s those
  lines out of the notebook rather than restating them, so it is the shipped code under test and
  not a paraphrase of it — a restated copy would leave the notebook's version unexercised).

- **Two runs redirected to the SAME output path produce a file that looks complete but has
  been partially overwritten.** `d7_train.txt` was written by a killed run and then by its
  re-issued replacement. `>` truncates at open, but the first process still held its handle and
  kept writing at *its own* byte offset, so the two streams interleaved by position. The result
  passed every casual check — correct header, correct `split=train`, plausible numbers, and the
  `D7 done` footer at the end — while Part B's run-7 block had been replaced by a run of
  whitespace and Part C was gone entirely. **A footer is not evidence of a complete file.** Give
  every run its own output path, or drop the redirect and let the task's own output file capture
  stdout (which also survives the process being killed). Cost of the lesson: the numbers had to
  be re-measured, and for a while the tracker said train-split Part C "was not obtained."

- **`python script.py > out.txt` buffers — a long diagnostic looks hung until it exits.**
  Redirected stdout is block-buffered, not line-buffered, so `out.txt` stays empty (or stops
  at the last 4 KB boundary) for the whole run and then appears complete at once. Watching
  the file to judge progress reports "nothing happening" for a script that is working fine,
  and — worse — gives no partial output if it is later killed. Use `python -u` for anything
  slow enough that you will be tempted to check on it. (Related, and separately load-bearing:
  never read an exit code through a pipe — `cmd | tail` makes `$?` report `tail`'s status, so
  a `SystemExit(1)` reads as success. Redirect to a file and check `$?` directly.)

- **"The STE-only retrain" in cell 11's comment is a misnomer — run 7 was not STE-only.**
  The comment reads *"Sign-fix (Run 7 follow-up): the STE-only retrain kept the router
  sign-inverted (forward router ranked blank paper above text)"*, which invites the
  conclusion that training the router on task CE alone was already tried and already failed.
  It was not tried. Run 7 took cell 11's `else` branch: `lambda_sparsity=2.0`,
  `lambda_entropy=0.05`, `LAMBDA_SAL=0.0` — STE **plus two auxiliary terms**, both of which
  act on the score distribution. "STE-only" described the absence of *ink* supervision, not
  the absence of auxiliaries. The cost of the shorthand is that it retires Pending 13(a)
  without evidence; the fix is to read the branch, not the adjective. See Pending 13 and D7.

- **The `ink`/`random` rows are router-independent at eval, and that is a load-bearing
  accident that could decay silently.** It is what makes D6's cross-run subtraction valid:
  those rows vary the weights while holding selection byte-identical, so they isolate the
  decoder. Two conditions hold it up, both in `src/router.py`:
  (1) an external ranking replaces `rank_by` entirely, so the scorer's values never enter
  `torch.topk`; (2) the STE score-scaling at `src/router.py:92` is gated on
  `self.training and use_ste and select_scores is None`, so at eval `selected_tokens` is a
  bare `torch.gather` and **scores never multiply the kept tokens**.
  Drop either guard — enable STE at eval, or let `select_scores` through it — and router
  weights start leaking into every row. Nothing would fail: the tables would still look
  ordinary and D6-style subtraction would quietly become meaningless. Corroborate before
  trusting it in a future run: `retained_ink` on those rows should be **equal to 3 dp**
  across runs (it was, all seven rows, runs 8 vs 9). If it moved, the guard is gone.

- **`Avg Loss` and `CE` printing identically is NOT evidence the auxiliary term is off.**
  Cell 11 accumulates `epoch_loss += loss_dict['loss'].item()` — the criterion's output —
  while `LAMBDA_SAL * _sal` is added to a *different* variable, the `loss` that reaches
  `backward()`. In the supervised branch `lambda_sparsity` and `lambda_entropy` are both
  `0.0`, so `loss_dict['loss'] == loss_dict['ce_loss']` and the two printed columns are
  identical **by construction**. Run 9 printed five epochs of `Avg Loss 0.3091 | CE 0.3091`
  and it is tempting — I did it — to read that as "the saliency loss never ran". It says
  nothing either way, because the term is unlogged in both directions: the log cannot tell
  `LAMBDA_SAL=0.5` from `LAMBDA_SAL=0`. Confirm which branch ran by reading
  `SUPERVISE_SALIENCY` in the *executed* notebook's cell 2 and the `if SUPERVISE_SALIENCY:`
  block in cell 11, not from the loss line. **Fixed 2026-09-01 by F3** — runs from now on
  print `Obj | CE | aux | sal … | dev | p`, and `sal OFF (LAMBDA_SAL=0)` when the branch does
  not fire. This Gotcha still applies to every log up to and including run 9.

- **A negative `aux` in the F3 epoch line is correct.** `src/loss.py:69` is
  `entropy_loss = -entropy` and binary entropy is ≥ 0, so `lambda_entropy`'s contribution is
  **≤ 0 always** — with `lambda_sparsity=0.0` the whole `aux` column goes negative. Measured:
  `aux` = −0.0099 at p=0.95, −0.0347 at p=0.50 (λ_ent=0.05). Its gradient pushes scores
  *toward* 0.5 from both sides, i.e. toward the constant-collapse state the `p ±std` column
  exists to detect, while making the printed loss look *better*. Weak (|d/dz| ≈ 0.0014) and
  it was competing with `lambda_sparsity=2.0` in runs 7–8, so do not read it as "runs 7–8
  collapsed" — read it as a pressure that was invisible twice over: absent from the config
  cells (D5) and loss-reducing in the log. See F3 for the full table.

- **`min_line_cov` is a per-image key; the row-level key is `mean_min_line_cov`.** Looking up
  `row['min_line_cov']` returns `None` on every row of every ablation file, which reads as
  "Q3 was skipped" when the data is fully present in `row['per_image'][i]['min_line_cov']`
  and aggregated under a different name. `p10_line_cov` and `mean_line_cov` exist per-image
  only, with **no** row-level aggregate at all — compute them from `per_image` if wanted.
  General form: a `.get()` on a row that returns `None` is indistinguishable from a key that
  was written as null, so check the key list (`sorted(row.keys())`) before concluding a
  measurement is missing.

- **The `by` lookup in cell 15 is keyed on `(keep_ratio, select_mode)`, so any extra
  `keep=1.00 router` row silently overwrites the real control.** `by = {(r['keep_ratio'],
  r['select_mode']): r for r in rows}` feeds every Q1–Q5 answer. Row 0 owns
  `(1.00, 'router')`. F2's harness-control row is the same key, which is why it is held in
  `harness_row` and deliberately **not** appended to `rows` — a dict comprehension has no
  duplicate-key error, so the collision would present as Q-section numbers that are quietly
  about a different checkpoint. `verify_harness_control.py` asserts the row stays out.

- **A sampled state-dict fingerprint can be blind to exactly the tensors you changed.**
  Hashing the first/middle/last key of a sorted Donut state dict lands on frozen Swin
  encoder weights, which training never touches — so it compares *equal* across two
  genuinely different checkpoints, and any "did the swap happen?" assert built on it passes
  vacuously. F2 sums every parameter instead (milliseconds on GPU; only deterministic
  equality is needed, not precision). Generally: a fingerprint used to detect a change must
  cover the region that changes, and the cheap way to find out is to mutate one parameter at
  a time and assert the hash moves — `verify_harness_control.py` section 3 does this.

- **An aggregate metric can rank two options in the opposite order from the
  outcome you care about.** D1 measured *summed* retained ink and concluded
  negating the router was a cheap win. D2 found random pruning retains **less**
  ink (0.496 vs 0.576) and reads the page **21 pts better**, because recall is
  gated by the *worst-covered* text line, not by total ink. When picking a proxy
  objective, check whether the true metric is a sum or a **minimum** over regions —
  and never optimise a sum when the thing you care about is bottlenecked.
  ~~Every aggregate statistic mis-orders those two rows; every worst-case statistic
  reproduces the recall order exactly.~~ **That second sentence was the mistake, and
  D3 struck it (2026-08-31).** It generalised a 4-row ordering into a family-level law.
  At n=50 there is no such split: all four statistics land within 0.10 of each other and
  which "family" wins depends on which member you pick. The heuristic above survives
  because it is about *choosing what to optimise*; what does not survive is promoting the
  worst-case statistic to an **acceptance gate** on the strength of four points. A proxy
  that orders a handful of rows correctly has been *tested* on a handful of rows.
- **A statistic can correlate with an outcome and still be useless as a gate.** Run 8 at
  keep=0.35: `router` has min line coverage **0.127** and reads **77.80**; `random` has
  min coverage **0.137** — slightly *better* — and reads **48.37**. Equal on the
  statistic, 29.42 pts apart on the thing that matters. No amount of correlation rescues
  a gate that two same-budget rows can straddle like that, which is why D3 retired min
  coverage on two independent grounds (weak correlation *and* this counterexample) rather
  than one. Ask of any proposed gate: "can I find two rows it calls equal that differ by
  a lot?" — before adopting it, not after.
- **Post-encoder pruning means the token count is NOT a cost axis.** The router sits
  after the frozen Swin, so all 4800 tokens are computed at every `keep_ratio`; the only
  thing that shrinks is decoder cross-attention KV length. Measured: −65% visual tokens
  → −7.1% wall-clock (0.18–0.22× proportional), and latency correlates with *generated*
  tokens (r ≈ +0.93/+0.98), not visual ones (r ≈ −0.10/+0.15). Anything that reads a
  compression percentage as a speedup percentage is wrong by roughly 5×, and the
  architecture — not the measurement — is why. Cell 15's Q5 note currently states the
  opposite; Pending item 7.
- **A control stops being a control the moment the weights change.** The `keep=1.00` row
  was introduced to reproduce run 6's 77.74 and catch harness breakage. Runs 7–8 kept the
  row but retrained the model, so its drift (−10.93, +0.51) now conflates two causes and
  can be told as either story — which makes it unfalsifiable, which makes it not a
  control. A control must hold *everything* fixed, including the thing the run is
  changing; if the run changes the weights, the control row needs the old weights loaded
  back. Pending item 4.
- **A stale mode dispatch produces PASSes on paths that never ran.** `SELECT_MODES` grew
  from four entries to six; `verify_select_modes.py`'s inline `kwargs` dispatch handled
  three and fell through to `{}` for the rest, so `stratified` and `stratified_negated`
  were exercised as plain-`router` calls — and the check "stratified: selected exactly
  K=24" *reported PASS* on a router selection. The pairwise-distinctness checks are what
  caught it, i.e. the verifier survived only because it happened to contain one test that
  compared modes to each other. Fixed by making unknown modes raise
  (`scripts/verify_select_modes.py:151`). **General form: any `if/elif` chain over a
  collection defined elsewhere needs a raising `else`.** A silent default in a *verifier*
  is worse than a bug in the code it verifies, because it converts an untested path into
  a green check.
- **The "half these tokens are droppable" premise is a property of the WEIGHTS, not the
  page.** Identical FUNSD pages, identical ink masks: run 7 printed `Q2 PREMISE IS WEAK`
  (ink oracle −10.06 vs full page) and run 8 printed `Q2 PREMISE HOLDS` (−3.46). The page
  did not change; the decoder did. So "how much can be pruned" is not a fact about the
  dataset that can be established once and reused — it is re-opened by every retrain, and
  a premise check must be re-run per checkpoint rather than cited from an earlier run.
- **`nn.Sigmoid()` at the end of a scoring head plus `*_with_logits` downstream is a
  double sigmoid, and it fails QUIETLY UPWARD.** `PatchSaliencyRouter.scorer` ends in
  `nn.Sigmoid()` (`src/router.py:25`) and the ink-BCE term in
  `kaggle_pruning_run.ipynb` cell 11 passes its output to
  `binary_cross_entropy_with_logits`. It does not crash and it is not inert — sigmoid is
  monotone, so the ranking still trains and the run still *succeeds*, which is why it went
  unnoticed through the project's headline result. What it costs: predictions confined to
  [0.500, 0.731], a loss that floors at 0.313 instead of ~0, and a gradient attenuated
  **3.7× on already-correct tokens rising to 112× on the ones the scorer is most wrong
  about** — the attenuation *grows with the error*, so no loss weight can absorb it (D4).
  **General form: whenever a `*_with_logits` loss is added to an existing head, read the
  head's last layer.** The two conventions collide precisely because both are correct in
  isolation — a scoring head that must return [0, 1] wants the sigmoid, and a numerically
  stable BCE wants the logit. Pick one place for the squash and write down which.
  **Resolved 2026-08-31 (F1): the squash lives in the head.** The loss recovers the logit
  with `torch.logit(p.clamp(1e-6, 1-1e-6))` instead of the head giving it up, because three
  other consumers read that same tensor as a probability (D5). If you ever need the logit
  elsewhere, add it as a *second* output — do not change the existing one.
- **The cell with no verifier is where the bug was.** Runs 7–8's notebook differs from the
  canonical one in exactly three cells; the selection mechanism (cells 4/7/15) is
  byte-identical and covered 44/44 by `verify_selection_ablation.py`, and the new training
  cell 11 had no execution check at all. D4's defect is in cell 11. This is a coverage
  argument, not a coincidence: **when adding a cell, note whether any verifier reaches
  it** — and if the answer is no, that cell is where to look first when a result is
  surprising in either direction.
- **Spatially clumpy selection is not a defect here — it is what winning looks
  like.** The ink oracle has the *longest* contiguous drop-runs of any mode
  (mean 5.54 vs random's 1.97) and the best accuracy, because long runs are the
  blank margins between words. D1's section E treated spatial contiguity as a
  virtue and scored a whitespace detector as healthy for it; the honest reading is
  that contiguity is uninformative about quality in *either* direction. Do not add
  a spatial-spread term to a router loss.
- **`merge_ratio=0.0` in every run means `BipartiteTokenMerger` has NEVER
  EXECUTED.** `src/tome.py:39` returns `tokens, coords` unchanged when
  `merge_ratio <= 0.0`. Half the headline architecture is inert across runs 2–6 —
  the same failure mode as `no_repeat_ngram_size=3`, found the same way (reading the
  code instead of trusting the config). ToMe is training-free by design, so it costs
  nothing to include in the sweep and should be.
- **At `keep_ratio=1.0` the router is not a no-op — it PERMUTES.** `torch.topk(...,
  sorted=True)` in `src/router.py:60` returns indices in *descending score* order,
  and the gather at line 64 reorders the token sequence accordingly. Harmless while
  `merge_ratio=0.0` (cross-attention is permutation-invariant and nothing is
  dropped), but **ToMe's bipartite split is by sequence parity**
  (`arange(0,K,2)` / `arange(1,K,2)`, `src/tome.py:47-48`), so the moment
  `merge_ratio > 0` it will partition by score-rank parity rather than spatial
  adjacency — which contradicts its own docstring about "compacting continuous text
  regions". Decide this before the merge sweep: either pass `sorted=False` plus a
  positional re-sort of the kept indices, or accept score-order partitioning
  deliberately and say so.
  **Why this is the *only* place the damage lands, which is also why 10 runs missed it
  (2026-09-09).** ToMe's similarity search is **global** — every A is compared against
  every B (`src/tome.py:63`) — and the coords it carries are **never used in the
  matching**, only averaged into centroids afterwards. So the A/B parity split is the
  **sole** consumer of sequence order in the entire pipeline, and the decoder's
  cross-attention is permutation-invariant. The router's permutation is therefore inert
  everywhere except inside a component that `merge_ratio=0.0` short-circuits. A defect
  that is invisible until you enable the feature it breaks.
- **The parity fix is a HALF-fix, and the 0.0% figure that makes it look complete is a
  fixture artifact (measured 2026-09-09).** `diagnose_tome_parity.py` declares its
  redundant pairs as `(0,1), (2,3), (4,5), …` — **horizontally** adjacent pairs, each
  straddling an even/odd boundary by construction — so "spatial ordering ⇒ 0.0% missed"
  is true *of horizontal redundancy only* and cannot say anything about the vertical
  case. The grid is **80 rows × 60 columns**, and **60 is even**, so token `i` and the
  token directly below it (`i + 60`) have the **same parity always**. Re-running the
  script's own machinery with vertically-adjacent pairs:

  | ordering / redundancy type | missed |
  |---|---|
  | spatial, horizontal duplicates | 0.0% |
  | spatial, **vertical** duplicates | **100.0%** |

  So Pending 15's option (b) — `sorted=False` + positional re-sort — would recover
  horizontal redundancy and **none** of the vertical, on a document task where a text
  line's strokes span several patch rows and inter-line whitespace is the most redundant
  thing on the page. A split that actually works needs to not be raster parity at all:
  **checkerboard on `(row + col) % 2`** puts every 4-neighbour in the opposite half and
  costs the same. Recorded because the on-file recommendation was written against a
  number that only covered half the failure, and would have been implemented, swept, and
  read as "merging does not help this model".
- **The checkerboard split is ORDER-INDEPENDENT, which is the property that makes it the
  right fix (measured 2026-09-09).** Full 3×2×2 table, `diagnose_tome_parity.py`'s own
  `merged_pairs()` machinery, N=4800, merge_ratio=0.5:

  | split | redundancy | raster order | router-sorted order |
  |---|---|---|---|
  | parity (current) | horizontal | 0.0% | 49.3% |
  | parity (current) | vertical | **100.0%** | 50.5% |
  | parity (current) | diagonal | 24.7% | 62.7% |
  | **checkerboard** | horizontal | **0.0%** | **0.0%** |
  | **checkerboard** | vertical | **0.0%** | **0.0%** |
  | checkerboard | diagonal | 100.0% | 100.0% |

  Both checkerboard columns are identical, because membership is computed from the
  token's **original page position**, not from where it landed in the pruned sequence.
  **So the router does not have to change at all** — no `sorted=False`, no positional
  re-sort, and no risk to the `topk`/gather path that all ten runs depend on. That is a
  strictly smaller blast radius than the `sorted=False` fix this file recommended for
  ten days, and it fixes strictly more.
  **The honest cost:** diagonal-only redundancy goes 24.7% → 100% missed, because
  diagonal neighbours share checkerboard colour. Acceptable but not free, and the reason
  it is acceptable is mechanical rather than hand-waved: ToMe merges `r` pairs total by
  giving each A its single best B partner, so what it needs is *a* good partner in the
  opposite half, not that every redundant pair be reachable. Under checkerboard every
  token has all four page-neighbours in the opposite half. A token whose only redundancy
  is diagonal — not horizontal, not vertical — is a corner case on a document page.
  **Precondition, already satisfied:** the fix needs a trustworthy token↔grid mapping.
  That is `TOKEN_GRID = (80, 60)` (`src/model.py:14`), the same mapping `patch_ink()`
  uses, and it is indirectly validated by the ink oracle working at all — retaining 0.994
  of a page's ink at keep=0.50 is impossible if the grid mapping is wrong. Note
  `_generate_2d_coords` **re-derives** H/W from N and a hardcoded 3:4 aspect instead of
  reading `TOKEN_GRID`; it agrees at N=4800 (60, 80) and is a second source of truth for
  the same fact that would diverge at another resolution.
- **The router has never been trained under selection pressure, and it shows.** At
  `keep_ratio=1.0`, `K = N`, so top-k keeps everything and no token is ever dropped.
  The STE multiplier `1.0 + (w - w.detach())` has value *exactly* 1.0, so the
  forward pass is unaffected by scores, while gradient still reaches the scorer.
  The router therefore learned a "does scaling this token's magnitude help" proxy —
  **never** feedback about the consequence of *removing* a token. This was logged as
  "the single most important unknown before the sweep"; **Diagnostic D1 resolved it,
  badly**: the proxy is anti-correlated with ink (r ≈ −0.24), the router retains
  34–38% of a page's text where random pruning retains 50%, and negating its score
  beats random. Training a top-k router at `keep_ratio=1.0` does not merely fail to
  teach saliency — it actively teaches the inverse. The sigmoid-uniformity risk also
  logged here did **not** materialise (std 0.209, 0% saturation, 4799/4800 unique).
- **Trained, spread, content-dependent and clustered are all true of a router that
  keeps blank paper.** D1's sections A–E all came back clean and the verdict printed
  "no concerns"; section F then showed the ranking was worse than random. Each of
  A–E measures that the scorer does something *consistent*, none measures whether it
  does the *right* thing — and blank regions are contiguous, so the clustering check
  scored the failure as a success. **When validating a ranking, measure it against
  the actual objective (here: does the kept set contain the ink?) and against the
  strongest cheap baseline, not against degenerate ones.** Beating "random mask" and
  "untrained projection" proved nothing; the 0.503-vs-0.333 clustering headline was
  mostly inherited from Swin feature smoothness (an untrained router scores 0.455).
- **Include an oracle and a random baseline in the same table as the thing you are
  testing.** In D1 the numbers only became readable once random (0.50) and an ink
  oracle (1.00) sat beside the router (0.38) — 0.38 alone looks like a plausible
  score. A metric with no baseline is a number, not evidence.
- **A hyperparameter lives in four places, not one.** The notebook is what trains,
  but `src/model.py`, `infer.py` (×3: function default, CLI default, help text) and
  `scripts/geom_probe.py` all carried their own copy of `repetition_penalty=1.3`.
  Patching only the notebook would have left the bug shipping through `infer.py` and
  silently skewing any future geometry probe. **After changing a decoding or model
  default, grep the whole repo for it.** Archived `__notebook__.ipynb` files under
  `pruned_ocr_results_*/` and `run 5/` are run *records* — never patch those.
- **Running the tests:** `pytest` is **not installed** locally; run each
  `tests/test_*.py` as a script **with `PYTHONPATH=.`**. `test_modules.py` **and
  `test_tome_correctness.py`** both do `from src.… import …` and fail with
  `ModuleNotFoundError: No module named 'src'` without it.
  `test_end_to_end.py` needs donut-base, which is already in the HF cache — run it
  with `HF_HUB_OFFLINE=1` to prove it is not silently re-downloading.
  **Its failure mode is a false alarm that looks like a broken repo:** `python -m pytest
  tests/` dies with `No module named pytest`, and if you only read exit statuses that
  presents as **5 failing tests**. They are written as `if __name__ == "__main__"`
  scripts, not pytest collections, so direct invocation *is* the intended one.
  **Corrected 2026-08-31 (F2 regression run):** this entry previously said all five exit 0
  "when invoked directly" and named only `test_modules.py` as needing `PYTHONPATH`. Measured:
  bare `python tests/test_x.py` gives **3 pass / 2 fail**; `PYTHONPATH=. python tests/test_x.py`
  gives **5/5**. The two failures surfaced immediately after a notebook edit and read as
  breakage caused by it, when the edit touched no Python module — before attributing a red
  test to your change, check it was green under the *same invocation*, because "it passed
  last time" is not a control if last time used a different command.

- **`repetition_penalty` is not a mild knob on long documents — it is a length
  cap.** At 1.3 it cost 27 pts of recall and 82 pts of valid-JSON rate (run 6).
  HF divides the logit of every token already emitted; a full-page form re-uses its
  whole vocabulary, so eventually only EOS is unpenalized. Sequence-length metrics
  will show this and accuracy metrics alone will not. **Default is now 1.0 — do not
  raise it.** Corollary: it is a no-op on logits of exactly 0.0 (positive scores are
  divided, negative multiplied), which makes it easy to write a test that wrongly
  concludes it does nothing.
- **A no-op setting can look like a working setting for four runs.**
  `no_repeat_ngram_size=3` sat in the config since run 2 and was bit-exactly inert
  the whole time, because rp=1.3 upstream meant nothing ever repeated. Two
  interacting knobs, one masking the other. Vary knobs independently or the
  attribution will be wrong even when the fix happens to work.
- **Kaggle silently gives you a CPU session.** If no accelerator is selected,
  `torch.cuda.is_available()` is False, the notebook prints `Using device: cpu`,
  and everything proceeds — slowly and with different numerics. Cell 2 now asserts
  `device.type == 'cuda'` unless `ALLOW_CPU=True`. **Always check the accelerator
  before Run All.**
- **Kaggle mount paths are not what you'd guess.** Run 6's checkpoint landed at
  `/kaggle/input/datasets/nafis8766/token-pruning-dataset/adaptive_donut_funsd.pt`
  — note the extra `datasets/<user>/` segments that no local layout suggests. Never
  hardcode a mount path from memory; run `!ls -R /kaggle/input/` or let cell 2's
  resolver find it.
- **`DonutSwinModel.layernorm` exists on transformers 4.x (Kaggle) but not 5.x
  (local).** Hardcoding `model.model.encoder.layernorm` crashes with
  `AttributeError`. Always `getattr(model.model.encoder, 'layernorm', None)`.
  Run 5's log printed `Unfroze top 1 Swin stage(s): 25.2M` with no `+ final norm`
  — Kaggle also lacks it, so this guard is what kept the run alive.
- **Partial unfreeze is memory-safe by construction.** The frozen prefix emits
  non-grad outputs so autograd saves no activations for it; the graph begins at the
  unfrozen tail. Cell 7's `forward()` auto-detects this and drops the `no_grad`
  wrapper — no model-class edit was needed:
  ```python
  encoder_is_frozen = not any(p.requires_grad for p in self.model.encoder.parameters())
  ```
- **HF `setdefault` semantics**: explicit kwargs override the defaults;
  `no_repeat_ngram_size=0` and `repetition_penalty=1.0` disable those processors;
  `min_new_tokens` suppresses early EOS.
- Notebook is **nbformat 4.4** — no cell `id` fields, which is correct (ids are
  4.5+). Cell 1's `!pip install` never parses as Python; pre-existing, ignore it.
- Diagnostics need `PYTHONIOENCODING=utf-8` (cp1252 otherwise).
- `reading_order_words()` fixes FUNSD's annotation-order labels.
- `infer.py` geometry fix for internet images: `do_align_long_axis=False` +
  Lanczos upscale (`min_long_edge=1500`).
- Local env: python 3.10.4, torch 2.12.1+cpu, transformers 5.4.0. **Kaggle runs
  transformers 4.x** — version-sensitive code must work on both.
- **The notebook duplicates the model classes; `src/` is not its source of truth.**
  Cell 4 has its own `PatchSaliencyRouter`, cell 7 its own `AdaptiveDonutOCR`, and the
  notebook imports nothing from `src/`. Any mechanism added in `src/` must be ported
  by patcher before a notebook cell can use it, and the port must be checked
  **numerically** against the original (same weights, same input, assert identical
  output) — a paraphrase that merely looks right makes Kaggle rows silently
  non-comparable to local ones. `scripts/verify_selection_ablation.py` §1 is the
  pattern.
- **A global top-k can only starve a region when the region it prefers is at least as
  large as the budget.** Obvious in hindsight, but it invalidated a verifier fixture:
  5 hot rows out of 80 (300 tokens) against K=2400 starved nothing, because the
  leftover budget has to land *somewhere*. Bounds when per-row stratification can
  help at all — see Pending 1d.
- **A grid guard keyed on token *count* passes for any reshape with the same
  product.** `patch_ink` compares `gh*gw` to `num_tokens`, so 96×50 and 80×60 are both
  4800 and both accepted. Correct behaviour, but it means "non-standard grid" test
  fixtures must actually change the product to exercise the raise path.
- **Long eval loops must checkpoint their results per row.** A local n=50 × 5-config
  run was killed at 30/50 of row 1 and lost everything, because the harness wrote its
  JSON only after the last row. Cheap to avoid: dump after every row with a
  `complete: false` marker in `meta`.
- **`<s_doc>` is not a special token in this tokenizer.** It tokenizes to **five**
  ordinary subwords — `['▁<', 's', '_', 'doc', '>']` → `[41040, 46192, 41403, 35702,
  34791]` — whereas `</s>` and `<s>` really are single ids (2 and 0). The Donut paper
  adds task tokens to the vocabulary; this project never did (`len(tok) == 57525`,
  unextended). **It is harmless because train and eval agree**: cell 13 builds
  `prompt_ids` and the dataset builds `f"<s_doc>{json}</s>"` through the same
  `add_special_tokens=False` path, so the model learned to condition on that 5-token
  sequence. Do not "fix" it — `tokenizer.add_tokens(['<s_doc>'])` would take the vocab
  to 57526, resize the embedding matrix, break `load_state_dict` on **every existing
  checkpoint**, and change the prompt's meaning, requiring a full retrain. The only
  live consequences: 5 prompt tokens count against `max_length`, and the pieces are
  shared with ordinary text.
- **A defaulted hyperparameter is an undeclared one.** `lambda_entropy = 0.05` shaped
  every run to date and appears in **no config cell** — cell 11 never passes it, so it
  comes from `src/loss.py`'s signature default. It is not negligible (up to 42% of the
  saliency gradient) and it pushes scores *toward* 0.5, i.e. against the ink-BCE. Nobody
  chose it and nobody reading the notebook could see it. Worse, it changes *relative*
  strength when you re-tune a different knob: halve `LAMBDA_SAL` and the entropy term
  goes from 42% to 170% of it without anyone editing a line. **Grep the loss signature
  for `lambda_*` defaults before calling a run one-knob.**
- **Before changing a value's units or range, enumerate its readers.** D4 called its fix
  "one line" — a claim about the diff, not the blast radius. `scores` turned out to have
  three consumers (ink-BCE, sparsity, entropy) plus the STE, and two of them require a
  probability, so the "clean" logit fix would have silently retargeted the entropy
  regularizer at whichever tokens happen to have a logit in (0,1). `grep` for the field
  name; do not reason from the one call site in front of you.
- **The checkpoint is prompt-dependent — unprompted generation is garbage.** Same run-8
  weights, same image, one difference: with `decoder_input_ids=<s_doc>` the output is
  `'<s_doc>{"text": "ATT. GEN. ADMIN. OFFICE Fax: 614-466- 5087…'`; with no prompt it
  is `'<s>"}"}- 12- 12- 12- 29-…'`. Not a defect — the real eval always prompts (cell 15
  line 111 passes `decoder_input_ids=prompt_ids`, cell 13 sets `TASK_PROMPT = '<s_doc>'`)
  and the model was never trained to start from bare `<s>`. But `src/model.py:generate()`
  falls back to `decoder_start_token_id … or 0` = `<s>` when no prompt is passed, so
  **any caller that omits the prompt gets fluent-looking nonsense with no error.** If a
  new harness ever reports catastrophic numbers on known-good weights, check this first.
- **The notebook's cells share one namespace, so cell 7 and cell 11 use names only cell 2
  imports — every extraction-based verifier has to reproduce that.** Measured 2026-09-02:
  cell 2 `import gc`, and cells **7 and 11 both call `gc.collect()` without importing it**.
  On Kaggle that is fine (one global namespace); in a verifier that `exec`s cells 4/5/7 into
  a dict it is a `NameError` — and note *where* it fires: not at class-definition time but
  inside `AdaptiveDonutOCR.__init__`, i.e. **after** a 200M-parameter backbone has loaded,
  which is why `ast.parse` and `grep` both stay clean. This is the same shape as D5's
  defaulted `lambda_entropy`: a dependency that is invisible in the cell you are reading.
  The fix that stops it recurring is to seed the namespace from **cell 2's own import
  statements** (`ast.walk` for `Import`/`ImportFrom`, then `exec` them) rather than from a
  hand-written list of the names you happen to remember — `verify_attn_train_step.py` does
  this, and asserts cell 2 still imports `gc` so the day that stops being true is reported
  as a real defect instead of silently passing. Do **not** "fix" this by adding `import gc`
  to cells 7/11: the coupling is harmless on Kaggle and the notebook is generated, so the
  edit would have to live in the generator for no behavioural gain.
- **`python foo.py | tee log` reports tee's exit status, not the script's.** Bit me on
  2026-09-02: the pre-flight died with a `NameError` traceback and the harness reported
  **"exited with code 0"**. Every convention in this file about pre-registering thresholds
  and asserting values is worthless if the pipeline launders the exit code — a CI step or a
  `for f in …; do …; done` suite loop keyed on `$?` would have recorded that crash as a
  pass. Redirect (`> log 2>&1`) or set `set -o pipefail`; do not pipe a verifier into
  anything. The suite loop in Conventions is safe because it runs `python -u "$f"` bare.

---

## Changelog

**The dated changelog lives in `AGENTS-ARCHIVE-CHANGELOG.md`**, together with the Kilo
contributions section. It is the longest single section in the project and is read
retrospectively rather than at the start of a session, which is why it is not loaded here.
Append new entries **there**, newest-last, in the existing format — and record anything that
changes a number in this file, because the archives are not covered by any audit.

- **2026-09-24 — AGENTS.md restructured; three archives created; nothing deleted.**
  This file was ~~**8,945 lines**~~ **10,276 lines / 809,072 bytes /** ~~≈202K~~ **≈230K tokens**
  and is injected in full as
  project instructions on **every** session, so that cost was paid unconditionally — it was
  18× the next-largest doc in the repo and ~~on its own enough to fill a 200K context window~~
  **on its own ~30K tokens LARGER than a 200K context window** (2026-09-25 measurement).
  The historical bulk moved verbatim into `AGENTS-ARCHIVE-DIAGNOSTICS.md`,
  `AGENTS-ARCHIVE-RUNS.md` and `AGENTS-ARCHIVE-CHANGELOG.md`.
  **Three properties of how it was done, each a standing convention of this project applied to
  itself:**
  (a) **Archive, never delete.** Strike-and-supersede exists because the *reason* a claim was
  wrong is worth more than the claim; deleting the record to save tokens would have traded the
  project's main methodological asset for a context-window win.
  (b) **The edit is pure line slicing plus purely additive new text.** The only authored prose
  is the compact diagnostics index, the archive pointer, the per-archive headers and this
  entry. No existing sentence was rewritten, so no non-ASCII character was retyped — which is
  the 2026-09-06 mojibake failure mode avoided by construction rather than by care.
  (c) **A byte-accounting assertion, not a grep.** `scripts/split_agents_md.py` asserts that
  the eight slices concatenated in original order reproduce the source byte-for-byte before it
  writes anything. That is the "check on what it was NOT supposed to change" the 2026-09-06
  incident called for: there, the grep for the intended change came back clean while 1117
  unrelated characters were corrupted.
  **What deliberately stayed:** the `▶ TODO` queue and resume protocol (two saved memories name
  this file and this section by name, so moving it would break resume), the four claims, the
  file map, the eval protocol and run table, **the run-17 pre-registration** — the rule T4/T7
  are about to be scored against, which must be readable without opening an archive — and
  Conventions + Gotchas, the two sections that are advice for work *about to happen* rather
  than a record of work already done.
  ⚠ **The archives inherit the staleness problem the four prose docs already have, and have no
  audit at all.** `check_writeup_numbers.py` does not read them. When a figure is corrected
  here, grep all three archives for the old value — this file now has four derived documents
  and three archives downstream of it, and only `WRITEUP.md` is checked.
  ⚠ **`scripts/check_agents_md_format.py` was re-run against the trimmed file and each archive**
  after the split; the invariants it pins (balanced fences, no ragged table rows, no paste
  debris) hold on all four.
