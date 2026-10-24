import type { Calendar, DateTuple } from './calendar';
import type { RunListing } from './run';

/**
 * Authoring a ripple in the Observatory (#110): the form's fields turned into a request for the
 * launcher's `/api/ripple` (which replays it as a branch of the run and diffs it), and the runs as a
 * tree of branches.
 */
export const KINDS = ['protect', 'doom', 'favour', 'luck', 'inject', 'plant', 'structural'] as const;
export type Kind = (typeof KINDS)[number];

/** What each kind does, for the form. */
export const ABOUT: Record<Kind, string> = {
	protect: 'keep them alive until a date: a death becomes a near miss',
	doom: 'they die on the date, by an in-world cause',
	favour: 'their schemes go better until a date: steps likelier, exposure less likely',
	luck: 'their own draws are re-rolled until a date: a change of fortune',
	inject: "a world's scripted event at a place (e.g. the ward failure)",
	plant: "a rumour in a town's talk",
	structural: 'the world changes shape: a route closes or reopens'
};

export interface RippleForm {
	kind: Kind | string;
	target: string;
	date: string;
	until?: string;
	by?: string;
	script?: string;
	claim?: string; // JSON: {"pred", "args"}
	share?: string;
	open?: 'closed' | 'open' | '';
	days?: string;
	why?: string;
	name?: string;
}

export interface RippleRequest {
	run: string;
	kind: string;
	target: string;
	date: string;
	params?: Record<string, unknown>;
	name?: string;
}

/** The end of a date given as a year ("4A 9": its last day), else the day itself. */
function endOf(cal: Calendar, text: string): DateTuple {
	const d = cal.parse(text);
	return text.trim().split(/\s+/).length === 2 ? [d[0], d[1], cal.daysPerYear - 1] : d;
}

/** The launcher request for a form, or an Error saying what's missing (as the engine would refuse it). */
export function rippleRequest(cal: Calendar, run: string, f: RippleForm): RippleRequest {
	if (!f.target.trim()) throw new Error('a ripple needs a target');
	const date = cal.parse(f.date); // (throws on a date the calendar can't read)
	const params: Record<string, unknown> = {};
	if (f.kind === 'protect' || f.kind === 'favour' || f.kind === 'luck') {
		if (!f.until?.trim()) throw new Error(`a ${f.kind} ripple needs an until date`);
		const until = endOf(cal, f.until);
		if (cal.sortKey(until) < cal.sortKey(date)) throw new Error('until must be on or after the date');
		params.until = until;
	}
	if (f.kind === 'favour') {
		const by = Number(f.by?.trim() || '0.3');
		if (!(by > 0 && by <= 1)) throw new Error('favour is by a number in (0, 1]');
		params.by = by;
	}
	if (f.kind === 'inject' && f.script) params.script = f.script;
	if (f.kind === 'plant') {
		try {
			params.claim = JSON.parse(f.claim ?? '');
		} catch {
			throw new Error('the claim must be JSON: {"pred": "killed", "args": {"victim": …, "by": …}}');
		}
		if (f.share) params.share = Number(f.share);
	}
	if (f.kind === 'structural') {
		if (f.open === 'closed') params.open = false;
		if (f.open === 'open') params.open = true;
		if (f.days) params.days = Number(f.days);
		if (!('open' in params) && !('days' in params)) throw new Error('say whether the route closes, reopens or takes other days');
	}
	if (f.why && (f.kind === 'structural' || f.kind === 'inject')) params.why = f.why;
	const out: RippleRequest = { run, kind: f.kind, target: f.target.trim(), date: f.date.trim() };
	if (Object.keys(params).length) out.params = params;
	if (f.name?.trim()) out.name = f.name.trim();
	return out;
}

export interface RecipeRipple {
	id: string;
	kind: string;
	target: string;
	date: string;
	params?: Record<string, unknown>;
}

export interface Branch {
	run: RunListing;
	depth: number;
	parent: string | null;
	added: RecipeRipple[]; // the ripples it has that its parent doesn't
}

/** The runs as a tree: each under the run it was replayed (forked) from or branched off, depth first, by name. */
export function branches(runs: RunListing[]): Branch[] {
	const names = new Set(runs.map((r) => r.name));
	const parentOf = (r: RunListing) => {
		const meta = r.manifest.meta as { ripple_of?: { run: string }; latch_of?: { run: string } };
		// (a branch run from the start, when its parent had no checkpoint early enough, says so in ripple_of/latch_of)
		const p = r.manifest.meta.replayed_from?.run ?? meta.ripple_of?.run ?? meta.latch_of?.run ?? null;
		return p && names.has(p) && p !== r.name ? p : null;
	};
	const ripples = (r: RunListing | undefined) => ((r?.manifest.meta.recipe?.ripple ?? []) as RecipeRipple[]);
	const byName = new Map(runs.map((r) => [r.name, r]));
	const children = new Map<string | null, RunListing[]>();
	for (const r of runs) children.set(parentOf(r), [...(children.get(parentOf(r)) ?? []), r]);
	const out: Branch[] = [];
	const seen = new Set<string>();
	const walk = (parent: string | null, depth: number) => {
		for (const r of [...(children.get(parent) ?? [])].sort((a, b) => a.name.localeCompare(b.name))) {
			if (seen.has(r.name)) continue;
			seen.add(r.name);
			const mine = parent ? new Set(ripples(byName.get(parent)).map((x) => JSON.stringify(x))) : new Set<string>();
			out.push({ run: r, depth, parent, added: ripples(r).filter((x) => !mine.has(JSON.stringify(x))) });
			walk(r.name, depth + 1);
		}
	};
	walk(null, 0);
	for (const r of runs) if (!seen.has(r.name)) out.push({ run: r, depth: 0, parent: null, added: ripples(r) }); // (a cycle)
	return out;
}
