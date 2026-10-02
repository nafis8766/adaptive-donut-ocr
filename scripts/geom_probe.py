"""Geometry probe: is the spelling garble on the wide screenshot caused by
Donut's preprocessing (90-deg align-long-axis rotation + thumbnail-only shrink
that leaves small text tiny in a huge portrait canvas), or by the model itself?

Single model/checkpoint, single image. We vary ONLY preprocessing:
  A) as-is           (upscale x1, align_long_axis=True)  -> reproduces infer.py
  B) upscale x4      (align_long_axis=True)              -> bigger text, still rotated
  C) upscale x4      (align_long_axis=False)             -> bigger text, upright

A->B isolates resolution; B->C isolates the rotation.
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import torch
from PIL import Image
from transformers import DonutProcessor
from src.model import AdaptiveDonutOCR

IMG = r"C:\Users\Nafis\Desktop\Project\Screenshot 2026-08-26 233927.png"
# NOT "run 7/". This is pruned_ocr_results_2/, a distinct Kaggle output dir that
# still exists under its original name; the Pending 12 bulk rewrite of
# results_2 -> "run 7" corrupted this literal via substring collision (2026-09-06).
CKPT = r"pruned_ocr_results_2/checkpoints/adaptive_donut_funsd.pt"
PROMPT = "<s_doc>"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
proc = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)
model.load_state_dict(torch.load(CKPT, map_location=device))
model.eval()
prompt_ids = proc.tokenizer(PROMPT, add_special_tokens=False, return_tensors="pt").input_ids.to(device)

raw = Image.open(IMG).convert("RGB")
print(f"source image: {raw.size} (WxH)")


def run(label, upscale, align):
    img = raw
    if upscale != 1:
        img = raw.resize((raw.size[0] * upscale, raw.size[1] * upscale), Image.LANCZOS)
    proc.image_processor.do_align_long_axis = align
    pv = proc(img, return_tensors="pt").pixel_values.to(device)
    t0 = time.perf_counter()
    with torch.no_grad():
        gen, _ = model.generate(pv, decoder_input_ids=prompt_ids, keep_ratio=1.0,
                                merge_ratio=0.0, max_length=512,
                                # rp=1.0: at 1.3 this probe truncated output to ~71%
                                # of gold length, so any geometry conclusion drawn
                                # from it was reading a decoding artifact. See
                                # AGENTS.md run 6.
                                repetition_penalty=1.0, no_repeat_ngram_size=3)
    dt = (time.perf_counter() - t0) * 1000
    txt = proc.batch_decode(gen, skip_special_tokens=True)[0]
    if txt.startswith(PROMPT):
        txt = txt[len(PROMPT):]
    print(f"\n===== {label} | upscale x{upscale} | align_long_axis={align} | fed_img={img.size} | {dt:.0f} ms =====")
    print(txt.strip())


run("A (as-is / infer.py)", 1, True)
run("B (x4, rotated)", 4, True)
run("C (x4, upright)", 4, False)
print("\nGT: ENG 091 Foundation Course | ENG 101 English Fundamentals | "
      "ENG 102 English Composition I | ENG 103* Advanced Writing Skills and Presentation")
