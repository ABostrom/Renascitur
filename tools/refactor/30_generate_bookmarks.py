"""Generate Obsidian bookmark groups for the view library.

Reads `.obsidian/bookmarks.json`, removes any previously-generated
'Views' top-level group, and rebuilds it from the files under
`docs/_meta/views/`. Preserves all of Aaron's other bookmarks.

Output structure (in the Bookmarks sidebar pane):
  Views/
    📂 Views Index
    By type/
      All Continents, All Regions, All Settlements, ...
    By realm/
      Pyrosia, Mokoweri, Arcturia, ...
    By faction/
      Firebrand Empire, Dwarven Holds, Saurian Enclave, ...
    By era/
      Age of the Endless Sun, Age of Forging, ...
    Workflow/
      Stub Backlog, Drafts, Canon, Recently Edited, ...
    Cross-cutting/
      Magic Disciplines, Notable NPCs, Saurian Elders, ...

Also repairs Aaron's pre-existing 'Main Realm' bookmark whose path
(docs/Realms/Renascita) no longer exists after the folder restructure
— rewires it to docs/continents/Renascita.md.

Idempotent. Re-run anytime to refresh after adding/removing views.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refactor.common import REPO_ROOT, DOCS_DIR


BOOKMARKS_PATH = REPO_ROOT / ".obsidian" / "bookmarks.json"

VIEWS_ROOT = DOCS_DIR / "_meta" / "views"

# Subfolder name -> human-readable group title
GROUP_LABEL = {
    "by-type":         "By type",
    "by-realm":        "By realm",
    "by-faction":      "By faction",
    "by-era":          "By era",
    "workflow":        "Workflow",
    "cross-cutting":   "Cross-cutting",
}

# Order in which groups appear under the Views parent
GROUP_ORDER = ["by-type", "by-realm", "by-faction", "by-era", "workflow", "cross-cutting"]


def _ms_now() -> int:
    return int(time.time() * 1000)


def _file_bookmark(path: Path, title: str = None) -> Dict[str, Any]:
    """A file-leaf bookmark."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    item: Dict[str, Any] = {
        "type": "file",
        "ctime": _ms_now(),
        "path": rel,
    }
    if title:
        item["title"] = title
    return item


def _group(title: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "group",
        "ctime": _ms_now(),
        "title": title,
        "items": items,
    }


def build_views_group() -> Dict[str, Any]:
    """Construct the 'Views' bookmark group from the file tree."""
    sub_groups: List[Dict[str, Any]] = []

    # Top-level: the master Views index
    index_path = VIEWS_ROOT / "Views.md"
    if index_path.exists():
        sub_groups.append(_file_bookmark(index_path, "📖 Views Index"))

    # Each subfolder becomes a group
    for subname in GROUP_ORDER:
        subdir = VIEWS_ROOT / subname
        if not subdir.exists():
            continue
        items: List[Dict[str, Any]] = []
        for md in sorted(subdir.glob("*.md")):
            # Strip prefixes/extensions for cleaner title
            title = md.stem
            # Tighten the very long titles
            title = title.replace(" — Overview", "").replace(" — Dashboard", "").replace(" — Era Dashboard", "")
            items.append(_file_bookmark(md, title))
        if items:
            sub_groups.append(_group(GROUP_LABEL[subname], items))

    return _group("Views", sub_groups)


def repair_main_realm_bookmark(items: List[Dict[str, Any]]) -> bool:
    """If Aaron's old 'Main Realm' bookmark points at the removed
    docs/Realms/Renascita folder, repoint it to docs/continents/Renascita.md.
    """
    changed = False
    for item in items:
        if item.get("title") == "Main Realm" and item.get("path", "").startswith("docs/Realms/"):
            item["type"] = "file"
            item["path"] = "docs/continents/Renascita.md"
            changed = True
        # Recurse into groups
        if item.get("type") == "group" and isinstance(item.get("items"), list):
            if repair_main_realm_bookmark(item["items"]):
                changed = True
    return changed


def strip_existing_views_group(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return items without any top-level group titled 'Views' (for idempotency)."""
    return [it for it in items if not (it.get("type") == "group" and it.get("title") == "Views")]


def main() -> None:
    if BOOKMARKS_PATH.exists():
        with BOOKMARKS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = {"items": []}

    items: List[Dict[str, Any]] = data.get("items", [])

    # Repair the broken Main Realm bookmark if present
    if repair_main_realm_bookmark(items):
        print("Repaired: 'Main Realm' bookmark -> docs/continents/Renascita.md")

    # Remove any prior 'Views' group (re-run safety)
    before = len(items)
    items = strip_existing_views_group(items)
    if len(items) < before:
        print("Removed previous 'Views' group ({} items)".format(before - len(items)))

    # Append the freshly-built Views group
    views_group = build_views_group()
    items.append(views_group)

    data["items"] = items
    # Pretty-print, preserve UTF-8
    with BOOKMARKS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    # Report
    sub_count = sum(
        len(g.get("items", [])) for g in views_group["items"] if g.get("type") == "group"
    )
    print("Wrote {} (Views group: {} files in {} sub-groups + index)".format(
        BOOKMARKS_PATH.relative_to(REPO_ROOT),
        sub_count,
        len([g for g in views_group["items"] if g.get("type") == "group"]),
    ))


if __name__ == "__main__":
    main()
