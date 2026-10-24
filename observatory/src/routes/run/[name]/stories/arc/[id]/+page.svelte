<script lang="ts">
	import { page } from '$app/state';

	import type { Run } from '$lib/run/run';
	import { bornOf, glyph, type Arc, type Saga } from '$lib/run/stories';
	import { loadRunStories } from '$lib/runs';
	import StoryPanel from '$lib/ui/StoryPanel.svelte';

	const name = $derived(page.params.name ?? '');
	const id = $derived(page.params.id ?? '');
	let run = $state<Run | null>(null);
	let arc = $state<Arc | null>(null);
	let saga = $state<Saga | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		const [n, amb] = [name, id];
		let stale = false;
		run = arc = saga = null;
		error = null;
		loadRunStories(n)
			.then(({ run: r, stories }) => {
				if (stale) return;
				run = r;
				if (!stories) return void (error = `No stories for ${n} yet: run \`uv run renasci stories runs/${n}\`.`);
				arc = stories.arcs.find((a) => a.ambition === amb) ?? null;
				if (!arc) return void (error = `No arc for ambition ${amb} in ${n}.`);
				saga = stories.sagas.find((s) => s.arcs.includes(arc!.id)) ?? null;
			})
			.catch((e) => {
				if (!stale) error = (e as Error).message;
			});
		return () => (stale = true);
	});

	const enc = encodeURIComponent;
	const eventHref = (e: string) => `/run/${enc(name)}/events?e=${enc(e)}`;
	const entityHref = (e: string) => `/run/${enc(name)}/entity/${enc(e)}`;
	const date = (d: [number, number, number]) => (run ? run.calendar.format(d, 'season') : d.join('-'));
</script>

<p class="crumbs">
	<a href="/">Runs</a> › <a href={`/run/${enc(name)}/events`}>{name}</a> ›
	<a href={`/run/${enc(name)}/stories`}>stories</a> › arc
</p>

{#if error}
	<p class="card">{error}</p>
{:else if !arc}
	<p class="muted">Loading…</p>
{:else}
	<h1>{arc.title}</h1>
	<StoryPanel run={name} subject="arc" id={arc.id} />
	<section class="card facts">
		<dl>
			<dt>Who</dt>
			<dd><a href={entityHref(arc.owner)}>{arc.owner_name}</a> wanted to {arc.class === 'Marry' ? 'marry' : arc.class.toLowerCase()}
				{#if arc.target}— aimed at <a href={entityHref(arc.target)}>{arc.target_name}</a>{/if}</dd>
			<dt>Born of</dt>
			<dd>
				{bornOf(arc)}
				{#if arc.born_of?.[0] === 'event'}<a class="mono" href={eventHref(arc.born_of[1])}>{arc.born_of[1]}</a>{/if}
				{#if arc.formed_by}· formed in <a class="mono" href={eventHref(arc.formed_by)}>{arc.formed_by}</a>{/if}
			</dd>
			<dt>Outcome</dt>
			<dd>{glyph(arc.outcome)} {arc.outcome.replace('_', ' ')} · years {arc.span[0]}–{arc.span[1]} · salience {arc.salience.toFixed(1)}</dd>
			{#if saga}
				<dt>Saga</dt>
				<dd><a href={`/run/${enc(name)}/stories/saga/${enc(saga.id)}`}>{saga.title}</a> ({saga.arcs.length} arcs)</dd>
			{/if}
			<dt>Ambition</dt>
			<dd><a class="mono" href={entityHref(arc.ambition)}>{arc.ambition}</a></dd>
		</dl>
	</section>

	{#if arc.progress.length}
		<section class="card">
			<h2>Schemes</h2>
			{#each arc.progress as p (p.scheme)}
				<div class="scheme">
					<a class="mono" href={entityHref(p.scheme)}>{p.scheme}</a> · {p.state}
					<ol class="plan">
						{#each p.plan as step, i (i)}
							<li class:done={i < p.step} class:now={i === p.step && p.state === 'active'}>{step}</li>
						{/each}
					</ol>
					<div class="bar"><span style={`width: ${p.steps ? (100 * p.step) / p.steps : 0}%`}></span></div>
				</div>
			{/each}
		</section>
	{/if}

	<section class="card">
		<h2>Beats</h2>
		<table>
			<tbody>
				{#each arc.timeline as b (b.event)}
					<tr class:turn={!!b.turn}>
						<td class="mono date">{date(b.date)}</td>
						<td><a href={eventHref(b.event)}>{b.type}</a></td>
						<td>{b.turn ?? ''}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>

	<section class="card">
		<h2>People touched</h2>
		<p class="people">
			{#each arc.people as p (p)}<a class="mono" href={entityHref(p)}>{p}</a>{/each}
		</p>
	</section>
{/if}

<style>
	.crumbs {
		color: var(--muted);
		margin-top: 0;
	}
	h1 {
		margin: 0.2rem 0 0.8rem;
	}
	h2 {
		margin: 0 0 0.4rem;
		font-size: 1.1rem;
	}
	section {
		margin-bottom: 1rem;
	}
	dl {
		display: grid;
		grid-template-columns: 7rem 1fr;
		gap: 0.3rem 1rem;
		margin: 0;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
	}
	.plan {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.4rem;
		margin: 0.3rem 0;
	}
	.plan li.done {
		color: var(--muted);
		text-decoration: line-through;
	}
	.plan li.now {
		font-weight: 600;
	}
	.bar {
		height: 4px;
		background: var(--surface-2);
		border-radius: 2px;
	}
	.bar span {
		display: block;
		height: 100%;
		background: var(--accent);
		border-radius: 2px;
	}
	table {
		border-collapse: collapse;
		width: 100%;
	}
	td {
		padding: 0.15rem 0.6rem 0.15rem 0;
		border-bottom: 1px solid var(--border);
	}
	tr.turn td {
		font-weight: 600;
	}
	.date {
		white-space: nowrap;
		color: var(--muted);
	}
	.people {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.9rem;
		margin: 0;
	}
</style>
