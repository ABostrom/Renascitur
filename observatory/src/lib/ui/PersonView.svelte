<script lang="ts">
	import type { Calendar, DateTuple } from '$lib/run/calendar';
	import type { EntityChange } from '$lib/run/entity';
	import { asOf, moments, personView, raceName, type StateIndex, type Who } from '$lib/run/person';
	import { beliefsOf, motives, type Lookup, type Step } from '$lib/run/provenance';

	import PromotePanel from './PromotePanel.svelte';

	let {
		ix,
		id,
		run,
		cal,
		changes,
		end,
		lookup
	}: { ix: StateIndex; id: string; run: string; cal: Calendar; changes: EntityChange[]; end: DateTuple; lookup: Lookup } = $props();

	const me = $derived(ix.get(id)!);
	const view = $derived(personView(ix, id));
	// The "as of" control steps through the years this record changed, from its creation to the run's end.
	const steps = $derived(moments(changes, end));
	let step = $state<number | null>(null);
	const at = $derived(steps.length ? Math.min(steps.length - 1, step ?? steps.length - 1) : -1);
	const when = $derived(at >= 0 ? steps[at] : null);
	const then = $derived(when ? asOf(me.fields, changes, when) : me.fields);

	const href = (x: string) => `/run/${encodeURIComponent(run)}/entity/${encodeURIComponent(x)}`;
	const eventHref = (e: string) => `/run/${encodeURIComponent(run)}/events?e=${encodeURIComponent(e)}`;
	const date = (d: DateTuple | null) => (d ? cal.format(d, 'year') : '—');
	const whoIs = (x: string): Who => ({ id: x, name: ix.get(x)?.fields.name ?? x, status: ix.get(x)?.status ?? 'unknown' });
	const wound = $derived(then.wound as { kind: string; event: string; since: DateTuple } | null);
	const wants = $derived((then.wants as string[] | null) ?? []);
	const grievances = $derived(
		(then.grievances as { against: string; event: string; kind: string; answered?: string }[] | null) ?? []
	);
	const race = $derived(raceName(me.fields.race));
	const beliefs = $derived(beliefsOf(then.beliefs as Record<string, any> | null, ix, lookup));
	const moves = $derived(motives(id, ix, me.fields.beliefs, lookup).filter((m) => m.trace.length));
	const atEnd = $derived(at < 0 || at === steps.length - 1);
	const STEP: Record<string, string> = {
		'belief.perceived': 'saw it',
		'belief.told': 'was told it',
		'belief.corrected': 'learned the truth',
		'belief.heard': 'heard it as news from the road'
	};
	function stepText(s: Step): string {
		const e = s.event;
		const holder = e.roles?.holder?.[0];
		const teller = e.roles?.teller?.[0];
		if (e.type === 'belief.told') {
			const how = s.lie ? 'was lied to' : e.payload?.intent === 'leak' ? 'had it let slip' : 'was told it';
			return `${whoIs(holder).name} ${how} by ${whoIs(teller).name}`;
		}
		if (e.type === 'belief.news_arrived') return `news came by road from ${whoIs(e.payload?.from).name}`;
		if (STEP[e.type]) return `${holder ? whoIs(holder).name + ' ' : ''}${STEP[e.type]}`;
		const what = String(e.type).replace(/[._]/g, ' ');
		return e.payload?.action ? `${e.payload.action} (${what})` : `the ${what}`;
	}
</script>

{#snippet walk(trace: Step[])}
	{#if trace.length}
		<ol class="trace">
			{#each trace as s, i (s.event.id)}
				<li class:lie={s.lie}>
					<a href={eventHref(s.event.id)} aria-label={`${date(s.event.date)}: ${stepText(s)} (the event)`}>{date(s.event.date)}</a> {stepText(s)}
					{#if s.lie}<span class="badge warn">lie</span>{:else if i && trace[i - 1].lie}<span class="badge ripple">behind the lie</span>{:else if s.origin}<span class="badge pin">where it began</span>{/if}
					{#if s.more}<span class="muted small">…and further back</span>{/if}
				</li>
			{/each}
		</ol>
	{:else}
		<p class="muted small">No record of where it came from.</p>
	{/if}
{/snippet}

{#snippet person(p: Who, role = '')}
	<a class="who" class:dead={p.status === 'dead'} class:dormant={p.status === 'dormant'} href={href(p.id)}
		title={`${role ? `${role}: ` : ''}${p.name}${p.status === 'dead' || p.status === 'dormant' ? ` (${p.status})` : ''}`}>
		{p.name}{#if p.status === 'dead'}<span class="muted" aria-hidden="true"> †</span><span class="sr">(dead)</span>{:else if p.status === 'dormant'}<span class="sr">(dormant)</span>{/if}
	</a>
{/snippet}

<section class="card person">
	<h2>{view.name}</h2>
	<p class="muted">
		{me.fields.sex === 'f' ? 'Woman' : me.fields.sex === 'm' ? 'Man' : 'Person'}{#if race}{' '}of {race}{/if}{#if view.born}, born {date(view.born)}{/if}{#if view.house}, of
			<a href={href(view.house.id)}>House {view.house.name}</a>{/if}{#if me.status !== 'active'} ({me.status}){/if}.
	</p>

	<PromotePanel {run} entity={id} />

	<h3>Family</h3>
	<div class="tree" aria-label="Family tree">
		<div class="row"><span class="label muted">parents</span>{#each view.parents as p (p.id)}{@render person(p, 'parent')}{:else}<span class="muted">unknown</span>{/each}</div>
		<div class="row">
			<span class="label muted">generation</span>
			<strong class="who self">{view.name}</strong>
			{#if view.spouse}<span class="muted">married to</span>{@render person(view.spouse, 'spouse')}{/if}
			{#if view.siblings.length}<span class="muted">· siblings</span>{#each view.siblings as s (s.id)}{@render person(s, 'sibling')}{/each}{/if}
		</div>
		<div class="row"><span class="label muted">children</span>{#each view.children as c (c.id)}{@render person(c, 'child')}{:else}<span class="muted">none</span>{/each}</div>
	</div>

	<h3>Inner life {when ? `as of ${date(when)}` : 'at the end'}</h3>
	{#if steps.length > 1}
		<label class="year">
			<span class="muted">year</span>
			<input type="range" min="0" max={steps.length - 1} value={at} aria-label="Year" aria-valuetext={date(when)}
				oninput={(e) => (step = +e.currentTarget.value)} />
			<span class="mono">{date(when)}</span>
			<span class="muted small">(the years something about them changed)</span>
		</label>
	{/if}
	<dl class="inner">
		<dt>Wound</dt>
		<dd>{#if wound}{wound.kind} <a class="muted" href={eventHref(wound.event)}>(since {date(wound.since)})</a>{:else}<span class="muted">none</span>{/if}</dd>
		<dt>Need</dt>
		<dd>{then.need ?? '—'}</dd>
		<dt>Wants</dt>
		<dd>{#if wants.length}<ul>{#each wants as w, i (i)}<li>{w}</li>{/each}</ul>{:else}<span class="muted">nothing pressing</span>{/if}</dd>
		<dt>Grievances</dt>
		<dd>
			{#if grievances.length}
				<ul>
					{#each grievances as g, i (i)}
						<li>
							against {@render person(whoIs(g.against))} ({g.kind}) <a class="muted" href={eventHref(g.event)}>why</a>
							{#if g.answered}· taken up as <a href={href(g.answered)}>an ambition</a>{/if}
						</li>
					{/each}
				</ul>
			{:else}<span class="muted">none</span>{/if}
		</dd>
		<dt>Favour at court</dt>
		<dd class="mono">{then.favour ?? 0}</dd>
		<dt>Lives in</dt>
		<dd>{#if then.place}<a href={href(String(then.place))}>{ix.get(String(then.place))?.fields.name ?? then.place}</a>{:else}—{/if}</dd>
	</dl>

	{#if beliefs.length}
		<h3>Beliefs ({beliefs.length})</h3>
		<p class="muted small">What they hold to be so, firmest first, and where each came from.</p>
		<ul class="beliefs">
			{#each beliefs as b (b.key)}
				<li>
					<details>
						<summary>
							{b.text} <span class="muted small">({Math.round(b.conf * 100)}% sure{b.secret ? ', kept secret' : ''})</span>
							{#if b.lie}<span class="badge warn">a lie in its past</span>{/if}
						</summary>
						{@render walk(b.trace)}
					</details>
				</li>
			{/each}
		</ul>
	{/if}
	{#if moves.length && atEnd}
		<h3>What moves them</h3>
		<ul class="beliefs">
			{#each moves as m (m.ambition)}
				<li>
					<a href={href(m.ambition)}>{m.class}</a>{#if m.target} against {@render person(whoIs(m.target))}{/if}, because
					{#if m.belief && me.fields.beliefs?.[m.belief]}they believe {beliefs.find((b) => b.key === m.belief)?.text ?? m.belief}{:else}of what happened{/if}:
					{@render walk(m.trace)}
				</li>
			{/each}
		</ul>
	{/if}

	<h3>Ambitions ({view.ambitions.length}, over the whole run)</h3>
	{#if view.ambitions.length}
		<div class="scroll">
			<table>
				<thead><tr><th>ambition</th><th>against</th><th>formed</th><th>outcome</th></tr></thead>
				<tbody>
					{#each view.ambitions as a (a.id)}
						<tr>
							<td><a href={href(a.id)}>{a.class}</a></td>
							<td>{#if a.target}{@render person(a.target)}{:else}<span class="muted">—</span>{/if}</td>
							<td class="mono">{date(a.formed)}</td>
							<td><span class={`badge ${a.state === 'fulfilled' ? 'ok' : a.state === 'active' ? '' : 'warn'}`}>{a.state}</span> {#if a.resolved}<span class="muted mono">{date(a.resolved)}</span>{/if}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="muted">None formed.</p>
	{/if}

	<h3>Ties ({view.ties.length}, at the end)</h3>
	{#if view.ties.length}
		<ul class="ties">
			{#each view.ties as t (t.id)}
				<li class:ended={t.ended}>
					<span class={`badge tie ${t.kind}`}>{t.kind}</span>
					{@render person(t.other)}
					<span class="bar" title={`strength ${t.strength}`}><span style:width={`${Math.round(100 * (t.strength ?? 0))}%`}></span></span>
					<span class="muted mono">{date(t.since)}{t.ended ? `–${date(t.ended)}` : ''}</span>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="muted">No ties.</p>
	{/if}

	<h3>Genome</h3>
	{#if view.alleles.length}
		<div class="scroll">
			<table class="genome">
				<thead><tr><th>locus</th><th>from</th><th>variant</th><th>entered the line</th></tr></thead>
				<tbody>
					{#each view.alleles as c, i (i)}
						<tr>
							<td class="mono">{c.locus}</td>
							<td>{c.from}</td>
							<td class="mono">{c.variant}</td>
							<td>{#if c.origin === 'founder'}founder stock of <span class="mono">{c.where}</span>{:else}a mutation at <a class="mono" href={eventHref(c.where)}>a birth</a>{/if}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else}
		<p class="muted">No genome in this world.</p>
	{/if}
</section>

<style>
	.beliefs {
		list-style: none;
		padding: 0;
	}
	.beliefs > li {
		margin: 0.35rem 0;
	}
	.trace {
		margin: 0.3rem 0 0.5rem 1.2rem;
		font-size: 0.9rem;
	}
	.trace li.lie {
		color: var(--unexplained);
	}
	.person h3 {
		margin: 1.25rem 0 0.5rem;
		font-size: 1rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.tree .row {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.35rem 0.6rem;
		padding: 0.35rem 0;
		border-bottom: 1px solid var(--border);
	}
	.tree .label {
		width: 6.5rem;
		flex: none;
		font-size: 0.85rem;
	}
	.who {
		padding: 0.05rem 0.45rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface-2);
	}
	.who.self {
		border-color: var(--accent);
	}
	.who.dead {
		opacity: 0.75;
	}
	.who.dormant {
		border-style: dashed;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.small {
		font-size: 0.85rem;
	}
	.year {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.inner {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.3rem 1rem;
	}
	.inner dt {
		color: var(--muted);
	}
	.inner dd {
		margin: 0;
	}
	.inner ul {
		margin: 0;
		padding-left: 1.1rem;
	}
	.ties {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.ties li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding: 0.2rem 0;
	}
	.ties li.ended {
		opacity: 0.6;
	}
	.tie.enemy,
	.tie.rival {
		color: var(--unexplained);
	}
	.tie.friend,
	.tie.mentor {
		color: var(--ok);
	}
	.bar {
		display: inline-block;
		width: 4rem;
		height: 0.4rem;
		background: var(--surface-2);
		border-radius: 2px;
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.scroll {
		overflow-x: auto;
	}
	.person th,
	.person td {
		padding: 0.15rem 1rem 0.15rem 0;
		text-align: left;
	}
</style>
