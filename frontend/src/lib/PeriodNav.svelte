<script lang="ts">
	import { periodLabel } from './dates';
	import type { PlanBrief } from './types';

	interface Props {
		/** Planen, der vises. */
		plan: PlanBrief;
		/** Alle planer, nyeste først. Pilene vises kun, når der er flere end én. */
		plans: PlanBrief[];
		onselect: (id: number) => void;
	}
	let { plan, plans, onselect }: Props = $props();

	const index = $derived(plans.findIndex((p) => p.id === plan.id));
</script>

<!-- Perioden under sidens titel. Pilene skifter mellem planer (uger), så det ikke forveksles med dagene. -->
<div class="period sub">
	{#if plans.length > 1}
		<button class="plain" aria-label="Forrige plan" disabled={index < 0 || index >= plans.length - 1} onclick={() => onselect(plans[index + 1].id)}>‹</button>
	{/if}
	<span>{periodLabel(plan.start_date, plan.end_date)}</span>
	{#if plans.length > 1}
		<button class="plain" aria-label="Næste plan" disabled={index <= 0} onclick={() => onselect(plans[index - 1].id)}>›</button>
	{/if}
</div>

<style>
	.period {
		display: flex;
		align-items: center;
	}
	/* Trykfladen er 44px, men må ikke gøre toppen højere: den rækker ud over linjen. */
	.period button {
		padding: 0;
		margin: -8px 0;
		font-size: 1.1rem;
		color: var(--accent);
	}
	.period button:first-child {
		margin-left: -18px;
	}
	.period button:disabled {
		visibility: hidden;
	}
</style>
