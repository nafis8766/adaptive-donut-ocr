"""
Adaptive Visual Token Pruning Engine for Low-Token Document OCR
"""
from .router import PatchSaliencyRouter
from .tome import BipartiteTokenMerger
from .loss import AdaptivePruningLoss

__all__ = [
    "PatchSaliencyRouter",
    "BipartiteTokenMerger",
    "AdaptivePruningLoss",
]

try:
    from .model import AdaptiveDonutOCR
    __all__.append("AdaptiveDonutOCR")
except ImportError:
    pass

try:
    from .dataset import SROIEDonutDataset, create_donut_data_collator
    __all__.extend(["SROIEDonutDataset", "create_donut_data_collator"])
except ImportError:
    pass
