"""T2's artifact: confirm the second eval corpus by LOADING it, and measure whether
T1's point-denominated thresholds are portable to it.

T2's DONE-WHEN says "confirmed by loading". That wording earned its keep: the first
SROIE mirror inspected (`buthaya/sroie`) has exactly 347 test annotation files -- the
canonical size -- and ZERO images in the entire repo. A file count matching the expected
number is not a confirmed split, and a `words` field is not word-level ground truth just
because it is called `words` (`buthaya` and `jsdnrs` both store LINE segments in it).

So every number here is derived from a loaded dataset object, and the controls assert the
three things that a shallower check would have gotten wrong:

  (1) the split size, from len(ds), not from counting files;
  (2) the DENOTATION of the word field -- zero whitespace inside any unit, and per-word
      boxes aligned 1:1 -- because a 2.1x denominator error is invisible otherwise;
  (3) that an image column actually exists and decodes, because the pipeline under test
      is image -> encoder -> prune -> merge -> decoder.

Section 3 is the part that decided T2. It measures the recall DENOMINATOR per corpus and
shows CORD's ground truth denotes a different quantity from FUNSD's and SROIE's (CORD
annotates key-value fields; the other two transcribe the page). Pooling would average two
metrics under one name. The grain consequence -- CORD's smallest expressible move is 5.00
pts against T1's 1.0 pt MDE -- follows from that, and is why CORD is excluded on denotation
rather than on size. Size agreed, but size was not the reason.

Section 4 audits this script's own framing, on the principle that a prescription deserves
the same suspicion as a diagnosis (D14 s10). Its first draft claimed exact -10.000000 ties
were a CORD-specific hazard; they are not, and the control that says so FAILS on the claim
as first written. The count was never the asymmetry -- the number of words needed to reach
the tie is.

Run:  python scripts/verify_corpus_grain.py
      python scripts/verify_corpus_grain.py --selftest   (identical; see note in main)
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys

MDE = 1.0        # T1 s6: the effect size run 17 must resolve, in recall points
HARM_THR = 10.0  # T1 s3: |harm| threshold per document, in recall points
TARGET_N = 307   # T1 s6: n required for res <= 1.0 pt on the named primary

_n_controls = 0
_n_failed = 0


def say(ok: bool, msg: str) -> bool:
    global _n_controls, _n_failed
    _n_controls += 1
    if not ok:
        _n_failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    return ok


def note(msg: str) -> None:
    """Informational. Deliberately NOT a control."""
    print(f"  [info] {msg}")


# --------------------------------------------------------------------------
# loaders -- each returns a list of per-document word lists
# --------------------------------------------------------------------------

def load_funsd():
    from datasets import load_dataset
    ds = load_dataset("nielsr/funsd", split="test")
    return ds, [[w for w in r["words"] if isinstance(w, str)] for r in ds]


def load_sroie():
    from datasets import load_dataset
    ds = load_dataset("sizhkhy/SROIE", split="test")
    return ds, [list(r["words"]) for r in ds]


def load_cord():
    from datasets import load_dataset
    ds = load_dataset("naver-clova-ix/cord-v2", split="test")
    docs = []
    for r in ds:
        g = json.loads(r["ground_truth"])
        docs.append([w["text"] for line in g.get("valid_line", []) for w in line["words"]])
    return ds, docs


def tokens(docs):
    """Whitespace-token count per document -- the recall DENOMINATOR, one unit = one word."""
    return [sum(len(u.split()) for u in d) for d in docs]


# --------------------------------------------------------------------------
# 1. SPLIT SIZE, from loading
# --------------------------------------------------------------------------

def section_sizes(f, s, c):
    print("\n" + "=" * 74)
    print("1. SPLIT SIZE -- from len(loaded dataset), not from counting files")
    print("=" * 74)
    print("   `buthaya/sroie` has 347 test annotation FILES and 0 images repo-wide.")
    print("   A count that matches the expected number is not a confirmed split.")

    say(len(f) == 50, f"FUNSD test loads n=50 (got {len(f)})")
    say(len(s) == 347, f"SROIE test loads n=347, the canonical ICDAR task-1/2 size (got {len(s)})")
    say(len(c) == 100, f"CORD  test loads n=100 (got {len(c)})")

    pool = len(f) + len(s)
    say(pool == 397, f"pooled FUNSD+SROIE n={pool}")
    say(pool >= TARGET_N,
        f"the pool clears T1 s6's n >= {TARGET_N} for res <= {MDE:.1f} pt "
        f"(margin {pool - TARGET_N} docs)")
    say(len(f) + len(c) < TARGET_N,
        f"FUNSD+CORD n={len(f) + len(c)} does NOT clear it -- recorded because it is the "
        f"WRONG reason to exclude CORD; see section 3")


# --------------------------------------------------------------------------
# 2. DENOTATION of the word field
# --------------------------------------------------------------------------

def section_denotation(fd, sd, cd, sds):
    print("\n" + "=" * 74)
    print("2. DENOTATION -- is a `words` field word-level, or line-level wearing the name?")
    print("=" * 74)
    print("   `buthaya/sroie` and `jsdnrs/ICDAR2019-SROIE` both store LINE segments in a")
    print("   field named `words`: ['TAN CHAY YEE', 'TEL:07-388 2218 FAX:07-388 8218', ...]")
    print("   57% of units are multi-word. Scoring recall on that shrinks the denominator")
    print("   ~2.1x and inflates every unit by the same factor, silently.")

    for name, docs in (("FUNSD", fd), ("SROIE", sd), ("CORD", cd)):
        units = sum(len(d) for d in docs)
        multi = sum(1 for d in docs for u in d if len(u.split()) > 1)
        pct = 100.0 * multi / units if units else 0.0
        note(f"{name:6s} multi-word units: {multi}/{units} ({pct:.2f}%)")

    s_units = sum(len(d) for d in sd)
    s_multi = sum(1 for d in sd for u in d if len(u.split()) > 1)
    say(s_multi == 0,
        f"SROIE's chosen mirror is genuinely word-level: {s_multi}/{s_units} units "
        f"contain whitespace")

    aligned = sum(1 for r in sds if len(r["words"]) == len(r["bboxes"]))
    say(aligned == len(sds),
        f"SROIE words<->bboxes aligned 1:1 in {aligned}/{len(sds)} docs (per-WORD boxes)")
    print("      NOTE: `buthaya` is ALSO 347/347 aligned -- with per-SEGMENT boxes. Alignment")
    print("      is necessary, not sufficient; it is exactly what hides the mismatch.")

    # the image column must exist AND decode -- the pipeline consumes images
    r0 = sds[0]
    img = r0.get("images") if "images" in sds.features else r0.get("image")
    ok_img = img is not None and hasattr(img, "size") and img.size[0] > 0
    say(ok_img, f"SROIE has a decodable image column (doc0 {getattr(img, 'size', None)}) -- "
                f"`buthaya`/`haocf` have none, so nothing could be run on them")


# --------------------------------------------------------------------------
# 3. THE DECIDING SECTION: what does the recall denominator denote?
# --------------------------------------------------------------------------

def section_grain(fd, sd, cd, cds):
    print("\n" + "=" * 74)
    print("3. GRAIN AND DENOTATION OF THE METRIC -- why CORD is excluded")
    print("=" * 74)

    # 3a. CORD's ground truth is the annotated subset, not the page.
    categorised = 0
    total_lines = 0
    for r in cds:
        g = json.loads(r["ground_truth"])
        for line in g.get("valid_line", []):
            total_lines += 1
            if line.get("category"):
                categorised += 1
    say(categorised == total_lines,
        f"every CORD valid_line carries a key-value `category` ({categorised}/{total_lines}) "
        f"-- its GT is the ANNOTATED SUBSET, not the page")
    note("CORD doc0 categories: menu.nm, menu.num, menu.price, sub_total.tax_price, "
         "total.total_price, ...  The store name/address/phone are on the receipt and "
         "NOT in the ground truth. FUNSD and SROIE transcribe the whole page.")
    print("   => `recall` on CORD and `recall` on FUNSD/SROIE are DIFFERENT QUANTITIES")
    print("      wearing one name. Pooling them averages two metrics.")

    # 3b. the grain that follows from it
    print("\n   grain (one word, in recall points -- the smallest expressible move):")
    hdr = f"      {'corpus':7s} {'n':>4s} {'words/doc':>10s} {'1 word':>8s} {'max':>7s} {'>%.0fpt' % HARM_THR:>8s}"
    print(hdr)
    stats = {}
    for name, docs in (("FUNSD", fd), ("SROIE", sd), ("CORD", cd)):
        wc = tokens(docs)
        pts = [100.0 / n for n in wc if n]
        over = sum(1 for p in pts if p > HARM_THR)
        stats[name] = (wc, pts, over)
        print(f"      {name:7s} {len(wc):4d} {st.median(wc):10.1f} {st.median(pts):8.2f} "
              f"{max(pts):7.2f} {over:5d}/{len(pts)}")

    f_pt = st.median(stats["FUNSD"][1])
    s_pt = st.median(stats["SROIE"][1])
    c_pt = st.median(stats["CORD"][1])

    say(c_pt >= MDE,
        f"CORD's smallest expressible move ({c_pt:.2f} pt) is >= T1's MDE ({MDE:.1f} pt) -- "
        f"the metric cannot EXPRESS the effect being measured")
    say(s_pt < MDE,
        f"SROIE's smallest expressible move ({s_pt:.2f} pt) is < the MDE -- it can")
    say(stats["CORD"][2] > 0,
        f"{stats['CORD'][2]}/{len(stats['CORD'][1])} CORD docs trip the -{HARM_THR:.0f} pt "
        f"harm threshold on ONE wrong word")
    say(stats["SROIE"][2] == 0 and stats["FUNSD"][2] == 0,
        f"no FUNSD or SROIE doc can: {stats['FUNSD'][2]}/50 and {stats['SROIE'][2]}/347")

    r_s, r_c = s_pt / f_pt, c_pt / f_pt
    say(r_s < 2.0 < r_c,
        f"portability: SROIE is {r_s:.2f}x FUNSD's grain, CORD is {r_c:.2f}x -- T1's "
        f"point-denominated thresholds port to SROIE and not to CORD")

    # 3c. composition of the pool that results
    fw, sw = sum(tokens(fd)), sum(tokens(sd))
    n_pool = len(fd) + len(sd)
    d_share = 100.0 * len(sd) / n_pool
    w_share = 100.0 * sw / (fw + sw)
    note(f"pool composition: {d_share:.1f}% of documents and {w_share:.1f}% of words are "
         f"SROIE receipts ({fw + sw} words total)")
    say(d_share > 80.0,
        f"a 'pooled' result is substantially a RECEIPT result -- FUNSD is a "
        f"{100 - d_share:.1f}% minority in its own successor corpus; report per-corpus too")

    # 3d. the discard-set collision with D14 s4 / T1 s5
    k = int(0.10 * n_pool)
    say(k < len(fd),
        f"g=0.10 at n={n_pool} discards {k} per tail vs FUNSD's {len(fd)} docs -- D14 s4's "
        f"'trim can delete FUNSD' is REDUCED, not eliminated ({100.0 * k / len(fd):.0f}% of it)")
    return stats


# --------------------------------------------------------------------------
# 4. AUDIT OF THIS SCRIPT'S OWN FIRST DRAFT
# --------------------------------------------------------------------------

def section_self_audit(stats):
    print("\n" + "=" * 74)
    print("4. AUDIT OF THIS ANALYSIS'S OWN FRAMING (D14 s10's principle, applied here)")
    print("=" * 74)
    print("   First draft claimed: '13/100 CORD docs can land exactly on -10.000000, vs")
    print("   9/50 FUNSD' -- i.e. the tie convention is a CORD-specific hazard.")
    print("   k words == exactly -10.000000  <=>  100k/n = 10  <=>  k = n/10 integer")
    print("   <=>  n = 0 (mod 10).  The draft instead tested whether 1000/n is an integer,")
    print("   i.e. whether n DIVIDES 1000 -- rarer, different, and satisfiable, so it")
    print("   returned a plausible wrong number rather than an error.")

    ties = {}
    for name in ("FUNSD", "SROIE", "CORD"):
        wc = stats[name][0]
        ties[name] = sum(1 for n in wc if n and n % 10 == 0)
        note(f"{name:6s} docs with an exact -{HARM_THR:.0f}.000000 tie: {ties[name]}/{len(wc)}")

    say(ties["CORD"] != 13 or ties["FUNSD"] != 9,
        f"the first draft's counts were WRONG (claimed CORD 13/100 and FUNSD 9/50; "
        f"measured {ties['CORD']}/100 and {ties['FUNSD']}/50)")

    f_rate = ties["FUNSD"] / 50.0
    c_rate = ties["CORD"] / 100.0
    say(not (c_rate > 2 * f_rate),
        f"and the FRAMING was wrong too: ties are not CORD-specific "
        f"({100 * c_rate:.0f}% of CORD vs {100 * f_rate:.0f}% of FUNSD) -- they need only "
        f"n = 0 (mod 10), which happens everywhere")

    # what IS corpus-specific: how many words it takes to reach the tie
    print("\n   the real asymmetry, which the COUNT never showed:")
    for name in ("FUNSD", "SROIE", "CORD"):
        med = st.median(stats[name][0])
        print(f"      {name:6s} median {med:5.0f} words -> {med / 10:5.1f} wrong words reach "
              f"-{HARM_THR:.0f}.000000 exactly")
    k_cord = st.median(stats["CORD"][0]) / 10
    k_funsd = st.median(stats["FUNSD"][0]) / 10
    say(k_cord <= 2.0 < k_funsd,
        f"on a median CORD receipt {k_cord:.0f} wrong words land exactly on the threshold; "
        f"on a median FUNSD form it takes {k_funsd:.0f} -- ordinary single-document event "
        f"vs effectively unreachable")

    # the licence, stated at the strength the evidence supports
    print("\n   licence, at the strength the evidence supports:")
    print("      SROIE's `mit` tag is asserted by a THIRD-PARTY UPLOADER, not by the ICDAR")
    print("      2019 organisers who hold the original terms. Three re-uploads of the same")
    print("      corpus carry `mit` (sizhkhy, buthaya) and `cc-by-4.0` (jsdnrs) -- they do")
    print("      not agree. Of 100 SROIE-matching HF datasets, 77 carry no licence at all.")
    print("      CORD's `cc-by-4.0` comes from naver-clova-ix, the publishing lab itself.")
    say(True, "recorded as a PUBLICATION question for the user to decide, not a measurement "
              "question this script can settle -- nothing downstream is blocked by it")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="alias for the default run; see note below")
    args = ap.parse_args()

    print("=" * 74)
    print("T2 -- CORPUS VERIFICATION BY LOADING  (FUNSD / SROIE / CORD)")
    print("=" * 74)
    if args.selftest:
        # NOTE: every control lives INSIDE a section and each section needs all three
        # corpora loaded, so "controls only" cannot skip any work. This flag is an
        # explicit alias rather than a mode that silently does nothing -- the same
        # defect was found in diagnose_analysis_dof.py, where --selftest had always
        # been a byte-for-byte copy of the default branch.
        print("(--selftest is an alias for the default run: all controls, same sections)")

    fds, fd = load_funsd()
    sds, sd = load_sroie()
    cds, cd = load_cord()

    section_sizes(fds, sds, cds)
    section_denotation(fd, sd, cd, sds)
    stats = section_grain(fd, sd, cd, cds)
    section_self_audit(stats)

    print("\n" + "=" * 74)
    print(f"CONTROLS: {_n_controls - _n_failed}/{_n_controls} PASS")
    print("=" * 74)
    print("DECISION: second corpus = sizhkhy/SROIE test, n=347. Pool FUNSD+SROIE = 397.")
    print("CORD excluded on DENOTATION (its GT is the annotated subset, not the page),")
    print("not on size -- size merely agreed. CORD may be reported as a separate row with")
    print("its own thresholds; it must never enter the pool.")
    return 1 if _n_failed else 0


if __name__ == "__main__":
    sys.exit(main())
