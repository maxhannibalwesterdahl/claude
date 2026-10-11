<script lang="ts">
	import IngredientPicker from '$lib/IngredientPicker.svelte';
	import type { IngredientRef } from '$lib/types';
	import Sheet from '$lib/ui/Sheet.svelte';

	interface Props {
		/** Teksten, der skal have en vare ("fiskesovs"). Står under titlen. */
		text: string;
		/** Første søgning i vælgeren. */
		initial: string;
		/** Appens bud. Vises øverst. */
		suggestion?: IngredientRef | null;
		/** En sætning i stedet for vælgeren: der hentes, eller der er intet at vælge. */
		instead?: string;
		/** En vare er valgt. null = "Ingen vare". Arket lukkes af den, der bruger det. */
		onpick: (ing: IngredientRef | null) => void;
		/** Lukket uden at vælge. */
		onclose: () => void;
	}
	let { text, initial, suggestion = null, instead = '', onpick, onclose }: Props = $props();
</script>

<!-- Vare-vælgeren i et ark. Varen bestemmer afdelingen, så rækken kommer til at
     stå det rigtige sted i butikken. -->
<Sheet title="Hvilken vare er det?" eyebrow={text} size="tall" initialFocus="first" {onclose}>
	{#snippet children(close)}
		{#if instead}
			<p class="note" role="status">{instead}</p>
		{:else}
			<IngredientPicker {initial} {suggestion} defaultDepartment="andet" {onpick} oncancel={close} />
		{/if}
	{/snippet}
</Sheet>
