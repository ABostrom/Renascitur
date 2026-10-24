<script lang="ts">
	import { page } from '$app/state';

	import { glyph, type Arc, type Saga } from '$lib/run/stories';
	import { loadRunStories } from '$lib/runs';
	import StoryPanel from '$lib/ui/StoryPanel.svelte';

	const name = $derived(page.params.name ?? '');
	const id = $derived(page.params.id ?? '');
	let saga = $state<Saga | null>(null);
	let arcs = $state<Arc[]>([]);
	let error = $state<string | null>(null);

	$effect(() => {
		const [n, sid] = [name, id];
		let stale = false;
		saga = null;
		arcs = [];
		error = null;
		loadRunStories(n)
			.then(({ stories }) => {
				if (stale) return;
				if (!stories) return void (error = `No stories for ${n} yet: run \`uv run renasci stories runs/${n}\`.`);
				saga = stories.sagas.find((s) => s.id === sid) ?? null;
				if (!saga) return void (error = `No saga ${sid} in ${n}.`);
				const mine = new Set(saga.arcs);
				arcs = stories.arcs.filter((a) => mine.has(a.id)).sort((x, y) => x.span[0] - y.span[0] || y.salience - x.salience);
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const enc = encodeURIComponent;
	const entityHref = (e: string) => `/run/${enc(name)}/entity/${enc(e)}`;
	const arcHref = (amb: string) => `/run/${enc(name)}/stories/arc/${enc(amb)}`;
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> ›
	<a href={`/run/${enc(name)}/stories`}>stories</a> › saga
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !saga}
	<p class="muted">Loading…</p>
{:else}
	<h1>{saga.title}</h1>
	<p class="muted">
		Years {saga.span[0]}–{saga.span[1]} · {saga.arcs.length} arcs · {saga.people.length} people · salience {saga.salience.toFixed(1)}
		· <a href={`/run/${enc(name)}/stories?from=${saga.span[0]}&to=${saga.span[1]}`}>see it on the river</a>
	</p>
	<StoryPanel run={name} subject="saga" id={saga.id} />
	<section class="card">
		<h2>Arcs, in order</h2>
		<table>
			<tbody>
				{#each arcs as a (a.id)}
					<tr>
						<td class="years">{a.span[0]}–{a.span[1]}</td>
						<td class="glyph">{glyph(a.outcome)}</td>
						<td><a href={arcHref(a.ambition)}>{a.title}</a></td>
						<td class="muted">{a.class} · <a href={entityHref(a.owner)}>{a.owner_name}</a></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>
	<section class="card">
		<h2>People</h2>
		<p class="people">
			{#each saga.people as p (p)}<a class="mono" href={entityHref(p)}>{p}</a>{/each}
		</p>
	</section>
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	h1 {
		margin: 0.2rem 0 0.3rem;
	}
	h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	section {
		margin-bottom: 1rem;
	}
	table {
		border-collapse: collapse;
		width: 100%;
	}
	td {
		padding: 0.2rem 0.6rem 0.2rem 0;
		border-bottom: 1px solid var(--border);
	}
	.years {
		white-space: nowrap;
		color: var(--muted);
	}
	.glyph {
		width: 1.2rem;
	}
	.people {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.9rem;
		margin: 0;
	}
</style>
