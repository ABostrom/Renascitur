import type { DateTuple } from './calendar';
import type { EntityChange } from './entity';

/** One record of a run's final state (`state.json.gz`). */
export interface StateEntity {
	id: string;
	kind: string;
	status: string;
	fields: Record<string, any>;
}

/** The final state by id, with each person's ambitions found by owner. Build once per run. */
export class StateIndex {
	readonly byId = new Map<string, StateEntity>();
	readonly ambitionsOf = new Map<string, StateEntity[]>();

	constructor(state: { entities: StateEntity[] }) {
		for (const e of state.entities) {
			this.byId.set(e.id, e);
			if (e.kind === 'ambition' && e.fields.owner) {
				const list = this.ambitionsOf.get(e.fields.owner) ?? [];
				list.push(e);
				this.ambitionsOf.set(e.fields.owner, list);
			}
		}
	}

	get(id: string | null | undefined): StateEntity | undefined {
		return id ? this.byId.get(id) : undefined;
	}
}

export interface Who {
	id: string;
	name: string;
	status: string;
}

export interface Copy {
	locus: string;
	from: 'mother' | 'father';
	variant: string;
	origin: 'founder' | 'mutation';
	where: string; // the founder group or settlement, or the birth event where it mutated
}

export interface PersonView {
	name: string;
	born: DateTuple | null; // (toy worlds keep a bare year, which isn't a date)
	parents: Who[];
	spouse: Who | null;
	children: Who[];
	siblings: Who[];
	house: Who | null;
	alleles: Copy[];
	ambitions: { id: string; class: string; state: string; target: Who | null; formed: DateTuple | null; resolved: DateTuple | null }[];
	ties: { id: string; other: Who; kind: string; strength: number; since: DateTuple | null; ended: DateTuple | null }[];
}

function who(ix: StateIndex, id: string): Who {
	const e = ix.get(id);
	return { id, name: e?.fields.name ?? id, status: e?.status ?? 'unknown' };
}

/** A genome's copies, mother's first (S3: `"variant@origin"`, origin `f:<group>` for founder stock, else
 * the birth event where the copy mutated). */
export function copies(genome: Record<string, string[]> | null | undefined): Copy[] {
	const out: Copy[] = [];
	for (const locus of Object.keys(genome ?? {}).sort()) {
		genome![locus].forEach((copy, i) => {
			const at = copy.indexOf('@');
			const variant = at < 0 ? copy : copy.slice(0, at);
			const origin = at < 0 ? '' : copy.slice(at + 1);
			out.push({
				locus,
				from: i === 0 ? 'mother' : 'father',
				variant,
				origin: origin.startsWith('f:') ? 'founder' : 'mutation',
				where: origin.startsWith('f:') ? origin.slice(2) : origin
			});
		});
	}
	return out;
}

/** Everything the person page shows about someone, from the final state. */
export function personView(ix: StateIndex, id: string): PersonView {
	const me = ix.get(id);
	const f = me?.fields ?? {};
	const parents = [f.mother, f.father].filter((p): p is string => !!p).map((p) => who(ix, p));
	const siblings = new Set<string>();
	for (const p of parents) for (const c of ix.get(p.id)?.fields.children ?? []) if (c !== id) siblings.add(c);
	const ambitions = (ix.ambitionsOf.get(id) ?? [])
		.map((a) => ({
			id: a.id,
			class: a.fields.class,
			state: a.fields.state,
			target: a.fields.target ? who(ix, a.fields.target) : null,
			formed: a.fields.formed ?? null,
			resolved: a.fields.resolved ? a.fields.resolved[0] : null
		}))
		.sort((a, b) => cmp(a.formed, b.formed) || a.id.localeCompare(b.id));
	const ties = (f.ties ?? [])
		.map((t: string) => ix.get(t))
		.filter((t: StateEntity | undefined): t is StateEntity => !!t)
		.map((t: StateEntity) => ({
			id: t.id,
			other: who(ix, t.fields.a === id ? t.fields.b : t.fields.a),
			kind: t.fields.kind,
			strength: t.fields.strength,
			since: t.fields.since ?? null,
			ended: t.fields.ended ?? null
		}));
	return {
		name: f.name ?? id,
		born: Array.isArray(f.born) && f.born.length === 3 ? (f.born as DateTuple) : null,
		parents,
		spouse: f.spouse ? who(ix, f.spouse) : null,
		children: (f.children ?? []).map((c: string) => who(ix, c)),
		siblings: [...siblings].map((s) => who(ix, s)),
		house: f.house ? who(ix, f.house) : null,
		alleles: copies(f.genome),
		ambitions,
		ties
	};
}

/** A race id without its prefix (`r:human` -> `human`); the catalogue has no display names yet. */
export function raceName(race: string | null | undefined): string | null {
	return race ? race.slice(race.indexOf(':') + 1) : null;
}

/**
 * The moments the "as of" control steps through: the end of every year in which this record changed,
 * from its first change (its creation) to the end of the run. Dates keep their age, so a life that
 * spans two ages steps across both. Empty when nothing was logged.
 */
export function moments(changes: EntityChange[], end: DateTuple): DateTuple[] {
	const years = new Map<string, DateTuple>();
	for (const c of changes) if (!c.bulk) years.set(`${c.date[0]}:${c.date[1]}`, [c.date[0], c.date[1], 9999]);
	if (years.size === 0) return [];
	years.set(`${end[0]}:${end[1]}`, [end[0], end[1], 9999]);
	return [...years.values()].sort(cmp);
}

const indexes = new WeakMap<object, Promise<StateIndex>>();

/** One StateIndex per run, built on first use; a failed load is forgotten so it can be retried. */
export function stateIndexOf(run: object, load: () => Promise<{ entities: StateEntity[] }>): Promise<StateIndex> {
	let p = indexes.get(run);
	if (!p) {
		p = load().then((s) => new StateIndex(s));
		p.catch(() => indexes.delete(run));
		indexes.set(run, p);
	}
	return p;
}

function cmp(a: DateTuple | null, b: DateTuple | null): number {
	if (!a || !b) return a ? 1 : b ? -1 : 0;
	return a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
}

/**
 * A record's fields as they stood on `date`, from its final fields and its logged changes: for each
 * changed field, the last change on or before the date, else the first change's old value.
 */
export function asOf(final: Record<string, unknown>, changes: EntityChange[], date: DateTuple): Record<string, unknown> {
	const out = { ...final };
	const byField = new Map<string, EntityChange[]>();
	for (const c of changes) {
		if (c.bulk) continue;
		const list = byField.get(c.field) ?? [];
		list.push(c);
		byField.set(c.field, list);
	}
	for (const [field, list] of byField) {
		const sorted = [...list].sort((a, b) => cmp(a.date, b.date));
		const before = sorted.filter((c) => cmp(c.date, date) <= 0);
		out[field] = before.length ? (before[before.length - 1].new ?? null) : (sorted[0].old ?? null);
	}
	return out;
}
