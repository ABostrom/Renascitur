# S9 Work, Crafts & Objects: Sub-project Spec

**Status:** r2, 2026-10-26. r1 was reviewed by an independent agent; r2 fixes:
- columns are cast up front (the store can't make them mid-run), and stock is an int;
- one system (`objects`) owns every object field; event roles and `dead_roles` are listed;
- deeds are limited to what events record (no "kills in a battle": battles name polities, not people);
- Covet and Steal draw nothing without a famous object, so worlds without crafts keep their history;
- the ripple criterion uses kinds that reach the masterwork draw; `plant`'s object form has its own params;
- `wealth` arrives with jobs (#123), before first owners need it; trade's opt-in param is named;
- exit criteria are countable; the Observatory gets a trade view.

Written without waiting for approval (the loop's low-ceremony rule); Aaron comments on #30 or the review queue
(#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §6 S9 ("jobs, materials, crafting,
  trade, object biographies"); §8.2 **M6** ("crafts and objects: the sword story emerges unscripted"); §5.9
  ripples (`plant` an object); S13's **Objects** inspector.
- **Handed to S9 by earlier specs:** S1's `plant` ripple ("planting an object waits for S9's objects",
  `PlantRumour`); S8's trade along open border routes (`relations.TRADE`, a flat per-route pull today); S8's
  levies and razing (what a sack destroys).
- **Builds on, as built:** S3 people, houses, populations and the conservation ledger (`population.bump`,
  `FLOWS`, cast columns); S4 settlements, routes and journeys (`geo.path`, `travel`); S6 claims and beliefs
  (predicates, `shares`, news by road); S7 ambitions, actions, schemes and the planner; S8 polities, relations,
  war and campaigns; S1 LOD (`coarse_fallback`, `relations.over`), ripples and pins.
- **Vault:** `type: item`, `artifact` and `resource` notes are reference (S2: "loaded, linked, given ids; not
  pinned in M1"). Canon artifacts (the Blade of Typhon, Second Age) arrive with the age handoffs (M7a, #136),
  not here. The Lux Faber guild is the Fourth Age's crafters (draft use only).
- **Tickets:** #123 jobs, skills and wealth; #124 materials and crafting; #125 trade; #126 object
  biographies; #109 the Observatory's object pages. Epic #10.

## 1. Scope and shape

S9 gives notables work, lets the skilled make things, moves goods along roads, and gives the things that
matter a **biography**: who made it, who held it, what it did, where it was lost and who found it. Its test is
the master spec's: **a sword story emerges unscripted** (a masterwork blade is forged, carried, named by its
deeds, lost with its bearer, found again, and coveted).

**Two scales, as everywhere:** notables are people with jobs, skills, wealth and possessions; the masses are
numbers (a settlement's workers, output and stock). **Only objects that matter are entities** (masterworks,
heirlooms, named things, and later a pinned vault artifact); ordinary goods are numbers in a settlement's
stock. That keeps the store small: a few hundred objects in a century, not millions of spoons.

Everything is world data: the jobs, materials and object types come from the world's catalogue (Renascita's
are a clearly marked draft). **A world without a `crafts` catalogue runs exactly as today:** no systems, no
columns, no draws.

**Columns are cast, not made:** the store can't add a column mid-run (`Engine.cast_column` is cast-time only),
so the scenario builder casts every settlement's `job:<id>` (int: masses in each job), `stock:<material>`
(int units) and the goods ledger's `goods:<material>:<flow>` columns from the catalogue. Systems declare
them by prefix (`job:*`, `stock:*`, `goods:*`).

## 2. Jobs, skills and wealth (#123)

- **Catalogue:** `jobs: {id: {name, makes?, income, demand}}` in the world's catalogue. Renascita's draft:
  farmer, herder, smith, weaver, mason, merchant, soldier, scholar, priest, steward. A noble's work is their
  office.
- **A notable's `job`** is chosen at adulthood (`people.work`, yearly, per settlement scope): a keyed draw
  weighted by the settlement's demand for each job (its catalogue weight times what it lacks), the parents'
  jobs (a smith's child leans to the forge), and house (a great house's children take offices and
  soldiering). It changes rarely (`people.job_changed`: hard times, a patron, a war's levy).
- **`wealth`** (a notable's number, abstract coin) grows with their job's yearly `income` (a merchant's and a
  master's most) and is spent on masterworks (§3) and favour. A sack or a raid takes some.
- **`skills`** (`{job: 0..1}`) grow each year a notable works, faster young and with wits (the S7 trait
  role), with diminishing returns; idleness lets them fade. Crafting and trade read skill; a soldier's skill
  can later add to a levy's quality.
- **The masses** keep job shares as the cast `job:<id>` columns, drifting toward demand; they set a
  settlement's output (§3) without individual people.

## 3. Materials and crafting (#124)

- **Materials:** `materials: {id: {name, yield: {region: rate}, value}}`. A settlement's region yields
  materials yearly into its **stock** (`stock:<material>`), scaled by its workers in the producing jobs.
- **The goods ledger:** every change to a stock is a flow with a reason: `produced`, `used`, `traded_in`,
  `traded_out`, `destroyed`, summed in `goods:<m>:<flow>`. The invariant, exact in ints: initial + produced +
  traded_in = stock + used + traded_out + destroyed.
- **Making:** a notable whose job `makes` a type (a smith makes blades and tools, a weaver cloth) uses stock
  and turns out ordinary goods (numbers). Each year, a keyed draw (purpose `act:craft`, so S1's favour ripple
  reaches it) at `skill^3 × MASTER_RATE` makes a **masterwork**: an **object** entity.
- **An object** (`kind: object`): `name` (none until it earns one), `type` (blade, armour, ring, book, tool),
  `material`, `maker`, `made` (date, place), `quality` (from skill), `owner`, `place` (where it lies when
  unowned), `deeds` (event ids), `fame` (0..1), `lost` (date or null). A destroyed object's status is
  `destroyed`, so no later event names it. Its biography is every event naming it in a role.
- **First owners:** a masterwork is sold or given: a keyed pick among nearby notables, weighted by `wealth` and
  by ties to the maker (a lord's commission wins). `object.made`, then `object.given`.
- **One owner of object fields:** the `objects` system (yearly, plus follow-ups) is the only writer of an
  object's `owner`, `place`, `lost`, `deeds`, `fame` and status. Other systems emit their own events (a death,
  a duel, a sack, a theft) and `objects` reacts: `life.die` and `Campaigns.raze` schedule an `objects`
  follow-up for anyone holding objects (as `vacate` schedules a succession), and so does Steal's success.

## 4. Trade (#125)

- **Goods are numbers.** Each year (`trade.flows`, yearly, one scope per route) stock flows along open routes
  from where a material is plentiful to where it is scarce (a gradient of stock per head), capped by the
  route's days and merchants present. Flows conserve: what leaves one stock enters another, on the ledger.
- **Polities shape it:** routes between polities at war carry nothing; a trade treaty raises the cap; tolls
  later. **S8's flat `TRADE` pull becomes the actual flow** (trust grows with goods exchanged) when the world
  sets `trade: true`. S8 worlds without it keep the flat pull and their histories.
- **Merchants** (a job) carry flows and earn `wealth`; wealth buys masterworks and favour (S7 `CourtFavour`
  odds), and is what a raid or a sack takes.

## 5. Object biographies (#126)

What happens to an object is ordinary events, each naming it in a role (`object`):
- **given and inherited:** an owner's death passes it to their heir (the house's heir, else the eldest child,
  else the spouse) (`object.inherited`); gifts at marriages and between friends (`object.given`).
- **deeds:** an owner who wins a duel (a successful `people.action` Duel), survives a battle their realm won
  while holding a command or office, or is guarded through a near miss while carrying it gives it a deed
  (`object.deed`) and fame. At fame ≥ `NAMED` it is **named** (`object.named`), a name from the world's
  naming tables and its deed ("the Blade of Redcairn"). (Kills in battle aren't recorded per person, since
  battles name polities; they wait for notables in the field, S8 #122.)
- **lost and found:** an owner who dies away from home (a journey, a battle, a sack) loses it there with a keyed
  chance (`object.lost`, `place` set, no owner). Each year someone living at or passing a place with a lost
  object may find it (`object.found`), likelier the more famous it is and the more people pass.
- **coveted and stolen:** a famous object is an **ambition**'s target (S7 `Covet`: a notable who knows of it,
  status-hungry or of its maker's line); the plot is a new action `Steal` (secret, in person) or S7's harms
  against its holder. A stolen object is held openly or hidden (S6: who believes who has it). **Covet is
  eligible only when a famous object exists, and draws nothing otherwise; only Covet ever plans Steal**, so
  adding them to the library changes no world without crafts.
- **destroyed:** a sack may destroy objects in a town (rare).
- **Event types** (roles; `[dead]` marks a `dead_roles` entry): `object.made` (maker, object),
  `object.given` (giver 0..1, owner, object), `object.inherited` (from [dead], owner, object), `object.deed`
  (owner, object; the deed's event in the payload), `object.named` (object), `object.lost` (owner [dead],
  object; place), `object.found` (finder, object; place), `object.stolen` (thief, from, object),
  `object.destroyed` (object; place).
- **Beliefs (S6):** new predicates `owns(object, by)` and `made(object, by)`. An object's fame spreads its
  claims through `shares` like any news, so a lost blade is "known to be somewhere in Redcairn".
- **Ripples:** S1's `plant` gains an object form: `params.object` (`{type, material, quality, name?}`) instead
  of `params.claim`, checked by its disguise as a claim is, appearing as `object.found` at the target place.
  `protect` covers an object: `objects` asks `ctx.guarded(object)` before `object.lost` and
  `object.destroyed` (a protected object is kept, a near miss), for the "what if it survived" latch point.

## 6. Observatory (#109)

- An **object page** (`/run/<name>/object/<id>`): its biography as a timeline (made, owners as a strip, deeds,
  lost and found), its makers and owners linked, its fame over time.
- An **objects list:** named and famous objects, filterable by type and age.
- A **trade view:** each route's flows over time (a strip per route in the map page's route table), so a war
  cutting a route shows as its flow falling to nothing.
- The person page gains possessions; a settlement page its stock over time.

## 7. Temporal LOD

Every S9 system has a `coarse_fallback`: jobs and skills step N years at once; crafting draws "a masterwork in
N years" (`over(p, years)`); trade moves N years of flow as one flow (N times the year's, capped by the stock
there; the ledger rule is unchanged, each flow entered once in full); finding draws over N years. Deeds need
fine time (battles, duels), so they mostly come from focus windows.

## 8. Exit criteria

- A Fourth Age 4A 1–100 run with crafts on (Renascita's draft catalogue), on 5 fixed seeds:
  - **the sword story:** in at least 3 of the 5, an object whose biography holds, in this order,
    `object.made`, `object.given`, a deed, `object.named`, then `object.lost` or `object.stolen`, with at
    least 3 owners over its life (checked on the event log; the object page shows it);
  - **goods conserve:** the goods ledger balances every year, exactly;
  - **a ripple on a smith** (doom before their masterwork, or favour) makes a recorded difference to whether
    a masterwork exists, which divergence analysis traces to the ripple;
  - **trade follows the map:** in a seed with a war, a route between the two sides carries no flow while the
    war lasts (on the ledger), and the trade view shows it.
- Worlds without a crafts catalogue are unchanged (their recipe hash and history).
- Budget: crafts add at most 25% to a 4A 1–100 run's time.

## 9. Open questions (defaults chosen; on the review queue)

1. **The jobs and materials catalogue** for Renascita: default, a short draft list (§2–3). Lux Lapis as a
   material is S10's call, since its wards are S10's.
2. **Money:** an abstract `wealth` number (default), or a currency from the vault.
3. **Which objects deserve entities:** masterworks and heirlooms (default), or every weapon a notable carries.
4. **Vault artifacts:** reference now; pinned objects (a canon artifact that must exist, held by X in 4A Y)
   come with the age handoffs (#136).

## 10. Plan: working order

1. **#123 Jobs, skills and wealth:** the catalogue schema and Renascita's draft; the cast columns;
   `people.work`; skills; wealth; the masses' job shares. (Small: no new entity kinds.)
2. **#124 Materials and crafting:** materials and stock, the goods ledger, crafting and masterworks, the object
   entity and the `objects` system, first owners.
3. **#126 Object biographies:** inheritance, deeds and naming, lost and found, Covet and Steal, the S6
   predicates, the `plant` and `protect` object forms.
4. **#109 The Observatory's object pages** (can start once #124 writes objects).
5. **#125 Trade:** flows, the ledger across routes, merchants' income, S8's trade from flows (`trade: true`),
   the trade view.
6. The exit-criteria golden (the sword story over 5 seeds) and the budget check.

**Risky bits:**
- **Object explosion:** only masterworks and heirlooms are entities, with a cap per settlement-year as a guard.
- **Conservation:** goods move in three systems (crafting, trade, war): one ledger, one invariant, from the
  start.
- **The sword story is emergent, not scripted:** the criteria ask for its shape in most seeds, never a given
  blade's fate. Tuning `MASTER_RATE`, `NAMED` and the find odds is the work.
- **History preservation:** every addition (Covet, Steal, trade from flows) is inert without the world's opt-in,
  as every addition so far has been.
