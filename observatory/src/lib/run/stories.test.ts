import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { NodeSource } from './node-source';
import { glyph, inPeriod, loadStories, presets, river, runYears } from './stories';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

describe('stories', async () => {
	const source = new NodeSource(RUNS);
	const stories = (await loadStories(source, 'kin'))!;

	it('loads analysis/stories.json, or null when `renasci stories` has not been run', async () => {
		expect(stories.arcs.length).toBeGreaterThan(50);
		expect(stories.sagas.length).toBeGreaterThan(0);
		expect(await loadStories(source, 'base')).toBeNull();
	});

	it('offers presets: the whole run, then generations and decades', () => {
		const [lo, hi] = runYears(stories);
		const ps = presets(lo, hi);
		expect(ps[0]).toEqual({ label: 'Whole run', from: lo, to: hi });
		const decades = ps.filter((p) => p.label.startsWith('Years'));
		expect(decades.length).toBeGreaterThan(1);
		for (const p of ps) expect(p.from <= p.to && p.from >= lo && p.to <= hi).toBe(true);
	});

	it('keeps what flows through a period, most salient first', () => {
		const got = inPeriod(stories, 10, 20);
		expect(got.arcs.length).toBeGreaterThan(0);
		for (const a of got.arcs) expect(a.span[0] <= 20 && a.span[1] >= 10).toBe(true);
		for (const s of got.sagas) expect(s.span[0] <= 20 && s.span[1] >= 10).toBe(true);
		const sal = got.arcs.map((a) => a.salience);
		expect(sal).toEqual([...sal].sort((x, y) => y - x));
	});

	it('lays the river out by house, bars in lanes that never overlap', () => {
		const lanes = river(stories.arcs, 1, 40);
		expect(lanes.length).toBeGreaterThan(1);
		expect(lanes.at(-1)!.house).toBeNull(); // the houseless last
		for (const house of lanes) {
			const byLane = new Map<number, [number, number][]>();
			for (const b of house.bars) {
				const spans = byLane.get(b.lane) ?? [];
				for (const [x0, x1] of spans) expect(b.from > x1 || b.to < x0).toBe(true);
				spans.push([b.from, b.to]);
				byLane.set(b.lane, spans);
			}
			expect(house.lanes).toBe(Math.max(0, ...house.bars.map((b) => b.lane)) + 1);
		}
	});

	it('clips bars to the period and marks turning points', () => {
		const lanes = river(stories.arcs, 20, 25);
		for (const b of lanes.flatMap((h) => h.bars)) {
			expect(b.from >= 20 && b.to <= 25).toBe(true);
			for (const t of b.turns) expect(t.year >= 20 && t.year <= 25).toBe(true);
		}
		expect(lanes.flatMap((h) => h.bars).some((b) => b.turns.length > 0)).toBe(true);
	});

	it('leaves a column after each bar for its glyph, and runs a still-wanted bar to the period end', () => {
		for (const house of river(stories.arcs, 1, 40)) {
			const byLane = new Map<number, { from: number; to: number }[]>();
			for (const b of house.bars) byLane.set(b.lane, [...(byLane.get(b.lane) ?? []), b]);
			for (const bars of byLane.values()) {
				bars.sort((x, y) => x.from - y.from);
				for (let i = 1; i < bars.length; i++) expect(bars[i].from).toBeGreaterThan(bars[i - 1].to + 1);
			}
		}
		const active = river(stories.arcs, 1, 40).flatMap((h) => h.bars).filter((b) => b.arc.outcome === 'active');
		for (const b of active) expect(b.to).toBe(40);
	});

	it('gives every outcome a glyph', () => {
		for (const o of ['fulfilled', 'thwarted', 'abandoned', 'died_unfulfilled', 'active']) expect(glyph(o)).not.toBe('');
	});
});
