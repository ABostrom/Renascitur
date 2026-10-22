# Renascitur History Engine: Master Design Spec

- **Version:** v2, 2026-10-21. It incorporates the review findings, the proof-of-concept results and the second round of Q&A.
- **Status:** Draft for review.
- **Sources:**
  - Brainstorm handoff: `notes/2026-10-21-world-sim-brainstorm.md`.
  - Proof of concept (throwaway): `poc/history_poc.py`, and the Observatory PoC built from `poc/`.
- **Scope:** the whole platform. It covers the vision, the concepts, the architecture, the sub-projects, the transformation of the `renasci` prototype, and the roadmap. Each sub-project gets its own spec, then a plan, then implementation, in roadmap order. **Sub-project S1 (engine foundation) is specced first.**

---

## 1. Vision

The **Renascitur History Engine** generates the history of Renascitur by simulating it from the ground up. It is an **authoring tool with a god's-eye quality**, not a game:

1. **Run** a history.
2. **Find** the stories in it.
3. **Nudge** it at the moments that matter.
4. **Re-run**.
5. **Keep** what is good.

What it produces is **source material**: a queryable graph of what truly happened, what everyone believed, what they wanted, what they schemed, and why. That graph feeds novels, novellas and campaigns. It also fills out the vault, which is the world's curated canon.

Guiding beliefs:

- **Stories emerge from simulated wants.** People with heritable traits, drives, ambitions and beliefs scheme, ally, betray and fail. Those threads, flowing through a period of time, are the product. A blacksmith is drawn into a king's plot. A younger son poisons his brother for the seat. A wronged ward-keeper races the man who framed her.
- **History is written by the victors.** There is one *true* history and many *believed* ones. Lies, framing and omission are tracked, never collapsed into the truth.
- **Canon is placed; the rest grows.** This is the PCG override model. Hand-authored and hand-promoted canon are pinned like hand-placed trees, and the simulation grows the forest around them.
- **The author's hand is the god's hand.** You find the latch points (a person who died unfulfilled, a plot that nearly succeeded), nudge them with a ripple, and watch the consequences. Ripples are always disguised as in-world causes.
- **AI stays out of the sim loop.** The sim is deterministic and structured. Claude writes prose afterwards and checks it against the truth.

## 2. Settled decisions

| Area | Decision |
|---|---|
| Product | An offline history generator and authoring tool. It is not a game. |
| Time span | One causal timeline across four ages. The First Age is years 1–10000 and the Second is 10001–12000. The Third is undated and sparse (to be filled). **The Fourth Age runs 256 years so far: 4A 1 is the Psychic Schism, and 4A 256 is the campaign present.** The sim stops at the present. |
| Dating | **Age-relative years** ("4A 37"). Absolute years are derived once the Third Age's length is decided, and everything shifts automatically. |
| Re-running | A continuous history with **checkpoints**. Age boundaries are always checkpoints. A ripple replays from the nearest earlier checkpoint, and runs can fork like branches. |
| Rules per age | A shared engine plus a pluggable **ruleset** per age. The Fourth Age ruleset covers the aftermath of the Schism, aberrations and night terrors, Lux Lapis, the Vialux, the Firebrand Empire and its Great Houses. |
| Durability | **Canon is durable; seeds are disposable.** Liked output is kept by canonising it, because seeds stop reproducing history once the engine changes. |
| Canon home | **The vault is the canon ledger**, and it is curated. Promotion drafts a typed note with `canon: proposed`. You edit it in Obsidian and set `canon: true`. User edits win. |
| Identity | Every canon note carries a stable **`id:`** in its frontmatter. Each run begins with **casting**: canon entities are placed into the world (they exist, with the right parents, house and traits) before anything grows around them. The bindings are logged, and diffs and the Observatory match entities by vault id first, then by causal id. |
| Canon characters | Most named characters are **modern** (alive at 4A 256). They use **pinned lineage**: the character and their ancestry are cast up front, and the sim grows the bloodline to reach them. |
| Emperors | **Eight named Emperors** (Unimus, Duo, Tertia, Tetrus, Quintavius, Sextus, Septimus, Octavian) are **one bloodline**: each Emperor descends from the one before, so they are a **lineage pin**, not an elected succession. Octavian is alive and reigning at 4A 256. |
| Pin scope | Promoting pins the event and its participants' existence. You choose which upstream **events** to keep as causes (beliefs and drives are not pinnable); the rest regenerate. |
| Pin precision | Exact date, window, ordering ("after X, before Y"), or open-ended goal ("X travels from A to B in the Fourth Age"). |
| Ripples | Recorded, replayable, and **disguised as in-world causes**. Kinds: protect, doom, favour, luck, inject, plant, structural. |
| Ripple guarantee | **No unexplained change.** Every difference between a run and its ripple re-run traces to the ripple through a real causal path, and the Observatory can show that path. Spread is not damped; it can be wide. **Reshuffle from year X** re-rolls everything later in time on purpose. |
| What-ifs | **You pick and it runs.** The Observatory suggests latch points; you choose one, adjust the ripple, and the engine replays from a checkpoint and shows a side-by-side diff. There is no automatic batch exploration. |
| Fidelity | **Maximal realism**, made affordable by level of detail (LOD) across both population and time. Every system can be swapped for a deeper version. |
| Heart | **People, bloodlines and their ambitions:** simulated genomes, drives, ambitions, and schemes that pursue them. |
| Schemes | A library of actions written as **Python classes** (preconditions, effects, odds, secrecy, flavour) and a **planner** that chains them toward an ambition's goal. Plots are new combinations of a vocabulary you control. |
| Stories | Structured as **saga › arc › beat**. A saga is an entangled affair. An arc is one character's ambition from formation to outcome. A beat is an event. |
| Motivation | Simulated drives produce behaviour. Ambitions are first-class records (formed → pursued → fulfilled / thwarted / abandoned / died unfulfilled). An emergent want / need / wound layer supports writing arcs. |
| Mythic beings | Gods and immortals are agents, their canon deeds are pinned, and faith is a force (from M5). |
| First Age | High fantasy blended with science fiction: Solarans, the Endless Sun, World Trees, the stars. It is the largest body of lore to generate, so it gets its **own milestone (M5)** and ruleset (S14), right after the story layer. |
| Realms | Renascita only for now. Pyrosia is the first mapped region. |
| Run budget | Overnight for a full multi-age run; minutes for a replay from a checkpoint. A full Fourth Age run (about 250 years) should take minutes at M1 scale. |
| Observatory | The **driver and the viewer**: a **SvelteKit** web app. **Viewing needs no server**: the page reads run folders (**plain JSON Lines + a JSON manifest**) directly with ordinary JavaScript. There's no database or query engine, which keeps the stack small. A run can be published as a static page. **Acting needs the local engine**: `renasci serve` (FastAPI, local only) starts runs and replays and promotes to the vault. Without it, the page is read-only. |
| Stack | Python 3.12 with uv, NumPy, pytest and hypothesis. **Keep the stack small.** Data is JSON everywhere, with no Parquet, DuckDB or pickle. A Rust rewrite may come much later; speed is not an early goal. |
| Engine | A rewrite in this repo. The `renasci` prototype is reference only. |
| Geography | `images/Renascitur.png` (Inkarnate) is the source map; 1 cell = 24 miles. We build our own map editor. Routes have travel time by mode and season, danger by time of day, and access rules. The Vialux is safe at night. |

## 3. Core concepts

| Term | Meaning |
|---|---|
| **Truth** | The authoritative world state and the event log of what actually happened. |
| **Entity** | Anything with an id and a history: a person, house, faction, place, route, object or deity. It has a **biography** (the events it took part in). |
| **Event** | A typed, dated fact: participants in roles, a place, **causes**, a payload and a source. Events are truth. Some are **secret** (known only to their participants). |
| **Cause** | A link from an event to what produced it: events, belief states, drives, ambitions, pins or ripples. |
| **Ambition** | A first-class want with an owner, kind, target, cause, formation date, actions taken (beats) and an outcome: fulfilled, thwarted, abandoned, or died unfulfilled. |
| **Action** | A unit of agency from the action library: preconditions, effects, odds, secrecy and flavour. Examples: poison, bribe, slander, recruit, petition, duel, forge a letter. |
| **Scheme** | A plan: a sequence of actions the planner chose toward an ambition, with accomplices, progress and exposure risk. |
| **Saga / Arc / Beat** | Story structure found in a run. A **saga** is a cluster of entangled arcs. An **arc** is one ambition followed from start to end. A **beat** is an event in an arc. |
| **Latch point** | A moment where a nudge could unlock story, ranked by potential. Examples: someone dies with an ambition unfulfilled; a scheme is exposed by a narrow margin; a duel turns on a hair. |
| **Hinge** | A recorded random outcome whose margin was small. The source data for latch points. |
| **Mind** | A notable's inner state: beliefs, values, generalisations, drives, ambitions, want / need / wound. |
| **Claim / Belief** | A proposition held by a mind (or, as a distribution, by a population), with confidence and **provenance**. It may be true, false, a lie, framed, or half-true. |
| **Population (aggregate)** | The masses at a place, held as NumPy distributions. It uses the same model as individuals, at a coarser grain. |
| **Notable** | A fully simulated individual. **Promotion** pulls one out of an aggregate; **demotion** fades them back in as a dormant record. |
| **Pin** | A canon constraint read from the vault: existence, lineage, event, ordering, succession, goal. |
| **Casting** | The run-start step that binds pins to sim entities and places canon into the initial state. |
| **Ripple** | An authored intervention, disguised as an in-world cause. |
| **Run** | Engine version + seed + vault snapshot (pin set) + ripples + reshuffles. It produces a run folder. |
| **Checkpoint** | A full saved state from which replays and forks start. |
| **Ruleset** | The active systems, parameters and time-step policy for an age. |
| **Scenario** | The starting point of a run: a start date, an initial state (synthesised population plus cast canon), and a ruleset. |

## 4. Architecture

### 4.1 Layers

```
 vault (docs/, Obsidian)                 Observatory (SvelteKit)
   │  canon notes ─► pins, casting        │ view: reads run folders directly (JSON Lines)
   │  ◄─ proposed notes                   │ act:  calls `renasci serve` when it is running
   ▼                                      ▼
┌──────────────────────── renasci (Python package) ────────────────────────┐
│ vault bridge   notes → typed entities, pins, casting; write proposed notes │
│ engine core    calendar · scheduler · keyed RNG · entity store ·           │
│                event log + cause graph · checkpoints · recipes ·           │
│                pin director · ripple applier · system registry · LOD       │
│ world model    places · routes · regions (cell mesh later)                 │
│ systems        people & bloodlines · ambitions, actions & schemes · minds  │
│                & epistemics · polities · crafts & objects · ecology · myth │
│ rulesets       per age                                                     │
│ story finder   sagas · arcs · beats · hinges · latch points · salience     │
│ story layer    context packs · POV chronicles · canon checks · MCP         │
│ outputs        run folder (JSONL + manifest) · `renasci serve` (FastAPI) │
└───────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Run data flow

```
recipe (engine version, seed, vault commit, ripples, reshuffles)
  → feasibility check of pins → casting → initial state (scenario or checkpoint)
  → scheduler loop: due systems/agents act → actions → events (with causes) → state
       ↳ ambitions form from drives, wounds, beliefs; the planner builds schemes
       ↳ pin director guards / steers / forces; ripples fire, disguised
       ↳ hinges recorded; checkpoints at age boundaries and intervals
  → run folder: events, causes, people, ambitions, schemes, beliefs, timeseries, manifest
  → story finder: sagas, arcs, latch points
  → Observatory reads it. You pick a latch point → ripple → replay → diff → promote
  → vault bridge drafts `canon: proposed` notes → you curate in Obsidian
```

### 4.3 Boundaries

- **Systems never call each other directly.** They read state through the entity store, act through actions, emit events, and react via the scheduler.
- **Each system declares its read-set** (which state it reads), so locality can be reasoned about and tested.
- The engine is usable without the Observatory, through the CLI and Python API. The Observatory never imports engine code: it talks to run folders and to `renasci serve`.

## 5. Cross-cutting design

### 5.1 Determinism and randomness

- **Keyed counter-based draws:** `rng(seed, system, stable_entity_id, purpose, canonical_tick, ordinal)`, using NumPy Philox.
  - The **ordinal** is derived locally (the n-th draw for that key within that tick), never from a global count.
  - The **canonical tick** is a coarse time unit (a season) that does not depend on the current time-step resolution. Finer steps sub-key under it, so changing resolution inside a focus window does not change unrelated draws.
- **Causal ids.** Entity ids derive from what created them: `hash(parent_ids, creating_event_key, ordinal)`. Cast canon entities use their vault id. There are never global counters.
- **Total scheduler order:** `(time, priority, stable_entity_id, purpose)`. Insertion order never breaks ties.
- **Choice among candidates** (partners, targets, accomplices) uses **rendezvous (min-hash) selection**. Adding or removing one candidate then only matters if that candidate would have won. Greedy matching in list order is banned; the PoC showed it couples unrelated people.
- **Hazards:**
  - Sim code may not iterate sets or hash-ordered containers.
  - BLAS runs single-threaded.
  - NumPy and Python versions are part of the engine version.
  - Determinism hashes use a canonical serialisation with quantised floats.
- **Reshuffle from year X** salts every key dated at or after X.

### 5.2 Locality

- **Guarantee: no unexplained divergence.** Comparing a run with its ripple re-run, every entity whose state differs must be reachable from the ripple through recorded causes, shared events, provenance links or a declared read-set.
- **Validated by the PoC.** Over 120 simulated years there were 0 unexplained divergences among about 16,000–39,000 divergent events.
- **The PoC also showed** that causal spread through a small, intermarried nobility is near-total within a century. The guarantee is about explainability, not small diffs.
- The Observatory shows the **causal wave**: the share of events that differ, per place, over time.

### 5.3 Time

- Age-relative dates (`4A 37`) on a configurable calendar. Defaults are placeholders until in-world names exist.
- **Multi-rate scheduler:**
  - notables act monthly
  - urgent follow-ups fire days later
  - populations update seasonally
  - structural systems update yearly
- **Temporal LOD:** quiet eras step coarsely, and **focus windows** run at full resolution. The interface (switching between coarse and fine, and promoting individuals out of aggregates that skipped time) is **designed in S1**, even though tuning for deep time comes with the First Age (M5).

### 5.4 Storage

- **Entity store:** stable ids, columnar NumPy components for bulk data (aggregates, genomes), and records for notables. **Dormant records are never deleted.**
- **Run folder** (the unit the Observatory reads):
  - **Contents:** a `manifest.json` (recipe, engine and schema versions, vault commit, checks) plus JSON Lines tables (one `.jsonl` per table per segment): `events`, `causes`, `participants`, `people`, `ambitions`, `schemes`, `beliefs` (provenance), `state_deltas` (dated changes for "as of" views), `timeseries`, `hinges`, `stories`.
  - **Partitioning:** files are partitioned by age or segment.
  - **Forks** share the prefix before the fork point by reference.
  - **Aggregates** are logged as timeseries, not events. Belief provenance is sampled in aggregates and complete for notables.
- **Storage budget:** a full Fourth Age run at M1 scale stays under about 1 GB. S1 sets up measurement, and each milestone checks against the budget.
- **Checkpoints** contain the entity store, the scheduler queue (with pending actions and their cause references), draw ordinals in flight, indices, pin-director state, fired ripples, active schemes, and the run-folder high-water mark (for truncating on replay).
- **Versioning:** event-type schemas, the run-folder schema, the recipe format, the checkpoint format and the canon frontmatter fields are all versioned. An engine change invalidates old checkpoints, and replays then restart from the scenario. During development, that cost is accepted and made visible.
- **Run recipes** (TOML: engine version, seed, vault commit or pin-set hash, ripples, reshuffles) are committed to git. Run folders are gitignored.

### 5.5 Events, causes and secrecy

- An event has an id, a date, a type, participants by role, a place, causes, a payload, a source (system, action, pin or ripple) and a **visibility** (public, or secret to its participants).
- Causes form a DAG that can be queried both ways.
- A secret event (a poisoning) and its public cover (a death from "a wasting illness") are separate events linked by a cause. The epistemic layer decides who learns the truth.

### 5.6 Ambitions, actions and schemes

- **Ambitions** form from drives, wounds, grievances, beliefs, roles and scenario hooks. Formation has cooldowns. Each ambition records its cause, so arcs can say what it was "born of".
- **Actions** are Python classes sharing one interface: `preconditions(world, actor, target)`, `effects`, `odds(world, actor, target)`, `secrecy`, `duration`, `flavour`. Content grows by adding classes.
- **Planner:** a goal-directed search (HTN or GOAP-style) over the action library, bounded by the actor's wits and knowledge. It builds a **scheme**: ordered steps, recruited accomplices, progress, and exposure risk per secret step.
  - **Starter library (M1):** recruit, bribe, petition, court favour, arrange marriage, poison, duel, assassinate, flee, confess.
  - **M2 adds belief actions:** slander, forge a letter, spread a rumour, frame, bear witness. These make deception a scheming tool.
- **Outcomes** resolve ambitions. Death resolves every active ambition as **died unfulfilled**.
- **Hinges:** every consequential draw records its margin. Close calls (an exposure roll, a duel, a death roll while ambitions are active) feed latch points.

### 5.7 Story finding

- **Arcs** come from ambitions: formation, then beats, then outcome, with the cause they were born of.
- **Sagas** cluster arcs that share events, causes or targets (for example, plotters racing each other), with sub-arc splitting so one affair doesn't swallow a whole house.
- **Latch points** rank people who died unfulfilled, plus near-miss hinges, by potential: youth, talent, scheme progress, margin and stakes. Each suggests a ripple and the means it would use (stop a natural death, spare them in a fight, pardon them at the scaffold).
- **Salience** scores events, arcs and sagas. Period queries ("what flows through 4A 40–90?") return the sagas and arcs alive in that window.

### 5.8 Pins, casting and the pin director

- **Kinds:** existence, lineage (a person with an ancestry), event, ordering, **succession** (an ordered list of holders of an office, e.g. a Great House's heads; the eight Emperors are a lineage pin instead), goal.
- **Feasibility pass at load:** build the ordering DAG, detect cycles, intersect windows, check that genome and lineage constraints are satisfiable, and classify pins **outside the run window** (or of unsupported kinds) as *out of scope* rather than strained.
- **Casting** places existence and lineage pins into the initial state, or reserves them for the right moment, and binds pins to entities.
- **The director, in order of preference:**
  1. **Guard:** a pinned participant can't be removed before their pins are fulfilled. A fatal outcome becomes a disguised near-miss.
  2. **Steer:** only when a pin's satisfaction odds fall below a threshold. Steering never biases a pin that would be met naturally.
  3. **Force:** at the deadline, with a constructed plausible cause.
- **If force fails** (the pin is impossible), the pin is logged as **violated** and the run continues.
- All guarding, steering, forcing and violation are logged as **canon strain**.
- **Invariant:** re-running a recipe plus a pin just promoted from that run is a no-op with zero strain.

### 5.9 Ripples

Kinds: protect, doom, favour (scheme odds), luck, inject an event, plant (an object or rumour), structural (a pass closes, a harvest fails).

Each ripple is applied through an **in-world disguise** (a physician's care, a Leonin outrider, a timely pardon). Deity attribution is deferred to S11. Ripples are cause nodes, so the "why" chain can show the author's hand; prose never does.

### 5.10 Level of detail

- **Individual:** full mind, genome and relationships. **Aggregate:** distributions per settlement, held as arrays.
- **Promotion:** when someone enters a pin, ripple, scheme or salient event, a concrete individual is sampled consistent with the aggregate. The sampling is keyed by place, event and ordinal.
- **Demotion:** a faded individual becomes a **dormant record**, keeping their id, events and relationships.
  - Pinned entities, and anyone with an active ambition, are never demoted.
  - Conservation covers counts, age structure and allele frequencies.
  - Synthetic **unknown-parent** placeholders are allowed in genealogies of promoted people.

### 5.11 Vault bridge

- **Note-type mapping:**

  | Note | Becomes |
  |---|---|
  | event, character, house, faction, artifact | pins |
  | chronicle, myth, prophecy | **claim seeds** (beliefs held by those who wrote or tell them, not truth) |
  | essays, indexes | ignored |
  | `status: draft` | opts out |

- **Write:** promoted entities and events become typed notes with `canon: proposed`. Each note carries a `generated_hash` of the generated content. If the note no longer matches the hash, you have edited it, and the bridge never overwrites it.
- **Stale proposals:** proposed notes from a superseded run that you haven't touched are listed for cleanup. They are never auto-deleted.

## 6. Sub-projects

Each entry gives the scope, then *depends on* → *done when*.

- **S1 Engine foundation.**
  - Scope: calendar (age-relative), scheduler with total order, keyed RNG with canonical ticks, causal ids, entity store, typed events (with causes and visibility), run-folder writer (JSON Lines + manifest), checkpoints and replay, recipes, ruleset switching, the temporal-LOD interface, pin director and casting skeletons, ripple applier, rendezvous choice, hinge recording, test harness.
  - Depends on nothing. Done when a toy ruleset *that includes matching and a shared resource* runs deterministically, replays equivalently from many checkpoint positions, passes the no-unexplained-divergence test for a ripple, and honours toy pins.
- **S2 Vault bridge.**
  - Scope: loader, note-type mapping, `id:` handling, pin extraction (vague dates, succession, lineage), feasibility pass, casting inputs, the proposed-note writer with `generated_hash`.
  - Depends on S1. Done when Fourth Age canon (the 12 Houses, 8 Emperors, modern characters with lineages) loads, passes feasibility, and casts. A promoted event round-trips to `canon: true`.
- **S3 People & bloodlines.**
  - Scope: genome and phenotype, life cycle, families, marriage via rendezvous matching, houses and succession (heirs named each generation), a relationship graph, drives, populations with promotion and demotion, scenario synthesis for 4A 1.
  - Depends on S1 and S2. Done when the Fourth Age runs its full span at M1 scale, conservation invariants hold, and lineage pins are met.
- **S4 World model & geography.**
  - Scope: **M1 needs only the minimal place/route format** (places, routes with travel days and Vialux flag, regions). The full model (cell mesh, mode/season/time-of-day routing, history by year) comes in M2.
  - Depends on S1. Done (minimal) when the sim moves people between Pyrosia places. Done (full) when news travels by route.
- **S5 Map editor & Inkarnate import.**
  - Scope: the web editor (places, routes, regions, terrain) and import.
  - Depends on S4 (full). Done when Pyrosia is fully edited and read by the sim.
- **S6 Epistemics.**
  - Scope: claims, belief stores, provenance, trust, drift, correction, aggregate belief distributions, visibility of secret events.
  - Depends on S3 and S4. Done when the ward-failure scenario (a **scripted injection**) produces divergent, traceable beliefs.
- **S7 Ambitions, actions & schemes.**
  - Scope: ambition lifecycle, the action-class interface, the starter action library, the planner, schemes (accomplices, progress, exposure), hinges.
  - Depends on S3. Done when succession plots, court intrigue and vengeance emerge from drives, and every scheme step traces to its ambition. In M2 it gains belief actions, depending on S6.
- **S8 Polities & conflict:** factions, offices, the imperial line, diplomacy, war, borders.
- **S9 Work, crafts & objects:** jobs, materials, crafting, trade, object biographies.
- **S10 Ecology & catastrophe:** climate, harvests, disease, famine, aberrations and night terrors, Lux Lapis and wards.
- **S11 Mythic beings & faith (M5):** gods and immortals as agents, worship, faith as a force, divine attribution of ripples.
- **S14 First Age ruleset (M5):**
  - Scope:
    - Solaran civilisation: research, inventions, colonies and schisms, as a technology system
    - the World Trees and the Elder Races
    - elemental and cosmic events
    - the stars as an abstract off-world realm
    - First Age canon pins
    - myth formation: events become myths and claim seeds for later ages
  - Depends on S3, S6, S7, S11 and the temporal-LOD interface from S1.
  - Done when a full First Age run holds its canon within budget and produces promotable lore.
- **S12 Story layer:** context packs, POV chronicles (the victor's account vs the truth), canon checks of prose, the MCP server. **Story finding (sagas, arcs, latch points) is not here.** It belongs to S7 plus S13, and lands in M1.
- **S13 Observatory:**
  - The SvelteKit driver and viewer. It reads JSON Lines run folders directly and acts through `renasci serve`. It grows every milestone.
  - Its core inspectors:
    - **Stories:** period selector, story river, sagas › arcs › beats, latch points with what-if launching and diffs.
    - **World history:** timeline, cause chains, map by year.
    - **World knowledge:** truth vs belief, claim lineage, spread.
    - **Individuals:** genome with allele origins, family tree, inner life as of any date, ambitions and schemes, beliefs with provenance, relationship web, life events.
    - **Objects.**
    - **Run diff:** the causal wave.
  - Depends on S1.

S8–S11 each depend on S3, S4 and S7 (and S6 where beliefs are involved). Each has its own spec and its own exit criteria.

## 7. Transforming the `renasci` prototype

| Prototype concept | Fate |
|---|---|
| `World.advance_year()` | Replaced by the multi-rate scheduler (S1). |
| `EventBus` cascade | Replaced by typed events with explicit causes. Follow-ups become scheduled actions that record their trigger as a cause. |
| Birth / death / marriage generators | S3 systems with keyed RNG, LOD and rendezvous matching. |
| `StatThreshold` / world stats | Derived indicators inside S8 and S10. |
| `Person`, `House`, kinship, races | Rebuilt in S3 on the entity store and genome. Races come from the vault. |
| `StatDelta` per tick | Superseded by `state_deltas` and timeseries in the run folder. |
| `PersonView` projection | **Kept as a pattern** for belief-projected and "as of" views. |

**Steps:**

1. Set up `pyproject.toml` with uv and Python 3.12. All commands go through `uv run` (the machine default is 3.7).
2. Move the prototype to `src/renasci_legacy/` (reference only). Delete `setup.py` and retire `src/main.py`.
3. Build S1 fresh in `src/renasci/`.
4. Delete the legacy code once S3 covers it.
5. `poc/` remains as a reference until M1 ships, then it is deleted.

## 8. Roadmap

### 8.1 Principles

- **Stories first.** Every milestone ends with a demo that shows *stories*, not just plumbing. From M1 onward, the Observatory's front page is the Stories inspector.
- **Two tracks advance together:** the Engine and the Observatory. Every milestone ships the views needed to see, judge, ripple and canonise what it built.
- **Spec → plan → build** per sub-project. Exit criteria are tests plus a demo. Benchmarks are recorded from M0.

### 8.2 Milestones

**M0: Foundation** (S1, S13 v0)
- **Engine:** S1 in full. The toy ruleset includes matching and a shared resource, so that locality is actually tested.
- **Observatory v0:** the SvelteKit shell; open a run folder; an event browser; the cause-chain explorer; run diff with the causal wave; launch run/replay via `renasci serve`. Benchmarks are reported by the CLI.
- **Demo:** a toy run of a few hundred years. Add a ripple, replay from a checkpoint, and see the causal wave with zero unexplained divergences.
- **Exit:** determinism, replay equivalence (many checkpoint positions), the locality tests, and a recorded benchmark baseline.

**M1: The Fourth Age, lived** (S2, S3, minimal S4, S7 core, S13 v1)
- **Engine:**
  - The vault bridge, with Fourth Age canon and feasibility.
  - Casting: the 12 Great Houses, the 8 Emperors as one pinned imperial bloodline, and modern characters with pinned lineage.
  - Scenario synthesis at 4A 1 (the Psychic Schism's aftermath).
  - Genome, families, houses and succession, the relationship graph, drives.
  - Ambitions, the starter action library, the planner and schemes.
  - Hinges, then sagas, arcs and latch points.
  - Minimal Pyrosia places and routes.
- **Observatory v1:**
  - **Stories:** period selector, story river, sagas › arcs › beats, latch points, a what-if launcher with side-by-side diff.
  - **Individuals:** genome with allele origins, family tree, inner life as of a date, ambitions and schemes, relationship web, events.
  - House pages, population charts, the canon-strain report, and promote with event-cause selection.
- **Demo:**
  - Simulate 4A 1 to 4A 256. All eight Emperors reign in order, and the modern canon characters are born into their pinned lineages.
  - Find a saga in 4A 80–140.
  - Pick a latch point (someone who died unfulfilled), protect them, re-run, and see what changed.
  - Promote an arc into the vault.
- **Exit:**
  - Canon pins hold or are classified, with strain visible.
  - Conservation invariants pass.
  - The full run completes within minutes at M1 scale (tens of thousands of people, 1k–5k notables).
  - The promote round trip works.
  - A promoted pin is a no-op on its source run.

**M2: Rumour and deception** (full S4, S6, S7 belief actions, S13 v2)
- **Engine:** routes by mode, season and danger; news travels by road; claims, trust, drift, provenance; secret events and their covers; belief actions (slander, frame, forge a letter, bear witness); the ward failure as a scripted injection.
- **Observatory v2:** world knowledge (truth vs belief, claim lineage, spread maps); person pages gain beliefs with provenance; motivation traces from want back to belief back to origin.
- **Demo:** the ward failure. The guild's lie travels the Vialux, a witness races a cover-up, and the outcome depends on who survives. Latch points now include "the witness who never testified".
- **Exit:** the ward-failure golden scenario passes, and propagation stays within budget at M1 scale.

**M3: The map and the god's-eye loop** (S5, S13 v3)
- **Engine:** all ripple kinds; fork and compare across several runs; reshuffle.
- **Observatory v3:** the map editor and Inkarnate import; map by year; object biographies; a ripple authoring panel on every page; branch management.
- **Exit:** the full loop (run → find → ripple → re-run → compare → promote) with no code, on an edited map.

**M4: Story layer** (S12)
- **Engine:** context packs (a schema and a builder), POV chronicles, canon checks, the MCP server.
- **Observatory v4:** a context-pack builder from any saga or arc, plus canon-check reports.
- **Exit (structural):**
  - Context packs validate against their schema.
  - Canon-check recall is at least 90% on a set of seeded contradictions.
  - A POV chronicle and a campaign brief (a defined template: the saga, factions, NPCs with wants, hooks) are generated from one run.

**M5: The First Age** (S14, S11, temporal LOD at scale, minimal S8 polities)
- **Why here:** the First Age is high fantasy blended with science fiction. It is also the largest source of lore to generate. It comes once the engine, stories, epistemics and the prose layer exist to do it justice.
- **Engine:**
  - the First Age ruleset: Solaran civilisation, technology and research, the World Trees, the Elder Races, Muradin's communion with the elements, the Endless Sun, the Solarans reaching the stars
  - gods and primordial beings as agents (Ishna, Lord Syuul)
  - **the stars as an abstract off-world realm** (a place graph, not a map)
  - temporal LOD and focus windows tuned for a 10,000-year age
  - First Age events turn into myths and claim seeds that later ages inherit
- **Observatory v5:** technology and research timelines, a civilisation-scale map by millennium, focus-window controls, and a myth lineage view (event → myth → Fourth Age belief).
- **Demo:** a full First Age run, years 1–10000. Every First Age canon pin holds (the Endless Sun is built and falls, Solara collapses, Syuul is imprisoned). Generated Solaran colonies, inventions and schisms become sagas. One of them is still told, distorted, as a Fourth Age myth.
- **Exit:**
  - First Age canon holds or is classified.
  - The run stays within the overnight budget.
  - Generated lore can be promoted through the normal curation flow.

**M6: Breadth** (S8 in full, S9, S10, each its own spec, in an order chosen at M5)
- Each has its own exit criteria and Observatory views. Examples: polities and war with border maps; crafts and objects (the sword story emerges unscripted); ecology and catastrophe with disease and famine heatmaps.

**M7a: Deep time, mechanics:** a Third Age ruleset and run (filling the sparse age), plus the handoffs between ages: ruins, artifacts and myths carry over from First to Second to Third to Fourth.

**M7b: Deep time, scale:** the Second Age ruleset (Arcanometry, the Forge Wars, multi-realm), a full multi-age run overnight, and scale-up (Rust or PyO3 where profiled).

### 8.3 Dependencies

```
S1 ─┬─ S2 ─┐
    ├─ S3 ◄┴─ S7 ──────────┐
    ├─ S4(min) ─ S4(full) ─┼─ S6 ─ S7(belief actions)
    │              └─ S5   ├─ S11 ─ S14 (First Age, M5)
    │                      ├─ S8 · S9 · S10 (M6) ── M7a/b
    ├─ S13 (v0 → v6)       │
    └──────────────────────┴─ S12
```

### 8.4 Risks

| Risk | Mitigation |
|---|---|
| Scale/time budget | LOD from S1; benchmarks from M0; a storage budget; Rust where profiled. |
| Canon fights the sim | Feasibility pass; steer only when needed; strain visible from M0; out-of-scope classification. |
| Pinned lineages over-constrain M1 | Lineages are proposed with you before M1. The feasibility pass flags conflicts early. |
| The planner is slow or opaque | A bounded search depth; plans recorded as data; every step traces to its ambition. |
| Stories lumped or noisy | Saga › arc structure, sub-arc splitting, salience tuning in the Observatory. |
| Scope sprawl | Strict exits; the First Age waits for M5 and breadth for M6; one spec per sub-project. |
| The First Age overwhelms the engine | The stars are an abstract realm; temporal LOD keeps 10,000 years affordable; S14 has its own spec. |
| Vault churn | Curated promotion; `generated_hash` overwrite protection; a stale-proposal list. |
| Lore gaps | Placeholder calendar; age-relative dates; drafted timelines for you to correct. |

## 9. Performance

- **M1 target:** the Fourth Age (about 250 years) at tens of thousands of people with 1k–5k notables, in minutes. A replay from a checkpoint takes under a minute.
- **Eventual target:** hundreds of thousands to millions of people with 10k–50k notables, and a full multi-age run overnight.
- **Levers, in order:**
  1. LOD
  2. vectorised aggregates
  3. indexes (no full scans)
  4. scheduler batching
  5. planner depth bounds
  6. parallel independent runs (what-ifs)
  7. Rust or PyO3 on profiled hot paths
- The PoC ran 7 runs of 120 years (about 900 people each) in parallel in under 1 minute.

## 10. Testing

- **Determinism:** a canonical event hash, identical across repeated runs.
- **Replay equivalence:** a replay from N checkpoint positions matches the continuous run.
- **No unexplained divergence:** a ripple run against the baseline, checked with taint tracking.
- **Invariants:**
  - pins are honoured, classified or logged as violated
  - no events involve dead participants
  - genealogies are acyclic
  - conservation holds (counts, age structure, allele frequencies)
  - every scheme step traces to an ambition
- **Promotion no-op:** promoting from a run and re-running gives the same history with zero strain.
- **Property tests** (`hypothesis`) for the genome, scheduler order, calendar, rendezvous choice and the planner.
- **Golden scenarios:** the ward failure, a succession plot, and the imperial bloodline (all eight Emperors, in order).
- **Benchmarks:** years per second and storage per run, tracked over time.

## 11. Validated by the proof of concept

The throwaway PoC (`poc/`) simulated 120 years of a small Pyrosia. It had genomes, families, rendezvous matching, a relationship graph, drives, ambitions and schemes, the ward failure with a lie and drifting rumours, aggregates with promotion and demotion, pins with guard and steer, ripples, checkpoints and what-ifs. Results:

- Determinism and checkpoint replay equivalence: **pass**.
- No unexplained divergence: **pass**, with greedy matching fixed by rendezvous choice.
- "History is written by the victors" emerges. With no surviving witness, the guild's lie dominates. With the witness saved, the truth spreads and drives a feud.
- Story finding works in rough form: titled threads, latch points, and real what-if re-runs. One died-young duelist "rises to greatness" when protected; one would-be usurper lives on and still fails.
- **Lessons:**
  - Greedy matching couples everything.
  - Beliefs must compete (confirmation bias), or everyone believes everything.
  - Grievances need violent, attributed causes, or vengeance becomes an epidemic.
  - Ambitions need traits, cooldowns and heirs each generation, or one kind floods the history.
  - A thread-finder lumps entangled affairs, hence saga › arc.

## 12. Changes from the brainstorm handoff

- Ages are not about 2,000 years each. The First Age is 10,000 years (the vault's dates), and the Fourth Age is about 250 years.
- The Firebrand Empire belongs to the **Fourth Age**, which begins with the Psychic Schism. The vault currently files `Psychic Schism.md` under `History/Third Age/`; it may need moving or re-dating.
- The first spec is the foundation (S1), not an epistemic slice. The ambition engine moves into M1. The belief layer is M2.
- Deferred, not dropped:
  - "a faction's map can be wrong" (S6 with S4)
  - portable ward networks (S10)
  - a geography MCP (S12's MCP)

## 13. Open items

- **Drafted for you to correct before M1:**
  - a dated Fourth Age timeline (Emperor reigns, key events)
  - proposed lineages for the modern canon characters
- The genome loci and trait catalogue (S3).
- Claim formalism: confirm "claims + framing; a lie is a false claim plus intent" (S6).
- The map file format and editor details (S4, S5).
- Calendar names and dating conventions (placeholders until then).
- The Third Age's length (for absolute dates).
- The salience model and context-pack schema (S7/S13 for salience; S12 for packs).
- Whether other realms get maps (Renascita only for now).
