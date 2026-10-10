# Adaptive Visual Token Pruning for Document OCR

A document page becomes **4,800 visual tokens** inside [Donut](https://huggingface.co/naver-clova-ix/donut-base), and most of them are margin and whitespace. This project asks how few you can keep and still transcribe the page — and whether a *learned* router picks better tokens than random selection or a hand-crafted ink heuristic.

Independent research project. Donut (Swin-B + mBART) on FUNSD full-page OCR, trained on a single free-tier Kaggle T4.

**Trained weights:** [`nafis8766/adaptive-donut-ocr-router`](https://huggingface.co/nafis8766/adaptive-donut-ocr-router) · **5-page report:** [report/report.pdf](report/report.pdf) · **[Run the results in Colab →](https://colab.research.google.com/github/nafis8766/adaptive-donut-ocr/blob/main/colab/reproduce_results.ipynb)**

```
frozen Swin-B encoder  →  PatchSaliencyRouter  →  BipartiteTokenMerger  →  mBART decoder
  (4800 patch tokens)     MLP score + STE top-k    ToMe cosine soft-merge      seq2seq
```

## Results

FUNSD test ×50 · `MAX_WORDS=128` · `max_length=512` · prompt `<s_doc>` · `repetition_penalty=1.0`

| Configuration | Visual tokens | Recall | CharAcc | Order | NED |
|---|---|---|---|---|---|
| Unpruned ceiling (run 6) | 4800 | 77.74 | 64.70 | 53.05 | 0.353 |
| Pruned, `keep=0.50` (run 9) | 2400 | **79.63** | 64.81 | 54.08 | 0.352 |

**Three results, each with its scope attached:**

1. **Pruning to a third of the visual tokens costs nothing — *if you train for it*.** At `keep=0.35`, run 9 gives up 65% of its tokens for **−0.26 recall points** (t −0.18, n=50 paired). The conditional is load-bearing: run 5, which never trained under pruning, loses **monotonically** on *bit-identical* token sets — −1.57 / −6.03 / −11.47 / −20.34 at keep=0.50/0.35/0.25/0.20. So the gain is train/test matching, not inference-time denoising, and not a property of the pruner. A dedicated ablation (run 11) isolated pruning-aware training from the extra epochs it came with: **−10.49 pts** when the pruning is removed and only the epochs kept.

2. **The router's selection value is real and large.** Against a random mask at the same budget: **+17.7 / +27.4 / +34.0 / +29.3 points** at keep=0.50/0.35/0.25/0.20, the margin widening as the budget tightens.

3. **One measured efficiency claim, with its price attached.** At `keep=0.35` the decoder cross-attention KV cache falls **150.00 → 52.50 MiB (−65.0%)** for that −0.26 points. Unpruned cross-KV is 19.46% of the model's 771 MiB of parameters, so this is real working memory. Analytic and hook-observed byte counts agree to a relative gap of 0.0000 at all five budgets.

## What this project does *not* claim

This matters more than the results above, and it is stated first in every internal document for a reason.

- **It is not a latency result.** Cutting 4800 → 960 visual tokens (5×) buys **1.04× wall-clock** — 1.05× at most over ten measured rows. The router sits *after* the frozen encoder, so all 4,800 tokens are computed at every `keep_ratio`, and generation is decoder-bound (243–280 autoregressive steps against one encoder pass). **Any latency or throughput claim from this work is false.** An earlier framing here reported "7–11% wall-clock savings"; those were single-budget latency *increases* misread as savings, and the measurement that caught it is [`scripts/eval_budget_binding.py`](scripts/eval_budget_binding.py).
- **The token-merging half is unresolved, not free.** Scored under a pre-registration written before the run, merging-vs-pruning at a matched budget of 1,920 tokens is **`UNDERPOWERED`** in both available runs (+1.66 and +0.02 points, zero quantities surviving Holm correction). Reaching a 1.0-point resolution needs **n ≳ 307 documents**; FUNSD's test split is **50**, and it is the whole split. An earlier "merging 20% is free" framing did not survive its own estimator.
- **Pruning is re-opened by every retrain.** How much of a page is droppable turned out to be a property of the *weights*, not the dataset: identical pages and ink masks gave "premise is weak" on one checkpoint and "premise holds" on the next.

## The methodology is part of the result

- **14 diagnostics** (`D1`–`D14`, `M1`) that each re-derive their numbers from cached artifacts, so any claim is recheckable without a GPU.
- **`verify_*.py` checks that `exec` real notebook cells** rather than linting them. Three correctness defects were found this way rather than by a run failing — including an ink-supervision loss fed a probability where it expected a logit, attenuating the gradient up to **112×** on exactly the tokens the scorer was most wrong about.
- **Pre-registration.** The estimator, standard error, interval method, tail statistic, multiplicity correction and verdict table for the next run were all fixed in writing *before* any number from it existed — then exercised against prior runs, where they found a defect in the pre-registration itself.
- **Negative results are recorded, not buried.** Several diagnostics falsified the hypothesis they were built to support: an attention-based selection target lost to a plain ink heuristic once budgets actually bound (−5.63 and −12.81 points at keep=0.25/0.20), and two cheap acceptance gates were promoted and then falsified, leaving the honest conclusion that no cheap gate for a router checkpoint currently exists.
- **Sabotage controls.** Verifiers are checked by breaking the thing they verify and confirming they go red. A green check that a broken system would also pass is treated as decorative.

A worked example of why this is load-bearing: run 6 changed **no weights** and gained **+27.18 recall points**. A `repetition_penalty` of 1.3 was dividing the logit of every already-emitted token, so on a full-page form — which legitimately reuses its whole vocabulary — only `EOS` stayed unpenalized. The model was not getting the page wrong; it was *stopping*, at 71% of gold length. The same single root cause also took valid-JSON output from **0% to 82%**, a bug that had been logged as cosmetic and separate for four runs.

## Reproducing

**Check the numbers yourself, in about a minute, on a free CPU runtime.** [`colab/reproduce_results.ipynb`](colab/reproduce_results.ipynb) — [open in Colab](https://colab.research.google.com/github/nafis8766/adaptive-donut-ocr/blob/main/colab/reproduce_results.ipynb) — clones this repo and re-derives both result tables from the committed `results/*.json`, then runs the repository's own numeric audit and the pre-registered merge scoring. **No GPU, no weights, no dataset download.** It demonstrates the claim that matters most: every figure here re-derives from a cached artifact.

**Use the trained weights:** [`nafis8766/adaptive-donut-ocr-router`](https://huggingface.co/nafis8766/adaptive-donut-ocr-router) — the pruning-aware checkpoint every headline figure comes from. The model card states the three settings that will silently ruin your output if you miss them, and the licence position of the training data.

```bash
pip install -r requirements.txt
```

**The real runs happen on Kaggle.** Import [`kaggle_pruning_run.ipynb`](kaggle_pruning_run.ipynb), set Accelerator to GPU, attach the base checkpoint as a dataset, and run all. Cell 2 asserts the accelerator — Kaggle silently hands you a CPU session if none is selected, which produces a plausible-but-wrong table several hours later. That notebook is written for Kaggle and will **not** run unmodified in Colab: it carries 22 hardcoded `/kaggle/` paths and five CUDA assertions. Use the reproduce-results notebook above instead.

**Never hand-edit that notebook.** It is generated by [`scripts/make_kaggle_pruning_notebook.py`](scripts/make_kaggle_pruning_notebook.py); an edit typed into it survives until the next regeneration and then silently vanishes. Edit the generator, regenerate, then re-run the verifiers — regenerating *is* the test.

```bash
# Verifiers — these execute real notebook cells
python scripts/verify_tome_merge_port.py        # 96/96
python scripts/verify_pooled_corpus_port.py     # 62/62
python scripts/score_preregistered.py           # 64/64

# Tests: pytest is not required; these are __main__ scripts and need PYTHONPATH
PYTHONPATH=. python tests/test_modules.py
PYTHONPATH=. HF_HUB_OFFLINE=1 python tests/test_end_to_end.py
```

## Repository layout

```
AGENTS.md                        # source of truth: runs, findings, dead ends, gotchas
  AGENTS-ARCHIVE-{DIAGNOSTICS,RUNS,CHANGELOG}.md
NOTES.md                         # maintainer notes: every caveat, in detail
WRITEUP.md                       # results-first, claim by claim (numerically audited)
STORY.md                         # chronological, for a reader with no ML background

kaggle_token_pruning_ocr.ipynb   # canonical notebook — produced runs 2-6
kaggle_pruning_run.ipynb         # GENERATED from it — produced runs 7-14
src/                             # library mirror (NOT what produced the results)
scripts/                         # 80 files: asserted patchers, verifiers, diagnostics
tests/                           # 5 suites
run */, results/                 # per-run artifacts; every diagnostic re-derives from these
infer.py                         # standalone inference on arbitrary images
```

Model weights (`*.pt`) and the per-run result archives (`*.zip`) are not versioned — each is ~1 GB. The JSON artifacts the diagnostics actually read **are** versioned, so the analyses reproduce without the weights.

## Status

**Closed, October 2026.** Runs 2–14 complete; the three results above are the deliverable.

The merge axis was closed **unresolved, deliberately.** Merging-vs-pruning at a matched budget
is `UNDERPOWERED` in both available runs, and reaching a 1.0-point resolution needs **n ≳ 307
documents** against FUNSD's 50 — which is the entire test split, so `n` was never a knob. The
pooled 29-row sweep that would have reached it was built, verified green by five checks, and
costed at 5.92 h against a 9 h budget. It never ran, because no corpus with a licence I could
read was available: the official competition archive contains no licence, terms or citation file
in any of its 4,226 entries and its terms live only on a host serving a certificate for a
different domain; of the alternatives, the one with clean first-party licensing annotates only a
key-value subset of each page rather than the page, and the one with the right annotations
carries a bare uploader-asserted licence with no attribution to the competition that produced
the scans.

So the reported outcome is the one the pre-registration named in advance for exactly this case —
`UNDERPOWERED`, with the required `n` quoted beside it — rather than a claim resting on data I
could not account for. `AGENTS.md` → `## Project closed 2026-10-05` is the final accounting.

**`AGENTS.md` is the source of truth.** Every other document here, including this one, is
derived from it.
