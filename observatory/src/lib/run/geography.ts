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
