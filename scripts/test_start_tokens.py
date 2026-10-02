import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR

def test_start_tokens():
    ds = load_dataset("nielsr/funsd", split="test")
    img = ds[0]["image"].convert("RGB")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    pixel_values = processor(img, return_tensors="pt").pixel_values

    model = AdaptiveDonutOCR(freeze_encoder=True)
    # pruned_ocr_results/ (unsuffixed) is gone since the Kaggle move; fixed 2026-09-06.
    ckpt = torch.load("run 5/checkpoints/adaptive_donut_funsd.pt", map_location="cpu")
    model.load_state_dict(ckpt)
    model.eval()

    # In Donut / mBART, shift_tokens_right uses pad_token_id or eos_token_id
    for start_id in [0, 1, 2, processor.tokenizer.pad_token_id, processor.tokenizer.eos_token_id]:
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pixel_values,
                decoder_start_token_id=start_id,
                max_length=128
            )
        decoded = processor.batch_decode(gen_ids, skip_special_tokens=False)[0]
        decoded_clean = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        print(f"start_id={start_id} -> Full: {decoded[:80]} | Clean: {decoded_clean[:80]}")

if __name__ == "__main__":
    test_start_tokens()
