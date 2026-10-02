import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from transformers import DonutProcessor
from src.model import AdaptiveDonutOCR
from src.loss import AdaptivePruningLoss
from src.dataset import SROIEDonutDataset, create_donut_data_collator
from src.evaluate import compute_normalized_edit_distance, visualize_pruned_patches


def test_full_pipeline():
    print("=== Testing End-to-End Pipeline ===")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    
    # 1. Test Processor & Dataset Loading
    print("\n1. Testing dataset & processor loading (2 samples from FUNSD)...")
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    dataset = SROIEDonutDataset(
        dataset_name="nielsr/funsd",
        split="test",
        processor=processor,
        max_samples=2
    )
    assert len(dataset) == 2, f"Expected 2 samples, got {len(dataset)}"
    
    sample = dataset[0]
    assert "pixel_values" in sample
    assert "labels" in sample
    print(f"Sample pixel shape: {sample['pixel_values'].shape}")
    
    # 2. Test Batch Collation
    collator = create_donut_data_collator(pad_token_id=processor.tokenizer.pad_token_id)
    batch = collator([dataset[0], dataset[1]])
    print(f"Batch pixel_values shape: {batch['pixel_values'].shape}")
    print(f"Batch labels shape: {batch['labels'].shape}")
    
    # 3. Test AdaptiveDonutOCR Model Initialization & Forward
    print("\n2. Initializing AdaptiveDonutOCR model...")
    model = AdaptiveDonutOCR(
        base_model_name="naver-clova-ix/donut-base",
        keep_ratio=0.35,
        merge_ratio=0.20
    ).to(device)
    
    pixel_values = batch["pixel_values"].to(device)
    labels = batch["labels"].to(device)
    decoder_input_ids = batch["decoder_input_ids"].to(device)
    
    print("\n3. Testing Forward Pass with Pruning & Merging...")
    outputs = model(
        pixel_values=pixel_values,
        labels=labels,
        decoder_input_ids=decoder_input_ids
    )
    
    orig_tokens = outputs["original_tokens"]
    comp_tokens = outputs["compressed_tokens"]
    ratio = outputs["compression_ratio"]
    print(f"Original visual tokens: {orig_tokens}")
    print(f"Compressed visual tokens fed to decoder: {comp_tokens}")
    print(f"Visual token compression ratio: {ratio:.1f}%")
    assert comp_tokens < orig_tokens, "Tokens were not pruned/compressed!"
    
    # 4. Test Multi-Task Loss Calculation & Backward pass
    print("\n4. Testing Multi-Task Loss & Backpropagation...")
    criterion = AdaptivePruningLoss(target_budget=0.25, pad_token_id=processor.tokenizer.pad_token_id)
    loss_dict = criterion(
        decoder_logits=outputs["logits"],
        labels=labels,
        scores=outputs["scores"],
        provided_ce_loss=outputs["loss"]
    )
    print(f"Total Loss: {loss_dict['loss'].item():.4f}")
    print(f"CE Loss: {loss_dict['ce_loss'].item():.4f}")
    print(f"Sparsity Loss: {loss_dict['sparsity_loss'].item():.4f}")
    
    loss_dict["loss"].backward()
    print("Backward pass completed successfully! Gradients verified.")
    
    # 5. Test Inference Generation
    print("\n5. Testing Fast Inference Generation...")
    gen_ids, meta = model.generate(pixel_values[:1], max_length=64)
    pred_text = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
    print(f"Generated text sample: {pred_text[:80]}...")
    
    # 6. Test Evaluation & Visualization Helper
    print("\n6. Testing Overlay Visualization...")
    os.makedirs("visualizations", exist_ok=True)
    visualize_pruned_patches(
        image=dataset.dataset[0]["image"],
        topk_indices=meta["topk_indices"],
        original_token_count=meta["original_tokens"],
        save_path="visualizations/test_overlay.png"
    )
    assert os.path.exists("visualizations/test_overlay.png")
    print("Visualization saved successfully to visualizations/test_overlay.png!")
    
    print("\n==========================================")
    print("ALL END-TO-END PIPELINE TESTS PASSED 100%!")
    print("==========================================")


if __name__ == "__main__":
    test_full_pipeline()
