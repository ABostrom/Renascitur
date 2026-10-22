import type { Run } from './run';

export interface SegmentFile {
	path: string;
	gz: boolean;
}

const seg = (i: number) => `seg-${String(i).padStart(5, '0')}`;

/**
 * Which files make up a table, in order. The browser can't repair a folder, so it chooses the way
 * runfolder._recover would:
 * - below `manifest.segments` (closed): the gzipped segment (raw only if no .gz exists);
 * - at `manifest.segments` (the open segment): the raw file; a stray .gz there is an interrupted
 *   close and is ignored;
 * - `.tmp` files are never asked for.
 */
export async function segmentFiles(run: Run, table: string): Promise<SegmentFile[]> {
	const out: SegmentFile[] = [];
	const closed = run.manifest.segments;
	for (let i = 0; i <= closed; i++) {
		const base = `${run.name}/${table}/${seg(i)}.jsonl`;
		if (i < closed && (await run.source.has(base + '.gz'))) {
			out.push({ path: `${table}/${seg(i)}.jsonl.gz`, gz: true });
		} else if (await run.source.has(base)) {
			out.push({ path: `${table}/${seg(i)}.jsonl`, gz: false });
		}
	}
	return out;
}
