"""Verify cell 15's PROVENANCE block (Pending 6) -- statically AND by executing it.

Two things could go wrong with a provenance stamp, and only one of them is visible to a
grep. The obvious one is that it does not reach the JSON. The dangerous one is that it
reaches the JSON while being *decorative*: a stamp that echoes a variable instead of
reading the file would look identical in every output, would pass any "is the key
present" check, and would still let a results file be attributed to the wrong
checkpoint -- which is the exact failure (diagnose_decoder.py's silent fall-through to an
older run) this stamp exists to prevent.

So section 2 stamps a file, MUTATES that file, re-stamps it, and requires the two stamps
to differ. A constant-returning implementation fails that and passes everything else.

Sections:
  1. static shape -- the block exists, lands after `rows = []` (so
     verify_harness_control.py's own extraction is unchanged), and reaches BOTH writes
  2. execution -- happy path, the mutation check above, and five degraded inputs that
     must each yield a recorded reason rather than an exception
  3. the writes -- exec the two real `json.dump` statements and read provenance back off
     disk, because "the key is in the source" is not "the key is in the file"

Usage:
    PYTHONIOENCODING=utf-8 python scripts/verify_results_provenance.py [notebook]
Defaults to the canonical notebook; pass kaggle_pruning_run.ipynb to check the file that
actually runs on Kaggle (the generator copies cell 15 verbatim, but verify, don't assume).
Exit 0 iff every check passes.
"""
import json
import os
import sys
import tempfile
import textwrap
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kaggle_token_pruning_ocr.ipynb")

npass = nfail = 0


def check(ok, label, detail=""):
    global npass, nfail
    if ok:
        npass += 1
    else:
        nfail += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""))
    return ok


src = "".join(json.load(open(NB, encoding="utf-8"))["cells"][15]["source"])

print("=" * 74)
print(f"1. STATIC SHAPE  ({os.path.basename(NB)})")
print("=" * 74)

if not check("PROVENANCE = {" in src, "cell 15 has a PROVENANCE block"):
    print("\n  block absent -- this is the expected state BEFORE the patch; run")
    print("  scripts/patch_notebook_provenance.py.")
    print(f"\n{npass} passed, {nfail} failed")
    raise SystemExit(1)

BEGIN = next(l for l in src.splitlines() if l.startswith("# --") and l.endswith("PROVENANCE"))
# The sweep loop that closes the provenance block. The canonical notebook iterates
# SELECTION_CONFIGS; the GENERATED one iterates ALL_CONFIGS with two extra loop vars
# (make_kaggle_pruning_notebook.py, patch G4). Hard-coding the canonical form made
# this whole file raise on kaggle_pruning_run.ipynb -- so the check that closed
# Pending 6, and that caught run 12's wrong checkpoint, was not actually covering the
# notebook runs 12-14 were produced by. Match either, and say so if neither is there.
END = next((l for l in src.splitlines()
            if l.startswith("for _name, _kr, _mode") and l.rstrip().endswith(":")), None)
assert END is not None, (
    "sweep-loop anchor not found: expected a line starting 'for _name, _kr, _mode'")
block = textwrap.dedent(src[src.index(BEGIN):src.index(END)])

check(src.count("PROVENANCE = {") == 1, "exactly one PROVENANCE assignment")
check(src.count("'provenance': PROVENANCE") == 2,
      "provenance reaches BOTH json writes", "partial (after every row) and final")
check(src.index("\nrows = []") < src.index(BEGIN),
      "block lands AFTER `rows = []`",
      "verify_harness_control.py extracts src[BEGIN:index('\\nrows = []')]")
check("PROVENANCE" not in src[src.index("# ---------------------------------------"
                                        "------------------------- HARNESS CONTROL")
                              : src.index("\nrows = []")],
      "harness-control block is unchanged by this patch",
      "that verifier keeps testing what it was written to test")
check(src.index("_ctrl_ckpt = ") < src.index(BEGIN),
      "both checkpoint variables are defined before the block reads them")
check("json.dumps(PROVENANCE)" in block,
      "the dict is proven JSON-able at build time",
      "the first write lands minutes of GPU in, not at the top of the cell")
for tok in ("raise ", "assert ", "sys.exit"):
    check(tok not in block, f"block cannot abort the run ({tok.strip()!r} absent)",
          "provenance is bookkeeping; it must never cost a session")

print()
print("=" * 74)
print("2. EXECUTION")
print("=" * 74)

TMP = tempfile.mkdtemp(prefix="provenance_")
EVAL_PATH = os.path.join(TMP, "adaptive_donut_pruned.pt")
CTRL_PATH = os.path.join(TMP, "run5.pt")
with open(EVAL_PATH, "wb") as f:
    f.write(b"x" * 4096)
with open(CTRL_PATH, "wb") as f:
    f.write(b"y" * 512)


class _P:
    def __init__(self, device):
        self.device = device


def run_block(*, eval_ckpt=EVAL_PATH, ctrl_ckpt=CTRL_PATH, device="cpu",
              params=True, torch_stub=None, no_transformers=False):
    """Exec the extracted block against stubs. Returns the namespace, or raises."""
    torch_stub = torch_stub or types.SimpleNamespace(
        __version__="2.12.1+cpu",
        cuda=types.SimpleNamespace(get_device_name=lambda d: f"NVIDIA STUB ({d})"))
    model = types.SimpleNamespace(
        parameters=lambda: iter([_P(device)] if params else []))
    ns = {"os": os, "time": time, "json": json, "torch": torch_stub, "model": model,
          "_eval_ckpt": eval_ckpt, "_ctrl_ckpt": ctrl_ckpt}
    saved = sys.modules.get("transformers", "<absent>")
    if no_transformers:
        sys.modules["transformers"] = None          # makes `import transformers` raise
    try:
        exec(compile(block, "<cell15-provenance>", "exec"), ns)
    finally:
        if no_transformers:
            if saved == "<absent>":
                sys.modules.pop("transformers", None)
            else:
                sys.modules["transformers"] = saved
    return ns


print("\n  A. happy path")
ns = run_block()
P = ns["PROVENANCE"]
check(set(P) == {"eval_ckpt", "control_ckpt", "transformers", "torch", "device",
                 "device_name", "written"},
      "all seven fields present", ", ".join(sorted(P)))
check(P["eval_ckpt"]["path"] == EVAL_PATH, "eval checkpoint path recorded")
check(P["eval_ckpt"]["size_bytes"] == 4096, "eval size read off disk",
      f"{P['eval_ckpt']['size_bytes']} B")
check(P["control_ckpt"]["size_bytes"] == 512, "control size read off disk",
      "the two stamps are not the same object")
check("error" not in P["eval_ckpt"] and "error" not in P["control_ckpt"],
      "no error key on the happy path")
check(P["torch"] == "2.12.1+cpu", "torch version stamped", P["torch"])
check(P["transformers"] not in (None, "", "unknown")
      and not P["transformers"].startswith("unavailable"),
      "transformers version stamped", P["transformers"])
check(P["device"] == "cpu" and P["device_name"] == "cpu", "cpu device recorded")
check(P["written"].endswith("Z") and P["written"][4] == "-",
      "written timestamp is ISO-ish UTC", P["written"])

print("\n  B. the stamp READS THE FILE -- mutate it and the stamp must move")
print("     (a constant-returning _ckpt_stamp passes every other check in this file)")
before = ns["PROVENANCE"]["eval_ckpt"]
time.sleep(1.1)                       # coarse mtime resolution on some filesystems
with open(EVAL_PATH, "ab") as f:
    f.write(b"z" * 100)
after = run_block()["PROVENANCE"]["eval_ckpt"]
check(after["size_bytes"] == before["size_bytes"] + 100,
      "size_bytes tracks the file", f"{before['size_bytes']} -> {after['size_bytes']}")
check(after["mtime"] != before["mtime"],
      "mtime tracks the file", f"{before['mtime']} -> {after['mtime']}")
check(after["path"] == before["path"], "path is stable across the mutation")

print("\n  C. degraded inputs -- each must RECORD a reason, never raise")
ns = run_block(eval_ckpt=os.path.join(TMP, "does_not_exist.pt"))
e = ns["PROVENANCE"]["eval_ckpt"]
# `.get`, not `[...]`: a stamp that silently drops the error key should be reported as a
# FAIL here, not raise a KeyError that hides the rest of section C.
check("Error" in str(e.get("error", "")), "missing file -> error string", str(e))
check(str(e.get("path", "")).endswith("does_not_exist.pt"),
      "missing file still records the path it looked for",
      "'we looked and it was not there' != 'this file predates provenance'")

ns = run_block(eval_ckpt=None)
e = ns["PROVENANCE"]["eval_ckpt"]
check(e == {"path": None,
            "error": "no checkpoint variable set (EVAL_CKPT / RESUME_CKPT)"},
      "unset checkpoint -> explicit reason", str(e))

ns = run_block(params=False)
check(ns["PROVENANCE"]["device"] == "unknown"
      and ns["PROVENANCE"]["device_name"] == "unknown",
      "model with no parameters -> device 'unknown'")

ns = run_block(device="cuda:0")
check(ns["PROVENANCE"]["device"] == "cuda:0"
      and "STUB" in ns["PROVENANCE"]["device_name"],
      "cuda device -> name comes from torch.cuda.get_device_name",
      ns["PROVENANCE"]["device_name"])

ns = run_block(device="cuda:0", torch_stub=types.SimpleNamespace(
    __version__="2.12.1", cuda=types.SimpleNamespace(
        get_device_name=lambda d: (_ for _ in ()).throw(RuntimeError("no driver")))))
check(ns["PROVENANCE"]["device_name"] == "cuda (name unavailable)",
      "a raising get_device_name degrades instead of killing the run")

ns = run_block(no_transformers=True)
check(ns["PROVENANCE"]["transformers"].startswith("unavailable"),
      "an unimportable transformers degrades to a recorded reason",
      ns["PROVENANCE"]["transformers"])
check(ns["PROVENANCE"]["torch"] == "2.12.1+cpu",
      "and the other fields still populate")

ns = run_block(torch_stub=types.SimpleNamespace(cuda=types.SimpleNamespace()))
check(ns["PROVENANCE"]["torch"] == "unknown",
      "a torch without __version__ degrades to 'unknown'")

print()
print("=" * 74)
print("3. THE WRITES -- provenance must land on disk, not just in the source")
print("=" * 74)

PARTIAL = textwrap.dedent(src[src.index("    with open(SELECTION_OUT, 'w') as f:"):
                              src.index("\nhdr = (")])
FINAL = src[src.index("\nwith open(SELECTION_OUT, 'w') as f:"):
            src.index("\nprint(f'\\nWrote {SELECTION_OUT}")]

OUT = os.path.join(TMP, "ablation_selection.json")
ROW = {"config": "keep=1.00 router CONTROL", "keep_ratio": 1.0, "select_mode": "router",
       "word_recall_pct": 79.63, "character_accuracy_pct": 64.81,
       "word_order_pct": 54.08, "num_eval_samples": 50}
PROV = run_block()["PROVENANCE"]


def write_ns():
    # The generated notebook's final write also serialises the Q6 block and prints an
    # elapsed time, so its `json.dump` needs five names the canonical notebook's does
    # not. Stubbed with sentinels rather than realistic values: nothing here is under
    # test except that PROVENANCE survives the round trip, and a sentinel that showed
    # up inside a provenance stamp would be obvious.
    return {"open": open, "json": json, "SELECTION_OUT": OUT,
            "RUN6_REFERENCE": (77.74, 64.70, 53.05), "SELECTION_SEED": 0,
            "SELECTION_MAX_LEN": 512, "MAX_WORDS": 128, "harness_verified": True,
            "harness_note": "verified", "harness_row": ROW, "PROVENANCE": PROV,
            "rows": [ROW], "drift": 0.0, "ctrl": ROW, "_ctrl_ckpt": CTRL_PATH,
            "Q6_RESOLUTION_PTS": -1.0, "q6_rows": [], "sabotage_row": None,
            "time": time, "_t0": time.perf_counter()}


for label, code in (("partial write (after every row)", PARTIAL), ("final write", FINAL)):
    if os.path.exists(OUT):
        os.remove(OUT)
    exec(compile(code, f"<cell15-{label}>", "exec"), write_ns())
    meta = json.load(open(OUT))["meta"]
    got = meta.get("provenance")
    check(got == PROV, f"{label}: provenance round-trips to disk intact",
          "" if got == PROV else f"got {got!r}")
    check(got and got["eval_ckpt"]["size_bytes"] == PROV["eval_ckpt"]["size_bytes"],
          f"{label}: the checkpoint stamp survives serialisation")

print()
print("=" * 74)
print(f"{npass} passed, {nfail} failed")
print("=" * 74)
raise SystemExit(1 if nfail else 0)
