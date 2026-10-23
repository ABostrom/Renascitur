"""`vault suggest` (S2 spec §5.3): frontmatter for today's notes, from their labelled body bullets.

The vault's notes keep facts in the body (`- **House**: [[House Kundarak]]`). This proposes the matching
frontmatter from a **fixed table**, by note type (a house's `**Race**:` is its head's, not a field of the
house), and nothing else:

| Note | Body | Field |
|---|---|---|
| character | `**House**: [[X]]`, or a `## House Affiliation` section's first bullet `- [[X]]` | `house` |
| character | `**Race**: [[X]]`, or a `## Race` section's first bullet `- [[X]]` | `race` |
| character | `**Spouse**: [[X]]` | `spouse` |
| house | `**Current Head**: [[X]]` | `head` |
| house | `**Primary Seat**: [[X]]` | `seat` |

Only bullets (a line starting `- `), only a wikilink straight after the label, only fields the note
doesn't already have, and never prose ("younger brother of" is left to Aaron). A label naming no link
(`**Spouse**: **Empress Valeria**`) suggests nothing; a link that names no note (or not the expected
kind) is skipped and reported, so a field never points nowhere. `apply` writes them as a diff Aaron
reviews, through the id migration's writer (lines added after the opening `---`, nothing else touched).
"""

from __future__ import annotations

import re
from pathlib import Path

from renasci.vault.ids import add_lines
from renasci.vault.loader import EXPECTS

LABELS = {  # note type -> {bullet label: field}
    "character": {"House": "house", "Race": "race", "Spouse": "spouse"},
    "house": {"Current Head": "head", "Primary Seat": "seat"},
}
SECTIONS = {"character": {"Race": "race", "House Affiliation": "house"}}  # heading -> field
LINK_BULLET = re.compile(r"^\s*-\s+(\[\[[^\[\]]+\]\])")


def _bullet(labels):
    return re.compile(r"^\s*-\s+\*\*(" + "|".join(map(re.escape, labels)) + r")\*\*:\s*(\[\[[^\[\]]+\]\])")


def suggest(vault) -> tuple[dict[str, dict[str, str]], list[dict]]:
    """({note key: {field: "[[link]]"}}, [{key, field, why}] for what was skipped)."""
    out: dict[str, dict[str, str]] = {}
    skipped: list[dict] = []
    for key, note in vault.notes.items():
        labels, sections = LABELS.get(note.type), SECTIONS.get(note.type, {})
        if not labels:
            continue
        bullet = _bullet(labels)
        heading = re.compile(r"^#{1,6}\s+(" + "|".join(map(re.escape, sections)) + r")\s*$") if sections else None
        lines = Path(note.path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n")
        found: dict[str, str] = {}
        under = None  # the field a section heading is waiting to fill
        for line in lines:
            m = bullet.match(line)
            if m:
                found.setdefault(labels[m.group(1)], m.group(2))
            h = heading.match(line) if heading else None
            if h:
                under = sections[h.group(1)]
                continue
            if under:
                lm = LINK_BULLET.match(line)
                if lm:
                    found.setdefault(under, lm.group(1))
                    under = None
                elif line.strip() and not line.lstrip().startswith("-"):
                    under = None
        good = {}
        for field, link in found.items():
            if field in note.frontmatter:
                continue
            if vault.resolve(link, EXPECTS.get(field)) is None:
                skipped.append({"key": key, "field": field, "why": f"{link} names no note (or several)"})
                continue
            good[field] = link
        if good:
            out[key] = dict(sorted(good.items()))
    return out, skipped


def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def apply(vault, suggestions: dict) -> int:
    """Add the suggested fields; returns how many notes were written (unclosed frontmatter is left alone)."""
    written = 0
    for key, fields in sorted(suggestions.items()):
        note = vault.notes[key]
        if note.frontmatter_state == "unclosed":
            continue
        add_lines(Path(note.path), [f"{k}: {_q(v)}" for k, v in fields.items()], note.frontmatter_state == "present")
        written += 1
    return written
