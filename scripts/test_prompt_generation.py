import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR

def test_generation():
    ds = load_dataset("nielsr/funsd", split="test")
    img = ds[0]["image"].convert("RGB")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    pixel_values = processor(img, return_tensors="pt").pixel_values

    model = AdaptiveDonutOCR(freeze_encoder=True)
    # pruned_ocr_results/ (unsuffixed) is gone since the Kaggle move; fixed 2026-09-06.
    ckpt = torch.load("run 5/checkpoints/adaptive_donut_funsd.pt", map_location="cpu")
    model.load_state_dict(ckpt)
    model.eval()

    prompt_str = '<s_doc>{"text":'
    p_ids = processor.tokenizer(prompt_str, add_special_tokens=False, return_tensors="pt").input_ids
    print("Prompt tokens:", p_ids)

    with torch.no_grad():
        gen_ids, meta = model.generate(pixel_values, decoder_input_ids=p_ids, max_length=256)

    pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
    print("\n" + "="*50)
    print("GENERATED RESULT:")
    print(pred)
    print("="*50)

if __name__ == "__main__":
    test_generation()
