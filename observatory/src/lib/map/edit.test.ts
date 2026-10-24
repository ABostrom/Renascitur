import { describe, expect, it } from 'vitest';

import { addPlace, addRoute, deletePlace, movePlace, placeAt, redrawRoute, setAttr, traced, type MapState } from './edit';
import { near } from './hex';

const S: MapState = {
	geography: {
		regions: [{ id: 'g:land' }, { id: 'g:north', within: 'g:land' }],
		places: [
			{ id: 't:a', kind: 'settlement', region: 'g:north' },
			{ id: 't:b', kind: 'settlement', region: 'g:north' }
		],
		routes: [{ id: 'g:a--b', ends: ['t:a', 't:b'], days: 3, kind: 'road' }]
	},
	grid: { cols: 10, rows: 8, miles: 24, days_per_cell: 1.2, terrain: { plains: 1, water: null }, cells: { 'c:6,6': { region: 'g:north' } } },
	layout: { places: { 't:a': { cell: 'c:1,1' }, 't:b': { cell: 'c:4,1' } }, routes: { 'g:a--b': { cells: ['c:1,1', 'c:2,1', 'c:3,1', 'c:4,1'] } } }
};
const walkable = (cells: string[]) => cells.every((c, i) => i === 0 || near(cells[i - 1], S.grid).includes(c));

describe('map edits', () => {
	it('traces a path through clicked cells, each step to a neighbour', () => {
		const p = traced(['c:0,0', 'c:5,3', 'c:2,6'], S.grid);
		expect(p[0]).toBe('c:0,0');
		expect(p.at(-1)).toBe('c:2,6');
		expect(walkable(p)).toBe(true);
	});

	it('moves a place and its routes follow it', () => {
		const s = movePlace(S, 't:b', 'c:6,4');
		expect(s.layout.places['t:b'].cell).toBe('c:6,4');
		const p = s.layout.routes['g:a--b'].cells;
		expect(p[0]).toBe('c:1,1');
		expect(p.at(-1)).toBe('c:6,4');
		expect(walkable(p)).toBe(true);
		expect(S.layout.places['t:b'].cell).toBe('c:4,1'); // (edits are copies: undo keeps the old state)
	});

	it("adds a place in its cell's region, else in a leaf region", () => {
		const s = addPlace(S, { id: 'g:camp', name: 'Camp', kind: 'waypoint' }, 'c:6,6');
		expect(s.geography.places.at(-1)).toEqual({ id: 'g:camp', name: 'Camp', kind: 'waypoint', region: 'g:north' });
		expect(placeAt(s, 'c:6,6')).toBe('g:camp');
		const t = addPlace(S, { id: 'g:hut', name: 'Hut', kind: 'waypoint' }, 'c:0,7');
		expect(t.geography.places.at(-1)?.region).toBe('g:north'); // (g:land has a region within it)
		expect(() => addPlace(S, { id: 't:a', name: 'x', kind: 'x' }, 'c:0,0')).toThrow(/exists/);
		expect(() => addPlace(S, { id: 'nope', name: 'x', kind: 'x' }, 'c:0,0')).toThrow(/id/);
	});

	it('adds a route between placed places, and draws it again', () => {
		const s = addRoute(S, 't:a', 't:b', ['c:2,3'], 'track');
		const r = s.geography.routes.at(-1)!;
		expect(r.id).toBe('g:a--b-2');
		expect(r.kind).toBe('track');
		const p = s.layout.routes[r.id].cells;
		expect(p[0]).toBe('c:1,1');
		expect(p).toContain('c:2,3');
		expect(walkable(p)).toBe(true);
		const t = redrawRoute(s, r.id, ['c:3,5']);
		expect(t.layout.routes[r.id].cells).toContain('c:3,5');
		expect(() => addRoute(S, 't:a', 't:a', [])).toThrow();
	});

	it('draws the existing route when the two places already have one of that kind', () => {
		const s = addRoute(S, 't:b', 't:a', ['c:3,4']); // (drawn from the other end: the path is turned round)
		expect(s.geography.routes.map((r) => r.id)).toEqual(['g:a--b']);
		const p = s.layout.routes['g:a--b'].cells;
		expect(p[0]).toBe('c:1,1');
		expect(p.at(-1)).toBe('c:4,1');
		expect(p).toContain('c:3,4');
	});

	it('removes a place with its routes, and sets attributes', () => {
		const s = deletePlace(S, 't:a');
		expect(s.geography.places.map((p) => p.id)).toEqual(['t:b']);
		expect(s.geography.routes).toEqual([]);
		expect(s.layout.routes).toEqual({});
		const t = setAttr(S, 'route', 'g:a--b', 'vialux', true);
		expect(t.geography.routes[0].vialux).toBe(true);
		expect(setAttr(t, 'route', 'g:a--b', 'vialux', '').geography.routes[0].vialux).toBeUndefined();
	});
});
