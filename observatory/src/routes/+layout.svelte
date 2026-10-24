<script lang="ts">
	import { onMount } from 'svelte';

	import { page } from '$app/state';

	import { openRun, readTable } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';
	import '$lib/theme.css';
	import RipplePanel from '$lib/ui/RipplePanel.svelte';

	let { children } = $props();

	// A read-only hook for scripted checks (the smoke test reads rows through the app's own code).
	onMount(() => {
		(window as unknown as Record<string, unknown>).__observatory = { HttpSource, openRun, readTable };
	});
</script>

<header>
	<a class="brand" href="/">Observatory</a>
	<span class="sub">Renascitur History Engine</span>
</header>

<main>
	{@render children()}
	{#if page.params.name && page.route.id?.startsWith('/run/')}
		<!-- (on every run page: author a ripple on this run, with this page's entity as its target, #110) -->
		<RipplePanel run={page.params.name} target={page.route.id === '/run/[name]/entity/[id]' ? (page.params.id ?? '') : ''} />
	{/if}
</main>

<style>
	header {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.9rem 1.5rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}
	.brand {
		font-family: var(--serif);
		font-size: 1.3rem;
		font-weight: 600;
		color: var(--text);
		text-decoration: none;
	}
	.sub {
		color: var(--muted);
		font-size: 0.85rem;
	}
	main {
		max-width: 1100px;
		margin: 0 auto;
		padding: 1.5rem;
	}
</style>
