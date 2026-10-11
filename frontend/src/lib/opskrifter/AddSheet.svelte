<script lang="ts">
	import Icon from '$lib/ui/Icon.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';

	let { onclose }: { onclose: () => void } = $props();
</script>

<!-- De to måder at få en opskrift ind på. -->
<Sheet title="Ny opskrift" {onclose}>
	<a class="kv" href="/importer">
		<span class="k">Importér fra link<small>Valdemarsro, nemlig og de fleste andre sider</small></span>
		<Icon name="chev" />
	</a>
	<a class="kv" href="/ny">
		<span class="k">Skriv selv<small>Titel, ingredienser og fremgangsmåde</small></span>
		<Icon name="chev" />
	</a>
</Sheet>

<style>
	a :global(svg) {
		color: var(--muted);
	}
</style>
