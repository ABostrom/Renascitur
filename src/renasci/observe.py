"""`renasci observe`: serve the Observatory and a runs folder, read-only, on localhost.

A static file server and nothing more. It uses only the standard library, binds to 127.0.0.1,
answers GET (and HEAD) only, and never writes:

- `/runs/index.json`  the run folders, each with its manifest
- `/runs/<path>`      files inside the runs folder (never outside it)
- anything else       the built Observatory; unknown paths fall back to index.html (SPA routing)
"""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".gz": "application/gzip",
         ".jsonl": "application/x-ndjson"}


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

    def __init__(self, *args, app: Path, runs: Path, **kw):
        self.app, self.runs = app.resolve(), runs.resolve()
        super().__init__(*args, **kw)

    def log_message(self, format, *args):  # noqa: A002  (quiet)
        pass

    def _send(self, status: int, body: bytes, kind: str, head_only: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _file(self, path: Path, head_only: bool) -> None:
        kind = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(HTTPStatus.OK, path.read_bytes(), kind, head_only)

    @staticmethod
    def _inside(root: Path, rel: str) -> Path | None:
        target = (root / rel).resolve()
        return target if target.is_relative_to(root) and target.is_file() else None

    def _get(self, head_only: bool) -> None:
        path = unquote(urlsplit(self.path).path)
        if ".." in Path(path).parts:
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain", head_only)
        if path == "/runs/index.json":
            body = json.dumps(list_runs(self.runs)).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        if path.startswith("/runs/"):
            target = self._inside(self.runs, path[len("/runs/"):])
            if target is None:
                return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain", head_only)
            return self._file(target, head_only)
        target = self._inside(self.app, path.lstrip("/")) if path != "/" else None
        if target is None:
            index = self.app / "index.html"
            if not index.is_file():
                return self._send(HTTPStatus.NOT_FOUND, b"the Observatory is not built", "text/plain", head_only)
            target = index
        self._file(target, head_only)

    def do_GET(self):  # noqa: N802
        self._get(head_only=False)

    def do_HEAD(self):  # noqa: N802
        self._get(head_only=True)

    def _refuse(self):
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, b"read-only", "text/plain")

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
