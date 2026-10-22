import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { buildCauseGraph, nodeKey } from './causes';
import { entityDetail } from './entity';
import { buildIndex } from './index';
import { NodeSource } from './node-source';
import { openRun } from './run';

const source = new NodeSource(resolve(__dirname, '../../../fixtures/runs'));

describe('cause graph', async () => {
	const run = await openRun(source, 'protected');
	const index = await buildIndex(run);
	const graph = await buildCauseGraph(index);

	const secret = index.row(index.ids.findIndex((_, i) => index.types[index.typeOf[i]] === 'ripple.doom'));
	const death = index.row(
		index.ids.findIndex((_, i) => {
			const e = index.row(i);
			return e.type === 'toy.death' && e.causes.some(([k, r]: [string, string]) => k === 'ripple' && r === 'r2');
		})
	);

	it('walks forward from a ripple to the world it changed', () => {
		const fromRipple = graph.children({ kind: 'ripple', ref: 'r2' }).map(nodeKey);
		expect(fromRipple).toContain(`event:${secret.id}`);
		expect(fromRipple).toContain(`event:${death.id}`);
	});

	it("walks back from the doom's death to the author's hand", () => {
		const why = graph.parents({ kind: 'event', ref: death.id }).map(nodeKey);
		expect(why).toContain('ripple:r2');
		expect(why).toContain(`event:${secret.id}`);
		expect(graph.parents({ kind: 'event', ref: secret.id }).map(nodeKey)).toContain('ripple:r2');
	});

	it('treats activations as nodes: an event came from its activation', () => {
		const e = index.row(index.ids.findIndex((_, i) => index.types[index.typeOf[i]] === 'toy.granary'));
		const parents = graph.parents({ kind: 'event', ref: e.id });
		expect(parents.some((p) => p.kind === 'activation' && p.ref === e.activation)).toBe(true);
		expect(graph.children({ kind: 'activation', ref: e.activation }).map(nodeKey)).toContain(`event:${e.id}`);
	});

	it('labels nodes for people', () => {
		expect(graph.label({ kind: 'event', ref: death.id })).toContain('toy.death');
		expect(graph.label({ kind: 'ripple', ref: 'r2' })).toContain('r2');
	});
});

describe('entity detail', async () => {
	const run = await openRun(source, 'base');
	const index = await buildIndex(run);

	it("gives a village its record, events and every state change, including column cells", async () => {
		const village = await entityDetail(run, index, 't:Ashford');
		expect(village.record?.kind).toBe('place');
		expect(village.events.length).toBeGreaterThan(0);
		expect(village.changes.some((c) => c.field === 'residents')).toBe(true);
		const valley = await entityDetail(run, index, 't:North');
		expect(valley.changes.some((c) => c.field === 'stock' && c.bulk)).toBe(true);
		expect(valley.cells.stock).toBeGreaterThanOrEqual(0);
	});

	it('handles an entity with no record', async () => {
		const ghost = await entityDetail(run, index, 't:nobody');
		expect(ghost.record).toBeNull();
		expect(ghost.events).toEqual([]);
	});
});
