"""Verify the Phase 2c decoding-ablation cell actually RUNS (not just parses).

Three things are checked, all without a GPU or model download:

  1. OVERRIDE PLUMBING (the critical one). generate() sets its decoding defaults
     with setdefault(), so if kwargs did NOT take precedence the ablation would
     silently re-run the SAME config five times and "prove" nothing. This test
     extracts the REAL gen_kwargs block out of notebook cell 7 and execs it, so it
     cannot drift from the notebook.
  2. EPOCHS=0 resume trick: range(1, EPOCHS+1) must be empty so the training loop
     body never executes.
  3. THE WHOLE ABLATION CELL, exec'd against stubs (fake model/processor/dataset)
     with a stub that mimics the hypothesis: truncated output under trigram
     blocking, longer output without it. Confirms the loop, the table, the control
     drift check, the interpretation branches and the JSON write all execute.
"""
import ast
import io
import json
import os
import re
import sys
import tempfile

import numpy as np
import torch

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
cells = ["".join(c["source"]) for c in nb["cells"]]
fails = []

# ---------------------------------------------------------------- 1. plumbing
model_cell = next(c for c in cells if "gen_kwargs = dict(kwargs)" in c)
start = model_cell.index("gen_kwargs = dict(kwargs)")
end = model_cell.index("no_repeat_ngram_size', 3)") + len("no_repeat_ngram_size', 3)")
block = "\n".join(line.strip() for line in model_cell[start:end].splitlines())
# strip the `if decoder_input_ids is not None:` branch indentation problems by
# exec'ing the real block inside a function with the same locals generate() has
real_src = model_cell[start:end]
real_src = "\n".join(l[8:] if l.startswith(" " * 8) else l for l in real_src.splitlines())

ns = {"kwargs": {"repetition_penalty": 1.0, "no_repeat_ngram_size": 0},
      "decoder_input_ids": torch.tensor([[1, 2]]),
      "self": type("S", (), {"model": type("M", (), {"config": type("C", (), {"decoder_start_token_id": 0})()})()})()}
exec(real_src, ns)
gk = ns["gen_kwargs"]
ok1 = gk.get("repetition_penalty") == 1.0 and gk.get("no_repeat_ngram_size") == 0
print(f"1. override plumbing: rp={gk.get('repetition_penalty')} nrns={gk.get('no_repeat_ngram_size')} "
      f"-> {'PASS (kwargs beat setdefault)' if ok1 else 'FAIL (setdefault clobbered overrides!)'}")
if not ok1:
    fails.append("override plumbing")

# min_new_tokens must be a real generation param in the installed transformers
from transformers import GenerationConfig
ok1b = hasattr(GenerationConfig(), "min_new_tokens")
print(f"   min_new_tokens supported by transformers: {'PASS' if ok1b else 'FAIL'}")
if not ok1b:
    fails.append("min_new_tokens unsupported")

# ------------------------------------------------------------- 2. EPOCHS=0
# Select by the LOAD call, not by the mere mention of RESUME_CKPT: the phase2c
# hotfix moved the RESUME_CKPT *definition* into cell 2, so "first cell mentioning
# RESUME_CKPT" silently started matching the config cell and this check failed
# against the wrong cell. Assert uniqueness so that cannot recur.
_train_cells = [c for c in cells if "torch.load(RESUME_CKPT" in c]
assert len(_train_cells) == 1, f"expected 1 training cell, found {len(_train_cells)}"
train_cell = _train_cells[0]
ok2 = list(range(1, 0 + 1)) == [] and "EPOCHS = 0" in train_cell and "if EPOCHS > 0:" in train_cell
print(f"2. EPOCHS=0 skips loop: range(1,1)={list(range(1, 1))}, save guarded -> {'PASS' if ok2 else 'FAIL'}")
if not ok2:
    fails.append("EPOCHS=0 resume")

# ------------------------------------------------- 3. exec the ablation cell
abl = next(c for c in cells if "DECODE_CONFIGS" in c)


class StubImg:
    def convert(self, mode):
        return self


class StubPV:
    pixel_values = torch.zeros(1, 3, 8, 8)


class StubProcessor:
    def __call__(self, img, return_tensors=None):
        return StubPV()

    def batch_decode(self, ids, skip_special_tokens=True):
        return [self._text]


GOLD = ("ATT GEN ADMIN OFFICE Fax 614 466 5087 Dec 10 98 Attorney General Betty D "
        "Montgomery CONFIDENTIAL FACSIMILE TRANSMISSION COVER SHEET FAX NO TO George Baroody "
        "PHONE NUMBER DATE SPECIAL INSTRUCTIONS NOTE THIS MESSAGE IS INTENDED ONLY FOR USE").split()

proc = StubProcessor()


class StubModel:
    """Mimics the hypothesis: trigram blocking truncates, removing it does not."""

    def eval(self):
        return self

    def generate(self, pv, decoder_input_ids=None, max_length=512, **ov):
        n_words = 12 if ov.get("no_repeat_ngram_size", 0) > 0 else 46
        text = '<s_doc>{"text": "' + " ".join(GOLD[:n_words]) + '"}'
        proc._text = text
        ntok = min(max_length, 8 + 3 * n_words)
        return torch.zeros(1, ntok, dtype=torch.long), {"compression_ratio": 0.0}


def reading_order_words(words, bboxes):
    return list(words)


def compute_word_metrics(pred, gt_words):
    pw = re.findall(r"\w+", pred.lower())
    gold = re.findall(r"\w+", " ".join(gt_words).lower())
    gs = set(gold)
    rec = len(gs & set(pw)) / len(gs) if gs else 0.0
    d = abs(len(pw) - len(gold))
    return rec, max(0.0, 1.0 - d / max(len(pw), len(gold), 1))


def compute_ned(pred, target):
    m = max(len(pred), len(target))
    return abs(len(pred) - len(target)) / m if m else 0.0


tmp = tempfile.mkdtemp()
_real_open = open


def fake_open(path, *a, **k):
    p = str(path)
    if p.startswith("/kaggle/working"):
        path = os.path.join(tmp, os.path.basename(p))
    return _real_open(path, *a, **k)


g = {
    "__builtins__": __builtins__, "np": np, "json": json, "torch": torch,
    "model": StubModel(), "processor": proc,
    "test_raw": [{"image": StubImg(), "words": GOLD, "bboxes": None} for _ in range(6)],
    "reading_order_words": reading_order_words,
    "compute_word_metrics": compute_word_metrics, "compute_ned": compute_ned,
    "MAX_WORDS": 128, "TASK_PROMPT": "<s_doc>", "prompt_ids": torch.tensor([[1]]),
    "device": torch.device("cpu"), "tqdm": lambda it, **k: it, "open": fake_open,
}

buf = io.StringIO()
_stdout = sys.stdout
try:
    sys.stdout = buf
    exec(abl, g)
    ok3, err = True, None
except Exception as e:
    ok3, err = False, f"{type(e).__name__}: {e}"
finally:
    sys.stdout = _stdout

out = buf.getvalue()
print(f"3. ablation cell exec: {'PASS' if ok3 else 'FAIL -> ' + str(err)}")
if not ok3:
    fails.append("ablation cell exec")
else:
    wrote = os.path.exists(os.path.join(tmp, "ablation_decoding.json"))
    rows = g.get("rows", [])
    grid_ok = len(rows) == 5
    # the stub makes 'no ngram block' the winner; the cell should say so AND
    # attribute it to length
    verdict_ok = "under-generation was the cap" in out
    lens = {r["config"]: r["mean_pred_words"] for r in rows}
    print(f"   rows={len(rows)} (expect 5): {'PASS' if grid_ok else 'FAIL'}")
    print(f"   json written: {'PASS' if wrote else 'FAIL'}")
    print(f"   length instrumentation: baseline {lens.get('baseline (run5)')} words vs "
          f"no-ngram {lens.get('no ngram block')} words")
    print(f"   interpretation branch fired: {'PASS' if verdict_ok else 'FAIL'}")
    for label, cond in (("grid", grid_ok), ("json write", wrote), ("verdict", verdict_ok)):
        if not cond:
            fails.append(label)
    print("\n   --- captured table ---")
    for line in out.splitlines():
        if line.strip():
            print("   " + line)

print("\nRESULT:", "PASS - ablation cell runs end-to-end" if not fails else f"FAIL: {fails}")
raise SystemExit(0 if not fails else 1)
