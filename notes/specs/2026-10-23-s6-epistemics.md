# S6 Epistemics: Sub-project Spec

**Status:** r2, 2026-10-23.
- r1 was reviewed by an independent agent. r2 fixes:
  - claims are values, not store entities (entities clashed across scopes and tied every settlement together);
  - truth is judged offline, never in sim state;
  - belief shares are a field per settlement, not a column per claim;
  - the ward failure can spare its leader by a script param;
  - event volume is bounded by design;
  - only co-residents hear, and gossip is scoped per teller;
  - shared read/write constants for perception;
  - covers map to claims;
  - news memory is state;
  - grievance causes and the known-killer rule;
  - **correction**, and competing claims grouped by **topic**;
  - M2 trimmed.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #27 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §2 (Pin scope), §3 (Event, Cause, Mind, Claim / Belief), §5.2 (locality), §5.4 (storage), §5.5 (events, causes and secrecy), §5.6 (belief actions), §5.9 (ripples), §6 S6, §8.2 M2, §11 (PoC lessons).
- **Builds on:** S1 (events, visibility, causes, scopes, ripples incl. `inject`), S3 (people, ties), S4 (routes, journeys), S7 (actions, covers, exposure, grievances) as built.
- **Tickets:** #86 claims and belief stores, #87 provenance, trust and propagation, #88 aggregate beliefs, #89 secret events and covers, #90 the ward failure, #79 news by route (S4), #98 belief actions (S7). The Observatory side is #106, #107.

## 0. In one paragraph

Events are truth; **claims** are what people say about them. A claim is a structured proposition ("Vane's agents cracked the ward-stones"): a plain value, identified by its digest, that may drift from a parent claim as it is retold. Notables hold **beliefs** (a claim, a confidence, where it came from); they form them by **perceiving** the events they could see, and by being **told** by people they trust: by those living with them, by travellers arriving, and by news along roads. Beliefs **compete** within a **topic** (the PoC's lesson: otherwise everyone believes everything), and public evidence can **correct** a firm lie. The masses hold **belief shares** per settlement. **Secret events** are perceived only by those in them, behind a public **cover**; they leak through accomplices and exposure. A **lie** is a claim told by someone who believes otherwise. What people believe, not what happened, drives grievances. Whether a claim is true is judged afterwards, against the event log, by analysis and the Observatory. **Done when** the ward failure, a scripted injection, produces divergent, traceable beliefs: with no surviving witness the guild's lie dominates; with the witness spared, the truth spreads.

## 1. Principles

- **Truth and belief never collapse.** The event log is truth. Nothing in the sim stores whether a claim is true: that is judged offline (§3), so no sim state can confuse the two, and no system reads the event log as if it were state.
- **Provenance is causes.** Every belief a notable gains comes with an event (`belief.perceived`, `belief.told`, `belief.corrected`) caused by what produced it. The cause graph answers "why does she believe this?", and the diff explains beliefs like anything else.
- **Beliefs compete** within a topic, **decay** without reinforcement, and **trust** depends on the relationship. Public evidence **corrects**.
- **Locality.** Telling happens between people living in the same settlement, scoped **per teller**. Between settlements, only along roads: travellers telling on arrival, and news as scheduled follow-ups at the route's speed.
- **Deterministic and keyed.** Draws are owned by (teller, hearer, claim) or (witness, event).
- **Bounded.** Perception only of salient events, reinforcement emits nothing, tellings capped per settlement-season, beliefs per person capped (§12).

## 2. Records

### 2.1 claims are values (#86)

A claim is a canonical JSON value, `{"pred": str, "args": {role: id}}`, and its **key** is the digest of that value (`c:<digest>`). It is never a store entity: it lives inside beliefs, belief shares and `belief.*` event payloads, so creating "the same claim" in two scopes is just two equal values. The Observatory builds its claim table (text, lineage, truth) from the events.

**Predicates** are classes (behaviour in classes, state in records, as S7). Each has:
- `topic(args) -> key`: what the claim is *about* (two claims compete when they share a topic and differ, e.g. who caused the ward failure);
- `drift(args, rng) -> args | None`: how a retelling mutates it;
- `salience(args) -> 0..1`: how much people care to repeat it;
- `text(args, names)`: a template;
- `evaluate(events, args) -> (truth, basis)`: **analysis only** (§3).

M2 ships three: `caused(event, by)` (agency), `fault(event, party)` (blame without agency: "the ward-keeper misaligned the stones"), `killed(victim, by)`. Worlds add predicates by subclassing. (`alive`, `did`, `conspire` wait for M3.)

### 2.2 belief (#86, #87)

On a notable's person record, `beliefs: {claim key: {"claim": value, "conf": 0..1, "since": date, "from": event id, "heard": date, "secret"?: true}}`. `secret` (present only when true, #89) marks a belief its holder came by in a secret event: how they know it, not whether it's true. It is capped at `belief_cap` (default 16), dropping the lowest salience × confidence. `from` is the event that last *changed* it (a perception, a telling, a correction). `heard` is the last reinforcement, which decay reads. Nothing about truth or lies is stored on it.

### 2.3 belief shares (#88)

On each settlement, `shares: {claim key: {"claim": value, "share": 0..1}}`: the share of its masses holding the claim, capped at `share_cap` (default 12) and written with `ctx.set`, so it has deltas and "as of" views and dropping a claim is a write. Within a topic, shares sum to at most 1 (the rest haven't heard, or don't care).

### 2.4 news memory (#79)

On each settlement, `news_sent: {claim key: [route ids]}`, so a claim goes out along a route once, and a replay from a checkpoint doesn't send it again.

## 3. Truth (offline)

`renasci.analysis.truth` judges a claim against a finished run's events: `true`, `false`, `half` (its agent right, its detail wrong) or `unknown` (the truth says nothing, as for a vault claim seed), with the events it rests on (`basis`). The Observatory (#106) and the golden test (§10) use it. The sim never does: nothing there needs it, and reading the event log from inside an activation would be an unrecorded read.

## 4. Perceiving (#86, #89)

When a **salient** world event happens, the system that emits it calls `beliefs.perceive(ctx, event, claims)`. Salient events are deaths, S7 actions and exposures, the injection's events and anything a ruleset lists, not births, marriages or bookkeeping.
- **Who perceives:**
  - a public event: its participants, plus up to `witness_cap` (default 3) notables of its settlement, drawn per (event, witness);
  - a **secret** event: its participants only.
- **What they believe:** the claims the emitting system passes, each with a confidence. A participant gets 0.9 and a bystander 0.5. A predicate may give a bystander a different claim (the PoC: some survivors saw sabotage, some "faulty stones"), drawn per witness.
- Perception emits `belief.perceived` (perceiver, claim; caused by the event) only when it *changes* a belief.
- **Declarations:** `PERCEIVE_READS` and `PERCEIVE_WRITES` (`beliefs`, `residents`, `ids:settlement`) and `PERCEIVE_EVENTS`, shared like `DIE_WRITES`. Life (deaths), Schemes (actions, exposure) and the injection's disguise system add them.

## 5. Secret events and covers (#89)

- As built, a secret action (S7 `Poison`, `Assassinate`) emits a secret `people.action` and **one public death** whose payload carries the cover ("a wasting illness"). S6 adds `Action.cover_claim(victim, cover) -> claim` (default: `fault(death, illness)`). The public perceive the death with the cover claim; the actor and accomplices perceive the secret action with `killed(victim, actor)`.
- **Leaks:** each season, a holder of a secret truth tells it with a small chance (`leak_rate`, more for accomplices than the actor), as an ordinary telling (§6).
- **Exposure** (S7 `people.scheme_exposed`) is public evidence: perceiving it **corrects** (§6).

## 6. Telling, trust, drift and correction (#87)

`beliefs.gossip` (seasonal, after minds). For each settlement, in **one scope per settlement** (its tellings share one budget, so each depends on the others: the diff must see them together; built per teller first, the review found the shared budget leaked between scopes), each **resident notable who isn't travelling** may tell:
- **Budget:** at most `tell_cap` (default 2) of the teller's most salient beliefs, to residents of the same settlement who aren't travelling: tie partners, then household (spouse, parents, children). There are at most `settlement_tells` (default 40) tellings per settlement-season, the settlement's most salient first.
- **Chance:** `p = closeness × salience × (0.5 + 0.5 × charm)`, where closeness is the tie's strength, or 0.5 for household with no tie.
- **Trust:** acceptance confidence is `teller_conf × trust`, with trust by tie kind (mentor 0.8, friend 0.7, lover 0.7, rival 0.3, enemy 0.1) and 0.8 for household.
- **Competition:** if the hearer holds a claim in the **same topic** with a higher confidence than the acceptance, the telling is rejected and emits nothing. Otherwise the hearer holds it (emitting `belief.told`) and same-topic rivals are halved. A claim the hearer already holds at least as firmly is **reinforced**: its `heard` is refreshed, under one `belief.reinforced` event per settlement-season (not one per hearing).
- **Drift:** with `drift_rate` (default 0.08) the teller tells the predicate's `drift` instead: a new claim, and the event's payload carries `drifted_from`. That payload is the lineage.
- **Lies:** a teller with a reason (a scheme step, §8, or the injection's guild master) tells a claim they don't hold. The payload records `intent: "lie"`. The hearer doesn't know, and their belief record doesn't say.
- **Correction:** public evidence comes from perceiving an exposure, a `BearWitness` testimony or an injection's evidence event. It carries **authority** (a confidence of at least 0.85) and **bypasses competition**: it sets the claim and drops same-topic rivals below it, emitting `belief.corrected`. This is how "the truth spreads" can beat a firm lie.
- **Decay:** once a year, a belief not heard or seen again for more than `decay_years` (default 10) loses 0.1 confidence, and is dropped below 0.1, under one `belief.faded` event per settlement.
- **Provenance:** `belief.told` is caused by the teller's belief's `from` event, so "every belief traces to its origin" is a walk of causes to a perception, a correction or the injection.

## 7. News along routes (#79)

- **Travellers:** `travel.arrive` calls `beliefs.on_arrival(ctx, person, settlement)`. The traveller tells up to `tell_cap` residents (§6), in their own scope. Systems that handle `arrive` (Schemes, Migration) declare `PERCEIVE_*` and the gossip declarations.
- **News:** when a claim's share in a settlement passes `news_threshold` (default 0.3) and it isn't in `news_sent` for a route, the masses system schedules a `news` follow-up along that route, arriving after the route's days. The Vialux carries the official line: no drift, and the hearer's trust is +0.1. Wild roads drift at twice `drift_rate`. On arrival, the destination's share for the claim rises by `news_weight` (default 0.15), and one resident notable is told.

## 8. Belief-driven behaviour

- **Grievances follow belief.** In a world with S6:
  - a notable who comes to believe `killed(v, k)`, with confidence at least 0.5, about someone they grieve, holds the grievance against `k`, whether or not `k` did it (a frame makes a feud with the wrong house);
  - the grievance is caused by `Cause("event", belief.from)`, so taint flows;
  - `life.die`'s known-killer rule is switched off (`grievance_from: "belief"` world param), so it doesn't count twice. Worlds without S6 keep the S7 rule.
- **Promotion** (#105): `belief.*` events are not pinnable (master spec §2), so the promote panel doesn't offer them as causes to keep.
- **Belief actions** (#98, S7 in M2), trimmed for M2:
  - `Slander`: tell a damaging false claim;
  - `Frame`: the target's kin perceive a false `killed` claim with high confidence;
  - `BearWitness`: public testimony, which corrects (§6).
  
  `ForgeLetter` and `SpreadRumour` wait for M3.

## 9. Aggregates (#88)

`beliefs.masses` runs each season (as built, inside `beliefs.gossip`'s settlement scope, after the season's tellings; a share is written only when it moves by 0.005 or more, or a claim comes or goes). Each settlement's `shares` move toward its resident notables' mean confidence (`masses_follow`, default 0.25 a season), plus arriving news (§7), minus decay. Within each topic they are renormalised so they sum to at most 1, and capped at `share_cap`. With six settlements and a dozen claims each this is plain Python over a JSON field; vectorising waits until there are hundreds of settlements (M3). "Conserved" means no share leaves [0, 1] and no topic sums past 1, and a test checks both.

## 10. The ward failure (#90)

A **scripted injection**: ripple kind `inject` (already in `ripples.SUPPORTED`), with the script `ward_failure` handled by a disguise system in the Fourth Age ruleset.
- **Params:** `{"script": "ward_failure", "spare": null | "leader"}`. The cast is chosen from the world at the ripple's date by keyed draws. A baseline and its what-if see the same state before the inject, so they cast the same people, and `spare: "leader"` spares the leader without knowing their id up front.
- **Cast:** a caravan leader of one Great House travelling the Vialux, the head of a rival house, the guild master of Lux Faber, and a ward-keeper and guards (promoted from the masses).
- **Events:**
  - `contract_lost` (the rivalry, a cause);
  - `sabotage` (**secret**, ordered by the rival head);
  - `ward_failure` (public: night terrors);
  - the deaths it causes (the leader dies unless spared; one guard dies either way);
  - the survivors' perceptions (each draws "sabotage", `caused(failure, rival house)`, or "faulty stones", `fault(failure, guild)`);
  - the guild master's **lie** (`fault(failure, ward-keeper)`, `intent: lie`), told on the Vialux.
- **The witness** is the spared leader. They saw the sabotage, and their `BearWitness` (an ambition the injection gives them) is public evidence that corrects.
- **Golden test** (judged with §3's offline truth):
  - with no spared leader, the lie, or a claim drifted from it, holds the largest share along the Vialux after five years;
  - with `spare: "leader"`, the true claim spreads and a grievance against the rival house forms;
  - in both runs, every belief walks back to a perception, a correction or the injection;
  - the diff explains every divergent belief.
- The script's details are a draft of the vault's ward-failure story, chosen from the world each run, not canon. Aaron may pin it later.

## 11. Storage and the Observatory

- **No new table.** Beliefs and shares live in records (with `state_deltas` for "as of" views), and provenance lives in `belief.*` events. These together are the master spec's `beliefs` table.
- **The Observatory** (#106, #107) reads them with §3's truth: truth vs belief per claim, claim lineage (`drifted_from`), spread maps (shares over the S4 map, #154), and a person's beliefs with provenance. That work is out of scope here.

## 12. Volume and performance

Bounds by construction at M1 scale (about 2,500 notables, 6 settlements):
- perception: salient events only, at most `witness_cap` bystanders each;
- gossip: at most `settlement_tells` × 6 settlements × 4 seasons = 960 `belief.told` events a year at most, and reinforcement and rejection emit nothing;
- beliefs: at most `belief_cap` per notable, and shares at most `share_cap` per settlement.

That is under about 250k belief events over 250 years, against the run's 143k events today. Budget: S6 adds at most 50% to an M1 run's time (12.7 min for 250 years, #75). It is measured with `renasci bench` once #87 lands. If it's over, `settlement_tells` is the dial.

## 13. Testing

- **Truth (offline):** each predicate's `evaluate` against small event logs. Sim state carries no truth (a test checks that no person or settlement field mentions it).
- **Perception and secrecy:** a poisoning is perceived as the cover by the public and as the truth by the schemer and accomplices. It stays secret unless leaked or exposed (#89's acceptance).
- **Telling:**
  - trust, rejection within a topic, reinforcement (silent), drift lineage, decay, the caps, co-residents only, travellers excluded;
  - a lie is recorded with intent; correction overturns a firm lie.
- **Provenance:** for every belief in a run, a walk of causes reaches a perception, a correction or the injection (#87's acceptance).
- **Aggregates:** shares in [0, 1], topic sums ≤ 1, caps (#88).
- **Locality:** a ripple in one settlement changes another's beliefs only after a route's days, and the diff explains it. A change in one teller's beliefs taints only their own tellings.
- **Replay:** checkpoint and replay mid-propagation, including news in flight and `news_sent`, give identical beliefs.
- **Golden:** the ward failure (§10).

## 14. Open questions (defaults chosen; on the review queue)

1. **The predicates** (§2.1): three for M2, `caused`, `fault` and `killed`. Worlds add more.
2. **Grievances follow belief** (§8), including wrong ones: a frame makes a feud with the wrong house. Default yes.
3. **Trust, drift, decay, news and caps** (§6, §7): placeholders to tune against the golden.
4. **The ward failure's cast** (§10) is a draft of the vault's story, chosen from the world each run, not canon.
5. **Masses don't tell notables** in M2: shares are fed by notables and news, not the other way.

## 15. Plan: working order

1. **#86 Claims, predicates, beliefs, perception:**
   - claim values and keys;
   - the three predicates and topics;
   - the `beliefs` field and caps;
   - `perceive` and its declarations, wired into deaths and actions;
   - offline truth in `renasci.analysis.truth`.
2. **#89 Secret events and covers:** `cover_claim`, perception by visibility, leaks, exposure as evidence.
3. **#87 Telling:** gossip per teller, trust, topics, reinforcement, drift, lies, correction, decay; the provenance walk test.
4. **#79 News by route:** `on_arrival`, news follow-ups and `news_sent`, the Vialux vs wild roads.
5. **#88 Aggregates:** the `shares` field and its update; the conservation test.
6. **#90 The ward failure:** the inject script (with `spare`) and the golden test.
7. **#98 Belief actions** (S7): Slander, Frame, BearWitness.
8. **Grievances follow belief** (§8), with the S7 tests kept for worlds without S6.

**Risky bits:**
- **Divergence explanation:** a hearer reads a teller's belief. Gossip must run per teller with declared reads, or the diff will call belief changes unexplained. Test it before tuning.
- **Feedback loops:** grievances from false beliefs can cascade into feuds everywhere (the PoC's vengeance epidemic). The confidence threshold and S7's cooldowns are the brake, tuned on the golden.
- **Correction vs competition:** too strong and nothing stays contested; too weak and lies never fall. The golden's two outcomes pin it down.
