import type { DateTuple } from './calendar';
import { readTable, type Run } from './run';

/**
 * Canon strain (S1 pins): what the director did to honour canon, and how every pin ended.
 *
 * - the run's `strain` table: each guard (a death turned into a near miss: its event), force (the
 *   pinned event constructed: its event is the `pins` table's "forced" row) and violation (at a
 *   deadline: no event, a reason);
 * - the run's `pins` table: each pin's status changes (met, forced, violated, bound). A pin met at the
 *   start (canon the scenario already placed) or still open at the end logs no change;
 * - `canon.json`, when the run was cast from a vault: every pin given to the run, the pins dropped
 *   before it (casting), and the vault check's verdicts (out of scope, unsupported, infeasible).
 */
export interface StrainEntry {
	date: DateTuple;
	action: 'guard' | 'force' | 'violated' | string;
	pin: string;
	kind: string;
	entity: string | null; // who a guard saved
	event: string | null;
	reason: string | null;
}

export interface PinRow {
	id: string;
	kind: string | null;
	window: [DateTuple, DateTuple] | null;
	status: string; // satisfied, forced, violated, out_of_scope, unsupported, infeasible, dropped, no change logged
	event: string | null; // the event that met or forced it
	date: DateTuple | null;
	guards: number;
	why: string | null;
	notes: string[]; // vault notes it came from
}

export interface StrainReport {
	entries: StrainEntry[];
	pins: PinRow[];
	counts: { guard: number; force: number; violated: number; met: number; outside: number };
}

const OUTSIDE = new Set(['out_of_scope', 'unsupported', 'infeasible', 'dropped']);

export function strainReport(strain: any[], pinRows: any[], canon: any | null): StrainReport {
	const last = new Map<string, any>(); // each pin's last status change
	const forced = new Map<string, string>();
	const violatedAt = new Map<string, string>(); // `${pin}|${date}` -> the event that broke it, if any
	for (const p of pinRows) {
		last.set(p.pin, p);
		if (p.status === 'forced' && p.event) forced.set(p.pin, p.event);
		if (p.status === 'violated' && p.event) violatedAt.set(`${p.pin}|${p.date}`, p.event);
	}
	const entries: StrainEntry[] = strain.map((s) => ({
		date: s.date,
		action: s.action,
		pin: s.pin,
		kind: s.kind,
		entity: s.entity ?? null,
		event:
			s.event ??
			(s.action === 'force' ? forced.get(s.pin) : s.action === 'violated' ? violatedAt.get(`${s.pin}|${s.date}`) : null) ??
			null,
		reason: s.reason ?? null
	}));
	const guards = new Map<string, number>();
	for (const e of entries) if (e.action === 'guard') guards.set(e.pin, (guards.get(e.pin) ?? 0) + 1);

	const verdicts: Record<string, { verdict: string; why: string; notes: string[] }> = canon?.feasibility?.pins ?? {};
	const rows = new Map<string, PinRow>();
	const add = (id: string, kind: string | null, window: PinRow['window']) => {
		if (rows.has(id)) return rows.get(id)!;
		const v = verdicts[id];
		const change = last.get(id);
		const row: PinRow = {
			id,
			kind,
			window,
			status: change?.status ?? (v && v.verdict !== 'ok' ? v.verdict : 'no change logged'),
			event: change?.event ?? null,
			date: change?.date ?? null,
			guards: guards.get(id) ?? 0,
			why: v && v.verdict !== 'ok' ? v.why : null,
			notes: v?.notes ?? []
		};
		rows.set(id, row);
		return row;
	};
	for (const p of canon?.pins ?? []) add(p.id, p.kind ?? null, p.window ?? null);
	for (const id of last.keys()) add(id, null, null);
	for (const e of entries) add(e.pin, e.kind, null);
	for (const d of canon?.dropped ?? []) {
		const row = add(d.pin, null, null);
		row.status = 'dropped';
		row.why = d.why;
	}
	for (const [id, v] of Object.entries(verdicts)) if (v.verdict !== 'ok') add(id, null, null);

	const list = [...rows.values()].sort((a, b) => a.id.localeCompare(b.id));
	return {
		entries,
		pins: list,
		counts: {
			guard: entries.filter((e) => e.action === 'guard').length,
			force: entries.filter((e) => e.action === 'force').length,
			violated: entries.filter((e) => e.action === 'violated').length,
			met: list.filter((p) => p.status === 'satisfied' && p.guards === 0).length, // (met only after a guard is strain)
			outside: list.filter((p) => OUTSIDE.has(p.status)).length
		}
	};
}

/** A run's strain report, or null when the run had no pins at all. */
export async function loadStrain(run: Run): Promise<StrainReport | null> {
	const strain: any[] = [];
	const pins: any[] = [];
	for await (const r of readTable(run, 'strain')) strain.push(r);
	for await (const r of readTable(run, 'pins')) pins.push(r);
	const path = `${run.name}/canon.json`;
	const canon = (await run.source.has(path)) ? JSON.parse(await run.source.text(path)) : null;
	if (!canon && strain.length === 0 && pins.length === 0) return null;
	return strainReport(strain, pins, canon);
}
