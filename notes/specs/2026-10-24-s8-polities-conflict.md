# S8 Polities & Conflict: Sub-project Spec

**Status:** r2, 2026-10-24.
- r1 was reviewed by an independent agent. r2 fixes:
  - **mechanisms that didn't fit the code:**
    - a seized office no longer breaks `RULES[rule]`;
    - elective and appointed offices get a `choose` hook;
    - the four edits a control change needs are listed;
    - presence and deaths in battle go through `life.die` and the population ledger;
  - **pins vs war:** a director guard now protects the holder of a pinned office until their pin closes;
  - **the coarse core:** coarse execution doesn't exist in the engine yet; it is now a prerequisite ticket, and S8 ships only the fallbacks;
  - **the milestones:** the spec is split into **Part A** (M5: minimal polities) and **Part B** (M6: war in full);
  - **exit criteria:** testable, and none forces a result;
  - **draft marking:** the council is advisory before 4A 80, per the draft timeline;
  - **rules restated:** scopes and system order; who writes grievances; sparse relations; S7 reuse (Usurp generalises Seize, Rally is a Recruit); no new ripple disguises; stat pins deferred.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #29 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`:
  - §1 (the Firebrand Empire and its Great Houses; the eight Emperors as one pinned bloodline);
  - §5.4 pins (succession pins);
  - §6 S8 ("factions, offices, the imperial line, diplomacy, war, borders");
  - the stats table (`StatThreshold`: "derived indicators inside S8 and S10");
  - §8.2 roadmap: **M5** needs "minimal S8 polities" for the First Age's civilisations (#142); **M6** "S8 in full… polities and war with border maps".
- **Handed to S8 by earlier specs:**
  - S3: the throne as an office (#74); cadet branches.
  - S4: a city razed; "whatever else changes the map later (a war)".
  - S7: courts and exile (open question 3).
  - S2: a scenario `offices` list; title offices (the Emperors' reigns) reported `unsupported` until an office exists.
- **Builds on, as built:**
  - S3 houses and offices (`people/houses.py`: `line_of_succession`, `RULES`, `name_heir`, `succeed`, `people.succession`, `SuccessionForcer` in `people/canon.py`, `guard_pin`);
  - S4 geography (`geo.py`: dated `changes`, `geo.changed`, `apply_change`, `CHANGE_READS`/`CHANGE_WRITES`, MapHistory; `analysis/mapyear.py`; routing with an `army` mode; S4 journeys);
  - S6 beliefs (predicates, gossip, `shares`, news by road);
  - S7 ambitions, actions, schemes and the planner (`Seize`, `Recruit`, `Petition`, `CourtFavour`);
  - S1 ripples (one disguise per kind per ruleset), pins and director guards, temporal-LOD interfaces (`core/lod.py`).
- **Draft lore used:** the vault's Firebrand Empire and Great Houses notes, and `notes/lore/2026-10-22-fourth-age-timeline-draft.md`.
- **Tickets:**
  - Part A: #120 (polities, control, offices, the throne), #121 (diplomacy), and new tickets for the coarse fallbacks and for coarse execution in the engine (an S1 prerequisite).
  - Part B: #122 (war and borders), and new tickets for courts and razing, for ambitions and beliefs at polity scale, and for the Observatory views.
  - Epic #9.

## 0. In one paragraph

A **polity** is a sovereign power (an empire, a dominion, a clan confederacy); a **faction** is a bloc
inside one (houses allied in council, a guild, an order). Both are entities made from a world's data,
with **offices** (a throne, a council's seats, a guild's master) that reuse S3's succession, and
**control** of places, which is what a border is. Polities keep **relations** (stance, treaties, trust,
grievances) that drift with what their people do to each other; treaties are made and broken. A polity
at odds with another may go to **war**:
- **Part A** (the coarse model, enough for M5's First Age civilisations): a yearly draw per war.
- **Part B** (the full model, M6): seasonal campaigns along the routing graph, battles in which people
  die, sieges that change control, and a peace that cedes places.

Wars and treaties are claims too, so each side's official line spreads (S6), and the victor's account
differs from the loser's. Nothing is scripted. A war comes from a chain the story layer can find and a
ripple can change: a border incident, a grievance, an ambitious ruler.

**Done when** (§12):
- **Part A:**
  - the toy world's polities make war and peace, with control changing and the map by year showing it;
  - a Fourth Age run has the Empire, its throne under the Emperors' pins (every reign pin in the window
    holds) and its advisory council;
  - the coarse fallbacks exist and are tested on their own.
- **Part B:**
  - across a fixed set of seeds of a war-prone draft scenario, wars emerge, each with a cause chain,
    battles, deaths, changes of control, a treaty, a border map by year and two official lines that differ;
  - a treaty is broken somewhere in the set;
  - a ripple on a commander makes a recorded difference to a battle's odds that divergence analysis
    traces back to it.

## 1. Principles

- **Engine-agnostic.** Polity kinds, governments, office rules, treaty kinds and war aims are classes and
  data; Renascita's Empire is data, and draft. Tests run on the toy world (its two valleys become two
  polities).
- **Everything through state and events.** Control is a field; a border is where control changes along
  routes; a war is an entity with a biography. Systems never query the event log: what a later decision
  needs, an earlier system writes to state (§4's ledger).
- **Local, scoped decisions** (S3's principle):
  - a polity's choices run in `ctx.scope(polity)`;
  - a war's season in `ctx.scope(war)`;
  - a relation's drift in `ctx.scope(relation)`;
  - each with declared reads, so a change in one polity's affairs doesn't reshuffle another's draws.
- **Abstract war.** No tactics or units; armies are numbers; battles are keyed draws with readable odds.
- **People matter:**
  - rulers decide, with their traits and wants weighing;
  - commanders lead, with their wits weighing;
  - notables die in battle;
  - a house's killings, marriages and schemes reach its polity's relations.
- **Pins hold by mechanism, not special cases** (§3.4).
- **No new ripple disguises.** Each kind already has its one disguise in Renascita's ruleset: doom is an
  illness, inject the ward failure, plant a rumour, structural an upheaval. S8 adds none. A doom on a
  commander reads as an illness; a war-flavoured inject would have to share `WardFailure`'s dispatcher
  (`params.script`).

# Part A: minimal polities (M5)

## 2. Polities, factions and control (#120)

- **`polity`** entity:
  - `name`; `kind` (a label);
  - `government` (a class: how decisions are made, §3.3);
  - `seat` (a settlement);
  - `ruler` (an office id);
  - `members` (houses), `founded`, `ended`;
  - derived stats (§6).
- **`faction`** entity: `name`, `polity`, `kind` (bloc, guild, order, cult), `members` (houses
  in a scenario's data; people may join in a run), `aims` (war, peace, a rival's ruin), `standing` (0–1).
- **Control:** a settlement's and a place's `control` field names the polity that holds it, or none.
  - It is distinct from S4's `region`: provinces don't move when a town changes hands.
  - A **border** is a route whose ends are controlled by different polities.
- **Data:** a scenario's `polities`, `factions` and `offices` lists (S2's planned `offices` list, built in
  step 2). Each polity's `control` is a list of claims on regions (and so every place in them, down the
  `within` tree) and single places; the most specific claim wins (a place named outright, else its
  nearest claimed region). A run's `geography.json` carries each place's starting control.
  - Validated at load (`renasci.polities.check`): a malformed record, an id another entity has, a seat the
    polity doesn't hold, a claim on nothing or claimed twice, a house in two polities, a faction member
    outside its polity, a change handing a place to no polity.
- **Changing control** reuses S4's dated-change machinery. Four edits:
  1. `apply_change`'s `place` branch writes whichever of `region` and `control` the change carries (today
     it always writes `region`);
  2. `CHANGE_WRITES` gains `control`;
  3. `analysis/mapyear.geography_at` replays `control` as it replays `region`;
  4. the scenario's change validation and the structural ripple's params accept `control`.
- **Relations are sparse** (made by diplomacy, step 4): a `relation` entity exists only for a pair in
  contact (sharing a border, or a treaty) or at a stance other than neutral. Factions get relations only
  inside their own polity.
- **Renascita draft data** (not canon, marked in the data):
  - the Firebrand Empire controls Pyrosia's settlements;
  - its council's blocs are seeded from `The 12 Great Houses.md` (which already describes them) and the
    house notes' Political Alignment sections;
  - for Part B's war-prone scenario, a **draft** "Frontier clans" polity needs new draft settlements and
    routes in Frontier's Edge, which `fourth_age.json` doesn't have yet (§13).

## 3. Offices, the throne and the council

1. **Offices generalise:**
   - an office has a `scope` (house, polity or faction), `holder`, `heir` and `rule` (always a
     succession class, so `RULES[rule]` keeps working);
   - a separate `legitimacy` field is `lawful` or `seized`. It is set by a coup or conquest and back to
     lawful at the next lawful succession; stability reads it.
2. **Rules** get a `choose(ctx, office, predecessor)` hook that defaults to `candidates(...)[0]` (S3's
   rules are unchanged):
   - **lineage:** S3's primogenitures, scoped to the office's house. The throne's house is an **imperial
     house** entity, draft-named, which holds the bloodline and is not one of the twelve. S2's "no house:
     the holder's own line" stays for offices without one.
   - **appointment:** the holder of another office names the next. `choose` picks among candidates by
     traits and favour, with a keyed draw. `heir` is the presumptive pick.
   - **election:** a council votes, in `ctx.scope(polity)`, as a `polity.vote` event that records each
     voter's choice. A member's weight is its standing (house rank, favour, faction); ties go to
     seniority. `heir` is the presumptive favourite (the current front-runner), or none.
3. **The council and government:**
   - A government class says who decides war, peace and treaties: the ruler alone, the ruler **advised**
     by a council, or a council that **votes**.
   - **Council seats are derived on read:** a seat "goes with" another office (each house head sits), so
     `succeed` never has to update seats.
   - **Renascita (draft):** the Imperial Council **advises** the Emperor (the vault: "advises"); per the
     draft timeline it is formalised in 4A 80–95, after which it votes. Advice is a `polity.council`
     event (who urged what). The Emperor weighs it by traits and the advisers' standing.
4. **Pins vs war.**
   - **The gap:** `guard_pin` protects a person only while they are a role in an open pin. Once the next
     Emperor is born, the reigning one is unguarded. If he died in battle, by a coup or by execution, his
     heir would accede before the next succession pin's window opened, and that pin would fail.
   - **The fix, a new director rule:** the holder of an office named in a succession pin is guarded, the way
     roles are guarded, until that pin's window **opens**; inside the window the holder is left to fate (a death
     there is how the pinned heir most often succeeds). Only an office's next pin counts. **Done (#120).**
   - **What the guard does:**
     - a guarded ruler's lethal draws are near misses, so battles, coups and executions can't kill them;
     - a guarded office can't be seized;
     - its war can still be lost. Conquest of a pinned polity's seat is refused while it lasts, and the
       war ends in a treaty instead.
   - This is the general mechanism. There are no Emperor special cases.
5. **Cadet branches** (from S3): a yearly draw by size lets a large house's landed second son found a
   cadet house (`cadet_of`), which inherits its parent's relations.

## 4. Relations and diplomacy (#121)

- **`relation`** fields:
  - `stance`: war, hostile, cold, neutral, friendly or allied;
  - `trust`: −1 to 1;
  - `treaties`;
  - a **ledger** of what happened between the two since the last drift, with weights.
- **Who writes the ledger.** Systems append through `relations.note(ctx, a, b, kind, event)`, each
  declaring the write:
  - `life.die`'s killer branch, when killer and victim belong to different polities or factions;
  - `schemes`' exposure, across polities or factions;
  - marriage, when the spouses are of the two ruling houses;
  - raids and incidents;
  - a broken treaty.
- **Drift** (`polity.diplomacy`, yearly, in `ctx.scope(relation)`):
  - trust and stance move with the ledger, then the ledger is cleared;
  - **trade** counts the open border routes between the pair (read from the routes' and settlements'
    `control`);
  - **shared enemies** reads the pair's relations with third parties (their stances);
  - **rulers' traits:** an ambitious, bold ruler hardens.
- **Border incidents:** a yearly draw per border route, likelier at hostile stance. An incident is an
  event and a ledger entry, with a few deaths in Part B.
- **Treaties** are classes:
  - **truce:** no war for N years;
  - **alliance:** join each other's defensive wars;
  - **vassalage:** tribute, and follow in war;
  - **trade:** open routes, and trust grows;
  - **dynastic marriage:** an S3 marriage between ruling houses, made as a term.
  - A treaty is proposed by a ruler, put to the government (advice or vote), and accepted by the other
    side's ruler. Its terms and expiry are recorded.
- **Betrayal:** breaking a treaty (war during a truce, refusing an ally's call, withholding tribute) is a
  ruler's decision. It is an event, a large trust loss with every party to the treaty, and, in Part B, a
  claim (§9).

## 5. War, coarse (Part A) (#122's coarse half)

- **Declaration:**
  - Yearly, in `ctx.scope(polity)`, a ruler at hostile stance with a casus belli may propose war: a
    weighty ledger entry, a betrayal, a claim to a throne, or an `Expand` ambition (Part B).
  - The government decides. Allies are called.
  - `polity.war_declared` names the cause: the ledger events.
- **The `war` entity:** `sides`, `aims`, `cause`, `started`, `ended`, `outcome` and `exhaustion` per side.
- **Coarse resolution:** one draw per year per war, in `ctx.scope(war)`.
  - Odds come from the sides' `strength` (§6).
  - The year's outcome: control of one or two border places changes, exhaustion builds, and perhaps a
    ruler or a commander dies (through `life.die`, at home, cause "fell in battle"; subject to §3.4's
    guard).
- **Peace:**
  - Exhaustion past a threshold, or a decisive year, brings a treaty: places ceded, tribute, a truce.
  - Or a polity ends: its seat is taken and it has no heir, so its places go to the victor.
- **System order within a year** (priorities): diplomacy, then the council or government, then
  declarations, then war, all after `people.houses`.

## 6. Derived stats

Per polity, yearly, written as fields:
- **`strength`:** the levy its controlled settlements could raise;
- **`stability`:** legitimacy, the government's support, recent defeats and executions;
- **`wealth`:** controlled settlements and trade treaties.

Pins on them (`StatThreshold`, "never conquered before…") are **future**: `pins.SUPPORTED` has only
existence, event and ordering pins. That support is a separate ticket, not in S8.

## 7. The coarse fallbacks and coarse execution (M5)

- S8 ships each Part A system's `coarse_fallback` callable: rulers only, a government's decision as one
  draw, drift and treaties yearly, war as §5, the stats. Each is tested on its own.
- **Coarse execution is not built in the engine:** `Engine.__init__` refuses a coarse policy, and nothing
  calls `coarse_fallback`. It is a **prerequisite** S1 ticket for M5. Focus windows are set by the
  author before a run; dynamic promotion mid-run is deferred, as a determinism hazard. The 1,000-year
  toy budget (§12) depends on that ticket.

# Part B: war in full (M6)

## 8. Campaigns, battles, sieges and razing (#122)

- **Armies:**
  - An army is a number: a levy from its controlled settlements' populations, times a rate. Levy losses
    go through `population.bump`, so S3's conservation ledger holds.
  - Each season (`polity.war`, seasonal, `ctx.scope(war)`) an army moves along the routing graph toward a
    contested border settlement. It uses S4's `army` mode; seasons and the Vialux count.
  - A **commander** (an office under appointment) leads it.
- **Who is present:**
  - A commander and a ruler who takes the field are on a **journey** (S4 travel) with the army; they die
    through `life.die` against their home settlement's residents, as journeys already do.
  - Levies are numbers, not people.
- **A battle** is fought where armies meet.
  - Odds come from numbers, the commander's wits, defence (a seat, a fortress; in Renascita's draft data,
    Lux Lapis walls as a bonus) and supply (army-days from the seat).
  - It is a keyed draw. Levy losses are numbers. Notables present may die ("fell in battle"), subject to
    §3.4's guard.
- **A siege** of a settlement takes seasons. It falls or holds; a fall changes `control` through
  `apply_change`.
- **Razing** (from S4) follows a sack:
  - residents die or flee, through `population.bump` and `life.die`;
  - the fled go to the nearest settlement their polity controls, by routing;
  - the settlement may become a ruin (`kind: ruin`), and its routes may close;
  - `settlement.razed` records it.
- **Peace:** exhaustion builds from losses and seasons, and the treaty follows as in §5. A decisive battle
  can end it at once.

## 9. Polity-scale ambitions, actions and beliefs

- **Ambitions:**
  - `Usurp` **generalises S7's `Seize`** from house headships to any office, a throne or a council seat;
  - `Expand`: a ruler wants a neighbour's places, which adds a casus belli;
    **As built (#158):** a ruler (hot-tempered or wanting status) with a cold, hostile or warring neighbour
    across a border route claims its border places (`claims`); the plot is `Raid`s (each a `polity.raid`
    and a ledger entry, weight −0.15) until the relation is hostile; the ambition makes the ruler's realm
    2.5× likelier to propose war (`war.casus_belli`, a cause of the declaration). Won when a claimed place
    is the realm's.
  - `Secede`: a governed settlement's leading house wants out, and its revolt is a small war.
    **As built (#158):** the head of a member house seated in a town the realm holds (not its capital, not
    the ruler's house), hot-blooded and out of favour or wanting status. The plot: `Rally` (Recruit's
    variant: another house head of the realm joins) then `Revolt` (needs `rallied`): a new realm at the
    seat (`polity.seceded`, `seceded_from`), the seat's control, and `war.crush` (the realm declares on it;
    no allies called). A failed revolt is treason before the ruler (`courts.trial`). A rising crushed (its
    realm falls to the one it left) returns its houses to the realm. A plot against a realm, exposed, wrongs
    its ruler.
- **Actions:**
  - `Rally` is a variant of S7's `Recruit`: it wins a faction's or a council member's support;
  - `Treat` negotiates a treaty;
  - `Raid` makes a border incident on purpose;
  - `Coup` seizes an office: a violent action with exposure. The office's `legitimacy` becomes `seized`.
    **As built (#158):** `Usurp` forms for the head or heir of a realm's member house (not the ruler's own
    house, which is `Seize`'s), hot-tempered or wanting status, while canon names no successor to the
    throne (`ctx.succession_pinned`). Its goal is `seized:<ruler>`; its plot is a `Coup` (needs an accomplice,
    secret, in person, stakes 3). Success: `polity.seized`, the usurper holds the office, `deposed` names the
    old holder (alive); a guarded ruler foils it (`polity.coup_foiled`); failure costs favour. Where the
    usurper's own line can't hold the office (another house's headship), the deposed and then their line
    come next, so a restoration can follow; a lawful succession clears the seizure.
  - (Bribe is cut: `CourtFavour` covers it.)
- **Beliefs:**
  - new predicates: `started(war, by)`, `betrayed(treaty, by)`, `won(war, by)`;
  - each side's **official line** spreads through its settlements' `shares`, as the ward failure's lie
    does;
  - news of battles travels by road.
  - **As built (#158):** `renasci.lines`. At a declaration each side's line blames the other (`started`); at
    peace each side claims the victory, and a fall's victor does (`won`); a broken treaty is the other
    side's betrayal (`betrayed`). A line is a `polity.line` event, a 0.4 share of the claim in each of the
    realm's settlements (`beliefs.seeded`), and the ruler holding it; news by road does the rest.
    `analysis.truth` judges the three predicates against the log. Only with beliefs on.
- **Courts and exile** (from S7): a trial goes before the polity's ruler (`polity.trial`). It is held over
  an exposed scheme against an office holder, or the killing of a ruler's kin.
  - The verdict is **pardon**, **fine** (favour), **exile** or **execution** (a death, cause "executed",
    subject to §3.4).
  - Exile moves the person out of the polity's control and bars their return while that ruler reigns.
  - **As built (#158):** `people.courts`. The court is the realm controlling where the accused lives (else
    their house's realm), the judge its ruler (never the ruler themselves). Verdict weights: pardon from
    favour, friendship and kinship with the judge; exile and execution from the plot's gravity (a killing or
    seizure 1, a shaming 0.3), execution also from the judge's temper and a plot against the judge or their
    kin. Exile with nowhere outside the realm is a fine. Flee honours the bar; other moves (marriage,
    migration) don't yet, and an openly killed kin of the ruler isn't tried yet.

## 10. Observatory (S13)

- **The border map by year:** control as colour, borders drawn on routes, on the map page's existing
  year slider.
- **Wars:** a timeline of battles, sieges and the treaty, linked to the war's saga and its claims.
- **Relations:** polities and factions, with stance and trust over time.

## 11. Testing

- **Unit:**
  - each rule's `choose`;
  - votes and advice;
  - the ledger and drift;
  - treaties made and broken;
  - the coarse war year;
  - control changes and the map by year;
  - §3.4's guard: a guarded ruler survives a lethal battle draw as a near miss;
  - each coarse fallback;
  - determinism and replay.
- **Toy (Part A):** two valleys as two polities. A structural ripple opens a pass; contact brings
  incidents, and wars happen in some seeds. Control changes, and the map by year shows it.

## 12. Exit criteria

- **Part A:**
  - the toy test;
  - a Fourth Age 4A 1–40 run with polities on: the Empire, its throne, every reign pin in the window
    holding, and the advisory council's advice recorded;
  - #74's full 4A 1–256 golden run still passing with S8 on;
  - the coarse fallbacks tested.
  - The 1,000-year toy budget (under a minute) once coarse execution exists.
- **Part B**, the war-prone draft scenario (the Empire and the draft Frontier clans), 4A 1–40, a fixed
  seed set:
  - wars emerge in most seeds, each with a cause chain the story layer finds as a saga;
  - the map by year shows borders changing;
  - a treaty is broken somewhere in the set;
  - the two capitals' official lines on a war differ, and their chronicles disagree;
  - a ripple on a commander makes a recorded difference to a battle's odds that divergence analysis
    traces to it. Changing the outcome is a soft target, never forced.

## 13. Open questions (defaults chosen; on the review queue)

1. **The Empire's enemy** on Pyrosia's map. Default: a **draft** "Frontier clans" polity, with draft
   settlements and routes in Frontier's Edge (the vault calls it war-torn, with border clans).
2. **The imperial house's name** (the bloodline's house entity). Default: a draft placeholder.
3. **The council:** advisory until 4A 80–95, then voting, per the draft timeline.
4. **Abstract war** at settlement granularity, with yearly (coarse) or seasonal (full) resolution.
5. **Courts:** pardon, fine, exile or execution, by the ruler.

## 14. Plan: working order

**Part A (M5):**
1. **Polities core:** entity kinds, data and validation, casting, `control` and the four `apply_change`
   edits, control in the map by year (Python and the Observatory). **Done (#120).**
2. **Offices:** scope, `legitimacy`, the `choose` hook, appointment and election, the imperial house and
   the throne with its pins, advice and votes, cadet branches. **Done (#120)**; cadet branches and the
   vault's title-office reigns **done (#161)**.
3. **The pinned-office guard** (§3.4), in the director. **Done (#120).**
4. **Diplomacy:** sparse relations, the ledger and its writers, drift, incidents, treaties, betrayal. **Done (#121).**
5. **Coarse war:** declaration, the war entity, the yearly draw, peace. **Done (#122 Part A).**
6. **The coarse fallbacks** (`coarse_fallback(ctx, years)`: a coarse step of N years for N fine ones; the derived
   stats, `polity.stats`). **Done (#156).** Then, as the S1 prerequisite, coarse execution in the engine (#157).

**Part B (M6):**

7. Campaigns, battles, sieges, razing. Seasonal campaigns, battles and sieges (`renasci.campaigns`, behind
   `campaigns: true`) **done (#122, slice 1)**; razing, commanders and notables in the field, supply, and levy
   losses among the masses next.
8. Usurp, Expand, Secede; Rally, Treat, Raid, Coup; beliefs; courts. Usurp and Coup, with the deposed line's
   return, courts and exile, Expand and Raid, the official
   lines, and Secede with Rally and Revolt, **done (#158)**.
9. The Observatory views, the Frontier clans draft data, and the golden scenario.

**Risky bits:**
- **Emergence vs tuning:** wars must emerge without being forced. The exit criteria ask for emergence in
  most seeds, never a given outcome.
- **The pinned-office guard:** it must not freeze a polity's politics. It guards the holder's life and
  seat only, and only until the pin closes.
- **Cost:** Part B's seasonal campaigns. The coarse core and sparse relations are the escape hatches.
