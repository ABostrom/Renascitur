"""`renasci observe`: a read-only static server for the Observatory and the runs folder."""

import json
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
    cal = Calendar.from_json(data["calendar"])
    for v in data["vectors"]:
        d = Date.from_json(v["date"])
        assert cal.format(d, "year") == v["year"]
        assert cal.format(d, "season") == v["season"]
        assert cal.format(d, "day") == v["day"]
        assert cal.parse(v["day"]) == d
