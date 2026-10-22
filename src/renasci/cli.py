"""The `renasci` command line.

    renasci run <recipe.toml> [--out runs]
    renasci replay <run-folder> --recipe <recipe.toml> [--from "1X 40"] [--out runs]
    renasci diff <baseline-run> <variant-run>      (exit 3 if anything is unexplained)
    renasci inspect <run-folder> (--event <id> | --entity <id>)

`run` writes a run folder with a checkpoint every N years. `replay` forks a run at the latest
checkpoint before the first changed ripple (or `--from`), restores, and continues with the new
recipe. `diff` explains every difference between two runs (no unexplained divergence).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.io.checkpoint import load_checkpoint, save_checkpoint
from renasci.io.recipe import load_recipe, parse_recipe
from renasci.io.runfolder import TABLES, RunFolder, cut, flush
from renasci.worlds import get_world


def _checkpoint_dates(start: Date, end: Date, every: int) -> list[Date]:
    return [Date(start.age, y, 0) for y in range(start.year + every, end.year + 1, every)]


def _finish(engine, folder: RunFolder, recipe, after: Date | None = None) -> None:
    """Run to the end, cutting a segment and saving a checkpoint at each checkpoint date."""
    (folder.path / "checkpoints").mkdir(exist_ok=True)
    for at in _checkpoint_dates(engine.start, recipe.end, recipe.checkpoint_every_years):
        if after is not None and at <= after:
            continue
        engine.run_before(at)
        index = cut(engine, folder, at)
        save_checkpoint(folder.path / "checkpoints" / f"{at.age}-{at.year}-{at.day}.json.gz",
                        engine.checkpoint(at=at, segments=index + 1))
    engine.run(until=recipe.end)
    flush(engine, folder)
    folder.close_segment()
    save_checkpoint(folder.path / "state.json.gz", engine.store.to_json())
    folder.manifest["meta"]["state_hash"] = engine.state_hash()
    folder.manifest["meta"]["complete"] = True  # written last: readers refuse folders without it
    folder.save_manifest()


def _open_complete(path) -> RunFolder:
    rf = RunFolder.open(path)
    if rf.manifest["meta"].get("complete") is not True:
        raise ValueError(f"{path} is not a complete run (it may have failed); remove it and run again")
    return rf


def cmd_run(args) -> int:
    recipe = load_recipe(args.recipe)
    world = get_world(recipe.world)
    engine = world.new_engine(recipe.seed, ripples=recipe.ripples, **recipe.params)
    folder = RunFolder.create(Path(args.out) / recipe.name, {"recipe": recipe.raw, "complete": False})
    _finish(engine, folder, recipe)
    print(f"run {recipe.name}: {folder.manifest['segments']} segments, state {folder.manifest['meta']['state_hash']}")
    return 0


def cmd_replay(args) -> int:
    base = _open_complete(args.run)
    old = parse_recipe(base.manifest["meta"]["recipe"])
    new = load_recipe(args.recipe)
    world = get_world(new.world)

    def without_name_and_ripples(raw):
        return {k: ({kk: vv for kk, vv in v.items() if kk != "name"} if k == "run" else v)
                for k, v in raw.items() if k != "ripple"}

    if without_name_and_ripples(old.raw) != without_name_and_ripples(new.raw):
        raise ValueError("a replay may only change ripples (and the run name); for anything else, `renasci run`")
    if args.from_:
        target = world.calendar.parse(args.from_)
    else:
        def key(r):
            return json.dumps(r.to_json(), sort_keys=True)

        before, after = {key(r) for r in old.ripples}, {key(r) for r in new.ripples}
        changed = [r.date for r in new.ripples if key(r) not in before]  # added or changed: new date
        changed += [r.date for r in old.ripples if key(r) not in after]  # removed or changed: old date
        target = min(changed) if changed else new.end
    marks = [m for m in base.manifest["marks"] if Date.from_json(m["before"]) <= target]
    if not marks:
        raise ValueError(f"no checkpoint at or before {world.calendar.format(target)}; use `renasci run`")
    mark = marks[-1]
    at = Date.from_json(mark["before"])
    cp = load_checkpoint(base.path / "checkpoints" / f"{at.age}-{at.year}-{at.day}.json.gz")
    engine = world.restore(cp, new.seed, ripples=new.ripples, **new.params)
    folder = RunFolder.fork(base.path, Path(args.out) / new.name, keep=mark["segment"] + 1,
                            meta={"recipe": new.raw, "complete": False,
                                  "replayed_from": {"run": base.path.name, "at": mark["before"]}})
    _finish(engine, folder, new, after=at)
    print(f"replayed {new.name} from {base.path.name} at {world.calendar.format(at)}")
    return 0


def _load(path: Path) -> tuple[dict, dict, dict]:
    rf = _open_complete(path)
    tables = {t: list(rf.read(t)) for t in TABLES}
    state = json.loads(gzip.decompress((path / "state.json.gz").read_bytes()))
    ripples = {r["id"]: json.dumps(r, sort_keys=True) for r in rf.manifest["meta"]["recipe"].get("ripple", [])}
    return tables, state, ripples


def cmd_diff(args) -> int:
    a_path, b_path = Path(args.a), Path(args.b)
    a, sa, ra = _load(a_path)
    b, sb, rb = _load(b_path)
    ripples = sorted({i for i in set(ra) | set(rb) if ra.get(i) != rb.get(i)})
    report = analyse(a, b, sa, sb, ripples=ripples)
    (b_path / "analysis").mkdir(exist_ok=True)
    (b_path / "analysis" / "divergence.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"{report['divergent_events']} of {report['events']} events diverge; "
          f"{report['unexplained_events']} unexplained events, {report['unexplained_entities']} unexplained "
          f"entities, {report['unexplained_cells']} unexplained cells")
    for e in report["unexplained"]["events"][:5]:
        print(f"  unexplained: {e['type']} {e['date']} {e['roles']}")
    clean = report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0
    return 0 if clean else 3  # 3, not 2: argparse uses 2 for usage errors


def cmd_inspect(args) -> int:
    path = Path(args.run)
    rf = _open_complete(path)
    if args.event:
        event = next((e for e in rf.read("events") if e["id"] == args.event), None)
        if event is None:
            raise ValueError(f"no event {args.event}")
        print(json.dumps(event, indent=1))
        causes = [c for c in rf.read("causes") if c["event"] == args.event]
        for c in causes:
            print(f"caused by {c['kind']} {c['ref']}")
    if args.entity:
        state = json.loads(gzip.decompress((path / "state.json.gz").read_bytes()))
        record = next((e for e in state["entities"] if e["id"] == args.entity), None)
        print(json.dumps(record, indent=1) if record else f"{args.entity}: not in the final state")
        ids = {p["event"] for p in rf.read("participants") if p["entity"] == args.entity}
        print("events:")
        for e in rf.read("events"):
            if e["id"] in ids:
                print(f"  {e['date']} {e['type']} {e['id']}")
        print("state changes:")
        for d in rf.read("state_deltas"):
            if d["entity"] == args.entity:
                print(f"  {d['date']} {d['field']}: {json.dumps(d['old'])} -> {json.dumps(d['new'])}  ({d['event']})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="renasci", description="The Renascitur History Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="run a recipe into a run folder")
    p.add_argument("recipe")
    p.add_argument("--out", default="runs")
    p = sub.add_parser("replay", help="replay a run from a checkpoint with a (changed) recipe")
    p.add_argument("run")
    p.add_argument("--recipe", required=True)
    p.add_argument("--from", dest="from_", default=None)
    p.add_argument("--out", default="runs")
    p = sub.add_parser("diff", help="explain the differences between two runs")
    p.add_argument("a")
    p.add_argument("b")
    p = sub.add_parser("inspect", help="show an event or an entity")
    p.add_argument("run")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--event")
    target.add_argument("--entity")
    args = parser.parse_args(argv)
    try:
        return {"run": cmd_run, "replay": cmd_replay, "diff": cmd_diff, "inspect": cmd_inspect}[args.command](args)
    except (ValueError, FileExistsError, FileNotFoundError) as err:
        print(f"renasci: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
