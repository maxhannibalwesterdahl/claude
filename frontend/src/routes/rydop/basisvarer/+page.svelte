<script lang="ts">
	import { catalog } from '$lib/catalog.svelte';
	import IngredientList from '$lib/rydop/IngredientList.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';

	let list: IngredientList | undefined = $state();
	const count = $derived(catalog.ingredients.filter((i) => i.pantry).length);
</script>

<main>
	<ScreenHeader title="Basisvarer" eyebrow={count ? `Ryd op · ${count === 1 ? '1 basisvare' : `${count} basisvarer`}` : 'Ryd op'} back="/rydop">
		{#snippet actions()}
			<button type="button" class="btn sm primary" onclick={() => list?.openNew()}>Ny vare</button>
		{/snippet}
	</ScreenHeader>
	<IngredientList bind:this={list} mode="basis" />
</main>
