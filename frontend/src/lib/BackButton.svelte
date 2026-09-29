<script lang="ts">
	import { navState } from './nav.svelte';

	/** Siden, der bruges, hvis siden er åbnet direkte (fx fra et bogmærke). */
	let { fallback }: { fallback: string } = $props();

	function back(e: MouseEvent) {
		if (navState.inApp) {
			e.preventDefault();
			history.back();
		}
	}
</script>

<a class="button" href={fallback} onclick={back} aria-label="Tilbage">‹</a>
