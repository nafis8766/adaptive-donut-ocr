"""Fix a latent NameError in the data-pipeline cell of kaggle_token_pruning_ocr.ipynb.

The cell defines `test_ds = DocumentDataset(...)` AFTER the `if EVAL_ONLY / else`
block, but the `else` branch prints `Test samples: {len(test_ds)}` before that
definition -> NameError whenever the else branch runs (i.e. any non-eval-only
training, or the new DO_TRAIN pruning-ON retrain). Eval-only runs (run 6) hid it
because the else branch was skipped. The second `print(f'Test samples: ...')`
(still inside the module-level test_ds definition) already reports the count, so
the forward reference in the first print is redundant and is simply dropped.

Asserted, ast-checked, idempotent.
"""
import ast
import json
import os

NB = "kaggle_token_pruning_ocr.ipynb"
nb = json.loads(open(NB, encoding="utf-8").read())
cells = nb["cells"]

# Find the data-pipeline code cell (the one defining DocumentDataset).
idx = next(i for i, c in enumerate(cells)
           if c["cell_type"] == "code" and "class DocumentDataset" in "".join(c["source"]))
src = "".join(cells[idx]["source"])

OLD = "    print(f'Train samples: {len(train_ds)}, Test samples: {len(test_ds)}')"
NEW = "    print(f'Train samples: {len(train_ds)}')"
n = src.count(OLD)
assert n == 1, f"expected exactly 1 occurrence of the buggy print, found {n}"
src = src.replace(OLD, NEW)

ast.parse(src)
cells[idx]["source"] = src.splitlines(keepends=True)
with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(f"fixed {NB} (data-pipeline cell {idx}): dropped forward-referenced test_ds in print")
