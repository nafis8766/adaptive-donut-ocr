import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import time
import json
import numpy as np
from tqdm import tqdm
from datasets import load_dataset
from transformers import DonutProcessor
from src.model import AdaptiveDonutOCR
from src.evaluate import compute_normalized_edit_distance

def run_test_eval(max_docs=20):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading model on {device}...")

    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    test_ds = load_dataset("nielsr/funsd", split="test")
    if max_docs and max_docs < len(test_ds):
        test_ds = test_ds.select(range(max_docs))

    model = AdaptiveDonutOCR(freeze_encoder=True).to(device)
    # pruned_ocr_results/ (unsuffixed) has not existed since the Kaggle outputs were
    # moved in under per-run names; fixed 2026-09-06 (see AGENTS.md 2026-08-31 entry,
    # which repaired only diagnose_decoder.py).
    ckpt = torch.load("run 5/checkpoints/adaptive_donut_funsd.pt", map_location=device)
    model.load_state_dict(ckpt)
    model.eval()

    neds, latencies, savings, orig_toks, comp_toks = [], [], [], [], []

    for sample in tqdm(test_ds, desc="Evaluating Test Documents"):
        img = sample["image"].convert("RGB")
        pixel_values = processor(img, return_tensors="pt").pixel_values.to(device)
        words = sample.get("words", [])
        gt_text = json.dumps({"text": " ".join(words[:40])})

        t0 = time.perf_counter()
        with torch.no_grad():
            gen_ids, meta = model.generate(pixel_values, max_length=256)
        lat = (time.perf_counter() - t0) * 1000.0

        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        ned = compute_normalized_edit_distance(pred, gt_text)

        neds.append(ned)
        latencies.append(lat)
        savings.append(meta["compression_ratio"])
        orig_toks.append(meta["original_tokens"])
        comp_toks.append(meta["compressed_tokens"])

    metrics = {
        "num_test_docs": len(test_ds),
        "mean_ned": float(np.mean(neds)),
        "character_accuracy_pct": float((1.0 - np.mean(neds)) * 100.0),
        "visual_token_savings_pct": float(np.mean(savings)),
        "mean_original_tokens": int(np.mean(orig_toks)),
        "mean_compressed_tokens": int(np.mean(comp_toks)),
        "mean_latency_ms": float(np.mean(latencies))
    }

    os.makedirs("visualizations", exist_ok=True)
    with open("visualizations/benchmark_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "="*50)
    print("           EVALUATION BENCHMARK SUMMARY")
    print("="*50)
    print(f"Evaluated Test Documents:     {metrics['num_test_docs']}")
    print(f"Mean Visual Token Reduction:  {metrics['visual_token_savings_pct']:.1f}%")
    print(f"Visual Tokens per Document:   {metrics['mean_compressed_tokens']} / {metrics['mean_original_tokens']}")
    print(f"Mean Edit Distance (NED):     {metrics['mean_ned']:.4f}")
    print(f"Character Accuracy:           {metrics['character_accuracy_pct']:.2f}%")
    print(f"Avg Inference Latency:        {metrics['mean_latency_ms']:.1f} ms")
    print("="*50)
    return metrics

if __name__ == "__main__":
    run_test_eval(max_docs=15)
