"""The MCP server (S12 spec §5, #118): Claude queries runs and the vault, and fetches packs, over stdio."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from renasci.mcp import Server

VAULT = Path(__file__).resolve().parents[1] / "fixtures" / "vault_people"


@pytest.fixture(scope="module")
def server(m4):
    return Server(runs=m4.parent, vault=VAULT)


def rpc(server, method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return server.handle(msg)


def tool(server, name, **args):
    out = rpc(server, "tools/call", {"name": name, "arguments": args})
    result = out["result"]
    data = json.loads(result["content"][0]["text"])
    return result.get("isError", False), data


def test_the_handshake(server):
    out = rpc(server, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}})
    r = out["result"]
    assert out["id"] == 1 and r["protocolVersion"] == "2025-06-18"
    assert r["capabilities"] == {"tools": {"listChanged": False}} and r["serverInfo"]["name"] == "renasci"
    old = rpc(server, "initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"]
    assert old in ("2024-11-05", "2025-03-26", "2025-06-18")
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None  # (never answered)
    assert rpc(server, "ping")["result"] == {}


def test_errors(server):
    assert rpc(server, "nope")["error"]["code"] == -32601
    assert rpc(server, "tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602
    assert rpc(server, "tools/call", {"name": "event"})["error"]["code"] == -32602  # (no arguments)


def test_tools_are_listed_with_their_schemas(server):
    tools = rpc(server, "tools/list")["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"runs", "run_summary", "events", "event", "person", "stories", "claims", "pack", "fetch",
            "vault_search", "vault_note"} <= names
    assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in tools)


def test_runs_and_a_summary(server, m4run):
    err, runs = tool(server, "runs")
    assert not err and "m4" in [r["name"] for r in runs["runs"]]
    err, s = tool(server, "run_summary", run="m4")
    assert not err and s["world"] == "fourth_age" and s["sagas"] and s["ripples"][0]["kind"] == "inject"


def test_events_are_filtered_and_paged(server, m4run):
    fail = next(e for e in m4run.events if e["type"] == "ward.failure")
    err, page = tool(server, "events", run="m4", type="ward.", limit=10)
    assert not err and fail["id"] in [e["id"] for e in page["events"]]
    err, a = tool(server, "events", run="m4", limit=5)
    err, b = tool(server, "events", run="m4", limit=5, cursor=a["next"])
    assert len(a["events"]) == 5 and a["events"][-1]["id"] != b["events"][0]["id"]
    err, one = tool(server, "event", run="m4", id=fail["id"])
    assert not err and one["text"] and any(c["type"] == "ward.sabotage" for c in one["causes"])
    assert one["consequences"]


def test_a_person_with_beliefs_and_their_origins(server, m4run):
    holder = next(p for p in m4run.holders() if m4run.ents[p]["fields"].get("beliefs"))
    err, p = tool(server, "person", run="m4", id=holder)
    assert not err and p["name"] and p["beliefs"] and all("origin" in b for b in p["beliefs"])


def test_stories_and_claims(server):
    err, s = tool(server, "stories", run="m4")
    assert not err and s["sagas"] and s["arcs"]
    err, c = tool(server, "claims", run="m4")
    assert not err and any(t["about_type"] == "ward.failure" for t in c["topics"])


def test_a_pack_comes_back_as_a_summary_and_a_handle_to_fetch(server, m4run):
    fail = next(e for e in m4run.events if e["type"] == "ward.failure")
    err, p = tool(server, "pack", run="m4", subject="event", id=fail["id"], pov="v:lux-oescus")
    assert not err and p["handle"] and p["counts"]["events"] > 0 and "events" not in p
    err, page = tool(server, "fetch", handle=p["handle"], section="events", cursor=0)
    assert not err and page["items"] and page["total"] == p["counts"]["events"]
    err, nope = tool(server, "fetch", handle="nope", section="events")
    assert err


def test_the_vault(server):
    err, found = tool(server, "vault_search", query="")
    assert not err and found["notes"]
    first = found["notes"][0]
    err, note = tool(server, "vault_note", note=first["title"])
    assert not err and note["title"] == first["title"] and "text" in note


@pytest.mark.parametrize("name, args", [("run_summary", {"run": "../m4"}), ("run_summary", {"run": "C:/x"}),
                                        ("run_summary", {"run": "nope"}), ("event", {"run": "m4", "id": "x nope"}),
                                        ("vault_note", {"note": "../../secret"})])
def test_bad_arguments_are_tool_errors_not_crashes(server, name, args):
    err, data = tool(server, name, **args)
    assert err and data["error"]


def test_over_stdio_nothing_but_json_lines(m4):
    lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
             {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "runs", "arguments": {}}}]
    done = subprocess.run([sys.executable, "-m", "renasci.cli", "mcp", "--runs", str(m4.parent)],
                          input="\n".join(json.dumps(m) for m in lines) + "\nnot json\n", capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    out = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    assert [m.get("id") for m in out] == [1, 2, 3, None]  # (the notification unanswered; bad JSON: an error)
    assert out[-1]["error"]["code"] == -32700


@pytest.mark.parametrize("name, args", [("vault_search", {"query": 5}), ("events", {"run": "m4", "limit": "x"}),
                                        ("events", {"run": "m4", "from": "soon"})])
def test_arguments_of_the_wrong_type_are_refused_as_params(server, name, args):
    assert rpc(server, "tools/call", {"name": name, "arguments": args})["error"]["code"] == -32602


def test_a_tool_without_arguments_needs_no_arguments_field(server):
    assert not rpc(server, "tools/call", {"name": "runs"})["result"]["isError"]
    assert rpc(server, "initialize", ["x"])["error"]["code"] == -32602


def test_a_negative_cursor_is_refused(server):
    err, _ = tool(server, "events", run="m4", cursor=-1)
    assert err


def test_the_stream_survives_bad_bytes_surrogates_and_nan(m4):
    lines = [b"\xff\xfe{}\n", b'{"jsonrpc":"2.0","id":"\ud800","method":"ping"}\n',
             b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n', b'{"jsonrpc":"2.0","id":9,"method":"ping"}\n']
    done = subprocess.run([sys.executable, "-m", "renasci.cli", "mcp", "--runs", str(m4.parent)],
                          input=b"".join(lines), capture_output=True, timeout=120)
    out = [json.loads(line) for line in done.stdout.decode("ascii").splitlines() if line.strip()]
    assert done.returncode == 0 and [m.get("id") for m in out] == [None, "\ud800", None, 9]
    assert out[0]["error"]["code"] == -32700 and out[2]["error"]["code"] == -32700
