import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { dominant, lineage, loadClaims, type Topic } from './knowledge';
import { NodeSource } from './node-source';

const RUNS = resolve(__dirname, '../../../fixtures/runs');

const claim = (key: string, parent: string | null, shares: Record<string, number> = {}, truth = 'false') => ({
	key,
	claim: { pred: 'fault', args: {} },
	text: key,
	truth,
	basis: [],
	holders: 1,
	shares,
	parent,
	first: [1, 0, 0] as [number, number, number],
	lies: 0
});

const TOPIC: Topic = {
	topic: 'why:e',
	about: 'e',
	about_type: 'ward.failure',
	about_name: 'the ward failure',
	holders: 3,
	people: 3,
	claims: [
		claim('c:b', 'c:a', { 't:x': 0.1, 't:y': 0.4 }),
		claim('c:a', null, { 't:x': 0.3 }, 'true'),
		claim('c:c', 'c:b'),
		claim('c:d', 'c:gone') // (drifted from a claim nobody holds any more: a root of its own)
	]
};

describe('knowledge', async () => {
	const source = new NodeSource(RUNS);

	it('loads analysis/claims.json, or null when `renasci claims` has not been run', async () => {
		const claims = (await loadClaims(source, 'ward'))!;
		const ward = claims.topics.find((t) => t.about_type === 'ward.failure')!;
		expect(ward.claims.some((c) => c.truth === 'false' && c.lies > 0)).toBe(true);
		expect(await loadClaims(source, 'base')).toBeNull();
	});

	it('lays a topic out as lineage: each claim under the one it drifted from', () => {
		expect(lineage(TOPIC).map((r) => [r.claim.key, r.depth])).toEqual([
			['c:a', 0],
			['c:b', 1],
			['c:c', 2],
			['c:d', 0]
		]);
	});

	it('finds what each settlement mostly believes', () => {
		const d = dominant(TOPIC);
		expect(d['t:x'].claim.key).toBe('c:a');
		expect(d['t:y'].claim.key).toBe('c:b');
		expect(d['t:y'].share).toBeCloseTo(0.4);
	});
});
