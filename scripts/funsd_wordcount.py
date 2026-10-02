"""Diagnose whether the training target is being silently truncated, which would
cap recall regardless of model quality:
  - words per FUNSD sample (is the 128-word cap biting?)
  - tokenized length of the <s_doc>{"text": ...128 words...}</s> target
    (is max_length=512 truncating even the capped target -> tail words never
     appear in labels -> model never learns them)
"""
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import numpy as np
from transformers import DonutProcessor
from datasets import load_dataset
from src.dataset import reading_order_words, MAX_TARGET_WORDS

proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
tok = proc.tokenizer

for split in ["train", "test"]:
    ds = load_dataset("nielsr/funsd", split=split)
    wc = np.array([len(s["words"]) for s in ds])
    # tokenized length of the capped target actually used in training
    tlens = []
    for s in ds:
        words = reading_order_words(s["words"], s.get("bboxes"))[:MAX_TARGET_WORDS]
        full = f'<s_doc>{json.dumps({"text": " ".join(words)}, ensure_ascii=False)}</s>'
        tlens.append(len(tok(full, add_special_tokens=False).input_ids))
    tlens = np.array(tlens)
    print(f"\n=== {split} (n={len(ds)}) ===")
    print(f"words/sample: min={wc.min()} median={int(np.median(wc))} mean={wc.mean():.0f} max={wc.max()}")
    print(f"  samples > {MAX_TARGET_WORDS} words (cap bites): {(wc > MAX_TARGET_WORDS).sum()} ({(wc > MAX_TARGET_WORDS).mean()*100:.0f}%)")
    print(f"target tokens (cap={MAX_TARGET_WORDS}): median={int(np.median(tlens))} mean={tlens.mean():.0f} max={tlens.max()}")
    print(f"  samples hitting max_length=512 (target truncated): {(tlens >= 512).sum()} ({(tlens >= 512).mean()*100:.0f}%)")
