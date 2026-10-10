"""Generate colab/reproduce_results.ipynb.

Kept as a generator rather than a hand-written .ipynb so the notebook is reproducible and
diffable as source, the same convention this project uses for kaggle_pruning_run.ipynb.
Regenerate after editing; never hand-edit the notebook.

    python colab/_generate_notebook.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "reproduce_results.ipynb")


def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src}


CELLS = []

CELLS.append(md(r"""# AdaptiveDonutOCR — reproduce the results

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/nafis8766/adaptive-donut-ocr/blob/main/colab/reproduce_results.ipynb)

**Runs in about a minute on a free CPU runtime. No GPU, no model weights, no dataset download.**

This notebook re-derives the headline numbers of
[AdaptiveDonutOCR](https://github.com/nafis8766/adaptive-donut-ocr) from the result artifacts
committed to the repository. Nothing here re-runs training — every figure is recomputed from
`results/*.json`, which is the same route the project's own auditors take on CPU.

The point is that you do not have to take the numbers on trust. What is being demonstrated is
the project's fourth claim: that the measurement layer is reproducible from cached artifacts.

---

### What you will see

| step | what it establishes |
|---|---|
| 1 | the repo's own numeric audit passes — 121 checks, 58 figures re-derived from artifacts |
| 2 | the budget table: pruning to 35% of visual tokens is free; the two tight budgets are costly |
| 3 | the selection-value table: learned ranking vs a random mask at matched budgets |
| 4 | the pre-registered merge scoring, which reports **UNDERPOWERED** on both runs |

Step 4 is the interesting one. It is the project scoring *itself* against a rule written in
advance, and returning a verdict that licenses nothing — including the project's own former
headline claim, which that scoring retired.
"""))

CELLS.append(md(r"""## 1 · Get the repository

If you opened this from GitHub via the badge above, Colab has not cloned anything yet, so this
cell does it. If you are running locally, it detects the checkout and skips."""))
CELLS.append(code(r'''import os, subprocess

REPO_URL = "https://github.com/nafis8766/adaptive-donut-ocr.git"
REPO_DIR = "adaptive-donut-ocr"

# Already inside a checkout? Then use it.
if os.path.exists("results/why_pruning_helps_local.json"):
    root = "."
elif os.path.exists(os.path.join(REPO_DIR, "results", "why_pruning_helps_local.json")):
    root = REPO_DIR
else:
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
    root = REPO_DIR

os.chdir(root)
print("working directory :", os.getcwd())

# The three artifacts every figure below is derived from. Assert they are present rather than
# letting a later KeyError look like a wrong number.
required = [
    "results/why_pruning_helps_local.json",   # D12: the budget curve, both checkpoints
    "results/budget_binding_local.json",      # D11: router vs random at matched budgets
    "results/kv_memory_local.json",           # M1:  cross-attention KV bytes
]
for p in required:
    assert os.path.exists(p), "missing artifact: " + p
    print("  ok  {:42s} {:>10,} bytes".format(p, os.path.getsize(p)))
'''))

CELLS.append(md(r"""## 2 · Run the repository's own numeric audit

`scripts/check_report_numbers.py` re-derives every load-bearing figure in the project's 5-page
report from a named field of a named artifact, then requires it to be present in the report.
It also carries a self-sabotage control: it corrupts a headline figure in memory and asserts
the audit goes red, so a passing run is known to be able to fail.

That control is not decoration. The first version of this script passed a corrupted headline
figure at exit 0, because the corrupted value happened to occur once in an archive by
coincidence — it was decorative, and the sabotage test is how that was found."""))
CELLS.append(code(r'''!python scripts/check_report_numbers.py'''))

CELLS.append(md(r"""## 3 · The budget table

Pruning to 35% of the visual tokens frees 65% of the decoder's cross-attention KV for −0.26
points of word recall. The deltas and *t* values below are recomputed from the stored
**per-image** recall arrays, paired across the same 50 documents — not read off a column."""))
CELLS.append(code(r'''import json, math

D12 = json.load(open("results/why_pruning_helps_local.json"))
M1  = json.load(open("results/kv_memory_local.json"))
MiB = 1048576.0

def row(ckpt, keep, field="word_recall_pct"):
    """A D12 row, selected by checkpoint substring and keep ratio."""
    return next(r[field] for r in D12["rows"]
                if ckpt in r["checkpoint"] and abs(r["keep_ratio"] - keep) < 1e-9)

def kv_bytes(vt):
    """M1's analytic cross-attention KV for a given visual-token count."""
    return next(r["cross_kv_bytes_analytic"] for r in M1["rows"]
                if r["visual_tokens"] == vt)

def paired(a, b):
    """Mean paired difference in POINTS, and its t statistic."""
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    return m * 100.0, m / (sd / math.sqrt(n))

base_kv  = kv_bytes(4800)
base_rec = row("run 9", 1.0, "per_image_recall")

print("{:>5} {:>7} {:>13} {:>8} {:>8} {:>8}".format(
    "keep", "tokens", "cross-KV", "recall", "delta", "t"))
print("-" * 56)
for k in (1.00, 0.50, 0.35, 0.25, 0.20):
    vt = int(round(k * 4800))
    rec = row("run 9", k)
    pct = 100 * (kv_bytes(vt) / base_kv - 1)
    if k == 1.0:
        delta, tstat = "ceiling", ""
    else:
        m, t = paired(row("run 9", k, "per_image_recall"), base_rec)
        delta, tstat = "{:+.2f}".format(m), "{:.2f}".format(t)
    print("{:>5.2f} {:>7} {:>10.2f} MiB {:>8.2f} {:>8} {:>8}   ({:+.1f}%)".format(
        k, vt, kv_bytes(vt) / MiB, rec, delta, tstat, pct))
'''))

CELLS.append(md(r"""### The same data, as a picture

The shape is the result: this checkpoint's curve is **flat** down to keep=0.35 and then falls
away. The second curve is a checkpoint that never trained with pruning, scored on
**bit-identical token sets** — it declines monotonically. That contrast is the entire finding,
and it is why the claim requires the word *if*."""))
CELLS.append(code(r'''import matplotlib.pyplot as plt

keeps  = [1.00, 0.50, 0.35, 0.25, 0.20]
tokens = [int(round(k * 4800)) for k in keeps]
aware  = [row("run 9", k) for k in keeps]   # trained WITH pruning
naive  = [row("run 5", k) for k in keeps]   # trained WITHOUT pruning

fig, ax = plt.subplots(figsize=(7.2, 4.2))
ax.plot(tokens, aware, "o-",  color="#1A4F8B", lw=2, label="trained with pruning on")
ax.plot(tokens, naive, "s--", color="#B0432A", lw=2, label="never trained with pruning")
ax.axvline(1680, color="#888888", lw=1, ls=":")
ax.annotate("keep=0.35\n65% of tokens cut\n-0.26 pts (t -0.18)",
            xy=(1680, 77.37), xytext=(2200, 56),
            arrowprops=dict(arrowstyle="->", color="#888888"),
            fontsize=9, color="#333333")
ax.set_xlabel("visual tokens retained (of 4,800)")
ax.set_ylabel("word recall (%)")
ax.set_title("Same token sets, different training - the difference is the result")
ax.invert_xaxis()
ax.grid(alpha=0.25)
ax.legend(fontsize=9, loc="lower left")
plt.tight_layout()
plt.show()

print("Both curves are scored on bit-identical token sets -- 'ink' selection is")
print("weight-independent -- so every gap between them is attributable to the weights,")
print("not to a different choice of which tokens to keep.")
'''))

CELLS.append(md(r"""## 4 · Learned selection vs a random mask

Random selection at the same budget is the floor a learned router has to clear. The margin
**widens** as the budget tightens: at a slack budget a random subset still catches most of the
text, so there is little for a selector to add; at a tight budget every retained token has to
carry glyphs."""))
CELLS.append(code(r'''D11 = json.load(open("results/budget_binding_local.json"))

def d11(mode, keep):
    """A D11 row for run 9's checkpoint at a given budget."""
    return next(r["word_recall_pct"] for r in D11["rows"]
                if r.get("select_mode") == mode
                and abs(r["keep_ratio"] - keep) < 1e-9
                and "run 9" in r.get("checkpoint", ""))

ks      = [0.50, 0.35, 0.25, 0.20]
router_ = [d11("router", k) for k in ks]
random_ = [d11("random", k) for k in ks]

print("{:>5} {:>8} {:>8} {:>8}".format("keep", "router", "random", "margin"))
print("-" * 32)
for k, a, b in zip(ks, router_, random_):
    print("{:>5.2f} {:>8.2f} {:>8.2f} {:>+8.1f}".format(k, a, b, a - b))

fig, ax = plt.subplots(figsize=(7.2, 3.6))
x = list(range(len(ks)))
w = 0.36
ax.bar([i - w / 2 for i in x], router_, w, label="router (learned)", color="#1A4F8B")
ax.bar([i + w / 2 for i in x], random_, w, label="random mask",      color="#B9C6D6")
for i, (a, b) in enumerate(zip(router_, random_)):
    ax.text(i, max(a, b) + 1.5, "+{:.1f}".format(a - b),
            ha="center", fontsize=9, color="#1A4F8B")
ax.set_xticks(x)
ax.set_xticklabels(["keep={:.2f}".format(k) for k in ks])
ax.set_ylabel("word recall (%)")
ax.set_ylim(0, 95)
ax.set_title("Learned selection vs random, at matched token budgets")
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.show()

print("Scope: this is a claim against RANDOM selection. It is NOT a claim that the")
print("router beats a hand-crafted ink heuristic -- that margin is t=+1.62 on n=50,")
print("under the threshold of 2.0 fixed in advance. Directional, not significant.")
'''))

CELLS.append(md(r"""## 5 · The project scoring itself

This is the part worth reading. The rule scored here was fixed **before** the run it was
written for — estimator, standard error, interval method, a tail statistic alongside the
location statistic, multiplicity treatment, and a verdict table stating what each verdict
licenses. That run was never collected, so the rule was applied **backwards** to two earlier
runs instead.

It did not return the headline those runs had been reported with. Watch for `UNDERPOWERED`."""))
CELLS.append(code(r'''!python scripts/score_preregistered.py'''))

CELLS.append(md(r"""## 6 · What this demonstrates, and what it does not

**What you just verified.** Every figure above was recomputed from a committed JSON artifact
on a CPU runtime, in about a minute, with no GPU, no weights and no dataset. That is the
project's methodological claim, and it is what makes the other three worth reading.

**What this notebook does not do.** It does not re-run training, and it cannot check a
*claim* — only the arithmetic. A figure can reproduce exactly and still belong to a verdict
the project has retired; that is precisely what happened here, when the pre-registered rule
above retired the project's own former headline (*"merging 20% is free"*) even though both of
its numbers still reproduce exactly from the original run. Deciding whether a sentence is
still the project's position is a job for reading, not for a script.

**Two things the project says about itself that are worth knowing:**

- **The merge axis is unresolved.** At a matched budget of 1920 tokens, merging versus simply
  pruning harder measures +1.66 [−0.81, +4.14] and +0.02 [−1.90, +1.94] across two runs, with
  **0 of 3** confirmatory quantities surviving Holm correction in either. `UNDERPOWERED`
  licenses nothing — not even "merging changes nothing". Reaching the target resolution needs
  roughly 307 documents; FUNSD's test split is 50, and that is the whole split.
- **There is no speed win.** Cutting 4,800 visual tokens to 960 — a 5× reduction — buys
  **1.04×** wall-clock, because the router sits *after* the frozen Swin encoder and all 4,800
  tokens are computed at every budget.

The [5-page technical report](https://github.com/nafis8766/adaptive-donut-ocr/blob/main/report/report.pdf)
has the full method and every scope limit. `AGENTS.md` in the repository is the source of
truth and wins on any disagreement.
"""))

NB = {
    "cells": CELLS,
    "metadata": {
        "colab": {"provenance": [], "toc_visible": True},
        "kernelspec": {"display_name": "Python 3", "name": "python3",
                       "language": "python"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 4,
}

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(NB, f, indent=1, ensure_ascii=False)
    f.write("\n")

ncode = sum(1 for c in CELLS if c["cell_type"] == "code")
print("wrote {}: {} cells ({} code, {} markdown)".format(
    os.path.relpath(OUT), len(CELLS), ncode, len(CELLS) - ncode))
