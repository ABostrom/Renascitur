# Renascitur — Refactor & Tidy-Up Design Options

*Companion to `working-model.md`. This document lays out the realistic options for big systemic tidy-up, in enough detail that you can compare them honestly. It is not a committed plan — final direction is still subject to your choice.*

*Direction confirmed: Approach A (Typed Vault). Revised 2026-05-18 to reflect the Tolkien-esque, history-first worldbuilding philosophy.*

---

## Confirmed priorities (from brainstorming)

These guide every option below:

1. **Lore vault is the primary refactor target.** The Python lib (`renasci`) is a "for fun, someday" side-project — touched only in the long-term backlog. (But see §Tolkien below — the sim's role may grow.)
2. **Obsidian-first ergonomics over published-site ergonomics.** The MkDocs site is secondary; "not broken" is enough.
3. **All four navigation modes must work**: folder tree, quick-switcher, wikilink graph, tags / Dataview / AI. Frontmatter and templates therefore have the highest leverage.
4. **Campaign-running needs**: fast NPC stat-block lookup, faction/location summary cards, session-prep assembly. Canon-vs-campaign-state separation is not yet a priority.
5. **Strictness**: templates *strongly encouraged* for typed reference notes; long-form prose stays free.
6. **Execution shape**: one big-ish initial refactor pass to establish the system, then incremental work on a long-term backlog.
7. **Authorial philosophy**: **Tolkien-esque breadth and depth of history.** **Build the world history first; then write stories inside it.** This means History is not "one section among many" — it is the spine of the world, and every other section ultimately references it. The other taxonomy decisions are downstream of this.

---

## Approach A — "Typed Vault" *(recommended, revised for Tolkien-esque + history-first)*

The premise: every reference note becomes formally typed (`type: continent`, `type: event`, `type: chronicle`, …) with templated structure and required frontmatter. Free-prose essays remain exempt. The frontmatter is treated as a small relational graph — not just for filtering, but for declaring connections (a continent's rivers, an event's chronicled sources, a house's lineage). This unlocks Dataview queries, tag filtering, AI navigation, and reliable site nav simultaneously, and gives the Tolkien-esque history a queryable backbone.

### A.0 The pattern you already started

Your existing continent files (Arcturia, Pyrosia, Mokoweri, Qethusiyya, Thundrakar, Uftine) already use **relational frontmatter** as a small graph database:

```yaml
type: continent
terrain: [mountains, glaciers, evergreen forests, frozen tundra]
inhabited_by: ["[[Uftine Human]]", "[[Icebound|Icebound Dwarves]]"]
provinces: ["[[Aurora Forest]]", "[[Calderian Mountains]]", ...]
cities: ["[[Uftine]]", "[[Runehart]]"]
mountains: ["[[Calderian Peaks]]", "[[Thornback Ridge]]", "[[Wyrmspine Mountains]]"]
rivers: ["[[Tharic Runoff]]", "[[Icevein River]]"]
```

This is exactly the right shape. The refactor's job is to **finish what you started** — propagate the pattern down to the leaves (rivers, mountains, cities, locations have no frontmatter today, only the continent does), and extend the pattern across all the other categories of note. The type taxonomy below is designed to match what you're already doing.

### A.1 Note-type taxonomy (revised — ~22 types in 6 groups)

A larger but tightly-grouped vocabulary. Granular types make Dataview queries write themselves and match the folder-typing you already use.

#### Geography (6 types)
| `type:`        | Folder cue                       | Examples |
|----------------|----------------------------------|----------|
| `continent`    | `Geography/<Name>/<Name>.md`     | Arcturia, Pyrosia, Mokoweri |
| `region`       | `Geography/<C>/Provinces/`       | Ashen Plains, Khalgar, Misty Shores |
| `settlement`   | `Geography/<C>/Cities/`          | Eltabarr, Draumhavn, Aeloria |
| `landmark`     | `Geography/<C>/Locations/`       | Salt Cradle, Eversoul Grove, Crystalward Gate |
| `waterway`     | `Geography/<C>/Rivers/`          | Icevein River, Tharic Runoff |
| `range`        | `Geography/<C>/Mountains/`       | Wyrmspine Mountains, Obsidian Spine |

`settlement` carries a `size:` field (`hamlet`/`village`/`town`/`city`/`great-city`/`hold`) so it covers the full settlement scale. Sub-locations *inside* a city (districts, named buildings) are `landmark` with `inside: "[[City Name]]"`.

#### People & groups (6 types)
| `type:`        | Examples |
|----------------|----------|
| `character`    | Drezna Ironmaul, Arthur Denison, Esravash, Muradin |
| `race`         | Solaran, Saurian, Grundthain, Elasi, Kyojin (biological/mythic lineage) |
| `culture`      | Tidebound, Rahalan, Firebrand, Thraysian (distinct from race — multiple races may share a culture) |
| `faction`      | Firebrand Empire, Weavers of Agony, Blackiron Collective |
| `house`        | Clan Brinevein, House Lyrandar (dynastic lineage — feeds from the Python sim eventually) |
| `organisation` | Athenaeum of Arcane Arts and Sciences, Lux Faber Guild |

The `race` ≠ `culture` split matters for Tolkien-esque depth: the Tidebound are a culture; the Dwarves are a race; you can be a Tidebound Dwarf, a Tidebound Human exile, etc.

#### Time & history (4 types) — the spine
| `type:`        | Examples |
|----------------|----------|
| `era`          | First Age, Second Age, Third Age, Fourth Age (and any named sub-ages) |
| `event`        | Hexweave Binding, Collapse of Solara, Founding of Runehart |
| `myth`         | The Creation of the World (when it's narrated as myth rather than history) |
| `chronicle`    | Archive of the Ancients (Solaran), Tideforging Manuscripts, Ferrun Codex — **in-world source texts** |

The `event` vs `myth` distinction is the Tolkien move: the same occurrence may have a sober historical account *and* a mythic version told by a different culture. Both can exist with cross-links.

`chronicle` is the most important addition: in-world manuscripts that *are* the lore (the Archive of the Ancients piece is a chronicle). They have `attributed-to:`, `era:`, `housed-in:` fields. Stories you write later can be `chronicle` entries too — "found in the Eltabarr archives".

#### Things & technology (4 types)
| `type:`        | Examples |
|----------------|----------|
| `artifact`     | Anvil of Eternity, Time Piece of Travel (legendary, named, often singular) |
| `item`         | mundane or lesser magical objects |
| `resource`     | Skyforged Steel, Skyshatter Ore, Storm Quartz (substances/materials) |
| `technology`   | Arcanometry, Vialux tech, Tideforging-the-technique (knowledge/techniques) |

#### Concepts (4 types)
| `type:`        | Examples |
|----------------|----------|
| `deity`        | Morbus, Noxarian, Hyperion, Muradin |
| `cosmic-force` | Concorda, Specular, Luminis, Entropy (abstract forces, not anthropomorphic) |
| `tradition`    | Tideforging-the-ritual, Mokoweri Ancestor Rites |
| `language`     | Elemental Tongue, Ancient Solaran, Thaysian Common |

#### Meta (2 types)
| `type:`        | Examples |
|----------------|----------|
| `essay`        | Author-voice meta-lore commentary. Free-prose. Required only `type`, `topic`, `status`. |
| `index`        | Dataview-driven dashboards in `_meta/` (Stub Backlog, NPCs by Faction, Timeline). |

**Notes on the design:**
- `status` is universal across every type: `stub` | `draft` | `canon` | `archived`. The default for new notes is `draft`.
- `tags:` stays free-form on top of the controlled `type:`.
- Most types carry an `era:` field — even geography. A city founded in the Second Age and abandoned in the Third has `founded-in: "[[Second Age]]"`, `lost-in: "[[Third Age]]"`. This is what makes history the spine.
- Every link inside frontmatter uses `"[[Name]]"` quoted-wikilink syntax (Obsidian renders this in the Bases / Dataview panes natively, and you already do this on Arcturia).

### A.2a Canonical Age names and the reckoning convention

*Decided 2026-05-18.* The four Ages get flavor names that double as the dating reckoning. Filename prefix applies to `event` and `chronicle` notes only (history-spine). All other types stay clean.

| Age          | Canonical name              | Code | Folder                              | Year display | Filename prefix example |
|--------------|-----------------------------|------|-------------------------------------|--------------|-------------------------|
| First Age    | **Age of the Endless Sun**  | `ES` | `History/Age of the Endless Sun/`   | `ES 0412`    | `ES0412 <Title>.md`     |
| Second Age   | **Age of Forging**          | `AF` | `History/Age of Forging/`           | `AF 0412`    | `AF0412 <Title>.md`     |
| Third Age    | **Age of Stagnation**       | `AS` | `History/Age of Stagnation/`        | `AS 0412`    | `AS0412 <Title>.md`     |
| Fourth Age   | **Age of Night**            | `AN` | `History/Age of Night/`             | `AN 0412`    | `AN0412 <Title>.md`     |

**Arc** *(emergent property of the chosen names)*: ascendance → active building → long decline → present struggle. Worth preserving in the `era` summary pages.

**Rules:**
- Year is **zero-padded to 4 digits** in the filename prefix (`AF0412`) for filesystem-correct sort. In prose and `year-display:` it's unpadded (`AF 412`).
- Folder rename happens once as part of the initial pass; Obsidian's `alwaysUpdateLinks: true` (already enabled) preserves existing wikilinks. Old names ("First Age", "Second Age", ...) are added as `aliases:` on each era page so `[[Second Age]]` still resolves.
- The frontmatter field `era:` always links the **flavor name**, not the old numeric name: `era: "[[Age of Forging]]"`.
- Year `0` is reserved for "undated within the era." `pre-`/`post-` prefixes (e.g., `pre-AS`) for events whose exact era is uncertain.
- **Multi-culture reckonings (Tolkien bonus)** — the schema is *receptive* to optional `reckonings:` map (Saurian / Dwarven / Firebrand etc.) added in a later phase. Not required now.

### A.2 Frontmatter schema (canonical examples)

A `character`:
```yaml
---
type: character
status: canon
tags: [tidebound, dwarves, draumhavn, smith]
race: "[[Dwarf]]"
culture: "[[Tidebound]]"
affiliation: "[[Clan Brinevein]]"
location: "[[Draumhavn]]"
era: "[[Third Age]]"
aliases: [Dag, Thorne]
created: 2024-08-12
updated: 2026-05-18
---
```

An `event` (the spine of the world):
```yaml
---
type: event
status: canon
tags: [forge-wars, runehart, muradin]
era: "[[Second Age]]"
year: "S.A. 412"     # in-world dating
location: "[[Runehart]]"
participants: ["[[Muradin]]", "[[Typhon, The Archon of Death]]"]
caused-by: ["[[Vecna's Descent Begins]]"]
caused: ["[[Collapse of Runehart]]", "[[Muradin's Ascension]]"]
chronicled-in: ["[[The Anvil Scriptures]]", "[[Annals of the Grundthain]]"]
---
```

A `chronicle` (an in-world source text):
```yaml
---
type: chronicle
status: canon
tags: [solaran, archive-of-the-ancients]
attributed-to: "[[Aeloria Elder Council]]"
era-of-composition: "[[Second Age]]"
housed-in: "[[Aeloria]]"
records: ["[[Fall of the Endless Sun]]", "[[Creation of the Saurians]]"]
---
```

`status: stub` files have *only* the required frontmatter and the title. They are valid, queryable, and listed in the backlog index.

### A.3 Templates to write or rewrite

The template set is reorganised to mirror the 22-type taxonomy. Older templates (City, NPC, Faction, Organisation, Item, PointOfInterest) are folded into the new set with consistent schema. Each new template has a one-line description of what the type is *for*, so authoring decisions are easy.

| Template            | Status         | Action |
|---------------------|----------------|--------|
| **Geography**       |                | |
| `Continent.md`      | new            | New — match the existing Arcturia-style relational frontmatter |
| `Region.md`         | new            | Province / political-geographic subdivision |
| `Settlement.md`     | replaces City  | Carries `size:` field (hamlet → great-city → hold) |
| `Landmark.md`       | replaces POI   | POI, ruin, named site, in-city district |
| `Waterway.md`       | new            | River, lake, sea, coast |
| `Range.md`          | new            | Mountain range or named peak |
| **People & groups** |                | |
| `Character.md`      | replaces NPC   | Any named figure — NPC, hero, villain, deceased |
| `Race.md`           | new            | Biological/mythic lineage |
| `Culture.md`        | new            | Distinct from race (Tidebound, Rahalan, …) |
| `Faction.md`        | exists         | Rewrite to enforce schema |
| `House.md`          | new            | Dynastic lineage — frontmatter ready for sim-generated genealogy |
| `Organisation.md`   | exists         | Rewrite to enforce schema |
| **Time & history**  |                | |
| `Era.md`            | new            | Named Age, with overview + key events list |
| `Event.md`          | new            | Discrete historical occurrence |
| `Myth.md`           | new            | Mythic counterpart of event or pre-historical narrative |
| `Chronicle.md`      | new            | In-world source text — the Tolkien specialty |
| **Things**          |                | |
| `Artifact.md`       | new            | Legendary, named, often singular item |
| `Item.md`           | exists         | Rewrite — for lesser/non-legendary items |
| `Resource.md`       | new            | Substance / material |
| `Technology.md`     | new            | Technique or invention |
| **Concepts**        |                | |
| `Deity.md`          | new            | God or cosmic entity |
| `CosmicForce.md`    | new            | Abstract force (Concorda, Entropy, …) |
| `Tradition.md`      | new            | Ritual or practice |
| `Language.md`       | new            | Includes etymology, phonology, sample text, script |
| **Meta**            |                | |
| `Essay.md`          | new            | Free-prose author commentary |

Adopt the **Templater** community plugin so templates can pre-fill `created:` date, sluggify the title, prompt for required fields on creation, and auto-suggest `era:` and `realm:` from the file's folder location.

### A.4 Folder hygiene (surgical, not wholesale)

Keep the existing top-level taxonomy (`Cosmology/`, `History/`, `Realms/`, `Races/`, `Languages/`, `Story/`). Apply only these fixes:

1. **Create missing race summary files** at the parent level so the folder isn't bare:
   - `Races/Humans/Elasi/Elasi.md`
   - `Races/Humans/Terran/Terran.md`
   - `Races/Kyojin/Leonin/Leonin.md`
   - `Races/Kyojin/Orcs/Orcs.md`
   - `Races/Grundthains/Dwarves/Dwarves.md`
2. **Decide fate of the 7 single-file realm stubs** (Solirion, Nihilum, Thargrun, Veltharyn, Woudum, Sigmora, Infernum, Imperium). Two reasonable choices:
   - **Collapse** into a single `Cosmology/Planes/Outer Planes.md` reference, deleting the individual stub folders.
   - **Promote**: each becomes a folder with at least a one-screen summary file. Defer to backlog.
   - Recommended in the initial pass: collapse for now, promote later if any realm earns deeper treatment.
3. **Resolve `Factions/` vs `Societies/` ambiguity** in Renascita: define `Societies/` = cultures / polities (in-world ethnic or political identities), `Factions/` = organised groups with agendas (cults, secret orders). Move the Blackiron Collective duplicate content into one canonical home.
4. **Add `_meta/`** at the docs root for conventions, indices, and stub backlog (see §A.6). Underscore-prefix keeps it sorted to top.

No top-level reshape. No mass file movement.

### A.5 Stubs handling

86 fully-empty + ~83 nearly-empty markdown files. Strategy:

1. **Bulk-set frontmatter** `type: <inferred>` + `status: stub` on every stub. Type is inferred from folder (e.g., notes under `…/Characters/` get `type: npc`, under `…/Locations/` get `type: location`).
2. **No deletions** in the initial pass — they encode authorial intent.
3. **Generate `_meta/Stub Backlog.md`** as a Dataview table listing every stub by type + folder, so you can see "all the holes" at a glance.

This converts the 169 stubs from clutter into an honest, navigable to-do list.

### A.6 Dataview index pages

Create `_meta/` with these auto-generated dashboards:

| Page                        | Query |
|-----------------------------|-------|
| `Stub Backlog.md`           | All files where `status = stub`, grouped by `type` |
| `NPCs by Faction.md`        | All `type: npc`, grouped by `affiliation` |
| `Locations by Realm.md`     | All `type: location`, grouped by `realm` |
| `Factions of Renascita.md`  | All `type: faction` with `realm: Renascita` |
| `Campaign Reference.md`     | Quick links — most-used factions, recent NPCs, "fast lookup" panel for sessions |
| `Conventions.md`            | Plain-prose doc describing the type taxonomy, frontmatter schema, and templates |

### A.7 Obsidian config changes

- Install **Templater**.
- Configure **obsidian-linter** with rules: require `type` and `status` keys on non-`essay` notes; require `tags` to be a list; normalise YAML.
- Update `.obsidian/templates.json` to point at the rewritten template set.
- Consider an `obsidian-projects` or **Bases**-driven dashboard as an alternative to Dataview for the indices (Bases is already enabled).

### A.8 MkDocs minimal fix

- Add an explicit `nav:` listing the top-level sections only (no need to enumerate every file).
- Stop installing the unused `mkdocs-ezlinks-plugin` in CI.
- Optionally: add a build-time wikilink-validity check (e.g., `mkdocs --strict` or a custom hook). Deferred to backlog.

### A.9 What lands in the initial pass vs the backlog

**Hard rule for the initial pass: PURE STRUCTURAL WORK, NO CONTENT DRAFTING.** Past attempts at this refactor stalled because manual typing/authoring drained motivation. The initial pass is "I prepare the work in a branch; you review and merge." Your hands-on time is review only — no typing YAML, no writing prose. All creative authorship is preserved for whenever inspiration strikes, into a system that's already ready.

**Initial pass (mechanical, AI-prepared, one branch):**
- Define and document the type taxonomy and frontmatter schema in `_meta/Conventions.md`.
- Write all 23 templates.
- Install Templater plugin config, update obsidian-linter rules.
- **Bulk script: infer `type:` from folder path and write frontmatter into every `.md` under `docs/`.** Aaron reviews the inference rules (~12 lines: "files in folder X get type Y") before the script runs. Stub-sized files additionally get `status: stub`; non-stubs get `status: draft`.
- **Bulk script: add `era:` field** to every file under `History/<age>/` based on its folder, using the canonical Age names.
- **Folder renames:** `Third Age` → `Age of Stagnation`, etc. for all four Ages. Old names added as aliases on era summary files.
- **File renames:** history events get `<CODE><YYYY> ` prefix where year is recoverable from prose or frontmatter; default `<CODE>0000` for undated. `aliases:` preserves wikilink ergonomics.
- **Create missing skeleton files** (no body content):
  - Race parent summaries: Elasi.md, Terran.md, Leonin.md, Orcs.md, Dwarves.md
  - Promoted realm folders: each single-file plane gets its own folder with a skeleton summary
  - Four era summary pages (one per Age) — frontmatter only, body empty
  - Heavy-impact event stubs (Hexweave Binding, Forge Wars, Breaking of the Hexweave Seal, Machinery of Death) get a `status: stub` frontmatter shell — body stays empty
- Create `_meta/` with Conventions.md, Stub Backlog.md, NPCs by Faction.md, Locations by Realm.md, Factions of Renascita.md, Campaign Reference.md (Dataview-driven; populates from frontmatter).
- Minimal `mkdocs.yml` patch (explicit top-level nav, remove unused ezlinks).

**Explicitly NOT in the initial pass:**
- No prose drafting (era summaries, event content, faction overviews — all of it).
- No content judgement calls beyond the type-inference rule sheet.
- No manual per-file authorship by Aaron.

**Long-term backlog** — see §4 below. Backlog work happens organically, at Aaron's pace, into the structure the initial pass establishes. No deadline.

### Trade-offs
- ✅ Unlocks all four navigation modes at once
- ✅ Honors the "strict for reference, free for prose" preference
- ✅ Honors the relational-frontmatter pattern you already started on the continents
- ✅ Stubs become a tracked backlog instead of clutter
- ✅ Incremental — backlog items are independent and bite-sized
- ⚠️ Bulk frontmatter migration is mechanical work; we'll script it but every script needs review
- ⚠️ Requires committing to a type vocabulary (we can extend it later but breaking changes get expensive once notes exist)

---

## §Tolkien — what "history-first, Tolkien-esque depth" implies

This isn't a separate approach; it's a *lens* on Approach A that promotes certain types and certain backlog work to the foreground.

### History is the spine, not a section

In a Tolkien-shaped world, every other note ultimately points back to History. A continent has founders, a city has a founding event and possibly a fall, a faction has an origin and key turning points, a deity has acts that shape mortal time, a language has a period of bloom and a period of decline. The current `History/` folder is treated as one section among six (Cosmology, History, Realms, Races, Languages, Story); the refactor reframes it as the **temporal backbone** that all six attach to.

Concretely:
- Every `event` page is a first-class node with `era:`, `year:`, `participants:`, `caused-by:`, `caused:`, `chronicled-in:` frontmatter — establishing it as a graph node in time, causality, and source-attestation.
- Every other type (settlement, character, faction, house, artifact, language, deity, …) carries at least one `era:` field — *when does this exist in the world?* Cities with `founded-in:` and optional `lost-in:`. Houses with `founded:` / `extinct:`. Languages with `bloom-era:` / `decline-era:`.
- A `chronicle` is what makes the world feel old. A historical event might be `chronicled-in: ["[[The Anvil Scriptures]]", "[[Annals of the Grundthain]]"]`. Different chronicles can disagree. That disagreement is itself the worldbuilding.
- The `event` ↔ `myth` distinction lets two cultures tell the same occurrence differently. Both are linked from the canonical event page via `mythic-account:` / `historical-account:` fields.

### What this changes in the backlog

The long-term backlog (§4 below) is **re-prioritised**: filling in History becomes Phase 1, not Phase 2. The order of operations:

1. Build out each Age's `era` summary page first (overview, themes, key events, key chronicles).
2. Stub-fill the heavy-impact event pages first (Hexweave Binding, Forge Wars, Breaking of the Hexweave Seal, Machinery of Death — all currently empty but referenced from dozens of other notes).
3. *Then* the Realms backfill (cities, rivers, mountains) gets its `era:` fields and links back to founding/falling events.
4. Chronicles get authored alongside, as the in-world source layer.
5. Stories ("Story/" folder) come *last* — they sit inside the world, not beside it.

### How this reframes the Python sim

You called the `renasci` simulator "for fun, someday, miles away." Under the Tolkien-esque lens it's actually **the missing piece for one specific kind of depth**: dynastic genealogies and the chronicle of houses over centuries. Tolkien's Appendix A is exactly that. The sim already produces:
- 250 years of marriages, births, deaths, succession crises, house allegiance changes, founding events.
- All of it timestamped to in-world years.
- Stat-driven flavor (prestige, unrest, wealth, ambition).

The Phase 4 backlog item "**P7. Bridge: simulation → vault**" — previously labelled speculative — should be promoted: it's a credible long-term tool for generating *the kind of dense lineage-and-events material that makes a Tolkienic world feel old.* Not Phase 1 work, but no longer "for fun, someday" — it's a specific future tool with a specific purpose.

The bridge would be: simulation produces a JSON or Markdown trace; a thin converter maps each event to a `type: event` note with full frontmatter, each person to a `type: character`, each house to a `type: house`. The result lands under `_simulated/` and is authored over/edited by hand as needed. Pure-content automation, no narrative invention.

### Long-term ambition: Dwarf Fortress-style world-gen *(parked, captured for posterity)*

The natural endpoint of the simulator's evolution — explicitly **parked** for now, but worth recording so the type taxonomy and frontmatter schema don't paint us into a corner:

The aesthetic target is DF's initial world-gen — procedural history that produces lineages, wars, founded/abandoned cities, named heroes with deeds, artifacts forged at specific moments by specific people in specific materials, and **generated myths** (gods doing things, creation accounts, hero cycles). DF's output is queryable and so dense that the player feels they've walked into a world with millennia behind it. That is the Tolkien-esque depth, generated as substrate.

What `renasci` already covers: the **dynastic-lineage slice** (births, marriages, deaths, succession, house allegiances).

What it would need to grow into to approach DF-level depth (NOT scope for now — just the long-term shape):
- **Conflict events** — wars between houses, sieges, alliances, betrayals.
- **Geographic events** — founding settlements, abandoning settlements, building monuments, natural disasters.
- **Artifact-creation events** — a specific person, at a specific year, in a specific city, using a specific resource, forges a named artifact. (This connects `character`, `settlement`, `resource`, `artifact`, and `event` simultaneously — a five-way frontmatter link.)
- **Myth generation** — generative templates for creation-myths, hero-cycle myths, cosmic-conflict myths. The `myth` type in the taxonomy is sized to receive these.
- **Cultural drift** — traditions emerge/fade, languages diverge, factions split.

**Why we capture this now even though we're parking it:**
1. The type taxonomy in §A.1 is designed to be *receptive* to this output. `event`, `myth`, `artifact`, `chronicle`, `house`, `character`, `settlement` are exactly the types DF-style world-gen would write into.
2. The `_simulated/` subfolder convention keeps generated content quarantined from hand-written canon — author promotes things to canon by moving them out and editing.
3. A `generated: true` frontmatter flag (default `false`, set by the bridge) lets Dataview pages distinguish hand-written from generated content. Useful for "show me only canon" and "show me all sim-suggested events I haven't reviewed yet."

This whole sub-section is a future ambition, not a near-term commitment. The initial refactor pass establishes the schema. The Phase 4 bridge work, if and when you choose to pursue it, expands the sim's event vocabulary in the direction of DF-style depth.

### What it does *not* change

- The initial pass is still about establishing the type system and the frontmatter schema. We don't write Tolkienic history *now* — we set up the structure that makes writing it possible later.
- Folder structure stays largely the same (still no big move).
- The Python sim stays in Phase 3. It just has a clearer purpose.

---

## Approach B — "Folder First"

The premise: the folder tree is the wrong shape for how you use the vault. Reorganise top-level around use-mode (Canon / Campaign / Drafts), then deal with templates afterwards.

### B.1 Proposed new top-level

```
docs/
├── Canon/            — the in-world reference, organised by domain
│   ├── Cosmology/
│   ├── History/
│   ├── Realms/
│   ├── Races/
│   └── Languages/
├── Campaign/         — anything tied to actual play
│   ├── Sessions/
│   ├── Party/
│   └── Hooks/
├── Drafts/           — WIP and brainstorming
└── _meta/            — conventions, indices, dashboards
```

### B.2 What this fixes
- Sharp split between "world canon" (slow-changing reference) and "campaign state" (fast-changing in-play).
- Drafts folder becomes the legitimate home for stubs and half-ideas, lowering the bar to start a note.
- Sidebar tree becomes shallower at the top, deeper inside each domain.

### B.3 What it costs
- **Massive file movement.** ~522 files move under new parents. Obsidian will auto-update wikilinks, but the git diff is enormous and irreversible-ish.
- Doesn't help the Dataview / tag / AI navigation paths at all — they care about frontmatter, not folders.
- You explicitly said canon-vs-campaign-state separation isn't a priority *yet*. Doing it pre-emptively is over-engineering.
- Doesn't define what makes a note typed.

### B.4 Trade-offs
- ✅ Lighter mental model for sidebar browsing
- ❌ Highest-risk, biggest diff
- ❌ Solves a problem you haven't reported having
- ❌ Doesn't address frontmatter / templates / stubs

Reasonable to revisit later as a *second-phase* refactor, after typed notes have lived for a while and we can see which folders are actually over- or under-used.

---

## Approach C — "Stubs and Standards"

The premise: don't restructure anything. Add templates, bulk-mark stubs, ship one dashboard, done.

### C.1 Concrete actions
- Write the 6 missing templates.
- Add `status: stub` to every empty/near-empty file.
- Add one Dataview "Stub Backlog" page.
- Patch `mkdocs.yml` minimally.

### C.2 Trade-offs
- ✅ Smallest diff, finishable in an evening
- ✅ Zero risk to existing notes
- ❌ Leaves the typed-note opportunity on the table — you still can't ask "all NPCs in the Firebrand Empire"
- ❌ Doesn't fix missing race parent files, the Solaran/Solarans wikilink drift, or the Factions/Societies overlap
- ❌ Doesn't satisfy "big systemic tidying" — this is a minor pass, not a refactor

---

## §4 Long-term backlog (post initial-pass)

Every pain point from `working-model.md §6`, re-ordered so History is the spine. Each item is independently shippable.

### Phase 1 — History as the spine (recurring, indefinite)
This is the new top priority under the Tolkien-esque, history-first lens.
- **H1**. Write the four `era` summary pages (First / Second / Third / Fourth Age), each with overview, themes, key events list, key chronicles list. Currently `The First Age.md`, `The Second Age.md` exist but the era pages aren't framed as overviews-of-the-era.
- **H2**. Fill in the highest-value event stubs that are referenced from dozens of other notes but currently empty:
  - `History/Second Age/Hexweave Binding.md`
  - `History/Second Age/The Forge Wars.md`
  - `History/Third Age/Breaking of the Hexweave Seal.md`
  - `Cosmology/.../Machinery of Death.md` (referenced, has no dedicated page)
- **H3**. Expand the Third and Fourth Ages — currently 2 files each, vs 18–19 for the older ages. Tolkien-esque depth means dozens of events per era; pick a target density (e.g., 15+ events per Age) and add stubs as a backlog.
- **H4**. Author the first 3–5 `chronicle` pages (in-world source texts). The Archive of the Ancients is already half-one — break its 10 numbered artifact descriptions into linked sub-chronicles. Each chronicle attributes the events to its in-world author.
- **H5**. Add `myth` counterparts for 2–3 major events — same occurrence narrated by a different culture. Establishes the pattern for Tolkien-style multi-source history.
- **H6**. Update the `History/Timeline.md` to use the `aprils-automatic-timelines` plugin properly (frontmatter-driven, not hand-maintained).

### Phase 2 — Reference content (continuous)
- **L1**. Migrate remaining ~400 reference notes to the typed schema, chunk by type or by Society. Start with `character`, then `settlement`, then `faction` — those see most session-time use.
- **L2**. Backfill `era:` fields on existing geography (cities founded-in, cultures bloomed-in, factions founded-in / dissolved-in). This is what makes Phase 1 events "land" everywhere.
- **L3**. Audit and rewrite wikilinks for consistent target naming (`[[Solaran]]` vs `[[Solarans]]`, etc.). Tag-Wrangler + the linter can semi-automate this.
- **L4**. Decide each single-file realm individually: collapse into `Cosmology/Planes/` summary, promote to a folder with `era`-aware content, or archive.
- **L5**. Consolidate Blackiron Collective duplicate content into one canonical home.
- **L6**. Build per-Society "campaign reference card" notes for fast in-session lookup. These are Dataview-driven from the typed entries underneath.
- **L7**. Build out `Languages/` with the Language template (etymology, phonology, sample text, script) — Tolkien's signature.
- **L8**. Differentiate `race` pages from `culture` pages explicitly. Where a race page currently mixes both (e.g., Elasi), split into a `race` and one or more `culture` notes.

### Phase 3 — Tooling & site
- **T1**. Add Markdown / link-validity check to CI; fail build on broken wikilinks.
- **T2**. Build an `images/` index (Dataview page listing every image and the notes that embed it). Move orphans to `images/_archive/` or delete.
- **T3**. Add explicit MkDocs nav for top-2 levels; consider grouping plug-in for better section ordering.
- **T4**. Add a `LICENSE` file (CC-BY-4.0 for lore is common; your call).
- **T5**. Decide whether the published site is still useful. If not, retire the workflow.
- **T6**. Filter out `vault backup:` commits from the engineering log via a `git-log` alias, or migrate to squashed nightly backup branches.

### Phase 4 — Python library — repositioned as "the genealogy / annals generator"
The sim is no longer "for fun, someday" — under the Tolkien-esque lens it has a specific role: generating dynastic genealogies and dated event traces to seed the History layer.
- **P1**. Resolve the `world.current_context` lifecycle (make it a proper field initialised in `__post_init__`).
- **P2**. Move race profiles, name banks, and house templates out of `main.py` into JSON/YAML data files. **And** decide whether those data files should be sourced *from* the vault (race profiles live in `Races/*` as canon, sim consumes a derived JSON build artifact). This is the data direction question.
- **P3**. Decide whether to keep or remove the Eberron-style house names in `main.py`; align with vault lore (Tidebound clans, Firebrand Houses, etc.) instead.
- **P4**. Finish or delete the `traits/` package. If kept, integrate with the StatThresholdGenerator pattern.
- **P5**. Add minimal pytest coverage for the event-cascading paths (DeathEvent → SuccessionEvent → HouseChangeEvent).
- **P6**. Write a tiny README inside `src/` explaining what the lib does, how to run the demo, and the planned bridge to the vault.
- **P7** ***(promoted from speculative — this is now the long-term raison d'être of the sim)***. Bridge: write simulation output as Markdown notes under a `_simulated/` subfolder of the vault, using the typed-vault frontmatter schema. Each sim run produces:
  - a `chronicle` page summarising the run as an in-world source
  - one `event` page per significant occurrence, with full `era:` / `year:` / `participants:` / `caused-by:` / `chronicled-in:` frontmatter
  - one `character` page per named person, with `era:`, `family:`, `house:` frontmatter
  - one `house` page per dynasty with members list and founding/extinction events
  These notes are imported as drafts (`status: draft`) and edited/canonised by hand. The sim is a content seed, not a content author.

### Phase 5 — Project-level hygiene
- **R1**. Glossary entry in `_meta/Conventions.md` explaining Renascitur vs Renascita vs renasci, locked in as canon.
- **R2**. Top-level `README.md` revised to explicitly state the worldbuilding philosophy ("Tolkien-esque breadth and depth; build the world history first, write stories within it") and to mention the Python lib alongside the lore.
- **R3**. Delete or revive the `loredrop` branch.
- **R4**. Decide policy on the `.obsidian/` folder being committed (currently tracked; this is fine but unusual — document it).

---

## §5 Resolved decisions

All open questions are now answered. Decisions made on 2026-05-18:

| # | Decision | Choice |
|---|----------|--------|
| 1 | Taxonomy: race vs culture | **Keep separate** — Tidebound (culture) ≠ Dwarf (race) |
| 2 | Taxonomy: `chronicle` | **Separate top-level type** with own template |
| 3 | Taxonomy: `myth` | **Separate type AND `account-type:` field on event** (both patterns coexist) |
| 4 | Taxonomy: supplementary types | **Add `prophecy`** (covers omens/prophecies/dreams). No `quest-hook`. No generic `note`. |
| 5 | Year format | **Sketch 3** — numeric `year:` + `era:` link + Templater-derived `year-display:` |
| 6 | Age names | **Age of the Endless Sun (ES) / Age of Forging (AF) / Age of Stagnation (AS) / Age of Night (AN)** |
| 7 | Filename prefix scope | **History only** (event + chronicle types) |
| 8 | Folder rename | **Yes** — folders renamed to the canonical Age names; old names preserved as aliases |
| 9 | Quoted wikilinks | **Yes** — match Aaron's existing pattern |
| 10 | `created:` / `updated:` | **Yes** — Templater auto-tracks |
| 11 | Single-file realms | **Promote each into its own folder** with skeleton |
| 12 | History-first vs parallel | **History first**, then reference content |
| 13 | Initial-pass scope | **Full mechanical sweep, AI-prepared, single branch, Aaron reviews + merges** |
| 14 | Content drafting in initial pass | **NONE** — pure structure, no prose. Era pages and heavy-event stubs get frontmatter shells, bodies stay empty. Content authorship is backlog work at Aaron's pace. |
| 15 | Templater install | **Yes** |
| 16 | Indices technology | **Dataview** (Bases reserved for future relational views) |
| 17 | Python sim early POC | **No** — strictly Phase 4, the sim is parked |

The design is final. The next move is producing the implementation plan.

---

## §6 Next step

Final design locked in. The next move is the **writing-plans skill**, which derives this design into a step-by-step implementation plan runnable as its own session: ordered tasks, with review checkpoints between mechanical chunks, ready for execution.

Aaron's hands-on time during execution will be: (a) approve the type-inference rule sheet up front, (b) review the diff at each checkpoint, (c) merge. No typing of YAML, no writing of prose.
