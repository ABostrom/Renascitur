import type { EventIndex } from './index';
import { readTable } from './run';

/** A node in the cause graph: an event, an activation, a ripple (the author) or a pin (canon). */
export interface CauseNode {
	kind: string;
	ref: string;
}

export const nodeKey = (n: CauseNode) => `${n.kind}:${n.ref}`;

export interface CauseGraph {
	parents(n: CauseNode): CauseNode[];
	children(n: CauseNode): CauseNode[];
	label(n: CauseNode): string;
}

/**
 * The cause graph of a run, walkable both ways.
 *
 * - An event's parents are its recorded causes, its source (a ripple or pin), and the activation it
 *   came from.
 * - An activation's parents are its own causes (a follow-up names the event and activation that
 *   scheduled it).
 * - Children are the reverse.
 */
export async function buildCauseGraph(index: EventIndex): Promise<CauseGraph> {
	const run = index.run;
	const activations = new Map<string, { system: string; date: [number, number, number]; causes: [string, string][] }>();
	for await (const a of readTable(run, 'activations')) activations.set(a.activation, a);

	const kids = new Map<string, CauseNode[]>();
	const addChild = (parent: CauseNode, child: CauseNode) => {
		const k = nodeKey(parent);
		let list = kids.get(k);
		if (!list) kids.set(k, (list = []));
		list.push(child);
	};

	const eventParents = (i: number): CauseNode[] => {
		const e = index.row(i);
		const out: CauseNode[] = e.causes.map(([kind, ref]: [string, string]) => ({ kind, ref }));
		if (e.source && (e.source[0] === 'ripple' || e.source[0] === 'pin')) {
			const src = { kind: e.source[0], ref: e.source[1] };
			if (!out.some((p) => nodeKey(p) === nodeKey(src))) out.push(src);
		}
		if (e.activation) out.push({ kind: 'activation', ref: e.activation });
		return out;
	};

	for (let i = 0; i < index.count; i++) {
		const child = { kind: 'event', ref: index.ids[i] };
		for (const p of eventParents(i)) addChild(p, child);
	}
	for (const [id, a] of activations) {
		for (const [kind, ref] of a.causes) addChild({ kind, ref: ref.split('#')[0] }, { kind: 'activation', ref: id });
	}

	const cal = run.calendar;
	return {
		parents(n) {
			if (n.kind === 'event') {
				const i = index.position.get(n.ref);
				return i === undefined ? [] : eventParents(i);
			}
			if (n.kind === 'activation') {
				const a = activations.get(n.ref.split('#')[0]);
				return a ? a.causes.map(([kind, ref]) => ({ kind, ref })) : [];
			}
			return []; // ripples and pins are where explanation stops: the author, or canon
		},
		children(n) {
			return kids.get(nodeKey(n)) ?? [];
		},
		label(n) {
			if (n.kind === 'event') {
				const i = index.position.get(n.ref);
				if (i === undefined) return `event ${n.ref} (not in this run)`;
				const e = index.row(i);
				return `${e.type} · ${cal.format(e.date, 'day')}`;
			}
			if (n.kind === 'activation') {
				const a = activations.get(n.ref.split('#')[0]);
				const scope = n.ref.includes('#') ? ` in ${n.ref.split('#')[1]}` : '';
				return a ? `${a.system}${scope} · ${cal.format(a.date, 'day')}` : `activation ${n.ref}`;
			}
			if (n.kind === 'ripple') return `ripple ${n.ref} (the author's hand)`;
			if (n.kind === 'pin') return `pin ${n.ref} (canon)`;
			return `${n.kind} ${n.ref}`;
		}
	};
}
