---
title: S1 Engine foundation: sub-project spec
status: draft r3 (review folded in; JSON everywhere, no pickle, per Aaron 2026-10-22)
parent: notes/specs/2026-10-21-history-engine-design.md
tickets: "#22 (this spec), epic #2, build tickets #36–#52 (#114 is M3)"
---

# S1 Engine foundation

S1 is the deterministic core that everything else stands on. It contains no Renascita content.
It runs a **toy ruleset** that is just rich enough to test the things that are hard to get right:

- determinism
- replay from checkpoints
- locality (no unexplained divergence)
- pins

**Guiding choices (Aaron, 2026-10-22):**
- **JSON is the structure everywhere.** It's readable from any tool, and any future Rust rewrite can
  read it.
- **No pickle.**
- **A small stack.** No Parquet, DuckDB or Arrow: run folders are plain JSON Lines.
- **Clarity beats speed.** A later Rust rewrite is the performance plan, so S1 picks the simple,
  inspectable option whenever there's a choice.

This spec refines master spec §4–§5 and §10 for S1 only. Where the two disagree, this one wins for S1,
and the master spec should be updated to match.

> **Defaults pending #16.** These are marked ⟨#16⟩ below:
> - the base grain is a season
> - run folders live in `runs/` (gitignored)
> - the toy world is villages with a marriage market and a shared granary
>
> If Aaron's answers differ, this spec changes before the plan is written.

## 1. Goals and exit

**Done when** (from master §6, made testable):

1. **Determinism.** The same recipe produces the same canonical event hash. This holds across
   repeated runs, across processes, and across different `PYTHONHASHSEED` values.
2. **Replay equivalence.** For at least 8 checkpoint positions, replaying from the checkpoint gives
   the same event hash and the same final state hash as the continuous run.
3. **No unexplained divergence, and the test has teeth.** A ripple run of the toy world differs from
   its baseline only in events *and final entity state* reachable from the ripple. Reachability goes
   through recorded causes, participation, state deltas and **actual reads** (§3.15). The test
   asserts three things:
   - the unexplained count is zero
   - the valley the ripple never touches is byte-identical between the two runs
   - a **negative control** fails: a deliberately injected coupling bug (a global counter, or a
     list-order pick) must produce unexplained > 0
4. **Toy pins.** Toy pins are honoured, classified out of scope, or logged as violated, and canon
   strain is recorded. Re-running a recipe with a pin promoted from the same run gives an identical
   event hash and zero strain. That requires satisfied pins to be pure observers (§3.9).
5. **Benchmark baseline.** `renasci bench` records years/second, events/second and run-folder MB
   in `bench/history.csv`.

**Not in S1:**

- Renascita content, the vault bridge (S2) and genomes (S3)
- the Observatory (S13 v0 reads S1's run folder)
- `renasci serve` (S13 / M0 or M1 ⟨#16⟩)
- tuning the temporal level of detail (M5), and **coarse-step execution**: S1 ships the LOD interface
  only (§3.8)
- **the rest of the ripple kinds, reshuffle, director steering and fork prefix sharing.** These are
  in M3 per master §8.2, and #114 carries them. S1 keeps their slots in the key and data formats
  so that adding them later is not a format change.

## 2. Layout

```
pyproject.toml                    # repo root; uv; Python 3.12; package "renasci"; console script "renasci"
src/renasci/
  core/
    calendar.py   # Date, Calendar, Span
    rng.py        # keyed Philox streams, canonical ticks, ordinals, reshuffle salts
    ids.py        # causal ids, event keys
    store.py      # entity store: records + columnar components, statuses, state deltas
    events.py     # EventType registry, Event, Cause, visibility, cause index
    scheduler.py  # activations, total order, cadences, batching
    systems.py    # System base, read/write sets, Ruleset, registry, ruleset switching
    context.py    # Ctx handed to systems: guarded store access, emit, schedule, rng, choose, chance
    choice.py     # rendezvous choose(), chance() with hinge recording
    lod.py        # resolution policy, focus windows, promote/demote interface
    pins.py       # Pin kinds, feasibility pass, casting skeleton, director, strain log
    ripples.py    # Ripple kinds, applier, disguise hook, reshuffle
    canon.py      # canonical serialisation, quantised floats, state and event hashes
    engine.py     # Engine: run loop, checkpoint cadence, run lifecycle
  io/
    runfolder.py  # JSON Lines writer/reader + manifest
    checkpoint.py # save/load, versioned
    recipe.py     # TOML recipe load/validate
  analysis/
    divergence.py # taint propagation, unexplained set, causal wave
    diff.py       # run-to-run diff summary
  toy/            # toy ruleset: villages, people, marriage, granary, toy pins and scenario
  cli.py          # renasci run | replay | diff | bench | inspect
src/renasci_legacy/   # old prototype, reference only (#36)
tests/                # pytest + hypothesis, mirrors src/renasci
recipes/              # committed run recipes (TOML)
runs/                 # gitignored run folders ⟨#16⟩
bench/history.csv     # committed benchmark history
```

**Dependencies:**

- runtime: `numpy` only. The standard library covers `json`, `gzip` and `tomllib` (for recipes).
- dev: `pytest` and `hypothesis`

The CLI uses `argparse`, so there's no extra dependency. `renasci/__init__.py` sets
`OPENBLAS_NUM_THREADS=1` and `MKL_NUM_THREADS=1` before NumPy is imported.

## 3. Components

### 3.1 Calendar (#37)

- `Date(age: int, year: int, day: int)` is frozen and totally ordered by tuple comparison. The day
  counts from 0 within the year.
- `Calendar` holds the age names and abbreviations (`"4A"`), `days_per_year` (placeholder: 360),
  `months` (12×30) and `seasons` (4×90). Formatting gives `"4A 37"`, `"4A 37 Spring"` and
  `"4A 37 m3 d12"`. Names are placeholders until lore exists.
- `canonical_tick(date) = (age, year, quarter)`, where quarter is `day * 4 // days_per_year`. These are fixed quarters, not the named seasons, so changing a setting's seasons never changes RNG keys.
- Arithmetic: `calendar.add(date, Span(years=…, days=…))`, plus `start_of_next(date, unit)` for month, season and year cadences. There are no month spans, because months have uneven lengths. It never crosses an age boundary
  implicitly: crossing one raises an error unless the ruleset handles the boundary.
- Property tests:
  - ordering is total and consistent with arithmetic
  - format and parse round-trip

### 3.2 Keyed RNG (#38)

- `key = blake2b(seed, system, entity_id, purpose, canonical_tick, occurrence, salt)` gives 128 bits,
  which become the Philox `key`. The draw index is the Philox counter.
- **occurrence:** the n-th stream opened for the same `(system, entity, purpose, canonical_tick)`.
  It's counted locally in an `OrdinalTable` scoped to exactly that tuple. It is never a global
  count. A table is discarded when its tick ends, and checkpointed while its tick is open.
- **Every stream has an owner key.** `entity=None` is forbidden. Batch and aggregate draws key by the
  place or aggregate id they act on (`ctx.rng(purpose, entity=place_id)`). Otherwise one extra
  stream opened early in a tick would shift every later draw in that tick.
- `ctx.rng(purpose, entity=None) -> Stream`. A stream has `random()`, `integers()`, `normal()`,
  `choice_index(weights)`, and `size=` array forms for aggregates. Systems get streams only via `rng.open(table, system, entity, purpose, tick)`, which counts the occurrence and builds the stream in one step. A stream lives inside one activation and never spans a checkpoint.
- **Reshuffle** (the format slot only in S1; behaviour in #114): a recipe entry
  `reshuffle(from_date, salt)` sets `salt` for every key whose canonical tick is ≥ `from_date`. In S1,
  `salt` is always empty.
- **Cost:** Philox setup is around a microsecond. That's accepted; speed isn't an S1 goal.
- Tests:
  - the same key gives the same draws
  - changing an unrelated key leaves the draws unchanged
  - occurrence counting is local
  - a reshuffle changes only keys at or after its date

### 3.3 Causal ids and entity store (#39)

- **EntityId:** `"e" + blake2b(creator_event_id, role, ordinal)[:16 hex]`. Entities cast from the
  vault get `"v:" + vault_id`. Toy cast entities get `"t:" + name`.
- **EventId:** `"x" + blake2b(event_key)[:16]`. The `event_key` is
  `(system, actor_id, purpose, date, occurrence, activation_id)`. Here, occurrence is the n-th event emitted for
  that `(actor_id, purpose)` within one activation, and `actor_id` must be given explicitly. Skipping one
  event therefore never renumbers the others. The same cause in the same place gives the same id in another
  run, and that is what makes runs comparable by id. Events and state deltas also carry their activation id,
  and follow-ups carry a `Cause("activation", parent)`.
- **Store:**
  - `records[kind][id]` holds dataclass records for notables.
  - `ComponentTable` holds columnar data for bulk state: NumPy columns plus a sorted id index.
  - Status is `active`, `dormant` or `dead`. Nothing is ever deleted.
- **Iteration is always in id order.** `store.ids(kind, status=…)` returns a sorted list, and the
  store never exposes sets or dict-ordered iteration.
- **Writes go through the context.** A write with no current event is an error. There are two forms:
  - **Record writes:** `ctx.set(entity, field, value)` appends a
    `StateDelta(date, entity, field, old, new, event_id)`. This is the "as of" record.
  - **Bulk writes:** `ctx.write_column(component, ids_or_mask, values)` appends **one**
    `BulkDelta(date, activation, component, id_range_or_mask_hash, values_hash)` per call. No per-element
    Python work and no values are stored. The aggregate *values* go to `timeseries` (master §5.4).
- **Bulk writes are taint sources.** An activation that reads a component row written by a tainted
  bulk delta is tainted. This keeps divergence analysis able to see aggregates without logging them
  element by element.

### 3.4 Typed events and causes (#41)

- **EventType** is registered with a name (`"toy.marriage"`), a version, role names with
  cardinality, payload fields with types, and a default visibility.
- **Event:**
  - `id`, `date`, `type`
  - `roles: dict[str, tuple[EntityId, ...]]` (sorted keys) and `place`
  - `causes: tuple[Cause, ...]` and `payload`
  - `source: Source(kind=system|action|pin|ripple|lod|scenario, ref)`
  - `visibility: public | secret` (secret means visible to its participants only)
- **Cause** is `Cause(kind, ref)`. Kinds: `event`, `pin`, `ripple`, `state` (a state delta), and
  `ambition`, `belief` and `drive`, which are reserved for S3, S6 and S7.
- **A cover story** is a separate public event with a `Cause(event, secret_id)`.
- **The cause index** is an in-memory DAG with both directions: `ancestors(id, depth)` and
  `descendants(id, depth)`. It's persisted as the `causes` table.
- `ctx.emit()` validates against the schema. Two hard rules: no dead participant in an active role,
  and the event date must be today.

### 3.5 Scheduler (#40)

- **Activation(date, priority, entity_id, purpose, system, payload, causes).**
- **Order:** `(date, priority, entity_id, purpose, system, activation_hash)`. The hash covers the
  payload in canonical form, so the order is total. Insertion order never matters, and identical
  activations are deduplicated as a bug.
- **Cadences** are declared per system: `daily`, `monthly`, `seasonal`, `yearly` or `on_demand`.
  - A **batch system** runs once per due date over its population, in id order.
  - **Follow-ups** go through `ctx.schedule(after=Span, purpose, payload)`. They carry the current
    event as a cause.
- The queue is a heap of key tuples, checkpointed as versioned, sorted JSON together with the last activation run. **A push must sort strictly after the last activation popped.** A same-day follow-up therefore needs a higher priority number, or the next day, which keeps the order independent of when things were scheduled.

### 3.6 Systems, read-sets, rulesets (#45)

- A **`System`** declares:
  - `name`, `cadence`, `priority`
  - `reads: frozenset[str]` (component or record fields) and `writes`
  - `event_types`
  - `run(ctx, due: list[EntityId] | None)`
- **`Ctx`** enforces the read and write sets when `strict=True`, which is the setting in tests. An
  undeclared read raises an error.
- **Actual reads are recorded.** Every activation records the `(entity, field)` pairs it actually
  read, as a compact per-activation set written to the `reads` table. Bulk reads record
  `(component, id range)`. Divergence analysis propagates from these, not from declared read-sets.
  Declared sets bound what may be read; recorded reads say what was read.
- **Read storage (#151).** A recipe run keeps **one digest per scope** (`digest`, `n`) by default.
  `[run] full_reads = true` keeps every read row, for analysis runs. Divergence analysis is exact
  with full reads on both sides. With a digest on either side, any difference in what a scope read
  taints it, which can hide a bug that changes only *which* fields are read. A difference in an
  activation's **unscoped** reads explains *every* event of that activation. So the exit test runs
  with full reads, and `renasci diff` reports the mode (`reads`: full, digest or mixed) and warns when
  it isn't full. A replay may switch `full_reads`, but exact analysis needs both runs recorded with
  it. The engine's Python API keeps full reads unless told otherwise.
- **`Ruleset`** is a name, a version, an ordered list of systems, parameters and a `ResolutionPolicy`.
  The engine switches ruleset at configured dates, which are always checkpoints (age boundaries).
- Systems never call each other. They communicate only through state, events and scheduled
  activations (master §4.3).

### 3.7 Rendezvous choice and hinges (#47)

- **`choose(candidates, key_parts)`** returns the candidate with the minimum
  `blake2b(key_parts, candidate_id)`. It also has a weighted form (`-log(u)/w`, the minimum wins)
  and a `k`-best form. Property test: removing a non-winning candidate never changes the winner.
- **Matching** (marriage and so on) is built from rendezvous proposals. Each seeker chooses; a
  contested target picks its suitor by rendezvous. Greedy list-order matching is banned.
- **`ctx.chance(p, purpose, hinge=Hinge(stakes, roles))`** draws `u` and returns `u < p`. If a hinge
  is given, it records `(event_id, date, purpose, p, u, margin=|u-p|, stakes, roles)` in `hinges`.

### 3.8 Temporal LOD interface (#46)

S1 delivers the **interface only**: the policy type, focus windows, and promote/demote. Every run in
S1 is `fine`. Coarse-step execution and its tuning come in M5. The rule is fixed now so the
formats don't change later: **a coarse step draws under its first canonical tick, plus a step
ordinal**.

- **`ResolutionPolicy(date) -> Resolution`**, either `fine` or `coarse(step=Span)`. **Focus windows**
  are date ranges forced to `fine`.
- **Coarse mode (declared now, executed from M5):** systems declare `coarse_ok` or
  `coarse_fallback`, and the engine rejects a policy that asks for coarse in S1.
- **Population LOD:**
  - `ctx.promote(aggregate, reason)` samples an individual, keyed by
    `(place, reason event, ordinal)`.
  - `ctx.demote(id)` sets the status to dormant.
  - Both emit `lod.*` events.
  - The conservation check is a hook that rulesets implement.

### 3.9 Pins, casting and director: skeletons (#48)

- **Pin(id, kind, subject, window, after, before, payload, source)**. The kinds are existence,
  event, ordering, lineage, succession and goal. **S1 implements existence, event and ordering.** The
  other three parse and run feasibility but are classified *unsupported* until S2 and S3.
- **Feasibility pass:**
  - build the ordering DAG and check for cycles
  - intersect windows
  - classify pins as `ok`, `out_of_scope` (outside the run window), `unsupported` or `infeasible`
- **Casting:** existence pins create or reserve entities with their pinned id before the first tick.
  The bindings go into `manifest.casting`.
- **Director:**
  - **guard:** fatal outcomes for pinned entities with unmet pins are converted by a
    ruleset-supplied `near_miss` hook.
  - **steer:** a **no-op hook** in S1. It comes in M3 (#114), and only with a ruleset-supplied
    *pure* odds function, never a look-ahead.
  - **force:** at the deadline, the ruleset's `force(pin)` constructs the event with a plausible cause.
  - **violated:** if forcing fails.
  - Every action is logged in the `strain` table.
- **Pure observation.** A pin that is being met naturally causes no draws, no state writes and no
  events. The director only *checks* until it has to guard or force. This is what makes the
  promotion no-op hold.
- **Casting a promoted entity** does not pre-create it. The pin binds to the entity's **natural
  creating event key** (from the run it was promoted from), and the director checks that the key
  occurs inside the window. The entity gets its usual causal id, so RNG keys and scheduler order are
  unchanged. Only entities with no natural origin (true canon, e.g. a vault id) are cast up front.

### 3.10 Ripples and reshuffle (#49, #114)

- **Ripple(id, kind, date, target, params, disguise)**. The kinds are protect, doom, favour, luck,
  inject, plant and structural.
- **The applier** turns a ripple into a `ripple.<kind>` event, which is secret and has
  `source=ripple`. A disguise event (public, ruleset-supplied, e.g. "a physician's care") has the
  ripple event as its cause.
- Protect and doom hook into the same guard path as pins. Favour and luck adjust the odds in
  `chance()` for the target, recorded as a cause.
- **#49 delivers** protect, doom and inject on the toy. **#114 (M3) delivers** structural, favour,
  luck, plant and reshuffle.
- **Replay start:** a ripple dated before the chosen checkpoint is rejected, and the CLI picks the
  latest checkpoint at or before the earliest ripple.

### 3.11 Run folder (#42)

```
runs/<name>/
  manifest.json      # recipe, engine/schema versions, ruleset versions, seed, casting, checkpoints, checks, hashes
  events/        seg-00000.jsonl …     # one canonical JSON object per line: id, date, type, place, source, visibility, roles, causes, payload
  participants/  seg-…                 # event_id, role, entity_id
  causes/        seg-…                 # event_id, cause_kind, cause_ref
  state_deltas/  seg-…                 # date, entity_id, field, old(json), new(json), event_id
  entities/      seg-…                 # id, kind, created_by, status changes
  hinges/ strain/ timeseries/ seg-…
  checkpoints/   <age>-<year>-<day>.json.gz
```

- **Segments** are cut at each checkpoint. That makes truncating on replay a file operation:
  delete the segments after the checkpoint's high-water mark.
- **Forks:** in S1, a replay copies the prefix segments into its own folder. The manifest still records
  `parent: {run, upto_segment}`, so prefix sharing by reference (M3) is not a format change.
- An extra table, **`reads/`**, holds the recorded actual reads per activation (§3.6).
- **Everything is canonical JSON Lines** (decided). Each table segment is a `.jsonl` file with one
  object per line, in emission order. Segments are gzipped (`.jsonl.gz`) once they are closed, and
  the reader handles both forms. You can grep it, `jq` it, or read it from any language.
- The reader API (`RunFolder.events(where…)`) is used by tests, diff and the CLI. The Observatory
  reads the same files with plain `fetch` and JSON parsing.

### 3.12 Checkpoints and replay (#43)

- **A checkpoint is a single canonical JSON document**, gzipped (`.json.gz`). There is no pickle. It
  contains:
  - a `header`: engine, checkpoint format, ruleset versions, recipe hash, date
  - the store: records, sorted by kind then id
  - NumPy columns as `{dtype, shape, data}`, where `data` is a plain JSON list
  - the scheduler queue, as a sorted list
  - the ordinal tables
  - the director state, fired ripples, the cause index (as sorted edges) and the run-folder high-water
    mark
- **Every engine type serialises explicitly** through `to_json()` / `from_json()`. Loading is
  schema-checked. A version mismatch is rejected with a clear message: "engine changed; replay from
  scenario". Because the format is language-neutral, a future Rust engine could load the same
  checkpoints.
- **Floats** are written with Python's shortest round-trip `repr`. That is exact for float64, and
  Rust's serde reads it back bit-identically. NaN and infinities are forbidden.
- **Position:** a checkpoint dated D is taken **before any activation dated D**. At that point every
  ordinal table for the previous tick is closed, and only the open tick's tables (if D is mid-tick)
  are saved.
- **`state_hash` is the blake2b of the checkpoint's canonical JSON**, excluding the header. There is
  one serialiser for both saving and hashing, so the two can't drift apart. Replay equivalence
  compares the event hash and the final `state_hash`.
- **Isolation:** the replay-equivalence test loads each checkpoint in a **fresh subprocess**, so no
  in-process state can leak between the two runs.
- **Cadence:** every N years (recipe; default 10), plus every ruleset switch.

### 3.13 Recipes and CLI (#44)

```toml
[run]
name = "toy-baseline"
engine = "0.1"          # must match, or the run refuses
seed = 1234
ruleset = "toy"
scenario = "toy.villages"
start = "1X 1"
end = "1X 300"
checkpoint_every_years = 10

[pins]
source = "toy"          # S2 adds: source = "vault", commit = "<sha>"

[[ripple]]
id = "r1"
kind = "protect"
date = "1X 120"
target = "t:Ada Millbrook"
disguise = "toy.healer"

[[reshuffle]]
from = "1X 200"
salt = "b"
```

CLI commands:

- `renasci run <recipe>`
- `renasci replay <run> --recipe <recipe> [--from <date>]`, which writes a fork run folder
- `renasci diff <runA> <runB>`, which prints the divergence report (§3.15)
- `renasci bench [--years N]`
- `renasci inspect <run> [--entity id | --event id]`, which prints causes and biography

### 3.14 Determinism hazards (#50)

- **Canonical serialisation:**
  - sorted keys
  - floats hashed by their **exact float64 bits** (`-0.0` normalised, NaN forbidden). There's no
    quantisation: the same machine and pinned versions are assumed, and rounding would hide real
    divergence and make hashes flip near boundaries
  - dates as tuples, sets forbidden
  - the event hash is `blake2b` over canonical events in emission order
- **Tests:**
  - run the toy in subprocesses with `PYTHONHASHSEED` set to 0, 1 and 12345, and compare hashes
  - a static check (an `ast` walk in a test) flags `set(`, set literals and iteration over `.keys()`
    of non-sorted dicts in `src/renasci/core` and `toy`, with an allow-list comment
  - single-thread BLAS is asserted at startup
- The engine version, NumPy version and Python minor version go into the manifest and the checkpoint
  header.

### 3.15 Divergence analysis (part of #51)

As built (r4). Earlier drafts propagated taint along recorded reads; review showed that version was
timeless and value-blind, so a whole valley would look explained and real coupling bugs passed.

- **What is recorded:** for every activation, and every `ctx.scope(key)` inside it (one village, one
  valley), each field read *and a digest of the value seen*, plus the events emitted there.
  `ctx.guarded(entity)` always records a `(entity, "guard")` read whose value names the protecting
  pin or ripple, or none. An ordered `activations` table lists every activation run.
- **A scope is tainted** when a read made in both runs saw different values. Deterministic code
  diverges first at a shared read whose value differs, so reads made in only one run are ignored:
  they follow a decision that already differed.
- **An event is explained** if its scope (or its activation's unscoped reads) is tainted, its source is
  a ripple, or a cause is tainted: a tainted event, an activation or scope that is tainted or exists in
  only one run for a tainted reason, a ripple, or a pin whose status history differs.
- **A final difference** in an entity's field or a column cell is explained if the event that last
  wrote it, in either run, is tainted.
- **Unexplained** means the code depended on something it did not read through the engine (a module
  global, `hash()`, a shared counter). The report lists the first unexplained items, which point at
  the root coupling, and the causal wave (divergent events per place per year).
- **Limitation:** the scope is the unit of explanation. A coupling *inside* a scope whose inputs
  already differ is indistinguishable from a legitimate consequence. Use scopes as fine as decisions.
- **Proven by the tests:** a protect ripple and a doom ripple give zero unexplained divergence and an
  untouched other valley. Two planted bugs (a world-wide counter and a per-valley module global) are
  each flagged at their first hidden coupling.

### 3.16 Toy ruleset (#51)

This world is deliberately not Renascita ⟨#16⟩.

- **The world:** 6 villages in 2 valleys, about 600 people at the start, run for 300 years.
- **Systems:**
  - `toy.life` (monthly): ageing and deaths. Hazard by age, plus famine.
  - `toy.marriage` (seasonal): rendezvous matching within and between villages.
  - `toy.births` (seasonal).
  - `toy.granary` (seasonal, batch): each valley shares one granary. Harvests are drawn per village
    and consumption per head. A shortfall raises famine risk across the whole valley. **This is
    the shared resource that tests locality.**
  - `toy.migration` (yearly): moving between villages in a valley.
- **LOD:** villages hold an aggregate of commoners, and a few dozen named people per village are
  promoted through toy events.
- **Toy pins:**
  - existence: "Ada Millbrook" is born in 1X 40–60 and lives to 1X 120
  - event: "the Eastvale fire" happens in 1X 150–160
  - ordering: the fire comes after Ada's marriage

  These are enough to exercise guard, steer, force and strain.
- **Golden tests:**
  - the baseline hash is pinned in `tests/golden/` and updated deliberately
  - a ripple protecting a villager at 1X 120 yields zero unexplained divergence

### 3.17 Benchmarks (#52)

- `renasci bench` runs the toy for N years and appends to `bench/history.csv`:
  `date, commit (git describe, with -dirty), engine, python, numpy, world, years, people_start, people_peak, events, seconds, years_per_s, events_per_s, run_mb`. Seconds cover the simulation and writing the run folder, not world setup
- Not gated in CI. The plan records the first baseline as the M0 exit.

## 4. Testing summary

| Area | Tests |
|---|---|
| calendar, rng, choice, scheduler | `hypothesis` properties (§3.1, §3.2, §3.5, §3.7) |
| store, events | schema validation, the dead-participant rule, delta logging, cause index both ways |
| determinism | repeat runs; subprocesses with different `PYTHONHASHSEED`; the static set-iteration check |
| replay | 8+ checkpoint positions, comparing the event hash and the final state hash |
| locality | toy ripple → zero unexplained (events and state); the untouched valley is byte-identical; the negative control (an injected coupling bug) is caught; read-set enforcement in strict mode |
| pins | feasibility classification; guard, force and violated paths; a satisfied pin makes no draws, writes or events; promotion no-op (identical hash, zero strain) |
| run folder | write → read round-trip; truncation on replay; fork prefix sharing |
| golden | the toy baseline hash |

## 5. Ticket map

| Ticket | Delivers | Needs |
|---|---|---|
| #36 | scaffold, `renasci_legacy`, pytest, CI-less `uv run pytest` | — |
| #37 | calendar | #36 |
| #38 | keyed RNG | #37 |
| #39 | ids + store + deltas | #37 |
| #41 | events + causes | #39 |
| #40 | scheduler | #37, #41 |
| #45 | systems, ctx, rulesets | #38, #39, #40, #41 |
| #47 | choice + hinges | #38, #45 |
| #42 | run folder | #41 |
| #43 | checkpoints + replay | #42, #45 |
| #50 | determinism hazards | #45 |
| #46 | LOD interface | #45 |
| #48 | pins skeleton | #45 |
| #49 | ripple applier: protect, doom, inject | #48 |
| #51 | toy ruleset + divergence | #43, #47, #49, #46 |
| #44 | recipes + CLI | #43, #51 |
| #52 | bench | #44 |
| #114 (M3) | structural, favour, luck, plant, reshuffle, steer, fork prefix sharing | #49, #51 |

**Housekeeping:** #134–#139 carry the S1 label but belong to M5 or M7. They are deep-time tuning,
later rulesets and Rust. They stay under the S1 epic but are not part of the S1 exit.

## 6. Changes from the independent review (r2)

All eight concerns were accepted:

1. Locality now propagates from **recorded actual reads**, taints both runs, compares final state, and
   has a negative control.
2. S1 is cut to the M0 exit. Coarse execution, steer, fork sharing and four ripple kinds move to M3
   or M5.
3. Satisfied pins are pure observers, and promoted entities bind to their natural creating key.
4. Hashes use exact float bits, with no quantisation.
5. The checkpoint position, the canonical state serialiser, the occurrence scopes and subprocess
   replay are specified, and owner-less streams are forbidden.
6. A bulk-delta API is added for columnar and aggregate writes.
7. The coarse-step RNG keying rule is fixed now, and execution is deferred.
8. Steer is a no-op hook in S1.

## 7. Open decisions

1. ⟨#16⟩ The base grain is a season, with daily or monthly sub-steps.
2. ⟨#16⟩ Run folders live in `runs/` (gitignored), and recipes in `recipes/` (committed).
3. ⟨#16⟩ The toy world is villages, a marriage market and a shared granary.
4. ~~Payload format~~ **Decided:** canonical JSON.
5. ~~Checkpoint format~~ **Decided:** canonical JSON, gzipped, with no pickle. Engine changes still
   invalidate checkpoints, as the master spec accepts.
6. ~~Recording actual reads costs speed~~ **Decided:** always record them. Speed is not an S1 concern,
   and a Rust rewrite is the later performance path.
