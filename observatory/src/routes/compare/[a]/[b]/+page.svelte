<script lang="ts">
	import { page } from '$app/state';

	import type { DateTuple } from '$lib/run/calendar';
	import { loadDivergence, type Divergence } from '$lib/run/diff';
	import { filterEvents } from '$lib/run/index';
	import { compareArcs } from '$lib/run/latch';
	import { HttpSource } from '$lib/run/source';
	import { glyph, runYears, type Arc, type Stories } from '$lib/run/stories';
	import { loadRun, loadRunStories } from '$lib/runs';
	import StoryRiver from '$lib/ui/StoryRiver.svelte';
	import type { Run } from '$lib/run/run';

	// A what-if next to its baseline (#101): the ripple, what the diff found, the person's fate in each,
	// both story rivers over the same years, and the arcs that came out differently.
	const a = $derived(page.params.a ?? '');
	const b = $derived(page.params.b ?? '');
	let base = $state<{ run: Run; stories: Stories | null } | null>(null);
	let variant = $state<{ run: Run; stories: Stories | null } | null>(null);
	let divergence = $state<Divergence | null>(null);
	let fates = $state<[string, string] | null>(null);
	let error = $state<string | null>(null);
	let whole = $state(false);

	type Ripple = { id: string; kind: string; date: string; target: string; params?: { until?: DateTuple } };
	const ripple = $derived((variant?.run.manifest.meta.recipe?.ripple?.[0] as Ripple | undefined) ?? null);
	const latchOf = $derived(variant?.run.manifest.meta.latch_of as { rank: number; kind: string } | undefined);

	$effect(() => {
		const [x, y] = [a, b];
		let stale = false;
		base = variant = divergence = fates = null;
		error = null;
		Promise.all([loadRunStories(x), loadRunStories(y), loadDivergence(new HttpSource(), y)])
			.then(([bx, vy, d]) => {
				if (stale) return;
				base = bx;
				variant = vy;
				divergence = d && d.runs.baseline === x ? d : null;
				if (!bx.stories || !vy.stories) error = `Both runs need stories: \`uv run renasci stories runs/${!bx.stories ? x : y}\`.`;
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	// The ripple's target, in each history: when they died, if they did (from each run's event index).
	$effect(() => {
		const target = ripple?.target;
		if (!target || !base || !variant) return;
		let stale = false;
		Promise.all([fateIn(a, target), fateIn(b, target)])
			.then((f) => {
				if (!stale) fates = f;
			})
			.catch((e) => {
				if (!stale) fates = [`unknown (${(e as Error).message})`, 'unknown'];
			});
		return () => (stale = true);
	});
	async function fateIn(run: string, who: string): Promise<string> {
		const { index } = await loadRun(run);
		for (const i of filterEvents(index, { entity: who, type: 'people.death' })) {
			const e = index.row(i);
			if (!(e.roles.deceased ?? []).includes(who)) continue; // (their victims' deaths name them too)
			return `dies ${index.run.calendar.format(e.date, 'season')} (${e.payload.cause})`;
		}
		return 'lives on';
	}

	const rippleYear = $derived(ripple ? Number(ripple.date.split(' ')[1]) : null);
	const span = $derived.by((): [number, number] => {
		if (!base?.stories || !variant?.stories) return [0, 0];
		const [lo1, hi1] = runYears(base.stories);
		const [lo2, hi2] = runYears(variant.stories);
		const lo = Math.min(lo1, lo2);
		const hi = Math.max(hi1, hi2);
		if (whole || rippleYear === null) return [lo, hi];
		return [Math.max(lo, rippleYear - 2), Math.min(hi, rippleYear + 20)];
	});
	const diff = $derived(base?.stories && variant?.stories ? compareArcs(base.stories, variant.stories) : null);
	const highlight = $derived(
		new Set(diff ? [...diff.onlyBaseline, ...diff.onlyVariant, ...diff.changed.map((p) => p[0])].map((x) => x.ambition) : [])
	);
	const enc = encodeURIComponent;
	const arcHref = (run: string, x: Arc) => `/run/${enc(run)}/stories/arc/${enc(x.ambition)}`;
</script>

<p class="crumbs">
	<a href="/">Runs</a> › compare › <a href={`/run/${enc(a)}/stories`}>{a}</a> → <a href={`/run/${enc(b)}/stories`}>{b}</a>
	· <a href={`/diff/${enc(a)}/${enc(b)}`}>diff</a>
	{#if latchOf}· <a href={`/run/${enc(a)}/latch`}>latch points</a>{/if}
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !base?.stories || !variant?.stories}
	<p class="muted">Loading both histories…</p>
{:else}
	<section class="card summary">
		<h1>What if…</h1>
		{#if ripple}
			<p>
				<strong>{ripple.kind === 'protect' ? 'Protect' : ripple.kind === 'doom' ? 'Doom' : ripple.kind}</strong>
				<a class="mono" href={`/run/${enc(b)}/entity/${enc(ripple.target)}`}>{ripple.target}</a>
				from {ripple.date}{#if ripple.params?.until} until {variant.run.calendar.format(ripple.params.until, 'year')}{/if}
				{#if latchOf}<span class="muted">(latch point {latchOf.rank}, a {latchOf.kind.replace('_', ' ')})</span>{/if}
			</p>
		{:else}
			<p class="muted">{b} has no ripple of its own: it differs from {a} by its recipe.</p>
		{/if}
		{#if ripple}
			<div class="fates">
				<div><span class="muted">In {a}:</span> {fates ? fates[0] : '…'}</div>
				<div><span class="muted">In {b}:</span> {fates ? fates[1] : '…'}</div>
			</div>
		{/if}
		{#if divergence}
			{@const clean = divergence.unexplained_events + divergence.unexplained_entities + divergence.unexplained_cells === 0}
			<p>
				{divergence.divergent_events.toLocaleString()} of {divergence.events.toLocaleString()} events diverge;
				<span class={clean ? 'ok' : 'bad'}>{clean ? 'every difference traces to the ripple' : 'some differences are unexplained'}</span>.
			</p>
		{/if}
		{#if diff}
			<p class="muted">
				{diff.changed.length} shared ambitions ended differently · {diff.onlyVariant.length} only in the what-if ·
				{diff.onlyBaseline.length} only in {a}. They are outlined in the rivers.
			</p>
		{/if}
	</section>

	<div class="period">
		<span class="muted">Years {span[0]}–{span[1]}</span>
		<label><input type="checkbox" bind:checked={whole} /> the whole run</label>
	</div>

	<section class="card">
		<h2>{a} <span class="muted">(as it was)</span></h2>
		<StoryRiver arcs={base.stories.arcs} from={span[0]} to={span[1]} run={a} mark={rippleYear} {highlight} />
	</section>
	<section class="card">
		<h2>{b} <span class="muted">(what if)</span></h2>
		<StoryRiver arcs={variant.stories.arcs} from={span[0]} to={span[1]} run={b} mark={rippleYear} {highlight} />
	</section>

	{#if diff}
		<div class="cols">
			<section class="card">
				<h2>Ended differently</h2>
				{#if diff.changed.length === 0}<p class="muted">None.</p>{/if}
				<ul class="list">
					{#each diff.changed.slice(0, 20) as [x, y] (x.id)}
						<li>
							<a href={arcHref(a, x)}>{x.title}</a>: {glyph(x.outcome)} {x.outcome.replace('_', ' ')}
							<span class="muted">{x.span[0]}–{x.span[1]}</span> →
							<a href={arcHref(b, y)}>{glyph(y.outcome)} {y.outcome.replace('_', ' ')}</a>
							<span class="muted">{y.span[0]}–{y.span[1]}</span>
						</li>
					{/each}
				</ul>
			</section>
			<section class="card">
				<h2>Only in the what-if</h2>
				{#if diff.onlyVariant.length === 0}<p class="muted">None.</p>{/if}
				<ul class="list">
					{#each diff.onlyVariant.slice(0, 20) as x (x.id)}
						<li><a href={arcHref(b, x)}>{x.title}</a> <span class="muted">{x.span[0]}–{x.span[1]}</span></li>
					{/each}
				</ul>
				<h2 class="later">Only in {a}</h2>
				{#if diff.onlyBaseline.length === 0}<p class="muted">None.</p>{/if}
				<ul class="list">
					{#each diff.onlyBaseline.slice(0, 20) as x (x.id)}
						<li><a href={arcHref(a, x)}>{x.title}</a> <span class="muted">{x.span[0]}–{x.span[1]}</span></li>
					{/each}
				</ul>
			</section>
		</div>
	{/if}
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	h1 {
		margin: 0 0 0.3rem;
		font-size: 1.4rem;
	}
	h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	h2.later {
		margin-top: 0.9rem;
	}
	section {
		margin-bottom: 1rem;
	}
	.fates {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.3rem 1rem;
		margin: 0.4rem 0;
	}
	.period {
		display: flex;
		gap: 1rem;
		align-items: center;
		margin-bottom: 0.6rem;
	}
	.ok {
		color: var(--ok);
	}
	.bad {
		color: var(--unexplained);
	}
	.cols {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}
	.list {
		margin: 0;
		padding-left: 1.1rem;
	}
	.list li {
		margin: 0.2rem 0;
	}
</style>
