/**
 * Canon checks in the Observatory (#111, S12 §4): the report `renasci check-prose` writes, and its findings
 * in the order a writer wants them (contradictions first, then by sentence), as `story.check.findings`
 * orders them.
 */
export const ORDER = ['contradiction', 'leak', 'half', 'ambiguous', 'invention', 'consistent'] as const;
export type Finding = (typeof ORDER)[number];

export interface Claim {
	pred: string;
	args: Record<string, unknown>;
	date: number[] | null;
	by: string;
	verdict: string;
	finding: Finding;
	events: string[];
}

export interface Unresolved {
	mention: string;
	kind: string;
	why: string;
	finding: 'ambiguous';
	candidates: { id: string; name?: string; house?: string | null; born?: number[] | null; died?: number[] | null }[];
}

export interface Sentence {
	n: number;
	text: string;
	date: number[] | null;
	claims: Claim[];
	unresolved: Unresolved[];
}

export interface CheckReport {
	schema: string;
	run: string;
	pov: { kind: string; id: string | null; name: string };
	text: string;
	counts: Record<Finding, number>;
	sentences: Sentence[];
}

export type Row = ({ type: 'claim' } & Claim | { type: 'mention' } & Unresolved) & { n: number; sentence: string };

/** Every finding but `consistent`, contradictions first, then in the text's order. */
export function findingsOf(report: CheckReport): Row[] {
	const rows: Row[] = [];
	for (const s of report.sentences) {
		for (const c of s.claims) if (c.finding !== 'consistent') rows.push({ type: 'claim', ...c, n: s.n, sentence: s.text });
		for (const u of s.unresolved) rows.push({ type: 'mention', ...u, finding: 'ambiguous', n: s.n, sentence: s.text });
	}
	return rows.sort((a, b) => ORDER.indexOf(a.finding) - ORDER.indexOf(b.finding) || a.n - b.n);
}

/** A claim as a line: `killed {victim: …, by: …} in 4A 9`. */
export function claimLine(c: Claim): string {
	const args = Object.entries(c.args)
		.map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
		.join(', ');
	return `${c.pred}(${args})${c.date ? ` at ${c.date.slice(0, 2).join(':')}` : ''}`;
}
