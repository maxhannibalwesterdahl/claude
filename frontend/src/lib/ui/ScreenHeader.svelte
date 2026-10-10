<script lang="ts">
	import type { Snippet } from 'svelte';
	import BackButton from '$lib/BackButton.svelte';

	interface Props {
		title: string;
		/** Lille dæmpet linje ved titlen (periode, antal). */
		eyebrow?: string;
		/** false: linjen står under titlen. */
		eyebrowAbove?: boolean;
		/** Viser Tilbage til venstre. Siden, der bruges, hvis siden er åbnet direkte. */
		back?: string;
		/** Øverst til højre (uge frem og tilbage, chip, tæller). */
		actions?: Snippet;
	}
	let { title, eyebrow, eyebrowAbove = true, back, actions }: Props = $props();
</script>

<!-- Sidens top. Lange titler brydes over flere linjer i stedet for at blive skåret af. -->
<header class="hd pad">
	{#if back}<BackButton fallback={back} />{/if}
	<div class="grow">
		{#if eyebrow && eyebrowAbove}<p class="ey">{eyebrow}</p>{/if}
		<h1 class="serif">{title}</h1>
		{#if eyebrow && !eyebrowAbove}<p class="ey">{eyebrow}</p>{/if}
	</div>
	{#if actions}<div class="actions">{@render actions()}</div>{/if}
</header>

<style>
	.hd {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		min-height: 68px;
		padding-top: 8px;
		padding-bottom: 6px;
	}
	h1 {
		font-size: var(--fs-title);
		line-height: 36px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	/* Knapperne står ud for titlens linje, også når der er en linje over den. */
	.actions,
	.hd > :global(.rnd) {
		margin-top: 12px;
	}
	.actions {
		flex: none;
		display: flex;
		align-items: center;
		gap: 8px;
	}
</style>
