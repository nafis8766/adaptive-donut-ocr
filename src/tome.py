import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, Sequence


def checkerboard_color(orig_idx: torch.Tensor, grid_w: int) -> torch.Tensor:
    """Map ORIGINAL raster token indices to a {0, 1} checkerboard colour.

    Args:
        orig_idx: (B, K) positions into the encoder's pre-prune raster sequence
            (i.e. the router's `topk_indices`), NOT positions in the pruned
            sequence.
        grid_w: width of the token grid, so row = idx // grid_w, col = idx % grid_w.

    Returns:
        (B, K) tensor of 0/1. Colour is `(row + col) % 2`, which places every
        4-neighbour (up / down / left / right) in the OPPOSITE set.

    Why the original position and not the sequence position: the router's
    `torch.topk(..., sorted=True)` reorders the surviving tokens by descending
    score, so by the time they reach ToMe a token's index in the sequence means
    "rank", not "place on the page". The previous split (`arange(0,K,2)` /
    `arange(1,K,2)`) read that sequence position directly and therefore
    partitioned by score-rank parity. Deriving colour from `orig_idx` makes the
    split independent of the order tokens arrive in -- measured, see
    `scripts/diagnose_tome_parity.py`.

    Note this is also why raster order alone was not a fix: the grid is 60 wide
    and 60 is even, so `i` and `i + 60` (the token directly below) share parity
    and 100% of vertically-adjacent redundancy was unmergable. See AGENTS.md
    Gotchas.
    """
    if grid_w <= 0:
        raise ValueError(f"grid_w must be positive, got {grid_w}")
    if not torch.is_tensor(orig_idx):
        raise TypeError(f"orig_idx must be a tensor, got {type(orig_idx).__name__}")
    return ((orig_idx // grid_w) + (orig_idx % grid_w)) % 2


class BipartiteTokenMerger(nn.Module):
    """
    Bipartite Token Merging (ToMe) module for visual embeddings.

    Partitions the surviving visual tokens into two disjoint sets by CHECKERBOARD
    COLOUR OF THEIR ORIGINAL PAGE POSITION, computes cosine similarity across the
    two sets, and soft-merges the most mutually similar pairs -- compacting
    redundant regions without in-place mutation or autograd version conflicts.

    The split is order-independent by construction, which is the whole point: the
    router hands tokens over in descending-score order, so any split that reads
    sequence position strands roughly half of all genuinely-redundant pairs in
    the same set, where ToMe's A->B merge can never reach them.
    """
    def __init__(self, hidden_dim: int = 1024):
        super().__init__()
        self.hidden_dim = hidden_dim

    def forward(
        self,
        tokens: torch.Tensor,
        merge_ratio: float = 0.20,
        coords: Optional[torch.Tensor] = None,
        orig_idx: Optional[torch.Tensor] = None,
        token_grid: Optional[Sequence[int]] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Merges redundant visual tokens via bipartite matching.

        Args:
            tokens (torch.Tensor): Visual token embeddings (B, K, D).
            merge_ratio (float): Fraction of tokens to merge away (0.0 <= merge_ratio < 0.5).
            coords (torch.Tensor, optional): 2D normalized coordinates (B, K, 2).
            orig_idx (torch.Tensor): (B, K) indices of these tokens in the
                encoder's ORIGINAL raster sequence -- the router's `topk_indices`.
                REQUIRED whenever merging actually happens; see the raise below.
            token_grid (tuple): (grid_h, grid_w) of the encoder token grid, e.g.
                (80, 60). Only `grid_w` is used. REQUIRED alongside `orig_idx`.

        Returns:
            merged_tokens (torch.Tensor): Compact token embeddings (B, M, D) where M = K - r.
            merged_coords (torch.Tensor, optional): Updated 2D centroid coordinates (B, M, 2).

        Raises:
            ValueError: if merging would happen but `orig_idx`/`token_grid` were
                not supplied. This is deliberate rather than a silent fallback to
                the old parity split: that split is only correct under raster
                order, the router does not deliver raster order, and the failure
                is invisible in the output (it produces a plausible merged tensor
                that merged the wrong things). A caller that has not thought
                about page position must not get a merge.
        """
        B, K, D = tokens.shape
        if K <= 4 or merge_ratio <= 0.0:
            return tokens, coords

        r = min(int(round(K * merge_ratio)), K // 2)
        if r <= 0:
            return tokens, coords

        if orig_idx is None or token_grid is None:
            raise ValueError(
                "BipartiteTokenMerger needs orig_idx (B, K) and token_grid "
                "(grid_h, grid_w) once merge_ratio > 0: the A/B split is a "
                "checkerboard over ORIGINAL page position, because the router "
                "delivers tokens in descending-score order and a split that "
                "reads sequence position merges by score-rank neighbourhood "
                "instead of spatial adjacency. See AGENTS.md Gotchas."
            )

        if len(token_grid) != 2:
            raise ValueError(f"token_grid must be (grid_h, grid_w), got {tuple(token_grid)}")
        grid_w = int(token_grid[1])
        if tuple(orig_idx.shape) != (B, K):
            raise ValueError(
                f"orig_idx must be (B, K) = {(B, K)}, got {tuple(orig_idx.shape)}"
            )

        color = checkerboard_color(orig_idx, grid_w)  # (B, K) in {0, 1}

        # Membership is per-image (it depends on which tokens the router kept), so
        # K_A varies down the batch even though K does not. Loop rather than pad:
        # B is small, the existing code already loops for the unmerged gather, and
        # M = K_B + (K_A - r) = K - r is constant regardless of how the split
        # falls -- which is what keeps the output batchable.
        idx_A_list = [torch.nonzero(color[b] == 0, as_tuple=False).squeeze(-1) for b in range(B)]
        idx_B_list = [torch.nonzero(color[b] == 1, as_tuple=False).squeeze(-1) for b in range(B)]

        min_K_A = min(int(x.numel()) for x in idx_A_list)
        min_K_B = min(int(x.numel()) for x in idx_B_list)
        if min_K_A == 0 or min_K_B == 0:
            # A degenerate selection (every kept token one colour) has nothing to
            # merge into. Pass through rather than merge the wrong things.
            return tokens, coords

        # r must be uniform across the batch or M would differ per image.
        r_actual = min(r, min_K_A)
        if r_actual <= 0:
            return tokens, coords

        out_tokens_list = []
        out_coords_list = []
        for b in range(B):
            idx_A, idx_B = idx_A_list[b], idx_B_list[b]
            A = tokens[b:b + 1, idx_A, :]          # (1, K_A, D)
            B_set = tokens[b:b + 1, idx_B, :]      # (1, K_B, D)
            coords_A = coords[b:b + 1, idx_A, :] if coords is not None else None
            coords_B = coords[b:b + 1, idx_B, :] if coords is not None else None

            K_A, K_B = A.shape[1], B_set.shape[1]

            A_norm = F.normalize(A, p=2, dim=-1)
            B_norm = F.normalize(B_set, p=2, dim=-1)
            sim = torch.bmm(A_norm, B_norm.transpose(1, 2))  # (1, K_A, K_B)

            max_sim_val, max_sim_idx = sim.max(dim=-1)       # (1, K_A)
            _, top_r_A_idx = torch.topk(max_sim_val, k=r_actual, dim=-1, largest=True)

            T = torch.zeros((1, K_A, K_B), device=tokens.device, dtype=tokens.dtype)
            row_idx = torch.zeros((1, r_actual), dtype=torch.long, device=tokens.device)
            target_b = torch.gather(max_sim_idx, 1, top_r_A_idx)
            T[row_idx, top_r_A_idx, target_b] = 1.0

            T_t = T.transpose(1, 2)                          # (1, K_B, K_A)
            W_B = 1.0 + T_t.sum(dim=-1, keepdim=True)        # (1, K_B, 1)
            B_merged = (B_set + torch.bmm(T_t, A)) / W_B

            mask_A = torch.ones((1, K_A), dtype=torch.bool, device=tokens.device)
            mask_A[row_idx, top_r_A_idx] = False
            A_unmerged = A[0, mask_A[0]].unsqueeze(0)        # (1, K_A - r, D)

            out_tokens_list.append(torch.cat([B_merged, A_unmerged], dim=1))

            if coords is not None:
                coords_B_merged = (coords_B + torch.bmm(T_t, coords_A)) / W_B
                coords_A_unmerged = coords_A[0, mask_A[0]].unsqueeze(0)
                out_coords_list.append(torch.cat([coords_B_merged, coords_A_unmerged], dim=1))

        out_tokens = torch.cat(out_tokens_list, dim=0)
        out_coords = torch.cat(out_coords_list, dim=0) if coords is not None else None

        return out_tokens, out_coords
