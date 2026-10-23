<script lang="ts">
	import { page } from '$app/state';

	import { finalState } from '$lib/run/entity';
	import { houseRows, populationSeries, successions, type HouseRow, type PopRow, type Reign } from '$lib/run/houses';
	import { stateIndexOf, type StateIndex } from '$lib/run/person';
	import { openRun, readTable, type Run } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';
	import LineChart, { type Line } from '$lib/ui/LineChart.svelte';

	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let ix = $state<StateIndex | null>(null);
	let pops = $state<PopRow[]>([]);
	let reigns = $state<Map<string, Reign[]> | null>(null);
	let error = $state<string | null>(null);
	let group = $state('region');
	let measure = $state<'people' | 'notables'>('people');

	$effect(() => {
		const n = name;
		let stale = false;
		run = ix = reigns = null;
		pops = [];
		error = null;
		(async () => {
			const r = await openRun(new HttpSource(), n);
			if (r.manifest.meta.complete === false) throw new Error('This run has not finished: houses and population need its final state.');
			const state = await stateIndexOf(r, () => finalState(r));
			const rows: PopRow[] = [];
			for await (const row of readTable(r, 'timeseries')) if (row.system === 'people.population') rows.push(row);
			if (stale) return;
			run = r;
			ix = state;
			pops = rows;
			// Successions read every state change; the table shows without them first.
			const offices = new Set([...state.byId.values()].filter((e) => e.kind === 'office').map((e) => e.id));
			const deltas = [];
			for await (const d of readTable(r, 'state_deltas')) if (d.field === 'holder') deltas.push(d);
			if (!stale) reigns = successions(deltas, offices);
		})().catch((e) => {
			if (!stale) error = (e as Error).message;
		});
		return () => (stale = true);
	});

	const cal = $derived(run?.calendar);
	const nameOf = (id: string) => ix?.get(id)?.fields.name ?? id;
	const regionOf = $derived(
		Object.fromEntries([...(ix?.byId.values() ?? [])].filter((e) => e.kind === 'settlement').map((e) => [e.id, e.fields.region as string]))
	);
	const regions = $derived([...new Set(Object.values(regionOf))].sort());
	const series = $derived(ix ? populationSeries(pops, regionOf, { group, measure }) : []);
	// Colour follows the entity, never its rank: the shown series take slots in key order (at most
	// eight, since the rest fold into "other"), so changing what's counted never repaints a line.
	const slots = $derived(
		Object.fromEntries(series.filter((s) => s.key !== 'other').map((s) => s.key).sort().map((k, i) => [k, i + 1]))
	);
	const lines: Line[] = $derived(
		series.map((s) => ({
			key: s.key,
			label: s.key === 'other' ? 'Other' : nameOf(s.key).replace(/^[a-z]:/, ''),
			color: s.key === 'other' ? 'var(--series-other)' : `var(--series-${slots[s.key]})`,
			points: s.points
		}))
	);
	const houses: HouseRow[] = $derived(ix ? houseRows(ix) : []);
	const href = (id: string) => `/run/${encodeURIComponent(name)}/entity/${encodeURIComponent(id)}`;
	const date = (d: [number, number, number] | null) => (d && cal ? cal.format(d, 'year') : '—');
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <strong>{name}</strong> › houses · <a href={`/run/${encodeURIComponent(name)}/events`}>events</a> ·
	<a href={`/run/${encodeURIComponent(name)}/stories`}>stories</a> · <a href={`/run/${encodeURIComponent(name)}/map`}>map</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !ix || !cal}
	<p class="muted">Loading…</p>
{:else}
	<h1>Houses and people</h1>

	<section class="card">
		<h2>Population by place</h2>
		{#if lines.length === 0}
			<p class="muted">This run's world keeps no population timeseries.</p>
		{:else}
			<div class="controls">
				<label>Show
					<select bind:value={group}>
						<option value="region">every region</option>
						{#each regions as r (r)}<option value={r}>{nameOf(r).replace(/^[a-z]:/, '')}'s settlements</option>{/each}
					</select>
				</label>
				<label>Count
					<select bind:value={measure}>
						<option value="people">everyone (notables and the masses)</option>
						<option value="notables">notables only</option>
					</select>
				</label>
			</div>
			<LineChart {lines} yearLabel={(y) => cal!.format([y[0], y[1], 0], 'year')}
				title={`${measure === 'people' ? 'People' : 'Notables'} by ${group === 'region' ? 'region' : 'settlement'}, by year`} />
		{/if}
	</section>

	<section class="card">
		<h2>Houses ({houses.length})</h2>
		<div class="scroll">
			<table class="houses">
				<thead>
					<tr><th>house</th><th>rank</th><th>seat</th><th>head at the end</th><th class="num">living</th><th class="num" title="faded back into the masses">dormant</th><th class="num">dead</th><th>founded</th><th>heads, in order</th></tr>
				</thead>
				<tbody>
					{#each houses as h (h.id)}
						<tr class:extinct={h.extinct}>
							<td><a href={href(h.id)}>{h.name}</a>{#if h.extinct}<span class="badge warn">extinct {date(h.extinct)}</span>{/if}</td>
							<td class="num">{h.rank}</td>
							<td>{#if h.seat}<a href={href(h.seat.id)}>{h.seat.name.replace(/^[a-z]:/, '')}</a>{/if}</td>
							<td>{#if h.head}<a href={href(h.head.id)}>{h.head.name}</a>{:else}<span class="muted">none</span>{/if}</td>
							<td class="num mono">{h.living}</td>
							<td class="num mono">{h.dormant}</td>
							<td class="num mono">{h.dead}</td>
							<td class="mono">{date(h.founded)}</td>
							<td class="heads">
								{#if !reigns}<span class="muted">…</span>
								{:else}
									{#each reigns.get(h.office ?? '') ?? [] as r, i (i)}
										{#if i}<span class="muted">{' → '}</span>{/if}<span class="reign"><a href={href(r.holder)} title={`${date(r.from)}–${r.to ? date(r.to) : 'end'}`}>{nameOf(r.holder)}</a>{' '}<span class="muted small">{date(r.from)}</span></span>
									{:else}<span class="muted">—</span>{/each}
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.25rem;
		margin-bottom: 0.75rem;
	}
	.scroll {
		overflow-x: auto;
	}
	.houses th,
	.houses td {
		padding: 0.25rem 0.9rem 0.25rem 0;
		text-align: left;
		vertical-align: top;
	}
	.houses .num {
		text-align: right;
	}
	.houses .heads {
		min-width: 18rem;
	}
	.houses td:nth-child(3),
	.reign {
		white-space: nowrap;
	}
	tr.extinct {
		opacity: 0.7;
	}
	.badge {
		margin-left: 0.4rem;
	}
	.small {
		font-size: 0.8rem;
	}
</style>
