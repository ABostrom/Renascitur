import type { RippleRequest } from './ripple';
import type { DateTuple } from './calendar';
import type { Manifest } from './run';
import type { RunSource } from './source';
import type { Arc, Stories } from './stories';

/** A latch point (`renasci latch`, S7 §8): a moment a small change would have mattered, and its what-if. */
export interface LatchPoint {
	rank: number;
	kind: 'died_unfulfilled' | 'near_miss';
	person: string;
	date: DateTuple;
	score: number;
	potential: number;
	why: string;
	means: string;
	ambitions?: string[];
	age?: number;
	margin?: number;
	after?: number;
	event?: string;
	hinge?: string;
	ripple: { kind: string; date: DateTuple; target: string; params: { until?: DateTuple } };
}

export interface Latch {
	run: string;
	points: LatchPoint[];
}

/** The run's `analysis/latch.json`, or null when `renasci latch` hasn't been run for it. */
export async function loadLatch(source: RunSource, run: string): Promise<Latch | null> {
	const path = `${run}/analysis/latch.json`;
	if (!(await source.has(path))) return null;
	return JSON.parse(await source.text(path)) as Latch;
}

/** The what-ifs launched from `run`, by the rank of the point they tried (each `meta.latch_of`). */
export function whatIfsOf(runs: { name: string; manifest: Manifest }[], run: string): Map<number, string[]> {
	const out = new Map<number, string[]>();
	for (const r of runs) {
		const of = r.manifest.meta.latch_of as { run?: string; rank?: number } | undefined;
		if (!of || of.run !== run || typeof of.rank !== 'number') continue;
		out.set(of.rank, [...(out.get(of.rank) ?? []), r.name].sort());
	}
	return out;
}

export interface Adjust {
	kind?: string;
	date?: string;
	until?: string;
}

/** The command that launches a point by hand (when the server wasn't started with --allow-launch). */
export function latchCommand(run: string, rank: number, adjust: Adjust): string {
	const parts = [`uv run renasci latch runs/${run} --launch ${rank}`];
	if (adjust.kind) parts.push(`--kind ${adjust.kind}`);
	if (adjust.date) parts.push(`--date '${adjust.date}'`);
	if (adjust.until) parts.push(`--until '${adjust.until}'`);
	return parts.join(' ');
}

/** How a what-if's stories differ from its baseline's: arcs only one side has (by ambition), and arcs
 * both have that ended differently. Ambitions formed before the ripple keep their ids. */
export function compareArcs(base: Stories, variant: Stories) {
	const b = new Map(base.arcs.map((a) => [a.ambition, a]));
	const v = new Map(variant.arcs.map((a) => [a.ambition, a]));
	const bySalience = (x: Arc, y: Arc) => y.salience - x.salience || (x.id < y.id ? -1 : 1);
	const changed: [Arc, Arc][] = [];
	let shared = 0;
	for (const [amb, a] of b) {
		const other = v.get(amb);
		if (!other) continue;
		shared++;
		if (other.outcome !== a.outcome || other.span[1] !== a.span[1]) changed.push([a, other]);
	}
	changed.sort((x, y) => bySalience(x[0], y[0]));
	return {
		shared,
		changed,
		onlyBaseline: [...b.values()].filter((a) => !v.has(a.ambition)).sort(bySalience),
		onlyVariant: [...v.values()].filter((a) => !b.has(a.ambition)).sort(bySalience)
	};
}

export interface Job {
	id: number;
	state: 'running' | 'done' | 'failed';
	job?: 'latch' | 'run' | 'replay' | 'propose' | 'ripple' | StoryKind | 'check'; // a latch what-if, a run or replay from a recipe, a proposed note, an authored ripple, a story document, a canon check
	file?: string | null; // a story document or check report the job wrote: a path inside the runs folder
	subject?: string;
	of?: string;
	pov?: string | null;
	recipe?: string;
	run: string;
	rank: number;
	kind: string | null;
	date: string | null;
	until: string | null;
	returncode: number | null;
	output: string;
	variant: string | null;
	warning?: string | null; // done, but the diff found unexplained divergence (exit 3)
}

/** The server's launcher (`renasci observe --allow-launch`): whether it is on, the jobs, a launch. */
export const launcher = {
	async enabled(): Promise<boolean> {
		try {
			const r = await fetch('/api/capabilities');
			return r.ok && (await r.json()).launch === true;
		} catch {
			return false;
		}
	},
	async jobs(): Promise<Job[]> {
		const r = await fetch('/api/jobs');
		return r.ok ? r.json() : [];
	},
	async launch(run: string, rank: number, adjust: Adjust): Promise<Job> {
		const body: Record<string, unknown> = { run, rank };
		for (const [k, v] of Object.entries(adjust)) if (v) body[k] = v;
		return post('/api/launch', body);
	},
	/** The recipes the server may run (its recipes folder). */
	async recipes(): Promise<Recipe[]> {
		const r = await fetch('/api/recipes');
		return r.ok ? r.json() : [];
	},
	run(recipe: string): Promise<Job> {
		return post('/api/run', { recipe });
	},
	replay(run: string, recipe: string): Promise<Job> {
		return post('/api/replay', { run, recipe });
	},
	/** A ripple authored on a run, replayed as a branch of it and diffed (#110). */
	ripple(req: RippleRequest): Promise<Job> {
		return post('/api/ripple', req);
	},
	/** Whether this server can write proposed notes to a vault (the launcher is on and it has one). */
	async canPropose(): Promise<boolean> {
		try {
			const r = await fetch('/api/capabilities');
			return r.ok && (await r.json()).propose === true;
		} catch {
			return false;
		}
	},
	/** Propose a run's person or event as a `canon: proposed` note, keeping the causes ticked (#105). */
	propose(run: string, entity: string, causes: string[] = []): Promise<Job> {
		return post('/api/propose', { run, entity, causes });
	},
	/** A context pack, chronicle or campaign brief of a run's arc, saga, person or event (#111). */
	story(kind: StoryKind, run: string, subject: StorySubject, id: string, pov = 'omniscient'): Promise<Job> {
		return post(`/api/${kind}`, kind === 'brief' ? { run, subject, id } : { run, subject, id, pov });
	},
	/** A canon check of prose against a run, from a point of view (#111). */
	check(run: string, text: string, pov = 'omniscient'): Promise<Job> {
		return post('/api/check', { run, text, pov });
	}
};

export type StoryKind = 'pack' | 'chronicle' | 'brief';
export type StorySubject = 'arc' | 'saga' | 'person' | 'event' | 'topic';

export interface Recipe {
	file: string;
	name: string | null;
	world: string | null;
	end: string | null;
	ripples: number;
	error: string | null;
}

async function post(url: string, body: unknown): Promise<Job> {
	const r = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-Renasci-Launch': '1' },
		body: JSON.stringify(body)
	});
	if (!r.ok) throw new Error((await r.text()) || `launch refused (${r.status})`);
	return r.json();
}
