<script lang="ts">
	/**
	 * Propose a run's event or person to the vault as a `canon: proposed` note (#105, S2 §9), keeping the
	 * causes ticked. Renders nothing unless the server can write to a vault (`renasci observe
	 * --allow-launch --vault docs`). Promotion itself (setting `canon: true`) stays in the vault, by hand.
	 */
	import { onDestroy, onMount } from 'svelte';

	import { launcher, type Job } from '$lib/run/latch';

	let { run, entity, causes = [] }: { run: string; entity: string; causes?: [string, string][] } = $props();

	let enabled = $state(false);
	let keep = $state<Record<string, boolean>>({});
	let job = $state<Job | null>(null);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setTimeout> | null = null;
	let alive = true;

	onMount(async () => {
		enabled = await launcher.canPropose();
	});
	onDestroy(() => {
		alive = false;
		if (timer) clearTimeout(timer);
	});
	$effect(() => {
		void run;
		void entity; // a new event or person (or run): start over, and stop watching the old job
		if (timer) clearTimeout(timer);
		timer = null;
		job = null;
		error = null;
		keep = {};
	});

	const key = ([kind, ref]: [string, string]) => `${kind}:${ref}`;

	async function propose() {
		error = null;
		try {
			job = await launcher.propose(run, entity, causes.map(key).filter((k) => keep[k]));
			watch(job.id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function watch(id: number) {
		timer = setTimeout(async () => {
			timer = null;
			if (!alive) return;
			if (job?.id !== id) return; // (the panel moved on to another event)
			try {
				const found = (await launcher.jobs()).find((j) => j.id === id);
				if (found && job?.id === id) job = found;
			} catch {
				// (ask again)
			}
			if (job?.id === id && job.state === 'running') watch(id);
		}, 1000);
	}
</script>

{#if enabled}
	<section class="promote">
		<h3>Propose to the vault</h3>
		<p class="muted small">Writes a <code>canon: proposed</code> note in the vault's <code>_proposed/</code> (never over one you've edited). It becomes canon only when you promote it there.</p>
		{#if causes.length}
			<fieldset>
				<legend class="small">Causes to keep with it</legend>
				{#each causes as c (key(c))}
					<label class="cause"><input type="checkbox" bind:checked={keep[key(c)]} /> <span class="mono small">{c[0]} {c[1]}</span></label>
				{/each}
			</fieldset>
		{/if}
		<button onclick={propose} disabled={job?.state === 'running'}>Propose</button>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if job}
			<p aria-live="polite">
				<span class={`badge ${job.state === 'done' ? 'ok' : job.state === 'failed' ? 'warn' : ''}`}>{job.state}</span>
				{#if job.state === 'done' && job.variant}wrote <code>{job.variant}</code>{/if}
			</p>
			{#if job.state === 'failed'}<pre class="out">{job.output.trim().split('\n').slice(-4).join('\n')}</pre>{/if}
		{/if}
	</section>
{/if}

<style>
	.promote {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
	}
	.promote h3 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
	}
	fieldset {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		margin: 0.5rem 0;
		padding: 0.35rem 0.6rem;
	}
	.cause {
		display: block;
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
