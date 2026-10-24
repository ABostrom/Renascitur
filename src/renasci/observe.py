"""`renasci observe`: serve the Observatory and a runs folder, read-only, on localhost.

A static file server and nothing more. It uses only the standard library and never writes, unless it
is started with `--allow-launch`: then the Observatory may launch, each in a child process that writes
a new run folder:
- latch-point what-ifs (#101): `renasci latch <run> --launch N`;
- runs and replays from the recipes folder (`--recipes`, default `recipes`; #57): `renasci run <recipe>`
  and `renasci replay <run> --recipe <recipe>`. Only `.toml` files directly in that folder, by name;
- proposals, only with an explicit `--vault` (#105): `renasci vault propose <run> <entity> <vault> --write
  [--cause kind:ref...]`, a `canon: proposed` note in the vault's `_proposed/`, never over an edit;
- the story layer (#111): a context pack, a chronicle or a campaign brief of a run's arc, saga, person or
  event (`renasci pack|chronicle|brief`, into the run's `analysis/`), and a canon check of pasted prose (the
  text is kept as `analysis/checks/<digest>.md` and `renasci check-prose` judges it). Each job reports the
  file it wrote, as a path inside the runs folder.

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
- **The launcher** (off by default) answers POSTs to `/api/launch`, `/api/run`, `/api/replay`,
  `/api/ripple` (a ripple authored on a run: replayed as a branch and diffed, #110), `/api/propose`,
  `/api/pack`, `/api/chronicle`, `/api/brief` and `/api/check` (its own cap: 256 KB of prose), and only
  from the Observatory
  itself: the `Origin` must be this server, the body JSON, and a custom `X-Renasci-Launch` header
  present (a cross-site page can't send one without a preflight, which this server never answers). The
  body is validated field by field; the child gets an argument list, never a shell. One job at a time.
  `GET /api/capabilities` says whether launching is on; `GET /api/jobs` lists the jobs (each with its
  `job`: latch, run or replay; and the run folder it made as `variant`); `GET /api/recipes` lists the recipes.
"""

from __future__ import annotations

import itertools
import json
import mimetypes
import os
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
         ".jsonl": "application/x-ndjson", ".md": "text/markdown; charset=utf-8"}


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
RIPPLE_KEYS = {"run", "kind", "target", "date", "params", "name"}
CALENDAR_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .'-]{0,39}$")  # "1K 26", "1K 26 m6 d1", "A.E. 3"; never "-..."
MAX_BODY = 4096
CHECK_TEXT = 256 * 1024  # (prose to check: the launcher's 4 KB is too little, and argv can't carry text)
CHECK_MAX_BODY = 6 * CHECK_TEXT + 4096  # (JSON escapes grow a text: the text's own cap is checked once parsed)
SUBJECTS = ("arc", "saga", "person", "event", "topic")
DOCUMENTS = ("pack", "chronicle", "brief", "check")  # (jobs that write a file into a run, not a new run)
MAP_MAX_BODY = 16 * 1024 * 1024  # (an edited map: geography, grid and layout)
JOB_SECONDS = 3600  # a what-if that takes longer than an hour is stopped


# What each kind of job prints when it has made its run folder (the folder's name in group 1).
MADE = {"latch": r"^latch: launched (\S+)$", "run": r"^run (\S+): ", "replay": r"^replayed (\S+) from ",
        "propose": r"^wrote (.+?) \(canon: proposed", "ripple": r"^ripple: launched (\S+)$",
        **{d: rf"^{d}: .* -> (.+)$" for d in DOCUMENTS}}
ENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_.-]{0,127}")  # a run's entity or event id
CAUSE = re.compile(r"[a-z]+:[A-Za-z0-9:_.-]{1,160}")  # kind:ref, as an event records it


def list_recipes(folder: Path | None) -> list[dict]:
    """The `.toml` recipes directly in `folder`: what each would run, or why it can't be read."""
    from renasci.io.recipe import load_recipe

    if folder is None or not folder.is_dir():
        return []
    root = folder.resolve()
    out = []
    for path in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix == ".toml"):
        if path.resolve().parent != root:
            continue  # (a link out of the folder: never read, as `_recipe` never runs it)
        row = {"file": path.name, "name": None, "world": None, "end": None, "ripples": 0, "error": None}
        try:
            r = load_recipe(path)
            row.update(name=r.name, world=r.world, end=str(r.raw["run"]["end"]), ripples=len(r.ripples))
        except Exception as err:  # (any failure to read is shown, not raised: it's someone's draft)
            row["error"] = str(err) or type(err).__name__
        out.append(row)
    return out


class Jobs:
    """What-if launches: one child process at a time, its output kept for the Observatory to show."""

    def __init__(self, root: Path | None = None):
        self.root = root.resolve() if root is not None else None  # (the runs folder: files are named inside it)
        self.lock = threading.Lock()
        self.jobs: list[dict] = []
        self.ids = itertools.count(1)

    def busy(self) -> bool:
        return any(j["state"] == "running" for j in self.jobs)

    def start(self, argv: list[str], about: dict) -> dict | None:
        with self.lock:
            if self.busy():
                return None
            job = {"id": next(self.ids), "state": "running", "returncode": None, "output": "", "variant": None,
                   "job": "latch", **about}
            self.jobs.append(job)
        threading.Thread(target=self._run, args=(job, argv), daemon=True).start()
        return dict(job)

    def _run(self, job: dict, argv: list[str]) -> None:
        try:
            done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=JOB_SECONDS, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            out, code = (done.stdout + done.stderr)[-4000:], done.returncode
        except subprocess.TimeoutExpired:
            out, code = f"stopped after {JOB_SECONDS} s", -1
        except OSError as err:
            out, code = str(err), -1
        found = re.search(MADE[job["job"]], out, re.MULTILINE)
        ok = code in (0, 3) if job["job"] in ("latch", "ripple") else code == 0  # (3: the diff found something)
        file = self._within(found.group(1).strip()) if found and job["job"] in DOCUMENTS else None
        if job["job"] in DOCUMENTS and not file:
            found = None
        with self.lock:  # exit 3 (latch): the what-if ran, but its diff found unexplained divergence
            if job["job"] in DOCUMENTS:
                job["file"] = file
            job.update(output=out, returncode=code,
                       variant=None if job["job"] in DOCUMENTS else found.group(1) if found else None,
                       state="done" if ok and found else "failed",
                       warning="unexplained divergence" if job["job"] in ("latch", "ripple") and code == 3 else None)

    def _within(self, written: str) -> str | None:
        """A file a job wrote, as a POSIX path inside the runs folder (else None)."""
        try:
            return Path(written).resolve().relative_to(self.root).as_posix() if self.root else None
        except (ValueError, OSError):
            return None

    def list(self) -> list[dict]:
        with self.lock:
            return [dict(j) for j in self.jobs]


class Handler(BaseHTTPRequestHandler):
    server_version = "renasci-observe"
    protocol_version = "HTTP/1.1"  # keep-alive: the Observatory asks for many small files

    def __init__(self, *args, app: Path, runs: Path, jobs: Jobs | None = None, recipes: Path | None = None,
                 vault: Path | None = None, map_files=None, **kw):
        self.map_files = map_files  # (renasci.mapedit.MapFiles with --edit-map; else None: no editor)
        self.vault = vault.resolve() if vault is not None and vault.is_dir() else None
        self.recipes = recipes.resolve() if recipes is not None else None
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
            body = json.dumps({"launch": self.jobs is not None,
                               "propose": self.jobs is not None and self.vault is not None,
                               "edit_map": self.map_files.world if self.map_files else None}).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        if path == "/api/recipes":
            if self.jobs is None:
                return self._send(HTTPStatus.NOT_FOUND, b"the launcher is off", "text/plain", head_only=head_only)
            body = json.dumps(list_recipes(self.recipes)).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only=head_only)
        if path in ("/api/map", "/api/map/base.png"):
            return self._map_get(path, head_only)
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

    do_DELETE = do_PATCH = _refuse  # noqa: N815

    def _map_get(self, path: str, head_only: bool) -> None:
        if self.map_files is None:
            return self._send(HTTPStatus.NOT_FOUND, b"no map is being edited (--edit-map)", "text/plain", head_only)
        if path == "/api/map":
            body = json.dumps(self.map_files.load()).encode("utf-8")
            return self._send(HTTPStatus.OK, body, "application/json", head_only)
        image = self.map_files.base()
        if image is None:
            return self._send(HTTPStatus.NOT_FOUND, b"no base image: run renasci map import", "text/plain", head_only)
        self.send_response(HTTPStatus.OK)  # (the private map: never cached, never embeddable by another site)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(image.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head_only:
            with image.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)

    def _trusted_json(self, limit: int):
        """The request's JSON body, if the request comes from the Observatory itself (Host, Origin, the
        custom header, the type) and says its length within `limit`; else an error has been sent: None."""
        port = self.server.server_address[1]
        if not self._host_ok() or self.headers.get("Origin") not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}") \
                or self.headers.get("X-Renasci-Launch") != "1" \
                or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain", head_only=False)
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        if not 0 <= length <= limit:  # (unread bytes would be taken for the next request: close instead)
            self.close_connection = True
            self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > limit else HTTPStatus.LENGTH_REQUIRED,
                       b"body too large, or no length", "text/plain", head_only=False)
            return None
        try:
            return json.loads(self.rfile.read(length) or b"null")
        except (ValueError, RecursionError):
            self._send(HTTPStatus.BAD_REQUEST, b"not JSON", "text/plain", head_only=False)
            return None

    def _map_write(self, route: str) -> None:
        """POST /api/map/check (findings for an unsaved state) and PUT /api/map (save it)."""
        from renasci import mapedit

        body = self._trusted_json(MAP_MAX_BODY)
        if body is None:
            return
        bad = mapedit.shape(body)
        if bad:
            return self._send(HTTPStatus.BAD_REQUEST, bad.encode("utf-8"), "text/plain", head_only=False)
        try:
            if route == "/api/map/check":
                out = json.dumps(mapedit.check(body)).encode("utf-8")
                return self._send(HTTPStatus.OK, out, "application/json", head_only=False)
            findings, changed = mapedit.save(self.map_files, body)
        except PermissionError as err:  # (Windows: a file open elsewhere; nothing was changed)
            return self._send(HTTPStatus.CONFLICT, f"couldn't write: {err}".encode("utf-8"), "text/plain", False)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as err:  # (a state the checks choke on)
            return self._send(HTTPStatus.BAD_REQUEST, f"a malformed map: {err!r}".encode("utf-8"), "text/plain", False)
        if changed or not any(f["severity"] == "error" for f in findings):
            out = json.dumps({"changed": changed, "findings": findings}).encode("utf-8")
            return self._send(HTTPStatus.OK, out, "application/json", head_only=False)
        return self._send(HTTPStatus.BAD_REQUEST, json.dumps(findings).encode("utf-8"), "application/json", False)

    def do_PUT(self):  # noqa: N802
        route = unquote(urlsplit(self.path).path)
        if self.map_files is None or route != "/api/map":
            return self._refuse()
        self._map_write(route)

    def do_POST(self):  # noqa: N802
        route = unquote(urlsplit(self.path).path)
        if route == "/api/map/check" and self.map_files is not None:
            return self._map_write(route)
        builders = {"/api/launch": self._launch_argv, "/api/run": self._run_argv, "/api/replay": self._replay_argv,
                    "/api/propose": self._propose_argv, "/api/ripple": self._ripple_argv,
                    "/api/pack": partial(self._story_argv, "pack"), "/api/chronicle": partial(self._story_argv, "chronicle"),
                    "/api/brief": partial(self._story_argv, "brief")}
        if self.jobs is not None and route == "/api/check":
            body = self._trusted_json(CHECK_MAX_BODY)
            if body is None:
                return
            try:
                argv, about = self._check_argv(body)
            except (ValueError, TypeError, OSError) as err:
                return self._send(HTTPStatus.BAD_REQUEST, str(err).encode("utf-8"), "text/plain", head_only=False)
            return self._start(argv, about)
        if self.jobs is None or route not in builders:
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
            argv, about = builders[route](body)
        except (ValueError, TypeError, RecursionError) as err:  # (RecursionError: a deeply nested body)
            return self._send(HTTPStatus.BAD_REQUEST, str(err).encode("utf-8"), "text/plain", head_only=False)
        self._start(argv, about)

    def _start(self, argv, about) -> None:
        job = self.jobs.start(argv, about)
        if job is None:
            return self._send(HTTPStatus.CONFLICT, b"a job is already running", "text/plain", head_only=False)
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


    def _recipe(self, name) -> Path:
        """A recipe in the recipes folder, by file name only."""
        if not isinstance(name, str) or safe_relative(name) != name or "/" in name or not name.endswith(".toml"):
            raise ValueError("recipe must be the name of a .toml file in the recipes folder")
        path = self._inside(self.recipes, name) if self.recipes is not None else None
        if path is None or not path.is_file():
            raise ValueError(f"no recipe {name!r}")
        return path

    def _run_folder(self, run) -> Path:
        if not isinstance(run, str) or safe_relative(run) != run or "/" in run:
            raise ValueError("run must be a run folder's name")
        folder = self._inside(self.runs, run)
        if folder is None or not (folder / "manifest.json").is_file():
            raise ValueError(f"no run {run!r}")
        return folder

    def _run_argv(self, body) -> tuple[list[str], dict]:
        """`renasci run <recipe>` into the runs folder."""
        if not isinstance(body, dict) or set(body) != {"recipe"}:
            raise ValueError(f"a run is {{recipe}}; got {body!r}")
        recipe = self._recipe(body["recipe"])
        return ([sys.executable, "-m", "renasci.cli", "run", str(recipe), "--out", str(self.runs)],
                {"job": "run", "recipe": recipe.name})

    def _propose_argv(self, body) -> tuple[list[str], dict]:
        """`renasci vault propose <run> <entity> <vault> --write [--cause ...]`: a proposed note."""
        if not isinstance(body, dict) or not {"run", "entity"} <= set(body) or set(body) - {"run", "entity", "causes"}:
            raise ValueError(f"a proposal is {{run, entity}} and optionally causes; got {body!r}")
        if self.vault is None:
            raise ValueError("this server has no vault to write to (start it with --vault)")
        folder = self._run_folder(body["run"])
        entity, causes = body["entity"], body.get("causes", [])
        if isinstance(causes, list):
            causes = list(dict.fromkeys(causes)) if all(isinstance(c, str) for c in causes) else causes
        if not isinstance(entity, str) or not ENTITY.fullmatch(entity):
            raise ValueError("entity must be a run's entity or event id")
        if not isinstance(causes, list) or len(causes) > 20 \
                or not all(isinstance(c, str) and CAUSE.fullmatch(c) for c in causes):
            raise ValueError("causes must be at most 20 of the event's own causes, each kind:ref")
        argv = [sys.executable, "-m", "renasci.cli", "vault", "propose", str(folder), entity, str(self.vault), "--write"]
        for c in causes:
            argv += ["--cause", c]
        return argv, {"job": "propose", "run": body["run"], "entity": entity, "causes": causes}

    @staticmethod
    def _pov(pov) -> str:
        if pov != "omniscient" and (not isinstance(pov, str) or not ENTITY.fullmatch(pov)):
            raise ValueError("pov is omniscient, or a person, house or settlement id")
        return pov

    def _story_argv(self, cmd: str, body) -> tuple[list[str], dict]:
        """`renasci pack|chronicle|brief <run> --<subject> <id> [--pov <pov>]` (#111): a story document."""
        keys = {"run", "subject", "id"} | ({"pov"} if cmd != "brief" else set())
        if not isinstance(body, dict) or set(body) - keys or not {"run", "subject", "id"} <= set(body):
            raise ValueError(f"a {cmd} is {{{', '.join(sorted(keys))}}}; got {body!r}")
        folder = self._run_folder(body["run"])
        if body["subject"] not in SUBJECTS:
            raise ValueError(f"subject is one of {', '.join(SUBJECTS)}")
        if not isinstance(body["id"], str) or not ENTITY.fullmatch(body["id"]):
            raise ValueError("id must be an entity or event id")
        argv = [sys.executable, "-m", "renasci.cli", cmd, str(folder), f"--{body['subject']}", body["id"]]
        pov = None
        if cmd != "brief":
            pov = self._pov(body.get("pov", "omniscient"))
            argv += ["--pov", pov]
        return argv, {"job": cmd, "run": body["run"], "subject": body["subject"], "of": body["id"], "pov": pov}

    def _check_argv(self, body) -> tuple[list[str], dict]:
        """A canon check of pasted prose (#111): the text is kept as `<run>/analysis/checks/<digest>.md`, and
        `renasci check-prose <run> <that file> --pov <pov>` judges it."""
        from renasci.core.canon import digest_text

        if not isinstance(body, dict) or set(body) - {"run", "text", "pov"} or not {"run", "text"} <= set(body):
            raise ValueError(f"a check is {{run, text}} and optionally pov; got {body!r}")
        folder = self._run_folder(body["run"])
        text, pov = body["text"], self._pov(body.get("pov", "omniscient"))
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be the prose to check")
        if len(text.encode("utf-8")) > CHECK_TEXT:
            raise ValueError(f"the text is over {CHECK_TEXT // 1024} KB")
        kept = folder / "analysis" / "checks" / f"{digest_text(text, 16)}.md"
        if not kept.exists():  # (named by its digest: the same text is the same file; never rewritten under a job)
            kept.parent.mkdir(parents=True, exist_ok=True)
            tmp = kept.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(text, encoding="utf-8", newline="\n")
            os.replace(tmp, kept)
        return ([sys.executable, "-m", "renasci.cli", "check-prose", str(folder), str(kept), "--pov", pov],
                {"job": "check", "run": body["run"], "pov": pov, "text": kept.name})

    def _replay_argv(self, body) -> tuple[list[str], dict]:
        """`renasci replay <run> --recipe <recipe>` into the runs folder (the recipe changes only ripples)."""
        if not isinstance(body, dict) or set(body) != {"run", "recipe"}:
            raise ValueError(f"a replay is {{run, recipe}}; got {body!r}")
        folder, recipe = self._run_folder(body["run"]), self._recipe(body["recipe"])
        return ([sys.executable, "-m", "renasci.cli", "replay", str(folder), "--recipe", str(recipe), "--out",
                 str(self.runs)], {"job": "replay", "run": body["run"], "recipe": recipe.name})

    def _ripple_argv(self, body) -> tuple[list[str], dict]:
        """`renasci ripple <run> --kind --target --date [--params] [--name]` (#110): a ripple authored in the
        Observatory, replayed as a branch of the run and diffed against it."""
        from renasci.core.ripples import KINDS
        from renasci.io.recipe import check_run_name

        if not isinstance(body, dict) or set(body) - RIPPLE_KEYS or not {"run", "kind", "target", "date"} <= set(body):
            raise ValueError(f"a ripple is {{run, kind, target, date}} and optionally params, name; got {body!r}")
        folder = self._run_folder(body["run"])
        if body["kind"] not in KINDS:
            raise ValueError(f"kind is one of {', '.join(KINDS)}")
        if not isinstance(body["target"], str) or not ENTITY.fullmatch(body["target"]):
            raise ValueError("target must be an entity id")
        if not isinstance(body["date"], str) or not CALENDAR_TEXT.fullmatch(body["date"]):
            raise ValueError("date must be a date like '1K 26' or '1K 26 m6 d1'")
        argv = [sys.executable, "-m", "renasci.cli", "ripple", str(folder), "--kind", body["kind"], "--target",
                body["target"], "--date", body["date"], "--out", str(self.runs)]
        if "params" in body:
            if not isinstance(body["params"], dict):
                raise ValueError("params must be an object")
            argv += ["--params", json.dumps(body["params"])]
        if "name" in body:
            argv += ["--name", check_run_name(body["name"])]
        return argv, {"job": "ripple", "run": body["run"], "kind": body["kind"], "target": body["target"],
                      "date": body["date"]}


def make_server(app, runs, port: int = 8765, launch: bool = False, recipes=None, vault=None, edit_map=None,
                maps=None) -> ThreadingHTTPServer:
    map_files = None
    if edit_map is not None:  # (the map editor: the geography file and its world's private layers)
        from renasci.mapedit import MapFiles

        edit_map = Path(edit_map)
        map_files = MapFiles(edit_map, Path(maps) / edit_map.stem / "private")
    handler = partial(Handler, app=Path(app), runs=Path(runs), jobs=Jobs(Path(runs)) if launch else None,
                      recipes=Path(recipes) if recipes is not None else None,
                      vault=Path(vault) if vault is not None else None, map_files=map_files)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(app, runs, port: int = 8765, open_browser: bool = True, launch: bool = False, recipes=None,
          vault=None, edit_map=None, maps=None) -> None:
    server = make_server(app, runs, port, launch=launch, recipes=recipes, vault=vault, edit_map=edit_map, maps=maps)
    if edit_map is not None:
        print(f"Editing the map {Path(edit_map).resolve()} at /edit (its private layers in "
              f"{Path(maps) / Path(edit_map).stem / 'private'})")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    if launch and vault is not None:
        print(f"Proposed notes may be written into {Path(vault).resolve()}/_proposed (never over an edit)")
    print(f"Observatory at {url}  (runs from {Path(runs).resolve()}"
          f"{'; runs, replays and what-ifs can be launched from it' if launch else ''}; Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
