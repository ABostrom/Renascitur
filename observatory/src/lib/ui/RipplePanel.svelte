<script lang="ts">
	/**
	 * Author a ripple on the run being viewed (#110): pick a kind, a target (this page's entity, if it has
	 * one) and a date, and the launcher replays it as a branch of this run and diffs it. Renders nothing
	 * when the launcher is off (`renasci observe --allow-launch`): without it the Observatory is read-only.
	 */
	import { onDestroy } from 'svelte';

	import type { Calendar } from '$lib/run/calendar';
	import { launcher, type Job } from '$lib/run/latch';
	import { ABOUT, KINDS, rippleRequest, type RippleForm } from '$lib/run/ripple';
	import { openRun } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	let { run, target = '' }: { run: string; target?: string } = $props();

	let enabled = $state(false);
	let cal = $state<Calendar | null>(null);
	let form = $state<RippleForm>({ kind: 'protect', target: '', date: '', until: '', open: '' });
	let job = $state<Job | null>(null);
	let error = $state<string | null>(null);
	let alive = true;
	let timer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		form.target = target; // (the page's entity, when the page changes)
	});
	$effect(() => {
		const r = run;
		let stale = false;
		job = null;
		error = null;
		enabled = false;
		cal = null;
		if (timer) clearTimeout(timer); // (a job started on another run stays there)
		timer = null;
		launcher.enabled().then(async (on) => {
			if (stale || !on) return;
			const opened = await openRun(new HttpSource(), r);
			if (stale) return;
			cal = opened.calendar;
			enabled = true;
		}).catch(() => {});
		return () => (stale = true);
	});
	onDestroy(() => {
		alive = false;
		if (timer) clearTimeout(timer);
	});

	function poll(id: number) {
		timer = setTimeout(async () => {
			if (!alive) return;
			try {
				const found = (await launcher.jobs()).find((j) => j.id === id);
				if (found) job = found;
			} catch {
				// (the server was busy: ask again)
			}
			if (job?.state === 'running') poll(id);
		}, 1500);
	}

	async function go() {
		error = null;
		try {
			const req = rippleRequest(cal!, run, form);
			job = await launcher.ripple(req);
			poll(job.id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const enc = encodeURIComponent;
	const shows = (...kinds: string[]) => kinds.includes(form.kind);
</script>

{#if enabled && cal}
	<details class="card ripple-panel">
		<summary>Ripple this run…</summary>
		<p class="muted small">Replayed as a branch of <strong>{run}</strong> from the checkpoint before its date, then diffed against it.</p>
		<form onsubmit={(e) => (e.preventDefault(), go())}>
			<label>Kind
				<select bind:value={form.kind} aria-describedby="ripple-about">
					{#each KINDS as k (k)}<option value={k}>{k}</option>{/each}
				</select>
			</label>
			<span class="muted small about" id="ripple-about">{ABOUT[form.kind as keyof typeof ABOUT]}</span>
			<label>Target <input bind:value={form.target} placeholder="an entity, route or settlement id" class="mono" /></label>
			<label>Date <input bind:value={form.date} placeholder={`e.g. ${cal.format([cal.json.ages[0].index, 2, 0], 'year')}`} /></label>
			{#if shows('protect', 'favour', 'luck')}
				<label>Until <input bind:value={form.until} placeholder="a year means its end" /></label>
			{/if}
			{#if shows('favour')}<label>By <input bind:value={form.by} placeholder="0.3" inputmode="decimal" /></label>{/if}
			{#if shows('inject')}<label>Script <input bind:value={form.script} placeholder="e.g. ward_failure" /></label>{/if}
			{#if shows('plant')}
				<label class="wide">Claim <input bind:value={form.claim} class="mono" placeholder={'{"pred": "killed", "args": {"victim": "…", "by": "…"}}'} /></label>
				<label>Share <input bind:value={form.share} placeholder="0.2" inputmode="decimal" /></label>
			{/if}
			{#if shows('structural')}
				<label>The route
					<select bind:value={form.open}>
						<option value="">keeps its state</option>
						<option value="closed">closes</option>
						<option value="open">reopens</option>
					</select>
				</label>
				<label>Days <input bind:value={form.days} placeholder="(unchanged)" inputmode="numeric" /></label>
			{/if}
			{#if shows('structural', 'inject')}<label>Why <input bind:value={form.why} placeholder="a rockslide" /></label>{/if}
			<label>Branch name <input bind:value={form.name} placeholder="(automatic)" class="mono" /></label>
			<button type="submit" disabled={job?.state === 'running'}>Replay with this ripple</button>
		</form>
		{#if error}<p class="warn" role="alert">{error}</p>{/if}
		{#if job}
			<div role="status">
				{#if job.state === 'running'}
					Replaying… <span class="muted small">(the branch appears on the runs page when it's done)</span>
				{:else if job.state === 'done' && job.variant}
					<span class="badge ok">done</span> <a href={`/run/${enc(job.variant)}/events`}>{job.variant}</a> ·
					<a href={`/diff/${enc(job.run)}/${enc(job.variant)}`}>what changed</a> ·
					<a href={`/compare/${enc(job.run)}/${enc(job.variant)}`}>side by side</a>
					{#if job.warning}<span class="badge warn">{job.warning}</span>{/if}
				{:else}
					<span class="badge warn">failed</span>
					<pre class="small">{job.output.split('\n').filter((l) => l.trim()).slice(-3).join('\n')}</pre>
				{/if}
			</div>
		{/if}
	</details>
{/if}

<style>
	.ripple-panel {
		margin-top: 1.5rem;
	}
	.ripple-panel summary {
		cursor: pointer;
		font-weight: 600;
	}
	form {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		align-items: end;
		margin-top: 0.6rem;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.85rem;
	}
	label.wide {
		flex: 1 1 100%;
	}
	label.wide input {
		width: 100%;
	}
	.about {
		flex: 1 1 100%;
	}
	.warn {
		color: var(--unexplained);
	}
	.small {
		font-size: 0.85rem;
	}
</style>
