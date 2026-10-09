"""Audit every numeric figure in report/report.tex.

Why this exists: `scripts/check_writeup_numbers.py` audits WRITEUP.md and knows nothing
about report/report.tex, so the attachable PDF would otherwise be the one derived document
with no numeric audit -- the gap AGENTS.md records for STORY.md.

THREE SECTIONS, in descending order of how much a green is worth:

  1. TARGETED (the real audit). ~50 load-bearing figures, each RE-DERIVED from a named
     field of a named artifact and then required to be PRESENT in report.tex. Corrupting
     any headline figure turns this red. This is the section that makes the green mean
     something.

  2. SWEEP (a backstop, and a weak one -- its false-pass rate is MEASURED and printed).
     Every remaining figure in the report must exist somewhere in results/*.json or in a
     tracker file. Catches a figure invented out of nothing; does NOT catch a figure
     swapped for another real figure.

  3. NON-VACUITY CONTROLS, including a self-sabotage: the script mutates its own copy of
     the report in memory and asserts section 1 goes red. A check that cannot be shown to
     fail is decorative, and this one was -- see the history note below.

HISTORY -- this script's own two defects, both found by running it rather than reading it:

  (a) Tier 1 began as a SUBSTRING match against the JSON, which stores full float
      precision. The selection table's four `random` cells: 62.77 / 37.20 / 33.80 PASSED
      against 62.77... / 37.2... / 33.8... because those round by *truncation*; 51.84
      FAILED against the stored 51.838991011355475. Three of four sibling figures were
      being decided by luck and the fourth by arithmetic -- and the one that failed was
      CORRECT. Fixed by rounding each stored value to the figure's own decimal count.

  (b) The existence sweep PASSED A CORRUPTED HEADLINE. Mutating the report's headline
      recall 77.37 -> 77.31 left the script at exit 0, because 77.31 happens to appear
      once in AGENTS-ARCHIVE-RUNS.md in an unrelated merge table. Measured false-pass
      rate: 5% of random 2-decimal values in [30,90] clear the existence bar. That is a
      decorative check being reported as an audit, which is exactly the failure mode
      AGENTS.md's Conventions warn about ("ask what a FAILING system would score"). Fixed
      by adding section 1 and by making section 3 sabotage section 1 on every run.

SCOPE LIMIT, and it is not closable by any script here: this checks ARITHMETIC AND
PRESENCE, never whether the sentence around a figure is still the project's position. A
withdrawn verdict whose numbers still reproduce passes everything below -- the defect that
sat under a green `check_writeup_numbers.py` for 11 days. Only a human read catches that.

Usage:
    python scripts/check_report_numbers.py
Exit 0 iff section 1 has no failures, section 2 has no unsourced figures, and every
control in section 3 holds.
"""
import glob
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "report", "report.tex")
TRACKERS = [
    "AGENTS.md",
    "AGENTS-ARCHIVE-DIAGNOSTICS.md",
    "AGENTS-ARCHIVE-RUNS.md",
    "AGENTS-ARCHIVE-CHANGELOG.md",
]
MiB = 1048576.0

passed = 0
failed = []


def ok(label, detail=""):
    global passed
    passed += 1
    print(f"  [PASS] {label}" + (f"   {detail}" if detail else ""))


def bad(label, detail=""):
    failed.append(label)
    print(f"  [FAIL] {label}" + (f"   {detail}" if detail else ""))


# ----------------------------------------------------------------------------- sources
# A shrunken source set is how this check would go quietly useless -- the 2026-09-24 split
# broke check_writeup_numbers.py exactly that way. Raise rather than audit against less.
tracker_parts = []
for name in TRACKERS:
    p = os.path.join(ROOT, name)
    assert os.path.exists(p), f"tracker missing, refusing to audit against a partial corpus: {name}"
    tracker_parts.append(open(p, encoding="utf-8").read())
tracker_corpus = "\n".join(tracker_parts)

artifact_values = []
artifact_files = 0


def _walk(node):
    """Collect numeric leaves. bool subclasses int -- exclude it explicitly."""
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        artifact_values.append(float(node))
    elif isinstance(node, dict):
        for v in node.values():
            _walk(v)
    elif isinstance(node, list):
        for v in node:
            _walk(v)


for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
    try:
        obj = json.load(open(p, encoding="utf-8"))
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [warn] skipped unreadable artifact {os.path.basename(p)}: {exc}")
        continue
    artifact_files += 1
    _walk(obj)

assert artifact_values, "no readable results/*.json -- refusing to audit against prose alone"
# Rounded at the figure's own precision, never substring -- see history note (a).
ROUNDED = {d: {f"{v:.{d}f}" for v in artifact_values} for d in range(0, 5)}

D12 = json.load(open(os.path.join(ROOT, "results", "why_pruning_helps_local.json"), encoding="utf-8"))
D11 = json.load(open(os.path.join(ROOT, "results", "budget_binding_local.json"), encoding="utf-8"))
M1 = json.load(open(os.path.join(ROOT, "results", "kv_memory_local.json"), encoding="utf-8"))

report_src = open(REPORT, encoding="utf-8").read()


def normalise(tex):
    """Strip LaTeX so a bare numeral in the source is findable as a bare numeral.

    Order matters: `{,}` (the thousands separator in `4{,}800`) must go BEFORE braces are
    stripped, or the number becomes `4 , 800` and no needle matches it.
    """
    s = re.sub(r"(?m)^\s*%.*$", " ", tex)       # comments: never claims
    s = s.replace("{,}", "")                     # 4{,}800 -> 4800
    s = s.replace("\\,", "").replace("\\ ", "")  # thin space inside 52.50\,MiB
    s = re.sub(r"\\[a-zA-Z]+", " ", s)           # \textbf \bm \times ...
    s = s.replace("{", " ").replace("}", " ").replace("$", " ")
    return s


REPORT_NORM = normalise(report_src)


def present(needle, text=None):
    """Is this exact numeral in the report? Guarded so -0.26 does not match -0.265."""
    hay = REPORT_NORM if text is None else text
    return re.search(r"(?<![\d.])" + re.escape(needle) + r"(?![\d])", hay) is not None


# --------------------------------------------------------------- derivations from artifacts
def d12_row(ck_sub, keep, field="word_recall_pct"):
    for r in D12["rows"]:
        if ck_sub in r["checkpoint"] and abs(r["keep_ratio"] - keep) < 1e-9:
            return r[field]
    raise KeyError((ck_sub, keep, field))


def d11_row(mode, keep, field="word_recall_pct"):
    for r in D11["rows"]:
        if r.get("select_mode") == mode and abs(r["keep_ratio"] - keep) < 1e-9 \
                and "run 9" in r.get("checkpoint", ""):
            return r[field]
    raise KeyError((mode, keep, field))


def paired(a, b):
    """mean difference in POINTS, its SE, and the paired t."""
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    se = sd / math.sqrt(n)
    return m * 100.0, se * 100.0, m / se


def m1_bytes(vt, keep=None):
    for r in M1["rows"]:
        if r["visual_tokens"] == vt and (keep is None or abs(r["keep_ratio"] - keep) < 1e-9):
            return r["cross_kv_bytes_analytic"]
    raise KeyError(vt)


BUDGETS = (0.50, 0.35, 0.25, 0.20)


def build_targeted():
    """Every load-bearing figure: (label, needle, provenance). Derived, never transcribed."""
    checks = []

    # -- the architecture constants the whole report rests on
    checks.append(("grid: 4800 visual tokens", "4800", "80x60 token grid"))
    for keep in BUDGETS:
        vt = int(round(keep * 4800))
        checks.append((f"visual tokens @ keep={keep:.2f}", str(vt), f"{keep} x 4800"))

    # -- section 2 budget table: recall levels, run 9, select_mode=ink  (D12)
    base9 = d12_row("run 9", 1.0)
    checks.append(("budget table: unpruned ceiling", f"{base9:.2f}",
                   "D12 run 9 keep=1.00 word_recall_pct"))
    for keep in BUDGETS:
        checks.append((f"budget table: recall @ keep={keep:.2f}", f"{d12_row('run 9', keep):.2f}",
                       f"D12 run 9 keep={keep} word_recall_pct"))

    # -- section 2 budget table: deltas and paired t, re-derived from per-image arrays
    p9base = d12_row("run 9", 1.0, "per_image_recall")
    for keep in BUDGETS:
        m, se, t = paired(d12_row("run 9", keep, "per_image_recall"), p9base)
        checks.append((f"budget table: delta @ keep={keep:.2f}", f"{m:+.2f}",
                       "D12 paired per-image vs own keep=1.00"))
        checks.append((f"budget table: t @ keep={keep:.2f}", f"{t:.2f}",
                       "D12 paired t, n=50"))

    # -- section 2: the minimum detectable effect on the two free rows.
    #    READ meta.resolution_pts, do NOT recompute as 1.96*SE. The project's convention is
    #    2*SE (2 x 1.3822 = 2.764, 2 x 1.4074 = 2.815), and my first version of this check
    #    used 1.96*SE, derived 2.71/2.76, and reported the REPORT as wrong. The report was
    #    right. "Suspect the verifier first" -- re-derive from the named field, not from a
    #    convention you assumed the project shares.
    res = D12["meta"]["resolution_pts"]
    for keep in (0.50, 0.35):
        key = next(k for k in res if "run 9" in k and k.endswith(f"|{keep:g}"))
        checks.append((f"budget table: MDE @ keep={keep:.2f}", f"{res[key]:.2f}",
                       f"D12 meta.resolution_pts[{key!r}] (= 2 x paired SE)"))

    # -- section 2: cross-attention KV, analytic bytes -> MiB and percentage  (M1)
    base_kv = m1_bytes(4800)
    checks.append(("KV: unpruned MiB", f"{base_kv / MiB:.2f}", "M1 cross_kv_bytes_analytic @4800"))
    for keep in BUDGETS:
        vt = int(round(keep * 4800))
        by = m1_bytes(vt, keep)
        checks.append((f"KV: MiB @ keep={keep:.2f}", f"{by / MiB:.2f}",
                       f"M1 cross_kv_bytes_analytic @{vt}"))
        checks.append((f"KV: pct vs unpruned @ keep={keep:.2f}", f"{100 * (by / base_kv - 1):+.1f}",
                       "M1 analytic ratio"))
    # cross-KV as a share of the 771 MiB parameter budget
    checks.append(("KV: share of 771 MiB params", f"{100 * base_kv / (771 * MiB):.2f}",
                   "M1 analytic @4800 / 771 MiB"))
    # the prune+merge row, and the decomposition the report is required to state.
    # NOTE: the 60.00 MiB level at M=1920 is deliberately NOT required -- the report states
    # the RATIOS and never the level, and demanding a figure the report has no reason to
    # print is an over-specified check, not a finding about the report.
    kv1920 = m1_bytes(1920, 0.50)
    checks.append(("KV: combined ratio at M=1920", f"{base_kv / kv1920:.2f}", "M1 150.00/60.00 MiB"))
    checks.append(("KV: merge-step-alone ratio", f"{m1_bytes(2400, 0.50) / kv1920:.2f}",
                   "M1 2400/1920 -- the report MUST separate this from the 2.50x"))

    # -- section 3 selection-value table: router, random, margin  (D11)
    for keep in BUDGETS:
        r_router = d11_row("router", keep)
        r_random = d11_row("random", keep)
        checks.append((f"selection table: router @ keep={keep:.2f}", f"{r_router:.2f}",
                       f"D11 run 9 router keep={keep}"))
        checks.append((f"selection table: random @ keep={keep:.2f}", f"{r_random:.2f}",
                       f"D11 run 9 random keep={keep}"))
        checks.append((f"selection table: margin @ keep={keep:.2f}", f"{r_router - r_random:+.1f}",
                       "D11 router minus random, same budget"))

    # -- section 4 difference-in-differences table  (D12, both checkpoints)
    p5base = d12_row("run 5", 1.0, "per_image_recall")
    for keep in BUDGETS:
        m5, _, _ = paired(d12_row("run 5", keep, "per_image_recall"), p5base)
        m9, _, _ = paired(d12_row("run 9", keep, "per_image_recall"), p9base)
        checks.append((f"DiD table: trained-unpruned delta @ keep={keep:.2f}", f"{m5:+.2f}",
                       f"D12 run 5 paired vs own keep=1.00"))
        # DiD column sign in the report is (unpruned-trained) - (pruning-trained)
        d5 = [x - y for x, y in zip(d12_row("run 5", keep, "per_image_recall"), p5base)]
        d9 = [x - y for x, y in zip(d12_row("run 9", keep, "per_image_recall"), p9base)]
        dd = [x - y for x, y in zip(d5, d9)]
        n = len(dd)
        mm = sum(dd) / n
        sdd = math.sqrt(sum((x - mm) ** 2 for x in dd) / (n - 1))
        checks.append((f"DiD table: DiD @ keep={keep:.2f}", f"{mm * 100:+.2f}",
                       "D12 (run5 delta - run9 delta), paired"))
        checks.append((f"DiD table: t @ keep={keep:.2f}", f"{mm / (sdd / math.sqrt(n)):.2f}",
                       "D12 paired t on the DiD, n=50"))

    # -- the closing sentence: the headline delta and its standard error
    m, se, _ = paired(d12_row("run 9", 0.35, "per_image_recall"), p9base)
    checks.append(("closing line: headline delta", f"{m:+.2f}", "D12 keep=0.35 paired mean"))
    checks.append(("closing line: its standard error", f"{se:.2f}",
                   "1 x paired SE -- NOT 1.96; the report must label which"))

    return checks


def run_targeted(label_prefix, norm_text, announce=True):
    """Returns (n_pass, failures). Used twice: on the real report, and on a sabotaged copy."""
    npass, fails = 0, []
    for label, needle, prov in build_targeted():
        if present(needle, norm_text):
            npass += 1
            if announce:
                ok(f"{label} = {needle}", prov)
        else:
            fails.append((label, needle, prov))
            if announce:
                bad(f"{label} = {needle} NOT IN REPORT", prov)
    return npass, fails


# ============================================================================== section 1
print("=" * 78)
print("report/report.tex -- numeric audit")
print("=" * 78)
print(f"artifacts : {artifact_files} results/*.json ({len(artifact_values):,} numeric leaves)")
print(f"trackers  : {len(TRACKERS)} ({len(tracker_corpus):,} chars)")
print()
print("-" * 78)
print("SECTION 1 -- TARGETED: each figure re-derived from a named artifact field")
print("-" * 78)
t_pass, t_fails = run_targeted("targeted", REPORT_NORM)
for label, needle, prov in t_fails:
    failed.append(label)
passed += t_pass
print(f"\n  section 1: {t_pass} re-derived figures present, {len(t_fails)} missing")

# ============================================================================== section 2
print()
print("-" * 78)
print("SECTION 2 -- SWEEP (backstop): every other figure must exist in SOME source")
print("-" * 78)

body = report_src.split(r"\begin{document}", 1)[1]
body = re.sub(r"(?m)^\s*%.*$", " ", body)
body = re.sub(r"\\(?:vspace|hspace|titlespacing|setlist|hrule|definecolor|usepackage"
              r"|documentclass|rule|enlargethispage|geometry)\s*(\*)?(\[[^\]]*\])?(\{[^{}]*\})*", " ", body)
body = re.sub(r"\d+(\.\d+)?\s*(cm|em|ex|pt|mm|in|bp|sp)\b", " ", body)

raw = set()
for m in re.finditer(r"\d+\.\d+", body):
    raw.add(m.group(0))
for m in re.finditer(r"(?<![\d.])\d{3,}(?![\d.])", body):
    raw.add(m.group(0))

IGNORE = {"2026", "8766"}
TARGETED_NEEDLES = {n for _, n, _ in build_targeted()}


def variants(fig):
    v = {fig}
    if len(fig) == 4 and fig.isdigit():
        v.add(f"{fig[0]},{fig[1:]}")
        v.add(f"{fig[0]}{{,}}{fig[1:]}")
    return v


def in_artifacts(fig):
    d = len(fig.split(".")[1]) if "." in fig else 0
    return d <= 4 and fig in ROUNDED[d]


sweep_art, sweep_prose, sweep_missing, sweep_skipped = [], [], [], []
for fig in sorted(raw, key=lambda s: (len(s), s)):
    if fig in IGNORE:
        continue
    if fig in TARGETED_NEEDLES or fig.lstrip("+-") in TARGETED_NEEDLES:
        sweep_skipped.append(fig)
        continue
    if in_artifacts(fig):
        sweep_art.append(fig)
    elif any(v in tracker_corpus for v in variants(fig)):
        sweep_prose.append(fig)
    else:
        sweep_missing.append(fig)

print(f"  figures already covered by section 1 : {len(sweep_skipped)}")
print(f"  backed by a measured artifact        : {len(sweep_art)}")
print(f"  backed by tracker prose only         : {len(sweep_prose)}")
print(f"  unsourced                            : {len(sweep_missing)}")
if sweep_prose:
    print("\n  resting on PROSE rather than on a measurement (an eye is warranted --")
    print("  prose is where a transcription error survives):")
    for fig in sweep_prose:
        print(f"    [prose] {fig}")
if sweep_missing:
    print()
    for fig in sweep_missing:
        m = re.search(r".{0,70}" + re.escape(fig) + r".{0,70}", body, re.S)
        ctx = " ".join(m.group(0).split()) if m else "(context not recovered)"
        bad(f"unsourced figure {fig}", f"...{ctx}...")

# ============================================================================== section 3
print()
print("-" * 78)
print("SECTION 3 -- NON-VACUITY: can any of the above actually fail?")
print("-" * 78)

# C1: a sentinel must match nothing, anywhere.
SENTINEL = "77.7777"
if not in_artifacts(SENTINEL) and SENTINEL not in tracker_corpus:
    ok("C1 sentinel 77.7777 matches no source", "the sweep matcher can report absence")
else:
    bad("C1 sentinel leaked into a source", "the sweep matcher can no longer fail")

# C2: the rounding matcher resolves a figure whose stored form is NOT its prefix.
#     This is history note (a) pinned so the substring form cannot come back.
if in_artifacts("51.84"):
    ok("C2 rounding control: 51.84 resolves from stored 51.838991...",
       "a substring matcher FAILS this")
else:
    bad("C2 rounding regression", "51.84 no longer resolves -- substring matching is back")

# C3: SELF-SABOTAGE. Mutate the headline recall in a copy and require section 1 to go red.
#     This is history note (b): the previous version of this script passed exactly this
#     mutation, because 77.31 occurs by coincidence in an archive.
head = f"{d12_row('run 9', 0.35):.2f}"
assert present(head), f"headline {head} not in report -- cannot run the sabotage control"
sabotaged = REPORT_NORM.replace(head, "77.31")
_, sab_fails = run_targeted("sabotage", sabotaged, announce=False)
if sab_fails:
    ok(f"C3 self-sabotage: headline {head} -> 77.31 breaks section 1",
       f"{len(sab_fails)} targeted check(s) go red, incl. {sab_fails[0][0]!r}")
else:
    bad("C3 SELF-SABOTAGE PASSED", "section 1 cannot detect a corrupted headline")

# C4: and the thing that makes C3 worth running -- show the SWEEP alone would NOT catch it.
sweep_would_catch = not (in_artifacts("77.31") or "77.31" in tracker_corpus)
if not sweep_would_catch:
    ok("C4 the sweep alone would MISS that corruption",
       "77.31 occurs in a tracker by coincidence -- section 1 is what catches it")
else:
    ok("C4 the sweep would also have caught it", "section 1 is still the stronger check")

# C5: measure, rather than assert, how weak the sweep is. Deterministic LCG -- Math.random
#     equivalents are avoided so this number is reproducible run to run.
seed, hits, N = 20261008, 0, 500
samples = []
for _ in range(N):
    seed = (1103515245 * seed + 12345) % (2 ** 31)
    samples.append(f"{30 + 60 * (seed / (2 ** 31)):.2f}")
for s in samples:
    if in_artifacts(s) or s in tracker_corpus:
        hits += 1
print(f"  [info] C5 sweep false-pass rate: {hits}/{N} = {100 * hits / N:.1f}% of random "
      f"2dp values in [30,90] clear the EXISTENCE bar")
print("         -> section 2 is a backstop, not an audit. Section 1 is the audit.")

# C6: CALIBRATION. This script recomputes every delta/SE/t from per_image_recall with its
#     own paired() helper. D12 also STORES those three quantities in curve_vs_unpruned.
#     Assert the two agree -- otherwise section 1 is auditing the report against my
#     reimplementation rather than against the project's measurement. Same family as
#     AGENTS.md's rule: when re-deriving a recorded value, re-derive it and assert it.
cal_bad = []
for stored in D12["curve_vs_unpruned"]:
    ck, keep = stored["checkpoint"], stored["keep_ratio"]
    base = d12_row("run 9" if "run 9" in ck else "run 5", 1.0, "per_image_recall")
    m, se, t = paired(d12_row("run 9" if "run 9" in ck else "run 5", keep, "per_image_recall"), base)
    for name, mine, theirs in (("delta_pts", m, stored["delta_pts"]),
                               ("se_pts", se, stored["se_pts"]),
                               ("t", t, stored["t"])):
        if abs(mine - theirs) > 1e-9:
            cal_bad.append(f"{ck}|{keep} {name}: mine {mine!r} vs stored {theirs!r}")
if cal_bad:
    bad("C6 calibration: my paired() disagrees with D12's stored fields", "; ".join(cal_bad[:3]))
else:
    ok(f"C6 calibration: paired() reproduces all {3 * len(D12['curve_vs_unpruned'])} stored "
       f"delta/SE/t values to 1e-9", "section 1 audits against the measurement, not my restatement")

# ============================================================================== verdict
print()
print("=" * 78)
print(f"TOTAL: {passed} passed, {len(failed)} failed")
print("=" * 78)
if failed:
    print()
    for f in failed:
        print(f"  FAILED: {f}")
    print(f"\n{len(failed)} CHECK(S) FAILED")
    sys.exit(1)

print()
print("Every load-bearing figure in the report re-derives from a named artifact field,")
print("and a corrupted headline is proven to break this check (control C3).")
print()
print("SCOPE LIMIT -- do not over-read this green: it establishes arithmetic and presence,")
print("NOT that the sentence around any figure is still the project's position. A withdrawn")
print("verdict whose numbers still reproduce passes everything above. Only a human read of")
print("the prose catches that, which is why AGENTS.md wins on any disagreement.")
sys.exit(0)
