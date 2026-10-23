import type { DateTuple } from './calendar';
import type { RunSource } from './source';

/** One beat of an arc; `turn` is its line on the story river when it is a turning point. */
export interface Beat {
	event: string;
	date: DateTuple;
	type: string;
	turn: string | null;
}

export interface SchemeProgress {
	scheme: string;
	state: string;
	step: number;
	steps: number;
	plan: string[];
}

/** An ambition told as a story (`renasci stories`, S7 §9). Years are within the run's age. */
export interface Arc {
	id: string;
	ambition: string;
	owner: string;
	owner_name: string;
	class: string;
	target: string | null;
	target_name: string | null;
	house: string | null;
	house_name: string | null;
	outcome: string;
	born_of: [string, string] | null;
	formed_by: string | null;
	beats: string[];
	timeline: Beat[];
	schemes: string[];
	progress: SchemeProgress[];
	people: string[];
	span: [number, number];
	violent: number;
	salience: number;
	title: string;
}

export interface Saga {
	id: string;
	arcs: string[];
	people: string[];
	span: [number, number];
	salience: number;
	title: string;
}

export interface Stories {
	run: string;
	arcs: Arc[];
	sagas: Saga[];
}

/** The run's `analysis/stories.json`, or null when `renasci stories` hasn't been run for it. */
export async function loadStories(source: RunSource, run: string): Promise<Stories | null> {
	const path = `${run}/analysis/stories.json`;
	if (!(await source.has(path))) return null;
	return JSON.parse(await source.text(path)) as Stories;
}

/** The first and last year any arc touches. */
export function runYears(s: Stories): [number, number] {
	if (s.arcs.length === 0) return [0, 0];
	return [Math.min(...s.arcs.map((a) => a.span[0])), Math.max(...s.arcs.map((a) => a.span[1]))];
}

export interface Preset {
	label: string;
	from: number;
	to: number;
}

/** Period presets: the whole run, then each generation (25 years), then each decade. */
export function presets(lo: number, hi: number): Preset[] {
	const out: Preset[] = [{ label: 'Whole run', from: lo, to: hi }];
	const chunks = (size: number, name: (a: number, b: number) => string) => {
		for (let a = Math.floor((lo - 1) / size) * size + 1; a <= hi; a += size) {
			const from = Math.max(a, lo);
			const to = Math.min(a + size - 1, hi);
			out.push({ label: name(from, to), from, to });
		}
	};
	if (hi - lo >= 25) chunks(25, (a, b) => `Generation ${a}–${b}`);
	chunks(10, (a, b) => `Years ${a}–${b}`);
	return out;
}

const active = (span: [number, number], from: number, to: number) => span[0] <= to && span[1] >= from;

/** What flows through years `from`..`to`: arcs most salient first, sagas as ranked. */
export function inPeriod(s: Stories, from: number, to: number): { arcs: Arc[]; sagas: Saga[] } {
	return {
		arcs: s.arcs.filter((a) => active(a.span, from, to)).sort((x, y) => y.salience - x.salience || (x.id < y.id ? -1 : 1)),
		sagas: s.sagas.filter((g) => active(g.span, from, to))
	};
}

export interface Bar {
	arc: Arc;
	from: number; // clipped to the period
	to: number;
	lane: number;
	turns: { year: number; event: string; label: string }[];
}

export interface HouseLanes {
	house: string | null;
	name: string;
	lanes: number;
	bars: Bar[];
}

/** The story river: each house's arcs as bars over the period, packed into lanes (a bar and its glyph's
 * column never overlap the next in a lane), houses by how much story they hold, the houseless last. A
 * still-wanted ambition runs to the period's end. Years are within one age (a run crossing ages would
 * need ages on the axis; no world does yet). */
export function river(arcs: Arc[], from: number, to: number): HouseLanes[] {
	const byHouse = new Map<string | null, Arc[]>();
	for (const a of arcs) {
		if (!active(a.span, from, to)) continue;
		const list = byHouse.get(a.house) ?? [];
		list.push(a);
		byHouse.set(a.house, list);
	}
	const out: HouseLanes[] = [];
	for (const [house, list] of byHouse) {
		list.sort((x, y) => x.span[0] - y.span[0] || y.salience - x.salience || (x.id < y.id ? -1 : 1));
		const ends: number[] = []; // the last year taken in each lane
		const bars: Bar[] = [];
		for (const arc of list) {
			const a = Math.max(arc.span[0], from);
			const b = arc.outcome === 'active' ? to : Math.min(arc.span[1], to);
			let lane = ends.findIndex((end) => end + 1 < a); // (the column after a bar holds its glyph)
			if (lane === -1) lane = ends.push(b) - 1;
			else ends[lane] = b;
			const turns = arc.timeline
				.filter((t) => t.turn && t.type !== 'people.ambition_resolved' && t.date[1] >= from && t.date[1] <= to) // (the end is the glyph)
				.map((t) => ({ year: t.date[1], event: t.event, label: t.turn! }));
			bars.push({ arc, from: a, to: b, lane, turns });
		}
		out.push({ house, name: house ? (list[0].house_name ?? house) : 'No house', lanes: ends.length, bars });
	}
	const weight = (h: HouseLanes) => h.bars.reduce((s, b) => s + b.arc.salience, 0);
	return out.sort((x, y) => (x.house === null ? 1 : 0) - (y.house === null ? 1 : 0) || weight(y) - weight(x));
}

const GLYPHS: Record<string, string> = {
	fulfilled: '✓',
	thwarted: '✗',
	abandoned: '○',
	died_unfulfilled: '†',
	active: '→'
};

/** The outcome's mark at the end of a bar. */
export function glyph(outcome: string): string {
	return GLYPHS[outcome] ?? '·';
}

/** What an ambition was born of, in words. */
export function bornOf(arc: Arc): string {
	if (!arc.born_of) return '';
	const [kind, ref] = arc.born_of;
	if (kind === 'drive') return `a want of ${ref}`;
	if (kind === 'wound') return `a wound (${ref})`;
	return 'an event';
}
