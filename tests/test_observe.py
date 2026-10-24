"""`renasci observe`: a read-only static server for the Observatory and the runs folder."""

import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

import pytest

from renasci.cli import main
from renasci.core.calendar import Age, Calendar, Date
from renasci.observe import make_server

RECIPE = """
[run]
name = "{name}"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 3"
checkpoint_every_years = 2

[world]
people_per_village = 4
"""


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("observe")
    runs = tmp / "runs"
    recipe = tmp / "r.toml"
    recipe.write_text(RECIPE.format(name="tiny"), encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(runs)]) == 0
    app = tmp / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html><title>Observatory</title>", encoding="utf-8")
    (app / "_app").mkdir()
    (app / "_app" / "x.js").write_text("export const x = 1;", encoding="utf-8")
    server = make_server(app, runs, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", runs
    server.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_serves_the_app_and_falls_back_to_index_for_routes(served):
    base, _ = served
    assert b"Observatory" in get(base + "/")[2]
    assert get(base + "/_app/x.js")[1].startswith(("text/javascript", "application/javascript"))
    assert b"Observatory" in get(base + "/run/tiny/events")[2]  # SPA route


def test_lists_runs_with_their_manifests(served):
    base, _ = served
    status, kind, body = get(base + "/runs/index.json")
    runs = json.loads(body)
    assert status == 200 and kind.startswith("application/json")
    assert [r["name"] for r in runs] == ["tiny"]
    assert runs[0]["manifest"]["meta"]["complete"] is True
    assert runs[0]["manifest"]["meta"]["calendar"]["ages"][0]["abbrev"] == "1X"


def test_serves_run_files_raw(served):
    base, _ = served
    status, _, body = get(base + "/runs/tiny/events/seg-00000.jsonl.gz")
    assert status == 200 and body[:2] == b"\x1f\x8b"


def test_refuses_escapes_writes_and_missing_files(served):
    base, _ = served
    for path in ("/runs/../pyproject.toml", "/runs/tiny/../../x", "/runs/nope/manifest.json"):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(base + path)
        assert err.value.code in (403, 404)
    req = urllib.request.Request(base + "/runs/index.json", data=b"x", method="POST")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code in (405, 501)


def test_binds_to_localhost_only(tmp_path):
    server = make_server(tmp_path, tmp_path, port=0)
    assert server.server_address[0] == "127.0.0.1"
    server.server_close()


# ---------------------------------------------------------------- calendar in the manifest, shared vectors


def test_calendar_round_trips_through_json():
    cal = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=400), Age(4, "4A", "Fourth Age")))
    again = Calendar.from_json(cal.to_json())
    assert again == cal and again.format(Date(4, 37, 95), "season") == cal.format(Date(4, 37, 95), "season")


def test_shared_calendar_vectors():
    """The same vectors are checked by the Observatory's TypeScript port (observatory/src/lib/run)."""
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures" / "calendar_vectors.json").read_text(encoding="utf-8"))
    for case in data["cases"]:
        cal = Calendar.from_json(case["calendar"])
        for v in case["vectors"]:
            d = Date.from_json(v["date"])
            assert cal.format(d, "year") == v["year"]
            assert cal.format(d, "season") == v["season"]
            assert cal.format(d, "day") == v["day"]
            assert cal.parse(v["day"]) == d
        for text in case["invalid"]:
            with pytest.raises(ValueError):
                cal.parse(text)


# ---------------------------------------------------------------- review fixes: security


def raw_get(base, path, host=None):
    """GET without urllib normalising the path, optionally with a forged Host header."""
    import http.client
    from urllib.parse import urlsplit

    u = urlsplit(base)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    conn.putrequest("GET", path, skip_host=host is not None)
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, body


@pytest.mark.parametrize("path", [
    "/runs/%5C%5Cattacker.example%5Cshare%5Cx",   # UNC: would make Windows open SMB
    "/runs/C:%5CWindows%5Cwin.ini",               # drive letter
    "/runs/tiny%5C..%5C..%5Cpyproject.toml",      # backslash traversal
    "/runs/%2F%2Fattacker%2Fshare",               # encoded slashes to an absolute path
    "/runs/tiny/%00manifest.json",                # NUL
])
def test_paths_that_could_leave_the_folders_are_refused_before_touching_the_disk(served, path):
    base, _ = served
    status, _ = raw_get(base, path)
    assert status in (400, 403, 404)


def test_requests_for_another_host_are_refused(served):
    """DNS rebinding: evil.example resolving to 127.0.0.1 must not read the runs."""
    base, _ = served
    port = base.rsplit(":", 1)[1]
    assert raw_get(base, "/runs/index.json", host="evil.example")[0] == 403
    assert raw_get(base, "/runs/index.json", host=f"evil.example:{port}")[0] == 403
    assert raw_get(base, "/runs/index.json", host=f"localhost:{port}")[0] == 200


def test_directory_listings_are_json_file_names(served):
    base, _ = served
    status, kind, body = get(base + "/runs/tiny/events/")
    names = json.loads(body)
    assert status == 200 and kind.startswith("application/json")
    assert "seg-00000.jsonl.gz" in names and all("/" not in n for n in names)


def test_head_does_not_read_the_file(served, monkeypatch):
    import pathlib

    base, _ = served
    calls = []
    real = pathlib.Path.read_bytes
    monkeypatch.setattr(pathlib.Path, "read_bytes", lambda self: calls.append(self) or real(self))
    req = urllib.request.Request(base + "/runs/tiny/events/seg-00000.jsonl.gz", method="HEAD")
    with urllib.request.urlopen(req) as r:
        assert r.status == 200 and int(r.headers["Content-Length"]) > 0
    assert calls == []


@pytest.mark.parametrize("rel, ok", [
    ("tiny/events/seg-00000.jsonl.gz", True),
    ("index.html", True),
    ("_app/x.js", True),
    (r"\\attacker\share\x", False),
    (r"C:\Windows\win.ini", False),
    ("C:/Windows/win.ini", False),
    ("/etc/passwd", False),
    ("//attacker/share", False),
    ("tiny/../../x", False),
    (r"tiny\..\x", False),
    ("tiny/\x00x", False),
    ("tiny/con", True),  # an ordinary name; Windows device names are refused by is_file() later
])
def test_safe_relative_is_decided_without_the_file_system(rel, ok):
    from renasci.observe import safe_relative

    assert (safe_relative(rel) is not None) == ok


def test_observe_defaults_to_the_committed_build(monkeypatch):
    """`renasci observe` with no --app serves observatory/build from this checkout."""
    import renasci.observe as observe
    from renasci.cli import main as cli_main

    seen = {}
    monkeypatch.setattr(observe, "serve", lambda app, runs, port, open_browser, launch, recipes=None, vault=None, edit_map=None, maps=None:
                        seen.update(app=app, launch=launch, vault=vault))
    cli_main(["observe", "--no-browser"])
    from pathlib import Path

    assert (Path(seen["app"]) / "index.html").is_file() and seen["launch"] is False
    assert seen["vault"] is None  # writing to the lore notes is never a default: it needs --vault


@pytest.mark.parametrize("path", ["/run/base/entity/t%3AAshford", "/%5C%5Cattacker.example%5Cshare%5Cx", "/C:%5Cx"])
def test_unsafe_looking_app_routes_get_the_app_without_touching_the_disk(served, path, monkeypatch):
    """Entity ids contain colons; UNC-looking paths must not reach the file system: both get index.html."""
    import pathlib

    base, _ = served
    touched = []
    real = pathlib.Path.resolve
    monkeypatch.setattr(pathlib.Path, "resolve", lambda self, *a, **k: touched.append(str(self)) or real(self, *a, **k))
    status, body = raw_get(base, path)
    assert status == 200 and b"Observatory" in body
    assert not any("attacker" in t or t.startswith("C:\\x") for t in touched)


# ---------------------------------------------------------------- the what-if launcher (opt-in)


def call(base, path, body=None, headers=None, method=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def launch_headers(base):
    return {"Content-Type": "application/json", "Origin": base, "X-Renasci-Launch": "1"}


def test_the_launcher_is_off_unless_asked_for(served):
    base, _ = served
    assert call(base, "/api/capabilities") == (200, {"launch": False, "propose": False, "edit_map": None})
    assert call(base, "/api/launch", {"run": "tiny", "rank": 1}, launch_headers(base))[0] == 405


@pytest.fixture(scope="module")
def launcher(tmp_path_factory, served):
    _, runs = served
    app = tmp_path_factory.mktemp("app2")
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, runs, port=0, launch=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_launch_must_come_from_the_observatory_itself(launcher):
    base = launcher
    assert call(base, "/api/capabilities") == (200, {"launch": True, "propose": False, "edit_map": None})
    body = {"run": "tiny", "rank": 1}
    assert call(base, "/api/launch", body, {**launch_headers(base), "Origin": "http://evil.example"})[0] == 403
    no_header = {k: v for k, v in launch_headers(base).items() if k != "X-Renasci-Launch"}
    assert call(base, "/api/launch", body, no_header)[0] == 403
    assert call(base, "/api/launch", body, {**launch_headers(base), "Content-Type": "text/plain"})[0] == 403


@pytest.mark.parametrize("body", [{"run": "../tiny", "rank": 1}, {"run": "nope", "rank": 1}, {"run": "tiny", "rank": "1"},
                                  {"run": "tiny", "rank": 1, "kind": "favour"}, {"run": "tiny", "rank": 1, "date": "1X 3; rm"},
                                  {"run": "tiny", "rank": 1, "extra": 1}, ["tiny"]])
def test_a_launch_request_is_validated(launcher, body):
    assert call(launcher, "/api/launch", body, launch_headers(launcher))[0] == 400


def test_a_launch_runs_as_a_job_and_reports_back(launcher):
    import time

    status, job = call(launcher, "/api/launch", {"run": "tiny", "rank": 999, "kind": "doom"}, launch_headers(launcher))
    assert status == 202 and job["state"] == "running"
    for _ in range(300):
        _, jobs = call(launcher, "/api/jobs")
        mine = next(j for j in jobs if j["id"] == job["id"])
        if mine["state"] != "running":
            break
        time.sleep(0.2)
    assert mine["state"] == "failed" and "latch point" in mine["output"]  # (a toy run has no latch points)


def test_a_launch_body_must_say_its_length_and_be_small(launcher):
    import http.client
    from urllib.parse import urlsplit

    host = urlsplit(launcher).netloc
    for length, big in (("-1", b"{}"), ("99999", b"{}"), ("abc", b"{}")):
        conn = http.client.HTTPConnection(host, timeout=5)
        conn.putrequest("POST", "/api/launch")
        for k, v in {**launch_headers(launcher), "Host": host, "Content-Length": length}.items():
            conn.putheader(k, v)
        try:
            conn.endheaders(big)
            assert conn.getresponse().status in (411, 413)
        except (ConnectionError, http.client.RemoteDisconnected):
            pass  # the server refused and closed first (it may, under load): refused all the same
        finally:
            conn.close()


# ---------------------------------------------------------------- launching runs and replays from recipes (#57)


@pytest.fixture(scope="module")
def recipes_launcher(tmp_path_factory, served):
    _, runs = served
    tmp = tmp_path_factory.mktemp("recipes")
    recipes = tmp / "recipes"
    recipes.mkdir()
    (recipes / "fresh.toml").write_text(RECIPE.format(name="fresh"), encoding="utf-8")
    (recipes / "again.toml").write_text(RECIPE.format(name="tiny"), encoding="utf-8")  # its run already exists
    (recipes / "broken.toml").write_text("[run\nname = ", encoding="utf-8")
    (recipes / "notes.txt").write_text("not a recipe", encoding="utf-8")
    (recipes / "what-if.toml").write_text(RECIPE.format(name="tiny-whatif") + '\n[[ripple]]\nid = "r1"\nkind = "doom"\n'
                                          'date = "1X 3"\ntarget = "t:Ashford-00"\n', encoding="utf-8")
    app = tmp / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, runs, port=0, launch=True, recipes=recipes)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", runs
    server.shutdown()


def wait_for(base, job):
    import time

    for _ in range(600):
        _, jobs = call(base, "/api/jobs")
        mine = next(j for j in jobs if j["id"] == job["id"])
        if mine["state"] != "running":
            return mine
        time.sleep(0.2)
    raise AssertionError("the job never finished")


def test_recipes_are_listed_with_what_they_run(recipes_launcher):
    base, _ = recipes_launcher
    status, recipes = call(base, "/api/recipes")
    assert status == 200
    by = {r["file"]: r for r in recipes}
    assert sorted(by) == ["again.toml", "broken.toml", "fresh.toml", "what-if.toml"]  # .toml only
    assert by["fresh.toml"] == {"file": "fresh.toml", "name": "fresh", "world": "toy", "end": "1X 3", "ripples": 0,
                                "error": None}
    assert by["what-if.toml"]["ripples"] == 1 and by["broken.toml"]["error"]


def test_no_recipes_without_the_launcher(served):
    base, _ = served
    assert call(base, "/api/recipes")[0] in (404, 405) or call(base, "/api/recipes")[1] == []


def test_a_run_is_launched_from_a_recipe_and_named(recipes_launcher):
    base, runs = recipes_launcher
    status, job = call(base, "/api/run", {"recipe": "fresh.toml"}, launch_headers(base))
    assert status == 202 and job["job"] == "run" and job["recipe"] == "fresh.toml"
    done = wait_for(base, job)
    assert done["state"] == "done" and done["variant"] == "fresh", done["output"]
    assert (runs / "fresh" / "manifest.json").is_file()


def test_a_run_whose_folder_exists_fails_and_says_why(recipes_launcher):
    base, _ = recipes_launcher
    status, job = call(base, "/api/run", {"recipe": "again.toml"}, launch_headers(base))
    assert status == 202
    done = wait_for(base, job)
    assert done["state"] == "failed" and done["output"]


def test_a_replay_forks_a_run_with_a_recipes_ripples(recipes_launcher):
    base, runs = recipes_launcher
    status, job = call(base, "/api/replay", {"run": "tiny", "recipe": "what-if.toml"}, launch_headers(base))
    assert status == 202 and job["job"] == "replay"
    done = wait_for(base, job)
    assert done["state"] == "done" and done["variant"] == "tiny-whatif", done["output"]
    assert (runs / "tiny-whatif" / "manifest.json").is_file()


@pytest.mark.parametrize("path, body", [
    ("/api/run", {"recipe": "../fresh.toml"}), ("/api/run", {"recipe": "notes.txt"}), ("/api/run", {"recipe": "nope.toml"}),
    ("/api/run", {"recipe": 3}), ("/api/run", {"recipe": "fresh.toml", "extra": 1}), ("/api/run", ["fresh.toml"]),
    ("/api/run", {"recipe": "sub/fresh.toml"}), ("/api/run", {"recipe": "C:fresh.toml"}),
    ("/api/replay", {"run": "nope", "recipe": "what-if.toml"}), ("/api/replay", {"run": "tiny"}),
])
def test_launch_requests_are_validated(recipes_launcher, path, body):
    base, _ = recipes_launcher
    assert call(base, path, body, launch_headers(base))[0] == 400


def test_a_run_launch_must_come_from_the_observatory_itself(recipes_launcher):
    base, _ = recipes_launcher
    body = {"recipe": "fresh.toml"}
    assert call(base, "/api/run", body, {**launch_headers(base), "Origin": "http://evil.example"})[0] == 403
    assert call(base, "/api/replay", {"run": "tiny", "recipe": "what-if.toml"},
                {k: v for k, v in launch_headers(base).items() if k != "X-Renasci-Launch"})[0] == 403


def test_a_relative_recipes_folder_works(tmp_path, monkeypatch, served):
    _, runs = served
    monkeypatch.chdir(tmp_path)
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "ok.toml").write_text(RECIPE.format(name="rel"), encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, runs, port=0, launch=True, recipes="recipes")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert [r["file"] for r in call(base, "/api/recipes")[1]] == ["ok.toml"]
        status, job = call(base, "/api/run", {"recipe": "ok.toml"}, launch_headers(base))
        assert status == 202
        assert wait_for(base, job)["state"] == "done"
    finally:
        server.shutdown()


def test_recipes_listed_never_reach_outside_the_folder(tmp_path):
    from renasci.observe import list_recipes

    (tmp_path / "outside.toml").write_text(RECIPE.format(name="outside"), encoding="utf-8")
    folder = tmp_path / "recipes"
    folder.mkdir()
    try:
        (folder / "link.toml").symlink_to(tmp_path / "outside.toml")
    except OSError:
        pytest.skip("this system can't make symlinks")
    assert list_recipes(folder) == []


# ---------------------------------------------------------------- promoting to the vault (#105)


@pytest.fixture(scope="module")
def promoter(tmp_path_factory):
    """A Fourth Age run cast from a copy of the test vault, served with the launcher and that vault."""
    import gzip
    import shutil

    tmp = tmp_path_factory.mktemp("promote")
    vault = tmp / "vault"
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_people", vault)
    runs = tmp / "runs"
    recipe = tmp / "canon.toml"
    recipe.write_text(f'[run]\nname = "canon"\nengine = "0.1.0"\nseed = 1234\nworld = "fourth_age"\nend = "4A 21"\n\n'
                      f'[vault]\npath = "{vault.as_posix()}"\n', encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(runs)]) == 0
    strain = [json.loads(line) for p in sorted((runs / "canon" / "strain").glob("*.gz"))
              for line in gzip.decompress(p.read_bytes()).decode("utf-8").splitlines() if line]
    near_miss = next(s["event"] for s in strain if s["action"] == "guard")
    app = tmp / "app"
    app.mkdir()
    (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
    server = make_server(app, runs, port=0, launch=True, vault=vault)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", vault, near_miss
    server.shutdown()


def test_capabilities_say_whether_promoting_is_possible(promoter, served):
    base, _, _ = promoter
    assert call(base, "/api/capabilities") == (200, {"launch": True, "propose": True, "edit_map": None})
    assert call(served[0], "/api/capabilities") == (200, {"launch": False, "propose": False, "edit_map": None})


def test_an_event_is_promoted_with_the_causes_ticked_and_the_note_appears_in_the_vault(promoter):
    base, vault, near_miss = promoter
    body = {"run": "canon", "entity": near_miss, "causes": ["pin:v:bryn-ardent:born"]}
    status, job = call(base, "/api/propose", body, launch_headers(base))
    assert status == 202 and job["job"] == "propose"
    done = wait_for(base, job)
    assert done["state"] == "done", done["output"]
    note = vault / done["variant"]
    assert note.is_file() and done["variant"].startswith("_proposed/event/")
    text = note.read_text(encoding="utf-8")
    assert "canon: proposed" in text and "causes: [pin:v:bryn-ardent:born]" in text


@pytest.mark.parametrize("body", [
    {"run": "canon", "entity": "x 1"}, {"run": "canon", "entity": "../x"}, {"run": "nope", "entity": "x1"},
    {"run": "canon", "entity": "x1", "causes": "pin:a"}, {"run": "canon", "entity": "x1", "causes": ["pin a"]},
    {"run": "canon", "entity": "x1", "causes": ["x"] * 30}, {"run": "canon", "entity": "x1", "extra": 1},
])
def test_a_promotion_request_is_validated(promoter, body):
    base, _, _ = promoter
    assert call(base, "/api/propose", body, launch_headers(base))[0] == 400


def test_no_promotion_without_a_vault(recipes_launcher):
    base, _ = recipes_launcher
    assert call(base, "/api/propose", {"run": "tiny", "entity": "x1"}, launch_headers(base))[0] == 400


def test_a_cause_ticked_twice_is_kept_once(promoter):
    base, vault, near_miss = promoter
    body = {"run": "canon", "entity": near_miss, "causes": ["pin:v:bryn-ardent:born", "pin:v:bryn-ardent:born"]}
    status, job = call(base, "/api/propose", body, launch_headers(base))
    assert status == 202 and job["causes"] == ["pin:v:bryn-ardent:born"]
    wait_for(base, job)


def test_a_ripple_is_authored_on_a_run_and_comes_back_as_a_diffed_branch(launcher, served):
    _, runs = served
    body = {"run": "tiny", "kind": "doom", "target": "t:Ashford-00", "date": "1X 3", "name": "tiny-authored"}
    status, job = call(launcher, "/api/ripple", body, launch_headers(launcher))
    assert status == 202 and job["job"] == "ripple"
    done = wait_for(launcher, job)
    assert done["state"] == "done" and done["variant"] == "tiny-authored", done["output"]
    assert (runs / "tiny-authored" / "analysis" / "divergence.json").is_file()


@pytest.mark.parametrize("body", [
    {"run": "tiny", "kind": "smite", "target": "t:a", "date": "1X 3"},
    {"run": "../tiny", "kind": "doom", "target": "t:a", "date": "1X 3"},
    {"run": "tiny", "kind": "doom", "target": "t:a b", "date": "1X 3"},
    {"run": "tiny", "kind": "doom", "target": "t:a", "date": "1X 3; rm"},
    {"run": "tiny", "kind": "doom", "target": "t:a", "date": "1X 3", "params": [1]},
    {"run": "tiny", "kind": "doom", "target": "t:a", "date": "1X 3", "name": "../x"},
    {"run": "tiny", "kind": "doom", "target": "t:a", "date": "1X 3", "extra": 1},
    {"run": "tiny", "kind": "doom", "target": "t:a"},
])
def test_a_ripple_request_is_validated(launcher, body):
    assert call(launcher, "/api/ripple", body, launch_headers(launcher))[0] == 400
