<script lang="ts">
	import type { PlanBrief } from '$lib/types';
	import Icon from './Icon.svelte';

	interface Props {
		/** Planen, der vises. */
		plan: PlanBrief;
		/** Alle planer, nyeste først. */
		plans: PlanBrief[];
		onselect: (id: number) => void;
		/** Givet: ved den nyeste plan bliver "næste" til et plus, der laver en ny uge. */
		onnew?: () => void;
	}
	let { plan, plans, onselect, onnew }: Props = $props();

	const index = $derived(plans.findIndex((p) => p.id === plan.id));
</script>

<!-- Pilene skifter mellem planer (uger). Perioden står i sidens top, ikke her.
     En pil, der ikke kan bruges, bliver stående, så knapperne ikke flytter sig. -->
<div class="weeknav">
	<button
		type="button"
		class="rnd"
		aria-label="Forrige uge"
		disabled={index < 0 || index >= plans.length - 1}
		onclick={() => onselect(plans[index + 1].id)}
	>
		<Icon name="left" stroke={2.2} />
	</button>
	{#if index === 0 && onnew}
		<button type="button" class="rnd" aria-label="Ny uge" onclick={onnew}><Icon name="plus" stroke={2.2} /></button>
	{:else}
		<button type="button" class="rnd" aria-label="Næste uge" disabled={index <= 0} onclick={() => onselect(plans[index - 1].id)}>
			<Icon name="right" stroke={2.2} />
		</button>
	{/if}
</div>

<style>
	.weeknav {
		flex: none;
		display: flex;
		gap: 8px;
	}
</style>
