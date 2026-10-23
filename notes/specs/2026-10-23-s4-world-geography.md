# S4 World Model & Geography: Sub-project Spec

**Status:** r2, 2026-10-23.
- r1 was reviewed by an independent agent. r2 fixes: Flee's duration (the journey carries the days, not the step), settlements in the geography but not the scenario, who declares `journey`, a second mover so the done-when isn't empty, `Court` out of the presence list, route ids (`r:` is races), the run-folder copy, read declarations, arrival details, and drops the wedding's travel days.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #25 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §2 (Geography), §3 (Entity), §6 S4, §8.1–8.2 (M1, M2).
- **Builds on:** S1 (engine), S3 (settlements, residents, marriage residence) and S7 (`Flee`, scheme steps) as built.
- **Tickets:** #76 (format + Pyrosia graph) and #77 (movement) are M1. #78–#81 are M2 and only sketched here (§8).

## 0. In one paragraph

M1 needs a world people can **move through**, not a map. S4 (minimal) adds a **geography file**: places, regions and routes (with travel days and a Vialux flag), one per world, plain JSON in git. The engine casts it at the start of a run as entities, finds paths over it, and turns a move (fleeing, or a small yearly migration) into a **journey** with a departure and an arrival, so travel takes the days the route says. The Observatory reads the same file from the run folder. The full model (cell mesh, routing by mode, season and time of day, news by road, the map by year) is M2.

**Done (minimal) when** the Fourth Age draft moves people between Pyrosia places along routes, and every arrival is dated by the route's days.

## 1. Principles

- **Data, not code.** A world's geography is a JSON file; the engine knows nothing of Pyrosia.
- **Ids are the vault's.** A place that has a vault note uses its id (`v:lions-rest`), as the Fourth Age scenario already does; a place, region or route with no note gets a `g:` id (`g` joins `core.ids.CAST_PREFIXES`; `r:` is taken by races).
- **Static in M1, entities anyway.** Routes and regions are cast as entities so that M2 can change them over time (a road opens, a pass closes) without changing how systems read them.
- **One path rule.** Every system that needs "how far" or "which way" calls the same function (§4), so travel time means the same thing everywhere.
- **Deterministic.** Paths are a pure function of the routes; ties break by id.

## 2. The geography file (#76)

One JSON object per world, saved with sorted keys, two-space indent and one record per line inside each list, so a diff shows one changed place or route per line.

```json
{
  "about": "Pyrosia, hand-drawn for M1. Provisional: every number is a placeholder.",
  "draft": true,
  "regions": [
    {"id": "v:ashen-plains", "name": "Ashen Plains", "within": "v:pyrosia"}
  ],
  "places": [
    {"id": "v:lions-rest", "name": "Lion’s Rest", "kind": "settlement", "region": "v:ashen-plains"},
    {"id": "v:candle-keep", "name": "Candle Keep", "kind": "landmark", "region": "v:ashen-plains", "at": [41.5, 22.0]}
  ],
  "routes": [
    {"id": "g:lions-rest--lux-oescus", "ends": ["v:lions-rest", "v:lux-oescus"], "days": 6, "kind": "road", "vialux": true}
  ]
}
```

| Field | Meaning |
|---|---|
| `regions[].within` | Optional parent (a continent or realm). Regions nest; a place names its innermost region. |
| `places[].kind` | `settlement` (people live there) or any other word (`landmark`, `fortress`, `ruin`, `waypoint`…). Only settlements have residents in M1. |
| `places[].at` | Optional position in **map cells** (1 cell = 24 miles), for drawing only. Never read by the sim. |
| `routes[].ends` | Two place ids. Routes are **undirected** in M1. |
| `routes[].days` | Travel days on foot at an ordinary pace. A positive integer, required in M1 (no derivation from `at`). |
| `routes[].kind` | `road`, `track`, `river`, `sea`, `pass`. Data only in M1; M2 routes by mode. |
| `routes[].vialux` | True for the Vialux. Data only in M1 (drawn distinctly); M2 makes it safe at night (§8). |

**Validation** (`renasci.geo.load` returns findings, like the vault loader; a world with an error doesn't run):
- ids are unique across regions, places and routes, and match `v:…` or `g:…`;
- every `region`, `within` and route end names a known entry; `within` has no cycle;
- `days` is a positive integer; no route joins a place to itself; two routes may join the same pair (a road and a sea lane) but must differ in `kind`;
- **warning** if the settlements aren't all connected (a run may still want an island).

**The scenario names its geography** (`"geography": "pyrosia.json"`, relative to the scenario). Then the scenario's settlements and the geography's places of kind `settlement` must be **the same set** (a settlement nobody lives in is a `landmark` or `ruin`), each with the same `region`, and the scenario's `regions` map is derived from the geography (if the scenario also has one, it must agree). A scenario without a geography runs as today: no routes, no journeys, moves are instant (the kin and toy worlds stay as they are).

## 3. In the engine

At the start of a run, `synthesise` casts the geography after the settlements:
- **regions** as `region` entities (`name`, `within`);
- **places** that aren't settlements as `place` entities (`name`, `kind`, `region`); settlements stay `settlement` entities and gain nothing but the check above;
- **routes** as `route` entities (`ends`, `days`, `kind`, `vialux`, `open: true`).

`cli._run` writes a copy of the file into the run folder as `geography.json`, and `_replay` copies it into a forked folder, the same way `canon.json` is handled (neither is in the manifest). It is for the Observatory: replays take routes from the checkpoint's store.

Systems that read routes declare `ids:route` and the fields they read (`ends`, `days`, `open`), plus `region` and `within` where regions are read. In M1 nothing writes them after the start.

## 4. Paths

`renasci.geo.path(ctx, a, b) -> (days, [place ids]) | None`: the shortest path by `days` over **open** routes, Dijkstra, ties broken by the lexicographically smaller list of place ids. `None` when there is no path. `geo.reach(ctx, a, max_days)` gives every place within `max_days`, with its days.

The graph is small (tens of places in M1), so `path` rebuilds the adjacency from the route entities on every call. Clarity first; a cache keyed on the routes' versions can come with the benchmark (#75) if it shows up.

## 5. Movement (#77)

A move between settlements is a **journey**:

1. **Depart:** `travel.depart(ctx, person, to, why, causes=())` finds the path; if none, the move doesn't happen (returns `None`). Otherwise it sets the person's `journey` to `{"from", "to", "path", "depart", "arrive", "why"}`, emits `people.depart`, and schedules an `arrive` follow-up `days` later (`entity=person`). The person stays a resident of the origin while on the road: residents and population flows change only on arrival, so the conservation invariants hold through a journey.
2. **On the road:** a traveller isn't in the marriage market, isn't a candidate for `Court`, and can't take another journey (`Flee` is impossible while `journey` is set). They age, scheme and can die; a death on the road is recorded at the origin with a `journey` field in the death's payload, and clears the journey. So `journey` joins `life.DIE_READS`/`DIE_WRITES` (Life, Illness, Schemes and the forcers inherit them), and Marriage and `Court` declare reading it.
3. **Arrive:** the `arrive` activation, in its own scope, checks the person is still `active` (so a traveller demoted to the masses mid-journey arrives nowhere) and the journey is still the one it was scheduled for (same `depart`); then it moves them (residents, `place`, flows in and out, as `families._wed` and `Flee` do today), clears `journey`, and emits `people.arrive`, caused by the departure.

`ctx.schedule` schedules follow-ups for the calling system, so **the system that starts a journey handles its `arrive`** by calling `travel.arrive`. In M1 that is the schemes system (for `Flee`; `Schemes.handle` gains the `arrive` purpose) and the migration system below.

**Ruleset switches:** `Engine._switch` drops queued activations of a system whose cadence or priority changed, which would strand a traveller. A switch clears every `journey` whose `arrive` was dropped (the traveller stays home); test it.

**Who moves in M1:**
- **`Flee`** goes to any settlement (`ctx.ids("settlement")`) reachable within `flee_days` (a new world param, validated in `life.world_params`: a positive int, default 30) instead of only its own region, chosen by `ctx.choose` with nearer places weighted higher (weight `1 / days`). The step keeps a short fixed duration (deciding to go); `succeed` calls `travel.depart`, so the journey alone carries the route's days and nothing counts them twice.
- **Migration** (`people.migration`, yearly): `Flee` needs an unmarried, office-less schemer whose plan contains it, which may be too rare for the done-when. So each unmarried adult notable with no office has a small yearly chance (`migration_rate`, default 0.01) to set out for a reachable settlement, weighted by `1 / days` and the destination's free capacity. Before tuning, measure how often `Flee` fires in a Fourth Age run.
- **Marriage residence** stays instant in M1: the bride's (or groom's) party is taken to arrive before the wedding, and the market is regional, so the gap is days. (A journey here would break "spouses always share a settlement", which births rely on; revisit if markets go cross-region.)
- **Nothing else moves people yet.** Seasonal travel and households moving together are not M1.

## 6. Presence for actions

Some S7 actions need the actor where the target is: `Duel`, `Poison`, `Assassinate`. (`Court` has no target: it already looks only at the actor's own settlement, and a traveller can't court.) An action gains `present = True` for those. When actor and target live in different settlements, the step's duration grows by the path's days (the actor goes there; the return isn't modelled), and the action is impossible if there's no path. `Action.duration(ctx, actor, target)` replaces `schemes._next` reading `duration_days` directly (the target is known when the step is scheduled); it is `duration_days` when presence doesn't apply or there's no geography. Actions without presence (`Petition`, `Shame`, `Recruit` by letter) are unchanged.

## 7. The Pyrosia draft (#76)

`src/renasci/renascita/pyrosia.json`, generated by `scripts/pyrosia_draft.py` from the vault and a hand-kept routes table in the script:
- **Places:** the six cities (settlements) and the named locations under `Geography/Pyrosia` (landmarks, ruins, keeps), about 25 in all. Ids are the vault's (`v:` slugs from `vault.ids.assign`, so they match once Aaron writes the ids); names are the note titles.
- **Regions:** Pyrosia and its provinces, from the folder layout (`Provinces/<name>`); a city's region is the scenario's, a location's is the city or province folder it sits in.
- **Routes:** hand-written, enough to connect every settlement; days are **placeholders**, marked so by the file's `draft: true` and `about`. The Vialux flag is set on routes the vault describes as part of it (none yet carry dates or exact courses; this is a guess, clearly marked).
- **No positions from the map.** `images/Renascitur.png` stays private, so the draft has no `at` coordinates; the Observatory lays the graph out itself until Aaron decides (queue question).

A test checks that the draft loads with no errors, every scenario settlement is connected, and every `v:` id is one `vault.ids.assign` would give a note.

## 8. The full model (M2, sketched)

- **#80 Cell mesh:** a Voronoi mesh over the map (1 cell = 24 miles) with terrain per cell; places sit in cells and routes become cell paths, so `days` derive from terrain and length.
- **#78 Routing by mode, season, time of day and access:** `path` takes a traveller (mode: foot, horse, cart, ship; their access) and a date; each route gains cost per mode and season and danger by time of day. The Vialux is safe at night, so journeys on it don't stop at dusk.
- **#79 News travels by route:** S6 claims spread along the same paths, at the speed of whoever carries them.
- **#81 The map by year:** route and place fields change by events (a road built, a city razed); the Observatory shows the map at a date.

M2's routing keeps `path`'s signature with optional arguments, so M1 callers don't change.

## 9. Testing

- **Loader:** each validation rule has a failing fixture; a good file round-trips (load, save, identical bytes).
- **Paths:** a small fixture graph checks shortest days, ties broken by id, closed routes avoided, unreachable gives `None`, `reach` bounds.
- **Journeys:** a person departs and arrives exactly `days` later; residents don't change until arrival; a death on the road clears the journey and the arrival does nothing; a replay from a checkpoint taken mid-journey arrives on the same day (the journey is plain JSON).
- **Migration:** with geography, a decade of a small world has migrants who arrive on the path's days; without geography, no migration system runs.
- **Switch:** a ruleset switch that drops an `arrive` clears that journey.
- **Flee:** with geography, a fleeing person can leave their region and arrives on the path's days; without geography, behaviour is unchanged (existing tests pass untouched).
- **Presence:** a duel against someone two settlements away lasts `30 + days`.
- **Settlement sets:** a geography settlement the scenario lacks (or the reverse) is an error.
- **Fourth Age:** a run of the draft over a few decades has journeys that arrive, and conservation holds.

## 10. Open questions (defaults chosen; on the review queue)

1. **Map positions.** May the draft carry `at` coordinates read from the private Inkarnate map? Default: no; the Observatory lays the graph out.
2. **Travel days.** Placeholders by eye from the vault's prose. Aaron may want real numbers from the map (24 miles a cell, ~20 miles a day on foot).
3. **Marriage moves** stay instant in M1 (§5). Default kept until the marriage market crosses regions.
4. **Migration** (§5) is a new, small behaviour so the Fourth Age shows journeys at all. Default rate 1% a year for unmarried adult notables.

## 11. Plan: working order

1. **#76 Format and loader:** `renasci/geo.py` (load, validate, save, `path`, `reach`) with fixtures. Scenario `geography` key and its checks; casting regions, places and routes; `geography.json` in the run folder.
2. **#76 Pyrosia draft:** `scripts/pyrosia_draft.py` and `pyrosia.json`; the Fourth Age scenario names it.
3. **#77 Journeys:** `travel.depart` and `travel.arrive`, the `journey` field and its declarations, the market and `Court` skipping travellers, the switch clean-up; `Flee` through journeys; migration.
4. **#77 Presence:** `Action.present` and `Action.duration`.
5. **Observatory:** read `geography.json` and draw the graph (places, routes, Vialux, who is where and on the road), as part of the population-by-place work (#103) or its own ticket.

**Risky bits:**
- **Checkpoints mid-journey:** the `arrive` activation and the `journey` field must both survive a checkpoint; test it first.
- **Read declarations:** systems that now call `path` must declare `ids:route` and the route fields, or the context's read checks fail.
- **Fourth Age behaviour drift:** `Flee`'s wider reach changes existing stories. The S7 story tests use the kin world, which has no geography, so they shouldn't move; the Fourth Age smoke test may.
