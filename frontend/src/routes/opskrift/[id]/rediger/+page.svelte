<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
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
	     spørges først, hvis der er ændringer, der ikke er gemt. Derfor sidens egen top. -->
	<header class="hd pad">
		<a class="rnd" href="/opskrift/{page.params.id}" aria-label="Tilbage"><Icon name="left" stroke={2.2} /></a>
		<div class="grow">
			<p class="ey">{recipe?.title ?? 'Opskrift'}</p>
			<h1 class="serif">Rediger</h1>
		</div>
	</header>
	{#if error}<p class="msg" role="alert">{error}</p>{/if}
	{#if recipe}
		{#key recipe.id}
			<RecipeEditor {recipe} onsave={(r) => goto(`/opskrift/${r.id}`)} />
		{/key}
	{/if}
</main>

<style>
	/* Samme mål som ScreenHeader. */
	.hd {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		min-height: 68px;
		padding-top: 8px;
		padding-bottom: 6px;
	}
	.hd .rnd {
		margin-top: 12px;
	}
	h1 {
		font-size: var(--fs-title);
		line-height: 36px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
</style>
