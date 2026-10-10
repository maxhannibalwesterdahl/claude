<script lang="ts">
	import BackButton from '$lib/BackButton.svelte';
	import Plate from './Plate.svelte';

	interface Props {
		/** Opskriftens billede. Uden billede vises en tallerken på en farvet flade. */
		src?: string | null;
		/** Opskriftens id eller titel: vælger tallerkenens farver. */
		seed?: string | number;
		/** Siden, Tilbage går til, hvis siden er åbnet direkte. Uden den vises ingen knap. */
		back?: string;
	}
	let { src = null, seed = '', back }: Props = $props();
</script>

<!-- Toppen af en opskrift og af "Lav mad": billede fra kant til kant. -->
<div class="hero" class:photo={!!src}>
	{#if src}
		<img {src} alt="" />
	{:else}
		<Plate {seed} size={132} />
	{/if}
	{#if back}<div class="back"><BackButton fallback={back} float /></div>{/if}
</div>

<style>
	/* Fladen går op bag telefonens statuslinje. */
	.hero {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		height: calc(180px + env(safe-area-inset-top));
		margin-top: calc(-1 * env(safe-area-inset-top));
		padding-top: env(safe-area-inset-top);
		overflow: hidden;
		background: linear-gradient(160deg, var(--hero-a), var(--hero-b));
	}
	.photo {
		height: calc(min(240px, 34vh) + env(safe-area-inset-top));
		padding-top: 0;
	}
	img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.back {
		position: absolute;
		top: calc(env(safe-area-inset-top) + 8px);
		left: max(12px, env(safe-area-inset-left));
	}
	@media (min-width: 900px) {
		.hero {
			margin-top: 16px;
			border-radius: var(--r-card);
		}
	}
</style>
