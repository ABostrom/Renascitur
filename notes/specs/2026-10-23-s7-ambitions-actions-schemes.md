# S7 Ambitions, Actions & Schemes: Sub-project Spec

**Status:** r2, 2026-10-23.
- r1 was reviewed by an independent agent. r2 fixes:
  - unreachable planner goals (ambitions now give subgoals; one achieved tag per action);
  - calling `die` from a scheme;
  - cause inheritance for steps, with a non-vacuous trace test;
  - draw owners and tie-breaks;
  - lifecycle gaps;
  - LOD sparing the ambitious;
  - traits the worlds lack;
  - a story finder that can actually split sagas.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #28 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §2 (Schemes, Stories, Motivation), §5.6, §5.7, §6 S7, §8.2 M1, §10.
- **Builds on:** S1 (engine) and S3 (`notes/specs/2026-10-22-s3-people-bloodlines.md`) as built.
- **Design note (#8, agreed with Aaron):** actions, ambitions and schemes are **classes**. Classes hold behaviour; JSON records hold state. Plots, arcs and sagas are **found** afterwards, not run.
- **Tickets:** #91–#97 (epic #8). Belief actions (#98) wait for S6 (M2).

## 0. In one paragraph

S7 gives notables wants and the means to pursue them:
- **Ambitions** form from drives, wounds, grievances and roles. They live as records naming their class, and end fulfilled, thwarted, abandoned or *died unfulfilled*.
- **Actions** are classes (preconditions, odds, effects, secrecy, duration, cover) in a library that grows by subclassing.
- A **planner** chains actions toward the concrete **subgoals** an ambition names, bounded by the schemer's wits.
- **Schemes** recruit accomplices, progress step by step, and risk exposure on secret steps. Each step runs in an activation caused by its scheme and its ambition, so **every event of every step traces to its ambition**.
- A **story finder** reads the run afterwards and finds **arcs**, **sagas** (split so none swallows a house) and **latch points**.

**Done when** (from the master spec): succession plots, court intrigue and vengeance emerge from drives on the kin world and the Fourth Age draft, every scheme step traces to its ambition, and the top latch points re-run as what-ifs.

## 1. Principles

- **Behaviour in classes, state in records.** An `Ambition` or `Action` is a stateless Python class. A live ambition or scheme is a store record whose `class` field names it, so checkpoints stay JSON.
- **Through `Ctx`.**
  - Odds use `ctx.chance` with `stakes` (hinges, ripples and the director apply).
  - Choices use `ctx.choose`.
  - Effects emit events with causes.
- **Causes carry the story.** The cause kind `ambition` already exists (`core.events.CAUSE_KINDS`); S7 adds `scheme`.
  - A scheme's step **activations** are scheduled with causes `("scheme", id)` and `("ambition", id)` (§13: `ctx.schedule(causes=)`). Every event emitted in a step inherits them: the action's own event, a death through `life.die`, its `tie_ended` and succession follow-ups, the cover.
  - The cover event (§5) carries them too, and links to the true event, which is secret.
- **Draws are owned by the decision's unit,** so two activations on one day can't shift each other's draws (S1 counts ordinals per owner):
  - scheme steps: `owner=scheme id`;
  - formation: `owner=person`, `purpose=f"form:{class}"`;
  - planning: `owner=ambition id`.
- **Locality.**
  - Ambitions form and resolve in the owner's settlement scope.
  - Each scheme step runs in `ctx.scope(scheme id)`. A scheme that reaches into another settlement is one unit of explanation; its reads there are recorded reads in its own scope.
- **Plots are emergent.** No recogniser classes in M1 (§11 Q1).

## 2. Records

### ambition

| Field | Notes |
|---|---|
| `owner`, `class`, `target` | `target` is an entity or null. |
| `formed`, `status`, `resolved` | `status`: `active`, `fulfilled`, `thwarted`, `abandoned`, `died_unfulfilled`. `resolved` is `[date, event]`. |
| `scheme` | The current scheme, cleared when any scheme ends. |
| `born_of` | `["drive", name]`, `["event", id]` or `["wound", kind]`. |

A person gains `ambitions` (active ids, sorted) and `cooldowns` (`{class: year}`).

### scheme

| Field | Notes |
|---|---|
| `owner`, `ambition`, `target` | |
| `plan` | `[{"action": "Poison", "target": id, "accomplice": id or null, "secret": bool}, ...]`. |
| `step`, `retries` | `retries` counts this step's failed attempts. |
| `replans` | 0 or 1. |
| `accomplices` | Sorted ids. |
| `progress` | 0–1. |
| `status` | `active`, `succeeded`, `failed`, `exposed`, `moot`. |
| `started`, `ended` | Dates. |

### person additions (#95)

All are written only on change, so they can be read as of any date:
- `grievances`: `[{"against", "event", "since"}]`.
- `wound`: `{"kind", "event", "since"}` or null.
- `need`.
- `wants`.
- `favour`: 0–1. Court favour, decaying yearly, read by the `status` drive.

## 3. Ambitions (#91)

```python
class Ambition:
    name: str
    cooldown_years: int = 5
    reads: frozenset[str]
    def eligible(self, ctx, person) -> Formation | None: ...  # target, born_of: may this person want it now?
    def urge(self, ctx, person) -> float: ...                 # 0..1: how likely, per year, to form when eligible
    def subgoals(self, ctx, amb) -> list[frozenset[str]]: ... # concrete tag sets the planner can reach (any one)
    def satisfied(self, ctx, amb) -> bool: ...
    def moot(self, ctx, amb) -> bool: ...                      # can no longer be met
    def text(self, ctx, amb) -> str: ...
```

- **Eligibility is deterministic** (no draws). Formation is `eligible` plus a keyed `ctx.chance(urge, owner=person, purpose=f"form:{class}")`. An active ambition is **abandoned** only if `eligible` turns false or it becomes `moot`, so the draw can't abandon it by chance.

**`people.ambitions`** (yearly, per settlement scope, after drives):
1. **Resolve:** `satisfied` → `fulfilled`; `moot` → `abandoned`; no longer `eligible` → `abandoned`. Each resolution is a `people.ambition_resolved` event, caused by the ambition.
2. **Form:** each class in name order, past its cooldown and not already held. The `people.ambition_formed` event is caused by `born_of`.

**Death:** `life.die` resolves every active ambition as `died_unfulfilled` (§13). `AMBITION_RESOLVED` has `dead_roles=("owner",)`.

**At a scheme's last step,** `satisfied` is checked at once, so a won ambition can't be logged `died_unfulfilled` if its owner dies before the yearly pass.

**Starter ambitions (M1)** and their **subgoals**, the tag sets the planner works toward:

| Class | Eligible when | Subgoals |
|---|---|---|
| `Marry` | Unmarried, of age, belonging below 0.5. | `{married}` |
| `Standing` | In a house, status below 0.6. | `{favoured}` |
| `Seize` | In a house, behind someone in its headship's line of succession, close kin of the holder; temper high or status low. | `{dead:p for each person ahead of them in the line, up to 3}`. With fewer ahead, the line itself delivers. Satisfied when they hold it. |
| `Vengeance` | Holds a grievance against a living person. | `{dead:<them>}` or `{shamed:<them>}` |
| `Protect` | A spouse or child is the target of an active scheme they know of (an exposed one). | `{dead:<schemer>}` or `{shamed:<schemer>}` |

## 4. Actions (#92)

```python
class Action:
    name: str
    target_role: str | None = "target"   # whom it acts on; None for self
    requires: frozenset[str]             # tags that must hold first (facts or earlier achieves)
    achieves: str                        # exactly one tag, with {target} substituted ("dead:{target}")
    secrecy: float = 0.0                 # chance factor that a step is exposed
    duration_days: int = 90
    retries: int = 1                     # failed attempts allowed before the step fails
    weight: float = 1.0
    reads/writes/event_types
    def possible(self, ctx, actor, target, scheme) -> bool: ...
    def odds(self, ctx, actor, target, scheme) -> float: ...
    def succeed(self, ctx, actor, target, scheme) -> None: ...
    def fail(self, ctx, actor, target, scheme) -> None: ...
    def cover(self, ctx, actor, target, scheme) -> str | None: ...  # the public story of a secret success
```

**The starter library (M1).** Each achieves one tag. An action with two possible outcomes would be two classes.

| Action | Requires | Achieves | Secret | On success |
|---|---|---|---|---|
| `Recruit` | `tie:{accomplice}` | `accomplice` | yes | The accomplice joins. |
| `Petition` | | `heard` | no | An audience. |
| `CourtFavour` | `heard` | `favoured` | no | `favour` rises. |
| `Court` | | `married` | no | A match arranged outside the market (S3 `_wed`). |
| `Poison` | `accomplice` | `dead:{target}` | yes | `life.die(killer=None)`. Cover: a wasting illness. |
| `Assassinate` | `accomplice` | `dead:{target}` | yes | `life.die(killer=None)`. Cover: found dead. |
| `Duel` | | `dead:{target}` | no | `life.die(killer=actor)`, which is **attributed**. Losing is the actor's death or shame. |
| `Shame` | `heard` | `shamed:{target}` | no | The target's `favour` falls; they gain a `shame` wound. |
| `Flee` | | `safe` | no | A move to another settlement in the region (before S4). |
| `Confess` | | `absolved` | no | Ends one's own scheme; status falls. |

- **`Bribe` waits** until there is wealth (S9).
- **`Recruit` names its accomplice** in the plan (the `accomplice` slot), chosen when the plan is made (§5).

**Exposure:** a secret step draws `ctx.chance(secrecy * world.exposure_base * (1.5 - wits), owner=scheme, purpose="expose", stakes=1 + progress)`.

**Deaths** go through `life.die`, so guards and pins still apply: a protected target gets a near miss. The step activation's causes come along (§1).

## 5. The planner (#93)

**Backward chaining** from one of the ambition's subgoal sets:
- **Facts** are evaluated through `Ctx` (recorded reads): `tie:<id>`, `heard` (holds the favour mark), `married`, `dead:<id>`, `shamed:<id>`, `accomplice` (the scheme has one).
- **Search:**
  - For each unmet tag, try actions in **class-name order** whose `achieves` matches it. Their `requires` become subgoals, depth-first.
  - The depth is bounded by `2 + round(3 * wits)`.
  - Targets come from the tag. The accomplice slot is filled by candidates in **sorted id order**: ties of the actor (friend, kin, house) who aren't the target.
- **Cost:** the sum over steps of `1/odds + secrecy`. The cheapest plan wins. Ties break on the canonical tuple of `(action, target, accomplice)` per step. The search is deterministic and makes no draws.
- **The plan is stored** on the scheme record, so it can be replayed and explained.
- **Knowledge:** in M1 a schemer knows the world as it is. S6 bounds plans by beliefs.

## 6. Schemes (#94)

**`people.schemes`** (yearly, per settlement scope) starts schemes:
- for each active ambition with no scheme, a keyed chance (`owner=ambition`) to plan now;
- with a plan, `people.scheme_begun` (caused by the ambition) creates the record;
- the first step is scheduled with `ctx.schedule(Span(days=duration), "step", payload={"scheme": id}, causes=(scheme, ambition))`.

Its follow-ups run in `ctx.scope(scheme)`. **`people.schemes.handle` also routes `succession` follow-ups** to `houses.succeed`, because a death in a step vacates offices (§13).

**A step:**
1. **Moot** if the owner is dead or dormant, the target is dead or dormant (for a target that must live), or the ambition is resolved. The scheme ends `moot`, and `ambition.scheme` is cleared.
2. **An accomplice who died or was demoted** is dropped. A plan that needs one goes back to the `Recruit` step.
3. **`possible`?** If not, it counts as a failure (step 5).
4. **Secret step:** the exposure draw. If exposed:
   - `people.scheme_exposed`;
   - the ambition is `thwarted`;
   - an `enemy` tie forms between target and owner;
   - the owner's `favour` falls and they gain a `shame` wound;
   - the target and the target's spouse, children and parents gain a **grievance** against the owner;
   - the scheme ends `exposed`.
5. **Odds draw (`owner=scheme`):**
   - **On success:** `succeed`. A secret success also emits its cover (§4).
   - **On failure:** `fail`. Retry until the action's `retries` are used up, then **replan once** (`replans`) from the current state; with no plan, the scheme `failed`.
6. **Next:** with steps left, schedule the next. Otherwise the scheme `succeeded` and `satisfied` is checked at once (§3). In every ending, `ambition.scheme` is cleared.

**The trace test** (non-vacuous): every event emitted in a step activation carries both `("scheme", id)` and `("ambition", id)`, and a test run has at least one of each kind of step.

## 7. Wants, needs, wounds and grievances (#95)

- **Wounds:**
  - `grief`: a parent, spouse or child dies by violence;
  - `betrayal`: a tie turns enemy, or one's accomplice confesses;
  - `terror`: one's own near miss;
  - `shame`: one's own plot exposed, or one is `Shame`d.
  
  A wound heals after `wound_years` (default 10), or a fresher wound replaces it.
- **Grievances** come only from **attributed** harm:
  - a killing with a known `killer`, as in a duel;
  - an exposed plot against oneself or close kin.
  
  A secret success breeds none until S6's beliefs reveal it (the PoC's lesson).
- **`need`** is a phrase per wound kind (world data). **`wants`** are the active ambitions' `text`s.
- **`people.minds`** (yearly, per settlement scope, after ambitions) writes them only on change.

## 8. Hinges and latch points (#96)

- **Stakes** (S1 hinges):
  - a death draw: 1 + active ambitions;
  - exposure: 1 + progress;
  - a duel's odds: 2;
  - other steps: 1.
- **Latch points** are found after the run (§9) and ranked by potential:
  - **died unfulfilled:** youth, scheme progress, the ambition's stakes, the arcs touched;
  - **near misses:** small hinge margins on people who later mattered.
- **Each suggests a ripple and its means:**
  - protect (a physician's care);
  - spare (a second's intervention);
  - doom (an illness).
- `renasci latch <run>` lists them, and `--launch N` replays one as a what-if (the CLI's replay and diff).

## 9. The story finder (#97)

An analysis pass (`renasci.analysis.stories`, `renasci stories <run>`) writes `analysis/stories.json`.

- **Arcs:** one per ambition. Formation (born of …), beats (the events whose causes include the ambition or its schemes) and outcome. **Salience** comes from the ambition's stakes, violent beats, the people touched and the owner's house rank.
- **Sagas** form from a **weighted graph of arcs** with *direct* links only:

  | Link | Weight |
  |---|---|
  | One arc's target is the other's owner | 3 |
  | A shared beat event | 2 |
  | A direct cause edge between their beats | 1 |

  Long cause chains don't count, because causal spread reaches nearly everyone within a century (master §5.2).
  - Components are taken over edges of weight 2 or more.
  - **Splitting:** a component above the size limit (§11 Q5) drops its lowest-weight edges, and then edges between arcs more than a generation apart, until every part fits.
- **"No saga swallows a house"**, as a test: for every house with 4 or more arcs, no saga contains arcs owned by more than half of that house's notables alive during the saga's span.
- **Titles** come from per-class templates (data), such as "The poisoning of Arn of House Cannith" or "Vadalis' long revenge". A saga takes the title of its most salient arc.
- **Period queries:** arcs and sagas are indexed by their active years (S13 #99).

## 10. Testing

- **Invariants:**
  - the trace test (§6);
  - every scheme's events lie between its start and end;
  - no active ambition on a dead or dormant owner;
  - the state machine (no resurrection);
  - cooldowns;
  - `ambition.scheme` is null whenever its scheme has ended.
- **Emergence** over a seeded 100-year kin run and the Fourth Age draft: at least one succession plot (a `Seize` scheme), court intrigue (`Standing` with `CourtFavour`) and vengeance (`Vengeance` after an attributed killing). The test asserts the classes and causes.
- **The planner** (hypothesis):
  - deterministic;
  - never deeper than its bound;
  - the cheapest plan found;
  - every subgoal of every starter ambition is reachable with the starter library (a test, so #1 can't recur).
- **The S1 guarantees:** determinism, replay equivalence, and no unexplained divergence for a protect ripple on a scheme's target and a doom ripple on a schemer.
- **Stories:** the house test (§9), titles for every arc and saga, latch points ranked, and the top one replays and diffs cleanly.

## 11. Open questions (defaults chosen; on the review queue)

1. **Recognisers?** Emergent only in M1.
2. **The action vocabulary:** Claude drafts the starter library, and Aaron adds or renames. World flavour (poisons, rites) is data.
3. **Punishing an exposed plot:** an enemy tie, lost favour, a shame wound, and grievances for the victim's close kin. Courts and exile are S8.
4. **`Flee` before S4:** another settlement in the region.
5. **Saga size:** split above 12 arcs or 40 people.

## 12. Traits

Actions and urges read **traits by role** (`wits`, `temper`, `charm`), mapped to the world's catalogue through ruleset params: `{"wits": "wits", ...}`. A trait the world doesn't have reads as 0.5. The kin world maps none, so everyone is average; the Fourth Age draft maps all three.

## 13. S1 and S3 additions

| Addition | Where | Why |
|---|---|---|
| Cause kind `scheme` | `core.events` | §1. |
| `ctx.schedule(..., causes=())` adds causes to the follow-up | `core.context` | Step activations carry scheme and ambition (§1, §6). |
| `life.die(ctx, person, settlement, cause, *, killer=None)`, plus a `DIE_READS`, `DIE_WRITES`, `DIE_EVENTS` bundle that every caller declares | S3 | Schemes can kill. The ambition hook (`died_unfulfilled`) and grievances (with `killer`) live there. |
| `houses.vacate` follow-ups are handled by any system that calls `die`, through a shared `houses.handle_succession` | S3 | `ctx.schedule` schedules the caller. |
| Lod spares the ambitious: it reads `ambitions` and skips owners, accomplices and targets of active schemes | S3 `Lod._quiet` | Master §5.10: the ambitious are never demoted. |
| `favour` on persons; the `status` drive reads it | S3 drives | `CourtFavour`, `Shame`. |
| `stories.json` and `latch.json` in `analysis/`, read by the Observatory | S1, S13 | §8, §9. |

## 14. Plan: working order

Each step is TDD on the kin world, with a code review and a merge per step.

1. **The §13 additions,** plus ambition records and their lifecycle (#91): `Ambition`, `people.ambitions`, death resolving, cooldowns, `Marry` and `Standing`.
2. **Actions (#92):** the interface and the starter library, each tested alone.
3. **The planner (#93):** facts, bounded search, costs, the reachability test.
4. **Schemes (#94):** steps, exposure, outcomes, covers, accomplices, replanning; `Seize`, `Vengeance` and `Protect`; the trace test.
5. **Minds (#95).**
6. **Latch points (#96)** and `renasci latch`.
7. **The story finder (#97)** and `renasci stories`.
8. **The emergence test.** Then S13's Stories pages (#99–#101).

**Risky bits:**
- Exposure tuning against the emergence test (world data).
- Saga splitting, which is tested from the start.
- Planner cost at 3,000 notables: planning is rare and bounded, and is measured in step 3.
