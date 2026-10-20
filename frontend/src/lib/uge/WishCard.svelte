<script lang="ts">
	import type { Plan } from '$lib/types';
	import { draggable } from '$lib/ui/drag.svelte';

	interface Props {
		plan: Plan;
		/** Dage uden ret, der ikke er gået. Uden dem kan ønskerne ikke fordeles. */
		freeDays: number;
		ondistribute: () => void;
		onshow: () => void;
	}
	let { plan, freeDays, ondistribute, onshow }: Props = $props();

	const n = $derived(plan.wishlist.length);
	const planned = $derived(plan.days.filter((d) => d.meal).length);
</script>

<!-- Ønsker, der venter: ét tryk fordeler dem på de ledige dage. Hvert ønske kan
     også trækkes hen på en dag (hold fingeren på det), eller lægges på en dag fra
     ønskelisten. -->
<section class="card wishes" aria-label="Ønskeliste">
	<p class="lab">{planned} af {plan.days.length} dage planlagt</p>
	<p class="serif head">{n === 1 ? '1 ønske venter på en dag' : `${n} ønsker venter på en dag`}</p>
	<div class="chips">
		{#each plan.wishlist as w (w.id)}
			<button type="button" class="chip" use:draggable={`wish:${w.id}`} onclick={onshow}><span class="ellipsis">{w.title}</span></button>
		{/each}
	</div>
	<p class="small muted hint">Hold fingeren på et ønske, og træk det hen på en dag.</p>
	<div class="btns">
		{#if freeDays > 0}
			<button type="button" class="btn primary" onclick={ondistribute}>Fordel ønsker</button>
		{/if}
		<button type="button" class="btn" onclick={onshow}>Vælg dage</button>
	</div>
</section>

<style>
	.wishes {
		margin: 12px var(--gutter) 6px;
		padding: 16px;
	}
	.head {
		margin-block: 6px 2px;
		font-size: 21px;
		line-height: 26px;
		font-weight: 700;
	}
	.chips {
		margin-top: 10px;
	}
	.hint {
		margin-top: 8px;
	}
	.btns {
		margin-top: 14px;
	}
</style>
