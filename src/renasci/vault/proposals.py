"""Proposals (S2 spec §9): what a run made, offered back to the vault as `canon: proposed` notes.

- `propose(state, events, entity, vault, calendar, source, bindings)`: a **character** note for a run's
  person (name, born, died, sex, house, father, mother: canon ones as links, whether cast with a canon id
  or born through a birth pin (`bindings`); others are named in the report so they can be proposed first),
  or an **event** note for a run's world event whose participants are all canon (`engine:` its type).
  Frontmatter in the §5.3 schema, a fresh `id` (unique among notes *and* other proposals), `canon:
  proposed`, a `source` (run, its path, entity or event, the run's state hash, the vault digest) and a
  `generated_hash`; a short generated body. Someone already canon is refused.
- `write_proposal(root, rel, text)`: into `_proposed/<type>/`. An existing file **for the same entity**
  that still matches its own `generated_hash` (untouched) is regenerated in place; an edited one, or one
  for someone else of the same name, is never overwritten: the proposal goes to `<name>-2.md`, `-3`…
- **Promotion** is Aaron's: set `canon: true` (or drop `canon:`), and move the note where it belongs. The
  loader reads a promoted note even while it's still in `_proposed/` (with a finding suggesting the move),
  and nothing else from there. The bridge never writes `canon: true`.
- `stale(root, runs)`: untouched proposals whose source run is gone, or has been run again since (its
  state hash changed). Edited proposals are Aaron's and are never listed; nothing is deleted.

`generated_hash` is the sha256 of the note's normalised text (UTF-8, LF, no BOM, NFC) without its
`generated_hash:` line.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from renasci.core.calendar import Date
from renasci.vault.ids import assign, slug
from renasci.vault.loader import nfc, normalise

HASH_LINE = re.compile(r"^generated_hash: .*\n", re.MULTILINE)
WORLD_EVENTS = ("people.",)  # event types a proposal may be made of (not engine or LOD bookkeeping)
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def content_hash(text: str) -> str:
    return hashlib.sha256(HASH_LINE.sub("", text, count=1).encode("utf-8")).hexdigest()


def untouched(text: str) -> bool:
    m = re.search(r"^generated_hash: (\S+)$", text, re.MULTILINE)
    return bool(m) and m.group(1) == content_hash(text)


def _source_of(text: str) -> str | None:
    m = re.search(r"^  (?:entity|event): (\S+)$", text, re.MULTILINE)
    return m.group(1) if m else None


def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _filename(title: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", title).strip().rstrip(". ") or "proposal"
    return f"{safe}_" if safe.split(".")[0].lower() in RESERVED else safe


def _proposed_ids(root: Path) -> set[str]:
    out = set()
    for p in (root / "_proposed").rglob("*.md") if (root / "_proposed").is_dir() else []:
        m = re.search(r"^id: (\S+)$", normalise(p.read_bytes())[0], re.MULTILINE)
        if m:
            out.add(m.group(1))
    return out


def propose(state: dict, events: list[dict], entity: str, vault, calendar, source: dict,
            bindings: dict | None = None) -> tuple[str, str, list[str]]:
    """(the note's path under the vault, its text, notes for Aaron) for a run's person or event."""
    ids = assign(vault)
    key_of = {v: k for k, v in ids.items()}
    canon_of = {ent: cid for cid, ent in (bindings or {}).items()}  # a run entity born as a canon id

    def canon(eid):
        return eid if eid in key_of else canon_of.get(eid) if canon_of.get(eid) in key_of else None

    def link(eid):
        cid = canon(eid)
        return _q(f"[[{vault.notes[key_of[cid]].title}]]") if cid else None

    def when(d):
        return calendar.format(Date.from_json(d), "day")

    if canon(entity):
        raise ValueError(f"{entity} is already canon as {canon(entity)}")
    ents = {e["id"]: e for e in state["entities"]}
    stems = {n.title.lower() for n in vault.notes.values()}
    taken = set(ids.values()) | _proposed_ids(Path(vault.root))
    notes: list[str] = []
    if entity in ents and ents[entity]["kind"] == "person":
        f = ents[entity]["fields"]
        name = nfc(f.get("name") or entity)
        title = name if name.lower() not in stems else f"{name} ({entity[-6:]})"
        fm = [("type", "character"), ("name", _q(name))]
        died = next((ev for ev in events if ev["type"] == "people.death" and entity in ev["roles"].get("deceased", [])), None)
        fm += [("born", when(f["born"]))] if f.get("born") else []
        fm += [("died", when(died["date"]))] if died else []
        fm += [("sex", f["sex"])] if f.get("sex") in ("m", "f") else []
        for k in ("house", "father", "mother"):
            if f.get(k):
                if link(f[k]):
                    fm.append((k, link(f[k])))
                else:
                    notes.append(f"{k} {f[k]} is not canon: propose them first to link them")
        kind, source_key = "character", "entity"
        body = (f"{name}, born {when(f['born'])}" if f.get("born") else name) + \
               (f", died {when(died['date'])} ({died['payload'].get('cause')})" if died else "") + "."
    else:
        ev = next((e for e in events if e["id"] == entity), None)
        if ev is None:
            raise ValueError(f"{entity} is neither a person nor an event of that run")
        if not ev["type"].startswith(WORLD_EVENTS):
            raise ValueError(f"{ev['type']} is engine bookkeeping, not a story to propose")
        roles = {}
        for role, members in sorted(ev["roles"].items()):
            if not members:
                continue
            missing = [m for m in members if not link(m)]
            if missing:
                raise ValueError(f"{entity}'s {role} {missing} isn't canon: propose them first (S2 §9)")
            roles[role] = [link(m) for m in members]
        if not roles:
            raise ValueError(f"{entity} names nobody: there is nothing canon to tie it to")
        title = f"{ev['type'].split('.')[-1].replace('_', ' ').title()} {when(ev['date'])}"
        fm = [("type", "event"), ("engine", ev["type"]), ("date", when(ev["date"])),
              ("participants", "{" + ", ".join(f"{r}: {v[0] if len(v) == 1 else '[' + ', '.join(v) + ']'}"
                                               for r, v in roles.items()) + "}")]
        kind, source_key = "event", "event"
        body = f"A {ev['type']} of the run, {when(ev['date'])}."
    base = slug(title) or "proposal"
    vid, n = f"v:{base}", 2
    while vid in taken:
        vid, n = f"v:{base}-{n}", n + 1
    lines = ["---", f"id: {vid}", *(f"{k}: {v}" for k, v in fm), "canon: proposed", "source:",
             f"  run: {source['run']}", f"  run_path: {source.get('run_path', '')}", f"  {source_key}: {entity}",
             f"  state_hash: {source.get('state_hash', '')}", f"  vault_digest: {vault.digest}",
             "generated_hash: PENDING", "---",
             f"*Proposed from the run {source['run']}: generated, not canon until promoted (S2 §9).*", "", body, ""]
    text = nfc("\n".join(lines))
    text = text.replace("generated_hash: PENDING", f"generated_hash: {content_hash(text)}")
    return f"_proposed/{kind}/{_filename(title)}.md", text, notes


def write_proposal(root, rel: str, text: str) -> str:
    """Write `text` at `rel` (under the vault root) unless that file was edited or is someone else's;
    then at `-2`, `-3`… Returns where it went."""
    root = Path(root)
    base, n = rel.removesuffix(".md"), 1
    mine = _source_of(text)
    while True:
        target = rel if n == 1 else f"{base}-{n}.md"
        path = root / target
        if path.exists():
            old = normalise(path.read_bytes())[0]
            if not (untouched(old) and _source_of(old) == mine):
                n += 1
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return target


def stale(root, runs) -> list[dict]:
    """Untouched proposals whose run is gone or has been run again since ([{path, why}]). A proposal's run
    is found where it was (`run_path`), else under `runs`."""
    root, runs = Path(root), Path(runs)
    out = []
    for p in sorted((root / "_proposed").rglob("*.md")) if (root / "_proposed").is_dir() else []:
        text = normalise(p.read_bytes())[0]
        if "\ncanon: proposed\n" not in text or not untouched(text):
            continue
        run = re.search(r"^  run: (.+)$", text, re.MULTILINE)
        where = re.search(r"^  run_path: (.*)$", text, re.MULTILINE)
        recorded = re.search(r"^  state_hash: (.*)$", text, re.MULTILINE)
        if not run:
            continue
        rel = p.relative_to(root).as_posix()
        folder = Path(where.group(1).strip()) if where and where.group(1).strip() else runs / run.group(1)
        manifest = folder / "manifest.json"
        if not manifest.is_file():
            out.append({"path": rel, "why": f"its run {run.group(1)} is gone"})
        elif json.loads(manifest.read_text(encoding="utf-8")).get("meta", {}).get("state_hash") != (
                recorded.group(1).strip() if recorded else None):
            out.append({"path": rel, "why": f"its run {run.group(1)} has been run again since"})
    return out
