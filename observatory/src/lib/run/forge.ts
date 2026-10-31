/** The Forge (#165): find a person, a thing or a town in a run, read its card, and keep it as a hard truth for the next
 * run. Every button is a CLI command (`renasci gen`, `renasci keep`); the page holds no logic of its own. */

import { launcher, type Job } from './latch';

export interface Line {
	date: [number, number, number];
	text: string;
	event: string;
}

export interface Card {
	kind: 'person' | 'object' | 'settlement';
	id: string;
	name: string | null;
	status?: string;
	told: number;
	history: Line[];
	marks: { mark: string; event: string }[];
	[field: string]: unknown;
}

export interface Found {
	found: number;
	cards: Card[];
	closest?: Record<string, number>;
}

export interface Truths {
	places?: { id: string; name: string; kind: string; region: string }[];
	objects?: { id: string; name: string | null; type: string; place: string; from?: string }[];
}

export interface Search {
	what: string;
	filters: Record<string, string>;
	notable: boolean;
	seed: number;
}

/** The filters a generator takes, for the form. */
export const FILTERS: Record<string, string[]> = {
	person: ['race', 'house', 'age', 'job', 'mark', 'status'],
	object: ['type', 'fame', 'mark', 'lost'],
	village: ['region', 'mark']
};

function trimmed(filters: Record<string, string>): Record<string, string> {
	return Object.fromEntries(Object.entries(filters).filter(([, v]) => v.trim() !== '').map(([k, v]) => [k, v.trim()]));
}

async function post(url: string, body: unknown): Promise<Job> {
	const r = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-Renasci-Launch': '1' },
		body: JSON.stringify(body)
	});
	if (!r.ok) throw new Error((await r.text()) || `refused (${r.status})`);
	return r.json();
}

/** Wait for a job, and say why it failed if it did. */
async function finished(job: Job, wait = 300): Promise<Job> {
	for (;;) {
		const now = (await launcher.jobs()).find((j) => j.id === job.id);
		if (now && now.state !== 'running') {
			if (now.state === 'failed') throw new Error(now.output.trim().split('\n').pop() || 'it failed');
			return now;
		}
		await new Promise((done) => setTimeout(done, wait));
	}
}

export const forge = {
	/** Whether this server can keep things: started with --allow-launch and --truths. */
	async enabled(): Promise<boolean> {
		try {
			const r = await fetch('/api/capabilities');
			return r.ok && (await r.json()).forge === true;
		} catch {
			return false;
		}
	},
	async search(run: string, s: Search): Promise<Found> {
		await finished(
			await post('/api/gen', { run, what: s.what, filters: trimmed(s.filters), seed: s.seed, count: 12, notable: s.notable })
		);
		const r = await fetch(`/runs/${encodeURIComponent(run)}/analysis/cards/last.json`, { cache: 'no-store' });
		if (!r.ok) throw new Error('no cards came back');
		return r.json();
	},
	async keep(run: string, entity: string): Promise<void> {
		await finished(await post('/api/keep', { run, entity }));
	},
	async truths(): Promise<Truths> {
		const r = await fetch('/api/truths');
		return r.ok ? r.json() : {};
	}
};

/** What a card can be kept as today: the truth file takes objects. */
export const keepable = (c: Card): boolean => c.kind === 'object' && c.status === 'active';

/** A card's facts, in the order worth reading. */
export function facts(c: Card): [string, string][] {
	const shown: [string, unknown][] =
		c.kind === 'person'
			? [['race', c.race], ['house', c.house], ['job', c.job], ['place', c.place], ['status', c.status]]
			: c.kind === 'object'
				? [['type', c.type], ['material', c.material], ['fame', c.fame], ['owner', c.owner], ['place', c.place], ['from', c.origin]]
				: [['region', c.region], ['race', c.race], ['notables', c.residents], ['razed', c.razed]];
	return shown.filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => [k, String(v)]);
}
