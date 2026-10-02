import os
import sys
import unittest

import torch
import torch.nn.functional as F

# Running this as `python tests/test_tome_correctness.py` puts tests/ on sys.path
# instead of the repo root, so `import src` fails with ModuleNotFoundError. Add the
# root explicitly, the way tests/test_model_pipeline.py already does. A test that
# needs an env var prefix to run is a test people stop running.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tome import BipartiteTokenMerger, checkerboard_color


def row_order(x: torch.Tensor) -> torch.Tensor:
    """Canonical row ordering so two token SETS can be compared regardless of
    the order they happen to come out in."""
    key = x[0].sum(dim=-1)
    return x[0][key.argsort()]


class TestCheckerboardSplit(unittest.TestCase):
    def test_four_neighbours_are_opposite_colours(self):
        # The whole point of the checkerboard: every up/down/left/right neighbour
        # on the real 80x60 grid must land in the OPPOSITE merge set, so ToMe's
        # A->B merge can always reach it. The old parity split failed this for
        # 100% of vertical neighbours (grid width 60 is even, so i and i+60 share
        # parity).
        GH, GW = 80, 60
        idx = torch.arange(GH * GW).view(1, -1)
        color = checkerboard_color(idx, GW).view(GH, GW)

        self.assertTrue((color[:, :-1] != color[:, 1:]).all(),
                        "horizontal neighbours share a colour")
        self.assertTrue((color[:-1, :] != color[1:, :]).all(),
                        "vertical neighbours share a colour")
        # And the split is close to balanced, so neither set starves.
        frac = color.float().mean().item()
        self.assertAlmostEqual(frac, 0.5, places=2)

    def test_diagonal_neighbours_share_a_colour(self):
        # The honest cost of the checkerboard, asserted rather than left implicit:
        # diagonal neighbours ARE unreachable. Accepted because every token also
        # has four 4-neighbours in the opposite set, and ToMe merges each A token
        # with its single best partner anywhere in B.
        GH, GW = 80, 60
        color = checkerboard_color(torch.arange(GH * GW).view(1, -1), GW).view(GH, GW)
        self.assertTrue((color[:-1, :-1] == color[1:, 1:]).all())

    def test_colour_is_independent_of_arrival_order(self):
        # Colour is a function of the ORIGINAL index only, so permuting the
        # sequence permutes the colours identically -- it does not change which
        # set a token belongs to. This is the property the router's score-sort
        # used to destroy.
        idx = torch.arange(4800).view(1, -1)
        perm = torch.randperm(4800)
        c1 = checkerboard_color(idx, 60)[0][perm]
        c2 = checkerboard_color(idx[0][perm].view(1, -1), 60)[0]
        self.assertTrue(torch.equal(c1, c2))


class TestTomeCorrectness(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0)
        self.D = 32

    def test_merges_similar_pairs(self):
        # 8 tokens on a 1x8 strip as 4 horizontally-adjacent pairs of
        # near-identical vectors. The checkerboard puts each pair across the split.
        base = torch.randn(self.D)
        tok = torch.zeros(8, self.D)
        for i in range(4):
            tok[2 * i] = base + torch.randn(self.D) * 1e-3
            tok[2 * i + 1] = base + torch.randn(self.D) * 1e-3
        tokens = tok.unsqueeze(0)
        coords = torch.rand(1, 8, 2)
        orig_idx = torch.arange(8).view(1, 8)

        merger = BipartiteTokenMerger(hidden_dim=self.D)
        merged, _ = merger(tokens, merge_ratio=0.5, coords=coords,
                           orig_idx=orig_idx, token_grid=(1, 8))

        # 8 tokens, r = min(round(8*0.5), 4) = 4 -> M = 4
        self.assertEqual(merged.shape, (1, 4, self.D))
        # All four merged vectors sit near the shared base => mutually similar.
        normed = F.normalize(merged[0], p=2, dim=-1)
        sims = normed @ normed.t()  # (4,4) pairwise cosine
        off_diag = sims[~torch.eye(4, dtype=torch.bool)]
        self.assertGreater(off_diag.mean().item(), 0.99,
                           "Soft-merged vectors should be near-identical")

    def test_dissimilar_clusters_survive(self):
        # Two well-separated clusters, interleaved. Only the single most-similar
        # pair may merge; the rest must survive (M == K - 1).
        a = torch.randn(self.D)
        b = torch.randn(self.D) + 50.0  # far from a
        K = 10
        tok = torch.zeros(K, self.D)
        for i in range(K):
            tok[i] = (a if i % 2 == 0 else b) + torch.randn(self.D) * 1e-2
        tokens = tok.unsqueeze(0)
        coords = torch.rand(1, K, 2)
        orig_idx = torch.arange(K).view(1, K)

        merger = BipartiteTokenMerger(hidden_dim=self.D)
        merged, _ = merger(tokens, merge_ratio=0.1, coords=coords,
                           orig_idx=orig_idx, token_grid=(1, K))

        r = min(int(round(K * 0.1)), K // 2)  # 1
        self.assertEqual(merged.shape[1], K - r)

    def test_coord_centroid_correct(self):
        # Merged coordinates must equal the average of the two endpoints.
        B, K, D = 1, 6, self.D
        tokens = torch.randn(B, K, D)
        coords = torch.arange(K, dtype=torch.float32).view(1, K, 1).expand(B, K, 2) / 10.0
        orig_idx = torch.arange(K).view(1, K)

        merger = BipartiteTokenMerger(hidden_dim=D)
        _, mcoords = merger(tokens, merge_ratio=0.5, coords=coords,
                            orig_idx=orig_idx, token_grid=(1, K))

        # Centroids are averages of input coords, so they must lie strictly
        # inside [min, max] of the inputs.
        self.assertTrue((mcoords >= coords.min() - 1e-5).all())
        self.assertTrue((mcoords <= coords.max() + 1e-5).all())

    def test_output_length_is_K_minus_r(self):
        # M must not depend on how the checkerboard falls, or the batch could not
        # be stacked. Exercised with a lopsided selection (mostly one colour).
        GW = 6
        orig_idx = torch.tensor([[0, 2, 4, 6, 8, 10, 12, 1, 3, 5]])  # 7 vs 3 split
        K = orig_idx.shape[1]
        tokens = torch.randn(1, K, self.D)
        merger = BipartiteTokenMerger(hidden_dim=self.D)
        merged, _ = merger(tokens, merge_ratio=0.2, orig_idx=orig_idx, token_grid=(4, GW))
        r = min(int(round(K * 0.2)), K // 2)
        self.assertEqual(merged.shape[1], K - r)

    def test_batch_with_different_splits_stays_stackable(self):
        # Two images whose kept tokens fall differently across the checkerboard.
        # K_A differs down the batch; M must not.
        K = 12
        orig_idx = torch.stack([
            torch.arange(K),                      # alternating colours
            torch.arange(0, 2 * K, 2),            # skewed toward one colour
        ])
        tokens = torch.randn(2, K, self.D)
        merger = BipartiteTokenMerger(hidden_dim=self.D)
        merged, _ = merger(tokens, merge_ratio=0.25, orig_idx=orig_idx, token_grid=(4, 6))
        r = min(int(round(K * 0.25)), K // 2)
        self.assertEqual(merged.shape, (2, K - r, self.D))

    def test_merging_is_order_independent(self):
        # THE regression test for the gotcha. Previously this file asserted the
        # OPPOSITE (`test_parity_is_order_dependent`), because the old split read
        # sequence position and order-independence was evidence the split had
        # stopped working. That is exactly backwards for the pipeline we have: the
        # router hands ToMe tokens in DESCENDING SCORE order, so any order-sensitive
        # split merges by score-rank neighbourhood instead of spatial adjacency.
        #
        # Same tokens, two arrival orders, same merge decisions.
        torch.manual_seed(1)
        GH, GW = 4, 6
        K = GH * GW
        n_pairs = K // 2
        pair_vec = torch.randn(n_pairs, self.D)
        tok = torch.zeros(K, self.D)
        for p in range(n_pairs):
            # Horizontally adjacent cells (2c, 2c+1) within a row of width 6.
            i = (p // 3) * GW + (p % 3) * 2
            tok[i] = pair_vec[p]
            tok[i + 1] = pair_vec[p] + torch.randn(self.D) * 1e-3

        raster = torch.arange(K)
        scrambled = torch.randperm(K)

        merger = BipartiteTokenMerger(hidden_dim=self.D)

        def merge(order):
            t = tok[order].unsqueeze(0)
            idx = raster[order].view(1, K)
            merged, _ = merger(t, merge_ratio=0.5, orig_idx=idx, token_grid=(GH, GW))
            return merged

        m_raster = merge(raster)
        m_scrambled = merge(scrambled)

        # The output SEQUENCE differs (it follows arrival order); the merged SET
        # must not.
        diff = (row_order(m_raster) - row_order(m_scrambled)).abs().max().item()
        self.assertLess(diff, 1e-4,
                        "Same tokens in a different arrival order produced "
                        "different merges; the split is still reading sequence "
                        "position instead of original page position")


class TestTomeGuards(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0)
        self.D = 16
        self.merger = BipartiteTokenMerger(hidden_dim=self.D)

    def test_merging_without_orig_idx_raises(self):
        # A silent fallback to the old parity split would produce a
        # plausible-looking merged tensor that merged the wrong things, so the
        # broken configuration is made unrepresentable instead.
        tokens = torch.randn(1, 12, self.D)
        with self.assertRaises(ValueError):
            self.merger(tokens, merge_ratio=0.25)
        with self.assertRaises(ValueError):
            self.merger(tokens, merge_ratio=0.25, orig_idx=torch.arange(12).view(1, 12))

    def test_zero_merge_ratio_is_a_passthrough(self):
        # Every run so far used merge_ratio=0.0; that path must stay callable
        # without page indices, and must return the input untouched.
        tokens = torch.randn(1, 12, self.D)
        coords = torch.rand(1, 12, 2)
        out, ocoords = self.merger(tokens, merge_ratio=0.0, coords=coords)
        self.assertTrue(torch.equal(out, tokens))
        self.assertTrue(torch.equal(ocoords, coords))

    def test_mismatched_orig_idx_shape_raises(self):
        tokens = torch.randn(1, 12, self.D)
        with self.assertRaises(ValueError):
            self.merger(tokens, merge_ratio=0.25,
                        orig_idx=torch.arange(10).view(1, 10), token_grid=(4, 6))

    def test_single_colour_selection_passes_through(self):
        # Degenerate: every kept token the same colour, nothing to merge into.
        # Pass through rather than merge the wrong things.
        orig_idx = torch.arange(0, 24, 2).view(1, 12)  # all even index, GW=6 -> ?
        color = checkerboard_color(orig_idx, 6)
        tokens = torch.randn(1, 12, self.D)
        out, _ = self.merger(tokens, merge_ratio=0.25, orig_idx=orig_idx, token_grid=(6, 6))
        if color.unique().numel() == 1:
            self.assertTrue(torch.equal(out, tokens))
        else:
            self.assertEqual(out.shape[1], 12 - min(int(round(12 * 0.25)), 6))


if __name__ == "__main__":
    unittest.main()
