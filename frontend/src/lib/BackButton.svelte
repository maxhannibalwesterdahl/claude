<script lang="ts">
	import { navState } from './nav.svelte';
	import Icon from './ui/Icon.svelte';

	interface Props {
		/** Siden, der bruges, hvis siden er åbnet direkte (fx fra et bogmærke). */
		fallback: string;
		/** Knappen ligger oven på et billede. */
		float?: boolean;
	}
	let { fallback, float = false }: Props = $props();

	function back(e: MouseEvent) {
		if (navState.inApp) {
			e.preventDefault();
			history.back();
		}
	}
</script>

<a class="rnd" class:float href={fallback} onclick={back} aria-label="Tilbage"><Icon name="left" stroke={2.2} /></a>
