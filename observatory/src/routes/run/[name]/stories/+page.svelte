<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import type { Run } from '$lib/run/run';
	import { glyph, inPeriod, presets, runYears, type Stories } from '$lib/run/stories';
	import { loadRunStories } from '$lib/runs';
	import StoryRiver from '$lib/ui/StoryRiver.svelte';

	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let stories = $state<Stories | null>(null);
	let missing = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const n = name;
		let stale = false;
		run = stories = null;
		missing = false;
		error = null;
		loadRunStories(n)
			.then((r) => {
				if (stale) return;
				run = r.run;
				stories = r.stories;
				missing = !r.stories;
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	// The period lives in the URL (?from=&to=, years of the run's age), so views can be bookmarked.
	const years = $derived(stories ? runYears(stories) : ([0, 0] as [number, number]));
	const params = $derived(page.url.searchParams);
	// A missing or unreadable bound is the run's own; reversed bounds are swapped.
	const bounds = $derived.by(() => {
		const a = year(params.get('from'), years[0]);
		const b = year(params.get('to'), years[1]);
		return a <= b ? [a, b] : [b, a];
	});
	const from = $derived(bounds[0]);
	const to = $derived(bounds[1]);
	function year(text: string | null, fallback: number) {
		const y = text === null || text.trim() === '' ? NaN : Number(text);
		return Number.isFinite(y) ? Math.min(Math.max(Math.round(y), years[0]), years[1]) : fallback;
	}
	function setPeriod(a: number, b: number) {
		const p = new URLSearchParams(page.url.searchParams.toString());
		p.set('from', String(Math.min(a, b)));
		p.set('to', String(Math.max(a, b)));
		goto(`?${p}`, { replace: true, reset: false });
	}

	const choices = $derived(stories ? presets(years[0], years[1]) : []);
	const chosen = $derived(choices.findIndex((c) => c.from === from && c.to === to));
	const flowing = $derived(stories ? inPeriod(stories, from, to) : { arcs: [], sagas: [] });
	const age = $derived(stories?.arcs[0]?.timeline[0]?.date[0] ?? 1);
	const label = (y: number) => (run ? run.calendar.format([age, y, 0], 'year') : String(y));

	const enc = encodeURIComponent;
	const arcHref = (amb: string) => `/run/${enc(name)}/stories/arc/${enc(amb)}`;
	const sagaHref = (id: string) => `/run/${enc(name)}/stories/saga/${enc(id)}`;
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> › stories ·
	<a href={`/run/${enc(name)}/latch`}>latch points</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if missing}
	<p class="card">
		No stories for <strong>{name}</strong> yet. Find them with <code>uv run renasci stories runs/{name}</code>, then
		reload.
	</p>
{:else if !stories || !run}
	<p class="muted">Loading stories…</p>
{:else}
	<div class="card period">
		<label
			>Period
			<select
				value={chosen}
				onchange={(e) => {
					const c = choices[Number(e.currentTarget.value)];
					if (c) setPeriod(c.from, c.to);
				}}
			>
				{#if chosen === -1}<option value={-1}>Custom</option>{/if}
				{#each choices as c, i (c.label)}<option value={i}>{c.label}</option>{/each}
			</select>
		</label>
		<label
			>From <input type="number" min={years[0]} max={years[1]} value={from}
				onchange={(e) => {
					const y = year(e.currentTarget.value, from);
					e.currentTarget.value = String(y); // (shows what is used, not what was typed)
					setPeriod(y, to);
				}} /></label
		>
		<label
			>To <input type="number" min={years[0]} max={years[1]} value={to}
				onchange={(e) => {
					const y = year(e.currentTarget.value, to);
					e.currentTarget.value = String(y);
					setPeriod(from, y);
				}} /></label
		>
		<span class="muted">{label(from)} – {label(to)} · {flowing.arcs.length} arcs · {flowing.sagas.length} sagas</span>
	</div>

	<section class="card">
		<h2>The story river</h2>
		<p class="muted legend">
			Each bar is an ambition, from its forming to its end ({glyph('fulfilled')} fulfilled, {glyph('thwarted')} thwarted,
			{glyph('died_unfulfilled')} died unfulfilled, {glyph('abandoned')} abandoned, {glyph('active')} still wanted). Dots
			are turning points. <span class="key seize">Seize</span> <span class="key vengeance">Vengeance</span>
			<span class="key protect">Protect</span> <span class="key standing">Standing</span> <span class="key marry">Marry</span>
		</p>
		<StoryRiver arcs={stories.arcs} {from} {to} run={name} />
	</section>

	<div class="cols">
		<section class="card">
			<h2>Sagas</h2>
			{#if flowing.sagas.length === 0}
				<p class="muted">No saga runs through these years.</p>
			{:else}
				<ol class="list">
					{#each flowing.sagas as s (s.id)}
						<li>
							<a href={sagaHref(s.id)}>{s.title}</a>
							<span class="muted">{label(s.span[0])} – {label(s.span[1])} · {s.arcs.length} arcs · {s.people.length} people</span>
						</li>
					{/each}
				</ol>
			{/if}
		</section>
		<section class="card">
			<h2>Most salient arcs</h2>
			{#if flowing.arcs.length === 0}<p class="muted">No ambition stirs in these years.</p>{/if}
			<ol class="list">
				{#each flowing.arcs.slice(0, 15) as a (a.id)}
					<li>
						<span class="glyph-inline">{glyph(a.outcome)}</span>
						<a href={arcHref(a.ambition)}>{a.title}</a>
						<span class="muted">{a.span[0]}–{a.span[1]} · {a.class}</span>
					</li>
				{/each}
			</ol>
		</section>
	</div>
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	.period {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		align-items: end;
		margin-bottom: 0.8rem;
	}
	.period input {
		width: 5.5rem;
	}
	h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	.legend {
		font-size: 0.85rem;
		margin-top: 0;
	}
	.seize {
		background: var(--unexplained);
	}
	.vengeance {
		background: var(--divergent);
	}
	.protect {
		background: var(--pin);
	}
	.standing {
		background: var(--ripple);
	}
	.marry {
		background: var(--ok);
	}
	.key {
		color: var(--surface);
		padding: 0 0.35rem;
		border-radius: 3px;
		font-size: 0.8rem;
	}
	.cols {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-top: 1rem;
	}
	.list {
		margin: 0;
		padding-left: 1.2rem;
	}
	.list li {
		margin: 0.2rem 0;
	}
	.glyph-inline {
		display: inline-block;
		width: 1rem;
		color: var(--muted);
	}
</style>
