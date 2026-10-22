/**
 * Age-relative dates, ported from renasci.core.calendar. A run's manifest carries its calendar, so the
 * Observatory formats and parses dates without knowing any world. Shared vectors
 * (tests/fixtures/calendar_vectors.json) keep the two implementations identical.
 */

export type DateTuple = [age: number, year: number, day: number];

export interface CalendarJson {
	ages: { index: number; abbrev: string; name: string; last_year: number | null }[];
	months: [string, number][];
	seasons: [string, number][];
}

function starts(parts: [string, number][]): number[] {
	const out: number[] = [];
	let total = 0;
	for (const [, n] of parts) {
		out.push(total);
		total += n;
	}
	return out;
}

function indexOf(parts: [string, number][], day: number): number {
	let total = 0;
	for (let i = 0; i < parts.length; i++) {
		total += parts[i][1];
		if (day < total) return i;
	}
	throw new Error(`day ${day} outside the year`);
}

export class Calendar {
	readonly daysPerYear: number;
	private byIndex = new Map<number, CalendarJson['ages'][number]>();
	private byAbbrev = new Map<string, CalendarJson['ages'][number]>();

	constructor(readonly json: CalendarJson) {
		this.daysPerYear = json.months.reduce((s, [, n]) => s + n, 0);
		for (const a of json.ages) {
			this.byIndex.set(a.index, a);
			this.byAbbrev.set(a.abbrev, a);
		}
	}

	static fromJson(json: CalendarJson): Calendar {
		return new Calendar(json);
	}

	month(d: DateTuple): number {
		return indexOf(this.json.months, d[2]);
	}

	season(d: DateTuple): number {
		return indexOf(this.json.seasons, d[2]);
	}

	format(d: DateTuple, style: 'year' | 'season' | 'day' = 'year'): string {
		const age = this.byIndex.get(d[0]);
		const head = `${age ? age.abbrev : d[0]} ${d[1]}`;
		if (style === 'year') return head;
		if (style === 'season') return `${head} ${this.json.seasons[this.season(d)][0]}`;
		const m = this.month(d);
		return `${head} m${m + 1} d${d[2] - starts(this.json.months)[m] + 1}`;
	}

	parse(text: string): DateTuple {
		const m = /^(\S+) ([0-9]+)(?: m([0-9]+) d([0-9]+)| (.+))?$/.exec(text.trim());
		if (!m) throw new Error(`cannot parse date ${JSON.stringify(text)}`);
		const [, abbrev, year, month, day, season] = m;
		const age = this.byAbbrev.get(abbrev);
		if (!age) throw new Error(`unknown age ${abbrev}`);
		let doy = 0;
		if (season !== undefined) {
			const i = this.json.seasons.findIndex(([n]) => n === season);
			if (i < 0) throw new Error(`unknown season ${season}`);
			doy = starts(this.json.seasons)[i];
		} else if (month !== undefined) {
			const mi = Number(month) - 1;
			const dom = Number(day) - 1;
			if (!(mi >= 0 && mi < this.json.months.length && dom >= 0 && dom < this.json.months[mi][1])) {
				throw new Error(`no such day: ${text}`);
			}
			doy = starts(this.json.months)[mi] + dom;
		}
		return this.check([age.index, Number(year), doy]);
	}

	/** Throw unless `d` is a real date in this calendar (as Python's Calendar.check). */
	check(d: DateTuple): DateTuple {
		const age = this.byIndex.get(d[0]);
		if (!age) throw new Error(`unknown age ${d[0]}`);
		if (d[1] < 1 || d[2] < 0 || d[2] >= this.daysPerYear) throw new Error(`date out of range: ${d}`);
		if (age.last_year !== null && d[1] > age.last_year) throw new Error(`${d} is past the end of ${age.name}`);
		return d;
	}

	/** A sortable integer for a date: not Python's `ordinal` (days since the age began). */
	sortKey(d: DateTuple): number {
		return d[0] * 1e7 + d[1] * this.daysPerYear + d[2];
	}
}
