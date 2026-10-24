<script lang="ts">
	/**
	 * The map editor (S5 §6, #84): places and routes on the world's cell grid, over its private base image.
	 * Served only by `renasci observe --edit-map <geography>`; saving checks, bakes and writes on the server.
	 */
	import { onMount } from 'svelte';

	import { addPlace, addRoute, deletePlace, deleteRoute, movePlace, placeAt, redrawRoute, setAttr, type MapState } from '$lib/map/edit';
	import { at, centre, corners, days, regionOf, terrainOf, type Grid } from '$lib/map/hex';

	type Finding = { kind: string; id: string | null; message: string; severity: 'error' | 'warning' };
	type Tool = 'select' | 'move' | 'place' | 'route';

	let world = $state<string | null>(null);
	let unavailable = $state(false);
	let hasBase = $state(false);
	let markers = $state<{ id: string; x: number; y: number }[]>([]);
	let s = $state<MapState | null>(null);
	let past = $state<string[]>([]);
	let future = $state<string[]>([]);
	let saved = $state<string | null>(null); // the state as last saved (to say what's unsaved)
	let findings = $state<Finding[]>([]);
	let message = $state<string | null>(null);
	let tool = $state<Tool>('select');
	let selected = $state<{ what: 'place' | 'route'; id: string } | null>(null);
	let drawing = $state<{ from: string; via: string[]; redraw?: string } | null>(null);
	let newPlace = $state({ id: '', name: '', kind: 'settlement' });
	let routeKind = $state('road');
	let saving = $state(false);
	let checks = 0; // (each check's number: a slower, older answer is ignored)
	let showBase = $state(true);
	let showGrid = $state(true);

	const grid = $derived(s?.grid as Grid | undefined);
	const W = $derived(grid ? grid.cols * grid.miles + grid.miles / 2 : 0);
	const H = $derived(grid ? (grid.rows * 1.5 + 0.5) * (grid.miles / Math.sqrt(3)) : 0);
	// The map image's own size in miles (the cells overhang it); markers are fractions of it.
	const extent = $derived((grid as Grid & { extent?: [number, number] } | undefined)?.extent ?? [W, H]);
	const unsaved = $derived(s !== null && saved !== null && JSON.stringify(s) !== saved);
	const errors = $derived(findings.filter((f) => f.severity === 'error'));

	onMount(async () => {
		const caps = await (await fetch('/api/capabilities')).json();
		if (!caps.edit_map) {
			unavailable = true;
			return;
		}
		const r = await (await fetch('/api/map')).json();
		world = r.world;
		if (r.error) {
			message = r.error;
			return;
		}
		hasBase = r.base;
		markers = r.markers;
		if (!r.grid) {
			message = 'This world has no grid yet: run `renasci map grid` first.';
			return;
		}
		s = { geography: r.geography, grid: r.grid, layout: r.layout };
		saved = JSON.stringify(s);
		check();
	});

	let timer: ReturnType<typeof setTimeout> | null = null;
	function check() {
		if (timer) clearTimeout(timer);
		timer = setTimeout(async () => {
			if (!s) return;
			const mine = ++checks;
			try {
				const r = await fetch('/api/map/check', { method: 'POST', headers: headers(), body: JSON.stringify(s) });
				const answer = r.ok ? await r.json() : [{ kind: 'server', id: null, message: await r.text(), severity: 'error' }];
				if (mine === checks) findings = answer;
			} catch (e) {
				if (mine === checks) message = `Couldn't check: ${(e as Error).message}`;
			}
		}, 300);
	}
	const headers = () => ({ 'Content-Type': 'application/json', 'X-Renasci-Launch': '1' });

	/** One undoable edit. */
	function edit(f: (s: MapState) => MapState) {
		if (!s) return;
		if (saving) {
			message = 'Saving… (edits wait until it is done)';
			return;
		}
		try {
			const next = f(s);
			past = [...past, JSON.stringify(s)].slice(-200);
			future = [];
			s = next;
			message = null;
			check();
		} catch (e) {
			message = (e as Error).message;
		}
	}
	function undo() {
		if (!past.length || !s) return;
		future = [JSON.stringify(s), ...future];
		s = JSON.parse(past.at(-1)!);
		past = past.slice(0, -1);
		check();
	}
	function redo() {
		if (!future.length || !s) return;
		past = [...past, JSON.stringify(s)];
		s = JSON.parse(future[0]);
		future = future.slice(1);
		check();
	}

	async function save() {
		if (!s || saving) return;
		saving = true;
		try {
			await saveNow();
		} catch (e) {
			message = `Not saved: ${(e as Error).message}`;
		} finally {
			saving = false;
		}
	}
	async function saveNow() {
		if (!s) return;
		const r = await fetch('/api/map', { method: 'PUT', headers: headers(), body: JSON.stringify(s) });
		if (r.ok) {
			const out = await r.json();
			const fresh = await (await fetch('/api/map')).json(); // (the baked geography: days and regions)
			s = { geography: fresh.geography, grid: fresh.grid, layout: fresh.layout };
			saved = JSON.stringify(s);
			message = `Saved${out.changed.length ? `: ${out.changed.join(', ')} baked` : ''}.`;
			check();
		} else {
			const body = await r.text();
			try {
				findings = JSON.parse(body);
				message = 'Not saved: fix the errors below.';
			} catch {
				message = `Not saved: ${body}`;
			}
		}
	}

	function cellAt(e: MouseEvent): string | null {
		const svg = (e.currentTarget as SVGSVGElement) ?? null;
		if (!svg || !grid) return null;
		const pt = svg.createSVGPoint();
		pt.x = e.clientX;
		pt.y = e.clientY;
		const p = pt.matrixTransform(svg.getScreenCTM()!.inverse());
		return at(p.x, p.y, grid);
	}

	function click(e: MouseEvent) {
		if (!s) return;
		const c = cellAt(e);
		if (!c) return;
		const here = placeAt(s, c);
		if (saving) return;
		if (tool === 'select') selected = here ? { what: 'place', id: here } : null;
		else if (tool === 'move' && selected?.what === 'place') edit((x) => movePlace(x, selected!.id, c));
		else if (tool === 'place') edit((x) => addPlace(x, { ...newPlace }, c));
		else if (tool === 'route') {
			if (!drawing) {
				if (here) drawing = { from: here, via: [] };
				else message = 'Start a route on a place.';
			} else if (drawing.redraw && c === s.layout.places[s.geography.routes.find((r) => r.id === drawing!.redraw)?.ends[1] ?? '']?.cell) {
				const d = drawing;
				edit((x) => redrawRoute(x, d.redraw!, d.via));
				drawing = null;
			} else if (!drawing.redraw && here && here !== drawing.from) {
				const d = drawing;
				edit((x) => addRoute(x, d.from, here, d.via, routeKind));
				drawing = null;
			} else drawing = { ...drawing, via: [...drawing.via, c] };
		}
	}

	const hexPath = (id: string, miles: number) => 'M' + corners(id, miles).map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join('L') + 'Z';
	const TERRAIN_FILL: Record<string, string> = {
		water: 'var(--series-1)', forest: 'var(--series-6)', hills: 'var(--series-4)', mountains: 'var(--muted)',
		marsh: 'var(--series-3)', desert: 'var(--series-5)'
	};
	const painted = $derived(grid ? Object.entries(grid.cells).filter(([, v]) => v.terrain && v.terrain !== 'plains') : []);
	// (the outline depends only on the grid's size, not on each edit: worked out once per size)
	const size = $derived(grid ? `${grid.cols},${grid.rows},${grid.miles}` : '');
	const outlineFor = (key: string) => {
		const [cols, rows, miles] = key.split(',').map(Number);
		return Array.from({ length: rows * cols }, (_, i) => hexPath(`c:${i % cols},${Math.floor(i / cols)}`, miles)).join('');
	};
	const outline = $derived(size && showGrid ? outlineFor(size) : '');
	const pts = (cells: string[]) => cells.map((c) => centre(c, grid!.miles).map((v) => v.toFixed(2)).join(',')).join(' ');
	const name = (id: string) => (s?.geography.places.find((p) => p.id === id) as { name?: string } | undefined)?.name ?? id;
	const place = $derived(selected?.what === 'place' ? s?.geography.places.find((p) => p.id === selected!.id) : undefined);
	const route = $derived(selected?.what === 'route' ? s?.geography.routes.find((r) => r.id === selected!.id) : undefined);
	const byCells = $derived(route && s?.layout.routes[route.id] ? days(s.layout.routes[route.id].cells, grid!) : null);
</script>

<svelte:window
	onkeydown={(e) => {
		const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement;
		if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') (e.preventDefault(), e.shiftKey ? redo() : undo());
		if (e.key === 'Escape') drawing = null;
	}} />

<p class="crumbs"><a href="/">Runs</a> › map editor{world ? `: ${world}` : ''}</p>

{#if unavailable}
	<p class="card">No map is being edited. Start the Observatory with <code>renasci observe --edit-map src/renasci/renascita/pyrosia.json</code>.</p>
{:else if !s || !grid}
	<p class="card">{message ?? 'Loading the map…'}</p>
{:else}
	<h1>Map editor <span class="muted small">{world}</span></h1>
	<div class="toolbar" role="toolbar" aria-label="Tools">
		{#each [['select', 'Select'], ['move', 'Move place'], ['place', 'Add place'], ['route', 'Draw route']] as [t, label] (t)}
			<button class:active={tool === t} aria-pressed={tool === t} onclick={() => ((tool = t as Tool), (drawing = null))}>{label}</button>
		{/each}
		<span class="sep"></span>
		<button onclick={undo} disabled={!past.length}>Undo</button>
		<button onclick={redo} disabled={!future.length}>Redo</button>
		<button class="save" onclick={save} disabled={!unsaved || errors.length > 0 || saving}>{saving ? 'Saving…' : unsaved ? 'Save' : 'Saved'}</button>
		<label class="small"><input type="checkbox" bind:checked={showBase} disabled={!hasBase} /> map image</label>
		<label class="small"><input type="checkbox" bind:checked={showGrid} /> cells</label>
	</div>
	{#if tool === 'place'}
		<div class="toolbar small">
			<label>Id <input bind:value={newPlace.id} placeholder="v:… or g:…" class="mono" /></label>
			<label>Name <input bind:value={newPlace.name} /></label>
			<label>Kind <input bind:value={newPlace.kind} /></label>
			<span class="muted">then click a cell</span>
		</div>
	{/if}
	{#if tool === 'route' && !drawing}
		<div class="toolbar small">
			<label>Kind
				<select bind:value={routeKind}>
					{#each ['road', 'track', 'pass', 'river', 'sea'] as k (k)}<option value={k}>{k}</option>{/each}
				</select>
			</label>
			<span class="muted">then click a place, the cells it passes, and another place</span>
		</div>
	{/if}
	{#if drawing}
		<p class="muted small" role="status">
			Drawing from {name(drawing.from)} through {drawing.via.length} cell{drawing.via.length === 1 ? '' : 's'}:
			click cells, then {drawing.redraw ? 'its far end' : 'another place'} (Esc to stop).
		</p>
	{/if}
	{#if message}<p class="note" role="status">{message}</p>{/if}

	<div class="layout">
		<div class="scroll card">
			<!-- (the map is pointer-driven; every edit it makes is also reachable from the side panel and the lists) -->
			<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
			<svg class="map" viewBox={`0 0 ${W} ${H}`} role="application" aria-label={`Map of ${world}: click cells to edit`} onclick={click}>
				{#if hasBase && showBase}<image href="/api/map/base.png" x="0" y="0" width={extent[0]} height={extent[1]} preserveAspectRatio="none" opacity="0.85" />{/if}
				{#each painted as [c, v] (c)}
					<path d={hexPath(c, grid.miles)} class="terrain" style={`fill: ${TERRAIN_FILL[v.terrain ?? ''] ?? 'none'}`} />
				{/each}
				{#if outline}<path d={outline} class="outline" />{/if}
				{#each s.geography.routes as r (r.id)}
					{@const path = s.layout.routes[r.id]?.cells}
					{#if path?.length}
						<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
						<polyline points={pts(path)} class={`route ${r.kind}`} class:vialux={r.vialux} class:picked={selected?.id === r.id}
							onclick={(e) => { if (tool === 'select') { e.stopPropagation(); selected = { what: 'route', id: r.id }; } }} />
					{/if}
				{/each}
				{#if drawing && s.layout.places[drawing.from]}
					<polyline points={pts([s.layout.places[drawing.from].cell, ...drawing.via])} class="drawing" />
				{/if}
				{#each markers as m (m.id)}
					<rect x={m.x * extent[0] - 3} y={m.y * extent[1] - 3} width="6" height="6" class="marker"><title>marker {m.id}</title></rect>
				{/each}
				{#each Object.entries(s.layout.places) as [pid, v] (pid)}
					{@const [x, y] = centre(v.cell, grid.miles)}
					<circle cx={x} cy={y} r={grid.miles / 3} class="place" class:picked={selected?.id === pid}><title>{name(pid)}</title></circle>
					<text x={x} y={y - grid.miles / 2} class="label">{name(pid)}</text>
				{/each}
			</svg>
		</div>

		<aside class="card side">
			{#if place}
				<h2>{name(place.id)}</h2>
				<p class="mono small">{place.id} · {s.layout.places[place.id]?.cell ?? 'not placed'} · {place.region}</p>
				<label>Name <input value={(place as { name?: string }).name ?? ''} onchange={(e) => edit((x) => setAttr(x, 'place', place.id, 'name', e.currentTarget.value))} /></label>
				<label>Kind <input value={place.kind} onchange={(e) => edit((x) => setAttr(x, 'place', place.id, 'kind', e.currentTarget.value))} /></label>
				<p class="small muted">Its region comes from its cell when saved{s.layout.places[place.id] ? `: ${regionOf(s.layout.places[place.id].cell, grid) ?? 'none painted yet'}` : ''}.</p>
				<button onclick={() => (tool = 'move')}>{s.layout.places[place.id] ? 'Move it…' : 'Place it…'}</button>
				{#if s.layout.places[place.id]}
					<button onclick={() => { tool = 'route'; drawing = { from: place.id, via: [] }; }}>Draw a route from here…</button>
				{/if}
				<button class="danger" onclick={() => { const id = place.id; edit((x) => deletePlace(x, id)); selected = null; }}>Delete</button>
			{:else if route}
				<h2>{name(route.ends[0])} – {name(route.ends[1])}</h2>
				<p class="mono small">{route.id}</p>
				<label>Kind
					<select value={route.kind} onchange={(e) => edit((x) => setAttr(x, 'route', route.id, 'kind', e.currentTarget.value))}>
						{#each [...new Set(['road', 'track', 'river', 'sea', 'pass', route.kind])] as k (k)}<option value={k}>{k}</option>{/each}
					</select>
				</label>
				<label class="check"><input type="checkbox" checked={!!route.vialux} onchange={(e) => edit((x) => setAttr(x, 'route', route.id, 'vialux', e.currentTarget.checked || ''))} /> the Vialux</label>
				<label class="check"><input type="checkbox" checked={route.open !== false} onchange={(e) => edit((x) => setAttr(x, 'route', route.id, 'open', e.currentTarget.checked ? '' : false))} /> open</label>
				<p class="small">
					{route.days} days{#if route.kind === 'sea' || route.kind === 'river'} (typed: by boat){:else if byCells !== null && byCells !== route.days} · <strong>{byCells}</strong> by its cells, when saved{:else if byCells === null && s.layout.routes[route.id]} · <span class="warn">crosses water</span>{/if}
				</p>
				{#if route.kind === 'sea' || route.kind === 'river'}
					<label>Days <input type="number" min="1" value={route.days} onchange={(e) => edit((x) => setAttr(x, 'route', route.id, 'days', Number(e.currentTarget.value)))} /></label>
				{/if}
				{#if s.layout.places[route.ends[0]] && s.layout.places[route.ends[1]]}
					<button onclick={() => { tool = 'route'; drawing = { from: route.ends[0], via: [], redraw: route.id }; }}>Redraw its path…</button>
				{:else}
					<p class="small muted">Place both its ends to draw it.</p>
				{/if}
				<button class="danger" onclick={() => { const id = route.id; edit((x) => deleteRoute(x, id)); selected = null; }}>Delete</button>
			{:else}
				<p class="muted small">Select a place or a route. Places: {s.geography.places.length}, on the map: {Object.keys(s.layout.places).length}; routes: {s.geography.routes.length}.</p>
				<h3>Routes</h3>
				<ul class="small">
					{#each s.geography.routes as r (r.id)}
						<li><button class="link" onclick={() => (selected = { what: 'route', id: r.id })}>{name(r.ends[0])} – {name(r.ends[1])}</button> <span class="muted">{r.kind}, {r.days} d{s.layout.routes[r.id]?.cells?.length ? '' : ', not drawn'}</span></li>
					{/each}
				</ul>
				{#if s.geography.places.some((p) => !s!.layout.places[p.id])}
					<h3>Not placed yet</h3>
					<ul class="small">
						{#each s.geography.places.filter((p) => !s!.layout.places[p.id]) as p (p.id)}
							<li><button class="link" onclick={() => { selected = { what: 'place', id: p.id }; tool = 'move'; }}>{name(p.id)}</button></li>
						{/each}
					</ul>
				{/if}
			{/if}
			<h3>Checks</h3>
			{#if findings.length === 0}
				<p class="small"><span class="badge ok">ok</span></p>
			{:else}
				<ul class="findings small">
					{#each findings as f, i (i)}
						<li class={f.severity}>{f.severity}: {f.message}</li>
					{/each}
				</ul>
			{/if}
		</aside>
	</div>
{/if}

<style>
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
		margin-bottom: 0.6rem;
	}
	.toolbar button.active {
		border-color: var(--accent);
		background: var(--surface);
	}
	.sep {
		width: 1rem;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 280px;
		gap: 1rem;
	}
	@media (max-width: 800px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}
	.scroll {
		overflow: auto;
		padding: 0.5rem;
	}
	.map {
		width: 100%;
		min-width: 600px;
		height: auto;
		display: block;
		cursor: crosshair;
		background: var(--surface-2);
	}
	.outline {
		fill: none;
		stroke: var(--border);
		stroke-width: 0.6;
		pointer-events: none;
	}
	.terrain {
		opacity: 0.55;
		pointer-events: none;
	}
	.route {
		fill: none;
		stroke: var(--text);
		stroke-width: 3;
		stroke-linejoin: round;
	}
	.route.track {
		stroke-dasharray: 4 4;
	}
	.route.sea,
	.route.river {
		stroke: var(--pin);
		stroke-dasharray: 8 5;
	}
	.route.vialux {
		stroke: var(--accent);
		stroke-width: 5;
	}
	.route.picked,
	.place.picked {
		stroke: var(--ripple);
		stroke-width: 6;
	}
	.drawing {
		fill: none;
		stroke: var(--ripple);
		stroke-width: 3;
		stroke-dasharray: 2 4;
		pointer-events: none;
	}
	.place {
		fill: var(--surface);
		stroke: var(--accent);
		stroke-width: 3;
	}
	.marker {
		fill: var(--unexplained);
		opacity: 0.7;
		pointer-events: none;
	}
	.label {
		font: 14px var(--serif);
		fill: var(--text);
		text-anchor: middle;
		paint-order: stroke;
		stroke: var(--surface);
		stroke-width: 4px;
		pointer-events: none;
	}
	.side label {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		margin: 0.4rem 0;
		font-size: 0.85rem;
	}
	.side label.check {
		flex-direction: row;
		align-items: center;
	}
	.side button {
		margin: 0.2rem 0.2rem 0 0;
	}
	.danger {
		color: var(--unexplained);
	}
	button.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
	}
	.findings li.error {
		color: var(--unexplained);
	}
	.findings li.warning {
		color: var(--divergent);
	}
	.warn {
		color: var(--unexplained);
	}
	.small {
		font-size: 0.85rem;
	}
	.save {
		font-weight: 600;
	}
</style>
