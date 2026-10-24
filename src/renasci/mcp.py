"""An MCP server over runs and the vault (S12 spec §5, #118): how Claude, in a session, reads a run and
fetches context packs to write from.

`renasci mcp --runs <folder> [--vault <folder>]` speaks MCP over stdio: JSON-RPC 2.0, one message per
line, UTF-8. `initialize` (the client's protocol version if we know it, else our latest), `ping`,
`tools/list`, `tools/call`; notifications are never answered. A tool's own failure (no such run) is a
result with `isError`, so the model sees it; protocol errors are JSON-RPC errors (-32700 bad JSON,
-32601 unknown method, -32602 bad params or an unknown tool). Nothing else is ever written to stdout.

The tools read runs (summaries, events, people with their beliefs' origins, stories, claims) and the
vault (search, a note). The writing tools write under the run's `analysis/` (atomically): `pack` (a
context pack), `chronicle`, `brief` and `check_prose` (a canon check of prose Claude wrote). Each answers
with a summary and a **handle**: a document can be larger than a client takes in one result, so its
sections are paged with `fetch`. Runs are named, never pathed: a run is a folder directly in the runs folder.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from renasci import __version__
from renasci.observe import ENTITY, list_runs, safe_relative

VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
PAGE = 50
MAX_PAGE = 200
HANDLES = 32
TOOLS = {
    "runs": ("The run folders: world, end, ripples, and the run each was replayed from.", {}),
    "run_summary": ("A run's span, people, top sagas and ripples.", {"run": "string"}),
    "events": ("A run's events (paged), filtered by type prefix, an entity in them, a place, or a date span "
               "([age, year, day] lists).", {"run": "string", "type": "string?", "entity": "string?", "place": "string?",
                                            "from": "array?", "to": "array?", "cursor": "integer?", "limit": "integer?"}),
    "event": ("One event, read in a line, with its causes and consequences.", {"run": "string", "id": "string"}),
    "person": ("A person: kin, house, wants, wound, ties, schemes, and their beliefs with where each began.",
               {"run": "string", "id": "string"}),
    "stories": ("A run's sagas and arcs (paged).", {"run": "string", "cursor": "integer?"}),
    "claims": ("What the run's world believes, by question, each claim judged against what happened.", {"run": "string"}),
    "pack": ("Build a context pack: subject arc|saga|person|event|topic and its id, from a point of view "
             "(omniscient, or a person, house or settlement id). Answers with a summary and a handle for fetch.",
             {"run": "string", "subject": "string", "id": "string", "pov": "string?"}),
    "chronicle": ("Write a POV chronicle: the subject told as its author (pov) believes it, with where it departs "
                  "from the truth. Answers with a summary and a handle (sections: text, divergence).",
                  {"run": "string", "subject": "string", "id": "string", "pov": "string?"}),
    "brief": ("Write a campaign brief for a saga or an event: premise, what really happened, beliefs, factions, NPCs, "
              "hooks, places. Answers with a summary and a handle (sections: text, threads).",
              {"run": "string", "subject": "string", "id": "string"}),
    "check_prose": ("Check prose against a run (up to 256 KB of Markdown; ```claims blocks are read exactly), from a "
                    "point of view: contradictions, leaks, half truths, ambiguous names. Answers with the counts and a "
                    "handle (sections: findings, sentences).", {"run": "string", "text": "string", "pov": "string?"}),
    "fetch": ("A page of a handle's section: a pack's people, places, events, beliefs, threads; a chronicle's or "
              "brief's text (lines) and divergence or threads; a check's findings and sentences.",
              {"handle": "string", "section": "string", "cursor": "integer?"}),
    "vault_search": ("The vault's notes whose title, type or id contains the query (empty: all, paged).",
                     {"query": "string", "type": "string?", "cursor": "integer?"}),
    "vault_note": ("A vault note by id or title: its front matter and text.", {"note": "string"}),
}
JSON_TYPES = {"string": "string", "integer": "integer", "array": "array"}
PY_TYPES = {"string": str, "integer": int, "array": list}


class ToolError(Exception):
    """A tool's own failure: told to the model as a result, not a protocol error."""


def _schema(args: dict) -> dict:
    props, required = {}, []
    for name, t in args.items():
        props[name] = {"type": JSON_TYPES[t.rstrip("?")]}
        if not t.endswith("?"):
            required.append(name)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


class Server:
    def __init__(self, runs, vault=None):
        self.runs = Path(runs).resolve()
        self.vault_root = Path(vault).resolve() if vault else None
        self._vault = None
        self._open: dict[str, object] = {}  # run name -> story.pack.Run (the last few)
        self.handles: dict[str, dict] = {}

    # ------------------------------------------------------------ protocol

    def handle(self, msg) -> dict | None:
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "not a JSON-RPC 2.0 request")
        if "id" not in msg:
            return None  # (a notification: never answered)
        mid, method, params = msg["id"], msg["method"], msg.get("params") or {}
        if not isinstance(params, dict):
            return _error(mid, -32602, "params is an object")
        if method == "initialize":
            asked = params.get("protocolVersion")
            return _result(mid, {"protocolVersion": asked if asked in VERSIONS else VERSIONS[-1],
                                 "capabilities": {"tools": {"listChanged": False}},
                                 "serverInfo": {"name": "renasci", "version": __version__}})
        if method == "ping":
            return _result(mid, {})
        if method == "tools/list":
            return _result(mid, {"tools": [{"name": n, "description": d, "inputSchema": _schema(a)}
                                           for n, (d, a) in TOOLS.items()]})
        if method == "tools/call":
            name, args = params.get("name"), params.get("arguments") or {}
            if name not in TOOLS:
                return _error(mid, -32602, f"no tool {name!r}")
            spec = TOOLS[name][1]
            if not isinstance(args, dict) or set(args) - set(spec) or \
                    any(not t.endswith("?") and k not in args for k, t in spec.items()):
                return _error(mid, -32602, f"{name} takes {sorted(spec)} (required: "
                                           f"{sorted(k for k, t in spec.items() if not t.endswith('?'))})")
            wrong = [k for k, v in args.items() if not isinstance(v, PY_TYPES[spec[k].rstrip("?")])
                     or isinstance(v, bool)]
            if wrong:
                return _error(mid, -32602, f"{name}: {wrong} of the wrong type (see its inputSchema)")
            try:
                with redirect_stdout(io.StringIO()):  # (nothing a reused function prints may reach the stream)
                    text, error = json.dumps(getattr(self, f"t_{name}")(**args), ensure_ascii=False, allow_nan=False), False
            except (ToolError, ValueError, LookupError, TypeError, AttributeError, OSError) as err:
                text, error = json.dumps({"error": str(err) or type(err).__name__}, ensure_ascii=False), True
            return _result(mid, {"content": [{"type": "text", "text": text}], "isError": error})
        return _error(mid, -32601, f"no method {method!r}")

    # ------------------------------------------------------------ helpers

    def run(self, name):
        from renasci.story.pack import Run

        if not isinstance(name, str) or safe_relative(name) != name or "/" in name:
            raise ToolError(f"a run is named by its folder, not a path: {name!r}")
        folder = (self.runs / name).resolve()
        if not folder.is_relative_to(self.runs) or not (folder / "manifest.json").is_file():
            raise ToolError(f"no run {name!r} (see the runs tool)")
        if name not in self._open:
            if len(self._open) >= 2:
                self._open.pop(next(iter(self._open)))
            self._open[name] = Run(folder)
        return self._open[name]

    @staticmethod
    def _id(ident) -> str:
        if not isinstance(ident, str) or not ENTITY.fullmatch(ident):
            raise ToolError(f"not an id: {ident!r}")
        return ident

    @staticmethod
    def _page(items: list, cursor, limit=PAGE) -> dict:
        start = int(cursor or 0)
        if start < 0:
            raise ToolError("a cursor is a `next` from an earlier page (0 or more)")
        limit = max(1, min(int(PAGE if limit is None else limit), MAX_PAGE))
        part = items[start:start + limit]
        return {"items": part, "total": len(items), "next": start + limit if start + limit < len(items) else None}

    def vault(self):
        if self.vault_root is None:
            raise ToolError("no vault (start the server with --vault)")
        if self._vault is None:
            from renasci.vault.loader import load

            self._vault = load(self.vault_root)
        return self._vault

    # ------------------------------------------------------------ tools

    def t_runs(self):
        out = []
        for r in list_runs(self.runs):
            meta = r["manifest"].get("meta", {})
            recipe = meta.get("recipe", {})
            out.append({"name": r["name"], "world": recipe.get("run", {}).get("world"), "end": recipe.get("run", {}).get("end"),
                        "complete": meta.get("complete", True), "ripples": len(recipe.get("ripple", [])),
                        "from": (meta.get("replayed_from") or {}).get("run")})
        return {"runs": out}

    def t_run_summary(self, run):
        r = self.run(run)
        recipe = r.manifest["meta"].get("recipe", {})
        people = [e for e in r.ents.values() if e["kind"] == "person"]
        return {"run": r.name, "world": recipe.get("run", {}).get("world"),
                "span": [r.events[0]["date"], r.events[-1]["date"]] if r.events else None,
                "people": len(people), "living": sum(1 for p in people if p["status"] == "active"),
                "events": len(r.events), "ripples": recipe.get("ripple", []),
                "sagas": [{"id": s["id"], "title": s["title"], "span": s["span"]} for s in r.stories["sagas"][:10]]}

    def t_events(self, run, type=None, entity=None, place=None, cursor=0, limit=PAGE, **span):
        from renasci.story.text import reading

        r = self.run(run)
        lo, hi = span.get("from"), span.get("to")
        pool = list(dict.fromkeys(r.involves.get(self._id(entity), []))) if entity else [e["id"] for e in r.events]
        rows = []
        for i in pool:
            e = r.by_id[i]
            if (type and not e["type"].startswith(type)) or (place and e.get("place") != place) \
                    or (lo and e["date"] < lo) or (hi and e["date"] > hi):
                continue
            rows.append({"id": i, "date": e["date"], "type": e["type"], "place": e.get("place"),
                         "text": reading(e, r.names, r.by_id) or e["type"], "secret": e.get("visibility") == "secret"})
        page = self._page(rows, cursor, limit)
        return {"events": page["items"], "total": page["total"], "next": page["next"]}

    def t_event(self, run, id):
        from renasci.story.text import reading

        r = self.run(run)
        e = r.by_id.get(self._id(id))
        if e is None:
            raise ToolError(f"no event {id} in {run}")

        def brief(x):
            return {"id": x["id"], "date": x["date"], "type": x["type"], "text": reading(x, r.names, r.by_id) or x["type"]}

        causes = [r.by_id[ref] for kind, ref in e.get("causes") or [] if kind == "event" and ref in r.by_id]
        return {**brief(e), "place": e.get("place"), "roles": e.get("roles"), "payload": e.get("payload"),
                "secret": e.get("visibility") == "secret", "causes": [brief(c) for c in causes],
                "consequences": [brief(r.by_id[c]) for c in r.consequences.get(id, [])][:MAX_PAGE]}

    def t_person(self, run, id):
        from renasci.story.pack import _belief_rows

        r = self.run(run)
        p = r.ents.get(self._id(id))
        if p is None or p["kind"] != "person":
            raise ToolError(f"no person {id} in {run}")
        f = p["fields"]
        kin = {k: (f.get(k) if k != "children" else f.get(k) or []) for k in ("mother", "father", "spouse", "children")}
        schemes = [{"id": i, "state": e["fields"].get("state"), "target": e["fields"].get("target"),
                    "plan": [s["action"] for s in e["fields"].get("plan") or []]}
                   for i, e in sorted(r.ents.items()) if e["kind"] == "scheme" and e["fields"].get("owner") == id]
        ties = [{"other": (lambda t: t.get("b") if t.get("a") == id else t.get("a"))(r.ents[t]["fields"]),
                 "kind": r.ents[t]["fields"].get("kind"), "ended": r.ents[t]["fields"].get("ended")}
                for t in f.get("ties") or [] if t in r.ents]
        return {"id": id, "name": r.names.full(id), "status": p["status"], "born": f.get("born"),
                "died": r.died.get(id), "house": f.get("house"), "kin": kin, "wants": f.get("wants") or [],
                "wound": f.get("wound"), "need": f.get("need"), "grievances": f.get("grievances") or [],
                "ties": ties, "schemes": schemes, "beliefs": _belief_rows(r, id, f.get("beliefs") or {}, verdicts=True)}

    def t_stories(self, run, cursor=0):
        r = self.run(run)
        arcs = [{k: a[k] for k in ("id", "title", "owner_name", "class", "outcome", "span", "salience")} for a in r.stories["arcs"]]
        page = self._page(arcs, cursor)
        return {"sagas": r.stories["sagas"], "arcs": page["items"], "total_arcs": page["total"], "next": page["next"]}

    def t_claims(self, run):
        r = self.run(run)
        f = r.folder / "analysis" / "claims.json" if r.folder else None
        if f is not None and f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        from renasci.analysis.claims import claims_report

        return claims_report(r.events, r.state, r.geography)

    def _subject(self, run, subject, id, pov="omniscient"):
        r = self.run(run)
        if subject not in ("arc", "saga", "person", "event", "topic"):
            raise ToolError("subject is arc, saga, person, event or topic")
        self._id(id)
        if pov != "omniscient":
            self._id(pov)
        return r

    @staticmethod
    def _write(path: Path, text: str) -> None:
        """Atomically: a temporary file, then a rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(path)

    def _keep(self, kind: str, key: list, sections: dict) -> str:
        from renasci.core.canon import digest

        handle = kind + digest(key, size=8)
        self.handles.pop(handle, None)
        self.handles[handle] = sections
        while len(self.handles) > HANDLES:  # (the oldest go: a long session doesn't grow without end)
            self.handles.pop(next(iter(self.handles)))
        return handle

    def t_pack(self, run, subject, id, pov="omniscient"):
        from renasci.core.canon import canonical
        from renasci.story.pack import build
        from renasci.story.schema import PACK, validate

        r = self._subject(run, subject, id, pov)
        pack = build(r, (subject, id), pov)
        if validate(pack, PACK):
            raise ToolError("the pack didn't fit its schema")
        handle = self._keep("pk", [r.name, subject, id, pov], {k: pack[k] for k in PACK_SECTIONS})
        if r.folder is not None:
            self._write(r.folder / "analysis" / "packs" / f"{subject}-{_safe(id)}--{_safe(pov)}.json", canonical(pack) + "\n")
        return {"handle": handle, "subject": pack["subject"], "pov": pack["pov"], "span": pack["span"],
                "counts": {k: len(pack[k]) for k in PACK_SECTIONS}, "sections": list(PACK_SECTIONS)}

    def t_chronicle(self, run, subject, id, pov="omniscient"):
        from renasci.story.chronicle import chronicle

        r = self._subject(run, subject, id, pov)
        doc = chronicle(r, (subject, id), pov)
        name = f"{subject}-{_safe(id)}--{_safe(pov)}.md"
        if r.folder is not None:
            self._write(r.folder / "analysis" / "chronicles" / name, doc["text"])
        handle = self._keep("ch", [r.name, subject, id, pov], {"text": _lines(doc["text"]), "divergence": doc["divergence"]})
        return {"handle": handle, "title": doc["title"], "file": name, "divergence": len(doc["divergence"]),
                "lines": len(_lines(doc["text"])), "sections": ["text", "divergence"]}

    def t_brief(self, run, subject, id):
        from renasci.story.brief import brief

        r = self._subject(run, subject, id)
        doc = brief(r, (subject, id))
        name = f"{subject}-{_safe(id)}.md"
        if r.folder is not None:
            self._write(r.folder / "analysis" / "briefs" / name, doc["text"])
        handle = self._keep("br", [r.name, subject, id], {"text": _lines(doc["text"]), "threads": doc["threads"]})
        return {"handle": handle, "title": doc["pack"]["subject"]["title"], "file": name, "npcs": len(doc["npcs"]),
                "hooks": len(doc["threads"]), "latch": len(doc["latch"]), "lines": len(_lines(doc["text"])),
                "sections": ["text", "threads"]}

    def t_check_prose(self, run, text, pov="omniscient"):
        from renasci.core.canon import canonical
        from renasci.story.check import MAX_TEXT, check, findings

        if len(text.encode("utf-8")) > MAX_TEXT:
            raise ToolError(f"the text is over {MAX_TEXT // 1024} KB")
        r = self.run(run)
        if pov != "omniscient":
            self._id(pov)
        report = check(r, text, pov)
        name = f"{report['text']}--{_safe(pov)}.json"
        if r.folder is not None:
            self._write(r.folder / "analysis" / "checks" / name, canonical(report) + "\n")
        found = findings(report)
        handle = self._keep("ck", [r.name, report["text"], pov], {"findings": found, "sentences": report["sentences"]})
        return {"handle": handle, "file": name, "counts": report["counts"], "sentences": len(report["sentences"]),
                "sections": ["findings", "sentences"]}

    def t_fetch(self, handle, section, cursor=0):
        doc = self.handles.get(handle)
        if doc is None:
            raise ToolError(f"no handle {handle!r} (make one with pack, chronicle, brief or check_prose)")
        if section not in doc:
            raise ToolError(f"this handle's sections are {', '.join(doc)}")
        return self._page(doc[section], cursor)

    def t_vault_search(self, query, type=None, cursor=0):
        v = self.vault()
        q = query.lower()
        rows = [{"key": k, "title": n.title, "id": n.id, "type": n.type, "status": n.status}
                for k, n in v.notes.items() if (not type or n.type == type)
                and (not q or q in n.title.lower() or q in (n.id or "").lower() or q == n.type)]
        page = self._page(rows, cursor)
        return {"notes": page["items"], "total": page["total"], "next": page["next"]}

    def t_vault_note(self, note):
        v = self.vault()
        key = next((k for k, n in v.notes.items() if note in (n.id, n.title, k)), None) or v.resolve(note)
        if key is None:
            raise ToolError(f"no note {note!r} in the vault")
        n = v.notes[key]
        path = (Path(v.root) / n.path).resolve() if n.path else None
        if path is None or not path.is_relative_to(self.vault_root) or path.suffix != ".md":
            raise ToolError(f"note {note!r} isn't readable")
        return {"key": key, "title": n.title, "id": n.id, "type": n.type, "status": n.status,
                "frontmatter": n.frontmatter, "text": path.read_text(encoding="utf-8")}


PACK_SECTIONS = ("people", "places", "events", "beliefs", "threads")


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _result(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _no_nan(constant):
    raise ValueError(f"{constant} isn't JSON")


def serve(runs, vault=None, stdin=None, stdout=None) -> None:
    """Read requests a line at a time and answer each on a line of its own, until the input ends."""
    stdin = stdin or sys.stdin.buffer  # (bytes: a line that isn't UTF-8 is that line's error, not the server's end)
    out = stdout or io.TextIOWrapper(sys.stdout.buffer, encoding="ascii", newline="\n", write_through=True)
    server = Server(runs, vault)
    for line in stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line, parse_constant=_no_nan)
        except ValueError:
            reply = _error(None, -32700, "not JSON")
        else:
            try:
                reply = server.handle(msg)
            except Exception as err:  # noqa: BLE001  (a bug answers as an error; the server keeps going)
                print(f"renasci mcp: {err!r}", file=sys.stderr)
                reply = _error(msg.get("id") if isinstance(msg, dict) else None, -32603, "internal error")
        if reply is not None:
            out.write(json.dumps(reply, allow_nan=False) + "\n")  # (ASCII: a lone surrogate is escaped, not fatal)
            out.flush()
