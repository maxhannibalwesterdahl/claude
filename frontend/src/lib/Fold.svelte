<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		/** Antallet i afsnittet, vist på linjen, også når afsnittet er lukket. */
		count: number | string;
		children: Snippet;
	}
	let { title, count, children }: Props = $props();
</script>

<!-- Et afsnit, der er lukket, til man trykker på det. -->
<details>
	<summary>
		<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
		<span class="grow">{title}</span>
		<span class="count" aria-live="polite">{count}</span>
	</summary>
	<div class="content">{@render children()}</div>
</details>

<style>
	details {
		margin-top: 8px;
		border-radius: var(--radius-seg);
		background: var(--card);
		border: 1px solid var(--line);
	}
	summary {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 48px;
		padding: 4px 12px;
		font-weight: 600;
		cursor: pointer;
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	svg {
		width: 18px;
		height: 18px;
		flex: none;
		fill: none;
		stroke: var(--muted);
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
		transition: transform 0.15s;
	}
	details[open] svg {
		transform: rotate(90deg);
	}
	.count {
		font-size: 0.85rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.content {
		padding: 0 8px 8px;
	}
</style>
