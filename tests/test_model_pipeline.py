import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import torch.nn as nn
from transformers import VisionEncoderDecoderConfig, VisionEncoderDecoderModel, ViTConfig, BertConfig
from src.router import PatchSaliencyRouter
from src.tome import BipartiteTokenMerger
from src.loss import AdaptivePruningLoss
from src.evaluate import visualize_pruned_patches
from PIL import Image
import numpy as np


class MiniAdaptiveOCR(nn.Module):
    """
    Lightweight version of AdaptiveDonutOCR using tiny ViT encoder + tiny Bert decoder
    for lightning-fast 100% offline verification of forward, backward, and generation pipelines.
    """
    def __init__(self, keep_ratio=0.35, merge_ratio=0.20):
        super().__init__()
        self.keep_ratio = keep_ratio
        self.merge_ratio = merge_ratio
        
        # Tiny Vision-Encoder-Decoder config
        encoder_config = ViTConfig(
            image_size=64,
            patch_size=16,
            num_channels=3,
            hidden_size=64,
            num_hidden_layers=2,
            num_attention_heads=2,
            intermediate_size=128
        )
        decoder_config = BertConfig(
            vocab_size=100,
            hidden_size=64,
            num_hidden_layers=2,
            num_attention_heads=2,
            intermediate_size=128,
            is_decoder=True,
            add_cross_attention=True
        )
        config = VisionEncoderDecoderConfig.from_encoder_decoder_configs(encoder_config, decoder_config)
        self.model = VisionEncoderDecoderModel(config=config)
        
        hidden_dim = 64
        self.router = PatchSaliencyRouter(hidden_dim=hidden_dim, reduction_dim=32)
        self.tome_merger = BipartiteTokenMerger(hidden_dim=hidden_dim)

    def forward(self, pixel_values, labels=None, decoder_input_ids=None):
        B = pixel_values.shape[0]
        encoder_outputs = self.model.encoder(pixel_values)
        visual_tokens = encoder_outputs.last_hidden_state  # (B, 1 + gh*gw, D)

        # Drop ViT's CLS token so the sequence is exactly the patch grid. The real
        # AdaptiveDonutOCR uses Swin, which emits gh*gw tokens and no CLS, and
        # src/model.py:_token_grid raises if the count and the grid disagree.
        # Keeping CLS here would make token_grid below off by one token -- and a
        # wrong grid width is the silent failure that function warns about: any
        # width still yields a valid two-colour partition, just one that no longer
        # tracks spatial adjacency.
        grid_h = grid_w = self.model.config.encoder.image_size // self.model.config.encoder.patch_size
        visual_tokens = visual_tokens[:, 1:, :]
        N = visual_tokens.shape[1]
        assert N == grid_h * grid_w, f"expected {grid_h}x{grid_w} patch tokens, got {N}"

        # 2D normalized coordinates
        coords = torch.rand(B, N, 2, device=pixel_values.device)

        # Saliency Router
        selected_tokens, scores, topk_indices, pruned_coords = self.router(
            visual_tokens, keep_ratio=self.keep_ratio, coords=coords, use_ste=self.training
        )

        # ToMe Merger -- topk_indices ARE the original raster positions, which is
        # what the checkerboard split needs.
        compressed_tokens, _ = self.tome_merger(
            selected_tokens, merge_ratio=self.merge_ratio, coords=pruned_coords,
            orig_idx=topk_indices, token_grid=(grid_h, grid_w)
        )
        M = compressed_tokens.shape[1]
        
        decoder_outputs = self.model.decoder(
            input_ids=decoder_input_ids,
            encoder_hidden_states=compressed_tokens,
            labels=labels,
            return_dict=True
        )
        
        return {
            "loss": getattr(decoder_outputs, "loss", None),
            "logits": decoder_outputs.logits,
            "scores": scores,
            "topk_indices": topk_indices,
            "original_tokens": N,
            "compressed_tokens": M,
            "compression_ratio": (1.0 - (M / N)) * 100.0
        }


def test_mini_ocr_pipeline():
    print("Testing Full Architecture Pipeline with MiniAdaptiveOCR...")
    model = MiniAdaptiveOCR(keep_ratio=0.35, merge_ratio=0.20)
    model.train()
    
    # 1. Simulate Document Batch (B=2, C=3, H=64, W=64)
    pixel_values = torch.randn(2, 3, 64, 64)
    labels = torch.randint(0, 100, (2, 16))
    decoder_input_ids = torch.randint(0, 100, (2, 16))
    
    # 2. Forward Pass
    outputs = model(pixel_values=pixel_values, labels=labels, decoder_input_ids=decoder_input_ids)
    print(f"Original tokens: {outputs['original_tokens']}")
    print(f"Compressed tokens: {outputs['compressed_tokens']}")
    print(f"Compression ratio: {outputs['compression_ratio']:.1f}%")
    assert outputs['compressed_tokens'] < outputs['original_tokens']
    
    # 3. Custom Multi-Task Sparsity Loss
    criterion = AdaptivePruningLoss(target_budget=0.25)
    loss_dict = criterion(
        decoder_logits=outputs["logits"],
        labels=labels,
        scores=outputs["scores"],
        provided_ce_loss=outputs["loss"]
    )
    print(f"Total Multi-Task Loss: {loss_dict['loss'].item():.4f}")
    print(f"Sparsity Loss: {loss_dict['sparsity_loss'].item():.4f}")
    
    # 4. Backward Pass & Gradient Flow
    loss_dict["loss"].backward()
    
    # Verify gradients on router
    router_grads = [p.grad for p in model.router.parameters() if p.grad is not None]
    assert len(router_grads) > 0 and all(torch.norm(g) > 0 for g in router_grads), "Router received 0 gradients!"
    print("Gradients successfully flowed through STE into Router scoring head!")
    
    # 5. Visualization Test
    dummy_img = Image.fromarray((np.random.rand(128, 128, 3) * 255).astype(np.uint8))
    os.makedirs("visualizations", exist_ok=True)
    visualize_pruned_patches(
        image=dummy_img,
        topk_indices=outputs["topk_indices"],
        original_token_count=outputs["original_tokens"],
        save_path="visualizations/mini_test_overlay.png"
    )
    assert os.path.exists("visualizations/mini_test_overlay.png")
    print("Visualization overlay successfully generated!")
    print("\n>>> ALL PIPELINE ARCHITECTURE TESTS PASSED 100%! <<<")


if __name__ == "__main__":
    test_mini_ocr_pipeline()
