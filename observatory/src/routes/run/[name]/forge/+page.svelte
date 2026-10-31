<script lang="ts">
	import { page } from '$app/state';

	import { FILTERS, facts, forge, keepable, type Card, type Found, type Truths } from '$lib/run/forge';

	/** The Forge (#165): find what's worth having in a run, read its card, keep it for the next. */
	const name = $derived(page.params.name ?? '');
	const base = $derived(`/run/${encodeURIComponent(name)}`);
	const why = (id: string) => `${base}/events?e=${encodeURIComponent(id)}`;

	let on = $state(false);
	let what = $state('person');
	let filters = $state<Record<string, string>>({});
	let notable = $state(true);
	let seed = $state(0);
	let found = $state.raw<Found | null>(null);
	let chosen = $state.raw<Card | null>(null);
	let truths = $state.raw<Truths>({});
	let busy = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		forge.enabled().then(async (yes) => {
			on = yes;
			if (yes) truths = await forge.truths();
		});
	});

	async function act(work: () => Promise<void>) {
		busy = true;
		error = null;
		try {
			await work();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
	const search = () =>
		act(async () => {
			found = await forge.search(name, { what, filters, notable, seed });
			chosen = found.cards[0] ?? null;
		});
	const keep = (c: Card) =>
		act(async () => {
			await forge.keep(name, c.id);
			truths = await forge.truths();
		});
</script>

<svelte:head><title>The Forge · {name}</title></svelte:head>

<h1>The Forge</h1>
{#if !on}
	<p>
		To find and keep things here, start the Observatory with
		<code>renasci observe --allow-launch --truths my_world.json</code>. From the terminal, it's
		<code>renasci gen</code> and <code>renasci keep</code>.
	</p>
{:else}
	<div class="forge">
		<form
			onsubmit={(e) => {
				e.preventDefault();
				search();
			}}
		>
			<label>
				Find
				<select bind:value={what} onchange={() => (filters = {})}>
					{#each Object.keys(FILTERS) as w}<option>{w}</option>{/each}
				</select>
			</label>
			{#each FILTERS[what] as f}
				<label>{f} <input bind:value={filters[f]} /></label>
			{/each}
			<label class="row"><input type="checkbox" bind:checked={notable} /> most to tell first</label>
			<label>seed <input type="number" bind:value={seed} /></label>
			<button disabled={busy}>{busy ? 'Looking…' : 'Find'}</button>
			{#if found}
				<p>{found.found} found</p>
				{#if found.closest}
					<p>Loosen one to find more:</p>
					<ul>
						{#each Object.entries(found.closest) as [k, n]}<li>without {k}: {n}</li>{/each}
					</ul>
				{/if}
				<ul class="list">
					{#each found.cards as c}
						<li>
							<button type="button" class:on={chosen?.id === c.id} onclick={() => (chosen = c)}>
								{c.name ?? c.type ?? c.id}
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</form>

		<section>
			{#if error}<p class="error">{error}</p>{/if}
			{#if chosen}
				<h2><a href={`${base}/entity/${encodeURIComponent(chosen.id)}`}>{chosen.name ?? chosen.type ?? chosen.id}</a></h2>
				<dl>
					{#each facts(chosen) as [k, v]}<dt>{k}</dt><dd>{v}</dd>{/each}
				</dl>
				{#if chosen.marks.length}
					<p>Marked: {#each chosen.marks as m, i}{i ? ', ' : ''}<a href={why(m.event)}>{m.mark}</a>{/each}</p>
				{/if}
				<h3>What happened{chosen.told > chosen.history.length ? ` (${chosen.history.length} of ${chosen.told})` : ''}</h3>
				<ol>
					{#each chosen.history as line}<li><a href={why(line.event)}>{line.text}</a></li>{/each}
				</ol>
				{#if keepable(chosen)}
					<button disabled={busy} onclick={() => chosen && keep(chosen)}>Keep</button>
				{:else}
					<p>Only things can be kept so far.</p>
				{/if}
			{/if}
		</section>

		<aside>
			<h2>World truths</h2>
			{#each truths.objects ?? [] as o}<p>{o.name ?? o.type} <small>{o.place}</small></p>{/each}
			{#each truths.places ?? [] as p}<p>{p.name} <small>{p.kind}</small></p>{/each}
			{#if !truths.objects?.length && !truths.places?.length}<p>Nothing kept yet.</p>{/if}
			<p><small>To run a world with these, name the file in a recipe: <code>[world] truths</code>.</small></p>
		</aside>
	</div>
{/if}

<style>
	.forge {
		display: grid;
		grid-template-columns: minmax(12rem, 16rem) minmax(0, 1fr) minmax(12rem, 16rem);
		gap: 1.5rem;
	}
	@media (max-width: 800px) {
		.forge {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	label {
		display: block;
		margin-bottom: 0.4rem;
	}
	label input:not([type='checkbox']),
	select {
		display: block;
		width: 100%;
	}
	.list {
		list-style: none;
		padding: 0;
	}
	.on {
		font-weight: 600;
	}
	.error {
		color: var(--bad, #b00);
	}
	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.1rem 1rem;
	}
	dd {
		margin: 0;
	}
</style>
