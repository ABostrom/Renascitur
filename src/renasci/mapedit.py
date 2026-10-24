"""The map editor's files (S5 spec §6-7, #84): what `renasci observe --edit-map` reads and writes.

A world being edited is its geography file (the S4 file the sim reads, committed) and its private
layers in `maps/<world>/private/` (git-ignored): `grid.json` and `layout.json` (#80), and the import's
`markers.json` and `base.png` (#82). The editor holds all of it as one **state**
`{geography, grid, layout}`; a save is that state, checked together (a painted region and the place it
moves must agree), baked (route days and regions from the cells), and written: the geography with
`geo.dumps` (a reviewable diff), the private layers as sorted JSON; each atomically (a temporary file,
then a rename), with the previous version kept as `<file>.bak` (git-ignored).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from renasci import geo, mapgrid

STATE_KEYS = ("geography", "grid", "layout")
_SAVING = threading.Lock()  # (two tabs saving at once take turns)


class MapFiles:
    def __init__(self, geography, private):
        self.geography, self.private = Path(geography).resolve(), Path(private).resolve()
        self.world = self.geography.stem

    def _json(self, name: str, default):
        path = self.private / name
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default

    def load(self) -> dict:
        """Everything the editor shows; a file that can't be read is said, rather than a hang."""
        try:
            return self._load()
        except (OSError, ValueError) as err:
            return {"world": self.world, "error": f"couldn't read the map's files: {err}"}

    def _load(self) -> dict:
        markers = self._json("markers.json", {"markers": []})
        return {"world": self.world, "geography": json.loads(self.geography.read_text(encoding="utf-8")),
                "grid": self._json("grid.json", None), "layout": self._json("layout.json", {"places": {}, "routes": {}}),
                "markers": markers.get("markers", []), "base": (self.private / "base.png").is_file()}

    def base(self) -> Path | None:
        path = self.private / "base.png"
        return path if path.is_file() else None


def shape(state) -> str | None:
    """What's wrong with a state's shape (before anything is checked), or None."""
    if not isinstance(state, dict) or set(state) != set(STATE_KEYS):
        return f"a map state is exactly {{{', '.join(STATE_KEYS)}}}"
    if not isinstance(state["geography"], dict) or not isinstance(state["layout"], dict) \
            or not isinstance(state["grid"], (dict, type(None))):
        return "geography and layout are tables; grid is a table or null"
    lay = state["layout"]
    places, routes = lay.get("places", {}), lay.get("routes", {})
    if set(lay) - {"places", "routes"} or not isinstance(places, dict) or not isinstance(routes, dict):
        return "the layout is {places: {...}, routes: {...}}"
    if not all(isinstance(v, dict) and isinstance(v.get("cell"), str) for v in places.values()):
        return "each layout place is {cell: 'c:<col>,<row>'}"
    if not all(isinstance(v, dict) and isinstance(v.get("cells"), list) and all(isinstance(c, str) for c in v["cells"])
               for v in routes.values()):
        return "each layout route is {cells: [cell ids]}"
    g = state["grid"]
    if g is not None:
        bad = mapgrid._malformed(g)
        if bad:
            return bad
        for v in g["cells"].values():
            if not all(isinstance(v.get(k, ""), str) for k in ("terrain", "region")):
                return "a painted cell's terrain and region are names"
    return None


def check(state: dict) -> list[dict]:
    """The geography's findings, then the map's (with a grid): errors and warnings."""
    findings = geo.check(state["geography"])
    if state["grid"] is not None and not any(f["severity"] == "error" for f in findings):
        findings += mapgrid.check(state["geography"], state["grid"], state["layout"])
    return findings


def _write_all(files: dict[Path, str]) -> None:
    """Write several files as one: every new version to a temporary file first, each old one kept as
    <file>.bak, then the swaps back to back; if a swap fails (Windows: a file open elsewhere), those
    already swapped are put back from their .bak, so the files never disagree. Raises PermissionError."""
    tmps = {}
    try:
        for path, text in files.items():
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8", newline="\n")
            tmps[path] = tmp
            if path.exists():
                path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
        done = []
        try:
            for path, tmp in tmps.items():
                os.replace(tmp, path)
                done.append(path)
        except OSError as err:
            for path in done:
                bak = path.with_name(path.name + ".bak")
                if bak.exists():
                    path.write_bytes(bak.read_bytes())
            raise PermissionError(f"{path.name}: {err}") from err
    finally:
        for tmp in tmps.values():
            tmp.unlink(missing_ok=True)


def save(files: MapFiles, state: dict) -> tuple[list[dict], list[str]]:
    """Check, bake and write a state; returns (findings, what the bake changed). Nothing is written when
    the state has errors (findings then say why)."""
    with _SAVING:
        return _save(files, state)


def _save(files: MapFiles, state: dict) -> tuple[list[dict], list[str]]:
    findings = check(state)
    if any(f["severity"] == "error" for f in findings):
        return findings, []
    doc = state["geography"]
    if state["grid"] is not None:
        baked, findings = mapgrid.bake(doc, state["grid"], state["layout"])
        findings = geo.check(baked) + findings
    else:
        baked = doc
    if any(f["severity"] == "error" for f in findings):
        return findings, []
    before = {r["id"]: r["days"] for r in doc.get("routes", [])} | {p["id"]: p.get("region") for p in doc.get("places", [])}
    changed = [r["id"] for r in baked.get("routes", []) if before.get(r["id"]) != r["days"]] + \
        [p["id"] for p in baked.get("places", []) if before.get(p["id"]) != p.get("region")]
    files.private.mkdir(parents=True, exist_ok=True)
    out = {files.geography: geo.dumps(baked),
           files.private / "layout.json": json.dumps(state["layout"], indent=1, sort_keys=True) + "\n"}
    if state["grid"] is not None:
        out[files.private / "grid.json"] = json.dumps(state["grid"], indent=1, sort_keys=True) + "\n"
    _write_all(out)
    return findings, changed
