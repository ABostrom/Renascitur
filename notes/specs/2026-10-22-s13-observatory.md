---
title: S13 Observatory: sub-project spec
status: r2 (independent review folded in; #35)
parent: notes/specs/2026-10-21-history-engine-design.md (§6 S13, §8.2)
tickets: "#35 (this spec), epic #15, v0 build tickets #53–#56; #57 (launching runs) moves to M1"
---

# S13 Observatory

The Observatory is how Aaron *sees* a run, and later how he drives one. It is a browser app that reads
run folders. This spec fixes the architecture for all versions and details **v0**, the M0 deliverable.

**Standing choices** (Aaron, 2026-10-22):
- **Small stack.** SvelteKit, nothing heavy. No database in the browser, no DuckDB, no chart library.
  Charts are hand-made SVG.
- **Formats are JSON.** The Observatory reads the run folder's JSON Lines and gzipped JSON as they are.
- **Viewing needs no *application* server.** It does need a static file server, because browsers
  won't run a modern JS app from `file://`. Acting (launching runs) comes with `renasci serve` in M1.

## 1. v0: goals and exit

**v0 is done when**, given run folders produced by `renasci run` / `replay` / `diff`:

1. **`uv run renasci observe [runs]`** serves the built Observatory and the runs folder on
   `http://127.0.0.1:<port>`, read-only, using only Python's standard library, and opens the browser.
   The home page lists the runs with each manifest: recipe, seed, versions, segments, marks, state hash,
   and whether it is complete or a replay of another run. Incomplete runs are shown as such and can
   still be browsed.
2. **Event browser:** every event, filterable by type, date range, place, participant and free text,
   in a virtualised list that stays smooth at the v0 ceiling (**1M events**). Selecting an event shows
   it in full: roles, payload, causes, its activation and scope, the reads that scope made (with value
   digests), and the hinges it turned on.
3. **Cause-chain explorer:** from any event, walk *why* (ancestors) and *what it led to*
   (descendants) across events, activations, pins and ripples, as an expandable tree with depth
   control. Ripples and pins are visually distinct.
4. **Entity page** (may slip to v1 if #54 runs long): the entity's final record, its events, and its
   state changes (record fields from `state_deltas`, column cells from `bulk_deltas`).
5. **Run diff:** pick a baseline and a variant from the run list. A replay pre-selects its parent.
   The page shows divergent and unexplained counts, every unexplained item (each linking into the
   right run's event browser), and the **causal wave**: a heatmap of (place × age-year) cells showing
   divergent/total events. Clicking a cell filters the event browser to those divergent events.
6. **No-Python fallback:** a folder picker (`showDirectoryPicker` where available, otherwise
   `<input webkitdirectory>`) opens one run without `renasci observe`. Bookmarks and diffs then need
   re-picking, and the page says so.

**Not in v0:**
- launching runs (M1, `renasci serve`)
- stories and latch points (v1)
- genome and family tree (v1)
- beliefs (v2)
- maps (v3)
- a manual theme toggle: tokens follow `prefers-color-scheme` only

## 2. Architecture

```
observatory/                        # SvelteKit app: adapter-static, SPA mode (fallback index.html)
  src/lib/run/                      # data layer: no UI, unit-tested in Node
    source.ts      # RunSource: list(dir) and stream(path): ReadableStream<Uint8Array>
                   #   HttpSource (renasci observe), PickerSource (FS Access / webkitdirectory), NodeSource (tests)
    segments.ts    # which files make up a table: recovery rules ported from runfolder._recover
    jsonl.ts       # streaming line splitter over (gunzipped) bytes; splits only on "\n"
    calendar.ts    # format and parse dates from the manifest's calendar (a port of core.calendar)
    tables.ts      # lazy per-table loading
    index.ts       # compact indexes (int ids, typed arrays); full rows parsed on demand
    diff.ts        # divergence.json and pairing
  src/lib/ui/                       # virtual list, cause tree, wave heatmap, JSON view
  src/lib/theme.css                 # design tokens (light and dark via prefers-color-scheme)
  src/routes/                       # / (runs), /run/[name]/events, /run/[name]/event/[id],
                                    # /run/[name]/entity/[id], /diff/[a]/[b]
  fixtures/                         # committed golden run folders (+ scripts/regenerate.py)
src/renasci/observe.py              # the static server behind `renasci observe`
```

**Serving.** `renasci observe` is about 60 lines of `http.server`:
- `/` serves `observatory/build` (unknown paths fall back to `index.html` for SPA routing)
- `/runs/<name>/...` serves files from the runs folder
- `/runs/index.json` lists the run folders with their manifests

It binds to 127.0.0.1 only and accepts GET only. The built app is committed to
`observatory/build`, so Aaron doesn't need Node to *view*, only to change the Observatory.

**Reading.**
- Every read is a stream: `RunSource.stream()` returns a `ReadableStream`, and gzip goes through the
  browser's native `DecompressionStream`.
- Lines split only on `"\n"`, never `splitlines`, because U+2028 is legal inside JSON strings. A
  trailing line with no newline is dropped, since it belongs to an in-progress segment.
- `state.json.gz` and checkpoints are parsed whole. That's acceptable at v0 scale, and the ceiling is
  stated below.

**Segments and recovery.** The browser can't repair a folder, so it *selects*:
- below `manifest.segments`, prefer `seg-N.jsonl.gz`
- at `segments` (the open segment), prefer the raw `seg-N.jsonl`
- ignore `*.tmp`

These are the same rules as `runfolder._recover`, and a fixture with an interrupted close covers them.

**Memory and scale.**
- Indexes are compact. Event ids map to ints, and dates are packed into `Int32Array` (age × 10⁷ +
  year × 360 + day).
- There are postings lists per type, place and participant, as `Int32Array`s, plus causes in both
  directions as int pairs.
- Full event objects are kept only for the current page and the selection, and re-parsed from a
  per-segment byte-offset table when needed.
- **v0 ceiling: 1M events** (the toy baseline is 23k). Past that, the engine writes a per-run
  `index.json` (M1), which the reviewer flagged as likely to be needed.

**Engine changes (in the tickets below)**

| Change | Ticket | Why |
|---|---|---|
| The manifest records the **calendar** (ages, months, seasons) | #53 | Dates are formatted and parsed without knowing the world |
| Event rows record their **scope** (`activation`, `scope`) | #54 | Event detail finds its reads without scanning |
| Each closed segment gets a **sidecar** `index/seg-N.json`: first and last date, row counts per table | #54 | The right segment is loaded for a date or a scope |
| `divergence.json` lists **divergent ids per side** (`only_baseline`, `only_variant`, `changed`), **every** unexplained item with its run side, and **age-qualified** wave cells | #56 | The diff page links, highlights and drills down |
| `renasci observe` | #53 | Serving |

**Routing.**
- Views live in the URL, keyed by run *name*: `/run/toy-baseline/events?type=toy.death&from=1X 40`.
  Under `renasci observe` a bookmark or reload re-resolves the name.
- Under the picker fallback, a reload shows "re-open toy-baseline". On Chromium the directory handle
  is kept in IndexedDB, so re-opening takes one click.

**What each view reads**

| View | Tables and files |
|---|---|
| runs list | `runs/index.json` (manifests) |
| event browser | `events` (the participants index is built from event roles) |
| event detail | that event's row, `causes`, `hinges` (by event), and `reads` for its scope only (found via the sidecar's segment range) |
| cause tree | `causes` (both directions) and `activations` (activation causes) |
| entity page | `state.json.gz`, `participants`, `state_deltas`, `bulk_deltas` |
| diff | both runs' manifests, the variant's `analysis/divergence.json`, and both runs' `events` for links |

## 3. Design

- **Tokens** on `:root` cover background, surface, text, muted, accent, and the colours for
  divergent, unexplained, pin and ripple. They are redefined under `prefers-color-scheme: dark`.
- **Typography:** a quiet serif for headings and a monospace font for ids, payloads and dates.
- **Colour carries meaning, consistently.** A ripple always looks like the author's hand (one colour
  plus an icon). A pin always looks like canon. Unexplained always reads as an error.
- **The wave** uses one sequential ramp for divergent/total. Unexplained cells are outlined, not
  recoloured, so they work in both themes.
- **Dates** come from the calendar port: `format`/`parse` vectors are shared with Python tests, so the
  two implementations can't drift.
- **Layout:** works down to tablet width.

## 4. Testing

- **Data layer** (Vitest, in Node, through `NodeSource`), against **committed** fixture run folders:
  - a tiny toy run, a replay, its diff, and an interrupted-close folder
  - fixtures are regenerated only on purpose, with `scripts/regenerate_fixtures.py`
  - covers stream splitting (U+2028, gzip member boundaries, trailing partial lines), segment
    selection, indexes and diff pairing
- **Calendar:** shared JSON vectors are tested by both `pytest` and Vitest.
- **Server:** `renasci observe` has pytest coverage (listing, SPA fallback, GET-only, localhost only).
- **Built app:** one Playwright smoke test opens the served build in Chromium, opens a fixture run and
  sees its events. It's the only browser test in v0, and it guards the shipping model, which was the
  reviewer's top risk.

## 5. Ticket map (v0)

| Ticket | Delivers | Needs |
|---|---|---|
| #53 | scaffold (SvelteKit static, Vitest), tokens, `RunSource` (HTTP, picker, Node), segment selection, streaming JSONL, calendar port, runs list; **engine:** calendar in the manifest; **`renasci observe`**; committed build; smoke test | — |
| #54 | compact indexes, event browser with filters, event detail; **engine:** event scope, segment sidecars | #53 |
| #55 | cause-chain explorer; entity page (may slip) | #54 |
| #56 | diff page and causal wave; **engine:** richer `divergence.json` | #54 |
| #57 | `renasci serve` and launching: **M1** | — |

## 6. Later versions (direction)

- **v1 (M1):** Stories (period selector, story river, sagas › arcs › beats, latch points with what-if
  launching via `renasci serve`); Individuals (genome, family tree, ambitions and schemes,
  relationship web); a per-run `index.json` for scale.
- **v2:** world knowledge.
- **v3:** maps, ripple authoring, branches.
- **v4:** context packs.
- **v5:** First Age views.
- **v6:** breadth.

## 7. Changes from the review (r2)

1. **Shipping:** the static build can't run from `file://`, so there's a stdlib static server,
   `renasci observe`, a committed build and a real-browser smoke test.
2. **Routing:** runs are keyed by name. The picker fallback has a re-open prompt, with IndexedDB
   handles on Chromium.
3. **Event → reads:** events record their scope, and segment sidecars give date ranges and counts.
4. **Memory:** streaming everywhere, compact typed-array indexes, rows parsed on demand, and a stated
   1M-event ceiling.
5. **Diff data:** `divergence.json` gains per-side divergent ids, every unexplained item with its side,
   and age-qualified cells. Pairing goes through the run list.
6. **Recovery:** browser-side segment selection mirrors `_recover`, with its own fixture.
7. **Data per view** is listed. Calendar `parse` and `format` are ported, with shared vectors.
8. **Scope and testing:** committed fixtures, a Node source for tests, no theme toggle in v0, the
   entity page may slip, and master §8.2 now has `serve` in M1.
