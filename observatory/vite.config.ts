import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	// A single-page app: `renasci observe` serves index.html for every route.
	plugins: [
		sveltekit({
			adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html', strict: false }),
			alias: { $lib: 'src/lib' }
		})
	],
	test: { include: ['src/**/*.test.ts'], environment: 'node' }
});
