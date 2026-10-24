<script lang="ts">
	/**
	 * The story layer's buttons (#111, S12 §7): a context pack, a chronicle or a campaign brief of this arc,
	 * saga, person or event, made by the launcher (`renasci observe --allow-launch`) into the run's
	 * `analysis/`, and offered as a file when done (a pack has passed its schema check by then). Renders
	 * nothing unless the launcher is on.
	 */
	import { onDestroy, onMount } from 'svelte';

	import { launcher, type Job, type StoryKind, type StorySubject } from '$lib/run/latch';

	let { run, subject, id }: { run: string; subject: StorySubject; id: string } = $props();

	let enabled = $state(false);
	let pov = $state('omniscient');
	let job = $state<Job | null>(null);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setTimeout> | null = null;
	let alive = true;

	const KINDS: [StoryKind, string, string][] = [
		['pack', 'Context pack', 'JSON: the people, places, events and beliefs, from a point of view'],
		['chronicle', 'Chronicle', 'the account its author believes, and where it departs from the truth'],
		['brief', 'Campaign brief', 'for a GM: premise, what really happened, factions, NPCs, hooks']
	];

	onMount(async () => {
		enabled = await launcher.enabled();
	});
	onDestroy(() => {
		alive = false;
		if (timer) clearTimeout(timer);
	});
	$effect(() => {
		void run;
		void id; // a new subject (or run): start over, and stop watching the old job
		if (timer) clearTimeout(timer);
		timer = null;
		job = null;
		error = null;
	});

	async function make(kind: StoryKind) {
		error = null;
		const asked = `${run}|${id}`;
		try {
			const started = await launcher.story(kind, run, subject, id, pov.trim() || 'omniscient');
			if (`${run}|${id}` !== asked) return; // (the page moved to another subject meanwhile)
			job = started;
			watch(started.id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function watch(jid: number) {
		timer = setTimeout(async () => {
			timer = null;
			if (!alive || job?.id !== jid) return;
			try {
				const found = (await launcher.jobs()).find((j) => j.id === jid);
				if (found && job?.id === jid) job = found;
			} catch {
				// (ask again)
			}
			if (job?.id === jid && job.state === 'running') watch(jid);
		}, 1000);
	}

	const fileUrl = (file: string) => `/runs/${file.split('/').map(encodeURIComponent).join('/')}`;
</script>

{#if enabled}
	<section class="story">
		<h3>Write from it</h3>
		<p class="muted small">Made into the run's <code>analysis/</code>. A point of view (a person, house or settlement id) filters the pack and voices the chronicle; the brief is always the GM's.</p>
		<label class="small">Point of view <input bind:value={pov} size="24" class="mono" /></label>
		<div class="buttons">
			{#each KINDS as [kind, label, about] (kind)}
				<button onclick={() => make(kind)} disabled={job?.state === 'running'} title={about}>{label}</button>
			{/each}
		</div>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if job}
			<p aria-live="polite">
				<span class={`badge ${job.state === 'done' ? 'ok' : job.state === 'failed' ? 'warn' : ''}`}>{job.state}</span>
				{job.job}
				{#if job.state === 'done' && job.file}<a href={fileUrl(job.file)} target="_blank" rel="noopener">open {job.file.split('/').pop()}</a>{/if}
			</p>
			{#if job.state === 'failed'}<pre class="out">{job.output.trim().split('\n').slice(-4).join('\n')}</pre>{/if}
		{/if}
	</section>
{/if}

<style>
	.story {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
	}
	.story h3 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
	}
	.buttons {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin: 0.5rem 0;
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
