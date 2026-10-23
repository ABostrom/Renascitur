import type { DateTuple } from './calendar';
import type { StateIndex, Who } from './person';

/** A `people.population` row of the timeseries table: one settlement on one date. */
export interface PopRow {
	date: DateTuple;
	entity: string;
	system: string;
	values: { notables: number; pop: Record<string, number[]> };
}

export interface Series {
	key: string; // a region, a settlement, or "other"
	points: { year: [number, number]; value: number }[];
}

/** Categorical colours run out at eight (dataviz rule): the rest fold into "Other". */
export const MAX_SERIES = 8;

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);

/**
 * Population over time, one point a year (the year's last row): `people` is notables plus the masses,
 * `notables` the named ones only. `group: 'region'` sums each region's settlements; a region id shows
 * that region's settlements. Biggest (by the last value) first; past `MAX_SERIES`, the smallest fold
 * into one "other" series.
 */
export function populationSeries(
	rows: PopRow[],
	regionOf: Record<string, string>,
	opts: { group: string; measure: 'people' | 'notables' }
): Series[] {
	const last = new Map<string, PopRow>(); // `${entity}|${age}|${year}` -> that year's last row
	for (const r of rows) {
		if (r.system !== 'people.population') continue;
		const k = `${r.entity}|${r.date[0]}|${r.date[1]}`;
		const prev = last.get(k);
		if (!prev || prev.date[2] <= r.date[2]) last.set(k, r);
	}
	const years = new Map<string, [number, number]>();
	const perPlace = new Map<string, Map<string, number>>(); // settlement -> year key -> value
	const keyOf = new Map<string, string>(); // settlement -> its series
	for (const r of last.values()) {
		const key = opts.group === 'region' ? regionOf[r.entity] ?? r.entity : regionOf[r.entity] === opts.group ? r.entity : null;
		if (key === null) continue;
		const yk = `${r.date[0]}|${r.date[1]}`;
		years.set(yk, [r.date[0], r.date[1]]);
		const v = (r.values.notables ?? 0) + (opts.measure === 'people' ? sum(Object.values(r.values.pop ?? {}).flat()) : 0);
		const s = perPlace.get(r.entity) ?? new Map<string, number>();
		s.set(yk, v);
		perPlace.set(r.entity, s);
		keyOf.set(r.entity, key);
	}
	const order = [...years.entries()].sort((a, b) => a[1][0] - b[1][0] || a[1][1] - b[1][1]);
	// A year with no row keeps the place's last value (0 before its first row), so a gap isn't a dip.
	const totals = new Map<string, number[]>();
	for (const [place, byYear] of perPlace) {
		const acc = totals.get(keyOf.get(place)!) ?? order.map(() => 0);
		let carried = 0;
		order.forEach(([yk], i) => {
			carried = byYear.get(yk) ?? carried;
			acc[i] += carried;
		});
		totals.set(keyOf.get(place)!, acc);
	}
	const series: Series[] = [...totals.entries()].map(([key, vals]) => ({
		key,
		points: order.map(([, year], i) => ({ year, value: vals[i] }))
	}));
	const final = (s: Series) => s.points[s.points.length - 1]?.value ?? 0;
	series.sort((a, b) => final(b) - final(a) || a.key.localeCompare(b.key));
	if (series.length <= MAX_SERIES) return series;
	const kept = series.slice(0, MAX_SERIES - 1);
	const rest = series.slice(MAX_SERIES - 1);
	kept.push({
		key: 'other',
		points: order.map(([, year], i) => ({ year, value: sum(rest.map((s) => s.points[i].value)) }))
	});
	return kept;
}

/** Axis ticks: whole numbers from 0 to at least `max` (and at least 1), about five of them, never repeated. */
export function niceTicks(max: number): number[] {
	const m = Math.max(1, Number.isFinite(max) ? max : 0);
	const raw = m / 4;
	const mag = 10 ** Math.floor(Math.log10(raw));
	const step = Math.max(1, [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => s >= raw) ?? raw);
	const out: number[] = [];
	for (let v = 0; out[out.length - 1] === undefined || out[out.length - 1] < m; v += step) {
		const t = Math.round(v);
		if (t !== out[out.length - 1]) out.push(t);
	}
	return out;
}

export interface Reign {
	holder: string;
	from: DateTuple;
	to: DateTuple | null;
	event: string;
}

/** Each office's holders in order, from the `holder` changes in `state_deltas`. */
export function successions(
	deltas: Iterable<{ date: DateTuple; entity: string; field: string; old?: unknown; new?: unknown; event: string }>,
	offices: Set<string>
): Map<string, Reign[]> {
	const out = new Map<string, Reign[]>();
	for (const d of deltas) {
		if (d.field !== 'holder' || !offices.has(d.entity)) continue;
		const reigns = out.get(d.entity) ?? [];
		const open = reigns[reigns.length - 1];
		if (open && open.to === null) open.to = d.date;
		if (typeof d.new === 'string') reigns.push({ holder: d.new, from: d.date, to: null, event: d.event });
		out.set(d.entity, reigns);
	}
	return out;
}

export interface HouseRow {
	id: string;
	name: string;
	seat: Who | null;
	rank: number;
	founded: DateTuple | null;
	extinct: DateTuple | null;
	office: string | null;
	head: Who | null;
	living: number;
	dormant: number; // faded back into the masses (S3): of the house, but no longer followed
	dead: number;
}

/** Every house at the end of the run: its seat, head, and how many of its blood live and have died. */
export function houseRows(ix: StateIndex): HouseRow[] {
	const counts = new Map<string, { living: number; dormant: number; dead: number }>();
	for (const e of ix.byId.values()) {
		if (e.kind !== 'person' || !e.fields.house) continue;
		const c = counts.get(e.fields.house) ?? { living: 0, dormant: 0, dead: 0 };
		if (e.status === 'dead') c.dead++;
		else if (e.status === 'dormant') c.dormant++;
		else c.living++;
		counts.set(e.fields.house, c);
	}
	const who = (id: string | null | undefined): Who | null => {
		const e = ix.get(id);
		return id ? { id, name: e?.fields.name ?? id, status: e?.status ?? 'unknown' } : null;
	};
	return [...ix.byId.values()]
		.filter((e) => e.kind === 'house')
		.map((h) => {
			const office = h.fields.headship ?? null;
			const c = counts.get(h.id) ?? { living: 0, dormant: 0, dead: 0 };
			return {
				id: h.id,
				name: h.fields.name ?? h.id,
				seat: who(h.fields.seat),
				rank: h.fields.rank ?? 0,
				founded: h.fields.founded ?? null,
				extinct: h.fields.extinct ?? null,
				office,
				head: who(ix.get(office)?.fields.holder),
				...c
			};
		})
		.sort((a, b) => b.rank - a.rank || a.name.localeCompare(b.name));
}
