# S3 People & Bloodlines: Sub-project Spec

**Status:** r2, 2026-10-22.
- r1 was reviewed by an independent agent. r2 fixes:
  - pin handling (no steering in M1; canon children bind to natural births);
  - the explainability of kin reads;
  - global coupling;
  - S1 API mismatches;
  - the conservation ledger;
  - cost estimates.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #24 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md` (§2 Heart, §5.1, §5.8, §5.10, §6 S3, §8.2 M1).
- **Builds on:** S1 (`notes/specs/2026-10-22-s1-engine-foundation.md`), as merged. §15 lists the small S1 additions S3 needs.
- **Tickets:** #65–#75 (epic #4).

## 0. In one paragraph

People are the engine's heart. S3 adds a **world-agnostic `renasci.people` package**:
- individuals with genomes and families;
- houses whose headship passes by a succession rule;
- offices, such as a throne;
- a relationship graph;
- drives;
- populations held as aggregates, with named individuals promoted out of them and demoted back.

Everything specific to a world is **data the world supplies**: races, the genome catalogue, hazard tables, settlements, houses and their rules. That covers Renascita too. A small non-Renascita test world, **kin**, exercises it in tests, as the toy world did for S1. The Fourth Age is the same code plus a scenario file and the canon that S2 casts.

**Done when** (from the master spec): the Fourth Age runs 4A 1–256 at M1 scale (tens of thousands of people, 1k–5k notables) in minutes, conservation invariants hold, and lineage pins are met: all eight Emperors reign in order, and modern characters are born into their lineages.

## 1. Principles

- **Classes hold behaviour; JSON records hold state.** Systems, succession rules and drives are Python classes, while people, houses, offices and ties are store records. Checkpoints stay JSON. This follows the design note on #8.
- **Everything goes through `Ctx`.** Reads are declared and recorded, draws are keyed, choices use rendezvous, and events carry their causes.
- **Every decision reads local, scoped state.** No system lists all people (`ctx.ids("person")` reads every status ever and is unscoped, so one difference would taint everything). Systems walk **settlements**, read the settlement's `residents` inside `ctx.scope(settlement)`, and decide about each resident there. Houses and offices are decided in `ctx.scope(house)`. That keeps divergence explanation sharp (S1 §3.15) and the causal wave meaningful.
- **Notables are few, the masses are many.** Individuals cost records, events and reads, while aggregates cost a few numbers per settlement per season. Promotion is driven by need, never by quota.

## 2. Records

All ids are causal (S1): `entity_id(event, role, ordinal)`. Canon with no natural origin (a vault id, existing at the start) is cast up front. Canon born during the run **binds** to its natural birth (§4.3).

### person

| Field | Type | Notes |
|---|---|---|
| `name` | str | From the world's name lists, chosen by a keyed draw. A bound canon pin supplies it instead. |
| `sex` | `"f"` / `"m"` | |
| `born` | date | Age is derived from it, so nothing ages a record. |
| `race` | str | A key into the world's race table. |
| `place` | str | The settlement where they live; mirrored in the settlement's `residents`. |
| `house` | str or null | |
| `mother`, `father` | str or null | Null means unknown (promoted, or founding stock). |
| `children` | [person id] | **A real field**, in birth order, written by the birth event. Kin reads see it (§6). |
| `spouse` | str or null | The current spouse. Past spouses are in the event log. |
| `genome` | {locus: [allele, allele]} | See §3. |
| `traits` | {trait: float} | Phenotype, fixed at birth (§3.4). |
| `drives` | {drive: float} | Quantised to 0.05 (§7). |
| `ties` | [tie id] | Sorted. Non-kin relationships (§6). |
| `last_birth` | date or null | Birth spacing (on the mother). |

**Status** is `active`, `dormant` (demoted into the aggregate; the record and its history are kept) or `dead`. Dead and dormant people never act, and no event names a dead person in an acting role (an invariant).

### settlement

`name`, `race_mix`, `genome_group`, `danger`, `residents` (sorted ids of its active notables), `notable_target` (a per-settlement budget, §8.3). Settlements come from the world (the scenario, then S4).

### house

`name`, `seat` (place), `rank` (int, higher is greater), `founded` (date), `headship` (its office id), `extinct` (date or null). Members are read through the head's descendants and the house's notables in the seat (§5). A house holds no global member list.

### office

`name`, `holder`, `heir`, `rule` (the name of a succession-rule class, §5), `house` (the house whose members are eligible, or null). A house's headship is an office, and so is the imperial throne.

### tie

`a`, `b` (ordered by id), `kind` (friend, rival, patron, mentor, lover, enemy), `strength` (0–1, quantised to 0.05), `since`, `ended` (date or null). Kin is never a tie: it is derived from the parent, children and spouse fields.

### population (aggregate state, as columns keyed by settlement id)

- `pop:<sex>:<band>`: counts in 5-year bands (0–4 up to 95+, so 2 × 20 columns).
- `allele:<locus>:<variant>`: **counts of allele copies**, integers. Invariant: for every locus, the copies sum to twice the aggregate count.
- `flow:<name>`: cumulative ledgers for conservation (§8.4): `initial`, `born`, `died`, `promoted`, `demoted`, `in`, `out`.

A settlement's column changes in one step are written **together** as one bulk delta (§15), not one per column.

## 3. Genome

### 3.1 Catalogue (world data, JSON)

```json
{"loci": [
  {"id": "eye", "variants": ["brown", "blue"], "model": "dominant", "order": ["brown", "blue"],
   "mutation": 1e-5, "traits": {"eye_colour": {"brown": 0, "blue": 1}}},
  {"id": "stature1", "variants": ["+", "-"], "model": "additive", "mutation": 1e-5,
   "traits": {"stature": {"+": 0.1, "-": -0.1}}}
 ],
 "groups": {"lowland": {"eye": {"brown": 0.8, "blue": 0.2}}},
 "traits": {"stature": {"base": 0.5, "environment": {"nutrition": 0.1}}}}
```

- **Models:**
  - `dominant`: the first variant in `order` that is present shows;
  - `additive`: allele effects sum;
  - `threshold`: sums that reach a required cut-off show a trait (polygenic gifts).
- **Groups** give founder frequencies. A settlement names its group, and a race can override it.

### 3.2 Alleles carry their origin

An allele copy is the string `variant@origin`:
- **Founder copies** (from synthesis or an aggregate): the origin is `f:<settlement or group>`.
- **Mutated copies:** the origin is the id of the birth event in which the mutation happened.

The Observatory's "genome with allele origins" (#102) needs nothing more. **Aggregates hold variant counts only**: a demoted allele loses its origin, and a promoted one gets `f:<settlement>`. This is documented, not a bug.

### 3.3 Inheritance

- **Assortment:** each locus independently takes one copy from each parent, by a keyed draw per child, per locus, per parent.
- **Linkage** is a later option (catalogue `chromosome`/`position`). It is not in M1.
- **Mutation:** a keyed draw per copy switches to another variant, with origin set to the birth event.
- **Unknown parent:** a copy is drawn from the settlement's allele counts, the same way as for promotion.

### 3.4 Phenotype

`traits = f(genome, environment)`, where `f` is a pure function of the catalogue. The environment is a small dict that the birth system snapshots, for example `nutrition` from the settlement's food state. Traits are computed once at birth and stored. Systems use them through ruleset parameters: longevity, fertility, wits (S7's planner), charm, temper.

**The trait catalogue is world data.** The Fourth Age's catalogue is a provisional draft (§11, Q1).

## 4. Life cycle

All of the following run settlement by settlement, each in `ctx.scope(settlement)`, over its `residents`.

### 4.1 people.life (seasonal): death

- **The draw:** `ctx.chance(q, "death", owner=person)`, where `q` comes from the race's hazard table by sex and age band, scaled by traits and circumstance (famine now; disease and catastrophe arrive with S10). It is quarterly: `q = 1 - (1 - annual)^(1/4)`.
- **Guard:** if `ctx.guarded(person)`, the system writes `people.near_miss` instead of a death (S1 machinery).
- **Hinges:** a death draw records a hinge only when its margin is close (S1's `hinge_margin`), with `stakes` raised for office holders, heirs and, once S7 exists, the ambitious.
- **Death writes:**
  - `status = dead`;
  - the spouse's `spouse = null`;
  - the ties' `ended`;
  - removal from the settlement's `residents`;
  - `flow:died`.
- **Succession:** a death that leaves an office empty schedules a **people.life follow-up** (`purpose="succession"`, payload: the office), caused by the death. Its `handle` runs the succession code in `ctx.scope(house)`. Follow-ups stay within one system, so S1's `schedule` is unchanged.

### 4.2 people.births (seasonal)

- **Who can have a child:** a married couple, both active, with the mother within the race's fertile ages and past a birth spacing (a parameter, default 18 months).
- **Odds:** `ctx.chance(p, "birth", owner=mother)`, with `p` from the race's fertility curve, the mother's fertility trait and the parity so far.
- **The child:**
  - a notable with a causal id (`creates`);
  - gets the genome by §3.3 and traits by §3.4;
  - takes the house by the house rule (default the father's) and the place of the mother;
  - is appended to both parents' `children` and to the settlement's `residents`, and counted in `flow:born`.
- **Twins:** a keyed draw. Twins get different names.
- **Crowding** (#67): a settlement may have a `capacity`. Fertility is scaled by
  `clamp(2 * (1 - residents / capacity), 0, 1.5)`: 1.5x when nearly empty, 1x at half capacity, none when
  full. Without a capacity, fertility is unlimited. (Aggregates and food arrive with #71 and S10; until
  then this keeps notable-only worlds from exploding.)
- **The same season:** births run before deaths, so a mother who dies this season may still give birth,
  and a newborn takes its first (band-0) death draw in the season it is born.
- **Spouses live together:** marriage moves one spouse (§4.4), so a birth reads and writes the father's
  `children` inside the mother's settlement scope. If a world ever lets spouses live apart, that write
  becomes cross-scope and must be revisited.
- **A mutated copy names its birth** through `ctx.peek_event_id`, so the child is created right the
  first time (no second write).

### 4.3 Canon born during the run: birth pins

S1 §3.9's rule applies: **an entity with a natural origin is never pre-created**. A pinned person born during the run (an Emperor after the first, or a modern character's ancestors) is a **birth pin**: an event pin of type `people.birth`, with roles `mother` and `father` (vault ids or earlier bindings), an optional `sex`, the `child` vault id, a name, and a window. S2 produces these pins (#61, #63). S1 casts only pins whose subjects exist at the start.

- **Observe (zero strain):** a natural `people.birth` inside the window, to the pinned parents, with the pinned sex if one is given, **fulfils** the pin. The pin binds `child → <causal id>` (a `pins` table row, and `manifest.casting`). The child's name is the canon name.
  - For a pin promoted from this very run, that is the name it already had, so the promotion no-op invariant holds: no draws, no strain.
  - A birth of the wrong sex simply doesn't fulfil the pin. No drawn outcome is ever overridden.
- **Guard:** the pinned parents are roles of an open event pin, so S1's guard already keeps them alive until the pin is met or forced.
- **No steering in M1.** Steering waits for #114 (M3), which defines it as a pure odds function.
- **Force:** at the deadline, the ruleset's `Forcer` for `people.birth` constructs the birth (caused by the pin, logged as strain). If the parents aren't married, it constructs the marriage first, as a `people.marriage` caused by the same pin.
- **Marriage pins:** a lineage whose parents must marry is a `people.marriage` event pin with the same observe, guard and force behaviour. The matcher (§4.4) makes no exception for it. Pins never bias odds in M1; they are met naturally or forced.

**S1 changes:** the director resolves a pin's role ids **through bindings** (a vault id bound earlier to a causal id), and `observe` accepts a `people.birth` whose roles match after resolution (§15).

### 4.4 people.marriage (yearly, per marriage region)

- **Who:** each region's settlements are read in scope, and the seekers come from their `residents`.
- **Eligibility:**
  - active, unmarried or widowed;
  - within the race's marriage ages;
  - **not kin**: no shared ancestor within `kin_degree` generations (default 2, so siblings and first cousins can't marry). The check walks recorded `mother`/`father` fields up the tree.
- **Matching:** `ctx.match`, S1's round-based rendezvous. Acceptance weights come from:
  - rank closeness of the houses;
  - an alliance bonus for crossing houses;
  - the age gap;
  - race.
- **Entering the market** (#67): each eligible man enters with `market_rate` per year (default 0.35).
  He weighs each eligible woman by `exp(-age gap / 8)`, ×2 for the same settlement and ×0.1 for another
  race. Kin are left out entirely, not just down-weighted.
- **One-way drain:** wives move to husbands, so a shrinking village can lose its young women and empty
  out (seen on some kin seeds; whole regions hold). Movement between places (S4 #77) rebalances it.
- **`flow:in` / `flow:out`** are written once aggregates and their ledgers exist (#71/#72); until then a
  move updates only `residents` and `place`.
- **Market size matters:** a closed market of a few dozen people runs out of unrelated partners within
  generations (seen on the kin world at 10 per settlement). Worlds need regions of a few hundred, or
  commoner spouses (below).
- **Commoner spouses:** a notable still unmatched `commoner_after` years past the minimum age may marry a commoner. The spouse is **promoted** from the local aggregate (§8.2).
- **Residence:** set by a world parameter (default: the wife moves to the husband's settlement). The move updates both settlements' `residents` and their `flow:in` and `flow:out`.

## 5. Houses, offices and succession

- **Succession rules are classes:**
  ```python
  class SuccessionRule:
      name: str
      def candidates(self, ctx, office) -> list[str]:  # ordered, best first; alive and eligible only
          ...
  ```
  - `MalePreferencePrimogeniture`: the holder's `children` in birth order, sons first, recursing into a dead child's line; then siblings (the parent's `children`); then the nearest kin within the house, walked through `children` fields.
  - `AbsolutePrimogeniture`: the same, ignoring sex.
  - Every read goes through recorded `children` fields, so a child born or dead in one run is a recorded read that differs, and the scope is tainted. That is explainable.
- **people.houses (yearly, one `ctx.scope(house)` per house):** recomputes each office's `heir` and emits `people.heir_named` only when the heir changes. Heirs are therefore first-class each generation (a PoC lesson). Births don't recompute heirs; this yearly pass does, so a birth never reads across houses.
- **Succession:** a holder's death triggers the follow-up in §4.1, which sets `holder = heir`, emits `people.succession` (cause: the death) and recomputes the heir.
- **Extinction:** when a house office has no candidate, the house gets `extinct` and a `people.house_extinct` event. Absorbing or founding a cadet branch is S8's job.
- **The imperial throne (#74), with the Emperors as a lineage (master §2):**
  - The eight Emperors are **one bloodline**: each is a **birth pin** whose parent is the previous Emperor (§4.3). The first Emperor is cast at the start.
  - Their **reigns in order** are `people.succession` event pins on the throne, one per Emperor, with windows from the dated timeline (#17), plus ordering pins between them. The throne uses the world's normal rule.
  - When the pinned successor is the natural heir (the eldest son, typically), the pin is observed with zero strain. Otherwise the pin's Forcer, at the deadline, constructs an **abdication** in favour of the pinned successor, caused by the pin and logged as strain. The predecessor's death isn't forced, and no rule is biased.
  - **Guarding ends** naturally: an Emperor is a role (`mother`/`father`) in the next Emperor's birth pin, and is guarded only until that birth. The successor is the guarded role in their own succession pin, until they accede. Nobody is guarded "until a reign ends", so there is no deadlock.
  - **The golden test:** all eight reign in order in every run, with strain reported.

## 6. Relationships

- **Kin is derived** from the `mother`, `father`, `children` and `spouse` fields, through helper functions (`parents`, `children`, `siblings`, `kin_within(n)`) that read through `Ctx`. Every hop is a recorded field read. There is no hidden index.
- **Ties** (non-kin) are records, plus each person's sorted `ties` list.
  - **people.ties (yearly, per settlement scope):** forms friend, rival and mentor ties at low rates from co-residence (similar age, same house; mentors are older with a higher trait). Strength decays, and ties end below 0.1 or on death.
  - **S7** adds enemy, patron and lover ties through actions.
  - **Events:** `people.tie_formed`, `people.tie_ended`, plus strength changes as state deltas.
- **As of any date:** ties and strengths are rebuilt from `state_deltas` (#69).

## 7. Drives

- **Drives are classes**, listed by the ruleset:
  ```python
  class Drive:
      name: str
      reads: frozenset[str]
      def level(self, ctx, person) -> float: ...  # 0 (desperate) .. 1 (sated)
  ```
- **Starter set:**
  - `food`: the settlement's food state;
  - `safety`: the settlement's danger, plus recent violence nearby;
  - `belonging`: spouse, children, ties;
  - `status`: house rank, offices held, heir status.
- **people.drives (yearly, per settlement scope):** sets `drives` when any drive moves by at least 0.05 (quantised). Each change is a state delta, so drives are visible as of any date (#70). S7 reads drives to form ambitions.

## 8. Populations and level of detail

### 8.1 Aggregates (#71)

`people.population` (seasonal) walks settlements in id order, each in `ctx.scope(settlement)`, and vectorises within a settlement:
- **Deaths:** for each band and sex, a binomial count with the band's quarterly hazard.
- **Births:** a binomial count from the fertile female bands and the race's fertility. Newborns enter band 0, split by sex at the world's sex ratio.
- **Ageing** (the first quarter of each year): a fifth of each band, binomially drawn, moves up one band.
- **Alleles:**
  - newborn copies are drawn from the settlement's counts (a keyed multinomial, two copies per newborn);
  - dying people's copies are removed by a **multivariate hypergeometric** draw, two per death, which stays integer and exact.
  
  So every locus's copies always sum to twice the aggregate count.
- **Draws** come from the settlement's keyed stream: `ctx.rng("population", settlement)`, keyed by (system, settlement, purpose, canonical tick, ordinal). S1's `Stream` gains `binomial`, `multinomial` and `hypergeometric` methods (§15).
- **Writes:** one bulk delta per settlement per season for all its changed columns (§15).
- **Timeseries:** a new **`timeseries`** run-folder table, with one row per settlement per year holding the counts by band and the notable count. The Observatory's population charts (#103) read it.

### 8.2 Promotion (#72)

S3 supplies the sampler and calls S1's `ctx.promote`, which is extended to take several column decrements (§15).
- **Draws:** keyed by (system, owner=settlement, purpose `promote:<reason>`, tick, ordinal). The promote event doesn't exist yet when the fields are sampled, so it can't key them.
- **Band and sex:** from the counts, constrained by the reason (a spouse is of marriageable age).
- **Birth date:** uniform within the band.
- **Genome:** two copies per locus drawn from the settlement's allele counts and decremented.
- **The rest:** parents unknown, the race from the settlement's race mix, and `residents` and `flow:promoted` updated.
- **Unknown-parent placeholders** (master §5.10) are created only when a pin needs an ancestor the aggregate has no record of. Otherwise the parents stay null.

### 8.3 Demotion (people.lod, yearly, per settlement scope)

- **Who can be demoted:** a resident who:
  - holds no office and is no heir;
  - isn't guarded by a pin;
  - has no active ambition or scheme (S7 supplies `demotable` predicates through the ruleset);
  - has no living notable spouse or minor child;
  - has been quiet for `quiet_years` (a `last_event` date, updated whenever they take part in an event).
- **When:** only while the **settlement's** residents outnumber its `notable_target`, with a keyed chance per candidate. The budget is per settlement, so a change elsewhere never changes who is demoted here.
- **Effect:**
  - counts and allele copies are added back;
  - `flow:demoted` and `residents` are updated;
  - the status becomes `dormant`.
  
  The dead are never demoted.

### 8.4 Conservation (the ruleset's `conservation(store)`)

These are checked from the store alone, using the `flow:` ledgers:
- **Counts:** for each settlement, the aggregate count plus residents equals `initial + born − died + in − out`, with both notables and the aggregate counted in the flows. Promotion and demotion move people between the aggregate and residents, so they balance inside the left-hand side. Their own flows are kept for the Observatory.
- **Alleles:** for every locus, the aggregate's copies equal twice the aggregate count. Inheritance copies alleles and mutation changes variants, so no wider "allele balance" exists. Allele *frequencies* are checked statistically: the drift over 250 years stays within bounds on the kin world.
- **Round trip:** a promotion followed by a demotion restores the counts and allele counts exactly (a property test).

## 9. Scenario synthesis (#73)

A **scenario** is world data (JSON):
- the start date;
- settlements: id, name, population, race mix, genome group, danger, notable target;
- races: hazard and fertility curves, marriage ages, name lists;
- houses: id, name, seat, rank, headship rule;
- offices;
- the genome catalogue;
- world parameters (residence, house inheritance, `kin_degree`, `quiet_years`, `commoner_after`).

Synthesis is deterministic from the seed, the scenario and the pin set. Casting (S2) runs first, so canon is placed and synthesis grows around it.

1. **Aggregates:** each settlement's age structure comes from the race's stable population, a life table computed from the hazard and fertility curves. Counts are keyed draws, and allele counts come from the genome group's frequencies.
2. **Houses:** each house gets a synthesised family:
   - a head aged 30–55, a spouse and 0–5 children, as the curves allow;
   - living siblings and their families, down to `house_depth`;
   - all of them notables with founder genomes.
   
   Canon (S2) replaces synthesised members where it names them.
3. **Offices:** holders and heirs are set by each office's rule.

**For the Fourth Age**, `worlds/renascita/fourth_age.json` is a **provisional draft** from the vault: the 12 Great Houses, Pyrosia's settlements with rough sizes, and races. It is marked as a draft, never canon, and S2 later supplies the canon parts. **For tests**, the kin world: 3 regions, 12 settlements, 4 houses, 2 races and a 10-locus catalogue.

## 10. Event types (all schema version 1)

| Type | Roles | Payload |
|---|---|---|
| `people.birth` | mother, father?, child | `twin`, `mutations` |
| `people.death` | deceased | `age`, `cause` |
| `people.near_miss` | survivor | `would_have` |
| `people.marriage` | spouse (2) | `commoner` |
| `people.heir_named` | holder, heir | `office` |
| `people.succession` | predecessor?, successor | `office`, `abdication` |
| `people.house_extinct` | (none) | `house` |
| `people.tie_formed` / `people.tie_ended` | a, b | `kind` |
| `lod.promote` / `lod.demote` | from S1 | `reason` |

**Run folder:**
- **`timeseries`** is a new table, which is a **minor format bump**. Old readers ignore unknown tables, and the Observatory treats it as optional.
- **No `people` table.** The master spec's §5.4 lists one, but people are fully described by `entities` (creation), `state_deltas` (every change) and `state.json.gz` (the final state). The Observatory's person page (#102) reads those, as the entity page already does. The master spec gets a one-line note.

## 11. Open questions (defaults chosen; on the review queue)

1. **Trait catalogue for the Fourth Age.** Default: a provisional generic set:
   - physical: eye colour, hair, stature, build;
   - abilities: constitution, longevity, fertility, wits, charm, will, temper;
   - one threshold "gift" locus standing in for Renascita's aptitudes, renamed when the lore names it.
2. **Great House succession.** Default: male-preference primogeniture (the master spec says "children then siblings"). Absolute primogeniture is one parameter away.
3. **House and residence.** Default: patrilineal houses, and the wife moves. Both are world parameters.
4. **Marriage among kin.** Default: no shared ancestor within 2 generations (first cousins are barred).
5. **Notable targets.** Default: per settlement, proportional to its population, summing to about 3,000 in the Fourth Age.
6. **Unfulfilled Emperor successions** are forced as an abdication, not a death (§5).

## 12. Costs and risks

**Rough M1 volumes:** 3,000 notables over 1,000 quarters.

| Item | Volume |
|---|---|
| Keyed draws | About 3M death draws, 0.5M births, 0.3M marriages and others: about 4–5M. |
| Events | About 150k. |
| Recorded reads | Tens of millions, if every read is logged as S1 does today. |
| Aggregate deltas | 50–200 settlements × 1,000 seasons, one each: 50k–200k small rows. |

| Risk | Mitigation |
|---|---|
| **Reads storage.** At these volumes the reads table alone would break the ~1 GB budget. | **#150 becomes a blocker for #66, not just the benchmark.** The plan does per-scope read hashes (a digest of a scope's reads instead of each row) plus a recipe flag for full reads, **before** the life cycle (§13 step 2). |
| **Per-draw cost.** Each `ctx.chance` builds a keyed Philox and a blake2b key: 4–5M of them could take many minutes. | Measure in #66. If it's too slow, a scope draws a purpose's numbers from one keyed stream per (scope, purpose, tick), with the person's position fixed by sorted `residents`. That is deterministic, and its coupling stays inside the scope (explainable), at the cost of somewhat wider waves. Each ticket records its numbers in `bench/history.csv`. |
| **Lineage pins over-constrain** the run. | Observe first, force at the deadline, with strain visible. The feasibility pass (S2 #62) checks windows against fertile ages first. Steering arrives with #114. |
| **Settlements couple through promotion.** | Promotion is scoped to the settlement and keyed by (settlement, purpose, tick, ordinal). A promotion that differs taints only that scope. A locality test covers it. |
| **Kin checks read deep ancestries.** | Bounded by `kin_degree`. Every hop is a recorded field read. |

## 13. Plan: working order

Each step is TDD on the kin world, with a code review and a merge per step. Each records its volumes.

1. **#65 Genome:** a pure module with the catalogue, inheritance, mutation, phenotype, and hypothesis property tests. Recessive traits resurface.
2. **#150 storage (S1 change):** per-scope read hashes plus a recipe flag for full reads. Divergence analysis works from hashes first and from full reads when present.
3. **S1 additions (§15),** as one small build ticket.
4. **#66 Life cycle:** settlements and residents, person records, `people.life` and `people.births`, guards, hinges. Measure the per-draw cost.
5. **#67 Marriage:** eligibility, kin checks, `ctx.match`, commoner spouses (they use a stub promoter until step 7).
6. **#68 Houses and offices:** succession rule classes, the yearly heir pass, succession follow-ups, extinction.
7. **#71 and #72 Aggregates and LOD:** populations, the timeseries table, the promotion sampler, demotion, flows and conservation.
8. **#69 Ties and #70 Drives.**
9. **Birth and marriage pins** (the S1 binding resolution, the Forcers): tested with kin-world lineage pins. It feeds #63 and #74.
10. **#73 Scenario synthesis:** generic synthesis, then the provisional Fourth Age scenario file.
11. **#74 Imperial office:** the eight-ruler golden test on the kin world, then on the Fourth Age once S2 casts.
12. **#75 Benchmark:** the whole Fourth Age, recorded in `bench/history.csv`.

The S2 loader and casting (#58–#63) can proceed in parallel. #73's Fourth Age file and #74's Fourth Age golden test wait for them.

## 14. Testing

- **Property tests:** inheritance (each copy comes from a parent or a mutation; mutation rates), the phenotype is pure, promotion followed by demotion round-trips, and the hypergeometric removal keeps the copies at twice the count.
- **Invariants on every kin-world run:**
  - no event names a dead person in an acting role;
  - genealogies are acyclic;
  - conservation holds;
  - every non-extinct house has a holder and a defined heir, or no candidate exists;
  - `residents` matches the places of the active notables.
- **Plausibility:** the age structure stays within the life table's range over 250 years (#66).
- **S1 guarantees on the kin world:** determinism, replay equivalence from several checkpoints, and **no unexplained divergence** for a protect ripple on a notable, a doom ripple on an heir, and a commoner-spouse promotion.
- **Golden tests:**
  - the eight-ruler pinned line (kin world now, the Fourth Age after S2);
  - a modern character born into a pinned lineage, with zero strain when the pin was promoted from the same run.

## 15. S1 additions S3 needs (one build ticket, step 3)

| Addition | Why |
|---|---|
| `Stream.binomial`, `Stream.multinomial`, `Stream.hypergeometric`, keyed and deterministic like the existing methods | Aggregate dynamics (§8.1). |
| `ctx.promote` / `ctx.demote` take several column changes (band plus allele columns) | Promotion and demotion (§8.2, §8.3). |
| `ctx.write_columns(entity, {column: value})`: one bulk delta for many columns | Aggregate storage (§2, §8.1). |
| Pin role ids resolve **through bindings**; `observe` binds a pin's `child` to the natural birth that fulfils it, recorded in `pins` and `manifest.casting` | Birth and marriage pins (§4.3). |
| `apply_pins` casts only pins whose subjects exist at the start (birth pins are never pre-created) | §4.3. |
| Per-scope read hashes plus a recipe flag for full reads (#150) | Storage (§12). |
