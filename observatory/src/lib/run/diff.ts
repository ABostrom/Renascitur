import type { DateTuple } from './calendar';
import type { Manifest } from './run';
import type { RunSource } from './source';

export type Side = 'baseline' | 'variant' | 'both';

export interface UnexplainedEvent {
	id: string;
	date: DateTuple;
	type: string;
	place: string | null;
	roles: Record<string, string[]>;
	causes: [string, string][];
	activation: string;
	side: Side;
}

export interface WaveCell {
	age: number;
	year: number;
	place: string | null; // the event's place, else the scope that decided it
	divergent: number;
	unexplained: number;
	total: number;
}

/** `analysis/divergence.json`, written into the variant's folder by `renasci diff`. */
export interface Divergence {
	runs: { baseline: string; variant: string };
	events: number;
	divergent_events: number;
	unexplained_events: number;
	divergent_entities: number;
	unexplained_entities: number;
	divergent_cells: number;
	unexplained_cells: number;
	tainted_scope_names: string[];
	divergent: { only_baseline: string[]; only_variant: string[]; changed: string[] };
	unexplained: {
		events: UnexplainedEvent[];
		entities: { id: string; side: Side }[];
		cells: { id: string; column: string; side: Side }[];
	};
	wave: WaveCell[];
}

/** The run a variant is compared with by default: the one it was replayed (forked) from. */
export function defaultBaseline(m: Manifest): string | null {
	return m.meta.replayed_from?.run ?? m.parent?.run ?? null;
}

/** The variant's divergence report, or null when `renasci diff` hasn't been run for it. */
export async function loadDivergence(source: RunSource, variant: string): Promise<Divergence | null> {
	const path = `${variant}/analysis/divergence.json`;
	if (!(await source.has(path))) return null;
	return JSON.parse(await source.text(path)) as Divergence;
}

/** The divergent events that exist in one side's run (so its event browser can show them). */
export function divergentIds(d: Divergence, side: 'baseline' | 'variant'): Set<string> {
	const only = side === 'baseline' ? d.divergent.only_baseline : d.divergent.only_variant;
	return new Set([...only, ...d.divergent.changed]);
}

/** Unexplained events no other unexplained event caused: where the bug first showed. */
export function rootEvents(d: Divergence): Set<string> {
	const unexplained = new Set(d.unexplained.events.map((e) => e.id));
	return new Set(
		d.unexplained.events
			.filter((e) => !e.causes.some(([kind, ref]) => kind === 'event' && unexplained.has(ref)))
			.map((e) => e.id)
	);
}

export type YearKey = [number, number]; // [age, year]

/** The wave as a grid: places (rows) × age-years (columns). Years run unbroken from first to last. */
export function waveGrid(d: Divergence) {
	const cells = new Map<string, WaveCell>();
	const places = new Set<string | null>();
	const years = new Map<string, YearKey>();
	for (const c of d.wave) {
		cells.set(`${c.place ?? ''}|${c.age}|${c.year}`, c);
		places.add(c.place);
		years.set(`${c.age}|${c.year}`, [c.age, c.year]);
	}
	const sorted = [...years.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
	const filled: YearKey[] = [];
	for (const y of sorted) {
		const last = filled.at(-1);
		if (last && last[0] === y[0]) for (let n = last[1] + 1; n < y[1]; n++) filled.push([y[0], n]);
		filled.push(y);
	}
	const byDivergence = [...places].sort((a, b) => {
		if (a === null || b === null) return a === null ? 1 : -1; // events with nowhere go last
		return a.localeCompare(b);
	});
	return {
		places: byDivergence,
		years: filled,
		cell: (place: string | null, [age, year]: YearKey) => cells.get(`${place ?? ''}|${age}|${year}`),
		max: Math.max(1, ...d.wave.map((c) => c.divergent))
	};
}
