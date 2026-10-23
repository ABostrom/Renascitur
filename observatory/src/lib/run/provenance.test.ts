import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { finalState } from './entity';
import { buildIndex } from './index';
import { NodeSource } from './node-source';
import { StateIndex } from './person';
import { beliefsOf, claimText, motives, trace, type Lookup } from './provenance';
import { openRun } from './run';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

const ev = (id: string, type: string, causes: string[] = [], payload: any = {}, roles: any = {}) => ({
	id,
	type,
	date: [1, 2, 0],
	roles,
	payload,
	causes: causes.map((c) => ['event', c])
});
const LOG = [
	ev('x:ripple', 'ripple.inject'),
	ev('x:journey', 'people.journey'),
	ev('x:death', 'people.death', ['x:poison'], {}, { deceased: ['p:v'] }),
	ev('x:poison', 'people.action', [], { action: 'Poison' }),
	// (an event's causes include its activation's, sorted by id: the ripple and the journey sort first)
	ev('x:saw', 'belief.perceived', ['x:death', 'x:ripple'].sort(), { key: 'c:1' }, { holder: ['p:a'] }),
	ev('x:told1', 'belief.told', ['x:journey', 'x:saw'].sort(), { key: 'c:1', intent: 'honest' }, { holder: ['p:b'], teller: ['p:a'] }),
	ev('x:told2', 'belief.told', ['x:told1'], { key: 'c:1', intent: 'honest' }, { holder: ['p:me'], teller: ['p:b'] }),
	ev('x:slander', 'people.action', [], { action: 'Slander' }),
	ev('x:lie', 'belief.told', ['x:ripple', 'x:slander'].sort(), { key: 'c:2', intent: 'lie' }, { holder: ['p:me'], teller: ['p:s'] }),
	ev('x:exposed', 'people.action', [], { action: 'BearWitness' }),
	ev('x:fixed', 'belief.corrected', ['x:exposed'], { key: 'c:1' }, { holder: ['p:me'] })
];
const byId = new Map(LOG.map((e) => [e.id, e]));
const lookup: Lookup = (id) => byId.get(id);

const STATE = new StateIndex({
	entities: [
		{ id: 'p:v', kind: 'person', status: 'dead', fields: { name: 'Vel' } },
		{ id: 'p:k', kind: 'person', status: 'active', fields: { name: 'Kor' } },
		{ id: 'p:x', kind: 'person', status: 'active', fields: { name: 'Xan' } },
		{
			id: 'p:me',
			kind: 'person',
			status: 'active',
			fields: {
				name: 'Me',
				ambitions: ['a:1'],
				beliefs: {
					'c:1': { claim: { pred: 'killed', args: { victim: 'p:v', by: 'p:k' } }, conf: 0.6, from: 'x:told2', since: [1, 2, 0] },
					'c:2': { claim: { pred: 'killed', args: { victim: 'p:v', by: 'p:x' } }, conf: 0.8, from: 'x:lie', since: [1, 2, 0] }
				},
				grievances: [{ against: 'p:x', event: 'x:lie', kind: 'killed', about: 'p:v' }]
			}
		},
		{ id: 'a:1', kind: 'ambition', status: 'active', fields: { owner: 'p:me', class: 'Vengeance', state: 'active', target: 'p:x', born_of: ['event', 'x:lie'] } },
		// (a rivalry against a killer: no belief behind it, though they believe the target killed someone)
		{ id: 'a:2', kind: 'ambition', status: 'active', fields: { owner: 'p:me', class: 'Ruin', state: 'active', target: 'p:k', born_of: ['drive', 'rivalry'] } }
	]
});

describe('provenance', () => {
	it('reads a claim out with names', () => {
		expect(claimText({ pred: 'killed', args: { victim: 'p:v', by: 'p:k' } }, STATE, lookup)).toBe('Vel was killed by Kor');
		expect(claimText({ pred: 'fault', args: { event: 'x:death', party: 'p:k' } }, STATE, lookup)).toBe('the people death was the fault of Kor');
	});

	it('walks a belief back through each telling to the event it began with', () => {
		const steps = trace(lookup, 'x:told2');
		expect(steps.map((s) => s.event.id)).toEqual(['x:told2', 'x:told1', 'x:saw', 'x:death']);
		expect(steps.at(-1)!.origin).toBe(true);
	});

	it('ends a correction at what exposed the truth', () => {
		expect(trace(lookup, 'x:fixed').map((s) => [s.event.id, s.origin])).toEqual([
			['x:fixed', false],
			['x:exposed', true]
		]);
	});

	it('stops a trace at a lie, with the scheme that told it', () => {
		const steps = trace(lookup, 'x:lie');
		expect(steps.map((s) => s.event.id)).toEqual(['x:lie', 'x:slander']);
		expect(steps[0].lie).toBe(true);
	});

	it("lists a person's beliefs, firmest first, each with its verdict-free trace", () => {
		const bs = beliefsOf(STATE.get('p:me')!.fields.beliefs, STATE, lookup);
		expect(bs.map((b) => b.key)).toEqual(['c:2', 'c:1']);
		expect(bs[0].text).toBe('Vel was killed by Xan');
		expect(bs[0].lie).toBe(true);
		expect(bs[1].trace.at(-1)!.event.id).toBe('x:death');
	});

	it('ties a want to the belief that moves it', () => {
		const m = motives('p:me', STATE, STATE.get('p:me')!.fields.beliefs, lookup);
		expect(m).toHaveLength(1);
		expect(m[0].ambition).toBe('a:1');
		expect(m[0].belief).toBe('c:2');
		expect(m[0].trace[0].lie).toBe(true);
	});

	it('traces every belief in the ward run back to an event or a lie', async () => {
		const run = await openRun(new NodeSource(RUNS), 'ward');
		const index = await buildIndex(run);
		const look: Lookup = (id) => {
			const i = index.position.get(id);
			return i === undefined ? undefined : index.row(i);
		};
		const state = new StateIndex(await finalState(run));
		let traced = 0;
		for (const e of state.byId.values()) {
			if (e.kind !== 'person' || !e.fields.beliefs) continue;
			for (const b of beliefsOf(e.fields.beliefs, state, look)) {
				const last = b.trace.at(-1)!;
				expect(last.origin || b.trace.some((s) => s.lie)).toBe(true);
				traced++;
			}
		}
		expect(traced).toBeGreaterThan(10);
	});
});
