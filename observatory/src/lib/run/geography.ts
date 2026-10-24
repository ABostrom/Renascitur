import { readTable, type Run } from './run';
import type { RunSource } from './source';

/** A run's `geography.json` (S4 spec §2): what the run's places, regions and routes were. */
export interface Region {
	id: string;
	name?: string;
	within?: string | null;
}

export interface Place {
	id: string;
	name?: string;
	kind: string;
	region: string;
	control?: string | null; // the polity that holds it (S8), when the world has polities
	at?: [number, number];
}

export interface Route {
	id: string;
	ends: [string, string];
	days: number;
	kind: string;
	vialux?: boolean;
	open?: boolean;
}

export interface Geography {
	about?: string;
	draft?: boolean;
	changes?: unknown[]; // dated changes the run makes (S4 §8, #81)
	regions: Region[];
	places: Place[];
	routes: Route[];
}

export type Layout = Record<string, { x: number; y: number }>;

/** The run's geography, or null for a world without one. */
export async function loadGeography(source: RunSource, run: string): Promise<Geography | null> {
	const path = `${run}/geography.json`;
	if (!(await source.has(path))) return null;
	return JSON.parse(await source.text(path));
}

const MARGIN_X = 90; // room for a label centred on a place at the edge
const MARGIN_Y = 28;

/** Fit points into the box, keeping their aspect. */
function fit(points: Layout, width: number, height: number): Layout {
	const xs = Object.values(points).map((p) => p.x);
	const ys = Object.values(points).map((p) => p.y);
	const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
	const scale = Math.min((width - 2 * MARGIN_X) / (x1 - x0 || 1), (height - 2 * MARGIN_Y) / (y1 - y0 || 1));
	const dx = (width - (x1 - x0) * scale) / 2;
	const dy = (height - (y1 - y0) * scale) / 2;
	const out: Layout = {};
	for (const [id, p] of Object.entries(points)) out[id] = { x: dx + (p.x - x0) * scale, y: dy + (p.y - y0) * scale };
	return out;
}

/**
 * Where to draw each place. The file's `at` (map cells) when every place has one; otherwise a
 * force layout: springs along routes whose rest length grows with their days, and every place pushing
 * every other away. It starts from a circle in id order and draws nothing at random, so the same
 * geography always gives the same picture.
 */
export function layout(geo: Geography, width: number, height: number): Layout {
	const ids = geo.places.map((p) => p.id).sort();
	if (ids.length === 0) return {};
	if (geo.places.every((p) => p.at)) {
		return fit(Object.fromEntries(geo.places.map((p) => [p.id, { x: p.at![0], y: p.at![1] }])), width, height);
	}
	const pos = ids.map((_, i) => {
		const a = (2 * Math.PI * i) / ids.length;
		return { x: Math.cos(a), y: Math.sin(a) };
	});
	const at = new Map(ids.map((id, i) => [id, i]));
	const drawn = geo.routes.filter((r) => at.has(r.ends[0]) && at.has(r.ends[1]));
	const meanDays = drawn.reduce((s, r) => s + r.days, 0) / (drawn.length || 1);
	const springs = drawn.map((r) => ({ a: at.get(r.ends[0])!, b: at.get(r.ends[1])!, rest: (0.35 * r.days) / meanDays }));
	const n = ids.length;
	for (let step = 0; step < 600; step++) {
		const cool = 0.05 * (1 - step / 600) + 0.002;
		const force = pos.map(() => ({ x: 0, y: 0 }));
		for (let i = 0; i < n; i++) {
			for (let j = i + 1; j < n; j++) {
				let dx = pos[i].x - pos[j].x;
				let dy = pos[i].y - pos[j].y;
				let d2 = dx * dx + dy * dy;
				if (d2 < 1e-9) [dx, dy, d2] = [1e-3 * (j - i), 1e-3, 1e-6];
				const push = 0.02 / d2;
				force[i].x += dx * push;
				force[i].y += dy * push;
				force[j].x -= dx * push;
				force[j].y -= dy * push;
			}
		}
		for (const s of springs) {
			const dx = pos[s.b].x - pos[s.a].x;
			const dy = pos[s.b].y - pos[s.a].y;
			const d = Math.hypot(dx, dy) || 1e-6;
			const pull = (d - s.rest) / d;
			force[s.a].x += dx * pull;
			force[s.a].y += dy * pull;
			force[s.b].x -= dx * pull;
			force[s.b].y -= dy * pull;
		}
		for (let i = 0; i < n; i++) {
			const f = Math.hypot(force[i].x, force[i].y);
			const move = Math.min(cool, f) / (f || 1);
			pos[i].x += force[i].x * move;
			pos[i].y += force[i].y * move;
		}
	}
	return fit(Object.fromEntries(ids.map((id, i) => [id, pos[i]])), width, height);
}

export interface Traveller {
	id: string;
	name: string;
	from: string;
	to: string;
	next: string; // the next place on the path (where to draw them)
	why: string;
}

/** Who lives where and who is on the road, from the run's final state. */
export function occupancy(state: { entities: { id: string; kind: string; status: string; fields: Record<string, any> }[] }, geo: Geography) {
	const places = new Set(geo.places.map((p) => p.id));
	const residents: Record<string, number> = {};
	const travellers: Traveller[] = [];
	for (const e of state.entities) {
		if (e.kind === 'settlement' && places.has(e.id)) residents[e.id] = (e.fields.residents ?? []).length;
		const j = e.fields.journey;
		if (e.kind === 'person' && e.status === 'active' && j) {
			travellers.push({ id: e.id, name: e.fields.name ?? e.id, from: j.from, to: j.to, next: j.path?.[1] ?? j.to, why: j.why });
		}
	}
	return { residents, travellers };
}

/**
 * The map by year (S4 §8, #81). A run's state changes to its routes (their ends, days, kind, Vialux,
 * open, bars; a route built mid-run from its first), its places' regions (a border moved) and its regions'
 * `within`. Replaying them onto `geography.json` gives the map as of any date: whatever changed it in the
 * run (the geography's planned `changes`, or a system) is in the state changes.
 */
export interface MapDelta {
	date: [number, number, number];
	entity: string;
	field: string;
	old?: unknown;
	new: unknown;
	event: string;
}

const ROUTE_FIELDS = new Set(['ends', 'days', 'kind', 'vialux', 'open', 'barred']);

/** The ids that are routes: the file's, and any with `ends` set in the run (built mid-run). */
function routeIds(geo: Geography, deltas: MapDelta[]): Set<string> {
	const ids = new Set(geo.routes.map((r) => r.id));
	for (const d of deltas) if (d.field === 'ends') ids.add(d.entity);
	return ids;
}

/** Only the changes to the map: a route's fields (and a built route's appearing), a place's region, a
 * region's `within`. (A settlement's other fields, its residents, aren't the map.) */
function onMap(geo: Geography, deltas: MapDelta[]): MapDelta[] {
	const routes = routeIds(geo, deltas);
	const places = new Set(geo.places.map((p) => p.id));
	const regions = new Set(geo.regions.map((r) => r.id));
	// The file's own values, cast at the start (old null, new as in the file): not a change.
	const fileValue = new Map<string, unknown>();
	for (const r of geo.routes) for (const [f, v] of Object.entries({ open: true, vialux: false, ...r })) fileValue.set(`${r.id}|${f}`, v);
	for (const p of geo.places) {
		fileValue.set(`${p.id}|region`, p.region);
		fileValue.set(`${p.id}|control`, p.control ?? null);
	}
	for (const r of geo.regions) fileValue.set(`${r.id}|within`, r.within ?? null);
	const cast = (d: MapDelta) =>
		(d.old ?? null) === null &&
		(d.field === 'status' || JSON.stringify(fileValue.get(`${d.entity}|${d.field}`) ?? null) === JSON.stringify(d.new ?? null)) &&
		(places.has(d.entity) || regions.has(d.entity) || geo.routes.some((r) => r.id === d.entity));
	return deltas.filter(
		(d) =>
			!cast(d) &&
			((routes.has(d.entity) && (ROUTE_FIELDS.has(d.field) || d.field === 'status')) ||
			(places.has(d.entity) && (d.field === 'region' || d.field === 'control')) ||
			(regions.has(d.entity) && d.field === 'within'))
	);
}

/** The run's state changes that touch its map, in order. */
export async function loadMapDeltas(run: Run, geo: Geography): Promise<MapDelta[]> {
	const rows: MapDelta[] = [];
	for await (const d of readTable(run, 'state_deltas')) {
		if (d.field === 'region' || d.field === 'control' || d.field === 'within' || d.field === 'status' || ROUTE_FIELDS.has(d.field))
			rows.push({ date: d.date, entity: d.entity, field: d.field, old: d.old, new: d.new, event: d.event });
	}
	return onMap(geo, rows);
}

/** The geography as of the end of the day with sort key `at` (`key` turns a date into its sort key). */
export function geographyAt(geo: Geography, deltas: MapDelta[], at: number, key: (d: [number, number, number]) => number): Geography {
	const out: Geography = JSON.parse(JSON.stringify(geo)); // (a plain copy: geo may be a reactive proxy)
	delete (out as { changes?: unknown }).changes;
	const routes = new Map(out.routes.map((r) => [r.id, r as unknown as Record<string, unknown>]));
	const places = new Map(out.places.map((p) => [p.id, p]));
	const regions = new Map(out.regions.map((r) => [r.id, r]));
	const ids = routeIds(geo, deltas);
	const built = new Map<string, Record<string, unknown>>();
	for (const d of onMap(geo, deltas)) {
		if (key(d.date) > at) continue;
		if (routes.has(d.entity) && ROUTE_FIELDS.has(d.field)) routes.get(d.entity)![d.field] = d.new;
		else if (places.has(d.entity) && d.field === 'region') places.get(d.entity)!.region = d.new as string;
		else if (places.has(d.entity) && d.field === 'control') places.get(d.entity)!.control = (d.new as string | null) ?? null;
		else if (regions.has(d.entity) && d.field === 'within') regions.get(d.entity)!.within = d.new as string | null;
		else if (ids.has(d.entity) && ROUTE_FIELDS.has(d.field)) {
			const r = built.get(d.entity) ?? { id: d.entity };
			r[d.field] = d.new;
			built.set(d.entity, r);
		}
	}
	for (const r of [...built.values()].sort((a, b) => String(a.id).localeCompare(String(b.id))))
		if (r.ends && r.days && r.kind) out.routes.push(r as unknown as Route);
	return out;
}

export interface MapChange {
	date: [number, number, number];
	event: string;
	what: 'built' | 'closed' | 'opened' | 'days' | 'moved' | 'taken' | 'changed';
	site: string; // the route or place
	detail: string;
}

/** What changed the map, one entry per event (in order). */
export function mapChanges(geo: Geography, deltas: MapDelta[]): MapChange[] {
	const known = new Set(geo.routes.map((r) => r.id));
	const ids = routeIds(geo, deltas);
	const out: MapChange[] = [];
	const byEvent = new Map<string, MapDelta[]>();
	for (const d of onMap(geo, deltas)) {
		if (!byEvent.has(d.event)) byEvent.set(d.event, []);
		byEvent.get(d.event)!.push(d);
	}
	for (const [event, ds] of byEvent) {
		const first = ds[0];
		const f = new Map(ds.map((d) => [d.field, d.new]));
		let what: MapChange['what'] = 'changed';
		let detail = '';
		if (ids.has(first.entity) && !known.has(first.entity) && f.has('ends')) {
			what = 'built';
			detail = `${(f.get('ends') as string[]).join(' – ')}, ${f.get('days')} days by ${f.get('kind')}`;
		} else if (f.get('open') === false) what = 'closed';
		else if (f.get('open') === true) what = 'opened';
		else if (f.has('days')) what = 'days';
		else if (f.has('region')) what = 'moved';
		else if (f.has('control')) what = 'taken';
		if (f.has('days') && what !== 'built') detail = `${f.get('days')} days`;
		if (what === 'moved') detail = `into ${f.get('region')}${f.has('control') ? `, held by ${f.get('control') ?? 'nobody'}` : ''}`;
		if (what === 'taken') detail = `held by ${f.get('control') ?? 'nobody'}`;
		out.push({ date: first.date, event, what, site: first.entity, detail });
	}
	return out;
}
