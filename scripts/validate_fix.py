"""
Validation: prove the label-shift fix makes the decoder learn NEXT-token
prediction (not copy). Overfits ONE FUNSD sample for a handful of steps using
the edited AdaptiveDonutOCR.forward(), then greedy-generates primed with <s_doc>.

Success criteria:
  - training CE loss drops steadily
  - NEXT-token accuracy climbs from ~0% toward high %
  - generation reproduces the target text instead of a single repeated char
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import torch
from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR


def main():
    torch.manual_seed(0)
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    tok = processor.tokenizer

    # Fresh model (no checkpoint) — mirrors the state at the start of a Kaggle rerun
    model = AdaptiveDonutOCR(freeze_encoder=True)

    ds = load_dataset("nielsr/funsd", split="test")
    sample = ds[0]
    img = sample["image"].convert("RGB")
    pixel_values = processor(img, return_tensors="pt").pixel_values

    # Short target to keep the CPU test fast
    words = sample.get("words", ["sample", "document"])
    target_json = json.dumps({"text": " ".join(words[:10])})
    full = f"<s_doc>{target_json}</s>"
    MAXLEN = 48
    enc = tok(full, add_special_tokens=False, max_length=MAXLEN,
              padding="max_length", truncation=True, return_tensors="pt")
    labels = enc.input_ids.clone()
    labels[labels == tok.pad_token_id] = -100
    decoder_input_ids = labels.clone()
    decoder_input_ids[decoder_input_ids == -100] = tok.pad_token_id

    print(f"Target: {full[:120]!r}")

    # Train router + decoder, exactly like the real setup
    params = list(model.router.parameters()) + list(model.model.decoder.parameters())
    opt = torch.optim.AdamW(params, lr=1e-4)

    def next_token_acc(logits):
        pred = logits[:, :-1].argmax(-1)
        gold = labels[:, 1:]
        m = gold != -100
        return (pred[m] == gold[m]).float().mean().item()

    model.train()
    print("\nstep | loss   | next-tok acc")
    for step in range(1, 26):
        opt.zero_grad()
        out = model(pixel_values=pixel_values, labels=labels, decoder_input_ids=decoder_input_ids)
        loss = out["loss"]
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        if step % 5 == 0 or step == 1:
            print(f"{step:4d} | {loss.item():6.3f} | {next_token_acc(out['logits'])*100:5.1f}%")

    # Greedy generation primed with <s_doc>, like infer.py / the fixed eval cell
    model.eval()
    p_ids = tok("<s_doc>", add_special_tokens=False, return_tensors="pt").input_ids
    with torch.no_grad():
        gen_ids, _ = model.generate(pixel_values, decoder_input_ids=p_ids, max_length=MAXLEN)
    pred = tok.batch_decode(gen_ids, skip_special_tokens=True)[0]
    print("\n=== after overfitting one sample ===")
    print(f"GENERATED: {pred[:160]!r}")
    print(f"TARGET   : {full[:160]!r}")


if __name__ == "__main__":
    main()
