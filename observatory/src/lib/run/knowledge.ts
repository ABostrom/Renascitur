import type { DateTuple } from './calendar';
import type { RunSource } from './source';

/**
 * World knowledge (S6 epistemics, #106): what a run's world believes, beside what happened.
 *
 * `renasci claims <run>` writes `analysis/claims.json`: every claim the run's beliefs carried, grouped
 * by topic (the question it answers: who killed X, whose doing was E), each judged offline against the
 * event log (true, half, false) with its holders at the end, its share of each settlement's masses, the
 * claim it drifted from in a retelling (`parent`), and the times it was told as a lie.
 */
export interface Claim {
	key: string;
	claim: { pred: string; args: Record<string, string> };
	text: string;
	truth: 'true' | 'half' | 'false' | 'unknown' | string; // unknown: nothing in the log to judge it by
	basis: string[]; // the events the verdict rests on
	holders: number;
	shares: Record<string, number>; // settlement -> share of its masses
	parent: string | null;
	first: DateTuple | null; // null: only ever in a town's talk, set there directly
	lies: number;
}

export interface Topic {
	topic: string;
	about: string;
	about_type: string;
	about_name: string;
	holders: number; // holdings, summed over its claims (one person can hold two rival claims)
	people: number; // the notables holding any of them
	claims: Claim[];
}

export interface Claims {
	run: string;
	topics: Topic[];
}

/** The run's `analysis/claims.json`, or null when `renasci claims` hasn't been run for it. */
export async function loadClaims(source: RunSource, run: string): Promise<Claims | null> {
	const path = `${run}/analysis/claims.json`;
	if (!(await source.has(path))) return null;
	return JSON.parse(await source.text(path)) as Claims;
}

export interface LineageRow {
	claim: Claim;
	depth: number;
}

/**
 * A topic's claims as a tree, flattened depth first: each under the claim it drifted from. A claim
 * whose parent isn't in the topic (no longer held anywhere) is a root of its own. Order within a level
 * is the report's (most held first).
 */
export function lineage(topic: Topic): LineageRow[] {
	const keys = new Set(topic.claims.map((c) => c.key));
	const children = new Map<string | null, Claim[]>();
	for (const c of topic.claims) {
		const p = c.parent && keys.has(c.parent) ? c.parent : null;
		children.set(p, [...(children.get(p) ?? []), c]);
	}
	const out: LineageRow[] = [];
	const seen = new Set<string>();
	const walk = (parent: string | null, depth: number) => {
		for (const c of children.get(parent) ?? []) {
			if (seen.has(c.key)) continue; // (a drift cycle: shown once)
			seen.add(c.key);
			out.push({ claim: c, depth });
			walk(c.key, depth + 1);
		}
	};
	walk(null, 0);
	for (const c of topic.claims) if (!seen.has(c.key)) out.push({ claim: c, depth: 0 });
	return out;
}

/** For each settlement, the topic's claim with the largest share of its masses (ties: the lower key). */
export function dominant(topic: Topic): Record<string, { claim: Claim; share: number }> {
	const out: Record<string, { claim: Claim; share: number }> = {};
	for (const c of topic.claims) {
		for (const [place, share] of Object.entries(c.shares)) {
			const best = out[place];
			if (!best || share > best.share || (share === best.share && c.key < best.claim.key)) out[place] = { claim: c, share };
		}
	}
	return out;
}
