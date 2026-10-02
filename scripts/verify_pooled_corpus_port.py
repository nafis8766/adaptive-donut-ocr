"""PATCH I's companion: EXECUTE the pooled-corpus port, do not merely parse it.

T4 moves the 28-row sweep from FUNSD (n=50) to FUNSD+SROIE (n=397). PATCH I is the
first patch in this project to touch the data path, and it ships a class --
`PooledTestSet` -- that has never run anywhere. `ast.parse` passing says nothing about
it: the `.layernorm` gotcha in AGENTS.md is exactly a crash that parsed clean.

Every check here drives the SHIPPED code, spliced out of the generated notebook rather
than restated. That is the `diagnose_tome_parity.py` lesson: a diagnostic that declares
its own copy of the thing it is checking cannot fail. Where a check is an equality, a
non-vacuity control asserts a broken version scores differently.

Sections
  0  structural -- the anchors landed where PATCH I claims, and only there
  1  the image adapter, EXECUTED on both corpora + the control that proves it is needed
  2  PooledTestSet, EXECUTED against the real splits: n, per-corpus counts, corpus
     tagging, laziness, and index/iteration agreement
  3  the random arm -- at the pre-registered primary's own budget, and reproducible
  4  canonical-notebook parity -- the canonical notebook must stay FUNSD-only
  5  the per-corpus aggregate, EXECUTED, and asserted to DECOMPOSE the pooled figure

FALSIFIERS, stated before running:
  - If the naive `sample['image']` does NOT raise on SROIE, section 1's adapter is
    unnecessary and PATCH I's cell-9/13/15 rewrites are noise.
  - If PooledTestSet's per-corpus counts do not sum to 397, T1 s6's `n >~ 307` is not
    met and the FREE verdict stays unreachable -- the port has not achieved its purpose.
  - If the canonical notebook also became pooled, runs 2-6 stop being reproducible and
    PATCH I must be reverted, not adjusted.

WHAT THIS CANNOT SAY: nothing here is an accuracy result, and it does not run the
sweep. It establishes that the pooled sweep CAN run and that its artifact will carry
the fields T1's scorer needs.

Run:  python -u scripts/verify_pooled_corpus_port.py > results/verify_pooled_corpus_port.log 2>&1
      (redirect, never pipe -- `| tee` would launder the exit code, AGENTS.md Gotchas)
"""

from __future__ import annotations

import ast
import json
import re
import sys
import textwrap

sys.stdout.reconfigure(encoding="utf-8")

GEN = "kaggle_pruning_run.ipynb"
CANON = "kaggle_token_pruning_ocr.ipynb"

_n = _f = 0


def ck(cond: bool, msg: str) -> bool:
    global _n, _f
    _n += 1
    if not cond:
        _f += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    return bool(cond)


def note(msg: str) -> None:
    print(f"  [info] {msg}")


def cells(path: str):
    nb = json.loads(open(path, encoding="utf-8").read())
    return ["".join(c["source"]) for c in nb["cells"]]


def slice_block(src: str, start: str, end: str, what: str) -> str:
    """Lift a verbatim block out of a cell. Asserts the delimiters are unique."""
    assert src.count(start) == 1, f"{what}: start delimiter x{src.count(start)}"
    i = src.index(start)
    j = src.index(end, i)
    assert j > i, f"{what}: end delimiter not after start"
    return src[i:j]


# ==========================================================================
# 0. structural
# ==========================================================================

def section_structural(g):
    print("\n" + "=" * 74)
    print("0. STRUCTURAL -- PATCH I landed where it claims, and only there")
    print("=" * 74)
    c2, c9, c13, c15 = g[2], g[9], g[13], g[15]

    # the corpus list is a DECLARED config (D5: a defaulted hyperparameter is an
    # undeclared one), and it parses as a literal rather than as prose
    m = re.search(r"^EVAL_CORPORA = \[.*?^\]", c2, re.S | re.M)
    ck(m is not None, "cell 2 declares EVAL_CORPORA as a top-level literal")
    corpora = ast.literal_eval(m.group(0).split("=", 1)[1].strip())
    note(f"EVAL_CORPORA = {corpora}")
    ck(len(corpora) == 2 and corpora[0][0] == "funsd" and corpora[1][0] == "sroie",
       "EVAL_CORPORA is exactly (funsd, sroie), FUNSD first")
    # T2's exclusion is on DENOTATION, not size -- so the check is that CORD is not a
    # member, independent of how many documents anything has
    ck(not any("cord" in str(x).lower() for c in corpora for x in c),
       "CORD is NOT a member -- T2 excluded it because its GT denotes the annotated "
       "key-value subset, not the page (a denotation reason, which more receipts "
       "cannot repair)")
    ck("POOLED_N_EXPECTED = 397" in c2, "cell 2 pins POOLED_N_EXPECTED = 397")

    # the three call sites that hard-KeyError on SROIE
    for i, c in ((9, c9), (13, c13), (15, c15)):
        ck(c.count("sample['image']") == 0,
           f"cell {i}: no raw sample['image'] remains")
    # Count the CALL, not the substring: `def doc_image(sample):` in cell 9 also
    # contains "doc_image(sample)", which is the loose-selector mistake AGENTS.md
    # records twice (RESUME_CKPT, _TRAIN_SELECT_MODES). Anchor on the assignment.
    for i, c in ((9, c9), (13, c13), (15, c15)):
        ck(c.count("img = doc_image(sample).convert('RGB')") == 1,
           f"cell {i}: the image load goes through doc_image() exactly once")

    ck("test_raw = PooledTestSet(EVAL_CORPORA)" in c13,
       "cell 13 builds test_raw from the pooled set (cells 14/15 inherit it)")
    ck("assert len(test_raw) == POOLED_N_EXPECTED" in c13,
       "cell 13 ASSERTS the pooled size at load time -- a resharded mirror is a crash "
       "at minute one, not a wrong denominator six hours in")

    # the training-side test_ds is deliberately NOT pooled
    ck("test_ds = DocumentDataset(dataset_name='nielsr/funsd'" in c9,
       "cell 9's training-side test_ds stays FUNSD-only (T4 is eval-only; pooling it "
       "would silently change what a future DO_TRAIN run validates against)")

    # the fields T1's scorer needs
    ck("'corpus': sample.get('corpus', 'funsd')," in c15,
       "per_image carries `corpus` -- without it T1 s5's per-corpus discard constraint "
       "is not merely unimplemented, it is UNCOMPUTABLE")
    ck("'word_order': float(o)," in c15,
       "per_image carries `word_order` -- T4's DONE-WHEN, confirmed by REGENERATING "
       "rather than by grepping a committed notebook")
    ck("'per_corpus': per_corpus," in c15, "each row carries per-corpus aggregates")

    # row count
    sc = re.search(r"^SELECTION_CONFIGS = \[.*?^\]", c15, re.S | re.M).group(0)
    mc = re.search(r"^MERGE_CONFIGS = \[.*?^\]", c15, re.S | re.M).group(0)
    nsel = len(re.findall(r"^    \('", sc, re.M))
    nmer = len(re.findall(r"^    \('", mc, re.M))
    ck(nsel == 15, f"SELECTION_CONFIGS untouched at {nsel} published rows "
                   f"(their numbers are already cited; PATCH G left them alone too)")
    ck(nmer == 14, f"MERGE_CONFIGS is {nmer} = 13 + the random arm")
    ck(nsel + nmer == 29, f"total sweep rows {nsel + nmer} (was 28)")
    return nsel + nmer


# ==========================================================================
# 1. the adapter, executed
# ==========================================================================

def section_adapter(g):
    from datasets import load_dataset

    print("\n" + "=" * 74)
    print("1. THE ADAPTER -- spliced from cell 9 and EXECUTED on both corpora")
    print("=" * 74)

    blk = slice_block(g[9], "def doc_image(", "class PooledTestSet", "cell 9 helpers")
    ns: dict = {}
    exec(compile(blk, "<cell9-helpers>", "exec"), ns)
    doc_image = ns["doc_image"]
    note(f"spliced and exec'd {len(blk.splitlines())} lines of cell 9 verbatim "
         f"(not a restatement -- a restated copy would test itself)")

    f = load_dataset("nielsr/funsd", split="test")
    s = load_dataset("sizhkhy/SROIE", split="test")

    # NON-VACUITY: the adapter must be provably load-bearing
    raised = False
    try:
        _ = s[0]["image"]
    except (KeyError, ValueError) as e:
        raised = True
        note(f"naive sample['image'] on SROIE raises {type(e).__name__}: {str(e)[:50]}")
    ck(raised, "NON-VACUITY: the pre-PATCH-I access RAISES on SROIE -- so the adapter "
               "cannot later be deleted as defensive clutter")

    ck(doc_image(f[0]).size[0] > 0, f"adapter decodes FUNSD doc0 {doc_image(f[0]).size}")
    ck(doc_image(s[0]).size[0] > 0, f"adapter decodes SROIE doc0 {doc_image(s[0]).size}")

    # the raising else -- AGENTS.md: "any if/elif chain over a collection defined
    # elsewhere needs a raising else". A silent default in a VERIFIER is worse than a
    # bug in the code it verifies, because it converts an untested path into a green
    # check. Here the shipped adapter is the one under test.
    raised = False
    try:
        doc_image({"words": [], "bboxes": []})
    except KeyError:
        raised = True
    ck(raised, "adapter RAISES on a corpus with a third column name rather than "
               "returning None into a .convert() several frames away")

    # There is deliberately NO box adapter to test. `words` and `bboxes` are named
    # IDENTICALLY on both corpora, so the image column is the pool's only schema
    # divergence -- PATCH I shipped an uncalled doc_boxes() until 2026-09-30, dead code
    # of the `final_coords` kind. Assert the FACT that makes an adapter unnecessary, so
    # a future corpus that DOES rename boxes fails here instead of at document 51.
    _shared = {"words", "bboxes"}
    ck(_shared <= set(f.column_names) and _shared <= set(s.column_names),
       f"`words` and `bboxes` are common to BOTH corpora, so the image column is the "
       f"only divergence (funsd-only "
       f"{sorted(set(f.column_names) - set(s.column_names))}, sroie-only "
       f"{sorted(set(s.column_names) - set(f.column_names))})")

    # By ast, not by substring: the generator now carries a COMMENT naming doc_boxes to
    # record why it is gone, and a substring test would read that comment as the defect
    # it is documenting.
    _c9_defs = {n.name for n in ast.walk(ast.parse(g[9]))
                if isinstance(n, ast.FunctionDef)}
    ck("doc_image" in _c9_defs and "doc_boxes" not in _c9_defs,
       f"cell 9 defines doc_image and no uncalled doc_boxes -- an adapter for a "
       f"divergence that does not exist makes a reader believe a path is wired when "
       f"nothing reaches it (cell 9 defs: {sorted(_c9_defs)})")

    ck(len(s[0]["words"]) == len(s[0]["bboxes"]),
       f"SROIE words<->boxes 1:1 on doc0 ({len(s[0]['words'])}) -- per-WORD boxes, "
       f"which is what makes its recall the same quantity as FUNSD's")
    return f, s, ns


# ==========================================================================
# 2. PooledTestSet, executed
# ==========================================================================

def section_pooled(g, f, s, ns):
    print("\n" + "=" * 74)
    print("2. PooledTestSet -- EXECUTED against the real splits")
    print("=" * 74)

    blk = slice_block(g[9], "class PooledTestSet", "class DocumentDataset",
                      "cell 9 PooledTestSet")
    from datasets import load_dataset
    ns = dict(ns)
    ns["load_dataset"] = load_dataset
    exec(compile(blk, "<cell9-pooled>", "exec"), ns)
    Pooled = ns["PooledTestSet"]
    note(f"spliced and exec'd {len(blk.splitlines())} lines verbatim")

    specs = [("funsd", "nielsr/funsd", "test"), ("sroie", "sizhkhy/SROIE", "test")]
    p = Pooled(specs)

    ck(len(p) == 397, f"len(pooled) == {len(p)}")
    ck(p.counts() == {"funsd": 50, "sroie": 347}, f"per-corpus counts {p.counts()}")
    ck(len(p) >= 307, f"n={len(p)} clears T1 s6's n >~ 307, so `res <= 1.0 pt` and "
                      f"therefore the FREE verdict are REACHABLE for the first time")

    # corpus tagging -- the field T1 s5 needs
    ck(p[0]["corpus"] == "funsd" and p[49]["corpus"] == "funsd",
       "documents 0..49 are tagged funsd")
    ck(p[50]["corpus"] == "sroie" and p[396]["corpus"] == "sroie",
       "documents 50..396 are tagged sroie")
    tags = [p.index[k][0] for k in range(len(p))]
    ck(tags == sorted(tags),
       "the pool is BLOCKED by corpus, not interleaved -- so a per-corpus slice of any "
       "artifact is a contiguous range and FUNSD-only rows stay trivially recoverable")

    # the tag must not collide with a real column
    ck("corpus" not in f.features and "corpus" not in s.features,
       "neither corpus already defines a `corpus` column, so the tag overwrites nothing")

    # identity with the underlying rows -- non-vacuity: prove the wrapper is not
    # returning some other document
    ck(p[0]["words"] == f[0]["words"], "pooled[0] is FUNSD's doc 0 (words match)")
    ck(p[50]["words"] == s[0]["words"], "pooled[50] is SROIE's doc 0 (words match)")
    ck(p[396]["words"] == s[346]["words"], "pooled[396] is SROIE's last doc")
    ck(p[0]["words"] != p[50]["words"],
       "NON-VACUITY: the two probes above are not both matching the same row")

    # iteration order must agree with indexing -- cell 15 enumerates, cell 13 indexes
    it = [r["corpus"] for r in p]
    ck(it == [p[k]["corpus"] for k in range(len(p))],
       "__iter__ order == __getitem__ order (cell 15 enumerates, cell 13 indexes; a "
       "disagreement would mis-label every per-image record)")

    # LAZINESS. A list of eagerly-decoded dicts would hold ~2 GB of PIL images for the
    # whole sweep. Assert the index holds plain (part, row) pairs and nothing decoded.
    ck(all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], int)
           for x in p.index),
       "the index holds only (part, row) integer pairs -- no decoded images retained")
    ck(not any(hasattr(x, "size") for x in p.index),
       "NON-VACUITY: nothing image-like is resident in the index")
    return p


# ==========================================================================
# 3. the random arm
# ==========================================================================

def section_random_arm(g):
    print("\n" + "=" * 74)
    print("3. THE RANDOM ARM -- T1 s8 / T3 s6's promoted BLOCKER")
    print("=" * 74)
    c15 = g[15]

    mc = re.search(r"^MERGE_CONFIGS = \[.*?^\]", c15, re.S | re.M).group(0)
    rows = ast.literal_eval(re.sub(r"^\s*#.*$", "", mc.split("=", 1)[1].strip(),
                                   flags=re.M))
    em = re.search(r"^EXPECTED_M = \{.*?^\}", c15, re.S | re.M).group(0)
    exp = ast.literal_eval(re.sub(r"^\s*#.*$", "", em.split("=", 1)[1].strip(),
                                  flags=re.M))

    arm = [r for r in rows if r[2] == "random"]
    ck(len(arm) == 1, f"exactly one random row in MERGE_CONFIGS: {arm}")
    label, keep, mode, merge, split = arm[0]
    key = (keep, mode, merge, split)
    ck(key in exp, f"EXPECTED_M declares the arm {key}")
    ck(exp[key] == 1920, f"the random arm is at M={exp[key]}")

    # THE point of the arm: it must sit at the pre-registered primary's OWN budget.
    # Checked against EXPECTED_M's literals rather than recomputed from keep*4800, so
    # this tests the table the notebook asserts against at runtime.
    prim_t = (0.50, "ink", 0.20, "checkerboard")
    prim_c = (0.40, "ink", 0.00, "checkerboard")
    ck(exp[prim_t] == exp[prim_c] == exp[key] == 1920,
       f"token-matched to BOTH arms of T1 s1's primary "
       f"(`keep=0.50 m=0.20 ink` and `keep=0.40 ink TWIN`) at M=1920")

    # the gap this closes, re-derived from the table rather than cited from D14
    merge_b = sorted({v for k, v in exp.items() if k[2] > 0})
    prune_b = sorted({v for k, v in exp.items() if k[2] == 0 and k[1] != "random"})
    rand_b = sorted({v for k, v in exp.items() if k[1] == "random"})
    note(f"merge budgets {merge_b} | prune-twin budgets {prune_b} | random {rand_b}")
    ck(set(rand_b) & set(merge_b) == {1920},
       "the random budget now INTERSECTS the merge budgets at 1920 -- in runs 13/14 "
       "that intersection was EMPTY, so 'merging beats random at matched M' was not "
       "computable from either run at all")

    # reproducibility: cell 15 reseeds per row, so the masks repeat across re-runs
    ck("SELECTION_SEED = 0" in c15, "SELECTION_SEED is declared")
    ck(c15.count("torch.manual_seed(SELECTION_SEED)") >= 1,
       "cell 15 reseeds from SELECTION_SEED inside the per-row loop -- src/model.py's "
       "random branch draws from the AMBIENT RNG, so without this the arm would not "
       "reproduce")

    import torch
    torch.manual_seed(0)
    a = torch.rand(1, 4800)
    torch.manual_seed(0)
    b = torch.rand(1, 4800)
    torch.manual_seed(1)
    c = torch.rand(1, 4800)
    ck(torch.equal(a, b), "same seed -> bit-identical mask scores (the arm reproduces)")
    ck(not torch.equal(a, c),
       "NON-VACUITY: a different seed gives different scores, so the equality above is "
       "not an artifact of a degenerate RNG")

    # the sabotage row must NOT have been duplicated -- Conventions: a question closed
    # by three nulls is closed
    sab = [r for r in rows if r[4] == "rank_parity"]
    ck(len(sab) == 1,
       f"the tome_split sabotage row is still exactly 1 ({len(sab)}) -- runs 12/13/14 "
       f"already paid for it three times and a fourth changes nothing")
    return label


# ==========================================================================
# 4. canonical parity
# ==========================================================================

def section_canonical_parity():
    print("\n" + "=" * 74)
    print("4. CANONICAL PARITY -- the canonical notebook must stay FUNSD-only")
    print("=" * 74)
    c = cells(CANON)
    joined = "\n".join(c)
    ck("PooledTestSet" not in joined,
       "the canonical notebook has NO PooledTestSet -- runs 2-6 still reproduce")
    ck("sizhkhy/SROIE" not in joined,
       "the canonical notebook never names SROIE")
    ck("EVAL_CORPORA" not in joined,
       "the pooled config exists only in the generated notebook and its generator")
    ck(joined.count("load_dataset('nielsr/funsd', split='test')") >= 1,
       "NON-VACUITY: the canonical notebook does still load FUNSD test, so the three "
       "absences above are a deliberate split and not an empty file")


# ==========================================================================
# 5. the per-corpus aggregate, executed
# ==========================================================================

def section_aggregate(g):
    print("\n" + "=" * 74)
    print("5. PER-CORPUS AGGREGATE -- spliced from cell 15 and EXECUTED")
    print("=" * 74)
    import numpy as np

    blk = slice_block(g[15], "    _by_corpus = {}", "    return {",
                      "cell 15 per-corpus aggregate")
    # The block lives inside the sweep function, so it arrives indented. dedent is
    # whitespace-only -- it preserves every token, so this is still the shipped code
    # under test rather than a restatement of it.
    blk = textwrap.dedent(blk)
    note(f"spliced {len(blk.splitlines())} lines verbatim from the sweep function "
         f"(dedented only; no token changed)")

    # a synthetic per_image with a KNOWN per-corpus split, so the decomposition is
    # checkable by construction rather than by eyeballing a plausible number
    per_image = (
        [{"corpus": "funsd", "recall": 0.80, "ned": 0.30, "word_order": 0.50,
          "gen_tokens": 300} for _ in range(50)]
        + [{"corpus": "sroie", "recall": 0.40, "ned": 0.60, "word_order": 0.20,
            "gen_tokens": 200} for _ in range(347)])
    ns = {"per_image": per_image, "np": np}
    exec(compile(blk, "<cell15-aggregate>", "exec"), ns)
    pc = ns["per_corpus"]

    ck(set(pc) == {"funsd", "sroie"}, f"aggregate keys {sorted(pc)}")
    ck(pc["funsd"]["n"] == 50 and pc["sroie"]["n"] == 347,
       f"per-corpus n: funsd {pc['funsd']['n']}, sroie {pc['sroie']['n']}")
    ck(abs(pc["funsd"]["word_recall_pct"] - 80.0) < 1e-9,
       f"FUNSD slice recovers its own recall exactly ({pc['funsd']['word_recall_pct']:.4f})")
    ck(abs(pc["sroie"]["word_recall_pct"] - 40.0) < 1e-9,
       f"SROIE slice recovers its own recall exactly ({pc['sroie']['word_recall_pct']:.4f})")

    # THE property that makes FUNSD-only rows comparable to runs 13/14 without a re-run
    pooled = float(np.mean([p["recall"] for p in per_image]) * 100.0)
    recomb = (pc["funsd"]["word_recall_pct"] * 50 + pc["sroie"]["word_recall_pct"] * 347) / 397
    ck(abs(pooled - recomb) < 1e-9,
       f"the per-corpus slices DECOMPOSE the pooled figure "
       f"({recomb:.6f} vs {pooled:.6f}) -- so the artifact cannot report a pooled number "
       f"that its own strata contradict")
    ck(abs(pooled - pc["funsd"]["word_recall_pct"]) > 1.0,
       f"NON-VACUITY: pooled ({pooled:.1f}) differs from the FUNSD slice "
       f"({pc['funsd']['word_recall_pct']:.1f}) by {pooled - pc['funsd']['word_recall_pct']:+.1f} "
       f"pts -- the decomposition above is not two copies of one number")

    # charAcc must stay the affine map of NED that T1 s4 relies on
    ck(abs(pc["funsd"]["character_accuracy_pct"] - (1 - 0.30) * 100) < 1e-9,
       "per-corpus charAcc is (1 - mean ned) x 100, the same affine map T1 s4 uses to "
       "justify a family of THREE quantities rather than four")

    # the default for an untagged record -- historical artifacts have no corpus field
    ns2 = {"per_image": [{"recall": 0.5, "ned": 0.5, "word_order": 0.5,
                          "gen_tokens": 1} for _ in range(3)], "np": np}
    exec(compile(blk, "<cell15-aggregate>", "exec"), ns2)
    ck(set(ns2["per_corpus"]) == {"funsd"},
       "an untagged per_image defaults to 'funsd' -- runs 13/14's artifacts remain "
       "readable by the same code path")

    # 87.4% receipts, the distribution-shift warning T4 records, computed not quoted
    share = 347 / 397 * 100
    note(f"the pool is {share:.1f}% receipts by document -- a 'pooled' number is "
         f"substantially a RECEIPT number, and FUNSD (every result from runs 2-14) is "
         f"a {50 / 397 * 100:.1f}% minority in its own successor. Never report the "
         f"pooled figure alone.")


def main() -> int:
    print("=" * 74)
    print("VERIFY PATCH I -- pooled eval corpus, corpus labels, token-matched random arm")
    print("=" * 74)
    g = cells(GEN)
    rows = section_structural(g)
    f, s, ns = section_adapter(g)
    section_pooled(g, f, s, ns)
    label = section_random_arm(g)
    section_canonical_parity()
    section_aggregate(g)

    print("\n" + "=" * 74)
    print(f"CONTROLS: {_n - _f}/{_n} PASS   |   sweep is {rows} rows, new arm `{label}`")
    print("=" * 74)
    return 1 if _f else 0


if __name__ == "__main__":
    sys.exit(main())
