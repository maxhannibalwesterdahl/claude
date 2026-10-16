<script lang="ts">
	import Plate from '$lib/ui/Plate.svelte';
	import type { RecipeSummary } from '$lib/types';

	interface Props {
		recipe: RecipeSummary;
		/** Den lille linje nederst (ønskeliste, sidst på planen, hovedingredienser). */
		meta: string;
	}
	let { recipe, meta }: Props = $props();
	// Tiden først, så den ses også på de lange linjer.
	const line = $derived([recipe.total_minutes ? `${recipe.total_minutes} min` : '', meta].filter(Boolean).join(' · '));
</script>

<!-- Én opskrift i samlingen. Hele flisen er linket. -->
<a class="rc" href="/opskrift/{recipe.id}">
	<Plate src={recipe.image_url} seed={recipe.id} size={60} lazy />
	<span class="n">{recipe.title}</span>
	{#if recipe.to_review}<span class="tag">{recipe.to_review} at tjekke</span>{/if}
	{#if line}<span class="m">{line}</span>{/if}
</a>

<style>
	/* Lange navne: højst tre linjer, så fliserne i en række følges ad. */
	.n,
	.m {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		overflow: hidden;
	}
	.m {
		-webkit-line-clamp: 2;
		line-clamp: 2;
	}
	.tag {
		align-self: flex-start;
	}
</style>
