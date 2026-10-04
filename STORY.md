# The story of AdaptiveDonutOCR

*How this project actually went: what we set out to do at each stage, what went wrong, and what
we did about it. Written 2026-09-17, updated 2026-10-03 to cover today's worklog
(chapters 16–23, the one-page digest, and per-chapter summaries).*

*This is the narrative companion to the other documents in this repo.
[AGENTS.md](AGENTS.md) is the single source of truth — every number here comes from it, and where
the two disagree, AGENTS.md is right and this file is stale. [WRITEUP.md](WRITEUP.md) presents
the findings results-first, for a reader who wants the conclusions. [REPORT.md](REPORT.md) is a
standing summary. **This file is the only one organised by time rather than by result**, and it
is the one to read if you want to understand *why* the project looks the way it does.*

---

## How to read this

If you have one minute, read [**The whole story in one page**](#the-whole-story-in-one-page) and
stop. That is the version to send to a colleague.

If you have an hour, read the chapters in order. Each chapter now starts with an
**"in one line"** summary, so you can skim the shape of the story before committing to the detail.

Each stage below has the same three parts:

> **What we set out to do.** The plan going in, and the belief behind it.
> **What went wrong.** The result that did not match the belief.
> **What we did about it.** The fix, and what it cost.

You do not need a machine-learning background. The next section gives you everything you need.
Terms in **bold** on first use are defined in the glossary at the end.

---

## The whole story in one page

*The digest. The chapters below are the full version; this is the short one.*

1. **The question (Ch 0).** Donut reads a page by looking at 4800 small square-summaries, and
   most of the squares are blank. How few can you keep?
2. **The floor, and two wrong theories (Ch 1–3).** A 54% recall baseline. "Not enough data" —
   two runs, one of which said no. "The encoder is bad" — unfreeze it, and notice the model was
   stopping 29% early.
3. **The free lunch (Ch 4).** A decoding setting was capping output length. +27.18 points on
   *unchanged weights* — the largest single effect in the project. The run table restarts here.
4. **The router, backwards, then fixed (Ch 5–9).** It had learned to love blank paper because it
   was only ever trained when nothing was discarded. Ink supervision flipped the sign; the loss
   that trained it had a double-sigmoid bug; the safe fix grew the whole layer of verification
   the project is now famous for — and the ink proxy turned out to be the wrong objective.
5. **Better targets, no gain (Ch 10–11).** The decoder's own attention fits better and still
   moves nothing, because at that budget pruning already beat not-pruning. The latency claim
   dies (1.04× at 5× fewer tokens); the router's +17.7 to +34.0 points over random becomes a
   headline claim.
6. **The honest efficiency claim (Ch 12).** −65% of the decoder's cross-attention memory for
   −0.26 points. Cross-attention only; not total memory, not latency.
7. **"Why does pruning help?" (Ch 13–14).** Only because the model was trained for it. Five
   extra epochs buy +0.52 points. "If you train for it" is load-bearing.
8. **The half of the architecture that never ran (Ch 15).** The merger had `merge_ratio=0.0`
   everywhere, and its split was broken (100% of vertical redundancy missed). The checkerboard
   fix.
9. **The merge question, answered and re-scored (Ch 16–19).** Run 12 lands on the wrong
   checkpoint; run 13 on the right weights reads "20% merge is free, 40% costs ~4 points"; run 14
   trains with merging. Then we measure the instrument: 50 documents cannot resolve a 1–2 point
   question, and the scoring rule itself was unpinned — so the rule is written *before* the next
   data (the pre-registration), the past is re-scored under it, and "free" becomes
   **UNDERPOWERED**.
10. **The second corpus and its licence (Ch 19–21).** 397 documents (FUNSD + the SROIE mirror)
    are prepared and everything verified — then the mirror is rejected on licence; every
    alternative measures dead; the fix is the official ICDAR download, which is a human step, not
    an agent step.
11. **Where the merger lives (Ch 22).** It stays after the frozen encoder: its encoder saving is
    0% by construction, and the version that would pay is a new project, not a fix.
12. **Today (Ch 23).** A licence guard in `.gitignore` written *before* the data arrives, and the
    pre-registered thresholds re-derived at the official pool size (410 documents, not 397 — the
    plan survives). One step left: the ICDAR registration + download.

**The four claims we can defend (one line each):**

1. Pruning to a third of the visual tokens costs nothing — *if you train for it*.
2. The learned router beats random selection by +17.7 to +34.0 points at matched budgets.
3. −65% of decoder cross-attention memory for −0.26 points; of the 2.50× KV saving at
   prune-to-0.50-then-merge-0.20, **2.0× is pruning's and 1.25× is the merge step's**; and
   "merging is free" is not licensed yet (UNDERPOWERED at n=50, needs ≳307 documents).
4. The methodological layer — diagnostics that execute, verifiers that run the real code, a
   grading rule written before the data — is a first-class result in its own right.

**Where it is stuck:** one ingredient, a licensed second corpus. Everything else for the pooled
sweep is built, verified, and ≈5.9 hours from booking.

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

**In one line:** Establish the floor — 54% recall, a locked evaluation protocol, and nothing goes
wrong. The only chapter where nothing goes wrong.

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

**In one line:** Two runs try to prove "not enough data"; run 4's negative result kills the theory
and the expansion plan.

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

**In one line:** Unfreezing the encoder buys fidelity but loses recall — and exposes that the
model stops 29% early, which becomes the turning point.

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

**In one line:** A decoding setting, not the weights, was capping output length: +27.18 points on
unchanged weights, the largest single effect in the project.

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

**In one line:** The router had learned to love blank paper, because it was only ever trained in a
mode where nothing is ever discarded; the signal is real, it was just pointing the wrong way.

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

**In one line:** Ink is chosen as the training target with the reservation written down first, and
the ink-oracle and random rows that every later sweep depends on are built.

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

**In one line:** Ink supervision flips the sign decisively (the negated row collapses from 73.09
to 2.70); two procedural flaws are noted for the cost they later cost.

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

**In one line:** The loss had a double-sigmoid bug; the safe fix required three repairs (F1 the
loss, F2 the harness control, F3 telemetry) and the execute-the-real-code verification layer that
has defined the project's second half.

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

**In one line:** The fixed mechanism works exactly as designed (retained ink 0.790 → 0.922) and
accuracy falls: ink is a proxy, not the objective.

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

**In one line:** A better-motivated target (the decoder's own attention) fits better and still
moves nothing — the null was structurally guaranteed by the budget, because pruning already beat
not-pruning there.

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

**In one line:** At budgets that bind: the attention target loses (−5.63, −12.81), the latency
claim dies (1.04× at 5× fewer tokens), and the router's +17.7 to +34.0 points over random becomes
a headline claim.

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

**In one line:** The one honest efficiency claim survives: −65% of decoder cross-attention memory
for −0.26 points, scoped to exactly what it is.

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

**In one line:** Pruning helps only because the model was trained with it — run 5 declines where
"denoising" predicted improvement, so "if you train for it" becomes load-bearing.

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

**In one line:** Five extra epochs without pruning buy +0.52 points (t 0.24): the gain is the
pruning-aware training itself, and the main claim gets its isolation.

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

**In one line:** The merger had never executed and its split was broken (100% of vertical
redundancy missed); the checkerboard fix lands, and run 12's sweep runs with the
checkpoint-provenance question left open.

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

## Chapter 16 — The sweep finally runs on the right weights (runs 12, 13, 14)

**In one line:** The merge question gets its real answer — run 12's provenance doubt is
confirmed, run 13 re-runs the sweep on the intended weights and reads "20% merge is a null, 40%
costs ~4 points", and run 14 shows that quoting one column of four is how you mislead.

> **What we set out to do.** Settle run 12's open question, then actually answer *is merging
> better than pruning at a fixed token count?* on the intended weights, and finally train *with*
> merging so the checkpoint's own operating point is a merged one.
>
> **What happened with run 12.** The provenance question from the previous chapter is settled:
> yes, it was run 5's checkpoint (the stamp names it, and its router arm reproduces the D1
> inversion to the digit — router 24.97 against random 59.06 and ink oracle 73.69). So run 12's
> router pairs are not a measurement of the merge stage at all; only the two ink-oracle pairs —
> weight-independent — are interpretable. The sweep machinery itself (28 rows, six token-matched
> pairs, the sabotage arm) worked exactly as designed.
>
> **Run 13** re-ran the identical 28-row sweep on the intended weights (run 9's). The control
> drift was 1.09 points, so the ground had not moved. The headline, at face value:
>
> - **20% merge is a null at all four budgets** — five m=0.20 rows, all inside their own
>   uncertainty.
> - **40% merge at keep=0.50 costs −3.86 points [−7.54, −0.35]** — the first merge row that
>   actually costs something.
>
> That is the merge result of record. It is also, as the next chapters show, a number that had
> not yet survived its own measurement instrument.
>
> **Run 14** is the arm that was missing: not just *evaluating* merge but **training with merge
> on** (`TRAIN_MERGE_RATIO=0.40`), so the checkpoint is merge-aware and its trained operating
> point is a merged one — keep=0.50 → 2400 tokens, merge 40% of those → **M=1440**:
>
> | | run 9 (no merge, M=2400) | run 14 (merge-trained, M=1440) |
> |---|---|---|
> | word recall | 79.63 | 78.87 |
> | char accuracy | 64.81 | 61.76 |
> | word order | 54.08 | 50.13 |
> | NED | 0.352 | 0.382 |
>
> "Run 14 matches run 9 with 40% fewer tokens" is quoting **one column of four**. Recall barely
> moved; the other three metrics clearly did not.

---

## Chapter 17 — The instrument is coarser than the question (D13, D14)

**In one line:** Before scoring any more merge numbers, we measured the instrument: 50 documents
cannot resolve a 1–2 point question, and it turned out we could pick the scoring rule to make
any answer come out we wanted.

> **What we set out to do.** Run 13 read "20% merge is free". Before buying more runs on that,
> measure the instrument itself: how variable are the per-document differences, and can 50
> documents resolve effects of the size we are looking for?
>
> **What we found. Two diagnostics, both aimed at our own analysis.**
>
> **D13 — the power problem is structural.** The merge question is a 1–3 point question. The
> per-document differences have a standard deviation of 11–13 points. With 50 documents, a
> confidence interval is 2–5 points wide. **UNDERPOWERED is not what run 13's result happened to
> be; it is what the instrument delivers at n=50, full stop.** Worse: 5 of the 50 documents carry
> **75.6%** of the total variability — the difference distribution is heavy-tailed, and a single
> page can lose 72 points while the average barely notices. Measured: both natural location
> estimators (the plain mean, and the trimmed mean we were considering) hide that −72 point page.
> A rule with only an average is therefore not a rule; it must carry a **tail** statistic in the
> same breath.
>
> **D14 — the estimator was the smallest choice.** The pre-registration item had been scoped as
> "pick an estimator". D14 found the estimator is the smallest of **seven** unpinned choices:
> which two rows *are* "the" contrast ("run 14, m=0.40" names two contrasts that differ by
> **5.08 points**), direction per quantity, which location statistic and in what order, which
> tail statistic and what its ties mean, what the discard set may contain, and what counts as
> confirmatory. And over the families the historical runs actually support, **Holm correction
> leaves zero survivors in either run** — both published "MERGING WINS" verdicts sat on *disjoint*
> rows.
>
> **What we did about it.** Nothing in the data can be fixed; the response is procedural:
> **the entire grading rule gets written down, in full, before the next merge number exists.**

---

## Chapter 18 — The grading rule written before the data (T1, the run-17 pre-registration)

**In one line:** One question named, one estimator pinned, a tail check beside the average, three
quantities corrected together, four verdicts of equal arity — and the number of documents
(≳307) that "free" will require.

> **What we set out to do.** Write the rule D14 said was missing, with every choice blind to the
> sign of any effect.
>
> **The rule, in plain words.**
>
> 1. **Name the question first.** *At an equal budget of 1920 tokens, does merging preserve more
>    word recall than pruning alone?* The arms: `keep=0.50 m=0.20 ink` against `keep=0.40 ink
>    TWIN` — the ink arm, because the sweep's own table says that is the arm that isolates the
>    mechanism from the router's weakness. This pair had **never been declared a winner**, which
>    is evidence the choice was not effect-shopping.
> 2. **The average.** Take each document's difference (the document is the unit of analysis; the
>    pairing is the design), then **trim the most extreme 10% before averaging** — the trimmed
>    mean. Uncertainty is the **Tukey–McLaughlin** standard error (the naive version is ~33% too
>    small, which is exactly how it looks on paper). No bootstrap: a bootstrap endpoint is one
>    draw, not a value, and we had just watched verdicts turn on that kind of noise.
> 3. **The tail, in the same breath.** Two checks on the worst documents, each normalised against
>    the row's own *matched-normal null* — a simulation of "what the worst document looks like
>    when everything is noise, at this n and this variability", run at scoring time so the bar
>    tightens as n grows instead of being a constant: a worst-document ratio, and a count of
>    documents that lost more than 10 points. On the data we already had, run 14's primary reads
>    +0.02 points — the cleanest "no measured cost" imaginable — and **fails both**: its worst
>    document lost 40.00 points (ratio 3.22, above even the null's p99) and 5 documents were
>    harmed against a null p95 of 4. A rule without a tail would report that row as a perfect
>    null.
> 4. **Three quantities, corrected together.** Word recall (primary), NED ≡ character accuracy
>    (co-primary; they are one quantity, so we count it once), and word order (co-primary — not
>    stored in runs 13/14, so the three-way family is *written* now and *exercised* from run 17
>    onward, not quietly dropped to two). **Holm** step-down at 5%, so testing three quantities
>    does not inflate the false-alarm rate.
> 5. **Four verdicts of equal arity.** DEGRADED (a confidence interval excluding 0, negative, on
>    any of the three), IMPROVED (positive on the primary), FREE (all three include 0, **and**
>    the resolution is ≤ 1.0 point, **and** both tail gates pass), and UNDERPOWERED (any
>    confirmatory quantity flat with resolution > 1.0 point). The one deliberate asymmetry: harm
>    on any quantity fires DEGRADED, but a gain on a secondary does not fire IMPROVED — a harm
>    signal is still harm, while a gain signal on a secondary is metric-shopping.
>
> **The number the whole thing turns on:** at n=50 the resolution is 2.48 points (run 13) / 1.92
> (run 14). The FREE verdict needs resolution ≤ 1.0 point, which at run 13's variability requires
> **≳307 documents**. Fifty is a sixth of that. **The FREE verdict is unreachable on FUNSD
> alone. That is the finding, not a footnote.**

---

## Chapter 19 — Re-scoring the past, and finding the corpus was not the whole problem (T2, T3)

**In one line:** A second corpus is needed (397 documents, chosen on what it measures, not its
size), and when the new rule re-scores the old runs, "free" becomes UNDERPOWERED and two more of
our own headlines die.

> **What we set out to do.** T1 said n ≳ 307, so find the second corpus; then re-score runs 13/14
> under the new rule before anyone quotes them again.
>
> **T2 — the corpus decision, and why size was not what decided it.** Two candidates, both
> verified *by loading them* rather than trusting memory: CORD's test split is exactly 100
> documents, SROIE's mirror is exactly 347. CORD has the cleaner licence (first-party, CC-BY-4.0,
> published by the same organisation that publishes the base model we use) — and the wrong
> **denotation**: its ground truth annotates the receipt's key-value lines (menu, total, address)
> but not the whole page, so its recall measures a different quantity from FUNSD's, and its grain
> (1 word = 4.24 points) is four times coarser than the 1.0 point we want to resolve. Pooling
> them would average two different metrics under one name. **SROIE has the right denotation — a
> whole-page transcription — and the wrong licence story**: a bare "MIT" asserted by the uploader,
> with zero attribution to the ICDAR competition the scans actually come from. The ruling on that
> came later (Chapter 21); at this point the pool was **FUNSD + SROIE = 397**, which clears the
> 307 requirement with margin.
>
> **T3 — the re-scoring, done by an executable scorer, not by prose.** `score_preregistered.py`
> (45 controls, all passing) re-derives everything under the pinned rule:
>
> - **The pre-registered primary is UNDERPOWERED in both runs**: +1.66 [−0.81, +4.14] in run 13,
>   +0.02 [−1.90, +1.94] in run 14. Zero Holm survivors. And run 14 does not score "free" despite
>   +0.02, because both tail gates fail — the one behaviour the rule was written to produce.
> - **Caveat (i): "free" is not sign-robust.** Claim 3's +0.54 was a plain mean; under the pinned
>   estimator the same row reads **−0.65** in run 13 — and **+0.16** in run 14. All of them are
>   nulls, so "no measured cost" survives; the sign does not.
> - **Caveat (ii): the tail.** Run 14's m=0.40 row at M=1440 contains a page that lost
>   **72.34 points**. The trimmed mean is blind to it *to the last bit*: pushing that page 25
>   points further moves the trimmed estimate by exactly 0.0e+00, while the plain mean moves by
>   181% of the row's own effect.
> - **Finding 1: "resolved and negative" does not replicate.** The M=1440 price: run 13 gives
>   −3.23 [−5.70, −0.76] (excludes zero); run 14 gives −0.17 [−2.40, +2.06] (includes zero). A
>   sentence stated as *resolved* is denied by one of its two runs.
> - **Finding 2: one sentence paired two baselines.** The 2.50× KV figure is measured against
>   keep=1.00; the +0.54's control row is M=2400. The merge step alone is **1.25×**; the other
>   2.0× belongs to pruning.
> - **Finding 3: the tail gate is not specific to merging.** In the direction the design forces,
>   **13 of 21 contrasts containing no merging at all** fire the gate, and the sweep's worst
>   per-document loss (−80.85 points, ratio 5.43) belongs to `keep=0.75 ink ORACLE` — a row where
>   *nothing is merged*. So a firing gate cannot be attributed to merging until an active
>   comparator exists: **a random arm at a matched token budget. Neither run has one** — the merge
>   budgets are [1344, 1440, 1920, 3840], the random budgets [1680, 2400, 3600], and the two
>   lists do not overlap. Any past "merging beats random" statement was comparing across budgets.
>
> **What we did about it.** Rewrote claim 3 (its merge sentence now carries the rule's interval
> and both caveats), promoted the missing random arm to a **build requirement** of the next sweep
> (it becomes the 29th row), and recorded that the gate's bar must come from that active
> comparator, not from the normal null alone.

---

## Chapter 20 — The pooled sweep is built, and the notebook on disk was a cancelled run's config (T4)

**In one line:** Everything for the 397-document sweep is built and verified — and the day we
checked, the notebook on disk was set to *train* an unauthorised run, through a generator that
no longer ran.

> **What we set out to do.** Port the 28-row sweep to the pooled corpus: eval-only, no training,
> roughly six hours on Kaggle.
>
> **What shipped (PATCH I).** A `PooledTestSet` that loads both corpora behind one interface
> (397 documents), a per-document `corpus` label so every row reports **per-corpus strata** (the
> pool is 87% receipts by document — a pooled number is substantially a *receipt* number, and
> FUNSD, where every result from runs 2–14 was measured, is a 12.6% minority of its own
> successor), `word_order` now stored per document (so the three-quantity rule becomes
> executable from run 17 on), and the **29th row: `keep=0.40 random TWIN` at M=1920** — the
> token-matched random arm T3 promoted from a check to a blocker.
>
> The cost was measured by actually generating, not by arithmetic: SROIE documents generate
> 0.66× the tokens of FUNSD's, so the sweep is **5.92 hours** against the 9-hour Kaggle cap, not
> the naive 8.06.
>
> **What went wrong — found 2026-10-02 by *running* the generator instead of reading it.** The
> notebook on disk shipped `DO_TRAIN = True` and `TRAIN_SELECT_MODE = 'ink'`: **run 18's
> config** — a training run staged by a parallel session whose chat was lost to context
> compaction, authorised by nothing in the repo, and off the serial queue. The user's ruling:
> **cancelled, not deferred** — and the SROIE mirror **rejected on licence** (Chapter 21).
>
> Worse: the generator itself had stopped running (a stale patch anchor), so **none of the
> "green" verifiers had ever executed against a T4 notebook** — they all certified the armed
> run-18 config. A ~4-hour training run was one Run-All away from executing on the pooled corpus.
>
> **What we did about it.** Re-keyed the anchor so config flips cannot rot it again, reverted the
> select mode to `router`, **wrote the guard the code comment claimed already existed** (an
> eval-only run must load a pruning-era checkpoint; attaching run 5's weights now *raises*
> instead of sweeping 29 rows through an anti-selective router — run 12, one assert away),
> regenerated the notebook (cell 2 only, every other cell diffed byte-identical; the armed
> notebook is archived as evidence, not deleted), and re-ran **five** verifiers *after* the
> regeneration, checking each log is newer than the notebook it reads: **14/14** (the new guard,
> sabotage-tested — deleting it takes the verifier to 8/14, exit 1), **96/96, 35/35, 62/62,
> 64/64**.
>
> **The generalised lesson:** an edited generator is an unverified generator. Regenerating is not
> a deployment step to do when convenient; it *is* the test. And a verifier log that predates the
> input it reads is not evidence, however green it is.

---

## Chapter 21 — Why every alternative corpus measured dead, and the step that remains (the licence ruling)

**In one line:** "Just switch datasets" has no target — the one clean-licence corpus measures the
wrong thing — so the ruling is against the *mirror*, not the corpus, and the remaining step is a
human one.

> **What we set out to do.** The ruling "I would rather switch datasets than get into copyright
> issues" looked like it would collapse the pool to FUNSD-only and make UNDERPOWERED permanent.
> So: measure every alternative on disk before accepting that.
>
> **What we found — two defects, on opposite corpora, neither fixable by swapping.**
>
> | corpus | test n | 1 word = | denotation | licence as it reads locally |
> |---|---|---|---|---|
> | FUNSD | 50 | 0.57 pt | whole page (the reference) | — |
> | SROIE mirror | 347 | 0.86 pt | whole page ✅ | `mit`, **uploader-asserted** ❌ |
> | CORD | 100 | 4.24 pt | **key-value lines only** ❌ | `cc-by-4.0`, first-party ✅ |
> | SynthDoG | — | — | whole page | *empty* ❌, and contaminated |
>
> CORD is first-party and clean — and unusable: across its entire test split the `dontcare` field
> yields **zero recoverable words**, so it cannot be converted into a whole-page target, and at
> 4.24 points per word a single word moves recall by more than four times the effect being
> resolved. SynthDoG's licence field is empty in both its README and its metadata, and runs 4/5
> trained on it. FUNSD's own 149-document train split is contaminated (training on it would bias
> the paired differences *toward null* — precisely the verdict we are trying to separate from
> UNDERPOWERED) and 199 < 307 anyway.
>
> **What that leaves: option 1, re-sourcing SROIE from the official ICDAR 2019 competition.** It
> keeps every number in the pre-registration intact (the pool, the thresholds, the 29-row sweep,
> the 5.9-hour cost, all the green verifiers) at zero code churn — the only reason it is worth
> checking at all.
>
> **And why the first step is the user's, not an agent's.** Two consecutive sessions failed to
> read the competition's terms for *structural* reasons: web search is unsupported for this
> model, and the RRC host serves a certificate for a different domain than the one requested, so
> the connection cannot be verified. **A licensing decision must not rest on a source that cannot
> be authenticated.** So: register at the portal, read the terms, download.
>
> **The one cost that was anticipated, then tested.** Official SROIE ships *line-level*
> transcriptions where the mirror had *per-word* boxes, so word-level ground truth might need
> re-deriving. A local probe (`diagnose_gt_granularity.py`, 4/4 controls) re-scored FUNSD through
> reconstructed lines with the *shipped* pipeline: **word recall is granularity-invariant** — the
> denominator is identical on 50/50 documents, and recall moved on 0 of 35 mismatches. The primary
> quantity is safe. **Word order and NED are not** (the gold *sequence* differs on 21/50
> documents), so those two co-primaries must be reported per-corpus-stratum, and the probe must be
> re-run against the official annotations when they arrive.

---

## Chapter 22 — Where the merger lives, decided (T5)

**In one line:** ToMe stays where it is — after the frozen encoder, before the decoder — because
its encoder saving at its current spot is 0% by construction, and the version that would pay is a
new project, not a fix.

> **What we set out to do.** Decide in writing, before the next merge run, whether ToMe stays
> post-encoder or moves *inside* Swin. The decision gates the two queued training runs: if the
> answer is "move it inside", they are moot as designed.
>
> **What we measured.** An analytic FLOPs proxy per Swin stage, computed from donut-base's own
> config (5/5 controls, tied to the repo's token grid):
>
> | stage | tokens | blocks | share of encoder |
> |---|---|---|---|
> | 0 | 307,200 | 2 | 10.8% |
> | 1 | 76,800 | 2 | 10.2% |
> | 2 | 19,200 | 14 | **69.2%** |
> | 3 | 4,800 | 2 | 9.7% |
>
> The merger sits after stage 3's 4,800-token output — downstream of **all 20 encoder blocks**, so
> its encoder saving is not small, it is **zero, by construction**. Moving it one stage earlier
> caps at **4.9%** even at a 50% merge (only 9.7% of the encoder is downstream of that point). The
> version that would pay must precede stage 2: a 19,200-token grid inside a frozen pretrained
> encoder, where window partitioning, shifted-window cyclic shifts and relative position bias all
> assume an intact spatial grid — plus re-establishing every comparability baseline in the
> project (the 77.74 ceiling, run 9's checkpoint, D11, D12, M1). That is a new project with the
> same title.
>
> **The decision: keep it.** Consequences, both directions:
>
> - **Forbidden:** any encoder-FLOPs / speedup / latency framing for the merger (0.0% is measured
>   and structural); quoting the 2.50× as a merging result (pruning supplies 2.0× of it; the
>   merge step alone is **1.25×**); calling the compression "free" (UNDERPOWERED in both runs,
>   required n ≳ 307).
> - **Not mooted:** the two queued training runs. ToMe's entire remaining justification is one
>   narrow claim — *at a matched token budget, merging preserves more accuracy than pruning* —
>   evaluated on the decoder's cross-attention KV, which is where the project's one true
>   efficiency claim lives.

---

## Chapter 23 — Today: guarding the door before the data arrives (2026-10-03)

**In one line:** Two unrecorded artifacts landed today — a licence guard written *before* the
data, and the pre-registered thresholds re-derived at the official pool size — and the only step
left is a human one.

> **What arrived, and why it is recorded here instead of left to the filesystem.**
>
> 1. **A licence guard in `.gitignore`, added before the download rather than after.** This repo
>    is public, and the ICDAR terms may forbid redistribution — republishing the corpus from a
>    public clone would be an irreversible disclosure. So `data/`, `corpora/`, and any SROIE path
>    are git-ignored *now*: a bulk `git add -A` over a downloaded corpus directory cannot leak it
>    into version history. If the terms turn out to permit redistribution, those lines come out
>    deliberately, with a note in AGENTS.md — the data must not arrive in history as a side
>    effect.
> 2. **The pre-registered tail-gate threshold, re-derived at the official pool size.** The mirror's
>    SROIE test split was 347 documents; the official one is evidently **360** — the pool would
>    be **410, not 397**. Running the shipped null simulator (its n=50 and n=397 controls both
>    reproduce the recorded values to 3 dp, so the measurement is trustworthy) gives the
>    matched-normal p95 **1.5088 at n=410**, against 1.5062 at n=397: a +0.0026 change. The plan
>    survives; the number is now off the right pool.
>
> **Status.** Everything agent-side is built and verified: the pooled loader, the 29-row sweep
> with its token-matched random arm, the executable three-quantity rule, five green verifiers with
> provenance-checked logs, and ≈5.9 hours of measured cost. **The blocker is the ICDAR
> registration + download, and it is the user's step by design.** After it lands: verify the
> terms, re-run the two granularity probes against the official annotations, adapt the loader if
> the schema differs (it currently expects the mirror's field names, and the port check *asserts*
> that), re-run the five verifiers against the regenerated notebook with mtime checks — and book
> the sweep.

---

## Where the project actually stands

*Current as of today's worklog, 2026-10-03. The queue itself lives in AGENTS.md; this is the
narrative version.*

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
3. **One measured efficiency claim, with its price attached.** The memory half is unchanged and
   still measured: cross-attention KV 150.00 → 52.50 MiB (−65.0%) at keep=0.35 for −0.26 points,
   and extended to the merge rows — prune to 0.50 then merge 0.20 → M=1920, cross-KV 150.00 →
   60.00 MiB (2.50×), of which **2.0× is pruning's and 1.25× is the merge step's**. The accuracy
   half, re-scored under the pre-registered rule, is **UNDERPOWERED in both merge runs at n=50**
   (needs ≳307 documents), and the 2.50× row contains a single page that lost 72.34 points.
   Cross-KV only — not total, not peak, not encoder, **not latency**. The merger sits after the
   frozen encoder, so it saves no encoder compute either (T5).
4. **The methodology is a first-class result.** Diagnostics that re-derive their numbers from
   cached artifacts, verifiers that *execute* the real notebook cells, an executable scorer for
   the pre-registration, and the 2026-10-02 generator/notebook incident caught by running things
   instead of reading them. Three correctness defects were found this way rather than by a run
   failing; the count has only gone up.

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
| "20% merge is free, 40% costs −3.86" (the run 13/14 headline) | T3 under the T1 rule: the pre-registered primary is UNDERPOWERED in both runs; "free" is not sign-robust; the M=1440 price is not replicated (−0.17 [−2.40, +2.06] in run 14) |
| "Merging beats random at matched M" | Not computable from runs 13/14 — their merge and random budgets do not intersect. Now a required 29th row of the sweep, not a statement |
| Any encoder-FLOPs / speedup framing for the merger | T5: 0% encoder saving by construction; the merge step is 1.25× of the 2.50× KV figure |
| The SROIE HF mirror as the second corpus | Licence rejected 2026-10-02 (uploader-asserted MIT, zero attribution to ICDAR RRC) |
| CORD as the second corpus | Denotation (annotates the key-value subset, not the page) and grain (4.24 pts/word), both measured |
| Run 18 (the ink select-mode training arm) | Cancelled 2026-10-02: staged by a lost session, authorised by nothing, off the serial queue |

### Still open

- **A licensed second corpus — the only remaining blocker.** Everything else in T4 is built and
  verified (five verifiers green with provenance-checked logs; ≈5.9 h measured cost). The step
  that remains is the user's: register at the ICDAR RRC portal, read the terms, download the
  official SROIE (decided 2026-10-02, option 1).
- **Then, in queue:** T6 (train the symmetric checkpoint `keep=0.30, merge=0.0`, ≈4–4.5 h) and T7
  (the redesigned merge run on the pooled corpus, ≈2–3 h; the pre-registered primary becomes
  scorable at n=410).
- **Housekeeping (T8):** REPORT.md is stale — its banner still says "ToMe has never executed" and
  its run table stops at run 10. This file now covers today's worklog but **has no numeric
  audit** (every figure here is transcribed from AGENTS.md; if a number is corrected there, this
  file goes stale). Dead code at `src/model.py:248`: `final_coords` is computed and thrown away.
- **Older open items, still standing:** the ~18% of outputs that are not valid JSON, which nobody
  has characterised; local-vs-Kaggle generation drift, written up as a limitation — run 5 reads
  74.72 locally against 77.74 on Kaggle on identical weights and images, and the gap widens as
  the budget tightens. Token *selection* reproduces bit-exactly; *generation* does not. **This is
  why nothing in the analysis compares a local number to a Kaggle one — within-checkpoint deltas
  are the comparable quantity.**

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

**9. Write the grading rule before the data.** D14 found seven unpinned choices, any one of which
could move the verdict by several points; runs 13/14 had both declared "MERGING WINS" on *disjoint*
rows. So the rule — which rows, which estimator, which tail check, thresholds in points, Holm over
which family, what each verdict licenses, how many documents "free" costs — was written **before
run 17 existed**, and re-scoring the past under it killed two of the repo's own headlines. A rule
written after the data is not a rule; it is a story.

**10. Measure the instrument before booking the experiment.** D13: 50 documents against 11–13
points of per-document variability cannot resolve a 1–2 point question — UNDERPOWERED was not run
13's result, it was the instrument's design. And the instrument's blind spot is asymmetric: the
average is provably blind to a single −72-point page, so any accuracy-*preservation* rule needs a
tail statistic in the same breath as the location one.

**11. A licensing decision must not rest on a source you cannot authenticate.** Two agent attempts
to read the ICDAR terms failed for structural reasons (web search unsupported for this model; the
competition host's certificate mismatch), and the mirror's "MIT" was an uploader's assertion with
zero attribution. So the download is a human step — register, read, download — and the repo got a
git-ignored data guard *before* the data arrived, so a bulk add cannot leak a possibly
non-redistributable corpus into a public history.

**12. An edited generator is an unverified generator.** The shipped notebook carried a cancelled
run's config (`DO_TRAIN=True`, an unauthorised select mode) because the last regeneration that had
ever *run* was of the wrong thing — and the generator behind it had been silently crashing on a
stale anchor for two days. All four "green" verifiers were certifying the armed config.
Regenerating is not a deployment step to do when convenient; it *is* the test. Corollary: a
verifier log older than the input it reads is not evidence, however green it is — check the
mtime.

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
| **SROIE** | The receipt-OCR dataset from the ICDAR 2019 Robust Reading Competition. The intended second test corpus; the HF mirror is licence-rejected, the official download is the remaining step. |
| **CORD** | A Korean receipt dataset with a clean first-party licence; excluded because it annotates only the key-value lines of a receipt, not the whole page. |
| **Word recall** | Our main metric: percentage of the correct words that appeared in the output. |
| **pts** | Percentage points. |
| **t** (t-statistic) | Roughly, effect size divided by its uncertainty. Above ~2 in absolute value is conventionally "probably real"; near 0 means indistinguishable from nothing. |
| **SE** (standard error) | How much the measured number would wobble if we re-ran on different images. |
| **Paired** | The two things being compared were measured on the *same* 50 images, which cancels out per-image difficulty and makes small differences detectable. |
| **Underpowered** | We could not have detected an effect this size even if it existed — importantly **not** the same as "there is no effect". |
| **UNDERPOWERED** | The pre-registered verdict (capitalised) for "too few documents to resolve this question". It licenses nothing and must be quoted with the required n. |
| **Ink oracle** | A selector that picks the highest-contrast squares directly from pixels. Weight-independent, so it gives identical token sets across checkpoints — which makes it the fair way to compare two models. |
| **Ablation** | Re-running with one thing changed, to see what that thing was doing. |
| **Checkpoint** | A saved copy of a trained model's weights. |
| **KV cache** | Memory the decoder holds during generation. Pruning shrinks the part of it that stores visual tokens. |
| **Pre-registration** | Writing the exact grading rule — which rows to compare, which estimator, which tail check, thresholds in points, what each verdict licenses, how many documents "free" requires — before the data exists, so the rule cannot bend to fit the result. |
| **Trimmed mean** | An average computed after discarding the most extreme 10% of values in each tail; resistant to a single disaster page without giving up the rest. |
| **Tail gate** | A check on the worst individual documents, reported beside the average, because the average is provably blind to a single −72-point page. |
| **Matched-normal null** | A simulation of "what the worst document looks like when everything is noise, at this row's own n and variability" — the tail gate's bar tightens as n grows instead of being a constant. |
| **Token-matched** | Two sweep rows that hand the decoder the same number of tokens, so the only difference between them is how the tokens got there (merged vs pruned harder). |
| **Denotation** | What the ground truth actually measures. Two corpora can both be "receipts" and still score recall against different denominators. |
| **Holm correction** | A step-down way of testing several quantities at once that keeps the overall false-alarm rate at 5%. |
| **Checkpoint provenance** | Which weights a result was actually measured on, recorded in the result's own file so it can be checked later (the field that caught run 12). |
| **mtime** | A file's modification time. Used to prove a check ran *after* the thing it checked. |
