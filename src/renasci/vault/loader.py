"""The vault loader (S2 spec §2): every note as a record, its links resolved, and what's wrong as findings.

`load(root)` walks `*.md` under the vault root in sorted order (skipping dot-folders, and proposals in
`_proposed/` until they are promoted),
normalises each file (UTF-8, no BOM, `\\n` line ends), reads its frontmatter (`frontmatter.parse`),
and resolves every `[[wikilink]]` like Obsidian, in this order (§2.3):

1. a **path** (`[[docs/Races/Kyojin/Leonin/Leonin|…]]`): a leading `docs/` is dropped; a folder path means
   its folder note (`<folder>/<name>.md`);
2. a **unique file stem**, case-insensitively;
3. a **shared stem**, settled by what the frontmatter field expects (`race: [[Leonin]]` wants a race);
4. a **unique alias**, last.

What can't be settled is a finding (`unresolved_link`, `ambiguous_link`), as is frontmatter beyond the
subset (`frontmatter_subset`) or a type that isn't one of the 22 (`unknown_type`). Findings never stop
the load: the vault is a manuscript, and the loader reports on it.

Types come from `type:` (through `vault.toml`'s type aliases), then its folder rules, then `essay`
(§3.2). The digest covers the sorted `[key, hash]` pairs and `vault.toml` (ids replace keys, #60).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from renasci.vault.config import ID, Config
from renasci.vault.frontmatter import parse
from renasci.vault.loader_types import TYPES

# What a frontmatter field's links should be, to settle a shared name (§2.3 step 3).
EXPECTS = {"race": {"race"}, "house": {"house"}, "father": {"character"}, "mother": {"character"},
           "spouse": {"character"}, "head": {"character"}, "seat": {"settlement", "landmark"},
           "home": {"settlement"}, "offices": {"house", "organisation"}, "participants": {"character", "house"}}
WIKILINK = re.compile(r"!?\[\[([^\[\]]+)\]\]")
ATTACHMENT = re.compile(r"\.(png|jpe?g|gif|webp|svg|bmp|avif|pdf|mp3|mp4|webm|m4a|ogg|wav|flac|mov|mkv|canvas|base"
                        r"|excalidraw)$", re.IGNORECASE)
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")


BOM, CR, LF = chr(0xFEFF), chr(13), chr(10)
CRLF = CR + LF


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


@dataclass
class Note:
    key: str
    title: str
    id: str | None
    type: str
    type_from: str  # frontmatter | folder | default
    status: str  # canon | draft | proposed
    frontmatter: dict
    links: dict = field(default_factory=dict)  # field -> [note keys], in order, without repeats
    body_links: list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    aliases: list = field(default_factory=list)
    line_of: dict = field(default_factory=dict)
    hash: str = ""
    path: str = ""  # the file, as found (its name may not be NFC)
    frontmatter_state: str = "none"  # none | present | unclosed


@dataclass
class Vault:
    root: str
    notes: dict  # key -> Note, sorted by key
    findings: list
    digest: str
    config: Config = field(default_factory=Config)
    bad_ids: frozenset = frozenset()  # notes whose `id:` is malformed or shared (their pins are blocked)
    resolver: Resolver | None = None
    proposed_ids: frozenset = frozenset()  # ids taken by proposals not yet promoted (never reassigned)

    def resolve(self, text: str, expects: set[str] | None = None) -> str | None:
        """The note key a link text names (`[[X]]` or `X`), or None when it names none or several."""
        if self.resolver is None:
            self.resolver = Resolver(self.notes)
        m = WIKILINK.search(text)
        outcome, key = self.resolver.resolve(m.group(1) if m else text, expects)
        return key if outcome == "note" else None

    def to_json(self) -> dict:
        return {"notes": [asdict(n) for n in self.notes.values()], "findings": self.findings, "digest": self.digest}


def normalise(raw: bytes) -> tuple[str, bool]:
    """(text, was it UTF-8): no BOM, LF line ends, NFC. Undecodable bytes become U+FFFD (a finding)."""
    try:
        text, ok = raw.decode("utf-8"), True
    except UnicodeDecodeError:
        text, ok = raw.decode("utf-8", errors="replace"), False
    return nfc(text.removeprefix(BOM).replace(CRLF, LF).replace(CR, LF)), ok


def _walk(root: Path, config: Config):
    """Notes: `*.md` exactly (on every platform), outside dot-folders and the config's `ignore`, by NFC
    key (`load` then sets aside proposals not yet promoted)."""
    found = []
    for p in root.rglob("*.md"):
        rel = p.relative_to(root)
        if p.suffix != ".md" or any(part.startswith(".") for part in rel.parts):
            continue
        key = nfc(rel.with_suffix("").as_posix())
        if not config.ignored(key):
            found.append((key, p))
    return sorted(found)


def _code_free(text: str) -> str:
    """The body with fenced blocks and inline code blanked (same lines): Obsidian doesn't link inside code."""
    out, fenced = [], None
    for line in text.split(LF):
        m = FENCE.match(line)
        if fenced:
            out.append("")
            if m and m.group(1) == fenced:
                fenced = None
            continue
        if m:
            fenced = m.group(1)
            out.append("")
            continue
        out.append(INLINE_CODE.sub(lambda c: " " * len(c.group(0)), line))
    return LF.join(out)


def _aliases(value) -> list[str]:
    if value is None:
        return []
    return [str(a) for a in (value if isinstance(value, list) else [value]) if a is not None]


def _link_texts(value):
    """Every wikilink inside a frontmatter value (strings, lists, maps), in order."""
    if isinstance(value, str):
        yield from WIKILINK.findall(value)
    elif isinstance(value, list):
        for v in value:
            yield from _link_texts(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _link_texts(v)


class Resolver:
    def __init__(self, notes: dict[str, Note]):
        self.notes = notes
        self.by_key = {k.lower(): k for k in notes}
        self.by_stem: dict[str, list[str]] = {}
        self.by_alias: dict[str, list[str]] = {}
        for k, n in notes.items():
            self.by_stem.setdefault(n.title.lower(), []).append(k)
            for a in n.aliases:
                self.by_alias.setdefault(nfc(a).lower(), []).append(k)

    def resolve(self, text: str, expects: set[str] | None = None, here: str | None = None) -> tuple[str, str | None]:
        """("note", key) | ("attachment", name) | ("unresolved", None) | ("ambiguous", None). `here` is the
        linking note: `[[#Heading]]` links to it."""
        target = nfc(text.split("|", 1)[0].rstrip("\\").split("#", 1)[0].strip())  # (`\|` in tables)
        if not target:
            return ("note", here) if here and "#" in text else ("unresolved", None)
        if ATTACHMENT.search(target):
            return "attachment", target
        target = target.removesuffix(".md")
        if "/" in target:
            path = target.removeprefix("docs/").strip("/")
            key = self.by_key.get(path.lower())
            if key is None:  # a folder: its folder note
                key = self.by_key.get(f"{path}/{PurePosixPath(path).name}".lower())
            return ("note", key) if key else ("unresolved", None)
        stems = self.by_stem.get(target.lower(), [])
        if len(stems) == 1:
            return "note", stems[0]
        if len(stems) > 1:
            fitting = [k for k in stems if expects and self.notes[k].type in expects]
            return ("note", fitting[0]) if len(fitting) == 1 else ("ambiguous", None)
        aliases = sorted(set(self.by_alias.get(target.lower(), [])))
        if len(aliases) == 1:
            return "note", aliases[0]
        return ("ambiguous", None) if aliases else ("unresolved", None)


def load(root, config: Config | None = None) -> Vault:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"no vault at {root}")
    config = config if config is not None else Config.load(root)
    proposed_ids: set[str] = set()  # ids written in proposals not yet promoted: reserved
    notes: dict[str, Note] = {}
    texts: dict[str, tuple[str, int]] = {}
    findings: list[dict] = []

    def finding(kind, key, line, message):
        findings.append({"kind": kind, "key": key, "line": line, "message": message})

    for key, path in _walk(root, config):
        text, utf8 = normalise(path.read_bytes())
        if not utf8:
            finding("not_utf8", key, 1, "not UTF-8: undecodable bytes were replaced")
        fm, problems, line_of, body_start = parse(text)
        if key.startswith("_proposed/"):  # the writer's until promoted (S2 §9): canon: true, or no canon: at all
            promoted = body_start > 0 and (fm.get("canon") is True or "canon" not in fm)
            if not promoted:
                if isinstance(fm.get("id"), str):
                    proposed_ids.add(fm["id"])
                continue
            finding("promoted_in_proposed", key, 1, "promoted: move it out of _proposed/ to where it belongs")
        state = ("present" if body_start > 0 else
                 "unclosed" if any("never closes" in p["message"] for p in problems) else "none")
        for p in problems:
            finding("frontmatter_subset", key, p["line"], (f"{p['field']}: " if p["field"] else "") + p["message"])
        declared = fm.get("type")
        declared = config.type_aliases.get(declared, declared) if isinstance(declared, str) else declared
        if isinstance(declared, str) and declared in TYPES:
            kind, kind_from = declared, "frontmatter"
        else:
            if declared is not None:
                finding("unknown_type", key, line_of.get("type", 1), f"type {declared!r} is not one of the 22")
            folder = config.folder_type(key, fm)
            kind, kind_from = (folder, "folder") if folder else ("essay", "default")
        status = ("proposed" if fm.get("canon") == "proposed" else "draft" if fm.get("status") == "draft" else "canon")
        notes[key] = Note(key, PurePosixPath(key).name, fm.get("id") if isinstance(fm.get("id"), str) else None,
                          kind, kind_from, status, fm, aliases=_aliases(fm.get("aliases")), line_of=line_of,
                          hash=hashlib.sha256(text.encode("utf-8")).hexdigest(), path=str(path),
                          frontmatter_state=state)
        texts[key] = (text, body_start)

    resolver = Resolver(notes)
    for key, note in notes.items():
        def take(text, line, expects, into):
            outcome, target = resolver.resolve(text, expects, here=key)
            if outcome == "note":
                if target not in into:
                    into.append(target)
            elif outcome == "attachment":
                if target not in note.attachments:
                    note.attachments.append(target)
            else:
                finding(f"{outcome}_link", key, line, f"[[{text}]]")

        for fname, value in note.frontmatter.items():
            for text in _link_texts(value):
                take(text, note.line_of.get(fname, 1), EXPECTS.get(fname), note.links.setdefault(fname, []))
        note.links = {k: v for k, v in note.links.items() if v}
        text, body_start = texts[key]
        for n, line in enumerate(_code_free(text).split("\n")[body_start:], start=body_start + 1):
            for t in WIKILINK.findall(line):
                take(t, n, None, note.body_links)

    by_id: dict[str, list[str]] = {}
    bad = set()
    for key, note in notes.items():
        if "id" in note.frontmatter and (note.id is None or not ID.fullmatch(note.id)):
            finding("bad_id", key, note.line_of.get("id", 1), f"id {note.frontmatter['id']!r} is not like v:house-medani")
            bad.add(key)
        elif note.id:
            by_id.setdefault(note.id, []).append(key)
    for vid, keys in by_id.items():
        if len(keys) > 1:
            for key in keys:
                finding("duplicate_id", key, notes[key].line_of.get("id", 1), f"{vid} is also on {', '.join(k for k in keys if k != key)}")
                bad.add(key)
    findings.sort(key=lambda f: (f["key"], f["line"], f["kind"], f["message"]))
    config_hash = hashlib.sha256(config.digest_text.encode("utf-8")).hexdigest()
    digest = hashlib.sha256(json.dumps({"notes": sorted([k, n.hash] for k, n in notes.items()), "config": config_hash},
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    return Vault(str(root), dict(sorted(notes.items())), findings, digest, config, frozenset(bad), resolver,
                 frozenset(proposed_ids))
