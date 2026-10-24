import { describe, expect, it } from 'vitest';

import { at, centre, days, line, near, type Grid } from './hex';

// (reference values from renasci.mapgrid, so the editor and the server agree)
describe('hex', () => {
	it('puts centres where the Python grid does, and finds cells back from points', () => {
		const want: Record<string, [number, number]> = {
			'c:0,0': [12, 13.8564],
			'c:7,3': [192, 76.2102],
			'c:19,14': [468, 304.8409],
			'c:4,9': [120, 200.9179]
		};
		const g = { cols: 20, rows: 15, miles: 24 };
		for (const [c, [x, y]] of Object.entries(want)) {
			const [cx, cy] = centre(c, 24);
			expect(cx).toBeCloseTo(x, 3);
			expect(cy).toBeCloseTo(y, 3);
			expect(at(cx + 5, cy - 4, g)).toBe(c);
		}
	});

	it('has the same neighbours and lines', () => {
		expect(near('c:2,1', { cols: 6, rows: 5 }).sort()).toEqual(['c:1,1', 'c:2,0', 'c:2,2', 'c:3,0', 'c:3,1', 'c:3,2']);
		expect(line('c:0,0', 'c:5,3')).toEqual(['c:0,0', 'c:1,0', 'c:1,1', 'c:2,1', 'c:3,2', 'c:4,2', 'c:4,3', 'c:5,3']);
		const g = { cols: 9, rows: 8 };
		for (let a = 0; a < 9 * 8; a++)
			for (let b = 0; b < 9 * 8; b++) {
				const [ca, cb] = [`c:${a % 9},${Math.floor(a / 9)}`, `c:${b % 9},${Math.floor(b / 9)}`];
				for (const c of line(ca, cb, g)) {
					const [col, row] = c.slice(2).split(',').map(Number);
					expect(col >= 0 && col < 9 && row >= 0 && row < 8).toBe(true);
				}
			}
	});

	it('counts days as the server bakes them', () => {
		const g: Grid = { cols: 6, rows: 5, miles: 24, days_per_cell: 1.2, terrain: { plains: 1, hills: 2, water: null }, cells: { 'c:2,0': { terrain: 'hills' }, 'c:4,2': { terrain: 'water' } } };
		expect(days(['c:0,0', 'c:1,0', 'c:2,0', 'c:3,0'], g)).toBe(5);
		expect(days(['c:0,0', 'c:1,0'], g)).toBe(2);
		expect(days(['c:3,1', 'c:4,2'], g)).toBeNull();
	});
});
