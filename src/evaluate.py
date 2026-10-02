import os
import re
import argparse
import time
import json
import torch
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple
from PIL import Image
from transformers import DonutProcessor
from datasets import load_dataset
from tqdm import tqdm

from src.model import AdaptiveDonutOCR
from src.dataset import reading_order_words, MAX_TARGET_WORDS


def compute_normalized_edit_distance(prediction: str, target: str) -> float:
    """
    Computes Normalized Levenshtein Distance (NED) between 0.0 (identical) and 1.0 (completely different).
    """
    try:
        import editdistance
        dist = editdistance.eval(prediction, target)
    except ImportError:
        # Fallback simple edit distance
        m, n = len(prediction), len(target)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if prediction[i - 1] == target[j - 1] else 1
                dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
        dist = dp[m][n]
        
    max_len = max(len(prediction), len(target))
    return dist / max_len if max_len > 0 else 0.0


def compute_word_metrics(prediction: str, gt_words: List[str]) -> Tuple[float, float]:
    """Return (word_recall, word_order_score), both in [0, 1].

    - recall: fraction of unique ground-truth words present anywhere in the
      prediction (order-independent -> "are we missing words?").
    - order:  1 - normalized word-level edit distance between the predicted and
      ground-truth word sequences ("is the sequence right?").
    """
    pred_words = re.findall(r"\w+", prediction.lower())
    gold = re.findall(r"\w+", " ".join(gt_words).lower())  # tokenize gold the same way
    gold_set = set(gold)
    recall = len(gold_set & set(pred_words)) / len(gold_set) if gold_set else 0.0
    try:
        import editdistance
        d = editdistance.eval(pred_words, gold)
    except ImportError:
        d = abs(len(pred_words) - len(gold))
    denom = max(len(pred_words), len(gold), 1)
    order = max(0.0, 1.0 - d / denom)
    return recall, order


def visualize_pruned_patches(
    image: Image.Image,
    topk_indices: torch.Tensor,
    original_token_count: int,
    save_path: str = "visualizations/pruned_overlay.png"
):
    """
    Renders an overlay highlighting kept visual patches on the original document image.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    img_np = np.array(image.convert("RGB"))
    H_img, W_img, _ = img_np.shape
    
    # Estimate grid dimensions (4:3 aspect ratio)
    aspect_ratio = 4.0 / 3.0
    W_grid = int(round((original_token_count * aspect_ratio) ** 0.5))
    H_grid = max(1, original_token_count // W_grid)
    
    mask = np.zeros((H_grid, W_grid), dtype=np.float32)
    selected_set = set(topk_indices[0].cpu().numpy().tolist())
    
    for idx in range(min(H_grid * W_grid, original_token_count)):
        h = idx // W_grid
        w = idx % W_grid
        if idx in selected_set:
            mask[h, w] = 1.0  # Kept patch
            
    # Resize mask to image dimensions
    mask_resized = np.array(Image.fromarray((mask * 255).astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)) / 255.0
    
    # Create side-by-side plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    axes[0].imshow(img_np)
    axes[0].set_title("Original Document Image")
    axes[0].axis("off")
    
    # Overlay kept regions in green and darken pruned regions
    overlay = img_np.copy().astype(np.float32)
    overlay[mask_resized < 0.5] *= 0.35  # Dim pruned whitespace
    
    axes[1].imshow(overlay.astype(np.uint8))
    axes[1].set_title(f"Adaptive Retained Tokens ({len(selected_set)} / {original_token_count})")
    axes[1].axis("off")
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()
    print(f"Saved saliency overlay visualization to: {save_path}")


def evaluate(
    model: AdaptiveDonutOCR,
    dataset_name: str = "nielsr/funsd",
    processor: DonutProcessor = None,
    num_samples: int = 50,
    keep_ratio: float = 0.35,
    merge_ratio: float = 0.20,
    device: torch.device = torch.device("cpu"),
    save_viz: bool = True,
    task_prompt: str = "<s_doc>"
):
    model.eval()
    print(f"\nEvaluating on {num_samples} test samples (Keep Ratio={keep_ratio}, Merge Ratio={merge_ratio})...")
    
    test_ds = load_dataset(dataset_name, split="test")
    if num_samples < len(test_ds):
        test_ds = test_ds.select(range(num_samples))
        
    edit_distances = []
    recalls = []
    word_orders = []
    latencies = []
    original_tokens_list = []
    compressed_tokens_list = []

    # Prime generation with the same task prompt used in training (<s_doc>),
    # or the decoder starts from the wrong token and emits junk.
    prompt_ids = processor.tokenizer(
        task_prompt, add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)

    for i, sample in enumerate(tqdm(test_ds, desc="Evaluating")):
        img = sample["image"].convert("RGB")
        pixel_values = processor(img, return_tensors="pt").pixel_values.to(device)

        # Ground truth: reading-order transcription (matches the training target).
        if "words" in sample:
            boxes = sample.get("bboxes") or sample.get("boxes") or sample.get("bbox")
            gt_words = reading_order_words(sample["words"], boxes) if boxes else list(sample["words"])
            gt_words = gt_words[:MAX_TARGET_WORDS]
            gt_text = json.dumps({"text": " ".join(gt_words)})
        elif "total" in sample or "company" in sample:
            gt_text = json.dumps({
                "company": str(sample.get("company", "")).strip(),
                "date": str(sample.get("date", "")).strip(),
                "address": str(sample.get("address", "")).strip(),
                "total": str(sample.get("total", "")).strip()
            })
            gt_words = re.findall(r"\w+", gt_text.lower())
        else:
            gt_text = json.dumps(sample.get("ground_truth", {}))
            gt_words = re.findall(r"\w+", gt_text.lower())

        # Timed generation (primed with the task prompt)
        start_t = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(
                pixel_values=pixel_values,
                decoder_input_ids=prompt_ids,
                keep_ratio=keep_ratio,
                merge_ratio=merge_ratio,
                max_length=512
            )
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        latencies.append(latency_ms)

        pred_text = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred_text.startswith(task_prompt):
            pred_text = pred_text[len(task_prompt):]
        pred_text = pred_text.strip()

        edit_distances.append(compute_normalized_edit_distance(pred_text, gt_text))
        recall, order = compute_word_metrics(pred_text, gt_words)
        recalls.append(recall)
        word_orders.append(order)

        original_tokens_list.append(meta["original_tokens"])
        compressed_tokens_list.append(meta["compressed_tokens"])
        
        # Save visualization for first sample
        if i == 0 and save_viz:
            visualize_pruned_patches(
                image=img,
                topk_indices=meta["topk_indices"],
                original_token_count=meta["original_tokens"]
            )
            
    avg_ned = np.mean(edit_distances)
    avg_accuracy = (1.0 - avg_ned) * 100.0
    avg_recall = np.mean(recalls) * 100.0
    avg_order = np.mean(word_orders) * 100.0
    avg_latency = np.mean(latencies)
    avg_orig = np.mean(original_tokens_list)
    avg_comp = np.mean(compressed_tokens_list)
    token_savings = (1.0 - (avg_comp / avg_orig)) * 100.0

    print("\n" + "=" * 50)
    print("           BENCHMARK EVALUATION RESULTS           ")
    print("=" * 50)
    print(f"  [Stage 1] Word Recall (no missing words): {avg_recall:.2f}%")
    print(f"  [Stage 2] Character Accuracy:             {avg_accuracy:.2f}%")
    print(f"  [Stage 3] Word-Order / Sequence Score:    {avg_order:.2f}%")
    print(f"  Normalized Edit Distance (NED):           {avg_ned:.4f}")
    print(f"  Average Original Visual Tokens:           {avg_orig:.0f}")
    print(f"  Average Compressed Tokens Fed to LLM:     {avg_comp:.0f}")
    print(f"  Visual Token Savings / Economy:           {token_savings:.1f}%")
    print(f"  Average Generation Latency:               {avg_latency:.1f} ms/doc")
    print("=" * 50)

    return {
        "word_recall_pct": float(avg_recall),
        "character_accuracy_pct": float(avg_accuracy),
        "word_order_pct": float(avg_order),
        "mean_ned": float(avg_ned),
        "avg_token_savings_pct": float(token_savings),
        "avg_latency_ms": float(avg_latency),
        "num_eval_samples": int(len(edit_distances)),
    }


def main():
    parser = argparse.ArgumentParser()
    # pruned_ocr_results/ (unsuffixed) is gone since the Kaggle move; fixed 2026-09-06.
    parser.add_argument("--checkpoint", type=str, default="run 5/checkpoints/adaptive_donut_funsd.pt")
    parser.add_argument("--base_model", type=str, default="naver-clova-ix/donut-base")
    parser.add_argument("--dataset_name", type=str, default="nielsr/funsd")
    parser.add_argument("--num_samples", type=int, default=30)
    parser.add_argument("--keep_ratio", type=float, default=0.35)
    parser.add_argument("--merge_ratio", type=float, default=0.20)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = DonutProcessor.from_pretrained(args.base_model)
    model = AdaptiveDonutOCR(base_model_name=args.base_model).to(device)

    if args.checkpoint and os.path.exists(args.checkpoint):
        print(f"Loading weights from {args.checkpoint}...")
        ckpt = torch.load(args.checkpoint, map_location=device)
        # Kaggle saves a raw state_dict; older checkpoints wrap it in a dict.
        state_dict = ckpt.get("model_state_dict", ckpt) if isinstance(ckpt, dict) and "model_state_dict" in ckpt else ckpt
        model.load_state_dict(state_dict)
        print("-> Checkpoint loaded.")
    else:
        print(f"Warning: checkpoint '{args.checkpoint}' not found; evaluating randomly-initialized weights.")

    evaluate(
        model=model,
        dataset_name=args.dataset_name,
        processor=processor,
        num_samples=args.num_samples,
        keep_ratio=args.keep_ratio,
        merge_ratio=args.merge_ratio,
        device=device
    )


if __name__ == "__main__":
    main()
