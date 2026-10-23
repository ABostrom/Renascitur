<script lang="ts">
	/**
	 * Launch runs and replays from the server's recipes folder (`renasci observe --allow-launch`, #57).
	 * Renders nothing when the launcher is off: without it the Observatory is read-only.
	 */
	import { onDestroy, onMount } from 'svelte';

	import { launcher, type Job, type Recipe } from '$lib/run/latch';

	let { runs, onfinished }: { runs: string[]; onfinished: () => void } = $props();

	let enabled = $state(false);
	let recipes = $state<Recipe[]>([]);
	let jobs = $state<Job[]>([]);
	let base = $state<Record<string, string>>({}); // replay: the run each ripple recipe forks
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setTimeout> | null = null;
	let alive = true;

	const running = $derived(jobs.some((j) => j.state === 'running'));
	const mine = $derived(jobs.filter((j) => j.job === 'run' || j.job === 'replay').slice(-5).reverse());

	onMount(async () => {
		enabled = await launcher.enabled();
		if (!enabled) return;
		[recipes, jobs] = await Promise.all([launcher.recipes(), launcher.jobs()]);
		if (running) poll();
	});
	onDestroy(() => {
		alive = false;
		if (timer) clearTimeout(timer);
	});

	function poll() {
		if (timer || !alive) return;
		timer = setTimeout(async () => {
			timer = null;
			if (!alive) return;
			const was = new Set(jobs.filter((j) => j.state === 'running').map((j) => j.id));
			try {
				jobs = await launcher.jobs();
				if (alive && jobs.some((j) => was.has(j.id) && j.state !== 'running')) {
					onfinished();
					recipes = await launcher.recipes();
				}
			} catch {
				// (the server was busy or restarting: ask again next time)
			}
			if (running) poll();
		}, 1500);
	}

	async function go(start: () => Promise<Job>) {
		error = null;
		try {
			const job = await start();
			jobs = [...jobs, job];
			poll();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const what = (j: Job) => (j.job === 'replay' ? `replay ${j.run} with ${j.recipe}` : `run ${j.recipe}`);
</script>

{#if enabled}
	<section class="card launch">
		<h2>Launch</h2>
		<p class="muted small">From the recipes folder this server was started with. Each writes a new run folder; one at a time.</p>
		{#if recipes.length === 0}
			<p class="muted">No recipes (<code>.toml</code> files) in the recipes folder.</p>
		{:else}
			<div class="scroll">
				<table>
					<thead><tr><th>recipe</th><th>world</th><th>until</th><th></th></tr></thead>
					<tbody>
						{#each recipes as r (r.file)}
							<tr>
								<td><code>{r.file}</code>{#if r.name}<span class="muted small"> → {r.name}</span>{/if}</td>
								<td>{r.world ?? '—'}</td>
								<td class="mono">{r.end ?? '—'}</td>
								<td class="actions">
									{#if r.error}
										<span class="badge warn" title={r.error}>can't read it</span>
									{:else}
										<button disabled={running || runs.includes(r.name ?? '')}
											title={runs.includes(r.name ?? '') ? `a run named ${r.name} exists` : ''}
											onclick={() => go(() => launcher.run(r.file))}>Run</button>
										{#if r.ripples > 0}
											<label class="small">replay
												<select bind:value={base[r.file]} aria-label={`Run to replay with ${r.file}`}>
													<option value="">a run…</option>
													{#each runs as n (n)}<option value={n}>{n}</option>{/each}
												</select>
											</label>
											<button disabled={running || !base[r.file]} onclick={() => go(() => launcher.replay(base[r.file], r.file))}>Replay</button>
										{/if}
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if mine.length}
			<ul class="jobs" aria-live="polite">
				{#each mine as j (j.id)}
					<li>
						<span class={`badge ${j.state === 'done' ? 'ok' : j.state === 'failed' ? 'warn' : ''}`}>{j.state}</span>
						{what(j)}
						{#if j.state === 'done' && j.variant}· <a href={`/run/${encodeURIComponent(j.variant)}/events`}>open {j.variant}</a>{/if}
						{#if j.state === 'failed'}<pre class="out">{j.output.trim().split('\n').slice(-4).join('\n')}</pre>{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<style>
	.small {
		font-size: 0.85rem;
	}
	.scroll {
		overflow-x: auto;
	}
	th,
	td {
		padding: 0.25rem 0.9rem 0.25rem 0;
		text-align: left;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.jobs {
		list-style: none;
		padding: 0;
		margin: 0.75rem 0 0;
	}
	.jobs li {
		padding: 0.25rem 0;
	}
	.out {
		margin: 0.25rem 0 0;
		font-size: 0.8rem;
		white-space: pre-wrap;
		color: var(--muted);
	}
	.error {
		color: var(--unexplained);
	}
</style>
