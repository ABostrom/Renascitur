<script lang="ts">
	import type { Calendar } from '$lib/run/calendar';
	import { waveGrid, type Divergence, type WaveCell, type YearKey } from '$lib/run/diff';

	/**
	 * The causal wave: places (rows) × age-years (columns). A cell's shade is the share of its events
	 * that diverge, on one ramp; unexplained cells are outlined, not recoloured, so both themes read.
	 */
	let {
		divergence,
		calendar,
		href
	}: {
		divergence: Divergence;
		calendar: Calendar;
		href: (place: string | null, year: YearKey) => string;
	} = $props();

	const grid = $derived(waveGrid(divergence));
	const label = (y: YearKey) => calendar.format([y[0], y[1], 0], 'year');
	const shade = (c: WaveCell) => (c.divergent ? 15 + Math.round((85 * c.divergent) / c.total) : 0);
	const title = (p: string | null, y: YearKey, c: WaveCell) =>
		`${p ?? 'nowhere'} · ${label(y)}: ${c.divergent} of ${c.total} diverge` + (c.unexplained ? `, ${c.unexplained} unexplained` : '');
</script>

<div class="wrap">
	<table class="wave">
		<thead>
			<tr>
				<th></th>
				{#each grid.years as y (y.join('|'))}<th class="year mono"><span>{label(y)}</span></th>{/each}
			</tr>
		</thead>
		<tbody>
			{#each grid.places as p (p ?? '')}
				<tr>
					<th class="place mono">{p ?? '(engine)'}</th>
					{#each grid.years as y (y.join('|'))}
						{@const c = grid.cell(p, y)}
						<td>
							{#if c && c.divergent}
								<a
									class="cell"
									class:unexplained={c.unexplained > 0}
									style={`--shade: ${shade(c)}%`}
									href={href(p, y)}
									title={title(p, y, c)}
									aria-label={title(p, y, c)}
								></a>
							{:else if c}
								<span class="cell quiet" title={`${p ?? 'nowhere'} · ${label(y)}: ${c.total} events, none diverge`}></span>
							{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<p class="legend muted">
	<span class="cell" style="--shade: 25%"></span> few diverge
	<span class="cell" style="--shade: 100%"></span> all diverge
	<span class="cell unexplained" style="--shade: 50%"></span> has unexplained events
</p>

<style>
	.wrap {
		overflow-x: auto;
	}
	.wave {
		border-collapse: separate;
		border-spacing: 2px;
	}
	th {
		font-weight: 400;
		color: var(--muted);
		font-size: 0.78rem;
	}
	.place {
		text-align: right;
		padding-right: 0.5rem;
		white-space: nowrap;
	}
	.year {
		height: 4.2rem;
		vertical-align: bottom;
	}
	.year span {
		display: inline-block;
		writing-mode: vertical-rl;
		transform: rotate(180deg);
	}
	td {
		padding: 0;
	}
	.cell {
		display: inline-block;
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 3px;
		background: color-mix(in srgb, var(--divergent) var(--shade), var(--surface));
		border: 1px solid var(--border);
		box-sizing: border-box;
		vertical-align: middle;
	}
	.cell.quiet {
		background: var(--surface);
	}
	.cell.unexplained {
		outline: 2px solid var(--unexplained);
		outline-offset: 1px;
	}
	a.cell:hover {
		border-color: var(--text);
	}
	.legend {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
		font-size: 0.82rem;
	}
	.legend .cell {
		margin-left: 0.6rem;
	}
	.muted {
		color: var(--muted);
	}
</style>
