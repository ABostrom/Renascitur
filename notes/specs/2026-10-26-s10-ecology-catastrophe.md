# S10 Ecology & Catastrophe: Sub-project Spec

**Status:** r2, 2026-10-26. r1 was reviewed by an independent agent; r2 fixes:
- **ripples:** the harvest ripple fits `Ripple.check` and the one structural disguise; doom and inject
  dispatch on their params;
- **the masses:** deaths go through a shared `population.kill` (bands, alleles, flows; needs `aggregates`);
  SIR counts are kept consistent with the bands; deaths by cause get cast columns;
- **journeys:** night strikes are drawn per route leg at departure, since a journey has no legs at run time;
- **opt-in:** a new `ward.failed` type (the scripted one stays); effective danger is computed, so S7's `safety`
  is untouched; a siege's shortfall raises its fall chance; reads are added only when the switch is on;
- **the plan:** the full S9 dependency (#125 for trade-borne effects) is spelled out;
- **exit criteria:** forced-input unit tests per mechanism, goldens on chosen seeds, and series asserted
  rather than heatmaps.

Written without waiting for approval (the loop's low-ceremony rule); Aaron comments on #31 or the review queue
(#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §1 (the Fourth Age ruleset covers
  "aberrations and night terrors, Lux Lapis, the Vialux"); §6 S10 ("climate, harvests, disease, famine,
  aberrations and night terrors, Lux Lapis and wards"); the stats table ("derived indicators inside S8 and
  S10"); §5.9 ripples (structural: "a harvest fails"); §8.2 **M6** ("ecology and catastrophe with disease and
  famine heatmaps"); the PoC's "portable ward networks (S10)".
- **Vault:** `History/Third Age/Psychic Schism.md`: after the Schism, aberrations rained from the sky and night
  terrors descend "on travellers far from light sources"; Lux Lapis fell with them, and the Firebrand Empire's
  founder taught the forging of **Light Wards** (the Night War). Wards and Lux Lapis are canon in outline; every
  number here is a draft.
- **Builds on, as built:**
  - S3: `people.life`'s hazards, the masses' bands, alleles and flows, the `Illness` disguise;
  - S4: settlements' `danger`, routes, seasons and journeys (`travel.depart`, a path of places);
  - S6: beliefs and news;
  - S7: drives (`safety` reads `danger`);
  - S8: war, sieges and razing (`campaigns.py`);
  - S9: materials, stock and the goods ledger;
  - the scripted ward failure (`renascita/ward.py`, `ward.failure`), which stays.
- **Tickets:** #127 climate and harvests, #128 disease, #129 famine, #130 aberrations, night terrors, Lux Lapis
  and wards. Epic #11. The Observatory's views ride with each.

## 1. Scope and shape

S10 is the world pushing back: weather that makes or breaks a harvest, hunger when it breaks, sickness that
travels the roads, and the dark, where night terrors take whoever is far from a ward's light. Each is a slow
pressure on the masses (numbers) with sharp edges for notables (a death, a flight, a feud over grain).

**Opt-in by catalogue and switch.** A world without an `ecology` section runs as today, with identical events
and state and the same recipe hash. Each part has its own switch (`climate`, `disease`, `famine`, `night`).
A system's extra reads (a hunger factor on `people.life`, a shortfall on a siege) are added only when its
switch is on, as `campaigns: true` adds its system, so manifests of other worlds don't change.

**The masses need aggregates:** S10's effects on the masses require `aggregates: true` (`population.bump` does
nothing without it). A world without aggregates gets only the notables' side.

**One way to kill the masses:** a shared `population.kill(ctx, settlement, by_band, cause)` takes deaths out of
the bands, removes the dead's allele copies (the hypergeometric draw `Population.run` uses today, which it is
refactored to call), adds `flow:died`, and adds `died:<cause>` (cast int columns per cause, summing to
`flow:died`). Famine, disease, night and razing all use it, so S3's conservation checks still hold.

**Columns are cast:** `died:<cause>`, `sick:<disease>`, `immune:<disease>`, `food` (via S9's `stock:food`),
`wards`, and the climate's state are cast by the scenario builder from the catalogue.

## 2. Climate and harvests (#127)

- **Climate:** each region has a `climate` (catalogue: a mean and a spread per season for warmth and wet). Each
  season a keyed draw per region gives that season's anomaly, correlated a little with the last (a drought
  lasts). An event (`climate.season`) is emitted only for notable anomalies (drought, flood, hard winter).
- **Harvest:** at the harvest season, each settlement's farmers (S9 job shares) yield food into `stock:food`
  (S9's ledger: `produced`), scaled by the region's weather. **S10's harvest replaces S9's yearly food
  production** when `climate` is on; S9's other materials stay yearly. A bad harvest is `harvest.failed`, its
  cause the weather event.
- **The harvest ripple:** `{"kind": "structural", "target": <region>, "params": {"harvest": true, "factor":
  0..1, "until"?}}`. `Ripple.check` gains the `harvest` form, and the structural disguise (`geo.upheaval`)
  branches on it: one structural disguise per ruleset, two forms. It shows as an ordinary `harvest.failed`.

## 3. Famine (#129)

- **Consumption:** each season a settlement's people eat from `stock:food` (`used`). Short of it, a
  **shortfall** raises the masses' death rate by band (the old and the young first, through `population.kill`,
  cause "hunger") and notables' hazards (a `hunger` factor on `people.life`, read only when `famine` is on).
- **Responses:** notables may flee (S7 Flee's urge rises with hunger); a hungry town's leading house's Secede
  urge rises (S8). **Food drawn by trade needs S9 #125**; until then, famine has no relief but the harvest.
- **Sieges starve:** a besieged town's shortfall raises the siege's fall chance (`campaigns.siege`'s `p`, read
  only with `famine` on). A town with full stores holds longer.
- **Events:** `famine.began` and `famine.ended` per settlement (thresholds with hysteresis); deaths are
  `people.death` (cause "hunger") for notables and `died:hunger` for the masses.

## 4. Disease (#128)

- **Diseases** (catalogue): `{id, name, infectivity, lethality, duration_seasons, immunity_years, origin}`.
- **The masses:** each settlement carries `sick:<d>` and `immune:<d>` (cast ints). Each season, an SIR step by
  keyed binomials (`ctx.rng(purpose).binomial`, one per settlement, disease and transition): these draws skip
  the odds hooks and hinges, so ripples reach disease through its own forms (below). Disease deaths are spread
  over the bands in proportion to each band's share, weighted by the disease's age profile, through
  `population.kill` (cause the disease). **After every population step** (births, natural deaths, ageing,
  promotion, migration), `sick` and `immune` are prorated to the band total, so they never exceed it.
- **Notables:** each resident may catch it, with odds from the settlement's sick share (a keyed draw per
  person), and die of it (`people.death`, cause the disease) or recover (`disease.caught`,
  `disease.recovered`).
- **Spread:** a traveller from a sick town may carry it (decided at `depart`, recorded on the journey); on
  arrival, they seed the destination's sick count, `disease.outbreak` with the journey as its cause. Spread by
  trade flows needs S9 #125.
- **Beliefs (S6):** a predicate `plague(settlement)` spreads as news, raising flight; a `caused` claim can
  blame the wrong house.
- **Ripples:** `inject` an outbreak dispatches on `params.disease` (the ward-failure script keeps
  `params.script`); `protect` keeps a person well (disease asks `ctx.guarded` before a notable's death, as
  `life.die` already does).

## 5. Night: aberrations, night terrors, Lux Lapis and wards (#130)

- **Effective danger:** S4's `danger` stays the base a settlement was cast with (S7's `safety` reads it as
  today). With `night` on, an effective danger is computed from the base, the season's night factor
  (catalogue, per season), wards and surges. Routes gain `danger` and `warded` fields in the geography schema
  (`geo.check`, cast): the Vialux is warded by default.
- **Travellers:** a journey is one `depart` and one `arrive`, and its path is a list of places. So at `depart`
  each leg's route (path pair → route) and days give a keyed strike draw (`night:<leg>`, a fixed number of
  draws per journey). A strike is recorded on the journey and resolved on arrival (`travel.arrive`, which
  handles the follow-up for whichever system started the journey): `night.attack`, a death (`people.death`,
  cause "night terrors") unless guarded.
- **Towns:** a settlement's effective danger takes a small seasonal toll on its masses (`population.kill`,
  cause "night terrors") and, rarely, a notable.
- **Wards:** a settlement's `wards` (0..1, cast) cut danger multiplicatively. **Lux Lapis** is an S9 material
  that wards use up; a **warden** (an S9 job) keeps them. Neglected, they decay. A ward can fail
  (**`ward.failed`**, a new type; the scripted M2 `ward.failure` stays as it is):
  - by decay (no Lux Lapis, no warden);
  - by sabotage (a new S7 action `Sabotage`, secret, against a rival's town or caravan, planned by the existing
    harms' ambitions (Ruin, Vengeance) when the world has `night` on);
  - by an aberration surge.
- **Aberrations:** surges (`night.surge`, a keyed seasonal draw per region at the catalogue's rate) raise a
  region's danger for some seasons. A surge on a ward-failed town is a catastrophe: many deaths, flight, and
  possibly ruin through S8's raze path, cause "night terrors".
- **Ripples:** `doom` on a ward entity fails it (the doom disguise dispatches on the target's kind: a person
  dies as today); `protect` on a ward keeps it (ward code asks `ctx.guarded(ward)` before `ward.failed`).

## 6. Observatory

- **Heatmaps** on the map by year: famine (shortfall), disease (sick share), danger (effective, with wards) per
  settlement, with a layer chooser, read from the run's series.
- **Settlement page:** food stock, harvests and shortfalls, sickness and deaths by cause (`died:*`) over time.
- **Events:** outbreaks, famines and ward failures in the event browser's filters. A catastrophe's cause chain
  (weather → harvest → famine → flight → a feud) is the story the explorer already shows.

## 7. Temporal LOD

Climate, harvest, famine and the masses' disease steps have coarse fallbacks: N seasons' weather as one draw
per region, a mean harvest, SIR stepped in one go with the same conservation. Night strikes on travellers come
with journeys, which only fine time makes; a coarse step applies an aggregate toll on the settlement instead.

## 8. Exit criteria

- **One unit test per mechanism, with forced inputs** (a pinned anomaly, a pinned shortfall, a seeded outbreak,
  a forced strike, a decayed ward): each produces its events, its deaths through `population.kill`, and a
  balanced ledger.
- **A golden on chosen seeds** (Fourth Age 4A 1–100, ecology on, a draft catalogue; the seeds are recorded,
  not "most"):
  - a `famine.began` whose cause chain reaches a `harvest.failed` and a weather event, with `died:hunger` > 0;
  - an outbreak in one settlement seeding a second by a recorded journey, visible in the `sick:*` series
    season by season;
  - night deaths rising with unwarded road-days: across the run's journeys, the strike rate per unwarded day
    exceeds the rate per warded day by at least a set factor;
  - an unscripted `ward.failed` (decay or sabotage) on at least one of the chosen seeds;
  - S3's population ledger, the `died:*` sum, and S9's goods ledger balance every season.
- A structural harvest ripple makes a recorded difference traced to it by divergence analysis.
- Worlds without an ecology catalogue are unchanged: identical events and state, and the same recipe hash.
- Budget: ecology adds at most 30% to a 4A 1–100 run.

## 9. Open questions (defaults chosen; on the review queue)

1. **The catalogue** (climates per region, the diseases, aberration rates, night factors): default, a small
   draft.
2. **Lux Lapis:** an S9 material that wards consume (default), or a resource found only where it fell.
3. **Who keeps the wards:** a warden job (default) or a guild (the vault's Lux Faber) as an S8 faction.
4. **How lethal the night is:** tuned so the Vialux is nearly safe and wild roads at night truly dangerous;
   the numbers are drafts.

## 10. Plan: working order

0. **Prerequisites:**
   - S9 #123–#124: jobs (farmer, warden), materials (food, Lux Lapis), stock and the goods ledger, cast columns;
   - `population.kill` and `died:*` (a small S3 refactor, the first S10 ticket's first task).
1. **#127 Climate and harvests**, with the structural harvest form.
2. **#129 Famine:** consumption, shortfall hazards, flight and Secede urges, sieges starving. Relief by trade
   waits for S9 #125.
3. **#128 Disease:** SIR for the masses with proration, notables, spread by journeys, beliefs, inject and
   protect. Spread by trade waits for #125.
4. **#130 Night:** effective danger, route fields, strikes per leg, wards, Lux Lapis, decay, `Sabotage`,
   surges, the doom and protect forms.
5. The heatmaps and settlement views, and the golden.

**Risky bits:**
- **Death-toll tuning:** famine and plague can empty a world. Tests check mechanisms and conservation, never a
  given toll, and the draft rates start gentle.
- **Keeping counts consistent:** SIR counts against bands, `died:*` against `flow:died`, allele copies against
  masses. One shared kill path, and prorating after every population step.
- **Coupling with S8 and S9:** sieges starving, famines fuelling risings, trade-borne plague. Each sits behind
  its switch, so other worlds keep their histories.
