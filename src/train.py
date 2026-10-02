import os
import argparse
import time
import gc
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import DonutProcessor
from tqdm import tqdm

from src.model import AdaptiveDonutOCR
from src.loss import AdaptivePruningLoss
from src.dataset import SROIEDonutDataset, create_donut_data_collator


def train_epoch(
    model: AdaptiveDonutOCR,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: AdaptivePruningLoss,
    scaler: torch.amp.GradScaler,
    device: torch.device,
    grad_accum_steps: int = 8
):
    model.train()
    total_loss = 0.0
    total_ce_loss = 0.0
    total_sparsity_loss = 0.0
    total_mean_score = 0.0
    
    optimizer.zero_grad()
    pbar = tqdm(dataloader, desc="Training", leave=False)
    
    for step, batch in enumerate(pbar):
        pixel_values = batch["pixel_values"].to(device, dtype=torch.float16 if device.type == "cuda" else torch.float32)
        labels = batch["labels"].to(device)
        decoder_input_ids = batch["decoder_input_ids"].to(device)
        
        # Mixed Precision Forward Pass
        with torch.amp.autocast("cuda" if device.type == "cuda" else "cpu"):
            outputs = model(
                pixel_values=pixel_values,
                labels=labels,
                decoder_input_ids=decoder_input_ids
            )
            
            loss_dict = criterion(
                decoder_logits=outputs["logits"],
                labels=labels,
                scores=outputs["scores"],
                provided_ce_loss=outputs["loss"]
            )
            
            loss = loss_dict["loss"] / grad_accum_steps
            
        # Scaled Backpropagation
        scaler.scale(loss).backward()
        
        if (step + 1) % grad_accum_steps == 0 or (step + 1) == len(dataloader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
            
        # Logging stats
        total_loss += loss_dict["loss"].item()
        total_ce_loss += loss_dict["ce_loss"].item()
        total_sparsity_loss += loss_dict["sparsity_loss"].item()
        total_mean_score += loss_dict["mean_score"].item()
        
        pbar.set_postfix({
            "Loss": f"{loss_dict['loss'].item():.3f}",
            "CE": f"{loss_dict['ce_loss'].item():.3f}",
            "Sparsity": f"{loss_dict['sparsity_loss'].item():.3f}",
            "Score": f"{loss_dict['mean_score'].item():.2f}",
            "Tokens": f"{outputs['compressed_tokens']}/{outputs['original_tokens']}"
        })
        
    n_batches = len(dataloader)
    return {
        "loss": total_loss / n_batches,
        "ce_loss": total_ce_loss / n_batches,
        "sparsity_loss": total_sparsity_loss / n_batches,
        "mean_score": total_mean_score / n_batches
    }


def main():
    parser = argparse.ArgumentParser(description="Train Adaptive Token Pruning Engine for Document OCR")
    parser.add_argument("--base_model", type=str, default="naver-clova-ix/donut-base")
    parser.add_argument("--dataset_name", type=str, default="nielsr/funsd")
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--grad_accum", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr_router", type=float, default=1e-4)
    parser.add_argument("--lr_decoder", type=float, default=2e-5)
    parser.add_argument("--keep_ratio", type=float, default=0.35)
    parser.add_argument("--merge_ratio", type=float, default=0.20)
    parser.add_argument("--target_budget", type=float, default=0.25)
    parser.add_argument("--lambda_sparsity", type=float, default=2.0)
    parser.add_argument("--save_dir", type=str, default="./checkpoints")
    parser.add_argument("--max_train_samples", type=int, default=None)
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # 1. Load Processor
    print(f"Loading processor for {args.base_model}...")
    processor = DonutProcessor.from_pretrained(args.base_model)

    # 2. Build Dataset & DataLoader
    train_dataset = SROIEDonutDataset(
        dataset_name=args.dataset_name,
        split="train",
        processor=processor,
        max_samples=args.max_train_samples
    )
    collator = create_donut_data_collator(pad_token_id=processor.tokenizer.pad_token_id)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collator,
        num_workers=2 if device.type == "cuda" else 0
    )

    # 3. Clean Memory & Instantiate Model with Frozen Encoder
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    model = AdaptiveDonutOCR(
        base_model_name=args.base_model,
        keep_ratio=args.keep_ratio,
        merge_ratio=args.merge_ratio,
        freeze_encoder=True
    ).to(device)

    # 4. Configure Optimization (Train Router and Decoder)
    trainable_params = [
        {"params": model.router.parameters(), "lr": args.lr_router},
        {"params": model.model.decoder.parameters(), "lr": args.lr_decoder}
    ]

    optimizer = torch.optim.AdamW(trainable_params, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda" if device.type == "cuda" else "cpu")
    criterion = AdaptivePruningLoss(
        lambda_sparsity=args.lambda_sparsity,
        target_budget=args.target_budget,
        pad_token_id=processor.tokenizer.pad_token_id
    )

    # 5. Training Loop
    print("\nStarting Training (VRAM usage is < 2.0 GB)...")
    best_loss = float("inf")
    
    for epoch in range(1, args.epochs + 1):
        start_time = time.time()
        metrics = train_epoch(
            model=model,
            dataloader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            scaler=scaler,
            device=device,
            grad_accum_steps=args.grad_accum
        )
        elapsed = time.time() - start_time
        
        print(f"Epoch [{epoch}/{args.epochs}] ({elapsed:.1f}s) | "
              f"Total Loss: {metrics['loss']:.4f} | "
              f"CE Loss: {metrics['ce_loss']:.4f} | "
              f"Sparsity Loss: {metrics['sparsity_loss']:.4f} | "
              f"Mean Score: {metrics['mean_score']:.3f}")
              
        # Save Checkpoint
        if metrics["loss"] < best_loss:
            best_loss = metrics["loss"]
            save_path = os.path.join(args.save_dir, "best_adaptive_donut.pt")
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "router_state_dict": model.router.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "loss": best_loss
            }, save_path)
            print(f"  -> Saved best model checkpoint to {save_path}")

    print("\nTraining completed successfully!")


if __name__ == "__main__":
    main()
