<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './ui/Icon.svelte';

	interface Props {
		title: string;
		/** Antallet i afsnittet, vist på linjen, også når afsnittet er lukket. */
		count: number | string;
		children: Snippet;
	}
	let { title, count, children }: Props = $props();
</script>

<!-- Et afsnit, der er lukket, til man trykker på det. Indholdet har ingen luft
     omkring sig: rækkerne i det bærer deres egen. -->
<details>
	<summary class="kv">
		<Icon name="chev" />
		<span class="k grow">{title}</span>
		<span class="tag" aria-live="polite">{count}</span>
	</summary>
	{@render children()}
</details>

<style>
	summary {
		cursor: pointer;
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary :global(svg) {
		color: var(--muted);
		transition: transform 0.15s;
	}
	details[open] > summary :global(svg) {
		transform: rotate(90deg);
	}
	.tag {
		font-variant-numeric: tabular-nums;
	}
</style>
