# S12 Story Layer: Sub-project Spec

**Status:** r2, 2026-10-24.
- r1 was reviewed by an independent agent. r2 fixes:
  - **the M4 run:** no recipe could turn beliefs on, so a real run never diverged; there is now a step 0 and an M4 recipe;
  - **subjects:** the ward failure is in no saga, so there is now an event or topic subject;
  - **the ward test:** the guild master privately believes the truth, so the divergence is tested from the town's and the townsfolk's view;
  - **readings:** the event readings to "move" from TS don't exist; they are new, and the provenance trace needs a Python port;
  - **the POV rule:** a residence timeline from `state_deltas`, a verdict table, rival claims in a house;
  - **judging:** gaps around a living victim, a dead person alive, half truths, events named in prose, literal parties;
  - **the benchmark:** it measured the extractor on its own templates; it now has a paraphrase table and a held-out set;
  - **MCP:** protocol details, output size, stdout hygiene, security;
  - **the Observatory:** the canon-check route can't go through the launcher's 4 KB argv;
  - **determinism:** the rules are now stated.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #33 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`:
  - §1 ("AI stays out of the sim loop… Claude writes prose afterwards and checks it against the truth");
  - §5.11 (vault chronicles and myths are claim seeds);
  - §6 S12;
  - §8.2 (the roadmap, M4: schema-valid packs, at least 90% canon-check recall, a chronicle and a campaign brief from one run).
- **Builds on**, as built:
  - S7/S13 stories (`analysis/stories.json`: arcs and sagas from ambitions and schemes) and latch points;
  - S6 epistemics (`beliefs.py` claims and predicates; `truth.judge`; the claims report, #106);
  - the person view's belief traces (#107; in TypeScript only so far).
- **Tickets:** #115 (context packs), #116 (POV chronicles), #117 (canon checks), #118 (MCP server), #119 (campaign brief), #111 (Observatory). Epic #13.

## 0. In one paragraph

A run is a graph of what happened, who believed what, and who wanted what. The story layer turns it into **material a writer can use, and checks the writing against it**. Every part of it is deterministic, and none of it calls a model.
- A **context pack** is a JSON bundle about one subject (an arc, a saga, a person, or an event and what followed it), from one point of view, with every item traceable to its events.
- A **chronicle** is that pack told as an in-world account: the version its author believes.
- A **campaign brief** lays a saga out for a game.
- A **canon check** reads prose, finds its claims and judges each against the run.

Claude writes the real prose in a session, through an **MCP server** over runs and the vault, and the canon check reads what it wrote.

**Done when**, on **the M4 run** (§1a):
- packs validate against their schema;
- the canon check finds at least 90% of the contradictions seeded into its benchmark (and its held-out recall is reported);
- a chronicle that diverges from the truth, and a campaign brief, are generated;
- Claude can query the run and fetch a pack through MCP.

## 1. Principles

- **No model in the engine.** Packs, chronicles, briefs and checks are pure functions of a run folder (and the vault). Prose by Claude is a separate step in a session over MCP: checked, never trusted.
- **Everything has provenance.** Every statement names the events (and claims) it rests on.
- **A point of view is a filter, not a rewrite.** A POV pack holds what its holder could know and believe (§2). Only the chronicle states beliefs as fact, and it says whose account it is.
- **Determinism, exactly:**
  - JSON is written with `core.canon.canonical` (sorted keys, floats rounded: `conf` to 3 places);
  - every list is sorted by (date, id);
  - text is built only from sorted inputs, never from set or dict iteration order;
  - front matter carries no timestamps: it holds the run's manifest digest, the engine version and, when the vault was read, the vault digest.
- **Small stack.**
  - The MCP server is a small stdio JSON-RPC loop with no SDK.
  - Schemas are checked by a small validator over a frozen subset of JSON Schema: `type`, `required`, `enum`, `items`, `properties`, `additionalProperties: false`. There is no `jsonschema` dependency.

## 1a. Step 0: the M4 run

Worlds can't turn beliefs on from a recipe today: `fourth_age` takes only `scenario` and `scale`. So, before #115:
- `beliefs` becomes a `fourth_age` world parameter: a recipe's `[world] beliefs = true` sets the scenario's param.
- **`recipes/m4.toml`**, committed:
  - the Fourth Age with beliefs;
  - the ward-failure inject ripple at Lux Oescus in 4A 2;
  - 25 years, so schemes, slander and sagas have time to happen.
  - This is **the M4 run** every test and acceptance names; the story tests build its run folder once (a session fixture).
- **`renasci.story.trace`**: the belief trace (provenance #107: `trace`/`causeOf`) ported to Python, used by packs and by the MCP `person` tool. Shared test vectors (`tests/fixtures/traces.json`: event logs and their expected trace ids) are run by both pytest and Vitest, so the two can't drift.

## 2. Context packs (#115)

`renasci pack <run> (--arc ID | --saga ID | --person ID | --event ID | --topic KEY) [--pov omniscient|<person>|<house>|<settlement>]` writes `analysis/packs/<subject>--<pov>.json`.

**Subjects:**
- an **arc**, its events and people; a **saga**, its arcs (both from `stories.json`; their year spans become the first day of the first year to the last day of the last);
- a **person**, over their life;
- an **event**: it, its causes to depth 2, and its consequences (events caused by it) to depth 3. The ward failure, a ripple's work, is in no saga, and this is how it gets told;
- a **topic** from the claims report (#106): the event the topic is about, plus every competing claim.

**Contents:**
- `events`: each with a one-line reading;
- `people`: with `roles`, a list (a person can be lead and victim in different arcs);
- `places`;
- `beliefs`: claim, reading, confidence, holder and origin (the trace's last event); with `truth` only in the omniscient pack;
- `threads`: open schemes, grievances not taken up, latch points;
- `timeline`.

The schema is `schemas/pack.json`, with tests of known-bad packs.

**Readings** (`renasci.story.text`): new work, a template table for about 40 event types (people.*, belief.*, ward.*, geo.*, the toy's). Claims read through `Predicate.text`, which already exists. An unknown type gets a generic line from its roles.

**What a point of view could know** (person POV):
- **Residence over time:** their birth or cast place, then each `place` change in `state_deltas`, with journeys from `people.depart`/`people.arrive`.
- **Events:** public events at their residence while they lived there; any event where they hold a role; secret events only where they hold a role, or where they hold a belief whose trace reaches the event.
- **News:** in worlds with beliefs, news reaches them as their beliefs show. In worlds without, they learn nothing beyond their town, except the deaths and successions of their own house, which are known everywhere.
- **Beliefs:** as they stood at the end of the subject's span (or at the author's death), rebuilt from `state_deltas`, not from the final state.

**House** POV: the union of its members'. Where members hold rival claims on one topic, the **house's** is the head's, else the firmest, then the lower claim key.

**Settlement** POV: public events there, and its masses' shares as they stood then (rebuilt from `state_deltas`).

The person and omniscient POVs come first; house and settlement follow in the same ticket if time allows.

**As built (#115).**
- `renasci.story`:
  - `text`: readings for each event type; plain wording for ties, ambition and scheme ends, deaths and failed actions;
  - `pack`: `Run`, plus `Run.of` for tests; `build`;
  - `schema`: the validator, with the schema at `schemas/pack.json`;
  - `trace`.
- `renasci pack <run> --arc|--saga|--person|--event|--topic ID [--pov …]` writes `analysis/packs/`.
- State changes (`place`, `beliefs`, `shares`) are indexed by entity and field. A value "as it stood then" is:
  - the last change on or before the date;
  - before the first change, what that change replaced;
  - with no changes, the final state's.
- **The dead:** they learn nothing after their death, and their beliefs are as they died with them.
- **Rival claims:** a person keeps theirs; a house keeps one per question.
- **Topic packs** hold that question's claims, from everyone, titled "Who killed X?" or "Whose doing was …?".
- **Roles:** POV packs carry no verdict-like roles (the ward-keeper isn't "accused").
- **Not yet:**
  - arc and saga spans are the events' dates, not whole years;
  - travellers count as at their origin until they arrive;
  - house membership is the final state's.

## 3. POV chronicles (#116)

`renasci chronicle <run> --subject … --pov …` writes `analysis/chronicles/<subject>--<pov>.md`, built from the POV pack:
- **Telling:** in date order, a paragraph a year, with sentences from the readings. Where the author holds a claim about an event, the sentence states the claim, not the truth.
- **Silence:** what the author couldn't know isn't told.
- **Liars:** an author who told a lie on a topic (`belief.told` with `intent: "lie"`, the author as teller) narrates their lie: the victor's account. Without it, the guild master, who privately believes the truth, would tell the truth.
- **Front matter:**
  - the run, the subject and whose account it is;
  - `type: chronicle`, compatible with the vault's chronicles, so one can later be proposed to the vault;
  - a `divergence` list: every sentence whose claim is false or half true, with the event that tells the truth.
- **Slant:** optional and plain. The author's house leads each year. A small table, and nothing at random.

**The acceptance test**, on the M4 run's ward failure (`--event`):
- from **Lux Oescus** (its masses' shares), from **a townsman told the lie**, and from **the guild master** (a liar), the chronicle tells the lie and lists the divergence;
- from **the spared leader** (when the run spares them; a variant recipe with `spare = "leader"`), it tells the truth.

## 4. Canon checks (#117)

`renasci check-prose <run> <file.md> [--pov …]` writes `analysis/checks/<digest of the text>.json` and prints the findings.

1. **Claims out of prose:**
   - **Names:** resolved against the run. A name several people share is narrowed by a house or era the sentence states (hard filters only when stated). Otherwise it's reported as `ambiguous`, with the candidates (id, house, life span), so the prose can be repaired.
   - **Events:** "the ward failure at Lux Oescus in 4A 2" is resolved by type noun, place and year; an ambiguous reference is reported. This lets `caused` and `fault` claims, which take events, be checked.
   - **Relations** come from a pattern table per predicate (data; a world can add verbs):
     - killed (active and passive), caused, fault (its party may be a literal: "the guild's stones");
     - married, died in a year, member of a house, ruled from a year;
     - **alive at**: any dated sentence where a person acts.
   - **Dates** in the calendar's forms.
   - **`claims` blocks:** a fenced block of JSON lines `{"pred": …, "args": {…}}` (ids or names) is read verbatim, for exact checking.
2. **Judging:**
   - the S6 predicates through `truth.judge`, extended:
     - a `killed` whose victim was alive at the end, or died after the claimed date, is **false** (not unknown);
     - `half` is kept;
   - the new predicates through the final state and the event log (`alive_at` against death dates).
3. **Verdicts:**

   | | the author believed it | the author didn't |
   |---|---|---|
   | **true** | consistent | consistent if they could know it; else a **leak** |
   | **half** | consistent | a **half** finding |
   | **false** | consistent (their account) | a **contradiction** |
   | **unknown** | consistent | invention: listed, allowed |

   Omniscient is the row-wise default: everything is knowable and nothing is believed.
4. **The benchmark** (`renasci.story.bench`):
   - **Seeded set:** claims are seeded at the claim level, from the M4 run's true claims, mutated by kind:
     - wrong killer;
     - wrong victim (alive);
     - wrong year;
     - wrong house;
     - swapped spouse;
     - a dead person acting.

     A fixed number per kind is drawn by keyed draws. They are rendered by a **paraphrase table the extractor never imports**: active and passive voice, synonyms, both date forms, reordered clauses, "of House H" in different places. The same table renders the unseeded true sentences. M4's gate is **recall of at least 0.9** on the seeded set; precision on the unseeded set is reported (target: no false alarms).
   - **Held-out set:** about 50 sentences of free prose with labelled contradictions. They are written once by Claude in a session about the M4 run and committed as JSON (`tests/fixtures/heldout_prose.json`). Their recall is **reported, not gated**: it is the honest number for prose nobody templated.
   - `claims` blocks are excluded from both sets: they are exact by construction.

## 5. The MCP server (#118)

`renasci mcp --runs <abs path> [--vault <abs path>]` speaks MCP over stdio.

**Protocol:**
- Newline-delimited UTF-8 JSON-RPC 2.0, one message per line. On Windows, stdout is reconfigured to UTF-8 with `\n` line endings.
- **Nothing else writes to stdout.** Logs go to stderr, and the CLI functions the tools reuse run with stdout captured.
- `initialize`:
  - answers with the client's `protocolVersion` if it's one we support (2024-11-05, 2025-03-26, 2025-06-18), else our latest;
  - returns `capabilities: {"tools": {"listChanged": false}}` and `serverInfo: {name: "renasci", version}`.
- **Notifications** (`notifications/initialized`, `notifications/cancelled`, any without an id) are never answered.
- `ping` → `{}`.
- **Errors:**
  - -32700 for bad JSON;
  - -32601 for an unknown method;
  - -32602 for bad params or an unknown tool.
  - A tool's own failure (no such run, no such saga) is a **result** with `isError: true` and a text item, so the model sees it.
- **Shapes:**
  - `tools/list` returns `[{name, description, inputSchema}]`;
  - `tools/call` returns `{"content": [{"type": "text", "text": "<json>"}], "isError": false}`.

**Read tools:**
- `runs`, `run_summary`;
- `events` (paged);
- `event` (causes and consequences);
- `person` (kin, house, wants, wound, beliefs with traces, ties, schemes);
- `stories`, `claims`;
- `vault_search`, `vault_note`.

**Writing tools:** `pack`, `chronicle`, `brief`, `check_prose`.
- They write under the run's `analysis/` (atomically: a temporary file, then a rename).
- They return a **summary and a handle**, not the whole document: a saga's pack can pass the client's output cap (about 25k tokens). `fetch(handle, section, cursor)` pages through it.

**Safety:**
- Run names go through `observe.safe_relative` and the runs root, and ids through `observe.ENTITY`.
- `check_prose` caps its text at 256 KB and names its report by the text's digest.
- `vault_note` resolves through the loader only, by id, stem or title, never by path:
  - only the vault's `.md` notes, excluding dot-folders and `_proposed/` as the loader does;
  - `maps/*/private/` and anything outside the vault are never reachable.

**Setup:** a project-scoped `.mcp.json` with absolute paths (`uv run renasci mcp --runs <repo>/runs --vault <repo>/docs`). The README says so.

## 6. The campaign brief (#119)

`renasci brief <run> --saga ID` (or `--event`) writes `analysis/briefs/<subject>.md` from the omniscient pack, as a fixed template. It is deterministic, with event ids as footnotes:
1. **Premise:** the title, the span, and the latch point at the heart of it.
2. **What really happened** (for the GM).
3. **What people believe:** the claims that matter, their spread, and which are true.
4. **Factions:** the houses and towns involved, with heads, wants and grievances (plain lists to start).
5. **NPCs:** the living people at the end of the span, with wants, wound, secret, a false belief they hold, and ties.
6. **Hooks:** open schemes, grievances not taken up, lies a truth could overturn, latch points.
7. **Places:** a plain list.

## 7. The Observatory (#111)

- **Pack, chronicle and brief buttons** on saga, arc, person and event pages (with `--allow-launch`): `/api/pack`, `/api/chronicle` and `/api/brief` launch the command as a job, and the page offers the file, validated.
- **The canon-check page:** prose is pasted to `/api/check`.
  - It has its own cap (256 KB), since the launcher's bodies are 4 KB and argv can't carry text.
  - The server writes the text to `analysis/checks/<digest>.md` and launches `renasci check-prose <run> <that file>`.
  - The page shows each sentence with its claims, verdicts and the events behind them, contradictions first.
- The new routes join the module docstring's list of protected POSTs, with the same checks.

## 8. Testing

- **Step 0:**
  - a recipe with `beliefs = true` runs with beliefs;
  - the M4 run has the ward failure and some claims;
  - the trace vectors pass in Python and TS.
- **Packs:**
  - schema-valid for each subject kind and POV on the M4 run; known-bad packs refused;
  - a person POV holds no event they couldn't know (another's secret; another town's events before they lived there);
  - every item's events exist;
  - the same run gives the same bytes.
- **Chronicles:** §3's acceptance test: the lie and its divergence from the town, a told townsman and the master; the truth from the spared leader.
- **Canon check:**
  - extractor tests per pattern, voice and date form;
  - an ambiguous name and an ambiguous event are reported with their candidates;
  - each verdict-table cell;
  - the benchmark: seeded recall of at least 0.9, unseeded precision reported, held-out recall reported.
- **MCP**, as a scripted stdio session:
  - the handshake;
  - a notification getting no reply;
  - an unknown method (-32601);
  - each read tool;
  - a pack via its handle and `fetch`;
  - `isError` on a bad id;
  - a path-like argument refused;
  - nothing but JSON on stdout.
- **Brief:** every section present for the M4 run's top saga, and its hooks name real open threads.

## 9. Open questions (defaults chosen; on the review queue)

1. **No model in the engine**; prose only in sessions over MCP. A later `renasci write` calling the API is possible but not planned.
2. **A pattern extractor**, not a parser. The held-out recall shows what it misses, and `claims` blocks make a text exactly checkable.
3. **Chronicle voice and slant:** plain, left to Claude's rewrite.
4. **The campaign brief template** (§6): other sections (stat blocks, encounters)?
5. **Vault chronicles and myths as claim seeds** (master §5.11): S12's extractor can read a vault note's prose into claims. That is deferred to the vault bridge's next round, not M4.

## 10. Plan: working order

0. **Step 0** (§1a): the beliefs parameter, the M4 recipe, and the trace port with shared vectors.
1. **#115 packs:**
   - readings (new);
   - subjects (arc, saga, person, event, topic);
   - the omniscient and person POVs, then house and settlement;
   - the schema and validator; `renasci pack`.
2. **#118 MCP, the read tools:** the protocol, the read tools, `pack` with handles, and the scripted test. This is "query a run and fetch a pack", early.
3. **#116 chronicles:** the renderer with liars, the front matter and divergence, and the acceptance test.
4. **#117 canon checks:**
   - extractor (names, events, patterns, dates, blocks);
   - judging extensions and the verdict table;
   - the benchmark (paraphrase table, seeded set; the held-out set written in a session);
   - `renasci check-prose`.
5. **#119 brief:** the template.
6. **#118 MCP, the writing tools:** `chronicle`, `brief`, `check_prose`.
7. **#111 Observatory:** the buttons, `/api/check` and the page.

**Risky bits:**
- The extractor on free prose (the held-out recall shows it).
- Name ambiguity in big runs.
- Rebuilding beliefs and residence as of a date from `state_deltas` (cost, on long runs: index once per run).
- MCP output size.
