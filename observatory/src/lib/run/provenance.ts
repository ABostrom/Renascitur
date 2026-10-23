import type { DateTuple } from './calendar';
import type { StateIndex } from './person';

/**
 * Where a person's beliefs came from, and what they move them to do (S13, #107; S6 spec §3).
 *
 * An event's causes are its own plus its activation's (sorted by id), so the walk picks the cause by
 * kind, not position: a telling follows the teller's belief event; a lie, a perception or a correction
 * the event behind it (never the ripple that set the activation off, if anything else is there); a rumour
 * from the road, the news that brought it.
 *
 * A belief records the event that put it in its holder's head (`from`). Walking back from there:
 * a telling's cause is the teller's own belief event, so the walk passes each telling in turn until it
 * reaches what the first holder perceived (and the event they saw), a correction or a rumour heard from
 * the town, or a lie (and the scheme's step that told it). A want is an active ambition; one born of a
 * grievance carries that grievance's event, which in a world with beliefs is the belief behind it.
 */
export type Lookup = (id: string) => any | undefined;

export interface Step {
	event: any;
	lie: boolean; // a lie told: the walk stops here (and shows what told it)
	origin: boolean; // where the belief began: an event outside the belief machinery, or news from another town
	more?: boolean; // the walk was cut short: there is more before this
}

export interface HeldBelief {
	key: string;
	claim: { pred: string; args: Record<string, string> };
	text: string;
	conf: number;
	since: DateTuple | null;
	secret: boolean;
	lie: boolean; // somewhere along the way, someone lied
	trace: Step[];
}

export interface Motive {
	ambition: string;
	class: string;
	target: string | null;
	belief: string | null; // the belief behind it, if it was born of one
	trace: Step[];
}

const MAX_STEPS = 24;
const BEHIND = new Set(['belief.perceived', 'belief.corrected']); // (one step on: what was seen, or what exposed it)

/** The event cause the walk follows from `e` (see above), or undefined. */
function causeOf(e: any, lookup: Lookup): any | undefined {
	const causes = (e.causes ?? [])
		.filter((c: [string, string]) => c[0] === 'event')
		.map((c: [string, string]) => lookup(c[1]))
		.filter((c: any) => c);
	const is = (prefix: string) => (c: any) => String(c.type).startsWith(prefix);
	const honest = e.type === 'belief.told' && e.payload?.intent !== 'lie';
	if (honest) return causes.find(is('belief.')) ?? causes[0];
	if (e.type === 'belief.heard') return causes.find((c: any) => c.type === 'belief.news_arrived') ?? causes[0];
	return causes.find((c: any) => !is('ripple.')(c) && !is('belief.')(c)) ?? causes.find((c: any) => !is('ripple.')(c)) ?? causes[0];
}

/** A claim read out with the names of the people (and the kind of event) in it. */
export function claimText(claim: { pred: string; args: Record<string, string> }, ix: StateIndex, lookup: Lookup): string {
	const name = (id: string) => ix.get(id)?.fields.name ?? id;
	const what = (id: string) => {
		const e = lookup(id);
		return e ? `the ${String(e.type).replace(/[._]/g, ' ')}` : 'it';
	};
	const a = claim.args;
	if (claim.pred === 'killed') return `${name(a.victim)} was killed by ${name(a.by)}`;
	if (claim.pred === 'caused') return `${name(a.by)} caused ${what(a.event)}`;
	if (claim.pred === 'fault') return `${what(a.event)} was the fault of ${name(a.party)}`;
	return `${claim.pred}(${Object.values(a).map(name).join(', ')})`;
}

/** The walk back from a belief event to where it began. */
export function trace(lookup: Lookup, from: string): Step[] {
	const steps: Step[] = [];
	const seen = new Set<string>();
	let e: any = lookup(from);
	while (e && !seen.has(e.id)) {
		if (steps.length === MAX_STEPS) {
			steps[steps.length - 1].more = true;
			break;
		}
		seen.add(e.id);
		const belief = String(e.type).startsWith('belief.');
		const lie = e.type === 'belief.told' && e.payload?.intent === 'lie';
		const step: Step = { event: e, lie, origin: !belief || e.type === 'belief.news_arrived' };
		steps.push(step);
		if (step.origin) break;
		const next = causeOf(e, lookup);
		if (lie || BEHIND.has(e.type)) {
			// (one step on, and stop: the scheme's step that told the lie, what was seen, what exposed it)
			if (next && !seen.has(next.id)) steps.push({ event: next, lie: false, origin: true });
			else step.origin = true;
			break;
		}
		if (!next) step.origin = true; // (nothing recorded before it)
		e = next;
	}
	return steps;
}

/** A person's beliefs (their `beliefs` field), firmest first, each traced to where it began. */
export function beliefsOf(beliefs: Record<string, any> | null | undefined, ix: StateIndex, lookup: Lookup): HeldBelief[] {
	return Object.entries(beliefs ?? {})
		.map(([key, b]) => {
			const steps = b.from ? trace(lookup, b.from) : [];
			return {
				key,
				claim: b.claim,
				text: claimText(b.claim, ix, lookup),
				conf: b.conf,
				since: b.since ?? null,
				secret: !!b.secret,
				lie: steps.some((s) => s.lie),
				trace: steps
			};
		})
		.sort((a, b) => b.conf - a.conf || a.key.localeCompare(b.key));
}

/**
 * Why a person wants what they want: each active ambition born of an event (a grievance's), traced from
 * that event, with the belief behind it: that the target killed the one the grievance is about. An
 * ambition born of a drive (status, rivalry) has no belief behind it and isn't listed.
 */
export function motives(person: string, ix: StateIndex, beliefs: Record<string, any> | null | undefined, lookup: Lookup): Motive[] {
	const held = Object.entries(beliefs ?? {});
	const out: Motive[] = [];
	const grievances: any[] = ix.get(person)?.fields.grievances ?? [];
	for (const a of ix.ambitionsOf.get(person) ?? []) {
		if (a.fields.state !== 'active') continue;
		const born = a.fields.born_of as [string, string] | undefined;
		if (born?.[0] !== 'event') continue; // (a drive's ambition: no belief behind it)
		const target = a.fields.target ?? null;
		// The grievance it answers names who died; the belief is that the target killed them.
		const g = grievances.find((g) => g.answered === a.id) ?? grievances.find((g) => g.event === born[1] && g.against === target);
		const match = held.find(
			([, b]) => b.claim?.pred === 'killed' && b.claim.args.by === target && (!g?.about || b.claim.args.victim === g.about)
		);
		out.push({ ambition: a.id, class: a.fields.class, target, belief: match?.[0] ?? null, trace: trace(lookup, born[1]) });
	}
	return out;
}
