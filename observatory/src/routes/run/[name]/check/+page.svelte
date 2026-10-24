<script lang="ts">
	/**
	 * The canon check (#111, S12 §4 and §7): prose pasted here is judged against the run, from a point of
	 * view. The launcher keeps the text as `analysis/checks/<digest>.md` and runs `renasci check-prose` on
	 * it; the page shows each finding with the claim, its verdict and the events behind it, contradictions
	 * first. Needs `renasci observe --allow-launch`.
	 */
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';

	import { claimLine, findingsOf, type CheckReport, type Row } from '$lib/run/check';
	import { launcher, type Job } from '$lib/run/latch';

	const MAX = 256 * 1024;
	const name = $derived(page.params.name ?? '');
	const enc = encodeURIComponent;
	let enabled = $state<boolean | null>(null);
	let text = $state('');
	let pov = $state('omniscient');
	let job = $state<Job | null>(null);
	let error = $state<string | null>(null);
	let report = $state<CheckReport | null>(null);
	let timer: ReturnType<typeof setTimeout> | null = null;
	let alive = true;

	const size = $derived(new TextEncoder().encode(text).length);
	const rows = $derived<Row[]>(report ? findingsOf(report) : []);

	onMount(async () => {
		enabled = await launcher.enabled();
	});
	$effect(() => {
		void name; // (another run: start over)
		if (timer) clearTimeout(timer);
		timer = null;
		job = null;
		report = null;
		error = null;
	});
	onDestroy(() => {
		alive = false;
		if (timer) clearTimeout(timer);
	});

	async function check() {
		error = null;
		report = null;
		const asked = name;
		try {
			const started = await launcher.check(name, text, pov.trim() || 'omniscient');
			if (name !== asked) return;
			job = started;
			watch(started.id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function watch(id: number) {
		timer = setTimeout(async () => {
			timer = null;
			if (!alive || job?.id !== id) return;
			try {
				const found = (await launcher.jobs()).find((j) => j.id === id);
				if (found && job?.id === id) job = found;
			} catch {
				// (ask again)
			}
			if (job?.id !== id) return;
			if (job.state === 'running') return watch(id);
			if (job.state === 'done' && job.file) {
				try {
					const r = await fetch(`/runs/${job.file.split('/').map(enc).join('/')}`);
					if (!r.ok) throw new Error(`couldn't read the report (${r.status})`);
					if (job?.id === id) report = await r.json();
				} catch (e) {
					error = (e as Error).message;
				}
			}
		}, 1000);
	}

	const eventHref = (e: string) => `/run/${enc(name)}/events?e=${enc(e)}`;
	const entityHref = (e: string) => `/run/${enc(name)}/entity/${enc(e)}`;
</script>

<svelte:head><title>Canon check · {name}</title></svelte:head>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> › canon check
</p>
<h1>Canon check</h1>
<p class="muted">
	Paste prose about this run (Markdown; a fenced <code>claims</code> block of JSON lines is read exactly). Each claim the
	checker finds is judged against what happened, and against what the point of view believed: a <strong>contradiction</strong>,
	a <strong>leak</strong> (true, but they couldn't know it), a <strong>half</strong> truth, an <strong>ambiguous</strong> name
	(with who it could be), or an <strong>invention</strong>.
</p>

{#if enabled === false}
	<p class="card">Checking prose needs the launcher: start the Observatory with <code>renasci observe --allow-launch</code>.</p>
{:else if enabled}
	<section class="card">
		<textarea bind:value={text} rows="12" aria-label="prose to check" placeholder="In 4A 5, Gwen of House Kundarak killed Jory of House Kundarak…"></textarea>
		<div class="row">
			<label class="small">Whose account <input bind:value={pov} size="24" class="mono" /></label>
			<span class={`small ${size > MAX ? 'error' : 'muted'}`}>{(size / 1024).toFixed(1)} of 256 KB</span>
			<button onclick={check} disabled={!text.trim() || size > MAX || job?.state === 'running'}>Check</button>
		</div>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if job}
			<p aria-live="polite">
				<span class={`badge ${job.state === 'done' ? 'ok' : job.state === 'failed' ? 'warn' : ''}`}>{job.state}</span>
				{#if job.state === 'done' && job.file}<a href={`/runs/${job.file.split('/').map(enc).join('/')}`} target="_blank" rel="noopener">the report</a>{/if}
			</p>
			{#if job.state === 'failed'}<pre class="out">{job.output.trim().split('\n').slice(-6).join('\n')}</pre>{/if}
		{/if}
	</section>
{/if}

{#if report}
	<section class="card">
		<h2>Findings</h2>
		<p class="counts">
			{#each Object.entries(report.counts) as [k, n] (k)}
				{#if n}<span class={`badge f-${k}`}>{n} {k}</span>{/if}
			{/each}
			· from <strong>{report.pov.name}</strong>'s point of view
		</p>
		{#if rows.length === 0}
			<p class="muted">Nothing to report: every claim found is consistent{report.counts.consistent ? '' : ' (and none was found)'}.</p>
		{/if}
		<ul class="findings">
			{#each rows as r, i (i)}
				<li>
					<span class={`badge f-${r.finding}`}>{r.finding}</span>
					<span class="muted small">#{r.n}</span> “{r.sentence}”
					{#if r.type === 'claim'}
						<div class="small mono">{claimLine(r)}: {r.verdict}</div>
						{#if r.events.length}
							<div class="small">rests on {#each r.events.slice(0, 6) as e, j (e)}{j ? ', ' : ''}<a class="mono" href={eventHref(e)}>{e}</a>{/each}</div>
						{/if}
					{:else}
						<div class="small">“{r.mention}”: {r.why}
							{#if r.candidates.length}— could be {#each r.candidates.slice(0, 6) as c, j (c.id)}{j ? ', ' : ''}<a href={r.kind === 'event' ? eventHref(c.id) : entityHref(c.id)}>{c.name ?? c.id}</a>{/each}{/if}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
		<details>
			<summary>Every sentence ({report.sentences.length})</summary>
			<ol class="sentences">
				{#each report.sentences as s (s.n)}
					<li value={s.n}>
						“{s.text}”
						{#each s.claims as c, j (j)}
							<div class="small"><span class={`badge f-${c.finding}`}>{c.finding}</span> <span class="mono">{claimLine(c)}</span>: {c.verdict}
								{#each c.events.slice(0, 4) as e (e)} <a class="mono" href={eventHref(e)}>{e}</a>{/each}</div>
						{/each}
					</li>
				{/each}
			</ol>
		</details>
	</section>
{/if}

<style>
	textarea {
		width: 100%;
		font: inherit;
		box-sizing: border-box;
	}
	.row {
		display: flex;
		gap: 1rem;
		align-items: center;
		flex-wrap: wrap;
		margin-top: 0.5rem;
	}
	.findings {
		list-style: none;
		padding: 0;
	}
	.findings li {
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--border);
	}
	.f-contradiction {
		background: var(--unexplained);
		color: white;
	}
	.small {
		font-size: 0.85rem;
	}
	.out {
		font-size: 0.8rem;
		white-space: pre-wrap;
		color: var(--muted);
	}
	.error {
		color: var(--unexplained);
	}
</style>
