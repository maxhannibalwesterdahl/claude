<script lang="ts">
	import { catalog } from '$lib/catalog.svelte';
	import IngredientList from '$lib/rydop/IngredientList.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';

	let list: IngredientList | undefined = $state();
	const count = $derived(catalog.ingredients.length);
</script>

<main>
	<ScreenHeader title="Alle varer" eyebrow={count ? `Ryd op · ${count} varer` : 'Ryd op'} back="/rydop">
		{#snippet actions()}
			<button type="button" class="btn sm primary" onclick={() => list?.openNew()}>Ny vare</button>
		{/snippet}
	</ScreenHeader>
	<IngredientList bind:this={list} mode="alle" />
</main>
