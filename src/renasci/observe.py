"""`renasci observe`: serve the Observatory and a runs folder, read-only, on localhost.

A static file server and nothing more. It uses only the standard library and never writes, unless it
is started with `--allow-launch`: then the Observatory may launch latch-point what-ifs (#101), each
`renasci latch <run> --launch N` in a child process that writes a new run folder.

- `/runs/index.json`  the run folders, each with its manifest
- `/runs/<dir>/`      a directory inside the runs folder, as a JSON list of file names
- `/runs/<path>`      a file inside the runs folder (never outside it)
- anything else       the built Observatory; unknown paths fall back to index.html (SPA routing)

Safety, because any web page in the browser can send requests to localhost:
- **Paths are validated as strings before any file-system call.** Backslashes, drive letters, colons,
  NUL bytes, absolute paths and `..` are refused outright. On Windows, merely resolving
  `\\\\host\\share` makes the OS open an SMB connection, which can leak the user's NTLM hash.
- **Host check:** only requests addressed to `127.0.0.1:<port>` or `localhost:<port>` are answered,
  so a DNS-rebinding page can't read runs.
- It binds to 127.0.0.1 and answers only GET and HEAD.
- **The launcher** (off by default) answers one POST, `/api/launch`, and only from the Observatory
  itself: the `Origin` must be this server, the body JSON, and a custom `X-Renasci-Launch` header
  present (a cross-site page can't send one without a preflight, which this server never answers). The
  body is validated field by field; the child gets an argument list, never a shell. One job at a time.
  `GET /api/capabilities` says whether launching is on; `GET /api/jobs` lists the jobs.
"""

from __future__ import annotations

import itertools
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".gz": "application/gzip",
         ".jsonl": "application/x-ndjson"}


def safe_relative(rel: str) -> str | None:
    """`rel` if it is a plain relative POSIX path inside a folder, else None. Never touches the disk."""
    if not rel or any(c in rel for c in ("\\", ":", "\x00")) or rel.startswith("/"):
        return None
    parts = PurePosixPath(rel).parts
    if not parts or any(p in ("..", ".") for p in parts) or PurePosixPath(rel).is_absolute():
        return None
    return "/".join(parts)


def list_runs(runs: Path) -> list[dict]:
    out = []
    if runs.is_dir():
        for folder in sorted(p for p in runs.iterdir() if p.is_dir()):
            manifest = folder / "manifest.json"
            if manifest.is_file():
                try:
                    out.append({"name": folder.name, "manifest": json.loads(manifest.read_text(encoding="utf-8"))})
                except (OSError, ValueError):
                    continue
    return out


LAUNCH_KEYS = {"run", "rank", "kind", "date", "until"}
CALENDAR_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .'-]{0,39}$")  # "1K 26", "1K 26 m6 d1", "A.E. 3"; never "-..."
MAX_BODY = 4096
JOB_SECONDS = 3600  # a what-if that takes longer than an hour is stopped


class Jobs:
    """What-if launches: one child process at a time, its output kept for the Observatory to show."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: list[dict] = []
        self.ids = itertools.count(1)

    def busy(self) -> bool:
        return any(j["state"] == "running" for j in self.jobs)

    def start(self, argv: list[str], about: dict) -> dict | None:
        with self.lock:
            if self.busy():
                return None
            job = {"id": next(self.ids), "state": "running", "returncode": None, "output": "", "variant": None, **about}
            self.jobs.append(job)
        threading.Thread(target=self._run, args=(job, argv), daemon=True).start()
        return dict(job)

    def _run(self, job: dict, argv: list[str]) -> None:
        try:
            done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=JOB_SECONDS)
            out, code = (done.stdout + done.stderr)[-4000:], done.returncode
        except subprocess.TimeoutExpired:
            out, code = f"stopped after {JOB_SECONDS} s", -1
        except OSError as err:
            out, code = str(err), -1
        found = re.search(r"^latch: launched (\S+)$", out, re.MULTILINE)
        with self.lock:  # exit 3: the what-if ran, but its diff found unexplained divergence
            job.update(output=out, returncode=code, variant=found.group(1) if found else None,
                       state="done" if code in (0, 3) and found else "failed",
                       warning="unexplained divergence" if code == 3 else None)

    def list(self) -> list[dict]:
        with self.lock:
            return [dict(j) for j in self.jobs]


class Handler(BaseHTTPRequestHandler):
    server_version = "renasci-observe"
    protocol_version = "HTTP/1.1"  # keep-alive: the Observatory asks for many small files

    def __init__(self, *args, app: Path, runs: Path, jobs: Jobs | None = None, **kw):
        self.app, self.runs, self.jobs = app.resolve(), runs.resolve(), jobs
        super().__init__(*args, **kw)

    def log_message(self, format, *args):  # noqa: A002  (quiet)
        pass

    def _headers(self, status: int, kind: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def _send(self, status: int, body: bytes, kind: str, head_only: bool) -> None:
        self._headers(status, kind, len(body))
        if not head_only:
            self.wfile.write(body)

    def _file(self, path: Path, head_only: bool) -> None:
        kind = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._headers(HTTPStatus.OK, kind, path.stat().st_size)
        if not head_only:
            with path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)

    @staticmethod
    def _inside(root: Path, rel: str) -> Path | None:
        """A path inside `root` for a *validated* relative path (symlinks and junctions can't escape)."""
        target = (root / rel).resolve()
        return target if target.is_relative_to(root) else None

    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _get(self, head_only: bool) -> None:
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, b"wrong host", "text/plain", head_only)
        path = unquote(urlsplit(self.path).path)
        if path == "/api/capabilities":
            body = json.dumps({"launch": self.jobs is not None}).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        if path == "/api/jobs":
            body = json.dumps(self.jobs.list() if self.jobs else []).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        if path == "/runs/index.json":
            body = json.dumps(list_runs(self.runs)).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        if path.startswith("/runs/"):
            rel = path[len("/runs/"):]
            is_dir = rel.endswith("/")
            rel = safe_relative(rel.rstrip("/"))
            target = self._inside(self.runs, rel) if rel is not None else None
            if target is None:
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain", head_only)
            if is_dir and target.is_dir():
                names = sorted(p.name for p in target.iterdir() if p.is_file())
                return self._send(HTTPStatus.OK, json.dumps(names).encode("utf-8"), "application/json", head_only)
            if not target.is_file():
                return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain", head_only)
            return self._file(target, head_only)
        # App routes can contain anything (entity ids like "t:Ashford"). A path that isn't a safe file
        # path is never looked up on disk: it is an app route, so it gets index.html.
        rel = safe_relative(path.lstrip("/")) if path != "/" else None
        target = self._inside(self.app, rel) if rel else None
        if target is None or not target.is_file():
            target = self.app / "index.html"
            if not target.is_file():
                return self._send(HTTPStatus.NOT_FOUND, b"the Observatory is not built", "text/plain", head_only)
        self._file(target, head_only)

    def do_GET(self):  # noqa: N802
        self._get(head_only=False)

    def do_HEAD(self):  # noqa: N802
        self._get(head_only=True)

    def _refuse(self):
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, b"read-only", "text/plain", head_only=False)

    do_PUT = do_DELETE = do_PATCH = _refuse  # noqa: N815

    def do_POST(self):  # noqa: N802
        if self.jobs is None or unquote(urlsplit(self.path).path) != "/api/launch":
            return self._refuse()
        port = self.server.server_address[1]
        if not self._host_ok() or self.headers.get("Origin") not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}") \
                or self.headers.get("X-Renasci-Launch") != "1" \
                or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain", head_only=False)
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:  # (unread bytes would be taken for the next request: close instead)
            self.close_connection = True
            return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > MAX_BODY else HTTPStatus.LENGTH_REQUIRED,
                              b"a launch is a small JSON body", "text/plain", head_only=False)
        try:
            body = json.loads(self.rfile.read(length) or b"null")
            argv, about = self._launch_argv(body)
        except (ValueError, TypeError) as err:
            return self._send(HTTPStatus.BAD_REQUEST, str(err).encode("utf-8"), "text/plain", head_only=False)
        job = self.jobs.start(argv, about)
        if job is None:
            return self._send(HTTPStatus.CONFLICT, b"a what-if is already running", "text/plain", head_only=False)
        self._send(HTTPStatus.ACCEPTED, json.dumps(job).encode("utf-8"), "application/json", head_only=False)

    def _launch_argv(self, body) -> tuple[list[str], dict]:
        """The child's argument list for a validated launch request (ValueError if anything is off)."""
        if not isinstance(body, dict) or set(body) - LAUNCH_KEYS or not {"run", "rank"} <= set(body):
            raise ValueError(f"a launch is {{run, rank}} and optionally kind, date, until; got {body!r}")
        run = body["run"]
        if not isinstance(run, str) or safe_relative(run) != run or "/" in run:
            raise ValueError("run must be a run folder's name")
        folder = self._inside(self.runs, run)
        if folder is None or not (folder / "manifest.json").is_file():
            raise ValueError(f"no run {run!r}")
        rank = body["rank"]
        if type(rank) is not int or not 1 <= rank <= 10_000:
            raise ValueError("rank must be a positive int")
        argv = [sys.executable, "-m", "renasci.cli", "latch", str(folder), "--launch", str(rank), "--out", str(self.runs),
                "--top", "0"]
        if "kind" in body:
            if body["kind"] not in ("protect", "doom"):
                raise ValueError("kind is protect or doom")
            argv += ["--kind", body["kind"]]
        for key in ("date", "until"):
            if key in body:
                if not isinstance(body[key], str) or not CALENDAR_TEXT.match(body[key]):
                    raise ValueError(f"{key} must be a date like '1K 26' or '1K 26 m6 d1'")
                argv += [f"--{key}", body[key]]
        return argv, {"run": run, "rank": rank, "kind": body.get("kind"), "date": body.get("date"),
                      "until": body.get("until")}


def make_server(app, runs, port: int = 8765, launch: bool = False) -> ThreadingHTTPServer:
    handler = partial(Handler, app=Path(app), runs=Path(runs), jobs=Jobs() if launch else None)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(app, runs, port: int = 8765, open_browser: bool = True, launch: bool = False) -> None:
    server = make_server(app, runs, port, launch=launch)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Observatory at {url}  (runs from {Path(runs).resolve()}"
          f"{'; what-ifs can be launched from it' if launch else ''}; Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
