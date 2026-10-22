<script lang="ts">
	import { eventDetail, type EventDetail, type EventIndex } from '$lib/run/index';

	let { index, id, onSelect }: { index: EventIndex; id: string; onSelect: (id: string) => void } = $props();

	const event = $derived.by(() => {
		const i = index.position.get(id);
		return i === undefined ? null : index.row(i);
	});
	let detail = $state<EventDetail | null>(null);
	let loading = $state(false);

	$effect(() => {
		const e = event;
		detail = null;
		if (!e) return;
		loading = true;
		eventDetail(index.run, e)
			.then((d) => (detail = d))
			.finally(() => (loading = false));
	});

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
				{#if event.place}<span>at <a href={`?entity=${encodeURIComponent(event.place)}`}>{event.place}</a></span>{/if}
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
						{#each members as m (m)}<a class="mono chip" href={`?entity=${encodeURIComponent(m)}`}>{m}</a>{/each}
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
			<h3>What it read</h3>
			{#if loading}
				<p class="muted">Loading the scope’s reads…</p>
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
			{:else}
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
		margin-right: 0.4rem;
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
	.hinges {
		padding-left: 1.1rem;
		margin: 0;
	}
</style>
