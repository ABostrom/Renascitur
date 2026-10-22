/**
 * Stream JSON Lines out of (optionally gzipped) bytes.
 *
 * Splits only on "\n": U+2028, U+2029 and \x85 are legal inside JSON strings, so a general line
 * splitter would break rows. A last line with no newline belongs to a write still in progress and is
 * dropped.
 */
export async function* lines(stream: ReadableStream<Uint8Array>, gz: boolean): AsyncGenerator<string> {
	const bytes = gz ? stream.pipeThrough(new DecompressionStream('gzip') as unknown as TransformStream<Uint8Array, Uint8Array>) : stream;
	const reader = bytes.pipeThrough(new TextDecoderStream() as unknown as TransformStream<Uint8Array, string>).getReader();
	let buffer = '';
	let finished = false;
	try {
		for (;;) {
			const { value, done } = await reader.read();
			if (done) {
				finished = true;
				break;
			}
			buffer += value;
			let nl = buffer.indexOf('\n');
			while (nl >= 0) {
				const line = buffer.slice(0, nl);
				if (line) yield line;
				buffer = buffer.slice(nl + 1);
				nl = buffer.indexOf('\n');
			}
		}
	} finally {
		if (!finished) await reader.cancel(); // the consumer stopped early: release the file or request
	}
	// whatever remains has no terminating newline: an in-progress write, dropped on purpose
}
