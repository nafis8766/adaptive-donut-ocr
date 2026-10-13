"""Publish run 9's checkpoint, the technical report, and the model card to the Hugging Face Hub.

Run 9 is the pruning-aware checkpoint every headline figure in this project comes from:
5 epochs with pruning ON at keep_ratio=0.50 plus ink-BCE router supervision, resumed from
the unpruned FUNSD fine-tune. AGENTS.md records its size as 1045901771 bytes under run 13's
`provenance.eval_ckpt`, and this script ASSERTS that before uploading anything -- the one
thing that must not happen is publishing a different checkpoint under run 9's results.

Why a script rather than a CLI one-liner: the size assertion, the head+tail fingerprint
(AGENTS.md's own convention for tying a results table to weights), the card-source check,
and the report gates below are all things a one-liner would skip, and this is an
irreversible public action.

The checkpoint is VERIFIED, not blindly re-sent. 2026-10-12: the original script uploaded
1 GB on every --push, which made a card-only or paper-only correction cost a full transfer
and therefore discouraged making one. It now reads the published file's size off the Hub
and re-uploads only if it is missing or does not match run 9's recorded provenance -- which
is a stronger guard than the old unconditional upload, because it checks what is actually
public rather than assuming the last upload stuck.

Usage:
    python hf/upload_model.py                  # dry run: verify everything, upload nothing
    python hf/upload_model.py --push           # publish card + report; weights only if needed
    python hf/upload_model.py --push --force-weights   # re-send the 1 GB checkpoint anyway
"""
import hashlib
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")
CARD = os.path.join(ROOT, "hf", "MODEL_CARD.md")
PAPER = os.path.join(ROOT, "report", "report.pdf")
PAPER_TEX = os.path.join(ROOT, "report", "report.tex")
AUDIT = os.path.join(ROOT, "scripts", "check_report_numbers.py")
REPO = "nafis8766/adaptive-donut-ocr-router"

CKPT_IN_REPO = "adaptive_donut_pruned.pt"
PAPER_IN_REPO = "report.pdf"

# From AGENTS.md: run 13's provenance.eval_ckpt names run 9's weights at this exact size.
# Run 5's is 1045901275 -- 496 bytes smaller, and attaching it by mistake is precisely what
# made run 12's headline an artifact. So the size is the guard, not a comment.
EXPECTED_BYTES = 1045901771
RUN5_BYTES = 1045901275

push = "--push" in sys.argv
force_weights = "--force-weights" in sys.argv

print("=" * 74)
print(f"Hugging Face upload -- {REPO}")
print("=" * 74)

# ---------------------------------------------------------------- pre-flight assertions
for p in (CKPT, CARD, PAPER, PAPER_TEX, AUDIT):
    assert os.path.exists(p), f"not found: {p}"

size = os.path.getsize(CKPT)
print(f"  checkpoint : {CKPT}")
print(f"  size       : {size:,} bytes")
assert size != RUN5_BYTES, (
    "REFUSING TO UPLOAD: this is run 5's checkpoint (pre-pruning), not run 9's. "
    "Publishing it under run 9's results is the run-12 defect reproduced."
)
assert size == EXPECTED_BYTES, (
    f"REFUSING TO UPLOAD: expected {EXPECTED_BYTES:,} bytes (run 9, per AGENTS.md), "
    f"got {size:,}. Do not publish an uncharacterised checkpoint."
)
print(f"  [PASS] size matches run 9's recorded provenance ({EXPECTED_BYTES:,})")

# AGENTS.md's fingerprint convention: sha256 over the first and last 8 MB. Enough to tell
# checkpoints apart without reading 1 GB, and it goes in the log so the upload is traceable.
CHUNK = 8 * 1024 * 1024
h = hashlib.sha256()
with open(CKPT, "rb") as f:
    h.update(f.read(CHUNK))
    f.seek(-CHUNK, os.SEEK_END)
    h.update(f.read(CHUNK))
fp = h.hexdigest()
print(f"  [INFO] sha256(head+tail 8 MiB) = {fp[:16]}  (full: {fp})")

card = open(CARD, encoding="utf-8").read()
assert card.startswith("---"), "model card is missing its YAML front matter"
assert "license: mit" in card, "model card must declare the inherited MIT licence"
for needle in ("Licence position", "license: ''", "No latency or throughput win",
               "underpowered", "repetition_penalty=1.0"):
    assert needle in card, f"model card is missing a required disclosure: {needle!r}"
print(f"  [PASS] card has front matter and all 5 required disclosures ({len(card):,} chars)")

# ------------------------------------------------------------------- report gates (2026-10-12)
# Three things must hold before a PDF of this report is made public. All three are cheap,
# and each one has already gone wrong at least once in this project.

# (1) The PDF must be newer than its source. A hand-edit to the .tex followed by a publish
#     with no rebuild ships the previous paper under the new commit. Compare getmtime
#     FLOATS, never formatted times -- AGENTS.md records a check that printed a day-newer
#     PDF as stale because the format string dropped the date.
t_pdf, t_tex = os.path.getmtime(PAPER), os.path.getmtime(PAPER_TEX)
assert t_pdf >= t_tex, (
    f"REFUSING TO UPLOAD: report.pdf ({t_pdf:.0f}) is OLDER than report.tex ({t_tex:.0f}). "
    "Run report/build.ps1 first -- this would publish the previous build."
)
print(f"  [PASS] report.pdf is not stale against report.tex "
      f"(+{t_pdf - t_tex:.0f}s, {os.path.getsize(PAPER):,} bytes)")

# (2) The report's numeric audit must pass. Since the subordination line was removed from
#     the paper by user ruling, this audit is the ONLY mechanical guard against the
#     document drifting from the measurements -- so the publication boundary is exactly
#     where it should be enforced, not merely "re-run it after an edit" in a comment.
r = subprocess.run([sys.executable, "-I", AUDIT], capture_output=True, text=True, cwd=ROOT)
tail = [ln for ln in r.stdout.splitlines() if "TOTAL:" in ln or "unsourced" in ln]
assert r.returncode == 0, (
    "REFUSING TO UPLOAD: scripts/check_report_numbers.py exited "
    f"{r.returncode}. Do not publish a report whose figures do not audit.\n"
    + "\n".join(r.stdout.splitlines()[-25:])
)
print("  [PASS] report numeric audit exits 0 -- " + " | ".join(s.strip() for s in tail))

# (3) No internal tracker reference may reach a reader. The user ruled on 2026-10-10 that
#     naming AGENTS.md as the source of truth has no place in a document read cold. A
#     purge list is only as good as its enumeration, which is how that one survived the
#     first audit -- so it is pinned here, at the boundary where it would become public.
#     Scope limit, stated: this reads the .tex, not the PDF. A LaTeX comment is therefore
#     not flagged (it cannot render), and a string built at typesetting time would not be
#     caught. The .tex is the only input to the PDF, which is what makes it sufficient.
tex_body = re.sub(r"(?m)^\s*%.*$", "", open(PAPER_TEX, encoding="utf-8").read())
for banned in ("AGENTS.md", "source of truth", "dated snapshot",
               "WRITEUP.md", "STORY.md", "NOTES.md"):
    assert banned not in tex_body, (
        f"REFUSING TO UPLOAD: report.tex names {banned!r} outside a comment. "
        "Internal bookkeeping must not reach a reader (user ruling, 2026-10-10)."
    )
print("  [PASS] report.tex is free of internal tracker references")

if not push:
    print()
    print("DRY RUN -- nothing uploaded. Re-run with --push to publish.")
    sys.exit(0)

# ------------------------------------------------------------------------------- upload
from huggingface_hub import HfApi, create_repo, whoami          # noqa: E402

me = whoami()
print(f"  [INFO] authenticated as {me.get('name')}")

create_repo(REPO, repo_type="model", private=False, exist_ok=True)
print(f"  [PASS] repo exists: https://huggingface.co/{REPO}")

api = HfApi()

# What is actually published right now? Read it rather than assume the last run stuck.
published = {}
try:
    info = api.model_info(REPO, files_metadata=True)
    for s in info.siblings or []:
        sz = getattr(s, "size", None)
        if sz is None:
            # LFS metadata is a BlobLfsInfo object in huggingface_hub 1.x and a dict in
            # some older releases. Reach for either, and tolerate neither.
            lfs = getattr(s, "lfs", None)
            sz = getattr(lfs, "size", None) if lfs is not None else None
            if sz is None and isinstance(lfs, dict):
                sz = lfs.get("size")
        published[s.rfilename] = sz
    print(f"  [INFO] already published: "
          + ", ".join(f"{k} ({v:,} B)" if isinstance(v, int) else f"{k} (size unknown)"
                      for k, v in sorted(published.items())))
except Exception as e:                                           # noqa: BLE001
    print(f"  [WARN] could not read published file list ({e}); will upload everything")

print("  uploading README.md ...")
api.upload_file(path_or_fileobj=CARD, path_in_repo="README.md",
                repo_id=REPO, repo_type="model",
                commit_message="Update model card: report link, scope limits, licence position")
print("  [PASS] README.md uploaded")

print(f"  uploading {PAPER_IN_REPO} ({os.path.getsize(PAPER) / 1024:.0f} KiB) ...")
api.upload_file(path_or_fileobj=PAPER, path_in_repo=PAPER_IN_REPO,
                repo_id=REPO, repo_type="model",
                commit_message="Add the technical report (journal manuscript form)")
print(f"  [PASS] {PAPER_IN_REPO} uploaded")

pub_ckpt = published.get(CKPT_IN_REPO)
if force_weights:
    need = True
    why = "--force-weights given"
elif pub_ckpt is None:
    need = True
    why = "not present on the Hub"
elif pub_ckpt != EXPECTED_BYTES:
    need = True
    why = f"published size {pub_ckpt:,} != expected {EXPECTED_BYTES:,}"
else:
    need = False
    why = f"already published at the correct size ({pub_ckpt:,} bytes)"

if need:
    print(f"  uploading {CKPT_IN_REPO} ({size / 1048576:.0f} MiB) -- {why}; this takes a while ...")
    api.upload_file(path_or_fileobj=CKPT, path_in_repo=CKPT_IN_REPO,
                    repo_id=REPO, repo_type="model",
                    commit_message=f"Add run 9 pruning-aware checkpoint (sha256 head+tail {fp[:16]})")
    print("  [PASS] checkpoint uploaded")
else:
    print(f"  [SKIP] {CKPT_IN_REPO}: {why}")

print()
print("=" * 74)
print(f"DONE -- https://huggingface.co/{REPO}")
print("=" * 74)
