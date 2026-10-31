import { describe, expect, it } from 'vitest';

import { biographies, type ObjectEvent } from './objects';

const ev = (id: string, type: string, year: number, roles: Record<string, string[]>, payload: Record<string, unknown> = {}, place: string | null = null): ObjectEvent => ({
	id,
	type,
	date: [4, year, 0],
	roles,
	payload,
	place
});

describe('object biographies', () => {
	const events = [
		ev('e1', 'object.made', 10, { maker: ['p:smith'], object: ['o:1'] }, { type: 'blade', material: 'iron', quality: 0.9 }, 's:a'),
		ev('e2', 'object.given', 10, { giver: ['p:smith'], owner: ['p:lord'], object: ['o:1'] }, { price: 12 }),
		ev('e3', 'object.deed', 14, { owner: ['p:lord'], object: ['o:1'] }, { deed: 'x1', kind: 'duel' }, 's:b'),
		ev('e4', 'object.named', 15, { object: ['o:1'] }, { name: 'the Blade of B' }),
		ev('e5', 'object.inherited', 20, { from: ['p:lord'], owner: ['p:son'], object: ['o:1'] }),
		ev('e6', 'object.lost', 30, { owner: ['p:son'], object: ['o:1'] }, { place: 's:c' }),
		ev('e7', 'object.found', 41, { finder: ['p:shepherd'], object: ['o:1'] }, { place: 's:c' }),
		ev('e8', 'object.stolen', 44, { thief: ['p:rogue'], from: ['p:shepherd'], object: ['o:1'] }),
		ev('e9', 'object.made', 12, { maker: ['p:weaver'], object: ['o:2'] }, { type: 'cloth', material: 'wool', quality: 0.4 }),
		ev('e10', 'object.destroyed', 13, { object: ['o:2'] }, { place: 's:a' })
	];

	it('follows each object from its making through every change of hands', () => {
		const b = biographies(events);
		const blade = b.get('o:1')!;
		expect([blade.type, blade.material, blade.maker, blade.name]).toEqual(['blade', 'iron', 'p:smith', 'the Blade of B']);
		expect(blade.owners.map((o) => [o.who, o.how])).toEqual([
			['p:lord', 'given'],
			['p:son', 'inherited'],
			[null, 'lost'],
			['p:shepherd', 'found'],
			['p:rogue', 'stolen']
		]);
		expect(blade.owner).toBe('p:rogue');
		expect(blade.deeds).toBe(1);
		expect(blade.beats.map((x) => x.kind)).toEqual(['made', 'given', 'deed', 'named', 'inherited', 'lost', 'found', 'stolen']);
	});

	it('marks the lost and the destroyed', () => {
		const b = biographies(events.slice(0, 6));
		expect(b.get('o:1')!.lost).toEqual([4, 30, 0]);
		const cloth = biographies(events).get('o:2')!;
		expect(cloth.destroyed).toEqual([4, 13, 0]);
		expect(cloth.owner).toBeNull();
	});

	it('takes in a planted object that was never made, its make from its record', () => {
		const b = biographies([ev('u1', 'object.unearthed', 7, { finder: ['p:a'], object: ['o:9'] }, { place: 's:z' })], {
			'o:9': { type: 'blade', material: 'iron', name: 'the Lost Blade' }
		});
		expect(b.get('o:9')!.maker).toBeNull();
		expect(b.get('o:9')!.owner).toBe('p:a');
		expect([b.get('o:9')!.type, b.get('o:9')!.name]).toEqual(['blade', 'the Lost Blade']);
	});
});
