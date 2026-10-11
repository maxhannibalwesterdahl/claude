<script lang="ts">
	import type { Snippet } from 'svelte';
	import Sheet from '$lib/ui/Sheet.svelte';

	interface Props {
		/** Antal linjer, der er fundet frem, og antal i alt. */
		found: number;
		total: number;
		/** Retten er ganget op eller ned: trinenes tekst passer ikke med mængderne. */
		scaled: boolean;
		onclose: () => void;
		/** Listen fra oversigten, med de samme lokale kryds. */
		children: Snippet;
	}
	let { found, total, scaled, onclose, children }: Props = $props();
</script>

<!-- Ingredienserne, mens man står midt i et trin. -->
<Sheet title="Ingredienser" eyebrow="{found} af {total} fundet frem" {onclose}>
	{#if scaled}<p class="pad muted small">Teksten er fra opskriften. Brug mængderne her.</p>{/if}
	{@render children()}
</Sheet>
