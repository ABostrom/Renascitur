import { buildIndex, type EventIndex } from './run/index';
import { openRun, type Run } from './run/run';
import { HttpSource } from './run/source';

/** Runs and their indexes, loaded once per page session and shared by every view. */
const cache = new Map<string, Promise<{ run: Run; index: EventIndex }>>();

export function loadRun(name: string, onProgress?: (n: number) => void) {
	let p = cache.get(name);
	if (!p) {
		p = (async () => {
			const run = await openRun(new HttpSource(), name);
			return { run, index: await buildIndex(run, onProgress) };
		})();
		p.catch(() => cache.delete(name));
		cache.set(name, p);
	}
	return p;
}
