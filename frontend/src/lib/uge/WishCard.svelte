<script lang="ts">
	import type { Plan } from '$lib/types';

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

<!-- Ønsker, der venter: ét tryk fordeler dem på de ledige dage. -->
<section class="card wishes" aria-label="Ønskeliste">
	<p class="lab">{planned} af {plan.days.length} dage planlagt</p>
	<p class="serif head">{n === 1 ? '1 ønske venter på en dag' : `${n} ønsker venter på en dag`}</p>
	<p class="small muted ellipsis">{plan.wishlist.map((w) => w.title).join(', ')}</p>
	<div class="btns">
		{#if freeDays > 0}
			<button type="button" class="btn primary" onclick={ondistribute}>Fordel ønsker</button>
		{/if}
		<button type="button" class="btn" onclick={onshow}>Se ønsker</button>
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
	.btns {
		margin-top: 14px;
	}
</style>
