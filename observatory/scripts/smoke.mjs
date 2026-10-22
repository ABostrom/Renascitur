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
	// the shipping data path, in Chrome: HTTP listing -> segment selection -> gzip -> JSON Lines
	const counts = await page.evaluate(async () => {
		const o = window.__observatory;
		const source = new o.HttpSource();
		const out = {};
		for (const name of ['base', 'interrupted']) {
			const run = await o.openRun(source, name);
			let n = 0;
			let last = null;
			for await (const e of o.readTable(run, 'events')) {
				n++;
				last = e.id;
			}
			out[name] = { n, last };
		}
		return out;
	});
	if (!(counts.base.n > 100)) throw new Error(`read ${counts.base.n} events from base in the browser`);
	if (counts.interrupted.last !== 'xopen1') throw new Error(`interrupted run ended at ${counts.interrupted.last}`);
	// the event browser: a deep link with a filter, a click, the detail with its scope's reads
	await page.goto(`http://127.0.0.1:${port}/run/base/events?type=toy.granary`);
	await page.getByText(/^\d+ events?$/).waitFor({ timeout: 15000 });
	const shown = Number((await page.getByText(/^\d+ events?$/).innerText()).split(' ')[0]);
	if (!(shown > 0)) throw new Error(`granary filter showed ${shown}`);
	await page.locator('button.event').first().click();
	await page.getByRole('heading', { name: 'What it read' }).waitFor({ timeout: 10000 });
	await page.locator('table.reads tbody tr').first().waitFor({ timeout: 10000 }); // the scope's reads, with digests
	if (errors.length) throw new Error(`page errors: ${errors.join('; ')}`);
	console.log(`smoke: ok (browser read ${counts.base.n} events from base; ${shown} granary events listed; detail shown)`);
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
