<script lang="ts">
	import { onMount } from 'svelte';

	import { Calendar } from '$lib/run/calendar';
	import { defaultBaseline } from '$lib/run/diff';
	import { listRuns, openRun, type Manifest, type RunListing } from '$lib/run/run';
	import { PickerSource } from '$lib/run/source';

	let runs = $state<RunListing[] | null>(null);
	let error = $state<string | null>(null);
	let picked = $state<{ name: string; manifest: Manifest }[] | null>(null);

	// Compare: a variant and its baseline. A replay pre-selects the run it was replayed from.
	let variant = $state('');
	let baseline = $state('');
	function pickVariant(name: string) {
		variant = name;
		const m = runs?.find((r) => r.name === name)?.manifest;
		const parent = m ? defaultBaseline(m) : null;
		if (parent && runs?.some((r) => r.name === parent)) baseline = parent;
	}
	const enc = encodeURIComponent;

	onMount(async () => {
		try {
			runs = await listRuns();
			const replay = runs.find((r) => r.manifest.meta.replayed_from);
			if (replay) pickVariant(replay.name);
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
		const names = source.runNames(); // a run folder, or a folder of runs
		if (names.length === 0) {
			error = 'That folder has no run in it (no manifest.json).';
			return;
		}
		try {
			picked = await Promise.all(
				names.map(async (n) => {
					const run = await openRun(source, n);
					return { name: n.split('/').at(-1) ?? n, manifest: run.manifest };
				})
			);
		} catch (e) {
			error = `Couldn't open that run: ${(e as Error).message}`;
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
						<a class="diff-link" href={`/run/${enc(run.name)}/stories`}>stories</a>
						<a class="diff-link" href={`/run/${enc(run.name)}/latch`}>latch points</a>
						{#if m.meta.latch_of}
							<a class="diff-link" href={`/compare/${enc(String((m.meta.latch_of as { run: string }).run))}/${enc(run.name)}`}>compare with {(m.meta.latch_of as { run: string }).run}</a>
						{/if}
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
						{#if defaultBaseline(m)}
							<a class="diff-link" href={`/diff/${enc(defaultBaseline(m) ?? '')}/${enc(run.name)}`}>diff against {defaultBaseline(m)}</a>
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
		{#if runs.length > 1}
			<section class="card compare">
				<h2>Compare two runs</h2>
				<label>Baseline
					<select bind:value={baseline}>
						<option value="" disabled>pick a run</option>
						{#each runs as r (r.name)}<option value={r.name}>{r.name}</option>{/each}
					</select>
				</label>
				<label>Variant
					<select value={variant} onchange={(e) => pickVariant(e.currentTarget.value)}>
						<option value="" disabled>pick a run</option>
						{#each runs as r (r.name)}<option value={r.name}>{r.name}</option>{/each}
					</select>
				</label>
				{#if baseline && variant && baseline !== variant}
					<a class="go" href={`/diff/${enc(baseline)}/${enc(variant)}`}>Show the diff</a>
				{/if}
			</section>
		{/if}
	{/if}
{/if}

<section class="card picker">
	<h2>Open a run folder</h2>
	<p>Without <code>renasci observe</code>, pick one run folder to view it in this browser. Bookmarks and diffs need the server.</p>
	<input type="file" webkitdirectory onchange={pick} aria-label="Pick a run folder" />
	{#if picked}
		<ul>
			{#each picked as p (p.name)}
				<li><strong>{p.name}</strong> · {p.manifest.segments} segments · {p.manifest.meta.complete ? 'complete' : 'incomplete'}</li>
			{/each}
		</ul>
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
	.diff-link {
		margin-left: auto;
		font-size: 0.9rem;
	}
	.compare {
		margin-top: 1.2rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		align-items: end;
	}
	.compare h2 {
		width: 100%;
		margin: 0;
		font-size: 1.05rem;
	}
	.compare label {
		display: flex;
		flex-direction: column;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.compare select {
		font: inherit;
		color: var(--text);
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.3rem 0.5rem;
	}
	.go {
		padding: 0.35rem 0;
	}
</style>
