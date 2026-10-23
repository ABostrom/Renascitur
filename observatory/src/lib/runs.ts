import { buildCauseGraph, type CauseGraph } from './run/causes';
import { buildIndex, type EventIndex } from './run/index';
import { openRun, type Run } from './run/run';
import { HttpSource } from './run/source';
import { loadStories, type Stories } from './run/stories';

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

const graphs = new Map<string, Promise<CauseGraph>>();

/** A run's cause graph, built on first use (it reads the activations table). */
export function loadGraph(name: string) {
	let p = graphs.get(name);
	if (!p) {
		p = loadRun(name).then(({ index }) => buildCauseGraph(index));
		p.catch(() => graphs.delete(name));
		graphs.set(name, p);
	}
	return p;
}

const storyCache = new Map<string, Promise<{ run: Run; stories: Stories | null }>>();

/** A run's `analysis/stories.json` (null if `renasci stories` hasn't been run), loaded once. */
export function loadRunStories(name: string) {
	let p = storyCache.get(name);
	if (!p) {
		p = (async () => {
			const source = new HttpSource();
			const run = await openRun(source, name);
			return { run, stories: await loadStories(source, name) };
		})();
		p.catch(() => storyCache.delete(name));
		storyCache.set(name, p);
	}
	return p;
}
