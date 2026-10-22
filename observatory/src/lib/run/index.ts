import type { DateTuple } from './calendar';
import { lines } from './jsonl';
import type { Run } from './run';
import { segmentFiles } from './segments';

/**
 * A compact, in-memory index of a run's events.
 *
 * Each event is kept as its raw JSON line (parsed only when shown), plus typed arrays for the fields
 * filters need. That keeps memory near the size of the text, and filtering a million events stays a
 * scan over integers.
 */
export interface EventIndex {
	run: Run;
	count: number;
	lines: string[];
	ids: string[];
	position: Map<string, number>;
	keys: Int32Array; // calendar sort key of each event's date
	typeOf: Uint16Array;
	types: string[];
	typeCounts: Map<string, number>;
	placeOf: Int32Array; // where it happened: its place, else the scope that decided it (-1: neither)
	places: string[];
	byEntity: Map<string, Int32Array>; // events each entity took part in, in order
	segmentOf: Uint16Array; // the segment each event was read from (so detail never guesses by date)
	lower?: string[]; // lowercased lines, built the first time text search is used
	row(i: number): any;
}

export async function buildIndex(run: Run, onProgress?: (n: number) => void): Promise<EventIndex> {
	const raw: string[] = [];
	const ids: string[] = [];
	const keys: number[] = [];
	const typeOf: number[] = [];
	const placeOf: number[] = [];
	const types: string[] = [];
	const typeId = new Map<string, number>();
	const places: string[] = [];
	const placeId = new Map<string, number>();
	const postings = new Map<string, number[]>();
	const typeCounts = new Map<string, number>();
	const segmentOf: number[] = [];

	for (const f of await segmentFiles(run, 'events')) {
		const segment = Number(/seg-(\d{5})/.exec(f.path)?.[1]);
		const stream = await run.source.stream(`${run.name}/${f.path}`);
		for await (const line of lines(stream, f.gz)) {
			const e = JSON.parse(line);
			const i = raw.length;
			raw.push(line);
			segmentOf.push(segment);
			ids.push(e.id);
			keys.push(run.calendar.sortKey(e.date));
			let t = typeId.get(e.type);
			if (t === undefined) {
				t = types.push(e.type) - 1;
				typeId.set(e.type, t);
			}
			typeOf.push(t);
			typeCounts.set(e.type, (typeCounts.get(e.type) ?? 0) + 1);
			let p = -1;
			const where: string | null = e.place || e.scope || null;
			if (where) {
				p = placeId.get(where) ?? -1;
				if (p < 0) {
					p = places.push(where) - 1;
					placeId.set(where, p);
				}
			}
			placeOf.push(p);
			const seen = new Set<string>();
			for (const members of Object.values(e.roles as Record<string, string[]>)) {
				for (const m of members) {
					if (seen.has(m)) continue;
					seen.add(m);
					let list = postings.get(m);
					if (!list) postings.set(m, (list = []));
					list.push(i);
				}
			}
			if (onProgress && i % 5000 === 0) onProgress(i);
		}
	}
	const byEntity = new Map<string, Int32Array>();
	for (const [k, v] of postings) byEntity.set(k, Int32Array.from(v));
	return {
		run,
		count: raw.length,
		lines: raw,
		ids,
		position: new Map(ids.map((id, i) => [id, i])),
		keys: Int32Array.from(keys),
		typeOf: Uint16Array.from(typeOf),
		types,
		typeCounts,
		placeOf: Int32Array.from(placeOf),
		places,
		byEntity,
		segmentOf: Uint16Array.from(segmentOf),
		row: (i: number) => JSON.parse(raw[i])
	};
}

export interface EventFilter {
	type?: string;
	place?: string; // "-": nowhere (neither place nor scope)
	entity?: string;
	from?: DateTuple;
	to?: DateTuple;
	text?: string;
	ids?: Set<string>; // only these events (a diff's divergent ids)
}

/** Indices of the events matching every given filter, in order. */
export function filterEvents(index: EventIndex, f: EventFilter): Int32Array {
	const cal = index.run.calendar;
	const type = f.type ? index.types.indexOf(f.type) : null;
	const place = f.place === '-' ? -1 : f.place ? index.places.indexOf(f.place) : null;
	if ((f.type && type === -1) || (f.place && f.place !== '-' && place === -1)) return new Int32Array(0);
	const from = f.from ? cal.sortKey(f.from) : -Infinity;
	const to = f.to ? cal.sortKey(f.to) : Infinity;
	const text = f.text?.trim().toLowerCase() || null;
	const candidates: ArrayLike<number> = f.entity
		? (index.byEntity.get(f.entity) ?? new Int32Array(0))
		: { length: index.count } as ArrayLike<number>;
	const out: number[] = [];
	for (let c = 0; c < candidates.length; c++) {
		const i = f.entity ? candidates[c] : c;
		if (type !== null && index.typeOf[i] !== type) continue;
		if (place !== null && index.placeOf[i] !== place) continue;
		if (f.ids && !f.ids.has(index.ids[i])) continue;
		const k = index.keys[i];
		if (k < from || k > to) continue;
		if (text && !(index.lower ??= index.lines.map((l) => l.toLowerCase()))[i].includes(text)) continue;
		out.push(i);
	}
	return Int32Array.from(out);
}

interface Sidecar {
	segment: number;
	first: DateTuple | null;
	last: DateTuple | null;
}

const sidecars = new WeakMap<Run, Promise<Sidecar[]>>();

function loadSidecars(run: Run): Promise<Sidecar[]> {
	let p = sidecars.get(run);
	if (!p) {
		p = (async () => {
			const names = (await run.source.list(`${run.name}/index`)).filter((n) => /^seg-\d{5}\.json$/.test(n));
			return Promise.all(names.map(async (n) => JSON.parse(await run.source.text(`${run.name}/index/${n}`))));
		})();
		sidecars.set(run, p);
	}
	return p;
}

/** Segments that can contain events dated `date` (the open segment when no sidecar covers it). */
export async function segmentsFor(run: Run, date: DateTuple): Promise<number[]> {
	const cal = run.calendar;
	const key = cal.sortKey(date);
	const sides = await loadSidecars(run);
	const hits = sides
		.filter((s) => s.first && s.last && cal.sortKey(s.first) <= key && key <= cal.sortKey(s.last))
		.map((s) => s.segment)
		.sort((a, b) => a - b);
	return hits.length ? hits : [run.manifest.segments];
}

async function* readSegments(run: Run, table: string, segments: number[]): AsyncGenerator<any> {
	const wanted = new Set(segments);
	for (const f of await segmentFiles(run, table)) {
		const n = Number(/seg-(\d{5})/.exec(f.path)?.[1]);
		if (!wanted.has(n)) continue;
		const stream = await run.source.stream(`${run.name}/${f.path}`);
		for await (const line of lines(stream, f.gz)) yield JSON.parse(line);
	}
}

type ReadRow = { activation: string; scope: string | null; reads: [string, string, string][]; events: string[] };

export interface EventDetail {
	scope: ReadRow | null; // the reads of the scope the event was emitted in
	unscoped: ReadRow | null; // the activation's unscoped reads, which inform everything it did
	hinges: any[];
}

/**
 * What an event turned on: its scope's reads and the activation's unscoped reads (with value
 * digests), and its hinges. `segment` (from the index) says where to look; without it the
 * sidecars are used to guess from the date.
 */
export async function eventDetail(run: Run, event: any, segment?: number): Promise<EventDetail> {
	const segments = segment !== undefined ? [segment] : await segmentsFor(run, event.date);
	let scope: ReadRow | null = null;
	let unscoped: ReadRow | null = null;
	if (event.activation) {
		for await (const r of readSegments(run, 'reads', segments)) {
			if (r.activation !== event.activation) continue;
			if (r.events.includes(event.id) && r.scope !== null) scope = r;
			else if (r.scope === null) unscoped = r;
			if (scope && unscoped) break;
		}
	}
	const hinges: any[] = [];
	for await (const h of readSegments(run, 'hinges', segments)) if (h.event === event.id) hinges.push(h);
	return { scope, unscoped, hinges };
}
