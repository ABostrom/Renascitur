import { afterEach, describe, expect, it } from 'vitest';

import { facts, forge, keepable, type Card } from './forge';

const real = globalThis.fetch;
afterEach(() => {
	globalThis.fetch = real;
});

const card = (over: Partial<Card>): Card => ({ kind: 'person', id: 'p', name: 'Ulf', told: 0, history: [], marks: [], ...over });

describe('the Forge', () => {
	it('asks the server for cards and reads them from the run', async () => {
		const sent: [string, unknown][] = [];
		globalThis.fetch = (async (url: string, init?: RequestInit) => {
			sent.push([url, init?.body ? JSON.parse(String(init.body)) : null]);
			if (url === '/api/gen') return new Response(JSON.stringify({ id: 'j1', state: 'running' }));
			if (url === '/api/jobs') return new Response(JSON.stringify([{ id: 'j1', state: 'done', output: '' }]));
			return new Response(JSON.stringify({ found: 1, cards: [card({})] }));
		}) as unknown as typeof fetch;
		const got = await forge.search('m4', { what: 'person', filters: { house: ' medani ', race: '' }, notable: true, seed: 2 });
		expect(got.found).toBe(1);
		expect(sent[0]).toEqual(['/api/gen', { run: 'm4', what: 'person', filters: { house: 'medani' }, seed: 2, count: 12, notable: true }]);
		expect(sent.at(-1)?.[0]).toBe('/runs/m4/analysis/cards/last.json');
	});

	it('says why a job failed', async () => {
		globalThis.fetch = (async (url: string) => {
			if (url === '/api/keep') return new Response(JSON.stringify({ id: 'j1', state: 'running' }));
			return new Response(JSON.stringify([{ id: 'j1', state: 'failed', output: 'x\nrenasci: already there\n' }]));
		}) as unknown as typeof fetch;
		await expect(forge.keep('m4', 'e1')).rejects.toThrow('renasci: already there');
	});

	it('is off unless the server says so', async () => {
		globalThis.fetch = (async () => new Response(JSON.stringify({ forge: false }))) as unknown as typeof fetch;
		expect(await forge.enabled()).toBe(false);
	});

	it('keeps only what still exists: things and people', () => {
		expect(keepable(card({ kind: 'object', status: 'active' }))).toBe(true);
		expect(keepable(card({ kind: 'object', status: 'dead' }))).toBe(false);
		expect(keepable(card({ status: 'active' }))).toBe(true);
		expect(keepable(card({}))).toBe(false);
		expect(keepable(card({ kind: 'house', status: 'active' }))).toBe(false);
	});

	it('leaves out empty facts', () => {
		expect(facts(card({ race: 'r:dwarf', house: null, job: 'herder' }))).toEqual([['race', 'r:dwarf'], ['job', 'herder']]);
	});
});
