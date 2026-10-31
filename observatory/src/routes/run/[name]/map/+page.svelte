<script lang="ts">
	import { page } from '$app/state';

	import { finalState } from '$lib/run/entity';
	import {
		geographyAt,
		layout,
		loadGeography,
		loadMapDeltas,
		mapChanges,
		occupancy,
		type Geography,
		type Layout,
		type MapChange,
		type MapDelta,
		type Traveller
	} from '$lib/run/geography';
	import { borders, colours } from '$lib/run/polities';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	const W = 900;
	const H = 600;
	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let geo = $state<Geography | null>(null);
	let missing = $state(false);
	let error = $state<string | null>(null);
	let residents = $state<Record<string, number>>({});
	let travellers = $state<Traveller[]>([]);
	let partial = $state(false); // an unfinished run has no final state: no residents, no travellers
	let deltas = $state<MapDelta[]>([]);
	let step = $state<number | null>(null); // which moment the map shows (null: the end)
	let polityNames = $state<Record<string, string>>({});

	$effect(() => {
		const n = name;
		let stale = false;
		run = geo = null;
		missing = false;
		error = null;
		residents = {};
		travellers = [];
		partial = false;
		deltas = [];
		step = null;
		polityNames = {};
		const source = new HttpSource();
		Promise.all([openRun(source, n), loadGeography(source, n)])
			.then(async ([r, g]) => {
				if (stale) return;
				run = r;
				geo = g;
				missing = !g;
				partial = r.manifest.meta.complete === false;
				const held = (g?.places ?? []).some((p) => p.control !== undefined); // (a world with polities, S8)
				if (g && (g.changes?.length || held)) {
					// (only a run whose map changes: it reads every state change once)
					const ds = await loadMapDeltas(r, g);
					if (stale) return;
					deltas = ds;
				}
				if (g && !partial) {
					const state = await finalState(r);
					const occ = occupancy(state, g);
					if (stale) return;
					// (the polities' names, from the final state: an unfinished run shows their ids)
					polityNames = Object.fromEntries(
						state.entities.filter((e: { kind: string }) => e.kind === 'polity').map((e: { id: string; fields: { name?: string } }) => [e.id, e.fields.name ?? e.id])
					);
					residents = occ.residents;
					travellers = occ.travellers;
				}
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const cal = $derived(run?.calendar);
	const key = (d: [number, number, number]) => cal!.sortKey(d);
	const changes = $derived(geo ? mapChanges(geo, deltas) : []);
	// The moments the map can be shown at: the start, then each change; the last is the end of the run.
	// One moment per day something changed (the map is as of the end of that day).
	const moments = $derived([
		null,
		...[...new Map(changes.map((c) => [key(c.date), c.date])).values()]
	] as ([number, number, number] | null)[]);
	const momentOf = (d: [number, number, number]) => moments.findIndex((m) => m !== null && key(m) === key(d));
	const at = $derived(step === null ? moments.length - 1 : Math.min(step, moments.length - 1));
	const atEnd = $derived(at === moments.length - 1);
	const shown = $derived(
		geo && cal ? (moments[at] === null ? geographyAt(geo, [], 0, key) : geographyAt(geo, deltas, key(moments[at]!), key)) : null
	);
	// Laid out once, from the map with every road the run ever had, so places don't jump between years.
	const everything = $derived(geo && cal && deltas.length ? geographyAt(geo, deltas, Infinity, key) : geo);
	const pos: Layout = $derived(everything ? layout(everything, W, H) : {});
	const when = (i: number) => (moments[i] === null ? 'the start' : cal ? cal.format(moments[i]!, 'season') : '');
	const eventHref = (e: string) => `/run/${encodeURIComponent(name)}/events?e=${encodeURIComponent(e)}`;
	function site(id: string): string {
		const r = everything?.routes.find((x) => x.id === id);
		return r ? `the ${r.kind} from ${names[r.ends[0]] ?? r.ends[0]} to ${names[r.ends[1]] ?? r.ends[1]}` : (names[id] ?? id);
	}
	function describe(c: MapChange): string {
		const r = everything?.routes.find((x) => x.id === c.site);
		if (c.what === 'built' && r) return `${site(c.site)} built (${r.days} days)`;
		if (c.what === 'moved') return `${site(c.site)} moved into ${regions[c.detail.slice(5)] ?? c.detail.slice(5)}`;
		if (c.what === 'opened') return `${site(c.site)} reopened${c.detail ? `, now ${c.detail}` : ''}`;
		if (c.what === 'taken') {
			const by = c.detail.replace(/^held by /, '');
			return `${site(c.site)} ${by === 'nobody' ? 'held by nobody' : `taken by ${polityName(by)}`}`;
		}
		return `${site(c.site)} ${WHAT[c.what]}${c.what === 'days' ? ` ${c.detail}` : ''}`;
	}
	const WHAT: Record<string, string> = {
		built: 'built',
		closed: 'closed',
		opened: 'reopened',
		days: 'now takes',
		moved: 'moved',
		changed: 'changed'
	};
	const names = $derived(Object.fromEntries((geo?.places ?? []).map((p) => [p.id, p.name ?? p.id])));
	// Who holds what (S8 §10): a colour per polity that ever held a place in the run, borders on the routes between.
	const holders = $derived(
		[
			...new Set([
				...(geo?.places ?? []).map((p) => p.control),
				...deltas.filter((d) => d.field === 'control').map((d) => d.new as string | null)
			])
		]
			.filter((c): c is string => !!c)
			.sort()
	);
	const tint = $derived(colours(holders));
	const controlOf = $derived(Object.fromEntries((shown?.places ?? []).map((p) => [p.id, p.control ?? null])));
	const border = $derived(shown ? borders(shown) : new Set<string>());
	const polityName = (id: string) => polityNames[id] ?? id;
	const regions = $derived(Object.fromEntries((geo?.regions ?? []).map((r) => [r.id, r.name ?? r.id])));
	const regionOf = $derived(Object.fromEntries((shown?.places ?? []).map((p) => [p.id, p.region])));
	const biggest = $derived(Math.max(1, ...Object.values(residents)));
	const onRoad = $derived(
		travellers.reduce<Record<string, number>>((acc, t) => ((acc[t.from] = (acc[t.from] ?? 0) + 1), acc), {})
	);

	function radius(id: string): number {
		return 6 + 14 * Math.sqrt((residents[id] ?? 0) / biggest);
	}

	function entity(id: string): string {
		return `/run/${encodeURIComponent(name)}/entity/${encodeURIComponent(id)}`;
	}
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › map · <a href={`/run/${encodeURIComponent(name)}/events`}>events</a> ·
	<a href={`/run/${encodeURIComponent(name)}/stories`}>stories</a> ·
	<a href={`/run/${encodeURIComponent(name)}/polities`}>polities</a> ·
	<a href={`/run/${encodeURIComponent(name)}/objects`}>objects</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if missing}
	<p class="card">This run's world has no geography (no <code>geography.json</code> in its folder).</p>
{:else if !geo}
	<p class="muted">Loading the map…</p>
{:else}
	<h1>Map</h1>
	{#if geo.draft}<p class="muted">{geo.about ?? 'A draft geography.'}</p>{/if}
	{#if changes.length}
		<label class="asof">
			As of
			<input type="range" min="0" max={moments.length - 1} value={at} aria-label="As of" aria-valuetext={when(at)}
				oninput={(e) => (step = +e.currentTarget.value)} />
			<span class="mono">{when(at)}</span>
			<span class="muted small">({changes.length} change{changes.length === 1 ? '' : 's'} to the map in this run)</span>
		</label>
	{/if}
	{#if !geo.places.every((p) => p.at)}
		<p class="muted small">Laid out by road distance: the file has no map positions, so distances are travel days, not miles.</p>
	{/if}

	<figure class="card map">
		<div class="scroll">
		<svg class="chart" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Map of ${geo.places.length} places and ${shown!.routes.length} routes`}>
			{#each shown!.routes as r (r.id)}
				{@const a = pos[r.ends[0]]}
				{@const b = pos[r.ends[1]]}
				{#if a && b}
					{#if border.has(r.id)}
						<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class="border" aria-hidden="true" />
					{/if}
					<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class={`route ${r.kind}`} class:vialux={r.vialux} class:closed={r.open === false}>
						<title>{names[r.ends[0]]} – {names[r.ends[1]]}: {r.days} days by {r.kind}{r.vialux ? ' (the Vialux)' : ''}{r.open === false ? ', closed' : ''}{border.has(r.id) ? ' (a border)' : ''}</title>
					</line>
					<text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3} class="days">{r.days}</text>
				{/if}
			{/each}
			{#each geo.places as p (p.id)}
				{@const at = pos[p.id]}
				<a href={entity(p.id)} aria-label={names[p.id]}>
					{#if p.kind === 'settlement'}
						<circle cx={at.x} cy={at.y} r={atEnd ? radius(p.id) : 8} class="settlement" style:fill={controlOf[p.id] ? tint[controlOf[p.id]!] : null}>
							<title>{names[p.id]} ({regions[regionOf[p.id]] ?? regionOf[p.id]}){controlOf[p.id] ? `, held by ${polityName(controlOf[p.id]!)}` : ''}{atEnd ? `: ${residents[p.id] ?? 0} notables${onRoad[p.id] ? `, ${onRoad[p.id]} on the road` : ''}` : ''}</title>
						</circle>
					{:else}
						<rect x={at.x - 4} y={at.y - 4} width="8" height="8" class={`place ${p.kind}`} transform={`rotate(45 ${at.x} ${at.y})`}>
							<title>{names[p.id]}: {p.kind} ({regions[p.region] ?? p.region})</title>
						</rect>
					{/if}
				</a>
			{/each}
			{#each geo.places as p (p.id)}
				{@const at = pos[p.id]}
				<text x={at.x} y={at.y + (p.kind === 'settlement' ? (atEnd ? radius(p.id) : 8) + 13 : 16)} class:label={true} class:minor={p.kind !== 'settlement'} aria-hidden="true">{names[p.id]}</text>
			{/each}
			{#each atEnd ? travellers : [] as t (t.id)}
				{@const a = pos[t.from]}
				{@const b = pos[t.next]}
				{#if a && b}
					<circle cx={a.x + (b.x - a.x) * 0.35} cy={a.y + (b.y - a.y) * 0.35} r="3.5" class="traveller">
						<title>{t.name}: on the road from {names[t.from]} to {names[t.to]} ({t.why})</title>
					</circle>
				{/if}
			{/each}
		</svg>
		</div>
		<figcaption class="legend small">
			<span><svg width="18" height="10" aria-hidden="true"><line x1="0" y1="5" x2="18" y2="5" class="route road" /></svg> road</span>
			<span><svg width="18" height="10" aria-hidden="true"><line x1="0" y1="5" x2="18" y2="5" class="route vialux" /></svg> the Vialux</span>
			<span><svg width="18" height="10" aria-hidden="true"><line x1="0" y1="5" x2="18" y2="5" class="route sea" /></svg> sea or river</span>
			<span><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="5" class="settlement" /></svg> settlement (size: notables)</span>
			<span><svg width="12" height="12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" class="place" /></svg> other place</span>
			<span><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="3.5" class="traveller" /></svg> on the road</span>
			{#if holders.length}
				<span><svg width="18" height="10" aria-hidden="true"><line x1="0" y1="5" x2="18" y2="5" class="border" /></svg> border</span>
				{#each holders as h (h)}
					<span><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="5" class="settlement" style:fill={tint[h]} /></svg> {polityName(h)}</span>
				{/each}
			{/if}
		</figcaption>
	</figure>

	{#if changes.length}
		<section class="card">
			<h2>Changes to the map</h2>
			<div class="scroll">
				<table>
					<thead><tr><th>When</th><th>What</th><th></th></tr></thead>
					<tbody>
						{#each changes as c, i (c.event)}
							<tr class:current={momentOf(c.date) === at}>
								<td><button class="link" onclick={() => (step = momentOf(c.date))}>{cal ? cal.format(c.date, 'season') : ''}</button></td>
								<td>{describe(c)}</td>
								<td><a href={eventHref(c.event)}>why</a></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}

	<section class="card">
		<h2>On the road at the end</h2>
		{#if partial}
			<p class="muted">The run hasn't finished, so there is no final state yet: no residents or travellers to show.</p>
		{:else if travellers.length === 0}
			<p class="muted">Nobody: every journey had arrived when the run ended.</p>
		{:else}
			<div class="scroll">
			<table>
				<thead><tr><th>Who</th><th>From</th><th>To</th><th>Why</th></tr></thead>
				<tbody>
					{#each travellers as t (t.id)}
						<tr><td><a href={entity(t.id)}>{t.name}</a></td><td>{names[t.from]}</td><td>{names[t.to]}</td><td>{t.why}</td></tr>
					{/each}
				</tbody>
			</table>
			</div>
		{/if}
	</section>
{/if}

<style>
	.scroll {
		overflow-x: auto;
	}
	.chart {
		width: 100%;
		min-width: 640px; /* below this the labels are too small to read: scroll instead */
		height: auto;
		display: block;
		overflow: visible;
	}
	.route {
		stroke: var(--muted);
		stroke-width: 1.5;
	}
	.route.track {
		stroke-dasharray: 2 3;
	}
	.route.sea,
	.route.river {
		stroke: var(--pin);
		stroke-dasharray: 6 4;
	}
	.route.pass {
		stroke-dasharray: 8 3 2 3;
	}
	.route.vialux {
		stroke: var(--accent);
		stroke-width: 3.5;
		stroke-dasharray: none;
	}
	.route.closed {
		opacity: 0.3;
	}
	.border {
		stroke: var(--text);
		stroke-width: 7;
		stroke-opacity: 0.18;
		stroke-linecap: round;
	}
	.days {
		font: 10px var(--sans);
		fill: var(--muted);
		text-anchor: middle;
	}
	.settlement {
		fill: var(--surface-2);
		stroke: var(--accent);
		stroke-width: 2;
	}
	.place {
		fill: var(--surface);
		stroke: var(--muted);
		stroke-width: 1.5;
	}
	.traveller {
		fill: var(--ripple);
	}
	.label {
		font: 12px var(--serif);
		fill: var(--text);
		text-anchor: middle;
		paint-order: stroke; /* a halo of the page colour, so routes don't cut through names */
		stroke: var(--surface);
		stroke-width: 3px;
		stroke-linejoin: round;
		pointer-events: none;
	}
	.label.minor {
		font-size: 10px;
		fill: var(--muted);
	}
	a:hover .settlement,
	a:hover .place {
		stroke: var(--text);
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
		margin-top: 0.5rem;
		color: var(--muted);
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.asof {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
		margin: 0.5rem 0;
	}
	button.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
	}
	tr.current {
		background: var(--surface-2);
	}
</style>
