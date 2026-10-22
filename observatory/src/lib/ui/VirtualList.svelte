<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';

	/**
	 * Renders only the rows in view, so a million rows scroll like a hundred. Rows have a fixed
	 * height. Browsers cap an element's height (Chrome at ~33M px), so very long lists use a
	 * capped spacer and map scroll position to rows proportionally.
	 */
	let {
		count,
		rowHeight = 30,
		row,
		height = '70vh',
		resetKey = ''
	}: { count: number; rowHeight?: number; row: Snippet<[number]>; height?: string; resetKey?: string } = $props();

	const MAX_PX = 10_000_000;
	let el = $state<HTMLElement | null>(null);
	let scrollTop = $state(0);
	let viewport = $state(600);
	const overscan = 10;

	const total = $derived(Math.min(count * rowHeight, MAX_PX));
	// the first row index in view: exact when the list fits, proportional when it is capped
	const top = $derived(
		count * rowHeight <= MAX_PX
			? scrollTop / rowHeight
			: (scrollTop / Math.max(1, total - viewport)) * Math.max(0, count - viewport / rowHeight)
	);
	const first = $derived(Math.max(0, Math.floor(top) - overscan));
	const last = $derived(Math.min(count, Math.ceil(top + viewport / rowHeight) + overscan));
	const visible = $derived(Array.from({ length: Math.max(0, last - first) }, (_, k) => first + k));

	// a new filter starts at the top
	$effect(() => {
		void resetKey;
		if (el) el.scrollTop = 0;
		scrollTop = 0;
	});
</script>

<div
	class="viewport"
	style:height
	bind:this={el}
	bind:clientHeight={viewport}
	onscroll={(e) => (scrollTop = (e.currentTarget as HTMLElement).scrollTop)}
>
	<div class="spacer" style:height={`${total}px`}>
		{#each visible as i (i)}
			<div class="row" style:top={`${scrollTop + (i - top) * rowHeight}px`} style:height={`${rowHeight}px`}>
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
