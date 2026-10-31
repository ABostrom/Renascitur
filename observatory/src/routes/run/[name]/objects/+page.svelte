<script lang="ts">
	import { page } from '$app/state';

	import { biographies, loadObjects, type Beat, type Biography, type ObjectEvent } from '$lib/run/objects';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	/** Objects and their biographies (S9 spec §6, #109): every masterwork, and the story of one. */
	const name = $derived(page.params.name ?? '');
	const chosen = $derived(page.url.searchParams.get('o'));
	let run = $state<Run | null>(null);
	let events = $state.raw<ObjectEvent[]>([]);
	let names = $state.raw<Record<string, string>>({});
	let fields = $state.raw<Record<string, Record<string, unknown>>>({});
	let error = $state<string | null>(null);

	$effect(() => {
		const n = name;
		let stale = false;
		run = null;
		events = [];
		names = {};
		fields = {};
		error = null;
		(async () => {
			const r = await openRun(new HttpSource(), n);
			const got = await loadObjects(r);
			if (stale) return;
			run = r;
			events = got.events;
			names = got.names;
			fields = got.fields;
		})().catch((e) => {
			if (!stale) error = (e as Error).message;
		});
		return () => (stale = true);
	});

	const cal = $derived(run?.calendar);
	const when = (d: [number, number, number] | null) => (cal && d ? cal.format(d, 'season') : '');
	const nameOf = (id: string | null) => (id ? (names[id] ?? id) : 'nobody');
	const all = $derived([...biographies(events, fields).values()]);
	const objects: Biography[] = $derived(
		[...all].sort((a, b) => b.deeds - a.deeds || (b.name ? 1 : 0) - (a.name ? 1 : 0) || a.id.localeCompare(b.id))
	);
	const one = $derived(chosen ? all.find((b) => b.id === chosen) ?? null : null);
	const base = $derived(`/run/${encodeURIComponent(name)}`);
	const entity = (id: string) => `${base}/entity/${encodeURIComponent(id)}`;
	const why = (id: string) => `${base}/events?e=${encodeURIComponent(id)}`;
	function title(b: Biography): string {
		if (b.name) return b.name;
		const words = [b.quality !== null && b.quality >= 0.8 ? 'fine' : '', b.material ?? '', b.type ?? 'thing'].filter(Boolean).join(' ');
		return `${/^[aeiou]/i.test(words) ? 'an' : 'a'} ${words}`;
	}
	const standing = (b: Biography) => (b.destroyed ? 'destroyed' : b.lost ? 'lost' : b.owner ? `held by ${nameOf(b.owner)}` : 'unknown');

	/** One beat of a biography, in words. */
	function told(b: Beat): string {
		switch (b.kind) {
			case 'made':
				return `made by ${nameOf(b.who)}`;
			case 'unearthed':
				return `turns up, found by ${nameOf(b.who)}`;
			case 'given':
				return b.from ? `passes from ${nameOf(b.from)} to ${nameOf(b.who)}${b.detail ? ` ${b.detail}` : ''}` : `kept by its maker`;
			case 'inherited':
				return `inherited by ${nameOf(b.who)} from ${nameOf(b.from)}`;
			case 'found':
				return `found by ${nameOf(b.who)}`;
			case 'stolen':
				return `stolen from ${nameOf(b.from)} by ${nameOf(b.who)}`;
			case 'lost':
				return `lost when ${nameOf(b.from)} fell`;
			case 'destroyed':
				return 'destroyed';
			case 'deed':
				return `a deed: ${b.detail === 'duel' ? 'a duel won' : b.detail === 'survived' ? 'a death escaped' : (b.detail ?? 'a deed')} by ${nameOf(b.who)}`;
			case 'named':
				return `named ${b.detail}`;
		}
	}
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › objects · <a href={`${base}/events`}>events</a> ·
	<a href={`${base}/houses`}>houses</a> · <a href={`${base}/polities`}>polities</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !run}
	<p class="muted">Loading objects…</p>
{:else if !objects.length}
	<h1>Objects</h1>
	<p class="card">This run made no objects (a world without crafts, or one where no master made anything yet).</p>
{:else}
	<h1>Objects</h1>

	{#if one}
		<section class="card">
			<h2>{title(one)}</h2>
			<p class="muted small">
				{one.type ?? 'thing'}{one.material ? ` of ${one.material}` : ''}{one.quality !== null ? `, quality ${one.quality.toFixed(2)}` : ''} ·
				{standing(one)} · <a href={entity(one.id)}>its record</a>
			</p>
			<ol class="timeline">
				{#each one.beats as b (b.event)}
					<li class={b.kind}>
						<span class="mono">{when(b.date)}</span>
						{told(b)}{#if b.place}, at <a href={entity(b.place)}>{nameOf(b.place)}</a>{/if} · <a href={why(b.cause ?? b.event)}>why</a>
					</li>
				{/each}
			</ol>
			<h3>Hands it passed through</h3>
			<p>
				{#each one.owners as o, i (o.event)}
					{#if i}<span class="muted">{' → '}</span>{/if}
					{#if o.who}<a href={entity(o.who)} title={`${o.how}, ${when(o.date)}`}>{nameOf(o.who)}</a>{:else}<span class="muted" title={when(o.date)}>(lost)</span>{/if}
				{/each}
			</p>
		</section>
	{/if}

	<section class="card">
		<h2>Every object ({objects.length})</h2>
		<div class="scroll">
			<table>
				<thead><tr><th>Object</th><th>Maker</th><th>Made</th><th class="num">Deeds</th><th>Now</th></tr></thead>
				<tbody>
					{#each objects as b (b.id)}
						<tr class:selected={b.id === chosen}>
							<td><a href={`?o=${encodeURIComponent(b.id)}`}>{title(b)}</a></td>
							<td>{#if b.maker}<a href={entity(b.maker)}>{nameOf(b.maker)}</a>{:else}<span class="muted">unknown</span>{/if}</td>
							<td class="mono">{when(b.made)}</td>
							<td class="num">{b.deeds}</td>
							<td>{standing(b)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.scroll {
		overflow-x: auto;
	}
	.small {
		font-size: 0.85rem;
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
	.timeline li.named,
	.timeline li.deed {
		border-left-color: var(--accent);
	}
	.timeline li.lost,
	.timeline li.stolen,
	.timeline li.destroyed {
		border-left-color: var(--unexplained);
	}
	tr.selected td {
		background: var(--surface-2, transparent);
	}
</style>
