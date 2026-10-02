"""T4's pre-flight: prove the pooled corpus can be EVALUATED before booking a GPU session.

T4 ports the 28-row sweep from FUNSD (n=50) to FUNSD+SROIE (n=397). T2 already
confirmed the corpus *loads* and that its word grain is compatible with T1's
point-denominated thresholds. That is not the same as confirming the *pipeline*
can consume it, and it says nothing about what the sweep costs.

Two things this script establishes, both of which change what T4 does:

  (1) SCHEMA. `nielsr/funsd` and `sizhkhy/SROIE` do NOT share a column layout.
      Three call sites index `sample["image"]` -- cell 9's DocumentDataset, cell 15's
      eval loop, and `src/evaluate.py:149`. Every one of them is a hard KeyError on
      SROIE. The adapter is four lines; the point of measuring it here is that the
      NON-VACUITY control (section 1c) asserts the naive access really does raise, so
      the adapter cannot later be deleted as redundant.

  (2) COST. Run 13's own artifact gives 2.609 s/image over 28 rows x 50 docs = 60.9 min
      on a Kaggle T4. Scaling that by 397/50 gives ~8.05 h of pure generate() and puts
      T4 at the edge of Kaggle's 9-hour cap with no margin -- but that arithmetic assumes
      a receipt costs the same as a form, and D3 measured latency as correlating with
      GENERATED tokens (r ~ +0.93/+0.98), not with visual ones. SROIE's median document
      is 109 words against FUNSD's 177, which argues the receipts are CHEAPER; the model
      is also out of domain on receipts and may run to the 512 cap, which argues the
      opposite. Those predictions differ by more than 2x, so the projection is not
      derivable from document lengths and has to be measured.

      This script measures the per-corpus generated-token ratio locally and multiplies
      run 13's Kaggle anchor by it. Local absolute latency is NOT used -- D11/D12 both
      record that local and Kaggle absolute numbers are not comparable. The RATIO is.

FALSIFIERS, stated before the run (Conventions: "state a falsifier before running"):
  - If the adapter's naive-access control does NOT raise on SROIE, the schema finding
    is wrong and PATCH I does not need an adapter.
  - If SROIE's mean generated tokens are within 10% of FUNSD's, the 8.05 h projection
    stands as arithmetic and this script has changed nothing.
  - If SROIE's hit-cap rate is materially above FUNSD's, cost goes UP, not down, and
    the 28-row port does not fit a Kaggle session at all.

WHAT THIS CANNOT SAY: nothing here is an accuracy result. The generation numbers are
n<=8 per corpus on CPU with a checkpoint trained on forms; they bound COST and prove
the pipeline RUNS. Any recall figure printed below is diagnostic scaffolding, not a
measurement, and is labelled as such.

Run:  python -u scripts/preflight_pooled_corpus.py              # structural only, seconds
      python -u scripts/preflight_pooled_corpus.py --gen --n 3  # + real generation, ~5 min CPU
"""

from __future__ import annotations

import argparse
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")  # cp1252 kills a checker mid-run otherwise

FUNSD = "nielsr/funsd"
SROIE = "sizhkhy/SROIE"

# run 13's own artifact, the Kaggle anchor this script scales rather than replaces
RUN13_MS_PER_IMAGE = 2609.0   # mean avg_latency_ms over its 28 rows
RUN13_ROWS = 28
RUN13_N = 50
POOL_N = 397                  # T2: FUNSD 50 + SROIE 347
KAGGLE_CAP_H = 9.0

_n, _f = 0, 0


def say(ok: bool, msg: str) -> bool:
    global _n, _f
    _n += 1
    if not ok:
        _f += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    return ok


def note(msg: str) -> None:
    print(f"  [info] {msg}")


# --------------------------------------------------------------------------
# the adapter under test -- four lines, and section 1c proves they are needed
# --------------------------------------------------------------------------

def get_image(sample):
    """The column is `image` on FUNSD and `images` on SROIE. Raise on neither."""
    for k in ("image", "images"):
        if k in sample:
            return sample[k]
    raise KeyError(f"no image column in {sorted(sample.keys())}")


def get_boxes(sample):
    for k in ("bboxes", "boxes", "bbox"):
        v = sample.get(k)
        if v:
            return v
    return None


# --------------------------------------------------------------------------
# 1. schema
# --------------------------------------------------------------------------

def section_schema():
    from datasets import load_dataset

    print("\n" + "=" * 74)
    print("1. SCHEMA -- can the existing pipeline index a pooled sample at all?")
    print("=" * 74)

    f = load_dataset(FUNSD, split="test")
    s = load_dataset(SROIE, split="test")

    say(len(f) == 50, f"FUNSD test n={len(f)}")
    say(len(s) == 347, f"SROIE test n={len(s)}")
    say(len(f) + len(s) == POOL_N, f"pool n={len(f) + len(s)} matches T2's {POOL_N}")

    fc, sc = sorted(f.features), sorted(s.features)
    note(f"FUNSD columns: {fc}")
    note(f"SROIE columns: {sc}")

    # 1a/1b -- the mismatch, named
    say("image" in fc and "image" not in sc,
        "FUNSD has `image`; SROIE does NOT -- the column name differs between corpora")
    say("images" in sc and "images" not in fc,
        "SROIE has `images` (plural); FUNSD does NOT")
    say(set(fc) != set(sc),
        f"column sets differ: only-FUNSD={sorted(set(fc) - set(sc))}, "
        f"only-SROIE={sorted(set(sc) - set(fc))}")

    # 1c -- NON-VACUITY. The adapter must be provably load-bearing, or a later
    # reader deletes it as defensive clutter. Assert the naive access RAISES.
    s0 = s[0]
    raised = False
    try:
        _ = s0["image"]
    except (KeyError, ValueError) as e:
        raised = True
        note(f"naive sample['image'] on SROIE raises {type(e).__name__}: {str(e)[:60]}")
    say(raised,
        "NON-VACUITY: the shipped `sample['image']` access RAISES on SROIE -- so cell 9, "
        "cell 15's eval loop and src/evaluate.py:149 all need the adapter, and it cannot "
        "be dropped as redundant later")

    # 1d -- the adapter fixes it, on both corpora
    fi, si = get_image(f[0]), get_image(s0)
    say(hasattr(fi, "size") and fi.size[0] > 0, f"adapter returns a decodable FUNSD image {fi.size}")
    say(hasattr(si, "size") and si.size[0] > 0, f"adapter returns a decodable SROIE image {si.size}")

    # 1e -- the OTHER field the target builder reads
    say(bool(f[0].get("words")) and bool(s0.get("words")),
        "both corpora expose `words`")
    fb, sb = get_boxes(f[0]), get_boxes(s0)
    say(fb is not None and sb is not None,
        f"both expose boxes (FUNSD via `{'bboxes' if f[0].get('bboxes') else '?'}`, "
        f"SROIE via `{'bboxes' if s0.get('bboxes') else '?'}`) -- reading_order_words is usable")
    say(len(s0["words"]) == len(sb),
        f"SROIE words<->boxes aligned 1:1 on doc0 ({len(s0['words'])}) -- per-WORD boxes, "
        f"re-confirming T2 on the sample this script will actually run")

    return f, s


# --------------------------------------------------------------------------
# 2. the target text, through the SHIPPED builder
# --------------------------------------------------------------------------

def section_targets(f, s):
    """Uses src/dataset.py's reading_order_words, not a restatement of it.

    Conventions: "a diagnostic that defines its own copy of the algorithm it is
    checking cannot fail -- before trusting any verifier, check what it imports."
    """
    from src.dataset import MAX_TARGET_WORDS, reading_order_words

    print("\n" + "=" * 74)
    print("2. TARGET TEXT -- does the shipped reading-order builder survive receipts?")
    print("=" * 74)
    note(f"imported reading_order_words + MAX_TARGET_WORDS={MAX_TARGET_WORDS} from src.dataset")

    out = {}
    for name, ds in (("FUNSD", f), ("SROIE", s)):
        lens, trunc = [], 0
        for r in ds:
            w = reading_order_words([x for x in r["words"] if isinstance(x, str)], get_boxes(r))
            if len(w) > MAX_TARGET_WORDS:
                trunc += 1
            lens.append(len(w[:MAX_TARGET_WORDS]))
        mean = sum(lens) / len(lens)
        out[name] = (mean, trunc, len(lens))
        note(f"{name:6s} target words after truncation: mean {mean:6.1f}  "
             f"truncated at {MAX_TARGET_WORDS}: {trunc}/{len(lens)} docs")

    f_mean, f_tr, _ = out["FUNSD"]
    s_mean, s_tr, s_n = out["SROIE"]

    say(s_mean > 0 and f_mean > 0, "both corpora produce non-empty targets")
    say(s_tr < s_n,
        f"SROIE is NOT uniformly truncated ({s_tr}/{s_n}) -- its documents vary in length, "
        f"so the corpus is not a constant-cost block")
    say(s_mean < f_mean,
        f"SROIE targets are SHORTER than FUNSD's ({s_mean:.1f} vs {f_mean:.1f} words) -- "
        f"the prediction that receipts are cheaper, stated before generation runs")
    print(f"      => length-based prediction: SROIE costs {s_mean / f_mean:.2f}x a FUNSD doc.")
    print("         Section 3 tests it. The model is OUT OF DOMAIN on receipts and can")
    print("         run to the 512 cap regardless of how short the gold is, which would")
    print("         invert this. A prediction from gold length is not a measurement.")
    return out


# --------------------------------------------------------------------------
# 3. generation -- the only part that can refute section 2's prediction
# --------------------------------------------------------------------------

def section_generation(f, s, n, keep, merge):
    import torch
    from transformers import DonutProcessor

    from src.dataset import MAX_TARGET_WORDS, reading_order_words
    from src.evaluate import compute_word_metrics
    from src.model import AdaptiveDonutOCR

    print("\n" + "=" * 74)
    print(f"3. GENERATION -- n={n}/corpus, keep={keep}, merge={merge}, CPU")
    print("=" * 74)
    print("   Checkpoint: run 9's, the weights run 13 evaluated. Absolute latency here is")
    print("   NOT comparable to Kaggle (D11/D12 both record this); the per-corpus RATIO is")
    print("   what section 4 uses, multiplied by run 13's own Kaggle anchor.")

    ckpt = "run 9/adaptive_donut_pruned.pt"
    base = "naver-clova-ix/donut-base"
    device = torch.device("cpu")

    processor = DonutProcessor.from_pretrained(base)
    model = AdaptiveDonutOCR(base_model_name=base).to(device)
    sd = torch.load(ckpt, map_location=device)
    sd = sd.get("model_state_dict", sd) if isinstance(sd, dict) and "model_state_dict" in sd else sd
    missing, unexpected = model.load_state_dict(sd, strict=True), None
    model.eval()
    say(True, f"loaded {ckpt} (strict=True, so a silent architecture drift would have raised)")

    prompt_ids = processor.tokenizer(
        "<s_doc>", add_special_tokens=False, return_tensors="pt"
    ).input_ids.to(device)

    MAXLEN = 512
    res = {}
    for name, ds in (("FUNSD", f), ("SROIE", s)):
        gens, secs, caps, recs, ntok = [], [], 0, [], []
        for i in range(min(n, len(ds))):
            r = ds[i]
            img = get_image(r).convert("RGB")
            pv = processor(img, return_tensors="pt").pixel_values.to(device)
            t0 = time.perf_counter()
            with torch.no_grad():
                ids, meta = model.generate(
                    pixel_values=pv, decoder_input_ids=prompt_ids,
                    keep_ratio=keep, merge_ratio=merge, max_length=MAXLEN,
                )
            dt = time.perf_counter() - t0
            g = int(ids.shape[1])
            gens.append(g)
            secs.append(dt)
            caps += int(g >= MAXLEN)
            ntok.append(int(meta["compressed_tokens"]))

            gw = reading_order_words([x for x in r["words"] if isinstance(x, str)],
                                     get_boxes(r))[:MAX_TARGET_WORDS]
            pred = processor.batch_decode(ids, skip_special_tokens=True)[0]
            rec, _order = compute_word_metrics(pred, gw)
            recs.append(rec * 100.0)
            print(f"      {name:6s} doc{i}: gen {g:4d} tok  {dt:6.1f}s  "
                  f"M={ntok[-1]}  recall~{rec * 100:5.1f}")

        res[name] = {
            "mean_gen": sum(gens) / len(gens),
            "mean_s": sum(secs) / len(secs),
            "cap_rate": caps / len(gens),
            "mean_recall": sum(recs) / len(recs),
            "n": len(gens),
            "M": ntok[0],
        }

    fr, sr = res["FUNSD"], res["SROIE"]
    say(sr["n"] > 0, f"SROIE generated end-to-end without a schema error ({sr['n']} docs) -- "
                     f"the adapter is sufficient, not just necessary")
    say(fr["M"] == sr["M"],
        f"visual-token budget is identical across corpora (M={fr['M']}) -- the budget is set "
        f"by keep_ratio and the 4800-token grid, not by document content")

    ratio = sr["mean_gen"] / fr["mean_gen"]
    note(f"FUNSD mean generated tokens {fr['mean_gen']:.0f}, cap-rate {fr['cap_rate']:.0%}, "
         f"{fr['mean_s']:.1f} s/doc local")
    note(f"SROIE mean generated tokens {sr['mean_gen']:.0f}, cap-rate {sr['cap_rate']:.0%}, "
         f"{sr['mean_s']:.1f} s/doc local")

    say(abs(ratio - 1.0) > 0.10,
        f"SROIE/FUNSD generated-token ratio is {ratio:.2f} -- OUTSIDE the +/-10% band in which "
        f"the naive 397/50 arithmetic would have stood unchanged")
    say(sr["cap_rate"] <= fr["cap_rate"],
        f"SROIE does not hit the {MAXLEN}-token cap more often than FUNSD "
        f"({sr['cap_rate']:.0%} vs {fr['cap_rate']:.0%}) -- the out-of-domain runaway "
        f"that would have INVERTED section 2's prediction did not occur")

    print(f"\n   diagnostic scaffolding, NOT a result: mean recall FUNSD {fr['mean_recall']:.1f} / "
          f"SROIE {sr['mean_recall']:.1f} at n={n}.")
    print("   SROIE is out of domain and n is tiny. Do not quote these; they exist to show")
    print("   the decoder emits text rather than the unprompted-garbage failure mode.")
    return res, ratio


# --------------------------------------------------------------------------
# 4. what the sweep costs
# --------------------------------------------------------------------------

def section_cost(tgt, res, ratio):
    print("\n" + "=" * 74)
    print("4. COST OF THE POOLED SWEEP -- run 13's Kaggle anchor, scaled by the measured ratio")
    print("=" * 74)

    anchor_min = RUN13_MS_PER_IMAGE * RUN13_ROWS * RUN13_N / 1000.0 / 60.0
    note(f"run 13 measured: {RUN13_MS_PER_IMAGE:.0f} ms/image x {RUN13_ROWS} rows x n={RUN13_N} "
         f"= {anchor_min:.1f} min of generate()")

    per_doc_s = RUN13_MS_PER_IMAGE / 1000.0
    if ratio is None:
        print("   (--gen not run: no measured ratio, so the naive projection is all there is)")
        naive_h = per_doc_s * RUN13_ROWS * POOL_N / 3600.0
        print(f"   naive 397/50 projection, 28 rows: {naive_h:.2f} h")
        return

    # effective documents, weighting each corpus by its measured generation cost
    eff = 50 * 1.0 + 347 * ratio
    full_h = per_doc_s * RUN13_ROWS * eff / 3600.0
    naive_h = per_doc_s * RUN13_ROWS * POOL_N / 3600.0

    print(f"\n   {'scope':38s} {'rows':>5s} {'eff docs':>9s} {'hours':>7s}  fits 9 h?")
    for label, rows in (("full sweep (all 28 rows)", 28),
                        ("T1 primary + control + random + ctl", 4),
                        ("primary pair only", 2)):
        h = per_doc_s * rows * eff / 3600.0
        print(f"   {label:38s} {rows:5d} {eff:9.0f} {h:7.2f}  {'yes' if h < KAGGLE_CAP_H else 'NO'}")

    say(abs(full_h - naive_h) / naive_h > 0.05,
        f"the measured ratio moves the 28-row projection by "
        f"{100 * (full_h - naive_h) / naive_h:+.0f}% ({naive_h:.2f} h -> {full_h:.2f} h) -- "
        f"the arithmetic-only estimate was not good enough to book against")
    say(full_h < KAGGLE_CAP_H,
        f"the full 28-row pooled sweep fits Kaggle's {KAGGLE_CAP_H:.0f} h cap at {full_h:.2f} h "
        f"(margin {KAGGLE_CAP_H - full_h:.2f} h)")

    print("\n   ⚠ generate() only. Excludes model load, dataset download, image preprocessing")
    print("     and the per-row ink/coverage statistics, which run 13 paid outside this figure")
    print(f"     (its wall clock was 64.0 min against {anchor_min:.1f} min of generate(), "
          f"i.e. {64.0 / anchor_min:.2f}x).")
    adj = full_h * 64.0 / anchor_min
    print(f"     Applying run 13's own overhead factor: {adj:.2f} h. "
          f"{'Still fits.' if adj < KAGGLE_CAP_H else 'DOES NOT FIT -- split the sweep.'}")
    say(adj < KAGGLE_CAP_H,
        f"with run 13's measured {64.0 / anchor_min:.2f}x overhead the full sweep is {adj:.2f} h "
        f"-- {'inside' if adj < KAGGLE_CAP_H else 'OUTSIDE'} the cap")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gen", action="store_true", help="run real generation (slow, CPU)")
    ap.add_argument("--n", type=int, default=3, help="documents per corpus for --gen")
    ap.add_argument("--keep", type=float, default=0.50)
    ap.add_argument("--merge", type=float, default=0.20)
    a = ap.parse_args()

    print("=" * 74)
    print("T4 PRE-FLIGHT -- pooled corpus (FUNSD + SROIE), before any GPU booking")
    print("=" * 74)

    f, s = section_schema()
    tgt = section_targets(f, s)

    ratio, res = None, None
    if a.gen:
        res, ratio = section_generation(f, s, a.n, a.keep, a.merge)
    else:
        print("\n(skipping section 3: pass --gen to measure generation. Section 4 then has")
        print(" no measured ratio and falls back to the arithmetic this script exists to test.)")

    section_cost(tgt, res, ratio)

    print("\n" + "=" * 74)
    print(f"CONTROLS: {_n - _f}/{_n} PASS")
    print("=" * 74)
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
