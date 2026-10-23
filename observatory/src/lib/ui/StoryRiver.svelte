<script lang="ts">
	import { glyph, river, type Arc } from '$lib/run/stories';

	// The story river (S13 #99): a run's ambitions as bars by house over years `from`..`to`. `mark` draws a
	// line at a year (a what-if's ripple); `highlight` outlines arcs by ambition (what changed).
	let {
		arcs,
		from,
		to,
		run,
		mark = null,
		highlight = new Set<string>(),
		width = 900
	}: {
		arcs: Arc[];
		from: number;
		to: number;
		run: string;
		mark?: number | null;
		highlight?: Set<string>;
		width?: number;
	} = $props();

	const lanes = $derived(river(arcs, from, to));
	const LEFT = 130;
	const ROW = 16;
	const GAP = 14;
	const col = $derived((width - LEFT - 10) / Math.max(1, to - from + 1));
	const x = (y: number) => LEFT + (y - from) * col;
	const tops = $derived(
		lanes.reduce<number[]>((acc, h, i) => [...acc, i === 0 ? 24 : acc[i - 1] + lanes[i - 1].lanes * ROW + GAP], [])
	);
	const height = $derived(lanes.length ? tops.at(-1)! + lanes.at(-1)!.lanes * ROW + 10 : 40);
	const ticks = $derived.by(() => {
		const span = to - from + 1;
		const step = span <= 12 ? 1 : span <= 30 ? 5 : span <= 120 ? 10 : 25;
		const out: number[] = [];
		for (let y = Math.ceil(from / step) * step; y <= to; y += step) out.push(y);
		return out;
	});
	const arcHref = (amb: string) => `/run/${encodeURIComponent(run)}/stories/arc/${encodeURIComponent(amb)}`;
	const CLASSES = ['Seize', 'Vengeance', 'Protect', 'Standing', 'Marry'];
	const cls = (c: string) => (CLASSES.includes(c) ? c.toLowerCase() : 'other');
</script>

<svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Ambitions by house, years ${from} to ${to}`}>
	{#each ticks as t (t)}
		<line class="tick" x1={x(t)} x2={x(t)} y1={16} y2={height} />
		<text class="tick-label" x={x(t) + 2} y={12}>{t}</text>
	{/each}
	{#if mark !== null && mark >= from && mark <= to}
		<line class="mark" x1={x(mark)} x2={x(mark)} y1={4} y2={height} />
	{/if}
	{#each lanes as h, i (h.house ?? '-')}
		<text class="house" x={4} y={tops[i] + 12}>{h.name}</text>
		{#each h.bars as b (b.arc.id)}
			{@const y0 = tops[i] + b.lane * ROW}
			<a href={arcHref(b.arc.ambition)} aria-label={`${b.arc.title}, ${b.arc.outcome.replace('_', ' ')}`}>
				<rect class={`bar ${cls(b.arc.class)}`} class:hl={highlight.has(b.arc.ambition)} x={x(b.from)} y={y0 + 2}
					width={Math.max(3, (b.to - b.from + 1) * col - 1)} height={ROW - 4} rx={3}>
					<title>{b.arc.title} ({b.arc.span[0]}–{b.arc.span[1]}, {b.arc.outcome.replace('_', ' ')})</title>
				</rect>
				{#if b.to === b.arc.span[1]}
					<text class="glyph" x={x(b.to) + col + 1} y={y0 + 12}>{glyph(b.arc.outcome)}</text>
				{/if}
				{#each b.turns as t (t.event)}
					<circle class="turn" cx={x(t.year) + col / 2} cy={y0 + ROW / 2} r={3}><title>{t.label}</title></circle>
				{/each}
			</a>
		{/each}
	{/each}
</svg>

<style>
	svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.tick {
		stroke: var(--border);
		stroke-width: 1;
	}
	.mark {
		stroke: var(--ripple);
		stroke-width: 2;
		stroke-dasharray: 4 3;
	}
	.tick-label,
	.house {
		fill: var(--muted);
		font-size: 11px;
	}
	.house {
		font-family: var(--serif);
		fill: var(--text);
		font-size: 12px;
	}
	.bar {
		opacity: 0.85;
	}
	.bar:hover {
		opacity: 1;
	}
	.bar.hl {
		stroke: var(--text);
		stroke-width: 2;
		opacity: 1;
	}
	.seize {
		fill: var(--unexplained);
	}
	.vengeance {
		fill: var(--divergent);
	}
	.protect {
		fill: var(--pin);
	}
	.standing {
		fill: var(--ripple);
	}
	.marry {
		fill: var(--ok);
	}
	.other {
		fill: var(--muted);
	}
	.glyph {
		fill: var(--text);
		font-size: 11px;
	}
	.turn {
		fill: var(--surface);
		stroke: var(--text);
		stroke-width: 1.5;
	}
</style>
