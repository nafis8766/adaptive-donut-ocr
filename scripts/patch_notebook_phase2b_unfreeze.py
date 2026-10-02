"""Phase 2b patch for kaggle_token_pruning_ocr.ipynb.

Why: run 4 (SynthDoG-heavy mix, encoder FROZEN, 5 ep) REGRESSED FUNSD word
recall 53.86 -> 51.72 while train CE collapsed 0.40 -> 0.049. Same overfit
signature as run 3. Diagnosis: the bottleneck is NOT decoder-side data volume --
it is the FROZEN Swin encoder. Its features are fixed no matter what text we feed
the decoder, so the decoder memorizes train pairs (CE->0) but cannot read unseen
test glyphs. Adding clean synthetic text (SynthDoG) at 63% of the mix only pulled
priors off-domain and hurt.

Fix (this patch): unfreeze the TOP Swin stage + final encoder norm so the visual
features can ADAPT to FUNSD's degraded fax/scan glyphs, with a low encoder LR;
and rebalance the data back to FUNSD-heavy (SynthDoG demoted to a small
anti-overfit garnish). Eval cell is left UNTOUCHED so run 5 stays directly
comparable to runs 2/3/4 (FUNSD test x50, same metrics). Pruning still OFF.

Memory note: unfreezing only the tail is memory-safe. The frozen early stages
receive pixel_values (requires_grad=False) and emit non-grad outputs, so autograd
saves NO activations for them -- the graph (and its VRAM) begins only at the
unfrozen last stage, which runs on the small 4800-token final grid. The forward's
existing `encoder_is_frozen` check auto-detects the partial unfreeze and drops the
no_grad wrapper, so no model-class edit is needed.

Edits (asserted, exactly-once replacements):
  Cell 9  (data)     : SYNTH_N 2000 -> 500 (FUNSD ~70% of the mix again).
  Cell 11 (training) : unfreeze top Swin stage + final norm after instantiation;
                       add encoder param group at lr 1e-5 (router 1e-4 / dec 2e-5
                       unchanged); honest VRAM print.
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
c = sub(c,
r"""# Phase 2-data: FUNSD (149 imgs) is data-starved and augmentation plateaued, so
# mix in SynthDoG-en (Donut's native full-text OCR corpus) to teach robust glyph
# reading. FUNSD is oversampled + augmented so form competence is preserved;
# SynthDoG is a parquet slice, so only the first shard(s) download on Kaggle.
SYNTH_N, FUNSD_REPEAT = 2000, 8""",
r"""# Phase 2b: the SynthDoG-heavy mix (run 4: 63% synth, encoder frozen) REGRESSED
# recall -- clean synthetic text is off-domain for FUNSD's noisy scans, and a
# frozen encoder cannot adapt to it anyway. Now that the top Swin stage is
# unfrozen (see training cell) the encoder can learn FUNSD glyphs directly, so
# SynthDoG is demoted to a small anti-overfit garnish and FUNSD dominates (~70%).
SYNTH_N, FUNSD_REPEAT = 500, 8""", "c9-mix-rebalance")
put(9, c)

# --------------------------- Cell 11: training ---------------------------
c = get(11)

# 11a: unfreeze the top Swin stage + final encoder norm, right after the model is
# built. Frozen prefix -> non-grad outputs -> no saved activations, so the full
# encoder can run without no_grad and VRAM stays modest (see module docstring).
c = sub(c,
r"""# Phase 1: pruning OFF (keep all tokens) to establish the accuracy ceiling.
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)""",
r"""# Phase 1: pruning OFF (keep all tokens) to establish the accuracy ceiling.
model = AdaptiveDonutOCR(keep_ratio=1.0, merge_ratio=0.0, freeze_encoder=True).to(device)

# Phase 2b: unfreeze the top Swin stage (+ final encoder norm where present) so
# the visual features can ADAPT to FUNSD's degraded fax/scan glyphs -- the
# bottleneck that decoder-side data (runs 3-4) could not move. The frozen early
# stages emit non-grad outputs, so autograd builds no graph for them; only the
# unfrozen tail (on the small 4800-token final grid) costs memory. forward()'s
# encoder_is_frozen check then auto-runs the encoder WITH grad -- no model-class
# change required. NOTE: DonutSwinModel.layernorm exists on transformers 4.x
# (Kaggle) but was folded away by 5.x, so unfreeze it defensively via getattr.
UNFREEZE_STAGES = 1
_swin_stages = model.model.encoder.encoder.layers
assert len(_swin_stages) >= UNFREEZE_STAGES, f'unexpected Swin structure: {len(_swin_stages)} stages'
for _stage in _swin_stages[-UNFREEZE_STAGES:]:
    for _p in _stage.parameters():
        _p.requires_grad = True
_final_norm = getattr(model.model.encoder, 'layernorm', None)
if _final_norm is not None:
    for _p in _final_norm.parameters():
        _p.requires_grad = True
_enc_trainable = sum(p.numel() for p in model.model.encoder.parameters() if p.requires_grad)
print(f'Unfroze top {UNFREEZE_STAGES} Swin stage(s){" + final norm" if _final_norm is not None else ""}: {_enc_trainable/1e6:.1f}M encoder params trainable')""",
"c11-unfreeze")

# 11b: add the unfrozen encoder tail as a third optimizer group at a low LR.
c = sub(c,
r"""# Train Router and Text Decoder
trainable_params = [
    {'params': model.router.parameters(), 'lr': 1e-4},
    {'params': model.model.decoder.parameters(), 'lr': 2e-5}
]
optimizer = torch.optim.AdamW(trainable_params, weight_decay=0.01)""",
r"""# Train Router, Text Decoder, and the newly-unfrozen Swin tail. Discriminative
# LRs: router (fresh head) fastest; decoder mid; encoder slowest (1e-5) since
# pretrained Swin features are delicate and a high LR would wreck them.
_enc_trainable_params = [p for p in model.model.encoder.parameters() if p.requires_grad]
trainable_params = [
    {'params': model.router.parameters(), 'lr': 1e-4},
    {'params': model.model.decoder.parameters(), 'lr': 2e-5},
    {'params': _enc_trainable_params, 'lr': 1e-5}
]
optimizer = torch.optim.AdamW(trainable_params, weight_decay=0.01)""",
"c11-optimizer")

# 11c: the old "< 2.0 GB" banner is no longer true with a trainable encoder tail.
c = sub(c,
r"""print('Starting Training (VRAM usage is < 2.0 GB)...')""",
r"""print('Starting Training (partial encoder fine-tune; VRAM ~3-5 GB on T4)...')""",
"c11-vram-print")
put(11, c)

json.dump(nb, open(NB, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("OK: notebook patched for Phase 2b unfreeze (cells 9, 11); all edited cells parse as valid Python.")
