# AGENTS-ARCHIVE-DIAGNOSTICS.md — diagnostics, fixes, and runs 7–10

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**,
including where this file contradicts a correction made there later. This archive has **no
numeric audit** — when a figure is corrected in `AGENTS.md`, grep here for the old value.

Holds: the full diagnostics index with its per-script notes, **D1–D14**, **M1**, fixes
**F1–F3**, the run 7/8/9 sections, the run 9 and run 10 launch checklists, and the run 10
result. Read the section here before citing any D-number — several of them are on record
mainly for the caveat attached to the finding.

---

**Diagnostics index.** Each is a standalone script that re-derives its numbers from
cached artifacts, so any claim below can be rechecked without a GPU:

| # | script | what it established |
| --- | --- | --- |
| D1 | `scripts/router_score_probe.py` | The trained router is an *inverted* saliency detector (r ≈ −0.24 vs ink). |
| D2 | `scripts/diagnose_selection_geometry.py` | Retained ink is the wrong objective. **Its own acceptance gate is now withdrawn — see D3.** |
| D3 | `scripts/diagnose_selection_statistics.py` | Runs 7–8 already answered three open questions; min-coverage gate falsified; the efficiency claim fails; "beats the oracle" is probably co-adaptation. |
| D4 | `scripts/diagnose_saliency_loss.py` | The ink-BCE loss behind the sign-fix is fed a probability where it expects a logit — so run 8's numbers are a **floor**. **FIXED 2026-08-31 (F1); the script now exits with a `SUPERSEDED` banner.** Its *recommended* fix was wrong — see D5. |
| D5 | `scripts/diagnose_saliency_loss_coupling.py` | D4's *recommended fix* was unsafe: `scores` has three consumers and two need a probability. Also: `lambda_entropy=0.05` was never chosen, and becomes dominant once `LAMBDA_SAL` drops. **Its own prescription was then superseded too** (autocast) — see F1. |
| D6 | (no script — derived from run 9's own rows, see its section) | The weight change and the selection change point opposite ways: F1's mechanism worked *and* cost accuracy (−2.5 pts at keep=0.50, −3.9 at 0.35). Retained ink is ruled out as an **objective**, upgrading D2 from correlation to intervention. |
| D7 | `scripts/diagnose_ste_signal.py` | **Pending 13(a) is dead.** Run 7's auxiliaries were a minority of the router gradient everywhere measured (2.5–17%), so run 7 was predominantly STE-driven — and it scored 18.80 recall. CE-through-STE is large but **incoherent** (cos 0.21 across pages) where ink-BCE is smaller-to-larger but **systematic** (0.85–0.90); the STE reaches exactly K of N tokens, so the dropped half is unreachable. Falsified my own collapse hypothesis, twice. |
| D8 | `scripts/diagnose_attn_target.py` | **13(b)'s target is real, on two pre-registered tests.** Decoder cross-attention is near-orthogonal to ink (r **+0.083**, overlap 0.62) and is *not* a fixed positional mask (top-5% centroid spread **6.12** grid rows vs ink's 1.81). `r(attn, router score) = −0.045` — the router is **uninformed** about what the decoder looks at. Independently reproduced D1's `r(score,ink) = −0.226` to three decimals. Two self-corrections: Test 1's thresholds were necessary-not-sufficient (a constant mask passes them), and `cosine` was the wrong statistic to threshold on (inflated for non-negative vectors — the router-score row reads cos +0.83 at r +0.10). |
| D9 | `scripts/diagnose_target_learnability.py` | **The attention target is reachable by the existing scorer — 13(b) is cleared to build.** A fresh copy of the router's own MLP, fit on 5 pages and scored on 3 **held-out** pages, reaches AUC 0.976 against a shuffled floor of 0.498. But the headline number is not the AUC: a **constant map with no features scores 0.764**, so the reportable quantity is the page-specific **lift, +0.212 for attention vs +0.151 for ink**. Establishes **reachability, not merit** — every number is scored against the teacher's own attention, and D6 is the standing warning about optimising proxies. |
| D10 | `scripts/diagnose_target_drift.py` | **The last precondition for 13(b) holds: the on-the-fly target is effectively stationary, and it is page-specific.** The encoder is *not* frozen during the retrain (`UNFREEZE_STAGES = 1`), so I had flagged "the router chases a moving target" as an unverified risk. Run 5 → run 9 is a completed run under the identical config, so the drift is already on disk: features move by median rel-L2 **0.0918** (**7.6× the 0.012 weight drift** — worth measuring, since weight drift bounds nothing), yet the recomputed top-K target keeps **S = 0.9613** of its positives (~93 of 2400 change) against a different-pages floor of **X = 0.6246**, gap **+0.3367**. Both thresholds were pre-registered in code before reading. The floor is the point: `X = 0.6246` is a **second independent estimate of the inflated null** that the ink-overlap number was once read against as if it were 0.500. |
| D11 | `scripts/eval_budget_binding.py` | **13(b) is DEAD — and this is the informative negative, not another null.** Run 10 was flat at keep=0.50 because the budget did not bind there. Re-asked at budgets that *do* bind (paired, n=50, local CPU): the attention target **loses to ink by −5.63 pts at keep=0.25 (t −2.40) and −12.81 at keep=0.20 (t −6.23)**, monotone in tightness (+0.20 → −3.84 → −5.63 → −12.81). Mechanism is in the ink column: run 10's router retains ink **0.355** and **0.257** against random's **0.251** / **0.201** — at binding budgets it selects barely better than randomly. All 10 controls pass with the 6 ink gates **exact to 3 decimals**. Also fixes the run-10 diagnosis (keep=0.35 was non-binding too, so *both* of that run's headline rows were unwinnable) and settles Pending 8: pruning 4800 → 960 tokens buys **1.04×** wall-clock. See the D11 section. |
| D13 | `scripts/diagnose_merge_power.py` | **The ToMe blocker is the instrument, not the merger — and this reorders the whole queue (2026-09-22, extended 2026-09-23, local, 36/36 controls).** Three runs read UNDERPOWERED on the merge axis and three sessions read that as a fact about ToMe. It is a fact about **n=50 against a per-document sd of 11–13 pts**: res ≈2.9–4.3 against effects of 0.5–3.1, so the verdict was structurally guaranteed. The sharpest single number: **M=1920 merge-vs-prune — the question ToMe exists to answer — observed +2.86 at res 3.16 and needed n ≥ 62. Run 13 had 50. It missed by twelve documents.** Variance is **not** document length (CUPED on `n_text_rows` buys +0.0–3.7%); it is concentrated — **5 of 50 documents carry 75.6% of the sum-of-squares**, two of them (−57, +44) dominating — which makes the pre-registered bootstrap-on-means the *least* powerful estimator available for this data. A 10% trimmed mean with a **Tukey–McLaughlin** SE buys ~30% of resolution for zero GPU time and is discriminating, not permissive: tighter on **6/6** merge contrasts, both sabotage rows stay null, run 14's primary stays null, the −64 pt `negated` control still excludes zero (⚠ *by ~10σ; it does **not** resolve in the tight-estimate sense — its own half-width is 6.09 at n=50, see D14 §5, which corrected this clause on 2026-09-23*). **Two self-corrections are the reusable part.** (i) The first pass used `stdev(trimmed)/sqrt(n_trimmed)` as the SE — the natural thing to write, **33% too small**, and it manufactured a RESOLVED verdict on the M=1440 pair that the correct SE deletes; `res_trimmed_naive()` survives in the script only so a control can pin the gap. (ii) The control "trimming is tighter everywhere" **failed at 9/10** and was right to: trimming is *wider* on the light-tailed `negated` control (5.31 → 6.09), because a trimmed mean only wins on heavy tails. An estimator that were tighter everywhere would be measuring nothing, so that exception is now an asserted control rather than an embarrassment. **Does not license switching estimator after seeing an effect** — it is an input to Pending 18 (now T1) and must be written before run 17 sees a number. Note it cuts *against* this project's claim 3: the trimmed estimate flips m=0.20's sign from **+0.54 to −0.65** (both nulls, but "free" is not sign-robust). **Extended 2026-09-23 (section 5, +6 controls, → 36/36): the tail, and it changes T1's answer.** Asking what the trim *discards* rather than what it saves: **every** merge contrast contains a catastrophically degraded document (−38.95, −42.86, −47.67, −56.98, and **−72.34** inside run 14's published *"no measured cost"* null, whose trimmed mean is −0.17). Measured against a deterministic matched-normal null whose own worst document sits at **2.33 sd** on every contrast, the real worst sits at **3.47–5.01** — a 1.49–2.15× margin, so this is a statement about the distribution and not about n. And the trimmed mean is not merely less sensitive to that tail, it is **exactly blind** to it: pushing the single worst document 25 pts further down leaves it unchanged to the last bit on **6/6** merge contrasts, while the same push moves the plain mean by **225% of the effect** on M=1344. Consequence for **T1**: an accuracy-*preservation* claim is a claim about every document, and *both* candidate location statistics answer the average question — the mean lets a −72 pt page hide inside ±4 pt resolution, the trimmed mean deletes it. So section 3's ~30% power gain is **not free either**; it is bought with exactly the documents the claim is about. T1 must pin a **tail statistic alongside** the location statistic rather than choose between mean and trimmed mean and stop. This cuts *harder* on merging than the current rule does. See the D13 section and `results/merge_power_local.log`. |
| D14 | `scripts/diagnose_analysis_dof.py` | **T1 was scoped as an estimator choice; the estimator is the smallest of seven unpinned degrees of freedom (2026-09-23, local, <10 s, 20/20 controls).** D13 said *which estimator*. D14 asked what a rule naming that estimator would still leave unwritten, and the answer is most of the analysis. **The sharpest finding arrived by accident: "run 14, m=0.40" names two contrasts 5.08 pts apart.** I measured the g- and DiD-sensitivities with an ad-hoc probe, wrote this script to make them reproducible, and **the script disagreed with the probe** — they had silently picked different control rows for the same named contrast. Against `keep=0.50 router` (same keep fraction, run 14's *published primary*) the trimmed estimate is **−0.17**, the "merging is free" null; against `keep=0.30 router TWIN` (token-matched, equal M) it is **+4.91**. Both are legitimate estimands, the pre-registration names neither, and this file's own prose has used the phrase both ways. So the hazard is not hypothetical — it produced a contradiction between two of my own measurements inside one session. **And the latitude was already spent: runs 13 and 14 both declared `MERGING WINS` on *disjoint* rows.** Section 9 reconstructs the pre-registered Q6 criterion from the raw arrays and scores all six pairs in both runs: run 13 certifies `M=3840 router` **+3.12** and `M=1344 ink` **+4.06**; run 14 certifies `M=1344 router` **+4.22** and `M=1440 router` **+5.78**; **intersection ∅**. Every run-13 winner regressed toward zero in run 14 (+3.12→+0.81, +4.06→+1.43) and both run-14 winners had been negative in run 13 (−0.22→+4.22; **−1.29→+5.78, a +7.07 swing**). The **arity** is the mechanism: `MERGING WINS` needs **1 of 6** pairs, `INDISTINGUISHABLE` needs **6 of 6** flat *and* 6 of 6 under `res ≤ 3.0` — and **4/6** pairs exceeded 3.0 in run 13, **5/6** in run 14, so the verdict the table itself calls *"the good outcome for the architecture"* was arithmetically **unreachable in both runs** while the positive one fired on one pair each. A ratchet, not a tie-breaker; the design annotated that row **"AT RISK"** and shipped it anyway, twice. The rule's prose sets a better standard (*"the evidence is the pattern"*) and **that fails too, roles swapped between runs**. So **no rule that takes the best of N pairs is admissible** — best-of-N is now measured as uncorrelated across runs. **And no declared winner survives the family it was drawn from.** Section 10 runs Holm at α=0.05 over **6 pairs × 2 quantities = 12** — 12 and not 18 because only `recall` and `ned` are stored per image, `charAcc = (1−mean(ned))×100` is an affine transform of `ned` (not an independent witness), and `word_order` is on disk for neither run; 12 is also the *weaker* correction. Run 13: **3/12** nominal, smallest p **0.0240**. Run 14: **2/12**, smallest p **0.0208**. First Holm threshold **0.00417**. **Zero survivors in either run**, both missing by ~5×, so the result is insensitive to the correction chosen (recall-only family of 6 → 0.00833, still ~2.5× below both). **Neither published `MERGING WINS` verdict survives any correction at all.** Filed but deliberately not promoted: run 13's smallest p is `M=1920 router` on **`ned`** (+3.66, p=0.0240), the pair the recall-only rule scored *flat* (+2.86) — so the pre-registered quantity was the less sensitive one **on the row D13 headlined**; a reason to distrust that null, **not** a licence to re-headline on ned. **Section 10's last control audits D14's own prescription and it fails:** §1c says *"set the `res` gate from the observed `sd`"*, but on the stored [0,1] fields a bare `res ≤ 2.0` **cannot fail** — native res **0.0264–0.0381**, arithmetic ceiling for a paired delta at n=50 **0.280** (7.1× inside the gate), and `count(d < −10)` can never fire since native deltas lie in [−1,1]. Any run scored on the arrays as-stored returns *"powered, no harmed documents"* **by arithmetic**, defensible as *"I used the stored field."* So thresholds must carry units, not just direction — §2's hole one level up. **Six more unpinned choices, each swinging ≥ the ~1.0 pt target effect:** which split is "the merge arm" (**+1.12 pts** — checkerboard trim +1.35 vs rank_parity +2.47 at M=1920, *both already on disk*); direction per quantity; the trim fraction g; the DiD ordering; the tie convention (run 13 m=0.20 has **exactly one** document at delta = −10.000000 under *both* pairings, so `count(d < −10)` gives 4 and `<=` gives 5); corpus composition. Run 13 alone offers **7** selection-matched and **12** budget-matched (merge, non-merge) pairs. **The three with teeth.** (a) *Direction is not in the harness:* `arr()` scales every key ×100 and encodes no direction, survivable only because all five `PUBLISHED` calibration tuples are recall. `ned` is an error rate, and on the negated sabotage arm its worst per-document delta is **+7.64** where recall's is **−96.61** — the only non-negative minimum in the sweep — so a tail statistic phrased "worst per-document delta" ranks the **deliberately-broken** arm safest. (b) *Adopting the trimmed mean **creates** a degree of freedom:* the mean is linear so a DiD is order-invariant (**+3.5822** both ways, gap identically zero); the trimmed mean is not — trim(per-doc DiD) **+3.8696** vs trim(d14)−trim(d13) **+3.0615**, gap **+0.8081 pts** (26% of the effect, 16× the seed-noise floor, **42%** of the resolution the trim buys). Naming "10% trimmed mean" does not determine the estimate. (c) *T1 × T4 can delete FUNSD:* at pooled n=500 a g=0.10 trim discards **k=50 per tail**, FUNSD's whole contribution is **50 documents**, and every harmed document fits inside the discard set under both pairings — two individually-correct fixes, jointly capable of removing the only corpus measured. Now recorded in **both** T1 and T4. **Also: there is no token-matched `random` arm in either run** (merge budgets `[1344,1440,1920,3840]`, random budgets `[1680,2400,3600]`, overlap **empty**), so "merging beats random at matched M" is not weak — it is **not computable** from runs 13/14. **And it corrected T1's own rationale line** *"the −64 pt control still resolves"*: its half-width is **6.09 at n=50** (≈1.92 at n=500), so it satisfies no absolute-width gate; it excludes zero by ~10σ and always will. D13's summary carried the same clause and is annotated in place. **Two of my own errors, both caught by this script's controls and both recorded:** (i) the first draft claimed the DiD gap was *larger* than the trim's resolution gain — it is 42% of it, the control asserting "larger" **failed**, and the overstatement flattered the argument; (ii) the first draft filed merge-minus-random as *unverified* because my probe used row names that do not exist — enumerating the budgets showed they do not exist *because no such pairing does*, so "I could not reproduce it" was concealing a finding. **Does not** license picking the flattering side of any of the seven: the swings measure analyst freedom, not effects, and §1b does not license preferring the +4.91 reading. See the D14 section and `results/analysis_dof_local.log`. |
| — | note on `verify_attn_target --real` | **A count is not a strength.** Of its 41 passes, *"target is not ink in disguise"* clears its own content-free floor by only **0.678 vs 0.654 = +0.024**, on **one** page. Read as "this statistic barely distinguishes the attention target from ink", not as evidence that it does. The load-bearing page-specificity evidence is elsewhere and much stronger: D8's top-5% centroid spread (**6.12** grid rows vs ink's **1.81**), D9's page-specific lift (**+0.212** attn vs +0.151 ink over a featureless map), and D10's **S − X = +0.337**. **D11 retires all of it as moot: the target is distinguishable from ink, reachable, and stationary — and selecting on it is worse.** |
| — | `scripts/verify_saliency_loss_cell.py` | Not a diagnostic but the check that closes D4/D5: **execs** cell 11's saliency block and asserts satisfiability, gradient proportionality (`\|d_sal/dz\|/\|p−t\| == 1.0`), explicit `lambda_*`, the (0,1) range contract, and generator/notebook parity. **11/11** (was 6/6; 2026-09-02 added case **G** — the ATTN and INK branches must produce **bit-identical `_sal`** on the same target, i.e. 13(b) changed the target and not the loss — and case **H**, which runs the degeneracy guard against an all-zero *and* an all-one *and* a valid target, and asserts the ink path still only warns). 3/6 before F1. |
| — | `scripts/verify_harness_control.py` | The check that closes Pending 4 (F2): **execs** cell 15's weight-swap block against a stub model under seven scenarios, including the two that must raise. Proves the retrained weights are provably restored before the sweep — the silent failure there would put all 15 rows on the wrong checkpoint with no symptom. **36/36 on `kaggle_token_pruning_ocr.ipynb`, 39/39 on `kaggle_pruning_run.ipynb`** (`argv[1]` picks the file); 0/1 before F2. **This row said "36/36 on both notebooks" until 2026-09-09, and the counts are not equal for a reason worth knowing:** the canonical notebook has no `DO_TRAIN` branch, so it gets one check saying so, while the generated one gets **four extra** — cell 6 must not starve a `DO_TRAIN` run of training data, cell 7 must resume *from* `RESUME_CKPT`, and cell 7 must save `PRUNED_CKPT` and repoint `EVAL_CKPT` at it before the block restores anything. Those four are exactly the preconditions a retrain-then-sweep run depends on, so **the notebook that matters for runs 9/10/11 is the one with the higher count**, and "both pass" was hiding which. |
| — | `scripts/verify_results_provenance.py` | The check that closes Pending 6 (2026-09-09): **execs** cell 15's `PROVENANCE` block against stubs, then **execs both real `json.dump` statements** and reads the stamp back off disk — "the key is in the source" is not "the key is in the file". The load-bearing case is section 2B: it stamps a file, **mutates that file**, re-stamps, and requires the two stamps to differ. A `_ckpt_stamp` that echoed its argument instead of calling `os.stat` would pass every other check in the file and still let a results table be attributed to the wrong checkpoint, which is the failure the stamp exists to prevent. Also covers six degraded inputs that must each *record a reason* rather than raise (missing file, unset variable, paramless model, cuda device, a `get_device_name` that throws, an unimportable `transformers`, a `torch` without `__version__`). **35/35** on both notebooks (`argv[1]` picks the file); 0/1 before the patch, and a deliberately decorative stamp scores 4 FAILs. **This row said "35/35 on both notebooks" from 2026-09-09 to 2026-09-22 while the script actually RAISED on `kaggle_pruning_run.ipynb` after its first check** — it sliced the provenance block with a hard-coded `for _name, _kr, _mode in SELECTION_CONFIGS:` end anchor, and generator patch G4 had renamed that loop to `ALL_CONFIGS` with two extra loop vars when the merge rows landed. So the check that closed Pending 6, and that is the only reason anyone knows run 12 evaluated the wrong checkpoint, **was not covering the notebook runs 12/13/14 were produced by** — the notebook where a wrong-checkpoint attach actually happened. Repaired 2026-09-22: the end anchor now matches either loop form and asserts if neither is present, and `write_ns()` supplies the five extra names the generated notebook's `json.dump` needs (`Q6_RESOLUTION_PTS`, `q6_rows`, `sabotage_row`, `time`, `_t0`). Now genuinely 35/35 on both. **The generalisable part is not the anchor — it is that a verifier which crashes is indistinguishable from one nobody ran, and this file recorded it as passing for 13 days.** |
| — | `scripts/verify_training_telemetry.py` | The check that closes Pending 11 (F3): **extracts and executes** cell 11's whole epoch loop against a real `AdaptivePruningLoss`/`GradScaler`/AdamW. Asserts the epoch line reports the saliency BCE, that `Obj == CE + aux + λ·sal` with `aux ≠ 0`, that **λ=0.5 and λ=0 print different lines**, that the value tracks a changed ink target, that the term still reaches `backward()`, and generator/notebook parity. **8/8** (was 6/6; 2026-09-02 added case M for 13(b)'s new `ov`/`ch`/`lift` columns — inverting the target must drive `ov` 1.000 → 0.000, and `lift` must equal `ov − ch`), and 1/6 before F3. |
| — | `scripts/verify_attn_target.py` | The check that closes Pending 13(b)'s build: **execs cells 4 + 7** and drives `attn_topk_target` against a **real** donut decoder — exact K, binary output, raises on pruned input, raises on all three empty-`cross_attentions` shapes (`()`, `None`, `(None, None)`), pad masking is not inert, and `forward()` really returns pre-prune `visual_tokens`. Its load-bearing control is a real decoder at its **default** config: must raise, then must succeed once cell 11's own eager lines are `exec`'d against it. **34/34 fast**; `--real` adds 7 more on run 5 weights + a real 4800-token FUNSD page (**41/41**) and prints the interior-prior floor so the ink-overlap number cannot be read against the wrong null. Slow, so `--real` is opt-in and not part of the suite. **One of those 41 passes is nearly non-discriminating — see the note below; do not read the count as 41 equally strong claims.** |
| — | `scripts/verify_attn_train_step.py` | **The run-10 pre-flight (2026-09-02): the only check that executes the 13(b) *composition* rather than its pieces.** Slices cell 11's DO_TRAIN **prologue (40 lines) and training body (181 lines) verbatim** out of the generator and runs them on 2 real FUNSD pages under `ATTN_TARGET=True` + run-5 weights, so the optimizer, criterion, `LAMBDA_SAL`, scaler and loop are the shipped lines, not a paraphrase. Everything else on this list tested a piece: `verify_attn_target` the target function alone, `verify_saliency_loss_cell` the loss with a *lambda* teacher, `verify_training_telemetry` the loop on the **ink** branch with a stub model, D10 the target outside any loop. **Nothing had run model fwd → `visual_tokens` → real frozen teacher → top-K target → BCE → scaled backward → optimizer step.** **8/8 fast** (anchor resolution, cell-2 import contract, and the **6-way** config gate — was 6/6 and a 4-way gate until 2026-09-16, when run 12 flipped `DO_TRAIN`'s shipped default to False and the table gained both directions of the new `assert DO_TRAIN or RESUME_CKPT` guard. The scenarios now set `DO_TRAIN` **explicitly**; they used to inherit the shipped literal, which worked only while it was True and is the same D5 shape this file argues against elsewhere); `--full` adds 10 by execution (**10/10**, ~25 min CPU): teacher's 110 params bit-identical after training, 6/6 router tensors moved (update applied, not scaler-skipped), `ch == K/N`, Swin drift `[0,0,0,33]` so `UNFREEZE_STAGES=1` is *executed* not read off a flag, and the target still exact-K when recomputed from the **drifted** encoder. Found three defects — see the `gc` and `tee` Gotchas and the cell-2 gate. |
| — | `scripts/diagnose_target_drift.py` | **D10.** Target stability under the encoder drift a real run produces. See the D10 section. |
| — | `scripts/eval_budget_binding.py` | **D11 (2026-09-04).** Re-asks 13(b) at keep=0.25/0.20 — budgets that *bind* — on the two existing checkpoints, eval only, no GPU. Not a re-run of the Phase-2d sweep: it is **paired** (both checkpoints see the same images, `random` is reseeded per config so both draw identical masks), so it reports the per-image delta's **standard error** instead of leaning on AGENTS.md's eyeballed ±1 pt floor. Writes `results/budget_binding_local.json` — deliberately *not* `ablation_selection_local.json`, which holds the historical Pending-1b n=4 rows. Reads its metric defs out of `kaggle_pruning_run.ipynb` (the notebook that produced runs 9/10), not the older `kaggle_token_pruning_ocr.ipynb` that `eval_select_modes.py` reads; all four defs verified byte-identical between the two on 2026-09-03, so that is a provenance fix, not a behaviour change. **Its own two controls were rewritten after the smoke run exposed them as unsound — see the note below, which is the reusable part.** |
| — | `scripts/eval_why_pruning_helps.py` | **D12 (2026-09-05, local CPU, 110 min) — H2 is REJECTED; "pruning helps" is train/test matching.** Asks why discarding tokens raises recall: **H1 train/test matching** (runs 9/10 trained at `TRAIN_KEEP_RATIO=0.50`, so keep=1.00 is off-distribution, the 77.62 ceiling is depressed, and the gain is a *recovery*) vs **H2 inference-time denoising** (blank paper dilutes cross-attention, so pruning should help a model never trained with it). **Run 5 discriminates** — trained *and* evaluated unpruned. H2 predicted run 5 would IMPROVE under pruning; it **falls monotonically** (−1.57 / −6.03 / −11.47 / −20.34 at keep=0.50/0.35/0.25/0.20, significant at the last three) while run 9 peaks at exactly the budget it was trained for. Uses `select_mode="ink"` so both checkpoints keep the **identical** token set (verified `0.00e+00` at all four budgets), which also gives H2 its most favourable selection — the ink oracle retains 0.994 of the page's ink at keep=0.50 — and it still failed. **H1 is supported but NOT isolated:** run 9 differs from run 5 by pruning-aware training *and* five more epochs. Writes `results/why_pruning_helps_local.json`; `--rescore` re-derives controls+verdict from it in 0.0 min, `--selftest` executes all four verdict branches. See the D12 section. **Extended 2026-09-15 for run 11:** `--pair {run5_run9,run11_run9,run5_run11}` over three named checkpoints, each with its own focus/reference/output path; the paired `ISO = Δ_focus − Δ_ref` difference-in-differences with `SE`/`t`/`resolution_pts`, a `1e-9` identity assertion and `decide_iso()` implementing the pre-registered table (`UNDERPOWERED` is the default branch, and `--selftest` now covers those branches too); `LOCAL_ANCHORS` keyed by checkpoint label, replacing a slot-B assumption that would have failed the `[run 5, run 11]` sheet. See "The analysis harness that produced it" under "Run 11 — result". |
| — | `scripts/eval_kv_memory.py` | **M1 (2026-09-06, local CPU, 72 s) — closes Pending 8(c): the project's one true efficiency claim.** Measures decoder cross-attention KV bytes at five budgets. **keep=0.35 → 150.00→52.50 MiB (−65.0%) for −0.26 pts (t −0.18, n=50 paired)**; the accuracy figures are read out of D12's JSON at runtime, and a control **fails** if that lookup does not resolve, so the memory number cannot silently detach from its price. Headline is deliberately not keep=0.20's −80.0% (costs 13.01 pts, t −5.42). Two independent measurements — analytic `2×4×16×64×tok×4 B` vs walking the real `past_key_values` — agree to **rel gap 0.0000** at all five budgets; the measured tensor is captured by a **forward hook on the decoder**, not re-derived, with a control asserting its `seq_len` == `generate()`'s own `meta["compressed_tokens"]`. Self-KV is asserted exactly `f(generated length)` and **non-monotone in keep** (0.25 → 10.19 MiB > 0.35 → 9.56 while cross-KV goes the other way), so a self/cross mix-up cannot pass as a pruning win. **25/25 controls PASS** (this row read "17/17" until 2026-09-09; the script has no control counter — `ok_all` is a boolean AND — so the count was eyeballed, and `results/kv_memory_local.log` carries 25 `[PASS]` lines and 0 `[FAIL]`. Corrected against the log, which is the artifact). ~~the script has no control counter~~ — **2026-09-18: it does now.** `say()` increments `n_controls`/`n_failed`, the totals go into the JSON, and the run prints its own `N/N` — added because I repeated the identical mistake (typed "38", measured 52) the first time I extended this script. Its pre-written docstring hedge ("a large cut in a small quantity") **was falsified by its own output** — unpruned cross-KV is 19.46% of the model's 771 MiB — so the script now derives that framing from the measured share. **Extended 2026-09-18 to the merge stage: 9 rows (5 prune + 4 merge), `52/52 controls`, `results/kv_memory_merge.log`.** The merge rows' accuracy cost is re-bootstrapped from `run 13/ablation_selection.json` at runtime with **selection held fixed** (NOT run 13's Q6, whose pairs vary selection *and* merging), and control (10) asserts in **both** directions that "free" has teeth: the m=0.20 CI must include 0 **and** the m=0.40 CI must exclude it and be negative. Control (8) asserts each merge row falls strictly below its prune-only twin in tokens *and* bytes — a silently-ignored `merge_ratio` would otherwise reproduce the twin's numbers exactly, which is this project's most-repeated defect. Row lookup is `row_at(keep, merge)`, which raises unless exactly one row matches, because with two `keep=1.00` rows the old positional `next(...)` would silently pick whichever came first. See the M1 section. |
| — | `scripts/diagnose_tome_parity.py` | (Kilo) Quantifies the ToMe score-order/parity gotcha: ~49% missed-redundancy rate. |
| — | `scripts/verify_tome_merge_port.py` | **The gate that had to be green before run 12 (2026-09-16): 85 checks, exit 0 — now 89 (2026-09-22, G3b).** Targets the **generated** notebook, because the checkerboard fix reaches only that one. **Execs** cell 4 and compares the merger's output to `src/tome.py` **bit-for-bit** at B ∈ {1,2} × four `(keep, merge)` configs, drives `generate()` through all 13 new rows asserting `meta['compressed_tokens']` **and `model.last_enc_len`** against the predicted `M`, and runs the whole 28-row cell-15 harness end to end. **Every equality check is paired with a non-vacuity check**, because code spliced from `src/` and compared against `src/` passes no matter what: checkerboard vs rank_parity must *disagree* (max \|diff\| ≈ 5.6), merging must compact rather than pass through, the missed-redundancy statistic is re-measured **on the shipped code against its own null** (49.7%/46.5% → 0.0%/0.0%), and `assert_token_matched` is fed a deliberately mismatched pair (M=1920 vs 1680) and required to raise. The sabotage arm's reference implementation is **extracted from the canonical notebook at runtime** rather than hand-copied — a local copy could drift into agreeing with the new merger and go green for the wrong reason. Two float mismatches at B=2 were fixed by matching the *computation shape* (drive the old merger per image too) rather than by widening a tolerance over the effect under test; see the per-image-loop gotcha. **2026-09-22 (+4, → 89): the per-image metric record.** Every row must store `word_order` per image; `word_order_pct` must equal `mean(per-image word_order)·100`; `character_accuracy_pct` must equal `(1 − mean(per-image ned))·100`; and the order identity must be **discriminating** — substituting `recall` has to break it, measured at **35.69 pts** of margin, because the plausible defect is a one-letter typo (`float(r)` for `float(o)`) in the same scope. Both identities were **mutation-tested**: storing recall FAILs check 2, and computing charAcc from the median NED FAILs check 4. |
| — | `scripts/diagnose_decoder.py` | LEGACY (copy-vs-next-token, settled before run 6). Re-run 2026-08-31 on run 8: **no copy failure** (COPY 0.0% / NEXT 74.5%) and a first look at raw generated text. See below. |
| — | `scripts/verify_corpus_grain.py` | **T2's artifact (2026-09-24, local, 21/21 controls, exit 0, `results/corpus_grain_local.log`).** Confirms the second eval corpus **by loading it** and measures whether T1's point-denominated thresholds port to it. **The answer changed the reason for the decision, not just the decision.** CORD is excluded on **denotation**, not size: all **1309/1309** of its `valid_line` entries carry a key-value `category`, so its GT is the *annotated subset* while FUNSD and SROIE transcribe the *page* — `recall` on CORD is a different quantity wearing the same name, and pooling averages two metrics. The grain follows: CORD **20 words/doc, one word = 5.00 pt = 8.82× FUNSD's grain**, against T1's **1.0 pt MDE**, so the metric cannot *express* the effect under test, and **4/100** docs trip the −10 pt harm threshold on a single wrong word. SROIE sits beside FUNSD (0.92 vs 0.57 pt, **1.62×**, 0/347). Recording "FUNSD+CORD = 150 < 307" as the reason would have left the real hazard live for whoever next finds 200 receipts. **"Confirmed by loading" caught three near-misses that a shallower check passes:** `buthaya/sroie` has exactly **347 test annotation files and zero images repo-wide** (a count matching the expected number is not a split); `buthaya` and `jsdnrs` both store **line segments in a field named `words`** (57% multi-word, denominator off ~2.1×) while being **347/347 `words`↔`boxes` aligned**, because the boxes are per-*segment* — **alignment is necessary, not sufficient; it is exactly what hides the mismatch**; and `jsdnrs`/`vishu12121` report **byte-identical** split sizes, so two "independent" mirrors agreeing is one upload counted twice. The chosen mirror loads to **0 of 40,411 units containing whitespace**, 347/347 per-word boxes, images decoding. **Section 4 audits the analysis's own first draft and two controls assert it was wrong:** the draft called exact −10.000000 ties a CORD-specific hazard at "13/100 vs 9/50" — measured **17/100 vs 7/50** (SROIE 27/347), and the framing was worse than the counts, since a tie needs only `n ≡ 0 (mod 10)` and so happens everywhere (17% vs 14%). Its test asked whether `1000/n` is an integer — whether *n divides 1000*, a different and rarer condition that is still satisfiable, so it returned **a plausible wrong number rather than an error**. The real asymmetry is one the count never showed: **2** wrong words reach the threshold on a median CORD receipt, **18** on a median FUNSD form. Also records the licence at the strength the evidence supports — SROIE's `mit` is **uploader-asserted, not from the ICDAR organisers**, three re-uploads disagree, **77 of 100** SROIE-matching HF datasets carry no licence at all, and only CORD's `cc-by-4.0` is first-hand — flagged as a **publication question for the user**, not a measurement one. See `## Corpus decision (T2)`. |
| — | `scripts/score_preregistered.py` | **T3's artifact (2026-09-24, local, 45/45 controls, exit 0, `results/score_preregistered_local.log`).** The **executable** form of T1 §§2–7, which existed only as prose until this file. Scores runs 13/14 on the pre-registered primary (`keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN`, token-matching at M=1920 asserted **from disk**), on claim 3's own same-keep rows **in a separate section that never pools with it** (D14 §1b's 5.08 pt hazard), and on a consistent keep=1.00 baseline. **Calibrated against the nine figures T1 recorded before this file existed** — all reproduce, and the load-bearing one is that the matched-null p95 **tightens** 1.74 → 1.52 → 1.51 as n goes 50 → 307 → 397, which a constant typed in and called a null could not do (D14 §10's failure mode). **Eight discriminating controls show each pinned choice is load-bearing:** the naive SE is **35% smaller** than Tukey–McLaughlin (0.6383 vs 0.9792); difference-then-trim moves the estimate **0.2555 pts** while **the same comparison on the plain mean is identically zero (−8.55e-15)**, so the non-additivity is a property of *trimming*, not of the data; sign-flipping `ned` changes the tail it reports (−23.50 → −29.66); in **points** the harm rule counts **5** where on the stored `[0,1]` field it counts **0**; and the harmed-count p95 is **7** on run 13 but **4** on run 14 *under the same rule*, because the bar is matched per row — **so counts are not comparable across rows and must be quoted with their null**. The gate also **fires on run 14 (3.22) and not on run 13 (1.11)**, so it is not a gate that fires on everything or nothing. **Result: `UNDERPOWERED` in both runs, zero Holm survivors, and run 14 is not scored `FREE` despite a +0.02 pt trimmed mean because both its recall tail gates fail** — the one behaviour T1 §3 exists to produce. **§5 is the section to read:** it runs D13 §5's untreated control, which had never run, and finds T1 §3's tail gate **is not specific to merging** — **13 of 21** contrasts with no merging clear 1.74, and the sweep's worst per-document loss (**−80.85 pts**) and highest ratio (**5.43**) both belong to `keep=0.75 ink ORACLE`, where nothing is merged. The failure is **specificity, not sensitivity** (`keep=1.00 router CONTROL` passes at 1.47); there is **no zero-treatment null on disk** (no config repeats within a run, decode is bit-identical on re-run, and runs 13/14 differ by a retrained checkpoint); and the gate is **not reversal-invariant** — swapping arms flips **10 of 28** verdicts. `--selftest` runs the same controls and is what CI should call. See `## Runs 13/14 re-scored under the run-17 rule (T3)`. |
| — | `scripts/check_writeup_numbers.py` | **The audit of `WRITEUP.md` (2026-09-09).** The writeup is the one document in this project with no execution behind it, and this file already records an incident where "the write-up had kept the [stale numbers]" — so every figure in it is **re-derived from `results/*.json`**, not compared against prose. **134/134.** It deliberately does **not** read AGENTS.md for the numeric sections: prose checked against prose proves nothing. Seven sections — budget table, selection table, DiD (which asserts each DiD **is** the run5−run9 arithmetic rather than a separately typed third number), inline claims, audit-corrected figures pinned so a fixed error cannot return, transcription-only checks that are *labelled* as not re-derivation, and banned claims. Two design points are the reusable part: (i) the banned-phrase regexes match only **affirmative** constructions, because the first version fired on the writeup's own disclaimer, and they are paired with **positive** checks that each disclaimer is present — otherwise the ban passes trivially on a file with no disclaimers at all; (ii) section 6 asks `in_doc and in_src`, not `not in_doc or in_src`, because the latter is vacuous the moment a corrupted figure no longer matches the searched string. Both were found by a **15-case sabotage harness**, which caught two decorative checks that the green run did not. Found six real errors, including a **double sign inversion** in the router-vs-ink comparison and a control count of "17/17" that was also wrong in *this file*. |
| — | `scripts/probe_generation_determinism.py` | **New 2026-09-14.** Tests, by execution, the assumption at `run_nrns_rp_sweep.py:263` that greedy generation makes a re-run bit-identical — the sentence every CI in `results/nrns_rp_sweep.json` rests on, because it is the sole justification for bootstrapping over documents only. Mirrors the sweep's exact conditions (same checkpoint, `keep_ratio=1.0`, same prompt/max_length/decoding) and **deliberately does not seed**: the sweep did not seed either, and seeding here would mask the effect under test — a green check that cannot fail. Writes token IDs per tag so a second invocation tests **across-process** determinism, which is the condition the two sweep files actually differed under; within-process equality alone would not clear the claim, since a startup-dependent difference (thread count, BLAS kernel, allocator layout) reproduces inside one process and still moves the aggregate. **6/6 within-process, 6/6 across two processes.** Verdict text states what each outcome would license, so a pass cannot be read as more than it is. |

**`diagnose_decoder.py` re-run on run 8's weights (2026-08-31).** It had rotted to a
non-existent checkpoint path and now resolves newest-run-first; the run is clean end to
end (HF donut-base and FUNSD are cached locally, no GPU). Three things worth keeping:

- **The copy bug is gone on the current weights, confirmed at the logit level.**
  Teacher-forced on a real FUNSD page: `argmax[t] == input[t]` (copy) **0/110 = 0.0%**,
  `argmax[t] == input[t+1]` (real next-token) **82/110 = 74.5%**, CE 3.02. The first ten
  positions — the `<s_doc>{"text": "` prefix — are predicted exactly; the misses start at
  the first content word. This is independent corroboration of run 8 from a different
  direction than the aggregate metrics: every other piece of evidence in this file is a
  recall/NED number, and a metric can be gamed in ways a per-position argmax cannot.
- **The generated text is genuinely legible**, which nothing else in this file
  demonstrates: `'<s_doc>{"text": "ATT. GEN. ADMIN. OFFICE Fax: 614-466- 5087 Dec 10 .98
  17 :46 P. 01 ATT.'` against a gold prefix of `'{"text": "TO: DATE: 3 Fax: NOTE:
  82092117 614 -466 -5087 Dec 10 \'98 17 :46 P. 01 ATT. GEN. ADMIN. OFFICE Attorney'` —
  right content, different reading order, which is exactly the 53.05 word-order / 77.74
  recall split the metrics report.
- **Two config facts it surfaced, both already handled, recorded so they don't get
  re-diagnosed:** `config.decoder_start_token_id`, `pad_token_id` and `eos_token_id` are
  all `None` on donut-base. `generate()` already compensates
  (`gen_kwargs.setdefault("eos_token_id", 2)`, `pad_token_id` 1) — which is why
  generation stops at `</s>` instead of running to `max_length`. The unset
  `decoder_start_token_id` is what makes the unprompted path fall back to `<s>`; see the
  prompt-dependence Gotcha.

**`eval_budget_binding.py` — the smoke run falsified two of its own controls, and the
lesson generalises to every check in this file (2026-09-04).** The script was written,
parsed, and smoke-run at `--n 2`; it exited 0 and printed a confident verdict. Both of
those facts were misleading, in two different ways:

1. **The gate could not fail for the right reason.** The original control compared the
   local run9→run10 recall delta to Kaggle's (`−0.22` at keep=0.50, `+0.49` at 0.35) and
   passed if the gap was under 2.0 pts. It **passed at n=2** — on two images, where the
   local estimate is nearly noise. That is the tell: Kaggle's own delta has an unknown
   SE from a single n=50 run, so "the two agree within 2 pts" mostly decodes to "both
   are consistent with zero," which is true of almost any pair of small numbers. A
   control that a noise draw satisfies is decoration. **Replaced by `retained_ink` at
   the same budgets**, which is the right kind of quantity for a control: near
   deterministic given the weights, so sampling moves it by <0.08 while a swapped,
   stale, or half-loaded checkpoint moves it by 0.25+. It now passes on 6 comparisons
   with a largest gap of 0.071, and it *can* fail. The recall-delta comparison is still
   printed, but labelled informational and no longer gates anything.
2. **The verdict path would have manufactured a null.** The `else` branch read "the
   attention target is INDISTINGUISHABLE from ink … 13(b) is a null where it counts" —
   and at n=2 it printed exactly that for both new budgets, where the paired SE was
   **8.88 and 14.34 pts**, i.e. nothing under ~18 and ~29 pts was detectable. The code
   could not tell *"we looked and saw nothing"* from *"we could not have seen it,"* and
   defaulted to reporting the first. Since the whole point of the run is to decide
   whether 13(b) is dead, that is the single most expensive mistake the script could
   make. Fixed by pre-registering `MIN_EFFECT_PTS = 3.0` and printing `T_SIGNIF × SE` —
   the smallest delta the test could call significant — for every budget; where that
   exceeds 3.0 pts the verdict is **UNDERPOWERED**, explicitly *not* a null, and the
   script reports how many images a 3-pt resolution would need.

A third control was **added** because the smoke run showed it was free: `random`-mode
retained ink must be *identical* across the two checkpoints, since the masks come from a
per-config reseeded generator and ink does not depend on the weights. It came back
`0.00e+00` at all four budgets, which upgrades "paired" from a design intention to a
measured fact — without it, a silently ineffective reseed would have made every paired
delta compare different draws with no visible symptom.

**The reusable part:** `EXIT=0` plus a green control plus a printed verdict is the state
this script was in *before* both defects were found. Two questions catch this class, and
neither is about whether the code runs — ask them of any check here. *Could this control
have failed on the data I actually have?* (if a 2-image noise draw passes it, no) and
*does a flat result mean absence, or does it mean I lacked the power to see presence?*
See the `green-checks-need-the-same-suspicion` and `check-the-constraint-binds` memories.

**`eval_why_pruning_helps.py` — three defects the smoke runs found, and a control
pre-registered mid-flight because the first n=50 row falsified it (2026-09-05).** All three
smoke defects are one error wearing different clothes: *a tolerance never compared to the
noise of the quantity it bounds.* D11 saw that error produce a decorative PASS; here it
produced two spurious FAILs and a spurious star.

1. **A gate that could not pass.** The harness anchor compares local run 5 @ keep=1.00 to
   run 6's `77.74`, which is a mean over **50** images, under a 1.5-pt tolerance. At `--n 2`
   local read `82.61` (those two pages are easy) for a gap of 4.87 — an automatic FAIL that
   says nothing about the harness. This is the mirror image of D11's defect: a tolerance
   *narrower* than the sampling noise is as useless as one wider, it just fails instead of
   passing. And a spurious FAIL is not harmless, because it **gates the verdict** — all four
   H1/H2 branches were dead code that had never executed. Fixed by **SKIP** (explicitly not
   a pass, recorded in `controls_skipped`) whenever `n < len(ds)`.
2. **A power check certifying resolution off two images.** It printed `run 9 keep=0.25 SE
   0.51 detectable >= 1.02 pts OK`. An SE estimated from two paired differences is itself
   mostly noise; two pages happening to move together manufacture a tiny SE and a fake OK.
   I had guarded against *reporting a null while underpowered* but not against the power
   estimate itself being noise. Fixed with `MIN_N_FOR_POWER = 10`.
3. **Two other readers of that same SE, left unguarded.** After fixing the power table I
   still printed significance stars from the same statistic in the curves table and the
   retrain table — the n=2 smoke starred `t = +25.55` off `SE 0.21`. **Enumerate every
   reader of a quantity before changing how it may be used**; one guard on one of three
   sites is not a fix. Replaced by a single `STAR_OK` flag read by one `star()` helper.

The verdict branches are now exercised by `--selftest`, which calls `decide()` itself — not
a copy of its logic — against six injected cases, and asserts all four branches execute and
separate. Two cases carry it: the same `−0.30` delta at `SE 5.00` and at `SE 0.40` must
return **UNDERPOWERED** and **NEITHER** respectively, or the power logic is decorative.
D11 shipped a verdict branch that had never run and it printed a confident null at SE 8.88.

**The mid-flight pre-registration (written after the first n=50 row, before the other nine).**
Local run 5 @ keep=1.00 came back **74.72** against the expected 77.74 — gap **3.02**, so the
anchor will FAIL and the verdict will print WITHHELD. I believe the *control* is wrong, and
the reason predates the failure: D11 established that **generation does not reproduce across
environments while selection does** (up to 3.4 pts on bit-identical token sets), and this
script's own JSON says `not_comparable_to_kaggle_in_level` — then gates the verdict on
exactly that level comparison. The 1.5-pt tolerance was derived from a +0.32 drift measured
on **run 9's** weights and applied to **run 5's**, which was never justified. Replacement,
committed here before the number exists: this run also measures **run 9 @ keep=1.00**, which
D11 measured at **77.62** on the same device, transformers, 50 images and greedy decode — a
like-for-like reproduction that must land within **0.5 pts**. Pass ⇒ the harness is sound and
the Kaggle gap is environment drift; fail ⇒ the harness changed and nothing here is
interpretable. The Kaggle comparison is demoted to informational. Stated plainly: I only
noticed the contradiction **because** the control failed, which is why the replacement is
pinned to a number not yet observed rather than to a widened tolerance on the one that was.

### Run 7 — pruning-ON retrain + Phase 2d sweep (Kaggle T4, 2026-08-30)

First run to actually train the router **with pruning ON** (`keep_ratio=0.5`, STE
active, sparsity loss targeting the real budget) from run-5 weights, then run the
full 15-row selection sweep on the retrained checkpoint
(`run 7/adaptive_donut_pruned.pt`, `run 7/ablation_selection.json`).

Headline: the STE-based pruning-ON retrain **did not fix the sign inversion**. The
forward `router` mode at keep=0.5 scores **18.80** recall (retained ink 0.295 — it
still ranks blank paper above text), i.e. worse than the random floor (62.31). So
setting K<N is insufficient: the gradient still asks "does scaling this token help"
rather than "is this token informative", and the scorer learns the wrong sign —
exactly D1's predicted trap.

**The learned ranking, flipped, is a working pruner.** `negated` / `strat_negated`
at keep=0.5 give **73.09 / 67.37** recall; at keep=0.35 `strat_negated` = **59.79**,
beating both the random floor (52.55) and the ink-oracle (54.71) at that budget. The
scorer *did* learn a real signal; only its sign is wrong. Negation-at-inference (or a
sign-correct objective) is the fix.

**The accuracy-vs-tokens curve (the deliverable) now exists** via `strat_negated`:

| keep | tokens | strat_neg recall | random | ink-oracle |
| --- | --- | --- | --- | --- |
| 1.00 (control) | 4800 | 72.55 | — | — |
| 0.75 | 3600 | 71.29 | 68.57 | 69.98 |
| 0.50 | 2400 | 67.37 | 62.31 | 62.50 |
| 0.35 | 1680 | 59.79 | 52.55 | 54.71 |

**~~Pending 1d answered (selection rule matters).~~ Partly right, and it does not
generalise — see run 8.** In run 7 `strat_negated` lifts worst-case line coverage
(min cov 0.38–0.63) far above global `negated` (0.08) and the forward router
(~0.003), which looked like confirmation of D2. Run 8 reverses it: with a
sign-correct scorer, `stratified` (75.80, min cov 0.441) *loses* 4.4 pts to the plain
global `router` (80.17, min cov 0.266) — i.e. **better worst-case coverage, worse
recall.** So a per-row budget rescues a *broken* scorer and costs accuracy on a
working one. The honest statement of 1d is conditional, not settled.

**Verdicts the harness printed for run 7, transcribed (they were not, at the time).**
Two of the five say something the summary above did not:

- **Q2 — "PREMISE IS WEAK."** The keep=0.50 ink oracle scored 62.50 vs a 72.55
  full-page control, **−10.06 pts**. This is the row designed to be able to kill 1a,
  and on run-7 weights it fired. Run 8 then printed **"PREMISE HOLDS"** (74.79 vs
  78.25, −3.46) on *identical masks* — the oracle's mask is weights-independent, so
  the premise's status is a property of **the weights, not the page**. A checkpoint
  can make half its own tokens undroppable. Do not treat "are these tokens
  droppable" as a fixed fact about the dataset.
- **Q3 — "INCONCLUSIVE"**, not the D2 confirmation implied above (ink ρ 0.571 vs min
  cov 0.565 over n=700). See Diagnostic D3.
- Q1 "NEGATION IS A REAL FIX", Q4 "THE SELECTION RULE WAS THE BUG", Q5 the curve —
  all consistent with the write-up above.

**Finding that got recorded as a caveat and should not have been: the pruning-ON
retrain cost 5.2 pts of full-page recall.** Control drift 10.93 pts — the retrained
full-page row (72.55 / 55.11 / 42.12) is below run 6 (77.74 / 64.70 / 53.05) by
−5.19 recall, −9.59 char acc, **−11.23 word order**. That is a real cost of training
with pruning ON, on the *unpruned* configuration, and word order took the worst of
it. It was logged as "the fine-tune lowered the ceiling" and moved past. Run 8's
supervised retrain did not pay this cost (+0.51 recall vs run 6), which suggests the
damage came from the STE/sparsity objective rather than from pruning per se —
testable, untested.

Rows are comparable to each other and to this control; do **not** quote against run 6
absolutely.

**ToMe still unexercised** — every row used `merge_ratio=0.0` (see Kilo finding:
~49% of redundancy is unmergable after the router's score-sort), so Pending 1c's
`merge_ratio` rows remain outstanding.

### Run 8 — sign-fix retrain (Kaggle T4, 2026-08-31)

The Run 7 follow-up. Same pruning-ON retrain (keep=0.5, 5 ep, from run-5 weights) **plus an
ink-BCE saliency loss** that supervises the router with a free text proxy (`patch_ink` contrast →
target), so it learns to rank TEXT high instead of the blank-paper-above-text inversion. Results
in `run 8/ablation_selection.json`, checkpoint `run 8/adaptive_donut_pruned.pt`.

**The sign-fix worked, and decisively.** The forward `router` mode is now correctly signed:

| keep | tokens | router (forward) | random | ink-oracle | negated (now broken) |
| --- | --- | --- | --- | --- | --- |
| 1.00 (control) | 4800 | 78.25 | — | — | — |
| 0.75 | 3600 | 75.19 | 72.10 | 75.96 | 38.80 |
| 0.50 | 2400 | **80.17** | 60.75 | 74.79 | 8.25 |
| 0.35 | 1680 | 77.80 | 48.37 | 74.24 | 3.00 |

- **The sign fix itself is solid and the role-flip is the proof.** `negated` collapsed
  from 73.09 (run 7, where it was the *working* mode) to **2.70**, and
  `strat_negated` from 67.37 to 8.25. A theory that predicts which row breaks next is
  doing real work; this is the strongest internal confirmation in the project.
- `router` at keep=0.35 keeps **77.80** recall — the curve is real.
- Worst-case line coverage of the forward router rises with keep (0.13 → 0.27 → 0.56).

**~~Forward `router` beats the ink oracle at every keep_ratio.~~ True as a number,
but it is very likely a train/eval distribution-match result, not a selection-quality
one.** Run 8 trained at `TRAIN_KEEP_RATIO = 0.50`
(`scripts/make_kaggle_pruning_notebook.py:63`), so exactly one cell of the table has
eval config == train config, and that cell is the peak. Diagnostic D3, at keep=0.50:

| rule | recall | retained ink | min line cov | on-distribution? |
|---|---|---|---|---|
| `router` | **80.17** | 0.790 | 0.266 | **the rule training used** |
| `stratified` | 75.80 | 0.720 | 0.441 | off |
| `ink` oracle | 74.79 | **0.994** | **0.955** | off |
| `random` | 60.75 | 0.497 | 0.265 | off |

The oracle has **more ink and better worst-case coverage** than the trained rule and
still loses by 5.38 pts; `stratified` uses the *same scores* with a better-covering
rule and loses by 4.42. Every rule the decoder was not adapted to pays, whether its
proxies are better or worse. And the router's own curve
(0.35→77.80, **0.50→80.17**, 0.75→75.19, 1.00→78.25) peaks exactly on the trained
ratio — which is also why keep=0.50 beats the full-page control. So the supportable
claim is **"a router co-adapted with the decoder beats selection rules the decoder was
not adapted to, at the ratio it was trained for"** — materially weaker than "beats the
best hand-crafted text proxy," and it would not survive review as written.

*Stated as a hypothesis with its falsifier, per convention:* co-adaptation predicts
that a decoder fine-tuned **with ink-oracle selection** would close most of that
5.38 pt gap. Untested. Note run 7 shows the effect is **not** unconditional — there the
trained rule was catastrophically bad and all five off-distribution rules beat it, so
"the trained rule always wins" is false; co-adaptation is a confound on the margin,
worth ~5 pts, not a universal artifact. `keep=0.75` (75.19) scoring *below*
`keep=0.35` (77.80) is **still unexplained** by this or any other hypothesis on file.

- **Control drift 1.3 pts is not a clean pass.** 78.25 vs run-6's 77.74 was read as
  "the retrain raised the ceiling, so the warning is benign." That may be true, but
  the row uses different weights, so it cannot distinguish that from a harness
  problem. See the note under the run table. **Addressed in code by F2 (2026-08-31):
  run 9 evaluates the run-5 weights through the same harness first, which makes the
  ceiling-vs-harness question decidable. Runs 7 and 8 remain ambiguous retroactively —
  no control can be added to a run that already happened.**
- **Two knobs changed at once — now verified against the source, not inferred.**
  `SUPERVISE_SALIENCY=True` flips **three** values in one `if/else`
  (`kaggle_pruning_run.ipynb` cell 11, lines 41–48): `lambda_sparsity` 2.0 → **0.0**,
  `target_budget` 0.50 → **1.0**, and `LAMBDA_SAL` 0.0 → **2.0**. So run 8 both *added*
  ink supervision and *removed* all token-budget pressure. This is the exact mistake the
  run-6 gotcha warns about — attribution is wrong even when the fix works. Probably
  harmless (top-k enforces the count regardless of what the loss wants), but it is an
  assumption, not a measurement, and it means "the ink-BCE loss fixed the sign" is
  strictly "one of these two changes fixed the sign."
- **And the ink-BCE loss itself is mis-specified — see Diagnostic D4.** It passes an
  already-sigmoid'd score to `binary_cross_entropy_with_logits`, attenuating the gradient
  3.7× on correct tokens and **112× on the tokens it is most wrong about**. The sign-fix
  survived because sigmoid is monotone, so this does not undercut the result — it means
  **80.17 / 77.80 are a floor**, reachable through a broken loss, and the corrected loss
  has never been run. **Fixed 2026-08-31 (F1), still not run — run 9 is the test.**
- **The efficiency claim does not hold.** 65% fewer tokens → 7.1% less wall-clock
  (0.22× proportional). See Diagnostic D3 and the deliverable note at the top.

**Conclusion, restated honestly.** Run 8 produced a real accuracy-vs-**token-count**
curve: 35% of visual tokens retains 77.80% word recall, within 0.5 pts of the
full-page ceiling. The learned router is the best *selection rule at its trained
budget*, which is a genuine result. It is not established that it beats the ink
proxy as a ranking, it is not an efficiency result, `merge_ratio` (ToMe) remains
untested after 8 runs, and the loss that produced it has a one-line defect (D4) that
should be fixed before any further tuning — the numbers above are a floor.
**Update 2026-08-31:** that defect is now fixed (F1) but **unrun**, so every number in this
section still comes from the broken loss. They stay as the record of run 8.

### Failed attempts (no metrics — recorded so they aren't repeated)

- **2026-08-29, Phase 2c attempt 1 — died at 1214 s, no results.** Two faults:
  1. `RESUME_CKPT not found: /kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt`.
     The assert did its job (20 min lost, not 4 h) but reported only what was
     *missing*, never what was *present*, so it gave nothing to correct with.
  2. **`Using device: cpu`** — no accelerator was attached, and **nothing objected.**
     This was the more dangerous fault: it does not raise. Had the path been
     correct, the ablation would have run 5 configs × 50 samples on CPU (hours, not
     ~11 min) and its CONTROL row would likely have tripped the 0.5 pt drift check
     regardless, because run 5's reference numbers came from a GPU and greedy
     decoding is not bit-identical across devices. A plausible-but-wrong table is
     worse than a crash.

  Also wasteful: ~19 of the 20 minutes went to downloading FUNSD×8 + 500 SynthDoG
  that eval-only mode then discarded via `EPOCHS=0`.

  All three fixed by `scripts/patch_notebook_phase2c_fixes.py`. **Attempt 2 then
  succeeded** and produced run 6 — the fixes worked: the log shows
  `Using device: cuda / GPU: Tesla T4` and `EVAL-ONLY mode: skipped train set`.

### Run 9 — F1 loss fix + F2 harness control (Kaggle T4, 2026-09-01)

Artifacts in `run 9/` (`ablation_selection.json`, `ablation_decoding.json`, `metrics.json`,
`pruned_ocr_results.zip` containing the executed `__notebook__.ipynb`). Configuration as
launched: `RESUME_CKPT` resolved by the cell-2 basename glob to
`/kaggle/input/datasets/nafis8766/token-pruning-dataset/adaptive_donut_funsd.pt`,
`DO_TRAIN=True`, `TRAIN_KEEP_RATIO=0.50`, `TRAIN_EPOCHS=5`, `SUPERVISE_SALIENCY=True`
(⇒ `LAMBDA_SAL=0.5`, `lambda_sparsity=0.0`, `lambda_entropy=0.0`, `target_budget=1.0`),
`SALIENCY_THRESHOLD=0.15`. Identical to run 8 except the loss — so run 8 → run 9 deltas
are the **loss change** and nothing else.

**The launch checklist worked.** All six watch-points printed as specified, including the
one that mattered: `Resumed … (missing=0, unexpected=0)`.

**F2 passed at 0.00 pts — the first anchored numbers in this project.**

```
--- HARNESS CONTROL: run-5 weights through this harness
    weights restored and fingerprint-verified
    got (77.74, 64.70, 53.05)  vs run 6 (77.74, 64.7, 53.05)  max drift 0.00 pts
    HARNESS OK - the same weights reproduce run 6 through this code, so row 0's
    drift below is the RETRAIN, not the measurement.
CONTROL vs run 6 (77.74, 64.7, 53.05)
  got (77.30, 64.21, 54.14)   max drift 1.09 pts
  DIFFERENT CEILING - and the harness was verified above, so this 1.09 pt gap
  is what the retrain did to unpruned accuracy, not measurement noise.
```

`harness_verified: true` is stamped in `ablation_selection.json`'s meta alongside
`control_ckpt`. The retrain cost −0.44 recall / −0.49 charAcc at keep=1.00 and *raised*
word_order +1.09 — the 1.09 pt drift is the word_order component, not a recall regression.
**Runs 7 and 8 remain retroactively ambiguous; run 9 onward is not.**

**Full sweep (16 rows, n=50, seed 0).** `minLC` = `mean_min_line_cov`, worst-covered text
line per image, averaged.

| config | keep | recall | charAcc | order | ink | minLC | lat ms | vis tok | gen tok |
|---|---|---|---|---|---|---|---|---|---|
| HARNESS CONTROL run-5 wts | 1.00 | 77.74 | 64.70 | 53.05 | 1.000 | 1.000 | 3066 | 4800 | 252 |
| keep=1.00 router CONTROL | 1.00 | 77.30 | 64.21 | 54.14 | 1.000 | 1.000 | 3058 | 4800 | 251 |
| keep=0.50 router | 0.50 | **79.63** | 64.81 | 54.08 | 0.922 | 0.601 | 2966 | 2400 | 270 |
| keep=0.50 NEGATED | 0.50 | 15.65 | — | — | 0.078 | 0.002 | 2390 | 2400 | 186 |
| keep=0.50 random | 0.50 | 62.56 | — | — | 0.497 | 0.265 | 2642 | 2400 | 224 |
| keep=0.50 ink ORACLE | 0.50 | 76.89 | — | — | 0.994 | 0.955 | 2873 | 2400 | 258 |
| keep=0.50 stratified | 0.50 | 73.13 | — | — | 0.758 | 0.495 | 2793 | 2400 | 245 |
| keep=0.50 strat NEGATED | 0.50 | 19.51 | — | — | 0.242 | 0.001 | 2353 | 2400 | 181 |
| keep=0.75 router | 0.75 | 79.41 | — | — | 0.986 | 0.862 | 2972 | 3600 | 259 |
| keep=0.75 random | 0.75 | 74.75 | — | — | 0.749 | 0.539 | 2826 | 3600 | 243 |
| keep=0.75 ink ORACLE | 0.75 | 77.84 | — | — | 1.000 | 0.998 | 2973 | 3600 | 263 |
| keep=0.75 strat NEGATED | 0.75 | 49.43 | — | — | 0.527 | 0.026 | 2607 | 3600 | 210 |
| keep=0.35 router | 0.35 | 75.85 | — | — | 0.826 | 0.392 | 2933 | 1680 | 271 |
| keep=0.35 random | 0.35 | 49.02 | — | — | 0.349 | 0.137 | 2551 | 1680 | 213 |
| keep=0.35 ink ORACLE | 0.35 | **77.60** | — | — | 0.950 | 0.739 | 2968 | 1680 | 272 |
| keep=0.35 strat NEGATED | 0.35 | 10.37 | — | — | 0.129 | 0.000 | 2204 | 1680 | 160 |

Training: `Epoch 1..5 | Avg Loss 0.3091 / 0.0658 / 0.0491 / 0.0395 / 0.0383`, `CE`
identical to 4 dp in every epoch — see the Gotcha, this is a *reporting* artifact and says
nothing about the saliency term.

**What run 9 settles.**

* **F1's mechanism worked.** Retained ink rose at every budget: +0.132 (keep=0.50),
  +0.061 (0.75), +0.135 (0.35). The D4 logit fix did exactly what it was designed to do.
* **F1's predicted accuracy gain did not appear** — see the struck prediction under
  "Run 9 — launch checklist". `keep=0.50 router` went 80.17 → **79.63**.
* **The sign fix holds decisively.** Forward 79.63 vs negated 15.65; ink 0.922 vs 0.078.
  D1's inversion is fully repaired (retained ink 0.922 vs random's 0.497).
* **Stratified selection is not the answer** — 73.13, *down* from run 8's 75.80, and 6.5 pts
  below the plain router. Pending 1a's "train with stratified selection" loses its premise.
* **`repetition_penalty=1.3` costs 24 pts, third independent confirmation**: 55.55 vs 79.63.
  `no_repeat_ngram_size=3` is inert when the penalty is on (55.55 either way) but worth
  +3.71 when it is off (79.63 vs 75.92). `min_new_tokens` is inert — "both off" and
  "both off + minlen" are identical to every decimal. Both already on the rejected list.

## Diagnostic D6 (2026-09-01, from run 9's own rows) — the weight change and the selection change can be separated, and they point opposite ways

Not a separate run: a re-read of run 9 against run 8. Costs nothing and is the most
valuable thing in run 9.

**The lever.** Seven of the 15 sweep rows have `Δretained_ink = 0.000` between run 8 and
run 9 — byte-identical token selection. Two independent reasons this is exact, not
approximate:

1. `select_mode` in `('ink', 'random')` derives the ranking from the image (ink) or a fixed
   `SELECTION_SEED=0` (random). Neither reads the router's scores.
2. `src/router.py:92` gates the STE score-scaling on `self.training and use_ste and
   select_scores is None`. At eval `self.training` is False, so `selected_tokens` is a bare
   `torch.gather` — **scores never scale the kept tokens.** Router weights can therefore
   influence only *which indices* are chosen, and in these rows they choose none of them.

So those rows vary the **weights** with selection held fixed, and the router rows vary
both. Subtract to get each contribution:

| row (selection identical) | run 8 | run 9 | Δ |
|---|---|---|---|
| keep=1.00 (nothing pruned) | 78.25 | 77.30 | **−0.94** |
| keep=0.50 ink | 74.79 | 76.89 | +2.10 |
| keep=0.50 random | 60.75 | 62.56 | +1.81 |
| keep=0.75 ink | 75.96 | 77.84 | +1.88 |
| keep=0.75 random | 72.10 | 74.75 | +2.65 |
| keep=0.35 ink | 74.24 | 77.60 | +3.36 |
| keep=0.35 random | 48.37 | 49.02 | +0.64 |

**Finding 1 — the decoder specialised further to pruned input.** Worse on full input,
better on *every* pruned input regardless of the rule that produced it. The encoder is
frozen and the router cannot reach these rows, so the decoder is the only candidate.
Mechanism: run 8 spent gradient on `LAMBDA_SAL=2.0` plus `lambda_entropy=0.05`; run 9 cut
both, so CE dominated and the decoder got better at its training condition (keep=0.50) and
its neighbourhood, at a small cost on the untrained keep=1.00 condition.

**Finding 2 — netting that ≈+2 pt baseline out of the router rows reverses the sign of
F1's effect on *selection*.**

| keep | router Δ | Δ retained ink | ≈ selection effect |
|---|---|---|---|
| 0.75 | +4.22 | +0.061 | **+1.9** |
| 0.50 | −0.54 | +0.132 | **−2.5** |
| 0.35 | −1.94 | +0.135 | **−3.9** |

F1 helped *above* the trained budget and hurt at and below it, and it hurt most where it
moved retained ink most. **This upgrades D2 from a broken correlation to an intervention:**
D2 showed retaining ink does not imply accuracy; run 9 shows optimising the ink proxy
*harder* actively costs accuracy. Corroborating, at keep=0.35 the ink oracle now *beats*
the router (77.60 vs 75.85) where run 8 had the router ahead by 3.56 — the router moved
toward the oracle's behaviour and inherited its ceiling.

**Caveat on the arithmetic.** The subtraction assumes the decoder's gain transfers
additively across selection modes. The ink and random rows agree within ~0.3 pt at keep=0.50
and 0.75 (+2.10/+1.81, +1.88/+2.65) but disagree by 2.7 pt at keep=0.35 (+3.36/+0.64), so
the −3.9 figure is the softest of the three. The *signs* do not depend on the assumption:
at keep=0.50 and 0.35 the router row moved down while both fixed-selection rows moved up.

**What this does NOT establish.** Not that the decoder is co-adapted to *the router's
particular* token distribution (Pending 5's question) — the gain here transfers to random
and ink alike, which is adaptation to reduced-token input in general. It does establish
that Pending 5's 2×2 cannot be skipped by pointing at the router's margin over the oracle,
since that margin now moves ±5 pts on a loss-config change alone. And it does not identify
a better training target; it only rules the ink proxy out as one.

**Q3 (worst-line coverage), incidentally answered.** `mean_min_line_cov` does not order the
rows: at keep=0.50 the router wins with 0.601 against the oracle's 0.955, and at keep=0.35
it loses with 0.392 against 0.739. Coverage looks binding only once it falls below ~0.4.
D2's retracted second half stays retracted.

## Diagnostic D7 (2026-09-01, local CPU) — Pending 13(a) is DEAD, and the reason reframes what the ink term was actually supplying

`scripts/diagnose_ste_signal.py`. Built to decide whether Pending 13(a) ("drop the auxiliary
term and train the router on task CE through the STE alone") was worth a GPU session, before
booking one. It answers no, and the *way* it answers no changes the design requirement for
13(b)/(c).

### The hypothesis I went in with — ~~falsified twice over~~

> ~~Run 7's STE-only retrain did not fail because STE is a weak signal; it failed because two
> collapse pressures (sparsity ×2.0 pulling mean(score) onto 0.50, entropy ×0.05 pushing every
> score toward 0.5) outweighed it. If true, 13(a) is well-motivated and is not a repeat of
> run 7.~~

Both halves are wrong, and each was refuted by a separate part of the same script:

- **No collapse happened.** Run 7's score std is **1.85× run 5's** (0.3817 vs 0.2059) — nearly
  double, not shrunk — and its mean sits **0.166 away from 0.50**, i.e. it moved *away* from
  the sparsity target rather than onto it.
- **The auxiliaries were never big enough to outweigh anything.** Combined, they are **3.2% of
  the router gradient** at run-5 weights and **7.6%** at run-7 weights (Part B). They could
  not have dominated a term 13–30× their size.

Left struck rather than deleted because the reasoning was sound and the conclusion was still
wrong: the algebra of both terms genuinely does push toward 0.5 (verified in F3, five score
values, gradient signs measured). What I never checked was whether they push *hard enough to
matter*, and the answer is no by more than an order of magnitude. A correct mechanism at a
negligible magnitude is not an explanation.

### Part A — score distributions across checkpoints (FUNSD, n=2)

| run | loss config | mean | std | r(score, ink) test | r(score, ink) train |
|---|---|---|---|---|---|
| run 5 | STE at keep=1.0 (K=N ⇒ multiplier ≡ 1.0, no routing gradient) | 0.4529 | 0.2059 | −0.150 | **−0.280** |
| run 7 | STE + sparsity 2.0 + entropy 0.05, no ink | 0.3343 | 0.3817 | −0.121 | **−0.242** |
| run 8 | STE + ink-BCE, D4 double-sigmoid bug live | 0.1607 | 0.3317 | +0.537 | **+0.630** |
| run 9 | STE + ink-BCE 0.5, D4 fixed | 0.3214 | 0.3266 | +0.748 | **+0.765** |

(mean/std shown for the test split; the train split gives the same picture — run 5 0.4453/0.2197,
run 7 0.3265/0.3769, run 8 0.1815/0.3483, run 9 0.2898/0.3385.)

All four load with `missing=0, unexpected=0`. **`r` at n=2 is noisy — do not quote the
values.** Run 5 reads −0.150 (test), −0.280 (train) and −0.237 on a single test page, against
D1's −0.226/−0.248; the *sign* and the run-to-run *ordering* are the robust content, not the
magnitude. What the ordering says is worth stating plainly: **five epochs of predominantly-STE
training moved run 7's correlation from −0.280 to −0.242 — it stayed inverted — while the ink
term took it to +0.765.**

### Part B — per-term gradient norm at `router.scorer`, each term backwarded alone

Measured at **two weight points × two splits**, and the spread across those four cells is the
main lesson of this part. Two weight points because the sparsity gradient is
`λ · smooth_l1'(mean, 0.50)`, which *grows* as the mean leaves the target, so a ratio taken
only at run 5's mean (0.4529, |dev| 0.047) would understate it across run 7's own trajectory
(ended at 0.3343, |dev| 0.166). Two splits because the CE gradient scales with the CE, and
run-5 weights pruned to keep=0.50 sit in a high-loss regime that a single split misrepresents.

Ratios are to CE-through-STE in the same cell (>1× means the term outweighs 13(a)'s whole signal):

| term | run-5 w, test | run-5 w, train | run-7 w, test | run-7 w, train |
|---|---|---|---|---|
| **CE through STE** ‖grad‖ (loss value) | 7.040 (3.15) | 9.237 (4.39) | 3.930 (3.25) | 1.881 (1.33) |
| sparsity ×2.0 (run 7 had this) | 0.028× | 0.022× | 0.069× | **0.157×** |
| entropy ×0.05 (run 7 had this) | 0.004× | 0.003× | 0.007× | 0.015× |
| ink-BCE ×0.5 (run 9 had this) | 0.125× | 0.139× | 0.415× | **1.074×** |
| run 7's two auxiliaries **combined** | **0.032×** | **0.025×** | **0.076×** | **0.172×** |

**Run 7's auxiliaries were a minority of its router gradient everywhere measured — 2.5% to
17.2%** — so run 7 was *predominantly* STE-driven, and 13(a) removes that minority while
keeping the ≥83%. That retires 13(a) on evidence already on file: run 7's forward `router` mode
at keep=0.50 scored **18.80 recall with min-cov 0.003** (see the D3 section), against 77.80 for
the ink-supervised run 8. There is no reading in which deleting a ≤17% term turns an
18.80-recall router into a good one — least of all since the auxiliaries push toward mean 0.5
and higher entropy, which is not the axis run 7's failure lies on (its `r(score,ink)` stayed
negative, −0.280 → −0.242).

**Correction, logged because I published the narrow number first.** I initially wrote
"3.2–7.6%, never exceeded 8%" from the **test split alone**. The train split at run-7 weights
gives **17.2%**, because in-distribution CE there is 1.33 against test's 3.25 — the CE gradient
is less than half as large, so every auxiliary's share roughly doubles. "Negligible" was too
strong; "minority" is what the data supports. The conclusion did not move, but the margin did,
and a 2.4× error in a load-bearing ratio is worth recording as a caution against quoting a
one-split gradient ratio as if it were a property of the loss.

**The genuinely new number here is ink-BCE at 1.074× on train/run-7.** In-distribution, at the
weights run 7 actually ended on, the ink term is *larger* than CE-through-STE — not the 0.125×
minor perturbation the test split suggested. Together with Part D's coherence contrast this
makes run 9's `r(score,ink) = +0.765` unsurprising rather than puzzling: ink was never the small
term.

Note the notebook comment calling run 7 "the STE-only retrain" therefore lands on the right
conclusion for the wrong reason — it was a mislabel (run 7 took the `else` branch *with* two
auxiliaries), and it is substantively defensible only because those auxiliaries turned out to be
a minority, which nobody had measured. See Gotchas.

### Part C — the STE gives gradient to exactly K of N tokens (measured, not inferred)

`2400 of 4800` tokens have nonzero score gradient at `keep=0.50`, exactly `K`, **on both splits**.
The N−K dropped tokens are **stationary**: the router can learn "this kept token was worth
keeping" but never "that dropped token would have been better." A dropped token re-enters only
when a kept token's score falls below it.

Mobility is *not* the binding constraint, and this is the part that had to be measured rather
than assumed:

| quantity | test split | train split |
|---|---|---|
| tokens with nonzero score gradient | 2400 of 4800 (= K) | 2400 of 4800 (= K) |
| score gap at the K/K+1 boundary | 1.15e-4 | 6.42e-5 |
| tokens within 1e-3 of the boundary | 21 | 18 |
| mean per-step \|d(CE)/d(score)\| over kept | 3.57e-3 | 3.78e-3 |
| ratio (per-step signal ÷ boundary gap) | ~31× | ~59× |

The kept set churns freely on both splits — the per-step gradient dwarfs the gap that would have
to be crossed. **What is missing is not the ability to reorder but any *information* about the
dropped half.** That distinction is the whole reason 13(a) could not have worked: adding
optimisation pressure to a signal that is structurally blind to half the tokens does not make it
see them.

(The train-split Part C was briefly recorded here as "not obtained" after the first run's output
file was corrupted — see Gotchas. It was re-run to a clean path and is the right-hand column
above. The `= K` identity is structural and could not have come out otherwise; the useful new
content is that the ~31× mobility headroom is not a test-split artifact but is if anything larger
in-distribution.)

### Part D — the decisive number: magnitude was never the problem, coherence was

Norm says how hard a term pushes; cosine between per-page gradients says whether the pushes
agree. Displacement over training scales roughly as norm × coherence, so the norms alone are
the wrong comparison.

| term | split | cos(page0, page1) | ‖g‖ page0 / page1 | ≈ coherent displacement |
|---|---|---|---|---|
| CE through STE | test | **+0.214** | 12.41 / 6.30 | ~2.00 |
| ink-BCE ×0.5 | test | **+0.896** | 1.01 / 0.90 | ~0.86 |
| CE through STE | train | **+0.209** | 12.78 / 11.09 | ~2.49 |
| ink-BCE ×0.5 | train | **+0.854** | 1.52 / 1.29 | ~1.20 |

**The contrast replicates in-distribution**, which is the thing that mattered most to check:
ink-BCE's norm on the train split is 1.07× CE's *term-for-term* at run-7 weights (Part B), so
the "small but coherent" framing had to be re-tested where ink is not small. It holds — the
cosines barely move (0.214→0.209, 0.896→0.854), because coherence is a property of the target's
structure, not of its scale. CE's ~10× norm advantage collapses to **~2.3× (test) / ~2.1×
(train)** in coherent displacement, and the incoherent remainder does not accumulate: it moves
scores around (run 7's std nearly doubled) without moving the *ranking* (r stayed negative).

This is what reconciles the two facts that otherwise contradict each other: ink-BCE is a
minority of CE by norm on the test split, yet it is the term that flipped r(score,ink) from
negative to +0.75 and delivered 77–80 recall. **CE-through-STE is large and incoherent (0.21);
ink-BCE is smaller-to-comparable and systematic (0.85–0.90).**

Caveat on this table: a two-page cosine is a one-sample estimate of coherence, and the
gradient vectors include the scorer's output bias, whose systematic component is a global score
shift rather than a re-ranking. The 0.21-vs-0.87 contrast is far too large to be an artifact of
either, and it now has two independent splits behind it, but the numbers themselves should not
be quoted to three digits.

### What D7 establishes for Pending 13

1. **13(a) is dropped.** Not "deprioritised" — it is a re-run of run 7's 18.80-recall router.
2. **D6's prediction that (a) beats run 9 at keep≤0.50 does not survive.** D6 measured the
   *marginal* effect of fitting ink harder (run 8 → run 9: −2.5 pts at keep=0.50, −3.9 at 0.35)
   and item 13 extrapolated that negative slope all the way to zero ink weight. Run 7 is the
   zero-ink endpoint and it scored 18.80. The relationship is non-monotonic: **ink's marginal
   contribution is negative near run 9's operating point while its contribution from zero is
   strongly positive.** A local slope does not license the extrapolation, and D6's own caveat
   ("the −3.9 figure is the softest of the three") was the hint.
3. **The design requirement for 13(b)/(c) is now explicit, and it is not "a better proxy".**
   What ink supplied was not correctness — D6 refuted that — but three structural properties
   the task loss cannot supply: it is **dense** (defined on all N tokens, covering the N−K the
   STE cannot reach), **coherent** (cos 0.90, so it accumulates over steps), and **free**. Any
   replacement must keep all three and change only the *content*. This is the criterion 13(b)
   has to be judged against, and it is why "just use the task loss" cannot work no matter how
   large its gradient is.

### Two bugs found while building this, both of which produced plausible wrong numbers

- **A hand-rolled `patch_ink` silently pooled the page into a 1×4800 strip.** Inferring the
  token grid as `side = round(sqrt(N))` then decrementing until `side² == N` never terminates
  correctly for 4800 (= 80×60, not a square): it walks down to `side=1`. It *ran*, and produced
  a full table with `r(ink) ≈ 0` for every checkpoint — a result that would have read as "no
  router is ink-aligned", quietly contradicting D1 and run 9's 0.922 retained ink. Replaced
  verbatim with cell 7's `stride=32` version, which **raises** on grid mismatch instead of
  degrading. The tell was the contradiction with an existing measurement, not anything in the
  output itself.
- **Synthetic labels padded with `pad_token_id=1`** where the model's CE uses
  `ignore_index=-100`, so ~500 pad positions were scored as real targets. This inflates CE and
  therefore the CE gradient — biasing Part B *toward* the conclusion that 13(a) has a strong
  signal, i.e. in the direction I was hoping for. Replaced with cell 9's real pipeline
  (`reading_order_words` + `build_target_text`, copied verbatim, `-100` masking).

**The split bias — raised as a worry, then measured, and it did not behave as predicted.** I
expected FUNSD **test** pages to inflate CE (and so flatter the "auxiliaries are negligible"
conclusion) relative to in-distribution training data. Measured, the effect is real but *runs
in opposite directions at the two weight points*: at run-5 weights train CE is **higher** than
test (4.39 vs 3.15, so the test split was if anything conservative), while at run-7 weights
train CE is **less than half** of test (1.33 vs 3.25, so the test split did overstate CE — and
that is the cell where the auxiliaries reach 17.2% and ink-BCE reaches 1.07×). Both splits are
now in the Part B table rather than one being called canonical.

Note also that the natural comparison point — run 9's printed *training* CE of 0.309 — is not
comparable to any of these: it is a different checkpoint, after five epochs of adaptation to
keep=0.50, on a 500-synth + 400-FUNSD mixture whose synthetic half is easier. The reason CE is
~1.3–4.4 here is that run-5 weights are being evaluated **at keep=0.50 when they were trained at
keep=1.0** — losing half the tokens is itself a large shift. That is the correct regime for this
measurement, since it is the initial condition of the run 13(a) would perform, but it is
consistent-with rather than separately isolated from other explanations.

## Diagnostic D8 (2026-09-01, local CPU) — decoder cross-attention is a *different* target from ink, and it is not a fixed mask

`scripts/diagnose_attn_target.py`, n=4 FUNSD test pages, run-5 weights at `keep_ratio=1.0`.
D7 killed 13(a) and left 13(b) — "distil a per-token target from the decoder's own
cross-attention" — as the surviving candidate. This tests the two cheap ways for 13(b) to be
dead on arrival, both **pre-registered before running** so the answer could not be rounded
toward the one that keeps the plan alive.

### Test 1 — is cross-attention just ink? No.

If attention mass simply tracked inked patches, 13(b) would *be* 13(c) with extra steps and D6
has already ruled that target out.

| quantity (mean over 4 pages) | value |
|---|---|
| r(attn, ink) | **+0.083** |
| r(attn, router score) | **−0.045** |
| r(router score, ink) | −0.226 |
| top-K overlap attn vs ink @ keep=0.50 | 0.621 |
| top-K overlap attn vs router score | 0.394 |
| attention mass inside top-K | 0.901 |
| attention mass inside top-5% | 0.276 |

Threshold was "drop 13(b) if r ≥ 0.8 **and** overlap ≥ 0.90." Measured +0.083 and 0.621, so
attention is **very nearly orthogonal to ink** — per-page r was 0.097 / 0.088 / 0.072 / 0.077,
i.e. stable, not a noisy average. Two side findings:

- **`r(router score, ink)` came out at −0.226, matching D1's −0.226 to three decimals.** D1 used
  an independent script and an independent ink implementation. That is the cleanest cross-
  validation the fixed `patch_ink` has had, and it retires the "r at n=2 is noisy" caveat at n=4.
- **`r(attn, router score) = −0.045`.** The router is not merely anti-correlated with *ink* — it
  is **uninformed about what the decoder actually looks at**. That, not the ink correlation, is
  the real argument that there is headroom here.
- Attention is concentrated, not diffuse: half the tokens hold 90.1% of the mass and the top 5%
  hold 27.6% (5.5× uniform). So it did not pass Test 1 by being noise.

### Test 2 — the blind spot in Test 1, and the reason it needed a second test

Test 1's thresholds are **necessary but not sufficient**, which I did not notice until the first
run's per-page lines came back agreeing to three decimals across two unrelated forms. "Not ink"
has two causes with opposite implications:

1. attention tracks something else about *this page's content* → 13(b) is worth building;
2. attention is largely **page-independent** (positional bias / attention sink) → 13(b) is dead,
   because a target that is the same mask on every document teaches the router a constant.

Cause (2) passes Test 1 *perfectly* — a fixed mask is maximally "different from ink." So Test 2
compares each quantity across all 6 page-pairs, with **ink as the calibration baseline**: two
mostly-white forms genuinely share layout, so ink's own cross-page agreement is the floor that
"content-dependent" has to beat, not 0.50.

| across-page agreement (6 pairs) | cosine | pearson r | top-K overlap | overlap range |
|---|---|---|---|---|
| **attention mass** | +0.598 | +0.380 | 0.645 | 0.602–0.685 |
| ink (baseline) | +0.548 | +0.308 | 0.655 | 0.600–0.778 |
| router score (baseline) | +0.831 | +0.097 | 0.569 | 0.547–0.599 |

| centre of mass of top-5% tokens, 80×60 grid | row spread (sd) | col spread (sd) |
|---|---|---|
| **attention** | **6.12** | 0.59 |
| ink | 1.81 | 1.03 |

**Verdict: not a fixed mask.** But the *reason* is the centroid spread, not the ink comparison,
and that distinction matters:

- The overlap comparison is **too close to call**. At n=2 attention looked more page-varying than
  ink (0.602 vs 0.635, gap 0.033); at n=4 the gap shrank to 0.010 (0.645 vs 0.655) with heavily
  overlapping ranges. The pre-registered branch fired on `attn ≤ ink`, but a 0.010 margin is not
  evidence. **Do not quote "attention varies more across pages than ink."** The defensible claim
  is that it varies *at least as much*.
- The robust discriminator is the **centroid spread: 6.12 vs 1.81 grid rows, a 3.4× difference.**
  Attention's top-5% centre of mass moves across a 15-row band (30.3 → 45.3) while ink's sits in
  a 5-row band. Attention picks *which* text region to look at; ink reports that all these forms
  have text in the middle. Note the columns invert (0.59 vs 1.03) — attention's variation is
  almost entirely vertical, which is what block-selection on a form should look like.

### A methodological correction: cosine was the wrong statistic to pre-register

I set the Test-2 threshold at `cosine ≥ 0.95`. **Cosine is inflated for these vectors** —
attention mass and ink are both non-negative, so a large shared positive mean dominates the inner
product regardless of structural agreement. The router-score row is the proof: cosine +0.831 with
pearson r of only +0.097. Cosine reads "83% agreement" for a vector whose mean-centred agreement
is ~10%; it was measuring the offset, not the pattern.

Pearson r is the right cross-page statistic here, and it is already in the table (+0.380 for
attention). The verdict is unaffected — 0.598 and 0.380 are both nowhere near "fixed mask" — but
the threshold was set on a statistic that could not have failed informatively. **Future
cross-page thresholds go on r, not cosine.**

### Per-layer: depth matters, and it is a design decision D8 does not settle

| decoder layer | mean r(attn, ink) | cross-page overlap@K | cross-page cosine |
|---|---|---|---|
| 0 | +0.022 | 0.653 | +0.546 |
| 1 | +0.062 | 0.662 | +0.603 |
| 2 | +0.045 | 0.658 | +0.574 |
| 3 | **+0.201** | 0.646 | **+0.498** |

The last layer is ~2.4× more ink-aligned than the 4-layer mean (+0.201 vs +0.083) *and* the most
page-varying (lowest cross-page cosine). Both point the same way: layer 3 is the most
content-specific. That cuts two ways and D8 cannot resolve it — using layer 3 alone would be the
most semantically focused teacher but moves 13(b) measurably *toward* ink; using the mean keeps
it maximally distinct from ink but averages in three layers that are nearly ink-orthogonal and
may be nearly content-orthogonal too. **Default to the mean over layers**, because that is the
aggregation whose properties were actually measured above, and record layer choice as an
untested knob.

### Standing caveat, unchanged by any of this

**Attention mass is not causal importance.** The rigorous target is the leave-one-out effect of
dropping each token on CE — 4800 forward passes per image, infeasible. Attention is a tractable
proxy, and *a proxy is exactly what D6 punished*. What makes it a better proxy than ink is that
it is derived from the model's own use of the tokens rather than from the pixels; that is an
argument, not a proof. 13(b) is validated by recall on a real run or not at all.

No `src/` change was needed: `model.model.decoder` accepts `output_attentions=True` directly.
**transformers 5.x defaults to SDPA, which does not materialise attention weights**, so the
script forces `_attn_implementation = "eager"` and then *asserts* `cross_attentions` is non-empty
rather than trusting it — a silent `None` would have made every number here a vacuous zero.

## Diagnostic D9 (2026-09-01, local CPU) — the attention target is *reachable* by this router, and the number that says so is not the one I first reported

`scripts/diagnose_target_learnability.py`. D8 established that cross-attention is a different,
content-bearing target. Neither of its tests established that the router can **predict** it, and
a target can satisfy every requirement D7 laid out and still be unreachable by the model that
has to fit it — a structural refutation, independent of D6's accuracy argument, worth one CPU run
instead of a GPU session to discover.

The reason this was a live risk: `PatchSaliencyRouter.scorer` is
`Linear(1024,256) → LayerNorm → GELU → Linear(256,1) → Sigmoid` applied to **one token's own
encoder feature**. No coordinates, no neighbourhood, no global pooling. Ink is a local contrast
statistic and Swin's late features encode local texture, so ink is learnable almost by
construction. Attention is chosen by a decoder that sees the whole page and its own generated
text so far; if that decision depends on context a single token's feature does not carry, no
amount of density, coherence or freeness helps.

Method: freeze run 5, extract per-page encoder features + teacher attention + ink for 8 FUNSD
test pages, then fit a **fresh scorer of the identical architecture** on 5 pages and evaluate on
3 **held-out pages** — held-out pages, not held-out tokens, because the router must generalise
across documents and an MLP fitting 4800 tokens of one page proves nothing about that. Same init
seed, optimiser and step budget for every target, so the only thing that varies is what is being
predicted.

| target | final BCE | AUC train | AUC held-out | retained teacher-attn mass @K |
|---|---|---|---|---|
| **attn** (the 13(b) target) | 0.0053 | 1.000 | **0.976** | **0.896** |
| ink (known-learnable reference) | 0.0233 | 1.000 | 0.926 | 0.558 |
| shuffled (known-unlearnable floor) | 0.2448 | 0.984 | **0.498** | 0.569 |
| _teacher's own top-K (ceiling)_ | – | – | 1.000 | 0.910 |
| _random selection (floor)_ | – | – | 0.500 | 0.505 |
| _mean attn map, no features (page-INDEPENDENT control)_ | – | – | **0.764** | 0.730 |
| _mean ink map, no features (page-INDEPENDENT control)_ | – | – | 0.775 | 0.490 |

### The control that changed the headline

The first run reported held-out AUC **0.979** and I did not believe it. The same failure mode D8
Part 2 was built to catch reappears one level down: **a probe can earn a large held-out AUC by
predicting only the component of the target that is identical on every page.** D8 had already
measured attention's cross-page pearson r at +0.38, so that component was known to be
substantial. Predicting it is worth nothing for routing — it is a constant mask.

So the control is the best possible page-independent predictor: the mean teacher map over the
training pages, no features and no fitting. **It scores 0.764.** Three quarters of the way to the
probe's 0.976, from a fixed vector. Reporting 0.976 as "attention is learnable" would have been a
badly over-read number.

**The reportable quantity is the lift, and it survives the control:**

| target | probe AUC | constant-map control | **page-specific lift** |
|---|---|---|---|
| attn | 0.976 | 0.764 | **+0.212** |
| ink | 0.926 | 0.775 | **+0.151** |

Attention's lift is **larger than ink's** — the probe reads more page-specific signal from the
attention target than from the ink target. That is the claim D9 supports, and it is a weaker and
more specific claim than "AUC 0.976."

### Three things this run got right that are worth keeping

1. **The shuffled control validated the whole setup rather than decorating it.** Train AUC 0.984,
   held-out 0.498. The probe demonstrably *can* memorise an arbitrary per-token target within a
   page and still lands exactly on chance across pages. Without that row a high held-out AUC
   would be uninterpretable — it is what rules out "this probe would score well on anything."
2. **D8 and D9 cross-validate through completely different measurements.** The **constant ink map
   (0.775) beats the constant attn map (0.764)** at predicting its own target, i.e. ink is the
   more page-invariant of the two. That is the same conclusion D8 reached from top-5% centroid
   spread (ink 1.81 vs attention 6.12 grid rows), by an unrelated route. D8's overlap comparison
   was too close to call at a 0.010 margin; this is independent confirmation that its centroid
   finding was the right discriminator.
3. **`AUC train = 1.000` is expected, not a red flag.** ~262K params against 5 × 4800 tokens
   memorises easily. It makes the held-out numbers a **conservative** estimate of reachability:
   the real run has ~900 images, so it would generalise better, not worse.

### What D9 does NOT establish — and the reminder is printed by the script itself

- **Reachability, not merit.** Every number is scored against the teacher's own attention, so a
  probe trained on attention winning the retained-attention-mass column is close to tautological.
  **D6 is the standing warning: fitting the ink proxy *harder* cost accuracy at two of three
  budgets.** 13(b) is validated by recall on a real run or not at all.
- **The auxiliary is measured in isolation.** In the real run the router receives attention-BCE
  *and* task CE through the STE simultaneously, while the decoder is itself adapting. D9 isolates
  the auxiliary — the right isolation for a reachability question, but it says nothing about the
  interaction.
- **Retained-mass for ink (0.558) is not a verdict on run 9.** It says an ink-trained scorer
  captures little *attention* mass, which is a restatement of r(attn,ink) = +0.083, not evidence
  about OCR recall.

## Diagnostic D10 (2026-09-02, local CPU) — the last precondition for 13(b): the on-the-fly target is stationary *and* page-specific

`scripts/diagnose_target_drift.py`, 5 FUNSD **train** pages, ~4 min on CPU, no GPU, no
downloads. Read-only.

**The question, and why it was still open.** 13(b) computes its target on the fly:
`topK(run5_decoder.cross_attention(student_encoder(page)))`. The teacher decoder is a frozen
run-5 snapshot, so *decoder* drift is irrelevant by construction. The encoder is **not**
frozen — `UNFREEZE_STAGES = 1` trains the top Swin stage — so the target is recomputed every
step from features that move. If it moves much, the router is fitting noise and 13(b) fails
for a reason that has nothing to do with the hypothesis. I had recorded this as an
unverified risk after getting the encoder-freeze question wrong once (see the 13(b)
precondition table), and had also recorded that the 1% weight drift **bounds nothing**,
because a small weight change can move representations further.

**The instrument was already on disk.** Run 5 → run 9 is a *completed* 5-epoch retrain under
the identical `UNFREEZE_STAGES = 1` config, so the drift run 10 will experience does not have
to be simulated or reasoned about. Load run 5's weights, encode; load run 9's weights,
encode the same pages; hold the teacher fixed; compare the targets. Everything measured is
attributable to the encoder alone.

**THE CONTROL IS THE POINT — and it is the same control this file already got wrong once.**
A high same-page overlap under drift means nothing on its own, because these targets share
page-invariant structure (both avoid the margins), so two targets from *different* pages
already overlap far above the combinatorial 0.500. So the reportable quantity is the gap:

- `S` = overlap(target from run-5 features, target from run-9 features) — **same page**
- `X` = overlap(target from page *i*, target from page *j*) — **different pages, the floor**

Both thresholds were written into the script **before** reading any output, so the diagnostic
could come out against launching: `S ≥ 0.90` **and** `S − X ≥ 0.20` → launch; `S < 0.75` or
`S − X < 0.10` → the on-the-fly design needs revisiting before spending GPU hours.

### A. Feature drift — 1% of weight movement moves the representation 7.6× further

| page | rel L2 ‖Δf‖/‖f‖ | cos(f5, f9) | per-token cos |
|---|---|---|---|
| 0 | 0.1194 | 0.9942 | 0.9702 |
| 1 | 0.0861 | 0.9974 | 0.9830 |
| 2 | 0.0918 | 0.9971 | 0.9796 |
| 3 | 0.0731 | 0.9983 | 0.9881 |
| 4 | 0.1357 | 0.9921 | 0.9599 |
| **median** | **0.0918** | 0.9971 | 0.9796 |

Weight drift was max **0.0120** on Swin stage 3 and exactly 0.000000 on stages 0–2. Feature
drift is **0.0918**, i.e. **7.6×** larger. That gap is the whole reason this section exists:
the weight numbers were reassuring and would have been the wrong thing to conclude from. The
representation still barely rotates in angle (global cos ≥ 0.992, per-token cos ≥ 0.96), which
is why the target survives — but "the weights only moved 1%" was not the argument that
established it.

### B. Target stability, against the floor it has to beat

| page | S = ov(T_run5, T_run9) | changed positives |
|---|---|---|
| 0 | 0.9671 | 79/2400 |
| 1 | 0.9567 | 104/2400 |
| 2 | 0.9729 | 65/2400 |
| 3 | 0.9613 | 93/2400 |
| 4 | 0.9529 | 113/2400 |

| quantity | value | |
|---|---|---|
| `S` same page, drifted encoder | **0.9613** | median over 5 pages |
| `X` different pages — the floor | **0.6246** | median over 20 pairs |
| chance (combinatorial) | 0.5000 | **NOT the right null; `X` is** |
| gap `S − X` | **+0.3367** | |

**Pre-registered `S ≥ 0.90` → PASS (0.9613). Pre-registered `S − X ≥ 0.20` → PASS (+0.3367).**
Fewer than 5% of the target's 2400 positives change across an entire 5-epoch retrain, and the
target carries a large amount of page-specific information that survives the drift.

### C. The drifted target is still well-posed

| features | positives | median grid rows touched |
|---|---|---|
| run 5 | {2400} (want {2400}) | 79/80 |
| run 9 | {2400} (want {2400}) | 79/80 |

Exactly K on every page from both encoders, and spread over 79 of 80 rows — the drift does
not collapse the target into a band or make it degenerate.

### `X = 0.6246` independently corroborates the inflated-floor lesson

This is the **second** construction to land in the 0.62–0.67 range as the null for a top-K
overlap on this grid: the content-free interior prior scores **0.654** against ink in
`verify_attn_target --real` (and 0.667 in an earlier probe), and cross-*page* attention
targets score **0.6246** here. Two unrelated routes to "structured maps on this grid overlap
≈0.63 for free." Any overlap statistic in this file read against 0.500 is overstated by
about **0.13**, which is exactly the error the ink-overlap number made once already.

### What D10 does NOT establish

- **Stationarity is not merit.** The target being stable says nothing about whether it helps.
  D6 is the standing case of a proxy fitted *harder* while accuracy fell. Acceptance for
  run 10 is recall at keep=0.50 and 0.35 against run 9, unchanged.
- **The drift was produced by run 9's objective, not run 10's.** Run 10 replaces the ink BCE
  with the attention BCE, and that changes the gradient reaching the top Swin stage, so run
  10's encoder need not drift by exactly 0.0918. The margin is wide (S = 0.96 against a
  0.90 threshold) but it is not a proof. **This residual risk is now observable at runtime
  rather than argued about:** the new `ov` column reports, every epoch, the fraction of the
  target's positives the router's own top-K keeps. A target moving out from under the router
  shows up there as `ov` stalling or oscillating near `ch`, in the training log, in epoch 1.
- **n = 5 pages, one drift trajectory.** The pages are FUNSD *train* pages, which is the
  right population for a question about what the router sees during training, but the
  medians are over five pages and twenty pairs.

## Diagnostic D1 (2026-08-29, local CPU, no GPU) — the router is an *inverted* saliency detector

Not a run: no training, no eval, no metrics row. `scripts/router_score_probe.py`,
run 5's checkpoint, 4 FUNSD test images, ~10 s/image on CPU. This was Pending
item 1's "cheap step 0", booked to answer one question before spending GPU hours:
**can the router rank tokens at all?**

It can. It ranks them *backwards*.

| # | What was measured | Result | Reading |
|---|---|---|---|
| A | Deviation of scorer weights from their distinctive init (LN weight 1.0, LN bias 0.0, final Linear bias const 0.5) | LN weight moved 0.035009, LN bias 0.0161198, final bias 0.00895119 | Router **did** train — gradient reached it |
| B | Score distribution, N=4800/image | mean 0.415–0.455, std 0.199–0.217, min ~0.012, max ~0.990, 4798–4800/4800 unique, **0%** saturated at either extreme; top-k boundary gap at keep=0.5 of 1.7e-05…2.0e-04 | Not flat, not saturated, selection not decided by ties |
| C | Cross-image Spearman of score-vs-position; top-50% Jaccard between images | rho **0.125**; Jaccard 0.398 (chance 0.333); score vs token L2-norm r = **−0.060** | Content-dependent, **not** a fixed positional mask, not a magnitude proxy |
| D | Same scores vs a **random-init** router on the same encoder features | Spearman **0.019**; Jaccard 0.348 (chance 0.333) | Training genuinely reoriented the ranking away from init |
| E | Neighbour agreement of the kept mask on the 80×60 grid | router **0.503**, random-init router **0.455**, random mask **0.333** | Kept set is spatially contiguous — but see below |
| F | **Fraction of the page's ink retained by the kept top-50%** | contrast: router **0.381** vs random **0.505**; darkness: router **0.343** vs random **0.500**. Pearson(score, ink) = **−0.226** / **−0.248** | **Worse than random. The router preferentially discards text.** |

**F is the finding. A–E are all true of a broken router.** Every one of A–E is a
property that a *good* router and a *whitespace* router share: both are trained,
well-spread, content-dependent, reoriented from init, and spatially clustered —
blank paper is contiguous too, which is *why* E looked good. A–E measure that the
router is doing *something* consistent; only F asks whether that something is the
right thing. Keeping half the tokens is only useful if they hold well over half
the ink; the router holds **34–38%**.

`visualizations/router_saliency_2.png` shows it without statistics: panel 2 (ink)
and panel 3 (saliency) are near photographic negatives of each other. The kept
mask is white in the blank gaps *between* text lines and black along the lines.

**The learned direction is real but sign-inverted.** Negating the score retains
**0.619** contrast / **0.657** darkness — above random, closing 23%/31% of the gap
to a perfect ink oracle, and better on all 4 images individually (0.646, 0.559,
0.712, 0.712 vs 0.354, 0.441, 0.288, 0.288). So the scorer did not fail to learn;
it learned a usable ranking and assigned it the wrong sign.

**Why, mechanically.** This is the `keep_ratio=1.0` STE trap (see gotchas) playing
out exactly as predicted, and then some. With K=N nothing is ever dropped and
`ste_multiplier = 1.0 + (w - w.detach())` has value exactly 1.0, so the only
gradient the scorer ever saw was `dL/dw_i = <dL/dtoken_i, token_i>` — "would
scaling this token's magnitude up reduce the loss?" That question has no reason to
align with "is this token informative", and empirically it anti-aligns: the
decoder's loss is reduced by *damping* high-magnitude glyph tokens (which it
already reads well) rather than by amplifying them. Four runs of training pushed
the scorer confidently in the wrong direction.

**Consequence for the plan.** The eval-only sweep would have measured this broken
ranking and produced a catastrophic accuracy-vs-tokens curve, and the natural
misreading of that curve is *"pruning ruins OCR"* rather than *"this router was
never trained to prune"*. The probe cost ~15 min of CPU and changed the
recommendation it was booked to support. Revised plan in Pending item 1.

## Diagnostic D2 (2026-08-29, local CPU, no GPU) — retained ink is the *wrong objective*; ~~worst-case line coverage is the right one~~ (second half retracted by D3)

> **PARTLY SUPERSEDED BY D3 (2026-08-31). Read D3 before acting on anything below.**
> D2's *negative* half survives: summed retained ink is not a sufficient objective,
> and H2 (contiguous gaps) is still falsified-and-inverted. D2's *positive* half —
> "worst-case line coverage is the right objective," which became the project's
> acceptance gate — **does not survive n=50**. The n=50 sweeps have a counterexample
> that retires it outright: run 8's `router` and `random` at keep=0.35 have
> essentially equal min line coverage (0.127 vs 0.137) and recall **29.42 pts** apart.
> The material below is kept because its reasoning is still instructive and the
> aggregate-vs-worst-case *question* is the right one to have asked; its conclusion is
> not to be quoted.

`scripts/diagnose_selection_geometry.py`, pure numpy on the arrays D1 already
cached in `visualizations/router_scores.npz` (4 FUNSD images, 4800 tokens each).
No model, no generation, runs in under a second.

**Why it was booked.** The n=2 smoke run of `scripts/eval_select_modes.py`
produced an ordering that D1's premise does not predict:

| mode | retained ink | word recall (n=2) |
|---|---|---|
| router | 0.424 | 42.60 |
| negated | 0.576 | 46.76 |
| random | 0.496 | **68.09** ← *less* ink than negated, **+21 pts** recall |
| ink oracle | 1.000 | 81.04 |

D1 had assumed retained ink was the quantity to maximise, and recommended
negation on that basis. **Random falsifies the assumption**: it retains less
total ink than negation and reads the page far better. So "maximise retained
ink" is not the objective, and a router trained toward it inherits the error.

**Two candidate geometries, both with the same total-ink signature:**

| # | Hypothesis | Result | Verdict |
|---|---|---|---|
| H1 | **Blinded lines.** What matters is whether every text line keeps *enough* to be read, not how much ink is kept in total. 0.5 spread evenly and "half the lines whole, half erased" are the same number. | ink stranded in rows below 25% coverage: router **35.1%**, negated **6.0%**, random **0.5%**, oracle **0.0%**. Coverage sd: negated 0.224 vs random 0.092 | **Direction confirmed, magnitude insufficient** — 6% stranded ink cannot alone buy a 21 pt gap |
| H2 | **Contiguous gaps.** Random drops isolated tokens (neighbours still cover the glyph); a ranked mode drops long runs, erasing whole words. | mean drop-run: random **1.97**, negated 2.62, router 3.20, **oracle 5.54** (38.2% of its gaps ≥ 5) | **FALSIFIED, and inverted** |

**H2 is worth dwelling on because it fails in the instructive direction.** The ink
oracle has by far the *longest* drop-runs and the *best* accuracy. Long runs are
the blank margins between words — dropping them is the entire point. So
"scattered selection is safer" is wrong; the best selection here is the
clumpiest one. Do not add a spatial-spread term to any router loss.

**The real split is AGGREGATE vs WORST-CASE, and it is clean:**

| statistic | family | ordering | vs recall |
|---|---|---|---|
| total retained ink | aggregate | ink > negated > random > router | **mis-orders** |
| mean line coverage | aggregate | ink > negated > random > router | **mis-orders** |
| min line coverage | worst-case | ink > random > negated > router | matches |
| p10 line coverage | worst-case | ink > random > negated > router | matches |
| −blinded ink | worst-case | ink > random > negated > router | matches |

Every aggregate statistic ranks negated above random; recall does the opposite.
Every worst-case statistic reproduces the recall order exactly. That is a
family-level split rather than one cherry-picked number, which is the only
reason it is worth reporting off 4 points — a single statistic ordering 4 rows
correctly is 1-in-24 by luck, and I tried several.

**Two consequences, one of which is architectural.**
1. **An auxiliary router loss must not reward summed retained saliency.** That is
   precisely the statistic that ranks negated above random, i.e. that gets the
   observed ordering backwards.
2. **A single global top-k has no mechanism to bound worst-case coverage at all** —
   it is free to spend the entire budget on one dense region, and the router
   demonstrably does something like this (min line coverage **0.000**: at least one
   text line loses *all* its ink). If that is the binding constraint, the fix is
   spatially-stratified selection (a per-row or per-tile budget), which is an
   architecture change and **not** something more training fixes. Cheap test
   proposed as Pending 1d.

**Status and limits.** The geometry above is stable — it is a property of the
masks, not of any accuracy measurement. What is provisional is the recall column
it is being compared against: **n=2**. The n=50 run is what decides whether the
random-beats-negated ordering is real; if it reverses, D2's explanandum
disappears and only the H2 falsification survives. The 4 cached images are also
not guaranteed to be the eval's first 4.

**Independent confirmation at n=4, with real accuracy and coverage measured on the
same images** (`results/ablation_selection_local.json`, local CPU, run-5 weights,
`keep_ratio=0.5`). This is a stronger test than the table above: D2's original
coverage numbers came from D1's cached npz, whereas `mean min line coverage` here is
computed per image inside the eval loop that produced the recall column.

| mode | retained ink | mean min line cov | word recall (n=4) |
|---|---|---|---|
| keep=1.00 router (CONTROL) | 1.000 | 1.000 | 83.67 |
| keep=0.50 router | 0.381 | 0.029 | 30.19 |
| keep=0.50 NEGATED | 0.619 | 0.133 | 56.22 |
| keep=0.50 random | 0.501 | 0.297 | **70.61** |
| keep=0.50 ink ORACLE | 1.000 | 1.000 | 83.66 |

The split holds and sharpens: **retained ink mis-orders** (negated 0.619 > random
0.501, yet negated loses by 14.4 pts), while **min line coverage reproduces the recall
order exactly** across all four pruned/unpruned rows. The oracle at 0.500 keep-ratio
retains ink 1.000 because every inked patch fits inside half the page — which is
itself the cleanest statement of why the droppability premise holds.

**Caveat on this table**: `meta.control_drift_pts = 8.89`, i.e. the local harness does
**not** reproduce run 6's absolute numbers (local transformers 5.4.0 vs Kaggle 4.x,
and n=4 vs n=50). Rows are comparable **to each other and to their own control**, not
to run 6. Phase 2d's n=50 GPU run is what closes this.

## Diagnostic D3 (2026-08-31, local, <1 s) — the runs answered three open questions and nobody read the answers

`scripts/diagnose_selection_statistics.py`, pure numpy over
`run 7/ablation_selection.json` and `run 8/ablation_selection.json`. No model,
no GPU. Re-runnable after any future sweep.

**Why it was booked.** Phase 2d's cell prints five verdicts per run, each with its
falsifying branch written *before* the run. Runs 7 and 8 both executed it. Only the
verdicts agreeing with the existing narrative reached this file — and one of the
unrecorded ones was Q3, the test built specifically so that D2 *could* fail. D2's
conclusion meanwhile stayed enshrined in Conventions, in Gotchas, in Pending 1b, and
in a saved cross-session memory. Every session since has inherited it.

### Q3 — is worst-case coverage really the better predictor? No.

Verbatim from run 8's executed notebook (`run 8/pruned_ocr_results.zip`):

```
Q3. Which statistic predicts per-image recall? (all pruned rows, n=700)
  retained_ink           aggregate                  0.699
  mean_line_cov          aggregate                  0.715
  p10_line_cov           worst-case                 0.677
  min_line_cov           worst-case                 0.612
  => D2 FALSIFIED per-image: summed ink is the better predictor after all.
     D2 was a 4-row coincidence; revise it and re-check 1a/1d.
```

Run 7 printed **INCONCLUSIVE** (0.571 / 0.600 / 0.596 / 0.565). So D2 was never
confirmed at n=50 and was once explicitly falsified.

**One honest complication, because it changes the strength of the claim.** The
harness compares `retained_ink` against `min_line_cov` specifically. Compare
*family bests* instead (`mean_line_cov` 0.713 vs `p10_line_cov` 0.677) and the gap
falls to 0.036, below the ±0.05 band, so D3's own criterion returns **INCONCLUSIVE for
both runs**. The verdict is sensitive to which member of each family you pick.

That does not rescue D2 — it dismantles it differently and more completely. D2's claim
was never "min coverage wins by a lot"; it was that **every** worst-case statistic
reproduces the recall order and **every** aggregate one mis-orders it, a *family-level*
split, which was explicitly the only reason it was reportable off 4 points. At n=50
there is no family-level split: all four statistics land within ~0.10 of each other and
which family "wins" depends on the member chosen. The clean dichotomy was an artifact
of n=4.

**And min line coverage specifically must be withdrawn as the acceptance gate**, on two
independent grounds:

1. It is the **weakest** of the four predictors in both runs, and worse than `p10` —
   its own family's other member — every time. Even inside D2's framework it was the
   wrong choice of statistic.
2. **A single pair retires it.** Run 8, keep=0.35: `router` min cov 0.127 → **77.80**
   recall; `random` min cov 0.137 → **48.37** recall. Equal worst-case coverage,
   **29.42 pts** apart. (Run 7 has the same shape at keep=0.50: `router` 0.003/18.80
   vs `stratified` 0.016/26.82, 8.03 pts.) A gate that scores a 77.80 row and a 48.37
   row identically is not a gate, whatever its correlation.

Within-mode correlations (the harder test, removing between-mode contrast) are weak for
both families — run 8: `router` ink 0.023 / min-cov 0.038; `ink` 0.013 / 0.123;
`stratified` 0.031 / −0.025. **No cheap statistic on file predicts per-image recall
well.** The pooled ρ≈0.7 is carried almost entirely by the catastrophically-broken
modes being bad on every axis at once; it is a between-mode effect wearing a
per-image disguise.

### EFF — does pruning buy wall-clock? Barely.

| run | −25% tokens | −50% tokens | −65% tokens | latency saved per token saved |
|---|---|---|---|---|
| 7 | −4.9% ms | −8.3% ms | −10.8% ms | **0.18×** |
| 8 | −10.6% ms | −6.2% ms | −7.1% ms | **0.22×** |

Both runs agree at ~0.2× proportional. The mechanism is architectural: the router runs
**after** the frozen Swin encoder, so all 4800 tokens are computed at every
`keep_ratio` and the only saving is decoder cross-attention KV length — which is not
what dominates a ~256-token autoregressive decode. Latency in run 8 tracks generated
tokens (r=+0.961) far better than visual tokens (r=+0.404); in run 7 generation length
was near-constant across rows so that contrast collapses, which is why the
**0.18–0.22× ratio, not the correlation, is the number to quote.**

The harness's Q5 verdict prints *"read the tok column for the actual encoder-side
saving."* **That note is wrong** and should be fixed in the cell: there is no
encoder-side saving. Pruning is post-encoder by construction.

### ADA — is "beats the oracle" a selection result? Probably not.

See the run 8 section: at the trained keep_ratio the ink oracle dominates the router on
both proxies and loses by 5.38 pts, `stratified` uses the same scores with better
coverage and loses by 4.42, and the router's curve peaks exactly on the trained ratio.
Leading hypothesis is decoder co-adaptation; falsifier stated there; untested.

### What D3 is really about

Three questions the project had already paid GPU time to answer sat unread in
`.json` and `.zip` files for one and two days. The harness did its job — falsifiable
verdicts, printed, with the falsifying branch pre-written. **The failure was purely
in transcription**, and it is more expensive than a failed run, because a falsified
claim left standing in this file gets *acted on*: the min-coverage gate had already
propagated into Conventions, Gotchas, Pending 1b and a cross-session memory before it
was checked. New convention below: transcribe the verdict, especially when it
disagrees.


## Diagnostic D4 (2026-08-31, local, <1 s) — the ink-BCE loss is fed a probability where it expects a logit — **FIXED 2026-08-31, see Fix F1**

`scripts/diagnose_saliency_loss.py`. Found while verifying a *different* claim (D3's
"runs 7→8 moved two knobs at once"), which is the usual way: the check that pays for
itself is rarely the one you booked. **Everything below describes the code as it stood in
runs 7–8**, which is what produced those runs' numbers; the script itself now detects the
fix and exits early rather than restating the defect as current.

**The defect.** `kaggle_pruning_run.ipynb` cell 11 computes the saliency term as

```python
_sal = F.binary_cross_entropy_with_logits(_sc.squeeze(-1), _tgt)
```

where `_sc` is `outputs['scores']` — and `PatchSaliencyRouter.scorer` **ends in
`nn.Sigmoid()`** (`src/router.py:25`, byte-identical in the notebook's own cell 4). So an
already-squashed probability in (0, 1) is passed to a function whose first act is to
squash it again. **A double sigmoid.** The diagnostic reads both halves out of the
notebook rather than quoting them, so it goes stale loudly if the loss is fixed.

**Why it survived five epochs and a successful run.** Sigmoid is monotone, so the
gradient *sign* is correct and the ranking is still learnable. Run 8's sign-fix is real —
`negated` collapsing 73.09 → 2.70 on the same weights cannot happen by accident. The
defect is in **magnitude and calibration**, and it is worst exactly where a BCE is
supposed to be strongest.

| what | measured |
| --- | --- |
| attainable predicted probability | **[0.500, 0.731]** — the model cannot express "blank" below 0.5 at all |
| loss floor, text patch | **0.3133** (a correct BCE reaches ~0) |
| loss floor, blank patch | **0.6931** |
| gradient attenuation, confidently wrong (z = −4) | **112×** too small |
| gradient attenuation, already correct (z = +4) | **3.7×** too small |

**The last two rows are the finding.** The attenuation is not a constant factor that
`LAMBDA_SAL` could absorb — it *grows as the prediction gets more wrong*, from 3.7× on
tokens the scorer already has right to 112× on a text patch it confidently calls blank.
A cross-entropy exists precisely to punish confident mistakes hardest; the extra sigmoid
saturates it into near-silence on exactly those tokens. `LAMBDA_SAL = 2.0` is the visible
symptom: it is large because it was tuned against an attenuated gradient.

**The target, by contrast, is sound** — checked on real FUNSD pages via D1's cached
`visualizations/router_scores.npz`, not a fixture. `_tgt = (ink / ink.max() > 0.15)` is
**37.1%** positive, and moves only **0.037** across `T ∈ [0.05, 0.30]`, because patch ink
is bimodal (a patch is blank or it has glyphs). So `SALIENCY_THRESHOLD` is **not a knob
worth sweeping** — a small negative result that saves someone a sweep.

**What this means for run 8, stated carefully.** Not "run 8 was invalid" — the opposite.
The sign-fix worked *through* a mis-specified loss rather than because of a well-specified
one, so **run 8's numbers are a floor on what ink supervision can do**, and there is
unclaimed headroom above the current best. ~~The fix is one line, preferably returning the
pre-sigmoid logit from the scorer and keeping the fused
`binary_cross_entropy_with_logits` (numerically stable, correct scale). Removing the
sigmoid from the ranking path changes nothing: **top-k is invariant under a monotone
transform of the score.**~~ **The recommended fix was wrong — see D5.** The claim about
top-k invariance is true but irrelevant: the ranking path is not the only consumer of
`scores`, and two others require a probability. Use D5's corrected fix. Re-tune
`LAMBDA_SAL` afterwards — it will be far too big. Pending item 9.

**Why nothing caught this.** ~~There is no verifier for cell 11.~~ **There was none until
2026-08-31; `verify_saliency_loss_cell.py` now covers it (F1).**
`verify_selection_ablation.py`
covers cells 4/7/15 — the selection mechanism — and the cell-hash diff above shows those
transferred byte-identically to the derived notebook. The training path is the *only*
part of runs 7–8 that was new, and it is the only part with no execution check. That is
not a coincidence to note in passing; it is the pattern: **the unverified cell is where
the bug was.** And when the check was finally written it failed **three** of six
assertions, covering **two** distinct defects — the double sigmoid (A, C) and the
undeclared `lambda_entropy` (D). The cell nobody checked had accumulated more than the one
bug that prompted the checking.

---

## Diagnostic D5 (2026-08-31, local, <1 s) — D4's own recommended fix would have broken two other loss terms

`scripts/diagnose_saliency_loss_coupling.py`. Booked while answering "what should we do
next?", where the answer was "item 9, it's one line." Checking that before recommending it
showed the fix was unsafe. **D4 diagnosed correctly and prescribed wrongly**, which is
worth as much shelf space as the original finding — the prescription is the part that
would have been executed. **Weights and tables below are run 8's** (`LAMBDA_SAL=2.0`,
`lambda_entropy` defaulted); F1 changed both, and the script now prints its frozen run-8
constants beside the live values it reads from the notebook so the two cannot be confused.
**D5's own prescription was superseded too** — it recommended plain
`F.binary_cross_entropy`, which is autocast-unsafe; see F1 for what shipped.

**`scores` has three consumers, not one.** D4 proposed changing the scorer to return the
pre-sigmoid logit. `AdaptivePruningLoss` (`src/loss.py`) reads the same tensor twice, and
both readings require a probability:

| consumer | code | assumes | weight in run 8 |
| --- | --- | --- | --- |
| sparsity | `smooth_l1(scores.mean(), target_budget)` | mean is a **fraction** vs `target_budget` ∈ (0,1] | `lambda_sparsity=0.0` — inert |
| entropy | `scores.clamp(1e-7, 1-1e-7)` → binary H | `scores` ∈ (0,1) | **0.05 — defaulted, never chosen** |
| ink-BCE | `bce_with_logits(scores, tgt)` | a **logit** (this is D4's bug) | `LAMBDA_SAL=2.0` |
| STE | `1 + (s − s.detach())` | nothing — value is exactly 1.0 either way | n/a |

Neither `loss.py` term would crash on a logit, which is the whole problem. Measured:
switching to logits drops the entropy term's `H` from **0.403 → 0.135** and attenuates its
max gradient **12×** — and worse than the attenuation, `clamp()` only passes gradient for
in-range inputs, so the term would go on regularizing **only the tokens whose logit
happens to land inside (0,1)**: an arbitrary slice unrelated to saliency. A regularizer
quietly retargeted at a meaningless subset, with no error and no crash. Same failure
class as D4 itself.

**The corrected fix — do this instead.** Keep the scorer's sigmoid; change only the loss
call in cell 11:

```python
_sal = F.binary_cross_entropy(_sc.squeeze(-1).clamp(1e-6, 1 - 1e-6), _tgt)
```

One line, one file, no other consumer touched. It gives up the fused version's
log-sum-exp stability, which the `clamp` covers at this scale. The alternative — return
both the logit (for the BCE) and the probability (for sparsity/entropy/STE) — is a
signature change across three copies of `PatchSaliencyRouter` plus every call site, for
a stability margin nothing has needed. Not worth it now.

**And a second finding that is arguably the more useful one: `lambda_entropy = 0.05` was
never chosen.** Cell 11 never passes it, so it inherits `src/loss.py`'s default in *both*
branches. Two terms shaped run 8's scores — ink-BCE at 2.0 and entropy at 0.05 — and only
the first was deliberate. The entropy term is `-H`, so minimizing total loss **maximizes**
entropy, i.e. it actively pushes every score back toward p=0.5 — the exact opposite of
what the ink-BCE wants. Nobody wrote that down as a design decision because nobody wrote
it down at all.

Is it big enough to matter? **Measured, and no — today.** Entropy is **1.0–42.4%** of the
BCE gradient across the score range the scorer actually occupies. So the COMPETE
hypothesis is falsified as a present-tense cause of anything, as predicted before
measuring. **But it becomes live at the moment of the D4 fix**, because the entropy weight
is fixed while `LAMBDA_SAL` must fall:

| `LAMBDA_SAL` | entropy share of the saliency gradient (max) |
| --- | --- |
| 2.0 (run 8) | 42% |
| 1.0 | 85% |
| 0.5 | 170% — entropy now dominates |
| 0.1 | 848% |

So `lambda_entropy` must be passed **explicitly** in the same run that fixes D4, or the
re-tuned `LAMBDA_SAL` will be tuned against a regularizer that silently grew to outweigh
it. This is the runs-7→8 two-knob mistake about to repeat itself through a *default*
rather than an edit, which is harder to see.

**A refinement of D4, from the cached real-page scores.** D4 argued from the range of
`sigmoid(p)`. The scorer's own output on 4 real FUNSD pages spans **[0.010, 0.990]**
(p1 0.032, median 0.459, p99 0.921) — it is **fully expressive**. So the defect is not
"the scorer cannot express confidence." It is sharper: the scorer *can* output 0.99, the
loss reads that as `sigmoid(0.99) = 0.729`, and a BCE at 0.729 against target 1 is never
satisfied. **The loss is structurally unsatisfiable** — no output the scorer can produce
drives it to ~0, so every token keeps receiving a push forever and the loss can never say
"this one is done." That is a better statement of the bug than D4's, and it came from
measuring the thing D4 had only reasoned about.

**The reusable lesson:** D4 called its fix "one line." That was a claim about the size of
the diff, not about the blast radius. Before changing the **units or range** of a value,
enumerate every reader of it — `grep` for the field, don't reason from the one call site
you happen to be looking at.


## Fix F1 (2026-08-31) — Pending 9 + 10 DONE: the loss is fixed in the *generator*, and cell 11 finally has a verifier

Pending 10 (write the check) was done **before** Pending 9 (apply the fix), on purpose, so
the check had to earn its keep by failing. It did: **3/6 on the unfixed code, failing
exactly the three assertions D4 and D5 predicted**, then 6/6 after the fix. Everything
below is measured output from `scripts/verify_saliency_loss_cell.py`, not a description of
intent.

**`scripts/verify_saliency_loss_cell.py` — 6/6 PASS, exit 0, <2 s, no GPU.** It does not
paraphrase the loss: it locates the block between `_sc = outputs['scores']` and the
`loss = loss +` that consumes it, `ast.parse`-checks it, and **`exec`s it** with a stubbed
`patch_ink` chosen so the block's own `_tgt = (_inkn > SALIENCY_THRESHOLD)` comes out as
the requested target (asserted, so the stub cannot silently bypass the target
construction). A paraphrase would verify the verifier instead of the thing that runs on
Kaggle. It raises rather than skips if the block's shape changes, so it goes stale loudly.

| assertion | unfixed | fixed | what it pins |
| --- | --- | --- | --- |
| **A SOLVED** | 0.5032 ❌ | **0.0000** ✅ | matched scores must drive `_sal` to ~0 (< 0.05). A loss that cannot be satisfied can never say "this token is done" — D5's structural-unsatisfiability finding, as an assertion. |
| **B ORDERED** | 1.0032 > 0.5032 ✅ | **13.8089 > 0.0000** ✅ | inverted must cost more than matched. **Passes even with the bug** — sigmoid is monotone, which is exactly why run 8's sign-fix worked at all. Kept as a regression guard, and as a standing reminder that this is the assertion a lazy check would have stopped at. |
| **C PROPORTIONAL** | spread **50.0×** ❌ | **1.0000 at every score (spread 1.0×)** ✅ | `\|d_sal/dz\| / \|p−t\|`, z = pre-sigmoid activation. For a correctly specified BCE this identity is **exactly 1.0**, so this is a closed-form target, not a tolerance. This is the assertion that catches D4. |
| **D EXPLICIT** | `lambda_entropy` defaulted ❌ | **3 sites, all `lambda_*` explicit, cross-copy defaults agree** ✅ | D5's undeclared-knob finding. Reads the parameter names from the notebook's **own** cell-5 copy of `AdaptivePruningLoss` (the notebook imports nothing from `src/`) and asserts all three copies' defaults still match. |
| **E RANGE** | ✅ | **scores ∈ (0.4955, 0.7644) ⊂ (0,1)** ✅ | the contract that makes D4's *original* fix fail loudly instead of silently: `scores` must stay a probability because `loss.py` reads it as one twice. Passed before and after — its job is to fail on a *future* edit. |
| **F PARITY** | ✅ | ✅ | the notebook's `_sal` line must equal the generator's, or the next regeneration reverts the fix. |

**The applied fix**, in `scripts/make_kaggle_pruning_notebook.py`:

```python
_sal = F.binary_cross_entropy_with_logits(
    torch.logit(_sc.squeeze(-1).clamp(1e-6, 1 - 1e-6)), _tgt)
```

**This is not the form D5 prescribed**, and the reason is worth keeping. D5 said use plain
`F.binary_cross_entropy(p, t)`. That is correct in value — both give 1.956011 where the
as-written version gives 0.919646 — but plain `binary_cross_entropy` is on PyTorch's
**autocast-unsafe list**, and this block runs inside `torch.amp.autocast` on the T4.
Recovering the logit and handing it to the fused op satisfies all four constraints at once:
identical value, `d/dz == p − t` exactly, log-sum-exp stability retained, and the blast
radius stays inside cell 11 — the scorer keeps its sigmoid, so all three probability
consumers are untouched. *Honest caveat:* the autocast restriction is documented but I
**could not reproduce it locally** — plain `F.binary_cross_entropy` did not raise under CPU
autocast, which uses bfloat16. The `torch.logit` form was chosen so the CUDA fp16 question
never has to be answered.

**Two knobs, both now explicit, and one of them is a genuine second change:**

- `LAMBDA_SAL` **2.0 → 0.5**. 2.0 was tuned against a gradient the bug attenuated 10–50×.
  **Reasoned, NOT tuned** — there is no run behind 0.5.
- `lambda_entropy` **explicit at every site: 0.0 supervised, 0.05 unsupervised.** 0.0 is
  deliberate: the term is `-H`, so minimizing it *maximizes* entropy and pushes every
  score back toward 0.5. Its stated job ("prevent early bimodal collapse") is a stand-in
  for supervision, so once an ink target tells each token what it should be, the term works
  directly against that target — and after the fix the BCE gradient **vanishes** at `p == t`
  while the entropy gradient does not, which would make entropy the *binding constraint at
  convergence* and hold scores off 0/1 permanently. D5's table says it would carry ~170% of
  the saliency gradient at `LAMBDA_SAL=0.5`.
- **So run 9 moves two knobs, exactly what runs 7→8 were criticized for in D3.** The
  difference is that this time it is written down in advance with a reason. **If run 9
  disappoints, revert `lambda_entropy` to 0.05 first** — it is the change with an argument
  behind it rather than a measurement.

**The fix went into the generator, not the notebook** — see the new Gotcha. Editing
`kaggle_pruning_run.ipynb` alone would have been reverted by the next regeneration, and F
PARITY exists to catch precisely that. One additional edit went to the **canonical**
`kaggle_token_pruning_ocr.ipynb` cell 11, which supplies the generated notebook's `else`
branch: `lambda_entropy=0.05` passed explicitly. That one is **behaviour-preserving** — it
passes the same value the signature already defaulted to — and was applied with an asserted
`count(old) == 1` plus `ast.parse` before writing. Its only purpose is that a reader of the
notebook can now see the knob.

**Checked for defaults drift across the three copies of `AdaptivePruningLoss`** (`src/loss.py`,
canonical notebook cell 5, generated notebook cell 5): **identical**, so Kaggle rows remain
comparable to local ones. Assertion D now fails if that ever stops being true.

**Regression, all execution-verified after the fix:** **9/9 `verify_*.py` OK** (including
`verify_selection_ablation.py` 44/44, which reads the canonical notebook I edited),
**6/6 no-GPU diagnostics OK**, and **5/5 `tests/` OK** (`test_amp_gradscaler`,
`test_end_to_end`, `test_model_pipeline`, `test_modules`, `test_tome_correctness` — run as
plain scripts; pytest is not installed, see Gotchas).

**What this does NOT establish.** No GPU ran. The fix is verified at the level of *value,
gradient, and range*; its effect on recall/NED/word-order is **unmeasured**, and D4's claim
that run 8's numbers are a floor is still a prediction. `LAMBDA_SAL=0.5` is a guess.
**Run 9 is what tests this**, and per Pending 4 it needs the control row — **which F2 has
now built (see the next section), so run 9 is no longer blocked on it.**

**D4's staleness guard was itself broken, and this is the more general finding.** D4 was
written to go stale loudly, via `uses_logits = "binary_cross_entropy_with_logits" in loss_src`.
The applied fix **keeps that string** (it wraps the argument), so the guard did not trip and
D4 went on printing `=> a probability in (0,1) is passed where a logit is expected` against
fixed code — a false positive introduced *by the fix*. Now corrected to test the condition
(`is the argument wrapped in torch.logit(`?) rather than grep for a symptom, and to exit 0
with a `SUPERSEDED` banner pointing at the verifier that now owns the invariant. The new
detector was itself falsification-tested against four variants — the run-7/8 line, the
shipped two-line fix, a single-line `torch.logit` form, and plain `bce` — and reports
"broken" only for the first. D5 was updated the same way: its run-8 weights are now frozen
as `RUN8_*` constants with the live values read from the notebook beside them, since it had
been asserting "cell 11 never passes `lambda_entropy`" (no longer true) and recommending a
fix that was not the one applied. **General form: a staleness guard that greps for the
*symptom* of a bug will not trip when the bug is fixed by any rewrite that preserves the
symptom's surface form. Assert the condition.**


## Fix F2 (2026-08-31) — Pending 4 DONE in code: cell 15 gets a control that holds the *weights* fixed

**The defect was a two-variable test wearing a control's name.** A control re-runs a known
setting and must reproduce a known number. Cell 15's row 0 (`keep=1.00 router CONTROL`) did
that in run 6. Runs 7–8 retrained the router *before* row 0 ran, so the row began varying
two things at once — the harness and the checkpoint — and its drift (−10.93 run 7, +0.51
run 8) could not be attributed to either. The run-8 write-up read +0.51 as "the retrain
raised the ceiling"; that may well be true, but the row could not distinguish it from a
harness fault, which is precisely what a control exists to rule out.

**The fix: a second control that fixes the weights instead of the setting.** Before the
15-row sweep, load `RESUME_CKPT` — the run-5 weights that *produced* 77.74/64.70/53.05 —
eval one `keep=1.00` row through the identical `run_selection_eval`, compare to
`RUN6_REFERENCE`, restore the swept weights, sweep. Nothing varies vs run 6 in that row,
so its drift is measurement (harness, library version, sampling) and nothing else. Row 0's
drift is then the retrain's effect alone. The two together are what make a number
attributable:

| HARNESS CONTROL | row 0 | reading |
|---|---|---|
| matches run 6 | matches run 6 | the retrain did not move the unpruned ceiling |
| matches run 6 | drifts | **the retrain moved the ceiling** — quote rows against row 0 |
| drifts | either | measurement problem; the retrain's effect is unreadable either way |

`keep_ratio=1.0` prunes nothing, so the control row is also independent of every selection
code path under test — it cannot be rescued or broken by the thing it is there to validate.

**Three properties that separate this from a decorative control.**

1. **The load must be complete.** Cell 11 resumes with `strict=False`. A silent key
   mismatch would evaluate a partly-random model and report the resulting drift *as a
   control reading*. Both load sites now assert `missing == unexpected == []` and name the
   first three of each in the message.
2. **The restore must be proven, not assumed.** This is the failure the change itself
   introduces, and it is the worst one available: if restoring the retrained weights
   silently failed, all 15 rows would measure the *control* checkpoint and the table would
   look entirely ordinary — plausible latencies, plausible ordering, wrong weights, no
   symptom. A full-state-dict fingerprint is taken before the swap and asserted equal after
   it. Without this assert, adding a control makes the run **less** trustworthy, not more.
3. **A drifted *metric* warns; a broken *load* raises.** The distinction matters and the
   block draws it deliberately. If the control number misses `RUN6_REFERENCE`, the sweep
   continues: a harness offset invalidates *absolute* quotes but not row-to-row comparisons,
   and rows-to-each-other is what Q1/Q2/Q4 actually ask, so halting would spend a scarce
   Kaggle GPU session to learn that one column is unquotable. Instead: a 70-char `!` banner
   plus `harness_verified: false` in the results JSON at **both** write sites, so nobody can
   later read absolute numbers out of the file without the flag being right there. But a
   *structural* failure — missing/unexpected keys either direction, a no-op control load, a
   restore that lands on the wrong tensors — raises immediately, because there the model
   state itself is untrustworthy and every row after it would be fiction. Warning is for
   "this number is not comparable"; raising is for "I do not know what I just measured."
   To make metric drift fatal too, add `assert harness_verified` after the block —
   `verify_harness_control.py` asserts that string is currently absent, so flipping the
   policy trips the verifier and forces the decision to be re-recorded here.

**Why the fingerprint covers every parameter and not a sample.** The obvious cheap version
hashes the first, middle and last key of the sorted state dict. On this architecture those
land on frozen Swin encoder tensors, which training never touches — so a 3-key fingerprint
would compare *equal* across two genuinely different checkpoints and the restore assert
would pass vacuously. One `.sum()` per tensor is milliseconds on GPU and only needs
deterministic equality, not precision. Section 3 of the verifier proves the point
empirically: it mutates each individually-unsampled parameter in turn and asserts the
fingerprint moves every time (3 tested, 0 blind spots on the stub).

**Where the edit went, and why not the file that runs.** Cell 15 lives in the canonical
`kaggle_token_pruning_ocr.ipynb`; `scripts/make_kaggle_pruning_notebook.py` rewrites only
cells **2, 9, 11** and copies the rest byte-identically, so a hand-edit to
`kaggle_pruning_run.ipynb` would be reverted at the next regenerate. Applied via
`scripts/patch_notebook_harness_control.py` (5 anchors, each asserted to match exactly once,
`ast.parse` before write, idempotent). Confirmed after regeneration: cells differing =
`[2, 9, 11]`, and cell 15 of the run notebook is **string-equal** to the canonical one.

**Compatibility with the canonical notebook, which has no `DO_TRAIN`.** `DO_TRAIN`,
`PRUNED_CKPT` and `EVAL_CKPT` exist only in the *generated* notebook. The block reads all
three through `globals().get(...)`, and when `DO_TRAIN` is false it **skips** — correctly,
because `model` then still holds the run-5 weights, so row 0 *already is* the harness
control. The skip is not silent: it writes its reason into `harness_note`, which reaches the
JSON. Note also that cell 15 has no `import torch` of its own and uses cell 2's ambient one
(`torch.manual_seed`, `torch.no_grad`); the block follows that convention rather than adding
an import, since the cell cannot run standalone anyway — `model` also comes from earlier.
My first patch attempt asserted `import torch` in cell 15 and failed; the precondition was
wrong, not the notebook.

**Verification — `scripts/verify_harness_control.py`, 33 checks, written before the fix and
observed to fail on it (`0 passed, 1 failed`).** 12 static, 18 execution, 3 fingerprint. The
execution half is the part that matters: a grep cannot tell you whether a weight swap is
safe, so the script extracts the block's source text out of the notebook JSON and `exec`s it
against a stub `nn.Module` with a faked `torch.load`, under seven scenarios — and it runs
against **both** notebooks (33/33 each; pass a path as `argv[1]`).

| scenario | required behaviour | observed |
|---|---|---|
| control reproduces run 6 | `harness_verified=True`, weights byte-equal to pre-swap | PASS, loads `[run5, pruned]` in that order |
| control drifts 3.70 pts | warn, `False`, **and still restore** | PASS |
| drift 0.39 / 0.56 pts | tolerance boundary at 0.5 both ways | PASS |
| control ckpt missing a key | raise, message says `missing` | PASS |
| control ckpt has an extra key | raise, message says `unexpected` | PASS |
| control ckpt == swept weights | raise `changed nothing` (not a control) | PASS |
| restore loads wrong values | raise `FAILED TO RESTORE` | PASS |
| restore missing a key | raise `restore checkpoint does not match` | PASS |
| `DO_TRAIN=False` | skip, `None`, **zero** checkpoint reads | PASS |
| checkpoint absent from disk | skip with the reason in `harness_note` | PASS |

Two ordering facts are asserted statically because they are invisible at runtime until they
bite: the restore happens **before** the drift report (so a restore failure cannot be
mistaken for a reporting failure, and the assert fires while its cause is still on screen),
and the control row is **not** appended to `rows`. That second one is a real trap —
`by = {(r['keep_ratio'], r['select_mode']): r for r in rows}` is keyed on
`(1.00, 'router')`, which row 0 already owns, so appending the control would silently
overwrite the actual control in every downstream Q1–Q5 lookup.

**Regression after F2**: 10/10 verifiers (including `verify_selection_ablation.py`'s 44
checks, untouched by the cell-15 edit), 6/6 diagnostics, `check_agents_md_format.py` clean,
5/5 `tests/`.

**What this does NOT establish.** No GPU ran. Whether run-5 weights *do* reproduce
77.74/64.70/53.05 through today's transformers version is exactly the open question, and F2
only makes it askable — a failing harness control on run 9 would be a genuine finding, not a
bug in F2. The 0.5-pt tolerance is inherited from the existing row-0 check and has never
been justified against measured run-to-run variance; nothing has measured that variance, so
treat the threshold as a convention, not a calibrated gate.

### F2 requires `RESUME_CKPT` to be set, and skips silently if it is not

Found while writing the run-9 launch steps, by tracing the flags across cells rather than
trusting the block in isolation. **Cell 2 ships `RESUME_CKPT = None`.** With that value
`_ctrl_ckpt` is `None`, so the block takes its "checkpoint not found" branch and the sweep
proceeds with no harness control at all — printing one skip line in a log that already has
hundreds. The fix I wrote would have been *present and inert* on the very run it was built
for. Setting `RESUME_CKPT` is therefore not an optional convenience, it is step 1 of run 9.

The cross-cell contract is now asserted by `verify_harness_control.py` section 4 (39/39 on
the generated notebook, 36/36 on the canonical one), because it spans three cells and no
single-cell check can see it:

| what | where | why it matters |
|---|---|---|
| `RESUME_CKPT = None` shipped | cell 2 | must be set at launch or F2 is inert |
| `EVAL_ONLY = bool(RESUME_CKPT)` | cell 2 | setting the path flips `EVAL_ONLY` as a side effect |
| skip guard is `EVAL_ONLY and not DO_TRAIN` | cell 6 | so setting the path does **not** starve a `DO_TRAIN` run of training data — this was the near-miss |
| `if RESUME_CKPT and os.path.exists(…)` → resume | cell 7 | runs 7–8 trained *from run-5 weights*; run 9 is only comparable if this fires |
| `torch.save(PRUNED_CKPT)` then `EVAL_CKPT = PRUNED_CKPT` | cell 7 | the block restores the **retrained** weights, not the control ones |

**Generalises past this fix:** a block that reads its configuration from `globals()` cannot
fail loudly when that configuration is absent — `globals().get(...)` is what *makes* it
skip-safe on the canonical notebook, and the same property makes it silently inert on the
run notebook. Skip-safe and fail-loud are in tension; when you choose skip-safe, the
launch procedure becomes load-bearing and belongs in this file, not in someone's memory.


## Fix F3 (2026-09-01) — Pending 11 DONE: the training log can now tell `LAMBDA_SAL=0.5` from `LAMBDA_SAL=0`

**The defect.** Run 9's five epoch lines read `Avg Loss 0.3091 | CE 0.3091`, identical to 4
decimal places, and there was no way to tell from the log whether the saliency term had run
at all. Two independent causes, both in the reporting rather than the maths:

1. `epoch_loss += loss_dict['loss'].item()` accumulates the **criterion's** output, while
   `LAMBDA_SAL * _sal` is added to the separate local `loss` that reaches `backward()`. The
   saliency term therefore reached the optimiser and **no printed number**.
2. In the supervised branch `lambda_sparsity = lambda_entropy = 0.0`, so
   `loss_dict['loss'] == loss_dict['ce_loss']` **by construction**. The two columns were
   guaranteed to agree regardless of anything the router did.

So the one quantity F1 exists to move had never been observed in any run — its behaviour was
only ever inferred from downstream metrics, which D6 then showed move in the *opposite*
direction from the mechanism. That is the worst possible configuration for a proxy objective.

**Test first, and it failed for the right reason.** `scripts/verify_training_telemetry.py`
was written before the patch and run against the unpatched notebook: **1/6**, with
`I DISCRIMINATING` reporting the defect in its own words —

```
LAMBDA_SAL=0.5 -> Epoch 1 | Avg Loss 2.6054 | CE 2.6054
LAMBDA_SAL=0.0 -> Epoch 1 | Avg Loss 2.6054 | CE 2.6054
[FAIL] I DISCRIMINATING: IDENTICAL lines at LAMBDA_SAL=0.5 and 0.0
```

The one pre-patch pass was `K GRAD INTACT` — the term *did* reach `backward()` all along
(scorer |grad| 0.109 at λ=0.5, exactly 0 at λ=0). That is the assertion that matters most
after the patch, because "make the number visible" is the kind of change that gets
implemented with a `.detach()` in the wrong place and silently switches the term off.

**The new line.** One per epoch, from the generator's `DO_TRAIN` branch:

```
Epoch 1 | Obj 2.7395 | CE 2.6054 | aux 0.0000 | sal 0.2681 x0.5 [3/3] | dev 0.2186 | p 0.515+-0.342
Epoch 1 | Obj 2.6054 | CE 2.6054 | aux 0.0000 | sal OFF (LAMBDA_SAL=0)
```

Every column is there because a specific past failure in this project was invisible without
it. This is the point of the fix — not "more logging", but *these* numbers:

| column | is | the failure it would have caught |
|---|---|---|
| `Obj` | `(epoch_loss + LAMBDA_SAL*epoch_sal)/n` | Pending 11 itself: no printed number equalled what `backward()` minimises |
| `CE` | unchanged | — |
| `aux` | `(epoch_loss − epoch_ce)/n` | D5: `lambda_entropy=0.05` defaulted in and shaped runs 7–8 while appearing in no config cell. Nonzero `aux` says so the epoch it happens |
| `sal` | mean ink-BCE, printed **with λ and the step count** | Pending 11 core. The knob and the fact that the branch fired are both in the log, so `sal OFF` and "λ set but branch skipped" (`[0/n]`) are distinguishable |
| `dev` | mean \|p − t\| | after D4's fix `d(sal)/dz == p − t` exactly, so this **is** the gradient magnitude. Separates "loss is low" from "router agrees with the target" |
| `p` | mean ± std of the scores | std → 0 is constant-collapse, which makes `torch.topk` return the first K indices — a structured-looking selection that is not learned at all, and completely silent. Mean drifting to 0.5 is D5's entropy concern |

**Result: 6/6, and the whole suite is green.** 11/11 `verify_*.py` exit 0, 5/5 `tests/*.py`
exit 0, `check_agents_md_format.py` clean.

| assertion | what it pins |
|---|---|
| `G LOGGED` | the reported `sal` equals an independently computed BCE on the same scores and target (0.2681 vs 0.2681) |
| `H IDENTITY` | `Obj == CE + aux + λ·sal`, run with `lambda_entropy=0.05` so `aux ≠ 0` and the identity cannot be satisfied trivially |
| `I DISCRIMINATING` | λ=0.5 and λ=0 print **different** lines — the property whose absence made run 9's log uninterpretable |
| `J LIVE` | inverting the ink target moves `sal` by the independently computed +1.5625 — not a constant, not the wrong tensor |
| `K GRAD INTACT` | the telemetry did not detach the term out of the graph |
| `L PARITY` | 14 telemetry lines identical in notebook and generator, so the next regeneration cannot revert them |

The verifier **extracts the epoch loop out of `kaggle_pruning_run.ipynb` cell 11 and executes
it** against a real `AdaptivePruningLoss`, a real `torch.amp.GradScaler`, and a real AdamW
subclass that snapshots the scorer gradient before the loop zeroes it. Nothing is paraphrased
— a paraphrase would verify the verifier. `lr=0.0` keeps the scores fixed across steps so the
expected `sal` is computable in closed form.

**Patched in the generator only.** Cell 11's `if DO_TRAIN:` branch is *created* by
`scripts/make_kaggle_pruning_notebook.py`; the canonical notebook has no such branch and is
untouched. A hand-edit of `kaggle_pruning_run.ipynb` would be reverted by the next
regeneration, which is what `L PARITY` exists to catch. Regeneration is idempotent (md5
unchanged on a second run).

**The untouched `else` branch is not a gap.** Cell 11 of the generated notebook ends with the
original cell wrapped as `else:`, and that loop still prints the old
`Epoch n Complete | Avg Loss: … | Avg CE: …`. It is deliberately left alone: the canonical
notebook's training loop has **no saliency term at all** — 0 references to `LAMBDA_SAL`,
`_sal` or `patch_ink` — so there is nothing there for F3 to log. Two consequences: F3's scope
covers every code path that *has* a saliency term, and the "identical by construction" trap
does not apply to that branch either, since its criterion is
`lambda_sparsity=0.0, lambda_entropy=0.05` and `aux` is therefore nonzero (and negative, per
below). Worth noting that this is the configuration run 5's base checkpoint was trained
under, so the only pressure on its router scores besides task CE was "move toward 0.5" — that
flattens, it cannot invert, so it is *not* a candidate explanation for D1.

### `L PARITY` needed narrowing — cell 11 contains *two* epoch loops

First version of the assertion regex-matched telemetry lines across the whole of cell 11 and
reported a divergence that did not exist (4 notebook lines vs 2 generator lines). Cause: the
generator wraps the original cell-11 body as the `else` branch, so **cell 11 holds two
complete training loops** — the `DO_TRAIN` one and the original, each with its own `pbar` and
its own epoch print. The generator source contains only the first. The fix is to extract both
sides *the same way* (`extract_epoch_loop`, which takes the first match) rather than to
loosen the comparison until it passes. Recorded because the instinct when a parity check
fires is to assume the files diverged, and here the checker was wrong.

### Found while verifying: the entropy term is negative-definite and pushes scores toward 0.5

`H IDENTITY` prints `aux -0.0227` — **negative**. `src/loss.py:69` is
`entropy_loss = -entropy`, so the term enters the total as `lambda_entropy * (−entropy)`, and
binary entropy is ≥ 0. Measured directly with runs 7–8's `else`-branch config
(`lambda_sparsity=0.0, lambda_entropy=0.05`):

| score p | `entropy_loss` | `aux` | `d(loss)/dz` | score moves |
|---|---|---|---|---|
| 0.95 | −0.1985 | −0.00993 | +0.00087 | **down** |
| 0.80 | −0.5004 | −0.02502 | +0.00139 | **down** |
| 0.50 | −0.6931 | −0.03466 | 0.00000 | flat |
| 0.20 | −0.5004 | −0.02502 | −0.00139 | **up** |
| 0.05 | −0.1985 | −0.00993 | −0.00087 | **up** |

`entropy_loss ≤ 0` for every p tested. Two consequences worth having written down:

- **A negative `aux` in the new log is correct, not a bug.** Expect it whenever
  `lambda_entropy > 0` and the sparsity term is small. Do not "fix" it.
- The term applies a **directional pressure toward constant collapse** — the exact state the
  new `p ±std` column watches for — while *lowering* the printed loss. Runs 7–8 had it live
  and unmentioned (D5). Magnitude is small (|d/dz| ≈ 0.0014, against CE gradients orders
  larger) and `lambda_sparsity=2.0` was pulling on the same scores, so this is **not** a
  claim that runs 7–8 collapsed — only that the pressure existed, pointed at 0.5, and was
  invisible in both directions: absent from the config cells *and* loss-reducing in the log.
  Run 9's supervised branch sets `lambda_entropy=0.0`, so run 9 is unaffected.

**What F3 unblocks.** Pending 5's co-adaptation 2×2 and Pending 13(a) (drop the auxiliary
term entirely) both hinge on reading the saliency loss during training. Neither was runnable
before this; both are now.


## Run 9 — launch checklist (written 2026-08-31; **EXECUTED 2026-09-01, see "Run 9" above**)

Kept as written because the prediction at the bottom was recorded before the run and is now
falsified — the value of a pre-registered prediction is entirely in not editing it
afterwards. Every step below behaved as specified when run.

Run 9 carries **three unrun code changes at once**: F1 (the loss fix), F2 (the harness
control), and item 10's verifier. That is deliberate — F2 is precisely what makes F1's
numbers readable — but it means the run needs its configuration recorded *before* it starts.

1. **Kaggle → Add Input → the run-5 checkpoint dataset.** Copy the path it shows.
2. **Cell 2, line 48: set `RESUME_CKPT`** to that path
   (runs 7–8 used `/kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt`). If the path
   is slightly wrong the cell 2 resolver finds it by basename and prints where; if the
   dataset is unattached it raises there, one minute in rather than twenty.
   **Leaving this `None` costs the harness control and nothing will fail.**
3. **Leave the rest of cell 2 alone**: `DO_TRAIN=True`, `TRAIN_KEEP_RATIO=0.50`,
   `TRAIN_EPOCHS=5`, `SUPERVISE_SALIENCY=True`, `SALIENCY_THRESHOLD=0.15`, `ALLOW_CPU=False`.
   These match run 8, so the loss fix is the only training-side change.
4. **Session options → Accelerator → GPU.** `ALLOW_CPU=False` now asserts on this, so a
   CPU session dies in cell 2 instead of producing a plausible-but-wrong table over hours
   (that was the 2026-08-29 failure).
5. **Run All**, then read four checkpoints in the log — listed under "what to watch" below.
6. **Download `/kaggle/working/pruned_ocr_results.zip`**, and file it as `results_4/` (or
   `run 9/` — the existing names are inconsistent; pick one and fix the others).
   **Settled 2026-09-01: it was filed as `run 9/`, so `run <n>/` is the convention.**
   **DONE 2026-09-06 (Pending 12): the convention now holds everywhere.** `results_2/` →
   `run 7/`, `results_3/` → `run 8/`, and run 6's seven Kaggle artifacts were split out of
   `results/` into `run 6/`. `results/` survives as local-diagnostics-only — it was never a
   run directory, which is why the item's own instruction to rename it wholesale was wrong.

**What to watch, in order.** Each of these is a place a previous run went wrong silently:

| stage | expect | if wrong |
|---|---|---|
| cell 2 | `Using device: cuda`, `GPU: Tesla T4`, `EVAL-ONLY mode: will load …run5…`, `PLAN: DO_TRAIN=True` | no `cuda` line ⇒ the assert should have fired; if it did not, stop |
| cell 7 start | `Resumed /kaggle/input/… (missing=0, unexpected=0)` | nonzero counts mean run 9 is not starting where runs 7–8 did |
| cell 7 end | `SAVED pruning-ON checkpoint -> /kaggle/working/adaptive_donut_pruned.pt` | without this, cell 8c has nothing to restore and F2's assert fires |
| cell 8c early | `--- HARNESS CONTROL: run-5 weights through this harness` … `weights restored and fingerprint-verified` | a `skipped:` line here means step 2 was missed — **the whole point of run 9's readability is gone** |
| cell 8c | `HARNESS OK` or the `!!!` banner | either is a result; the banner means absolute numbers are unquotable, rows still are |
| cell 8c row 0 | `DIFFERENT CEILING` is the *expected* reading if the retrain worked | `OK` at row 0 plus `HARNESS OK` means the retrain did not move the ceiling |

**Cost.** Rough, from the pieces this repo has measured: ~19 min dataset download, ~4 h
training (5 epochs, the figure this file uses elsewhere — never precisely logged, so treat
it as an estimate), ~3 min cell 8 eval, ~13 min cell 8b decoding ablation, ~42 min cell 8c
(16 rows × 50 images × ~3.1 s). **≈ 5.3 h.** Cell 8b is the one droppable piece: the
decoding question was settled at run 6 and its own control is against `RUN5_REFERENCE`,
which a retrained checkpoint will fail by construction — skipping it saves ~13 min and
loses nothing run 9 is asking.

**The prediction to record before the run, so it can be wrong. — FALSIFIED 2026-09-01.**
~~F1 fixed a loss whose gradient was attenuated 3.7×–112× and floored at 0.313; the router
should therefore learn the ink target *better* than run 8 did, so `keep=0.50 router` should
land at or above run 8's 80.17 and the gap to the ink oracle should narrow.~~ Measured
**79.63, i.e. −0.54**, and the oracle gap narrowed only because the oracle *rose* 2.10.

The prediction was wrong in an instructive way: its first clause was right and its second
did not follow from it. The router *did* learn the ink target better — retained ink 0.790 →
0.922 — so the double sigmoid **was** a binding constraint on how well the router fits its
objective. What the prediction assumed without saying so is that fitting that objective
better makes the OCR better. D6 shows it does the opposite at and below the trained budget.
So D4's "run 8's numbers are a floor" claim is **falsified**: 80.17 was not a floor, it was
close to the best the ink objective can do at keep=0.50.

The stated next knobs (`LAMBDA_SAL` 2.0 → 0.5 first, `lambda_entropy` second) are now the
wrong response — tuning the weight on a target that is itself wrong moves along the wrong
axis. See Pending 5 and Pending 13. (Pending 11, the logging that made the mechanism readable
at all, is **DONE 2026-09-01 — F3**, which is what unblocks both of them.)


## Run 10 — launch checklist (written 2026-09-02; **EXECUTED 2026-09-03, see "Run 10 — result" below**)

**One variable: `ATTN_TARGET = True`.** Everything else is run 9's configuration byte for
byte, which is the only reason a run-9 → run-10 delta means anything. The saliency term's
*shape* is untouched — same BCE call, same `LAMBDA_SAL = 0.5`, same `lambda_sparsity = 0.0`
/ `lambda_entropy = 0.0` — and only the **content** of `_tgt` changes, from `patch_ink >
0.15` to the top-K of a frozen run-5 decoder's cross-attention. That is literally what D7
asked for: keep the properties ink was supplying (dense / coherent / free) and replace what
it points at.

### Preconditions — all five are now measured, not argued

| precondition | status |
|---|---|
| the target is a *different* target from ink, not a relabelling | D8 — and read the honest version in Pending 13: the maps are near-orthogonal (r +0.083) but the binarised top-K overlaps ink **0.63–0.68**, against a content-free floor of **≈0.65**. "Different" rests on D8's centroid spread (6.12 vs 1.81 grid rows), not on the overlap number |
| this scorer can actually fit it | D9 — held-out AUC **0.976** vs a 0.498 shuffled floor, and **+0.212** over the best featureless constant map |
| it stays put while the encoder drifts | **D10 — S = 0.9613 same-page vs X = 0.6246 across pages, gap +0.3367.** Both thresholds pre-registered before reading |
| the code runs, and its guards fire | `verify_attn_target.py` **41/41 by execution**, plus the 18/18 suite. Caught four defects a parse check passes |
| **the whole composition runs, not just the pieces** | `verify_attn_train_step.py --full` **10/10 by execution** (2026-09-02): cell 11's verbatim prologue + training body, `ATTN_TARGET=True`, run-5 weights, 2 real pages, one real optimizer step. Teacher stayed bit-identical, all 6 router tensors moved, `ch == K/N`, Swin drift `[0,0,0,33]`, target still exact-K off the drifted encoder. **Do not read its epoch line as a forecast:** one step on two pages printed `ov 0.404 ch 0.500 lift −0.096`, i.e. *negative* lift, which is what one step should look like and is no evidence either way about the "lift well above 0.000 after epoch 1" the watch table asks for |

**None of these say the target helps.** D6 is the standing case of a proxy fitted harder
while accuracy fell — that is the entire question run 10 exists to answer.

### Configuration

1. **Kaggle → Add Input → the run-5 checkpoint dataset.** Required, not optional: both
   **cell 2 and cell 11 assert** `RESUME_CKPT` when `ATTN_TARGET` is on, because the teacher
   has to be the run-5 checkpoint D8/D9/D10 characterised. Without it the "teacher" would be
   donut-base's untuned decoder, which was never measured. **Cell 2's copy of the assert was
   added 2026-09-02** for the reason cell 2 already validates `RESUME_CKPT`'s path: cell 11
   runs *after* Cell 6's ~19-minute dataset download, so the same mistake used to cost twenty
   minutes instead of one. Note that `RESUME_CKPT`'s basename auto-resolution only fires when
   the variable is already truthy — leaving it `None` gets no help from it.
2. **Cell 2 `RESUME_CKPT`** → that path. The basename glob resolved it for run 9 even though
   the literal path was wrong, and prints where it landed.
3. **Cell 2 `ATTN_TARGET = True`.** This is the run's only edit beyond step 2.
4. **Touch nothing else**: `DO_TRAIN=True`, `TRAIN_KEEP_RATIO=0.50`, `TRAIN_EPOCHS=5`,
   `SUPERVISE_SALIENCY=True` (also asserted on — with it off, `LAMBDA_SAL=0` and 13(b)
   would be a silent no-op, an all-STE run mislabelled), `ALLOW_CPU=False`.
   `SALIENCY_THRESHOLD` is **inert** on this branch; leave it at 0.15 anyway so the diff
   against run 9 stays one line.
5. **Session options → Accelerator → GPU.**
6. **Run All**, watch the table below, then download `/kaggle/working/pruned_ocr_results.zip`
   and file it as **`run 10/`**.

### What to watch, in order

| stage | expect | if wrong |
|---|---|---|
| cell 2 | `CFG: SUPERVISE_SALIENCY=True ATTN_TARGET=True (target = FROZEN run-5 decoder cross-attention top-K …)` | `ATTN_TARGET=False` here means step 3 was missed and the run is a **duplicate of run 9** — kill it in the first minute rather than the fifth hour. This line is new (2026-09-02); run 9's log had no printed record of this knob at all |
| cell 7 start | `Resumed /kaggle/input/… (missing=0, unexpected=0)` | nonzero ⇒ not starting where run 9 did |
| cell 11 start | `13(b): frozen teacher decoder snapshotted from run 5 (eager attention). Target = top-K of its cross-attention, NOT patch ink.` | absent ⇒ `ATTN_TARGET` is off. **This print is the only proof the teacher exists** |
| cell 11 step 0 | `target: ATTN top-K \| positive rate 0.5000 (expected 0.5000 = 2400/4800)` | it **asserts** here rather than warning. A rate ≠ K/N means the target is not the top-K mask it claims to be; an all-zero target would train the router toward a constant and void the run silently |
| — | a `RuntimeError` naming `cross_attentions` | SDPA is still active on the teacher and the target would have been silently all-zero. This is the transformers-5.4 trap in the Gotchas: it logs a **warning, not an exception**, and returns an **empty tuple**, so the guard checks `not ca or ca[0] is None` every step |
| epoch 1 line | `… \| ov <n> ch 0.500 lift <n>` — and `lift` should already be **well above 0.000** | `lift ≈ 0.000` after a full epoch ⇒ the auxiliary is not taking, and every recall number downstream is uninformative about the hypothesis. `ch` must read **0.500**: it is the target's positive rate, and top-K pins it to K/N exactly |
| epochs 2–5 | `lift` rising or flat-high; `p` std **not** → 0 | std → 0 is constant-collapse, which makes `torch.topk` return the first K indices — a structured-looking selection that is not learned at all. `ov` oscillating near `ch` is D10's residual risk showing up: the target moving under the router |
| cell 15 early | `weights restored and fingerprint-verified`, then `got (77.74, 64.70, 53.05) … max drift 0.00` | a `skipped:` line means step 1/2 was missed and run 10's absolute numbers are unanchored |

### Cost

Run 9's measured shape plus one frozen-teacher decoder forward per optimiser step:
~19 min dataset download, ~4 h training **+15–20%** for the teacher pass, ~3 min cell 13
eval, ~42 min cell 15 (16 rows × 50 images × ~3.1 s). **≈ 5.5–6 h.** Cell 14 (the decoding
ablation, ~13 min) is droppable — settled at run 6 and its control is against
`RUN5_REFERENCE`, which a retrained checkpoint fails by construction.

The **+15–20% is still an estimate.** What *is* measured (`verify_attn_target --real`, CPU):
the teacher forward + target costs **0.3–0.4 s/step** and its cross-attention tensor is
**294 MB** fp32 at T=239 — 4 layers × 16 heads × T × 4800, materialised for all four layers
at once. Worst case is T=512 (≈630 MB fp32, ≈315 MB under autocast), which a 16 GB T4
absorbs, and the pad mask truncates T to the longest real prefix in the batch — with real
FUNSD labels **239/512 tokens, 53% pad**, so it typically halves.

### Acceptance — pre-registered, with the noise caveat stated first

**Nobody has ever run this config twice, so the training-seed variance is unknown.** Runs
8→9 were read as a real −0.54 pt effect, which was defensible only because the *mechanism*
moved measurably in the opposite direction at the same time. So: treat **|Δ| < 1.0 pt at a
single budget as no detectable effect**, and let the inference rest on two things noise
cannot easily fake — the **pattern across three budgets** moving together, and the `lift`
column agreeing with it.

Run 9 baseline, n=50, seed 0 (word recall):

| budget | run 9 router | run 9 ink oracle | headroom |
|---|---|---|---|
| keep=0.75 | 79.41 | 77.84 | router already above the oracle |
| keep=0.50 | **79.63** | 76.89 | router above the oracle (D3: probably co-adaptation, not selection) |
| keep=0.35 | **75.85** | **77.60** | **the oracle beats the router by 1.75** — the one budget with clear headroom, and the one 13(b) has the most to prove at |

| outcome | reading | what to do |
|---|---|---|
| recall up ≥1 pt at 0.35 **and** ≥0 at 0.50, `lift` positive | 13(b) works. The first target change in this project to pay off | keep it; then the layer choice inside `attn_topk_target` (currently the layer-mean) becomes the live knob |
| `lift` clearly positive, recall flat or down | **the D6 verdict transfers from ink to attention** — a real result, and arguably the more valuable one: two independent proxies fitted successfully while accuracy did not follow, which indicts the *pruning-as-selection* framing rather than the choice of proxy | stop tuning targets. Record it and move to Pending 5 / the ToMe branch |
| `lift ≈ 0.000` | the auxiliary never took. Recall says nothing | debug the target, do **not** interpret the recall table |
| recall up at every budget but `lift ≈ 0` | the gain is not the mechanism. Suspect the teacher forward perturbing something else | do not claim 13(b) |

### The prediction, recorded before the run so it can be wrong

**`lift` will be clearly positive by epoch 1** — D9 measured held-out AUC 0.976 for exactly
this scorer on exactly this target, and D10 says the target barely moves, so failing to fit
it would be surprising. **Recall I expect to be roughly flat at keep=0.50 (within ±1 pt of
79.63) and up modestly at keep=0.35**, where the ink oracle currently beats the router by
1.75 pts. I am **not** predicting a clear win, and the most likely single reason is a gap
none of D8/D9/D10 closes:

> **The teacher's attention is measured on the FULL 4800-token grid, but the target is used
> to choose 2400.** It answers *"where does the decoder look when it has everything?"*, not
> *"which half should I hand it?"* — and once tokens are removed the decoder's attention
> redistributes over what remains. D3's co-adaptation finding is the same phenomenon from
> the other side: the router "beats the oracle" at keep=0.50 largely because the decoder
> adapted to whatever the router kept, so changing the target perturbs both the selection
> *and* what the decoder adapts to.

If run 10 comes out flat, that gap is the first hypothesis to test, and it is testable
without a GPU: recompute the teacher's attention **through the pruned grid** and see whether
the top-K target changes materially. Do not add it to run 10 — one variable.


## Run 10 — result (Kaggle T4, executed 2026-09-03) — the auxiliary fit better than anything in this project and the accuracy did not move; **the reason is that keep=0.50 is not a binding budget**

**Verdict on 13(b): NULL on the pre-registered acceptance criterion.** Recall vs run 9, all
three trained budgets:

| budget | run 9 (ink target) | run 10 (attn target) | Δ | verdict |
|---|---|---|---|---|
| keep=0.75 router | 79.41 | 79.36 | **−0.06** | noise |
| keep=0.50 router | 79.63 | 79.41 | **−0.22** | noise |
| keep=0.35 router | 75.85 | 76.35 | **+0.49** | noise |

Every |Δ| is under the **±1 pt** floor that was pre-registered *before* the run (nobody has
run this config twice, so single-budget sub-point deltas are not results), and the signs are
inconsistent across budgets. **Do not report 13(b) as an improvement or as a regression.**
Cell 13's headline keep=0.50 numbers agree: 79.63 → 79.41 recall, 64.805 → 64.807 char acc,
0.35195 → 0.35193 NED.

### The comparison is clean — and that is verified by diff, not by trusting the checklist

Both runs' executed notebooks are inside their own `pruned_ocr_results.zip` as
`__notebook__.ipynb`, so "one variable" is checkable after the fact. Diffing run 9's against
run 10's, the **only removed lines in the whole notebook** are:

```
- _ink  = patch_ink(pixel_values, _sc.shape[1]).to(_sc.dtype)     <- the one variable
- _inkn = _ink / (_ink.amax(dim=1, keepdim=True) + 1e-9)          <- the one variable
- _tgt  = (_inkn > SALIENCY_THRESHOLD).float()                    <- the one variable
- print(f'Epoch {epoch} | Avg Loss {...} | CE {...}')             <- logging only
- ('retrain router WITH pruning ON (keep_ratio={TRAIN_KEEP_RATIO})...   <- the missing-f fix
```

Cell 4 is **purely additive** (+75/−0: `attn_topk_target`, and `forward()` also returning
pre-prune `visual_tokens`). `criterion = AdaptivePruningLoss(lambda_sparsity=0.0,
lambda_entropy=0.0, ...)`, `LAMBDA_SAL = 0.5`, all three learning rates, `GRAD_ACCUM`,
`TRAIN_EPOCHS` and the data pipeline are **byte-identical**. This is the first run in the
project whose "we changed one thing" claim is *demonstrated* rather than asserted — do this
diff for every future run, it costs 30 seconds.

**It also cleared a scare worth recording.** Run 9's epoch lines read `Avg Loss 0.3091 | CE
0.3091` with **no `sal` column**, which reads exactly like an unsupervised run — i.e. like the
baseline being an all-STE run mislabelled as ink-supervised, which would have voided the whole
comparison. Reading run 9's *executed source* settled it: `SUPERVISE_SALIENCY = True`,
`LAMBDA_SAL = 0.5`, `_tgt = (_inkn > SALIENCY_THRESHOLD)`, and `loss = loss + (LAMBDA_SAL *
_sal) / GRAD_ACCUM` are all present. Run 9 ran the **pre-F3** notebook, whose `epoch_loss`
accumulated CE only — that is *precisely* the defect F3 was written to fix, showing up as a
false alarm one run later. The ink term ran; the log just could not say so.

### The mechanism worked — better than any auxiliary this project has fitted

```
target: ATTN top-K | positive rate 0.5000 (expected 0.5000 = 2400/4800)
Epoch 1 | Obj 0.5714 | CE 0.3500 | sal 0.4429 x0.5 | dev 0.2789 | p 0.480+-0.330 | ov 0.798 ch 0.500 lift +0.298
Epoch 2 | Obj 0.2055 | CE 0.0728 | sal 0.2653 x0.5 | dev 0.1747 | p 0.484+-0.392 | ov 0.898 ch 0.500 lift +0.398
Epoch 3 | Obj 0.1651 | CE 0.0521 | sal 0.2260 x0.5 | dev 0.1470 | p 0.489+-0.411 | ov 0.917 ch 0.500 lift +0.417
Epoch 4 | Obj 0.1479 | CE 0.0462 | sal 0.2033 x0.5 | dev 0.1311 | p 0.493+-0.422 | ov 0.925 ch 0.500 lift +0.425
Epoch 5 | Obj 0.1379 | CE 0.0414 | sal 0.1930 x0.5 | dev 0.1231 | p 0.495+-0.428 | ov 0.930 ch 0.500 lift +0.430
```

- **`ov` 0.798 → 0.930 against `ch` 0.500** — the router's own top-2400 ends up containing
  **93%** of the frozen teacher's top-2400 attended tokens. `lift +0.430`. D9 predicted
  reachability (held-out AUC 0.976) and the real run delivered it.
- **No constant collapse:** `p` std *rose* 0.330 → 0.428. Collapse was the failure mode that
  would have made `torch.topk` return the first K indices and fake a structured selection.
- **`sal` 0.4429 → 0.1930, `dev` (mean |p−t|) 0.2789 → 0.1231** — monotone, still falling at
  epoch 5.
- **The router is a genuinely different router**, not a re-run: vs run 9's checkpoint its 6
  tensors moved **median rel-L2 0.3245, max 0.9066**. Decoder moved 0.0080, encoder top stage
  0.0044 (34/36 tensors, stages 0–2 untouched).

**So this is D6's pattern again, and sharper.** D6: proxy fitted harder, accuracy *fell*.
Run 10: proxy fitted **much** harder — the strongest auxiliary fit on record here — accuracy
**flat**. Fitting the auxiliary is not the difficulty.

### The finding that matters: retained ink is dead as an objective, on a third and independent line of evidence

| budget | `retained_ink` run 9 | run 10 | Δ ink | Δ recall |
|---|---|---|---|---|
| keep=0.75 | 0.986 | 0.840 | **−0.146** | −0.06 |
| keep=0.50 | 0.922 | **0.675** | **−0.247** | −0.22 |
| keep=0.35 | 0.826 | **0.511** | **−0.315** | +0.49 |

The router stopped following ink — it now keeps barely more ink than *random* at keep=0.35
(0.511 vs 0.349) — and recall did not move a point. D2 established this correlationally, D6
interventionally via the F1 sign fix, and run 10 now does it with a **completely different
objective**: a 25–32 pt collapse in retained ink at flat accuracy. Retained ink is not the
router's mechanism, and `mean_min_line_cov` / ink-coverage numbers should never again be
quoted as evidence a selection is good.

### Why the null was structurally guaranteed at keep=0.50 — read this before designing run 11

**`keep=1.00` scores 77.32. `keep=0.50` scores 79.41.** Pruning to *half* the tokens beats
not pruning, by **+2.1 pts** — and run 9 reproduces it independently (77.30 vs 79.63, +2.3).
At keep=0.50 the model is **not information-limited**: the discarded 2400 tokens carry nothing
the decoder needed, and pruning is acting as a mild regulariser. **No selection objective can
raise recall at a budget that is not binding**, so run 10's null at 0.50 and 0.75 says nothing
about whether attention is a better target than ink. It was unwinnable by construction, and
that was visible in run 9's own rows before run 10 was launched.

Where the budget *does* bind — the `router − random` gap, i.e. how much selection quality is
worth at all:

| budget | router | random | gap | binding? |
|---|---|---|---|---|
| keep=0.75 | 79.36 | 73.55 | +5.8 | barely |
| keep=0.50 | 79.41 | 65.42 | +14.0 | no — beats keep=1.00 |
| keep=0.35 | 76.35 | 48.57 | **+27.8** | **yes — 3.1 pts below the 0.50 score** |

keep=0.35 is the **only** budget where the question "is this target better?" is well-posed,
and it is the only one where 13(b) produced a positive delta (+0.49 — still noise). **Run 11
should test selection at keep=0.20–0.35, not 0.50.**

### One cost that does not appear in the headline, and one anomaly I cannot explain

**The ink ORACLE row fell 8.93 pts at keep=0.35 (77.60 → 68.67) on a bit-identical token
selection** (`retained_ink` 0.950 in both runs — the ink oracle ignores the router entirely).
Same tokens, different weights, so this is purely what the retrain did to the model's ability
to read an *ink*-selected token set. It is monotone in pruning aggressiveness: −0.70 at 0.75,
−2.41 at 0.50, **−8.93** at 0.35. The natural reading is that run 10's encoder+decoder
co-adapted to the attention-selected distribution and is now *more specialised* than run 9's.

**But that story does not hold up cleanly, so do not adopt it yet:** `random` at keep=0.50
*improved* +2.86 (62.56 → 65.42) on an equally bit-identical selection. Run 10's weights are
**better** on random token sets and **worse** on ink-selected ones. Both are off-distribution
for run 10's router, so specialisation alone does not predict the signs. Logged as open.

The `NEGATED` rows also swung hard (keep=0.50: 15.65 → 2.11 while their retained ink *rose*
0.078 → 0.325 — worse recall on more ink, one more nail in the ink coffin; keep=0.75
`stratified_negated` 49.43 → 59.78). These are deliberately-broken-input rows and large swings
there are expected; do not build on them.

### Harness and saturation checks

- **Harness anchored.** `harness_verified: true`, note *"run-5 weights reproduce run 6 within
  0.00 pts"*. `control_drift_pts = 0.98` is **not** a measurement fault: by cell 16's own
  design that figure is row 0 (`keep=1.00`, *retrained* weights) vs `RUN6_REFERENCE`, so with
  the harness verified it measures **what the retrain did to the unpruned ceiling**. Run 9's
  was 1.09. Both retrains cost ≈1 pt at keep=1.00; the per-metric split for run 10 is
  0.42 / 0.59 / 0.98.
- **Both runs are training-set saturated.** CE 0.3500 → **0.0414** (run 10) and 0.3091 →
  **0.0383** (run 9), over 1692 steps/epoch × 5 epochs — near-identical trajectories. This
  does not confound the delta (same data, epochs, LRs) but it caps what *any* objective tweak
  can do, and it is the same memorisation signature flagged for runs 3 and 4.

### What this run does and does not license

**Does:** retained ink is finished as an objective (three independent lines now). The router's
value is real and large (+14 to +28 pts over random) and is *not* ink coverage. The attention
target is fittable to `ov 0.930`. **50% token pruning is better than no pruning by ~2 pts, in
two independent runs** — that is the strongest deliverable claim the project has, and it does
not depend on 13(b) at all.

**Does not:** say anything about whether the decoder's attention is a better selection target
than ink. That question was tested at a budget where no target can win. It is still open, and
keep=0.20–0.35 is where to ask it.

The pre-registered "if run 10 comes out flat" hypothesis — that the teacher's attention is
measured on the full 4800-token grid but used to pick 2400, so it answers the wrong question —
is now **live**, and remains worth the CPU-only test described above. But it is the **second**
explanation to reach for: the non-binding-budget account above is simpler, is supported by
run 9's rows as well as run 10's, and predicts the null without appealing to the target at all.

**Run 10's pre-flight (`verify_attn_train_step.py --full`, 10/10) called this exactly right in
advance for the wrong-looking reason.** Its one-step epoch line printed `ov 0.404 ch 0.500
lift −0.096` and it was recorded as "no evidence either way" — correct, and the real run's
`lift +0.430` shows the pre-flight measured mechanism-liveness, not outcome. Keep that
separation: [[measure-mechanism-and-goal-separately]] is the lesson this run demonstrates in
its purest form so far — the mechanism moved as far as it possibly could, and the goal did not
move at all.

**Superseded in one respect by D11 (2026-09-04):** the section below claims keep=0.50 was
non-binding and treats keep=0.35 as a budget where the question was live. That is wrong.
Measured against each checkpoint's own ceiling, keep=0.35 is *also* non-binding on run 9
(79.25 vs a 77.62 ceiling, **+1.62**). So **both** of run 10's headline rows were unwinnable,
not just the keep=0.50 one, and its `+0.49` at keep=0.35 is as uninformative as its `−0.22`.
The budget first binds at **keep=0.25**.


## Diagnostic D11 (2026-09-04, local CPU, 182 min) — 13(b) is dead: at budgets that *bind*, the attention target is **worse** than ink, and the mechanism says why

**The question.** Run 10 replaced the router's target (patch ink → frozen run-5 decoder
cross-attention) and recall did not move. The Run-10 section diagnosed that as a
*non-binding budget* rather than a failed target: discarding half the tokens beat keeping
all of them, so no selection objective could win there. That diagnosis made a prediction —
at a budget where selection actually costs something, the better target should show up. D11
tests it on the two checkpoints already on disk. Eval only, no GPU, no training.

**The answer is the third of the three outcomes I pre-registered before the run, and it is
the most informative one: the attention target does not tie, it LOSES.**

| keep | tokens | run 9 (ink) | run 10 (attn) | Δ | SE | t | binds? |
|---|---|---|---|---|---|---|---|
| 1.00 | 4800 | 77.62 | 76.36 | −1.27 | 1.86 | −0.68 | — |
| 0.50 | 2400 | 80.46 | 80.66 | +0.20 | 1.58 | +0.13 | no (+2.84 over ceiling) |
| 0.35 | 1680 | 79.25 | 75.41 | −3.84 | 1.78 | **−2.15** | no (+1.62 over ceiling) |
| 0.25 | 1200 | 71.15 | 65.52 | **−5.63** | 2.35 | **−2.40** | **YES** (−6.47) |
| 0.20 | 960 | 63.10 | 50.30 | **−12.81** | 2.06 | **−6.23** | **YES** (−14.52) |

Monotone in budget tightness: `+0.20 → −3.84 → −5.63 → −12.81`. A sign-inconsistent scatter
around zero would have been another null; this is an ordered, growing penalty.

### The mechanism, and it is the whole result

`retained_ink` for the router, against the `random` floor at the same budget:

| keep | run 9 router | run 10 router | random floor | run 10 lift over random |
|---|---|---|---|---|
| 0.50 | 0.922 | 0.675 | 0.503 | +0.172 |
| 0.35 | 0.826 | 0.511 | 0.353 | +0.158 |
| 0.25 | 0.704 | **0.355** | 0.251 | **+0.104** |
| 0.20 | 0.612 | **0.257** | 0.201 | **+0.056** |

Run 10's router converges toward the random floor as the budget tightens. Supervising on the
decoder's cross-attention produced a selector that is **nearly ink-agnostic** — harmless
while there are enough tokens that the choice does not matter, ruinous once every token has
to carry text. Note what this does *not* say: it is not that attention is uncorrelated with
where the text is (D8 established it is a different, page-specific signal). It is that the
**top-K of the teacher's attention is not a good set of tokens to keep**, which is a
different claim and the one that matters for a pruner.

Corroborated by the selection headroom, which run 10 *loses* exactly where it should not:

| keep | run 9 router−random | run 10 router−random |
|---|---|---|
| 0.50 | +17.69 | +15.84 |
| 0.35 | +27.41 | +23.81 |
| 0.25 | **+33.95** | **+23.24** |
| 0.20 | **+29.30** | **+17.50** |

### The controls are the strongest in the project, and one of them was rebuilt to earn that

All 10 pass. The six `retained_ink` gates match Kaggle **exactly to three decimals**
(`0.922`, `0.826`, `0.675`, `0.511`, and `1.000` twice — every gap `0.000`), and `random`-mode
ink is bit-identical across the two checkpoints at all four budgets (`0.00e+00`), which makes
"paired" a measured fact rather than a design intention. This is why the control was moved
off the recall delta and onto ink — see the note under the verifier index; the original
version passed on a 2-image smoke run and could not have failed for the right reason.

**A second, unplanned payoff: the ink gates being exact while recall drifts separates two
things this project had been conflating.** At keep=0.35 the local ink is `0.826`, identical
to Kaggle's, yet local recall reads 79.25 against Kaggle's 75.85. Identical selection,
3.40 pts of recall difference. So *selection* reproduces bit-exactly across device and
transformers version, and **generation** is what drifts — and the drift widens as the budget
tightens (+0.32 at keep=1.00, +0.83 at 0.50, +3.40 at 0.35). Practical consequence: local
absolute recall at aggressive budgets must never be quoted against Kaggle's, while the
run10−run9 delta is unaffected because both checkpoints run under identical local conditions.

### The honest caveats — three, and the second is the real one

1. **My own power criterion was not met at any budget.** The pre-registered
   `MIN_EFFECT_PTS = 3.0` requires SE ≤ 1.5; observed SEs are 1.58–2.35, so the smallest
   *detectable* effect was 3.15–4.70 pts. A genuine 3-pt effect would have been missed. That
   does not undermine the two verdicts — a detected effect at |t| ≥ 2 is detected regardless
   of what the power projection said about smaller hypothetical ones, which is why the
   verdict branch tests |t| before it tests power — but it does mean **this run could not
   have returned a trustworthy null**, and had the answer been "tie" the correct output would
   have been UNDERPOWERED. Note also that FUNSD test has only 50 images and the train split
   is contaminated (runs 9/10 trained on it), so there is no clean way to buy more power.
2. **Local and Kaggle disagree on the *sign* at keep=0.35: −3.84 local vs +0.49 Kaggle, a
   4.33-pt gap.** This is the informational (non-gating) control, and it should not be waved
   away just because I demoted it — it is the one result in this run that does not reproduce.
   Ink is exact at that budget, so the selection is identical and the disagreement is
   generation-side, consistent with the drift pattern above. It matters because keep=0.25 and
   0.20 were **never measured on Kaggle**, so their local values carry the same unquantified
   environment sensitivity. What protects the conclusion is magnitude and mechanism, not
   agreement: −12.81 at t −6.23 is far outside any plausible environment artifact, and the
   ink-retention collapse that explains it is measured *exactly* at the budgets Kaggle did
   check. **The −5.63 at keep=0.25 (t −2.40, barely clearing the pre-registered 2.0) is the
   weak member of this run — do not quote it without the keep=0.20 row beside it.**
3. **Run 10's unpruned ceiling is 1.27 pts *below* run 9's locally** (76.36 vs 77.62) where
   Kaggle had them level (77.32 vs 77.30). Not significant (t −0.68), and the binding test
   uses each checkpoint's own ceiling so nothing here depends on it — logged because it is a
   third instance of the same local/Kaggle generation-side divergence.

### What D11 settles, and what it costs

**Settled: selection objectives are finished as a research direction on this setup.** Ink
supervision was already dead as an objective on three lines (D2 correlational, D6/run 9
interventional, run 10's collapse of retained ink with flat recall). Attention supervision is
now shown to be *actively worse* where selection matters. Both remaining candidates in the
Pending 13 list were variants of "supervise the router on a better per-token target", and the
mechanism found here — convergence to the random floor under a tight budget — is not specific
to which target is used. **Do not run run 11 in the form sketched under Pending 13.** The
hypothesis left "live" in the Run-10 section (recompute the teacher's attention *through* the
pruned grid) is also retired: the target was not measured on the wrong grid, it is the wrong
thing to select on.

**Also settled — Pending 8, and it goes against the deliverable.** Latency, n=50, per image,
router mode, both checkpoints:

| keep | visual tokens | run 9 ms | run 10 ms | speedup vs keep=1.00 | mean gen tokens |
|---|---|---|---|---|---|
| 1.00 | 4800 | 12914 | 12494 | 1.00× | 254 / 243 |
| 0.50 | 2400 | 12691 | 11889 | 1.02× / 1.05× | 271 / 261 |
| 0.35 | 1680 | 12512 | 12311 | 1.03× / 1.01× | 273 / 256 |
| 0.25 | 1200 | 12435 | 12329 | 1.04× / 1.01× | 277 / 261 |
| 0.20 | 960 | 12435 | 12173 | 1.04× / 1.03× | 280 / 256 |

**A 5× reduction in visual tokens buys 1.04×.** Generation is decoder-bound — 243–280
autoregressive steps, each a full decoder pass, while the encoder runs once regardless — so
pruning shrinks only the cross-attention KV. This confirms D3's "barely buys wall-clock" and
quantifies it across five budgets. **Any latency or throughput claim in the writeup is
false.** The defensible framing is visual-token count and the activation memory that scales
with it, explicitly not speed.

### What the deliverable actually is, now that the router direction is closed

Not the router. The result that survives everything in this file is that **post-encoder
pruning is close to free and can help**: at keep=0.35, run 9 discards **65% of visual tokens
and scores +1.62 over its own unpruned ceiling** (79.25 vs 77.62), reproducing the same
direction Kaggle measured at keep=0.50 in both runs 9 and 10 (+2.3, +2.1). Note this is a
larger claim than the keep=0.50 one quoted elsewhere in this file, and it is the one to
lead with. Its three live weaknesses, all recorded: ~~the efficiency claim is token-count only
(above)~~ — **as of M1 (2026-09-06) there is one measured efficiency claim, and keep=0.35 is
exactly where it lands: the decoder cross-attention KV cache falls 150.00 → 52.50 MiB
(−65.0%) at that budget, for −0.26 pts (t −0.18, n=50). So the sentence to lead with pairs the
same budget twice — 65% of the tokens discarded, 65% of the cross-attention KV freed, no
detectable accuracy cost. It is *not* a latency claim (D11: 1.04×) and *not* an encoder saving
(there is none); see the M1 section for the full scope limits** — the unpruned ceiling itself
moves with the retrain (caveat 3 and `control_drift_pts`
≈ 1.0), and ~~*why* pruning helps is still unexplained — a regularisation-like effect is the
obvious guess and nothing in this file tests it~~ — **D12 (2026-09-05) tested that guess and
refuted it.** The gain is *conditional on pruning-aware training*, not a property of pruning:
run 5, which never trained with pruning, loses monotonically at every budget on the identical
token sets (−1.57 / −6.03 / −11.47 / −20.34). **So the sentence to lead with is "pruning to a
third of the tokens costs nothing IF you train for it" — the "if" is load-bearing and was
absent from every earlier phrasing in this file.** Any framing that presents the gain as
inference-time denoising, free-lunch regularisation, or a property of the pruner itself is
now contradicted by evidence in this repo. See the D12 section.


## Diagnostic D12 (2026-09-05, local CPU, 110 min) — H2 is REJECTED: pruning does not denoise, it matches the training budget. The deliverable needs the word "if".

`scripts/eval_why_pruning_helps.py --n 50`, log `results/why_pruning_helps_n50.log`, data
`results/why_pruning_helps_local.json`, rescored verdict
`results/why_pruning_helps_n50_rescored.log`.

D11 left the deliverable standing on an unexplained fact: pruning *raises* recall. Two
explanations, with very different consequences:

- **H1 TRAIN/TEST MATCHING (mundane).** Runs 9/10 trained with pruning ON at
  `TRAIN_KEEP_RATIO=0.50`, so keep=1.00 at eval is **off-distribution** for those weights.
  The unpruned ceiling is artificially depressed and the "gain" is a **recovery**.
- **H2 INFERENCE-TIME DENOISING (interesting).** Most of a FUNSD page is blank paper;
  dropping it genuinely reduces cross-attention dilution, so it should help a model that
  **never trained with pruning** too. This was the file's own standing guess ("a
  regularisation-like effect is the obvious guess").

**Run 5 discriminates them** — the pre-pruning checkpoint, trained *and* evaluated at
keep=1.00. H1 predicts its curve peaks unpruned and falls; H2 predicts it improves under
pruning. `select_mode="ink"` makes the comparison controlled: ink ranks patches by pixel
contrast from the image alone, so it is **weight-independent** and both checkpoints keep the
*identical* token set at every budget — verified `0.00e+00` at all four, not assumed.

### The result: H2 predicted improvement and got monotone decline

| keep | tok | run 5 recall | vs 1.00 | SE | t | run 9 recall | vs 1.00 | SE | t | ink |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.00 | 4800 | 74.72 | — | — | — | 77.62 | — | — | — | 1.000 |
| 0.50 | 2400 | 73.16 | −1.57 | 2.60 | −0.60 | **78.22** | **+0.60** | 1.38 | +0.43 | 0.994 |
| 0.35 | 1680 | 68.70 | **−6.03** | 2.31 | **−2.61** | 77.37 | −0.26 | 1.41 | −0.18 | 0.950 |
| 0.25 | 1200 | 63.25 | **−11.47** | 2.50 | **−4.58** | 70.67 | **−6.96** | 2.46 | **−2.82** | 0.847 |
| 0.20 | 960 | 54.39 | **−20.34** | 2.80 | **−7.26** | 64.61 | **−13.01** | 2.40 | **−5.42** | 0.754 |

**Run 5 peaks at keep=1.00 and falls monotonically, significantly at three of four budgets.
Run 9 peaks at keep=0.50 — exactly the budget it was trained for.** That is H1's prediction
and the opposite of H2's, and it needs no cross-checkpoint comparison to read: it is the
shape of run 5's own curve, on its own weights, on its own images.

Two things make the rejection harder to escape:

1. **H2 was given its most favourable selection and still failed.** The ink oracle retains
   **0.994** of the page's ink at keep=0.50 — near-perfect text retention, blank paper is
   what got dropped. That is precisely the condition H2 says should help. Run 5 declined
   anyway.
2. **Retaining more ink scored *worse*.** Paired on the same 50 images, run 9 at keep=0.50
   with **router** selection scores 80.46 at retained ink 0.922, while **ink-oracle**
   selection scores 78.22 at retained ink 0.994: **−2.24 pts for +0.072 more ink** (SE 1.38,
   t −1.62). Not significant, so *not a claim* — but it is the fourth independent line
   pointing the same way as "retained ink is dead as an objective" (D2, D6/run 9, run 10).

### Difference-in-differences — same tokens, different weights

`did = (run5[k] − run5[1.00]) − (run9[k] − run9[1.00])`, paired per image. Negative means
run 5 is hurt *more* by the identical pruning. H2 predicts ≈ 0.

| keep | run 5 Δ | run 9 Δ | DiD | SE | t |
|---|---|---|---|---|---|
| 0.50 | −1.57 | +0.60 | −2.17 | 2.67 | −0.81 |
| 0.35 | −6.03 | −0.26 | **−5.77** | 2.53 | **−2.28** |
| 0.25 | −11.47 | −6.96 | −4.52 | 2.98 | −1.52 |
| 0.20 | −20.34 | −13.01 | **−7.33** | 2.45 | **−3.00** |

Negative at all four budgets, significant at two. Every DiD mean was asserted equal to the
difference of the two separately-computed deltas (`ok` on all four rows) — the arithmetic is
checked, not eyeballed.

### The pre-registered code verdict disagrees with the shape finding, and both are reported

**`decide()` returned UNDERPOWERED**, and that stands: run 5's keep=0.50 delta is −1.57 with
SE 2.60, so nothing under 5.20 pts was detectable *at that budget*. I am not overriding it.

But the criterion I wired into code keyed on **keep=0.50 alone** — the flattest point on the
curve, and the budget run 9 was trained for. The docstring's pre-registered *prose* prediction
was about curve **shape** ("H1 predicts run 5 PEAKS at keep=1.00 and falls monotonically"),
and that is resolved decisively. **The lesson is not that the verdict was wrong; it is that
the code criterion tested a narrower proxy than the hypothesis it stood in for**, and I only
noticed because the two disagreed. When a hypothesis is about the *shape* of a curve, the
statistic must be about the shape — a single point on it is a proxy, and
[[proxy-objectives-sum-vs-min]] applies to acceptance criteria too. Both readings are reported
above with their power; neither is quietly promoted.

Where the test *was* well-powered, it helps rather than hurts: run 9's flat rows at keep=0.50
and 0.35 are **powered OK** (detectable ≥ 2.76 / 2.81 pts), so run 9's insensitivity to losing
65% of its tokens is a measured null, not a failure to look. Run 5's four rows are all
underpowered for a 3-pt effect — but its *large* deltas (−6.03 to −20.34) clear their own
resolution comfortably, so the rejection of H2 does not rest on an underpowered row.

### Controls — 7 of 7, and the anchor was replaced mid-flight on a pre-registered number

| control | result |
|---|---|
| selection held fixed, 4 budgets | ink identical across checkpoints, **`0.00e+00`** ×4 |
| ink oracle vs Kaggle, keep=0.50 / 0.35 | **0.994 vs 0.994**, **0.950 vs 0.950**, gap 0.000 |
| harness anchor: run 9 @ keep=1.00 reproduces D11 | **77.62 vs 77.62, gap 0.00** (tol 0.5) |
| run 5 @ keep=1.00 vs Kaggle run 6 | 74.72 vs 77.74, gap 3.02 — **`[INFO]`, gates nothing** |

The anchor swap is the methodological content of this run and is documented in full in the
`eval_why_pruning_helps.py` note above the File map. Short version: the original gate compared
a *local* level to a *Kaggle* level, which D11 had already shown does not reproduce (up to 3.4
pts on bit-identical selections) — and this script's own JSON says
`not_comparable_to_kaggle_in_level` while gating on exactly that. It failed at n=50 (gap 3.02)
and withheld the verdict. The replacement was pinned to a **number that did not yet exist**:
run 9 @ keep=1.00 must reproduce D11's *local* 77.62 within 0.5 pts, same device, transformers,
images and decode. **It came back 77.62, gap 0.00.** So the harness is sound and the run-5
Kaggle gap is environment drift, exactly as predicted before the number was visible. The
levels are *not* comparable to Kaggle; the **within-checkpoint deltas** are, and those are
what every conclusion here rests on.

### What D12 settles, and the one thing it does not

**Settled:** H2 is rejected. Pruning is not inference-time denoising, and the recall gain is
not a property of the pruner. **The deliverable requires the word "if": pruning to a third of
the visual tokens costs nothing *if you train for it*.** Every earlier phrasing in this file
omitted that condition.

**NOT settled — and this was stated in the docstring before any output:** run 9 differs from
run 5 by pruning-aware training **and by five more epochs of it**. So H1 is *supported* but not
*isolated* — the cross-checkpoint rows (retrain gains +5.07 / +8.67 / +7.42 / +10.23, all
significant) say a difference exists, not that pruning-aware training caused it. Isolating it
needs a run-5-length control trained without pruning, which does not exist. **Do not upgrade
"H1 supported" to "H1 proven" anywhere in the writeup.**

**Caveat on levels:** run 5 reads 74.72 here vs 77.74 on Kaggle. Same weights, same 50 images,
same metric code — different device and transformers version. This is D11's
selection-reproduces-but-generation-does-not finding appearing a second time, now on a second
checkpoint, and it is why nothing in this section compares a local level to a Kaggle one.

## Measurement M1 (2026-09-06, local CPU, 72 s) — Pending 8(c) CLOSED: the one efficiency claim this project can actually make

`scripts/eval_kv_memory.py`. D11 killed the latency claim (5× fewer tokens → 1.04× wall-clock)
and option (a) was taken, which left the writeup with **no efficiency claim at all**. Option (c)
— decoder cross-attention KV memory — was the honest one still standing, and AGENTS.md recorded
for two days that it "still needs the memory measurement nobody has taken". Taken now.

| keep | tok | cross-KV MiB | vs keep=1.00 | % of params | self-KV MiB | gen tok |
| --- | --- | --- | --- | --- | --- | --- |
| 1.00 | 4800 | 150.00 | — | 19.46% | 10.69 | 343 |
| 0.50 | 2400 | 75.00 | −50.0% | 9.73% | 10.38 | 333 |
| **0.35** | **1680** | **52.50** | **−65.0%** | **6.81%** | 9.56 | 307 |
| 0.25 | 1200 | 37.50 | −75.0% | 4.86% | 10.19 | 327 |
| 0.20 | 960 | 30.00 | −80.0% | 3.89% | 7.72 | 248 |

**The claim, with its price attached: keep=0.35 cuts cross-attention KV 150.00 → 52.50 MiB
(−65.0%) for −0.26 pts of word recall (t −0.18, n=50 paired).** The pairing *is* the claim; the
percentage alone is not, which is why the headline is **not** keep=0.20's −80.0% — that budget
costs **13.01 pts (t −5.42)**, so the larger number is a memory win funded by an accuracy loss.
Both accuracy figures are read out of D12's JSON at runtime, not typed into this script.

### Why this is a measurement and not algebra

Four things, because "KV memory is reduced" is trivially easy to assert and hard to earn:

1. **Two independent measurements, asserted equal.** ANALYTIC `2 (K,V) × 4 layers × 16 heads ×
   64 head_dim × tokens × 4 B`, versus OBSERVED — walking the real `past_key_values` and summing
   `.numel() × .element_size()` over cross entries only. **Rel gap 0.0000 at all five budgets.**
   If these disagreed, the analytic model would not describe this architecture and every figure
   would be arithmetic dressed as evidence.
2. **The measured tensor is the one `generate()` decoded against.** My first draft re-derived
   the pruning path inside the eval script (`model.router(hidden)`, manual top-k) — a second copy
   of `src/model.py`'s logic, free to diverge from it, and it *was* already wrong (`router()`
   returns a 4-tuple, not scores). Replaced with a forward hook on the decoder that captures
   `encoder_hidden_states` on the first real step, **plus a control asserting its `seq_len`
   equals `generate()`'s own `meta["compressed_tokens"]`** at every budget. If the hook never
   fires the script raises rather than falling back on a re-derivation.
3. **Proportionality is asserted, not assumed.** Token ratio == byte ratio to 4 dp at all five
   budgets. A saving not proportional to the token count would mean something else is being
   measured.
4. **The self/cross split is proven, not commented.** Self-KV is asserted **exactly** equal to
   `2 × layers × heads × head_dim × (gen_tokens − 1) × 4 B` (rel gap 0.0000 ×5), and asserted
   **non-monotone in `keep`** — keep=0.25 generates 327 tokens against keep=0.35's 307, so its
   self-KV is *larger* (10.19 vs 9.56 MiB) while its cross-KV is *smaller* (37.50 vs 52.50).
   The two quantities are demonstrably not the same thing, so a self/cross mix-up cannot be
   reported as a pruning benefit.

### The docstring's own caution did not survive the data

I pre-wrote the hedge "a large *relative* reduction in a small absolute quantity is still small",
expecting KV to be a rounding error against the weights. **It is not: unpruned cross-KV is
19.46% of the model's own 771 MiB of parameters**, and 98 MiB is freed at the free budget. The
script now *derives* its framing from the measured share (`if share >= 10.0`) instead of printing
the prose I guessed in advance — the data's call to make, not the docstring's. This is the
mirror image of the usual failure mode in this file: a pre-written expectation that turned out
too *pessimistic*, and would have understated a real result had it been left to print.

### What this deliberately does not claim

- **Cross-attention KV only.** Not total, not peak, not encoder. The frozen Swin computes all
  4800 tokens at every budget (Pending 7), so there is **no encoder-side saving to report** —
  and both notebooks now say so.
- **fp32 on CPU.** Every byte figure halves at fp16/bf16 and scales linearly with batch size.
  The *percentage* is invariant to both. Reported rather than hidden, because it is the main
  thing that moves these numbers.
- **Not latency** (D11: 1.04×). Self-attention KV is unchanged by pruning.
- **n=1 image, and that is not a sample-size weakness.** Cross-KV size is a deterministic
  function of (layers, heads, head_dim, kept tokens, dtype) and does not vary with content;
  the analytic==observed control is what establishes that, rather than an average over images.
  Stated in the JSON as `n_images_note` so nobody has to take it on trust.

### Verification

17 controls, **all PASS**. Before the real run, a scratch selftest executed the two pure helpers
against stubs (extracted from the real source text by AST surgery, not retyped) across **three**
different cache layouts — legacy tuple-of-tuples, `EncoderDecoderCache` with `.layers[].keys`,
and `.key_cache`/`.value_cache` — and asserted all three yield **identical** numbers, so a
`transformers` upgrade cannot silently turn the cross figure into a self figure. Every control
was then fed a deliberately broken row and **required to FAIL**: observed at half analytic, a 2%
gap, non-proportional bytes, self-KV collapsing with the budget, self-KV of zero, self-KV sized
by *visual* tokens, a cross-KV-shaped monotone sequence, and a hook that grabbed the wrong
tensor. A control that has only ever seen good input is decorative. Scratch files removed.

### M1 extended to the merge stage (2026-09-18, local CPU, 154 s) — the 2.5× figure is now an artifact, not my arithmetic

Between run 13 landing and this extension, the claim *"2.5× cross-attention KV at M=1920 at no
measured cost"* was **cited to M1 — three times by name, twice with `results/kv_memory_local.json`
beside it — while that JSON contained no merge rows at all.** (Counted 2026-09-18 by grepping the
literal, not the topic: six pre-existing occurrences on five lines, across "The supported claim",
run 14's "what the 40% row buys", "Why 0.40 and not 0.20", run 14's decision table, and changelog
item (c). The three M1-citing ones are the first two and the last.) It was arithmetic I did in
prose: 4800/1920 = 2.5, times run 13's accuracy null. Both halves happened to
be right, and that is exactly the problem — a number that is right by luck reads identically to
one that is right by measurement. `scripts/eval_kv_memory.py` now measures the merge rows, so the
claim cites a JSON row instead of citing me.

Four rows appended to the grid. **`BUDGETS`' five rows above are deliberately not retyped** —
they are in the published `kv_memory_local.json` and in WRITEUP.md's audited numbers — so
`MERGE_BUDGETS` is a separate tuple and the loop runs their concatenation.

| keep | merge | K | r | tok M | cross-KV MiB | vs keep=1.00 | × reduction | self-KV MiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.00 | 0.20 | 4800 | 960 | 3840 | 120.00 | −20.0% | 1.25× | 10.72 |
| **0.50** | **0.20** | 2400 | 480 | **1920** | **60.00** | **−60.0%** | **2.50×** | 11.12 |
| 0.50 | 0.40 | 2400 | 960 | 1440 | 45.00 | −70.0% | 3.33× | 10.62 |
| 0.35 | 0.20 | 1680 | 336 | 1344 | 42.00 | −72.0% | 3.57× | 9.41 |

~~**The claim, with its price attached, exactly as the prune-only headline is stated: prune to
keep=0.50 and merge m=0.20 → M=1920, cross-KV 150.00 → 60.00 MiB (2.50×), for +0.54 pts of word
recall, 95% CI [−2.36, +3.83], n=50 paired. The CI includes zero: no measured cost.** And the row
that is *not* the headline: m=0.40 reaches 3.33× at M=1440 but costs **−3.86 pts [−7.45, −0.30]**
— resolved, and negative. 3.33× is available only with that cost quoted beside it.~~

> **SUPERSEDED 2026-09-24 by T3 — the accuracy half only. Every byte figure in this section
> stands unchanged.** The memory measurement is not what moved; the sentence wrapped around it
> was. Three defects, all in the two struck sentences above:
> 1. **The baselines don't match.** `2.50×` is `M=4800/M=1920` — against **keep=1.00** — while
>    the `+0.54` control row is `M=2400` (keep=0.50). So this paragraph pairs a *prune+merge*
>    memory ratio with a *merge-only* accuracy delta and reads as one intervention. The merge
>    step alone is **1.25×**. On a consistent keep=1.00 baseline the delta is **+2.29
>    [−0.44, +5.01]**, i.e. *better* — a **consistency defect, not an inflated result**.
> 2. **`+0.54` is the plain mean.** T1's pre-registered estimator gives **−0.65
>    [−2.36, +1.07]** on the identical row, and **+0.16** in run 14. Still a null; no longer
>    the same sign, in two independent directions.
> 3. **`−3.86 … resolved` does not replicate.** Run 13 gives −3.23 [−5.70, −0.76]; run 14 gives
>    **−0.17 [−2.40, +2.06]**. 3.33× remains unlicensed, now for being unreplicated.
>
> What this section is still the source of truth for: the **byte** table, the proportionality
> control below, and the analytic==observed agreement. For the accuracy pairing read claim 3 and
> `## Runs 13/14 re-scored under the run-17 rule (T3)`.

**Proportionality holds across the merge boundary, and that is the load-bearing result here.**
Token ratio == byte ratio to 4 dp on all nine rows (0.8000/0.4000/0.3000/0.2800 on the merge
rows). So **a token removed by merging frees exactly as many cache bytes as one removed by
pruning** — which is what licenses the equal-M comparison at all. Without this control, "merging
to M=1920 saves what pruning to M=1920 saves" would be an assumption sitting underneath every Q6
pair in run 13.

Three deliberate design choices, each of which was nearly a decorative check:

1. **The accuracy numbers are read off run 13's per-image arrays at runtime, not typed in.**
   `run13_merge_cost()` re-bootstraps from `run 13/ablation_selection.json` (20 000 resamples,
   document as the unit, seed 0). Hardcoding −3.86 would have made the JSON a transcript of this
   file rather than a check on it — the same reason M1's prune rows read D12's JSON.
2. **The contrast is selection-held-fixed, NOT run 13's `meta.q6_token_matched`.** Q6's pairs vary
   two things at once (how many tokens the router picks *and* whether the remainder is merged), so
   a Q6 delta is not the cost of the merger. Same `keep`, same `select_mode='router'`, same
   `tome_split`, merge on vs off, is. Recorded in the JSON as `merge_accuracy_cost.contrast` so
   the distinction survives being read by someone who did not make it.
3. **"Free" is asserted in both directions.** Control (10) requires the headline row's CI to
   include zero **and** requires the m=0.40 row's CI to exclude zero *and* be negative. Only the
   first half would have made "free" a word this script applies to whatever it happened to
   measure; the second half is what gives the label teeth. Note the asymmetry it protects
   against: a *wider* CI makes the "free" test easier to pass, so a non-vacuity partner that fails
   under wide CIs is the only thing standing between this and a null bought with noise.

Two further controls added for the same reason:

- **(8) the merger must actually have run.** Every byte figure on a merge row is *identical to its
  keep's prune-only row* if `merge_ratio` was silently ignored — and `merge_ratio` being silently
  ignored or silently inherited is this project's single most repeated defect (twelve callers once
  inherited `merge_ratio=0.20` from a constructor default and nothing failed). So each merge row
  is asserted **strictly below** its prune-only twin in both tokens and bytes.
- **Row lookup is explicit, not positional.** With merge rows in the table, `next(r for r in ROWS
  if r['keep_ratio'] == 1.00)` returns whichever of the **two** keep=1.00 rows came first.
  `row_at(keep, merge)` raises unless it matches exactly one row. This is the same key-collision
  defect PATCH G had to fix in cell 15, and it is silent in exactly the same way. The self-KV
  non-monotonicity control was narrowed to `PRUNE_ROWS` for the mirror-image reason: `ROWS` is now
  ordered prune-then-merge, so its keep column is not monotone at all and the test would have
  passed because of the **row order** rather than because of the physics.

**One number to read carefully, and the grep that found it is the lesson.** This file now carries
**three** different 95% CIs for the same −3.86 quantity, and I only noticed because I grepped for
the digits instead of the topic:

| filed at | CI | res | where |
| --- | --- | --- | --- |
| run 13 result table | [−7.54, −0.35] | 3.59 | the run-13 section and changelog (c) |
| run 14 launch checklist | [−7.47, −0.38] | 3.55 | the launch table and the trade-off watch |
| this extension | [−7.45, −0.30] | 3.57 | `kv_memory_local.json` / `kv_memory_merge.log` |

**None of them supersedes the others and none is an error.** The mean **−3.86 is deterministic**;
the *endpoints* are bootstrap draws, and all three agree to within **±0.05**, exactly the
resampling noise run 13's stability check measured (12/12 seeds exclude zero). Each `res` is the
half-width of its own interval, so all three are internally consistent too. What is a defect is
that **two of these were filed on 2026-09-18 with no note**, leaving a reader to discover a
three-way discrepancy in a number the project headlines. Standing rule, since this is the second
time a bootstrap endpoint has been quoted as if it were exact: **when a CI endpoint lands within
its own resampling noise of zero, quote the seed alongside it, or quote the rank test instead
(Wilcoxon p = 0.0048) — the rank test does not move with the draw.**

The substantive conclusion is unaffected in all three: the interval excludes zero and is negative,
which is why m=0.40 is not the headline.

**Scope limits unchanged, and they are the same ones, not new ones:** cross-attention KV only;
fp32 on CPU (every byte figure halves at fp16/bf16, the percentage is invariant); **no
encoder-side saving** — the frozen Swin computes all 4800 tokens before the router *and* before
the merger, so the merge stage adds no encoder benefit either; not latency (D11: 1.04×); self-KV
is driven by *generated* length and is untouched by any of this. **52/52 controls, all PASS**
(`results/kv_memory_merge.log`).

**And a counter, because this file has been burned by the absence of one.** `eval_kv_memory.py`
now increments on every `say()` and writes `controls_run` / `controls_failed` into the JSON. It
previously wrote only `controls_passed: true` — a boolean AND, equally true of 52 controls passing
and of 1 passing while 51 were skipped by a `continue`. That is exactly how **"17 of 17"** got
into this file, eyeballed off a log once and copied three times before the 2026-09-09 audit found
the real figure was 25. I then did it again here: I typed **"38 controls"** into the paragraph
above from memory before checking, and the measured number is **52**. The counter is the fix for
the class, not just for the instance. Verified non-vacuously: the script's self-report (52/52) and
an independent `grep -c '\[PASS\]'` over the log agree, so the counter counts printed controls
rather than counting itself.

**Artifact note.** `results/kv_memory_local.json` is now a **superset** — the five prune-only rows
are byte-for-byte the values in M1's table above, plus the four merge rows, so every existing M1
citation still resolves against it. The 2026-09-06 `results/kv_memory_local.log` is **deliberately
not overwritten**: it is what the 2026-09-09 audit cites for "25 of 25", and replacing it would
have quietly invalidated that citation. The new run logs to `results/kv_memory_merge.log`.

**Where the project actually is.** ***Historical as of 2026-08-31 — for the current
position see "THE FOUR CLAIMS THIS PROJECT CAN MAKE" at the top of this file.*** Run 8 is
a genuine success: the router is
sign-correct and reads 77.80% word recall on 35% of the visual tokens. Three things
qualify it, all found by D3 on 2026-08-31 by reading artifacts that already existed:

1. **It is not an efficiency result.** ~~−65% tokens buys −7% wall-clock~~ ~~**−4.1%
   (run 9); −50% tokens buys −3.0%**~~ — **both struck; D11 measures 1.04× at 5× fewer
   tokens, i.e. latency flat within noise at every budget, and M1 supplies the honest
   replacement (cross-KV −65.0% at keep=0.35). See claim 3 at the top of the file.**
   Because pruning is post-encoder. Accuracy-vs-token-
   count is what exists. Run 9 also shows *why* it is this small and not merely small:
   `mean_gen_tokens` **rises** as the budget falls (251 at keep=1.00 → 270 at 0.50 → 271 at
   0.35, `len_ratio_pct` 98.6% → 107.8% → 106.8%). Pruning cuts the cost *per* decoder step
   while increasing the *number* of steps, and the two nearly cancel. That is a second,
   independent reason the speedup is capped, and unlike the post-encoder one it would
   survive moving the router before the encoder.
2. **"Beats the ink oracle" is probably co-adaptation**, not selection quality — the
   curve peaks exactly on the trained `keep_ratio` and the oracle dominates on both
   proxies while losing. **Strengthened by run 9/D6:** the margin over the oracle moved
   from +5.38 to +2.74 at keep=0.50 and *reversed* to −1.75 at keep=0.35 on a
   loss-config change alone. Whatever that margin measures, it is not stable enough to
   be selection quality.
3. **D2's min-coverage acceptance gate is withdrawn.** Falsified/inconclusive at
   n=50, and retired outright by an equal-coverage/29-pt-recall-gap counterexample.
   **Run 9 confirms the withdrawal was right:** the router wins at keep=0.50 with
   `mean_min_line_cov` 0.601 against the oracle's 0.955.

A fourth, from D4, cuts the other way: **the loss that produced the sign-fix is
mis-specified** (a probability fed to `binary_cross_entropy_with_logits`, attenuating the
gradient up to 112× on precisely the tokens it is most wrong about). So 77.80 is a
**floor** on what ink supervision can reach, not a ceiling — one of the few pieces of good
news in this batch, and the cheapest open action in the file. **Actioned 2026-08-31 (F1):
fixed in the generator and covered by a 6/6 execution check, but never run on a GPU, so
"floor" is still a prediction rather than a demonstrated headroom.**
**~~Floor~~ — FALSIFIED by run 9 (2026-09-01).** The fix worked mechanically (retained ink
0.790 → 0.922) and accuracy went *down* 0.54 at keep=0.50 and 1.94 at keep=0.35. 80.17 was
approximately the *ceiling* of the ink objective, not a floor. The good news in this batch
is now D6's method, not D4's headroom.

**Settled (run 6).** The bottleneck was **under-generation caused by
`repetition_penalty=1.3`**, a hyperparameter tuned for aggressive pruning that
outlived its justification through four runs with pruning OFF. Fixed: cell 7 now
defaults to `repetition_penalty=1.0`, keeping `no_repeat_ngram_size=3` as the
repetition-collapse guard. Applied by
`scripts/patch_notebook_decode_default.py`, verified by
`scripts/verify_decode_default.py`.

~~Prime suspect: trigram blocking is actively wrong for full-page forms that
legitimately repeat trigrams.~~ **Falsified.** With rp=1.3 the trigram blocker
was a bit-exact no-op; removing it changed nothing. The reasoning was plausible
and pointed at the right *cell*, but the wrong *knob* — which is precisely why
the ablation varied both independently instead of just fixing the suspect.

**The real accuracy ceiling is 77.74 recall / 64.70 char acc / 53.05 order /
NED 0.353**, on run-5 weights, pruning OFF. That — not 50.56 — is the anchor the
accuracy-vs-tokens curve hangs off.

~~Minor, tracked but deliberately unfixed: generated JSON is malformed.~~
**Resolved as a side effect** — same root cause, 0.0% → 82.0% valid JSON. The
remaining 18% is unexplained and unmeasured beyond the percentage; predictions
are still never repaired, since repairing them would score the fix, not the model.

~~**Open question for the sweep.** The original comment's claim — that aggressive
pruning induces repetition collapse — was never tested, only inherited, and every
run so far has had pruning OFF. It may be true. If `hit_max_length_pct` climbs at
`keep_ratio` 0.5/0.35, collapse is real; the response is to tighten the n-gram
guard, **not** to reintroduce the repetition penalty, which costs 27 pts of recall
to buy length control that `nrns` already provides for free.~~

**ANSWERED — the inherited claim is FALSIFIED (2026-08-31, from runs 7–8's existing
rows; no new run needed).** Across all **30** swept rows, `hit_max_length_pct` never
exceeds **4.0%**, its median is **0.0**, and **no row exceeds 10%** — against the **22%**
that run 6's `both off` row produced when collapse was genuinely occurring. There *is* a
monotone trend in the predicted direction, and it is negligible: mean hit rate by budget
is 1.00→0.0%, 0.75→0.0–0.5%, 0.50→0.7%, 0.35→1.0%. So pruning at these budgets does
**not** induce repetition collapse; `no_repeat_ngram_size=3` holds on its own, and the
standing ban on `repetition_penalty > 1.0` needs no revisiting. (Side observation, and a
check that the metric is live rather than stuck at zero: run 8's `len_ratio_pct` bottoms
out at **32.0%** on the collapsed `negated` row — a broken *selection* under-generates,
which is the opposite failure from a broken decode, and worth knowing as a signature.)
This is the third open question runs 7–8 had already answered in an artifact nobody read;
see D3.

**New blocker (Diagnostic D1).** The remaining obstacle is not GPU time — it is
that the router ranks blank paper above text, retaining 34–38% of a page's ink
where random pruning retains 50%. Pruning by that ranking is worse than pruning at
random, so the accuracy-vs-tokens curve cannot be produced from run-5 weights and
be honest at the same time. Training with pruning ON moved from "open design
decision" to **required**. Two free experiments (negate the score; ink-oracle
upper bound) come first — see Pending 1b.

**RESOLVED by Run 7 (2026-08-30) and Run 8 (2026-08-31).** The router was retrained with
pruning ON (keep=0.5). Run 7 showed STE-only training left it **sign-inverted** (forward router
18.80 recall; only the *negated* score worked). Run 8 added an **ink-BCE saliency loss** supervising
the router with a free text proxy — the forward `router` is now correctly signed
(80.17 recall at keep=0.50, 77.80 at keep=0.35), and negation-at-inference is obsolete.
~~and beats the ink oracle at every keep_ratio~~ — see the co-adaptation table in the
run 8 section; that comparison is confounded. Remaining open items are no longer just
ToMe: **Pending 5–8** (co-adaptation test, provenance, the wrong Q5 note, the efficiency
scoping) — **4, 9 and 10 are done in code (F1, F2)**, though none of the three has been
executed on a GPU. Note the loss that achieved this is itself mis-specified (D4), so the
sign-fix is a floor; the fix exists but has not been run.

**Venue decision (2026-08-29).** All three remaining eval questions (1b, 1c, 1d) are
now built into the **notebook**, not the local scripts, and the local n=50 run was
killed to pay for it. Reasoning: local CPU generation measured at **~45 s/image**
(not the ~15 s inferred from one short FUNSD doc — that estimate was wrong by 3×), so
one row is ~38 min and 1c's sweep alone is 12+ hours. Pending 1a needs a GPU
regardless. The port cost ~40 min and buys all 15 rows in one GPU session. Cost of the
decision, stated plainly: the killed run had reached 30/50 images of row 1 of 5 and
wrote its JSON only at the end, so **nothing was recoverable** — which is why the new
notebook cell writes results after *every* row. See Phase 2d.

## Diagnostic D13 (2026-09-22, extended 2026-09-23, local, <60 s, 36/36 controls) — the ToMe blocker is the **instrument**, not the merger

`scripts/diagnose_merge_power.py`, log at `results/merge_power_local.log`. No GPU, no
model load, no network — it re-derives everything from the per-image arrays already in
`run 13/ablation_selection.json` and `run14/ablation_selection.json`.

**The question it was built for.** Three runs (12, 13, 14) returned UNDERPOWERED as the
modal verdict on the merge axis, and the working assumption across those sessions was
that something about ToMe was wrong. Nothing about ToMe is wrong. The merger executes
(`enc 1440` = 2400 − 960 on every run-14 epoch), it is correct
(`verify_tome_merge_port.py` **89/89** with non-vacuity controls, `test_tome_correctness.py`
**13/13**, token match hard-asserted per image), and it produced the project's cleanest
merge result. **The effects it produces are simply the same size as the harness's
resolution**, and that makes UNDERPOWERED a structural guarantee rather than a finding.

### Calibration first — the published figures reproduce from the raw arrays

Nothing below is readable unless the variance estimate is right, so the script's first
section re-derives five published `(mean, res)` pairs and **exits 1** if any misses.
`res` is the 95% CI half-width.

| contrast | mean | published | res | published |
|---|---|---|---|---|
| run13 m0.40−m0.00 | −3.86 | −3.86 | 3.59 | 3.57 |
| run13 m0.20−m0.00 | +0.54 | +0.54 | 3.13 | 3.07 |
| run14 m0.40−m0.00 | −0.28 | −0.28 | 3.98 | 3.95 |
| run13 M=1920 mrg−prn | +2.86 | +2.86 | 3.16 | 3.10 |
| run13 M=3840 mrg−prn | +3.12 | +3.12 | 2.92 | 2.90 |

Means to ≤0.02, resolutions to ≤0.06 (normal-approx vs bootstrap). The arrays and the
file agree.

### 1. The instrument, stated plainly

Per-document sd of the paired recall delta is **11–13 pts**. At n=50 that is res
**2.9–4.3**. The effects ToMe produces are **0.5–3.1 pts**. Effect size and resolution
are the same size.

> **The number that should have been noticed three runs ago:** M=1920 merge-vs-prune —
> the single question ToMe exists to answer — came in at **+2.86 with res 3.16**, i.e.
> CI **[−0.08, +6.17]**. To resolve its own observed effect it needed **n ≥ 62**. Run 13
> had **50**. It missed by **twelve documents** and 0.08 pts of CI, and was filed as
> UNDERPOWERED alongside everything else.

AGENTS.md already contained the binding constraint in one line — *"`n` is not a knob:
50 **is** FUNSD test"* — but it was written as a caveat on run 14's primary rather than
as the project-level blocker it is.

### 2. Where the variance lives — not document length

The m=0.40 paired deltas, sorted, are not remotely normal:

```
-57 -25 -22 -22 -18 -17 -16 -12 -11 -11 -8 -8 -8 -8 -7 -7 -6 -4 -4 -4 -4 -4 -3 -3 -3
 -2 -2 -2 -2 +0 +0 +0 +0 +0 +0 +1 +1 +1 +2 +2 +2 +2 +4 +5 +6 +6 +7 +7 +14 +44
```

- **5 of 50 documents carry 75.6% of the total sum-of-squares**, two of them (−57, +44)
  dominating. 6 documents change by exactly zero; 12 move more than 10 pts.
- Median **−2.72** against a mean of −3.86 — the mean is being dragged by the tails.
- **It is not document length.** CUPED on `n_text_rows` (already stored per image) buys
  **+0.0% to +3.7%**. That lever does not exist, which is worth recording so nobody
  spends a session rediscovering it.

The consequence: **the pre-registered bootstrap-on-means is the least powerful
estimator available for this data**, and it is the one designated to govern.

### 3. A robust estimator buys ~30% for free — and it is discriminating, not permissive

10% trimmed mean, **Tukey–McLaughlin** SE, percentile bootstrap (B=20 000, seed 0;
endpoints are one draw, per this file's standing caveat).

| contrast | mean | res | CI | ≠0 | trim | res | CI | ≠0 |
|---|---|---|---|---|---|---|---|---|
| 13 m=0.40 vs m=0.00 | −3.86 | 3.59 | [−7.44, −0.33] | **yes** | −3.23 | 2.47 | [−5.85, −0.97] | **yes** |
| 13 m=0.20 vs m=0.00 | +0.54 | 3.13 | [−2.37, +3.81] | no | **−0.65** | 1.72 | [−2.45, +1.77] | no |
| 13 M=3840 mrg−prn | +3.12 | 2.92 | [+0.20, +6.02] | **yes** | +2.23 | 2.09 | [+0.59, +4.58] | **yes** |
| 13 M=1920 mrg−prn | +2.86 | 3.16 | [−0.08, +6.17] | no | +1.35 | 2.68 | [−0.95, +4.36] | no |
| 13 M=1344 mrg−prn | −0.22 | 3.16 | [−3.47, +2.89] | no | −0.21 | 2.53 | [−2.72, +2.55] | no |
| 13 M=1440 mrg−prn | −1.29 | 3.55 | [−4.77, +2.19] | no | −1.65 | 2.09 | [−3.82, +1.11] | no |
| 14 m=0.40 vs m=0.00 *(null ctl)* | −0.28 | 3.98 | [−4.51, +3.41] | no | −0.17 | 2.23 | [−2.29, +2.30] | no |
| 13 SABOTAGE ckb−rankpar *(null ctl)* | −0.29 | 2.94 | [−3.09, +2.77] | no | −0.90 | 2.10 | [−3.12, +1.17] | no |
| 14 SABOTAGE ckb−rankpar *(null ctl)* | −0.88 | 4.34 | [−5.23, +3.32] | no | −0.24 | 2.60 | [−3.40, +2.26] | no |
| 13 NEGATED−router *(huge ctl)* | −63.98 | 5.31 | [−69.17, −58.67] | **yes** | −64.56 | 6.09 | [−70.47, −58.56] | **yes** |

The controls are what make this readable as an instrument change rather than a
convenient one: **every published null stays null** under trimming, the −64 pt control
still resolves, and verdicts are **stable across trim fractions g ∈ {0.05, 0.10, 0.15}
with zero flips**.

> ⚠ **Both of those last two clauses were sharpened on 2026-09-23 (D14) and mean less than
> they appear to.** (i) *"the −64 pt control still resolves"* is true in the sense of
> **excluding zero** — by ~10σ, as the table's own half-width of **6.09** shows — and false
> in the sense of being **estimated tightly**. It cannot satisfy an absolute-width gate at
> n=50 or at n=500 (≈1.92), so it must not be used to calibrate one. (ii) *"stable across g
> with zero flips"* is about **verdicts**, and verdict-stability is not estimate-stability:
> on run 14 m=0.40 the trimmed estimate reads **+0.22 / −0.17 / −0.24** at g = 0.05 / 0.10 /
> 0.15. All three are null, so the verdict column is honestly unchanged — but the **sign**
> is not, and a rule that reports a point estimate alongside its verdict lets g choose
> whether the sentence says merging gained or cost. Pin g in T1 for that reason, not because
> the verdicts are unstable.

> **It cuts against this project's own claim, which is the best evidence it is not
> motivated.** Trimming *tightens the m=0.40 cost* to [−5.85, −0.97], and it flips
> **m=0.20's point estimate from +0.54 to −0.65**. Both are nulls, so "no measured cost"
> survives — but **"free" is not sign-robust**, and claim 3 should say so (task T3).

### 4. What n would actually be needed

Same variance, more documents. `n` for the 95% CI half-width to reach a target:

| contrast | sd | 3.0 pts | 2.0 pts | 1.5 pts | 1.0 pts |
|---|---|---|---|---|---|
| | | mean / trim | mean / trim | mean / trim | mean / trim |
| 13 m=0.40 vs m=0.00 | 12.94 | 72 / 34 | 161 / 77 | 286 / 136 | 644 / 305 |
| 13 m=0.20 vs m=0.00 | 11.28 | 55 / 17 | 123 / 37 | 218 / 66 | 489 / 148 |
| 13 M=3840 mrg−prn | 10.55 | 48 / 25 | 107 / 55 | 191 / 98 | 428 / 219 |
| **13 M=1920 mrg−prn** | 11.40 | **56 / 40** | **125 / 90** | 222 / 160 | 500 / 360 |
| 13 M=1344 mrg−prn | 11.40 | 56 / 36 | 125 / 81 | 222 / 143 | 500 / 321 |
| 13 M=1440 mrg−prn | 12.81 | 71 / 25 | 158 / 55 | 281 / 98 | 631 / 219 |

**Reading:** a robust estimator alone does not rescue the merge axis — resolving a 2-pt
effect still needs ~55–90 documents. Roughly **n ≈ 500** (a pooled corpus) puts res at
**≈0.9–1.3 pts**, which resolves everything ToMe can do, *including* the m=0.20 "free"
claim as a **tight null** rather than an absence of evidence.

### Two self-corrections, which are the reusable part

1. **The obvious trimmed-mean SE is wrong in the permissive direction.** The first pass
   used `stdev(trimmed values)/sqrt(len(trimmed))` — the natural thing to write. It is
   **33% too small**, and it produced a RESOLVED verdict on the M=1440 pair
   (res 1.48, CI excluding zero) that the correct Tukey–McLaughlin SE **deletes**
   ([−3.82, +1.11]). The reported gain fell from "~55%" to "~30%" once fixed.
   `res_trimmed_naive()` is kept in the script purely so a control can assert the gap.
   *A wrong standard error does not look like an error; it looks like a better result.*
2. **The control "trimming is tighter everywhere" failed 9/10, and was right to.**
   Trimming is **wider** on the `negated` control (5.31 → 6.09), because that contrast
   is a compact bulk near −64 with no outliers and a trimmed mean only wins on heavy
   tails. The fix was to scope the assertion to the merge contrasts **and add the
   exception as its own control** — an estimator that were tighter everywhere would be
   measuring nothing. [[green-checks-need-the-same-suspicion]]

### Found while building this

**`src/model.py:248` computes merged coordinate centroids and throws them away.**
`compressed_tokens, final_coords = self.tome_merger(...)` — `final_coords` is never read
again, and the `generate()` path at `:372` already discards it as `_`. Only
`compressed_tokens` reaches the decoder. So the *"w/ 2D coord centroids"* in this file's
architecture diagram describes a path that is not wired, and the merger hands the decoder
no spatial signal at all. Consistent with the existing note that ToMe's coords "are never
used"; recorded here because the diagram still advertises them. Filed as T8.

**`word_order` is stored only as a row aggregate in runs 13/14, and is not recoverable.**
Checked 2026-09-23 while scoping T1's multiplicity rule. Both runs' `ablation_selection.json`
`per_image` records hold `gen_tokens, i, mean_line_cov, min_line_cov, n_text_rows, ned,
p10_line_cov, recall, retained_ink, tokens`; `word_order_pct` exists per *row* only.
This is the **opposite** of the charAcc case. charAcc collapsed into NED because
`character_accuracy_pct = (1 − mean(ned)) × 100` is an affine map of a stored field — the
quantity was redundant. Word order is not redundant and not stored:
`compute_word_metrics` (`src/evaluate.py:44`) computes it as
`1 − editdistance(pred_words, gold_words) / max(|pred|,|gold|)` from the raw predicted and
gold word *sequences*, and neither sequence is written to disk. `recall` cannot supply it
(it is set-valued and order-blind — that is explicitly its job) and `ned` cannot either
(character-level, over the serialised JSON string). Two consequences, both already filed:
T3 can back-score **two** of the three quantities, and the three-quantity primary is first
exercisable at **run 17**.
**Where the run-17 guarantee actually lives — checked, because the obvious answer is the
wrong one.** It is *not* "the checked-in `kaggle_pruning_run.ipynb` has the field." That
notebook is generated, and T4's DONE-WHEN requires re-verifying against a **regenerated**
one, so a field present only in the committed copy would vanish on the next regeneration
with no symptom. The guarantee is that **`scripts/make_kaggle_pruning_notebook.py` injects
it as patch G3b (`:1061`) behind an asserted anchor** (`expected 1 hit, found …`), so a
regeneration either carries the field or dies loudly. That is the load-bearing fact.
**Verified by executing it, not by reading it (2026-09-23).** Backed up the committed
notebook, ran `python scripts/make_kaggle_pruning_notebook.py` (exit 0), and checked three
things: the regenerated `per_image` record carries `word_order` (11 keys: `i, tokens,
recall, word_order, ned, retained_ink, gen_tokens, min_line_cov, p10_line_cov,
mean_line_cov, n_text_rows`); the regenerated notebook is **byte-identical** to the
committed one (sha256 prefix `2d35b7e0bc14e207` before and after), so there is **no drift**
between the committed generated artifact and its generator; and the backup restored to that
same hash. The idempotence result is the reusable one — it means a future regeneration
during T4 changes nothing silently, which is the only reason "verify by regenerating" is
cheap enough to be worth mandating.
Two related notes so nobody patches the wrong file: the **canonical**
`kaggle_token_pruning_ocr.ipynb` does *not* carry per-image `word_order` — correct and
expected, it is not the notebook that runs (see *"Do not run
`kaggle_token_pruning_ocr.ipynb`"*), and G3b is a generator patch by design. And its
`per_image` record also lacks **`tokens`**, which the generated one has; runs 13/14's
artifacts carry `tokens` but not `word_order`, i.e. they match *neither* notebook's present
state — they were produced by the generator as it stood before G3b. So T4's
*"the per-image arrays carry `word_order`"* clause is satisfied by the generator as it
stands and needs **verifying, not building** — verify it by regenerating, not by grepping
the committed notebook.
Check whether an unstorable metric is derivable from a stored one **before** planning
around its absence — and note the corollary bites here in reverse, since charAcc *was*
derivable and therefore was never independent evidence in the first place.

### 5. The tail — what BOTH location estimators hide (added 2026-09-23)

Section 3's ~30% resolution gain is real, and section 4's required-n table is the reason
to want it. This section is the reason **not to buy it with the trimmed mean alone**, and
it was found by asking what the trim throws away rather than what it saves.

| contrast | mean | trim | p10 | **min** | \|z\|max | kurt | matched-null \|z\| |
|---|---|---|---|---|---|---|---|
| 13 m=0.40 vs m=0.00 | −3.86 | −3.23 | −16.84 | **−56.98** | 4.11 | 6.87 | 2.33 |
| 13 m=0.20 vs m=0.00 | +0.54 | −0.65 | −6.67 | **−22.45** | 4.20 | 5.60 | 2.33 |
| 13 M=3840 mrg−prn | +3.12 | +2.23 | −2.15 | **−38.95** | 3.99 | 5.44 | 2.33 |
| 13 M=1920 mrg−prn | +2.86 | +1.35 | −6.25 | **−15.56** | 3.84 | 3.48 | 2.33 |
| 13 M=1344 mrg−prn | −0.22 | −0.21 | −12.36 | **−42.86** | 3.74 | 3.13 | 2.33 |
| 13 M=1440 mrg−prn | −1.29 | −1.65 | −11.11 | **−47.67** | 3.62 | 3.69 | 2.33 |
| 14 m=0.40 *(null ctl)* | −0.28 | −0.17 | −9.68 | **−72.34** | 5.01 | 11.30 | 2.33 |
| 13 SABOTAGE *(null ctl)* | −0.29 | −0.90 | −12.26 | **−22.45** | 3.84 | 4.46 | 2.33 |
| 14 SABOTAGE *(null ctl)* | −0.88 | −0.24 | −14.14 | **−55.10** | 3.47 | 4.04 | 2.33 |

> **Run 14's primary is published as "no measured cost" and contains a page that lost
> 72.34 points.** The trimmed mean of that contrast is −0.17. Both statements are true
> and they are about the same 50 documents.

Three things make this a finding rather than an anecdote:

1. **The extremity is measured against its own null, not against a threshold chosen
   after the fact.** `normal_like()` builds a deterministic light-tailed sample with the
   *same* n, mean and sd (evenly-spaced normal quantiles — no RNG, no seed to tune). Its
   worst document sits at **2.33 sd** on every contrast; the real data's sits at
   **3.47–5.01**, a **1.49–2.15×** margin. Without that null the check would be
   decorative, because the largest of n draws is always the largest.
2. **The trimmed mean is not merely less sensitive to the tail — it is exactly blind to
   it.** Push the single worst document 25 pts *further* down and the trimmed mean is
   unchanged to the last bit on **6/6** merge contrasts, because that document was never
   in the average. The plain mean moves by 25/50 = 0.50 — which is arithmetic, so the
   control asserts the *material* version instead: on M=1344 that 0.50 is **225% of the
   contrast's own effect**. One page degrading further more than doubles the headline,
   and the robust estimator does not notice.
3. **The tail is not a restatement of the location.** Ranking the contrasts by worst-case
   gives a different order than ranking by mean, so a tail rule carries information the
   location statistic does not.

**Why this bears on T1 and not just on prose.** An accuracy-*preservation* claim — "merging
20% is free" — is a claim about every document, not about the corpus average. Both
candidate estimators answer the average question:

- the **plain mean** lets one −72 pt page sit inside a published null, because 72/50 = 1.4 pts
  of movement is inside the ±4 pt resolution;
- the **trimmed mean** deletes that page from the estimate outright.

So the ~30% power gain in section 3 is **not free either** — it is bought with the exact
documents an OCR reliability claim is about. That does not make trimming wrong; it makes a
location-only rule wrong. **T1 must therefore pin a tail statistic alongside the location
statistic, not choose between mean and trimmed mean and stop.** Note also the direction this
cuts: it is *harder* on merging than the current rule, since every merge contrast has a
catastrophic document and the present claim set does not mention one.

### What D13 does and does not license

**Does:** re-order the queue. Pending 16 and 17 are sound designs blocked by a problem
neither of them addresses — building the missing `keep=0.30, merge=0.0` arm fixes the
*confound* and leaves the *power* untouched, so at n=50 the predicted outcome of 4–4.5
GPU-hours is a correctly-designed fourth UNDERPOWERED. Fix the instrument first. See the
TODO queue at the top of this file.

**Does not:** license choosing an estimator after seeing an effect. This is an input to
**Pending 18 / T1** and the rule must be written before run 17 sees a number; the
justification on record is the variance structure in section 2, never the sign of a
contrast. It also does not make the trimmed mean "the" effect — it is a different
estimand, as the m=0.20 sign flip shows.

**And after section 5, it specifically does not license two things it would have on
2026-09-22:**

- **Adopting the trimmed mean as the *sole* estimator.** Sections 2–4 argue for it on
  variance structure and that argument still stands; section 5 shows the statistic it
  recommends is *exactly blind* to the documents an accuracy-preservation claim is about.
  A location-only rule is therefore incomplete regardless of which location statistic wins.
  T1 pins a tail quantity too.
- **Restating run 14's merge null as "no measured cost" unqualified** — including in T3,
  which is the task that rewrites claim 3. The contrast contains a −72.34 pt page. The
  existing T3 caveat about the m=0.20 sign flip is necessary but **not sufficient**; the
  claim also needs the tail. Both estimators hide it, so this is not fixed by choosing
  between them.

Section 5 does **not** overturn sections 2–4: the heavy tail is *why* trimming helps and
*why* trimming is insufficient — one measurement, two consequences, and the project had
only written down the flattering one.

---

## Diagnostic D14 — T1 is not an estimator choice (2026-09-23, local, no GPU, 20/20 controls)

**Status: this section is the input to T1, and it invalidates T1's original scope.** T1 was
written as "pre-register the estimator (bootstrap-on-means vs Wilcoxon vs trimmed mean)
before run 17." That framing survives contact with the artifacts for about as long as it
takes to count the rows on disk. **The estimator is the smallest unpinned degree of freedom
in the design, and it is the only one T1 was going to pin.**

Every number below was recomputed from the raw `per_image` arrays in
`run 13/ablation_selection.json` and `run14/ablation_selection.json` by
`scripts/diagnose_analysis_dof.py` (**20/20 controls, exit 0**,
`results/analysis_dof_local.log`) — not from any summary table in this file.

### 1. Seven degrees of freedom, each individually decisive

A "degree of freedom" here means: a choice that is currently *unwritten*, that a
well-intentioned analyst could resolve either way after seeing the data, and whose swing is
comparable to or larger than the ~1.0 pt effect the design is trying to detect.

| # | Unpinned choice | Measured swing | How I checked it |
|---|---|---|---|
| 1 | **Which contrast is primary** | **5.08 pts** | run 13 has **7** selection-matched and **12** budget-matched (merge, non-merge) pairs across 4 budgets. Worse, the *same four words* name two of them — §1b. |
| 2 | **Which split is "the merge arm"** | **+1.12 pts** | At M=1920, both splits are already on disk: checkerboard trim **+1.35**, rank_parity trim **+2.47**. Same budget, same corpus, same checkpoint. |
| 3 | **Units / direction per quantity** | sign inversion | See §2 — a `min(delta)` tail rule on stored `ned` ranks the −64 pt catastrophe as the **safest** row in the sweep. |
| 4 | **Trim fraction g** | sign flip | run 14's **published primary** (m=0.40 vs `keep=0.50 router`): g=0.05 → **+0.22**, g=0.10 → **−0.17**, g=0.15 → **−0.24**. Contrast-specific: the token-matched pairing reads +6.09/+4.91/+4.46 and does *not* flip. |
| 5 | **DiD estimand order** | **+0.81 pts** | See §3 — trimmed means are not additive, so "trim then difference" ≠ "difference then trim". |
| 6 | **Tie convention** | count 4 vs 5 | run 13 m=0.20 has **exactly one** document at delta = −10.000000 — under *both* §1b pairings. A `count(d < −10)` tail rule gives 4 / `<=` gives 5 on the published primary (3 / 4 token-matched). Live *now*, on the headline row. |
| 7 | **Corpus composition** | see §4 | The trim's discard set at pooled n=500 is exactly the size of FUNSD's whole contribution. |

Items 1, 2 and 7 are the ones that matter most, because they are the ones where the *existing
artifacts already contain both answers* — no new run is needed to shop, only a choice of
which row to quote.

### 1b. "Run 14, m=0.40" names two contrasts, 5.08 pts apart — found by accident

This is the strongest item in the set and the one I was not looking for. I first measured
§1.4 and §3 with an ad-hoc probe, then wrote `scripts/diagnose_analysis_dof.py` to make the
numbers reproducible — and **the script disagreed with the probe.** Neither was wrong. They
had silently chosen different control rows for the same named contrast:

| what "run 14, m=0.40" can mean | control row | tokens | trimmed | mean |
|---|---|---|---|---|
| **same keep fraction** — *run 14's published primary* | `keep=0.50 router` | 2400 → 1440 | **−0.17** | −0.28 |
| **token-matched** — merge vs prune at equal M | `keep=0.30 router TWIN` | 1440 = 1440 | **+4.91** | +5.78 |

**A −0.17 pt null and a +4.91 pt gain from the same four words** — a 5.08 pt spread, 5× the
effect the design is trying to detect. Both are legitimate estimands answering different
questions (*"what does adding merging cost?"* vs *"at equal budget, does merging beat
pruning?"*), and the pre-registration names neither. This file's own prose uses "run 14's
m=0.40 primary" for the first and "merge-vs-prune" for the second without ever saying they
are different rows.

The mechanism is worth stating plainly: **this ambiguity produced a contradiction inside a
single session between two of my own measurements, and it took a third measurement to
establish that neither was mistaken.** That is what row-shopping looks like in practice — not
fraud, just two readings of the same phrase. It is also why §1.4 is contrast-specific: g
flips the sign on the published primary and does not flip on the token-matched pairing, so
"pin g" is not even well-defined until the contrast is named.

### 1c. The freedom was already exercised: runs 13 and 14 won on *disjoint* rows

§1 and §1b measure how much latitude the rule leaves. This section is the one that
matters, because it shows the latitude was **already spent** — not by a hypothetical
reader, but by this project, twice, in the two runs already on disk.

The verdict rule pre-registered for Q6 (this file, the table under *"Predicted
resolution"*) is **disjunctive and asymmetric**:

| verdict | pre-registered criterion | arity |
|---|---|---|
| **MERGING WINS** | CI excludes 0 with `Δ > 0` on **≥1 ink pair** | **1 of 6** |
| **MERGING LOSES** | CI excludes 0 with `Δ < 0` on **≥1 router pair and ≥1 ink pair** | 2 of 6 |
| **INDISTINGUISHABLE** | **every** pair's CI includes 0 **and every** pair's `res ≤ 3.0` | **12 of 12** |

`scripts/diagnose_analysis_dof.py` §9 reconstructs that criterion from the raw
per-image arrays (`mean ± res` reproduces the shipped CI column to ~0.01) and scores all
six pairs in both runs:

| pair | run 13 | run 14 |
|---|---|---|
| M=3840 router | **+3.12  [+0.19, +6.04]  WINS** | +0.81  [−2.27, +3.90] |
| M=1920 router | +2.86  [−0.30, +6.02] | +1.46  [−2.89, +5.81] |
| M=1344 router | −0.22  [−3.38, +2.94] | **+4.22  [+0.06, +8.37]  WINS** |
| M=1440 router | −1.29  [−4.84, +2.26] | **+5.78  [+0.88, +10.69]  WINS** |
| M=1920 ink | +2.28  [−0.46, +5.01] | −0.13  [−3.06, +2.80] |
| M=1344 ink | **+4.06  [+0.24, +7.87]  WINS** | +1.43  [−2.50, +5.36] |

**Both runs declared MERGING WINS. The two winner sets are disjoint — not one pair.**

| | run 13 | run 14 |
|---|---|---|
| winners | `M=3840 router`, `M=1344 ink` | `M=1344 router`, `M=1440 router` |
| intersection | **∅** | |

And the movement is symmetric in the worst way: every run-13 winner regressed toward
zero in run 14 (+3.12 → +0.81, +4.06 → +1.43), while both run-14 winners had been
**negative** in run 13 (−0.22 → +4.22, a +4.44 swing; −1.29 → +5.78, **+7.07**). A
7.07 pt cross-run swing on a pair the rule then certified is not a small-sample wobble
around a real effect; it is the pair being selected *because* it swung.

**The arity is the mechanism, and it is worse than the disjunction alone.** A 1-of-6
win condition would merely inflate the false-positive rate (~6× nominal, and this file
already notes *"Seven uncorrected comparisons"* run in the cell). But
`INDISTINGUISHABLE` — which the same table calls *"the **good** outcome for the
architecture"* — requires **all six** pairs flat **and** all six under `res ≤ 3.0`, so a
single wide pair vetoes it:

| | pairs with `res > 3.0` | null verdict | positive verdict |
|---|---|---|---|
| run 13 | **4 / 6** | **BLOCKED** | fired, on 1 pair |
| run 14 | **5 / 6** | **BLOCKED** | fired, on 1 pair |

So in both runs only one of the two verdicts was *reachable*, and it was the same one
both times. That is a ratchet, not a tie-breaker: noise can deliver `MERGING WINS` and
cannot deliver `INDISTINGUISHABLE`. The design predicted this exact failure — the
`INDISTINGUISHABLE` row is annotated **"AT RISK — this is the verdict the predicted
resolution most likely blocks"** — and then shipped the rule anyway, twice. `res` is
data-dependent, so the 4/6 and 5/6 counts could have come out otherwise; they did not.

> ⚠ **The rule's own prose sets a better standard than its criterion column, and that
> standard also fails.** The paragraph under the table says the evidence is *"the
> **pattern** — the two ink pairs agreeing with the two router pairs at the same merge
> ratio, and the tight budgets agreeing with the loose ones."* Scored against that:
> at m=0.20 M=1344, run 13 reads router **−0.22** vs ink **+4.06** (the ink pair is a
> declared winner, its router twin is negative), and run 14 reads router **+4.22** vs
> ink **+1.43** — the same disagreement, **with the roles swapped**. Tight-vs-loose
> inverts too: run 13 has M=3840 +3.12 above M=1344 −0.22, run 14 has M=3840 +0.81
> below M=1344 +4.22. The pattern standard is the right one and it is **not met in
> either run** — so the prose did not rescue the criterion, it was simply not the thing
> being checked. T1 must put the pattern requirement *in* the criterion, or drop the
> claim that the pattern is the evidence.

**Consequence for T1, and it is a hard constraint rather than a preference:** no verdict
rule that takes the best of N pairs is admissible here, because the best of N has
already been shown to be uncorrelated across runs. T1 must name **one** pair as primary
before run 15 is scored (see §6), give the null verdict the **same arity** as the
positive one, and set the `res` gate from the observed `sd` rather than from the 3.0
constant that has now blocked the null verdict in 2 runs out of 2 — cf. T4's note that
**n is not a knob** at `MAX_EVAL_SAMPLES = 50`, which is why the gate and not the sample
size is the thing that has to move.

### 1d. And no declared winner survives the family it was drawn from

§1c shows the 1-of-6 disjunction picked different winners each run. The obvious next
question — does any winner survive a correction for the family it was *selected* from? —
has a clean answer. `scripts/diagnose_analysis_dof.py` §10 runs Holm step-down at
α = 0.05 over the family, using **z-tests at 1.96**, i.e. the *same instrument the
published criterion already uses*, so this measures multiplicity in isolation and does
not smuggle in an estimator change.

**The family is 12, not 18.** Only `recall` and `ned` are stored per image in runs 13
and 14. `character_accuracy_pct = (1 − mean(ned)) × 100` is an affine transform of `ned`,
so it is **not** an independent third witness — entering it would double-count the one
quantity carrying the effect and bias *toward* declaring an effect. `word_order` is not
on disk for either run. So the family is **6 pairs × 2 quantities = 12**, and that is the
**weaker** correction, which is the honest one to apply here.

| | nominally `p < 0.05` | smallest `p` | first Holm threshold | **survivors** |
|---|---|---|---|---|
| run 13 | 3 of 12 | 0.0240 (`M=1920 router`, ned) | 0.05/12 = **0.00417** | **0** |
| run 14 | 2 of 12 | 0.0208 (`M=1440 router`, recall) | 0.00417 | **0** |

**Neither published `MERGING WINS` verdict survives the smallest defensible correction
for the family it came from.** Both miss the first threshold by roughly 5×, so the result
is not sensitive to the choice of correction — Bonferroni, Holm, or Šidák over 12 all
reject at the same step, and even a family of 6 (recall only) leaves the threshold at
0.00833, still ~2.5× below both.

> ⚠ **A second reading of the same table, recorded so it cannot be picked up later as a
> licence.** Run 13's smallest `p` in the whole family is `M=1920 router` on **`ned`**
> (+3.66, p = 0.0240) — and that is the pair the published recall-only rule scored
> **flat** (+2.86, CI [−0.30, +6.02]). So the pre-registered quantity was the *less
> sensitive* one on **the row D13 headlined**. That is a reason to distrust that row's
> null, and it is **not** a licence to re-headline on `ned`, which would be choosing the
> metric after seeing the data. The binding statistic stays the pre-registered one; the
> disagreement is filed as evidence the design cannot resolve this row, not as a result.

**⚠ The prescription in §1c has the same defect it diagnoses, and §10 catches it.**
§1c closes by telling T1 to *"set the `res` gate from the observed `sd`"*. Audited against
the stored fields, a gate written as a bare number **cannot fail**:

| | value |
|---|---|
| native-scale `res` over the 12 tests | **0.0264 – 0.0381** |
| max *conceivable* `res` for a paired delta of a [0,1] field at n=50 | **0.280** (deltas lie in [−1,1], so `sd ≤ 1`) |
| the gate as written, `res ≤ 2.0` | satisfied **52×** over by the observed values, **7.1×** over by the arithmetic ceiling |
| the tail rule as written, `count(d < −10)` | native deltas lie in [−1,1] — **no document can ever be below −10** |

Every `per_image` field is stored in [0,1]. So **any run scored on the arrays as-stored
returns "powered, no harmed documents" by arithmetic**, with the entirely auditable
defence *"I used the stored field."* This is the same hole as §2 — which found that `arr()`
pins no *direction* — one level up: the rule must pin **units per quantity**, not only
direction, and every threshold must carry its units in the text. A number without units
is not a pre-registration. Added to §6 as a named requirement.

### 2. Direction is not a property of the harness — and one quantity inverts

`scripts/diagnose_merge_power.py:arr()` reads

```python
return [pi[key] * 100.0 for pi in row["per_image"]]
```

It scales **every** key by 100 and encodes **no direction**. That is survivable only because
all five `PUBLISHED` calibration tuples use the default key, i.e. **all five are recall**,
where higher is better. `ned` is an *error* rate — lower is better — and the harness has
never been asked to distinguish them.

On the run 13 negated-vs-router sabotage contrast, the one the tracker leans on as its
non-vacuity control:

| quantity | mean delta | min delta |
|---|---|---|
| recall | **−63.98** | −96.61 |
| charAcc | −56.4 | −86.21 |
| **`ned` (raw, as stored)** | — | **+7.64** |

`ned`'s minimum is the **only non-negative minimum in the table.** So a tail statistic
specified as "worst per-document delta" — the obvious phrasing, and the one D13 §5 all but
invites — would read the deliberately-broken arm as the best-behaved row in the sweep, by a
comfortable margin, while recall reads −96.61 on the same 50 documents. The rule must pin
direction **per quantity**, not once globally.

### 3. Adopting the trimmed mean *creates* a degree of freedom that did not exist before

The plain mean is linear, so for a difference-in-differences it does not matter whether you
difference per document and then average, or average each run and then difference. On run 14
minus run 13 at m=0.40 (against `keep=0.50 router`, i.e. the published primary — see §1b),
both orders give **+3.5822**, and the gap is **identically zero**, as arithmetic requires.

The trimmed mean is **not** linear, and the two orders come apart:

```
trim(per-document DiD)        = +3.8696
trim(d14) − trim(d13)         = +3.0615
                          gap =  +0.8081 pts
```

**+0.81 points from an ordering the pre-registration does not mention.** For scale, and
stated in the three ways that bear on it:

- **26%** of the effect itself (+3.06…+3.87 pts depending on the order chosen);
- **16×** the ±0.05 pt bootstrap seed-noise floor already recorded in this file — so it is a
  real choice, not a rounding artifact;
- **42%** of the resolution the trim buys on this contrast (4.93 → 2.99, a gain of 1.94 pts).

> ⚠ **Correction, 2026-09-23.** The first draft of this section claimed the gap was *larger*
> than the resolution the trim was adopted for. It is not — it is 42% of it, on this
> contrast. I wrote that comparison from the ad-hoc probe, which had not computed the trim's
> resolution gain at all; the control in `diagnose_analysis_dof.py` §5 was written to assert
> the comparison and **failed**, which is how the error surfaced. The gap is material without
> being larger, and the overstatement was in the flattering direction for the argument this
> section is making.

The load-bearing point does not depend on the magnitude: **the plain mean has no such choice
to make, and the trimmed mean does.** Adopting a robust location statistic to reduce noise
introduces an estimand ambiguity that the noisier estimator did not have. That is why T1
cannot be a one-line estimator choice — naming "10% trimmed mean" does not determine the
estimate.

### 4. The trim's discard set at n=500 is exactly FUNSD

This is an interaction between **T1 and T4** — the top two items in the queue — and it was
recorded in neither.

T4 pools a second corpus to lift n from 50 to ~500, on D13 §2's arithmetic that the decisive
contrast needs n ≥ 62. T1 is expected to adopt a g=0.10 trimmed mean on D13 §3's arithmetic.
Composed:

- at pooled n=500, g=0.10 discards **k = 50 documents per tail**;
- FUNSD's entire contribution is **50 documents**;
- run 13 at m=0.40 has **10 documents worse than −10 pts** on the published primary
  (−57.0 … −10.5), or **6** on the token-matched pairing (−47.7 … −11.1). The conclusion is
  the same either way, which is the one place the §1b ambiguity does *not* bite.

So every harmed FUNSD page can sit inside the discarded lower tail, and the pooled estimate
can be numerically identical to one computed on the *new* corpus alone. The power fix and the
robustness fix are individually correct and jointly capable of deleting the only corpus the
project has ever measured. Neither task's DONE-WHEN would catch it.

Note the asymmetry that makes this easy to miss: `k = floor(500 × 0.10) = 50` is **arithmetic**,
so a control asserting "k equals 50" would be decorative — it could not have come out
otherwise. The claim with content is that the harmed documents *fit* inside the discard set,
which is a fact about the data and could have failed.

### 5. The −64 pt control cannot satisfy a tightness gate — contradicting T1's own rationale

T1's rationale currently reads *"every published null stays null, the −64 pt control still
resolves."* The second clause is **false under any absolute-width gate**, which is what a
RESOLVED verdict needs:

```
negated-vs-router, recall:  trim = −64.56,  Tukey–McLaughlin half-width = 6.09  at n=50
```

A control whose own 95% CI is ±6.09 cannot satisfy `h ≤ 1.5`. It resolves in the weak sense
of *excluding zero* — which it does by 10σ, and always will — but not in the sense of
"estimated tightly." At n=500 its half-width is ≈1.92, still above 1.5. The clause conflates
two different meanings of "resolves" and needs rewriting, not deleting: the control is doing
real work, just not the work the sentence claims.

### 6. What T1 must therefore pin

Written as the specification for the rule, not as the rule. **Order matters: (1) is a
precondition for (3) and (4)**, because g's sign-sensitivity and the tail counts are both
contrast-specific (§1b).

1. **One named primary contrast** — by `select_mode` + budget + split **and its control row**,
   written before run 17. Not "the merge contrast", and not "m=0.40" either: §1b shows that
   phrase names a −0.17 pt null and a +4.91 pt gain. Name the estimand in words too (*"merge
   vs prune at equal token budget"* or *"the cost of adding merging at fixed keep fraction"*),
   since the row names alone have already been read both ways in this file.
2. **Direction and units per quantity**, with `ned` explicitly flagged as lower-is-better
   (§2). A shared `arr()` that ignores direction is a defect, not a convention. **And every
   threshold must carry its units in the text** (§1d): on the stored [0,1] fields, `res ≤ 2.0`
   is satisfied 52× over and `count(d < −10)` can never fire, so a bare number is not a
   pre-registration — it is a check that passes by arithmetic.
3. **Location statistic, g, and DiD ordering** — all three, since g picks the sign (§1.4)
   and the ordering is worth +0.81 (§3).
4. **A tail statistic** (D13 §5), with its threshold, its direction, and its tie convention
   (§1.6) — and normalised against a matched null rather than a fixed constant, or it is
   decorative in the ninth sense already recorded in D13.
5. **The discard set, stated in documents rather than as a fraction**, and a constraint
   relating it to corpus composition under T4 (§4).
6. **Secondary quantities declared as secondary**, over the full three, not the two the
   historical runs can be back-scored on — already required by T3's `word_order` caveat.
7. **Equal arity for the positive and the null verdict** (§1c). A 1-of-N win condition
   against an N-of-N null condition is a ratchet: in both runs on disk only the positive
   verdict was reachable. Whatever N the positive verdict needs, the null verdict gets the
   same N.
8. **The correction family, named and sized before scoring** (§1d) — and sized at **6×2=12**
   for runs 13/14, since charAcc is an affine transform of `ned` and entering it as a third
   quantity would bias toward declaring an effect. No winner in either run survives it, so a
   rule that omits this step is not conservative, it is the reason the two published verdicts
   disagree.

### 7. There is no token-matched random arm — the control cannot be computed at all

Checked because an adversarial pass claimed the merge-minus-random control was *decorative*.
It is worse than that, and in a different way:

```
run 13:  merge-row budgets  [1344, 1440, 1920, 3840]
         random-row budgets [1680, 2400, 3600]
         overlap            []          <- empty. Same for run 14.
```

**No merge row shares a token budget with any `random` row, in either run.** So "merging
beats random selection at matched M" is not a weak control or a decorative one — it is not
computable from runs 13 or 14, and any statement of that form in this project's history was
comparing across budgets. Filed as a build requirement on T4 rather than as a finding about
merging.

### What D14 does and does not license

**Does:** rescope T1 from "choose an estimator" to "pin the analysis," and record that the
rescoping was forced by measurement rather than by taste. It also promotes §4 to a blocking
interaction between T1 and T4, and §7 to a build requirement on T4.

**Does not:** license treating any of the seven as *settled* by the numbers above. The swings
are evidence that the choices are live, **not** arguments for whichever side of each choice
flatters merging — picking g=0.05 because it returns +0.22 is exactly the failure this
section exists to prevent. Nor does it license quoting the swings as effects: +1.12 between
two splits is a measurement of analyst freedom, not of a merging benefit. And §1b does **not**
license preferring the +4.91 reading; if anything the same-keep contrast is the one the
project's "merging is free" claim has always been about.

**Provenance.** `scripts/diagnose_analysis_dof.py`, **20/20 controls, exit 0**, log at
`results/analysis_dof_local.log`. No GPU, no model load, no network. Section 0 reproduces
D13's published +2.86 / res 3.16 from the raw arrays before anything new is read off them, so
a loader regression voids the run rather than changing the numbers quietly.

> ⚠ **Two things this section got wrong on the first pass, both caught by its own controls.**
> (i) §3 claimed the DiD ordering gap was *larger* than the resolution the trim buys. It is
> **42%** of it. The control asserting "larger" **failed**, which is how it surfaced — the
> overstatement was in the direction that flattered the argument. (ii) The first draft
> recorded the merge-minus-random control as **unverified**, on the grounds that my probe
> used row names that do not exist. Re-checked properly in §7: the row names do not exist
> *because no such pairing exists in either run*, which is a stronger and different result
> than the adversarial pass reported. An "I could not reproduce it" was concealing a real
> finding, and only enumerating the budgets turned it up.

