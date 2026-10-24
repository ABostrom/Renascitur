import type { DateTuple } from './calendar';
import type { Geography } from './geography';
import { readTable, type Run } from './run';

/**
 * Polities on the Observatory (S8 spec §10, #159): the border map's colours and borders, wars as
 * timelines, and relations' stance and trust over time. Everything here reads the run's events and state
 * changes; nothing is recomputed.
 */
export interface PolityEvent {
	id: string;
	type: string;
	date: DateTuple;
	roles: Record<string, string[]>;
	payload: Record<string, unknown>;
}

export const SERIES = 8; // the theme's categorical colours (--series-1..8); past them, --series-other

/** A colour per polity, in id order (a polity's colour follows it, not its rank). */
export function colours(polities: string[]): Record<string, string> {
	return Object.fromEntries(
		[...new Set(polities)].sort().map((p, i) => [p, i < SERIES ? `var(--series-${i + 1})` : 'var(--series-other)'])
	);
}

/** The routes a border runs along: their two ends held by different polities (both held). */
export function borders(geo: Geography): Set<string> {
	const control = new Map(geo.places.map((p) => [p.id, p.control ?? null]));
	return new Set(
		geo.routes
			.filter((r) => {
				const [a, b] = r.ends.map((e) => control.get(e) ?? null);
				return a !== null && b !== null && a !== b;
			})
			.map((r) => r.id)
	);
}

export interface WarYear {
	date: DateTuple;
	winner: string;
	loser: string;
	place: string | null;
	event: string;
}

export interface War {
	id: string;
	aggressor: string;
	defender: string;
	date: DateTuple;
	event: string; // the declaration
	joined: { ally: string; side: string; date: DateTuple; event: string }[];
	years: WarYear[];
	falls: { polity: string; victor: string; date: DateTuple; event: string }[]; // (allies that fell, the war going on)
	end: { how: 'peace' | 'fallen' | 'ended'; winner: string | null; loser: string | null; date: DateTuple; event: string | null } | null;
}

/** The polity events the polities page shows. */
export const SHOWN = new Set([
	'polity.war_declared',
	'polity.joined',
	'polity.war_year',
	'polity.peace',
	'polity.fallen',
	'polity.treaty',
	'polity.treaty_ended',
	'polity.treaty_broken'
]);

const one = (e: PolityEvent, role: string) => e.roles[role]?.[0] ?? '';

/** Each war, from its declaration to its peace (or a leading side's fall), in the order they were declared.
 * `ended` (a war's `ended` state, by id) ends a war that ended with no event of its own: a side that led
 * it fell in another war. */
export function wars(events: PolityEvent[], ended: Record<string, DateTuple> = {}): War[] {
	const out = new Map<string, War>();
	for (const e of events) {
		const id = e.payload.war as string | undefined;
		if (!id) continue;
		if (e.type === 'polity.war_declared') {
			out.set(id, { id, aggressor: one(e, 'aggressor'), defender: one(e, 'defender'), date: e.date, event: e.id, joined: [], years: [], falls: [], end: null });
			continue;
		}
		const w = out.get(id);
		if (!w) continue;
		if (e.type === 'polity.joined') w.joined.push({ ally: one(e, 'ally'), side: one(e, 'side'), date: e.date, event: e.id });
		else if (e.type === 'polity.war_year')
			w.years.push({ date: e.date, winner: one(e, 'winner'), loser: one(e, 'loser'), place: (e.payload.place as string | null) ?? null, event: e.id });
		else if (e.type === 'polity.peace' && !w.end) w.end = { how: 'peace', winner: one(e, 'winner'), loser: one(e, 'loser'), date: e.date, event: e.id };
		else if (e.type === 'polity.fallen' && !w.end) {
			const fell = one(e, 'polity');
			if (fell === w.aggressor || fell === w.defender) w.end = { how: 'fallen', winner: one(e, 'victor'), loser: fell, date: e.date, event: e.id };
			else w.falls.push({ polity: fell, victor: one(e, 'victor'), date: e.date, event: e.id });
		}
	}
	for (const w of out.values())
		if (!w.end && ended[w.id]) w.end = { how: 'ended', winner: null, loser: null, date: ended[w.id], event: null };
	return [...out.values()];
}

export interface RelationDelta {
	date: DateTuple;
	entity: string;
	field: string;
	new: unknown;
	event: string;
}

export interface RelationPoint {
	date: DateTuple;
	stance: string | null;
	trust: number | null;
	event: string;
}

export interface Relation {
	id: string;
	a: string;
	b: string;
	points: RelationPoint[];
}

const RELATION_FIELDS = new Set(['a', 'b', 'stance', 'trust']);

/** Each relation's stance and trust over time: one point for each day either changed (deltas in order). */
export function relationSeries(deltas: RelationDelta[]): Record<string, Relation> {
	const out: Record<string, Relation> = {};
	for (const d of deltas) {
		if (!d.entity.startsWith('rel:') || !RELATION_FIELDS.has(d.field)) continue;
		const r = (out[d.entity] ??= { id: d.entity, a: '', b: '', points: [] });
		if (d.field === 'a' || d.field === 'b') {
			r[d.field] = d.new as string;
			continue;
		}
		const last = r.points.at(-1);
		const same = last && last.date.every((x, i) => x === d.date[i]);
		const point = same ? last : { date: d.date, stance: last?.stance ?? null, trust: last?.trust ?? null, event: d.event };
		if (d.field === 'stance') point.stance = d.new as string;
		else point.trust = d.new as number;
		if (!same) r.points.push(point);
	}
	return out;
}

/** The run's polity events (the ones the page shows), its relations' state changes, when its wars ended,
 * and the names of the polities in them, read once. */
export async function loadPolities(
	run: Run
): Promise<{ events: PolityEvent[]; relations: Record<string, Relation>; ended: Record<string, DateTuple>; names: Record<string, string> }> {
	const events: PolityEvent[] = [];
	const ids = new Set<string>();
	const ended: Record<string, DateTuple> = {};
	for await (const e of readTable(run, 'events'))
		if (SHOWN.has(e.type)) {
			events.push({ id: e.id, type: e.type, date: e.date, roles: e.roles ?? {}, payload: e.payload ?? {} });
			for (const members of Object.values((e.roles ?? {}) as Record<string, string[]>)) for (const m of members) ids.add(m);
			if (typeof e.payload?.place === 'string') ids.add(e.payload.place); // (a place taken in a war)
		}
	const deltas: RelationDelta[] = [];
	const every = new Map<string, string>(); // (every entity's latest name: a relation's parties are known only at its end)
	for await (const d of readTable(run, 'state_deltas')) {
		if (typeof d.entity !== 'string') continue;
		if (d.entity.startsWith('rel:') && RELATION_FIELDS.has(d.field)) {
			deltas.push({ date: d.date, entity: d.entity, field: d.field, new: d.new, event: d.event });
			if ((d.field === 'a' || d.field === 'b') && typeof d.new === 'string') ids.add(d.new);
		} else if (d.entity.startsWith('war:') && d.field === 'ended' && d.new) ended[d.entity] = d.new as DateTuple;
		else if (d.field === 'name' && typeof d.new === 'string') every.set(d.entity, d.new);
	}
	const names = Object.fromEntries([...ids].filter((id) => every.has(id)).map((id) => [id, every.get(id)!]));
	return { events, relations: relationSeries(deltas), ended, names };
}
