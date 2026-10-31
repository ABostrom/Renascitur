# Extending the engine

Every list of content lives in a **pool**. To add to one, write a Python file with an `extend(pools)` function and name it in a recipe. You don't edit engine files, and a world that doesn't name your file is unaffected.

[`examples/extensions/ext_pilgrims.py`](../examples/extensions/ext_pilgrims.py) adds something to nearly every pool. A test runs it, so it stays correct. Copy from it.

## Trying it

```toml
[run]
name = "pilgrims"
engine = "0.1.0"
seed = 3
world = "fourth_age"
end = "4A 10"
extensions = ["ext_pilgrims"]
```

Run from the folder holding the file, or put it on the Python path:

```
renasci run pilgrims.toml
renasci pools ext_pilgrims                # every entry, and which file added it
renasci graph --extensions ext_pilgrims --check
```

A digest of the extension's source is kept in the run's manifest, and a replay refuses an edited extension. Read a run (`stories`, `pack`, `gen`) from the same folder too: if the extension won't load, you get a note on stderr and its events read generically. An edited one is used as it now stands, so old runs take its new words.

## Every endpoint

| Pool | Adds | Shape | Read by |
|---|---|---|---|
| `actions` | a step in a scheme | `Action`: `achieves`, `possible`, `odds`, `succeed`; `killing` names a fatal one in stories | planner, schemes |
| `ambitions` | something to want | `Ambition`: `eligible`, `urge`, `subgoals`, `text`; `stakes`, `titles`; `held_by` and `act` for things that want | people each year |
| `goals` | a planner tag's meaning | `Goal(kind, check)`: is `kind:ref` already true? | planner |
| `drives` | a need | `Drive`: `level(ctx, person, settlement)` | `people.drives` |
| `marks` | a change over time | `Mark(id, name, fits, needs, gives, ...)`: `needs` are running counts or fields; `agency=True` makes a thing want | `Marks` |
| `verdicts` | a court's decision | `Verdict`: `weight`, `possible`, `carry_out` | `courts.trial` |
| `succession` | a line of succession | `SuccessionRule`: `candidates`, `choose`, `presumptive` | houses, by the scenario's `rule` |
| `event_types` | a kind of event | `EventType(name, version, roles, payload)` | everything |
| `reactions` | an authored beat | `Reaction(name, on, run, emits=...)`: runs after the event, and its event is caused by it | the engine |
| `systems` | a whole mechanic | `System`: `cadence`, `reads`, `writes`, `event_types`, `run` | every ruleset |
| `forcers` | how a pinned event is made to happen | `System` with `handles` (an event type) and `force(ctx, pin)` | every ruleset |
| `disguises` | how a ripple looks in the world | `Disguise`: `handles` (a ripple kind), `apply(ctx, ripple)` | every ruleset |
| `links` | a stated cause in the graph | `Link(cause, effect, why)`: describes and changes nothing | `renasci graph` |
| `wording` | how an event reads | `Wording(event_type, text)`: `text(event, names)` | story layer |
| `generators` | a kind of card | `Generator`: `kind`, `takes`, `fits`, `card`, `notable` | `renasci gen` (the Forge offers only the built-in kinds) |

A new kind of content needs one line: `pools.define("mine")`, in a module listed in `HOMES` in `core/pools.py`.

## Rules worth knowing

- **Declare what you touch.** `reads` and `writes` on an entry are granted for the run. Anything undeclared raises `UndeclaredAccess`. `ids:settlement` reads a list of ids, and `new:vow` creates an entity.
- **Keep nothing on the instance.** All state goes in the store, or checkpoints refuse the run.
- **Draw through `ctx`** (`ctx.chance`, `ctx.choose`), never `random`, so runs replay.
- **Connect through shared state.** To have a mechanic affect another, add to a stock (`core/stocks.py`) or write a field others read. A `Reaction` is for deliberate story, and shows up in a run as authored.
- **No two entries share a key,** and an extension can't replace a base entry. Two disguises for one ripple kind are refused. The exception is `wording`, which can reword a base event, as the base lines aren't in the pool.

## Not pools, and what to do instead

- **War's steps.** They're the flow of `Campaigns`, not a list. Add a `Reaction` on `polity.battle` or `polity.siege`, or a `System`.
- **Numbers.** Most mechanics take scenario params: ecology's rates are under `params.ecology`. Many module constants, such as `LEVY` and `SACK_MASSES`, aren't overridable yet. There's no separate tuning pool: when you want one changed, move it to a param.
- **An extension system in one age only.** Systems join every ruleset; check `ctx.params` or the date in `run`.
- **A realm's office** takes only `appointment` or `election`. A house can name any rule.
