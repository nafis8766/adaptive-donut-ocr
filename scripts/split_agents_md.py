"""One-shot restructure of AGENTS.md: move the historical bulk into three archive files.

WHY: AGENTS.md is auto-loaded IN FULL as project instructions on every session, so its
~202K tokens were consumed unconditionally whether or not anyone read it. It was 18x the
next-largest doc in the repo and on its own large enough to fill a 200K context window.

WHAT THIS IS NOT: a deletion. This project's strike-and-supersede convention keeps falsified
predictions and the reasons they were wrong. Every byte moves to an archive; nothing is
dropped. The only authored text is the compact diagnostics index, the archive pointer, the
per-archive headers and the changelog stub -- everything else is pure line slicing.

THE CHECK THAT MATTERS is accounting: the eight slices, concatenated in original order, must
reproduce the source file byte-for-byte. That is the "check on what it was NOT supposed to
change" the 2026-09-06 mojibake incident called for -- a grep for the intended change came
back clean there while 1117 unrelated characters were corrupted.

Encoding: read/write with explicit utf-8 and newline='' so EOLs survive byte-exact.
NEVER route this file through PowerShell Set-Content/Out-File (see Gotchas).
"""

import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "AGENTS.md")
BAK = os.path.join(ROOT, "AGENTS.md.bak-presplit")

ARCH_DIAG = os.path.join(ROOT, "AGENTS-ARCHIVE-DIAGNOSTICS.md")
ARCH_RUNS = os.path.join(ROOT, "AGENTS-ARCHIVE-RUNS.md")
ARCH_CHLOG = os.path.join(ROOT, "AGENTS-ARCHIVE-CHANGELOG.md")


def read(path):
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def find_anchor(lines, prefix, label):
    """Index of the unique line starting with `prefix`. Raises if 0 or >1 match."""
    hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(
            "ANCHOR %s: expected exactly 1 line starting with %r, found %d (lines %s)"
            % (label, prefix, len(hits), [h + 1 for h in hits])
        )
    return hits[0]


# ---------------------------------------------------------------- authored text

ARCHIVE_POINTER = """\
> **Restructured 2026-09-24 — this file was 8,945 lines and is auto-loaded in full on every
> session, so its ~202K tokens were being paid unconditionally.** The historical bulk now lives
> in three archives. **Nothing was deleted** — every line moved verbatim, per the
> strike-and-supersede convention, and a byte-accounting assertion checked it
> (`scripts/split_agents_md.py`). This file still wins on any disagreement with anything,
> including its own archives.
>
> | archive | holds | read it when |
> |---|---|---|
> | `AGENTS-ARCHIVE-DIAGNOSTICS.md` | the full diagnostics index, D1–D14, M1, fixes F1–F3, runs 7–10 sections and their launch checklists | citing any D-number, M1, or an F-fix |
> | `AGENTS-ARCHIVE-RUNS.md` | corpus decision (T2), the T3 re-scoring, the whole `## Pending` item history, runs 11–14 checklists + results, Phase 2c/2d | reading a run's result or a closed Pending item |
> | `AGENTS-ARCHIVE-CHANGELOG.md` | the dated changelog and the Kilo contributions section | reconstructing when and why something changed |
>
> **What stayed here, deliberately:** the TODO queue and resume protocol (two saved memories
> name this file and this section), the four claims, the file map, the eval protocol and run
> table, **the run-17 pre-registration** (the rule the next run is scored against), and
> Conventions + Gotchas (the two sections that are advice for *work about to happen* rather
> than a record of work already done).
>
> ⚠ **The archives are subordinate to this file and go stale the moment a run lands**, exactly
> like the four prose docs. When you correct a number here, grep the archives for the old value
> — `scripts/check_writeup_numbers.py` does not read them.

"""

NEW_INDEX = """\
**Diagnostics index — one line each. Full write-ups, with every table and every
self-correction, are in `AGENTS-ARCHIVE-DIAGNOSTICS.md`.** Each is a standalone script that
re-derives its numbers from cached artifacts, so any claim below can be rechecked without a
GPU. **The one-liners are pointers, not evidence** — read the archived section before citing
one, because in several cases the caveat is the finding.

| # | script | what it established |
| --- | --- | --- |
| D1 | `scripts/router_score_probe.py` | The trained router is an *inverted* saliency detector (r ≈ −0.24 vs ink), retaining 34–38% of a page's ink where random retains 50%. Its sections A–E were all clean and all decorative; only F asked the real question. |
| D2 | `scripts/diagnose_selection_geometry.py` | Retained ink is the wrong objective. Its own min-coverage acceptance gate is **withdrawn** — see D3. |
| D3 | `scripts/diagnose_selection_statistics.py` | Runs 7–8 had already answered three open questions nobody transcribed; min-coverage gate falsified; the efficiency claim fails; "beats the oracle" is probably co-adaptation. |
| D4 | `scripts/diagnose_saliency_loss.py` | The ink-BCE loss was fed a probability where it expects a logit, attenuating the gradient up to 112× on the tokens it was most wrong about. **FIXED by F1**; its own *recommended* fix was wrong — see D5. |
| D5 | `scripts/diagnose_saliency_loss_coupling.py` | D4's recommended fix was unsafe: `scores` has three consumers and two need a probability. Also found `lambda_entropy=0.05` was never chosen — it shaped two runs from a signature default. |
| D6 | (no script — re-read of run 9's own rows) | The weight change and the selection change point opposite ways: F1's mechanism worked *and* cost accuracy. Upgrades D2 from correlation to intervention. |
| D7 | `scripts/diagnose_ste_signal.py` | **Pending 13(a) is dead.** Run 7's auxiliaries were 2.5–17% of the router gradient, so it was already STE-driven — and scored 18.80 recall. CE-through-STE is large but incoherent (cos 0.21); ink-BCE is smaller and systematic (0.85–0.90). |
| D8 | `scripts/diagnose_attn_target.py` | Decoder cross-attention is a *different*, page-specific target from ink (r +0.083; top-5% centroid spread 6.12 grid rows vs ink's 1.81) and the router is **uninformed** about it (r −0.045). Cosine was the wrong statistic to pre-register. |
| D9 | `scripts/diagnose_target_learnability.py` | The attention target is reachable by the existing scorer — but the headline is the **lift over a featureless constant map (+0.212 vs ink's +0.151)**, not the 0.976 held-out AUC, three-quarters of which a constant map already earns. Reachability, not merit. |
| D10 | `scripts/diagnose_target_drift.py` | The on-the-fly target is effectively stationary and page-specific: S = 0.9613 across a full retrain against a different-pages floor of X = 0.6246. That floor is a second independent estimate of the ≈0.63 inflated null for top-K overlaps. |
| D11 | `scripts/eval_budget_binding.py` | **13(b) is DEAD, and this is the informative negative.** At budgets that *bind*, the attention target loses to ink by −5.63 at keep=0.25 and −12.81 at keep=0.20. Also settles Pending 8: 4800 → 960 tokens buys **1.04×** wall-clock. |
| D12 | `scripts/eval_why_pruning_helps.py` | **H2 is REJECTED — "pruning helps" is train/test matching, not denoising.** Run 5, never trained with pruning, falls monotonically on bit-identical token sets. This is where claim 1's load-bearing "if you train for it" comes from. |
| D13 | `scripts/diagnose_merge_power.py` | **The ToMe blocker is the instrument, not the merger.** n=50 against a per-document sd of 11–13 pts makes UNDERPOWERED structural. §5: both location estimators are blind to a −72 pt page, so a rule needs a **tail** statistic. 36/36 controls. |
| D14 | `scripts/diagnose_analysis_dof.py` | **T1 was scoped as an estimator choice; the estimator is the smallest of seven unpinned degrees of freedom.** "Run 14, m=0.40" names two contrasts 5.08 pts apart; runs 13/14 both declared MERGING WINS on **disjoint** rows; zero Holm survivors. 20/20 controls. |
| M1 | `scripts/eval_kv_memory.py` | **The project's one true efficiency claim.** Cross-attention KV 150.00 → 52.50 MiB (−65.0%) at keep=0.35 for −0.26 pts (t −0.18). Extended 2026-09-18 to the merge rows, **52/52 controls**. Cross-KV only — not total, not peak, not encoder, not latency. |
| — | `scripts/verify_saliency_loss_cell.py` | **Execs** cell 11's saliency block and asserts satisfiability, gradient proportionality (`\\|d_sal/dz\\|/\\|p−t\\| == 1.0`), explicit `lambda_*`, and the (0,1) range contract. **11/11**; 3/6 before F1. |
| — | `scripts/verify_harness_control.py` | **Execs** cell 15's weight-swap block under seven scenarios, two of which must raise. **36/36** canonical, **39/39** generated — and the higher count is the notebook that matters, because the four extra checks are the resume-train-save chain. |
| — | `scripts/verify_results_provenance.py` | **Execs** the `PROVENANCE` block and both real `json.dump`s, then reads the stamp back off disk. **35/35** on both notebooks — but it **raised silently on the generated notebook for 13 days** while this file recorded it as passing. A verifier that crashes reads exactly like one nobody ran. |
| — | `scripts/verify_training_telemetry.py` | **Extracts and executes** cell 11's epoch loop against a real loss/scaler/AdamW; asserts λ=0.5 and λ=0 print *different* lines — the property whose absence made run 9's log uninterpretable. **8/8**; 1/6 before F3. |
| — | `scripts/verify_attn_target.py` | **Execs** cells 4+7 against a real donut decoder. **34/34** fast, **41/41** with `--real`. One of those 41 clears its own content-free floor by 0.024 on one page — do not read the count as 41 equal claims. |
| — | `scripts/verify_attn_train_step.py` | The only check that executes the 13(b) *composition* rather than its pieces: cell 11's verbatim prologue + body on real pages. **13/13** fast, **24/24** with `--full`. Found three defects, incl. the `gc` cross-cell coupling. |
| — | `scripts/verify_tome_merge_port.py` | The gate that had to be green before run 12: merger output equal to `src/tome.py` **bit-for-bit**, every equality paired with a non-vacuity check. **89/89**. |
| — | `scripts/verify_corpus_grain.py` | **T2's artifact.** Confirms the second corpus **by loading it** and measures whether T1's point-denominated thresholds port. CORD excluded on **denotation**, not size. **21/21**. |
| — | `scripts/score_preregistered.py` | **T3's artifact — the executable form of T1 §§2–7**, which existed only as prose. Runs 13/14 score `UNDERPOWERED`; §5 shows T1 §3's tail gate is **not specific to merging**. **45/45**. |
| — | `scripts/check_writeup_numbers.py` | Re-derives every figure in `WRITEUP.md` from `results/*.json` — deliberately **not** from this file, because prose checked against prose proves nothing. **142/142**. Found six real errors incl. a double sign inversion. |
| — | `scripts/probe_generation_determinism.py` | Tests by execution the assumption that greedy generation is bit-identical across runs — the sole justification for bootstrapping over documents only. **6/6** within-process, **6/6** across two processes. |
| — | `scripts/diagnose_tome_parity.py` | Quantifies the ToMe score-order/parity gotcha (~49% missed redundancy). Imports the **shipped** `checkerboard_color`; a local restatement scored 10/10 under sabotage. |
| — | `scripts/diagnose_decoder.py` | LEGACY (copy-vs-next-token, settled before run 6). Re-run on run 8: no copy failure (COPY 0.0% / NEXT 74.5%), and the first legible sample of generated text recorded anywhere. |

"""

CHANGELOG_STUB = """\
## Changelog

**The dated changelog lives in `AGENTS-ARCHIVE-CHANGELOG.md`**, together with the Kilo
contributions section. It is the longest single section in the project and is read
retrospectively rather than at the start of a session, which is why it is not loaded here.
Append new entries **there**, newest-last, in the existing format — and record anything that
changes a number in this file, because the archives are not covered by any audit.

- **2026-09-24 — AGENTS.md restructured; three archives created; nothing deleted.**
  This file was **8,945 lines / 809,072 bytes / ≈202K tokens** and is injected in full as
  project instructions on **every** session, so that cost was paid unconditionally — it was
  18× the next-largest doc in the repo and on its own enough to fill a 200K context window.
  The historical bulk moved verbatim into `AGENTS-ARCHIVE-DIAGNOSTICS.md`,
  `AGENTS-ARCHIVE-RUNS.md` and `AGENTS-ARCHIVE-CHANGELOG.md`.
  **Three properties of how it was done, each a standing convention of this project applied to
  itself:**
  (a) **Archive, never delete.** Strike-and-supersede exists because the *reason* a claim was
  wrong is worth more than the claim; deleting the record to save tokens would have traded the
  project's main methodological asset for a context-window win.
  (b) **The edit is pure line slicing plus purely additive new text.** The only authored prose
  is the compact diagnostics index, the archive pointer, the per-archive headers and this
  entry. No existing sentence was rewritten, so no non-ASCII character was retyped — which is
  the 2026-09-06 mojibake failure mode avoided by construction rather than by care.
  (c) **A byte-accounting assertion, not a grep.** `scripts/split_agents_md.py` asserts that
  the eight slices concatenated in original order reproduce the source byte-for-byte before it
  writes anything. That is the "check on what it was NOT supposed to change" the 2026-09-06
  incident called for: there, the grep for the intended change came back clean while 1117
  unrelated characters were corrupted.
  **What deliberately stayed:** the `▶ TODO` queue and resume protocol (two saved memories name
  this file and this section by name, so moving it would break resume), the four claims, the
  file map, the eval protocol and run table, **the run-17 pre-registration** — the rule T4/T7
  are about to be scored against, which must be readable without opening an archive — and
  Conventions + Gotchas, the two sections that are advice for work *about to happen* rather
  than a record of work already done.
  ⚠ **The archives inherit the staleness problem the four prose docs already have, and have no
  audit at all.** `check_writeup_numbers.py` does not read them. When a figure is corrected
  here, grep all three archives for the old value — this file now has four derived documents
  and three archives downstream of it, and only `WRITEUP.md` is checked.
  ⚠ **`scripts/check_agents_md_format.py` was re-run against the trimmed file and each archive**
  after the split; the invariants it pins (balanced fences, no ragged table rows, no paste
  debris) hold on all four.
"""

ARCH_HEADERS = {
    ARCH_DIAG: """\
# AGENTS-ARCHIVE-DIAGNOSTICS.md — diagnostics, fixes, and runs 7–10

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**,
including where this file contradicts a correction made there later. This archive has **no
numeric audit** — when a figure is corrected in `AGENTS.md`, grep here for the old value.

Holds: the full diagnostics index with its per-script notes, **D1–D14**, **M1**, fixes
**F1–F3**, the run 7/8/9 sections, the run 9 and run 10 launch checklists, and the run 10
result. Read the section here before citing any D-number — several of them are on record
mainly for the caveat attached to the finding.

---

""",
    ARCH_RUNS: """\
# AGENTS-ARCHIVE-RUNS.md — corpus decision, re-scoring, Pending history, runs 11–14

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**.
This archive has **no numeric audit** — when a figure is corrected in `AGENTS.md`, grep here
for the old value.

Holds: the **corpus decision (T2)**, the **runs 13/14 re-scoring under the run-17 rule (T3)**,
the whole `## Pending` item history (items 1–19, almost all closed, kept because the *reasons*
they closed are the content), the **run 11/12/13/14 launch checklists and results**, and
Phase 2c / Phase 2d.

⚠ The live queue is **not** here. `AGENTS.md`'s `▶ TODO` section (T1–T8) is the execution
order; the `OPEN ITEMS` table in this file is the *detail* behind those items and its priority
ordering was superseded by D13. Do not start work from this file.

---

""",
    ARCH_CHLOG: """\
# AGENTS-ARCHIVE-CHANGELOG.md — the dated changelog

**Split out of `AGENTS.md` on 2026-09-24. Verbatim; nothing was edited on the way out.**
`AGENTS.md` is the single source of truth and **wins on any disagreement with this file**.

Append new entries here, newest-last, in the existing format. `AGENTS.md` keeps a short
`## Changelog` stub pointing at this file plus the entry for the split itself.

Also holds the **Kilo (tencent/hy3:free) contributions** section at the end, which is attributed
separately on purpose so those changes stay distinguishable.

---

""",
}


# ---------------------------------------------------------------- slice and verify

def main():
    original = read(SRC)
    lines = original.splitlines(keepends=True)

    i_todo = find_anchor(lines, "## ▶ TODO", "TODO queue")
    i_diag = find_anchor(lines, "**Diagnostics index.**", "diagnostics index")
    i_filemap = find_anchor(lines, "## File map", "file map")
    i_run7 = find_anchor(lines, "### Run 7 — pruning-ON retrain", "run 7")
    i_t1 = find_anchor(lines, "## Run 17 pre-registration (T1)", "T1 pre-registration")
    i_t2 = find_anchor(lines, "## Corpus decision (T2)", "T2 corpus decision")
    i_conv = find_anchor(lines, "## Conventions", "conventions")
    i_chlog = find_anchor(lines, "## Changelog", "changelog")

    order = [i_todo, i_diag, i_filemap, i_run7, i_t1, i_t2, i_conv, i_chlog]
    if order != sorted(order):
        raise SystemExit("ANCHORS OUT OF ORDER: %s" % [o + 1 for o in order])

    A1 = lines[:i_todo]                 # mandate / header
    A2 = lines[i_todo:i_diag]           # TODO queue + standing constraints + claims
    DIAG = lines[i_diag:i_filemap]      # -> archive (replaced by compact index)
    B = lines[i_filemap:i_run7]         # file map, eval protocol, run table, findings
    BLOCK1 = lines[i_run7:i_t1]         # -> archive: runs 7-10, D1-D14, M1, F1-F3
    C = lines[i_t1:i_t2]                # run 17 pre-registration
    BLOCK2 = lines[i_t2:i_conv]         # -> archive: T2, T3, Pending, runs 11-14
    D = lines[i_conv:i_chlog]           # conventions + gotchas
    BLOCK3 = lines[i_chlog:]            # -> archive: changelog + Kilo

    # THE accounting check. Must hold before anything is written.
    rebuilt = "".join(
        "".join(s) for s in (A1, A2, DIAG, B, BLOCK1, C, BLOCK2, D, BLOCK3)
    )
    if rebuilt != original:
        raise SystemExit("ACCOUNTING FAILED: slices do not reproduce the source byte-for-byte")
    total = sum(len(s) for s in (A1, A2, DIAG, B, BLOCK1, C, BLOCK2, D, BLOCK3))
    if total != len(lines):
        raise SystemExit("ACCOUNTING FAILED: line count %d != %d" % (total, len(lines)))

    # Backup first. Working dir is NOT a git repo -- this is the only undo.
    if not os.path.exists(BAK):
        write(BAK, original)
    if read(BAK) != original:
        raise SystemExit("BACKUP MISMATCH: %s exists and differs from the source" % BAK)

    new_agents = (
        "".join(A1)
        + ARCHIVE_POINTER
        + "".join(A2)
        + NEW_INDEX
        + "".join(B)
        + "".join(C)
        + "".join(D)
        + CHANGELOG_STUB
    )
    arch_diag = ARCH_HEADERS[ARCH_DIAG] + "".join(DIAG) + "".join(BLOCK1)
    arch_runs = ARCH_HEADERS[ARCH_RUNS] + "".join(BLOCK2)
    arch_chlog = ARCH_HEADERS[ARCH_CHLOG] + "".join(BLOCK3)

    # Every archived line must be present, verbatim, in exactly one archive.
    archived = arch_diag + arch_runs + arch_chlog
    for name, slc in (("DIAG", DIAG), ("BLOCK1", BLOCK1), ("BLOCK2", BLOCK2), ("BLOCK3", BLOCK3)):
        if "".join(slc) not in archived:
            raise SystemExit("ARCHIVE LOSS: %s not present verbatim in the archives" % name)

    write(SRC, new_agents)
    write(ARCH_DIAG, arch_diag)
    write(ARCH_RUNS, arch_runs)
    write(ARCH_CHLOG, arch_chlog)

    def stats(label, text):
        nl = len(text.splitlines())
        fences = sum(1 for ln in text.splitlines() if ln.lstrip().startswith("```"))
        return "%-34s lines=%-6d bytes=%-8d emdash=%-5d U+FFFD=%-3d fences=%d (%s)" % (
            label, nl, len(text.encode("utf-8")), text.count("—"),
            text.count("�"), fences, "balanced" if fences % 2 == 0 else "UNBALANCED",
        )

    print("ACCOUNTING OK - 8 slices reproduce the source byte-for-byte (%d lines)" % len(lines))
    print("")
    print(stats("BEFORE  AGENTS.md", original))
    print(stats("AFTER   AGENTS.md", new_agents))
    print(stats("        ARCHIVE-DIAGNOSTICS", arch_diag))
    print(stats("        ARCHIVE-RUNS", arch_runs))
    print(stats("        ARCHIVE-CHANGELOG", arch_chlog))
    print("")
    em_after = (new_agents.count("—") + arch_diag.count("—")
                + arch_runs.count("—") + arch_chlog.count("—"))
    print("em-dashes: %d before -> %d after (authored text adds some; must never DROP)"
          % (original.count("—"), em_after))
    print("U+FFFD anywhere: %d (must be 0)"
          % sum(t.count("�") for t in (new_agents, arch_diag, arch_runs, arch_chlog)))
    print("reduction: %.1fx fewer lines loaded per session (%d -> %d)"
          % (len(lines) / max(1, len(new_agents.splitlines())),
             len(lines), len(new_agents.splitlines())))
    print("backup: %s" % BAK)


if __name__ == "__main__":
    main()
