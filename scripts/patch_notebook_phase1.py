"""Phase-1 patch for kaggle_token_pruning_ocr.ipynb.

Edits (asserted, exactly-once replacements):
  Cell 9  (data)     : add reading_order_words + MAX_WORDS; reading-order target; max_length 256->512
  Cell 11 (training) : pruning OFF (keep_ratio=1.0, merge_ratio=0.0, sparsity=0.0), EPOCHS 5->30
  Cell 13 (eval)     : reading-order GT; word recall + word-order metrics; max_length 256->512
  Cell 14 (zip)      : add word_recall_pct + word_order_pct to metrics.json
All replacement text is raw so literal \n and \w survive into the notebook source.
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
    ast.parse(text)  # guard: the edited cell must still be valid Python
    nb["cells"][i]["source"] = text.splitlines(keepends=True)


# ----------------------------- Cell 9: data -----------------------------
c = get(9)
c = sub(c, r"""class DocumentDataset(Dataset):""", r"""MAX_WORDS = 128


def reading_order_words(words, bboxes):
    """ + '"""' + r"""Sort words top-to-bottom, left-to-right using boxes [x0,y0,x1,y1].
    FUNSD stores words in form-annotation order, not reading order, so a naive
    join yields a scrambled target the decoder cannot learn or be scored on.""" + '"""' + r"""
    if not bboxes or len(bboxes) != len(words):
        return list(words)
    hs = sorted(b[3] - b[1] for b in bboxes if b[3] > b[1])
    tol = max(1.0, (hs[len(hs) // 2] * 0.6) if hs else 10.0)
    lines = []
    for i in sorted(range(len(words)), key=lambda k: bboxes[k][1]):
        top = bboxes[i][1]
        for anchor, idxs in lines:
            if abs(top - anchor) <= tol:
                idxs.append(i)
                break
        else:
            lines.append((top, [i]))
    out = []
    for _, idxs in lines:
        out.extend(sorted(idxs, key=lambda k: bboxes[k][0]))
    return [words[i] for i in out]


class DocumentDataset(Dataset):""", "c9-helper")

c = sub(c,
r"""        words = sample.get('words', ['sample', 'document'])
        target_json = json.dumps({'text': ' '.join(words[:40])})""",
r"""        words = sample.get('words', ['sample', 'document'])
        boxes = sample.get('bboxes') or sample.get('boxes')
        if boxes:
            words = reading_order_words(words, boxes)
        target_json = json.dumps({'text': ' '.join(words[:MAX_WORDS])})""", "c9-target")

c = sub(c, r"""max_length=256, padding='max_length'""",
           r"""max_length=512, padding='max_length'""", "c9-maxlen")
put(9, c)

# --------------------------- Cell 11: training ---------------------------
c = get(11)
c = sub(c,
r"""model = AdaptiveDonutOCR(keep_ratio=0.35, merge_ratio=0.20, freeze_encoder=True).to(device)""",
r"""# Phase 1: pruning OFF (keep all tokens) to establish the accuracy ceiling.
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)""", "c11-model")

c = sub(c,
r"""criterion = AdaptivePruningLoss(lambda_sparsity=2.0, target_budget=0.25, pad_token_id=processor.tokenizer.pad_token_id)""",
r"""# lambda_sparsity=0.0 -> no token-budget pressure this phase (accuracy first)
criterion = AdaptivePruningLoss(lambda_sparsity=0.0, target_budget=1.0, pad_token_id=processor.tokenizer.pad_token_id)""", "c11-loss")

c = sub(c, r"""EPOCHS = 5""", r"""EPOCHS = 30""", "c11-epochs")
put(11, c)

# ----------------------------- Cell 13: eval -----------------------------
c = get(13)
c = sub(c, r"""def compute_ned(pred, target):""",
r"""def compute_word_metrics(pred, gt_words):
    import re
    pw = re.findall(r'\w+', pred.lower())
    gold = [w.lower() for w in gt_words]
    gs = set(gold)
    recall = len(gs & set(pw)) / len(gs) if gs else 0.0
    try:
        import editdistance
        d = editdistance.eval(pw, gold)
    except Exception:
        d = abs(len(pw) - len(gold))
    order = max(0.0, 1.0 - d / max(len(pw), len(gold), 1))
    return recall, order


def compute_ned(pred, target):""", "c13-wordmetrics")

c = sub(c, r"""neds, latencies, compression_ratios = [], [], []""",
           r"""neds, latencies, compression_ratios = [], [], []
recalls, word_orders = [], []""", "c13-lists")

c = sub(c,
r"""    words = sample.get('words', [])
    gt_str = json.dumps({'text': ' '.join(words[:40])})""",
r"""    words = sample.get('words', [])
    boxes = sample.get('bboxes') or sample.get('boxes')
    gt_words = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
    gt_str = json.dumps({'text': ' '.join(gt_words)})""", "c13-gt")

c = sub(c, r"""gen_ids, meta = model.generate(pixel_values, decoder_input_ids=prompt_ids, max_length=256)""",
           r"""gen_ids, meta = model.generate(pixel_values, decoder_input_ids=prompt_ids, max_length=512)""", "c13-maxlen")

c = sub(c,
r"""    neds.append(compute_ned(pred, gt_str))
    compression_ratios.append(meta['compression_ratio'])""",
r"""    neds.append(compute_ned(pred, gt_str))
    rec, order = compute_word_metrics(pred, gt_words)
    recalls.append(rec)
    word_orders.append(order)
    compression_ratios.append(meta['compression_ratio'])""", "c13-append")

c = sub(c,
r"""print('\n' + '='*45)
print(f'Mean Normalized Edit Distance: {np.mean(neds):.4f}')
print(f'Character Accuracy:           {(1.0 - np.mean(neds))*100:.2f}%')
print(f'Average Visual Token Savings:  {np.mean(compression_ratios):.1f}%')
print(f'Average Inference Latency:     {np.mean(latencies):.1f} ms/doc')
print('='*45)""",
r"""print('\n' + '='*52)
print(f'[Stage 1] Word Recall (no missing words): {np.mean(recalls)*100:.2f}%')
print(f'[Stage 2] Character Accuracy:             {(1.0 - np.mean(neds))*100:.2f}%')
print(f'[Stage 3] Word-Order / Sequence Score:    {np.mean(word_orders)*100:.2f}%')
print(f'Mean Normalized Edit Distance (NED):      {np.mean(neds):.4f}')
print(f'Average Visual Token Savings:             {np.mean(compression_ratios):.1f}%')
print(f'Average Inference Latency:                {np.mean(latencies):.1f} ms/doc')
print('='*52)""", "c13-print")
put(13, c)

# ------------------------------ Cell 14: zip ------------------------------
c = get(14)
c = sub(c,
r"""    metrics = {
        'mean_ned': float(np.mean(neds)),
        'character_accuracy_pct': float((1.0 - np.mean(neds)) * 100.0),
        'avg_token_savings_pct': float(np.mean(compression_ratios)),
        'avg_latency_ms': float(np.mean(latencies)),
        'num_eval_samples': len(neds),
    }""",
r"""    metrics = {
        'word_recall_pct': float(np.mean(recalls) * 100.0),
        'character_accuracy_pct': float((1.0 - np.mean(neds)) * 100.0),
        'word_order_pct': float(np.mean(word_orders) * 100.0),
        'mean_ned': float(np.mean(neds)),
        'avg_token_savings_pct': float(np.mean(compression_ratios)),
        'avg_latency_ms': float(np.mean(latencies)),
        'num_eval_samples': len(neds),
    }""", "c14-metrics")
put(14, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: notebook patched (cells 9, 11, 13, 14); all edited cells parse as valid Python.")
