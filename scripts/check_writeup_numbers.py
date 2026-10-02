"""Re-derive every number quoted in WRITEUP.md from the artifacts that produced them.

A writeup is the one document in this project with no execution behind it, and the failure
mode is silent: a figure that was right when typed stays in the file after the run that
produced it is superseded. That has already happened here once -- an audit of claims against
artifacts found the write-up still carrying numbers the artifacts no longer supported -- and
REPORT.md/README.md needed a second reconcile on 2026-09-09 for the same reason.

So this script parses WRITEUP.md's two result tables and its inline claims, and asserts each
against results/*.json. It does NOT read AGENTS.md: prose checked against prose proves
nothing. Every figure is traced to the JSON a script wrote.

Sources:
    results/budget_binding_local.json      D11 -- router vs random, latency framing
    results/why_pruning_helps_local.json   D12 -- run 5 vs run 9 curves, DiD, power
    results/kv_memory_local.json           M1  -- cross-attention KV bytes

Usage:
    python scripts/check_writeup_numbers.py [writeup.md]
Exit 0 iff every quoted number is reproduced. A one-digit edit to WRITEUP.md must fail this.
"""
import json
import os
import re
import sys

# This script prints non-ASCII (>=, times signs) in check labels, and Windows'
# default console codec is cp1252. Without this, the run dies mid-way with
# UnicodeEncodeError and exit code 1 -- IDENTICAL to a real numeric failure, but
# after only ~50 of 134 checks, so 84 never run and the exit code lies about why.
# Reconfigure rather than document a PYTHONIOENCODING prefix: a checker whose
# correct invocation is easy to forget is a checker that gets misread.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "WRITEUP.md")
MIB = 1024.0 * 1024.0

npass = nfail = 0


def check(ok, label, detail=""):
    global npass, nfail
    if ok:
        npass += 1
    else:
        nfail += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""))
    return ok


def close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def load(name):
    with open(os.path.join(ROOT, "results", name), encoding="utf-8") as fh:
        return json.load(fh)


d11, d12, m1 = (load("budget_binding_local.json"),
                load("why_pruning_helps_local.json"),
                load("kv_memory_local.json"))
doc = open(DOC, encoding="utf-8").read()
# The writeup is prose: normalise the typographic minus so "-6.03" and "−6.03" compare.
norm = doc.replace("−", "-").replace("–", "-")


def cells(line):
    return [c.strip().replace("*", "").replace("`", "") for c in line.strip("|").split("|")]


def rows_of(header_startswith):
    """The body rows of the first markdown table whose header line starts as given."""
    lines = norm.splitlines()
    for i, l in enumerate(lines):
        if l.startswith(header_startswith):
            out = []
            for body in lines[i + 2:]:
                if not body.startswith("|"):
                    break
                out.append(cells(body))
            return out
    return []


def num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def d12_curve(ckpt_sub, keep):
    for r in d12["curve_vs_unpruned"]:
        if ckpt_sub in r["checkpoint"] and abs(r["keep_ratio"] - keep) < 1e-9:
            return r
    return None


def d12_row(ckpt_sub, keep):
    for r in d12["rows"]:
        if ckpt_sub in r["checkpoint"] and abs(r["keep_ratio"] - keep) < 1e-9:
            return r
    return None


def d11_row(ckpt_sub, keep, mode):
    for r in d11["rows"]:
        if (ckpt_sub in r["checkpoint"] and abs(r["keep_ratio"] - keep) < 1e-9
                and r["select_mode"] == mode):
            return r
    return None


def m1_row(keep):
    return next((r for r in m1["rows"] if abs(r["keep_ratio"] - keep) < 1e-9), None)


print("=" * 74)
print(f"1. THE BUDGET TABLE  ({os.path.basename(DOC)}, section 2)")
print("=" * 74)

budget = rows_of("| keep | visual tokens | cross-attn KV |")
check(len(budget) == 5, "budget table has five rows", f"{len(budget)} found")
unpruned_kv = m1_row(1.00)["cross_kv_bytes_observed"] / MIB
for row in budget:
    keep = num(row[0])
    mr = m1_row(keep)
    d12r, d12c = d12_row("9", keep), d12_curve("9", keep)
    kv_mib = mr["cross_kv_bytes_observed"] / MIB

    check(num(row[1]) == mr["visual_tokens"],
          f"keep={keep:.2f} token count", f"{row[1]} vs {mr['visual_tokens']}")
    check(close(num(row[2]), kv_mib, 0.005),
          f"keep={keep:.2f} cross-attn KV MiB", f"{row[2]} vs {kv_mib:.2f}")
    if keep < 1.0:
        pct = 100.0 * (1.0 - kv_mib / unpruned_kv)
        quoted_pct = num(row[2].split("(")[1]) if "(" in row[2] else None
        check(close(abs(quoted_pct), pct, 0.05),
              f"keep={keep:.2f} KV reduction %", f"{quoted_pct} vs -{pct:.1f}")
        check(close(num(row[4]), d12c["delta_pts"], 0.005),
              f"keep={keep:.2f} recall delta", f"{row[4]} vs {d12c['delta_pts']:.2f}")
        check(close(num(row[5]), d12c["t"], 0.005),
              f"keep={keep:.2f} t", f"{row[5]} vs {d12c['t']:.2f}")
    check(close(num(row[3]), d12r["word_recall_pct"], 0.005),
          f"keep={keep:.2f} word recall", f"{row[3]} vs {d12r['word_recall_pct']:.2f}")

# The two "free" rows carry a power figure. A flat row without one is not a null.
for keep in (0.50, 0.35):
    res = d12["meta"]["resolution_pts"][f"run 9  (trained at keep=0.50)|{keep}"]
    quoted = [r for r in budget if num(r[0]) == keep][0][6]
    check(close(num(quoted), res, 0.005), f"keep={keep:.2f} stated power floor",
          f"{quoted!r} vs {res:.2f}")
    check(abs(d12_curve("9", keep)["t"]) < 2.0, f"keep={keep:.2f} really is flat",
          "a 'free' row whose t clears significance is mislabelled")

print()
print("=" * 74)
print("2. THE SELECTION TABLE (section 3)")
print("=" * 74)

sel = rows_of("| keep | visual tokens | router | random |")
check(len(sel) == 4, "selection table has four rows", f"{len(sel)} found")
for row in sel:
    keep = num(row[0])
    rt, rd = d11_row("run 9", keep, "router"), d11_row("run 9", keep, "random")
    check(num(row[1]) == rt["visual_tokens"], f"keep={keep:.2f} token count")
    check(close(num(row[2]), rt["word_recall_pct"], 0.005),
          f"keep={keep:.2f} router recall", f"{row[2]} vs {rt['word_recall_pct']:.2f}")
    check(close(num(row[3]), rd["word_recall_pct"], 0.005),
          f"keep={keep:.2f} random recall", f"{row[3]} vs {rd['word_recall_pct']:.2f}")
    margin = rt["word_recall_pct"] - rd["word_recall_pct"]
    check(close(num(row[4]), margin, 0.05),
          f"keep={keep:.2f} margin is router-minus-random", f"{row[4]} vs +{margin:.1f}")
    check(num(row[4]) > 0, f"keep={keep:.2f} margin is positive")

print()
print("=" * 74)
print("3. THE DiD TABLE (section 4)")
print("=" * 74)

did = rows_of("| keep | run 5 " + "Δ".replace("Δ", "Δ"))
if not did:
    did = rows_of("| keep | run 5")
check(len(did) == 4, "DiD table has four rows", f"{len(did)} found")
for row in did:
    keep = num(row[0])
    r5, r9 = d12_curve("run 5", keep), d12_curve("9", keep)
    check(close(num(row[1]), r5["delta_pts"], 0.005),
          f"keep={keep:.2f} run 5 delta", f"{row[1]} vs {r5['delta_pts']:.2f}")
    check(close(num(row[2]), r9["delta_pts"], 0.005),
          f"keep={keep:.2f} run 9 delta", f"{row[2]} vs {r9['delta_pts']:.2f}")
    # DiD is asserted to BE the difference of the two deltas, not an independently typed
    # third number -- the arithmetic is the claim.
    check(close(num(row[3]), r5["delta_pts"] - r9["delta_pts"], 0.02),
          f"keep={keep:.2f} DiD == run5 - run9",
          f"{row[3]} vs {r5['delta_pts'] - r9['delta_pts']:.2f}")

check(all(d12_curve("run 5", k)["delta_pts"] < 0 for k in (0.5, 0.35, 0.25, 0.2)),
      "run 5 declines at EVERY budget", "the fact that rejects H2")
check(all(d12_curve("run 5", k)["delta_pts"] > d12_curve("run 5", k2)["delta_pts"]
          for k, k2 in ((0.5, 0.35), (0.35, 0.25), (0.25, 0.2))),
      "run 5's decline is monotone in tightness", "the writeup says 'monotonically'")

print()
print("=" * 74)
print("4. INLINE CLAIMS")
print("=" * 74)

r9_035 = d12_curve("9", 0.35)
checks = [
    ("-0.26 pts of word recall (t -0.18, n=50 paired)",
     close(r9_035["delta_pts"], -0.26, 0.005) and close(r9_035["t"], -0.18, 0.005)
     and d12_row("9", 0.35)["num_eval_samples"] == 50,
     "headline delta, t and n"),
    ("-0.26 " + "±" + " 1.41",
     close(r9_035["se_pts"], 1.41, 0.005), "headline standard error"),
    ("costs 6.03 pts at the same budget",
     close(d12_curve("run 5", 0.35)["delta_pts"], -6.03, 0.005),
     "run 5's cost at keep=0.35"),
    ("65% of the visual tokens",
     m1_row(0.35)["visual_tokens"] == 1680 and m1_row(1.00)["visual_tokens"] == 4800,
     "1680/4800 = 35% kept"),
    ("frees 65% of ... cross-attention KV",
     close(100 * (1 - m1_row(0.35)["cross_kv_bytes_observed"]
                  / m1_row(1.00)["cross_kv_bytes_observed"]), 65.0, 0.05),
     "the two 65%s are the same 65%"),
    ("19.46% of the model's 771 MiB",
     close(100 * m1_row(1.00)["cross_kv_bytes_observed"] / m1["meta"]["param_bytes"],
           19.46, 0.01)
     and close(m1["meta"]["param_bytes"] / MIB, 771.0, 0.5), "KV share of parameters"),
    ("analytic and observed agree",
     all(r["cross_kv_bytes_analytic"] == r["cross_kv_bytes_observed"] for r in m1["rows"]),
     "rel gap 0.0000 at all five budgets"),
    ("self-KV non-monotone: 0.25 -> 10.19 exceeds 0.35 -> 9.56",
     close(m1_row(0.25)["self_kv_bytes_observed"] / MIB, 10.19, 0.005)
     and close(m1_row(0.35)["self_kv_bytes_observed"] / MIB, 9.56, 0.005)
     and m1_row(0.25)["self_kv_bytes_observed"] > m1_row(0.35)["self_kv_bytes_observed"],
     "a self/cross mix-up cannot pass as a pruning win"),
    ("17 of 17 controls pass (M1)", m1["meta"]["controls_passed"] is True, ""),
    ("run 9 at keep=0.35 with its own router scores 79.25",
     close(d11_row("run 9", 0.35, "router")["word_recall_pct"], 79.25, 0.005),
     "the +1.62 row, stated as the non-headline"),
    ("ink oracle retains 0.994 at keep=0.50",
     close(d12_row("9", 0.50)["retained_ink"], 0.994, 0.0005),
     "H2's most favourable condition"),
    ("bit-identical token sets across checkpoints",
     all(close(d12_row("9", k)["retained_ink"], d12_row("run 5", k)["retained_ink"], 1e-9)
         for k in (0.5, 0.35, 0.25, 0.2)),
     "verified 0.00e+00, the control the DiD rests on"),
    ("attention target loses: -5.63 @0.25, -12.81 @0.20",
     close(d11_row("run 10", 0.25, "router")["word_recall_pct"]
           - d11_row("run 9", 0.25, "router")["word_recall_pct"], -5.63, 0.02)
     and close(d11_row("run 10", 0.20, "router")["word_recall_pct"]
               - d11_row("run 9", 0.20, "router")["word_recall_pct"], -12.81, 0.02), ""),
    ("run 10 retains 0.257 ink vs random's 0.201 at keep=0.20",
     close(d11_row("run 10", 0.20, "router")["retained_ink"], 0.257, 0.0005)
     and close(d11_row("run 10", 0.20, "random")["retained_ink"], 0.201, 0.0005),
     "the near-ink-agnostic mechanism"),
    ("run 5 reads 74.72 local vs 77.74 Kaggle",
     close(d12_row("run 5", 1.00)["word_recall_pct"], 74.72, 0.005)
     and close(d12["meta"]["preregistered"]["run6_reference_recall"], 77.74, 0.005),
     "the cross-venue gap that forces paired deltas"),
    ("n = 50 everywhere",
     all(r["num_eval_samples"] == 50 for r in d12["rows"] + d11["rows"]), ""),
]
for label, ok, detail in checks:
    check(ok, label, detail)

print()
print("=" * 74)
print("5. THE FIGURES THE 2026-09-09 AUDIT CORRECTED")
print("=" * 74)
print("  Each of these was WRONG in the first draft. They are pinned here so a future")
print("  edit cannot quietly restore the error the audit removed.")
print()

# 5a. Sign of the router-vs-ink margin. The first draft said the router scored 2.24 pts
# BELOW ink at t -1.62; it is 2.24 ABOVE at t +1.62. The disclaimer ("no claim it beats
# ink") survives either way -- on significance, not on direction -- which is exactly why
# the error could sit there unnoticed. Recompute both from per-image data.
rt50 = d11_row("run 9", 0.50, "router")
ik50 = d12_row("9", 0.50)
gap = rt50["word_recall_pct"] - ik50["word_recall_pct"]
dd = [x - y for x, y in zip(rt50["per_image_recall"], ik50["per_image_recall"])]
mean_d = sum(dd) / len(dd)
var = sum((x - mean_d) ** 2 for x in dd) / (len(dd) - 1)
t_ri = mean_d / ((var / len(dd)) ** 0.5)
check(close(gap, 2.24, 0.01) and gap > 0,
      "router is 2.24 pts ABOVE ink at keep=0.50 (not below)", f"{gap:+.2f}")
check(close(t_ri, 1.62, 0.01) and t_ri > 0, "and the paired t is +1.62 (not -1.62)",
      f"t {t_ri:+.4f}")
check(abs(t_ri) < d11["meta"]["preregistered"]["t_signif"],
      "which is UNDER the pre-registered t>=2.0 -- the disclaimer rests on this",
      "not on the direction")
check(close(rt50["retained_ink"] - ik50["retained_ink"], -0.072, 0.001),
      "router retains 0.072 LESS ink than the oracle", "it is not rediscovering ink")
check("above" in norm[norm.index("beats a hand-crafted"):][:400]
      and "below" not in norm[norm.index("beats a hand-crafted"):][:400],
      "the writeup says 'above', not 'below'")

# 5b. Latency scope. "the maximum over ten measured rows" was ambiguous: D11 has 18 rows
# and random-mode reaches 1.19x. Ten is the ROUTER row count, and the disclaimer should
# quote the largest speed-up measured anywhere, not the smallest defensible one.
lat_base = {r["checkpoint"]: r["avg_latency_ms"]
            for r in d11["rows"] if r["keep_ratio"] == 1.0}
ratios = {m: [lat_base[r["checkpoint"]] / r["avg_latency_ms"] for r in d11["rows"]
              if r["select_mode"] == m and r["checkpoint"] in lat_base]
          for m in ("router", "random")}
check(len(ratios["router"]) == 10, "'ten router rows' is the true count",
      f"{len(ratios['router'])} router rows, {len(d11['rows'])} rows total")
check(close(max(ratios["router"]), 1.05, 0.005), "router max speed-up is 1.05x",
      f"{max(ratios['router']):.3f}")
check(close(max(ratios["random"]), 1.19, 0.005),
      "the largest speed-up ANYWHERE in D11 is 1.19x (random @0.20)",
      f"{max(ratios['random']):.3f} -- must be disclosed, it argues against our own claim")
check("1.19" in norm, "and 1.19 appears in the writeup",
      "quoting only 1.05 understates the counter-evidence to the no-latency claim")
r9_020 = d11_row("run 9", 0.20, "router")
check(close(lat_base[r9_020["checkpoint"]] / r9_020["avg_latency_ms"], 1.04, 0.005),
      "the headline 1.04x is 4800->960 at router selection")
gen = [r["mean_gen_tokens"] for r in d11["rows"] if r["select_mode"] == "router"]
check(round(min(gen)) == 243 and round(max(gen)) == 280,
      "'243-280 autoregressive steps' is the router-row range",
      f"{min(gen)}-{max(gen)}")

# 5c. M1's control count. The first draft said 17; the log carries 25.
with open(os.path.join(ROOT, "results", "kv_memory_local.log"), encoding="utf-8") as fh:
    m1log = fh.read()
n_pass = len(re.findall(r"^\s+\[PASS\]", m1log, re.M))
n_fail = len(re.findall(r"^\s+\[FAIL\]", m1log, re.M))
check(n_pass == 25 and n_fail == 0, "M1 logs 25 of 25 controls passing (not 17)",
      f"{n_pass} PASS / {n_fail} FAIL")
check(f"{n_pass} of {n_pass} controls pass" in norm,
      "and the writeup quotes that count exactly")

# 5d. D12's own control status. The first draft did not mention that D12 reports
# controls_passed=false / verdict WITHHELD. A writeup that cites a diagnostic's numbers
# while omitting its verdict is selecting on outcome.
check(d12["meta"]["controls_passed"] is False and d12["meta"]["verdict"] == "WITHHELD",
      "D12 really does report controls_passed=false / WITHHELD",
      "if this ever flips, the disclosure paragraph must be rewritten, not deleted")
fails = [v for v in d12["verdicts"] if not v.get("pass")]
check(len(fails) == 1 and "harness anchor" in fails[0]["check"],
      "exactly one D12 control fails, and it is the harness anchor",
      fails[0]["check"] if fails else "none")
check("3.02" in fails[0]["detail"] and "1.5" in fails[0]["detail"],
      "the failing gap is 3.02 pts against a 1.5 pt tolerance", fails[0]["detail"])
for needle, why in (("controls_passed: false", "the flag itself"),
                    ("WITHHELD", "the verdict"),
                    ("3.02", "the size of the failure"),
                    ("0.00e+00", "the controls the DiD actually rests on")):
    check(needle in norm, f"writeup discloses {needle!r}", why)
check(all(v.get("pass") for v in d12["verdicts"] if "selection fixed" in v["check"]),
      "the four selection-pairing controls do pass",
      "the disclosure would be misleading if they did not")

# 5e. Cross-checkpoint gaps, recomputed rather than transcribed, with significance.
for keep, quoted in ((0.50, 5.07), (0.35, 8.67), (0.25, 7.42), (0.20, 10.23)):
    a, b = d12_row("9", keep), d12_row("run 5", keep)
    g = a["word_recall_pct"] - b["word_recall_pct"]
    dd = [x - y for x, y in zip(a["per_image_recall"], b["per_image_recall"])]
    md = sum(dd) / len(dd)
    v = sum((x - md) ** 2 for x in dd) / (len(dd) - 1)
    tt = md / ((v / len(dd)) ** 0.5)
    check(close(g, quoted, 0.01) and abs(tt) >= d12["meta"]["preregistered"]["t_signif"],
          f"keep={keep:.2f} cross-checkpoint gap +{quoted} and significant",
          f"{g:+.2f}, t {tt:+.2f}")

# 5f. The UNDERPOWERED figure belongs to run 5 at keep=0.50 -- the arm the criterion keyed
# on -- not to run 9's 2.76.
check(close(d12["meta"]["resolution_pts"]["run 5  (no pruning in training)|0.5"], 5.20, 0.01),
      "run 5's resolution at keep=0.50 really is 5.20 pts")
check(re.search(r"nothing under 5\.20 pts", norm) is not None,
      "and the writeup quotes 5.20 as the criterion's floor",
      "run 9's floor is 2.76; quoting that arm instead would flatter the criterion, and "
      "checking only the JSON value would not notice the swap")

# 5g. Six ink gates matching to three decimals (the gate moved off recall onto ink).
gates = [v for v in d11["verdicts"] if v["check"].startswith("ink ")]
check(len(gates) == 6 and all(v["pass"] for v in gates),
      "six ink gates, all passing", f"{len(gates)} found")
check(all("0.000" in v["detail"] for v in gates),
      "each matched the Kaggle reference to three decimals")

print()
print("=" * 74)
print("6. TRANSCRIBED FROM AGENTS.md -- checked for TRANSCRIPTION ONLY")
print("=" * 74)
print("  These figures live in prose, not in a JSON this script can re-derive. Checking")
print("  them against AGENTS.md proves the writeup copied them correctly and nothing more;")
print("  it does NOT re-establish them. Listed separately so the distinction stays visible.")
print()
# 2026-10-02: READ THE ARCHIVES TOO. On 2026-09-24 AGENTS.md's historical bulk moved verbatim
# into three archives, and this section kept reading only AGENTS.md -- so 7 of its 142 checks
# began failing on figures that had merely MOVED and were never wrong (0.896, 0.910, 73.09,
# 18%, 49.2%, -3.22, -3.10). AGENTS.md went on recording this script as "142/142" the whole
# time. The restructure entry predicted the archives would be *unaudited*; the actual
# consequence was the inverse -- it broke the auditor. "The tracker" is now four files, so the
# transcription source has to be all four. Missing archives RAISE rather than silently
# shrinking the source back to AGENTS.md alone, which is precisely how this went unnoticed.
_TRACKER = ["AGENTS.md", "AGENTS-ARCHIVE-DIAGNOSTICS.md", "AGENTS-ARCHIVE-RUNS.md",
            "AGENTS-ARCHIVE-CHANGELOG.md"]
_parts = []
for _f in _TRACKER:
    _p = os.path.join(ROOT, _f)
    assert os.path.exists(_p), (
        f"transcription source {_f} is missing -- if the tracker was re-split, update "
        f"_TRACKER. Do NOT drop the file: a smaller source makes this section fail on "
        f"figures that are merely elsewhere.")
    _parts.append(open(_p, encoding="utf-8").read())
agents = "\n".join(_parts)
# 2026-09-18: normalise AGENTS.md the same way the writeup is normalised. `norm` folds U+2212
# MINUS SIGN to ASCII hyphen but `agents` was raw, so any figure carrying a sign was
# structurally unable to match -- it would be ASCII in `norm` and U+2212 in `agents` and the
# check would report "NOT IN AGENTS.md" on a figure that is plainly there. That is why every
# figure in the list below was previously unsigned: the list had quietly been restricted to the
# figures this comparison could handle, which is a limit of the tool being mistaken for a
# choice about what to verify. The merge rows added today are all signed deltas.
agents = agents.replace("−", "-").replace("–", "-")
# Each figure must be present in BOTH. An earlier version asked only "if it is in the doc,
# is it in AGENTS.md" -- which a corrupted figure passes vacuously, because the corrupted
# doc no longer contains the string being looked for. The check has to require presence,
# or it only ever fires on a document that is already correct.
for fig, why in (
        ("0.896", "held-out probe's retained teacher-attention mass at K"),
        ("0.910", "the teacher's own top-K ceiling, without which 0.896 is unreadable"),
        ("10.93", "the largest recorded ceiling drift between retrains"),
        ("1.30", "run 8's ceiling drift"),
        ("73.09", "negated mode while the router was inverted"),
        ("18.80", "forward router while it was inverted"),
        ("2.70", "negated after the fix -- the role flip"),
        ("71%", "the decoding cap defect"),
        ("49%", "ToMe missed-redundancy rate"),
        ("18%", "invalid-JSON rate"),
        # Run 13's merge rows, added to the writeup 2026-09-18. These are the numbers that
        # replaced "token merging has never executed", so they are exactly the ones a reader
        # will quote, and until now nothing checked the writeup had copied them correctly.
        ("-3.86", "run 13: cost of merging away 40% of the router's kept set"),
        ("-7.45", "lower endpoint of that CI -- the half the claim is usually quoted without"),
        ("49.2%", "missed horizontal redundancy under score-rank split, precise form"),
        ("50.5%", "missed vertical redundancy under score-rank split, precise form"),
        ("-1.51", "sabotage row, run 12 / run-5 weights: checkerboard minus rank_parity"),
        ("-3.22", "lower endpoint of the run-12 sabotage CI (the powered one, res 1.7)"),
        ("-0.29", "sabotage row, run 13 / run-9 weights"),
        ("-3.10", "lower endpoint of the run-13 sabotage CI")):
    in_doc, in_src = fig in norm, fig in agents
    check(in_doc and in_src, f"{fig} ({why})",
          "" if in_doc else "MISSING FROM THE WRITEUP -- corrupted, or dropped without "
          "updating this list" if in_src else "NOT IN AGENTS.md -- unsourced figure")

print()
print("=" * 74)
print("7. CLAIMS THE WRITEUP MUST NOT MAKE")
print("=" * 74)
print("  Dropping a claim is a decision; it should be enforced, not remembered.")
print()
for banned, why in (
        (r"beats?\s+the\s+ink\s+oracle", "the router-vs-ink margin is t +1.62, under 2.0"),
        (r"H1\s+is\s+(proven|established|isolated\b(?!\.))",
         "H1 is supported, not isolated -- the control has not run"),
        (r"\+14\s+to\s+\+28", "superseded range; D11 gives +17.7 to +34.0"),
        # Affirmative speed claims only. The disclaimers in section 5 legitimately contain
        # the words "latency" and "throughput"; an earlier version of this check banned the
        # bare words and fired on the disclaimer itself.
        (r"\d+(?:\.\d+)?\s*[x×]\s*(?:faster|speed-?up\b)", "D11: 1.04x at 5x fewer tokens"),
        (r"\b(?:is|are|runs?)\s+\d+(?:\.\d+)?\s*[x×]\s*faster", "same"),
        (r"(?<!not )(?<!no )efficiency\s+(?:win|gain|result)\b",
         "the efficiency story is memory only, and only cross-attention KV")):
    hits = [m.group(0) for m in re.finditer(banned, norm, re.I)]
    check(not hits, f"does not claim: {banned}", why + (f" -- found {hits}" if hits else ""))

# The disclaimers themselves must be PRESENT. Banning affirmative phrasings is worthless if
# the whole section can be deleted and still score green.
#
# 2026-09-18: the merging needle was "No merging result", which was the §5 heading while the
# merger had never executed. Runs 12/13 executed it, so that heading became false and was
# replaced by "The merging result is off-distribution." -- and this check FAILED, which is the
# check doing its job: it noticed the scope disclaimer had changed rather than letting the
# rename silently remove it. The needle is re-pointed at the NEW scope limit (every checkpoint
# was trained at merge_ratio=0.0) rather than deleted, because the writeup still owes the reader
# a merging caveat -- just a different one. Do not weaken this to a bare "off-distribution":
# the phrase has to be about the merging result specifically, or an unrelated sentence could
# satisfy it.
for needle in ("No latency win", "No encoder-side saving",
               "No claim that the router beats",
               "merging result is off-distribution",
               "not isolated"):
    check(needle in doc, f"disclaimer present: {needle!r}",
          "a banned-phrase check passes trivially on a file with no disclaimers at all")

print()
print("=" * 74)
print(f"{npass} passed, {nfail} failed")
print("=" * 74)
raise SystemExit(1 if nfail else 0)
