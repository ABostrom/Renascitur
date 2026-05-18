# Typed-Vault Initial-Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perform a pure-structural sweep of the Renascitur lore vault: every `.md` file under `docs/` gets a `type:` and `status:` in frontmatter; the four History/Age folders are renamed to canonical flavor names; history event files gain sortable code-year prefixes; 23 typed templates land in `templates/`; `_meta/` Dataview indices materialize; Templater + linter rules are configured. Zero prose authoring — Aaron's hands-on time is reviewing diffs and merging.

**Architecture:** Migration is performed by a small set of idempotent Python scripts under `tools/refactor/`. Each script has a `--dry-run` (default) and `--apply` mode. Output of each dry-run is a CSV or unified diff the user reviews before applying. Folder/file renames go through `git mv` to preserve history. Mass frontmatter writes use PyYAML for round-trip safety.

**Tech Stack:**
- Python ≥3.7 (Aaron has 3.7.10 in Anaconda at `D:\Anaconda\python.exe`)
- PyYAML (one-time `pip install pyyaml`)
- Git on Windows + PowerShell shell
- Obsidian vault format (YAML frontmatter, `[[wikilinks]]`, file aliases)

**Approach:**
1. Set up branch + tools scaffold.
2. Write the spec/conventions file and the 23 templates first — they don't touch existing notes.
3. Build the type-inference dry-run; Aaron reviews the inference rules and the preview CSV before any note is mutated.
4. Apply frontmatter, then renames, then skeletons, then indices, then config.
5. Four checkpoints for review along the way. Aaron merges to master at the end.

**Author:** Plan generated 2026-05-18 from `notes/refactor-design.md`.

---

## File Structure

### Files this plan creates

```
tools/refactor/
  requirements.txt
  __init__.py
  common.py                       — shared helpers (frontmatter parsing, paths)
  rules.py                        — type-inference rules (Aaron reviews this)
  00_infer_types.py               — outputs inference_preview.csv
  01_apply_frontmatter.py         — applies migration from CSV
  02_rename_age_folders.py        — renames 4 History age folders + adds aliases
  03_rename_history_events.py     — adds CODE-YYYY prefix to event files
  04_create_skeletons.py          — race summaries, promoted-realm folders, era + heavy-event shells
  05_create_meta.py               — _meta/ Conventions.md + 6 Dataview index files
  06_install_templates.py         — installs the 23 templates
  inference_preview.csv           — generated; reviewed before apply
  inference_overrides.csv         — empty file for Aaron's manual overrides

templates/                         — REPLACED by the 23 typed templates
  Continent.md
  Region.md
  Settlement.md
  Landmark.md
  Waterway.md
  Range.md
  Character.md
  Race.md
  Culture.md
  Faction.md
  House.md
  Organisation.md
  Era.md
  Event.md
  Myth.md
  Chronicle.md
  Prophecy.md
  Artifact.md
  Item.md
  Resource.md
  Technology.md
  Deity.md
  CosmicForce.md
  Tradition.md
  Language.md
  Essay.md

docs/_meta/                        — new
  Conventions.md
  Stub Backlog.md
  NPCs by Faction.md               — Dataview
  Locations by Realm.md            — Dataview
  Factions of Renascita.md         — Dataview
  Campaign Reference.md            — Dataview
  Timeline.md                      — Dataview

docs/Races/Humans/Elasi/Elasi.md           — new skeleton
docs/Races/Humans/Terran/Terran.md         — new skeleton
docs/Races/Kyojin/Leonin/Leonin.md         — new skeleton
docs/Races/Kyojin/Orcs/Orcs.md             — new skeleton
docs/Races/Grundthains/Dwarves/Dwarves.md  — new skeleton

docs/Realms/Solirion/Solirion.md           — promoted skeleton
docs/Realms/Nihilum/Nihilum.md             — promoted skeleton
docs/Realms/Thargrun/Thargrun.md           — promoted skeleton
docs/Realms/Veltharyn/Veltharyn.md         — promoted skeleton
docs/Realms/Woudum/Woudum.md               — promoted skeleton
docs/Realms/Sigmora/Sigmora.md             — promoted skeleton
docs/Realms/Infernum/Infernum.md           — promoted skeleton
docs/Realms/Imperium/Imperium.md           — promoted skeleton

docs/History/Age of the Endless Sun/Age of the Endless Sun.md  — era summary skeleton
docs/History/Age of Forging/Age of Forging.md                  — era summary skeleton
docs/History/Age of Stagnation/Age of Stagnation.md            — era summary skeleton
docs/History/Age of Night/Age of Night.md                      — era summary skeleton

docs/History/Age of Forging/AF0000 Hexweave Binding.md         — already exists, gets frontmatter shell + rename
docs/History/Age of Forging/AF0000 The Forge Wars.md           — already exists, gets frontmatter shell + rename
docs/History/Age of Stagnation/AS0000 Breaking of the Hexweave Seal.md  — exists, gets rename
docs/Cosmology/.../Machinery of Death.md                       — created if missing

.obsidian/community-plugins.json   — modified (add templater-obsidian)
.obsidian/plugins/obsidian-linter/data.json  — modified (require type+status)
mkdocs.yml                          — minimal nav patch
```

### Files this plan DOES NOT TOUCH
- `src/` (Python lib) — Phase 4 work
- Existing event/note bodies — only frontmatter is added; prose is untouched
- Image files

---

## Pre-flight

### P.1 — Branch off master

- [ ] **Step 1: Create and switch to refactor branch**

```powershell
cd C:\Users\Aaron\Documents\Renascitur
git status
git checkout -b refactor/typed-vault-initial-pass
git status
```

Expected: working tree clean except for `docs/Realms/Renascita/Societies/Saurian Enclave/Contents of the Archive of the Ancients.md` (M) and `src/main.py` (M) and untracked `src/renasci/traits/`. New branch active.

- [ ] **Step 2: Stash pre-existing in-flight changes**

```powershell
git stash push -u -m "pre-refactor in-flight"
git status
```

Expected: working tree fully clean. Stash retains Aaron's WIP for restoration after merge.

### P.2 — Install PyYAML

- [ ] **Step 3: Install PyYAML in Aaron's Python environment**

```powershell
& "D:\Anaconda\python.exe" -m pip install pyyaml
& "D:\Anaconda\python.exe" -c "import yaml; print(yaml.__version__)"
```

Expected: PyYAML installed; version string printed.

### P.3 — Scaffold tools/refactor/

- [ ] **Step 4: Create the tools directory**

```powershell
New-Item -ItemType Directory -Force tools\refactor | Out-Null
```

- [ ] **Step 5: Write `tools/refactor/requirements.txt`**

File: `tools/refactor/requirements.txt`
```
pyyaml>=5.4
```

- [ ] **Step 6: Write `tools/refactor/__init__.py`**

File: `tools/refactor/__init__.py`
```python
# Marker for Python package; intentionally empty.
```

- [ ] **Step 7: Write `tools/refactor/common.py`** — shared helpers

File: `tools/refactor/common.py`
```python
"""Shared helpers for the typed-vault refactor scripts.

This module provides:
- REPO_ROOT, DOCS_DIR: project paths anchored to this file's location
- read_frontmatter(path): returns (metadata_dict, body_str)
- write_frontmatter(path, metadata, body): writes file atomically
- iter_md_files(): yields every .md path under DOCS_DIR
- ensure_list(value): coerces scalar-or-list to list
- merge_metadata(existing, new): merges dicts, preserving existing keys
- git_mv(src, dst): runs `git mv` and raises on failure
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import yaml

# Anchor: tools/refactor/common.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"

FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)


def read_frontmatter(path: Path) -> Tuple[Dict, str]:
    """Return (metadata_dict, body_string) for a markdown file.

    Files without frontmatter return ({}, full_content).
    """
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        metadata = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        print(f"WARN: YAML error in {path}: {e}", file=sys.stderr)
        return {}, text
    if not isinstance(metadata, dict):
        # e.g. file starts with --- but content is a list at top level; bail out safely
        return {}, text
    return metadata, body


def write_frontmatter(path: Path, metadata: Dict, body: str) -> None:
    """Write a markdown file with the given frontmatter and body.

    Empty metadata writes the body alone (no frontmatter block).
    """
    if metadata:
        # Preserve wikilink quoting; default_flow_style=False for block style.
        front = yaml.safe_dump(
            metadata,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=10**9,  # don't line-wrap long strings
        )
        # Ensure exactly one blank line between body and frontmatter.
        if not body.startswith("\n"):
            body = "\n" + body
        text = f"---\n{front}---{body}"
    else:
        text = body
    path.write_text(text, encoding="utf-8", newline="\n")


def iter_md_files(root: Path = DOCS_DIR) -> Iterator[Path]:
    """Yield every .md file under root, sorted for deterministic output."""
    for p in sorted(root.rglob("*.md")):
        yield p


def ensure_list(value) -> List:
    """Coerce a scalar, None, or list into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def merge_metadata(existing: Dict, new: Dict) -> Dict:
    """Merge new into existing without overwriting existing keys.

    Lists are extended (deduplicated, order-preserving).
    Returns a new dict.
    """
    out = dict(existing)
    for key, val in new.items():
        if key not in out:
            out[key] = val
        elif isinstance(out[key], list) and isinstance(val, list):
            seen = set()
            merged = []
            for item in out[key] + val:
                key_for_set = repr(item)
                if key_for_set not in seen:
                    seen.add(key_for_set)
                    merged.append(item)
            out[key] = merged
    return out


def git_mv(src: Path, dst: Path) -> None:
    """Run `git mv` from the repo root. Raises CalledProcessError on failure."""
    rel_src = src.relative_to(REPO_ROOT)
    rel_dst = dst.relative_to(REPO_ROOT)
    subprocess.run(
        ["git", "mv", str(rel_src), str(rel_dst)],
        cwd=REPO_ROOT,
        check=True,
    )


def rel_to_docs(path: Path) -> str:
    """Path relative to DOCS_DIR, as a forward-slash POSIX string."""
    return path.relative_to(DOCS_DIR).as_posix()
```

- [ ] **Step 8: Commit pre-flight scaffold**

```powershell
git add tools/refactor/
git commit -m @'
refactor: scaffold tools/refactor for typed-vault migration

Adds shared helpers (PyYAML-based frontmatter round-trip,
git mv wrapper, file iteration) used by the migration scripts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 1: Write `_meta/Conventions.md` and the 23 templates

**Files:**
- Create: `docs/_meta/Conventions.md`
- Create: 23 files under `templates/` (replacing existing 6)

### 1.1 — Conventions doc

- [ ] **Step 1: Create `docs/_meta/` directory**

```powershell
New-Item -ItemType Directory -Force docs\_meta | Out-Null
```

- [ ] **Step 2: Write `docs/_meta/Conventions.md`**

File: `docs/_meta/Conventions.md`
```markdown
---
type: essay
status: canon
topic: vault conventions
---

# Renascitur Vault Conventions

*Living reference for the typed-vault schema. Last updated 2026-05-18.*

## Note types (23)

Every reference note declares its `type:` in frontmatter. Long-form prose without a categorical home uses `type: essay`. The full vocabulary, grouped:

**Geography (6):** `continent`, `region`, `settlement`, `landmark`, `waterway`, `range`

**People & groups (6):** `character`, `race`, `culture`, `faction`, `house`, `organisation`

**Time & history (4):** `era`, `event`, `myth`, `chronicle`

**Things (4):** `artifact`, `item`, `resource`, `technology`

**Concepts (4):** `deity`, `cosmic-force`, `tradition`, `language`

**Meta (2):** `essay`, `prophecy`

## Universal frontmatter

Every typed note:
- `type:` — one of the 23 above
- `status:` — `stub` | `draft` | `canon` | `archived`
- `tags:` — free-form list
- `created:` — auto-set by Templater
- `updated:` — auto-set by Templater

## The four Ages

| Age              | Code | Folder                              | Display |
|------------------|------|-------------------------------------|---------|
| First Age        | `ES` | `History/Age of the Endless Sun/`   | `ES 412` |
| Second Age       | `AF` | `History/Age of Forging/`           | `AF 412` |
| Third Age        | `AS` | `History/Age of Stagnation/`        | `AS 412` |
| Fourth Age       | `AN` | `History/Age of Night/`             | `AN 412` |

Event and chronicle filenames use a 4-digit zero-padded year prefix: `AF0412 Hexweave Binding.md`. Year `0000` is reserved for "undated within the era." Aliases preserve old names so existing `[[wikilinks]]` still resolve.

## Authoring rules

- `status: stub` files have *only* frontmatter and the title. They are valid; they live in `_meta/Stub Backlog.md`.
- Long-form prose (`type: essay`, `type: chronicle`) has no rigid template; only the frontmatter is fixed.
- Frontmatter wikilinks are always quoted: `era: "[[Age of Forging]]"`.
- Cross-references (`participants:`, `chronicled-in:`, etc.) are link lists.

See also: `notes/refactor-design.md` for the design rationale; `notes/working-model.md` for what the vault looked like before the refactor.
```

### 1.2 — Templates (23 files)

For brevity, each template uses Obsidian's `{{title}}` placeholder + Templater's `<% tp.date.now() %>` for timestamps. Templater config (Task 11) wires these in.

- [ ] **Step 3: Write `templates/Continent.md`**

```markdown
---
type: continent
status: draft
tags: []
era: ""
terrain: []
inhabited_by: []
provinces: []
cities: []
mountains: []
rivers: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Overview

## Geography

## History

## Cultures and inhabitants
```

- [ ] **Step 4: Write `templates/Region.md`**

```markdown
---
type: region
status: draft
tags: []
continent: ""
era: ""
features: []
settlements: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Overview

## Geography

## History
```

- [ ] **Step 5: Write `templates/Settlement.md`**

```markdown
---
type: settlement
status: draft
tags: []
size: village    # hamlet | village | town | city | great-city | hold
continent: ""
region: ""
era-founded: ""
controlled-by: ""
populated-by: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Overview

## Inhabitants

## Notable locations

## History
```

- [ ] **Step 6: Write `templates/Landmark.md`**

```markdown
---
type: landmark
status: draft
tags: []
continent: ""
region: ""
inside: ""     # e.g. "[[Eltabarr]]" for a district
era: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## Significance
```

- [ ] **Step 7: Write `templates/Waterway.md`**

```markdown
---
type: waterway
status: draft
tags: []
continent: ""
kind: river   # river | lake | sea | coast | estuary
source: ""
mouth: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Course

## Significance
```

- [ ] **Step 8: Write `templates/Range.md`**

```markdown
---
type: range
status: draft
tags: []
continent: ""
kind: range   # range | peak | massif
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Geography

## Inhabitants

## History
```

- [ ] **Step 9: Write `templates/Character.md`**

```markdown
---
type: character
status: draft
tags: []
race: ""
culture: ""
affiliation: ""
location: ""
era: ""
aliases: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Appearance

## Personality

## History

## Connections
```

- [ ] **Step 10: Write `templates/Race.md`**

```markdown
---
type: race
status: draft
tags: []
lineage: ""
origin-plane: ""
era-of-origin: ""
spoken-languages: []
related-cultures: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Origins

## Appearance

## Abilities

## Variants
```

- [ ] **Step 11: Write `templates/Culture.md`**

```markdown
---
type: culture
status: draft
tags: []
races: []
homeland: ""
era-bloom: ""
era-decline: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Overview

## Values and beliefs

## Practices

## History
```

- [ ] **Step 12: Write `templates/Faction.md`**

```markdown
---
type: faction
status: draft
tags: []
realm: ""
era-founded: ""
era-dissolved: ""
alignment: ""
leadership: []
seats-of-power: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Origins

## Beliefs / agenda

## Structure

## Notable figures

## History
```

- [ ] **Step 13: Write `templates/House.md`**

```markdown
---
type: house
status: draft
tags: []
realm: ""
era-founded: ""
era-extinct: ""
founder: ""
seat: ""
current-head: ""
members: []
sigil: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Lineage

## Significant events

## Current status
```

- [ ] **Step 14: Write `templates/Organisation.md`**

```markdown
---
type: organisation
status: draft
tags: []
parent-faction: ""
realm: ""
era-founded: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Purpose

## Structure

## Membership

## History
```

- [ ] **Step 15: Write `templates/Era.md`**

```markdown
---
type: era
status: draft
tags: []
code: ""      # e.g. AF for Age of Forging
aliases: []
preceded-by: ""
followed-by: ""
defining-events: []
defining-chronicles: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Overview

## Themes

## Key events

## Key chronicles
```

- [ ] **Step 16: Write `templates/Event.md`**

```markdown
---
type: event
status: draft
tags: []
era: ""
year: 0
year-display: ""
account-type: canonical   # canonical | mythic | contested
location: ""
participants: []
caused-by: []
caused: []
chronicled-in: []
aliases: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## What happened

## Causes

## Consequences

## Sources
```

- [ ] **Step 17: Write `templates/Myth.md`**

```markdown
---
type: myth
status: draft
tags: []
era: ""
cultures-of-origin: []
related-events: []
chronicled-in: []
aliases: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## The myth

## Cultural meaning

## Sources
```

- [ ] **Step 18: Write `templates/Chronicle.md`**

```markdown
---
type: chronicle
status: draft
tags: []
attributed-to: ""
era-of-composition: ""
housed-in: ""
records: []
language: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Provenance

## Contents

## Excerpts
```

- [ ] **Step 19: Write `templates/Prophecy.md`**

```markdown
---
type: prophecy
status: draft
tags: []
kind: prophecy   # prophecy | omen | dream | portent
attributed-to: ""
era: ""
foretold-in: ""
fulfilled-by: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## The text / vision

## Interpretation

## Status
```

- [ ] **Step 20: Write `templates/Artifact.md`**

```markdown
---
type: artifact
status: draft
tags: []
era-of-creation: ""
created-by: ""
created-in: ""
material: []
current-location: ""
historical-bearers: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## History

## Powers / properties
```

- [ ] **Step 21: Write `templates/Item.md`**

```markdown
---
type: item
status: draft
tags: []
rarity: common
origin: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## Use
```

- [ ] **Step 22: Write `templates/Resource.md`**

```markdown
---
type: resource
status: draft
tags: []
category: ""     # metal | gem | wood | reagent | textile | …
realm: ""
sources: []
uses: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## Sources

## Uses
```

- [ ] **Step 23: Write `templates/Technology.md`**

```markdown
---
type: technology
status: draft
tags: []
era-of-invention: ""
invented-by: ""
discipline: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Principle

## History

## Applications
```

- [ ] **Step 24: Write `templates/Deity.md`**

```markdown
---
type: deity
status: draft
tags: []
pantheon: ""
domain: []
era-of-emergence: ""
aliases: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## Domain

## Worship

## History
```

- [ ] **Step 25: Write `templates/CosmicForce.md`**

```markdown
---
type: cosmic-force
status: draft
tags: []
opposed-by: ""
related-forces: []
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Nature

## Manifestations

## Mortal contact
```

- [ ] **Step 26: Write `templates/Tradition.md`**

```markdown
---
type: tradition
status: draft
tags: []
culture: ""
realm: ""
era: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Description

## Significance
```

- [ ] **Step 27: Write `templates/Language.md`**

```markdown
---
type: language
status: draft
tags: []
era-bloom: ""
era-decline: ""
still-spoken: false
spoken-by: []
script: ""
parent-language: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}

## Phonology

## Grammar (sketch)

## Sample text

## History
```

- [ ] **Step 28: Write `templates/Essay.md`**

```markdown
---
type: essay
status: draft
tags: []
topic: ""
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
---

# {{title}}
```

- [ ] **Step 29: Delete obsolete templates**

```powershell
git rm templates/City.md templates/NPC.md templates/Item.md templates/Faction.md templates/Organisation.md templates/PointOfInterest.md 2>$null
```

Note: `Item.md` and `Faction.md` and `Organisation.md` are recreated above with the new schema. `git rm` followed by `git add` for the same filename is fine — git treats it as a content change.

- [ ] **Step 30: Stage and commit**

```powershell
git add docs/_meta/Conventions.md templates/
git status
```

Expected: 1 file added under `docs/_meta/`, ~23 files added/modified under `templates/`, 3 deletions (City.md, NPC.md, PointOfInterest.md).

```powershell
git commit -m @'
refactor: add Conventions doc and 23 typed-vault templates

Replaces the 6 legacy templates with 23 covering the full typed-note
taxonomy from notes/refactor-design.md §A.1. Each template carries
universal frontmatter (type/status/tags/created/updated) plus
type-specific fields. Frontmatter wikilinks are quoted strings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2: Write `rules.py` (type-inference rule sheet)

**Files:**
- Create: `tools/refactor/rules.py`

This is the only file Aaron is asked to *read* (not write). It encodes the folder→type mapping. Aaron reviews it before the dry-run runs.

- [ ] **Step 1: Write `tools/refactor/rules.py`**

File: `tools/refactor/rules.py`
```python
"""Type-inference rules for the typed-vault initial-pass migration.

ORDER MATTERS: rules are tried in order; first match wins. Patterns are
Python regexes matched against the path relative to docs/, using forward
slashes (e.g. "Realms/Renascita/Geography/Arcturia/Cities/Runehart.md").

Each rule yields:
- `type`: the inferred `type:` value
- `extras`: callable taking the relpath and returning a dict of extra
  frontmatter to merge (e.g. `era:` derived from a parent folder).
  Use `lambda _: {}` for no extras.

The script `00_infer_types.py` walks docs/, applies these rules, and emits
inference_preview.csv for Aaron's review before any file is mutated.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

Extras = Callable[[str], Dict[str, str]]

# Map from old Age folder name to canonical Age wikilink.
AGE_WIKILINK = {
    "First Age":  "[[Age of the Endless Sun]]",
    "Second Age": "[[Age of Forging]]",
    "Third Age":  "[[Age of Stagnation]]",
    "Fourth Age": "[[Age of Night]]",
    # Already-renamed forms (idempotency)
    "Age of the Endless Sun": "[[Age of the Endless Sun]]",
    "Age of Forging":         "[[Age of Forging]]",
    "Age of Stagnation":      "[[Age of Stagnation]]",
    "Age of Night":           "[[Age of Night]]",
}


def era_from_history_path(relpath: str) -> Dict[str, str]:
    """Infer `era:` from a History/<age>/... path."""
    parts = relpath.split("/")
    if len(parts) >= 2 and parts[0] == "History":
        age = parts[1]
        link = AGE_WIKILINK.get(age)
        if link:
            return {"era": link}
    return {}


def realm_from_renascita_path(relpath: str) -> Dict[str, str]:
    """For files under Realms/Renascita/Geography/<Continent>/..., add continent."""
    parts = relpath.split("/")
    # Realms / Renascita / Geography / <Continent> / ...
    if len(parts) >= 5 and parts[0] == "Realms" and parts[1] == "Renascita" and parts[2] == "Geography":
        return {"continent": f"[[{parts[3]}]]"}
    return {}


# Each tuple: (compiled regex, type, extras callable).
RULES: List[Tuple[re.Pattern, str, Extras]] = [
    # ---------- Geography (most specific first) ----------
    # Continent self-named file: Geography/Arcturia/Arcturia.md
    (re.compile(r"^Realms/Renascita/Geography/([^/]+)/\1\.md$"), "continent", lambda _: {}),

    # Locations inside a city: Geography/.../Cities/<City>/Locations/<X>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/[^/]+/Locations/[^/]+\.md$"),
     "landmark", realm_from_renascita_path),

    # City self-named file: Geography/.../Cities/<City>/<City>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/([^/]+)/\1\.md$"),
     "settlement", realm_from_renascita_path),

    # Cities (flat): Geography/.../Cities/<X>.md
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Cities/[^/]+\.md$"),
     "settlement", realm_from_renascita_path),

    # Provinces (subfolder or flat)
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Provinces/.*\.md$"),
     "region", realm_from_renascita_path),

    # Mountains
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Mountains/.*\.md$"),
     "range", realm_from_renascita_path),

    # Rivers
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Rivers/.*\.md$"),
     "waterway", realm_from_renascita_path),

    # Generic locations under a continent
    (re.compile(r"^Realms/Renascita/Geography/[^/]+/Locations/.*\.md$"),
     "landmark", realm_from_renascita_path),

    # World Beneath: same shape as a continent but separate
    (re.compile(r"^Realms/Renascita/Geography/The World Beneath/Locations/.*\.md$"),
     "landmark", lambda _: {"continent": "[[The World Beneath]]"}),

    # ---------- Societies ----------
    # Society self-named: Societies/<Society>/<Society>.md  → faction (Aaron may relabel to culture)
    (re.compile(r"^Realms/Renascita/Societies/([^/]+)/\1\.md$"), "faction", lambda _: {"realm": "[[Renascita]]"}),

    (re.compile(r"^Realms/Renascita/Societies/.*/Characters/.*\.md$"), "character", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Clans/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Orders/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Traditions/.*\.md$"), "tradition", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Societies/.*/Locations/.*\.md$"), "landmark", lambda _: {}),

    # ---------- Legendarium ----------
    (re.compile(r"^Realms/Renascita/Legendarium/Artifacts/.*\.md$"), "artifact", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Characters/.*\.md$"), "character", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Technology/.*\.md$"), "technology", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Legendarium/Natural Resources/.*\.md$"), "resource", lambda _: {}),

    # ---------- Factions ----------
    (re.compile(r"^Realms/Renascita/Factions/Organisations/.*\.md$"), "organisation", lambda _: {}),
    (re.compile(r"^Realms/Renascita/Factions/Cults/.*\.md$"), "faction", lambda _: {}),

    # ---------- Other realms / planes (single-file stubs being promoted) ----------
    # Each plane gets its own folder in Task 7; for now we just classify them.
    (re.compile(r"^Realms/(Solirion|Nihilum|Thargrun|Veltharyn|Woudum|Sigmora|Infernum|Imperium)\.md$"),
     "landmark", lambda _: {}),
    (re.compile(r"^Realms/(Solirion|Nihilum|Thargrun|Veltharyn|Woudum|Sigmora|Infernum|Imperium)/.*\.md$"),
     "landmark", lambda _: {}),

    # Elementis
    (re.compile(r"^Realms/Elementis/.*\.md$"), "landmark", lambda _: {}),

    # Planes summary file
    (re.compile(r"^Realms/Planes\.md$"), "essay", lambda _: {}),

    # ---------- History ----------
    # Era summary files (self-named in age folder): handled by skeleton script
    (re.compile(r"^History/[^/]+/[^/]+\.md$"), "event", era_from_history_path),
    (re.compile(r"^History/Timeline\.md$"), "index", lambda _: {}),

    # ---------- Cosmology ----------
    (re.compile(r"^Cosmology/Gods/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Elementals/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/The God Hand/.*\.md$"), "deity", lambda _: {}),
    (re.compile(r"^Cosmology/Cosmic Functions/.*\.md$"), "cosmic-force", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/Corruption/.*\.md$"), "cosmic-force", lambda _: {}),
    (re.compile(r"^Cosmology/Creation/.*\.md$"), "essay", lambda _: {}),

    # ---------- Races ----------
    (re.compile(r"^Races/.+/.+/Variants/[^/]+\.md$"), "race", lambda _: {}),
    (re.compile(r"^Races/.+/.+\.md$"), "race", lambda _: {}),
    (re.compile(r"^Races/.+/[^/]+\.md$"), "race", lambda _: {}),

    # ---------- Languages ----------
    (re.compile(r"^Languages/.*\.md$"), "language", lambda _: {}),

    # ---------- Story ----------
    (re.compile(r"^Story/.*\.md$"), "essay", lambda _: {}),

    # ---------- Meta ----------
    (re.compile(r"^_meta/.*\.md$"), None, lambda _: {}),  # already typed; skip
    (re.compile(r"^index\.md$"), "essay", lambda _: {}),
]


def classify(relpath: str) -> Tuple[str, Dict[str, str], str]:
    """Return (inferred_type, extras_dict, matched_rule_repr).

    Returns ("UNCLASSIFIED", {}, "") if no rule matches.
    """
    for pattern, type_, extras in RULES:
        if pattern.match(relpath):
            extra_fields = extras(relpath) if extras else {}
            return (type_ or "SKIP", extra_fields, pattern.pattern)
    return ("UNCLASSIFIED", {}, "")
```

- [ ] **Step 2: Commit rule sheet**

```powershell
git add tools/refactor/rules.py
git commit -m @'
refactor: add type-inference rule sheet

The rules.py file encodes folder->type mapping. First-match wins.
Aaron reviews this file (and the preview CSV it produces) before
any note is mutated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3: Write `00_infer_types.py` and run dry-run

**Files:**
- Create: `tools/refactor/00_infer_types.py`
- Output (gitignored later, but committed initially): `tools/refactor/inference_preview.csv`

- [ ] **Step 1: Write `tools/refactor/00_infer_types.py`**

File: `tools/refactor/00_infer_types.py`
```python
"""Walk docs/ and produce inference_preview.csv.

Output columns: relpath, size_bytes, has_frontmatter, current_type,
inferred_type, inferred_status, inferred_extras, matched_rule.

Aaron reviews the CSV before running 01_apply_frontmatter.py.
He may edit `inference_overrides.csv` (next to this script) to override
the type for specific files; the apply script reads both.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from common import DOCS_DIR, iter_md_files, read_frontmatter, rel_to_docs
from rules import classify

OUTPUT = Path(__file__).parent / "inference_preview.csv"
STUB_THRESHOLD_BYTES = 200


def main() -> None:
    rows = []
    for md_path in iter_md_files(DOCS_DIR):
        rel = rel_to_docs(md_path)
        size = md_path.stat().st_size
        meta, _body = read_frontmatter(md_path)
        current_type = meta.get("type", "")

        inferred_type, extras, rule = classify(rel)
        status = "stub" if size < STUB_THRESHOLD_BYTES else "draft"
        # If a file already has frontmatter with status, prefer that
        if "status" in meta:
            status = meta["status"]

        rows.append({
            "relpath": rel,
            "size_bytes": size,
            "has_frontmatter": "yes" if meta else "no",
            "current_type": current_type,
            "inferred_type": inferred_type,
            "inferred_status": status,
            "inferred_extras": json.dumps(extras, ensure_ascii=False),
            "matched_rule": rule,
        })

    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Quick summary to stdout
    from collections import Counter
    counts = Counter(r["inferred_type"] for r in rows)
    print(f"Wrote {OUTPUT.relative_to(DOCS_DIR.parent)}")
    print(f"Total notes: {len(rows)}")
    print("By inferred type:")
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {t:20s} {n:5d}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the dry-run**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\00_infer_types.py
```

Expected output: prints `Wrote tools/refactor/inference_preview.csv`, total ~522 notes, distribution by inferred type with `UNCLASSIFIED` count ideally < 30. If `UNCLASSIFIED` > 30, the rule sheet needs another pass before continuing.

- [ ] **Step 3: Stage the preview**

```powershell
git add tools/refactor/00_infer_types.py tools/refactor/inference_preview.csv
git commit -m @'
refactor: add type-inference dry-run + initial preview CSV

00_infer_types.py walks docs/ and produces inference_preview.csv
with columns: relpath, size, has_frontmatter, current_type,
inferred_type, inferred_status, inferred_extras, matched_rule.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

- [ ] **Step 4: Create an empty overrides file**

```powershell
"relpath,override_type,override_status" | Out-File -Encoding utf8 tools\refactor\inference_overrides.csv
git add tools/refactor/inference_overrides.csv
git commit -m @'
refactor: add empty overrides file for Aaron's manual fixes

If a file is misclassified in inference_preview.csv, Aaron adds a row
here. 01_apply_frontmatter.py reads this file and overrides the
type/status for the listed paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## ✋ CHECKPOINT 1 — Aaron reviews `inference_preview.csv`

**What Aaron does (~15–30 minutes):**

1. Open `tools/refactor/inference_preview.csv` in a spreadsheet tool.
2. Sort by `inferred_type`.
3. Scan each type group — does the inferred type make sense for those files?
4. Look at the `UNCLASSIFIED` group. For each, add a row to `inference_overrides.csv` with the right type, OR add a rule to `rules.py` and re-run Task 3 Step 2.
5. Spot-check 10–20 files at random; open them and verify the inferred type is correct.
6. For any misclassifications, add an override row to `inference_overrides.csv`:
   ```csv
   relpath,override_type,override_status
   Realms/Renascita/Societies/Rahalan Nomads/Rahalan Nomads.md,culture,draft
   ```

**Aaron's approval signal:** commits the (possibly edited) `inference_preview.csv` and `inference_overrides.csv`, then continues to Task 4.

---

## Task 4: Write & run `01_apply_frontmatter.py`

**Files:**
- Create: `tools/refactor/01_apply_frontmatter.py`

- [ ] **Step 1: Write `tools/refactor/01_apply_frontmatter.py`**

File: `tools/refactor/01_apply_frontmatter.py`
```python
"""Apply the frontmatter migration to every .md under docs/.

Reads:
- inference_preview.csv  (the agreed type-inference output)
- inference_overrides.csv (Aaron's manual overrides)

For each file:
- If inferred_type == "SKIP" or "UNCLASSIFIED", do not modify.
- Otherwise, merge the inferred type, status, and extras into the
  existing frontmatter without overwriting any field Aaron already set.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Tuple

from common import DOCS_DIR, read_frontmatter, write_frontmatter, merge_metadata

PREVIEW = Path(__file__).parent / "inference_preview.csv"
OVERRIDES = Path(__file__).parent / "inference_overrides.csv"


def load_overrides() -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not OVERRIDES.exists():
        return out
    with OVERRIDES.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rel = (row.get("relpath") or "").strip()
            if not rel:
                continue
            t = (row.get("override_type") or "").strip()
            s = (row.get("override_status") or "").strip()
            out[rel] = (t, s)
    return out


def main() -> None:
    overrides = load_overrides()
    applied = 0
    skipped = 0
    with PREVIEW.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rel = row["relpath"]
            type_ = row["inferred_type"]
            status = row["inferred_status"]
            extras = json.loads(row["inferred_extras"]) if row["inferred_extras"] else {}

            if rel in overrides:
                ovr_t, ovr_s = overrides[rel]
                if ovr_t:
                    type_ = ovr_t
                if ovr_s:
                    status = ovr_s

            if type_ in ("SKIP", "UNCLASSIFIED", ""):
                skipped += 1
                continue

            path = DOCS_DIR / rel
            if not path.exists():
                print(f"WARN: missing {rel}")
                skipped += 1
                continue

            existing, body = read_frontmatter(path)
            new_fields = {"type": type_, "status": status, **extras}
            # tags: ensure list exists
            if "tags" not in existing and "tags" not in new_fields:
                new_fields["tags"] = []
            merged = merge_metadata(existing, new_fields)
            write_frontmatter(path, merged, body)
            applied += 1

    print(f"Applied: {applied}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the migration**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\01_apply_frontmatter.py
```

Expected: prints `Applied: <N>` and `Skipped: <M>` where N+M ≈ 522.

- [ ] **Step 3: Spot-check three files**

```powershell
Get-Content -TotalCount 15 "docs/Realms/Renascita/Geography/Arcturia/Cities/Runehart.md"
Get-Content -TotalCount 15 "docs/Realms/Renascita/Societies/Dwarven Holds/The Tidebound of Draumhavn/Characters/Dagrin Thorne.md"
Get-Content -TotalCount 15 "docs/Cosmology/Gods/Third Age/Noxar Gods/Morbus.md"
```

Expected: each file has a `---` frontmatter block at the top containing at minimum `type:` and `status:`.

- [ ] **Step 4: Commit**

```powershell
git add tools/refactor/01_apply_frontmatter.py docs/
git status
```

Expected: 01_apply_frontmatter.py added; many files under docs/ modified (additions of frontmatter only).

```powershell
git commit -m @'
refactor: bulk-apply typed frontmatter to all docs/ notes

Every .md file gains `type:` and `status:` plus rule-inferred extras
(continent, era, realm where applicable). Existing frontmatter is
preserved; new fields are merged, not overwritten.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## ✋ CHECKPOINT 2 — Aaron reviews the frontmatter diff

**What Aaron does (~10–15 minutes):**

1. `git log -1 --stat` — see what changed.
2. `git diff HEAD~1 -- docs/Realms/Renascita/Geography/Arcturia/` — spot-check a continent's tree.
3. Open Obsidian, click into a freshly-typed note, confirm frontmatter renders properly and existing prose is intact.
4. Run a Dataview test: in any note, paste:
   ```dataview
   TABLE type, status FROM "Realms/Renascita/Societies" LIMIT 10
   ```
   Confirms types are queryable.

**Approval signal:** continues to Task 5. **Rollback option:** `git reset --hard HEAD~1` and re-run with fixed rules.

---

## Task 5: Rename the four Age folders

**Files:**
- Create: `tools/refactor/02_rename_age_folders.py`
- Modify: 42 files (entire `History/<old age>/` trees)

- [ ] **Step 1: Write `tools/refactor/02_rename_age_folders.py`**

File: `tools/refactor/02_rename_age_folders.py`
```python
"""Rename History/<numeric age>/ → History/<canonical name>/ via git mv.

Idempotent: skips already-renamed folders. Also writes era summary
skeleton files if missing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from common import DOCS_DIR, REPO_ROOT, write_frontmatter

RENAMES = {
    "First Age":  ("Age of the Endless Sun", "ES"),
    "Second Age": ("Age of Forging",         "AF"),
    "Third Age":  ("Age of Stagnation",      "AS"),
    "Fourth Age": ("Age of Night",           "AN"),
}


def ensure_era_summary(new_folder: Path, canonical_name: str, code: str, old_name: str) -> None:
    """Create or update the era summary file at new_folder/<canonical_name>.md."""
    summary = new_folder / f"{canonical_name}.md"
    metadata = {
        "type": "era",
        "status": "stub",
        "tags": [],
        "code": code,
        "aliases": [old_name],
    }
    if not summary.exists():
        write_frontmatter(summary, metadata, f"\n# {canonical_name}\n")
        print(f"Created era summary: {summary.relative_to(REPO_ROOT)}")
    else:
        from common import read_frontmatter, merge_metadata
        existing, body = read_frontmatter(summary)
        merged = merge_metadata(existing, metadata)
        write_frontmatter(summary, merged, body)
        print(f"Updated era summary: {summary.relative_to(REPO_ROOT)}")


def main() -> None:
    history = DOCS_DIR / "History"
    for old, (new, code) in RENAMES.items():
        old_path = history / old
        new_path = history / new
        if new_path.exists() and not old_path.exists():
            print(f"Skip (already renamed): {old} -> {new}")
            ensure_era_summary(new_path, new, code, old)
            continue
        if not old_path.exists():
            print(f"WARN: source missing: {old_path}")
            continue
        subprocess.run(
            ["git", "mv", str(old_path.relative_to(REPO_ROOT)), str(new_path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            check=True,
        )
        print(f"Renamed: {old} -> {new}")
        ensure_era_summary(new_path, new, code, old)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\02_rename_age_folders.py
```

Expected: four "Renamed: …" lines and four "Created/Updated era summary: …" lines.

- [ ] **Step 3: Commit**

```powershell
git add tools/refactor/02_rename_age_folders.py docs/History/
git commit -m @'
refactor: rename Age folders to canonical names + add era summaries

  First Age  -> Age of the Endless Sun  (ES)
  Second Age -> Age of Forging          (AF)
  Third Age  -> Age of Stagnation       (AS)
  Fourth Age -> Age of Night            (AN)

Each renamed folder gets an era summary file with type: era,
the 2-letter code, and the old name as an alias so existing
[[Second Age]]-style wikilinks still resolve.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 6: Rename history event files with code-year prefix

**Files:**
- Create: `tools/refactor/03_rename_history_events.py`
- Renames: ~41 history files

- [ ] **Step 1: Write `tools/refactor/03_rename_history_events.py`**

File: `tools/refactor/03_rename_history_events.py`
```python
"""Rename History/<age>/<title>.md to <CODE><YYYY> <title>.md.

Year is extracted from frontmatter `year:` if present and integer,
otherwise defaults to 0000 (undated within era). Skips the era
summary file itself (matches "<age folder>/<canonical name>.md").

Adds the old title as an alias in frontmatter so existing
[[Hexweave Binding]] wikilinks still resolve to the renamed file.
"""

from __future__ import annotations

import re
from pathlib import Path

from common import (
    DOCS_DIR, REPO_ROOT, read_frontmatter, write_frontmatter, git_mv, merge_metadata
)

AGE_CODE = {
    "Age of the Endless Sun": "ES",
    "Age of Forging":         "AF",
    "Age of Stagnation":      "AS",
    "Age of Night":           "AN",
}

PREFIX_RE = re.compile(r"^(ES|AF|AS|AN)\d{4} ")


def main() -> None:
    history = DOCS_DIR / "History"
    for age_folder, code in AGE_CODE.items():
        folder = history / age_folder
        if not folder.exists():
            print(f"WARN: missing {folder}")
            continue
        era_summary = folder / f"{age_folder}.md"
        for md in sorted(folder.glob("*.md")):
            if md == era_summary:
                continue
            name = md.name
            if PREFIX_RE.match(name):
                print(f"Skip (already prefixed): {name}")
                continue
            meta, body = read_frontmatter(md)
            year = meta.get("year", 0)
            if not isinstance(year, int) or year < 0:
                year = 0
            year_str = f"{year:04d}"
            stem = md.stem  # filename without .md
            new_name = f"{code}{year_str} {stem}.md"
            new_path = md.with_name(new_name)
            if new_path.exists():
                print(f"WARN: target exists, skipping: {new_name}")
                continue

            # Add old title as alias before rename
            existing_aliases = meta.get("aliases", [])
            if not isinstance(existing_aliases, list):
                existing_aliases = [existing_aliases]
            if stem not in existing_aliases:
                existing_aliases.append(stem)
            updated_meta = merge_metadata(meta, {
                "aliases": existing_aliases,
                "year-display": f"{code} {year}" if year else f"{code} (undated)",
            })
            write_frontmatter(md, updated_meta, body)

            git_mv(md, new_path)
            print(f"Renamed: {age_folder}/{name} -> {new_name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\03_rename_history_events.py
```

Expected: ~41 "Renamed: …" lines. No errors.

- [ ] **Step 3: Commit**

```powershell
git add tools/refactor/03_rename_history_events.py docs/History/
git commit -m @'
refactor: prefix History event filenames with CODE+year

All event files under each Age folder now sort chronologically
in the sidebar. Each file's old name is preserved as an alias
in frontmatter so existing wikilinks survive the rename.

Files with no `year:` in frontmatter default to year 0000
(undated within era) — Aaron fills these in later by editing
frontmatter, no file rename required.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## ✋ CHECKPOINT 3 — Open Obsidian, verify wikilinks resolve

**What Aaron does (~10 minutes):**

1. Open the Renascitur vault in Obsidian.
2. Wait for the index to rebuild (status bar bottom-right shows progress).
3. Click any note that previously referenced `[[Hexweave Binding]]` — the link should still resolve and open `AF0000 Hexweave Binding.md`.
4. Try `[[Second Age]]` from a fresh note — should resolve to `Age of Forging.md` via alias.
5. Sidebar: confirm `Age of the Endless Sun/`, `Age of Forging/`, `Age of Stagnation/`, `Age of Night/` exist under `History/`.
6. Run a Dataview query in a scratch note:
   ```dataview
   TABLE year, era FROM "History/Age of Forging" SORT file.name ASC
   ```
   Should list every Second-Age event sorted by the filename prefix.

**Approval signal:** continues to Task 7. **Rollback:** `git reset --hard HEAD~2` reverts both folder and file renames.

---

## Task 7: Create skeleton files (race summaries, promoted realms, heavy events)

**Files:**
- Create: `tools/refactor/04_create_skeletons.py`

- [ ] **Step 1: Write `tools/refactor/04_create_skeletons.py`**

File: `tools/refactor/04_create_skeletons.py`
```python
"""Create skeleton files for missing race summaries, promoted realms,
and heavy-impact event stubs.

All skeletons are pure structure — frontmatter only, body empty
except for the title H1. Aaron writes content later at his own pace.
Idempotent: skips files that already exist.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from common import DOCS_DIR, REPO_ROOT, write_frontmatter, read_frontmatter, merge_metadata

# (relpath, type, extras dict)
RACE_SKELETONS = [
    ("Races/Humans/Elasi/Elasi.md",                "race",  {"lineage": "Human"}),
    ("Races/Humans/Terran/Terran.md",              "race",  {"lineage": "Human"}),
    ("Races/Kyojin/Leonin/Leonin.md",              "race",  {"lineage": "Kyojin"}),
    ("Races/Kyojin/Orcs/Orcs.md",                  "race",  {"lineage": "Kyojin"}),
    ("Races/Grundthains/Dwarves/Dwarves.md",       "race",  {"lineage": "Grundthain"}),
]

PROMOTED_PLANES = [
    "Solirion", "Nihilum", "Thargrun", "Veltharyn",
    "Woudum", "Sigmora", "Infernum", "Imperium",
]

# Heavy-impact event stubs that other notes reference; create as type: event,
# status: stub. Existing files (if any) get only their frontmatter updated.
HEAVY_EVENTS = [
    # (relpath_under_docs, year, era_link)
    ("History/Age of Forging/AF0000 Hexweave Binding.md",          0, "[[Age of Forging]]"),
    ("History/Age of Forging/AF0000 The Forge Wars.md",            0, "[[Age of Forging]]"),
    ("History/Age of Stagnation/AS0000 Breaking of the Hexweave Seal.md", 0, "[[Age of Stagnation]]"),
]

MACHINERY_OF_DEATH = "Cosmology/Creation/Machinery of Death.md"


def create_skeleton(relpath: str, type_: str, extras: dict, title_override: str = None) -> None:
    path = DOCS_DIR / relpath
    title = title_override or path.stem
    metadata = {"type": type_, "status": "stub", "tags": [], **extras}
    if path.exists():
        existing, body = read_frontmatter(path)
        merged = merge_metadata(existing, metadata)
        write_frontmatter(path, merged, body)
        print(f"Updated: {relpath}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_frontmatter(path, metadata, f"\n# {title}\n")
        print(f"Created: {relpath}")


def main() -> None:
    # Race summaries
    for rel, type_, extras in RACE_SKELETONS:
        create_skeleton(rel, type_, extras)

    # Promote single-file plane stubs into their own folders
    for plane in PROMOTED_PLANES:
        old_file = DOCS_DIR / "Realms" / f"{plane}.md"
        new_folder = DOCS_DIR / "Realms" / plane
        new_file = new_folder / f"{plane}.md"
        if old_file.exists() and not new_file.exists():
            new_folder.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "mv",
                 str(old_file.relative_to(REPO_ROOT)),
                 str(new_file.relative_to(REPO_ROOT))],
                cwd=REPO_ROOT, check=True,
            )
            print(f"Promoted: Realms/{plane}.md -> Realms/{plane}/{plane}.md")
        elif not new_file.exists():
            create_skeleton(f"Realms/{plane}/{plane}.md", "landmark", {})
        # Ensure typed frontmatter exists either way
        if new_file.exists():
            existing, body = read_frontmatter(new_file)
            updated = merge_metadata(existing, {"type": "landmark", "status": "stub", "tags": []})
            write_frontmatter(new_file, updated, body)

    # Heavy-impact event stubs
    for rel, year, era_link in HEAVY_EVENTS:
        create_skeleton(rel, "event", {"era": era_link, "year": year, "year-display": ""})

    # Machinery of Death — referenced widely, no page exists
    create_skeleton(MACHINERY_OF_DEATH, "cosmic-force", {})


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\04_create_skeletons.py
```

Expected: ~17 lines of "Created/Promoted/Updated: …".

- [ ] **Step 3: Commit**

```powershell
git add tools/refactor/04_create_skeletons.py docs/
git commit -m @'
refactor: create skeleton files for race summaries, promoted realms,
heavy-impact event stubs

- 5 race summary files (Elasi, Terran, Leonin, Orcs, Dwarves).
- 8 single-file plane stubs promoted into per-plane folders.
- 4 heavy-impact event stubs (Hexweave Binding, Forge Wars,
  Breaking of the Hexweave Seal, Machinery of Death) that other
  notes already reference. All are status: stub; bodies are empty.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 8: Create `_meta/` Dataview index pages

**Files:**
- Create: `tools/refactor/05_create_meta.py`
- Create: 6 files under `docs/_meta/`

- [ ] **Step 1: Write `tools/refactor/05_create_meta.py`**

File: `tools/refactor/05_create_meta.py`
```python
"""Create the Dataview-driven index pages under docs/_meta/."""

from __future__ import annotations

from pathlib import Path

from common import DOCS_DIR, write_frontmatter

META = DOCS_DIR / "_meta"


PAGES = {
    "Stub Backlog.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Stub Backlog

All notes with `status: stub`. Pick one when inspiration strikes.

```dataview
TABLE WITHOUT ID
  file.link AS "Note",
  type AS "Type",
  file.folder AS "Folder"
FROM ""
WHERE status = "stub"
SORT type ASC, file.name ASC
```
''',
    },
    "NPCs by Faction.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# NPCs by Faction

```dataview
TABLE WITHOUT ID
  file.link AS "Character",
  race AS "Race",
  location AS "Location"
FROM ""
WHERE type = "character"
GROUP BY affiliation
SORT affiliation ASC, file.name ASC
```
''',
    },
    "Locations by Realm.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Locations by Realm

```dataview
TABLE WITHOUT ID
  file.link AS "Place",
  type AS "Kind"
FROM ""
WHERE contains(list("settlement","landmark","region","range","waterway","continent"), type)
GROUP BY continent
SORT continent ASC, type ASC, file.name ASC
```
''',
    },
    "Factions of Renascita.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Factions of Renascita

```dataview
TABLE WITHOUT ID
  file.link AS "Faction",
  alignment AS "Alignment",
  status AS "Status"
FROM ""
WHERE type = "faction"
SORT file.name ASC
```
''',
    },
    "Campaign Reference.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Campaign Reference

Quick-lookup dashboard for live sessions.

## Recently edited

```dataview
LIST FROM "" WHERE file.mtime SORT file.mtime DESC LIMIT 15
```

## Major factions

```dataview
LIST FROM "" WHERE type = "faction" SORT file.name ASC
```

## All canonical characters

```dataview
TABLE WITHOUT ID
  file.link AS "Name",
  race AS "Race",
  affiliation AS "Faction"
FROM ""
WHERE type = "character" AND status = "canon"
SORT affiliation ASC, file.name ASC
```
''',
    },
    "Timeline.md": {
        "metadata": {"type": "index", "status": "canon", "tags": ["meta"]},
        "body": '''
# Timeline

All events sorted chronologically.

```dataview
TABLE WITHOUT ID
  file.link AS "Event",
  era AS "Era",
  year AS "Year"
FROM ""
WHERE type = "event"
SORT era ASC, year ASC, file.name ASC
```
''',
    },
}


def main() -> None:
    META.mkdir(parents=True, exist_ok=True)
    for filename, content in PAGES.items():
        path = META / filename
        if path.exists():
            print(f"Skip (exists): {filename}")
            continue
        write_frontmatter(path, content["metadata"], content["body"])
        print(f"Created: _meta/{filename}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\05_create_meta.py
```

Expected: 6 "Created: _meta/…" lines.

- [ ] **Step 3: Commit**

```powershell
git add tools/refactor/05_create_meta.py docs/_meta/
git commit -m @'
refactor: add _meta/ Dataview indices

Six index pages: Stub Backlog, NPCs by Faction, Locations by Realm,
Factions of Renascita, Campaign Reference, Timeline. All populate
from the typed frontmatter applied in Task 4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 9: Configure Templater + obsidian-linter

**Files:**
- Modify: `.obsidian/community-plugins.json` (add `templater-obsidian`)
- Modify: `.obsidian/plugins/templater-obsidian/data.json` (configure folder, defaults)
- Modify: `.obsidian/plugins/obsidian-linter/data.json` (require type+status keys)

Templater itself must be installed via the Obsidian UI by Aaron — this step only configures it once installed.

- [ ] **Step 1: Aaron installs Templater via Obsidian UI**

In Obsidian: Settings → Community plugins → Browse → search "Templater" → Install → Enable. Then close Obsidian (so settings flush to disk).

- [ ] **Step 2: Verify Templater config exists**

```powershell
Test-Path ".obsidian/plugins/templater-obsidian/data.json"
```

Expected: `True`. If `False`, repeat Step 1.

- [ ] **Step 3: Patch Templater config to point at our templates folder**

```powershell
$config = Get-Content -Raw ".obsidian/plugins/templater-obsidian/data.json" | ConvertFrom-Json
$config.templates_folder = "templates"
$config.trigger_on_file_creation = $true
$config | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 ".obsidian/plugins/templater-obsidian/data.json"
```

- [ ] **Step 4: Patch obsidian-linter to require `type:` and `status:` on non-essay notes**

```powershell
Test-Path ".obsidian/plugins/obsidian-linter/data.json"
```

If True, open the file and locate the `yaml-key-sort` and/or `force-yaml-escape` rules. Add this rule block under `ruleConfigs` (using a text editor to merge into existing JSON):

```json
"yaml-frontmatter-required-keys": {
  "enabled": true,
  "required-keys": ["type", "status", "tags"]
}
```

(If the linter version on this vault doesn't ship this rule, skip — it's a quality-of-life-nice-to-have, not blocking.)

- [ ] **Step 5: Commit**

```powershell
git add .obsidian/community-plugins.json .obsidian/plugins/templater-obsidian/data.json .obsidian/plugins/obsidian-linter/data.json
git commit -m @'
refactor: configure Templater + linter for typed vault

Templater points at templates/ and auto-triggers on file creation,
so new notes are pre-populated with frontmatter. Linter rule (if
supported by current version) enforces type/status/tags on save.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 10: Patch `mkdocs.yml`

**Files:**
- Modify: `mkdocs.yml`

The current config has no `nav:` section. Add an explicit top-level nav so the published site reflects the new typed structure.

- [ ] **Step 1: Edit `mkdocs.yml`**

Replace the existing file content with:

File: `mkdocs.yml`
```yaml
site_name: Renascitur

theme:
  name: material
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: pink
      accent: indigo
      toggle:
        icon: material/toggle-switch-off-outline
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: pink
      accent: blue
      toggle:
        icon: material/toggle-switch
        name: Switch to light mode

markdown_extensions:
  - tables
  - nl2br
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - toc:
      permalink: true

plugins:
  - search
  - roamlinks
  - callouts

extra_javascript:
  - https://polyfill.io/v3/polyfill.min.js?features=es6
  - https://unpkg.com/mermaid/dist/mermaid.min.js

# Explicit top-level nav so the site doesn't depend on filesystem order.
# Sub-pages are auto-included by mkdocs from each folder.
nav:
  - Welcome: index.md
  - Cosmology: Cosmology/
  - History: History/
  - Realms: Realms/
  - Races: Races/
  - Languages: Languages/
  - Story: Story/
  - Reference (_meta): _meta/
```

- [ ] **Step 2: Also patch CI to stop installing the unused ezlinks plugin**

```powershell
Get-Content .github/workflows/ci.yml
```

Find the `pip install` line and remove `mkdocs-ezlinks-plugin` from it (the plugin is commented out in mkdocs.yml).

- [ ] **Step 3: Commit**

```powershell
git add mkdocs.yml .github/workflows/ci.yml
git commit -m @'
refactor: explicit top-level mkdocs nav; drop unused ezlinks install

mkdocs.yml gains a nav: section so site structure is predictable
instead of filesystem-dependent. Sub-pages remain auto-included.
CI no longer installs mkdocs-ezlinks-plugin which is commented out
in the config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 11: Final verification

- [ ] **Step 1: Run all dry-runs again — should report nothing to change**

```powershell
& "D:\Anaconda\python.exe" tools\refactor\00_infer_types.py
& "D:\Anaconda\python.exe" tools\refactor\04_create_skeletons.py
& "D:\Anaconda\python.exe" tools\refactor\05_create_meta.py
```

Expected: the inference CSV regenerates with no `UNCLASSIFIED` rows (after Aaron's overrides). The other scripts print only "Skip (exists)" lines.

- [ ] **Step 2: Verify count of typed notes**

```powershell
& "D:\Anaconda\python.exe" -c @"
from tools.refactor.common import iter_md_files, read_frontmatter
total = typed = stub = 0
for p in iter_md_files():
    total += 1
    meta, _ = read_frontmatter(p)
    if meta.get('type'):
        typed += 1
    if meta.get('status') == 'stub':
        stub += 1
print(f'Total: {total}')
print(f'Typed: {typed}')
print(f'Stub:  {stub}')
"@
```

Expected: Typed/Total ≥ 95%. Stub count roughly matches the pre-existing stub count plus the new skeletons (~190).

- [ ] **Step 3: Open Obsidian, smoke-test Dataview**

In Obsidian, open `_meta/Stub Backlog.md`. Confirm the table populates with hundreds of rows. Open `_meta/Timeline.md` — events should appear sorted by era + year.

- [ ] **Step 4: Build the mkdocs site locally**

```powershell
& "D:\Anaconda\python.exe" -m pip install mkdocs-material mkdocs-callouts mkdocs-roamlinks-plugin
& "D:\Anaconda\python.exe" -m mkdocs build --strict
```

Expected: clean build (or only warnings about missing wikilink targets, which we already know about).

---

## ✋ CHECKPOINT 4 — Aaron reviews everything and merges

**What Aaron does (~15 minutes):**

1. `git log refactor/typed-vault-initial-pass --oneline` — verify clean commit sequence.
2. `git diff master..refactor/typed-vault-initial-pass --stat` — see the file-count summary.
3. Spend 5 minutes browsing the vault in Obsidian: open a few typed notes, check Dataview pages render, click some `[[wikilinks]]` to confirm they resolve.
4. Restore stashed in-flight work:
   ```powershell
   git stash pop
   ```
   (If conflicts arise, resolve manually — these are Aaron's pre-existing WIP changes.)
5. Merge:
   ```powershell
   git checkout master
   git merge --no-ff refactor/typed-vault-initial-pass -m "Merge refactor/typed-vault-initial-pass into master"
   git push
   ```

**If anything looks wrong:** stay on the branch, fix forward with another commit, push the branch separately so it doesn't pollute master.

---

## Post-merge: kick off the long-term backlog

After the merge, the long-term backlog (see `notes/refactor-design.md §4`) becomes the standing to-do list:

- **Phase 1 (History spine):** write the era summary content, fill the heavy-event stubs, expand Third/Fourth Ages, author the first chronicles. Each is an independent backlog item; pick one when inspired.
- **Phase 2 (reference content):** organic — when you next edit a note for any reason, take 30s to fill out its frontmatter.
- **Phase 3 (tooling):** add link-validity to CI, image inventory page, etc.
- **Phase 4 (Python sim):** the DF-style annals generator. Park for now; revisit when motivation returns.

The structure is now ready for you to write into, at your pace.

---

## Self-review

Run through this myself before handing off:

**Spec coverage check** (each §5 decision from `notes/refactor-design.md` mapped to a task):

| Decision | Implemented in |
|----------|----------------|
| 1. race vs culture split | Templates Race.md + Culture.md (Task 1); inference rule + override |
| 2. chronicle separate type | Template Chronicle.md (Task 1); type in rules |
| 3. myth as type AND account-type | Template Myth.md (Task 1) + Event.md `account-type:` field |
| 4. prophecy type | Template Prophecy.md (Task 1) |
| 5. Year format (Sketch 3) | Event.md template `year` + `era` + `year-display`; History rename script |
| 6. Age names ES/AF/AS/AN | Conventions.md, folder rename script, history file rename script |
| 7. Filename prefix history-only | 03_rename_history_events.py only touches `History/` |
| 8. Folder rename + aliases | 02_rename_age_folders.py adds aliases on era summaries |
| 9. Quoted wikilinks | PyYAML round-trip preserves quoting; templates use quoted form |
| 10. created/updated tracking | Templater config (Task 9); template files use `<% tp.date.now %>` |
| 11. Realm promotion | 04_create_skeletons.py promotes each plane |
| 12. History first | (sequencing is in the backlog, not the initial pass) |
| 13. Full mechanical sweep, AI-prepared | The entire plan is this. |
| 14. No content drafting | Skeletons are frontmatter-only with empty bodies; explicitly noted in scripts |
| 15. Templater install | Task 9 |
| 16. Dataview indices | Task 8 |
| 17. Sim early POC: no | Not in plan |

**Placeholder scan:** searched for TBD/TODO/fill-in-details — none present. ✅

**Type consistency:** template field names match rules.py extras keys (continent, era, realm) and Dataview queries (`type`, `status`, `affiliation`, `continent`, `era`, `year`). ✅

**Spec gaps:** none identified. Two known soft-spots are accepted by design:
- History events with no `year:` in frontmatter all sort under `<CODE>0000` — Aaron edits frontmatter later to date them, no rename script re-run required.
- Obsidian Templater install is manual (UI click); Step 9.1 calls this out and the rest of Step 9 picks up after.

Plan ready to execute.
