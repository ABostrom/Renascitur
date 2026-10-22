import { Calendar, type CalendarJson } from './calendar';
import { lines } from './jsonl';
import { segmentFiles } from './segments';
import type { RunSource } from './source';

export interface Manifest {
	format: number;
	engine: string;
	versions?: Record<string, string>;
	segments: number;
	marks: { segment: number; before: [number, number, number] }[];
	parent: { run: string; segments: number } | null;
	tables: Record<string, number>;
	meta: {
		recipe?: Record<string, any>;
		complete?: boolean;
		calendar?: CalendarJson;
		state_hash?: string;
		replayed_from?: { run: string; at: [number, number, number] };
		[k: string]: unknown;
	};
}

export interface Run {
	name: string;
	source: RunSource;
	manifest: Manifest;
	calendar: Calendar;
}

const FALLBACK_CALENDAR: CalendarJson = {
	ages: [],
	months: Array.from({ length: 12 }, (_, i) => [`Month ${i + 1}`, 30] as [string, number]),
	seasons: [
		['Spring', 90],
		['Summer', 90],
		['Autumn', 90],
		['Winter', 90]
	]
};

export async function openRun(source: RunSource, name: string): Promise<Run> {
	const manifest = JSON.parse(await source.text(`${name}/manifest.json`)) as Manifest;
	if (manifest.format !== 1) throw new Error(`run folder format ${manifest.format} is not supported`);
	const calendar = Calendar.fromJson(manifest.meta.calendar ?? FALLBACK_CALENDAR);
	return { name, source, manifest, calendar };
}

/** Every row of a table, in order: closed segments, then the open one. Streams; never holds a file. */
export async function* readTable(run: Run, table: string): AsyncGenerator<any> {
	for (const f of await segmentFiles(run, table)) {
		const stream = await run.source.stream(`${run.name}/${f.path}`);
		for await (const line of lines(stream, f.gz)) yield JSON.parse(line);
	}
}

export interface RunListing {
	name: string;
	manifest: Manifest;
}

/** The runs `renasci observe` serves. */
export async function listRuns(base = '/runs'): Promise<RunListing[]> {
	const r = await fetch(`${base}/index.json`);
	if (!r.ok) throw new Error(`cannot list runs (${r.status}); is this served by \`renasci observe\`?`);
	return r.json();
}
