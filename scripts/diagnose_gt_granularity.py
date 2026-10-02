"""Is line-level ground truth equivalent to word-level, for this project's metrics?

WHY THIS EXISTS
---------------
AGENTS.md's T4 section records, as a cost of re-sourcing SROIE from the official
ICDAR competition:

    "official SROIE ships line-level transcriptions while the mirror carries
     per-word boxes, so the mirror likely tokenised the GT itself -- re-sourcing
     may require re-deriving word-level ground truth, which changes the recall
     denominator and requires verify_corpus_grain.py to be re-run."

That is a claim about the *pipeline*, asserted from the data description rather
than from the code. `src/evaluate.py:compute_word_metrics` contains:

    gold = re.findall(r"\\w+", " ".join(gt_words).lower())

i.e. the ground-truth tokens are JOINED and RE-TOKENISED. If that is the only
consumer of ground-truth segmentation, then ["ABC","COMPANY"] and ["ABC COMPANY"]
are indistinguishable downstream, line-level GT needs no re-derivation, and the
recall denominator does NOT change.

FALSIFIER, stated before running (per the project convention)
-------------------------------------------------------------
This probe FAILS -- and AGENTS.md's warning stands -- if, on any FUNSD test
document, aggregating per-word GT into line-level GT changes either
  (a) the gold token sequence, or
  (b) any value returned by the shipped compute_word_metrics.

NON-VACUITY: three sabotage controls must each produce a DIFFERENCE. A probe
where every comparison is equal cannot distinguish "invariant" from "my
comparison is broken".

SCOPE LIMIT: this tests word recall and word order, which are 2 of the 3
confirmatory quantities in T1 section 4. It says nothing about per-word boxes
being needed for anything OUTSIDE metric computation, and it is run on FUNSD
because official SROIE is not on this machine -- it establishes a property of
THE PIPELINE, not of SROIE.
"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # cp1252 would kill this mid-run
sys.path.insert(0, ".")

# Import the SHIPPED functions. A diagnostic that restates the logic under test
# is testing its own restatement (AGENTS.md, diagnose_tome_parity.py lesson).
from src.dataset import reading_order_words
from src.evaluate import compute_word_metrics

PASS = FAIL = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def to_lines(words, boxes):
    """Build a LINE-level fixture from per-word data.

    This simulates what an official SROIE-style annotation gives you: one
    transcription + one box per text line. It is deliberately MY code, not an
    import -- the fixture builder is not the thing under test; the metric's
    invariance is.
    """
    if not boxes or len(boxes) != len(words):
        return list(words), list(boxes)
    heights = sorted(b[3] - b[1] for b in boxes if b[3] > b[1])
    tol = (heights[len(heights) // 2] * 0.6) if heights else 10.0

    rows, used = [], set()
    for i in sorted(range(len(words)), key=lambda k: boxes[k][1]):
        if i in used:
            continue
        row = [i]
        used.add(i)
        for j in range(len(words)):
            if j not in used and abs(boxes[j][1] - boxes[i][1]) <= tol:
                row.append(j)
                used.add(j)
        rows.append(sorted(row, key=lambda k: boxes[k][0]))

    line_texts, line_boxes = [], []
    for row in rows:
        line_texts.append(" ".join(words[k] for k in row))
        line_boxes.append([
            min(boxes[k][0] for k in row), min(boxes[k][1] for k in row),
            max(boxes[k][2] for k in row), max(boxes[k][3] for k in row),
        ])
    return line_texts, line_boxes


def gold_tokens(words, boxes):
    """Exactly the gold path src/evaluate.py:154-155 then compute_word_metrics uses."""
    ordered = reading_order_words(list(words), list(boxes)) if boxes else list(words)
    return re.findall(r"\w+", " ".join(ordered).lower())


def main():
    from datasets import load_dataset

    print("=" * 74)
    print("Line-level vs word-level ground truth: pipeline equivalence probe")
    print("=" * 74)
    try:
        import editdistance  # noqa: F401
        print("editdistance: INSTALLED (exact word-order metric)")
    except ImportError:
        print("editdistance: ABSENT -- compute_word_metrics uses its length-difference")
        print("              fallback. Both arms take the same branch, so equality")
        print("              still tests what it claims, but word_order is coarser.")

    ds = load_dataset("nielsr/funsd", split="test")
    print(f"corpus: nielsr/funsd test, n={len(ds)}\n")

    print("-- 1. gold token sequence is identical under line aggregation --")
    seq_mismatch, denom_mismatch, checked = [], [], 0
    worst_lines = None
    for i, s in enumerate(ds):
        w, b = s["words"], s["bboxes"]
        gw, gl = gold_tokens(w, b), gold_tokens(*to_lines(w, b))
        if gw != gl:
            seq_mismatch.append(i)
        if len(set(gw)) != len(set(gl)):
            denom_mismatch.append(i)
        checked += 1
        lines, _ = to_lines(w, b)
        if worst_lines is None or len(lines) > worst_lines[1]:
            worst_lines = (i, len(lines), len(w))

    print(f"  MEASURED gold token sequence identical: "
          f"{checked - len(seq_mismatch)}/{checked} documents")
    print(f"  MEASURED recall denominator len(set(gold)) identical: "
          f"{checked - len(denom_mismatch)}/{checked} documents")
    print(f"           ^ this is the quantity AGENTS.md says changes")
    print(f"         (aggregation is real, not a no-op: doc {worst_lines[0]} went "
          f"{worst_lines[2]} words -> {worst_lines[1]} lines)")

    print("\n-- 2. shipped compute_word_metrics returns identical values --")
    metric_mismatch = []
    for i, s in enumerate(ds):
        w, b = s["words"], s["bboxes"]
        lw, lb = to_lines(w, b)
        g_word = reading_order_words(list(w), list(b))
        g_line = reading_order_words(list(lw), list(lb))
        # Two predictions: a perfect one and a degraded one, so the comparison is
        # not accidentally equal because both arms saturate at 1.0.
        full = " ".join(g_word)
        half = " ".join(g_word[: max(1, len(g_word) // 2)])
        for tag, pred in (("perfect", full), ("half", half)):
            rw, ow = compute_word_metrics(pred, g_word)
            rl, ol = compute_word_metrics(pred, g_line)
            if abs(rw - rl) > 1e-12 or abs(ow - ol) > 1e-12:
                metric_mismatch.append((i, tag, rw, rl, ow, ol))
    n_eq = 2 * len(ds) - len(metric_mismatch)
    print(f"  MEASURED (recall, word_order) identical: {n_eq}/{2 * len(ds)} "
          f"comparisons")
    # Split the mismatches by WHICH metric moved -- recall is set-based and
    # should be invariant; order is sequence-based and should not be.
    rec_moved = sum(1 for m in metric_mismatch if abs(m[2] - m[3]) > 1e-12)
    ord_moved = sum(1 for m in metric_mismatch if abs(m[4] - m[5]) > 1e-12)
    print(f"           of {len(metric_mismatch)} mismatches: recall moved in "
          f"{rec_moved}, word_order moved in {ord_moved}")
    r_p, o_p = compute_word_metrics(
        " ".join(reading_order_words(list(ds[0]["words"]), list(ds[0]["bboxes"]))),
        reading_order_words(list(ds[0]["words"]), list(ds[0]["bboxes"])))
    print(f"         (metrics are live, not degenerate: doc 0 perfect-pred "
          f"recall={r_p:.4f} order={o_p:.4f})")

    print("\n-- 3. NON-VACUITY: each sabotage must produce a DIFFERENCE --")
    s = ds[0]
    w, b = s["words"], s["bboxes"]
    base = gold_tokens(w, b)

    lines, lboxes = to_lines(w, b)

    # S1: perturb the GEOMETRY, not the list order. reading_order_words re-sorts
    # its input by bbox, so `lines[::-1]` is a no-op BY DESIGN -- an earlier
    # version of this control did exactly that and failed, which was the test's
    # fault, not the function's. Flipping y actually reverses reading order.
    ymax = max(bx[3] for bx in lboxes)
    flipped = [[bx[0], ymax - bx[3], bx[2], ymax - bx[1]] for bx in lboxes]
    rev = gold_tokens(lines, flipped)
    check("S1 flipping line geometry vertically changes the sequence",
          rev != base,
          f"equal={rev == base} (list-reversal would NOT work here: "
          f"reading_order_words re-sorts by box)")

    drop = gold_tokens(lines[:-1], lboxes[:-1])
    check("S2 dropping one line changes the sequence AND the denominator",
          drop != base and len(set(drop)) != len(set(base)),
          f"{len(set(drop))} vs {len(set(base))} unique tokens")

    g_word = reading_order_words(list(w), list(b))
    r_ok, _ = compute_word_metrics(" ".join(g_word), g_word)
    r_bad, _ = compute_word_metrics("totally unrelated text", g_word)
    check("S3 a wrong prediction moves recall (metric is not constant)",
          abs(r_ok - r_bad) > 0.5, f"recall {r_ok:.4f} -> {r_bad:.4f}")

    # Sabotage the ORDERING input itself: strip boxes so reading order is lost.
    nobox = gold_tokens(w, [])
    check("S4 removing boxes changes the sequence (so boxes ARE load-bearing "
          "for order)", nobox != base,
          f"equal={nobox == base} -- confirms LINE boxes still matter, only "
          f"per-WORD boxes do not")

    print("\n" + "=" * 74)
    print(f"CONTROLS: {PASS}/{PASS + FAIL} PASS")
    print("=" * 74)
    print("MEASURED (these are data verdicts, NOT check failures -- the same")
    print("distinction AGENTS.md draws for score_preregistered.log):")
    n_seq_ok = checked - len(seq_mismatch)
    n_den_ok = checked - len(denom_mismatch)
    print(f"  recall denominator identical : {n_den_ok}/{checked} documents")
    print(f"  gold sequence identical      : {n_seq_ok}/{checked} documents")
    print(f"  (recall, order) both identical: {100 - len(metric_mismatch)}/100 "
          f"comparisons")
    print()
    if FAIL:
        print("VERDICT: INCONCLUSIVE -- a non-vacuity control failed, so the")
        print("         equality results above cannot be trusted. Fix the probe.")
    elif not denom_mismatch and seq_mismatch:
        print("VERDICT: SPLIT, and it splits AGENTS.md's warning in half.")
        print("  * RECALL is granularity-INVARIANT. The recall denominator")
        print("    len(set(gold)) is identical on every document, because")
        print("    compute_word_metrics joins and re-tokenises the GT. The")
        print("    specific cost AGENTS.md names -- 'changes the recall")
        print("    denominator' -- is FALSE, measured.")
        print("  * WORD ORDER (and NED, which is also sequence-sensitive) are")
        print("    NOT invariant: reading order is re-derived from box geometry,")
        print("    and line boxes cluster differently from word boxes.")
        print("  CONSEQUENCE for T1 section 4's three-quantity family: the PRIMARY")
        print("  quantity is safe. The two co-primaries are computed on a")
        print("  different footing for a line-annotated corpus. Paired")
        print("  per-document differences stay internally valid -- both arms of a")
        print("  contrast score against the same GT -- so this is a")
        print("  CROSS-CORPUS COMPARABILITY issue, not a within-contrast one,")
        print("  and T1 section 5's per-corpus stratification is what must carry it.")
    elif not seq_mismatch:
        print("VERDICT: fully equivalent -- no re-derivation needed at all.")
    else:
        print("VERDICT: the denominator moved. AGENTS.md's warning STANDS as written.")
    print("=" * 74)
    print("SCOPE: measured on FUNSD with RECONSTRUCTED lines, because official")
    print("       SROIE is not on this machine. It establishes that the pipeline's")
    print("       reading-order step is sensitive to box granularity; it does not")
    print("       measure official SROIE's actual line annotations. Re-run against")
    print("       the real corpus before quoting a number from it.")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
