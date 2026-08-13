#!/usr/bin/env python3
"""
Repairs a Jupyter notebook whose outputs are missing required fields.

Fixes:
  - stream outputs missing "name"        -> adds "stdout" (or "stderr" if it looks like a warning)
  - display_data / execute_result missing "metadata" -> adds {}
  - error outputs missing ename/evalue/traceback
  - cells missing "outputs" / "execution_count" / "metadata" / "id"

Usage:
    python fix_notebook_when_corrupted.py your_notebook.ipynb
Writes the repaired file next to the original as <name>.fixed.ipynb
"""

import json
import re
import sys
import shutil
from pathlib import Path

STDERR_HINTS = re.compile(
    r"warning|traceback|error|deprecat|site-packages|/lib/python", re.IGNORECASE
)


def as_text(value):
    if isinstance(value, list):
        return "".join(value)
    return value or ""


def fix_output(out):
    changes = []
    kind = out.get("output_type")

    if kind == "stream":
        if "name" not in out:
            text = as_text(out.get("text"))
            out["name"] = "stderr" if STDERR_HINTS.search(text) else "stdout"
            changes.append(f'stream: added name="{out["name"]}"')
        if "text" not in out:
            out["text"] = ""
            changes.append("stream: added empty text")

    elif kind in ("display_data", "execute_result"):
        if "metadata" not in out:
            out["metadata"] = {}
            changes.append(f"{kind}: added metadata")
        if "data" not in out:
            out["data"] = {}
            changes.append(f"{kind}: added data")
        if kind == "execute_result" and "execution_count" not in out:
            out["execution_count"] = None
            changes.append("execute_result: added execution_count")

    elif kind == "error":
        for key, default in (("ename", ""), ("evalue", ""), ("traceback", [])):
            if key not in out:
                out[key] = default
                changes.append(f"error: added {key}")

    return changes


def fix_cell(cell, index):
    changes = []

    if "metadata" not in cell:
        cell["metadata"] = {}
        changes.append("added metadata")
    if "source" not in cell:
        cell["source"] = ""
        changes.append("added source")
    if "id" not in cell:
        cell["id"] = f"cell-{index}"
        changes.append("added id")

    if cell.get("cell_type") == "code":
        if "outputs" not in cell:
            cell["outputs"] = []
            changes.append("added outputs")
        if "execution_count" not in cell:
            cell["execution_count"] = None
            changes.append("added execution_count")
        for out in cell["outputs"]:
            changes.extend(fix_output(out))

    return changes


def main(path_str):
    path = Path(path_str)
    if not path.exists():
        sys.exit(f"File not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        nb = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(
            f"The JSON itself is broken at line {exc.lineno}, column {exc.colno}: {exc.msg}\n"
            "This script only fixes missing fields, not broken JSON. "
            "Open the file in a text editor and look at that line."
        )

    # keep a backup of the original
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)

    nb.setdefault("nbformat", 4)
    nb.setdefault("nbformat_minor", 5)
    nb.setdefault("metadata", {})
    nb.setdefault("cells", [])

    total = 0
    for i, cell in enumerate(nb["cells"]):
        for change in fix_cell(cell, i):
            print(f"  cell {i}: {change}")
            total += 1

    out_path = path.with_suffix(".fixed.ipynb")
    out_path.write_text(
        json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\n{total} fixes applied.")
    print(f"Backup of original: {backup}")
    print(f"Repaired notebook:  {out_path}")

    try:
        import nbformat

        nbformat.validate(nbformat.read(str(out_path), as_version=4))
        print("Validation: PASSED")
    except ImportError:
        print("Validation skipped (nbformat not installed).")
    except Exception as exc:
        print(f"Validation: still failing -> {str(exc)[:300]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python fix_notebook_when_corrupted.py your_notebook.ipynb")
    main(sys.argv[1])
