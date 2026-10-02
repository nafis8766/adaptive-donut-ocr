# Adaptive Visual Token Pruning for Document OCR

Research code for dynamic visual token pruning on **Donut** (`naver-clova-ix/donut-base`),
evaluated on **FUNSD** full-page document OCR.

A document page becomes **4800 visual tokens**, most of them margin and whitespace. This project
asks how few of them you can keep and still transcribe the page, and whether a learned router
picks better tokens than random selection or a hand-crafted ink heuristic.

```
frozen Swin-B encoder → PatchSaliencyRouter → BipartiteTokenMerger → mBART decoder
   (4800 patch tokens)    MLP score + STE top-k    ToMe cosine soft-merge    seq2seq
```

**`AGENTS.md` is the single source of truth for project state** — run history, findings,
diagnostics, rejected approaches, and gotchas. Read it before changing anything. `REPORT.md` is
a standing summary of what the project is and what each run established.

---

## Read this before quoting a number

- **This is not a latency result.** Cutting 4800 → 960 visual tokens (5×) buys **1.04×
  wall-clock** (max 1.05× over ten rows, D11). The router sits *after* the frozen encoder, so all
  4800 tokens are computed at every `keep_ratio`, and generation is decoder-bound (243–280
  autoregressive steps). Pruning shrinks only the cross-attention KV. The defensible axes are
  **visual-token count** and the cross-attention KV memory that scales with it — explicitly not
  speed.
- **The one measured efficiency claim is cross-attention KV memory, and it comes with its
  price.** keep=0.35 takes it **150.00 → 52.50 MiB (−65.0%) for −0.26 pts recall (t −0.18,
  n=50 paired)** — M1, 25/25 controls, analytic and hook-observed bytes agreeing to rel gap
  0.0000 at all five budgets. Unpruned cross-KV is 19.46% of the model's 771 MiB. Scope:
  cross-attention KV only — not total, not peak, **not encoder**, not latency.
  Extended 2026-09-18 to prune+merge (52/52 controls): keep=0.50 + merge 0.20 → M=1920 gives
  **150.00 → 60.00 MiB (2.50×)**. ~~for +0.54 pts, 95% CI [−2.36, +3.83], n=50 — no measured
  cost. The deeper 3.33× at M=1440 costs −3.86 pts [−7.45, −0.30] and must not be quoted
  without it.~~ **The accuracy half was restated 2026-09-24 by T3** under the run-17
  pre-registration (`scripts/score_preregistered.py`, 45/45 controls). **The memory figures
  stand; the sentence around them did not.** Three defects: the **baselines did not match**
  (2.50× is measured against keep=1.00, while +0.54's control row is keep=0.50 — the merge step
  alone is **1.25×**); **+0.54 is the plain mean**, where the pre-registered estimator gives
  **−0.65 [−2.36, +1.07]** on the same row and **+0.16** in run 14 (all nulls, but the sign is
  robust to neither the estimator nor the replicate); and **−3.86 "resolved and negative" does
  not replicate** — run 14 gives **−0.17 [−2.40, +2.06]**. 3.33× is still not licensed, now for
  being unreplicated. See claim 3 in `AGENTS.md`.
- **`BipartiteTokenMerger` now executes, and has been measured.** ~~`merge_ratio=0.0` in all ten
  runs short-circuits it. Half the architecture above is untested.~~ Runs 12 and 13 (Kaggle T4,
  2026-09-16/17) ran the full four-stage pipeline — frozen Swin-B → router prune → ToMe merge →
  mBART decoder — over a 28-row token-matched grid. ~~**Merging away 20% of the router's kept set
  is free; 40% costs −3.86 pts.**~~ Run 14 (2026-09-18) put merging into *training* to test
  whether that 40% cost is train/test mismatch. **It did not settle it:** the contrast went
  to −0.28 [−4.46, +3.44], but at resolution 3.95 against a pre-registered 3.6 bar, so the
  verdict is **UNDERPOWERED** and the interval still contains −3.86. **2.5× at M=1920 remains
  the measured limit; 3.33× at M=1440 is not licensed.**
  **2026-09-24 — "free" is retired, and the word was the problem.** Scored under the
  pre-registration, the primary contrast (`keep=0.50 m=0.20 ink` vs `keep=0.40 ink TWIN`,
  token-matched at M=1920) is **UNDERPOWERED in both runs** — +1.66 [−0.81, +4.14] in run 13,
  +0.02 [−1.90, +1.94] in run 14 — with **zero** quantities surviving Holm. `UNDERPOWERED`
  licenses nothing: the required n is **307** and FUNSD has 50. Run 14 is **not** scored free
  despite that +0.02 pt null, because both its tail gates fail: one page lost **40.00 pts**
  against a matched-null expectation of −12.43. **The corpus-average null is true and is not a
  claim about an arbitrary document** — and, separately, the tail test that surfaces those pages
  **is not specific to merging**: the sweep's worst single-document loss (**−80.85 pts**) is on
  a row where nothing is merged at all.

- **`src/` is a library mirror, not what produced the results.** The notebooks carry their own
  copies of the model classes and import nothing from `src/`. In particular, `src/loss.py` has
  **no saliency supervision**, so `src/train.py` cannot reproduce runs 8–10.
- **Never compare a local level to a Kaggle level.** Run 5 reads 74.72 recall locally vs 77.74
  on Kaggle on identical weights and identical images. Selection reproduces across the two to
  three decimals; generation does not, and the gap widens as the budget tightens.
  **Within-checkpoint deltas are the comparable quantity** — that is why every D11/D12 claim is
  a paired delta rather than an absolute.

## Current results

FUNSD test × 50 · word recall / char accuracy / word-order / mean NED · `MAX_WORDS=128` ·
`max_length=512` · prompt `<s_doc>` · `repetition_penalty=1.0`, `no_repeat_ngram_size=3`.

| Configuration | Visual tokens | Recall | CharAcc | Order | NED |
|---|---|---|---|---|---|
| Unpruned ceiling (run 6, run-5 weights) | 4800 | 77.74 | 64.70 | 53.05 | 0.353 |
| Pruned, `keep=0.50` (run 9) | 2400 | **79.63** | 64.81 | 54.08 | 0.352 |

**Post-encoder pruning to a third of the tokens costs nothing — *if you train for it*.** The
condition is load-bearing. Run 9, trained at `TRAIN_KEEP_RATIO=0.50`, gives up 65% of its tokens
at `keep=0.35` for **−0.26 pts (t −0.18)** against its own unpruned ceiling — a *measured* null,
detectable ≥ 2.81 pts. Run 5, trained and evaluated unpruned, loses monotonically on the
**identical** token sets: **−1.57 / −6.03 / −11.47 / −20.34** at keep=0.50/0.35/0.25/0.20. So
pruning is not a property of the pruner (D12). The attribution has a limit: run 9 differs from
run 5 by pruning-aware training **and by five more epochs of it**, so this is *supported, not
isolated* — the missing control is Pending 14.

The router beats random selection at the same budget by **+17.7 / +27.4 / +34.0 / +29.3 pts** at
keep=0.50 / 0.35 / 0.25 / 0.20 (D11; this supersedes the "+14 to +28" range earlier drafts
quoted). Do not cite "beats the ink oracle" — that comparison is −2.24 pts at t −1.62, which is
directional, not a result.

Data is `nielsr/funsd` (149 train / 50 test) plus `naver-clova-ix/synthdog-en`. **SROIE is
deliberately excluded** — its KIE schema would pollute the single `{"text": ...}` target.

## Repository layout

```
AGENTS.md                          # source of truth: runs, findings, diagnostics, gotchas
REPORT.md                          # standing summary of the project and each run
kaggle_token_pruning_ocr.ipynb     # canonical notebook (17 cells) — produced runs 2–6
kaggle_pruning_run.ipynb           # GENERATED from the above — produced runs 7–10
src/                               # library mirror: router, tome, loss, model, dataset,
                                   #   train, evaluate  (pre-run-8 architecture)
scripts/
  patch_notebook_*.py              # the only sanctioned way to edit a notebook
  verify_*.py                      # execution checks — they exec real cells, not stubs
  diagnose_*.py, eval_*.py         # diagnostics D1–D11, re-derived from cached artifacts
tests/                             # five suites, run as plain scripts (see below)
run 9/, run 10/, results*/         # per-run outputs: metrics, sweeps, checkpoints,
                                   #   and the executed notebook inside each .zip
visualizations/                    # D1 saliency overlays + cached scores (.npz)
infer.py                           # standalone inference on arbitrary images
```

## Running things

### Training and evaluation (Kaggle)

The real runs happen in `kaggle_pruning_run.ipynb` on a free-tier T4. Import it, set
**Accelerator** to GPU and **Internet** to On, attach the run-5 checkpoint as a dataset, and run
all. Kaggle silently gives you a CPU session if no accelerator is selected — cell 2 asserts
against this, because a CPU run produces a plausible-but-wrong table over several hours.

**Never hand-edit `kaggle_pruning_run.ipynb`.** It is generated by
`scripts/make_kaggle_pruning_notebook.py` from the canonical notebook; an edit typed into it
survives until the next regeneration and then silently vanishes. Edit the *generator* for
anything in the `DO_TRAIN` branch and the *canonical notebook* for anything else, then
regenerate.

### Local CLI (library mirror — does not reproduce the published runs)

```bash
pip install -r requirements.txt

python src/train.py --dataset_name nielsr/funsd --epochs 5 \
    --keep_ratio 0.35 --merge_ratio 0.20 --save_dir ./checkpoints

python src/evaluate.py --checkpoint ./checkpoints/best_adaptive_donut.pt \
    --num_samples 50 --keep_ratio 0.35 --merge_ratio 0.20
```

Discriminative learning rates: router **1e-4** / decoder **2e-5** / unfrozen encoder tail
**1e-5**.

### Tests

`pytest` is **not installed** locally, and the suites are `if __name__ == "__main__"` scripts
rather than pytest collections. Run each directly, **with `PYTHONPATH=.`** — without it two of
the five fail on `ModuleNotFoundError: No module named 'src'`, which reads as a broken repo:

```bash
PYTHONPATH=. python tests/test_modules.py          # 5/5 suites pass this way
PYTHONPATH=. HF_HUB_OFFLINE=1 python tests/test_end_to_end.py
```

## Architecture notes

**Differentiable saliency router.** A 2-layer MLP scoring head with a straight-through
estimator, `M_ste = TopK(s) + s − detach(s)`, giving discrete hard filtering in the forward pass
and end-to-end gradients from the decoder loss back into the router.

At `keep_ratio=1.0` this is **not** a no-op — it permutes. Training at K=N makes the STE
multiplier exactly 1.0, so the only gradient the scorer ever sees asks *"does scaling this token
help"*, which anti-aligns with *"is this token informative"*. That trap produced a router which
ranked blank paper above text for five runs (diagnostic D1); the fix was an explicit saliency
supervision term, added in run 8.

**Bipartite token merging (ToMe).** Partitions surviving tokens into two sets, computes cosine
similarity, and soft-merges the most similar into weighted centroids while tracking 2D
coordinate centroids. Measured on runs 12–14 (2026-09-16/17/18); ~~merging 20% of the router's
kept set is free, 40% costs −3.86 pts on merge-naive weights.~~ **restated 2026-09-24 under the
run-17 pre-registration: the primary contrast is `UNDERPOWERED` in both runs (+1.66 and +0.02
pts, neither surviving Holm), the required n is 307 against FUNSD's 50, and the 40% cost does
not replicate (−3.23 in run 13, −0.17 in run 14).** Training with merging on
(run 14) left that contrast flat but **underpowered**, and the A/B partition fix
(`checkerboard_color`) is **null on all three checkpoints** — correct about the partition,
unproven about recall. See `AGENTS.md`.

**Joint loss.** Cross-entropy + a target-sparsity MSE term + an entropy term, with an optional
saliency BCE term (notebook only). Note the entropy term is negative-definite and pushes scores
toward 0.5; `lambda_entropy` was never deliberately chosen and is set to 0 in the current runs.

## Conventions

- Notebook edits go through **asserted patchers** in `scripts/` — each backs up first, replaces
  via a helper that asserts exactly-one match, and `ast.parse`s every edited cell.
- Every patcher gets a `verify_*.py` companion that **executes** the real code. Parsing clean is
  not evidence it runs.
- A green check deserves the same suspicion as a red one. Before trusting a pass, ask what a
  *failing* system would score on the same check; if the answer is "about the same", the check
  is decorative.
- State a falsifier before running a diagnostic, and transcribe every printed verdict — the
  contradicting ones first.
- There is currently **no validated cheap acceptance gate** for a router checkpoint. Retained
  ink and min line coverage were both promoted and both falsified. The gate is an actual
  accuracy row against a random floor and an ink ceiling at the same budget.

## What's open

Two experiments, in priority order. `AGENTS.md` → "OPEN ITEMS AS OF 2026-09-09" is the live list.

1. **Pending 14 — isolate H1** (~4 h Kaggle T4). Train a run-5-length checkpoint *without*
   pruning. The headline claim rests on attributing run 9's advantage to pruning-aware training,
   and D12 explicitly did not isolate that from the five extra epochs. Highest value remaining.
2. ~~**Pending 15 — ToMe.** Either run the merger once and settle the merge-after-prune
   ordering, or scope it out of the architecture description. It has never executed.~~
   **Closed 2026-09-17 by run 13** — the ordering is settled (`checkerboard_color`) and the
   merger is measured. ~~**What replaces it: run 14 — train with merging on.**~~ **Run 14 ran
   on 2026-09-18 and came back UNDERPOWERED** (−0.28 [−4.46, +3.44], res 3.95 vs a 3.6 bar),
   so 3.33× at M=1440 is not licensed and **2.5× at M=1920 stays the limit**. Three findings
   from it shape whatever comes next: the merge-row gain was **not distinguishable from a
   general robustness lift** (+3.11 merged vs +3.43 on a *random, unmerged* selection,
   difference −0.32 p=0.60); **NED degraded significantly** (p=0.029) where recall did not, so
   "free" held on one metric of four; and the **router's margin over random fell** +17.07 →
   +13.16. **What replaces it: a redesigned merge-training run, not a rerun.** `n` is not a
   knob — 50 *is* FUNSD test — so the design has to change: both checkpoints contrasted in one
   session, a primary pre-registered across metrics, per-image `char_acc`/`word_order` stored
   so they can be tested at all, and a "did this checkpoint just improve at everything"
   control. Also still missing, and symmetric to Pending 14: a checkpoint trained at
   `keep=0.30, merge=0.0`, without which every token-matched M=1440 comparison has exactly one
   trained arm.

Closed and not to be reopened: ink as a training objective, the attention target, the latency
framing, stratified selection, `repetition_penalty > 1.0`, and run 11 as it was originally
sketched.
