"""Phase-1.5 patch for kaggle_token_pruning_ocr.ipynb.

Goal: lift the accuracy ceiling by fighting the 149-image overfit, with as few
moving parts as possible so the result is attributable.

Edits (asserted, exactly-once replacements):
  Cell 9  (data)     : add torchvision DOC_AUG; augment flag on DocumentDataset;
                       apply aug on TRAIN only; train_ds augment=True
  Cell 11 (training) : EPOCHS 30 -> 40 (augmented data is harder to fit)
  Cell 13 (eval)     : evaluate on ALL 50 test samples (was 20) for stable metrics

Unchanged on purpose: pruning still OFF, MAX_WORDS=128, max_length=512.
"""
import json, ast

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
nb = json.load(open(NB, encoding="utf-8"))


def sub(text, old, new, label):
    n = text.count(old)
    assert n == 1, f"[{label}] expected 1 match, found {n}"
    return text.replace(old, new)


def get(i):
    return "".join(nb["cells"][i]["source"])


def put(i, text):
    ast.parse(text)  # guard: edited cell must still be valid Python
    nb["cells"][i]["source"] = text.splitlines(keepends=True)


# ----------------------------- Cell 9: data -----------------------------
c = get(9)

c = sub(c, r"""# Cell 6: Data Pipeline
MAX_WORDS = 128""", r"""# Cell 6: Data Pipeline
from torchvision import transforms as T

MAX_WORDS = 128

# Phase 1.5: document-appropriate augmentation (TRAIN split only) to fight the
# 149-image overfit. Mild geometric + photometric jitter only -- NO flips or
# aggressive crops, which would destroy or drop text. fill=255 keeps the paper
# background white where rotation/scale expose the corners.
DOC_AUG = T.Compose([
    T.RandomApply([T.RandomRotation(degrees=2, fill=255)], p=0.5),
    T.ColorJitter(brightness=0.2, contrast=0.2),
    T.RandomApply([T.RandomAffine(degrees=0, scale=(0.9, 1.05), fill=255)], p=0.3),
    T.RandomApply([T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5))], p=0.3),
])""", "c9-aug-def")

c = sub(c,
r"""    def __init__(self, dataset_name='nielsr/funsd', split='train', processor=None, max_samples=None):
        self.processor = processor
        raw = load_dataset(dataset_name, split=split)""",
r"""    def __init__(self, dataset_name='nielsr/funsd', split='train', processor=None, max_samples=None, augment=False):
        self.processor = processor
        self.augment = augment
        raw = load_dataset(dataset_name, split=split)""", "c9-init")

c = sub(c,
r"""        img = sample['image'].convert('RGB')
        pixel_values = self.processor(img, return_tensors='pt').pixel_values.squeeze(0)""",
r"""        img = sample['image'].convert('RGB')
        if self.augment:
            img = DOC_AUG(img)
        pixel_values = self.processor(img, return_tensors='pt').pixel_values.squeeze(0)""", "c9-apply")

c = sub(c,
r"""train_ds = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor)""",
r"""train_ds = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor, augment=True)""", "c9-trainds")
put(9, c)

# --------------------------- Cell 11: training ---------------------------
c = get(11)
c = sub(c, r"""EPOCHS = 30""", r"""EPOCHS = 40""", "c11-epochs")
put(11, c)

# ----------------------------- Cell 13: eval -----------------------------
c = get(13)
c = sub(c,
r"""test_raw = load_dataset('nielsr/funsd', split='test').select(range(20))""",
r"""test_raw = load_dataset('nielsr/funsd', split='test')  # all 50 test samples for stable metrics""", "c13-eval50")
put(13, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: notebook patched for Phase 1.5 (cells 9, 11, 13); all edited cells parse as valid Python.")
