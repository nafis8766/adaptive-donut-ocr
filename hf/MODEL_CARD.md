---
license: mit
base_model: naver-clova-ix/donut-base
library_name: pytorch
pipeline_tag: image-to-text
tags:
  - document-ocr
  - token-pruning
  - donut
  - efficiency
  - funsd
---

# AdaptiveDonutOCR — learned visual-token pruning for document OCR

A [Donut](https://huggingface.co/naver-clova-ix/donut-base) checkpoint fine-tuned **with a
learned token-pruning router active**, for full-page OCR on FUNSD. A document page becomes
4,800 visual tokens inside Donut's Swin-B encoder, and most of them are margin and whitespace.
A small scoring head ranks those tokens and the low-ranked ones are discarded before the
decoder attends to them.

**The headline, with its condition attached:** at `keep_ratio=0.35` this checkpoint discards
**65% of the visual tokens** and **65% of the decoder's cross-attention KV cache**
(150.00 → 52.50 MiB) for **−0.26 points of word recall** (paired *t* = −0.18, *n* = 50). The
same operation applied to a checkpoint that was *not* trained under pruning costs **6.03
points**. The difference between those two sentences is the result — this is train/test
matching, not inference-time denoising, and that was tested rather than assumed.

Full method, every diagnostic, and the complete record of what failed:
**[github.com/nafis8766/adaptive-donut-ocr](https://github.com/nafis8766/adaptive-donut-ocr)** ·
[5-page technical report (PDF)](https://github.com/nafis8766/adaptive-donut-ocr/blob/main/report/report.pdf)

---

## What this checkpoint is

```
frozen Swin-B encoder  →  PatchSaliencyRouter  →  BipartiteTokenMerger  →  mBART decoder
  (4800 patch tokens)     MLP score + STE top-k   ToMe cosine soft-merge      seq2seq
                                                   (parameter-free)
```

| | |
|---|---|
| file | `adaptive_donut_pruned.pt` — a **bare `OrderedDict` state dict**, not a wrapper |
| entries | **490** — 484 under `model.` (the full Donut encoder + decoder), 6 under `router.` |
| parameters | **261,220,793** (~996.5 MiB at fp32) |
| size | 1,045,901,771 bytes |
| router head | `Linear(1024→256) → LayerNorm(256) → GELU → Linear(256→1) → Sigmoid` — 263,169 params |
| merger | **no parameters.** ToMe is training-free by design; it is not in this file |

The router is ~0.1% of the checkpoint. Everything else is the fine-tuned Donut.

## How to load it

The model class is not on the Hub — it lives in the repository, because the router and the
merger are custom modules:

```bash
git clone https://github.com/nafis8766/adaptive-donut-ocr
cd adaptive-donut-ocr
pip install torch transformers pillow
```

```python
import torch
from huggingface_hub import hf_hub_download
from src.model import AdaptiveDonutOCR

ckpt = hf_hub_download("nafis8766/adaptive-donut-ocr-router",
                       "adaptive_donut_pruned.pt")

model = AdaptiveDonutOCR(
    base_model_name="naver-clova-ix/donut-base",
    keep_ratio=0.35,      # the free budget; 1.00 keeps every token
    merge_ratio=0.0,      # leave at 0.0 -- see "the merge axis" below
)
missing, unexpected = model.load_state_dict(
    torch.load(ckpt, map_location="cpu"), strict=True)
model.eval()
```

### Three things that will silently ruin your output

These are not hypotheticals; each one cost this project real runs.

1. **You must prompt with `<s_doc>`.** It is **not** a special token in this tokenizer — it
   tokenizes to five ordinary subwords — and the model was never trained to start from a bare
   `<s>`. Unprompted generation produces fluent-looking nonsense with **no error**.
2. **Keep `repetition_penalty=1.0`.** At 1.3 it is not a mild knob, it is a length cap: a
   full page legitimately re-uses its whole vocabulary, so eventually only EOS is unpenalised
   and the model closes the JSON mid-page. Measured cost: **−27 points of recall** and valid
   JSON falling from 82% to 0%. Use `no_repeat_ngram_size=3` as well — once the penalty is
   off, greedy repetition collapse costs another 6.7 points without it.
3. **Leave `merge_ratio=0.0`.** Every result above was measured with merging off, and the
   merge axis is unresolved (below).

```python
gen = model.generate(
    pixel_values=pixel_values,
    decoder_input_ids=prompt_ids,        # <s_doc>, 5 tokens
    max_length=512,
    repetition_penalty=1.0,
    no_repeat_ngram_size=3,
)
```

## Results, each with its scope limit

Evaluation protocol, held constant: FUNSD test × 50 · word recall / character accuracy /
word order / mean NED · `MAX_WORDS=128` · `max_length=512` · prompt `<s_doc>`.

**1. Pruning to a third of the visual tokens costs nothing — if you train for it.**

| keep | visual tokens | cross-attn KV | word recall | Δ vs unpruned | *t* |
|---|---|---|---|---|---|
| 1.00 | 4800 | 150.00 MiB | 77.62 | — | — |
| 0.50 | 2400 | 75.00 MiB (−50.0%) | 78.22 | +0.60 | 0.43 |
| **0.35** | **1680** | **52.50 MiB (−65.0%)** | **77.37** | **−0.26** | **−0.18** |
| 0.25 | 1200 | 37.50 MiB (−75.0%) | 70.67 | −6.96 | −2.82 |
| 0.20 | 960 | 30.00 MiB (−80.0%) | 64.61 | −13.01 | −5.42 |

The two free rows are *powered*: minimum detectable effect 2.76 and 2.81 points, so "we
looked and saw nothing" is distinguishable from "we could not have seen it". The tight
budgets are reported as costs, not dropped.

**2. Learned selection is worth +17.7 to +34.0 points** over a random mask at an identical
token budget (80.46/79.25/71.15/63.10 against 62.77/51.84/37.20/33.80 at
keep=0.50/0.35/0.25/0.20), widening as the budget tightens.
**This is a claim against *random*.** It is **not** a claim that the router beats a
hand-crafted ink heuristic — that margin is *t* = +1.62 on *n* = 50, under the threshold of
2.0 fixed in advance. Directional, not significant.

**3. The mechanism is train/test matching.** A checkpoint trained *and* evaluated unpruned
declines monotonically under pruning (−1.57 / −6.03 / −11.47 / −20.34) where this one is
flat; both were evaluated on **bit-identical token sets**. A dedicated arm isolated the cause
— the same configuration with pruning removed from training and the epochs kept gives
`ISO(0.35) = −10.49` points (*t* = −3.74), and five unpruned epochs moved the ceiling by
+0.52 (*t* = 0.24). So the gain is pruning-aware training, not the extra epochs. Isolated at
keep=0.35/0.25/0.20; the **loose budgets are underpowered, not null**.

## What this model does NOT give you

Stated here rather than in a footnote, because all three are easy to assume:

- **No latency or throughput win.** Cutting 4,800 tokens to 960 — a 5× reduction — buys
  **1.04×** wall-clock, 1.05× at best across ten measured rows. This is structural: the
  router sits *after* the frozen Swin, so all 4,800 tokens are computed at every budget, and
  generation is decoder-bound at 243–280 autoregressive steps against an encoder that runs
  once. **Any latency claim from this architecture is false.**
- **No encoder-side saving**, for the same reason.
- **The saving is cross-attention KV only** — not total memory, not peak, not the encoder.
  Unpruned cross-attention KV is 19.46% of the model's 771 MiB of parameters, so it is a real
  quantity, but it is one quantity. Byte figures halve at fp16; the *percentage* is invariant.
- **The merge axis is unresolved.** At a matched budget of 1920 tokens, merging versus simply
  pruning harder measures **+1.66 [−0.81, +4.14]** in one run and **+0.02 [−1.90, +1.94]** in
  another, with **0 of 3** confirmatory quantities surviving Holm correction in either. Both
  are flat and both sit above the 1.0-point resolution the design targets, so the verdict is
  **underpowered** — which licenses nothing, not even "merging changes nothing". Reaching
  that resolution needs ≈307 documents; FUNSD's test split is 50, and that is the whole split.
  Leave `merge_ratio=0.0`.
- **Absolute recall is venue-dependent.** The same weights on the same 50 images score 77.74
  on a Kaggle T4 and 74.72 locally. Token *selection* reproduces to three decimals;
  *generation* does not. Every figure above is a within-checkpoint, within-venue paired delta.

## Training

| | |
|---|---|
| initialised from | a Donut checkpoint fine-tuned on FUNSD without pruning |
| schedule | 5 epochs, pruning **ON** at `keep_ratio=0.50` |
| router supervision | ink-BCE auxiliary on the scoring head (the router is sign-inverted without it — it learns to rank blank paper *above* text) |
| learning rates | router 1e-4 · decoder 2e-5 · unfrozen Swin tail 1e-5 |
| hardware | one free-tier Kaggle T4 |
| data | FUNSD train (149 images) + 500 SynthDoG-en pages |

## Licence position, stated rather than omitted

**This checkpoint is released under MIT**, inherited from
[`naver-clova-ix/donut-base`](https://huggingface.co/naver-clova-ix/donut-base), which these
weights are a fine-tune of and whose card states `license: mit`.

What is **not** established, and is recorded here instead of being left implicit:

- **SynthDoG-en's licence field is empty.** Read directly from the cached
  `dataset_infos.json`: `license: ''`. Not permissive, not restrictive — *unstated upstream*.
- **FUNSD's licence is not stated on its Hub card** either, in the copy available here.

No dataset content is redistributed by this repository — these are model weights, and no
FUNSD or SynthDoG image, annotation or transcription ships in a `.pt` file. But the training
data's terms could not be read, and a reader deciding whether to use this model in their own
context should know that rather than infer permission from the MIT tag on the weights. If you
need a cleaner provenance chain, train the router yourself: the full pipeline, the generator
and every verifier are in the repository.

## Reproducing the numbers

Every figure on this card re-derives from a cached artifact committed to the repository, on
CPU, without a GPU and without these weights:

```bash
python scripts/check_report_numbers.py     # 121 checks, 58 figures re-derived from artifacts
python scripts/score_preregistered.py      # the pre-registered merge scoring, 64 controls
```

There is also a [Colab notebook](https://colab.research.google.com/github/nafis8766/adaptive-donut-ocr/blob/main/colab/reproduce_results.ipynb)
that clones the repository and re-derives the tables above in about a minute on a free CPU
runtime.

## Citation

```bibtex
@misc{kamal2026adaptivedonutocr,
  author = {Kamal, MD. Nafis},
  title  = {AdaptiveDonutOCR: Learned Visual-Token Pruning for Document OCR},
  year   = {2026},
  howpublished = {\url{https://github.com/nafis8766/adaptive-donut-ocr}}
}
```

Built on Donut (Kim et al., ECCV 2022) and evaluated on FUNSD (Jaume et al., ICDAR-OST 2019).
