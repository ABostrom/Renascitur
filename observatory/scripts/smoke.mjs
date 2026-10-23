// Smoke test of the shipping model: the committed build, served by `renasci observe`, in a real browser.
//   npm run build && npm run smoke
import { execSync, spawn } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
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
let launched = '';
let launchServer = null;
const scratch = mkdtempSync(resolve(tmpdir(), 'renasci-smoke-'));

/** A second server, with the launcher on, over an empty runs folder and one tiny toy recipe. */
async function launchAndOpen(browser, errors) {
	const lport = port + 1;
	const recipes = resolve(scratch, 'recipes');
	const runs = resolve(scratch, 'runs');
	const vault = resolve(scratch, 'vault');
	mkdirSync(recipes, { recursive: true });
	mkdirSync(runs, { recursive: true });
	cpSync(resolve(repo, 'tests', 'fixtures', 'vault_people'), vault, { recursive: true });
	cpSync(resolve(app, 'fixtures', 'runs', 'canon'), resolve(runs, 'canon'), { recursive: true });
	writeFileSync(resolve(recipes, 'tiny.toml'),
		'[run]\nname = "tiny"\nengine = "0.1.0"\nseed = 7\nworld = "toy"\nend = "1X 2"\n\n[world]\npeople_per_village = 4\n');
	launchServer = spawn(`uv run renasci observe "${runs}" --app "${resolve(app, 'build')}" --port ${lport} --no-browser --allow-launch --recipes "${recipes}" --vault "${vault}"`,
		{ cwd: repo, stdio: 'ignore', shell: true });
	for (let i = 0; i < 100; i++) {
		try {
			if ((await fetch(`http://127.0.0.1:${lport}/api/capabilities`)).ok) break;
		} catch {}
		await new Promise((r) => setTimeout(r, 200));
	}
	const page = await browser.newPage();
	page.on('pageerror', (e) => errors.push(e.message));
	await page.goto(`http://127.0.0.1:${lport}/`);
	await page.getByRole('heading', { name: 'Launch' }).waitFor({ timeout: 15000 });
	await page.getByRole('button', { name: 'Run' }).first().click();
	await page.getByRole('link', { name: 'open tiny' }).click({ timeout: 60000 });
	await page.waitForURL(/\/run\/tiny\/events/, { timeout: 15000 });
	await page.locator('.filters').waitFor({ timeout: 20000 }); // (indexed: the launched run's events are there)
	// promote: the canon run's near miss, with the pin that caused it kept, written to the vault
	await page.goto(`http://127.0.0.1:${lport}/run/canon/strain`);
	await page.getByRole('heading', { name: /^Strain, in order/ }).waitFor({ timeout: 20000 });
	await page.locator('table a[href*="/events?e="]').first().click();
	await page.getByRole('heading', { name: 'Propose to the vault' }).waitFor({ timeout: 20000 });
	await page.getByRole('checkbox').first().check();
	await page.getByRole('button', { name: 'Propose' }).click();
	await page.getByText(/wrote _proposed\/event\//).waitFor({ timeout: 60000 });
	const written = readdirSync(resolve(vault, '_proposed', 'event'));
	if (written.length !== 1) throw new Error(`the vault has ${written.length} proposed events`);
	return 'a run launched from a recipe and opened; an event proposed to the vault with its cause';
}
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
	// a person: family, inner life as of a year, ambitions, ties and genome (a synthesised kin notable)
	await page.goto(`http://127.0.0.1:${port}/run/kin/entity/${encodeURIComponent('s:House-Ridge:010')}`);
	await page.getByRole('heading', { name: 'Family' }).waitFor({ timeout: 20000 });
	await page.getByRole('heading', { name: 'Genome' }).waitFor({ timeout: 5000 });
	if ((await page.locator('.person table.genome tbody tr').count()) === 0) throw new Error('the person page shows no genome');
	const asOf = page.getByRole('heading', { name: /^Inner life/ });
	const before = await asOf.textContent();
	await page.getByRole('slider', { name: 'Year' }).fill('0');
	if ((await asOf.textContent()) === before) throw new Error('the year control changed nothing');
	// houses and population: a line per region, a table of houses with their heads in order
	await page.goto(`http://127.0.0.1:${port}/run/kin/houses`);
	await page.getByRole('heading', { name: 'Population by place' }).waitFor({ timeout: 20000 });
	const popLines = await page.locator('.chart svg path').count();
	if (popLines < 2) throw new Error(`the population chart has ${popLines} lines`);
	await page.locator('table.houses tbody tr').first().waitFor({ timeout: 10000 });
	await page.locator('td.heads a').first().waitFor({ timeout: 20000 });
	// canon strain: a run cast from the test vault; its guard links to the near miss it caused
	await page.goto(`http://127.0.0.1:${port}/run/canon/strain`);
	await page.getByRole('heading', { name: /^Strain, in order/ }).waitFor({ timeout: 20000 });
	await page.locator('table a[href*="/events?e="]').first().click();
	await page.getByRole('heading', { name: 'What it read' }).waitFor({ timeout: 20000 });
	// the map: a Fourth Age run's places and routes, the Vialux drawn as itself; a world without one says so
	await page.goto(`http://127.0.0.1:${port}/run/pyrosia/map`);
	await page.getByRole('heading', { name: 'Map' }).waitFor({ timeout: 20000 });
	const towns = await page.locator('svg[aria-label^="Map of"] circle.settlement').count();
	if (towns < 6) throw new Error(`the map shows ${towns} settlements`);
	if ((await page.locator('svg[aria-label^="Map of"] line.route.vialux').count()) === 0) throw new Error('no Vialux on the map');
	// the map by year: the ward run's road built mid-run is there at the end, not at the start
	await page.goto(`http://127.0.0.1:${port}/run/ward/map`);
	await page.getByRole('heading', { name: 'Changes to the map' }).waitFor({ timeout: 20000 });
	const roads = () => page.locator('svg[aria-label^="Map of"] line.route').count();
	const atEnd = await roads();
	await page.getByRole('slider', { name: 'As of' }).fill('0');
	const atStart = await roads();
	if (atEnd !== atStart + 1) throw new Error(`the map by year: ${atStart} routes at the start, ${atEnd} at the end`);
	await page.goto(`http://127.0.0.1:${port}/run/base/map`);
	await page.getByText(/has no geography/).waitFor({ timeout: 15000 });
	// knowledge: the ward failure's lie beside the truth, and a claim picked onto the spread map
	await page.goto(`http://127.0.0.1:${port}/run/ward/knowledge`);
	await page.getByRole('heading', { name: 'Knowledge' }).waitFor({ timeout: 20000 });
	await page.getByRole('button', { name: /ward failure/ }).click();
	if ((await page.locator('table .badge.warn').count()) === 0) throw new Error('no false claim about the ward failure');
	const believing = await page.locator('svg[aria-label="Spread map"] circle.held').count();
	if (believing === 0) throw new Error('nobody believes anything on the spread map');
	await page.locator('table button.link').first().click();
	await page.getByRole('heading', { name: /^Where “/ }).waitFor({ timeout: 5000 });
	// a person's beliefs, each traced back: this townsman was told the guild's lie
	await page.goto(`http://127.0.0.1:${port}/run/ward/entity/${encodeURIComponent('s:lux-oescus:003')}`);
	await page.getByRole('heading', { name: /^Beliefs/ }).waitFor({ timeout: 30000 });
	const lied = page.locator('ul.beliefs details', { has: page.locator('.badge.warn') }).first();
	await lied.locator('summary').click();
	if ((await lied.locator('ol.trace li.lie').count()) === 0) throw new Error('a lie-born belief traces to no lie');
	// read-only without the launcher: the runs page offers no launch
	await page.goto(`http://127.0.0.1:${port}/`);
	await page.getByRole('heading', { name: 'Runs', exact: true, level: 1 }).waitFor({ timeout: 15000 });
	if ((await page.getByRole('heading', { name: 'Launch' }).count()) !== 0) throw new Error('a read-only server offered to launch');
	// with --allow-launch: a run launched from a recipe and opened from the UI (a scratch runs folder)
	launched = await launchAndOpen(browser, errors);
	if (errors.length) throw new Error(`page errors: ${errors.join('; ')}`);
	console.log(`smoke: ok (browser read ${counts.base.n} events from base; ${shown} granary events listed; detail, cause chain and entity page shown; diff wave of ${cells} cells, ${divergentShown} divergent events in one, buggy roots marked; story river of ${bars} bars, ${barsIn} in a decade, saga to arc to event; latch points and a what-if beside its baseline; a person's page; houses and ${popLines} population lines; canon strain to its event; the Pyrosia map with ${towns} settlements and a map by year; knowledge with ${believing} believing places and a belief traced to its lie; ${launched})`);
} catch (e) {
	failed = true;
	console.error('smoke: FAILED', e);
} finally {
	await browser.close();
	// stop the servers and everything they started (uv, python)
	for (const s of [server, launchServer].filter(Boolean)) {
		if (process.platform === 'win32') {
			try {
				execSync(`taskkill /pid ${s.pid} /T /F`, { stdio: 'ignore' });
			} catch {}
		} else s.kill();
	}
	try {
		rmSync(scratch, { recursive: true, force: true });
	} catch {}
}
process.exit(failed ? 1 : 0);
