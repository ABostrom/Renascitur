<script lang="ts">
	import { niceTicks } from '$lib/run/houses';

	/** Lines over years, one axis. Hover anywhere for a crosshair and every series' value that year. */
	export interface Line {
		key: string;
		label: string;
		color: string; // a CSS colour (a --series-n token)
		points: { year: [number, number]; value: number }[];
	}

	let { lines, yearLabel, title, unit = '' }: { lines: Line[]; yearLabel: (y: [number, number]) => string; title: string; unit?: string } = $props();

	const W = 760;
	const H = 300;
	const M = $derived({ top: 12, right: lines.length <= 4 ? 120 : 16, bottom: 28, left: 56 });
	const n = $derived(lines[0]?.points.length ?? 0);
	let pointer = $state<number | null>(null);
	const hover = $derived(pointer !== null && pointer < n ? pointer : null); // (a new selection may be shorter)
	const max = $derived(Math.max(1, ...lines.flatMap((l) => l.points.map((p) => p.value))));
	const ticks = $derived(niceTicks(max));
	const top = $derived(ticks[ticks.length - 1]);
	const x = (i: number) => M.left + (n <= 1 ? 0 : (i * (W - M.left - M.right)) / (n - 1));
	const y = (v: number) => H - M.bottom - (v / top) * (H - M.top - M.bottom);
	const path = (l: Line) => l.points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join('');
	const every = $derived(Math.max(1, Math.ceil(n / 8)));
	// Direct labels at the line ends, nudged apart so none overlap (at least 14 units between them).
	const labelY = $derived.by(() => {
		const ys = lines.map((l, k) => ({ k, y: n ? y(l.points[n - 1].value) + 4 : 0 })).sort((a, b) => a.y - b.y);
		for (let i = 1; i < ys.length; i++) ys[i].y = Math.max(ys[i].y, ys[i - 1].y + 14);
		return Object.fromEntries(ys.map((o) => [o.k, o.y]));
	});
	const fmt = (v: number) => v.toLocaleString();

	function move(e: PointerEvent) {
		const svg = e.currentTarget as SVGSVGElement;
		const r = svg.getBoundingClientRect();
		const px = ((e.clientX - r.left) / r.width) * W;
		const i = Math.round(((px - M.left) / (W - M.left - M.right)) * (n - 1));
		pointer = i >= 0 && i < n ? i : null;
	}

	function key(e: KeyboardEvent) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
		e.preventDefault();
		const at = hover ?? (e.key === 'ArrowLeft' ? n : -1);
		pointer = Math.min(n - 1, Math.max(0, at + (e.key === 'ArrowLeft' ? -1 : 1)));
	}
</script>

<div class="chart">
	<ul class="legend" aria-label="Legend">
		{#each lines as l (l.key)}
			<li><span class="swatch" style:background={l.color}></span>{l.label}</li>
		{/each}
	</ul>
	<div class="plot">
		<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions (the arrow keys step a crosshair; the table is the full alternative) -->
		<svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title} (arrow keys step through the years)`} tabindex="0"
			onpointermove={move} onpointerleave={() => (pointer = null)} onkeydown={key} onblur={() => (pointer = null)}>
			{#each ticks as t (t)}
				<line class="grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
				<text class="tick" x={M.left - 6} y={y(t) + 4} text-anchor="end">{fmt(t)}</text>
			{/each}
			{#each lines[0]?.points ?? [] as p, i (i)}
				{#if i % every === 0 || i === n - 1}
					<text class="tick" x={x(i)} y={H - 8} text-anchor="middle">{yearLabel(p.year)}</text>
				{/if}
			{/each}
			{#each lines as l, k (l.key)}
				<path d={path(l)} fill="none" stroke={l.color} stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
				{#if n === 1}<circle cx={x(0)} cy={y(l.points[0].value)} r="4" fill={l.color} />{/if}
				{#if lines.length <= 4 && n}
					<text class="direct" x={x(n - 1) + 8} y={labelY[k]}>{l.label}</text>
				{/if}
			{/each}
			{#if hover !== null}
				<line class="cross" x1={x(hover)} x2={x(hover)} y1={M.top} y2={H - M.bottom} />
				{#each lines as l (l.key)}
					<circle cx={x(hover)} cy={y(l.points[hover].value)} r="4" fill={l.color} class="dot" />
				{/each}
			{/if}
		</svg>
		{#if hover !== null}
			<div class="tip" style:left={`${(x(hover) / W) * 100}%`} class:flip={hover > n / 2} role="status">
				<strong>{yearLabel(lines[0].points[hover].year)}</strong>
				{#each [...lines].sort((a, b) => b.points[hover!].value - a.points[hover!].value) as l (l.key)}
					<div><span class="swatch" style:background={l.color}></span>{l.label} <span class="v">{fmt(l.points[hover].value)}{unit}</span></div>
				{/each}
			</div>
		{/if}
	</div>
	<details>
		<summary>Table</summary>
		<div class="scroll">
			<table>
				<thead><tr><th>year</th>{#each lines as l (l.key)}<th>{l.label}</th>{/each}</tr></thead>
				<tbody>
					{#each lines[0]?.points ?? [] as p, i (i)}
						<tr><td class="mono">{yearLabel(p.year)}</td>{#each lines as l (l.key)}<td class="mono num">{fmt(l.points[i].value)}</td>{/each}</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
</div>

<style>
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
		list-style: none;
		padding: 0;
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
		color: var(--text);
	}
	.swatch {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 2px;
		margin-right: 0.35rem;
		vertical-align: -0.05rem;
	}
	.plot {
		position: relative;
		overflow-x: auto;
	}
	svg:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	svg {
		width: 100%;
		min-width: 520px;
		height: auto;
		display: block;
		touch-action: none;
	}
	.grid {
		stroke: var(--border);
		stroke-width: 1;
	}
	.tick {
		font: 11px var(--sans);
		fill: var(--muted);
	}
	.direct {
		font: 12px var(--sans);
		fill: var(--text);
	}
	.cross {
		stroke: var(--muted);
		stroke-dasharray: 3 3;
	}
	.dot {
		stroke: var(--surface);
		stroke-width: 2;
	}
	.tip {
		position: absolute;
		top: 0.5rem;
		transform: translateX(12px);
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.4rem 0.6rem;
		font-size: 0.85rem;
		pointer-events: none;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgb(0 0 0 / 0.15);
	}
	.tip.flip {
		transform: translateX(calc(-100% - 12px));
	}
	.tip .v {
		margin-left: 0.75rem;
		float: right;
		font-family: var(--mono);
	}
	details {
		margin-top: 0.5rem;
		font-size: 0.85rem;
	}
	.scroll {
		overflow-x: auto;
	}
	th,
	td {
		padding: 0.1rem 0.75rem 0.1rem 0;
		text-align: left;
	}
	.num {
		text-align: right;
	}
</style>
