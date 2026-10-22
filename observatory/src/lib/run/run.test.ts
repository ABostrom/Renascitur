import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { Calendar } from './calendar';
import { lines } from './jsonl';
import { NodeSource } from './node-source';
import { openRun, readTable } from './run';
import { segmentFiles } from './segments';

const RUNS = resolve(__dirname, '../../../fixtures/runs');
const VECTORS = resolve(__dirname, '../../../../tests/fixtures/calendar_vectors.json');

function streamOf(text: string): ReadableStream<Uint8Array> {
	return new Blob([text]).stream();
}

async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
	const out: T[] = [];
	for await (const x of it) out.push(x);
	return out;
}

describe('jsonl', () => {
	it('splits only on \\n, keeping U+2028 and \\x85 inside strings', async () => {
		const row = { n: 'a b\u0085c d' };
		const got = await collect(lines(streamOf(JSON.stringify(row) + '\n'), false));
		expect(got.map((l) => JSON.parse(l))).toEqual([row]);
	});

	it('drops a trailing line with no newline (an in-progress write)', async () => {
		const got = await collect(lines(streamOf('{"a":1}\n{"a":2}\n{"a":'), false));
		expect(got).toEqual(['{"a":1}', '{"a":2}']);
	});

	it('handles lines split across chunks and multi-byte characters', async () => {
		const enc = new TextEncoder().encode('{"n":"é"}\n{"n":"ü"}\n');
		const parts = [enc.slice(0, 7), enc.slice(7, 8), enc.slice(8)]; // split inside "é"
		const stream = new ReadableStream<Uint8Array>({
			start(c) {
				parts.forEach((p) => c.enqueue(p));
				c.close();
			}
		});
		expect((await collect(lines(stream, false))).map((l) => JSON.parse(l).n)).toEqual(['é', 'ü']);
	});
});

describe('calendar', () => {
	const data = JSON.parse(readFileSync(VECTORS, 'utf-8'));
	const cal = Calendar.fromJson(data.calendar);
	it('formats and parses exactly like the Python calendar', () => {
		for (const v of data.vectors) {
			expect(cal.format(v.date, 'year')).toBe(v.year);
			expect(cal.format(v.date, 'season')).toBe(v.season);
			expect(cal.format(v.date, 'day')).toBe(v.day);
			expect(cal.parse(v.day)).toEqual(v.date);
		}
	});
	it('parses year and season forms to their first day', () => {
		expect(cal.parse('1X 37')).toEqual([1, 37, 0]);
		expect(cal.parse('1X 37 Summer')).toEqual([1, 37, 90]);
		expect(() => cal.parse('9Q 1')).toThrow();
	});
});

describe('run folders', () => {
	const source = new NodeSource(RUNS);

	it('opens a run and reads its manifest', async () => {
		const run = await openRun(source, 'base');
		expect(run.name).toBe('base');
		expect(run.manifest.meta.complete).toBe(true);
		expect(run.calendar.format([1, 3, 0], 'year')).toBe('1X 3');
	});

	it('reads every event in order across closed segments', async () => {
		const run = await openRun(source, 'base');
		const events = await collect(readTable(run, 'events'));
		expect(events.length).toBeGreaterThan(100);
		expect(events.some((e) => e.type === 'toy.birth' || e.type === 'toy.death')).toBe(true);
		const dates = events.map((e) => e.date[1] * 1000 + e.date[2]);
		expect(dates).toEqual([...dates].sort((a, b) => a - b));
	});

	it('selects segments the way the engine recovers them', async () => {
		const run = await openRun(source, 'interrupted');
		const files = await segmentFiles(run, 'events');
		const open = run.manifest.segments;
		expect(files.at(-1)).toEqual({ path: `events/seg-${String(open).padStart(5, '0')}.jsonl`, gz: false });
		expect(files.slice(0, -1).every((f) => f.gz)).toBe(true);
		const events = await collect(readTable(run, 'events'));
		const ids = events.map((e) => e.id);
		expect(ids).toContain('xopen1'); // the open segment, read raw
		expect(ids).not.toContain('xnever'); // its stray .gz is ignored
		expect(ids.at(-1)).toBe('xopen1'); // the partial last line is dropped
	});

	it('reads the replay and its diff report', async () => {
		const run = await openRun(source, 'protected');
		expect(run.manifest.parent).toEqual({ run: 'base', segments: 1 });
		const report = JSON.parse(await source.text('protected/analysis/divergence.json'));
		expect(report.unexplained_events).toBe(0);
	});
});
