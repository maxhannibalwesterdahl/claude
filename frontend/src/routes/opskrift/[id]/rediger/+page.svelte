<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
	import type { Recipe } from '$lib/types';

	let recipe = $state<Recipe | null>(null);
	let error = $state('');

	$effect(() => {
		api<Recipe>(`/recipes/${page.params.id}`)
			.then((r) => (recipe = r))
			.catch((e) => (error = e instanceof ApiError ? e.message : 'Kunne ikke hente opskriften'));
	});
</script>

<main>
	<header class="top">
		<a class="button" href="/opskrift/{page.params.id}" aria-label="Tilbage">‹</a>
		<h1>Rediger</h1>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if recipe}
		{#key recipe.id}
			<RecipeEditor {recipe} onsave={(r) => goto(`/opskrift/${r.id}`)} />
		{/key}
	{/if}
</main>
