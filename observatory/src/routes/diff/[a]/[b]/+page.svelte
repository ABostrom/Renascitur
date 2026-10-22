<script lang="ts">
	import { page } from '$app/state';

	import { loadDivergence, rootEvents, type Divergence, type Side, type YearKey } from '$lib/run/diff';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';
	import WaveHeatmap from '$lib/ui/WaveHeatmap.svelte';

	const a = $derived(page.params.a ?? '');
	const b = $derived(page.params.b ?? '');
	let variant = $state<Run | null>(null);
	let divergence = $state<Divergence | null>(null);
	let missing = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const [baseline, v] = [a, b];
		let stale = false;
		variant = divergence = null;
		missing = false;
		error = null;
		const source = new HttpSource();
		Promise.all([openRun(source, v), loadDivergence(source, v)])
			.then(([run, d]) => {
				if (stale) return;
				variant = run;
				// The report in the variant's folder is for one baseline; any other pair hasn't been diffed.
				if (!d || d.runs?.baseline !== baseline) missing = true;
				else divergence = d;
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const roots = $derived(divergence ? rootEvents(divergence) : new Set<string>());
	const runOf = (side: Side) => (side === 'baseline' ? a : b); // "both": shown in the variant
	const enc = encodeURIComponent;
	const eventHref = (id: string, side: Side) => `/run/${enc(runOf(side))}/events?e=${enc(id)}`;
	const entityHref = (id: string, side: Side) => `/run/${enc(runOf(side))}/entity/${enc(id)}`;
	function cellHref(place: string | null, [age, year]: YearKey) {
		const cal = variant!.calendar;
		const p = new URLSearchParams({ diff: b, from: cal.format([age, year, 0], 'year'), to: cal.format([age, year, 0], 'year') });
		if (place) p.set('place', place);
		return `/run/${enc(b)}/events?${p}`;
	}
	// Roots first: where the bug first showed, then what followed from it.
	const unexplainedEvents = $derived(
		divergence ? [...divergence.unexplained.events].sort((x, y) => Number(roots.has(y.id)) - Number(roots.has(x.id))) : []
	);
</script>

<p class="crumbs"><a href="/">Runs</a> › diff › <span class="mono">{a}</span> → <span class="mono">{b}</span></p>

{#if error}
	<p class="card">{error}</p>
{:else if missing}
	<p class="card">
		No diff of <strong>{b}</strong> against <strong>{a}</strong> yet. Make one with
		<code>uv run renasci diff runs/{a} runs/{b}</code>, then reload.
	</p>
{:else if !divergence || !variant}
	<p class="muted">Loading the diff…</p>
{:else}
	{@const d = divergence}
	{@const clean = d.unexplained_events + d.unexplained_entities + d.unexplained_cells === 0}
	<section class="counts">
		<div class="card stat">
			<span class="n">{d.divergent_events.toLocaleString()}</span>
			<span class="muted">of {d.events.toLocaleString()} events diverge</span>
		</div>
		<div class="card stat">
			<span class="n">{d.divergent_entities}</span><span class="muted">entities · </span>
			<span class="n">{d.divergent_cells}</span><span class="muted">column cells differ</span>
		</div>
		<div class={`card stat ${clean ? 'ok' : 'bad'}`}>
			{#if clean}
				<span class="n">0</span><span class="muted">unexplained: every difference traces to a ripple</span>
			{:else}
				<span class="n">{d.unexplained_events + d.unexplained_entities + d.unexplained_cells}</span>
				<span>unexplained: the code depended on something it didn't read through the engine</span>
			{/if}
		</div>
	</section>

	<section class="card">
		<h2>Causal wave</h2>
		<p class="muted">Divergent events by where they happened and when. Click a cell to see its divergent events in {b}.</p>
		<WaveHeatmap divergence={d} calendar={variant.calendar} href={cellHref} />
	</section>

	{#if !clean}
		<section class="card unexplained">
			<h2>Unexplained</h2>
			{#if unexplainedEvents.length}
				<h3>Events ({unexplainedEvents.length})</h3>
				<ul>
					{#each unexplainedEvents as e (e.id)}
						<li>
							{#if roots.has(e.id)}<span class="badge bad">root</span>{/if}
							<a class="mono" href={eventHref(e.id, e.side)}>{e.type}</a>
							<span class="mono muted">{variant.calendar.format(e.date, 'day')}</span>
							<span class="muted">in {runOf(e.side)}{e.side === 'both' ? ' (and changed)' : ' only'}</span>
							<span class="muted">· {Object.entries(e.roles).map(([r, m]) => `${r}: ${m.join(', ')}`).join(' · ')}</span>
						</li>
					{/each}
				</ul>
			{/if}
			{#if d.unexplained.entities.length}
				<h3>Entities ({d.unexplained.entities.length})</h3>
				<ul>
					{#each d.unexplained.entities as e (e.id)}
						<li><a class="mono" href={entityHref(e.id, e.side)}>{e.id}</a> <span class="muted">{e.side}</span></li>
					{/each}
				</ul>
			{/if}
			{#if d.unexplained.cells.length}
				<h3>Column cells ({d.unexplained.cells.length})</h3>
				<ul>
					{#each d.unexplained.cells as c (`${c.id}|${c.column}`)}
						<li><a class="mono" href={entityHref(c.id, c.side)}>{c.id}</a> <span class="mono muted">{c.column}</span></li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}

	{#if d.tainted_scope_names.length}
		<p class="muted">Scopes that saw different inputs: <span class="mono">{d.tainted_scope_names.join(', ')}</span></p>
	{/if}
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	.counts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: 0.8rem;
		margin-bottom: 1rem;
	}
	.stat {
		display: flex;
		gap: 0.4rem;
		align-items: baseline;
		flex-wrap: wrap;
	}
	.n {
		font-family: var(--serif);
		font-size: 1.6rem;
		font-weight: 600;
	}
	.stat.bad {
		border-color: var(--unexplained);
		color: var(--unexplained);
	}
	section.card {
		margin-bottom: 1rem;
	}
	h2 {
		font-size: 1.05rem;
		margin-top: 0;
	}
	h3 {
		font-size: 0.95rem;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	li {
		padding: 0.2rem 0;
		border-bottom: 1px solid var(--border);
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		align-items: baseline;
	}
	.badge.bad {
		color: var(--unexplained);
		border-color: var(--unexplained);
	}
	.muted {
		color: var(--muted);
	}
</style>
