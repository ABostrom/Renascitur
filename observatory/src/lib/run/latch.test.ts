import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { NodeSource } from './node-source';
import type { Manifest } from './run';
import { compareArcs, latchCommand, loadLatch, whatIfsOf } from './latch';
import { loadStories } from './stories';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

describe('latch points', async () => {
	const source = new NodeSource(RUNS);
	const latch = (await loadLatch(source, 'kin'))!;

	it('loads analysis/latch.json, or null when `renasci latch` has not been run', async () => {
		expect(latch.points.length).toBeGreaterThan(5);
		expect(latch.points.map((p) => p.rank)).toEqual(latch.points.map((_, i) => i + 1));
		expect(new Set(latch.points.map((p) => p.kind))).toEqual(new Set(['died_unfulfilled', 'near_miss']));
		expect(await loadLatch(source, 'base')).toBeNull();
	});

	it('finds the what-ifs launched from a run, by the point they tried', () => {
		const m = (latch_of: unknown, name: string) => ({ name, manifest: { meta: { latch_of } } as unknown as Manifest });
		const runs = [m({ run: 'kin', rank: 1 }, 'kin-latch1'), m({ run: 'kin', rank: 1 }, 'kin-latch1-2'),
			m({ run: 'kin', rank: 3 }, 'kin-latch3'), m({ run: 'other', rank: 1 }, 'other-latch1'), m(undefined, 'kin')];
		const got = whatIfsOf(runs, 'kin');
		expect([...got.keys()].sort()).toEqual([1, 3]);
		expect(got.get(1)).toEqual(['kin-latch1', 'kin-latch1-2']);
	});

	it('writes the CLI command for a launch, with the adjustments', () => {
		expect(latchCommand('kin', 3, {})).toBe('uv run renasci latch runs/kin --launch 3');
		expect(latchCommand('kin', 3, { kind: 'protect', date: '1K 20', until: '1K 30' })).toBe(
			"uv run renasci latch runs/kin --launch 3 --kind protect --date '1K 20' --until '1K 30'"
		);
	});

	it('compares the stories of a run and its what-if', async () => {
		const base = (await loadStories(source, 'kin'))!;
		const variant = (await loadStories(source, 'kin-latch1'))!;
		const c = compareArcs(base, variant);
		expect(c.shared + c.onlyBaseline.length).toBe(base.arcs.length);
		expect(c.shared + c.onlyVariant.length).toBe(variant.arcs.length);
		expect(c.onlyBaseline.length + c.onlyVariant.length + c.changed.length).toBeGreaterThan(0);
		for (const [a, b] of c.changed) expect(a.ambition).toBe(b.ambition);
	});
});
