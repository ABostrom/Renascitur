import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { finalState } from './entity';
import { houseRows, MAX_SERIES, populationSeries, successions, type PopRow } from './houses';
import { NodeSource } from './node-source';
import { StateIndex } from './person';
import { openRun, readTable } from './run';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

const row = (year: number, entity: string, notables: number, masses: number): PopRow => ({
	date: [1, year, 0],
	entity,
	system: 'people.population',
	values: { notables, pop: { f: [masses], m: [0] } }
});

describe('population series', () => {
	const rows = [row(1, 's:a', 5, 100), row(1, 's:b', 3, 50), row(1, 's:c', 2, 20), row(2, 's:a', 6, 110), row(2, 's:b', 3, 40), row(2, 's:c', 2, 25)];
	const regionOf = { 's:a': 'r:north', 's:b': 'r:north', 's:c': 'r:south' };

	it('sums people (notables and masses) by region, one point a year', () => {
		const s = populationSeries(rows, regionOf, { group: 'region', measure: 'people' });
		expect(s.map((x) => x.key)).toEqual(['r:north', 'r:south']);
		expect(s[0].points).toEqual([{ year: [1, 1], value: 158 }, { year: [1, 2], value: 159 }]);
	});

	it('shows one region\'s settlements, or notables only', () => {
		const s = populationSeries(rows, regionOf, { group: 'r:north', measure: 'notables' });
		expect(s.map((x) => [x.key, x.points.map((p) => p.value)])).toEqual([['s:a', [5, 6]], ['s:b', [3, 3]]]);
	});

	it('folds anything past the colour limit into "Other", keeping the biggest by their last value', () => {
		const many = Array.from({ length: MAX_SERIES + 3 }, (_, i) => row(1, `s:${String(i).padStart(2, '0')}`, 0, 10 + i));
		const s = populationSeries(many, Object.fromEntries(many.map((r) => [r.entity, 'r:x'])), { group: 'r:x', measure: 'people' });
		expect(s.length).toBe(MAX_SERIES);
		expect(s[s.length - 1].key).toBe('other');
		expect(s[s.length - 1].points[0].value).toBe(10 + 11 + 12 + 13);
		expect(s[0].key).toBe(`s:${MAX_SERIES + 2}`); // biggest first
	});
});

describe('successions', () => {
	it('lists each office\'s holders in order with their start and end', () => {
		const deltas: { date: [number, number, number]; entity: string; field: string; old: unknown; new: unknown; event: string }[] = [
			{ date: [1, 1, 0], entity: 'o:h', field: 'holder', old: null, new: 'p:a', event: 'x1' },
			{ date: [1, 9, 3], entity: 'o:h', field: 'holder', old: 'p:a', new: null, event: 'x2' },
			{ date: [1, 9, 3], entity: 'o:h', field: 'holder', old: null, new: 'p:b', event: 'x3' },
			{ date: [1, 9, 3], entity: 'o:other', field: 'name', old: null, new: 'x', event: 'x4' }
		];
		expect(successions(deltas, new Set(['o:h'])).get('o:h')).toEqual([
			{ holder: 'p:a', from: [1, 1, 0], to: [1, 9, 3], event: 'x1' },
			{ holder: 'p:b', from: [1, 9, 3], to: null, event: 'x3' }
		]);
	});
});

describe('the kin fixture', () => {
	it('has houses with members and heads, and population by region', async () => {
		const run = await openRun(new NodeSource(RUNS), 'kin');
		const ix = new StateIndex(await finalState(run));
		const houses = houseRows(ix);
		expect(houses.length).toBeGreaterThan(1);
		for (const h of houses) expect(h.living + h.dead).toBeGreaterThan(0);
		const pops: PopRow[] = [];
		for await (const r of readTable(run, 'timeseries')) if (r.system === 'people.population') pops.push(r);
		const regionOf = Object.fromEntries([...ix.byId.values()].filter((e) => e.kind === 'settlement').map((e) => [e.id, e.fields.region]));
		const s = populationSeries(pops, regionOf, { group: 'region', measure: 'people' });
		expect(s.length).toBeGreaterThan(1);
		expect(s.length).toBeLessThanOrEqual(MAX_SERIES);
		expect(s[0].points.length).toBe(40);
	});
});

describe('review fixes', () => {
	it('ticks are whole, distinct and reach the top, even for tiny or empty data', async () => {
		const { niceTicks } = await import('./houses');
		for (const m of [0, 1, 2, 3, 7, 1500, 1234567]) {
			const t = niceTicks(m);
			expect(new Set(t).size).toBe(t.length);
			expect(t[0]).toBe(0);
			expect(t[t.length - 1]).toBeGreaterThanOrEqual(Math.max(1, m));
			for (const v of t) expect(Number.isInteger(v)).toBe(true);
		}
	});

	it('a year with no row carries the last value forward (before its first row it is 0)', () => {
		const rows = [row(2, 's:a', 1, 9), row(1, 's:b', 1, 1), row(2, 's:b', 1, 1), row(3, 's:b', 1, 1), row(4, 's:a', 2, 9)];
		const s = populationSeries(rows, { 's:a': 'r', 's:b': 'r' }, { group: 'r', measure: 'people' });
		expect(s.find((x) => x.key === 's:a')!.points.map((p) => p.value)).toEqual([0, 10, 10, 11]);
	});

	it('a missing notables count is 0, not NaN', () => {
		const r = { ...row(1, 's:a', 0, 5), values: { pop: { f: [5], m: [0] } } } as unknown as PopRow;
		expect(populationSeries([r], { 's:a': 'r' }, { group: 'region', measure: 'people' })[0].points[0].value).toBe(5);
	});

	it('the dormant are counted apart from the living', () => {
		const ix = new StateIndex({
			entities: [
				{ id: 'h', kind: 'house', status: 'active', fields: { name: 'H' } },
				{ id: 'a', kind: 'person', status: 'active', fields: { house: 'h' } },
				{ id: 'b', kind: 'person', status: 'dormant', fields: { house: 'h' } },
				{ id: 'c', kind: 'person', status: 'dead', fields: { house: 'h' } }
			]
		});
		expect(houseRows(ix)[0]).toMatchObject({ living: 1, dormant: 1, dead: 1 });
	});
});
