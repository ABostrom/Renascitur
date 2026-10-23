<script lang="ts">
	import { page } from '$app/state';

	import { layout, loadGeography, type Geography, type Layout } from '$lib/run/geography';
	import { dominant, lineage, loadClaims, type Claim, type Claims } from '$lib/run/knowledge';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	const W = 900;
	const H = 600;
	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let claims = $state<Claims | null>(null);
	let geo = $state<Geography | null>(null);
	let loaded = $state(false);
	let error = $state<string | null>(null);
	let chosen = $state(0); // the topic shown
	let picked = $state<string | null>(null); // a claim whose spread the map shows; none: what each place mostly believes

	$effect(() => {
		const n = name;
		let stale = false;
		run = claims = geo = null;
		loaded = false;
		error = null;
		chosen = 0;
		picked = null;
		const source = new HttpSource();
		Promise.all([openRun(source, n), loadClaims(source, n), loadGeography(source, n)])
			.then(([r, c, g]) => {
				if (stale) return;
				run = r;
				claims = c;
				geo = g;
				loaded = true;
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const topic = $derived(claims?.topics[chosen] ?? null);
	const rows = $derived(topic ? lineage(topic) : []);
	const held = $derived(
		(topic?.claims ?? []).reduce<Record<string, number>>((acc, c) => ((acc[c.truth] = (acc[c.truth] ?? 0) + c.holders), acc), {})
	);
	const told = $derived(topic?.claims.filter((c) => c.truth === 'true') ?? []);
	const pickedClaim = $derived(topic?.claims.find((c) => c.key === picked) ?? null);
	const spread = $derived.by(() => {
		if (!topic) return {} as Record<string, { claim: Claim; share: number }>;
		if (!pickedClaim) return dominant(topic);
		return Object.fromEntries(Object.entries(pickedClaim.shares).map(([p, share]) => [p, { claim: pickedClaim, share }]));
	});
	const pos: Layout = $derived(geo ? layout(geo, W, H) : {});
	const names = $derived(Object.fromEntries((geo?.places ?? []).map((p) => [p.id, p.name ?? p.id])));
	const biggest = $derived(Math.max(0.01, ...Object.values(spread).map((s) => s.share)));

	const cal = $derived(run?.calendar);
	const TRUTH: Record<string, string> = { true: 'true', half: 'half true', false: 'false', unknown: 'unknown' };
	const VERDICTS = ['true', 'half', 'false', 'unknown'];
	const truth = (t: string) => TRUTH[t] ?? t;
	const tone = (t: string) => (t === 'true' ? 'ok' : t === 'false' ? 'warn' : t === 'half' ? 'half' : 'unknown');
	const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
	const pct = (x: number) => `${Math.round(x * 100)}%`;
	const total = (c: Claim) => Object.values(c.shares).reduce((s, x) => s + x, 0);
	const eventHref = (e: string) => `/run/${encodeURIComponent(name)}/events?e=${encodeURIComponent(e)}`;
	const entityHref = (e: string) => `/run/${encodeURIComponent(name)}/entity/${encodeURIComponent(e)}`;
	const aboutHref = $derived(topic ? (topic.about_type === 'person' ? entityHref(topic.about) : eventHref(topic.about)) : '');
	const radius = (share: number) => 5 + 18 * Math.sqrt(share / biggest);
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › knowledge · <a href={`/run/${encodeURIComponent(name)}/events`}>events</a> ·
	<a href={`/run/${encodeURIComponent(name)}/map`}>map</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !loaded}
	<p class="muted">Loading what the world believes…</p>
{:else if !claims}
	<p class="card">No claims report for this run yet: run <code>renasci claims runs/{name}</code> to write one.</p>
{:else if claims.topics.length === 0}
	<p class="card">Nobody in this run believes anything the engine tracks: its world has no beliefs.</p>
{:else if topic}
	<h1>Knowledge</h1>
	<p class="muted">What the world believes, beside what happened. Each claim is judged against the event log.</p>

	<nav class="topics" aria-label="Topics">
		{#each claims.topics as t, i (t.topic)}
			<button class:active={i === chosen} aria-pressed={i === chosen} onclick={() => ((chosen = i), (picked = null))}>
				{t.about_name} <span class="muted small">({t.people})</span>
			</button>
		{/each}
	</nav>

	<h2><a href={aboutHref}>{topic.about_name}</a></h2>
	<div class="side">
		<section class="card">
			<h3>What happened</h3>
			{#if told.length}
				<ul>
					{#each told as c (c.key)}<li>{c.text}</li>{/each}
				</ul>
			{:else}
				<p class="muted">No one ever told it true.</p>
			{/if}
			{#if topic.claims[0].basis.length}
				<p class="small muted">
					The verdict rests on {plural(topic.claims[0].basis.length, 'event')}:
					{#each topic.claims[0].basis as e, i (e)}{i ? ', ' : ''}<a href={eventHref(e)}><code>{e}</code></a>{/each}
				</p>
			{:else}
				<p class="small muted">The event log has nothing to judge it by.</p>
			{/if}
		</section>
		<section class="card">
			<h3>What is believed</h3>
			<p>{plural(topic.people, 'notable')} hold a view of it at the end. Some hold two rival claims; each holding counts here:</p>
			<ul class="tally">
				{#each VERDICTS as t (t)}
					{#if held[t]}<li><span class={`badge ${tone(t)}`}>{truth(t)}</span> {held[t]}</li>{/if}
				{/each}
			</ul>
		</section>
	</div>

	<section class="card">
		<h3>Claims and their lineage</h3>
		<p class="small muted">A retelling can drift: each claim sits under the one it drifted from. Pick one to see where it spread.</p>
		<div class="scroll">
			<table>
				<thead><tr><th>Claim</th><th>Truth</th><th>Holders</th><th>Of the masses</th><th>Lies taken up</th><th>First heard</th></tr></thead>
				<tbody>
					{#each rows as r (r.claim.key)}
						<tr class:picked={r.claim.key === picked}>
							<td style={`padding-left: ${0.5 + 1.25 * r.depth}rem`}>
								{#if r.depth}<span class="muted" aria-hidden="true">↳ </span><span class="sr">drifted from the claim above: </span>{/if}
								<button class="link" aria-pressed={r.claim.key === picked} onclick={() => (picked = picked === r.claim.key ? null : r.claim.key)}>{r.claim.text}</button>
							</td>
							<td><span class={`badge ${tone(r.claim.truth)}`}>{truth(r.claim.truth)}</span></td>
							<td class="num">{r.claim.holders}</td>
							<td class="num">{pct(total(r.claim))}</td>
							<td class="num">{r.claim.lies || ''}</td>
							<td>{cal && r.claim.first ? cal.format(r.claim.first, 'season') : '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	<section class="card">
		<h3>{pickedClaim ? `Where “${pickedClaim.text}” is believed` : 'What each place mostly believes'}</h3>
		{#if !geo}
			<p class="muted">This run's world has no geography to draw.</p>
		{:else}
			<div class="scroll">
				<svg class="chart" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Spread map">
					{#each geo.routes as r (r.id)}
						{@const a = pos[r.ends[0]]}
						{@const b = pos[r.ends[1]]}
						{#if a && b}<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class="route" class:vialux={r.vialux} />{/if}
					{/each}
					{#each geo.places.filter((p) => p.kind !== 'settlement') as p (p.id)}
						{@const at = pos[p.id]}
						<circle cx={at.x} cy={at.y} r="2.5" class="minor"><title>{names[p.id]} ({p.kind})</title></circle>
					{/each}
					{#each geo.places.filter((p) => p.kind === 'settlement') as p (p.id)}
						{@const at = pos[p.id]}
						{@const s = spread[p.id]}
						<circle cx={at.x} cy={at.y} r={s ? radius(s.share) : 4} class={s ? `held ${tone(s.claim.truth)}` : 'none'}>
							<title>{names[p.id]}: {s ? `${s.claim.text} (${truth(s.claim.truth)}), ${pct(s.share)} of the masses` : 'nobody here speaks of it'}</title>
						</circle>
						<text x={at.x} y={at.y + (s ? radius(s.share) : 4) + 13} class="label" aria-hidden="true">{names[p.id]}</text>
					{/each}
				</svg>
			</div>
			<p class="legend small">
				<span><span class="dot ok"></span> true</span>
				<span><span class="dot half"></span> half true</span>
				<span><span class="dot warn"></span> false</span>
				<span><span class="dot unknown"></span> unknown</span>
				<span><span class="dot none"></span> not spoken of</span>
				<span>size: share of the masses</span>
			</p>
			<details>
				<summary class="small">As a table</summary>
				<table>
					<thead><tr><th>Place</th><th>Claim</th><th>Truth</th><th>Of the masses</th></tr></thead>
					<tbody>
						{#each Object.entries(spread).sort((a, b) => b[1].share - a[1].share) as [p, s] (p)}
							<tr><td><a href={entityHref(p)}>{names[p] ?? p}</a></td><td>{s.claim.text}</td><td>{truth(s.claim.truth)}</td><td class="num">{pct(s.share)}</td></tr>
						{/each}
					</tbody>
				</table>
			</details>
		{/if}
	</section>
{/if}

<style>
	.topics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 1rem;
	}
	.topics button.active {
		border-color: var(--accent);
		background: var(--surface);
	}
	.side {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 1rem;
		margin-bottom: 1rem;
	}
	.tally {
		list-style: none;
		padding: 0;
		display: flex;
		gap: 1rem;
	}
	.badge.half {
		color: var(--divergent);
	}
	button.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-align: left;
		text-decoration: underline;
	}
	tr.picked {
		background: var(--surface-2);
	}
	th {
		text-align: left;
	}
	th,
	td {
		padding: 0.2rem 0.6rem;
	}
	.minor {
		fill: var(--border);
		stroke: none;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.scroll {
		overflow-x: auto;
	}
	.chart {
		width: 100%;
		min-width: 640px;
		height: auto;
		display: block;
		overflow: visible;
	}
	.route {
		stroke: var(--border);
		stroke-width: 1.5;
	}
	.route.vialux {
		stroke: var(--muted);
		stroke-width: 3;
	}
	circle {
		stroke: var(--surface);
		stroke-width: 2;
	}
	.held.ok,
	.dot.ok {
		fill: var(--ok);
		background: var(--ok);
	}
	.held.half,
	.dot.half {
		fill: var(--divergent);
		background: var(--divergent);
	}
	.held.warn,
	.dot.warn {
		fill: var(--unexplained);
		background: var(--unexplained);
	}
	.badge.unknown {
		color: var(--muted);
	}
	.held.unknown,
	.dot.unknown {
		fill: var(--muted);
		background: var(--muted);
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	.none,
	.dot.none {
		fill: var(--surface-2);
		background: var(--surface-2);
		stroke: var(--muted);
	}
	.label {
		font: 12px var(--serif);
		fill: var(--text);
		text-anchor: middle;
		paint-order: stroke;
		stroke: var(--surface);
		stroke-width: 3px;
		stroke-linejoin: round;
		pointer-events: none;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
		color: var(--muted);
	}
	.legend > span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		border: 1px solid var(--muted);
	}
	.small {
		font-size: 0.85rem;
	}
</style>
