import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import type { RunSource } from './source';

/** Run folders from the file system, for tests. */
export class NodeSource implements RunSource {
	constructor(private root: string) {}

	async list(dir: string): Promise<string[]> {
		const p = join(this.root, dir);
		if (!existsSync(p)) return [];
		return readdirSync(p, { withFileTypes: true })
			.filter((d) => d.isFile())
			.map((d) => d.name)
			.sort();
	}

	async has(path: string): Promise<boolean> {
		const p = join(this.root, path);
		return existsSync(p) && statSync(p).isFile();
	}

	async stream(path: string): Promise<ReadableStream<Uint8Array>> {
		return new Blob([readFileSync(join(this.root, path))]).stream();
	}

	async text(path: string): Promise<string> {
		return readFileSync(join(this.root, path), 'utf-8');
	}
}
