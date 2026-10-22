<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';

	/** Renders only the rows in view, so a million rows scroll like a hundred. Rows have a fixed height. */
	let {
		count,
		rowHeight = 30,
		row,
		height = '70vh'
	}: { count: number; rowHeight?: number; row: Snippet<[number]>; height?: string } = $props();

	let scrollTop = $state(0);
	let viewport = $state(600);
	const overscan = 10;

	const first = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - overscan));
	const last = $derived(Math.min(count, Math.ceil((scrollTop + viewport) / rowHeight) + overscan));
	const visible = $derived(Array.from({ length: Math.max(0, last - first) }, (_, k) => first + k));
</script>

<div
	class="viewport"
	style:height
	bind:clientHeight={viewport}
	onscroll={(e) => (scrollTop = (e.currentTarget as HTMLElement).scrollTop)}
>
	<div class="spacer" style:height={`${count * rowHeight}px`}>
		{#each visible as i (i)}
			<div class="row" style:top={`${i * rowHeight}px`} style:height={`${rowHeight}px`}>
				{@render row(i)}
			</div>
		{/each}
	</div>
</div>

<style>
	.viewport {
		overflow-y: auto;
		position: relative;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
	}
	.spacer {
		position: relative;
	}
	.row {
		position: absolute;
		left: 0;
		right: 0;
	}
</style>
