import { describe, expect, it } from 'vitest';

import { Calendar } from './calendar';
import { branches, rippleRequest } from './ripple';
import type { RunListing } from './run';

const CAL = new Calendar({
	ages: [{ abbrev: '4A', index: 4, last_year: 256, name: 'Fourth Age' }],
	months: [['M1', 30], ['M2', 30], ['M3', 30], ['M4', 30], ['M5', 30], ['M6', 30], ['M7', 30], ['M8', 30], ['M9', 30], ['M10', 30], ['M11', 30], ['M12', 30]],
	seasons: [['Spring', 90], ['Summer', 90], ['Autumn', 90], ['Winter', 90]]
} as never);

describe('rippleRequest', () => {
	it("builds each kind's params from the form, a year for `until` meaning its end", () => {
		expect(rippleRequest(CAL, 'base', { kind: 'protect', target: 'p:a', date: '4A 3', until: '4A 9' })).toEqual({
			run: 'base', kind: 'protect', target: 'p:a', date: '4A 3', params: { until: [4, 9, 359] }
		});
		expect(rippleRequest(CAL, 'base', { kind: 'favour', target: 'p:a', date: '4A 3', until: '4A 5', by: '0.3' }).params).toEqual({
			until: [4, 5, 359], by: 0.3
		});
		expect(rippleRequest(CAL, 'base', { kind: 'doom', target: 'p:a', date: '4A 3', name: 'mine' })).toEqual({
			run: 'base', kind: 'doom', target: 'p:a', date: '4A 3', name: 'mine'
		});
		expect(rippleRequest(CAL, 'b', { kind: 'structural', target: 'g:x', date: '4A 3', open: 'closed', why: 'a rockslide' }).params).toEqual({
			open: false, why: 'a rockslide'
		});
		const claim = { pred: 'killed', args: { victim: 'p:v', by: 'p:k' } };
		expect(rippleRequest(CAL, 'b', { kind: 'plant', target: 't:x', date: '4A 3', claim: JSON.stringify(claim), share: '0.4' }).params).toEqual({
			claim, share: 0.4
		});
	});

	it('refuses what the engine would, before asking it', () => {
		expect(() => rippleRequest(CAL, 'b', { kind: 'protect', target: 'p:a', date: '4A 3' })).toThrow(/until/);
		expect(() => rippleRequest(CAL, 'b', { kind: 'protect', target: 'p:a', date: '4A 3', until: '4A 1' })).toThrow(/after/);
		expect(() => rippleRequest(CAL, 'b', { kind: 'doom', target: '', date: '4A 3' })).toThrow(/target/);
		expect(() => rippleRequest(CAL, 'b', { kind: 'doom', target: 'p:a', date: 'soon' })).toThrow();
		expect(() => rippleRequest(CAL, 'b', { kind: 'plant', target: 't:x', date: '4A 3', claim: '{nope' })).toThrow(/claim/);
	});
});

const run = (name: string, from?: string, ripples: { id: string; kind: string; target: string; date: string }[] = []) =>
	({ name, manifest: { meta: { replayed_from: from ? { run: from, at: [4, 1, 0] } : undefined, recipe: { ripple: ripples } } } }) as unknown as RunListing;

describe('branches', () => {
	it('grows a tree of runs from the ones they were replayed from, roots and leaves in name order', () => {
		const tree = branches([run('b-doom1', 'base'), run('base'), run('other'), run('both', 'b-doom1'), run('b-luck2', 'base')]);
		expect(tree.map((n) => [n.run.name, n.depth])).toEqual([
			['base', 0],
			['b-doom1', 1],
			['both', 2],
			['b-luck2', 1],
			['other', 0]
		]);
	});

	it("names what each branch added to its parent's ripples", () => {
		const r1 = { id: 'doom1', kind: 'doom', target: 'p:a', date: '4A 3' };
		const r2 = { id: 'protect2', kind: 'protect', target: 'p:b', date: '4A 4' };
		const tree = branches([run('base'), run('b1', 'base', [r1]), run('b2', 'b1', [r1, r2])]);
		expect(tree.map((n) => n.added.map((r) => r.id))).toEqual([[], ['doom1'], ['protect2']]);
	});

	it('places a branch that was run from the start under the run it was authored on', () => {
		const fresh = { name: 'b-doom1', manifest: { meta: { ripple_of: { run: 'base', ripple: 'doom1' }, recipe: {} } } } as unknown as RunListing;
		expect(branches([run('base'), fresh]).map((n) => [n.run.name, n.depth])).toEqual([['base', 0], ['b-doom1', 1]]);
	});

	it('treats a run whose parent is missing as a root', () => {
		expect(branches([run('lost', 'gone')]).map((n) => [n.run.name, n.depth])).toEqual([['lost', 0]]);
	});
});
