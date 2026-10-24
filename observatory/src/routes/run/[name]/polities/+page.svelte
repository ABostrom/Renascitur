<script lang="ts">
	import { page } from '$app/state';

	import type { DateTuple } from '$lib/run/calendar';
	import { loadPolities, wars as warsOf, type PolityEvent, type Relation, type War } from '$lib/run/polities';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	/** Polities, their wars and their relations over time (S8 spec §10, #159). */
	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let events = $state.raw<PolityEvent[]>([]);
	let relations = $state.raw<Record<string, Relation>>({});
	let ended = $state.raw<Record<string, DateTuple>>({});
	let names = $state.raw<Record<string, string>>({});
	let error = $state<string | null>(null);

	$effect(() => {
		const n = name;
		let stale = false;
		run = null;
		events = [];
		relations = {};
		ended = {};
		names = {};
		error = null;
		(async () => {
			const r = await openRun(new HttpSource(), n);
			const got = await loadPolities(r);
			if (stale) return;
			run = r;
			events = got.events;
			relations = got.relations;
			ended = got.ended;
			names = got.names;
		})().catch((e) => {
			if (!stale) error = (e as Error).message;
		});
		return () => (stale = true);
	});

	const cal = $derived(run?.calendar);
	const when = (d: [number, number, number]) => (cal ? cal.format(d, 'season') : '');
	const nameOf = (id: string) => names[id] ?? id;
	const wars: War[] = $derived(warsOf(events, ended));
	const rels = $derived(Object.values(relations).filter((r) => r.points.length).sort((a, b) => a.id.localeCompare(b.id)));
	const href = (kind: 'events' | 'entity', id: string) =>
		kind === 'events'
			? `/run/${encodeURIComponent(name)}/events?e=${encodeURIComponent(id)}`
			: `/run/${encodeURIComponent(name)}/entity/${encodeURIComponent(id)}`;
	const treaties = $derived(events.filter((e) => e.type === 'polity.treaty' || e.type === 'polity.treaty_ended' || e.type === 'polity.treaty_broken'));
	const TREATY: Record<string, string> = { 'polity.treaty': 'signed', 'polity.treaty_ended': 'ended', 'polity.treaty_broken': 'broken' };

	// A relation's trust, -1..1, as a strip: one axis, a zero line, hover a point for its date and stance.
	const SW = 320;
	const SH = 48;
	// Every row on the run's time axis (from the earliest point of any relation to the latest), so rows line up.
	const span = $derived.by(() => {
		const keys = rels.flatMap((r) => r.points.map((p) => (cal ? cal.sortKey(p.date) : 0)));
		return keys.length ? [Math.min(...keys), Math.max(...keys)] : [0, 0];
	});
	function strip(r: Relation) {
		const pts = r.points.filter((p) => p.trust !== null);
		const keys = pts.map((p) => cal!.sortKey(p.date));
		const [lo, hi] = span;
		const x = (k: number) => 6 + (hi === lo ? 0 : ((k - lo) / (hi - lo)) * (SW - 12));
		const y = (t: number) => SH / 2 - (t * (SH - 8)) / 2;
		return pts.map((p, i) => ({ x: x(keys[i]), y: y(p.trust!), p }));
	}
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › polities · <a href={`/run/${encodeURIComponent(name)}/map`}>map</a> ·
	<a href={`/run/${encodeURIComponent(name)}/events`}>events</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !run}
	<p class="muted">Loading polities…</p>
{:else if !events.length && !rels.length}
	<h1>Polities</h1>
	<p class="card">This run has no polities (a world without them, or one where nothing passed between them).</p>
{:else}
	<h1>Polities</h1>

	<section class="card">
		<h2>Wars ({wars.length})</h2>
		{#if !wars.length}
			<p class="muted">No war was declared in this run.</p>
		{/if}
		{#each wars as w (w.id)}
			<article class="war">
				<h3>
					<a href={href('entity', w.aggressor)}>{nameOf(w.aggressor)}</a> against
					<a href={href('entity', w.defender)}>{nameOf(w.defender)}</a>
					<span class="muted small">
						({when(w.date)}–{w.end ? when(w.end.date) : 'still at war at the end'})
					</span>
				</h3>
				<ol class="timeline">
					<li><span class="mono">{when(w.date)}</span> declared · <a href={href('events', w.event)}>why</a></li>
					{#each w.joined as j (j.event)}
						<li><span class="mono">{when(j.date)}</span> {nameOf(j.ally)} joins {nameOf(j.side)}'s side · <a href={href('events', j.event)}>why</a></li>
					{/each}
					{#each w.years as y (y.event)}
						<li>
							<span class="mono">{when(y.date)}</span> {nameOf(y.winner)} has the better of {nameOf(y.loser)}{#if y.place}, taking
								<a href={href('entity', y.place)}>{nameOf(y.place)}</a>{/if} · <a href={href('events', y.event)}>why</a>
						</li>
					{/each}
					{#each w.falls as f (f.event)}
						<li><span class="mono">{when(f.date)}</span> {nameOf(f.polity)}, an ally, falls to {nameOf(f.victor)} · <a href={href('events', f.event)}>why</a></li>
					{/each}
					{#if w.end}
						<li class="end">
							<span class="mono">{when(w.end.date)}</span>
							{#if w.end.how === 'peace'}peace: {nameOf(w.end.loser ?? '')} yields to {nameOf(w.end.winner ?? '')}
							{:else if w.end.how === 'fallen'}{nameOf(w.end.loser ?? '')} falls to {nameOf(w.end.winner ?? '')}
							{:else}over: a side that led it fell in another war{/if}
							{#if w.end.event}· <a href={href('events', w.end.event)}>why</a>{/if}
						</li>
					{/if}
				</ol>
				<p class="small"><a href={href('entity', w.id)}>the war's record</a> (its state and claims)</p>
			</article>
		{/each}
	</section>

	<section class="card">
		<h2>Relations ({rels.length})</h2>
		<p class="muted small">Trust from −1 to 1 over the run (the line through the middle is 0); hover a point for its date and stance.</p>
		<div class="scroll">
			<table>
				<thead><tr><th>Between</th><th>Stance at the end</th><th class="num">Trust</th><th>Trust over time</th></tr></thead>
				<tbody>
					{#each rels as r (r.id)}
						{@const last = r.points.at(-1)!}
						<tr>
							<td><a href={href('entity', r.a)}>{nameOf(r.a)}</a> and <a href={href('entity', r.b)}>{nameOf(r.b)}</a></td>
							<td><span class={`stance ${last.stance ?? ''}`}>{last.stance ?? '—'}</span></td>
							<td class="num mono">{last.trust === null ? '—' : last.trust.toFixed(2)}</td>
							<td>
								{#if cal}
									{@const pts = strip(r)}
									<svg width={SW} height={SH} viewBox={`0 0 ${SW} ${SH}`} role="img" aria-label={`Trust between ${nameOf(r.a)} and ${nameOf(r.b)} over time`}>
										<line x1="0" x2={SW} y1={SH / 2} y2={SH / 2} class="zero" />
										<polyline points={pts.map((q) => `${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(' ')} class="trust" />
										{#each pts as q, i (i)}
											<circle cx={q.x} cy={q.y} r="5" class="hit"><title>{when(q.p.date)}: {q.p.stance ?? 'no stance'}, trust {q.p.trust!.toFixed(2)}</title></circle>
										{/each}
									</svg>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	{#if treaties.length}
		<section class="card">
			<h2>Treaties</h2>
			<div class="scroll">
				<table>
					<thead><tr><th>When</th><th>Between</th><th>What</th><th></th></tr></thead>
					<tbody>
						{#each treaties as t (t.id)}
							<tr>
								<td class="mono">{when(t.date)}</td>
								<td>{(t.roles.party ?? []).map(nameOf).join(' and ')}</td>
								<td>{String(t.payload.kind ?? 'treaty')} {TREATY[t.type]}{t.type === 'polity.treaty_broken' ? ` by ${nameOf(t.roles.by?.[0] ?? '')}` : ''}</td>
								<td><a href={href('events', t.id)}>why</a></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
{/if}

<style>
	.scroll {
		overflow-x: auto;
	}
	.small {
		font-size: 0.85rem;
	}
	.war + .war {
		border-top: 1px solid var(--border);
		margin-top: 1rem;
		padding-top: 0.5rem;
	}
	.timeline {
		list-style: none;
		padding-left: 0;
		margin: 0.25rem 0;
	}
	.timeline li {
		padding: 0.15rem 0 0.15rem 0.75rem;
		border-left: 2px solid var(--border);
	}
	.timeline li.end {
		border-left-color: var(--accent);
	}
	.zero {
		stroke: var(--border);
		stroke-width: 1;
	}
	.trust {
		fill: none;
		stroke: var(--accent);
		stroke-width: 2;
	}
	.hit {
		fill: transparent;
	}
	.hit:hover {
		fill: var(--accent);
	}
	.stance.war,
	.stance.hostile {
		color: var(--unexplained);
	}
	.stance.friendly,
	.stance.allied {
		color: var(--ok);
	}
</style>
