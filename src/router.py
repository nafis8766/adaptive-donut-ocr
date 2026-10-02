import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class PatchSaliencyRouter(nn.Module):
    """
    Lightweight trainable scoring router that predicts saliency/information density
    for each visual patch token and selects top-K tokens using a Straight-Through Estimator (STE).
    
    Attributes:
        hidden_dim (int): Dimensionality of input visual embeddings.
        mlp (nn.Sequential): 2-layer scoring network (Linear -> LayerNorm -> GELU -> Linear -> Sigmoid).
    """
    def __init__(self, hidden_dim: int = 1024, reduction_dim: int = 256):
        super().__init__()
        self.hidden_dim = hidden_dim
        
        self.scorer = nn.Sequential(
            nn.Linear(hidden_dim, reduction_dim),
            nn.LayerNorm(reduction_dim),
            nn.GELU(),
            nn.Linear(reduction_dim, 1),
            nn.Sigmoid()
        )
        
        # Initialize bias towards keeping tokens early in training
        nn.init.constant_(self.scorer[-2].bias, 0.5)

    def forward(
        self,
        tokens: torch.Tensor,
        keep_ratio: float = 0.35,
        coords: Optional[torch.Tensor] = None,
        use_ste: bool = True,
        select_scores: Optional[torch.Tensor] = None,
        invert: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass for dynamic token selection.

        Args:
            tokens (torch.Tensor): Visual token embeddings (B, N, D).
            keep_ratio (float): Fraction of tokens to retain (e.g. 0.25 to 0.50).
            coords (torch.Tensor, optional): Normalized 2D coordinates (B, N, 2).
            use_ste (bool): Whether to apply Straight-Through Estimator in training.
            select_scores (torch.Tensor, optional): (B, N) ranking signal to select by
                INSTEAD of the learned scores -- e.g. uniform noise for a
                random-pruning control, or patch ink for an oracle upper bound. The
                learned `scores` are still computed and returned so reporting is
                unaffected. Diagnostic/eval use only: STE is skipped when set, since
                gradient through a ranking the scorer did not produce is meaningless.
            invert (bool): Select the LOWEST-ranked tokens instead of the highest.
                Diagnostic D1 measured the trained router as anti-correlated with ink
                (r ~ -0.24), so inverting it retains 0.62-0.66 of a page's ink versus
                0.50 for random. See AGENTS.md Diagnostic D1.

        Returns:
            pruned_tokens (torch.Tensor): Filtered visual embeddings (B, K, D).
            scores (torch.Tensor): Raw token importance scores (B, N, 1).
            selected_indices (torch.Tensor): Indices of selected tokens (B, K).
            pruned_coords (torch.Tensor, optional): Filtered coordinates (B, K, 2).
        """
        B, N, D = tokens.shape
        K = max(1, int(round(N * keep_ratio)))

        # 1. Compute per-token saliency scores in range [0, 1]
        scores = self.scorer(tokens)  # (B, N, 1)

        # 2. Extract Top-K indices based on the ranking signal
        if select_scores is not None:
            if select_scores.shape[:2] != (B, N):
                raise ValueError(
                    f"select_scores must be (B, N) = {(B, N)}, got {tuple(select_scores.shape)}"
                )
            rank_by = select_scores.reshape(B, N).to(scores.dtype)
        else:
            rank_by = scores.squeeze(-1)
        topk_scores, topk_indices = torch.topk(
            rank_by, k=K, dim=1, largest=not invert, sorted=True
        )  # (B, K)

        # 3. Gather selected tokens
        indices_expanded = topk_indices.unsqueeze(-1).expand(-1, -1, D)  # (B, K, D)
        selected_tokens = torch.gather(tokens, dim=1, index=indices_expanded)

        # 4. Straight-Through Estimator (STE) for differentiability
        #    Skipped under an external ranking: `topk_scores` would then be the
        #    override's values, not the scorer's, and scaling tokens by those sends a
        #    gradient the scorer cannot be responsible for.
        if self.training and use_ste and select_scores is None:
            # Scale tokens by (1 + score - detach(score)) so d(Loss)/d(score) flows into the router head
            ste_weights = topk_scores.unsqueeze(-1)
            ste_multiplier = 1.0 + (ste_weights - ste_weights.detach())
            selected_tokens = selected_tokens * ste_multiplier
            
        # 5. Gather coordinates if provided
        pruned_coords = None
        if coords is not None:
            coords_expanded = topk_indices.unsqueeze(-1).expand(-1, -1, coords.shape[-1])  # (B, K, 2)
            pruned_coords = torch.gather(coords, dim=1, index=coords_expanded)
            
        return selected_tokens, scores, topk_indices, pruned_coords
