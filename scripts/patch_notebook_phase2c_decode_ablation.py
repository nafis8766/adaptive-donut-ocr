"""Phase 2c patch: eval-only DECODING ABLATION for kaggle_token_pruning_ocr.ipynb.

Why: across runs 2-5 word recall fell monotonically (54.07 -> 50.56) while char
accuracy and word order ROSE monotonically (36.00 -> 40.97, 21.40 -> 26.49). Run-5
sample 0 shows the mechanism: it transcribes the opening accurately, then closes
the JSON and STOPS while the gold continues a full page. Words never emitted
cannot be recalled -- so the cap looks like UNDER-GENERATION, not misreading.

Prime suspect is a STALE decoding config in AdaptiveDonutOCR.generate():
`repetition_penalty=1.3` + `no_repeat_ngram_size=3`, which its own comment says
were tuned because "aggressive pruning makes greedy decoding prone to repetition
collapse". But runs 2-5 all set keep_ratio=1.0 -- pruning is OFF -- so that
justification no longer holds, and trigram blocking is actively wrong for
full-page forms that legitimately repeat trigrams (form labels, phone numbers,
dotted leaders): once every continuation is blocked, EOS becomes top-1.

This patch adds an eval-only ablation over the SAME weights (no retraining) plus
an optional resume path so the 4h train can be skipped entirely.

Edits (asserted, exactly-once replacements):
  Cell 11 (training) : RESUME_CKPT hook -> load an uploaded checkpoint and set
                       EPOCHS=0 (range(1,1) is empty, so the training loop body
                       never runs -- no re-indentation needed); guard the save so
                       eval-only mode does not rewrite an 800MB checkpoint.
  NEW cell before the zip cell: decoding ablation grid + metrics table, written
                       to ablation_decoding.json so the zip cell packages it.

Design points that make the result trustworthy:
  * The FIRST grid row is a CONTROL reproducing run 5's exact settings. If it does
    not return ~50.56/40.97/26.49 the harness differs from the run-5 eval and no
    other row can be believed. The cell prints that drift check explicitly.
  * Length is measured DIRECTLY (mean predicted vs gold word counts, generated
    token counts, % hitting max_length) instead of being inferred from recall,
    because under-generation is precisely the hypothesis under test.
  * valid_json_pct is reported as a DIAGNOSTIC only -- run 5 emitted malformed
    `{"text ` (missing `": `). We measure it; we do not repair predictions, which
    would be scoring the fix rather than the model.

Unchanged on purpose: the eval cell, its metrics, the FUNSD test x50 protocol,
MAX_WORDS=128, and pruning OFF -- so ablation rows stay comparable to runs 2-5.
"""
import ast
import json
import os
import shutil

NB = r"c:\Users\Nafis\Desktop\Project\kaggle_token_pruning_ocr.ipynb"
BAK = NB + ".bak-phase2c"

# Back up the PRE-patch notebook, but never clobber an existing backup (a second
# run would otherwise overwrite the good backup with an already-patched file).
if not os.path.exists(BAK):
    shutil.copyfile(NB, BAK)
    print(f"backup written: {os.path.basename(BAK)}")
else:
    print(f"backup already exists, left as-is: {os.path.basename(BAK)}")

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


# --------------------------- Cell 11: training ---------------------------
c = get(11)

c = sub(c,
r"""EPOCHS = 5
GRAD_ACCUM = 8  # Effective batch size = 8""",
r"""EPOCHS = 5
GRAD_ACCUM = 8  # Effective batch size = 8

# Phase 2c: eval-only resume. Point RESUME_CKPT at an uploaded checkpoint (Kaggle:
# "Add Input" -> your dataset holding run 5's adaptive_donut_funsd.pt) to SKIP the
# ~4h retrain and go straight to eval + the decoding ablation. Leave it None to
# train normally. EPOCHS=0 makes range(1, EPOCHS+1) empty, so the training loop
# body never executes -- no re-indentation of the loop required.
RESUME_CKPT = None  # e.g. '/kaggle/input/adaptive-donut-run5/adaptive_donut_funsd.pt'
if RESUME_CKPT:
    assert os.path.exists(RESUME_CKPT), f'RESUME_CKPT not found: {RESUME_CKPT}'
    _sd = torch.load(RESUME_CKPT, map_location=device, weights_only=True)
    _missing, _unexpected = model.load_state_dict(_sd, strict=False)
    assert not _unexpected, f'unexpected keys in checkpoint: {list(_unexpected)[:5]}'
    print(f'Loaded {RESUME_CKPT} (missing={len(_missing)}, unexpected={len(_unexpected)})')
    EPOCHS = 0
    print('EVAL-ONLY mode: training loop skipped (EPOCHS=0)')""",
"c11-resume")

c = sub(c,
r"""os.makedirs('/kaggle/working/checkpoints', exist_ok=True)
torch.save(model.state_dict(), '/kaggle/working/checkpoints/adaptive_donut_funsd.pt')
print('Saved model to /kaggle/working/checkpoints/adaptive_donut_funsd.pt')""",
r"""if EPOCHS > 0:
    os.makedirs('/kaggle/working/checkpoints', exist_ok=True)
    torch.save(model.state_dict(), '/kaggle/working/checkpoints/adaptive_donut_funsd.pt')
    print('Saved model to /kaggle/working/checkpoints/adaptive_donut_funsd.pt')
else:
    print('EVAL-ONLY mode: skipped checkpoint save (weights identical to RESUME_CKPT)')""",
"c11-save-guard")
put(11, c)


# ------------------- NEW cell: decoding ablation -------------------
ABLATION = r'''# Cell 8b: Decoding ablation (EVAL-ONLY -- no retraining)
# Tests whether the stale generation config, not the model, caps word recall.
# repetition_penalty=1.3 + no_repeat_ngram_size=3 were tuned for AGGRESSIVE
# pruning ("repetition collapse"), but runs 2-5 all run keep_ratio=1.0 (pruning
# OFF). On full-page forms, trigram blocking is actively harmful: real documents
# repeat trigrams (form labels, phone numbers, dotted leaders), and once every
# continuation is blocked EOS becomes top-1, so the model stops mid-document.
# Re-evaluates the SAME weights under several decoding configs.
import re

# Row 0 is a CONTROL: it uses run 5's exact settings and must reproduce run 5's
# numbers. If it does not, this harness differs from the eval cell and NO other
# row is trustworthy -- the drift check below prints that verdict.
RUN5_REFERENCE = (50.56, 40.97, 26.49)  # recall / charAcc / order, FUNSD test x50
ABLATION_MAX_LEN = 512

DECODE_CONFIGS = [
    ('baseline (run5)',   dict(repetition_penalty=1.3, no_repeat_ngram_size=3)),
    ('no ngram block',    dict(repetition_penalty=1.3, no_repeat_ngram_size=0)),
    ('no rep penalty',    dict(repetition_penalty=1.0, no_repeat_ngram_size=3)),
    ('both off',          dict(repetition_penalty=1.0, no_repeat_ngram_size=0)),
    ('both off + minlen', dict(repetition_penalty=1.0, no_repeat_ngram_size=0, min_new_tokens=64)),
]


def run_decode_eval(label, overrides):
    """Re-run the FUNSD test set under one decoding config.

    Metrics mirror the eval cell exactly (same compute_word_metrics / compute_ned
    / reading_order_words / MAX_WORDS) so rows stay comparable to runs 2-5. The
    added length fields test the under-generation hypothesis directly rather than
    inferring it from recall.
    """
    model.eval()
    recs, ords_, neds_ = [], [], []
    pred_words, gold_words, gen_tokens = [], [], []
    json_ok, hit_cap = 0, 0

    for sample in tqdm(test_raw, desc=label, leave=False):
        img = sample['image'].convert('RGB')
        pv = processor(img, return_tensors='pt').pixel_values.to(device)
        words = sample.get('words', [])
        boxes = sample.get('bboxes') or sample.get('boxes')
        gt_words = reading_order_words(words, boxes)[:MAX_WORDS] if boxes else words[:MAX_WORDS]
        gt_str = json.dumps({'text': ' '.join(gt_words)})

        with torch.no_grad():
            gen_ids, _meta = model.generate(
                pv, decoder_input_ids=prompt_ids,
                max_length=ABLATION_MAX_LEN, **overrides
            )

        n_tok = int(gen_ids.shape[-1])
        gen_tokens.append(n_tok)
        if n_tok >= ABLATION_MAX_LEN:
            hit_cap += 1   # ran to the cap instead of emitting EOS

        pred = processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        if pred.startswith(TASK_PROMPT):
            pred = pred[len(TASK_PROMPT):]
        pred = pred.strip()

        # diagnostic only -- we never repair pred, that would score the fix
        try:
            json.loads(pred)
            json_ok += 1
        except Exception:
            pass

        r, o = compute_word_metrics(pred, gt_words)
        recs.append(r)
        ords_.append(o)
        neds_.append(compute_ned(pred, gt_str))
        pred_words.append(len(re.findall(r'\w+', pred.lower())))
        gold_words.append(len(re.findall(r'\w+', ' '.join(gt_words).lower())))

    n = max(len(recs), 1)
    mp, mg = float(np.mean(pred_words)), float(np.mean(gold_words))
    return {
        'config': label,
        'overrides': {k: v for k, v in overrides.items()},
        'word_recall_pct': float(np.mean(recs) * 100.0),
        'character_accuracy_pct': float((1.0 - np.mean(neds_)) * 100.0),
        'word_order_pct': float(np.mean(ords_) * 100.0),
        'mean_ned': float(np.mean(neds_)),
        'mean_pred_words': mp,
        'mean_gold_words': mg,
        'len_ratio_pct': 100.0 * mp / max(mg, 1e-9),
        'mean_gen_tokens': float(np.mean(gen_tokens)),
        'hit_max_length_pct': 100.0 * hit_cap / n,
        'valid_json_pct': 100.0 * json_ok / n,
        'num_eval_samples': len(recs),
    }


rows = []
for _name, _cfg in DECODE_CONFIGS:
    print(f'--- decoding: {_name}  {_cfg}')
    rows.append(run_decode_eval(_name, _cfg))

hdr = (f"{'config':20s} {'recall':>7s} {'charAcc':>8s} {'order':>7s} {'NED':>6s} "
       f"{'predW':>6s} {'goldW':>6s} {'len%':>6s} {'cap%':>5s} {'json%':>6s}")
print('\n' + '=' * len(hdr))
print(hdr)
print('-' * len(hdr))
for r in rows:
    print(f"{r['config']:20s} {r['word_recall_pct']:7.2f} {r['character_accuracy_pct']:8.2f} "
          f"{r['word_order_pct']:7.2f} {r['mean_ned']:6.3f} {r['mean_pred_words']:6.1f} "
          f"{r['mean_gold_words']:6.1f} {r['len_ratio_pct']:6.1f} "
          f"{r['hit_max_length_pct']:5.0f} {r['valid_json_pct']:6.1f}")
print('=' * len(hdr))

# --- CONTROL: does the baseline row reproduce run 5? ---
base = rows[0]
got = (base['word_recall_pct'], base['character_accuracy_pct'], base['word_order_pct'])
drift = max(abs(g - e) for g, e in zip(got, RUN5_REFERENCE))
print(f"\nCONTROL vs run 5 {RUN5_REFERENCE}")
print(f"  baseline got  ({got[0]:.2f}, {got[1]:.2f}, {got[2]:.2f})   max drift {drift:.2f} pts")
if drift < 0.5:
    print('  OK - harness reproduces run 5, so the other rows are comparable.')
else:
    print('  WARNING - harness does NOT match the run-5 eval (different weights, '
          'sampling, or transformers version). Treat other rows as suspect.')

# --- did loosening the decoder actually lengthen the output? ---
best = max(rows, key=lambda r: r['word_recall_pct'])
print(f"\nBest recall: '{best['config']}' at {best['word_recall_pct']:.2f}% "
      f"({best['word_recall_pct'] - base['word_recall_pct']:+.2f} vs baseline)")
print(f"  words emitted: {best['mean_pred_words']:.1f} vs baseline "
      f"{base['mean_pred_words']:.1f} (gold {base['mean_gold_words']:.1f})")
if best['config'] != base['config'] and best['mean_pred_words'] > base['mean_pred_words']:
    print('  => recall rose TOGETHER WITH length: under-generation was the cap.')
    print('     Re-run the Phase 2 pruning sweep with this config, not the stale one.')
elif best['config'] == base['config']:
    print('  => no config beat the baseline: the cap is NOT decoding. Look at the')
    print('     128-word target cap / encoder capacity instead (UNFREEZE_STAGES=2).')
else:
    print('  => recall rose WITHOUT more words: gain is fidelity, not coverage.')

with open('/kaggle/working/ablation_decoding.json', 'w') as f:
    json.dump(rows, f, indent=2)
print('\nWrote /kaggle/working/ablation_decoding.json')
'''

ast.parse(ABLATION)  # guard: new cell must be valid Python before insertion

# Self-locate the zip cell rather than hardcoding an index, and insert the
# ablation just before it so its JSON gets packaged into the results archive.
zip_idx = next(i for i, cell in enumerate(nb["cells"])
               if "ZIP_PATH" in "".join(cell["source"]))
assert not any("DECODE_CONFIGS" in "".join(cell["source"]) for cell in nb["cells"]), \
    "ablation cell already present -- restore from .bak-phase2c before re-patching"

# Mirror an existing code cell's key structure so nbformat stays consistent.
donor = nb["cells"][zip_idx]
new_cell = {"cell_type": "code", "metadata": {}, "outputs": [], "execution_count": None,
            "source": ABLATION.splitlines(keepends=True)}
if "id" in donor:
    new_cell["id"] = "decoding-ablation"
nb["cells"].insert(zip_idx, new_cell)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"OK: patched cell 11 (resume + save guard) and inserted the decoding "
      f"ablation at index {zip_idx} (zip cell moved to {zip_idx + 1}); "
      f"all edited/new cells parse as valid Python.")
