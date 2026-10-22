"""Run folders: what a run leaves behind, as plain JSON Lines.

    runs/<name>/
      manifest.json
      <table>/seg-00000.jsonl.gz   closed segments (gzipped, deterministic bytes)
      <table>/seg-00003.jsonl      the open segment

Every line is one canonical JSON object. Segments are cut at checkpoints, so truncating a run for
a replay is just deleting the segments after the checkpoint. Readable with jq, grep, or any
language; the Observatory reads the same files directly.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from renasci import __version__
from renasci.core.canon import canonical

FORMAT = 1
TABLES = ("events", "causes", "participants", "state_deltas", "bulk_deltas", "reads", "hinges")


def _seg(index: int) -> str:
    return f"seg-{index:05d}"


class RunFolder:
    def __init__(self, path: Path, manifest: dict):
        self.path = Path(path)
        self.manifest = manifest

    # ------------------------------------------------------------ lifecycle

    @classmethod
    def create(cls, path, meta: dict) -> RunFolder:
        path = Path(path)
        if path.exists() and any(path.iterdir()):
            raise FileExistsError(f"run folder {path} already exists")
        path.mkdir(parents=True, exist_ok=True)
        for t in TABLES:
            (path / t).mkdir()
        rf = cls(path, {"format": FORMAT, "engine": __version__, "tables": {t: 1 for t in TABLES},
                        "segments": 0, "meta": json.loads(canonical(meta))})
        rf.save_manifest()
        return rf

    @classmethod
    def open(cls, path) -> RunFolder:
        path = Path(path)
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format") != FORMAT:
            raise ValueError(f"run folder format {manifest.get('format')!r} is not {FORMAT}")
        return cls(path, manifest)

    def save_manifest(self) -> None:
        (self.path / "manifest.json").write_text(canonical(self.manifest) + "\n", encoding="utf-8", newline="\n")

    # ------------------------------------------------------------ writing

    def _open_file(self, table: str) -> Path:
        return self.path / table / f"{_seg(self.manifest['segments'])}.jsonl"

    def write(self, table: str, rows) -> None:
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}; tables are {TABLES}")
        lines = "".join(canonical(r) + "\n" for r in rows)  # validates every row first
        if lines:
            with self._open_file(table).open("a", encoding="utf-8", newline="\n") as f:
                f.write(lines)

    def close_segment(self) -> int:
        """Gzip the open segment of every table and start the next. Returns the closed index."""
        index = self.manifest["segments"]
        for t in TABLES:
            raw = self.path / t / f"{_seg(index)}.jsonl"
            data = raw.read_bytes() if raw.exists() else b""
            (self.path / t / f"{_seg(index)}.jsonl.gz").write_bytes(gzip.compress(data, mtime=0))
            if raw.exists():
                raw.unlink()
        self.manifest["segments"] = index + 1
        self.save_manifest()
        return index

    def truncate(self, keep: int) -> None:
        """Keep the first `keep` closed segments; delete everything after, including the open one."""
        if not 0 <= keep <= self.manifest["segments"]:
            raise ValueError(f"cannot keep {keep} of {self.manifest['segments']} segments")
        for t in TABLES:
            for f in sorted((self.path / t).iterdir()):
                if int(f.name[4:9]) >= keep:
                    f.unlink()
        self.manifest["segments"] = keep
        self.save_manifest()

    # ------------------------------------------------------------ reading

    def read(self, table: str):
        """Every row of `table`, in order: closed segments, then the open one."""
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}")
        for i in range(self.manifest["segments"] + 1):
            gz = self.path / table / f"{_seg(i)}.jsonl.gz"
            raw = self.path / table / f"{_seg(i)}.jsonl"
            if gz.exists():
                text = gzip.decompress(gz.read_bytes()).decode("utf-8")
            elif raw.exists():
                text = raw.read_text(encoding="utf-8")
            else:
                continue
            for line in text.splitlines():
                if line:
                    yield json.loads(line)


def flush(engine, folder: RunFolder) -> None:
    """Move the engine's pending history (events, deltas, reads, hinges) into the run folder."""
    for table, rows in engine.drain().items():
        folder.write(table, rows)
