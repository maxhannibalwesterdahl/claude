<script lang="ts">
	import BackButton from '$lib/BackButton.svelte';
	import { goto } from '$app/navigation';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
</script>

<main class="legacy">
	<header class="top">
		<BackButton fallback="/opskrifter" />
		<h1>Ny opskrift</h1>
	</header>
	<RecipeEditor recipe={null} onsave={(r) => goto(`/opskrift/${r.id}`)} />
</main>
