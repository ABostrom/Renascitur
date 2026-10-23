import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { NodeSource } from './node-source';
import { openRun } from './run';
import { loadStrain, strainReport } from './strain';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

const CANON = {
	pins: [
		{ id: 'p:guarded', kind: 'event', window: [[1, 2, 0], [1, 2, 359]] },
		{ id: 'p:forced', kind: 'event', window: [[1, 3, 0], [1, 3, 359]] },
		{ id: 'p:broken', kind: 'event', window: [[1, 4, 0], [1, 4, 359]] },
		{ id: 'p:held', kind: 'existence', window: null },
		{ id: 'p:later', kind: 'event', window: [[1, 90, 0], [1, 90, 359]] }
	],
	dropped: [{ pin: 'p:reign', why: 'not an office of the scenario' }],
	feasibility: {
		pins: {
			'p:later': { verdict: 'out_of_scope', why: 'S1: out_of_scope', notes: ['Events/Later'] },
			'p:odd': { verdict: 'unsupported', why: 'S1: unsupported', notes: ['Events/Odd'] },
			'p:guarded': { verdict: 'ok', why: '', notes: ['People/G'] }
		}
	}
};

const STRAIN = [
	{ action: 'guard', pin: 'p:guarded', kind: 'event', date: [1, 1, 10], entity: 'p:x', event: 'xnear', activation: 'a1' },
	{ action: 'force', pin: 'p:forced', kind: 'event', date: [1, 3, 359], event: null, activation: 'a2' },
	{ action: 'violated', pin: 'p:broken', kind: 'event', date: [1, 4, 359], event: null, activation: '', reason: 'no forcer could construct it' }
];
const PINS = [
	{ pin: 'p:guarded', status: 'satisfied', event: 'xmet', date: [1, 2, 5] },
	{ pin: 'p:forced', status: 'forced', event: 'xforced', date: [1, 3, 359] },
	{ pin: 'p:broken', status: 'violated', event: null, date: [1, 4, 359] }
];

describe('strain report', () => {
	const r = strainReport(STRAIN, PINS, CANON);

	it('links every strain entry to its event: a guard to its near miss, a force to the forced event', () => {
		expect(r.entries.map((e) => [e.action, e.pin, e.event])).toEqual([
			['guard', 'p:guarded', 'xnear'],
			['force', 'p:forced', 'xforced'],
			['violated', 'p:broken', null]
		]);
		expect(r.entries[2].reason).toBe('no forcer could construct it');
	});

	it('lists every pin with how it ended: met, forced, violated, out of scope, dropped, unsupported', () => {
		const status = Object.fromEntries(r.pins.map((p) => [p.id, p.status]));
		expect(status).toEqual({
			'p:guarded': 'satisfied', 'p:forced': 'forced', 'p:broken': 'violated', 'p:held': 'no change logged',
			'p:later': 'out_of_scope', 'p:reign': 'dropped', 'p:odd': 'unsupported'
		});
		expect(r.pins.find((p) => p.id === 'p:guarded')).toMatchObject({ event: 'xmet', guards: 1, notes: ['People/G'] });
		expect(r.pins.find((p) => p.id === 'p:reign')?.why).toBe('not an office of the scenario');
	});

	it('counts each kind of strain; a pin met only after a guard is not met on its own', () => {
		expect(r.counts).toEqual({ guard: 1, force: 1, violated: 1, met: 0, outside: 3 });
		const unguarded = strainReport([], [{ pin: 'p:a', status: 'satisfied', event: 'x', date: [1, 1, 0] }], null);
		expect(unguarded.counts.met).toBe(1);
	});

	it('a violation caught as it happened takes its event from the pins table', () => {
		const late = strainReport(
			[{ action: 'violated', pin: 'p:o', kind: 'ordering', date: [1, 5, 9], event: null, reason: 'b happened before a' }],
			[{ pin: 'p:o', status: 'violated', event: 'xlate', date: [1, 5, 9] }],
			null
		);
		expect(late.entries[0].event).toBe('xlate');
	});

	it('works without canon.json (pins only from the run tables)', () => {
		const bare = strainReport(STRAIN, PINS, null);
		expect(bare.pins.map((p) => p.id).sort()).toEqual(['p:broken', 'p:forced', 'p:guarded']);
	});
});

describe('the canon fixture', () => {
	it('has a guard linked to its near miss and a violation', async () => {
		const run = await openRun(new NodeSource(RUNS), 'canon');
		const r = await loadStrain(run);
		expect(r).not.toBeNull();
		expect(r!.entries.some((e) => e.action === 'guard' && e.event)).toBe(true);
		expect(r!.entries.some((e) => e.action === 'violated')).toBe(true);
		expect(r!.pins.some((p) => p.status === 'dropped')).toBe(true);
	});

	it('is null for a run with no pins at all', async () => {
		const run = await openRun(new NodeSource(RUNS), 'base');
		expect(await loadStrain(run)).toBeNull();
	});
});
