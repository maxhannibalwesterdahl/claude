<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		src?: string | null;
		/** sm 48px (lister i ark), md 64px (kort), lg 96px (redigering). */
		size?: 'sm' | 'md' | 'lg';
		lazy?: boolean;
		referrerpolicy?: ReferrerPolicy;
		/** Indhold i pladsholderen, når der ikke er et billede (fx et ikon). */
		children?: Snippet;
	}
	let { src = null, size = 'md', lazy = false, referrerpolicy, children }: Props = $props();
</script>

<!-- Rettens billede. Uden billede vises en farvet pladsholder i samme størrelse. -->
{#if src}
	<img class="thumb {size}" {src} alt="" loading={lazy ? 'lazy' : undefined} {referrerpolicy} />
{:else}
	<span class="thumb noimg {size}" aria-hidden="true">{@render children?.()}</span>
{/if}

<style>
	.thumb {
		flex: none;
		width: 64px;
		height: 64px;
		border-radius: var(--radius-thumb);
		object-fit: cover;
		background: var(--accent-soft);
	}
	.sm {
		width: 48px;
		height: 48px;
	}
	.lg {
		width: 96px;
		height: 96px;
	}
	.noimg {
		display: grid;
		place-items: center;
		color: var(--accent);
	}
	.noimg :global(svg) {
		width: 40%;
		height: 40%;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
