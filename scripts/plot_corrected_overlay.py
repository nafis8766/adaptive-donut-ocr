import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR
from src.evaluate import compute_normalized_edit_distance

def generate_corrected_visualization():
    print("Loading test sample and model checkpoint...")
    ds = load_dataset("nielsr/funsd", split="test")
    sample = ds[0]
    img = sample["image"].convert("RGB")

    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    pixel_values = processor(img, return_tensors="pt").pixel_values

    model = AdaptiveDonutOCR(freeze_encoder=True)
    # pruned_ocr_results/ (unsuffixed) is gone since the Kaggle move; fixed 2026-09-06.
    ckpt = torch.load("run 5/checkpoints/adaptive_donut_funsd.pt", map_location="cpu")
    model.load_state_dict(ckpt)
    model.eval()

    print("Running token-pruned generation (72% token economy)...")
    with torch.no_grad():
        gen_ids, meta = model.generate(pixel_values, max_length=256)

    pred_text = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
    words = sample.get("words", [])
    gt_text = " ".join(words[:40])

    print("\n" + "="*60)
    print("GROUND TRUTH TEXT:")
    print(gt_text)
    print("-"*60)
    print("MODEL GENERATED OCR PREDICTION:")
    print(pred_text)
    print("-"*60)
    print("="*60 + "\n")

    img_np = np.array(img)
    H_img, W_img, _ = img_np.shape

    # Correct portrait grid dimensions from Swin output
    # pixel_values is (1, 3, 2560, 1920) -> downsampled by 32 -> H=80, W=60
    H_grid = 80
    W_grid = 60
    N = meta["original_tokens"]

    mask = np.zeros((H_grid, W_grid), dtype=np.float32)
    selected = set(meta["topk_indices"][0].cpu().numpy().tolist())

    for idx in range(min(H_grid * W_grid, N)):
        h = idx // W_grid
        w = idx % W_grid
        if idx in selected:
            mask[h, w] = 1.0

    mask_res = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)) / 255.0

    # Side-by-side plot with clear highlights
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    axes[0].imshow(img_np)
    axes[0].set_title("Original Scanned Document (FUNSD)", fontsize=14, fontweight="bold")
    axes[0].axis("off")

    # Highlight kept regions (100% bright), dim pruned regions (25% brightness)
    overlay = img_np.copy().astype(np.float32)
    overlay[mask_res < 0.5] *= 0.25

    comp_tokens = meta["compressed_tokens"]
    savings = meta["compression_ratio"]

    axes[1].imshow(overlay.astype(np.uint8))
    axes[1].set_title(f"Retained Tokens: {comp_tokens}/{N} ({savings:.1f}% Token Economy)", fontsize=14, fontweight="bold")
    axes[1].axis("off")

    os.makedirs("visualizations", exist_ok=True)
    plt.tight_layout()
    save_path = "visualizations/corrected_overlay.png"
    plt.savefig(save_path, dpi=200)
    plt.close()
    print(f"Saved corrected visualization to {save_path}")

if __name__ == "__main__":
    generate_corrected_visualization()
