---
title: S2 Vault bridge
status: draft (r2, after an independent review)
date: 2026-10-23
tickets: "#23 (this spec); build #58–#64; epic #3"
master: notes/specs/2026-10-21-history-engine-design.md §5.11, §6 (S2)
---

# S2 Vault bridge

## 0. In one paragraph

The vault (`docs/`, an Obsidian vault published by MkDocs) is canon. The engine is not. The bridge reads
the vault into **typed notes**, turns canon notes into **pins** (S1's pin model) and chronicles into
**claim seeds**, checks the pins are **feasible** together, and hands them to **casting** so a run starts
with canon's people in place and canon's births and reigns reserved. In the other direction it
**proposes** notes for things a run made (`canon: proposed`, in their own folder), never overwrites a
note Aaron has edited, and lists stale proposals for cleanup. It never writes `canon: true` and never
invents canon: what the vault doesn't say is a report, not a guess.

## 1. Principles

- **Read-only by default.** `renasci vault check` only reads. Writes are explicit commands that print a
  diff first (`--write` applies it).
- **Ids are identity.** A note's `id:` (`v:<slug>`) is what pins, bindings and proposals name.
- **Report, don't crash.** Malformed notes, unresolved links, impossible dates and contradictions are
  findings with path and line; the rest of the vault still loads. Anything the engine would refuse (a
  duplicate bind, an infeasible ordering) is caught and reported by the bridge first.
- **Deterministic and portable.** The same vault gives the same notes, pins, report and digest on any
  machine (sorted walks, canonical JSON, normalised text: §2.5).
- **Small stack.** Standard library only. Frontmatter is a documented YAML subset (§2.2).
- **Engine-agnostic.** The core bridge knows the 22 note types, dates and the pin model. People-specific
  extraction and checks (births, lineage, fertility, reigns) are a **ruleset hook** the people package
  provides (§6, §8). World specifics are data in `vault.toml` at the vault root.

## 2. The loader (#58)

### 2.1 Walking

Every `*.md` under the vault root, in sorted path order, except dot-folders, `_proposed/` (loaded only for
the writer, §9, unless a proposal has been promoted, §9.4) and `vault.toml`'s `ignore` paths. A note's
**key** is its path relative to the root without `.md`; its **title** is the file stem.

### 2.2 Frontmatter (a YAML subset)

Between a leading `---` and the next `---`, the bridge reads:

- `key: value` scalars: plain, `"double"` or `'single'` quoted, integers, `true`/`false`, empty (null);
- a value that is exactly one wikilink, quoted or not (`origin-plane: [[Elemental Plane]]`), is a **link
  scalar**, not a nested list;
- flow lists `key: [a, b, "c, d"]`;
- block lists: `key:` followed by `- item` lines, **indented or at column 0** (the vault has both);
- one level of block map: `key:` followed by indented `sub: value` lines;
- **flow maps as list items**: `- {office: "[[Emperors]]", from: 4A 1, to: 4A 45}` (how `offices` and
  `participants` are written, §5.3).

Anything else is a finding ("frontmatter beyond the supported subset") and that note's frontmatter is read
as far as it parses. Keys are kept verbatim.

### 2.3 Links

`[[Target]]`, `[[Target|shown]]`, `[[Target#Heading]]` and embeds `![[Target]]` resolve in this order:

1. **Path form** (contains `/`): strip a leading `docs/` (the repo root also has an `.obsidian`), then the
   path must name a note (`Races/Kyojin/Leonin/Leonin`). A path that names a folder resolves to its
   **folder note** (`<folder>/<folder name>.md`) if there is one. Otherwise: a finding (stale path).
2. **A unique file stem** anywhere in the vault (case-insensitive).
3. **A stem shared by several notes:** when the link sits in a typed field (`race: [[Leonin]]`), the one
   note of the field's expected type (a race) resolves it; otherwise an **ambiguous** finding.
4. **A unique alias**, as a last resort (Obsidian itself doesn't resolve by alias, but the vault's
   frontmatter uses them); an alias shared by several notes is ambiguous.

Images and other files are attachments, not notes. Body links are collected for the graph and claim
seeds; only frontmatter links make pins.

### 2.4 The note record

```json
{"key": "Realms/.../Great Houses/House Medani", "id": "v:house-medani", "title": "House Medani",
 "type": "house", "type_from": "frontmatter|folder|default", "status": "canon|draft|proposed",
 "frontmatter": {...}, "links": {"field": ["v:..."]}, "body_links": ["v:..."], "aliases": [...],
 "line_of": {"field": 3}, "hash": "<sha256 of the normalised text>"}
```

### 2.5 Normalisation and the digest

Text is normalised before hashing: decoded as UTF-8, a BOM dropped, `\r\n` → `\n`. A note's `hash` is the
sha256 of that. The **vault digest** is the sha256 of canonical JSON of `{"notes": [[id, hash], ...]
(sorted, pin sources only), "config": <vault.toml normalised hash>}`. Writes keep a file's original line
endings.

## 3. Types and their mapping (#59)

### 3.1 The 22 types

continent, region, settlement, landmark, waterway, range · character, race, culture, faction, house,
organisation · era, event, myth, chronicle · artifact, item, resource, technology · deity, cosmic-force,
tradition, language · essay, index.

### 3.2 Where a type comes from

1. `type:` in the frontmatter: one of the 22, or a name in `vault.toml`'s `[type_aliases]` (`city =
   "settlement"`; two notes use `city` today). Anything else is a finding.
2. Otherwise **folder rules** in `vault.toml`, in order, first match wins. Patterns are path globs where
   `*` is one path segment and `**` any depth (not `fnmatch`). A rule may require a field (`when`):

   ```toml
   [[types]]   # eras first: they carry timeline dates too, and they are the age table's source
   match = "History/*/The * Age"
   type = "era"
   [[types]]
   match = "History/**"
   when = "aat-event-start-date"
   type = "event"
   [[types]]
   match = "Realms/*/Societies/*/Characters/*"
   type = "character"
   ```

3. Otherwise `essay`. `vault check` reports how many notes are typed by frontmatter, by folder and by
   default, so the typed-vault refactor can be followed.

### 3.3 What each type becomes

| Note | Becomes |
|---|---|
| character, house, organisation (offices), event, era | **pin sources** (§6) |
| settlement, region, continent, landmark, waterway, range | **places** (M1: names and ids; S4 reads them) |
| race, culture, language, deity, faction, artifact, … | **reference** (loaded, linked, given ids; not pinned in M1) |
| chronicle, myth (incl. `kind: prophecy`) | **claim seeds** (§10) |
| essay, index | **ignored** |

**Status:** a note with no `canon:` is canon (the vault is canon by default); `status: draft` opts out
(loads, reported, makes nothing); `canon: proposed` makes nothing until promoted (§9.4).

## 4. Ids (#60)

- **Form:** `id: v:<slug>`. The slug: the file stem, NFKD-normalised, combining marks dropped, apostrophes
  (`'` and `’`) dropped, every run of other non-alphanumerics → `-`, trimmed, lowercased. So `Lion’s Rest`
  → `v:lions-rest`, `Magnus’ Rest` → `v:magnus-rest`, `Duo - Second Emperor` → `v:duo-second-emperor`
  (matching the Fourth Age draft's ids). Collisions get `-2`, `-3`… in sorted key order (the language
  `Leonin` → `v:leonin`, the race → `v:leonin-2`; `vault.toml` may pin a preferred id per key instead).
- **Who gets one:** every note that isn't an essay or index (reference notes too: links name them).
- **Migration:** `renasci vault ids` prints the exact lines it would add (a diff); `--write` adds them and
  touches nothing else. Idempotent; never changes an existing id. Aaron reviews the git diff.
- **Afterwards:** renames and moves keep ids. A duplicate id is a finding that blocks pins from both notes.
- **Races:** `vault.toml` maps vault race ids to the scenario's race ids (`[races] "v:leonin-2" = "r:leonin"`),
  for casting and the fertility checks.

## 5. Dates and the typed schema

### 5.1 The age table

Dates are age-relative (`4A 123`, `4A 123 m3 d12`), as the engine's calendar parses them. The timeline
plugin writes **absolute** years; `vault.toml` gives each age's first absolute year (filled from era
notes' `aat-event-start-date` where present: *The Second Age* starts at 10001). Absolute year `n` in an
age starting at `s` is year `n - s + 1` (so an era starting at absolute 0 has year 1 at 0). A date
outside every age is a finding.

### 5.2 Vague dates

```
date   := exact | range | circa
exact  := AGE YEAR [ "m" MONTH "d" DAY ]        4A 123, 4A 123 m3 d12
range  := AGE YEAR ".." YEAR                    4A 120..140
circa  := "~" AGE YEAR                           ~4A 120  (± circa_years, default 5)
```

A year means its whole year (day 0 to `days_per_year - 1`). Windows are clamped to their age, with a
finding when clamping changed them. `before:`/`after:` links make orderings (§6).

### 5.3 The typed frontmatter (what the bridge reads)

| Type | Fields (all optional; links as `[[...]]`) |
|---|---|
| character | `born`, `died`, `race`, `sex` (m/f), `house`, `father`, `mother`, `spouse`, `home`, `offices` (block list of flow maps `{office, from, to}`) |
| house | `seat`, `founded`, `ended`, `head` (a character), `rule` (a succession rule name) |
| organisation | `kind: office` (a title, e.g. *Emperors*), `seat`, `rule` |
| event | `date` (or `aat-event-start-date`/`-end-date`), `engine` (an engine event type), `participants` (flow map role → link or list), `before`, `after` |
| era | `aat-event-start-date`, `aat-event-end-date` |

An **office** is either a house's headship (`office: [[House Medani]]`) or an organisation with `kind:
office`. Siblings have no field: "younger brother of X" is written by giving both the same `father`
(a placeholder note or a canon one).

**Today's notes keep facts in the body.** `renasci vault suggest` proposes frontmatter from a fixed set of
labelled bullets only (`**House**:`, `**Race**:`, `**Spouse**:`, `**Current Head**:`), never from prose,
as a diff (`--write` applies, sharing the id migration's writer). Dates are mostly absent from the Fourth
Age notes; filling them is lore work (#17, #18).

## 6. Pins (#61)

The core bridge emits only the kinds S1 supports (`existence`, `event`, `ordering`); never `lineage`,
`succession` or `goal` (S1 classifies those `unsupported`; goals are S7's, deferred). Pin ids:

| Pin | Id | Made by |
|---|---|---|
| a birth | `<char>:born` | people hook |
| alive over a dated window | `<char>:alive` | people hook |
| reign k of an office | `<char>:reign:<office>:<k>` | people hook |
| an event note | `<event>:event` | core |
| an ordering | `<a pin>:before:<b pin>` | core |

**The people hook's extraction:**

| From | Pin |
|---|---|
| a character with `born` inside the run and at least one parent | `event` pin, `type: people.birth`, window = `born`, `roles: {father: [id], mother: [id]}` (as given), `bind: {role: child, subject: <char id>, fields: {sex}}` |
| a character born before the run starts | **placed at start** (§7); plus `<char>:alive` **only** if the note states a `died` or a window (an existence pin without a window would guard them forever) |
| a character with `born` inside the run and no parent | **unplaced** (reported: the engine has no way to bring them in yet) |
| a character with no `born` | placed at start if their house is in the run, with a **drawn** age (marked `drawn` in `casting.json`, never canon); else unplaced |
| `offices` with `from` | `event` pin, `type: people.succession`, window = `from`, `roles: {successor: [char id]}`, `payload.office` = the office's **entity id** (a house headship is `<house id>-head`, as S3's synthesis names it; an office organisation is its own id, §7) |
| `died` | not a pin (the engine never kills to order): checked after the run, **met** or **missed** |

**Births come only from character notes:** an event note with `engine: people.birth` is reported and
skipped, so one birth never has two pins (two would leave one unmet and force a second birth).

**Core extraction:** an event note with `engine:` and a date gives an `event` pin with roles from
`participants` (canon ids only; a role naming a non-canon note is a finding). Without `engine:` it is
**unmodelled** (listed: a story the engine can't yet tell). Houses get **no** existence pins (S3's
extinction doesn't consult guards); a house's `ended` is checked after the run like `died`.

**Orderings** are emitted only between two **in-run event pins**. A note contributes its event pin (an
event note) or its birth pin (a character). `before`/`after` between notes where one side is out of the
run is checked by the bridge from the windows (met, or infeasible) and not emitted.

## 7. Casting (#63)

- **Canon is an input to synthesis** (S3 §4): `synthesise(engine, scenario, seed, canon=placed)` creates
  canon people first, then fills around them; `apply_pins` runs afterwards and finds them existing.
- **A canon head replaces the synthesised head** and holds `<house>-head`; synthesised relatives fill only
  the slots canon leaves open (a house with a canon head and canon siblings gets synthesised spouses and
  children around them, not a second head).
- **Office organisations** (the Emperors): the scenario gains `offices` (id, rule, seat, eligible houses
  or none for "any notable"); synthesis creates the office entity with the first canon holder. S3's
  succession candidates come from the office's house; an office without a house uses the holder's own
  line. Until that lands, imperial reign pins are `unsupported` and reported, not silently dropped.
- **Conservation:** placed canon people are counted in `residents` before the masses are cast, like
  synthesised notables, so the ledger starts right. They are not promotions.
- **Ancestors:** a canon parent outside the run is placed as a dormant record (S3's dormant state) when a
  living canon child names them; otherwise nobody invents ancestors.
- **Output:** `casting.json` in the run folder: every canon id with how it was cast (`placed`, `drawn`,
  `reserved`, `unplaced`, `out_of_scope`), the entity it became, and the pins that depend on it. The run
  folder also keeps `pins.json` (the resolved pins) so **replay uses the pins it was cast from**, not the
  vault as it is later; a replay warns when the vault's digest has changed since.

## 8. Feasibility (#62)

Two passes, same verdicts (`ok`, `out_of_scope`, `unsupported`, `infeasible`):

1. **S1's** `feasibility(pins, start, end)`: windows, scope, orderings and their cycles.
2. **The people hook's** check (pins + notes + races): a parent born after the child; a mother outside
   her race's fertile ages, or a father below `race.marriage[0]` (`BirthForcer`'s threshold), at the
   birth window; a child born after a parent's `died`; a lineage cycle; `died` before `born`; a life
   longer than the race allows; two reigns of one office overlapping; a reign outside the holder's life;
   two pins binding one subject. Genome satisfiability is deferred (no pin constrains genomes in M1).

"Dropped" means the bridge filters infeasible pins out **before** `apply_pins` (which re-runs S1's pass
on what remains). The report (`analysis/feasibility.json` in the run folder, stdout for `vault check`)
names each pin, its verdict and the notes involved.

## 9. Proposals (#64)

1. **Where:** `docs/_proposed/<type>/<slug>.md`, in the Obsidian vault and excluded from MkDocs
   (`exclude_docs: _proposed/`).
2. **What:** for M1, **characters** (a run's people: `born`, `died`, `house`, parents as canon links where
   they are canon) and **events whose roles are all canon** (else the proposal names the people it would
   need first). Frontmatter in the §5.3 schema, `canon: proposed`, a fresh `id`, `source: {run, entity or
   event, vault_digest}` and `generated_hash`; a short generated body linking the canon notes involved.
3. **`generated_hash`:** the sha256 of the normalised file text (§2.5) with the `generated_hash:` line
   removed. Writing a proposal at a path that exists: if the existing file still matches its own hash
   (untouched), it is regenerated in place; if not (Aaron edited it), it is **never overwritten** and the
   new proposal goes to `<slug>-2.md` with a note saying so.
4. **Promotion:** Aaron sets `canon: true` (or removes `canon:`) and moves the file out of `_proposed/`
   wherever it belongs; the next load reads it as canon and its pins come back. A promoted note left in
   `_proposed/` is loaded too (with a finding suggesting the move). The bridge never writes `canon: true`.
   **Round trip:** a proposed character with a `born` and canon parents becomes a birth pin the next run
   meets.
5. **Stale:** a proposal is stale when its source run folder is gone, or a later run (by manifest
   creation order) of the same recipe name exists, **and** it is untouched. `renasci vault stale` lists
   them; nothing is deleted. The vault digest in `source` is informational (any canon edit changes it).

## 10. Claim seeds

Chronicles and myths are kept as `claims.json` (note id, kind, the entities and events they mention, when
written if given). M1 doesn't use them; S6 seeds beliefs from them. They are never pins.

## 11. Commands

```
renasci vault check [docs] [--json]         load, map, extract pins, feasibility: a report (read-only)
renasci vault ids [docs] [--write]          assign missing ids (a diff first)
renasci vault suggest [docs] [--write]      frontmatter from labelled body bullets (a diff first)
renasci vault pins [docs] --age 4A          the resolved pins as JSON
renasci vault propose <run> <id> [docs]     write a proposed note (never over an edit)
renasci vault stale [docs] [runs]           untouched proposals from superseded runs
```

A recipe names the vault with `[vault] path = "docs"`; the run loads it, writes `pins.json`,
`casting.json` and `feasibility.json`, records the digest, and casts.

## 12. Testing

- **A fixture vault** (`tests/fixtures/vault/`) with typed and untyped notes; both date forms and the
  vague ones; path links with `docs/`, a folder link, a stale path; a stem collision resolved by field
  type and one left ambiguous; column-0 lists and link scalars; a draft; a proposal (untouched and edited);
  malformed frontmatter; a contradictory lineage; a reign overlap; two pins binding one subject; CRLF and
  LF copies of one note (same hash). Tests pin the notes, findings, pins and verdicts exactly.
- **The real vault** loads with zero errors (findings are fine), twice to one digest.
- **Ids:** the slug rule on the vault's names (`Lion’s Rest` → `v:lions-rest`); the migration is
  idempotent and additive.
- **Pins:** the fixture's characters give the expected pins by the §6 tables; the Fourth Age gives a pin
  skeleton for the 12 Houses and 8 Emperors plus the list of what's missing (dates, parents).
- **Casting:** fixture characters are placed (a canon head replaces the synthesised one), conservation
  holds, a reserved birth is met, and replay uses `pins.json`.
- **Round trip:** propose a character, promote it in the file, load: its birth pin appears; a second run
  meets it. An edited proposal is never overwritten.

**The done-when** (master §6: Fourth Age canon loads, passes feasibility, casts; a promoted event round-
trips) needs Fourth Age dates and lineages in the vault (#17, #18). Until they exist, S2 is accepted on
the fixture vault plus "the real vault loads clean and casts its undated canon heads".

## 13. Open questions (defaults chosen; on the review queue)

1. **Proposals live in** `docs/_proposed/`, excluded from MkDocs.
2. **Canon by default:** no `canon:` means canon; `status: draft` opts out.
3. **Death dates aren't forced** in M1 (checked and reported only).
4. **Undated canon people** are placed with drawn ages (marked `drawn`), rather than left out.
5. **The Emperors** need an office entity in S3 synthesis (§7); until then imperial reign pins are
   reported as unsupported.
6. **`circa_years` = 5.**

## 14. Plan: working order

1. **Loader** (#58): walk, the frontmatter subset, links with the §2.3 order, records, normalisation,
   findings; the real vault loads clean.
2. **Types and mapping** (#59): `vault.toml` (folder rules, type aliases), the §3.3 table, status gates.
3. **Ids** (#60): the slug rule, the migration and the shared diff writer; Aaron runs it on the vault.
4. **Dates and pins** (#61): the age table, the date grammar, core extraction, the people hook,
   `vault suggest`.
5. **Feasibility** (#62): the people hook's checks on top of S1's pass; the report.
6. **Casting** (#63): canon as a synthesis input, heads replacing synthesised heads, office entities,
   `casting.json`, `pins.json`, `[vault]` in recipes.
7. **Proposals** (#64): the writer, `generated_hash`, regeneration rules, stale list, the round trip.

**Risky bits:** the YAML subset against real notes (use the vault as the corpus); link resolution in the
vault's real collisions (`Leonin`, the `Medani` alias); and casting canon into synthesis without bending
conservation or S3's house structure.
