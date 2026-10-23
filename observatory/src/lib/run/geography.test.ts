import { describe, expect, it } from 'vitest';

import { layout, occupancy, type Geography } from './geography';

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
