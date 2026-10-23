import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';

import type { EntityChange } from './entity';
import { asOf, copies, moments, personView, raceName, StateIndex } from './person';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

const STATE = {
	entities: [
		{ id: 'p:mum', kind: 'person', status: 'dead', fields: { name: 'Ama', sex: 'f', children: ['p:me', 'p:sis'], spouse: null } },
		{ id: 'p:dad', kind: 'person', status: 'active', fields: { name: 'Brak', sex: 'm', children: ['p:me', 'p:sis'] } },
		{
			id: 'p:me',
			kind: 'person',
			status: 'active',
			fields: {
				name: 'Cass', sex: 'm', born: [1, 3, 0], mother: 'p:mum', father: 'p:dad', spouse: 'p:wife', children: ['p:kid'],
				house: 'h:ridge', place: 's:a', ties: ['t:1'], ambitions: ['a:1'],
				genome: { eye: ['grey@f:s:a', 'blue@x1234'], gift: ['n@f:lowland', 'y@f:lowland'] },
				wound: { kind: 'grief', event: 'x9', since: [1, 20, 0] }, need: 'to answer for the dead', wants: ['avenge Ama']
			}
		},
		{ id: 'p:sis', kind: 'person', status: 'active', fields: { name: 'Dara', mother: 'p:mum', father: 'p:dad' } },
		{ id: 'p:wife', kind: 'person', status: 'active', fields: { name: 'Erin', spouse: 'p:me' } },
		{ id: 'p:kid', kind: 'person', status: 'active', fields: { name: 'Fen', father: 'p:me', mother: 'p:wife' } },
		{ id: 'p:foe', kind: 'person', status: 'active', fields: { name: 'Garr' } },
		{ id: 't:1', kind: 'tie', status: 'active', fields: { a: 'p:foe', b: 'p:me', kind: 'enemy', strength: 0.6, since: [1, 21, 0], ended: null } },
		{ id: 'a:1', kind: 'ambition', status: 'active', fields: { owner: 'p:me', class: 'Vengeance', state: 'active', target: 'p:foe', formed: [1, 21, 0], resolved: null } },
		{ id: 'a:0', kind: 'ambition', status: 'active', fields: { owner: 'p:me', class: 'Marry', state: 'fulfilled', target: null, formed: [1, 18, 0], resolved: [[1, 19, 0], 'x8'] } },
		{ id: 'h:ridge', kind: 'house', status: 'active', fields: { name: 'Ridge' } }
	],
	columns: {}
};

describe('person view', () => {
	const ix = new StateIndex(STATE);

	it('names the family: parents, spouse, children, siblings', () => {
		const v = personView(ix, 'p:me');
		expect(v.parents.map((p) => p.name)).toEqual(['Ama', 'Brak']);
		expect(v.parents[0].status).toBe('dead');
		expect(v.spouse?.name).toBe('Erin');
		expect(v.children.map((p) => p.name)).toEqual(['Fen']);
		expect(v.siblings.map((p) => p.name)).toEqual(['Dara']);
		expect(v.house?.name).toBe('Ridge');
	});

	it('lists ambitions oldest first and ties with the other party', () => {
		const v = personView(ix, 'p:me');
		expect(v.ambitions.map((a) => a.class)).toEqual(['Marry', 'Vengeance']);
		expect(v.ambitions[1].target?.name).toBe('Garr');
		expect(v.ties).toEqual([{ id: 't:1', other: { id: 'p:foe', name: 'Garr', status: 'active' }, kind: 'enemy', strength: 0.6, since: [1, 21, 0], ended: null }]);
	});

	it('reads each allele copy: which parent, the variant, founder stock or a mutation', () => {
		expect(copies({ eye: ['grey@f:s:a', 'blue@x1234'] })).toEqual([
			{ locus: 'eye', from: 'mother', variant: 'grey', origin: 'founder', where: 's:a' },
			{ locus: 'eye', from: 'father', variant: 'blue', origin: 'mutation', where: 'x1234' }
		]);
	});
});

describe('as of a date', () => {
	const changes: EntityChange[] = [
		{ date: [1, 20, 0], field: 'wound', old: null, new: { kind: 'grief' }, event: 'x9', bulk: false },
		{ date: [1, 30, 0], field: 'wound', old: { kind: 'grief' }, new: null, event: 'x10', bulk: false },
		{ date: [1, 25, 0], field: 'need', old: null, new: 'to answer for the dead', event: 'x11', bulk: false }
	];
	const final = { wound: null, need: 'to answer for the dead', name: 'Cass' };

	it('takes the last change on or before the date, else the first change\'s old value, else the final value', () => {
		expect(asOf(final, changes, [1, 19, 0])).toEqual({ wound: null, need: null, name: 'Cass' });
		expect(asOf(final, changes, [1, 22, 0])).toEqual({ wound: { kind: 'grief' }, need: null, name: 'Cass' });
		expect(asOf(final, changes, [1, 26, 0])).toEqual({ wound: { kind: 'grief' }, need: 'to answer for the dead', name: 'Cass' });
		expect(asOf(final, changes, [1, 40, 0])).toEqual(final);
	});
});

describe('moments', () => {
	const ch = (date: [number, number, number], field = 'x'): EntityChange => ({ date, field, old: null, new: 1, event: 'e', bulk: false });

	it('is every year something changed, from the first change to the end, across ages', () => {
		const got = moments([ch([3, 250, 5], 'status'), ch([4, 2, 0]), ch([4, 2, 100]), ch([4, 9, 1])], [4, 12, 0]);
		expect(got).toEqual([[3, 250, 9999], [4, 2, 9999], [4, 9, 9999], [4, 12, 9999]]);
	});

	it('is empty without changes, and ignores column cells', () => {
		expect(moments([], [1, 5, 0])).toEqual([]);
		expect(moments([{ ...ch([1, 2, 0]), bulk: true }], [1, 5, 0])).toEqual([]);
	});
});

describe('race names', () => {
	it('drop the id prefix', () => {
		expect(raceName('r:human')).toBe('human');
		expect(raceName(undefined)).toBeNull();
	});
});

describe('every person in a run', () => {
	for (const run of ['kin', 'base', 'pyrosia']) {
		it(`renders a view (the ${run} fixture)`, () => {
			const state = JSON.parse(gunzipSync(readFileSync(resolve(RUNS, `${run}/state.json.gz`))).toString('utf-8'));
			const ix = new StateIndex(state);
			const people = state.entities.filter((e: { kind: string }) => e.kind === 'person');
			expect(people.length).toBeGreaterThan(20);
			for (const p of people) {
				const v = personView(ix, p.id);
				expect(v.name).toBeTruthy();
				expect(v.alleles.length).toBe(Object.values(p.fields.genome ?? {}).flat().length);
				expect(v.born === null || (Array.isArray(v.born) && v.born.length === 3)).toBe(true);
			}
		});
	}
});
