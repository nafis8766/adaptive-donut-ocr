"""
Decisive diagnostic: is the checkpoint actually able to predict the NEXT token,
or was it trained (buggily) to COPY the current token?

Also replicates the Kaggle generation path vs the infer.py prompted path so we can
see the real generated text (not just an aggregate NED number).

LEGACY (kept for provenance): the question above was settled before run 6 — the
right-shift fix is in `src/model.py:237-244` and the decoding artifact that dominated
the remaining gap was found in run 6. Re-run this only to re-check a *new* checkpoint
for the copy failure mode.

Path note (2026-08-31): this hard-coded `pruned_ocr_results/checkpoints/...`, a
directory that has not existed since the Kaggle outputs were moved in under
per-run names. It therefore failed with a bare FileNotFoundError rather than saying
what it wanted. Now it searches the known layouts and reports every path it tried.

Path note (2026-09-06, Pending 12): `results_2/` and `results_3/` are now `run 7/` and
`run 8/`, so the first two candidates were dead paths. Fixed -- and while fixing them,
`run 9/` and `run 10/` were **missing entirely** from a list whose whole contract is
"newest-run-first". An unqualified invocation had been silently diagnosing run 8 for five
days while claiming to diagnose the newest weights: a resolver that falls through to an
older path is worse than one that fails, because it answers the question about the wrong
checkpoint. Both are now listed ahead of run 8.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import torch
from transformers import DonutProcessor
from datasets import load_dataset
from src.model import AdaptiveDonutOCR

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Newest-run-first so an unqualified invocation diagnoses the most recent weights.
# Override with: python scripts/diagnose_decoder.py <path-to-.pt>
CKPT_CANDIDATES = (
    "run 10/adaptive_donut_pruned.pt",              # run 10 (13(b) attention target)
    "run 9/adaptive_donut_pruned.pt",               # run 9  (F1 loss fix + F2 harness control)
    "run 8/adaptive_donut_pruned.pt",               # run 8  (sign-fix + ink-BCE)
    "run 7/adaptive_donut_pruned.pt",               # run 7  (pruning-ON retrain)
    "run 5/checkpoints/adaptive_donut_funsd.pt",    # run 5 -- the run-6 ceiling weights
    "pruned_ocr_results_3/checkpoints/adaptive_donut_funsd.pt",
    "pruned_ocr_results_2/checkpoints/adaptive_donut_funsd.pt",
    "pruned_ocr_results-4/checkpoints/adaptive_donut_funsd.pt",
    # Intentionally-absent last resort, kept only so the "tried these" report names it.
    # scripts/_final_check.py skips literals on a line marked ALLOW-MISSING.
    "pruned_ocr_results/checkpoints/adaptive_donut_funsd.pt",   # ALLOW-MISSING: the original
)


def resolve_ckpt(argv):
    if len(argv) > 1:
        p = argv[1]
        if not os.path.exists(p):
            raise SystemExit(f"checkpoint not found: {p}")
        return p
    tried = []
    for rel in CKPT_CANDIDATES:
        p = os.path.join(ROOT, rel)
        tried.append(p)
        if os.path.exists(p):
            print(f"checkpoint: {rel}  ({os.path.getsize(p) / 1e6:.0f} MB)")
            return p
    raise SystemExit(
        "no checkpoint found. Tried:\n  " + "\n  ".join(tried)
        + "\nPass one explicitly: python scripts/diagnose_decoder.py <path-to-.pt>")


CKPT = None   # resolved in main(), so importing this module never touches the disk


def main():
    global CKPT
    CKPT = resolve_ckpt(sys.argv)
    import transformers
    print(f"transformers version: {transformers.__version__}")

    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    tok = processor.tokenizer

    # ---- Section A: tokenizer / config facts ----
    print("\n===== A. TOKENIZER / CONFIG FACTS =====")
    sdoc_ids = tok("<s_doc>", add_special_tokens=False).input_ids
    print(f"'<s_doc>' -> ids {sdoc_ids} -> re-decoded {tok.convert_ids_to_tokens(sdoc_ids)!r}")
    print(f"bos={tok.bos_token_id} eos={tok.eos_token_id} pad={tok.pad_token_id} unk={tok.unk_token_id}")

    model = AdaptiveDonutOCR(freeze_encoder=True)
    ckpt = torch.load(CKPT, map_location="cpu")
    model.load_state_dict(ckpt)
    model.eval()

    cfg = model.model.config
    print(f"config.decoder_start_token_id = {getattr(cfg, 'decoder_start_token_id', None)}")
    print(f"config.pad_token_id           = {getattr(cfg, 'pad_token_id', None)}")
    print(f"config.eos_token_id           = {getattr(cfg, 'eos_token_id', None)}")

    # ---- Load a FUNSD test image + its target, exactly like training ----
    ds = load_dataset("nielsr/funsd", split="test")
    sample = ds[0]
    img = sample["image"].convert("RGB")
    pixel_values = processor(img, return_tensors="pt").pixel_values

    words = sample.get("words", ["sample", "document"])
    target_json = json.dumps({"text": " ".join(words[:40])})
    full = f"<s_doc>{target_json}</s>"
    ids = tok(full, add_special_tokens=False, return_tensors="pt").input_ids  # (1, L)
    print(f"\nTarget string (first 120 chars): {full[:120]!r}")
    print(f"Target length in tokens: {ids.shape[1]}")

    # ---- Section B: TEACHER-FORCED next-token diagnostic (the decisive test) ----
    # Feed decoder_input_ids == labels (exactly the training/dataset construction),
    # then check whether argmax(logits[t]) matches input[t] (COPY) or input[t+1] (LM).
    print("\n===== B. TEACHER-FORCED PREDICTION PATTERN =====")
    labels = ids.clone()
    with torch.no_grad():
        out = model(pixel_values=pixel_values, labels=labels, decoder_input_ids=ids)
    logits = out["logits"]  # (1, L, V)
    pred = logits.argmax(-1)[0]  # (L,)
    inp = ids[0]
    L = inp.shape[0]

    copy_hits = (pred[:-1] == inp[:-1]).sum().item()      # argmax[t] == input[t]  (copy)
    next_hits = (pred[:-1] == inp[1:]).sum().item()        # argmax[t] == input[t+1] (real LM)
    print(f"reported CE loss on this sample: {out['loss'].item():.4f}")
    print(f"COPY  accuracy (argmax[t]==input[t])   : {copy_hits}/{L-1} = {copy_hits/(L-1)*100:.1f}%")
    print(f"NEXT  accuracy (argmax[t]==input[t+1]) : {next_hits}/{L-1} = {next_hits/(L-1)*100:.1f}%")
    print("\nPosition-by-position (first 15): input_tok | argmax_tok")
    for t in range(min(15, L - 1)):
        it = tok.convert_ids_to_tokens(int(inp[t]))
        pt = tok.convert_ids_to_tokens(int(pred[t]))
        nxt = tok.convert_ids_to_tokens(int(inp[t + 1]))
        tag = "COPY" if pred[t] == inp[t] else ("NEXT" if pred[t] == inp[t + 1] else "----")
        print(f"  t={t:2d} in={it!r:14} argmax={pt!r:14} (true_next={nxt!r:14}) {tag}")

    # ---- Section C: free generation, two ways ----
    print("\n===== C. FREE GENERATION (short, max_length=48) =====")

    # C1: Kaggle path -> no decoder prompt (falls back to config.decoder_start_token_id)
    with torch.no_grad():
        g1, _ = model.generate(pixel_values, max_length=48)
    raw1 = tok.batch_decode(g1, skip_special_tokens=False)[0]
    print(f"\n[C1 Kaggle path, no prompt]   ids: {g1[0][:20].tolist()}")
    print(f"    raw   : {raw1[:160]!r}")

    # C2: infer.py path -> primed with <s_doc>
    p_ids = tok("<s_doc>", add_special_tokens=False, return_tensors="pt").input_ids
    with torch.no_grad():
        g2, _ = model.generate(pixel_values, decoder_input_ids=p_ids, max_length=48)
    raw2 = tok.batch_decode(g2, skip_special_tokens=False)[0]
    print(f"\n[C2 infer.py path, <s_doc>]   ids: {g2[0][:20].tolist()}")
    print(f"    raw   : {raw2[:160]!r}")


if __name__ == "__main__":
    main()
