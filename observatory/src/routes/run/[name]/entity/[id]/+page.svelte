<script lang="ts">
	import { page } from '$app/state';

	import { entityDetail, type EntityDetailData } from '$lib/run/entity';
	import type { EventIndex } from '$lib/run/index';
	import { loadRun } from '$lib/runs';

	const name = $derived(page.params.name ?? '');
	const id = $derived(page.params.id ?? '');
	let index = $state<EventIndex | null>(null);
	let detail = $state<EntityDetailData | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		const n = name;
		const e = id;
		let stale = false;
		detail = null;
		error = null;
		loadRun(n)
			.then(async ({ index: ix }) => {
				const d = await entityDetail(ix.run, ix, e);
				if (!stale) {
					index = ix;
					detail = d;
				}
			})
			.catch((err) => {
				if (!stale) error = (err as Error).message;
			});
		return () => (stale = true);
	});

	const cal = $derived(index?.run.calendar);
	const show = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'string' ? v : JSON.stringify(v));
	const eventsHref = (eid: string) => `/run/${encodeURIComponent(name)}/events?e=${encodeURIComponent(eid)}`;
</script>

<p class="crumbs"><a href="/">Runs</a> › <a href={`/run/${encodeURIComponent(name)}/events`}>{name}</a> › <span class="mono">{id}</span></p>

{#if error}
	<p class="card">{error}</p>
{:else if !detail || !index || !cal}
	<p class="muted">Loading…</p>
{:else}
	<h1 class="mono">{id}</h1>
	<div class="grid">
		<section class="card">
			<h2>At the end of the run</h2>
			{#if detail.record}
				<p>
					<span class="badge">{detail.record.kind}</span>
					<span class={`badge ${detail.record.status === 'active' ? 'ok' : 'warn'}`}>{detail.record.status}</span>
				</p>
				<dl>
					{#each Object.entries(detail.record.fields) as [field, value] (field)}
						<dt>{field}</dt>
						<dd class="mono">{show(value)}</dd>
					{/each}
					{#each Object.entries(detail.cells) as [column, value] (column)}
						<dt>{column} <span class="muted">(column)</span></dt>
						<dd class="mono">{value}</dd>
					{/each}
				</dl>
			{:else}
				<p class="muted">No final record (the run may be incomplete, or this id isn't an entity).</p>
			{/if}
		</section>

		<section class="card">
			<h2>Life ({detail.events.length} event{detail.events.length === 1 ? '' : 's'})</h2>
			<ol class="events">
				{#each detail.events as i (i)}
					{@const e = index.row(i)}
					<li>
						<span class="date mono">{cal.format(e.date, 'season')}</span>
						<a href={eventsHref(e.id)}>{e.type}</a>
						<span class="muted">as {Object.entries(e.roles as Record<string, string[]>).filter(([, m]) => m.includes(id)).map(([r]) => r).join(', ')}</span>
					</li>
				{/each}
			</ol>
		</section>
	</div>

	<section class="card changes">
		<h2>State changes ({detail.changes.length})</h2>
		<table>
			<thead><tr><th>when</th><th>field</th><th>from</th><th>to</th><th>because of</th></tr></thead>
			<tbody>
				{#each detail.changes as c, k (k)}
					<tr>
						<td class="mono">{cal.format(c.date, 'day')}</td>
						<td class="mono">{c.field}{c.bulk ? ' (column)' : ''}</td>
						<td class="mono muted">{c.bulk ? '' : show(c.old)}</td>
						<td class="mono">{c.bulk ? 'updated' : show(c.new)}</td>
						<td><a class="mono" href={eventsHref(c.event)}>{c.event}</a></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	h1 {
		font-size: 1.4rem;
	}
	.grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
		gap: 1rem;
	}
	h2 {
		font-size: 1.05rem;
		margin-top: 0;
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.2rem 0.9rem;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}
	.events {
		list-style: none;
		padding: 0;
		margin: 0;
		max-height: 24rem;
		overflow: auto;
	}
	.events li {
		display: flex;
		gap: 0.6rem;
		padding: 0.15rem 0;
		border-bottom: 1px solid var(--border);
	}
	.date {
		color: var(--muted);
		min-width: 9.5rem;
	}
	.changes {
		margin-top: 1rem;
		overflow-x: auto;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		font-size: 0.88rem;
	}
	th {
		text-align: left;
		color: var(--muted);
		font-weight: 500;
	}
	td,
	th {
		padding: 0.2rem 0.5rem;
		border-bottom: 1px solid var(--border);
		vertical-align: top;
	}
	.muted {
		color: var(--muted);
	}
	@media (max-width: 900px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
