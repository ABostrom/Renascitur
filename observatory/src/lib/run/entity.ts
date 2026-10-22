import type { DateTuple } from './calendar';
import type { EventIndex } from './index';
import { readTable, type Run } from './run';

export interface EntityChange {
	date: DateTuple;
	field: string;
	old?: unknown;
	new?: unknown;
	event: string;
	bulk: boolean; // a column cell (aggregate state): the value itself isn't logged, only its hash
}

export interface EntityDetailData {
	record: { id: string; kind: string; status: string; fields: Record<string, unknown> } | null;
	cells: Record<string, number>; // final column values for this entity
	events: number[]; // indices into the event index
	changes: EntityChange[];
}

const finalStates = new WeakMap<Run, Promise<any>>();

/** The run's final state (state.json.gz), loaded once. */
export function finalState(run: Run): Promise<any> {
	let p = finalStates.get(run);
	if (!p) {
		p = (async () => {
			const stream = await run.source.stream(`${run.name}/state.json.gz`);
			const text = await new Response(
				stream.pipeThrough(new DecompressionStream('gzip') as unknown as TransformStream<Uint8Array, Uint8Array>)
			).text();
			return JSON.parse(text);
		})();
		p.catch(() => finalStates.delete(run)); // a run still being written may have its state later
		finalStates.set(run, p);
	}
	return p;
}

/** An entity's final record, the events it took part in, and every change to its state. */
export async function entityDetail(run: Run, index: EventIndex, id: string): Promise<EntityDetailData> {
	let record: EntityDetailData['record'] = null;
	const cells: Record<string, number> = {};
	// An incomplete run has no final state yet; its events and changes still work.
	if (run.manifest.meta.complete !== false) {
		const state = await finalState(run);
		record = state.entities.find((e: { id: string }) => e.id === id) ?? null;
		for (const [name, col] of Object.entries(state.columns as Record<string, { ids: string[]; data: number[] }>)) {
			const at = col.ids.indexOf(id);
			if (at >= 0) cells[name] = col.data[at];
		}
	}
	const changes: EntityChange[] = [];
	for await (const d of readTable(run, 'state_deltas')) {
		if (d.entity === id) changes.push({ date: d.date, field: d.field, old: d.old, new: d.new, event: d.event, bulk: false });
	}
	for await (const b of readTable(run, 'bulk_deltas')) {
		if (!b.ids.includes(id)) continue;
		for (const field of (b.components as string[] | undefined) ?? [b.component])
			changes.push({ date: b.date, field, event: b.event, bulk: true });
	}
	changes.sort((a, b) => run.calendar.sortKey(a.date) - run.calendar.sortKey(b.date));
	return { record, cells, events: [...(index.byEntity.get(id) ?? [])], changes };
}
