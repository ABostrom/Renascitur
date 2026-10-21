# World Sim + Epistemic Knowledge Graph — Brainstorm Handoff (2026-10-21)

Status: **superseded by the master spec v2**, `notes/specs/2026-10-21-history-engine-design.md`. That spec records later decisions, including corrections to this note. Keep this note as the brainstorm record.

## Vision

Upgrade `renasci` into a platform: a deep, person-based world/lore simulation
(ambition: deeper than Crusader Kings 3, Dwarf-Fortress-like history), with an
**epistemic knowledge graph at its core**. Not intended to become a game — it is an
**offline history generator** whose output is source material for **novels, novellas,
and campaigns**, using the graphs as LLM context.

Core idea: "history is written by the victors." There is one **true world graph**,
plus **beliefs per mind**, plus **provenance** of who told what to whom. Lies,
falsehoods, framings and bias are claims in belief graphs that diverge from truth.

The core loop:

```
truth -> perception (witnesses) -> belief (rumour, lies, drift) -> motivation -> action (events) -> truth
```

## Decisions made

- **Distortion types:** falsehood, lie, framing and bias/omission. Leaning toward claims with a truth status plus a framing layer; lies are a false claim plus intent; bias comes from querying omissions. Not formally locked.
- **Belief kinds:**
  - episodic claims ("elves poisoned the well")
  - generalizations with a strength ("elves are evil"). These filter which new claims get accepted, which creates a confirmation-bias feedback loop.
  - values ("my village first")
  - derived goals (BDI-style: Beliefs, Desires, Intentions)
- **Motivations are traceable:** any NPC goal can be traced back through beliefs to the originating rumour or lie.
- **Rumour mechanics:** trust, fit with existing beliefs, drift or mutation on retelling (claim lineage), and correction.
- **Level of detail:** notable individuals get full minds. The masses are aggregate populations holding belief *distributions*. People are promoted to individuals when they become notable and demoted when they fade.
- **Scale:**
  - Target: hundreds of thousands to low millions of people, with 10k–50k notable.
  - First milestone: tens of thousands, with 1k–5k notable.
  - Realistic medieval populations are fine, because the masses are aggregates.
- **Language:** Python. Populations in NumPy arrays. The belief-propagation hot path sits behind an interface so it can move to Rust or PyO3 later if profiling demands it.
- **Engine:** rewrite renasci's core in this repo. Its concepts (Houses, kinship succession, races, stat thresholds, reactive event bus) are re-implemented on a new foundation. The current prototype (about 1.3k LOC, no tests) is reference only.
- **Time:** multi-rate, event-scheduled time on a calendar with a scheduler queue.
  - Notables act on a roughly monthly cycle.
  - Urgent events schedule follow-ups days later.
  - Populations update seasonally.
  - Structural things update yearly.
  - Fine-grained time is needed for prose ("three days after the funeral").
- **Space is real.** Distance gates how news travels: a king's death reaches the provinces late, and a closed pass isolates a region.
- **The world has multiple realms:** Renascita, the Elementis planes (Aqua, Ignis, Terra, Ventus) and The World Beneath. They need inter-realm routes.
- **AI stays out of the sim loop.** The sim is deterministic and outputs structured truth, beliefs and causes. The LLM turns that into prose afterwards.
- **Story-layer requirements:**
  - Record causes (the "why") on every event.
  - Salience scoring for events, people and claims.
  - Context packs: focused, point-of-view-specific source bundles.
  - Canon checks of generated text against the true graph.
  - Probably exposed as an **MCP server over the whole sim**.
- **The vault is a seed and a sink:**
  - Hand-written lore seeds the truth and the founding myths.
  - Generated history can be written back as notes.
  - Chronicle, myth and prophecy note types are claims in all but name.

## Geography decisions

- **Source map:** `images/Renascitur.png`, an Inkarnate export.
  - 16,250 × 12,188 px.
  - Landmass outlines are broadly accurate.
  - The older Azgaar `.map` files in Downloads are **not** correct.
- **No Inkarnate connector.** Inkarnate has no public API and only stores brush strokes. We'll **build our own "Inkarnate lite" map editor** instead.
  - The map is data first: semantic layers that the sim, the MCP and the story layer read directly.
  - The sim can write back (new villages, roads, shifting borders), so the map has history and can be viewed by year.
  - Maps can also be beliefs: a faction's map can be wrong.
- **Editor v1 layers:** places, routes, named regions and terrain painting (all four).
- **Terrain structure:** an organic Voronoi cell mesh (Azgaar-style), shared by the editor and the sim. Recommended and assumed; the user didn't object.
- **Scale:** the Inkarnate grid is 255 × 188 cells, each about 64 px. **1 cell = 24 miles.**
  - The whole map is about 6,120 × 4,510 miles.
  - Land is roughly 35–40% of the map.
- **Import approach (hybrid):**
  - Auto-trace the coastlines; the sea is a uniform pale green with contour rings.
  - Auto-detect the square settlement markers (about 15).
  - Claude drafts the places, regions and routes from the image.
  - The user corrects everything in the editor.
- **What the map shows:**
  - The **western continent is Pyrosia**. Its tan areas divided by brown lines are **provinces**: Ashen Plains, Ashgatar, Ember Peaks, Flame Coast, Frontier's Edge and Burnt Reach.
  - The grey, orange and dark areas are **biomes**, so the tints import as both regions and terrain.
  - The **Firebrand Empire** is on Pyrosia, with its seat at Lion's Rest. Crossing it should take weeks on foot: the Lux road span is about 1,200 miles, roughly 8–9 weeks at 20 miles a day.
- **Lux roads** are the dotted white lines. Lux Lapis wards off night terrors, so Lux roads are safe at night. Off-road, caravans can deploy **portable ward networks**, which can be misconfigured or sabotaged.
- **Routes therefore need more than a length:**
  - travel time by mode (foot, horse, ship, army) and season
  - danger by time of day
  - access restrictions (can the Stained use them?)
  - The safe imperial network carries the official version of events, and rumours travel the wild roads.
- **The ward-failure event is a good test case for epistemics.** The true cause (apprentice error, sabotage by a rival house, or faulty Lux Faber wards) is hard to establish. The guild has a motive to blame user error, and survivors only saw part of it.

## Proposed decomposition (build order TBD)

1. **Engine foundation:**
   - seeded deterministic RNG
   - scheduler
   - typed events with participants and causes
   - save/load
   - tests
   - fixes for the current scaling hotspots (`get_alive_people` full scans, O(n²) marriage pairing)
2. **World model and geography:** cell mesh, places, routes, regions, realms, the map editor, the Inkarnate import, and a geography MCP.
3. **Epistemic core:** truth graph, belief stores, claims and provenance, trust, propagation with drift.
4. **Minds:** values, generalizations, goals, actions, levels of detail and promotion.
5. **Story layer:** salience, context packs, POV chronicles, canon checks, the sim MCP.

The user wanted a vertical slice to prove the loop early. The 50-person example
was rejected as too small for the overall goal, but the slice-first approach
itself wasn't rejected.

## Session 2 decisions (2026-10-21, later)

- **Framing:** an *authoring tool with a god's-eye quality*. It is not a game. You run, watch, nudge, re-run and keep.
- **Time span:** a hybrid. There is **one causal timeline across all four ages** (about 2,000 years each), with **checkpoints** (age boundaries are always checkpoints).
  - A run is defined by seed + canon pins + ripples.
  - A ripple replays from the nearest earlier checkpoint.
  - Forks are like git branches.
  - Each age plugs in its own **ruleset** on a shared engine.
  - The reset at the start of the Fourth Age is a ruleset change plus a canon event. Earlier eras persist as ruins and lost artifacts.
- **Canon is the durable thing; seeds are disposable.** Seeds won't reproduce history once the engine changes, so liked output is preserved by canonising it.
  - This is the PCG override model: hand-placed trees survive a forest reseed.
  - Hand-written lore is pinned from the start.
  - The sim generates *around* the pins.
- **Pin scope:** promoting pins the event and its participants' existence. You choose which upstream causes to keep; the rest regenerate.
- **Pin precision:** flexible. A pin can be an exact date, a window, an ordering, or an open-ended goal ("X travels A→B during the Third Age"). The sim resolves the specifics.
- **Canon home: the vault *is* the canon ledger, and it is curated.**
  - Promotion drafts a typed vault note with `canon: proposed`.
  - The user edits it in Obsidian and then flips it to `canon: true`. User edits win.
  - Nothing moves, so links stay stable.
- **Ripples (god-hand interventions):** nudge, inject, plant, protect or doom, change structure.
  - They are recorded and replayable.
  - They are **disguised as in-world causes** and may be attributed to a deity or omen, which feeds the epistemics.
- **Exploration UI:** map by year, timeline/chronicle by salience, and biography pages for people and objects. Claude/MCP is the prose and context layer, not the primary UI.
- **Fidelity: maximal realism (bottom-up).** Level of detail is mandatory: the same model runs at full detail where it matters and as aggregates elsewhere. Every system sits behind an interface so it can be swapped for a deeper version later.
- **Heart: people and bloodlines.**
  - **Simulated genome:** a few dozen loci with recombination and mutation, so recessive bloodline traits can resurface.
  - Phenotype comes from genotype plus environment.
- **Needs and wants come in two layers:**
  - simulated drives (food, safety, belonging, status) that produce behaviour
  - an emergent story layer (want vs need, wound/flaw) exported for arcs
- **Mythic beings:** gods and immortals are agents, and their major canon deeds are pinned. Faith is a real force.
- **Realms:** Renascita only for now. The other realms are off-map sources of events and visitors.
- **Run budget:** overnight for a full run; minutes for a replay from a checkpoint.
- **The output is the graph:** truth, beliefs, knowledge, relationships, motivations and causes per individual. That graph is the context for novels and campaigns, and prose is generated from it.
- **Lux Faber verified:** it is the guild that forges Lux Lapis into materials for the **Vialux** (the vault's name for the Lux roads) and the empire's protections.
- **Proposed first spec (awaiting confirmation):** engine foundation + people:
  - scheduler and checkpoints, typed events with causes
  - genome and life cycle
  - notable/aggregate level of detail
  - a minimal belief layer
  - canon pins read from the vault
  - all on a hand-drawn Pyrosia place graph

  The map editor and the deeper epistemics follow as separate specs.

## Open questions (continue here)

- Confirm the first-spec framing above. (In session 1 the "epistemic slice" was picked first; the heart has since become people and bloodlines.)
- Map editor tech stack (web app? framework?) and the map data file format (git-friendly).
- Distortion-type formalism: confirm the "claims + framing" approach.

## Current renasci engine (reference)

- `src/renasci`: yearly `World.advance_year()` (`world.py:51`), `EventBus` (`events/base.py:7`), generators, `Person` / `House` dataclasses, `StatBlock` with `StatDelta` recorded per tick in `WorldContext`.
- `PersonView` (`person.py:14`) is a "what-if" projection pattern worth reusing for belief-projected views.
- There are no beliefs, trust, communication or goals in the engine today.
- It needs Python 3.12+, but the machine's default `python` is 3.7.10.
