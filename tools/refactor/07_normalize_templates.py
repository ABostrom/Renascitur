"""Apply the same hyphen->underscore key normalization to templates/.

Templater expressions like `<% tp.date.now("YYYY-MM-DD") %>` contain
hyphens and must not be touched. We only rewrite hyphenated keys
that appear at the start of a frontmatter line.

Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT

TEMPLATES_DIR = REPO_ROOT / "templates"

# Match lines like `key-with-hyphens: value` at the start of a line.
# Avoid matching `aat-*` and avoid matching anywhere `<%` appears (Templater
# expressions can be on the value side; the key side is always safe before `:`).
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*?)(\s*:)")

PRESERVE_PREFIXES = ("aat-",)


def normalize_key(key: str) -> str:
    if any(key.startswith(p) for p in PRESERVE_PREFIXES):
        return key
    return key.replace("-", "_") if "-" in key else key


def normalize_line(line: str) -> str:
    """If line begins with `key: ...`, rename the key part only."""
    m = FRONTMATTER_KEY_RE.match(line)
    if not m:
        return line
    key = m.group(1)
    new_key = normalize_key(key)
    if new_key == key:
        return line
    return new_key + line[len(key):]


def normalize_template(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    # We only operate within the frontmatter block (between the first two `---`).
    if not lines or lines[0].strip() != "---":
        return 0
    fm_end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            fm_end = i
            break
    if fm_end is None:
        return 0
    changed = 0
    for i in range(1, fm_end):
        new_line = normalize_line(lines[i])
        if new_line != lines[i]:
            lines[i] = new_line
            changed += 1
    if changed:
        new_text = "\n".join(lines)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
    return changed


def main() -> None:
    total_changed = 0
    files_touched = 0
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        n = normalize_template(path)
        if n:
            files_touched += 1
            total_changed += n
            print("{}: {} key(s)".format(path.name, n))
    print("Templates touched: {}".format(files_touched))
    print("Keys renamed: {}".format(total_changed))


if __name__ == "__main__":
    main()
