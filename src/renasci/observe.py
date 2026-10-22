"""`renasci observe`: serve the Observatory and a runs folder, read-only, on localhost.

A static file server and nothing more. It uses only the standard library and never writes.

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
"""

from __future__ import annotations

import json
import mimetypes
import shutil
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


class Handler(BaseHTTPRequestHandler):
    server_version = "renasci-observe"
    protocol_version = "HTTP/1.1"  # keep-alive: the Observatory asks for many small files

    def __init__(self, *args, app: Path, runs: Path, **kw):
        self.app, self.runs = app.resolve(), runs.resolve()
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
        rel = safe_relative(path.lstrip("/")) if path != "/" else None
        if path != "/" and rel is None:
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain", head_only)
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

    do_POST = do_PUT = do_DELETE = do_PATCH = _refuse  # noqa: N815


def make_server(app, runs, port: int = 8765) -> ThreadingHTTPServer:
    handler = partial(Handler, app=Path(app), runs=Path(runs))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(app, runs, port: int = 8765, open_browser: bool = True) -> None:
    server = make_server(app, runs, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Observatory at {url}  (runs from {Path(runs).resolve()}; Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
