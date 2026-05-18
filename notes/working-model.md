# Renascitur — Working Model of the Current Repository

*Last reviewed: 2026-05-18. This document describes the system **as it is today**, not as it should be. The companion `refactor-design.md` (to be written) will describe target state and migration.*

---

## 1. What Renascitur Is

Renascitur is two things sharing one git repo:

1. **A worldbuilding vault** — ~522 Markdown notes under `docs/`, used as an Obsidian vault and also published as a static MkDocs site to GitHub Pages.
2. **A dynasty-simulation Python library** (`renasci`, v0.1.0) under `src/` — a procedural engine for noble houses, marriages, births, deaths, and succession events. Zero external dependencies. Currently independent of the lore vault (it does not read from or write to `docs/`).

The two halves coexist but are not technically connected. The Python lib could in principle generate lore that drops into the vault, but no such bridge exists today.

---

## 2. Repository Layout

```
Renascitur/
├── README.md              — Lore-focused overview (no mention of the Python lib)
├── mkdocs.yml             — MkDocs config (Material theme; NO explicit nav)
├── .gitignore             — Only ignores .obsidian/
├── .obsidian/             — Obsidian config + 7 community plugins (TRACKED — see §6.3)
├── .github/workflows/
│   └── ci.yml             — mkdocs gh-deploy on push to master/main
├── docs/                  — The lore vault (522 .md files, published as the site)
├── src/                   — The Python simulation engine
│   ├── main.py            — Demo: 250-year dynasty simulation
│   ├── setup.py           — Package metadata (name=renasci, v0.1.0)
│   ├── pyproject.toml     — Minimal PEP-517 build config
│   ├── requirements.txt   — Empty
│   └── renasci/           — Package source (see §5)
├── templates/             — 6 Obsidian note templates (see §4.4)
├── images/                — 24 image files, flat layout, UUID/timestamp names
└── notes/                 — Meta-engineering notes (this file lives here)
```

**Note on naming.** The world is spelled three ways in different places:
| Spelling      | Where                              |
|---------------|------------------------------------|
| **Renascitur**| repo name, README, mkdocs `site_name` |
| **Renascita** | primary in-world realm: `docs/Realms/Renascita/` |
| **renasci**   | Python package: `src/renasci/`     |

`Renascitur` is the wrapping setting/cosmos; `Renascita` is the main mortal-realm continent inside it; `renasci` is just a shortened package slug. The distinction is real but easy to confuse and is not explained anywhere in the repo.

---

## 3. The Lore Corpus (`docs/`)

### 3.1 Top-Level Taxonomy

| Folder        | Files | Purpose |
|---------------|------:|---------|
| `Cosmology/`  | 55    | Gods, creation myths, cosmic forces, elementals, corruption entities |
| `History/`    | 42    | Four-Age timeline; events, conflicts, turning points |
| `Realms/`     | 374   | Primary content. `Renascita/` (356 files) is the main setting; 10 other realms are mostly stubs |
| `Races/`      | 34    | Playable + NPC races, organized by lineage (Humans, Grundthains, Kyojin, Solarans, Engineered) |
| `Languages/`  | 15    | Ancient and modern in-world languages |
| `Story/`      | 2     | Campaign / narrative seeds |
| `index.md`    | 1     | "Welcome to Renascitur" — one line |

### 3.2 Realms Sub-Architecture (`docs/Realms/Renascita/`)

Renascita is the only realm with depth. It splits into four parallel hierarchies:

- **Geography/** — physical world (Pyrosia, Arcturia, Islands, The World Beneath, …)
- **Societies/** — cultures and polities (Firebrand Empire, Dwarven Holds, Thraysian Magocracy, Blackiron Collective, Saurian Enclave, Rahalan Nomads, …)
- **Legendarium/** — items, artifacts, characters of legend, technology, natural resources
- **Factions/** — Organisations and Cults

The other 10 realms (`Elementis`, `Solirion`, `Nihilum`, `Thargrun`, `Veltharyn`, `Woudum`, `Sigmora`, `Imperium`, `Infernum`) are single-file stubs or have at most a `Geography/Cities/` skeleton with empty contents.

### 3.3 Document Conventions

Conventions exist but adoption is highly uneven.

**Naming (consistent):**
- Folder names: `Title Case With Spaces` throughout
- File names: `Title Case With Spaces.md` throughout
- A "parent" entity living in its own folder uses a self-named file inside: `Thraysian Magocracy/Thraysian Magocracy.md`. There is **no** `index.md` / `_index.md` convention.

**Wikilinks (very high adoption):**
- ~95% of files use `[[wikilink]]` syntax
- Pipe-aliases (`[[Target|display text]]`) are used but rare
- Image embeds use `![[file.webp]]` (Obsidian-native)

**Frontmatter (low and inconsistent adoption):**
- Only **~40% of files** have YAML frontmatter
- Common keys: `type`, `tags`, `aliases`, `race`, `affiliation`, `location`, `continent`, `faction_control`, `rarity`, `origin`, `origin-plane`, `aat-race-tier`, `spoken-language`, `written-language`
- Different file-types share keys inconsistently (e.g., some characters have `type: npc`, most have no frontmatter at all)

**Heading structure (no enforced template):**
- Short stubs: `# Title` + 1–2 sentences
- Medium notes: `# Title`, `## Overview`, plus 1–2 themed sections
- Deep notes: 4-level hierarchy with custom sections (e.g., a faction may have `## Origins`, `## Beliefs`, `## Structure`, `## Sacred Sites`, `## Rituals & Symbols`, `## Threat & Spread`, `## Adventure Hooks`)
- Stat-block character pages (`Drezna Ironmaul.md`) use D&D-5e formatting with no headings at all

**Obsidian features used:**
- ✅ Wikilinks, image embeds, tags, frontmatter, the Bases plugin
- ✅ One Advanced Timeline code block (`History/Timeline.md`, partly filled)
- ❌ No Dataview queries found in samples
- ❌ No callout syntax (`> [!note]`)
- ❌ No Templater dynamic syntax (`<% %>`) — templates are plain stubs

### 3.4 Note-Quality Distribution

Of 522 `.md` files in `docs/`:

| Tier                    | Count | Notes |
|-------------------------|------:|-------|
| **Empty** (0 bytes)     | 86    | Outline-only — file created but never written |
| **Stub** (<200 bytes)   | ~169 (incl. the 86 empty) | One-liner or a title + 1 sentence |
| **Substantive**         | ~353  | Real content, but template/structure varies wildly |
| **Deep / polished**     | ~10–20 estimated | E.g., `Weavers of Agony`, `Athenaeum of Arcane Arts and Sciences`, `Contents of the Archive of the Ancients`, `Rahalan Nomads` |

So roughly **a third of all lore files are stubs or empty** — the structural outline is in place far ahead of the actual writing.

### 3.5 Drift / Inconsistency Catalogue

- **Single-file realms** — 7 realms exist as 1–2 line files (Solirion, Nihilum, etc.) with no internal structure; intent unclear (placeholder vs. abandoned vs. deliberately thin).
- **Race "parent" folders empty** — `Races/Humans/Elasi/`, `Races/Humans/Terran/`, `Races/Kyojin/Leonin/`, `Races/Kyojin/Orcs/`, `Races/Grundthains/Dwarves/` each have no own file, only a `Variants/` child folder. The summary file that would tie variants together is missing.
- **Wikilink target drift** — both `[[Solaran]]` and `[[Solarans]]` appear; references to `[[Machinery of Death]]` exist without a dedicated page.
- **Duplicate-ish content** — `The Blackiron Collective.md` exists both as a society entry and with content spread across `Characters/`, `Ironclad Arena/`, `Coalforge Engine/` subfolders.
- **Stale template adoption** — 6 templates exist (City, NPC, Item, Faction, Organisation, PointOfInterest), but few existing files use the `type:`/`tags:` fields they prescribe.
- **History stubs** — Several major historical events that are referenced from many other pages are themselves empty (`Hexweave Binding.md`, `Breaking of the Hexweave Seal.md`, `The Forge Wars.md`).
- **The one work-in-progress file in git status** — `docs/Realms/Renascita/Societies/Saurian Enclave/Contents of the Archive of the Ancients.md` — is one of the corpus's most ambitious pieces (10 numbered Solaran artifacts plus a full dialogue scene). It's also a structural outlier: it doesn't follow any template.

---

## 4. Tooling & Publishing

### 4.1 MkDocs

`mkdocs.yml` is minimal: Material theme, dark/light toggle, `pymdownx` extensions for tables/admonitions/superfences/toc, plus three plugins:
- `search` — built-in
- `roamlinks` — translates `[[wikilink]]` into Markdown links
- `callouts` — admonition rendering
- (`ezlinks` is commented out but still installed by CI — small waste)

**Critical drift:** there is **no `nav:` section**. With 522 files across 200+ nested folders, the auto-generated nav is unusable, and section ordering depends purely on filesystem order.

### 4.2 CI

`.github/workflows/ci.yml` runs on push to `master`/`main`: install mkdocs + plugins, `mkdocs gh-deploy --force`. No build validation, no link checking, no Python tests.

### 4.3 Obsidian Setup

`.obsidian/` is committed (only the subfolder is gitignored in some other paths — but at repo root it's tracked). Seven community plugins enabled:

| Plugin                     | Role |
|----------------------------|------|
| `obsidian-git`             | Auto-commits "vault backup" snapshots |
| `omnisearch`               | Full-text fuzzy search |
| `tag-wrangler`             | Tag tree management |
| `obsidian-timeline`        | Timeline view from dated notes |
| `aprils-automatic-timelines` | Frontmatter → timeline auto-gen |
| `obsidian-linter`          | Markdown / YAML normalization |
| `dataview`                 | Frontmatter-driven queries (installed but no queries found in corpus) |

**Notably absent:** Templater. The 6 templates in `templates/` are static — they only have `{{title}}` placeholders, not dynamic logic.

### 4.4 Templates (`templates/`)

| File                  | `type:`            | Extra fields                        |
|-----------------------|--------------------|-------------------------------------|
| `City.md`             | `city`             | `continent`, `faction_control`      |
| `NPC.md`              | `npc`              | `race`, `affiliation`, `location`   |
| `Item.md`             | `item`             | `rarity`, `origin`                  |
| `PointOfInterest.md`  | `point_of_interest`| `region`                            |
| `Faction.md`          | `faction`          | `continent`                         |
| `Organisation.md`     | `organisation`     | `parent_faction`                    |

Each has a `# {{title}}` heading, an emoji-tagged description section, and a `## 🔗 Connection` section with empty `[[ ]]` placeholders. They cover **only six** content types, leaving many real categories (race, deity, language, historical event, artifact, geographic feature, technology, natural resource) without a template.

### 4.5 Git History Shape

- **115 total commits**
- **50 are auto-generated "vault backup: YYYY-MM-DD HH:MM:SS"** (the obsidian-git plugin)
- **~60 are real engineering / lore commits**
- The last meaningful Python code commit was **2025-05-01**: `"stats threshold generation. See GrumblingEvent"`. Everything since is doc-only.
- One short-lived feature branch `loredrop` appears abandoned.

### 4.6 Images

`images/` has 24 files, ~38 MB total, flat layout. Names are UUIDs (DALL·E exports), `Pasted image YYYYMMDDHHMMSS.png` (clipboard captures), or one Tumblr-sourced JPG. There is no inventory linking each image back to the note(s) that embed it, so orphan-detection requires a corpus scan.

### 4.7 Missing Repo-Level Files

- No `LICENSE` (public repo, undeclared license)
- No `CONTRIBUTING.md`
- No `CHANGELOG.md`
- No Python CI workflow

---

## 5. The Python Simulation Engine (`src/renasci/`)

### 5.1 Architecture at a Glance

The library is a small **event-sourced dynasty simulator**. The top-level `World` advances year by year; in each year a set of **generators** produce **events**, events mutate world state via an **EventBus**, and threshold-based generators fire follow-on events when stats cross limits.

```
   World.advance_year()
        │
        ▼
   age all people
        │
        ▼
   CoreEventGenerators  ──►  yield events  ──►  EventBus.publish()
   (Birth, Marriage,                                │
    Death, Grumbling)                               ▼
                                              event.apply()
                                              mutates world,
                                              records StatDeltas
                                              into WorldContext
                                                    │
                                                    ▼
   StatThresholdGenerators  ──►  read deltas  ──►  yield more events
   (Grumbling at unrest≥30,                          (cascading)
    template for others)
```

Event sourcing is the design centerpiece: `Event.should_create_from(cause_event)` lets one event spawn another (e.g., `DeathEvent` → `SuccessionEvent` → `HouseChangeEvent`).

### 5.2 Module Inventory

```
src/
├── main.py             — 170 lines. Builds World, 12 major + 36 lesser houses
│                          for 5 races, simulates 250 years, prints all events.
│                          Race profiles, name banks, and house assignments
│                          are HARD-CODED inline. Currently MODIFIED in working tree.
│
├── setup.py            — name=renasci, v0.1.0, requires Python ≥3.9, no deps
├── pyproject.toml      — setuptools build backend, nothing else
├── requirements.txt    — empty
│
└── renasci/
    │
    │   ── Core domain ─────────────────────────────────────────────
    ├── person.py       — Person, PersonView, Life. Identity, family, stats
    ├── house.py        — House (dynastic). prestige/influence/unrest/wealth
    ├── race.py         — Race profiles (Human, Leonin, Orc, Dwarf, Gnome).
    │                     name banks, marriage/lifespan/childbearing ranges,
    │                     death_chance curve, valid_pairings
    ├── family.py       — Family, Marriage, determine_dominant_house,
    │                     find_relationship (succession kinship)
    ├── orientation.py  — Gender enum, Sexuality compatibility rules
    │
    │   ── World state ─────────────────────────────────────────────
    ├── world.py        — World container, advance_year() main loop
    ├── stats.py        — StatValue, StatBlock, StatDelta (observer pattern)
    ├── context.py      — WorldContext: per-year delta tracking
    │
    │   ── Event sourcing ─────────────────────────────────────────
    ├── events/
    │   ├── base.py            — Event base, EventBus dispatcher
    │   ├── person_events.py   — Birth, Marriage, Death, Succession, Widow
    │   ├── house_events.py    — Founding, HouseChange, Grumbling
    │   └── world_events.py    — EMPTY STUB
    │
    │   ── Procedural generation ─────────────────────────────────
    ├── generators/
    │   ├── base.py            — EventGenerator, CoreEventGenerator,
    │   │                        StatThresholdGenerator
    │   ├── births.py          — fertility_chance curve (~4 children
    │   │                        target, taper across reproductive years)
    │   ├── marriages.py       — eligibility, sexuality + race compatibility
    │   ├── deaths.py          — age-based mortality
    │   └── stats.py           — GrumblingGenerator: unrest ≥ 30
    │
    │   ── In-progress, UNTRACKED ───────────────────────────────
    ├── traits/                — UNTRACKED in git
    │   ├── __init__.py        — empty
    │   └── base.py            — `class Trait: name: str; description: str`
    │                            That's literally the entire file.
    │
    │   ── Helpers ───────────────────────────────────────────────
    └── utils/
        └── helpers.py         — create_person(), create_house() factories
```

### 5.3 Code-State Findings

**Strengths:**
- Pure-stdlib, dataclass-based, type-annotated — clean and readable
- Pub/sub event architecture is genuinely elegant; cascading events work well
- Stat system with delta recording is a good foundation for richer threshold-driven behavior

**Identified TODOs and rough edges (from inline comments and structure):**
- `world.py:52` — `self.current_context` is set inside `advance_year()` but treated as a field on World; fragile.
- `race.py:11` — race name is `Literal["Human", "Leonin", "Orc", "Dwarf", "Gnome"]`; should be data-driven so new races don't need a code edit.
- `orientation.py:25` — `Sexuality.value` is a Literal-string, should be an Enum.
- `utils/helpers.py:17` — TODO about making Sexuality a flyweight; commented-out `create_world()` stub at the bottom.
- `events/person_events.py:68` — TODO "not sure on this" on succession-event creation.
- `events/world_events.py` — placeholder, never written.
- `traits/base.py` — declared but not implemented. Suggests a planned feature paused mid-thought.
- `main.py` — race profiles, name banks, and house assignments are inline Python. Adding a race or renaming a house means editing the demo.
- No tests anywhere. No pytest config.
- `renasci.egg-info/` is checked in (or at least present in working tree).

### 5.4 Connection to the Lore Vault

**There is none.** The Python lib does not read `docs/`, does not write to it, and shares no data files with it. The races, houses, and name banks in `main.py` are independent from the in-vault lore — and partially contradictory (e.g., main.py uses Eberron's dragonmarked house names like Lyrandar/Medani/Tharashk/Vadalis/Jorasco/Cannith/Orien/Sivis/Deneith/Phiarlan/Kundarak, which do not appear in the lore vault at all).

This is a significant disconnect that any future work should address explicitly: are the simulator and the worldbuilding the same project, or two separate projects sharing a repo?

---

## 6. Master Drift / Pain-Point Inventory

A single consolidated list of every concrete issue identified — useful as the input list for the refactor proposal.

### 6.1 Lore-side
1. ~33% of notes are stubs or empty; structural outline is months ahead of the writing.
2. 86 fully-empty files litter the tree.
3. Race "parent" folders have no summary file, only `Variants/` subfolders.
4. Seven single-file "realm" stubs with unclear intent.
5. Wikilink target inconsistency (e.g., `[[Solaran]]` vs `[[Solarans]]`).
6. Some heavily-referenced concepts (Machinery of Death) have no page.
7. Template adoption is ~40%; the templates themselves only cover six categories.
8. No standard for character pages: prose vs stat-block vs one-liner all coexist.
9. Duplicated content for Blackiron Collective (file + parallel subfolders).
10. `History/Timeline.md` is partly filled, no Dataview/Bases-driven index of events.

### 6.2 Tooling-side
11. `mkdocs.yml` has no `nav:` — site navigation is whatever the filesystem happens to look like.
12. `ezlinks` is commented out but still installed by CI.
13. No build validation: no Markdown linting, no broken-wikilink check, no Python tests.
14. No `LICENSE`, `CONTRIBUTING.md`, or `CHANGELOG.md`.
15. `images/` is flat and unindexed; orphan detection is manual.
16. 50 of 115 commits are auto-vault-backups — real engineering history is hard to read.
17. `loredrop` branch appears abandoned.

### 6.3 Python-side
18. `traits/` is untracked, a 2-line stub blocking nothing but also doing nothing.
19. `main.py` is the only "config" — races, name banks, and house list are inline.
20. The Eberron-style house names in `main.py` don't match any in-vault lore.
21. `world.current_context` lifecycle is fragile.
22. No tests.
23. Five inline TODOs across the package.
24. Empty `events/world_events.py`.
25. No documented API; README never mentions the Python lib.

### 6.4 Cross-cutting
26. Three spellings of the world (Renascitur / Renascita / renasci) with no glossary explaining them.
27. The simulator and the vault are unrelated despite sharing a repo. This may be intentional but isn't documented.
28. No top-level guide explaining the structure of the project to a returning author after time away.

---

## 7. Glossary of Names That Matter

| Term | Meaning |
|------|---------|
| **Renascitur** | The full setting / project name. Used on the site and in the repo name. |
| **Renascita** | The primary mortal-realm continent inside Renascitur. The only realm with deep content. |
| **renasci** | Short slug for the Python package. No in-world meaning. |
| **Solaran / Solarans** | Ancient star-born race. Inconsistent singular/plural in wikilinks. |
| **Grundthain** | Ancestral race of the Dwarven lineage in the vault. |
| **Hexweave** | A magical/cosmological structure central to several historical events. Most pages about it are stubs. |
| **The God Hand** | Five elder cosmic entities under `Cosmology/Creation/`. |
| **Vault backup** | An auto-commit by the obsidian-git plugin, not a real commit. |

---

## 8. What This Document Is Not

This is a **snapshot of current state**, not a refactor plan. It deliberately makes no recommendations. The next step is a focused conversation about which of the pain points listed in §6 actually matter to the author, what the project's medium-term direction is, and which problems are worth tackling first — captured in `refactor-design.md`.
