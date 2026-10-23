"""Stable ids for notes (S2 spec §4): `v:<slug>`, kept in each note's frontmatter.

- **The slug** is the file stem with letters that don't decompose spelled out (`Þ` → `th`, `æ` → `ae`,
  `ß` → `ss`…), NFKD-normalised with combining marks dropped, apostrophes dropped, every other run of
  non-alphanumerics turned into `-`, trimmed and lowercased: `Lion’s Rest` → `lions-rest`,
  `Duo - Second Emperor` → `duo-second-emperor`. A name with no slug at all (only CJK, say) gets no id
  and a `no_slug` finding: give it one in `vault.toml`'s `[ids]`.
- **Who has one:** every note whose type isn't essay or index and that isn't a proposal (proposals get
  theirs when written). Drafts do: a draft is a note with an identity, just not canon yet.
- **Assignment** (`assign`) is deterministic. Every id already written in a file is reserved, good or
  bad; a note whose id is good keeps it; a note whose id is malformed or shared gets **none** (its `bad_id`
  or `duplicate_id` finding stands until it's fixed by hand). `vault.toml`'s `[ids]` can prefer an id for a
  note; the rest get `v:<slug>` in sorted key order, `-2`, `-3`… on collision. `check_ids` reports
  preferences that can't hold and names without a slug.
- **The migration** (`migrate`, `renasci vault ids`) writes the missing ones: one `id:` line after the
  opening `---` (or a new frontmatter block for a note with none), nothing else touched, the file's BOM
  and line endings kept. It never edits a note that has any `id:` field already or whose frontmatter never
  closes. A dry run (the default) only lists what it would add; run twice, it adds nothing.

Once written, an id is identity: a renamed or moved note keeps it, and everything the bridge makes names
notes by id.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from renasci.vault.config import ID
from renasci.vault.mapping import role

NEEDS_ID = ("pin_source", "place", "reference", "claim_seed", "draft")
NO_ID_TYPES = ("essay", "index")
SPELLED = {"Þ": "Th", "þ": "th", "Ð": "D", "ð": "d", "Æ": "Ae", "æ": "ae", "Ø": "O", "ø": "o", "ß": "ss",
           "Đ": "D", "đ": "d", "Ł": "L", "ł": "l", "Œ": "Oe", "œ": "oe", "ı": "i", "Ħ": "H", "ħ": "h"}
APOSTROPHES = "'’‘ʼ"


def slug(title: str) -> str:
    text = "".join(SPELLED.get(c, c) for c in title)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c) and c not in APOSTROPHES)
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()


def _wants_id(note) -> bool:
    return role(note) in NEEDS_ID and note.type not in NO_ID_TYPES


def assign(vault) -> dict[str, str]:
    """The id of every note that should have one: its own, the config's choice, or a fresh slug."""
    wanted = [k for k, n in vault.notes.items() if _wants_id(n)]
    out: dict[str, str] = {}
    taken = {n.frontmatter["id"] for n in vault.notes.values() if isinstance(n.frontmatter.get("id"), str)}
    taken |= set(getattr(vault, "proposed_ids", ()))  # (proposals hold theirs until promoted or deleted)
    for k in wanted:  # a good id already written is kept
        n = vault.notes[k]
        if n.id and k not in vault.bad_ids:
            out[k] = n.id
    for k in wanted:  # the config's preference, for notes with no id field at all
        want = vault.config.ids.get(k)
        if "id" not in vault.notes[k].frontmatter and want and want not in taken:
            out[k] = want
            taken.add(want)
    for k in wanted:  # the rest: slugs, in key order
        if k in out or "id" in vault.notes[k].frontmatter:
            continue
        s = slug(vault.notes[k].title)
        if not s:
            continue  # (a no_slug finding)
        candidate, n = f"v:{s}", 2
        while candidate in taken:
            candidate, n = f"v:{s}-{n}", n + 1
        out[k] = candidate
        taken.add(candidate)
    return dict(sorted(out.items()))


def check_ids(vault) -> list[dict]:
    """Findings about ids that the loader can't see: preferences that can't hold, names without a slug."""
    out = []
    stored = {n.frontmatter["id"]: k for k, n in vault.notes.items() if isinstance(n.frontmatter.get("id"), str)}
    seen: dict[str, str] = {}
    for key, want in sorted(vault.config.ids.items()):
        note = vault.notes.get(key)
        why = None
        if note is None:
            why = "no such note"
        elif not _wants_id(note):
            why = f"a {note.type} note doesn't get an id"
        elif "id" in note.frontmatter and note.frontmatter["id"] != want:
            why = f"the note already has id {note.frontmatter['id']!r}"
        elif want in stored and stored[want] != key:
            why = f"{want} is already {stored[want]}'s"
        elif want in seen:
            why = f"{want} is also preferred for {seen[want]}"
        seen.setdefault(want, key)
        if why:
            out.append({"kind": "id_preference", "key": key, "line": 1, "message": f"[ids] {want}: {why}"})
    for key, note in vault.notes.items():
        if _wants_id(note) and "id" not in note.frontmatter and key not in vault.config.ids and not slug(note.title):
            out.append({"kind": "no_slug", "key": key, "line": 1,
                        "message": "the name gives no slug: set its id in vault.toml's [ids]"})
    return out


def migrate(vault, write: bool = False) -> list[dict]:
    """The `id:` lines missing from notes ([{key, path, line}]); with `write`, add them."""
    plan = []
    for key, vid in assign(vault).items():
        note = vault.notes[key]
        if "id" in note.frontmatter or note.frontmatter_state == "unclosed" or not ID.fullmatch(vid):
            continue
        plan.append({"key": key, "path": note.path, "line": f"id: {vid}"})
    if write:
        for change in plan:
            note = vault.notes[change["key"]]
            _add_line(Path(note.path), change["line"], note.frontmatter_state == "present")
    return plan


def _add_line(path: Path, line: str, has_frontmatter: bool) -> None:
    add_lines(path, [line], has_frontmatter)


def add_lines(path: Path, lines: list[str], has_frontmatter: bool) -> None:
    """Add frontmatter lines after the opening `---` (or in a new block), touching nothing else: the
    file's BOM and line endings are kept. Shared by the id migration and `vault suggest`."""
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    nl = b"\r\n" if b"\r\n" in body else b"\n"
    add = b"".join(line.encode("utf-8") + nl for line in lines)
    if has_frontmatter:
        first, sep, rest = body.partition(b"\n")  # the opening --- (with its \r, if any)
        out = first + sep + add + rest
    else:
        out = b"---" + nl + add + b"---" + nl + body
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out)
