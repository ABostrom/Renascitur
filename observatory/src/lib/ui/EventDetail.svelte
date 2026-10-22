<script lang="ts">
	import { page } from '$app/state';

	import type { CauseGraph } from '$lib/run/causes';
	import { eventDetail, type EventDetail, type EventIndex } from '$lib/run/index';
	import { loadGraph } from '$lib/runs';

	import CauseTree from './CauseTree.svelte';

	let { index, id, onSelect }: { index: EventIndex; id: string; onSelect: (id: string) => void } = $props();

	const event = $derived.by(() => {
		const i = index.position.get(id);
		return i === undefined ? null : index.row(i);
	});
	let detail = $state<EventDetail | null>(null);
	let loading = $state(false);
	let failed = $state<string | null>(null);

	$effect(() => {
		const e = event;
		detail = null;
		failed = null;
		if (!e) return;
		let stale = false; // a newer selection supersedes this load
		loading = true;
		eventDetail(index.run, e, index.segmentOf[index.position.get(id) ?? 0])
			.then((d) => {
				if (!stale) detail = d;
			})
			.catch((err) => {
				if (!stale) failed = (err as Error).message;
			})
			.finally(() => {
				if (!stale) loading = false;
			});
		return () => (stale = true);
	});

	let graph = $state<CauseGraph | null>(null);
	let direction = $state<'why' | 'led'>('why');
	let depth = $state(2);
	$effect(() => {
		const name = index.run.name;
		loadGraph(name).then((g) => (graph = g));
	});

	/** A link to this view with one filter set (and the selection cleared). */
	function filterHref(key: string, value: string): string {
		const p = new URLSearchParams(page.url.searchParams.toString());
		p.delete('e');
		p.set(key, value);
		return `?${p}`;
	}

	const cal = $derived(index.run.calendar);
	const causeLabel: Record<string, string> = {
		event: 'event',
		activation: 'activation',
		ripple: 'ripple (the author)',
		pin: 'pin (canon)'
	};
</script>

{#if !event}
	<p class="muted">No event {id} in this run.</p>
{:else}
	<article>
		<header>
			<h2>{event.type}</h2>
			<div class="meta">
				<span>{cal.format(event.date, 'day')}</span>
				{#if event.place}<span>at <a href={filterHref('place', event.place)}>{event.place}</a></span>{/if}
				{#if event.visibility === 'secret'}<span class="badge warn">secret</span>{/if}
				{#if event.source?.[0] === 'ripple'}<span class="badge ripple">ripple {event.source[1]}</span>{/if}
			</div>
			<code class="id">{event.id}</code>
		</header>

		<section>
			<h3>Who</h3>
			<dl>
				{#each Object.entries(event.roles as Record<string, string[]>) as [role, members] (role)}
					<dt>{role}</dt>
					<dd>
						{#each members as m (m)}
							<span class="chip"><a class="mono" href={`/run/${encodeURIComponent(index.run.name)}/entity/${encodeURIComponent(m)}`}>{m}</a>
								<a class="filter" href={filterHref('entity', m)} title="Filter to this entity's events">⌕</a></span>
						{/each}
					</dd>
				{/each}
			</dl>
		</section>

		{#if Object.keys(event.payload).length}
			<section>
				<h3>Payload</h3>
				<pre>{JSON.stringify(event.payload, null, 1)}</pre>
			</section>
		{/if}

		<section>
			<h3>Why</h3>
			{#if event.causes.length === 0}
				<p class="muted">No recorded causes{event.activation ? ': it came from its system’s own rhythm.' : '.'}</p>
			{:else}
				<ul class="causes">
					{#each event.causes as [kind, ref] (kind + ref)}
						<li class={`cause ${kind}`}>
							<span class="kind">{causeLabel[kind] ?? kind}</span>
							{#if kind === 'event' && index.position.has(ref)}
								{@const c = index.row(index.position.get(ref) ?? 0)}
								<button class="link" onclick={() => onSelect(ref)}>{c.type} · {cal.format(c.date, 'day')}</button>
							{:else}
								<code>{ref}</code>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section>
			<h3>
				Cause chain
				<span class="controls">
					<button class:active={direction === 'why'} onclick={() => (direction = 'why')}>Why</button>
					<button class:active={direction === 'led'} onclick={() => (direction = 'led')}>What it led to</button>
					<label>depth <input type="number" min="1" max="8" bind:value={depth} /></label>
				</span>
			</h3>
			{#if graph}
				{#key `${id}:${direction}:${depth}`}
					<ul class="tree">
						<CauseTree {graph} node={{ kind: 'event', ref: id }} {direction} {depth} onSelect={onSelect} />
					</ul>
				{/key}
			{:else}
				<p class="muted">Building the cause graph…</p>
			{/if}
		</section>

		<section>
			<h3>What it read</h3>
			{#if loading}
				<p class="muted">Loading the scope’s reads…</p>
			{:else if failed}
				<p class="warn">Couldn’t load the reads: {failed}</p>
			{:else if detail?.scope}
				<p class="muted">
					{event.source?.[1]}{detail.scope.scope ? ` in ${detail.scope.scope}` : ''} read {detail.scope.reads.length}
					field{detail.scope.reads.length === 1 ? '' : 's'}, informing {detail.scope.events.length} event{detail.scope.events.length === 1 ? '' : 's'}.
				</p>
				<table class="reads">
					<thead><tr><th>entity</th><th>field</th><th>value seen</th></tr></thead>
					<tbody>
						{#each detail.scope.reads.slice(0, 200) as [entity, field, digest] (entity + field)}
							<tr><td class="mono">{entity}</td><td class="mono">{field}</td><td class="mono muted">{digest}</td></tr>
						{/each}
					</tbody>
				</table>
				{#if detail.scope.reads.length > 200}<p class="muted">…and {detail.scope.reads.length - 200} more.</p>{/if}
			{/if}
			{#if !loading && detail?.unscoped && detail.unscoped.reads.length}
				<p class="muted">Before any village or valley, the activation also read {detail.unscoped.reads.length} field{detail.unscoped.reads.length === 1 ? '' : 's'}; these inform everything it did:</p>
				<table class="reads">
					<tbody>
						{#each detail.unscoped.reads.slice(0, 50) as [entity, field, digest] (entity + field)}
							<tr><td class="mono">{entity}</td><td class="mono">{field}</td><td class="mono muted">{digest}</td></tr>
						{/each}
					</tbody>
				</table>
			{/if}
			{#if !loading && !failed && !detail?.scope && !detail?.unscoped}
				<p class="muted">No recorded reads (casting and engine events read nothing).</p>
			{/if}
		</section>

		{#if detail && detail.hinges.length}
			<section>
				<h3>Close calls it turned on</h3>
				<ul class="hinges">
					{#each detail.hinges as h (h.id)}
						<li>
							<span class="mono">{h.purpose}</span> for <span class="mono">{h.owner}</span>:
							{#if h.kind === 'chance'}
								rolled {h.u.toFixed(3)} against {h.p.toFixed(3)} (margin {h.margin.toFixed(4)}) → {h.outcome ? 'yes' : 'no'}
							{:else}
								{h.winner} over {h.runner_up} (gap {h.margin?.toFixed(4)})
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	</article>
{/if}

<style>
	header h2 {
		margin: 0;
	}
	.meta {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		color: var(--muted);
		margin: 0.25rem 0;
	}
	.id {
		color: var(--muted);
		font-size: 0.8rem;
	}
	section {
		margin-top: 1.1rem;
	}
	h3 {
		font-size: 1rem;
		margin: 0 0 0.4rem;
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.2rem 0.8rem;
		margin: 0;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
	}
	.chip {
		margin-right: 0.6rem;
		white-space: nowrap;
	}
	.filter {
		text-decoration: none;
		color: var(--muted);
		margin-left: 0.15rem;
	}
	.controls {
		display: inline-flex;
		gap: 0.35rem;
		margin-left: 0.6rem;
		font-family: var(--sans);
		font-weight: 400;
		font-size: 0.8rem;
		align-items: center;
	}
	.controls button {
		padding: 0.1rem 0.5rem;
	}
	.controls button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.controls input {
		width: 3rem;
	}
	.tree {
		list-style: none;
		padding: 0;
		margin: 0;
		font-size: 0.9rem;
		overflow-x: auto;
	}
	pre {
		margin: 0;
		background: var(--surface-2);
		padding: 0.5rem;
		border-radius: var(--radius);
		overflow: auto;
		font-family: var(--mono);
		font-size: 0.85rem;
	}
	.causes {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.cause {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		padding: 0.15rem 0;
	}
	.cause .kind {
		min-width: 8rem;
		color: var(--muted);
	}
	.cause.ripple .kind {
		color: var(--ripple);
		font-weight: 600;
	}
	.cause.pin .kind {
		color: var(--pin);
		font-weight: 600;
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.reads {
		border-collapse: collapse;
		width: 100%;
		font-size: 0.85rem;
	}
	.reads th {
		text-align: left;
		color: var(--muted);
		font-weight: 500;
	}
	.reads td,
	.reads th {
		padding: 0.15rem 0.4rem;
		border-bottom: 1px solid var(--border);
	}
	.muted {
		color: var(--muted);
	}
	.warn {
		color: var(--unexplained);
	}
	.hinges {
		padding-left: 1.1rem;
		margin: 0;
	}
</style>
