<script lang="ts">
	import { page } from '$app/state';

	import { finalState } from '$lib/run/entity';
	import { layout, loadGeography, occupancy, type Geography, type Layout, type Traveller } from '$lib/run/geography';
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

	$effect(() => {
		const n = name;
		let stale = false;
		run = geo = null;
		missing = false;
		error = null;
		residents = {};
		travellers = [];
		partial = false;
		const source = new HttpSource();
		Promise.all([openRun(source, n), loadGeography(source, n)])
			.then(async ([r, g]) => {
				if (stale) return;
				run = r;
				geo = g;
				missing = !g;
				partial = r.manifest.meta.complete === false;
				if (g && !partial) {
					const occ = occupancy(await finalState(r), g);
					if (stale) return;
					residents = occ.residents;
					travellers = occ.travellers;
				}
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const pos: Layout = $derived(geo ? layout(geo, W, H) : {});
	const names = $derived(Object.fromEntries((geo?.places ?? []).map((p) => [p.id, p.name ?? p.id])));
	const regions = $derived(Object.fromEntries((geo?.regions ?? []).map((r) => [r.id, r.name ?? r.id])));
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
	<a href={`/run/${encodeURIComponent(name)}/stories`}>stories</a>
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
	{#if !geo.places.every((p) => p.at)}
		<p class="muted small">Laid out by road distance: the file has no map positions, so distances are travel days, not miles.</p>
	{/if}

	<figure class="card map">
		<div class="scroll">
		<svg class="chart" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`Map of ${geo.places.length} places and ${geo.routes.length} routes`}>
			{#each geo.routes as r (r.id)}
				{@const a = pos[r.ends[0]]}
				{@const b = pos[r.ends[1]]}
				{#if a && b}
					<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class={`route ${r.kind}`} class:vialux={r.vialux} class:closed={r.open === false}>
						<title>{names[r.ends[0]]} – {names[r.ends[1]]}: {r.days} days by {r.kind}{r.vialux ? ' (the Vialux)' : ''}</title>
					</line>
					<text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3} class="days">{r.days}</text>
				{/if}
			{/each}
			{#each geo.places as p (p.id)}
				{@const at = pos[p.id]}
				<a href={entity(p.id)} aria-label={names[p.id]}>
					{#if p.kind === 'settlement'}
						<circle cx={at.x} cy={at.y} r={radius(p.id)} class="settlement">
							<title>{names[p.id]} ({regions[p.region] ?? p.region}): {residents[p.id] ?? 0} notables{onRoad[p.id] ? `, ${onRoad[p.id]} on the road` : ''}</title>
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
				<text x={at.x} y={at.y + (p.kind === 'settlement' ? radius(p.id) + 13 : 16)} class:label={true} class:minor={p.kind !== 'settlement'} aria-hidden="true">{names[p.id]}</text>
			{/each}
			{#each travellers as t (t.id)}
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
		</figcaption>
	</figure>

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
</style>
