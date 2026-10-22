import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { buildIndex, filterEvents, eventDetail, segmentsFor } from './index';
import { NodeSource } from './node-source';
import { openRun } from './run';

const source = new NodeSource(resolve(__dirname, '../../../fixtures/runs'));

describe('event index', async () => {
	const run = await openRun(source, 'base');
	const index = await buildIndex(run);

	it('holds every event, in date order, with types and places', () => {
		expect(index.count).toBeGreaterThan(100);
		for (let i = 1; i < index.count; i++) expect(index.keys[i]).toBeGreaterThanOrEqual(index.keys[i - 1]);
		expect(index.types).toContain('toy.granary');
		expect(index.places).toContain('t:Ashford');
		expect(index.row(0).id).toBe(index.ids[0]);
	});

	it('filters by type, place, participant, date and text, together', () => {
		const granary = filterEvents(index, { type: 'toy.granary' });
		expect(granary.length).toBe(index.typeCounts.get('toy.granary'));
		expect([...granary].every((i) => index.row(i).type === 'toy.granary')).toBe(true);

		const someone = index.row([...filterEvents(index, { type: 'toy.birth' })][0]).roles.mother[0];
		const theirs = filterEvents(index, { entity: someone });
		expect(theirs.length).toBeGreaterThan(0);
		expect([...theirs].every((i) => JSON.stringify(index.row(i).roles).includes(someone))).toBe(true);

		const year2 = filterEvents(index, { from: [1, 2, 0], to: [1, 2, 359] });
		expect([...year2].every((i) => index.row(i).date[1] === 2)).toBe(true);
		expect(year2.length).toBeGreaterThan(0);

		const text = filterEvents(index, { text: 'FAMINE' });
		expect([...text].every((i) => index.lines[i].toLowerCase().includes('famine'))).toBe(true);

		const both = filterEvents(index, { type: 'toy.granary', place: 'nowhere' });
		expect(both.length).toBe(0);
	});

	it('finds the segments that can hold a date from the sidecars', async () => {
		expect(await segmentsFor(run, [1, 1, 10])).toEqual([0]);
		const last = run.manifest.segments - 1;
		expect(await segmentsFor(run, [1, 5, 100])).toEqual([last]);
		// after the last closed segment's last event: the open segment
		expect(await segmentsFor(run, [1, 400, 0])).toEqual([run.manifest.segments]);
	});

	it("gives an event's detail: its scope's reads and its hinges", async () => {
		const i = [...filterEvents(index, { type: 'toy.birth' })][0];
		const detail = await eventDetail(run, index.row(i));
		expect(detail.scope?.scope).toBe(index.row(i).place);
		expect(detail.scope?.reads.length).toBeGreaterThan(0);
		expect(detail.scope?.events).toContain(index.row(i).id);
		expect(Array.isArray(detail.hinges)).toBe(true);
	});
});

describe('review fixes', async () => {
	const run = await openRun(source, 'base');
	const index = await buildIndex(run);

	it("knows each event's segment, so detail needs no sidecars", async () => {
		expect(index.segmentOf.length).toBe(index.count);
		const last = index.count - 1;
		expect(index.segmentOf[last]).toBe(run.manifest.segments - 1);
		const src = run.source;
		const hidden = {
			list: async (d: string) => (d.endsWith('/index') ? [] : src.list(d)), // no sidecars anywhere
			has: (p: string) => src.has(p),
			stream: (p: string) => src.stream(p),
			text: (p: string) => src.text(p)
		};
		const noSidecars = { ...run, source: hidden };
		const i = [...filterEvents(index, { type: 'toy.birth' })][0];
		const detail = await eventDetail(noSidecars, index.row(i), index.segmentOf[i]);
		expect(detail.scope?.events).toContain(index.row(i).id);
	});

	it('includes the activation-wide reads alongside the scope reads', async () => {
		const i = [...filterEvents(index, { type: 'toy.birth' })][0];
		const detail = await eventDetail(run, index.row(i), index.segmentOf[i]);
		expect(detail.scope?.scope).toBe(index.row(i).scope);
		expect(Array.isArray(detail.unscoped?.reads ?? [])).toBe(true);
	});
});
