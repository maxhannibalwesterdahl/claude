<script lang="ts">
	import { goto } from '$app/navigation';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
</script>

<main>
	<header class="top">
		<a class="button" href="/" aria-label="Tilbage">‹</a>
		<h1>Ny opskrift</h1>
	</header>
	<RecipeEditor recipe={null} onsave={(r) => goto(`/opskrift/${r.id}`)} />
</main>
