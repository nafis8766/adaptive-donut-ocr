import json
import torch
from torch.utils.data import Dataset
from typing import Dict, Any, Optional, List
from datasets import load_dataset
from PIL import Image


# Phase 1.5 augmentation (TRAIN split only). Mild, document-safe jitter to fight
# overfit on the small FUNSD train set; mirrors the DOC_AUG in the Kaggle
# notebook. No flips/crops (they destroy or drop text). Guarded so importing this
# module never hard-fails if torchvision's transform API differs.
try:
    from torchvision import transforms as _T
    DOC_AUG = _T.Compose([
        _T.RandomApply([_T.RandomRotation(degrees=2, fill=255)], p=0.5),
        _T.ColorJitter(brightness=0.2, contrast=0.2),
        _T.RandomApply([_T.RandomAffine(degrees=0, scale=(0.9, 1.05), fill=255)], p=0.3),
        _T.RandomApply([_T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5))], p=0.3),
    ])
except Exception:  # torchvision missing or API mismatch -> augmentation disabled
    DOC_AUG = None


# Cap on words per target. FUNSD forms run to ~220 words; 128 covers the vast
# majority while keeping the tokenized target under max_length=512.
MAX_TARGET_WORDS = 128


def reading_order_words(words: List[str], bboxes: List[List[float]]) -> List[str]:
    """Return ``words`` sorted into natural reading order (top-to-bottom, then
    left-to-right) using their bounding boxes ``[x0, y0, x1, y1]``.

    FUNSD stores words in form-entity annotation order, NOT reading order, so a
    target built by naively joining ``words`` is scrambled. The decoder can
    neither learn nor be scored on sequence against a scrambled target. We
    recover reading order by clustering boxes into text lines (rows whose top
    edge falls within a tolerance scaled to the median glyph height) and reading
    each line left-to-right.
    """
    if not bboxes or len(bboxes) != len(words):
        return list(words)

    heights = sorted(b[3] - b[1] for b in bboxes if b[3] > b[1])
    line_tol = max(1.0, (heights[len(heights) // 2] * 0.6) if heights else 10.0)

    lines: List[tuple] = []  # (anchor_top, [indices])
    for i in sorted(range(len(words)), key=lambda k: bboxes[k][1]):
        top = bboxes[i][1]
        for anchor_top, idxs in lines:
            if abs(top - anchor_top) <= line_tol:
                idxs.append(i)
                break
        else:
            lines.append((top, [i]))

    ordered: List[int] = []
    for _, idxs in lines:
        ordered.extend(sorted(idxs, key=lambda k: bboxes[k][0]))
    return [words[i] for i in ordered]


class SROIEDonutDataset(Dataset):
    """
    PyTorch Dataset wrapper for English document datasets (FUNSD / SROIE / CORD)
    formatted for Donut Vision-Decoder architecture.
    """
    def __init__(
        self,
        dataset_name: str = "nielsr/funsd",
        split: str = "train",
        processor: Any = None,
        max_length: int = 512,
        task_prompt: str = "<s_doc>",
        max_samples: Optional[int] = None,
        augment: bool = False
    ):
        super().__init__()
        self.processor = processor
        self.max_length = max_length
        self.task_prompt = task_prompt
        self.augment = augment
        
        # Load dataset from Hugging Face
        print(f"Loading {dataset_name} ({split} split) from Hugging Face...")
        raw_ds = load_dataset(dataset_name, split=split)
        
        if max_samples is not None and max_samples < len(raw_ds):
            raw_ds = raw_ds.select(range(max_samples))
            
        self.dataset = raw_ds
        print(f"Loaded {len(self.dataset)} samples for {split} split.")

    def __len__(self) -> int:
        return len(self.dataset)

    def _format_target_json(self, sample: Dict[str, Any]) -> str:
        """Converts key-value fields or words into a compact JSON string target."""
        if "words" in sample:
            words = sample.get("words", [])
            # FUNSD word order is form-annotation order, not reading order.
            # Re-sort by bounding box so the target is a coherent, ordered
            # transcription the decoder can actually learn and be scored on.
            boxes = sample.get("bboxes") or sample.get("boxes") or sample.get("bbox")
            if boxes:
                words = reading_order_words(words, boxes)
            target_dict = {"text": " ".join(words[:MAX_TARGET_WORDS])}
        elif "company" in sample or "total" in sample:
            target_dict = {
                "company": str(sample.get("company", "")).strip(),
                "date": str(sample.get("date", "")).strip(),
                "address": str(sample.get("address", "")).strip(),
                "total": str(sample.get("total", "")).strip()
            }
        elif "ground_truth" in sample:
            # SynthDoG-en: ground_truth is a JSON string
            # {"gt_parse": {"text_sequence": "..."}}. Normalize into the SAME
            # {"text": ...} schema as FUNSD (whitespace-split, 128-word cap) so
            # the decoder learns ONE output schema across mixed data sources.
            gt = sample["ground_truth"]
            try:
                gt_obj = json.loads(gt) if isinstance(gt, str) else gt
                parse = gt_obj.get("gt_parse", gt_obj) if isinstance(gt_obj, dict) else {}
                seq = parse.get("text_sequence", "") if isinstance(parse, dict) else str(parse)
            except Exception:
                seq = gt if isinstance(gt, str) else ""
            target_dict = {"text": " ".join(seq.split()[:MAX_TARGET_WORDS])}
        else:
            target_dict = {"text": "sample document"}
            
        return json.dumps(target_dict, ensure_ascii=False)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        sample = self.dataset[idx]
        
        # 1. Load image
        img: Image.Image = sample["image"].convert("RGB")

        # 1b. Optional train-time augmentation (off for eval/inference)
        if self.augment and DOC_AUG is not None:
            img = DOC_AUG(img)

        # 2. Process image with Donut processor
        pixel_values = self.processor(img, return_tensors="pt").pixel_values.squeeze(0)  # (3, H, W)
        
        # 3. Format ground truth text
        target_text = self._format_target_json(sample)
        full_target_str = f"{self.task_prompt}{target_text}</s>"
        
        # 4. Tokenize target text for decoder
        labels = self.processor.tokenizer(
            full_target_str,
            add_special_tokens=False,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        ).input_ids.squeeze(0)
        
        # Set padding tokens to -100 to ignore in Cross-Entropy Loss
        labels[labels == self.processor.tokenizer.pad_token_id] = -100

        # Decoder input = the full target sequence (NOT shifted here). The model's
        # forward() applies the right-shift when computing the loss, so position t
        # predicts token t+1. Do not pre-shift, or you double-shift the sequence.
        decoder_input_ids = labels.clone()
        decoder_input_ids[decoder_input_ids == -100] = self.processor.tokenizer.pad_token_id

        return {
            "pixel_values": pixel_values,
            "labels": labels,
            "decoder_input_ids": decoder_input_ids,
            "raw_text": target_text
        }


def create_donut_data_collator(pad_token_id: int = 1):
    """
    Data collator for batching document OCR samples.
    """
    def collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        pixel_values = torch.stack([item["pixel_values"] for item in batch], dim=0)
        labels = torch.stack([item["labels"] for item in batch], dim=0)
        decoder_input_ids = torch.stack([item["decoder_input_ids"] for item in batch], dim=0)
        
        return {
            "pixel_values": pixel_values,
            "labels": labels,
            "decoder_input_ids": decoder_input_ids
        }
    return collate_fn
