"""History Engine backlog: milestones, labels and issues derived from the master spec v2.

Creates them on GitHub with the gh CLI. Idempotent: existing milestones, labels and issue titles are skipped.
Usage:  uv run --python 3.12 python notes/specs/backlog.py [--dry-run]
"""
import json
import subprocess
import sys
import time

REPO = "ABostrom/Renascitur"
SPEC = "notes/specs/2026-10-21-history-engine-design.md"

MILESTONES = {
    "M0": ("M0 Foundation", "S1 engine foundation + Observatory v0. Demo: toy run, ripple, replay, causal wave with zero unexplained divergences. Exit: determinism, replay equivalence, locality tests, benchmark baseline."),
    "M1": ("M1 The Fourth Age, lived", "Vault canon + casting, people & bloodlines, ambitions/actions/schemes, Stories page. Demo: 4A 1-250 with 8 Emperors and modern canon lineages; find a saga, what-if a latch point, promote an arc."),
    "M2": ("M2 Rumour and deception", "Full geography routing, epistemics, belief actions, world-knowledge views. Demo: the ward failure - a lie on the Vialux vs a witness racing a cover-up."),
    "M3": ("M3 Map and god's-eye loop", "Map editor + Inkarnate import, all ripple kinds, fork/compare, map by year. Exit: full loop with no code."),
    "M4": ("M4 Story layer", "Context packs, POV chronicles, canon checks, MCP server. Exit: schema-valid packs, >=90% canon-check recall, chronicle + campaign brief from one run."),
    "M5": ("M5 The First Age", "High fantasy + sci-fi: Solaran civilisation and technology, World Trees, Elder Races, gods and primordials as agents, the stars as an off-world realm, temporal LOD for 10,000 years, myth formation. Demo: full First Age run; canon holds; generated Solaran sagas survive as Fourth Age myths."),
    "M6": ("M6 Breadth", "Polities & war, crafts & objects, ecology & catastrophe - each with its own spec and exits."),
    "M7a": ("M7a Deep time: mechanics", "Third Age ruleset and run; handoffs between ages (ruins, artifacts, myths)."),
    "M7b": ("M7b Deep time: scale", "Second Age ruleset, full multi-age overnight run, scale-up and Rust/PyO3 where profiled."),
}

SUBS = {
    "S1": ("Engine foundation", "M0", "Calendar, scheduler, keyed RNG, causal ids, entity store, events/causes, run folders, checkpoints, recipes, rulesets, temporal-LOD interface, pin/casting/ripple skeletons, hinges, test harness.", "A toy ruleset with matching and a shared resource runs deterministically, replays equivalently from many checkpoints, has no unexplained divergence after a ripple, and honours toy pins.", []),
    "S2": ("Vault bridge", "M1", "Loader, note-type mapping, stable ids, pin extraction, feasibility, casting inputs, proposed-note writer.", "Fourth Age canon loads, passes feasibility and casts; a promoted event round-trips to canon: true.", ["S1"]),
    "S3": ("People & bloodlines", "M1", "Genome, life cycle, families, rendezvous marriage, houses & succession, relationship graph, drives, populations with LOD, 4A 1 scenario synthesis.", "The whole Fourth Age runs at M1 scale with conservation invariants and lineage pins met.", ["S1", "S2"]),
    "S4": ("World model & geography", "M1", "Minimal place/route format in M1; full routing, cell mesh and history-by-year in M2.", "Minimal: people move between Pyrosia places. Full: news travels by road.", ["S1"]),
    "S5": ("Map editor & Inkarnate import", "M3", "Web editor for places, routes, regions, terrain; Inkarnate import.", "Pyrosia fully edited and read by the sim.", ["S4"]),
    "S6": ("Epistemics", "M2", "Claims, belief stores, provenance, trust, drift, correction, aggregate beliefs, secret events and covers.", "The ward-failure scenario yields divergent, traceable beliefs.", ["S3", "S4"]),
    "S7": ("Ambitions, actions & schemes", "M1", "Ambition lifecycle, action classes + starter library, planner, schemes, hinges, story finder; belief actions in M2.", "Succession plots, intrigue and vengeance emerge from drives; every scheme step traces to its ambition.", ["S3"]),
    "S8": ("Polities & conflict", "M6", "Factions, offices, imperial succession politics, diplomacy, war, borders.", "Exit criteria defined in its spec.", ["S3", "S4", "S7"]),
    "S9": ("Work, crafts & objects", "M6", "Jobs, materials, crafting, trade, object biographies.", "The sword story emerges unscripted.", ["S3", "S4", "S7"]),
    "S10": ("Ecology & catastrophe", "M6", "Climate, harvests, disease, famine, aberrations/night terrors, Lux Lapis and wards.", "Kingdoms can fall to famine and plague through simulated causes.", ["S3", "S4"]),
    "S11": ("Mythic beings & faith", "M5", "Gods and immortals as agents, worship, faith as a force, divine ripple attribution.", "Pinned divine deeds hold; faith shifts belief and power.", ["S3", "S7"]),
    "S12": ("Story layer", "M4", "Context packs, POV chronicles, canon checks, MCP server.", "Schema-valid packs, >=90% canon-check recall, chronicle + campaign brief from one run.", ["S6", "S7"]),
    "S14": ("First Age ruleset", "M5", "Solaran civilisation and technology (research, inventions, colonies, schisms), World Trees, Elder Races, elemental/cosmic events, the stars as an abstract realm, First Age canon pins, myth formation for later ages.", "A full First Age run holds its canon within the overnight budget and produces promotable lore.", ["S3", "S6", "S7", "S11"]),
    "S13": ("Observatory", "M0", "SvelteKit driver/viewer: reads JSON Lines run folders directly, acts via `renasci serve`; grows v0-v6.", "Defined per milestone.", ["S1"]),
}

# (sub, milestone, kind, title, scope, acceptance, extra_labels)
T = []


def t(sub, ms, kind, title, scope, accept, ready=False):
    T.append(dict(sub=sub, ms=ms, kind=kind, title=title, scope=scope, accept=accept, ready=ready))


# ---------------------------------------------------------------- review / lore
t(None, "M0", "spec", "Review master spec v2", "Read the master spec and the roadmap page; raise changes before sub-project specs build on it.", ["Spec approved or change list recorded"], ready=True)
t(None, "M1", "lore", "Draft a dated Fourth Age timeline (Emperor reigns and key events)", "From the vault's Emperor and Firebrand notes, propose reign windows for Unimus..Octavian across 4A 1-250 and date key events (Schism, Night War, founding). Age-relative dates.", ["Draft timeline in notes/ for review", "Each Emperor has a reign window", "Corrections from Aaron applied"], ready=True)
t(None, "M1", "lore", "Propose lineages for modern canon characters", "For each modern canon character, propose parents/grandparents within their house (generated names where the vault is silent) so lineage pins can be cast.", ["Lineage draft per character in notes/", "Conflicts with existing notes flagged", "Aaron's corrections applied"], ready=True)
t(None, "M1", "lore", "Re-file or re-date the Psychic Schism note", "`History/Third Age/Psychic Schism.md` describes 4A 1. Move it to the Fourth Age or mark it as the boundary event.", ["Note filed consistently with 4A 1 = Schism"], ready=True)
t(None, "M7a", "lore", "Decide the Third Age's length", "Needed to turn age-relative dates into absolute years.", ["Third Age start/end years recorded in the vault"])
t(None, "M1", "lore", "Name the in-world calendar", "Months, seasons and dating convention to replace placeholder calendar names.", ["Calendar note in the vault", "Engine calendar config updated"])

# ---------------------------------------------------------------- spec & plan per sub-project
for s, (name, ms, *_rest) in SUBS.items():
    t(s, ms, "spec", f"{s} spec & implementation plan: {name}",
      f"Write the detailed sub-project spec for {s} ({name}) from the master spec, get it approved, then write its implementation plan. Generate/refresh the build tickets under this epic from the plan.",
      ["Spec in notes/specs/ approved", "Plan written", "Build tickets match plan tasks"], ready=(s == "S1"))

# ---------------------------------------------------------------- S1 (M0)
S1 = [
    ("Project scaffold: uv, Python 3.12, src layout, pytest; move prototype to renasci_legacy", "pyproject.toml (uv, py3.12), src/renasci/, tests/, pytest + hypothesis; move prototype to src/renasci_legacy/, delete setup.py, retire src/main.py.", ["`uv run pytest` passes on an empty suite", "Legacy code importable only as renasci_legacy"], True),
    ("Age-relative calendar and date types", "Dates like 4A 37 with months/days/seasons, configurable calendar, canonical tick (season), conversions and ordering.", ["Property tests for ordering and arithmetic", "Placeholder month/season names configurable"], False),
    ("Keyed RNG: Philox keys, local ordinals, canonical ticks, reshuffle salt", "rng(seed, system, entity, purpose, tick, ordinal) with locally derived ordinals; reshuffle-from-year salting.", ["Same key -> same draw across processes", "Changing time-step resolution does not change unrelated draws", "Reshuffle changes only draws at/after X"], False),
    ("Causal ids and entity store", "ids = hash(parent ids, creating event key, ordinal); vault ids for cast entities; columnar NumPy components + notable records; dormant records never deleted.", ["No global counters", "Adding an entity does not change other ids"], False),
    ("Multi-rate scheduler with total ordering", "Priority queue ordered by (time, priority, stable id, purpose); monthly/seasonal/yearly cadences; urgent follow-ups.", ["Insertion order never affects execution order (property test)"], False),
    ("Typed events: schema registry, causes, visibility, cause DAG queries", "Event types with schemas; participants by role; causes; source; public/secret visibility; why/what-next queries.", ["Cause DAG queries both directions", "Schemas versioned"], False),
    ("Run folder writer: JSON Lines tables and manifest", "manifest.json + JSON Lines (events, causes, participants, people, ambitions, schemes, beliefs, state_deltas, timeseries, hinges, stories), partitioned by age/segment.", ["Every table readable with jq", "Schema version in manifest"], False),
    ("Checkpoints and replay", "Checkpoint contents per spec 5.4; replay truncates the run folder at the high-water mark; version invalidation policy.", ["Replay from N positions equals the continuous run"], False),
    ("Run recipes (TOML) and CLI: run, replay, diff", "Recipe = engine version, seed, vault commit/pin hash, ripples, reshuffles. `renasci run|replay|diff`.", ["Recipe reproduces a run exactly", "diff reports changed entities and causal wave"], False),
    ("System registry, read-set declarations and ruleset switching", "Systems declare cadence and read-sets; rulesets enable systems/params per age and switch at boundaries.", ["Ruleset switch at a boundary is checkpointed"], False),
    ("Temporal LOD interface and focus windows", "Coarse/fine stepping, focus windows, promotion out of aggregates that skipped time (interface + toy implementation).", ["Focus window does not perturb draws outside it"], False),
    ("Rendezvous choice utility and hinge recording", "Min-hash selection for partners/targets/accomplices; hinge records (margin, stakes) for consequential draws.", ["Adding a non-winning candidate never changes the choice (property test)"], False),
    ("Pin director and casting skeletons", "Guard / steer-below-threshold / force / violated; canon-strain log; casting binds pins to entities.", ["Toy pins honoured", "Violated pins logged, run continues"], False),
    ("Ripple applier with in-world disguise hook", "protect, favour, inject to start; ripple ids as cause nodes; disguise callbacks per system.", ["Ripple appears in cause chains", "Disguised event emitted"], False),
    ("Determinism hazards: canonical hash, quantised floats, no set iteration, single-thread BLAS", "Canonical event serialisation and hash; lint/test guarding set iteration in sim code; BLAS threads = 1; versions in engine version.", ["Two runs produce byte-identical hashes"], False),
    ("Toy ruleset with matching and a shared resource; no-unexplained-divergence test", "A toy world that couples agents via matching and a shared resource; taint-tracking test comparing baseline vs ripple.", ["Zero unexplained divergences", "Test fails if greedy matching is used"], False),
    ("Benchmark harness: years/second and storage per run", "Benchmarks at fixed scales, results recorded over time.", ["Baseline recorded in repo"], False),
]
for title, scope, acc, ready in S1:
    t("S1", "M0", "build", title, scope, acc, ready)

# ---------------------------------------------------------------- S13 v0 (M0)
for title, scope, acc in [
    ("Observatory v0: SvelteKit scaffold, design tokens, open a run folder", "SvelteKit app; theme tokens (light/dark); load a run folder's JSON Lines + manifest in the browser.", ["Opens a run folder with no server", "Builds to a static page"]),
    ("Observatory v0: event browser", "Filter by type, place, salience, text; virtualised list.", ["Handles 100k+ events smoothly"]),
    ("Observatory v0: cause-chain explorer", "Why did this happen / what did it lead to, across events, pins and ripples.", ["Walks causes both ways from any event"]),
    ("Observatory v0: run diff and causal wave", "Compare two run folders; divergence per place over time; unexplained-divergence count.", ["Matches CLI diff output"]),
    ("`renasci serve` and launching runs/replays from the Observatory", "Local-only FastAPI: list runs, start run/replay from recipe, progress; Observatory enables actions when the server is up.", ["Read-only mode without server", "Run launched and opened from the UI"]),
]:
    t("S13", "M0", "build", title, scope, acc)

# ---------------------------------------------------------------- S2 (M1)
for title, scope, acc in [
    ("Vault loader: frontmatter, wikilinks, typed entities", "Walk docs/, parse frontmatter (22-type taxonomy), resolve [[wikilinks]] to entity references.", ["Loads the whole vault without errors", "Unresolved links reported"]),
    ("Note-type mapping: pins, claim seeds, ignored, draft opt-out", "event/character/house/faction/artifact -> pins; chronicle/myth/prophecy -> claim seeds; essays/indexes ignored; status: draft opts out.", ["Mapping table covered by tests"]),
    ("Stable `id:` for canon notes", "Assign ids to canon notes (one-off migration script, reviewed diff); new notes get ids on creation.", ["Every pinnable note has a unique id", "Renames do not break identity"]),
    ("Pin extraction: existence, lineage, event, ordering, succession, goal; vague dates", "Parse pins from notes, including windows, orderings and the 8-Emperor succession.", ["Fourth Age canon produces the expected pin set"]),
    ("Feasibility pass", "Ordering DAG + cycle detection, window intersection, lineage/genome satisfiability, out-of-scope classification.", ["Contradictory fixtures are reported, not crashed on"]),
    ("Casting: bind pins, place lineages, reserve births", "Bind pins to entities at run start, place pinned lineages into the initial state, binding log in the run folder.", ["Modern characters cast with their ancestry"]),
    ("Proposed-note writer with generated_hash and stale-proposal list", "Write `canon: proposed` notes; never overwrite edited notes; list stale proposals from superseded runs.", ["Promote round trip to canon: true", "Edited note is never overwritten"]),
]:
    t("S2", "M1", "build", title, scope, acc)

# ---------------------------------------------------------------- S3 (M1)
for title, scope, acc in [
    ("Genome: loci catalogue, alleles with origins, recombination, mutation, phenotype", "Compact genome with origin tracking for each allele; phenotype from genotype + environment.", ["Property tests for inheritance", "Recessive traits can resurface"]),
    ("Life cycle: birth, ageing, mortality", "Hazard models, keyed draws, guarded by the pin director.", ["Age structure plausible over 250 years"]),
    ("Families and marriage via rendezvous matching", "Eligibility, kin checks, cross-house matching, commoner spouses promoted from aggregates.", ["No greedy matching; locality test passes"]),
    ("Houses, heirs each generation, succession", "Heir assignment per generation; succession to children then siblings.", ["Every house has a defined line of succession"]),
    ("Relationship graph", "kin, spouse, friend, rival, patron, mentor, lover, enemy; strength and history; changed by events.", ["State as of any date reconstructable"]),
    ("Drives: food, safety, belonging, status", "Drive update rules from circumstances and events; logged as state deltas.", ["Drives visible as-of any date"]),
    ("Population aggregates per settlement", "Counts, age structure, allele frequencies, as NumPy arrays; seasonal update.", ["Vectorised; benchmarked"]),
    ("Promotion and demotion with conservation", "Keyed sampling from aggregates; dormant records; unknown-parent placeholders; never demote pinned or ambitious people.", ["Counts, age structure and allele frequencies conserved"]),
    ("Scenario synthesis at 4A 1 and provisional Fourth Age ruleset", "Post-Schism Pyrosia: synthesised population, cast canon, initial houses.", ["4A 1 state generated deterministically from canon + seed"]),
    ("Imperial office and the 8-Emperor succession", "Minimal imperial office whose holders follow the succession pin.", ["All eight Emperors reign in order in every run"]),
    ("M1 scale benchmark: whole Fourth Age in minutes", "Tens of thousands of people, 1k-5k notables, 4A 1-250.", ["Within budget; recorded"]),
]:
    t("S3", "M1", "build", title, scope, acc)

# ---------------------------------------------------------------- S4
t("S4", "M1", "build", "Minimal place/route/region format and hand-drawn Pyrosia graph", "Git-friendly format: places, routes (travel days, Vialux flag), regions; ~20-40 Pyrosia places.", ["Loaded by the sim and the Observatory"])
t("S4", "M1", "build", "Movement between places", "People travel and relocate along routes.", ["Travel times respected"])
for title, scope, acc in [
    ("Routing by mode, season, time of day and access", "Foot/horse/ship/army; seasonal closures; night danger; Vialux safety; access restrictions (e.g. the Stained).", ["Route costs match spec examples (e.g. Lux road span ~8-9 weeks on foot)"]),
    ("News travels by route", "Claims move with travellers along routes; official line on the Vialux, rumours on wild roads.", ["Arrival delays follow route costs"]),
    ("Voronoi cell mesh world model", "Cell mesh shared by sim and editor; terrain per cell.", ["Pyrosia mesh generated from the map"]),
    ("Map history by year", "Settlements, roads and borders change over time and can be queried by year.", ["Map state as of any year"]),
]:
    t("S4", "M2", "build", title, scope, acc)

# ---------------------------------------------------------------- S5 (M3)
for title, scope, acc in [
    ("Inkarnate import: coastline trace and settlement markers", "Trace coastlines from images/Renascitur.png; detect square settlement markers.", ["Pyrosia coastline and ~15 markers imported"]),
    ("Claude-drafted places, regions and routes from the map image", "Draft provinces, biomes, roads for correction in the editor.", ["Draft layer loads in the editor"]),
    ("Map editor: places and routes", "Create/edit/delete places and routes with attributes.", ["Edits saved in the git-friendly format"]),
    ("Map editor: regions and terrain painting", "Paint regions and terrain on the cell mesh.", ["Painted regions read by the sim"]),
]:
    t("S5", "M3", "build", title, scope, acc)

# ---------------------------------------------------------------- S6 (M2)
for title, scope, acc in [
    ("Claims and belief stores", "Claims with truth status and framing; a lie is a false claim plus intent; per-mind belief stores with confidence.", ["Truth and belief never collapse"]),
    ("Provenance, trust and propagation with drift and confirmation bias", "Who told whom when; trust by relationship; competing beliefs; drift lineage.", ["Every belief traces to its origin"]),
    ("Aggregate belief distributions", "Population-level belief shares per place, fed by notables and arriving news.", ["Vectorised; conserved"]),
    ("Secret events and public covers", "Visibility rules; who learns the truth and how.", ["A poisoning stays secret unless exposed"]),
    ("Ward failure golden scenario (scripted injection)", "Sabotage, guild lie, witness, cover-up, all traceable.", ["Golden test passes"]),
]:
    t("S6", "M2", "build", title, scope, acc)

# ---------------------------------------------------------------- S7
for title, scope, acc in [
    ("Ambition lifecycle records", "Formed -> pursued -> fulfilled/thwarted/abandoned/died unfulfilled; causes; cooldowns.", ["Death resolves active ambitions as died unfulfilled"]),
    ("Action class interface and starter library", "preconditions/effects/odds/secrecy/duration/flavour; recruit, bribe, petition, court favour, arrange marriage, poison, duel, assassinate, flee, confess.", ["Adding an action needs only a new class"]),
    ("Planner: bounded HTN/GOAP over the action library", "Goal-directed plans bounded by wits and knowledge; plans stored as data.", ["Plans reproducible and explainable"]),
    ("Schemes: accomplices, progress, exposure, outcomes", "Multi-step schemes with recruitment and exposure risk per secret step.", ["Every scheme step traces to its ambition"]),
    ("Want / need / wound layer", "Emergent story layer from wounds, unmet needs and false beliefs.", ["Visible as-of any date"]),
    ("Hinges and latch points", "Record margins; rank died-unfulfilled and near misses with suggested ripples.", ["Top latch points re-runnable as what-ifs"]),
    ("Story finder: arcs, sagas with sub-arc splitting, salience, period queries", "Arcs from ambitions, sagas from shared events/targets, salience, 'what flows through 4A X-Y'.", ["No saga swallows a whole house; titles generated"]),
]:
    t("S7", "M1", "build", title, scope, acc)
t("S7", "M2", "build", "Belief actions: slander, frame, forge a letter, spread a rumour, bear witness", "Actions that create or move claims, making deception a scheming tool.", ["Schemes use deception; provenance intact"])

# ---------------------------------------------------------------- S13 v1-v6
for ms, title, scope, acc in [
    ("M1", "Observatory: Stories page - period selector and story river", "Ambitions as bars by house over any period, outcome glyphs, turning-point events.", ["Period presets and custom ranges"]),
    ("M1", "Observatory: sagas, arcs and beats", "Saga list, arc detail with what it was born of, scheme progress, beats.", ["Navigable to people and events"]),
    ("M1", "Observatory: latch points, what-if launcher and side-by-side diff", "Pick a latch point, adjust the ripple, replay via serve, compare outcomes.", ["What-if result viewable next to baseline"]),
    ("M1", "Observatory: individual page", "Genome with allele origins, family tree, inner life as of a date, ambitions ledger, relationship web, life events.", ["Every person in a run renders"]),
    ("M1", "Observatory: house pages and population charts", "Houses over time; population by place.", ["Charts readable in both themes"]),
    ("M1", "Observatory: canon-strain report", "Guards, steers, forces, violations, out-of-scope pins.", ["Every strain entry links to its event"]),
    ("M1", "Observatory: promote flow with event-cause selection", "Choose an arc/event, tick causes to keep, write proposed notes via serve.", ["Proposed note appears in the vault"]),
    ("M2", "Observatory: world knowledge - truth vs belief, claim lineage, spread maps", "Epistemic views over a run.", ["Truth and belief side by side"]),
    ("M2", "Observatory: beliefs with provenance and motivation traces", "Person beliefs with provenance; want -> belief -> origin.", ["Trace reaches the originating event or lie"]),
    ("M3", "Observatory: map by year", "Borders, settlements, ruins, spreading events on the map with a year slider.", ["Uses the S4 history-by-year model"]),
    ("M3", "Observatory: object biographies", "Every object's events and owners.", ["Sword-style biographies render"]),
    ("M3", "Observatory: ripple authoring, fork/compare and branch management", "Ripple panel on every page; multiple branches compared.", ["Full loop without code"]),
    ("M4", "Observatory: context-pack builder and canon-check reports", "Build packs from any saga/arc; view canon-check results.", ["Pack exported and validated"]),
    ("M5", "Observatory v5: technology timeline, civilisation map by millennium, focus windows, myth lineage", "First Age views: research and inventions over time, civilisations by millennium, focus-window controls, event -> myth -> later belief.", ["A Solaran invention traced from research to myth"]),
    ("M7a", "Observatory: age-spanning timeline, ruin and artifact tracing, run-cost dashboard", "Deep-time views.", ["Traces an object across ages"]),
]:
    t("S13", ms, "build", title, scope, acc)

t("S1", "M3", "build", "All ripple kinds and reshuffle from year X", "doom, luck, plant, structural; reshuffle salting; disguise per kind.", ["Each kind has a golden test"])

# ---------------------------------------------------------------- S12 (M4)
for title, scope, acc in [
    ("Context pack schema and builder", "POV-specific bundles of truth, beliefs, causes and wants for an arc or saga.", ["Schema-valid packs"]),
    ("POV chronicles: the victor's account vs the truth", "In-world chronicles written from a faction's beliefs.", ["Chronicle diverges from truth where beliefs do"]),
    ("Canon checks with a seeded-contradiction benchmark", "Check generated prose against the truth graph.", [">=90% recall on seeded contradictions"]),
    ("MCP server over runs and the vault", "Query runs, arcs, people, beliefs; fetch context packs.", ["Usable from Claude"]),
    ("Campaign brief generator", "Template: saga, factions, NPCs with wants, hooks.", ["Brief generated from one run"]),
]:
    t("S12", "M4", "build", title, scope, acc)

# ---------------------------------------------------------------- M5 breadth
for s, items in {
    "S8": [("Factions and offices", "Factions, offices and their holders."), ("Diplomacy", "Alliances, treaties, betrayals."), ("War and borders", "Campaigns, battles, shifting borders on the map.")],
    "S9": [("Jobs and skills", "Occupations and skill growth."), ("Materials and crafting", "Materials, crafting, masterworks."), ("Trade", "Goods flowing along routes."), ("Object biographies", "Objects gather deeds, owners and losses.")],
    "S10": [("Climate and harvests", "Seasonal climate driving harvests."), ("Disease", "Transmission along routes and in settlements."), ("Famine", "Food shortage dynamics."), ("Aberrations, night terrors, Lux Lapis and wards", "Night danger, wards, ward failures.")],
    "S11": [("Deity and immortal agents", "Gods and immortals with minds and goals."), ("Worship and faith as a force", "Faith feeds or drains divine power."), ("Divine attribution of ripples", "Ripples attributed to deities or omens in-world.")],
}.items():
    for title, scope in items:
        t(s, "M5" if s == "S11" else "M6", "build", f"{SUBS[s][0]}: {title}", scope, ["Meets the exit criteria in the sub-project spec"])

# ---------------------------------------------------------------- M6
for ms, title, scope in [
    ("M5", "Temporal LOD tuning and focus windows at scale", "Coarse quiet millennia, fine focus windows, budgets for a 10,000-year age."),
    ("M7a", "Third Age ruleset and run", "Fill the sparse Third Age."),
    ("M7a", "Handoffs between ages: ruins, artifacts, myths", "State that persists across age boundaries (First->Second->Third->Fourth)."),
    ("M7b", "Second Age ruleset", "Arcanometry, the Forge Wars, Vecna, multi-realm conflict."),
    ("M7b", "Full multi-age overnight run", "All ages, all canon pins, within the overnight budget."),
    ("M7b", "Profiling and Rust/PyO3 hot paths", "Move profiled hot paths behind existing interfaces."),
]:
    t("S1", ms, "build", title, scope, ["Within budget; canon pins hold"])


# ---------------------------------------------------------------- S14 First Age (M5)
for title, scope, acc in [
    ("First Age canon audit and pins", "Turn the First Age history notes (Creation, World Trees, Elder Races blessed, Solaran research, Endless Sun built and fallen, Solarans reach the stars, Collapse of Solara, Syuul created and imprisoned, Ishna awakens and corrupts, Muradin's pilgrimage and communion, Founding of Runehart, Golden Age of Harmony) into dated or ordered pins.", ["Every First Age note mapped to a pin, claim seed or out-of-scope"]),
    ("Solaran technology system: research, inventions, diffusion", "Research programmes, inventions with prerequisites, diffusion and loss; technology as a driver of ambitions and schemes.", ["Inventions emerge with causes; tech can be lost in collapses"]),
    ("Civilisation-scale polities for the First Age", "Solaran civilisation(s), colonies, Elder Race realms at coarse LOD; schisms and wars between them.", ["Polities form, split and fall over millennia"]),
    ("World Trees and the Elder Races", "World Trees as entities that bless races and anchor realms; the Elder Races' relationship to them.", ["Canon blessings hold; generated groves and wardens emerge"]),
    ("Elemental and cosmic events", "Communion with the elements, celestial events, cosmic-scale catastrophes as structural events.", ["Cosmic events cascade into history with causes"]),
    ("The stars as an abstract off-world realm", "Off-world place graph for the Solaran reach into the stars: colonies, voyages, losses.", ["Voyages and colonies recorded without a hand-drawn map"]),
    ("Myth formation: First Age events become later-age myths", "Events decay into myths and claim seeds with drift over millennia, inherited by later ages' cultures.", ["A Fourth Age belief traces back to a First Age event"]),
    ("First Age golden scenario: rise and fall of the Endless Sun", "Golden test: the Endless Sun is constructed and falls with generated causes and actors, canon intact.", ["Golden test passes"]),
]:
    t("S14", "M5", "build", title, scope, acc)
t(None, "M5", "lore", "First Age lore brief: what to generate", "Aaron's brief for the First Age: tone (high fantasy + sci-fi), what the sim should invent (Solaran colonies, technologies, factions, heroes, catastrophes), what must stay mythic or unknowable, and which First Age questions the sim should answer.", ["Brief in the vault or notes/", "Feeds the S14 spec"], ready=True)
t(None, "M5", "lore", "Solaran technology vocabulary", "A starter list of Solaran technologies, materials and sciences (and their fantasy/sci-fi flavour) for the technology system to combine.", ["Vocabulary note with prerequisites sketched"])

# ================================================================ GitHub
def gh(*args, data=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", input=data)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def api(method, path, payload=None):
    out = gh("api", "-X", method, f"repos/{REPO}/{path}", "--input", "-", data=json.dumps(payload or {})) if payload is not None else gh("api", "-X", method, f"repos/{REPO}/{path}")
    return json.loads(out) if out.strip() else None


def body_for(x, epic_no=None):
    lines = []
    if epic_no:
        lines.append(f"Part of #{epic_no}.\n")
    lines.append(x["scope"] + "\n")
    lines.append("**Acceptance**")
    lines += [f"- [ ] {a}" for a in x["accept"]]
    lines.append(f"\nSpec: `{SPEC}`")
    return "\n".join(lines)


def main(dry):
    labels = {s: "1f6feb" for s in SUBS} | {"epic": "5319e7", "spec": "fbca04", "plan": "fbca04", "build": "0e8a16", "lore": "b60205", "ready": "2ea043", "blocked": "d93f0b"}
    total = len(SUBS) + len(T)
    print(f"{len(MILESTONES)} milestones, {len(labels)} labels, {total} issues ({len(SUBS)} epics)")
    if dry:
        for x in T:
            print(f"  [{x['ms']}] {x['sub'] or '-'} {x['kind']}: {x['title']}")
        return
    existing_labels = {l["name"] for l in json.loads(gh("label", "list", "--repo", REPO, "--limit", "200", "--json", "name"))}
    for name, color in labels.items():
        if name not in existing_labels:
            gh("label", "create", name, "--repo", REPO, "--color", color)
    ms_no = {m["title"]: m["number"] for m in api("GET", "milestones?state=all&per_page=100")}
    for key, (title, desc) in MILESTONES.items():
        if title not in ms_no:
            ms_no[title] = api("POST", "milestones", dict(title=title, description=desc))["number"]
    existing = {}
    page = 1
    while True:
        batch = api("GET", f"issues?state=all&per_page=100&page={page}")
        if not batch:
            break
        existing.update({i["title"]: i for i in batch if "pull_request" not in i})
        page += 1

    def create(title, body, labels_, ms_key):
        if title in existing:
            return existing[title]
        issue = api("POST", "issues", dict(title=title, body=body, labels=labels_, milestone=ms_no[MILESTONES[ms_key][0]]))
        existing[title] = issue
        print(f"  #{issue['number']} {title}")
        time.sleep(2.5)  # stay under GitHub's content-creation rate limits
        return issue

    epics = {}
    for s, (name, ms, scope, done, deps) in SUBS.items():
        body = f"{scope}\n\n**Done when:** {done}\n\n**Depends on:** {', '.join(deps) or 'nothing'}\n\nSpec: `{SPEC}` (sub-project {s})"
        epics[s] = create(f"[Epic] {s} {name}", body, ["epic", s], ms)
    for x in T:
        epic = epics.get(x["sub"])
        labels_ = [x["kind"]] + ([x["sub"]] if x["sub"] else []) + (["ready"] if x["ready"] else [])
        issue = create(x["title"], body_for(x, epic["number"] if epic else None), labels_, x["ms"])
        if epic and not x.get("_linked"):
            try:
                api("POST", f"issues/{epic['number']}/sub_issues", dict(sub_issue_id=issue["id"]))
            except RuntimeError as e:
                if "already" not in str(e).lower() and "duplicate" not in str(e).lower():
                    print(f"    (sub-issue link failed: {e})")
    print("done")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
