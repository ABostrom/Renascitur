"""Run folders: what a run leaves behind, as plain JSON Lines.

    runs/<name>/
      manifest.json
      <table>/seg-00000.jsonl.gz   closed segments (gzipped, byte-identical on every platform)
      <table>/seg-00003.jsonl      the open segment

Every line is one canonical JSON object. Segments are cut at checkpoints (`cut`), so truncating a
run for a replay is just deleting the segments after the checkpoint, and a fork copies a prefix.
Readable with jq, grep, or any language; the Observatory reads the same files directly.

Crash safety: files are replaced atomically, and the manifest is updated last when a segment
closes. `open` repairs a folder left by an interrupted close.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
from pathlib import Path

from renasci import __version__
from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.determinism import versions

FORMAT = 1
TABLES = ("events", "causes", "participants", "entities", "state_deltas", "bulk_deltas", "reads",
          "hinges", "dropped")
_SEGMENT = re.compile(r"^seg-(\d{5})\.jsonl(\.gz)?$")


def _seg(index: int) -> str:
    return f"seg-{index:05d}"


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _gzip(data: bytes) -> bytes:
    out = bytearray(gzip.compress(data, compresslevel=9, mtime=0))
    out[9] = 0xFF  # OS byte "unknown": otherwise it differs between Windows, Linux and Python versions
    return bytes(out)


class RunFolder:
    def __init__(self, path: Path, manifest: dict):
        self.path = Path(path)
        self.manifest = manifest

    # ------------------------------------------------------------ lifecycle

    @classmethod
    def create(cls, path, meta: dict, parent: dict | None = None) -> RunFolder:
        path = Path(path)
        if path.exists() and any(path.iterdir()):
            raise FileExistsError(f"run folder {path} already exists")
        path.mkdir(parents=True, exist_ok=True)
        for t in TABLES:
            (path / t).mkdir()
        rf = cls(path, {"format": FORMAT, "engine": __version__, "versions": versions(),
                        "tables": {t: 1 for t in TABLES},
                        "segments": 0, "marks": [], "parent": parent, "meta": json.loads(canonical(meta))})
        rf.save_manifest()
        return rf

    @classmethod
    def open(cls, path) -> RunFolder:
        path = Path(path)
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format") != FORMAT:
            raise ValueError(f"run folder format {manifest.get('format')!r} is not {FORMAT}")
        rf = cls(path, manifest)
        rf._recover()
        return rf

    @classmethod
    def fork(cls, source, path, keep: int, meta: dict) -> RunFolder:
        """A new run folder that starts with the first `keep` closed segments of `source`."""
        src = cls.open(source)
        if not 0 <= keep <= src.manifest["segments"]:
            raise ValueError(f"cannot fork {keep} of {src.manifest['segments']} segments")
        child = cls.create(path, meta, parent={"run": src.path.name, "segments": keep})
        for t in TABLES:
            for i in range(keep):
                shutil.copyfile(src.path / t / f"{_seg(i)}.jsonl.gz", child.path / t / f"{_seg(i)}.jsonl.gz")
        child.manifest["segments"] = keep
        child.manifest["marks"] = [m for m in src.manifest["marks"] if m["segment"] < keep]
        child.save_manifest()
        return child

    def save_manifest(self) -> None:
        _atomic_write(self.path / "manifest.json", (canonical(self.manifest) + "\n").encode("utf-8"))

    def _segment_files(self, table: str):
        for f in sorted((self.path / table).iterdir()):
            m = _SEGMENT.match(f.name)
            if m:
                yield int(m.group(1)), bool(m.group(2)), f

    def _recover(self) -> None:
        """Repair what an interrupted `close_segment` left behind."""
        n = self.manifest["segments"]
        for t in TABLES:
            for index, gz, f in list(self._segment_files(t)):
                if index < n and not gz and (f.parent / f"{_seg(index)}.jsonl.gz").exists():
                    f.unlink()  # closed and recorded; the raw copy is a leftover
                elif index == n and gz:
                    f.unlink()  # gzipped but never recorded; the raw file is still the truth

    # ------------------------------------------------------------ writing

    def write(self, table: str, rows) -> None:
        self.write_many({table: rows})

    def write_many(self, tables: dict[str, list]) -> None:
        """Append rows to several tables. Every row is serialised before anything is written."""
        for t in tables:
            if t not in TABLES:
                raise ValueError(f"unknown table {t!r}; tables are {TABLES}")
        texts = {t: "".join(canonical(r) + "\n" for r in rows) for t, rows in tables.items()}
        for t, text in texts.items():
            if text:
                with (self.path / t / f"{_seg(self.manifest['segments'])}.jsonl").open(
                        "a", encoding="utf-8", newline="\n") as f:
                    f.write(text)

    def close_segment(self) -> int:
        """Gzip the open segment of every table and start the next. Returns the closed index."""
        index = self.manifest["segments"]
        raws = [self.path / t / f"{_seg(index)}.jsonl" for t in TABLES]
        for raw in raws:
            data = raw.read_bytes() if raw.exists() else b""
            _atomic_write(raw.with_name(raw.name + ".gz"), _gzip(data))
        self.manifest["segments"] = index + 1
        self.save_manifest()  # the commit point
        for raw in raws:
            if raw.exists():
                raw.unlink()
        return index

    def truncate(self, keep: int) -> None:
        """Keep the first `keep` closed segments; delete everything after, including the open one."""
        if not 0 <= keep <= self.manifest["segments"]:
            raise ValueError(f"cannot keep {keep} of {self.manifest['segments']} segments")
        self.manifest["segments"] = keep
        self.manifest["marks"] = [m for m in self.manifest["marks"] if m["segment"] < keep]
        self.save_manifest()
        for t in TABLES:
            for index, _, f in list(self._segment_files(t)):
                if index >= keep:
                    f.unlink()

    # ------------------------------------------------------------ reading

    def read(self, table: str):
        """Every row of `table`, in order: closed segments, then the open one."""
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}")
        for i in range(self.manifest["segments"] + 1):
            gz = self.path / table / f"{_seg(i)}.jsonl.gz"
            raw = self.path / table / f"{_seg(i)}.jsonl"
            if gz.exists() and raw.exists():
                raise ValueError(f"{table}/{_seg(i)} exists both gzipped and raw; open() repairs this")
            if gz.exists():
                text = gzip.decompress(gz.read_bytes()).decode("utf-8")
            elif raw.exists():
                text = raw.read_text(encoding="utf-8")
            else:
                continue
            for line in text.split("\n"):  # not splitlines: U+2028 etc. are legal inside JSON strings
                if line:
                    yield json.loads(line)


def flush(engine, folder: RunFolder) -> None:
    """Move the engine's pending history into the run folder. Nothing is lost if writing fails."""
    folder.write_many(engine.pending())
    engine.clear_pending()


def cut(engine, folder: RunFolder, at: Date) -> int:
    """Flush, close the segment, and mark it as ending just before `at` (a checkpoint date)."""
    flush(engine, folder)
    index = folder.close_segment()
    folder.manifest["marks"].append({"segment": index, "before": at.to_json()})
    folder.save_manifest()
    return index
