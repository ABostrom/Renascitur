// Smoke test of the shipping model: the committed build, served by `renasci observe`, in a real browser.
//   npm run build && npm run smoke
import { execSync, spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const app = resolve(here, '..');
const repo = resolve(app, '..');
const port = 8799;
const chrome = [
	process.env.CHROME_PATH,
	'C:/Program Files/Google/Chrome/Application/chrome.exe',
	'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
	'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
	'/usr/bin/google-chrome',
	'/usr/bin/chromium'
].find((p) => p && existsSync(p));
if (!chrome) {
	console.error('smoke: no Chrome found (set CHROME_PATH)');
	process.exit(2);
}

const command = `uv run renasci observe "${resolve(app, 'fixtures/runs')}" --app "${resolve(app, 'build')}" --port ${port} --no-browser`;
const server = spawn(command, { cwd: repo, stdio: 'ignore', shell: true });

async function waitForServer() {
	for (let i = 0; i < 100; i++) {
		try {
			if ((await fetch(`http://127.0.0.1:${port}/runs/index.json`)).ok) return;
		} catch {}
		await new Promise((r) => setTimeout(r, 200));
	}
	throw new Error('renasci observe did not start');
}

let failed = false;
const browser = await (async () => {
	await waitForServer();
	return chromium.launch({ executablePath: chrome, headless: true });
})();
try {
	const page = await browser.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	await page.goto(`http://127.0.0.1:${port}/`);
	await page.getByText('base', { exact: true }).waitFor({ timeout: 10000 });
	await page.getByText('replay of base').waitFor({ timeout: 10000 });
	await page.getByText('incomplete').first().waitFor({ timeout: 10000 });
	// a deep link is served the app (SPA fallback), not a 404
	const deep = await page.goto(`http://127.0.0.1:${port}/run/base/events`);
	if (!deep || deep.status() !== 200) throw new Error(`deep link returned ${deep && deep.status()}`);
	if (errors.length) throw new Error(`page errors: ${errors.join('; ')}`);
	console.log('smoke: ok');
} catch (e) {
	failed = true;
	console.error('smoke: FAILED', e);
} finally {
	await browser.close();
	// stop the server and everything it started (uv, python)
	if (process.platform === 'win32') {
		try {
			execSync(`taskkill /pid ${server.pid} /T /F`, { stdio: 'ignore' });
		} catch {}
	} else server.kill();
}
process.exit(failed ? 1 : 0);
