/**
 * Where run files come from. Paths are relative to the runs folder: "<run>/events/seg-00000.jsonl.gz".
 *
 * - HttpSource: `renasci observe` (the normal way). Bookmarks and diffs work.
 * - PickerSource: a folder chosen in the browser (no Python needed). One run at a time.
 * - NodeSource (tests): the file system.
 */
export interface RunSource {
	/** File names directly inside `dir` (relative to the runs folder). */
	list(dir: string): Promise<string[]>;
	has(path: string): Promise<boolean>;
	stream(path: string): Promise<ReadableStream<Uint8Array>>;
	text(path: string): Promise<string>;
}

export class HttpSource implements RunSource {
	constructor(private base = '/runs') {}

	private url(path: string): string {
		return `${this.base}/${path.split('/').map(encodeURIComponent).join('/')}`;
	}

	async list(dir: string): Promise<string[]> {
		const r = await fetch(this.url(dir) + '/');
		return r.ok ? r.json() : [];
	}

	async has(path: string): Promise<boolean> {
		const r = await fetch(this.url(path), { method: 'HEAD' });
		return r.ok;
	}

	async stream(path: string): Promise<ReadableStream<Uint8Array>> {
		const r = await fetch(this.url(path));
		if (!r.ok || !r.body) throw new Error(`cannot read ${path} (${r.status})`);
		return r.body;
	}

	async text(path: string): Promise<string> {
		const r = await fetch(this.url(path));
		if (!r.ok) throw new Error(`cannot read ${path} (${r.status})`);
		return r.text();
	}
}

/** A folder picked in the browser: <input webkitdirectory> files, keyed by their relative path. */
export class PickerSource implements RunSource {
	private files = new Map<string, File>();
	readonly name: string;

	constructor(files: FileList | File[]) {
		let root = '';
		for (const f of Array.from(files)) {
			const rel = (f as File & { webkitRelativePath: string }).webkitRelativePath || f.name;
			root = rel.split('/')[0];
			this.files.set(rel, f);
		}
		this.name = root;
	}

	async list(dir: string): Promise<string[]> {
		const prefix = dir.replace(/\/$/, '') + '/';
		return [...this.files.keys()]
			.filter((k) => k.startsWith(prefix) && !k.slice(prefix.length).includes('/'))
			.map((k) => k.slice(prefix.length))
			.sort();
	}

	/** Runs inside the picked folder: itself if it is a run, else its run subfolders. */
	runNames(): string[] {
		if (this.files.has(`${this.name}/manifest.json`)) return [this.name];
		return [...this.files.keys()]
			.filter((k) => /^[^/]+\/[^/]+\/manifest\.json$/.test(k))
			.map((k) => k.split('/').slice(0, 2).join('/'))
			.sort();
	}

	async has(path: string): Promise<boolean> {
		return this.files.has(path);
	}

	private file(path: string): File {
		const f = this.files.get(path);
		if (!f) throw new Error(`no file ${path} in the picked folder`);
		return f;
	}

	async stream(path: string): Promise<ReadableStream<Uint8Array>> {
		return this.file(path).stream() as ReadableStream<Uint8Array>;
	}

	async text(path: string): Promise<string> {
		return this.file(path).text();
	}
}
