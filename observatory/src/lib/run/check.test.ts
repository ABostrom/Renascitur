import { describe, expect, it } from 'vitest';

import { claimLine, findingsOf, type CheckReport } from './check';

const claim = (finding: string, pred = 'killed') =>
	({ pred, args: { victim: 'p:v', by: 'p:k' }, date: [4, 9], by: 'killed.0', verdict: 'false', finding, events: ['x:1'] }) as never;

const report: CheckReport = {
	schema: 'renasci.check/1',
	run: 'm4',
	pov: { kind: 'omniscient', id: null, name: 'omniscient' },
	text: 'abc',
	counts: { contradiction: 2, leak: 0, half: 0, ambiguous: 1, invention: 0, consistent: 1 },
	sentences: [
		{ n: 1, text: 'One.', date: null, claims: [claim('consistent'), claim('half')], unresolved: [] },
		{
			n: 2,
			text: 'Two.',
			date: null,
			claims: [claim('contradiction')],
			unresolved: [{ mention: 'Cara', kind: 'person', why: 'ambiguous', finding: 'ambiguous', candidates: [{ id: 'p:a' }] }]
		},
		{ n: 3, text: 'Three.', date: null, claims: [claim('contradiction')], unresolved: [] }
	]
};

describe('canon-check findings', () => {
	it('puts contradictions first, then by sentence, and leaves out what is consistent', () => {
		const rows = findingsOf(report);
		expect(rows.map((r) => [r.finding, r.n])).toEqual([
			['contradiction', 2],
			['contradiction', 3],
			['half', 1],
			['ambiguous', 2]
		]);
		expect(rows[3].type).toBe('mention');
	});

	it('reads a claim as a line', () => {
		expect(claimLine(claim('contradiction'))).toBe('killed(victim: p:v, by: p:k) at 4:9');
	});
});
