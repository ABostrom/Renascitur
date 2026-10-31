import type { DateTuple } from './calendar';
import { readTable, type Run } from './run';

/**
 * Objects on the Observatory (S9 spec §6, #109): each masterwork's biography, read from the run's `object.*`
 * events. Its making, every change of hands (given, inherited, lost, found, stolen, unearthed), its deeds and
 * its name; nothing is recomputed.
 */
export interface ObjectEvent {
	id: string;
	type: string;
	date: DateTuple;
	roles: Record<string, string[]>;
	payload: Record<string, unknown>;
	place: string | null;
}

export type Kind = 'made' | 'unearthed' | 'given' | 'inherited' | 'found' | 'stolen' | 'lost' | 'destroyed' | 'deed' | 'named';

export interface Beat {
	kind: Kind;
	date: DateTuple;
	event: string;
	who: string | null; // (the owner after it, or the maker, or the hero of a deed)
	from: string | null;
	place: string | null;
	detail: string | null; // (a deed's kind, a name, a price)
	cause: string | null; // (a deed's own event: the duel won, the death escaped)
}

export interface Biography {
	id: string;
	type: string | null;
	material: string | null;
	quality: number | null;
	maker: string | null;
	made: DateTuple | null;
	name: string | null;
	owner: string | null;
	owners: { who: string | null; how: Kind; date: DateTuple; event: string }[];
	deeds: number;
	lost: DateTuple | null;
	destroyed: DateTuple | null;
	beats: Beat[];
}

const one = (e: ObjectEvent, role: string) => e.roles[role]?.[0] ?? null;

/** The object event kinds, by event type. */
const KINDS: Record<string, Kind> = {
	'object.made': 'made',
	'object.unearthed': 'unearthed',
	'object.given': 'given',
	'object.inherited': 'inherited',
	'object.found': 'found',
	'object.stolen': 'stolen',
	'object.lost': 'lost',
	'object.destroyed': 'destroyed',
	'object.deed': 'deed',
	'object.named': 'named'
};

/** Every object's biography, by id, from its events (in log order). `fields` (an object's recorded `type`,
 * `material`, `quality`, `name`) fills what no event says: a planted object's make. */
export function biographies(events: ObjectEvent[], fields: Record<string, Record<string, unknown>> = {}): Map<string, Biography> {
	const out = new Map<string, Biography>();
	for (const e of events) {
		const kind = KINDS[e.type];
		const id = one(e, 'object');
		if (!kind || !id) continue;
		const b =
			out.get(id) ??
			({ id, type: null, material: null, quality: null, maker: null, made: null, name: null, owner: null, owners: [], deeds: 0, lost: null, destroyed: null, beats: [] } as Biography);
		out.set(id, b);
		let who: string | null = null;
		let from: string | null = null;
		let detail: string | null = null;
		let cause: string | null = null;
		const place = (typeof e.payload.place === 'string' ? e.payload.place : null) ?? e.place;
		switch (kind) {
			case 'made':
				b.type = (e.payload.type as string) ?? null;
				b.material = (e.payload.material as string) ?? null;
				b.quality = (e.payload.quality as number) ?? null;
				b.maker = who = one(e, 'maker');
				b.made = e.date;
				break;
			case 'unearthed':
			case 'found':
				who = one(e, 'finder');
				break;
			case 'given':
				who = one(e, 'owner');
				from = one(e, 'giver');
				detail = e.payload.price ? `for ${e.payload.price}` : null;
				break;
			case 'inherited':
				who = one(e, 'owner');
				from = one(e, 'from');
				break;
			case 'stolen':
				who = one(e, 'thief');
				from = one(e, 'from');
				break;
			case 'lost':
				from = one(e, 'owner');
				break;
			case 'deed':
				who = one(e, 'owner');
				detail = (e.payload.kind as string) ?? null;
				cause = (e.payload.deed as string) ?? null;
				b.deeds += 1;
				break;
			case 'named':
				detail = b.name = (e.payload.name as string) ?? null;
				break;
		}
		if (['unearthed', 'given', 'inherited', 'found', 'stolen', 'lost', 'destroyed'].includes(kind)) {
			b.owner = who;
			b.lost = kind === 'lost' ? e.date : kind === 'found' || kind === 'stolen' ? null : b.lost;
			if (kind === 'destroyed') b.destroyed = e.date;
			if (kind !== 'destroyed') b.owners.push({ who, how: kind, date: e.date, event: e.id });
		}
		b.beats.push({ kind, date: e.date, event: e.id, who, from, place, detail, cause });
	}
	for (const b of out.values()) {
		const f = fields[b.id] ?? {};
		b.type ??= (f.type as string) ?? null;
		b.material ??= (f.material as string) ?? null;
		b.quality ??= (f.quality as number) ?? null;
		b.name ??= (f.name as string) ?? null;
	}
	return out;
}

/** The run's object events, and the names of everyone and everywhere in them, read once. */
export async function loadObjects(
	run: Run
): Promise<{ events: ObjectEvent[]; names: Record<string, string>; fields: Record<string, Record<string, unknown>> }> {
	const events: ObjectEvent[] = [];
	const ids = new Set<string>();
	for await (const e of readTable(run, 'events'))
		if (typeof e.type === 'string' && e.type in KINDS) {
			events.push({ id: e.id, type: e.type, date: e.date, roles: e.roles ?? {}, payload: e.payload ?? {}, place: e.place ?? null });
			for (const members of Object.values((e.roles ?? {}) as Record<string, string[]>)) for (const m of members) ids.add(m);
			if (typeof e.payload?.place === 'string') ids.add(e.payload.place);
			if (typeof e.place === 'string') ids.add(e.place);
		}
	const names: Record<string, string> = {};
	const fields: Record<string, Record<string, unknown>> = {}; // (objects' recorded make, for those no event describes)
	const OWN = new Set(['type', 'material', 'quality', 'name']);
	if (ids.size)
		for await (const d of readTable(run, 'state_deltas')) {
			if (!ids.has(d.entity)) continue;
			if (d.field === 'name' && typeof d.new === 'string') names[d.entity] = d.new;
			if (OWN.has(d.field) && d.new !== null) (fields[d.entity] ??= {})[d.field] = d.new;
		}
	return { events, names, fields };
}
