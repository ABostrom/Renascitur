"""The map editor's server side (S5 spec §7, #84): `renasci observe --edit-map <geography>` serves the
geography and the world's private layers to the editor, checks an edited state, and saves it (baked,
validated together, written atomically with a .bak). Without the flag there is no editor."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from renasci import geo
from renasci.observe import make_server

DOC = {"regions": [{"id": "g:north"}],
       "places": [{"id": "t:a", "kind": "settlement", "region": "g:north"},
                  {"id": "t:b", "kind": "settlement", "region": "g:north"}],
       "routes": [{"id": "g:a--b", "ends": ["t:a", "t:b"], "days": 7, "kind": "road"}]}
GRID = {"cols": 6, "rows": 5, "miles": 24, "days_per_cell": 1.2,
        "terrain": {"plains": 1.0, "hills": 2.0, "water": None},
        "cells": {"c:1,1": {"region": "g:north"}, "c:2,1": {"region": "g:north"}, "c:4,4": {"terrain": "water"}}}
LAYOUT = {"places": {"t:a": {"cell": "c:1,1"}, "t:b": {"cell": "c:2,1"}}, "routes": {}}


@pytest.fixture()
def editor(tmp_path):
    world = tmp_path / "toyland.json"
    geo.save(world, DOC)
    private = tmp_path / "maps" / "toyland" / "private"
    private.mkdir(parents=True)
    (private / "grid.json").write_text(json.dumps(GRID), encoding="utf-8")
    (private / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    (private / "base.png").write_bytes(b"\x89PNG fake")
    app = tmp_path / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, tmp_path / "runs", port=0, edit_map=world, maps=tmp_path / "maps")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", world, private
    server.shutdown()


def call(base, path, body=None, method=None, headers=None, raw=False):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    h = {"Content-Type": "application/json", "Origin": base, "X-Renasci-Launch": "1"} if headers is None else headers
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data else "GET"), headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            payload = r.read()
            return r.status, (payload if raw else json.loads(payload or b"null")), dict(r.headers)
    except urllib.error.HTTPError as e:
        payload = e.read()
        try:
            return e.code, json.loads(payload), dict(e.headers)
        except ValueError:
            return e.code, payload, dict(e.headers)


def state(base):
    return call(base, "/api/map")[1]


def test_the_editor_reads_the_geography_and_the_private_layers(editor):
    base, _, _ = editor
    s = state(base)
    assert s["world"] == "toyland" and s["geography"] == DOC and s["grid"] == GRID and s["layout"] == LAYOUT
    assert s["markers"] == [] and call(base, "/api/capabilities")[1]["edit_map"] == "toyland"


def test_the_private_image_is_served_only_to_this_page(editor):
    base, _, _ = editor
    status, body, headers = call(base, "/api/map/base.png", raw=True)
    assert status == 200 and body.startswith(b"\x89PNG")
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin" and headers["Cache-Control"] == "no-store"


def test_a_check_returns_the_findings_for_an_unsaved_state(editor):
    base, _, _ = editor
    s = state(base)
    s["layout"]["routes"] = {"g:a--b": {"cells": ["c:1,1", "c:2,1"]}}
    status, findings, _ = call(base, "/api/map/check", {k: s[k] for k in ("geography", "grid", "layout")})
    assert status == 200 and [f["kind"] for f in findings] == ["days_differ"]  # (7 typed, 2 by the cells)


def test_a_save_bakes_and_writes_every_file_with_a_backup(editor):
    base, world, private = editor
    s = state(base)
    s["layout"]["routes"] = {"g:a--b": {"cells": ["c:1,1", "c:2,1"]}}
    s["grid"]["cells"]["c:3,1"] = {"terrain": "hills"}
    status, out, _ = call(base, "/api/map", {k: s[k] for k in ("geography", "grid", "layout")}, method="PUT")
    assert status == 200 and out["changed"] == ["g:a--b"]
    assert geo.load(world)["routes"][0]["days"] == 2  # (baked)
    assert world.read_text(encoding="utf-8") == geo.dumps(geo.load(world))  # (geo.dumps: a reviewable diff)
    assert json.loads((private / "layout.json").read_text(encoding="utf-8"))["routes"]["g:a--b"]["cells"] == ["c:1,1", "c:2,1"]
    assert json.loads((private / "grid.json").read_text(encoding="utf-8"))["cells"]["c:3,1"] == {"terrain": "hills"}
    assert geo.load(world.with_suffix(".json.bak"))["routes"][0]["days"] == 7  # (the version before)


def test_an_inconsistent_save_is_refused_with_findings_and_nothing_is_written(editor):
    base, world, private = editor
    before = world.read_text(encoding="utf-8"), (private / "grid.json").read_text(encoding="utf-8")
    s = state(base)
    s["grid"]["cells"]["c:1,1"] = {"region": "g:atlantis"}  # (a region the geography doesn't have)
    status, findings, _ = call(base, "/api/map", {k: s[k] for k in ("geography", "grid", "layout")}, method="PUT")
    assert status == 400 and any(f["kind"] == "unknown_region" for f in findings)
    assert (world.read_text(encoding="utf-8"), (private / "grid.json").read_text(encoding="utf-8")) == before


@pytest.mark.parametrize("change", ["origin", "header", "type", "host"])
def test_a_save_must_come_from_the_editor_itself(editor, change):
    base, world, _ = editor
    s = state(base)
    h = {"Content-Type": "application/json", "Origin": base, "X-Renasci-Launch": "1"}
    if change == "origin":
        h["Origin"] = "http://evil.example"
    elif change == "header":
        del h["X-Renasci-Launch"]
    elif change == "type":
        h["Content-Type"] = "text/plain"
    else:
        h["Host"] = "evil.example"
    before = world.read_text(encoding="utf-8")
    status, _, _ = call(base, "/api/map", {k: s[k] for k in ("geography", "grid", "layout")}, method="PUT", headers=h)
    assert status == 403 and world.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("body", [{"geography": DOC}, {"geography": DOC, "grid": GRID, "layout": LAYOUT, "path": "x"},
                                  ["nope"], {"geography": [], "grid": GRID, "layout": LAYOUT}])
def test_a_malformed_save_is_refused(editor, body):
    base, _, _ = editor
    assert call(base, "/api/map", body, method="PUT")[0] == 400


def test_without_the_flag_there_is_no_editor(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, tmp_path / "runs", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert call(base, "/api/capabilities")[1]["edit_map"] is None
        assert call(base, "/api/map")[0] == 404
        assert call(base, "/api/map", {"geography": DOC, "grid": GRID, "layout": LAYOUT}, method="PUT")[0] == 405
    finally:
        server.shutdown()


@pytest.mark.parametrize("bad", [{"layout": {"places": []}}, {"layout": {"places": {"t:a": {"cell": 3}}}},
                                 {"layout": {"routes": {"g:a--b": {"cells": "c:1,1"}}}},
                                 {"grid": {**GRID, "cells": {"c:1,1": {"terrain": []}}}}])
def test_a_badly_shaped_state_is_a_400_not_a_crash(editor, bad):
    base, _, _ = editor
    s = state(base)
    body = {k: s[k] for k in ("geography", "grid", "layout")}
    for k, v in bad.items():
        body[k] = v if k == "grid" else {"places": {}, "routes": {}, **v}
    for path, method in (("/api/map/check", "POST"), ("/api/map", "PUT")):
        assert call(base, path, body, method=method)[0] == 400


def test_a_save_that_fails_part_way_leaves_every_file_as_it_was(editor, monkeypatch):
    from renasci import mapedit

    base, world, private = editor
    before = {p: p.read_text(encoding="utf-8") for p in (world, private / "grid.json", private / "layout.json")}
    real = mapedit.os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 2:  # (the second file can't be replaced: open elsewhere, say)
            raise PermissionError("in use")
        return real(src, dst)

    monkeypatch.setattr(mapedit.os, "replace", flaky)
    s = state(base)
    s["layout"]["routes"] = {"g:a--b": {"cells": ["c:1,1", "c:2,1"]}}
    status, _, _ = call(base, "/api/map", {k: s[k] for k in ("geography", "grid", "layout")}, method="PUT")
    assert status == 409
    assert {p: p.read_text(encoding="utf-8") for p in before} == before
    assert not list(world.parent.glob("*.tmp")) and not list(private.glob("*.tmp"))
