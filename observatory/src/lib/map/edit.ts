import type { Geography } from '$lib/run/geography';

import { line, regionOf, type Grid } from './hex';

/**
 * The map editor's state and its edits (S5 §6, #84), as plain functions over a copy, so every edit is one
 * undoable step and the page only draws. The server checks and bakes on save (`renasci.mapedit`).
 */
export interface Layout {
	places: Record<string, { cell: string; at?: [number, number] }>;
	routes: Record<string, { cells: string[] }>;
}

export interface MapState {
	geography: Geography & { changes?: unknown[] };
	grid: Grid;
	layout: Layout;
}

const copy = <T>(x: T): T => JSON.parse(JSON.stringify(x));

/** The cells through each point in turn (a route drawn by clicking: lines between the clicks). */
export function traced(points: string[], grid?: Grid): string[] {
	const out: string[] = points.slice(0, 1);
	for (let i = 1; i < points.length; i++) out.push(...line(points[i - 1], points[i], grid).slice(1));
	return out;
}

/** The place standing on a cell, if any. */
export function placeAt(s: MapState, cell: string): string | null {
	return Object.entries(s.layout.places).find(([, v]) => v.cell === cell)?.[0] ?? null;
}

/** A leaf region (nothing within it): the one a new place is put in when its cell has no region. */
function leaf(s: MapState): string {
	const within = new Set(s.geography.regions.map((r) => r.within).filter(Boolean));
	return s.geography.regions.find((r) => !within.has(r.id))?.id ?? s.geography.regions[0]?.id ?? '';
}

/** Move a place to a cell: its routes' paths keep their middles and re-join the place at their ends. */
export function movePlace(s: MapState, id: string, to: string): MapState {
	const out = copy(s);
	const from = out.layout.places[id]?.cell;
	out.layout.places[id] = { ...out.layout.places[id], cell: to };
	delete out.layout.places[id].at; // (a marker position no longer holds)
	for (const r of out.geography.routes) {
		const path = out.layout.routes[r.id]?.cells;
		if (!path?.length || !r.ends.includes(id)) continue;
		let cells = [...path];
		if (cells.length === 1) cells = [to]; // (a one-cell path: the place itself)
		else if (cells[0] === from) cells = [...line(to, cells[1], out.grid).slice(0, -1), ...cells.slice(1)];
		if (cells.at(-1) === from) {
			const before = cells.at(-2) ?? to;
			cells = [...cells.slice(0, -1), ...line(before, to, out.grid).slice(1)];
		}
		out.layout.routes[r.id] = { cells: cells.filter((c, i) => c !== cells[i - 1]) };
	}
	return out;
}

/** A new place on a cell (in the cell's region, else a leaf region; the bake settles it). */
export function addPlace(s: MapState, place: { id: string; name: string; kind: string }, cell: string): MapState {
	if (s.geography.places.some((p) => p.id === place.id)) throw new Error(`${place.id} already exists`);
	if (!/^[vgt]:\S+$/.test(place.id)) throw new Error('a place id is v:… (a vault note), g:… (a new one) or t:…');
	if (placeAt(s, cell)) throw new Error(`${placeAt(s, cell)} already stands on ${cell}`);
	const out = copy(s);
	out.geography.places.push({ ...place, region: regionOf(cell, out.grid) ?? leaf(out) });
	out.layout.places[place.id] = { cell };
	return out;
}

/** Remove a place, and the routes to it. */
export function deletePlace(s: MapState, id: string): MapState {
	const out = copy(s);
	const gone = out.geography.routes.filter((r) => r.ends.includes(id)).map((r) => r.id);
	out.geography.places = out.geography.places.filter((p) => p.id !== id);
	out.geography.routes = out.geography.routes.filter((r) => !gone.includes(r.id));
	delete out.layout.places[id];
	for (const r of gone) delete out.layout.routes[r];
	return out;
}

/** A route from a to b through the clicked cells (days set when it's saved, from its cells). If the two
 * places already have a route of that kind (one per kind per pair), that route is drawn instead. */
export function addRoute(s: MapState, a: string, b: string, via: string[], kind = 'road'): MapState {
	const ca = s.layout.places[a]?.cell,
		cb = s.layout.places[b]?.cell;
	if (!ca || !cb) throw new Error('both ends must be placed on the map');
	if (a === b) throw new Error('a route joins two places');
	const same = s.geography.routes.find((r) => r.kind === kind && r.ends.includes(a) && r.ends.includes(b));
	if (same) return redrawRoute(s, same.id, same.ends[0] === a ? via : [...via].reverse());
	const base = `g:${a.slice(a.indexOf(':') + 1)}--${b.slice(b.indexOf(':') + 1)}`;
	let id = base;
	for (let n = 2; s.geography.routes.some((r) => r.id === id); n++) id = `${base}-${n}`;
	const out = copy(s);
	out.geography.routes.push({ id, ends: [a, b], days: 1, kind });
	out.layout.routes[id] = { cells: traced([ca, ...via, cb], out.grid) };
	return out;
}

/** Re-draw a route's path through the clicked cells, between its ends' cells. */
export function redrawRoute(s: MapState, id: string, via: string[]): MapState {
	const r = s.geography.routes.find((x) => x.id === id);
	if (!r) throw new Error(`no route ${id}`);
	const out = copy(s);
	out.layout.routes[id] = { cells: traced([s.layout.places[r.ends[0]].cell, ...via, s.layout.places[r.ends[1]].cell], out.grid) };
	return out;
}

export function deleteRoute(s: MapState, id: string): MapState {
	const out = copy(s);
	out.geography.routes = out.geography.routes.filter((r) => r.id !== id);
	delete out.layout.routes[id];
	return out;
}

/** Set a place's or route's attribute (name, kind, Vialux, open…). */
export function setAttr(s: MapState, what: 'place' | 'route', id: string, key: string, value: unknown): MapState {
	const out = copy(s);
	const list = (what === 'place' ? out.geography.places : out.geography.routes) as unknown as Record<string, unknown>[];
	const item = list.find((x) => x.id === id);
	if (!item) throw new Error(`no ${what} ${id}`);
	if (value === '' || value === undefined) delete item[key];
	else item[key] = value;
	return out;
}
