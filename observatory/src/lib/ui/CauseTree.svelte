<script lang="ts">
	import { untrack } from 'svelte';

	import { nodeKey, type CauseGraph, type CauseNode } from '$lib/run/causes';

	import Self from './CauseTree.svelte';

	/**
	 * A node and, expanded, its parents ("why") or children ("what it led to"). Expansion is lazy;
	 * `depth` sets how far it opens by itself. Ripples are the author's hand and pins are canon:
	 * they end a "why" walk. `budget` is shared by the whole tree: once that many nodes have opened by
	 * themselves the rest wait for a click, so a wide or deep run can't freeze the page.
	 */
	let {
		graph,
		node,
		direction,
		depth,
		path = [],
		budget = { left: 400 },
		onSelect
	}: {
		graph: CauseGraph;
		node: CauseNode;
		direction: 'why' | 'led';
		depth: number;
		path?: string[];
		budget?: { left: number };
		onSelect: (eventId: string) => void;
	} = $props();

	const key = $derived(nodeKey(node));
	const next = $derived(direction === 'why' ? graph.parents(node) : graph.children(node));
	const looped = $derived(path.includes(key));
	const LIMIT = 40;
	// Decided once, when the node mounts: does it open by itself?
	const auto = untrack(() => {
		if (depth <= 0 || budget.left <= 0) return false;
		budget.left -= Math.min(next.length, LIMIT);
		return true;
	});
	let open = $state<boolean | null>(null);
	const isOpen = $derived(open ?? auto);
	let showAll = $state(false);
	const shown = $derived(showAll ? next : next.slice(0, LIMIT));
</script>

<li class={`node ${node.kind}`}>
	<span class="line">
		{#if next.length && !looped}
			<button class="toggle" onclick={() => (open = !isOpen)} aria-label={isOpen ? 'Collapse' : 'Expand'}>{isOpen ? '▾' : '▸'}</button>
		{:else}
			<span class="toggle"></span>
		{/if}
		<span class="kind">{node.kind}</span>
		{#if node.kind === 'event'}
			<button class="label link" onclick={() => onSelect(node.ref)}>{graph.label(node)}</button>
		{:else}
			<span class="label">{graph.label(node)}</span>
		{/if}
		{#if next.length && !isOpen}<span class="muted">· {next.length}</span>{/if}
		{#if looped}<span class="muted">(already above)</span>{/if}
	</span>
	{#if isOpen && next.length && !looped}
		<ul>
			{#each shown as child (nodeKey(child))}
				<Self {graph} node={child} {direction} depth={depth - 1} path={[...path, key]} {budget} {onSelect} />
			{/each}
			{#if next.length > LIMIT && !showAll}
				<li><button class="link" onclick={() => (showAll = true)}>show all {next.length}</button></li>
			{/if}
		</ul>
	{/if}
</li>

<style>
	ul {
		list-style: none;
		margin: 0;
		padding-left: 1.1rem;
		border-left: 1px solid var(--border);
	}
	.node {
		padding: 0.08rem 0;
	}
	.line {
		display: flex;
		gap: 0.45rem;
		align-items: baseline;
		white-space: nowrap;
	}
	.toggle {
		width: 1rem;
		border: none;
		background: none;
		padding: 0;
		color: var(--muted);
		cursor: pointer;
	}
	.kind {
		font-size: 0.75rem;
		color: var(--muted);
		min-width: 4.8rem;
	}
	.ripple > .line .kind,
	.ripple > .line .label {
		color: var(--ripple);
		font-weight: 600;
	}
	.pin > .line .kind,
	.pin > .line .label {
		color: var(--pin);
		font-weight: 600;
	}
	.link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
		font: inherit;
	}
	.muted {
		color: var(--muted);
		font-size: 0.85rem;
	}
</style>
