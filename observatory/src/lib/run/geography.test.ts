import { describe, expect, it } from 'vitest';

import { geographyAt, layout, loadGeography, loadMapDeltas, mapChanges, occupancy, type Geography } from './geography';

const GEO: Geography = {
	regions: [{ id: 'g:land' }, { id: 'g:north', name: 'North', within: 'g:land' }],
	places: [
		{ id: 't:a', name: 'A', kind: 'settlement', region: 'g:north' },
		{ id: 't:b', name: 'B', kind: 'settlement', region: 'g:north' },
		{ id: 't:c', name: 'C', kind: 'settlement', region: 'g:land' },
		{ id: 'g:ruin', name: 'Ruin', kind: 'ruin', region: 'g:land' }
	],
	routes: [
		{ id: 'g:a--b', ends: ['t:a', 't:b'], days: 2, kind: 'road', vialux: true },
		{ id: 'g:b--c', ends: ['t:b', 't:c'], days: 6, kind: 'road' },
		{ id: 'g:a--ruin', ends: ['t:a', 'g:ruin'], days: 1, kind: 'track' }
	]
};

const dist = (p: { x: number; y: number }, q: { x: number; y: number }) => Math.hypot(p.x - q.x, p.y - q.y);

describe('layout', () => {
	it('is the same every time, inside the box, with no two places on top of each other', () => {
		const a = layout(GEO, 400, 300);
		expect(layout(GEO, 400, 300)).toEqual(a);
		for (const p of Object.values(a)) {
			expect(p.x).toBeGreaterThanOrEqual(0);
			expect(p.x).toBeLessThanOrEqual(400);
			expect(p.y).toBeGreaterThanOrEqual(0);
			expect(p.y).toBeLessThanOrEqual(300);
		}
		const pts = Object.values(a);
		for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) expect(dist(pts[i], pts[j])).toBeGreaterThan(10);
	});

	it('puts a long road longer than a short one', () => {
		const a = layout(GEO, 400, 300);
		expect(dist(a['t:b'], a['t:c'])).toBeGreaterThan(dist(a['t:a'], a['g:ruin']));
	});

	it('uses the file\'s positions when every place has one', () => {
		const placed = { ...GEO, places: GEO.places.map((p, i) => ({ ...p, at: [i * 10, i * 5] as [number, number] })) };
		const a = layout(placed, 400, 300);
		expect(a['t:a'].x).toBeLessThan(a['t:b'].x);
		expect(a['t:a'].y).toBeLessThan(a['t:b'].y);
	});
});

describe('occupancy', () => {
	it('counts residents and travellers from the final state', () => {
		const state = {
			entities: [
				{ id: 't:a', kind: 'settlement', status: 'active', fields: { residents: ['p1', 'p2', 'p3'] } },
				{ id: 't:b', kind: 'settlement', status: 'active', fields: { residents: [] } },
				{ id: 'p1', kind: 'person', status: 'active', fields: { name: 'Ama', place: 't:a', journey: { from: 't:a', to: 't:c', path: ['t:a', 't:b', 't:c'], why: 'migration' } } },
				{ id: 'p9', kind: 'person', status: 'dead', fields: { place: 't:a', journey: { from: 't:a', to: 't:b', path: ['t:a', 't:b'], why: 'flee' } } }
			],
			columns: {}
		};
		const occ = occupancy(state, GEO);
		expect(occ.residents).toEqual({ 't:a': 3, 't:b': 0 });
		expect(occ.travellers).toEqual([{ id: 'p1', name: 'Ama', from: 't:a', to: 't:c', next: 't:b', why: 'migration' }]);
	});
});

describe('the map by year', () => {
	const delta = (date: [number, number, number], entity: string, field: string, value: unknown, event = 'x1') => ({
		date, entity, field, new: value, event
	});
	const DELTAS = [
		{ ...delta([1, 3, 10], 'g:a--b', 'open', false, 'x1'), old: true },
		delta([1, 4, 0], 'g:b--ruin', 'status', 'active', 'x2'),
		delta([1, 4, 0], 'g:b--ruin', 'ends', ['t:b', 'g:ruin'], 'x2'),
		delta([1, 4, 0], 'g:b--ruin', 'days', 3, 'x2'),
		delta([1, 4, 0], 'g:b--ruin', 'kind', 'track', 'x2'),
		{ ...delta([1, 5, 0], 't:c', 'region', 'g:north', 'x3'), old: 'g:land' },
		delta([1, 1, 0], 't:b', 'region', 'g:north', 'x0'), // (cast at the start: the file's own)
		delta([1, 6, 0], 'g:north', 'within', 'g:wider', 'x4'), // (null to a value later: a real change)
		delta([1, 5, 0], 'p:someone', 'region', 'g:north', 'x9') // (not a place: ignored)
	];
	const key = (d: [number, number, number]) => d[0] * 1e6 + d[1] * 1000 + d[2];

	it('replays the changes up to a date, and no further', () => {
		const before = geographyAt(GEO, DELTAS, key([1, 3, 0]), key);
		expect(before).toEqual({ ...GEO });
		const later = geographyAt(GEO, DELTAS, key([1, 5, 0]), key);
		expect(later.routes.find((r) => r.id === 'g:a--b')!.open).toBe(false);
		expect(later.routes.find((r) => r.id === 'g:b--ruin')).toMatchObject({ ends: ['t:b', 'g:ruin'], days: 3, kind: 'track' });
		expect(later.places.find((p) => p.id === 't:c')!.region).toBe('g:north');
		expect(GEO.routes.find((r) => r.id === 'g:a--b')!.open).toBeUndefined(); // (the file is untouched)
	});

	it('lists what changed the map, one entry per event', () => {
		expect(mapChanges(GEO, DELTAS).map((c) => [c.event, c.what])).toEqual([
			['x1', 'closed'],
			['x2', 'built'],
			['x3', 'moved'],
			['x4', 'changed']
		]);
	});

	it('replays who held a place (S8), and lists it as taken', () => {
		const held = [...DELTAS, { ...delta([1, 7, 0], 't:c', 'control', 'v:clans', 'x5'), old: 'v:empire' }];
		const geo = { ...GEO, places: GEO.places.map((p) => (p.id === 't:c' ? { ...p, control: 'v:empire' } : p)) };
		expect(geographyAt(geo, held, key([1, 6, 0]), key).places.find((p) => p.id === 't:c')!.control).toBe('v:empire');
		expect(geographyAt(geo, held, key([1, 8, 0]), key).places.find((p) => p.id === 't:c')!.control).toBe('v:clans');
		expect(mapChanges(geo, held).at(-1)).toMatchObject({ event: 'x5', what: 'taken', detail: 'held by v:clans' });
	});

	it("reads the ward run's map changes from its state deltas", async () => {
		const { NodeSource } = await import('./node-source');
		const { openRun } = await import('./run');
		const { resolve } = await import('node:path');
		const run = await openRun(new NodeSource(resolve(__dirname, '../../../fixtures/runs')), 'ward');
		const geo = (await loadGeography(run.source, 'ward'))!;
		const changes = mapChanges(geo, await loadMapDeltas(run, geo));
		expect(changes.map((c) => c.what)).toEqual(['closed', 'built']);
	});
});
