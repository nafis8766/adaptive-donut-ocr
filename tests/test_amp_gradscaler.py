import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
import torch.nn as nn
from src.router import PatchSaliencyRouter
from src.loss import AdaptivePruningLoss

def test_amp_scaling():
    device = torch.device("cpu")
    router = PatchSaliencyRouter(hidden_dim=64, reduction_dim=32).to(device)
    decoder_sim = nn.Linear(64, 100).to(device)
    
    optimizer = torch.optim.AdamW(list(router.parameters()) + list(decoder_sim.parameters()), lr=1e-3)
    scaler = torch.amp.GradScaler('cpu')
    criterion = AdaptivePruningLoss(target_budget=0.25)
    
    tokens = torch.randn(2, 20, 64, device=device) # simulated frozen encoder output
    labels = torch.randint(0, 100, (2, 7), device=device)
    
    optimizer.zero_grad()
    with torch.amp.autocast('cpu'):
        selected, scores, _, _ = router(tokens, keep_ratio=0.35, use_ste=True)
        logits = decoder_sim(selected) # (2, 7, 100)
        loss_dict = criterion(logits, labels, scores)
        loss = loss_dict['loss']
        
    scaler.scale(loss).backward()
    scaler.unscale_(optimizer)
    torch.nn.utils.clip_grad_norm_(list(router.parameters()) + list(decoder_sim.parameters()), max_norm=1.0)
    scaler.step(optimizer)
    scaler.update()
    
    print("AMP GradScaler Step completed with 0 errors!")

if __name__ == "__main__":
    test_amp_scaling()
