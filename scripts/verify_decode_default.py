"""Verify the new decoding defaults RUN and behave, per the standing
"check it runs, not that it parses" rule.

The risky part is not the number itself, it is what the change does to the
ablation harness. The ablation's row 0 is the CONTROL: it passes
repetition_penalty=1.3 EXPLICITLY to reproduce run 5. If the new default of 1.0
were to win over that explicit kwarg, the control would silently become a
duplicate of the new default and the whole ablation would lose its reference
point -- while still printing a table that looks fine.

So this checks, by executing the notebook's own code:

  1. the real gen_kwargs block from cell 7 yields rp=1.0, nrns=3 with no kwargs
  2. an explicit rp=1.3 STILL overrides the new default (control stays a control)
  3. an explicit rp=1.0 is a no-op relative to the default (idempotent)
  4. the 1.3 default is gone from cell 7 -- no stale copy left behind
  5. rp=1.0 is a genuine identity for HF's processor (not merely "close"), and
     nrns=3 really does block a repeated trigram -- i.e. the retained guard is
     actually load-bearing, using the installed transformers, not an assumption
  6. the full ablation cell still execs end-to-end against stubs
"""
import io
import json
import re
import sys

import torch

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cells = ["".join(c["source"]) for c in nb["cells"]]
fails = []


def check(label, cond, detail=""):
    print(f"{label}: {'PASS' if cond else 'FAIL'}{(' -> ' + detail) if detail else ''}")
    if not cond:
        fails.append(label)


# ------------------------------------------- extract the REAL gen_kwargs block
model_cell = next(c for c in cells if "gen_kwargs = dict(kwargs)" in c)
start = model_cell.index("gen_kwargs = dict(kwargs)")
end = model_cell.index("no_repeat_ngram_size', 3)") + len("no_repeat_ngram_size', 3)")
real_src = model_cell[start:end]
real_src = "\n".join(l[8:] if l.startswith(" " * 8) else l for l in real_src.splitlines())


def run_block(**kwargs):
    ns = {
        "kwargs": dict(kwargs),
        "decoder_input_ids": torch.tensor([[1, 2]]),
        "self": type("S", (), {"model": type("M", (), {
            "config": type("C", (), {"decoder_start_token_id": 0})()})()})(),
    }
    exec(compile(real_src, "<gen_kwargs>", "exec"), ns)
    return ns["gen_kwargs"]


gk = run_block()
check("1. default with no kwargs is rp=1.0 / nrns=3",
      gk.get("repetition_penalty") == 1.0 and gk.get("no_repeat_ngram_size") == 3,
      f"rp={gk.get('repetition_penalty')} nrns={gk.get('no_repeat_ngram_size')}")

gk = run_block(repetition_penalty=1.3, no_repeat_ngram_size=3)
check("2. ablation CONTROL (explicit rp=1.3) still overrides the new default",
      gk.get("repetition_penalty") == 1.3,
      f"rp={gk.get('repetition_penalty')} -- control would be broken")

gk = run_block(repetition_penalty=1.0, no_repeat_ngram_size=0)
check("3. explicit rp=1.0 / nrns=0 passes through",
      gk.get("repetition_penalty") == 1.0 and gk.get("no_repeat_ngram_size") == 0,
      f"rp={gk.get('repetition_penalty')} nrns={gk.get('no_repeat_ngram_size')}")

check("4. no stale 1.3 default left in cell 7",
      "setdefault('repetition_penalty', 1.3)" not in model_cell)

# ------------- 5. the retained guard is load-bearing in the INSTALLED version
from transformers import (NoRepeatNGramLogitsProcessor,
                          RepetitionPenaltyLogitsProcessor)

ids = torch.tensor([[5, 6, 7, 5, 6]])          # trigram (5,6,7) already seen
logits = torch.zeros(1, 12)
# The penalized logit must belong to a token that was actually EMITTED, and it
# must be non-zero: the processor divides positive scores by the penalty, so a
# token sitting at exactly 0.0 is unchanged by any penalty value. Token 7 is in
# `ids` (so rp touches it) and is also the trigram continuation (so nrns blocks
# it) -- one fixture exercises both processors.
logits[0, 7] = 2.0
logits[0, 3] = 1.0                              # never emitted: rp must leave it alone

pen = RepetitionPenaltyLogitsProcessor(1.0)(ids, logits.clone())
check("5. rp=1.0 is an exact identity on the logits",
      torch.equal(pen, logits),
      f"max delta {(pen - logits).abs().max().item()}")

pen13 = RepetitionPenaltyLogitsProcessor(1.3)(ids, logits.clone())
check("   rp=1.3 does perturb logits (so 1.3 vs 1.0 is a real difference)",
      not torch.equal(pen13, logits),
      f"emitted token 7: {logits[0, 7].item()} -> {pen13[0, 7].item()}")
check("   rp=1.3 downweights an emitted token but not an unemitted one",
      pen13[0, 7] < logits[0, 7] and pen13[0, 3] == logits[0, 3],
      f"emitted 7: {pen13[0, 7].item()}, unemitted 3: {pen13[0, 3].item()}")

blocked = NoRepeatNGramLogitsProcessor(3)(ids, logits.clone())
check("   nrns=3 blocks the continuation that would repeat a trigram",
      torch.isinf(blocked[0, 7]) and blocked[0, 7] < 0,
      f"logit for token 7 = {blocked[0, 7].item()}")

# ------------------------------------------ 6. ablation cell still runs at all
abl = next(c for c in cells if "DECODE_CONFIGS" in c)
GOLD = ("ATT GEN ADMIN OFFICE Fax 614 466 5087 Dec 10 98 Attorney General Betty D "
        "Montgomery CONFIDENTIAL FACSIMILE TRANSMISSION COVER SHEET FAX NO TO George "
        "Baroody PHONE NUMBER DATE SPECIAL INSTRUCTIONS NOTE THIS MESSAGE IS FOR USE").split()


class StubImg:
    def convert(self, mode):
        return self


class StubProcessor:
    def __call__(self, img, return_tensors=None):
        return type("PV", (), {"pixel_values": torch.zeros(1, 3, 8, 8)})()

    def batch_decode(self, ids, skip_special_tokens=True):
        return [self._text]


proc = StubProcessor()


class StubModel:
    """Reproduces the measured shape of the result: rp=1.3 truncates, rp=1.0 does not."""

    def eval(self):
        return self

    def generate(self, pv, decoder_input_ids=None, max_length=512, **ov):
        n = 27 if ov.get("repetition_penalty", 1.0) > 1.0 else 46
        proc._text = '<s_doc>{"text": "' + " ".join(GOLD[:n]) + '"}'
        return torch.zeros(1, min(max_length, 8 + 3 * n), dtype=torch.long), {"compression_ratio": 0.0}


def compute_word_metrics(pred, gt_words):
    pw = re.findall(r"\w+", pred.lower())
    gold = re.findall(r"\w+", " ".join(gt_words).lower())
    gs = set(gold)
    rec = len(gs & set(pw)) / len(gs) if gs else 0.0
    d = abs(len(pw) - len(gold))
    return rec, max(0.0, 1.0 - d / max(len(pw), len(gold), 1))


import os
import tempfile

tmp = tempfile.mkdtemp()
_real_open = open


def fake_open(path, *a, **k):
    p = str(path)
    if p.startswith("/kaggle/working"):
        path = os.path.join(tmp, os.path.basename(p))
    return _real_open(path, *a, **k)


import numpy as np

g = {
    "__builtins__": __builtins__, "np": np, "json": json, "torch": torch,
    "model": StubModel(), "processor": proc,
    "test_raw": [{"image": StubImg(), "words": GOLD, "bboxes": None} for _ in range(6)],
    "reading_order_words": lambda w, b: list(w),
    "compute_word_metrics": compute_word_metrics,
    "compute_ned": lambda p, t: abs(len(p) - len(t)) / max(len(p), len(t), 1),
    "MAX_WORDS": 128, "TASK_PROMPT": "<s_doc>", "prompt_ids": torch.tensor([[1]]),
    "device": torch.device("cpu"), "tqdm": lambda it, **k: it, "open": fake_open,
}

buf, _stdout = io.StringIO(), sys.stdout
try:
    sys.stdout = buf
    exec(abl, g)
    ok6, err = True, ""
except Exception as e:
    ok6, err = False, f"{type(e).__name__}: {e}"
finally:
    sys.stdout = _stdout

check("6. ablation cell still execs end-to-end", ok6, err)
if ok6:
    rows = g.get("rows", [])
    check("   5 rows produced", len(rows) == 5, f"got {len(rows)}")
    ctrl = next((r for r in rows if r["config"] == "baseline (run5)"), None)
    win = next((r for r in rows if r["config"] == "no rep penalty"), None)
    # with the stub, the control (explicit 1.3) must still differ from the
    # rp=1.0 rows -- proof the control survives the default change
    check("   CONTROL row still distinguishable from rp=1.0 rows",
          ctrl and win and ctrl["mean_pred_words"] != win["mean_pred_words"],
          f"ctrl={ctrl and ctrl['mean_pred_words']} win={win and win['mean_pred_words']}")

print("\nRESULT:", "PASS - new defaults run, and the ablation control still controls"
      if not fails else f"FAIL: {fails}")
raise SystemExit(0 if not fails else 1)
