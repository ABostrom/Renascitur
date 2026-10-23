<script lang="ts">
	import { page } from '$app/state';
	import { onDestroy, untrack } from 'svelte';

	import { latchCommand, launcher, loadLatch, whatIfsOf, type Adjust, type Job, type Latch, type LatchPoint } from '$lib/run/latch';
	import { listRuns, openRun, type Run, type RunListing } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';

	const name = $derived(page.params.name ?? '');
	let run = $state<Run | null>(null);
	let latch = $state<Latch | null>(null);
	let runs = $state<RunListing[]>([]);
	let canLaunch = $state(false);
	let jobs = $state<Job[]>([]);
	let missing = $state(false);
	let error = $state<string | null>(null);
	let showAll = $state(false);
	let launchError = $state<string | null>(null);
	// Each point's adjustments, as typed (calendar text), keyed by rank.
	let adjust = $state<Record<number, Adjust>>({});

	$effect(() => {
		const n = name;
		let stale = false;
		run = latch = null;
		missing = false;
		error = null;
		const source = new HttpSource();
		Promise.all([openRun(source, n), loadLatch(source, n), listRuns(), launcher.enabled()])
			.then(([r, l, all, can]) => {
				if (stale) return;
				run = r;
				latch = l;
				missing = !l;
				runs = all;
				canLaunch = can;
				adjust = Object.fromEntries((l?.points ?? []).map((p) => [p.rank, defaults(r, p)]));
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	function defaults(r: Run, p: LatchPoint): Adjust {
		const until = p.ripple.params.until;
		return {
			kind: p.ripple.kind,
			date: r.calendar.format(p.ripple.date, 'day'),
			until: until ? r.calendar.format(until, 'year') : ''
		};
	}

	// One poller: while a what-if runs, ask after it every two seconds; when the last finishes, list the
	// runs again. It depends on the run and the launcher only (`untrack`), never on the jobs it writes.
	const running = $derived(jobs.some((j) => j.state === 'running'));
	let polling = false;
	let alive = true;
	async function poll() {
		if (polling || !alive) return;
		polling = true;
		try {
			const n = untrack(() => name);
			let before = untrack(() => jobs.some((j) => j.state === 'running'));
			for (;;) {
				const now = (await launcher.jobs()).filter((j) => (j.job ?? 'latch') === 'latch' && j.run === n);
				if (!alive || n !== untrack(() => name)) return;
				jobs = now;
				const busy = now.some((j) => j.state === 'running');
				if (before && !busy) runs = await listRuns();
				if (!busy) return;
				before = true;
				await new Promise((r) => setTimeout(r, 2000));
			}
		} catch (e) {
			launchError = `Couldn't ask after the what-ifs: ${(e as Error).message}`;
		} finally {
			polling = false;
		}
	}
	$effect(() => {
		if (canLaunch && name) untrack(poll);
	});
	onDestroy(() => (alive = false));

	async function launch(p: LatchPoint) {
		launchError = null;
		const a = adjust[p.rank];
		try {
			const job = await launcher.launch(name, p.rank, {
				kind: a.kind,
				date: a.date || undefined,
				until: a.kind === 'protect' ? a.until || undefined : undefined
			});
			jobs = [...jobs, job];
			poll();
		} catch (e) {
			launchError = (e as Error).message;
		}
	}

	const whatIfs = $derived(whatIfsOf(runs, name));
	const shown = $derived(latch ? (showAll ? latch.points : latch.points.slice(0, 15)) : []);
	const enc = encodeURIComponent;
	const entityHref = (id: string) => `/run/${enc(name)}/entity/${enc(id)}`;
	const compareHref = (v: string) => `/compare/${enc(name)}/${enc(v)}`;
	const changed = (p: LatchPoint) => {
		const a = adjust[p.rank];
		const d = run ? defaults(run, p) : a;
		return !!a && (a.kind !== d.kind || a.date !== d.date || (a.kind === 'protect' && a.until !== d.until));
	};
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> › latch points ·
	<a href={`/run/${enc(name)}/stories`}>stories</a>
</p>

{#if error}
	<p class="card">{error}</p>
{:else if missing}
	<p class="card">
		No latch points for <strong>{name}</strong> yet. Find them with <code>uv run renasci latch runs/{name}</code>, then
		reload.
	</p>
{:else if !latch || !run}
	<p class="muted">Loading latch points…</p>
{:else}
	<p class="muted intro">
		Moments where a small change would have mattered, best first within each kind. Each suggests a what-if: adjust it,
		launch it, and compare the history that follows with this one.
		{#if !canLaunch}
			Launching from here needs <code>uv run renasci observe --allow-launch</code>; until then, each point shows the
			command to run.
		{/if}
	</p>

	{#if jobs.length}
		<section class="card jobs">
			<h2>What-ifs launched</h2>
			{#each [...jobs].reverse() as j (j.id)}
				<div class="job">
					<span class={`badge ${j.state === 'failed' ? 'warn' : j.state === 'done' ? 'ok' : ''}`}>{j.state}</span>
					{#if j.warning}<span class="badge warn">{j.warning}</span>{/if}
					point {j.rank}{j.kind ? ` · ${j.kind}` : ''}{j.date ? ` · from ${j.date}` : ''}{j.until ? ` until ${j.until}` : ''}
					{#if j.variant}· <a href={compareHref(j.variant)}>compare {j.variant} with {name}</a>{/if}
					{#if j.state === 'failed'}<pre>{j.output}</pre>{/if}
				</div>
			{/each}
		</section>
	{/if}
	{#if launchError}<p class="card warn">{launchError}</p>{/if}

	<ol class="points">
		{#each shown as p (p.rank)}
			{@const a = adjust[p.rank]}
			<li class="card">
				<div class="head">
					<span class="rank">{p.rank}</span>
					<span class={`badge ${p.kind === 'near_miss' ? 'pin' : 'ripple'}`}>{p.kind === 'near_miss' ? 'near miss' : 'died unfulfilled'}</span>
					<span class="mono date">{run.calendar.format(p.date, 'day')}</span>
					<a class="mono" href={entityHref(p.person)}>{p.person}</a>
					<span class="muted score">score {p.score.toFixed(2)}</span>
				</div>
				<p class="why">{p.why}</p>
				<div class="whatif">
					<label
						>What if
						<select bind:value={a.kind}>
							<option value="protect">protect them</option>
							<option value="doom">doom them</option>
						</select>
					</label>
					<label>from <input class="mono" bind:value={a.date} size="14" /></label>
					{#if a.kind === 'protect'}
						<label>until <input class="mono" bind:value={a.until} size="10" /></label>
					{/if}
					<span class="muted">({changed(p) ? 'adjusted' : `suggested: ${p.means}`})</span>
					{#if canLaunch}
						<button disabled={running} onclick={() => launch(p)}>Launch</button>
					{:else}
						<code class="cmd">{latchCommand(name, p.rank, changed(p) ? { kind: a.kind, date: a.date, until: a.kind === 'protect' ? a.until : undefined } : {})}</code>
					{/if}
				</div>
				{#if whatIfs.get(p.rank)}
					<p class="tried">
						Tried:
						{#each whatIfs.get(p.rank) ?? [] as v (v)}
							<a href={compareHref(v)}>{v}</a>
							<a class="muted" href={`/diff/${enc(name)}/${enc(v)}`}>(diff)</a>
						{/each}
					</p>
				{/if}
			</li>
		{/each}
	</ol>
	{#if latch.points.length > 15 && !showAll}
		<button onclick={() => (showAll = true)}>Show all {latch.points.length}</button>
	{/if}
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	.intro {
		margin-top: 0;
	}
	h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	.points {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.7rem;
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.8rem;
		align-items: baseline;
	}
	.rank {
		font-family: var(--serif);
		font-size: 1.2rem;
		font-weight: 600;
	}
	.score {
		margin-left: auto;
	}
	.why {
		margin: 0.3rem 0;
	}
	.whatif {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.9rem;
		align-items: center;
	}
	.cmd {
		display: block;
		width: 100%;
		user-select: all;
		font-size: 0.85rem;
	}
	.tried {
		margin: 0.4rem 0 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.6rem;
	}
	.jobs {
		margin-bottom: 0.8rem;
	}
	.job {
		margin: 0.2rem 0;
	}
	.job pre {
		white-space: pre-wrap;
		font-size: 0.8rem;
		max-height: 10rem;
		overflow: auto;
	}
	.warn {
		color: var(--unexplained);
	}
</style>
