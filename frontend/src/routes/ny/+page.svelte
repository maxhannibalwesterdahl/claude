<script lang="ts">
	import { goto } from '$app/navigation';
	import RecipeEditor from '$lib/RecipeEditor.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
</script>

<main>
	<ScreenHeader title="Ny opskrift" eyebrow="Opskrifter" back="/opskrifter" />
	<RecipeEditor recipe={null} onsave={(r) => goto(`/opskrift/${r.id}`)} />
</main>
