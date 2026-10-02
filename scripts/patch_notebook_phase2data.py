"""Phase 2-data patch for kaggle_token_pruning_ocr.ipynb.

Goal: break the 149-image FUNSD ceiling (recall plateaued at ~54% through
Phase 1.5) by mixing in SynthDoG-en -- Donut's native full-text OCR corpus --
so the decoder re-learns robust glyph reading instead of memorizing 149 forms.

Edits (asserted, exactly-once replacements):
  Cell 9  (data)     : add build_target_text() (unifies FUNSD words + SynthDoG
                       gt_parse.text_sequence into ONE {"text": ...} schema);
                       __getitem__ uses it; train_ds = ConcatDataset of
                       oversampled+augmented FUNSD and a SynthDoG parquet slice.
  Cell 11 (training) : EPOCHS 40 -> 5 (mix is ~3192 samples/epoch, not 149).

Unchanged on purpose: eval cell (still FUNSD test x50, same metrics -> run 4 is
directly comparable to runs 2/3); pruning OFF; MAX_WORDS=128; max_length=512; LRs.
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

# 9a: unified target builder + ConcatDataset import, inserted above the class.
c = sub(c, r"""class DocumentDataset(Dataset):""", r"""from torch.utils.data import ConcatDataset


def build_target_text(sample):
    '''Unified target across mixed sources -> the words for {"text": ...}, capped
    at MAX_WORDS. FUNSD: reading-ordered words. SynthDoG-en: gt_parse.text_sequence.
    Keeps the decoder on ONE output schema.'''
    words = sample.get('words')
    if words:
        boxes = sample.get('bboxes') or sample.get('boxes')
        if boxes:
            words = reading_order_words(words, boxes)
        return ' '.join(words[:MAX_WORDS])
    gt = sample.get('ground_truth')
    if gt:
        try:
            obj = json.loads(gt) if isinstance(gt, str) else gt
            parse = obj.get('gt_parse', obj) if isinstance(obj, dict) else {}
            seq = parse.get('text_sequence', '') if isinstance(parse, dict) else str(parse)
        except Exception:
            seq = gt if isinstance(gt, str) else ''
        return ' '.join(seq.split()[:MAX_WORDS])
    return 'sample document'


class DocumentDataset(Dataset):""", "c9-builder")

# 9b: __getitem__ delegates target construction to build_target_text.
c = sub(c,
r"""        words = sample.get('words', ['sample', 'document'])
        boxes = sample.get('bboxes') or sample.get('boxes')
        if boxes:
            words = reading_order_words(words, boxes)
        target_json = json.dumps({'text': ' '.join(words[:MAX_WORDS])})
        prompt = f'<s_doc>{target_json}</s>'""",
r"""        target_json = json.dumps({'text': build_target_text(sample)})
        prompt = f'<s_doc>{target_json}</s>'""", "c9-getitem")

# 9c: mixed training set (oversampled+augmented FUNSD + SynthDoG-en slice).
c = sub(c,
r"""processor = DonutProcessor.from_pretrained('naver-clova-ix/donut-base')
train_ds = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor, augment=True)
test_ds = DocumentDataset(dataset_name='nielsr/funsd', split='test', processor=processor)""",
r"""processor = DonutProcessor.from_pretrained('naver-clova-ix/donut-base')

# Phase 2-data: FUNSD (149 imgs) is data-starved and augmentation plateaued, so
# mix in SynthDoG-en (Donut's native full-text OCR corpus) to teach robust glyph
# reading. FUNSD is oversampled + augmented so form competence is preserved;
# SynthDoG is a parquet slice, so only the first shard(s) download on Kaggle.
SYNTH_N, FUNSD_REPEAT = 2000, 8
funsd_train = DocumentDataset(dataset_name='nielsr/funsd', split='train', processor=processor, augment=True)
synth_train = DocumentDataset(dataset_name='naver-clova-ix/synthdog-en', split=f'train[:{SYNTH_N}]', processor=processor, augment=False)
train_ds = ConcatDataset([funsd_train] * FUNSD_REPEAT + [synth_train])
test_ds = DocumentDataset(dataset_name='nielsr/funsd', split='test', processor=processor)
print(f'Mixed train set: {len(funsd_train)} FUNSD x{FUNSD_REPEAT} + {len(synth_train)} SynthDoG = {len(train_ds)} samples')""", "c9-mix")
put(9, c)

# --------------------------- Cell 11: training ---------------------------
c = get(11)
c = sub(c, r"""EPOCHS = 40""", r"""EPOCHS = 5""", "c11-epochs")
put(11, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: notebook patched for Phase 2-data (cells 9, 11); all edited cells parse as valid Python.")
