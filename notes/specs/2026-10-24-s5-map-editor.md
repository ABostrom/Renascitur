# S5 Map Editor & Inkarnate Import: Sub-project Spec

**Status:** r2, 2026-10-24.
- r1 was reviewed by an independent agent. r2 fixes:
  - **privacy**: the image wasn't git-ignored (now it is, with a test); the mesh would have leaked the map's shape, so it is now private; viewing the image in a Claude session needs Aaron's OK;
  - **the mesh**: unstable cell ids, so it is now a frozen hex grid, not a regenerated Voronoi; an over-counting days formula; how `geo.check` takes the mesh;
  - **files**: where world files live (they stay in the package);
  - **import**: Pillow can't decode in strips, and the bomb limit;
  - **saving and the server**: cross-file validation, the endpoints' security details;
  - **scope**: dropped the TS check port, `d3-delaunay` and `params.cells`;
  - **replays and goldens**: a geography digest for replays, and when goldens move.
- Written without waiting for approval (the loop's low-ceremony rule). Aaron comments on #26 or the review queue (#150) if they disagree.

**References:**
- **Master spec:** `notes/specs/2026-10-21-history-engine-design.md`: §2 (Geography: "1 cell = 24 miles. We build our own map editor"), §6 S5, §8.3 (M3: "the full loop… on an edited map").
- **Builds on:** S4 as built (`notes/specs/2026-10-23-s4-world-geography.md`): the geography file, `geo.check`, paths, routing (#78), the map by year (#81); and the Observatory (S13) with its opt-in launcher.
- **Tickets:** #80 (cell mesh, an S4 ticket S5 needs first), #82 (import), #83 (Claude's draft layer), #84 (places and routes), #85 (regions and terrain). Epic #6.

## 0. In one paragraph

Pyrosia's geography is a hand-typed draft (S4): places and routes with placeholder days and no positions. S5 gives it a **map**, without publishing the map.
- An offline importer reads the private Inkarnate image and writes **private layers**: a downsampled base image, a land/water mask and candidate settlement markers.
- A **cell grid** of 24-mile hex cells carries terrain and regions, also privately.
- A **map editor** in the Observatory lets Aaron place settlements on cells, draw roads over cells and paint regions and terrain.
- When the editor saves, it **bakes** what the map implies (each route's days from the terrain it crosses, each settlement's region from its cell) into the **committed geography file**. That file keeps exactly the S4 shape the sim already reads, so nothing traced from the image reaches git.

**Done when** Pyrosia is fully edited in the editor and the Fourth Age runs on it: every settlement placed, every route drawn over cells with its days baked from terrain, and every region painted, with the baked geography read by the sim.

## 1. Principles

- **The image and everything traced from it stay private.**
  - `images/Renascitur.png` and `maps/*/private/` are git-ignored, and `tests/test_privacy.py` fails if they ever stop being ignored or become tracked.
  - Private covers the downsampled image, the mask, marker and place positions, the cell grid and its terrain and regions, and route cell paths: anything with a position or adjacency traced from the map.
  - Topology is a map too: committed adjacency plus per-cell terrain could be laid out again into the coastline. So none of it is committed.
- **What is committed is the S4 geography.** It holds places, regions and routes with days, all derived on save. A diff of `pyrosia.json` shows that a route's days changed, not where it runs. Whether positions may go public is Aaron's call (review queue Q20). If yes, the layout moves out of `private/` and nothing else changes.
- **The image isn't sent anywhere.** The importer runs locally. Claude drafting from tiles of the image (§5) would send pieces of it to the model API, so it waits for Aaron's explicit OK (a separate queue question). Until then Claude drafts from the vault and the importer's mask only.
- **Small stack.**
  - The importer is Python, with **Pillow** as an optional extra (`uv sync --extra map`). The engine never imports it.
  - The editor is an Observatory page with no new JavaScript dependency: the grid is drawn as SVG hexes.
  - Validation is the Python `geo.check`, behind an endpoint, rather than a TS port.
- **Writing is opt-in.** The editor saves through `renasci observe --edit-map <world folder>`, with the launcher's protections (§7). Without the flag there is no editor.
- **Stable by construction.** Cells are hexes with ids `c:<col>,<row>`, so they don't depend on a random seed or on float behaviour. The grid is generated once, per world, and then is the truth; changing its size is an explicit migration (§3).

## 2. Files

```
src/renasci/renascita/pyrosia.json      committed: the S4 geography, as baked by the editor (no positions, no cells)
maps/pyrosia/private/                   git-ignored, at the repo root (editor data, not package data)
  base.png         the image, reduced to about 4096 px wide, for the editor
  mask.png         land (white) and water (black), from the import
  markers.json     candidate settlement markers: position (as fractions of the map), size, confidence
  import.json      what the import was asked and found
  grid.json        the cell grid (§3): every cell's terrain and region
  layout.json      each place's cell and position, each route's cell path
  draft.json       Claude's draft layer (§5): places, regions, roads, terrain to accept or reject
```

- World data stays inside the package, where `geo.attach` resolves it next to the world module. There's no move and no path change: the editor is pointed at the file it edits, `--edit-map src/renasci/renascita/pyrosia.json`, and keeps its private layers in `maps/<world>/private/`, keyed by the file's stem.
- A world with no private layers works exactly as in S4.

## 3. The cell grid (#80)

**Cells:**
- A hexagonal grid, pointy-top in odd-r offset layout. A cell is 24 miles across its flats.
- Ids are `c:<col>,<row>`. Neighbours are computed from the id (six, fewer at the edges), so adjacency is never stored.
- The grid's width and height in cells come from the image's size and the map's scale (Q1: miles across). `renasci map grid <world> --miles-across N` writes `grid.json` once, after the import (§4), so the aspect is the image's.
- **Migration:** a grid at another scale is an explicit step, `renasci map regrid <world> --miles-across N`. It maps every old cell to the new cell containing its centre, so paths, places and paint survive (coarsened or stretched). Nothing regenerates silently.

**`grid.json`** (private):

```json
{"cols": 120, "rows": 90, "miles": 24,
 "terrain": {"plains": 1.0, "forest": 1.5, "hills": 2.0, "mountains": 4.0, "marsh": 2.5, "desert": 1.8, "water": null},
 "cells": {"c:12,40": {"terrain": "hills", "region": "v:ashen-plains"}}}
```

- Only painted cells are listed. An unpainted cell takes the mask's land/water (`plains` or `water`) and no region.
- Terrain kinds and costs are world data, and the defaults above are a draft (Q3). `null` means impassable by land.
- A cell names a **leaf** region (one with nothing `within` it), as places do.

**Derived days** (baked on save):
- A land route's cell path runs from its first end's cell to its last's, through adjacent cells.
- Its days are the sum over each step of the mean of the two cells' costs, times days per cell, rounded up, with a minimum of 1. Days per cell is 24 miles at about 20 miles a day on foot, so 1.2 (Q1).
- So two adjacent plains cells are 1.2 days, which rounds up to 2.
- **Water routes** (`sea`, `river`) keep their typed days: their path is for drawing only.
- **Routing (#78) applies on top.** Its mode factors are relative to an ordinary route of that kind. Terrain is in the base days, so a `pass` over mountain cells pays for the mountains through its cells and for the pass kind through #78. The editor shows both, and the factors may want retuning once real terrain lands.
- A route with no cell path keeps its typed days, as in S4.

**Regions** (baked on save): a settlement's region is its cell's region. The editor won't save a settlement standing on a cell with no region. `check_scenario` still requires the scenario's settlements to sit in the same regions as the geography's, so repainting a city into another province shows up as a scenario finding, to be fixed in the scenario draft, rather than applying silently.

**Checks** (`renasci.mapgrid.check(geography, grid, layout)` → findings, like `geo.check`):
- every cell named exists;
- every route path is adjacent step to step, and starts and ends on its places' cells;
- a land path never crosses `water`;
- every painted region exists and is a leaf;
- every settlement's cell has a region;
- the baked days and regions match what the geography says. A mismatch is a warning, so a file edited by hand still loads. These are the base days: a dated re-timing (#81 `changes`) changes them later in the run, so it doesn't excuse drift.

**As built (#80).**
- `renasci.mapgrid` holds the cells (ids, neighbours, centres, `at`, straight lines), `new_grid` (water painted from the import's mask), `days`, `check`, `bake` and `regrid`.
- `layout.json` is `{places: {id: {cell, at?}}, routes: {id: {cells}}}`.
- Commands:
  - `renasci map grid --world w --miles-across N`: once, from `import.json` and `mask.png`;
  - `renasci map check --world w --geography <file>`;
  - `renasci map bake --world w --geography <file> [--write]`: a dry run by default; a map with errors bakes nothing.
- The grid and layout stay private. Only the baked days and regions reach the geography file.
- Pyrosia's own grid waits for the map scale (Q1) and Aaron's import (#82).
- `regrid` is a library function for now, with no command.
  - Paint goes to the cell under each old cell's centre, by majority.
  - Paths are re-traced over land by the fewest cells.
- A route with an empty path has no path.
- A malformed grid is a finding, not a crash.
- A place of any kind takes its cell's region when baked.

## 4. Import (#82)

`renasci map import images/Renascitur.png --world pyrosia --water x,y [--water x,y …] --marker x,y` (needs the `map` extra) writes `maps/pyrosia/private/`:

1. **Decode once**, with `Image.MAX_IMAGE_PIXELS = None` set explicitly. 198 megapixels is over Pillow's bomb limit, and PNG can't be decoded in strips: it's one zlib stream with per-row filters. Then reduce straight away: to about 4096 px for `base.png` and the mask, and to about 8192 px for markers. Peak memory is about 800 MB, which is noted in the command's help.
2. **Mask:**
   - Water is the colours near the given `--water` samples (required: painted maps often have frames, so the corners aren't trusted). Land is the rest.
   - The mask is cleaned by a small numpy open/close and traced by marching squares for drawing.
   - Each grid cell then takes land or water by majority over its area.
   - scipy isn't in the stack, so the morphology, connected components and marching squares are hand-written numpy (small, and tested on synthetic images).
3. **Markers:**
   - Connected blobs near the `--marker` sample's colour, within a size range and roughly square (bounding-box fill and aspect).
   - Each is written with its position in cells and a confidence.
   - The importer reports how many it found (the ticket expects about 15) and never decides which place is which.
4. Positions are in cells, not pixels, so a different resolution of the same image imports the same layout.

**As built (#82).**
- `renasci map import <image> --world <w> --water x,y [--water …] --marker x,y` (module `renasci.mapimport`) writes `maps/<w>/private/`:
  - `base.png`;
  - `mask.png`: land and water as an image, 1024 px across, rather than traced polylines. The grid reads each cell's land or water from it, and the editor overlays it;
  - `markers.json`;
  - `import.json`.
- Positions are **fractions of the map's width and height**: the scale is unknown (Q1), and they convert to cells when the grid is made (#80).
- Markers:
  - a blob counts as a marker when it is within half to twice the sampled marker's area and square (fill × aspect at least 0.88; a circle is about 0.78);
  - connected components are found by row runs and union-find, in numpy, with no scipy.
- The real import needs a water point and a marker point read off the image in a viewer, so Aaron runs it (Q22). The importer never sends the image anywhere.
- After review:
  - It writes only where git ignores, when inside the repo, and refuses otherwise.
  - A marker point that misses an icon's fill (sea, outline, speck, round blob) is refused.
  - Points are checked before the decode.
  - The full image is reduced once, to the marker width, and every smaller layer comes from that.
  - An earlier import is replaced only with `--force`.
  - The mask at 1024 px loses islands under about 45 original px; raise `--mask-width` if one matters.

## 5. Claude's draft layer (#83)

- **Without the image (the default):** Claude drafts from the vault's geography notes (provinces, cities, roads named in prose) and from `markers.json` and the land share in `import.json` (not from `mask.png`, which is an image of the map's shape).
  - It writes `private/draft.json`: proposed regions as cell sets, terrain as cell sets (coast, likely hills from the notes), roads as cell paths between places, and places the markers missed.
  - Each item has a `why` (which note or which marker) and `draft: true`.
- **With the image** (only if Aaron says yes to Q5): the same, also reading downsampled tiles.
- The editor shows the draft as its own layer. Aaron accepts or rejects each item, or a whole kind, and only accepted items reach the grid, the layout and the baked geography. Nothing in a draft is canon.

## 6. The editor (#84, #85)

`/edit/<world>` in the Observatory, available when `observe` runs with `--edit-map`. The map pane shows the base image, hex cells, the mask outline, places, routes and the draft, each toggleable. A side pane shows the selection's attributes.

**Places and routes (#84):**
- **Places:** select, move (to a cell), add at a cell or from a marker, delete. Attributes are name, kind and id (an existing vault id, or a new `g:` id).
- **Routes:** draw by clicking cells from place to place. The path follows adjacency, and "cheapest by terrain" fills it in. Attributes are kind, Vialux, open and barred. Days are shown as derived. A water route's days are typed.
- **Changes** (S4 #81): add a dated change to the selected route or place.

**Regions and terrain (#85):**
- A **brush** paints the selected region, or the selected terrain, onto cells (click or drag; the size is a radius in cells).
- **Fill** floods adjacent land cells.
- A side list creates, renames and nests regions.

**Everywhere:**
- Undo and redo in memory.
- `POST /api/map/check` returns `geo.check` and the grid check's findings for the unsaved state, debounced as you edit. Errors block saving and warnings are listed.
- **Save** sends everything changed in one request (§7). The baked `pyrosia.json` is written by `geo.dumps`, so the commit is a reviewable diff, one record per line.

## 7. The server

`renasci observe runs --edit-map src/renasci/renascita/pyrosia.json`. This works without `--allow-launch`.
- `GET /api/map` returns the geography and the private layers (grid, layout, mask, markers, draft) as one JSON document.
- `GET /api/map/base.png` returns the private image.
  - Both GETs send `Cache-Control: no-store` and `Cross-Origin-Resource-Policy: same-origin`, so no other site can embed them.
- `POST /api/map/check` and `PUT /api/map` take the whole edited state, at most 16 MB. The PUT:
  - validates everything together (a painted region and the place it moves must agree);
  - bakes the geography;
  - then writes each file atomically, to a temporary file then `os.replace`, keeping one `.bak` (git-ignored).
  - A failed replace on Windows (the file open elsewhere) is a clear 409, not a 500.
- **Security:**
  - every check the launcher's POSTs make: the Host check, the Origin, `X-Renasci-Launch`, `Content-Type: application/json`, and Content-Length required, with the connection closed when the body is too large;
  - `do_PUT` is answered only for `/api/map`, and only with `--edit-map`;
  - the world file and its private folder are fixed at launch. No request names a path: the files written are a fixed set.

## 8. The sim and replays

- The sim reads only the baked geography, so the engine is unchanged.
- **Replays on an edited map:**
  - A run's manifest records the digest of the geography it ran on, and `renasci replay` warns when the file has changed since, as it does for the vault.
  - A replay restores the base's routes from its checkpoint, so it isn't affected. A run or rerun from the start uses the current file.
- **Goldens:**
  - The ward-failure and Fourth Age goldens depend on Pyrosia's route days.
  - Code alone (#80, #82, #84 before any save) leaves them byte-identical.
  - The first real save of Pyrosia in step 6 changes route days. Re-pin the seeds then and say so on the ticket.

## 9. Testing

- **Privacy:**
  - `tests/test_privacy.py`: ignored and untracked;
  - no committed file under `src/renasci/*/` carries `at`, `cell` or `cells`.
- **Grid:**
  - neighbours from ids (edges and corners);
  - derived days on a hand-computed path (adjacent plains is 2; a hills step is mean cost × 1.2);
  - a water route keeps its days;
  - a fixture for each check failure;
  - `regrid` keeps a place, a path and a painted region on their new cells.
- **Importer**, on synthetic PNGs drawn in the test (a sea with a framed border, an island, four square markers and a round blob that is not a marker):
  - mask and markers right;
  - the same layout at two resolutions;
  - the bomb limit handled.
- **Server:**
  - every refusal (Host, Origin, header, type, length, oversize, PUT without `--edit-map`);
  - a cross-file inconsistent save refused with findings and nothing written;
  - a valid save writes `geo.dumps` output, the `.bak` and the private files;
  - the GETs carry their headers.
- **Editor** (smoke test, on a small fixture world with a synthetic base image):
  1. move a place, draw a route over cells, paint a region;
  2. save; the baked file has the new days and region;
  3. reload, and the edits are there;
  4. `renasci run` on it.

## 10. Open questions (defaults chosen; on the review queue)

1. **Map scale:** how many miles across is the Inkarnate map (or what does its scale bar say)? The grid waits for it, because a guess would mean a regrid later. Days per cell (1.2) also assumes about 20 miles a day on foot.
2. **Positions public?** (Q20.) Default: no. Committed files carry only the baked S4 geography. Making positions public would publish the layout (cells and positions), which is a coarse copy of the map.
3. **Terrain kinds and costs:** the list in §3 is a draft.
4. **Hex cells, not Voronoi:** the master spec's "Voronoi" gives way to hexes for stable ids and a smaller build. Say if the irregular look matters (a jittered hex drawing can come later without changing ids).
5. **May Claude view tiles of the image** to draft (§5)? That sends pieces of it to the model API. Default: no; draft from the vault and the mask only.

## 11. Plan: working order

0. **Privacy:** ignore rules and `tests/test_privacy.py` (done with this spec).
1. **#82 import:** the Pillow extra, `renasci map import`, mask and markers, and the synthetic-image tests. This comes first: the grid's aspect comes from the image.
2. **#80 grid:** `renasci map grid` (after Q1, or at a draft scale clearly marked), `renasci.mapgrid` (neighbours, derived days, checks, bake), and `regrid`.
3. **#84 editor, places and routes:** the map endpoints (`--edit-map`), the editor page, check-as-you-go, save and bake, and the smoke test.
4. **#85 regions and terrain:** brush, fill, the region list, and region baking.
5. **#83 the draft layer:** accept and reject in the editor, then a drafting session (vault and mask; the image only if Q5 is yes).
6. **Pyrosia, edited**, with Aaron: place the cities, draw the roads, paint the provinces, save. Then re-pin the goldens that move.

**Risky bits:**
- Decoding 198 megapixels (about 800 MB, decoded once).
- Colour thresholds on a painted map.
- Keeping every traced position out of commits (the privacy tests).
- #78's factors double-counting terrain on passes.
- Goldens moving on the first save.
