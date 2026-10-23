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
	await page.getByRole('link', { name: 'base', exact: true }).waitFor({ timeout: 10000 });
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
	// the cause chain: from a doom ripple's secret event forward to the death it caused
	await page.goto(`http://127.0.0.1:${port}/run/protected/events?type=ripple.doom`);
	await page.locator('button.event').first().click();
	await page.getByRole('button', { name: 'What it led to' }).click();
	await page.locator('.tree').getByText(/toy\.death/).first().waitFor({ timeout: 15000 });
	// an entity page: record, life and state changes
	await page.goto(`http://127.0.0.1:${port}/run/base/entity/t%3AAshford`);
	await page.getByRole('heading', { name: /State changes \(\d+\)/ }).waitFor({ timeout: 15000 });
	if (errors.length) throw new Error(`page errors: ${errors.join('; ')}`);
	// the diff: a clean wave, and a cell that opens its divergent events in the variant's browser
	await page.goto(`http://127.0.0.1:${port}/diff/base/protected`);
	await page.getByText(/0\s*unexplained/).first().waitFor({ timeout: 15000 });
	const cells = await page.locator('a.cell').count();
	if (cells === 0) throw new Error('the wave has no divergent cells');
	await page.locator('a.cell').first().click();
	await page.getByText(/divergent in the diff of/).waitFor({ timeout: 15000 });
	const divergentShown = Number((await page.getByText(/^\d+ events?$/).textContent()).split(' ')[0]);
	if (!(divergentShown > 0)) throw new Error('a wave cell showed no divergent events');
	// the buggy world: unexplained, with its root events marked
	await page.goto(`http://127.0.0.1:${port}/diff/buggy/buggy-protected`);
	await page.getByRole('heading', { name: 'Unexplained' }).waitFor({ timeout: 15000 });
	await page.locator('.badge.bad', { hasText: 'root' }).first().waitFor({ timeout: 10000 });
	if ((await page.locator('a.cell.unexplained').count()) === 0) throw new Error('no unexplained wave cell outlined');
	// stories: the river over a preset period, a bar to its arc, a beat to the event browser, a saga
	await page.goto(`http://127.0.0.1:${port}/run/kin/stories`);
	await page.getByRole('heading', { name: 'The story river' }).waitFor({ timeout: 15000 });
	const bars = await page.locator('rect.bar').count();
	if (bars === 0) throw new Error('the story river has no bars');
	await page.locator('select').first().selectOption({ label: 'Years 11–20' });
	await page.waitForURL(/from=11&to=20/, { timeout: 10000 });
	const barsIn = await page.locator('rect.bar').count();
	if (!(barsIn > 0 && barsIn < bars)) throw new Error(`a decade showed ${barsIn} of ${bars} bars`);
	await page.goto(`http://127.0.0.1:${port}/run/kin/stories?from=5&to=30`);
	await page.locator('section', { hasText: 'Sagas' }).getByRole('link').first().click();
	await page.getByRole('heading', { name: 'Arcs, in order' }).waitFor({ timeout: 15000 });
	await page.locator('table a[href*="/stories/arc/"]').first().click();
	await page.getByRole('heading', { name: 'Beats' }).waitFor({ timeout: 15000 });
	await page.locator('table a[href*="/events?e="]').first().click();
	await page.getByRole('heading', { name: 'What it read' }).waitFor({ timeout: 20000 });
	// latch points (the launcher is off here, so each shows its command) and a what-if next to its baseline
	await page.goto(`http://127.0.0.1:${port}/run/kin/latch`);
	await page.locator('code.cmd', { hasText: '--launch 1' }).first().waitFor({ timeout: 15000 });
	await page.getByRole('link', { name: 'kin-latch1' }).first().click();
	await page.getByRole('heading', { name: 'What if…' }).waitFor({ timeout: 15000 });
	await page.getByText(/every difference traces to the ripple/).waitFor({ timeout: 15000 });
	await page.getByText(/In kin-latch1: (lives on|dies)/).waitFor({ timeout: 30000 });
	const rivers = await page.locator('svg[aria-label^="Ambitions by house"]').count();
	if (rivers !== 2) throw new Error(`the comparison shows ${rivers} rivers`);
	if (errors.length) throw new Error(`page errors: ${errors.join('; ')}`);
	console.log(`smoke: ok (browser read ${counts.base.n} events from base; ${shown} granary events listed; detail, cause chain and entity page shown; diff wave of ${cells} cells, ${divergentShown} divergent events in one, buggy roots marked; story river of ${bars} bars, ${barsIn} in a decade, saga to arc to event; latch points and a what-if beside its baseline)`);
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
