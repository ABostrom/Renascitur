import type { Run } from './run';

export interface SegmentFile {
	path: string;
	gz: boolean;
}

const seg = (i: number) => `seg-${String(i).padStart(5, '0')}`;

/**
 * Which files make up a table, in order. One directory listing per table, no per-file probing.
 *
 * The browser can't repair a folder, so it chooses the way runfolder._recover would:
 * - below `manifest.segments` (closed): the gzipped segment (the raw file only if no .gz exists);
 * - at `manifest.segments` (the open segment): the raw file. A stray .gz there is an interrupted
 *   close and is ignored, unless the raw file is gone: then the close has just finished while we
 *   were reading, and the .gz is the segment.
 * - `.tmp` files are never chosen.
 */
export async function segmentFiles(run: Run, table: string): Promise<SegmentFile[]> {
	const names = new Set(await run.source.list(`${run.name}/${table}`));
	const out: SegmentFile[] = [];
	const closed = run.manifest.segments;
	for (let i = 0; i <= closed; i++) {
		const raw = `${seg(i)}.jsonl`;
		const gz = `${raw}.gz`;
		const preferGz = i < closed || !names.has(raw);
		if (preferGz && names.has(gz)) out.push({ path: `${table}/${gz}`, gz: true });
		else if (names.has(raw)) out.push({ path: `${table}/${raw}`, gz: false });
	}
	return out;
}
