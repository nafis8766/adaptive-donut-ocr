"""Adopt the Phase 2c ablation winner as the notebook's decoding default.

EVIDENCE (results/ablation_decoding.json, 50 FUNSD test docs, run-5 weights,
CONTROL row reproduced run 5 with 0.00 pt drift):

    config                recall  charAcc   order    NED  predW  goldW   len%  cap%  json%
    baseline (run5)        50.56    40.97   26.49  0.590   80.5  113.0   71.3     0    0.0
    no ngram block         50.56    40.97   26.49  0.590   80.5  113.0   71.3     0    0.0
    no rep penalty         77.74    64.70   53.05  0.353  111.9  113.0   99.0     0   82.0
    both off               71.03    59.16   51.30  0.408  140.8  113.0  124.6    22   70.0
    both off + minlen      71.03    59.16   51.30  0.408  140.8  113.0  124.6    22   70.0

Two findings, and the knobs turn out to INTERACT:

1. `repetition_penalty=1.3` was the entire cap. Removing it: recall +27.18,
   char acc +23.73, word order +26.55, NED -0.237, and output length goes
   71.3% -> 99.0% of gold. Mechanism: HF divides the logit of every token
   already in the sequence. A full-page form legitimately re-uses its whole
   vocabulary (field labels, digits, punctuation, common words), so after ~80
   words nearly every plausible continuation is penalized -- while EOS, never
   emitted, is not. EOS wins, the model closes the JSON and stops mid-page.

2. `no_repeat_ngram_size=3` was NEVER the cause -- rows 1 and 2 are
   bit-identical, so the trigram blocker was a no-op at rp=1.3 (nothing ever
   repeated for it to block). But it EARNS ITS KEEP once rp is removed: without
   it ('both off') the model over-generates to 124.6% of gold and 22% of docs
   run into max_length -- classic greedy repetition collapse -- costing 6.71 pts
   of recall vs keeping it.

So the fix is rp 1.3 -> 1.0, KEEPING the trigram block as the collapse guard.
Not "both off", which the row order makes tempting.

`min_new_tokens=64` never bound (mean generation is 328 tokens) -- rows 4 and 5
are bit-identical. Not adopted; it would be dead configuration.

Also explains a bug filed separately as cosmetic: valid JSON 0.0% -> 82.0%. The
malformed `{"text ` (missing `": `) was the same penalty eating the repeated `"`
token in the structural prefix. One knob, both symptoms.
"""
import ast
import json
import os
import shutil

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
BAK = NB + ".bak-decode-default"

if not os.path.exists(BAK):
    shutil.copyfile(NB, BAK)
    print(f"backup written: {os.path.basename(BAK)}")
else:
    print(f"backup already exists, left as-is: {os.path.basename(BAK)}")

nb = json.load(open(NB, encoding="utf-8"))


def sub(text, old, new, label):
    n = text.count(old)
    assert n == 1, f"[{label}] expected 1 match, found {n}"
    return text.replace(old, new)


def get(i):
    return "".join(nb["cells"][i]["source"])


def put(i, text):
    ast.parse(text)  # guard: edited cell must still be valid Python
    nb["cells"][i]["source"] = text.splitlines(keepends=True)


# ---------------- Cell 7: generate() decoding defaults ----------------
c = get(7)

c = sub(c,
r"""        # Aggressive pruning makes greedy decoding prone to repetition
        # collapse; a mild penalty + n-gram block ~doubles char accuracy.
        gen_kwargs.setdefault('repetition_penalty', 1.3)
        gen_kwargs.setdefault('no_repeat_ngram_size', 3)""",
r"""        # Decoding defaults set by the Phase 2c ablation (50 FUNSD docs, run-5
        # weights, CONTROL row reproduced run 5 to 0.00 pt). See
        # results/ablation_decoding.json.
        #
        # repetition_penalty MUST stay 1.0. At the old 1.3 it capped output at
        # 71% of gold length and cost 27.2 pts of recall: HF penalizes every
        # token already emitted, but a full-page form legitimately re-uses its
        # whole vocabulary, so after ~80 words every plausible continuation is
        # downweighted while EOS -- never emitted -- is not. EOS wins and the
        # model stops mid-page. It also ate the repeated '"' in the JSON prefix
        # (valid JSON 0% -> 82% once removed).
        #
        # no_repeat_ngram_size stays 3. It was a no-op at rp=1.3 (nothing
        # repeated for it to block), but with rp=1.0 it is the guard against
        # greedy repetition collapse: dropping it over-generates to 124.6% of
        # gold, sends 22% of docs into max_length, and costs 6.7 pts of recall.
        gen_kwargs.setdefault('repetition_penalty', 1.0)
        gen_kwargs.setdefault('no_repeat_ngram_size', 3)""",
"c7-decode-default")
put(7, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: cell 7 repetition_penalty default 1.3 -> 1.0 (trigram block kept at 3); "
      "cell parses as valid Python.")
print("\nExpected effect on a plain eval run (no overrides): run-5 weights should now "
      "score ~77.7 recall / 64.7 charAcc / 53.0 order / NED 0.353, not 50.56 / 40.97 / 26.49.")
