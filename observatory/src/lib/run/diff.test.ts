import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { defaultBaseline, divergentIds, loadDivergence, rootEvents, waveGrid } from './diff';
import { buildIndex, filterEvents } from './index';
import { NodeSource } from './node-source';
import { openRun } from './run';

const source = new NodeSource(resolve(__dirname, '../../../fixtures/runs'));

describe('run diff', async () => {
	const clean = await loadDivergence(source, 'protected');
	const buggy = await loadDivergence(source, 'buggy-protected');

	it('pairs a replay with the run it was replayed from', async () => {
		expect(defaultBaseline((await openRun(source, 'protected')).manifest)).toBe('base');
		expect(defaultBaseline((await openRun(source, 'base')).manifest)).toBeNull();
	});

	it('reads the variant’s divergence report, or nothing when there is none', async () => {
		expect(clean?.runs).toEqual({ baseline: 'base', variant: 'protected' });
		expect(await loadDivergence(source, 'base')).toBeNull();
	});

	it('shows the protect replay’s wave with nothing unexplained', () => {
		const grid = waveGrid(clean!);
		expect(clean!.unexplained_events).toBe(0);
		expect(grid.places.length).toBeGreaterThan(1);
		const cells = grid.places.flatMap((p) => grid.years.map((y) => grid.cell(p, y)));
		expect(cells.reduce((n, c) => n + (c?.divergent ?? 0), 0)).toBe(clean!.divergent_events);
		expect(cells.every((c) => !c || c.unexplained === 0)).toBe(true);
	});

	it('finds the buggy world’s unexplained root events', () => {
		expect(buggy!.unexplained.events.length).toBe(buggy!.unexplained_events);
		const roots = rootEvents(buggy!);
		expect(roots.size).toBeGreaterThan(0);
		for (const e of buggy!.unexplained.events) {
			const causedByAnother = e.causes.some(([k, r]) => k === 'event' && buggy!.unexplained.events.some((u) => u.id === r));
			expect(roots.has(e.id)).toBe(!causedByAnother);
		}
	});

	it('gives each side its divergent ids', () => {
		const v = divergentIds(clean!, 'variant');
		const b = divergentIds(clean!, 'baseline');
		expect(v.size + b.size - clean!.divergent.changed.length).toBe(clean!.divergent_events);
	});

	it('lets the event browser show one wave cell: where, years and divergent ids', async () => {
		const run = await openRun(source, 'protected');
		const index = await buildIndex(run);
		const grid = waveGrid(clean!);
		const place = grid.places.find((p) => p && grid.years.some((y) => (grid.cell(p, y)?.divergent ?? 0) > 0))!;
		const year = grid.years.find((y) => (grid.cell(place, y)?.divergent ?? 0) > 0)!;
		const only = divergentIds(clean!, 'variant');
		const shown = filterEvents(index, {
			place: place ?? undefined,
			from: [year[0], year[1], 0],
			to: [year[0], year[1], run.calendar.daysPerYear - 1],
			ids: only
		});
		// the variant's browser shows the cell's divergent events except those only the baseline has
		const cell = grid.cell(place, year)!;
		expect(shown.length).toBeGreaterThan(0);
		expect(shown.length).toBeLessThanOrEqual(cell.divergent);
		expect(shown.length).toBeGreaterThanOrEqual(cell.divergent - clean!.divergent.only_baseline.length);
		for (const i of shown) expect(only.has(index.ids[i])).toBe(true);
	});
});

describe('where an event happened', async () => {
	it('is its place, else the scope that decided it', async () => {
		const index = await buildIndex(await openRun(source, 'base'));
		const granary = index.ids.findIndex((_, i) => index.types[index.typeOf[i]] === 'toy.granary');
		expect(index.places[index.placeOf[granary]]).toBe(index.row(granary).scope);
	});
});
