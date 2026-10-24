/**
 * The cell grid's geometry in the editor (S5 §3, #80), the same as `renasci.mapgrid`: pointy-top hexes in
 * odd-r offset rows (odd rows shifted half a cell right), `miles` across their flats, ids `c:<col>,<row>`.
 * Positions are miles from the map's top-left. The server checks and bakes; this only draws and picks.
 */
export interface Grid {
	cols: number;
	rows: number;
	miles: number;
	days_per_cell: number;
	terrain: Record<string, number | null>;
	cells: Record<string, { terrain?: string; region?: string }>;
}

export const cell = (col: number, row: number) => `c:${col},${row}`;

export function parse(id: string): [number, number] {
	const [c, r] = id.slice(2).split(',').map(Number);
	return [c, r];
}

export const inside = (col: number, row: number, g: Pick<Grid, 'cols' | 'rows'>) =>
	col >= 0 && row >= 0 && col < g.cols && row < g.rows;

const EVEN = [[1, 0], [-1, 0], [-1, -1], [0, -1], [-1, 1], [0, 1]];
const ODD = [[1, 0], [-1, 0], [0, -1], [1, -1], [0, 1], [1, 1]];

export function near(id: string, g: Pick<Grid, 'cols' | 'rows'>): string[] {
	const [col, row] = parse(id);
	return (row & 1 ? ODD : EVEN).filter(([dc, dr]) => inside(col + dc, row + dr, g)).map(([dc, dr]) => cell(col + dc, row + dr));
}

export function centre(id: string, miles: number): [number, number] {
	const [col, row] = parse(id);
	const radius = miles / Math.sqrt(3);
	return [miles * (col + 0.5 + 0.5 * (row & 1)), radius + row * 1.5 * radius];
}

/** The six corners of a cell, for drawing. */
export function corners(id: string, miles: number): [number, number][] {
	const [x, y] = centre(id, miles);
	const radius = miles / Math.sqrt(3);
	return [0, 1, 2, 3, 4, 5].map((i) => {
		const a = (Math.PI / 180) * (60 * i - 30);
		return [x + radius * Math.cos(a), y + radius * Math.sin(a)];
	});
}

function cubeRound(q: number, r: number): [number, number] {
	const s = -q - r;
	let rq = Math.round(q),
		rr = Math.round(r);
	const rs = Math.round(s);
	const dq = Math.abs(rq - q),
		dr = Math.abs(rr - r),
		ds = Math.abs(rs - s);
	if (dq > dr && dq > ds) rq = -rr - rs;
	else if (dr > ds) rr = -rq - rs;
	return [rq, rr];
}

const axial = (col: number, row: number): [number, number] => [col - (row - (row & 1)) / 2, row];
const offset = (q: number, r: number): [number, number] => [q + (r - (r & 1)) / 2, r];

/** The cell under a point (miles), clamped to the grid. */
export function at(x: number, y: number, g: Pick<Grid, 'cols' | 'rows' | 'miles'>): string {
	const radius = g.miles / Math.sqrt(3);
	const x0 = x - g.miles / 2,
		y0 = y - radius;
	const [q, r] = cubeRound(((Math.sqrt(3) / 3) * x0 - y0 / 3) / radius, ((2 / 3) * y0) / radius);
	const [col, row] = offset(q, r);
	return cell(Math.min(Math.max(col, 0), g.cols - 1), Math.min(Math.max(row, 0), g.rows - 1));
}

/** The cells on a straight line from a to b, each next to the one before (as `mapgrid.line`). */
export function line(a: string, b: string, g?: Pick<Grid, 'cols' | 'rows'>): string[] {
	const [qa, ra] = axial(...parse(a));
	const [qb, rb] = axial(...parse(b));
	const n = Math.max(Math.abs(qa - qb), Math.abs(ra - rb), Math.abs(qa + ra - (qb + rb)));
	const out: string[] = [];
	for (let i = 0; i <= n; i++) {
		const t = n ? i / n : 0;
		let c = '';
		for (const nudge of [1e-6, -1e-6]) {
			const [q, r] = cubeRound(qa + (qb - qa) * t + nudge, ra + (rb - ra) * t + nudge);
			const [col, row] = offset(q, r);
			c = cell(col, row);
			if (!g || inside(col, row, g)) break;
		}
		if (out.at(-1) !== c) out.push(c);
	}
	return out;
}

export const terrainOf = (id: string, g: Grid) => g.cells[id]?.terrain ?? 'plains';
export const regionOf = (id: string, g: Grid) => g.cells[id]?.region ?? null;

/** A land path's days, as the server will bake them (for showing while drawing); null if impassable. */
export function days(path: string[], g: Grid): number | null {
	const costs = path.map((c) => g.terrain[terrainOf(c, g)]);
	if (costs.some((c) => c === null || c === undefined)) return null;
	let total = 0;
	for (let i = 1; i < costs.length; i++) total += ((costs[i - 1] as number) + (costs[i] as number)) / 2;
	return Math.max(1, Math.ceil(total * g.days_per_cell - 1e-9));
}
