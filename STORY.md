# The story of AdaptiveDonutOCR

*How this project actually went: what we set out to do at each stage, what went wrong, and what
we did about it. Written 2026-09-17.*

*This is the narrative companion to the other three documents in this repo.
[AGENTS.md](AGENTS.md) is the single source of truth — every number here comes from it, and where
the two disagree, AGENTS.md is right and this file is stale. [WRITEUP.md](WRITEUP.md) presents
the findings results-first, for a reader who wants the conclusions. [REPORT.md](REPORT.md) is a
standing summary. **This file is the only one organised by time rather than by result**, and it
is the one to read if you want to understand *why* the project looks the way it does.*

---

## How to read this

Each stage below has the same three parts:

> **What we set out to do.** The plan going in, and the belief behind it.
> **What went wrong.** The result that did not match the belief.
> **What we did about it.** The fix, and what it cost.

You do not need a machine-learning background. The next section gives you everything you need.
Terms in **bold** on first use are defined in the glossary at the end.

---

## Chapter 0 — The idea, and the five things you need to know

### The setting

We are doing **OCR**: give a computer a photograph of a printed page — a form, an invoice, a
receipt — and ask it to type out the text. We use an existing open model called **Donut**
(`naver-clova-ix/donut-base`), which does this in one shot, reading an image and emitting text
without a separate "find the letters" step.

Donut works in two halves:

```
     the page                 4800 visual tokens              the transcript
  ┌────────────┐            ┌──────────────────┐            ┌──────────────┐
  │  an image  │  ────────► │  a long list of  │  ────────► │ "Name: ...   │
  │ 2560×1920  │  ENCODER   │  small summaries │  DECODER   │  Date: ..."  │
  └────────────┘            └──────────────────┘            └──────────────┘
```

The **encoder** chops the page into a grid of 80 × 60 = **4800 small squares**, and turns each
square into a short numeric summary. Each of those summaries is called a **visual token**. The
**decoder** then reads all 4800 of them and writes out the text one word at a time.

### The observation the project is built on

**Most of a document page is blank.** Margins, gutters, the white space between lines — on a
typical form, the large majority of those 4800 squares contain no ink at all. The decoder still
has to look at every single one of them, every time it writes a word.

### The question

> **How few of those 4800 visual tokens can you keep and still read the page correctly?**

And the follow-up, which is the part with research value:

> **Can a small neural network learn to pick *which* tokens to keep, better than picking at
> random or using an obvious hand-written rule?**

### The plan

Insert two components between the encoder and the decoder:

1. A **router** (`PatchSaliencyRouter`) — a tiny two-layer network that gives every token a score
   from 0 to 1 meaning "how much does the decoder need this one". We then keep the top-scoring
   fraction — the **keep ratio** — and throw the rest away. `keep_ratio=0.35` means keep 1680
   tokens out of 4800.
2. A **merger** (`BipartiteTokenMerger`, a technique called **ToMe**) — instead of deleting
   tokens, average together pairs that look nearly identical. Two adjacent squares of blank paper
   can become one token without losing anything.

The deliverable: an accuracy-versus-token-count curve, plus evidence that the learned router
beats the alternatives.

### The five facts that shaped everything that followed

These were not all obvious at the start. Several cost us runs to learn.

1. **The encoder is frozen and sits *before* the router.** All 4800 tokens get computed no matter
   what. Pruning only shrinks the decoder's work. *(This is why the latency claim later died.)*
2. **Training happens on a free Kaggle T4 GPU; analysis happens on a local CPU.** The two venues
   do not produce identical numbers, so you can only compare like with like.
3. **Every experiment is 50 test images from FUNSD**, a public dataset of scanned business forms.
   Fifty images is not many. Almost every hard moment in this project is a question about whether
   a difference is real or is noise.
4. **The main metric is word recall** — of the words that should have been transcribed, what
   percentage appeared. Higher is better. Points ("pts") are percentage points.
5. **There is no deadline.** This is a research project, which is why so much of it is spent
   checking work rather than producing more of it.

---

## Chapter 1 — Establish a floor (run 2)

> **What we set out to do.** Before optimising anything, prove the pipeline runs end to end and
> get a number to beat. Train Donut on FUNSD with pruning switched off entirely.
>
> **What happened.** It worked. **54.07% word recall** on 20 images. Not good, but real.
>
> **What we did about it.** Locked the evaluation protocol — 50 FUNSD test images, the same four
> metrics, the same prompt, the same generation length — and did not change it again. Everything
> from here is comparable to everything else, which is a decision that paid for itself many times
> over.

Nothing went wrong in this chapter. It is the only one.

---

## Chapter 2 — "It must be the data" (runs 3 and 4)

> **What we set out to do.** 54% is low. The obvious explanation for a model underperforming on
> 149 training images is that 149 training images is not enough. So: train harder (40 epochs,
> with image augmentation), then add synthetic documents from **SynthDoG**, a generator that
> produces unlimited fake pages with known text.
>
> **What went wrong. Twice, in opposite directions.**
>
> **Run 3** trained beautifully — training error fell from 0.32 to 0.13 — and test accuracy did
> not move at all (53.86). The model was learning the training set and generalising nothing.
>
> **Run 4** made it *worse*: −2.14 points, down to 51.72. And the training error collapsed to
> 0.049, which is the signature of memorisation, not learning.
>
> **What we did about it.** We took the negative result seriously instead of scaling up. The
> planned expansion to 4000–6000 synthetic pages was **cancelled**.
>
> The diagnosis: the frozen encoder could not tell FUNSD's degraded, scanned, noisy glyphs apart
> in the first place. Feeding the decoder cleaner synthetic pages did not help it read dirty real
> ones — it just dragged the model's expectations toward clean paper. The bottleneck was not how
> much data the decoder saw. **It was what the encoder could see.**

**The lesson, which recurs:** run 4 is the most valuable of the three, because it is the one that
said no. Two runs spent confirming that a plausible theory is wrong is two runs well spent, as
long as you actually update.

---

## Chapter 3 — "Then it must be the encoder" (run 5)

> **What we set out to do.** Act on run 4's diagnosis. Unfreeze the top stage of the encoder at a
> very low learning rate (1e-5) so it could adapt to FUNSD's scan quality, and rebalance the data
> mix back down to 500 synthetic pages.
>
> **What went wrong.** A genuinely mixed result. Character accuracy **+2.09**, word order
> **+3.66** — and word recall **−1.16**, to 50.56. The model was getting the characters more
> right and the words less complete.
>
> **What we did about it.** Two things.
>
> First, we **verified the unfreeze had actually happened** rather than trusting the flag: a
> tensor-by-tensor comparison of the checkpoints showed stage 3 had 34 of 34 tensors changed and
> stages 0–2 plus the embeddings had 0 of 315 changed. Exactly what was intended, demonstrated
> rather than assumed. This became a habit.
>
> Second — and this is the important one — we stopped and asked *why recall specifically*. The
> model's outputs were consistently coming in at about **71% of the length of the correct
> answer**. It was not getting words wrong. It was stopping early.

That observation opens the next chapter, which is the turning point of the whole project.

---

## Chapter 4 — The best result in the project cost zero GPU hours (run 6)

> **What we set out to do.** Find out why generation was stopping short. The suspected culprit
> was `no_repeat_ngram_size=3` — a setting that forbids the model from ever repeating any
> three-word sequence. On a business form full of "Name:", "Date:", "Signature:", that is a
> plausible gag order.
>
> So we ran a **decoding ablation**: no training at all, just re-evaluate the existing run-5
> weights five times with different generation settings, including a CONTROL row using the exact
> original settings.
>
> **What we found — and note that we were wrong about the cause.** The suspected knob was a
> **bit-exact no-op**. Rows 1 and 2 of the ablation were identical to the last digit.
>
> The actual culprit was `repetition_penalty=1.3`, a setting that makes each already-used word
> progressively less likely to be used again. On a page with 128 words, where "the" legitimately
> appears fifteen times, that is not a mild preference — it is a **length cap**. The model was
> being penalised out of finishing the page.
>
> **What we did about it.** Set `repetition_penalty` to 1.0. On **completely unchanged weights**:
>
> | | before | after |
> |---|---|---|
> | word recall | 50.56 | **77.74** |
> | valid JSON output | 0% | **82%** |
>
> **+27.18 points, for zero training.** Larger than every other effect in the project combined.

This chapter produced three durable consequences:

- **Runs 2–5 are an artifact.** Every number before run 6 was measured through a broken decoder
  setting. They are comparable to each other and to nothing else. **The run table restarts at
  run 6.** Four runs' worth of conclusions had to be re-read in that light.
- **The CONTROL row is why we believe it.** It reproduced run 5's number at 0.00 points of drift,
  proving the harness itself had not changed underneath us.
- **The suspected cause was the wrong one.** We only found the real one because the ablation
  varied several settings instead of testing the hypothesis we walked in with. *Test the
  neighbourhood, not the hypothesis.*

---

## Chapter 5 — Turning the router on, and discovering it was backwards (D1, run 7)

> **What we set out to do.** With a working baseline at last, actually do the research: train
> with pruning switched on, at `keep_ratio=0.50`.
>
> Before spending GPU time, we ran a cheap local diagnostic — **D1**, a probe of what the router's
> scores actually looked like on real pages.
>
> **What went wrong. The router was inverted.** It was systematically giving *high* scores to
> blank paper and *low* scores to text. It was a perfectly good saliency detector wired backwards.
>
> **Why — and this is the most interesting bug in the project.** Up to this point the router had
> only ever been trained with `keep_ratio = 1.0`, i.e. keeping everything.
>
> The router's scores reach the rest of the network through a device called a **straight-through
> estimator (STE)**, which multiplies each surviving token by `1 + (score − score.detach())`.
> That expression is numerically equal to 1.0 while still carrying a gradient — it is how you make
> a hard yes/no selection trainable.
>
> But when you keep *everything*, nothing is ever discarded, and so the only question the gradient
> can ever ask is **"would scaling this token up or down help?"** — never **"is this token worth
> keeping?"** Those two questions are different, and on this architecture they turn out to be
> *anti-correlated*. Blank tokens are the safe ones to amplify. So the router learned to love
> blank paper. It was answering the only question it was ever asked, correctly.
>
> **What we did about it.** Run 7: retrain with pruning genuinely on, so the selection question
> would finally be asked.
>
> **And it did not work.** With the router's scores driving selection, recall was **18.80** —
> catastrophically below the **62.31** you get by keeping tokens *at random*.
>
> But we had included a diagnostic row in the sweep that ranked tokens by the **negated** score,
> and that row scored **73.09**. The ranking contained strong, real signal. It was simply pointing
> the wrong way.

**Two things this established.** First, *exposing* a model to the right conditions is not the
same as *supervising* it — the STE gradient alone could not find the sign. Second, the practice
of putting an inverted control and a random baseline in the same table as the thing you are
measuring is what turned an unreadable failure into a precise diagnosis.

---

## Chapter 6 — Choosing what to teach it (D2, D3)

> **What we set out to do.** If the gradient will not teach the router which tokens matter, we
> have to tell it directly. But tell it *what*? We needed a target: some signal, computable for
> free on any page, that says "this square is important".
>
> The candidate was **ink**: measure the pixel contrast in each square, call the high-contrast
> ones important. It is free, it needs no labels, and it is obviously correlated with text.
>
> **What went wrong.** D1's own write-up had recommended a particular follow-up. **D2 overturned
> it in under a second** of compute, and **D3** — a statistical check of the selection — added
> more caveats.
>
> The finding that mattered: ink is a *proxy*, and optimising a proxy is not the same as
> optimising the goal. Nothing in the pipeline says a page's total retained ink is what the
> decoder needs. It might need the ink *distributed* — a bit of every line — rather than the
> maximum total, which a greedy selector would take from one dense paragraph.
>
> **What we did about it.** We went ahead with ink, because it was the only free target available
> and the sign fix was urgent — but we wrote the reservation down first, and we built the
> instruments that would later let us test it: per-image line coverage, an **ink oracle** row (a
> weight-independent selector that takes the highest-ink tokens directly, giving us a ceiling),
> and a **random** row (giving us a floor). Both appear in every sweep from here on.

---

## Chapter 7 — The sign fix works, and we change two things at once (run 8)

> **What we set out to do.** Add a supervised loss term — **ink-BCE** — that pushes the router's
> score toward 1 on high-ink squares and 0 on low-ink squares. Give it the answer directly.
>
> **What happened. It worked, decisively.** Run 8: **80.17** recall at keep=0.50 and **77.80** at
> keep=0.35 — at or above the unpruned ceiling, while discarding half to two-thirds of the page.
>
> The proof the sign had genuinely flipped was not the headline number but the **role-flip**: the
> `negated` row, which had scored 73.09 in run 7 by being right where the router was wrong,
> collapsed to **2.70**. The two rows traded places. That is much harder to fake than an
> improvement.
>
> **What went wrong.** Two things, both procedural, both of which cost us later.
>
> 1. **Three loss settings moved inside a single `if/else`.** The supervision weight, the entropy
>    weight and the sparsity weight all changed together, so "the ink loss worked" could not be
>    separated from "one of the other two did something".
> 2. **The loss itself was wrong.** It fed the router's output — already squashed to a probability
>    between 0 and 1 by a sigmoid — into `binary_cross_entropy_with_logits`, a function that
>    expects *un*-squashed numbers and applies its own sigmoid. **A double sigmoid.** The result
>    is a loss that still points roughly the right way but is heavily flattened, so it teaches far
>    more weakly than intended.
>
> **What we did about it.** Found both — the second one by a diagnostic, not by a failure — and
> fixed them in the next chapter. Run 8's result stands, but it stands as "something in that
> block helped", not as a clean attribution.

---

## Chapter 8 — The loss bug, and the layer we built because of it (D4, D5, F1–F3)

> **What we set out to do.** Fix the double sigmoid.
>
> **What went wrong — twice, and this is the instructive part.**
>
> **D4** diagnosed the bug correctly and prescribed a fix: have the router emit raw scores instead
> of probabilities. **D5 found that prescription was unsafe.** The router's scores have **three
> different consumers**: the ink loss, the sparsity loss (which compares the mean score against a
> target budget and therefore *requires* a 0–1 range), and the STE multiplier. Change the range
> for one and you silently break the other two.
>
> D5 then proposed its own fix, and **that one was unsafe too** — it misbehaved under mixed
> precision, which is how Kaggle actually trains.
>
> D5 also turned up something nobody had been looking for: `lambda_entropy = 0.05`, a
> hyperparameter that had been shaping **every run since the beginning** purely as a function
> default. It appeared in no log and no config. It was not a mistake, but it was undeclared, and
> an undeclared hyperparameter is one you cannot reason about.
>
> **What we did about it.** Three fixes, and a permanent change in how we work.
>
> - **F1** — the shipped loss fix. Convert the probability *back* to a logit before the loss,
>   leaving the range untouched for the other two consumers:
>   ```python
>   F.binary_cross_entropy_with_logits(
>       torch.logit(scores.clamp(1e-6, 1 - 1e-6)), target)
>   ```
> - **F2** — the **harness control**. Before any sweep runs, re-evaluate the *old* run-5 weights
>   through the *new* code. If the harness has not changed, that number must come back identical.
>   Runs 7 and 8 had no such control, which is precisely why "the ceiling moved" and "the harness
>   moved" could not be told apart in them.
> - **F3** — training telemetry, so each loss term is logged separately and "three knobs in one
>   `if/else`" cannot happen silently again.
>
> **And the standing rule:** every notebook change goes through a **patcher** script that asserts
> its anchor matches exactly once and parses the result, paired with a **`verify_*.py` script that
> executes the real cell against stubs.** Not lints it — *runs* it. This rule exists because a
> change once passed a syntax check and crashed on the GPU an hour into a run.

This is the chapter where the project grew its second half. From here on, roughly as much effort
goes into checking results as into producing them — and several of the best findings come out of
the checking.

---

## Chapter 9 — The fix works, the accuracy falls (run 9, D6)

> **What we set out to do.** Run 9: F1 + F2 together. A correctly-shaped ink loss and a verified
> harness. Expect the router to get better at ink, and accuracy to follow.
>
> **What happened.** Half of that.
>
> - **F2 passed at 0.00 points** — the first anchored numbers in the project. From run 9 onward we
>   know the ground has not moved under us.
> - **F1's mechanism worked exactly as designed.** Retained ink rose from **0.790 to 0.922**. The
>   router got substantially better at the thing we were teaching it.
> - **Accuracy fell.**
>
> **What we did about it.** Recorded it as **D6**, and stated the conclusion plainly:
> **optimising the ink proxy harder actively costs accuracy.**
>
> This is D2's reservation, confirmed by intervention rather than correlation. Ink is correlated
> with usefulness, and it is still the wrong objective — a selector maximising total ink
> concentrates on dense regions and starves the sparse lines, and the decoder needs a bit of every
> line more than it needs a lot of one.

**The generalisable lesson, and we now log for it deliberately:** a fix can work exactly as
designed and make the outcome worse. Measure the mechanism *and* the goal, in separate columns,
every time. If we had only logged recall, we would have concluded F1 did nothing. If we had only
logged retained ink, we would have declared victory.

---

## Chapter 10 — A better target, which also did not work (D7–D10, run 10)

> **What we set out to do.** Ink is the wrong target. Find a better one — and there is an obvious
> candidate. The decoder already tells us which tokens it uses: its **cross-attention** weights,
> the numbers that say how much the decoder looked at each visual token while writing each word.
> Take a frozen, working decoder, record where it looks, and teach the router to predict *that*.
>
> Before spending a run, four diagnostics in sequence:
>
> - **D7** — is the STE signal usable at all? (It falsified its own author's hypothesis twice
>   along the way.)
> - **D8** — is the attention target actually *different* from ink? **Yes**: correlation +0.083.
>   Nearly unrelated.
> - **D9** — is it *learnable* by a network this small? **Yes**: held-out AUC **0.976**. Easily.
> - **D10** — does it *move* as the encoder trains, i.e. are we chasing a target that runs away?
>   **No**: stationary. Safe to supervise against.
>
> Every precondition checked out. We also confirmed the router currently knows nothing about it
> (correlation −0.045). Run 10 was as well-motivated as any experiment in the project.
>
> **What went wrong.** **The mechanism fit better than any auxiliary we ever trained** — the
> router's top 2400 tokens contained **93%** of the teacher's top 2400, lift **+0.430** — and
> **accuracy did not move.** 79.41, against run 9's 79.63. Flat.
>
> It also **collapsed retained ink by 25–32 points at flat recall** — which, as a side effect,
> became the **third independent line of evidence** that ink is not the objective. You can throw
> the ink metric away entirely and lose nothing.
>
> **What we did about it.** Asked a harder question than "did it help": **could it possibly have
> helped?**
>
> And the answer was no. At `keep_ratio=0.50` on this model, **pruning half the page already beat
> not pruning at all, by +2.1 points.** There was no accuracy gap for a better selector to close.
> Run 10's null result was **structurally guaranteed by its own budget.** We had spent a run
> measuring an intervention at the one operating point where no intervention could register.

**The lesson, now a standing check:** before optimising *how* a budget is allocated, verify the
budget **binds** — that spending it badly actually hurts. The baseline's own rows usually say so
already, and in our case they had.

---

## Chapter 11 — Re-asking the question where the answer can exist (D11)

> **What we set out to do.** Repeat run 10's comparison at budgets that bind: keep=0.25 and
> keep=0.20, where tokens are genuinely scarce. Paired on the same 50 images, locally, no
> training — just evaluation.
>
> **What we found. Three things, two of them bad news.**
>
> **1. The attention target does not tie. It loses.** −5.63 points at keep=0.25 (t −2.40) and
> **−12.81** at keep=0.20 (t −6.23), getting monotonically worse as the budget tightens.
>
> The mechanism is legible: run 10's router retains ink **0.257** against random's **0.201**. It
> is a *near-ink-agnostic* selector. That is harmless while the budget is slack and there is
> enough room for a bad selection to still include the text — and ruinous once every retained
> token has to carry some.
>
> **2. The latency claim is false.** We measured wall-clock time across five budgets. Cutting
> 4800 tokens down to 960 — **five times fewer** — buys **1.04×** speed, at most **1.05×** across
> all ten router rows. (The largest speed-up anywhere in D11 is 1.19×, and it is on a *random* row
> — quoted here deliberately, because it is the strongest measured evidence against the very
> disclaimer it sits under.)
>
> Why, in hindsight obviously: the router sits *after* the frozen encoder, so all 4800 tokens are
> computed at every budget; and generation is decoder-bound, 243–280 sequential word-steps against
> one encoder pass. Pruning shrinks only the decoder's cross-attention.
>
> **3. The router's selection value is real and large.** Against random selection at identical
> budgets on identical images:
>
> | keep ratio | tokens kept | router | random | margin |
> |---|---|---|---|---|
> | 0.50 | 2400 | 80.46 | 62.77 | **+17.7** |
> | 0.35 | 1680 | 79.25 | 51.84 | **+27.4** |
> | 0.25 | 1200 | 71.15 | 37.20 | **+34.0** |
> | 0.20 | 960 | 63.10 | 33.80 | **+29.3** |
>
> **What we did about it.** Deleted the latency claim from every document rather than softening
> it, cancelled the planned follow-up to run 10 (the failure mode is not specific to which target
> you use), and promoted the selection-value table to a headline claim — it is measured, paired,
> large, and it survives every control we have aimed at it.

**A note on how D11's own controls were built**, because it is the pattern the project settled on:
the acceptance gate was originally a recall delta, and a smoke test showed that gate **passing on
two images**, where the estimate is pure noise. A control that cannot fail is decoration. It was
moved onto `retained_ink`, which is near-deterministic given the weights — and which then matched
the Kaggle numbers to three decimals on six separate gates.

---

## Chapter 12 — One honest efficiency claim (M1)

> **What we set out to do.** D11 had just deleted the project's only efficiency claim. But
> pruning must save *something* — it shrinks the decoder's cross-attention **KV cache**, the
> memory holding the visual tokens during generation. So: measure it. Two independent ways —
> analytically from the architecture, and observed via hooks on a live model.
>
> **What we found.** At keep=0.35, cross-attention KV goes from **150.00 MiB to 52.50 MiB, a 65%
> cut, for −0.26 points of recall (t −0.18, n=50 paired)** — a measured null, not an unmeasured
> one. Unpruned cross-KV is **19.46%** of the model's 771 MiB, so it is a large cut in a
> non-trivial quantity. 25 of 25 controls passed; the two independent measurements agreed to a
> relative gap of 0.0000 at all five budgets.
>
> **The interesting part is what the script did to its own author.** The docstring had been
> written *in advance* with a hedge — the finding would probably be "a large cut in a small
> quantity". The 19.46% figure **falsified the hedge**, and the framing was rewritten from the
> script's own output rather than left as drafted.
>
> **What we did about it.** Published it with its scope nailed down and its price attached:
> cross-attention KV **only** — not total memory, not peak, **not the encoder** (which computes
> all 4800 tokens regardless), and **not latency**. And we deliberately did *not* headline
> keep=0.20's more impressive −80.0%, because that one costs 13.01 points (t −5.42).

---

## Chapter 13 — "Why does pruning help?" — and the word that turned out to be load-bearing (D12)

> **What we set out to do.** An uncomfortable fact had been sitting unexplained since D11:
> **throwing away half the page makes the model better.** Every document in the repo had carried
> the same casual guess — a regularisation-like effect, blank paper diluting attention — and
> nothing had ever tested it.
>
> Two competing explanations:
>
> - **H1, train/test matching (mundane):** runs 9 and 10 *trained* with pruning on at keep=0.50.
>   So keep=1.00 is off-distribution *for them*, the unpruned "ceiling" is artificially depressed,
>   and the apparent gain is a **recovery**, not an improvement.
> - **H2, inference-time denoising (interesting):** blank tokens genuinely dilute the decoder's
>   attention, so pruning should help **any** model — including one that never saw pruning during
>   training.
>
> H2 makes a sharp, falsifiable prediction, and **run 5 tests it**: trained unpruned, evaluated
> unpruned, never exposed to the idea.
>
> **What we found. H2 is rejected.** Run 5 declines monotonically under pruning —
> **−1.57 / −6.03 / −11.47 / −20.34** at keep=0.50/0.35/0.25/0.20, significant at the last three
> — exactly where H2 predicted improvement. Run 9 peaks at precisely the budget it was trained
> for. The difference-in-differences is negative at all four budgets.
>
> H2 was given every advantage before being killed: both checkpoints selected tokens with
> `select_mode="ink"`, which is weight-independent, so they kept **bit-identical token sets**
> (verified at `0.00e+00` at all four budgets) — and the ink oracle retains 0.994 of the page's
> ink at keep=0.50, H2's most favourable possible selection. It failed anyway.
>
> **What we did about it.** Rewrote the project's headline claim to include a conditional that had
> been missing from every previous phrasing:
>
> > **Pruning to a third of the visual tokens costs nothing — *if you train for it*.**
>
> **"If you train for it" is load-bearing.** Without it the claim is false, and run 5's four
> declining numbers are the proof.

**A methodological wrinkle worth knowing about**, because it is the honest version of a thing most
projects quietly get wrong. D12's **pre-registered verdict function returned UNDERPOWERED** — and
we reported that, unchanged. But it keyed on keep=0.50 alone, the flattest point on the curve,
while the pre-registered *prose* prediction had been about the curve's **shape**, which is
resolved decisively. Both readings are in the write-up with their power stated. Neither was
quietly promoted over the other.

And the artifact D12 saved records `controls_passed: false` with a verdict of `WITHHELD`. That is
also stated rather than smoothed over: one of its seven controls fails — the cross-venue harness
anchor, at 3.02 against a 1.5 tolerance, which is precisely the local-vs-Kaggle drift described in
the limitations. **The four controls the difference-in-differences actually rests on pass at
`0.00e+00`.** A reader is entitled to both facts and to decide for themselves.

> **When your hypothesis is about the shape of a curve, your statistic has to be about the shape.**

---

## Chapter 14 — Closing the last hole in the main claim (run 11)

> **What we set out to do.** D12 had been explicit that it did **not** prove H1, only that it
> supported it. The hole: run 9 differs from run 5 by pruning-aware training **and by five more
> epochs of it**. Maybe it was just the extra epochs.
>
> Run 11 is the missing cell of the table: **run 5's architecture, run 9's schedule, run 9's loss,
> run 9's auxiliary, run 9's data — and no pruning.** The epochs without the pruning.
>
> ```
>   run 11 − run 5   =  5 more epochs                   ← the confound, alone
>   run 9  − run 11  =  pruning-aware training          ← THE ISOLATION
> ```
>
> **What we found. H1 is isolated.** The isolation statistic
> `ISO(0.35) = −10.49 points (t −3.74, n=50 paired)`. And the curve shape needs no cross-checkpoint
> arithmetic at all:
>
> | keep ratio | run 9 (pruning-aware) | run 11 (epochs only) |
> |---|---|---|
> | 1.00 | 77.30 | **78.25** |
> | 0.75 | 77.84 | 76.82 |
> | 0.50 | 76.89 | 75.47 |
> | 0.35 | 77.60 | **68.06** |
>
> **Run 11 peaks at keep=1.00 and declines monotonically. Run 9 does neither — it is flat.** Run
> 11 reproduces run 5's signature despite having everything else run 9 had.
>
> And the confound, measured alone for the first time: **five unpruned epochs bought +0.52 points
> (SE 2.15, t 0.24)** at the ceiling. Nothing.
>
> **What we did about it.** Upgraded claim 1 from "H1 supported" to "H1 isolated", and recorded
> the prediction we had written down *before* the run — "run 11 will look like run 5, not like run
> 9" — as having held.

**And we wrote down the two ways this could still be over-read**, because they are real: the run
happened on Kaggle while the pre-registration was written for local CPU, and Kaggle's grid has no
keep=0.25 or keep=0.20 rows — the two tightest budgets, where the predicted effect is *largest*.
What makes the cross-session comparison trustworthy anyway is that the run-5 harness control reads
**77.73756569694308 in runs 9, 10 and 11 — identical to all fourteen digits.** Those sessions are
not drifting against each other.

Also: cell 15's own printout **overstates its case**, calling a 1.90-point gap "what the retrain
did, not measurement noise". That 1.90 is the maximum drift across three metrics, and the metric
supplying it is word *order*, not recall — recall drifted 0.51, and the paired test puts it at
+0.52 with t = 0.24. We flagged our own output as not quotable rather than quoting it.

---

## Chapter 15 — The half of the architecture that had never run (ToMe, run 12)

> **What we set out to do.** Face an embarrassing fact. `BipartiteTokenMerger` — merging
> near-duplicate tokens instead of deleting them, half the described architecture — had
> `merge_ratio=0.0` in **every run from 2 to 11**. It had literally never executed. Worse, the
> default value lived in the class, so "it has never run" was technically false of the *repo* even
> though it was true of every *experiment*.
>
> **What went wrong. When we finally read the merge code carefully, the split was broken.**
>
> ToMe works by dividing tokens into two groups, A and B, and merging each A into its most similar
> B. The implementation split them by **alternating index** — even-numbered tokens into A,
> odd-numbered into B. On a flattened 80 × 60 grid with an even row width, **that puts every token
> in a given column into the same group.** Vertically adjacent tokens — the single most common
> form of redundancy on a document page, since blank rows stack — could never be merged with each
> other. The measurement: **100% of vertical redundancy missed.**
>
> It also looked completely fine. Every shape was right, every test passed, nothing crashed. This
> is the gotcha we wrote down in bold: *a shape assertion is not a correctness assertion, and ToMe
> makes the difference invisible.*
>
> **What we did about it.** Replaced the alternating split with a **checkerboard** split — group
> membership by `(row + column) % 2`, like the squares on a chessboard, so every token's four
> neighbours are in the opposite group.
>
> - Vertical redundancy missed: **100% → 0.0%**, and it holds after the router re-sorts the
>   tokens, which is the case that actually occurs in the pipeline.
> - 13 of 13 correctness tests, 10 of 10 parity properties.
> - **The accepted cost, stated rather than hidden:** *diagonal* redundancy is now 100% missed. A
>   checkerboard cannot merge along a diagonal. This is a half-fix, and the 0.0% figure that makes
>   it look complete is about vertical redundancy specifically.
>
> Then **run 12**: a 28-row sweep designed to answer, at last, *is merging better than pruning
> when you hold the token count fixed?* — comparing e.g. "prune to 2400, then merge to 1920"
> against "prune straight to 1920". Same number of tokens reaching the decoder, different way of
> getting there. With an ink-oracle arm (weight-independent) and a **sabotage arm** (a deliberately
> broken merge partition that the analysis must be able to catch).

**Status as of this writing:** run 12 has completed and its analysis is being done in a parallel
session. Two things about it are worth recording here as plain observations, without adjudicating
them:

- **The printed verdicts favour merging** at most matched budgets, most strongly in the
  ink-oracle arm at the tight budget (+5.39 points).
- **The run's own provenance stamp names run 5's checkpoint, not run 9's.** Its `metrics.json`
  reads `77.73756569694308` — the run-5 harness-control value, to all fourteen digits — and its
  router rows reproduce the D1 inversion (router 24.97 against random 59.06 and ink oracle 73.69).
  The launch checklist specified run 9's weights. **If the evaluated checkpoint is run 5's, the
  router-arm rows of the merge table are measured through the inverted router and cannot be read
  as run 9's answer** — though the ink-oracle rows, being weight-independent, are less affected.
  The sabotage arm returned "no measurable difference", which the analysis correctly reports as
  *correct about the partition, unproven about the outcome*.

That question belongs to the session that owns run 12. It is flagged here so this document does
not quietly inherit a number it cannot vouch for.

---

## Where the project actually stands

### The four claims we can defend

1. **Pruning to a third of the visual tokens costs nothing — *if you train for it*.** Run 9 gives
   up 65% of its tokens for −0.26 points (t −0.18) against its own ceiling — a measured null. Run
   5 and run 11, on the *identical* token sets, decline monotonically. The condition is
   load-bearing, and run 11 isolated it.
2. **The router's selection value is real and large.** +17.7 to +34.0 points over random selection
   at matched budgets, growing as the budget tightens. *(We do **not** claim it beats the
   hand-crafted ink heuristic. At keep=0.50 it scores 2.24 points **above** the ink oracle, 80.46
   against 78.22, while retaining 0.072 **less** of the page's ink — so it is not merely
   rediscovering ink — but at t +1.62 on 50 images that is directional, not significant. The
   defensible comparison is against random.)*
3. **One measured efficiency claim, with its price.** Cross-attention KV: 150.00 → 52.50 MiB
   (−65.0%) for −0.26 points. Cross-KV only. Not total, not peak, not encoder, **not latency**.
4. **The methodology is a first-class result.** See below.

### What died, and what killed it

| Direction | Killed by |
|---|---|
| More data / synthetic scale-up | Run 4 (−2.14 and memorisation), on run 3's evidence |
| `repetition_penalty > 1.0` | Run 6 (+27.18 on unchanged weights) |
| Ink as a training objective | Three independent lines: D2 (correlational), D6/run 9 (interventional), run 10 (collapsed 25–32 pts at flat recall) |
| The cross-attention target | D11 (−5.63 and −12.81 at binding budgets) |
| Any latency or throughput claim | D11 (1.04× at 5× fewer tokens) |
| H2, inference-time denoising | D12 (run 5 declines where H2 predicted improvement) |
| "It was just the extra epochs" | Run 11 (+0.52 pts, t 0.24) |

### Still open

- Run 12's merge sweep — the analysis, and the checkpoint-provenance question above.
- A re-measurement of the decoding settings on run-11 weights.
- An optional co-adaptation study.
- The ~18% of outputs that are still not valid JSON, which nobody has characterised.
- Local-vs-Kaggle generation drift, which needs writing up as a limitation: run 5 reads 74.72
  locally against 77.74 on Kaggle on identical weights and images, and the gap widens as the
  budget tightens. Token *selection* reproduces bit-exactly; *generation* does not. **This is why
  nothing in the analysis compares a local number to a Kaggle one — within-checkpoint deltas are
  the comparable quantity.**

---

## What we would tell someone starting this project over

The findings above are specific to this model and this dataset. These are not.

**1. A control that cannot fail is decoration.** We shipped several before we noticed: a gate that
passed on two images where the estimate is noise; a verdict branch that manufactured a null at a
standard error of 8.88; a check whose tolerance was wider than its own measurement noise. The
question to ask of every green check is not "did it pass" but **"what would have made it fail, and
could that have happened here?"**

**2. Measure the mechanism and the goal in separate columns.** Run 9's ink loss worked exactly as
designed — retained ink 0.790 → 0.922 — and accuracy fell. Either column alone tells you the wrong
story. Log the quantity you are targeting, its null, and the outcome, and assert that the targeted
column actually moved.

**3. Check that the constraint binds before you optimise allocation under it.** Run 10 was a
well-motivated experiment whose null result was guaranteed by its own budget: at keep=0.50,
pruning already beat not-pruning, so no selector could have registered. The baseline's own rows
said so, and we did not look.

**4. Read every verdict your code prints — starting with the ones that disagree with you.** D3's
pre-registered verdict went unread for days. D12's verdict *disagreed* with its own shape finding
and we published both. Run 11's cell 15 overstated its case in prose and we flagged our own output
as not quotable. The verdict that contradicts you is the one worth the most.

**5. A right diagnosis can carry a wrong fix.** D4 found the double-sigmoid bug correctly and
prescribed a change that would have silently broken two other consumers of the same value. Before
changing a value's range, units or meaning, **enumerate everything that reads it.**

**6. Verify that patches run, not just that they parse.** `ast.parse` once passed a change that
crashed on the GPU an hour into a run. Every notebook patch in this project now has a companion
script that *executes the real cell* against stubs, no GPU required.

**7. Put an oracle and a random baseline in the same table as the thing you are measuring.** Run
7's catastrophic 18.80 was unreadable on its own. Next to random's 62.31 and the negated row's
73.09, it was a precise diagnosis: right signal, wrong sign.

**8. The most valuable runs were the ones that said no.** Run 4 killed the data theory. Run 10
killed the attention target. D12 killed a guess this repo had carried for a week. Three separate
correctness bugs — the decoding cap, the keep=1.0 STE trap, and the double-sigmoid loss — were
found by *diagnostics*, not by anything failing. All three had been silently producing plausible
numbers for multiple runs.

---

## Glossary

| Term | What it means here |
|---|---|
| **OCR** | Optical character recognition — reading text out of an image. |
| **Donut** | The pretrained model we build on. Reads a page image and emits text directly. |
| **Encoder / decoder** | The encoder turns the image into 4800 numeric summaries; the decoder reads those and writes the text. |
| **Visual token** | One of those 4800 summaries — roughly one small square of the page. |
| **Keep ratio** | The fraction of tokens kept. `0.35` = 1680 of 4800. |
| **Router** | The small network that scores each token for importance. |
| **STE** (straight-through estimator) | The trick that lets a hard keep/discard decision still produce a training gradient. Chapter 5 is about how it misfired. |
| **ToMe / merger** | Merging near-identical tokens instead of deleting them. |
| **FUNSD** | The dataset: 149 training and 50 test images of scanned business forms. |
| **Word recall** | Our main metric: percentage of the correct words that appeared in the output. |
| **pts** | Percentage points. |
| **t** (t-statistic) | Roughly, effect size divided by its uncertainty. Above ~2 in absolute value is conventionally "probably real"; near 0 means indistinguishable from nothing. |
| **SE** (standard error) | How much the measured number would wobble if we re-ran on different images. |
| **Paired** | The two things being compared were measured on the *same* 50 images, which cancels out per-image difficulty and makes small differences detectable. |
| **Underpowered** | We could not have detected an effect this size even if it existed — importantly **not** the same as "there is no effect". |
| **Ink oracle** | A selector that picks the highest-contrast squares directly from pixels. Weight-independent, so it gives identical token sets across checkpoints — which makes it the fair way to compare two models. |
| **Ablation** | Re-running with one thing changed, to see what that thing was doing. |
| **Checkpoint** | A saved copy of a trained model's weights. |
| **KV cache** | Memory the decoder holds during generation. Pruning shrinks the part of it that stores visual tokens. |
