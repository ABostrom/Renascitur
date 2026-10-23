<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import type { Run } from '$lib/run/run';
	import { glyph, inPeriod, presets, river, runYears, type Stories } from '$lib/run/stories';
	import { loadRunStories } from '$lib/runs';

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
	const lanes = $derived(stories ? river(stories.arcs, from, to) : []);
	const age = $derived(stories?.arcs[0]?.timeline[0]?.date[0] ?? 1);
	const label = (y: number) => (run ? run.calendar.format([age, y, 0], 'year') : String(y));

	// Layout: one column per year, one row per lane, a gap between houses.
	const LEFT = 130;
	const ROW = 16;
	const GAP = 14;
	const width = 900;
	const col = $derived((width - LEFT - 10) / Math.max(1, to - from + 1));
	const x = (y: number) => LEFT + (y - from) * col;
	const tops = $derived(
		lanes.reduce<number[]>((acc, h, i) => [...acc, i === 0 ? 24 : acc[i - 1] + lanes[i - 1].lanes * ROW + GAP], [])
	);
	const height = $derived(lanes.length ? tops.at(-1)! + lanes.at(-1)!.lanes * ROW + 10 : 40);
	const ticks = $derived.by(() => {
		const span = to - from + 1;
		const step = span <= 12 ? 1 : span <= 30 ? 5 : span <= 120 ? 10 : 25;
		const out: number[] = [];
		for (let y = Math.ceil(from / step) * step; y <= to; y += step) out.push(y);
		return out;
	});
	const enc = encodeURIComponent;
	const arcHref = (amb: string) => `/run/${enc(name)}/stories/arc/${enc(amb)}`;
	const sagaHref = (id: string) => `/run/${enc(name)}/stories/saga/${enc(id)}`;
	const CLASSES = ['Seize', 'Vengeance', 'Protect', 'Standing', 'Marry'];
	const cls = (c: string) => (CLASSES.includes(c) ? c.toLowerCase() : 'other');
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> › stories
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
		<svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Ambitions by house over the period">
			{#each ticks as t (t)}
				<line class="tick" x1={x(t)} x2={x(t)} y1={16} y2={height} />
				<text class="tick-label" x={x(t) + 2} y={12}>{t}</text>
			{/each}
			{#each lanes as h, i (h.house ?? '-')}
				<text class="house" x={4} y={tops[i] + 12}>{h.name}</text>
				{#each h.bars as b (b.arc.id)}
					{@const y0 = tops[i] + b.lane * ROW}
					<a href={arcHref(b.arc.ambition)} aria-label={`${b.arc.title}, ${b.arc.outcome.replace('_', ' ')}`}>
						<rect class={`bar ${cls(b.arc.class)}`} x={x(b.from)} y={y0 + 2} width={Math.max(3, (b.to - b.from + 1) * col - 1)}
							height={ROW - 4} rx={3}>
							<title>{b.arc.title} ({b.arc.span[0]}–{b.arc.span[1]}, {b.arc.outcome.replace('_', ' ')})</title>
						</rect>
						{#if b.to === b.arc.span[1]}
							<text class="glyph" x={x(b.to) + col + 1} y={y0 + 12}>{glyph(b.arc.outcome)}</text>
						{/if}
						{#each b.turns as t (t.event)}
							<circle class="turn" cx={x(t.year) + col / 2} cy={y0 + ROW / 2} r={3}><title>{t.label}</title></circle>
						{/each}
					</a>
				{/each}
			{/each}
		</svg>
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
	svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.tick {
		stroke: var(--border);
		stroke-width: 1;
	}
	.tick-label,
	.house {
		fill: var(--muted);
		font-size: 11px;
	}
	.house {
		font-family: var(--serif);
		fill: var(--text);
		font-size: 12px;
	}
	.bar {
		opacity: 0.85;
	}
	.bar:hover {
		opacity: 1;
	}
	.seize {
		fill: var(--unexplained);
		background: var(--unexplained);
	}
	.vengeance {
		fill: var(--divergent);
		background: var(--divergent);
	}
	.protect {
		fill: var(--pin);
		background: var(--pin);
	}
	.standing {
		fill: var(--ripple);
		background: var(--ripple);
	}
	.marry {
		fill: var(--ok);
		background: var(--ok);
	}
	.other {
		fill: var(--muted);
	}
	.key {
		color: var(--surface);
		padding: 0 0.35rem;
		border-radius: 3px;
		font-size: 0.8rem;
	}
	.glyph {
		fill: var(--text);
		font-size: 11px;
	}
	.turn {
		fill: var(--surface);
		stroke: var(--text);
		stroke-width: 1.5;
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
