<script lang="ts">
	import { onMount } from 'svelte';

	import { Calendar } from '$lib/run/calendar';
	import { listRuns, openRun, type Manifest, type RunListing } from '$lib/run/run';
	import { PickerSource } from '$lib/run/source';

	let runs = $state<RunListing[] | null>(null);
	let error = $state<string | null>(null);
	let picked = $state<{ name: string; manifest: Manifest } | null>(null);

	onMount(async () => {
		try {
			runs = await listRuns();
		} catch (e) {
			error = (e as Error).message;
		}
	});

	function fmt(m: Manifest, d: [number, number, number] | undefined) {
		if (!d) return '';
		return m.meta.calendar ? Calendar.fromJson(m.meta.calendar).format(d, 'year') : d.join('-');
	}

	async function pick(event: Event) {
		const files = (event.target as HTMLInputElement).files;
		if (!files || files.length === 0) return;
		const source = new PickerSource(files);
		try {
			const run = await openRun(source, source.name);
			picked = { name: run.name, manifest: run.manifest };
		} catch (e) {
			error = `That folder isn't a run folder: ${(e as Error).message}`;
		}
	}
</script>

<h1>Runs</h1>

{#if error && !runs}
	<p class="card note">
		{error}<br />
		Start it with <code>uv run renasci observe runs</code>, or open one run folder below.
	</p>
{/if}

{#if runs}
	{#if runs.length === 0}
		<p class="card">No runs yet. Make one with <code>uv run renasci run recipes/toy-baseline.toml</code>.</p>
	{:else}
		<ul class="runs">
			{#each runs as run (run.name)}
				{@const m = run.manifest}
				{@const recipe = m.meta.recipe?.run ?? {}}
				<li class="card">
					<div class="head">
						<a class="name" href={`/run/${encodeURIComponent(run.name)}/events`}>{run.name}</a>
						{#if m.meta.complete}
							<span class="badge ok">complete</span>
						{:else}
							<span class="badge warn">incomplete</span>
						{/if}
						{#if m.meta.replayed_from}
							<span class="badge ripple">replay of {m.meta.replayed_from.run} from {fmt(m, m.meta.replayed_from.at)}</span>
						{/if}
						{#if (m.meta.recipe?.ripple ?? []).length}
							<span class="badge ripple">{m.meta.recipe?.ripple.length} ripple(s)</span>
						{/if}
					</div>
					<dl>
						<dt>world</dt><dd>{recipe.world ?? '—'}</dd>
						<dt>seed</dt><dd class="mono">{recipe.seed ?? '—'}</dd>
						<dt>to</dt><dd>{recipe.end ?? '—'}</dd>
						<dt>segments</dt><dd>{m.segments}</dd>
						<dt>checkpoints</dt><dd>{m.marks.map((k) => fmt(m, k.before)).join(', ') || '—'}</dd>
						<dt>engine</dt><dd class="mono">{m.engine}{m.versions ? ` · py ${m.versions.python} · numpy ${m.versions.numpy}` : ''}</dd>
						<dt>state</dt><dd class="mono">{m.meta.state_hash ?? '—'}</dd>
					</dl>
				</li>
			{/each}
		</ul>
	{/if}
{/if}

<section class="card picker">
	<h2>Open a run folder</h2>
	<p>Without <code>renasci observe</code>, pick one run folder to view it in this browser. Bookmarks and diffs need the server.</p>
	<input type="file" webkitdirectory onchange={pick} aria-label="Pick a run folder" />
	{#if picked}
		<p>Opened <strong>{picked.name}</strong> · {picked.manifest.segments} segments · {picked.manifest.meta.complete ? 'complete' : 'incomplete'}</p>
	{/if}
</section>

<style>
	.runs {
		list-style: none;
		padding: 0;
		display: grid;
		gap: 0.9rem;
	}
	.head {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.name {
		font-family: var(--serif);
		font-size: 1.15rem;
		font-weight: 600;
		text-decoration: none;
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.15rem 1rem;
		margin: 0.6rem 0 0;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}
	.note {
		border-color: var(--divergent);
	}
	.picker {
		margin-top: 2rem;
	}
</style>
