import os
import sys
import unittest

import torch
import torch.nn as nn

# Running this as `python tests/test_modules.py` puts tests/ on sys.path instead of
# the repo root, so `import src` fails with ModuleNotFoundError. Add the root
# explicitly, the way tests/test_model_pipeline.py already does.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.router import PatchSaliencyRouter
from src.tome import BipartiteTokenMerger
from src.loss import AdaptivePruningLoss


class TestTokenPruningModules(unittest.TestCase):
    def setUp(self):
        self.B = 2
        self.N = 1200
        self.D = 1024
        self.tokens = torch.randn(self.B, self.N, self.D, requires_grad=True)
        self.coords = torch.rand(self.B, self.N, 2)

    def test_router_shapes_and_gradient(self):
        router = PatchSaliencyRouter(hidden_dim=self.D)
        router.train()
        
        keep_ratio = 0.35
        expected_K = int(round(self.N * keep_ratio))  # 420
        
        pruned_tokens, scores, topk_indices, pruned_coords = router(
            self.tokens,
            keep_ratio=keep_ratio,
            coords=self.coords,
            use_ste=True
        )
        
        self.assertEqual(pruned_tokens.shape, (self.B, expected_K, self.D))
        self.assertEqual(scores.shape, (self.B, self.N, 1))
        self.assertEqual(topk_indices.shape, (self.B, expected_K))
        self.assertEqual(pruned_coords.shape, (self.B, expected_K, 2))
        
        # Test Straight-Through Estimator gradient flow to router parameters
        dummy_loss = pruned_tokens.sum()
        dummy_loss.backward()
        
        # Check that gradients reached router weights
        has_grad = any(p.grad is not None and torch.norm(p.grad) > 0 for p in router.parameters())
        self.assertTrue(has_grad, "Gradients failed to flow into router parameters via STE!")

    def test_tome_merger(self):
        merger = BipartiteTokenMerger(hidden_dim=self.D)
        K = 420
        pruned_tokens = torch.randn(self.B, K, self.D)
        pruned_coords = torch.rand(self.B, K, 2)

        # ToMe's A/B split is a checkerboard over ORIGINAL page position, so the
        # merger has to be told where each surviving token sat. N=1200 factors as
        # a 30x40 grid. orig_idx is deliberately SHUFFLED, not sorted: the router
        # hands tokens over in descending-score order, and a raster-ordered
        # fixture would hide the very order-dependence the checkerboard split
        # exists to remove (see scripts/diagnose_tome_parity.py).
        GRID_H, GRID_W = 30, 40
        self.assertEqual(GRID_H * GRID_W, self.N, "grid must cover exactly N tokens")
        g = torch.Generator().manual_seed(0)
        orig_idx = torch.stack(
            [torch.randperm(self.N, generator=g)[:K] for _ in range(self.B)]
        )

        merge_ratio = 0.20
        merged_tokens, merged_coords = merger(
            pruned_tokens,
            merge_ratio=merge_ratio,
            coords=pruned_coords,
            orig_idx=orig_idx,
            token_grid=(GRID_H, GRID_W)
        )

        expected_r = min(int(round(K * merge_ratio)), K // 2)
        expected_M = K - expected_r
        
        self.assertEqual(merged_tokens.shape, (self.B, expected_M, self.D))
        self.assertEqual(merged_coords.shape, (self.B, expected_M, 2))

    def test_adaptive_loss(self):
        criterion = AdaptivePruningLoss(target_budget=0.25)
        scores = torch.rand(self.B, self.N, 1, requires_grad=True)
        decoder_logits = torch.randn(self.B, 64, 1000)
        labels = torch.randint(0, 1000, (self.B, 64))
        
        loss_dict = criterion(decoder_logits, labels, scores)
        self.assertIn("loss", loss_dict)
        self.assertIn("ce_loss", loss_dict)
        self.assertIn("sparsity_loss", loss_dict)
        self.assertIn("entropy_loss", loss_dict)
        
        # Backward check
        loss_dict["loss"].backward()
        self.assertIsNotNone(scores.grad)


if __name__ == "__main__":
    unittest.main()
