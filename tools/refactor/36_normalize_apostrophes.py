"""Normalize curly apostrophes to straight in filenames and wikilinks.

Some filenames use U+2019 (curly right single quote: ') while their
frontmatter affiliations or wikilink references use U+0027 (straight
apostrophe: '). Result: wikilinks fail to resolve.

This script:
  1. Replaces U+2019 -> U+0027 inside every `[[...]]` wikilink in
     every file (body + frontmatter).
  2. Renames any file whose name contains U+2019 to use U+0027
     (via git mv).

After this, all wikilinks and filenames consistently use straight
apostrophes. Prose body text outside wikilinks is left untouched so
Aaron's stylistic curly quotes in prose survive.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import DOCS_DIR, REPO_ROOT


CURLY = "’"
STRAIGHT = "'"

WIKILINK_RE = re.compile(r"\[\[[^\]]+?\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def normalize_wikilinks_in_text(text: str) -> tuple:
    """Replace curly apostrophes with straight inside [[...]] only.
    Returns (new_text, replacements_count).
    """
    count = 0
    def _sub(m):
        nonlocal count
        original = m.group(0)
        normalized = original.replace(CURLY, STRAIGHT)
        if normalized != original:
            count += 1
        return normalized
    new_text = WIKILINK_RE.sub(_sub, text)

    # Also normalize within YAML frontmatter (where wikilinks aren't always
    # wrapped in [[]] capture but appear as quoted values).
    m = FRONTMATTER_RE.match(text)
    if m:
        fm = m.group(1)
        new_fm = fm.replace(CURLY, STRAIGHT)
        if new_fm != fm:
            count += 1
            new_text = "---\n{}\n---\n{}".format(new_fm, text[m.end():])
            # Re-apply wikilink normalization on body in case we just rebuilt
            body = text[m.end():]
            new_body = WIKILINK_RE.sub(_sub, body)
            new_text = "---\n{}\n---\n{}".format(new_fm, new_body)

    return new_text, count


def main() -> None:
    # 1. Walk docs/ + templates/, normalize wikilinks in text
    targets = list(DOCS_DIR.rglob("*.md"))
    templates_dir = REPO_ROOT / "templates"
    if templates_dir.exists():
        targets.extend(sorted(templates_dir.glob("*.md")))

    text_files_changed = 0
    total_replacements = 0
    for path in targets:
        text = path.read_text(encoding="utf-8")
        new_text, n = normalize_wikilinks_in_text(text)
        if n > 0:
            with path.open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_text)
            text_files_changed += 1
            total_replacements += n

    # 2. Rename files with curly apostrophes in name
    files_renamed = 0
    # Need to rebuild the file list after the text changes
    curly_named = [p for p in DOCS_DIR.rglob("*.md") if CURLY in p.name]
    for path in curly_named:
        new_name = path.name.replace(CURLY, STRAIGHT)
        new_path = path.with_name(new_name)
        if new_path.exists():
            print("Skip (dst exists): {}".format(new_name))
            continue
        try:
            subprocess.run(
                ["git", "mv",
                 str(path.relative_to(REPO_ROOT)),
                 str(new_path.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            )
            files_renamed += 1
            print("Renamed: {} -> {}".format(path.name, new_name))
        except subprocess.CalledProcessError as e:
            print("FAIL: {} :: {}".format(path.name, e.stderr.strip()))

    # 3. Same for folder names containing curly apostrophes
    curly_dirs = [p for p in DOCS_DIR.rglob("*") if p.is_dir() and CURLY in p.name]
    dirs_renamed = 0
    for path in curly_dirs:
        new_name = path.name.replace(CURLY, STRAIGHT)
        new_path = path.with_name(new_name)
        if new_path.exists():
            print("Skip dir (dst exists): {}".format(new_name))
            continue
        try:
            subprocess.run(
                ["git", "mv",
                 str(path.relative_to(REPO_ROOT)),
                 str(new_path.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True,
            )
            dirs_renamed += 1
            print("Renamed dir: {} -> {}".format(path.name, new_name))
        except subprocess.CalledProcessError as e:
            print("FAIL dir: {} :: {}".format(path.name, e.stderr.strip()))

    print("---")
    print("Text-files with normalized wikilinks: {} (replacements: {})".format(
        text_files_changed, total_replacements))
    print("Files renamed: {}".format(files_renamed))
    print("Dirs renamed: {}".format(dirs_renamed))


if __name__ == "__main__":
    main()
