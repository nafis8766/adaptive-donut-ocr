import os
import sys
import argparse
import json
import time
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from transformers import DonutProcessor

from src.model import AdaptiveDonutOCR


def run_inference(image_path: str, checkpoint_path: str, keep_ratio: float = 1.0, merge_ratio: float = 0.0, output_dir: str = "./visualizations", task_prompt: str = "<s_doc>", repetition_penalty: float = 1.0, no_repeat_ngram_size: int = 3, align_long_axis: bool = False, min_long_edge: int = 1500):
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at '{image_path}'")
        return

    os.makedirs(output_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device} ({'GPU' if torch.cuda.is_available() else 'CPU'})")

    # 1. Load Processor
    print("Loading Donut processor...")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    # Donut defaults to rotating any landscape image 90 deg to fill its portrait
    # canvas (do_align_long_axis=True). For an arbitrary user document that turns
    # horizontal text sideways and wrecks recognition, so keep the page upright by
    # default. See scripts/geom_probe.py for the A/B/C evidence behind this.
    processor.image_processor.do_align_long_axis = align_long_axis

    # 2. Load Image
    print(f"Loading document image: {image_path}")
    raw_img = Image.open(image_path).convert("RGB")

    # Donut's thumbnail step only ever shrinks, so a small image stays small inside
    # the big canvas and its text is under-resolved. Upscale small inputs (Lanczos)
    # so glyphs are legible before processing.
    long_edge = max(raw_img.size)
    if min_long_edge and long_edge < min_long_edge:
        scale = min_long_edge / long_edge
        new_size = (round(raw_img.size[0] * scale), round(raw_img.size[1] * scale))
        print(f"Upscaling small image {raw_img.size} -> {new_size} (long edge < {min_long_edge}px) for legibility")
        raw_img = raw_img.resize(new_size, Image.LANCZOS)

    print(f"Preprocessing (align_long_axis={align_long_axis})...")
    pixel_values = processor(raw_img, return_tensors="pt").pixel_values.to(device)

    # 3. Instantiate & Load Trained Model Checkpoint
    print(f"Loading model checkpoint from: {checkpoint_path}")
    model = AdaptiveDonutOCR(
        keep_ratio=keep_ratio,
        merge_ratio=merge_ratio,
        freeze_encoder=True
    ).to(device)

    if os.path.exists(checkpoint_path):
        ckpt = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(ckpt)
        print("-> Checkpoint loaded successfully!")
    else:
        print(f"Warning: Checkpoint '{checkpoint_path}' not found! Using initialized weights.")

    model.eval()

    # 4. Run Token-Pruned Generation
    #    The decoder was trained on sequences shaped like  <s_doc>{...json...}</s>
    #    (see src/dataset.py), so generation MUST be primed with the same task
    #    prompt. Without it the decoder starts from the default start token and
    #    emits EOS immediately -> empty output.
    print("\nRunning Adaptive Token Pruning OCR...")
    print(f"Priming decoder with task prompt: '{task_prompt}'")
    decoder_input_ids = processor.tokenizer(
        task_prompt, add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)

    t0 = time.perf_counter()
    with torch.no_grad():
        gen_ids, meta = model.generate(
            pixel_values,
            decoder_input_ids=decoder_input_ids,
            keep_ratio=keep_ratio,
            merge_ratio=merge_ratio,
            max_length=512,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=no_repeat_ngram_size
        )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # 5. Decode Output Text (strip the task-prompt prefix the model echoes back)
    pred_text = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
    if pred_text.startswith(task_prompt):
        pred_text = pred_text[len(task_prompt):]
    pred_text = pred_text.strip()

    # Print Formatted OCR Results
    orig_tokens = meta["original_tokens"]
    comp_tokens = meta["compressed_tokens"]
    savings_pct = meta["compression_ratio"]

    print("\n" + "="*60)
    print("               DOCUMENT OCR TRANSCRIPTION RESULTS")
    print("="*60)
    print(f"Original Visual Tokens:       {orig_tokens}")
    print(f"Tokens Fed to Decoder (LLM):  {comp_tokens}")
    print(f"Visual Token Savings:         {savings_pct:.1f}% Reduction")
    print(f"Inference Latency:            {elapsed_ms:.1f} ms")
    print("-"*60)
    print("EXTRACTED TEXT / JSON:")
    print(pred_text)
    print("="*60 + "\n")

    # 5b. Save Extracted Text to Disk (alongside the overlay image)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    text_path = os.path.join(output_dir, f"{base_name}_extracted.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(pred_text)

    json_path = os.path.join(output_dir, f"{base_name}_result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "image": image_path,
            "text": pred_text,
            "original_tokens": orig_tokens,
            "compressed_tokens": comp_tokens,
            "compression_ratio": savings_pct,
            "latency_ms": elapsed_ms,
        }, f, indent=2, ensure_ascii=False)

    print(f"Extracted text saved to:      {os.path.abspath(text_path)}")
    print(f"Result JSON saved to:         {os.path.abspath(json_path)}")

    # 6. Generate & Save Visual Heatmap Overlay
    print("Generating visual token pruning heatmap...")
    img_np = np.array(raw_img)
    H_img, W_img, _ = img_np.shape

    # Downsampled portrait grid dimensions
    H_grid = 80
    W_grid = 60
    N = orig_tokens

    mask = np.zeros((H_grid, W_grid), dtype=np.float32)
    selected_indices = set(meta["topk_indices"][0].cpu().numpy().tolist())

    for idx in range(min(H_grid * W_grid, N)):
        h = idx // W_grid
        w = idx % W_grid
        if idx in selected_indices:
            mask[h, w] = 1.0

    mask_res = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)) / 255.0

    fig, axes = plt.subplots(1, 2, figsize=(14, 8))

    axes[0].imshow(img_np)
    axes[0].set_title("Input Document Image", fontsize=14, fontweight="bold")
    axes[0].axis("off")

    overlay = img_np.copy().astype(np.float32)
    overlay[mask_res < 0.5] *= 0.25  # Dim pruned whitespace

    axes[1].imshow(overlay.astype(np.uint8))
    axes[1].set_title(f"Retained Tokens: {comp_tokens}/{orig_tokens} ({savings_pct:.0f}% Token Economy)", fontsize=14, fontweight="bold")
    axes[1].axis("off")

    save_path = os.path.join(output_dir, f"{base_name}_pruning_overlay.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()

    print(f"Overlay visualization saved to: {os.path.abspath(save_path)}")
    print("All done!")

    return pred_text


def main():
    parser = argparse.ArgumentParser(description="Run Adaptive Visual Token Pruning OCR on any custom image")
    parser.add_argument("--image", type=str, default=None, help="Path to your document/invoice/receipt image")
    # NOT "run 7/": pruned_ocr_results_2/ is a distinct dir that still exists under its
    # original name. The Pending 12 results_2 -> "run 7" rewrite corrupted this literal
    # by substring collision (2026-09-06).
    parser.add_argument("--checkpoint", type=str, default="pruned_ocr_results_2/checkpoints/adaptive_donut_funsd.pt", help="Path to trained model checkpoint")
    parser.add_argument("--keep_ratio", type=float, default=1.0, help="Ratio of visual tokens to keep. Phase-1 model was trained with pruning OFF, so keep 1.0 for a fair test.")
    parser.add_argument("--merge_ratio", type=float, default=0.0, help="Ratio of tokens to merge via ToMe. 0.0 = off (matches Phase-1 training).")
    parser.add_argument("--output_dir", type=str, default="./visualizations", help="Directory to save overlay heatmaps")
    parser.add_argument("--task_prompt", type=str, default="<s_doc>", help="Decoder task prompt the model was trained with (see src/dataset.py)")
    parser.add_argument("--repetition_penalty", type=float, default=1.0, help="Penalty >1.0 discourages repetition loops (1.0 = off). Keep 1.0: on full-page documents 1.3 truncated output to 71%% of gold length and cost 27 pts of word recall (see AGENTS.md run 6).")
    parser.add_argument("--no_repeat_ngram_size", type=int, default=3, help="Block repeating n-grams of this size (0 = off). Guards against '8 8 8 8' collapse -- load-bearing now that repetition_penalty is 1.0.")
    parser.add_argument("--align_long_axis", action="store_true", help="Rotate landscape images 90 deg to portrait (Donut's default). Off by default; enabling it turns horizontal text sideways and usually hurts recognition.")
    parser.add_argument("--min_long_edge", type=int, default=1500, help="Upscale images whose longer edge is below this many pixels so small text stays legible (0 = never upscale).")
    args = parser.parse_args()

    # If no image path provided, save and test with a sample from the test dataset
    if args.image is None:
        print("No --image specified. Extracting a test document sample to './sample_document.png'...")
        from datasets import load_dataset
        ds = load_dataset("nielsr/funsd", split="test")
        sample_img = ds[0]["image"].convert("RGB")
        sample_path = "./sample_document.png"
        sample_img.save(sample_path)
        args.image = sample_path
        print(f"Created sample document at '{sample_path}'\n")

    run_inference(
        image_path=args.image,
        checkpoint_path=args.checkpoint,
        keep_ratio=args.keep_ratio,
        merge_ratio=args.merge_ratio,
        output_dir=args.output_dir,
        task_prompt=args.task_prompt,
        repetition_penalty=args.repetition_penalty,
        no_repeat_ngram_size=args.no_repeat_ngram_size,
        align_long_axis=args.align_long_axis,
        min_long_edge=args.min_long_edge
    )


if __name__ == "__main__":
    main()
