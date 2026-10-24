import { describe, expect, it } from 'vitest';

import type { Geography } from './geography';
import { borders, colours, relationSeries, wars, type PolityEvent, type RelationDelta } from './polities';

const ev = (id: string, type: string, year: number, roles: Record<string, string[]>, payload: Record<string, unknown> = {}): PolityEvent => ({
	id,
	type,
	date: [4, year, 0],
	roles,
	payload
});

describe('colours', () => {
	it('gives each polity a series colour by id, so a polity keeps its colour whoever else exists', () => {
		const c = colours(['p:b', 'p:a']);
		expect(c).toEqual({ 'p:a': 'var(--series-1)', 'p:b': 'var(--series-2)' });
		expect(colours(['p:a', 'p:b', 'p:c'])['p:b']).toBe('var(--series-2)');
	});

	it('folds polities past the eighth into the other colour', () => {
		const ids = Array.from({ length: 10 }, (_, i) => `p:${i}`);
		const c = colours(ids);
		expect(c['p:7']).toBe('var(--series-8)');
		expect(c['p:8']).toBe('var(--series-other)');
	});
});

describe('borders', () => {
	const geo: Geography = {
		regions: [],
		places: [
			{ id: 's:a', kind: 'settlement', region: 'r', control: 'p:x' },
			{ id: 's:b', kind: 'settlement', region: 'r', control: 'p:y' },
			{ id: 's:c', kind: 'settlement', region: 'r', control: 'p:x' },
			{ id: 'w:d', kind: 'wild', region: 'r' }
		],
		routes: [
			{ id: 'ab', ends: ['s:a', 's:b'], days: 2, kind: 'road' },
			{ id: 'ac', ends: ['s:a', 's:c'], days: 2, kind: 'road' },
			{ id: 'ad', ends: ['s:a', 'w:d'], days: 2, kind: 'road' }
		]
	};

	it('runs along routes between places held by different polities', () => {
		expect([...borders(geo)]).toEqual(['ab']);
	});
});

describe('wars', () => {
	const events = [
		ev('e1', 'polity.war_declared', 10, { aggressor: ['p:x'], defender: ['p:y'] }, { war: 'war:1', relation: 'rel:p:x|p:y' }),
		ev('e2', 'polity.joined', 10, { ally: ['p:z'], side: ['p:y'] }, { war: 'war:1' }),
		ev('e3', 'polity.war_year', 11, { winner: ['p:x'], loser: ['p:y'] }, { war: 'war:1', place: 's:b' }),
		ev('e4', 'polity.war_year', 12, { winner: ['p:y'], loser: ['p:x'] }, { war: 'war:1', place: null }),
		ev('e5', 'polity.peace', 12, { winner: ['p:y'], loser: ['p:x'] }, { war: 'war:1' }),
		ev('e6', 'polity.war_declared', 20, { aggressor: ['p:y'], defender: ['p:z'] }, { war: 'war:2', relation: 'rel:p:y|p:z' })
	];

	it('gathers each war from its declaration to its end', () => {
		const [a, b] = wars(events);
		expect(a.id).toBe('war:1');
		expect([a.aggressor, a.defender, a.event]).toEqual(['p:x', 'p:y', 'e1']);
		expect(a.joined).toEqual([{ ally: 'p:z', side: 'p:y', date: [4, 10, 0], event: 'e2' }]);
		expect(a.years.map((y) => [y.winner, y.place])).toEqual([['p:x', 's:b'], ['p:y', null]]);
		expect(a.end).toEqual({ how: 'peace', winner: 'p:y', loser: 'p:x', date: [4, 12, 0], event: 'e5' });
		expect(b.end).toBeNull();
	});

	it('ends a war when a side falls', () => {
		const fallen = [...events.slice(0, 3), ev('e9', 'polity.fallen', 11, { polity: ['p:y'], victor: ['p:x'] }, { war: 'war:1' })];
		expect(wars(fallen)[0].end).toEqual({ how: 'fallen', winner: 'p:x', loser: 'p:y', date: [4, 11, 0], event: 'e9' });
	});

	it('keeps a war going when only an ally falls, until its peace', () => {
		const ally = [...events.slice(0, 3), ev('e9', 'polity.fallen', 11, { polity: ['p:z'], victor: ['p:x'] }, { war: 'war:1' }), ...events.slice(3, 5)];
		const [w] = wars(ally);
		expect(w.falls).toEqual([{ polity: 'p:z', victor: 'p:x', date: [4, 11, 0], event: 'e9' }]);
		expect(w.end?.how).toBe('peace');
	});

	it('ends a war its state says ended, with no event of its own (a side fell in another war)', () => {
		const [, b] = wars(events, { 'war:2': [4, 21, 0] });
		expect(b.end).toEqual({ how: 'ended', winner: null, loser: null, date: [4, 21, 0], event: null });
	});
});

describe('relation series', () => {
	const d = (year: number, field: string, value: unknown, event = `e${year}${field}`): RelationDelta => ({
		date: [4, year, 0],
		entity: 'rel:p:x|p:y',
		field,
		new: value,
		event
	});

	it('follows a relation\'s stance and trust, one point a day either changed', () => {
		const s = relationSeries([d(1, 'a', 'p:x'), d(1, 'b', 'p:y'), d(1, 'stance', 'neutral'), d(1, 'trust', 0.1), d(3, 'trust', -0.2), d(5, 'stance', 'cold')]);
		expect(Object.keys(s)).toEqual(['rel:p:x|p:y']);
		const r = s['rel:p:x|p:y'];
		expect([r.a, r.b]).toEqual(['p:x', 'p:y']);
		expect(r.points.map((p) => [p.date[1], p.stance, p.trust])).toEqual([[1, 'neutral', 0.1], [3, 'neutral', -0.2], [5, 'cold', -0.2]]);
	});

	it('ignores other entities\' fields', () => {
		expect(relationSeries([{ date: [4, 1, 0], entity: 's:a', field: 'trust', new: 1, event: 'x' }])).toEqual({});
	});
});
