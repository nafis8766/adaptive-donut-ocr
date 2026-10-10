"""Publish run 9's checkpoint and its model card to the Hugging Face Hub.

Run 9 is the pruning-aware checkpoint every headline figure in this project comes from:
5 epochs with pruning ON at keep_ratio=0.50 plus ink-BCE router supervision, resumed from
the unpruned FUNSD fine-tune. AGENTS.md records its size as 1045901771 bytes under run 13's
`provenance.eval_ckpt`, and this script ASSERTS that before uploading anything -- the one
thing that must not happen is publishing a different checkpoint under run 9's results.

Why a script rather than a CLI one-liner: the size assertion, the head+tail fingerprint
(AGENTS.md's own convention for tying a results table to weights), and the card-source
check are all things a one-liner would skip, and this is an irreversible public action.

Usage:
    python hf/upload_model.py            # dry run: verify everything, upload nothing
    python hf/upload_model.py --push     # actually create the repo and upload
"""
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(ROOT, "run 9", "adaptive_donut_pruned.pt")
CARD = os.path.join(ROOT, "hf", "MODEL_CARD.md")
REPO = "nafis8766/adaptive-donut-ocr-router"

# From AGENTS.md: run 13's provenance.eval_ckpt names run 9's weights at this exact size.
# Run 5's is 1045901275 -- 496 bytes smaller, and attaching it by mistake is precisely what
# made run 12's headline an artifact. So the size is the guard, not a comment.
EXPECTED_BYTES = 1045901771
RUN5_BYTES = 1045901275

push = "--push" in sys.argv

print("=" * 74)
print(f"Hugging Face upload -- {REPO}")
print("=" * 74)

# ---------------------------------------------------------------- pre-flight assertions
assert os.path.exists(CKPT), f"checkpoint not found: {CKPT}"
assert os.path.exists(CARD), f"model card not found: {CARD}"

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
print("  uploading README.md ...")
api.upload_file(path_or_fileobj=CARD, path_in_repo="README.md",
                repo_id=REPO, repo_type="model",
                commit_message="Add model card with scope limits and licence position")
print("  [PASS] README.md uploaded")

print(f"  uploading adaptive_donut_pruned.pt ({size / 1048576:.0f} MiB) -- this takes a while ...")
api.upload_file(path_or_fileobj=CKPT, path_in_repo="adaptive_donut_pruned.pt",
                repo_id=REPO, repo_type="model",
                commit_message=f"Add run 9 pruning-aware checkpoint (sha256 head+tail {fp[:16]})")
print("  [PASS] checkpoint uploaded")

print()
print("=" * 74)
print(f"DONE -- https://huggingface.co/{REPO}")
print("=" * 74)
