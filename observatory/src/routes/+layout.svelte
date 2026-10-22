<script lang="ts">
	import { onMount } from 'svelte';

	import { openRun, readTable } from '$lib/run/run';
	import { HttpSource } from '$lib/run/source';
	import '$lib/theme.css';

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
