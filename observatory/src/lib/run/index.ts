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
	placeOf: Int32Array; // -1: no place
	places: string[];
	byEntity: Map<string, Int32Array>; // events each entity took part in, in order
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

	for (const f of await segmentFiles(run, 'events')) {
		const stream = await run.source.stream(`${run.name}/${f.path}`);
		for await (const line of lines(stream, f.gz)) {
			const e = JSON.parse(line);
			const i = raw.length;
			raw.push(line);
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
			if (e.place) {
				p = placeId.get(e.place) ?? -1;
				if (p < 0) {
					p = places.push(e.place) - 1;
					placeId.set(e.place, p);
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
		row: (i: number) => JSON.parse(raw[i])
	};
}

export interface EventFilter {
	type?: string;
	place?: string;
	entity?: string;
	from?: DateTuple;
	to?: DateTuple;
	text?: string;
}

/** Indices of the events matching every given filter, in order. */
export function filterEvents(index: EventIndex, f: EventFilter): Int32Array {
	const cal = index.run.calendar;
	const type = f.type ? index.types.indexOf(f.type) : null;
	const place = f.place ? index.places.indexOf(f.place) : null;
	if ((f.type && type === -1) || (f.place && place === -1)) return new Int32Array(0);
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
		const k = index.keys[i];
		if (k < from || k > to) continue;
		if (text && !index.lines[i].toLowerCase().includes(text)) continue;
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

export interface EventDetail {
	scope: { activation: string; scope: string | null; reads: [string, string, string][]; events: string[] } | null;
	hinges: any[];
}

/** What an event turned on: the reads its scope made (with value digests) and its hinges. */
export async function eventDetail(run: Run, event: any): Promise<EventDetail> {
	const segments = await segmentsFor(run, event.date);
	let scope: EventDetail['scope'] = null;
	if (event.activation) {
		for await (const r of readSegments(run, 'reads', segments)) {
			if (r.activation === event.activation && r.scope === (event.scope ?? null)) {
				scope = r;
				break;
			}
		}
	}
	const hinges: any[] = [];
	for await (const h of readSegments(run, 'hinges', segments)) if (h.event === event.id) hinges.push(h);
	return { scope, hinges };
}
