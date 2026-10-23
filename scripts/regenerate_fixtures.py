"""Regenerate the Observatory's committed fixture runs. Run on purpose, then review the diff:

    uv run python scripts/regenerate_fixtures.py
"""

import gzip
import json
import shutil
from pathlib import Path

from renasci.cli import main

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "observatory" / "fixtures" / "runs"
RECIPE = """
[run]
name = "{name}"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 6"
checkpoint_every_years = 2
{run_extra}

[world]
people_per_village = 6
{extra}
"""
RIPPLE = """
[[ripple]]
id = "r1"
kind = "protect"
date = "1X 3"
target = "t:Ashford-00"
params = { until = [1, 6, 359] }

[[ripple]]
id = "r2"
kind = "doom"
date = "1X 4"
target = "t:Brook-02"
"""

KIN = """
[run]
name = "kin"
engine = "0.1.0"
seed = 1234
world = "kin"
end = "1K 40"
checkpoint_every_years = 10

[world]
people_per_settlement = 10
traits = { wits = "stature", charm = "stature", temper = "stature" }
"""


def recipe(name, extra="", full_reads=True):
    """base and protected keep every read (the Observatory shows them); the buggy pair keeps digests."""
    path = OUT.parent / f"{name}.toml"
    run_extra = "full_reads = true" if full_reads else ""
    path.write_text(RECIPE.format(name=name, extra=extra, run_extra=run_extra), encoding="utf-8", newline="\n")
    return str(path)


def main_() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    assert main(["run", recipe("base"), "--out", str(OUT)]) == 0
    assert main(["replay", str(OUT / "base"), "--recipe", recipe("protected", RIPPLE), "--out", str(OUT)]) == 0
    main(["diff", str(OUT / "base"), str(OUT / "protected")])
    # A negative control: a world with a planted coupling bug, so its diff has unexplained divergence.
    assert main(["run", recipe("buggy", "buggy = true", full_reads=False), "--out", str(OUT)]) == 0
    assert main(["replay", str(OUT / "buggy"), "--recipe", recipe("buggy-protected", "buggy = true\n" + RIPPLE,
                                                                      full_reads=False), "--out", str(OUT)]) == 0
    assert main(["diff", str(OUT / "buggy"), str(OUT / "buggy-protected")]) == 3, "the planted bug went unnoticed"

    # An interrupted folder: the open segment ends in a partial line, a stale .tmp is left behind, and a
    # close of the open segment was interrupted after gzipping one table but before the manifest.
    broken = OUT / "interrupted"
    shutil.copytree(OUT / "base", broken)
    events = broken / "events"
    n = max(int(p.name[4:9]) for p in events.glob("seg-*.jsonl.gz")) + 1  # the next (open) segment
    (events / f"seg-{n:05d}.jsonl").write_text('{"id":"xopen1","type":"toy.open"}\n{"id":"xpart', encoding="utf-8",
                                               newline="\n")
    (events / f"seg-{n:05d}.jsonl.gz").write_bytes(gzip.compress(b'{"id":"xnever"}\n'))
    (events / f"seg-{n:05d}.jsonl.gz.tmp").write_bytes(b"garbage")
    manifest = json.loads((broken / "manifest.json").read_text(encoding="utf-8"))
    manifest["meta"]["complete"] = False  # the run never finished
    text = json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    (broken / "manifest.json").write_text(text, encoding="utf-8", newline="\n")
    # A kin run with stories and latch points (the Stories pages): traits mapped, so plots and sagas emerge.
    kin = OUT.parent / "kin.toml"
    kin.write_text(KIN, encoding="utf-8", newline="\n")
    assert main(["run", str(kin), "--out", str(OUT)]) == 0
    assert main(["stories", str(OUT / "kin")]) == 0
    assert main(["latch", str(OUT / "kin")]) == 0
    assert main(["latch", str(OUT / "kin"), "--launch", "1", "--out", str(OUT)]) == 0  # a what-if: kin-latch1
    for f in (OUT.parent).glob("*.toml"):
        f.unlink()
    print(f"fixtures written to {OUT}")


if __name__ == "__main__":
    main_()
