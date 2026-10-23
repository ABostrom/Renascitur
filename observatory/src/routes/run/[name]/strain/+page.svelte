<script lang="ts">
	import { page } from '$app/state';

	import type { DateTuple } from '$lib/run/calendar';
	import { openRun, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';
	import { loadStrain, type StrainReport } from '$lib/run/strain';

	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let report = $state<StrainReport | null>(null);
	let loaded = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		const n = name;
		let stale = false;
		run = report = null;
		loaded = false;
		error = null;
		(async () => {
			const r = await openRun(new HttpSource(), n);
			const s = await loadStrain(r);
			if (stale) return;
			run = r;
			report = s;
			loaded = true;
		})().catch((e) => {
			if (!stale) error = (e as Error).message;
		});
		return () => (stale = true);
	});

	const cal = $derived(run?.calendar);
	const date = (d: DateTuple | null) => (d && cal ? cal.format(d, 'season') : '—');
	function span(w: [DateTuple, DateTuple] | null): string {
		if (!w || !cal) return '—';
		const [a, b] = [cal.format(w[0], 'year'), cal.format(w[1], 'year')];
		return a === b ? a : `${a}–${b}`;
	}
	const eventHref = (e: string) => `/run/${encodeURIComponent(name)}/events?e=${encodeURIComponent(e)}`;
	const entityHref = (e: string) => `/run/${encodeURIComponent(name)}/entity/${encodeURIComponent(e)}`;
	const ACTION: Record<string, string> = { guard: 'guarded', force: 'forced', violated: 'violated' };
	const STATUS: Record<string, string> = {
		satisfied: 'met',
		forced: 'forced',
		violated: 'violated',
		out_of_scope: 'outside the run',
		unsupported: 'unsupported',
		infeasible: 'infeasible',
		dropped: 'dropped before the run',
		'no change logged': 'no change logged (met at the start, or still open)'
	};
	const tone = (s: string) => (s === 'satisfied' ? 'ok' : s === 'violated' ? 'warn' : s === 'forced' ? 'pin' : 'muted-badge');
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › canon strain · <a href={`/run/${encodeURIComponent(name)}/events`}>events</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !loaded || !cal}
	<p class="muted">Loading…</p>
{:else if !report}
	<h1>Canon strain</h1>
	<p class="card">This run had no canon pins, so nothing held it to canon and there is no strain.</p>
{:else}
	<h1>Canon strain</h1>
	<p class="muted">What the director did to keep canon: deaths turned to near misses (guards), pinned events built at their deadline (forces), and canon it couldn't keep (violations). A pin history meets on its own costs nothing.</p>

	<div class="tiles">
		<div class="tile card"><span class="n">{report.counts.met}</span><span>met on their own (in the run)</span></div>
		<div class="tile card"><span class="n">{report.counts.guard}</span><span>guards</span></div>
		<div class="tile card"><span class="n">{report.counts.force}</span><span>forces</span></div>
		<div class="tile card" class:alarm={report.counts.violated > 0}><span class="n">{report.counts.violated}</span><span>violations</span></div>
		<div class="tile card"><span class="n">{report.counts.outside}</span><span>outside the run</span></div>
	</div>

	<section class="card">
		<h2>Strain, in order ({report.entries.length})</h2>
		{#if report.entries.length === 0}
			<p class="muted">None: every pin in the run was met without the director's help.</p>
		{:else}
			<div class="scroll">
				<table>
					<thead><tr><th>when</th><th>what</th><th>pin</th><th>who</th><th>event</th></tr></thead>
					<tbody>
						{#each report.entries as e, i (i)}
							<tr>
								<td class="mono">{date(e.date)}</td>
								<td><span class={`badge ${e.action === 'violated' ? 'warn' : e.action === 'force' ? 'pin' : ''}`}>{ACTION[e.action] ?? e.action}</span></td>
								<td class="mono">{e.pin}</td>
								<td>{#if e.entity}<a class="mono" href={entityHref(e.entity)}>{e.entity}</a>{:else}<span class="muted">—</span>{/if}</td>
								<td>
									{#if e.event}<a class="mono" href={eventHref(e.event)}>{e.event}</a>
									{:else if e.action === 'guard'}<span class="muted">no event recorded after the guard</span>
									{:else}<span class="muted">no event: {e.reason ?? 'it never happened'}</span>{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<section class="card">
		<h2>Every pin ({report.pins.length})</h2>
		<div class="scroll">
			<table>
				<thead><tr><th>pin</th><th>kind</th><th>window</th><th>how it ended</th><th class="num">guards</th><th>from the vault</th></tr></thead>
				<tbody>
					{#each report.pins as p (p.id)}
						<tr>
							<td class="mono">{p.id}</td>
							<td>{p.kind ?? '—'}</td>
							<td class="mono nowrap">{span(p.window)}</td>
							<td>
								<span class={`badge ${tone(p.status)}`}>{STATUS[p.status] ?? p.status}</span>
								{#if p.event}<a class="mono small" href={eventHref(p.event)} aria-label={`event ${p.event}, ${date(p.date)}`}>{date(p.date)}</a>{/if}
								{#if p.why}<span class="muted small">{p.why}</span>{/if}
							</td>
							<td class="num mono">{p.guards || ''}</td>
							<td class="small">{p.notes.join(', ')}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}
	.tile {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.tile .n {
		font: 600 1.8rem var(--serif);
		color: var(--text);
	}
	.tile.alarm .n {
		color: var(--unexplained);
	}
	.scroll {
		overflow-x: auto;
	}
	th,
	td {
		padding: 0.25rem 0.9rem 0.25rem 0;
		text-align: left;
		vertical-align: top;
	}
	.num {
		text-align: right;
	}
	.nowrap {
		white-space: nowrap;
	}
	.small {
		font-size: 0.8rem;
	}
	.badge.muted-badge {
		color: var(--muted);
	}
</style>
