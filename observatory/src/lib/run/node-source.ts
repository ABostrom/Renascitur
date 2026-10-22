import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import type { RunSource } from './source';

/** Run folders from the file system, for tests. */
export class NodeSource implements RunSource {
	constructor(private root: string) {}

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
