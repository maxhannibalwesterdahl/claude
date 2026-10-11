<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import type { Recipe } from '$lib/types';

	let recipe = $state<Recipe | null>(null);
	let error = $state('');

	$effect(() => {
		api<Recipe>(`/recipes/${page.params.id}`)
			.then((r) => (recipe = r))
			.catch((e) => (error = say(e)));
	});
</script>

<main>
	<!-- Tilbage er et almindeligt link til opskriften (ikke "gå tilbage"), så der
	     spørges først, hvis der er ændringer, der ikke er gemt. -->
	<ScreenHeader title="Rediger" eyebrow={recipe?.title ?? 'Opskrift'} back="/opskrift/{page.params.id}" backPlain />
	{#if error}<p class="msg" role="alert">{error}</p>{/if}
	{#if recipe}
		{#key recipe.id}
			<RecipeEditor {recipe} onsave={(r) => goto(`/opskrift/${r.id}`)} />
		{/key}
	{/if}
</main>

