<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import type { DateTuple } from '$lib/run/calendar';
	import { divergentIds, loadDivergence } from '$lib/run/diff';
	import { filterEvents, type EventIndex } from '$lib/run/index';
	import { loadRun } from '$lib/runs';
	import EventDetail from '$lib/ui/EventDetail.svelte';
	import VirtualList from '$lib/ui/VirtualList.svelte';

	const name = $derived(page.params.name ?? '');
	let index = $state<EventIndex | null>(null);
	let error = $state<string | null>(null);
	let progress = $state(0);

	$effect(() => {
		const n = name;
		index = null;
		error = null;
		loadRun(n, (p) => (progress = p))
			.then((r) => (index = r.index))
			.catch((e) => (error = (e as Error).message));
	});

	// Filters live in the URL, so views can be bookmarked and the back button works.
	const params = $derived(page.url.searchParams);
	const filter = $derived({
		type: params.get('type') || '',
		place: params.get('place') || '',
		entity: params.get('entity') || '',
		from: params.get('from') || '',
		to: params.get('to') || '',
		q: params.get('q') || '',
		diff: params.get('diff') || ''
	});

	// `diff=<variant>&base=<baseline>`: only the events that diverge in that diff (its report lives in
	// the variant's folder). Primitive deriveds, so other filter changes don't reload it.
	const diffParam = $derived(params.get('diff') || '');
	const baseParam = $derived(params.get('base') || '');
	let diffIds = $state<Set<string> | null>(null);
	let diffError = $state<string | null>(null);
	$effect(() => {
		const v = diffParam;
		const base = baseParam;
		const run = index?.run;
		diffIds = null;
		diffError = null;
		if (!v || !run) return;
		let stale = false;
		loadDivergence(run.source, v)
			.then((d) => {
				if (stale) return;
				if (!d) diffError = `No diff report in ${v}.`;
				else if (base && d.runs.baseline !== base) diffError = `${v} has since been diffed against ${d.runs.baseline}, not ${base}.`;
				else if (d.runs.variant !== run.name && d.runs.baseline !== run.name) diffError = `That diff doesn't involve ${run.name}.`;
				else diffIds = divergentIds(d, d.runs.variant === run.name ? 'variant' : 'baseline');
			})
			.catch((e) => {
				if (!stale) diffError = (e as Error).message;
			});
		return () => (stale = true);
	});
	const selected = $derived(params.get('e'));

	function setParam(key: string, value: string | null) {
		const p = new URLSearchParams(page.url.searchParams.toString());
		if (value) p.set(key, value);
		else p.delete(key);
		goto(`?${p}`, { replace: key !== 'e', reset: false });
	}

	function clearDiff() {
		const p = new URLSearchParams(page.url.searchParams.toString());
		p.delete('diff');
		p.delete('base');
		goto(`?${p}`, { replace: true, reset: false });
	}

	// Text search waits for a pause in typing, so each keystroke doesn't rescan every event.
	let textTimer: ReturnType<typeof setTimeout> | undefined;
	function setTextSoon(value: string) {
		clearTimeout(textTimer);
		textTimer = setTimeout(() => setParam('q', value), 200);
	}

	function parseDate(text: string, end: boolean): DateTuple | undefined {
		if (!text || !index) return undefined;
		try {
			const d = index.run.calendar.parse(text);
			const yearOnly = /^\S+ [0-9]+$/.test(text.trim());
			return end && yearOnly ? [d[0], d[1], index.run.calendar.daysPerYear - 1] : d;
		} catch {
			return undefined;
		}
	}

	const badDates = $derived(
		!!index && ((!!filter.from && !parseDate(filter.from, false)) || (!!filter.to && !parseDate(filter.to, true)))
	);
	const matches = $derived(
		index && (!filter.diff || diffIds)
			? filterEvents(index, {
					ids: diffIds ?? undefined,
					type: filter.type || undefined,
					place: filter.place || undefined,
					entity: filter.entity || undefined,
					from: parseDate(filter.from, false),
					to: parseDate(filter.to, true),
					text: filter.q || undefined
				})
			: new Int32Array(0)
	);

	function summary(i: number): string {
		const e = index!.row(i);
		const who = Object.entries(e.roles as Record<string, string[]>)
			.map(([r, m]) => `${r}: ${m.join(', ')}`)
			.join(' · ');
		return who;
	}
</script>

<p class="crumbs"><a href="/">Runs</a> › <strong>{name}</strong> › events · <a href={`/run/${encodeURIComponent(name)}/stories`}>stories</a> · <a href={`/run/${encodeURIComponent(name)}/houses`}>houses</a> · <a href={`/run/${encodeURIComponent(name)}/map`}>map</a> · <a href={`/run/${encodeURIComponent(name)}/strain`}>canon strain</a></p>

{#if error}
	<p class="card">{error}</p>
{:else if !index}
	<p class="muted">Indexing events… {progress ? `${progress.toLocaleString()} so far` : ''}</p>
{:else}
	<div class="filters card">
		<label>Type
			<select value={filter.type} onchange={(e) => setParam('type', e.currentTarget.value)}>
				<option value="">any ({index.count.toLocaleString()})</option>
				{#each [...index.typeCounts].sort((a, b) => a[0].localeCompare(b[0])) as [t, n] (t)}
					<option value={t}>{t} ({n.toLocaleString()})</option>
				{/each}
			</select>
		</label>
		<label>Where
			<select value={filter.place} onchange={(e) => setParam('place', e.currentTarget.value)}>
				<option value="">anywhere</option>
				{#each [...index.places].sort() as p (p)}<option value={p}>{p}</option>{/each}
				<option value="-">nowhere (engine)</option>
			</select>
		</label>
		<label>Who <input placeholder="entity id" value={filter.entity} onchange={(e) => setParam('entity', e.currentTarget.value.trim())} /></label>
		<label>From <input placeholder="e.g. 1X 40" value={filter.from} onchange={(e) => setParam('from', e.currentTarget.value.trim())} /></label>
		<label>To <input placeholder="e.g. 1X 60" value={filter.to} onchange={(e) => setParam('to', e.currentTarget.value.trim())} /></label>
		<label class="grow">Text <input placeholder="search ids, roles, payloads" value={filter.q} oninput={(e) => setTextSoon(e.currentTarget.value)} /></label>
		{#if filter.diff}
			<span class="diffing">
				{#if diffError}<span class="warn">{diffError}</span>{:else}divergent in the diff of <span class="mono">{filter.diff}</span>{/if}
				<button class="clear" onclick={clearDiff}>show all</button>
			</span>
		{/if}
		{#if badDates}<span class="warn">Dates look like “1X 40” or “1X 40 m3 d12”.</span>{/if}
	</div>

	<div class="layout" class:with-detail={!!selected}>
		<div>
			{#if diffParam && !diffIds && !diffError}
				<p class="muted count">Loading the diff…</p>
			{:else}
				<p class="muted count">{matches.length.toLocaleString()} event{matches.length === 1 ? '' : 's'}</p>
			{/if}
			<VirtualList count={matches.length} rowHeight={32} resetKey={JSON.stringify(filter) + (diffIds ? 'd' : '')}>
				{#snippet row(k)}
					{@const i = matches[k]}
					{@const id = index!.ids[i]}
					<button class="event" class:selected={id === selected} onclick={() => setParam('e', id)}>
						<span class="date mono">{index!.run.calendar.format(index!.row(i).date, 'season')}</span>
						<span class="type">{index!.types[index!.typeOf[i]]}</span>
						<span class="who">{summary(i)}</span>
					</button>
				{/snippet}
			</VirtualList>
		</div>
		{#if selected}
			<aside class="card detail">
				<button class="close" onclick={() => setParam('e', null)} aria-label="Close">×</button>
				<EventDetail {index} id={selected} onSelect={(id) => setParam('e', id)} />
			</aside>
		{/if}
	</div>
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		align-items: end;
		margin-bottom: 0.8rem;
	}
	label {
		display: flex;
		flex-direction: column;
		font-size: 0.8rem;
		color: var(--muted);
		gap: 0.15rem;
	}
	label.grow {
		flex: 1;
		min-width: 12rem;
	}
	input,
	select {
		font: inherit;
		font-size: 0.9rem;
		color: var(--text);
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.3rem 0.5rem;
	}
	.diffing {
		font-size: 0.85rem;
		color: var(--divergent);
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.clear {
		font: inherit;
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.warn {
		color: var(--unexplained);
		font-size: 0.85rem;
	}
	.layout {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1rem;
	}
	.layout.with-detail {
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
	}
	.count {
		margin: 0 0 0.3rem;
	}
	.event {
		display: grid;
		grid-template-columns: 9.5rem 9rem 1fr;
		gap: 0.6rem;
		width: 100%;
		height: 100%;
		text-align: left;
		align-items: center;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--border);
		border-radius: 0;
		padding: 0 0.6rem;
		white-space: nowrap;
		overflow: hidden;
	}
	.event:hover {
		background: var(--surface-2);
	}
	.event.selected {
		background: var(--surface-2);
		box-shadow: inset 3px 0 0 var(--accent);
	}
	.date {
		color: var(--muted);
	}
	.type {
		font-weight: 600;
	}
	.who {
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--muted);
	}
	.detail {
		position: relative;
		max-height: 75vh;
		overflow: auto;
	}
	.close {
		position: absolute;
		right: 0.6rem;
		top: 0.4rem;
		border: none;
		background: none;
		font-size: 1.3rem;
	}
	.muted {
		color: var(--muted);
	}
	@media (max-width: 900px) {
		.layout.with-detail {
			grid-template-columns: 1fr;
		}
	}
</style>
