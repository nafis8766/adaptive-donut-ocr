import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict


class AdaptivePruningLoss(nn.Module):
    """
    Custom Joint Multi-Task Loss balancing OCR transcription accuracy with token economy.
    
    Formula:
        L_total = L_CE + lambda_sparsity * L_sparsity + lambda_entropy * L_entropy
        
    where:
        L_sparsity = Smooth_L1(mean(scores) - target_budget)
        L_entropy  = Binary entropy regularization to ensure calibrated confidence
    """
    def __init__(
        self,
        lambda_sparsity: float = 2.0,
        lambda_entropy: float = 0.05,
        target_budget: float = 0.25,  # Keep 25% of tokens (75% compression)
        pad_token_id: int = -100
    ):
        super().__init__()
        self.lambda_sparsity = lambda_sparsity
        self.lambda_entropy = lambda_entropy
        self.target_budget = target_budget
        self.pad_token_id = pad_token_id
        self.ce_loss_fn = nn.CrossEntropyLoss(ignore_index=pad_token_id)

    def forward(
        self,
        decoder_logits: Optional[torch.Tensor],
        labels: Optional[torch.Tensor],
        scores: torch.Tensor,
        provided_ce_loss: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Calculates joint multi-task loss components.
        
        Args:
            decoder_logits (torch.Tensor, optional): Output logits from decoder (B, SeqLen, VocabSize).
            labels (torch.Tensor, optional): Target token IDs (B, SeqLen).
            scores (torch.Tensor): Visual patch saliency scores (B, N, 1).
            provided_ce_loss (torch.Tensor, optional): Precomputed CE loss from HuggingFace decoder.
            
        Returns:
            Dict containing 'loss' (total), 'ce_loss', 'sparsity_loss', 'entropy_loss', and 'mean_score'.
        """
        # 1. Transcription Cross-Entropy Loss
        if provided_ce_loss is not None:
            ce_loss = provided_ce_loss
        elif decoder_logits is not None and labels is not None:
            vocab_size = decoder_logits.shape[-1]
            ce_loss = self.ce_loss_fn(decoder_logits.view(-1, vocab_size), labels.view(-1))
        else:
            ce_loss = torch.tensor(0.0, device=scores.device)

        # 2. Token Budget Sparsity Loss (Smooth L1 distance to target budget)
        mean_score = scores.mean()
        target_tensor = torch.tensor(self.target_budget, device=scores.device, dtype=scores.dtype)
        sparsity_loss = F.smooth_l1_loss(mean_score, target_tensor)

        # 3. Saliency Entropy Regularization (Prevents early bimodal collapse)
        eps = 1e-7
        clamped_scores = scores.clamp(min=eps, max=1.0 - eps)
        entropy = -(clamped_scores * torch.log(clamped_scores) + (1.0 - clamped_scores) * torch.log(1.0 - clamped_scores)).mean()
        entropy_loss = -entropy  # Minimize negative entropy to avoid over-confident spikes early

        # 4. Total Weighted Loss
        total_loss = ce_loss + self.lambda_sparsity * sparsity_loss + self.lambda_entropy * entropy_loss

        return {
            "loss": total_loss,
            "ce_loss": ce_loss,
            "sparsity_loss": sparsity_loss,
            "entropy_loss": entropy_loss,
            "mean_score": mean_score.detach()
        }
