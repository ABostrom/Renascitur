# S11 Mythic Beings & Faith: Sub-project Spec

**Status:** r2, 2026-10-26. r1 was reviewed by an independent agent; r2 fixes:
- **the god loop:** a `divine` system runs deities' ambitions and schemes, since S7's loops only walk settlement
  residents;
- **no leaks:** divine ambitions and actions sit in their own registries, loaded only with a pantheon, so S7's
  library, reads and recipe hash don't change elsewhere;
- **attribution:** only kinds that write an event are attributed; the event types gaining `attributed_to` are
  listed; the truth judge follows the role;
- **naming and statuses:** deities are cast entities with `traits` (not `temper`); `faded`/`imprisoned` are
  fields, and the store's status stays `active` so a god can still be named in events;
- **columns:** `faith:*` is cast, owned by one system, and clamped;
- **opt-in and bounds:** immortality is gated on the pantheon; `power` has a stated cap;
- **plan:** a prerequisites step (S9 jobs and objects), with `Grant` moved after them; the S14 criterion moved
  to S14.

Written without waiting for approval (the loop's low-ceremony rule); Aaron comments on #32 or the review queue
(#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: the decisions table ("Mythic beings: gods
  and immortals are agents, their canon deeds are pinned, and faith is a force (from M5)"); §5.9 ripples
  ("deity attribution is deferred to S11"); §6 S11; §8.2 **M5** (S11 with S14: "gods and primordial beings as
  agents (Ishna, Lord Syuul)").
- **Vault:** `Cosmology/Gods/` (the Second Age's Muradin; the Third Age pantheons of Luxar and Noxar, eight gods
  each), `Cosmology/Creation/` (Aeternum, the Elder Races, Sylara), `History/First Age/Imprisonment of Lord
  Syuul.md`. Deities are S2 reference notes today (type `deity`).
- **Builds on, as built:**
  - S1: ripples, disguises, pins and forcers, `Cause` kinds;
  - S3: people and races;
  - S6: claims, beliefs, `shares` and news;
  - S7: ambitions, actions, schemes and the planner (`resolve`, `begin`, `step`);
  - S8: factions;
  - S9: jobs (priest) and objects (relics);
  - `analysis.truth`.
- **Tickets:** #131 deity and immortal agents, #132 worship and faith as a force, #133 divine attribution of
  ripples. Epic #12. S14 (#140–#147) builds the First Age's gods on it.

## 1. Scope and shape

S11 makes the gods real in the simulation without making them puppets: they want things, act through what the
world already has (blessings, curses, omens, champions, relics), and need the faithful to act at all. Mortals
believe, pray and convert; what they believe about the gods is S6 belief, and it can be wrong.

**Per age, by ruleset.** How present the gods are is an age's canon: the First Age's walk the world (S14); the
Fourth Age's (default, open question 1) are distant, felt through faith, omens and the rare miracle. A
ruleset sets a `pantheon` (which deities exist) and a `presence` (none, distant, present). **A world without a
pantheon runs exactly as today:** no systems, no columns, no classes, the same recipe hash.

## 2. Deities and immortals as agents (#131)

- **A deity** is a cast entity (`kind: deity`, its id the vault's `v:` id), from the ruleset's pantheon:
  `name`, `domains` (healing, war, death, light, shadow…), `traits` (the S7 roles wits, temper, charm),
  `power` (0..`POWER_CAP`, from faith: §3), `state` (active, sleeping, imprisoned; a field, so the store's
  status stays `active` and events can always name it), `realm` (a place, or an off-world realm from S14),
  `rivals`, `allies`. A god killed by a pinned deed becomes store-`dead`, and the roles that may name it after
  are listed with `dead_roles`.
- **The `divine` system** (yearly, `ctx.scope(deity)` per deity) forms deities' ambitions and runs their
  schemes, reusing S7's `resolve`, `begin` and `step`. S7's own loops walk settlement residents only, and
  deities aren't residents (they have no `born`).
- **Divine registries:** `DIVINE_AMBITIONS` (`Champion`, `Smite`, `Spread`, `Free`, `Corrupt`) and
  `DIVINE_ACTIONS` (`Bless`, `Curse`, `Omen`, `Manifest`, `Grant`, `Raise`) are separate from S7's
  `LIBRARY` and `ACTIONS`, loaded by the `divine` system only. Mortal plans never see them.
  - `Bless` and `Curse` raise or lower a mortal's odds for a span (an event naming the god as actor);
  - `Omen` is a sign that plants an S6 claim;
  - `Manifest` (present ages only) has a god walk the world for a season;
  - `Grant` makes a relic, an S9 object (after S9 #124);
  - `Raise` makes a mortal a champion: a patron, boosted traits, and an ambition the god chose.
  - Each costs `power`; a distant age allows only `Omen`, `Bless`, `Curse` (and `Grant`, rarely).
- **Immortals** (Elder Races, Saurians, Lord Syuul) are S3 people whose race has `mortal: false`, **read only
  when the world has a pantheon**: today's worlds with elves keep their mortality. A non-human-shaped being is
  `kind: being`, run by `divine`. Immortals die only by violence or a pinned fate.
- **Canon deeds are pins:** S1 event pins on deities ("Syuul is imprisoned by 1A 9200"), with a forcer (as
  succession pins have) that makes the deed happen in its window.
- **Cadence:** gods act yearly (fine) or by decade (coarse); a god's step is cheap and few.

## 3. Worship and faith as a force (#132)

- **Faith columns** (cast ints, `faith:<deity>`, per settlement; owned by the `faith` system): the masses'
  faithful of each god, summing to at most the masses. After every population step they're prorated to the
  band total (as S10's `sick`). A notable has a `patron` (one deity) and `devotion` (0..1).
- **Conversion** is S6 belief at work. Claims that a god acts (`blessed(person, by)`, `smote(place, by)`)
  spread through `shares`, and the masses' faith drifts toward the gods the town believes are acting for it,
  and away from those believed to have failed it. Priests (an S9 job) preach: they raise their god's share in
  their town each season; a temple (a place kind) multiplies it.
- **Faith is power:** each year a deity's `power` moves toward a function of its faithful (masses, and notables
  weighted by devotion), decays, and is capped at `POWER_CAP`. A god without faithful sleeps (`state:
  sleeping`). Power pays for divine actions, so faith and deeds feed each other within the cap.
- **Churches as factions:** a deity's priesthood in a polity is an S8 faction (aims: the god's). State
  religion and persecution are later S8 decisions.
- **Coarse:** faith drift and power step N years at once.

## 4. Divine attribution of ripples (#133)

- **Only kinds that write an event** are attributed: protect (its `people.near_miss`), doom (the disguise's
  death), inject (its script's events), structural (S10's `harvest.failed`, a map change), plant (its rumour
  or object). Favour and luck write no event of their own, so they are never attributed.
- The ruleset's `attribution` table maps each kind to domains; the god chosen is the active one whose domains fit
  best, with power to spare (a keyed pick).
- **In the log:** the attributed event types gain an optional `attributed_to` role (a new version of each:
  `people.near_miss` v2, `people.death` v2 for a disguise's death, …), and the ripple's cause gains a companion
  `Cause("deity", id)`, used only for attribution (divine actions don't need it: the deity is their actor).
  Divergence analysis treats a `deity` cause like the ripple it accompanies: explained.
- **In belief:** witnesses perceive `caused(event, by=deity)`. `analysis.truth` adds `attributed_to` to its
  agent roles, so the judge calls it true in-world; it gains judges for `blessed` and `smote` (the god's
  events). Attribution costs the god nothing; it is the world's reading of the author's hand.
- **Faith follows:** an attributed miracle raises that god's faith where it was seen.

## 5. Observatory

- A **pantheon page:** each deity's power and faithful over time, its deeds (events), champions and relics.
- A **faith layer** on the map by year: the leading faith per settlement, and its share.
- The person page shows patron and devotion; the event browser filters by deity.

## 6. Temporal LOD

Divine steps are yearly and cheap; faith drift has a coarse fallback (N years at once). A `Manifest` (a god in
the world) is a natural focus-window trigger for S14's long age.

## 7. Exit criteria

- **Unit tests with forced inputs:**
  - a blessing raises its target's odds and names its god;
  - an omen plants its claim;
  - a god with no faithful sleeps;
  - power pays for actions and stays under its cap over a long run;
  - an attributed near miss names its god and its witnesses believe it;
  - the truth judge calls it true in-world.
- **A Fourth Age run with a distant pantheon** (draft data from the vault's Luxar and Noxar gods), 4A 1–100 on
  chosen seeds, **with named ripples:** a protect on a notable and a structural harvest failure (S10), both
  attributed. The faith shares in the towns that saw them shift (asserted on the `faith:*` series), and no god
  manifests.
- **Ripple attribution is traceable:** the attributed protect makes a recorded difference that divergence
  analysis traces to the ripple, with the god named in the event.
- Worlds without a pantheon are unchanged: identical events and state, the same recipe hash.
- (The First Age's pinned divine deeds holding is S14's criterion, #147.)

## 8. Open questions (defaults chosen; on the review queue)

1. **The Fourth Age's gods:** distant (faith, omens, rare miracles: default), absent, or present?
2. **Which pantheon is worshipped in the Fourth Age:** the Third Age's Luxar and Noxar gods (default, as
   draft), or something the vault hasn't said yet.
3. **Can a god die or be made?** Default: gods sleep or are imprisoned; a pinned deed can kill one; the sim
   makes no new gods.
4. **Is attribution truth?** Default: in-world, an attributed ripple is the god's act; the log keeps both the
   ripple and the god.

## 9. Plan: working order

0. **Prerequisites:** S9 #123 (jobs: the priest) and S9 #124 (objects, the `objects` system) for priests and
   `Grant`.
1. **#131 Deities and immortals:** the deity entity and pantheon schema (cast from the vault's references);
   the `divine` system and its registries; power, state and the cap; divine ambitions and actions (`Grant`
   last, after S9 #124); gated immortal races; deed pins and their forcer; presence levels.
2. **#132 Worship and faith:** cast `faith:*` columns, their owner and proration; patrons and devotion; the S6
   predicates; priests and temples; faith → power; churches as S8 factions; coarse fallbacks.
3. **#133 Attribution:** the attribution table, the versioned event types with `attributed_to`, the `deity`
   cause kind, beliefs about it, the truth judge's role and predicates.
4. The Observatory's pantheon page and faith layer; the Fourth Age golden. S14 then builds on all of it.

**Risky bits:**
- **Gods as puppets:** divine actions must be wants with costs, never scripts; tests ask for mechanisms, not a
  given god's fate (except pinned canon).
- **History preservation:** divine classes in their own registries; immortality and attribution only with a
  pantheon.
- **Power runaway:** faith → power → miracles → faith is a loop; decay, costs and `POWER_CAP` bound it, and a
  test checks the bound over a long run.
