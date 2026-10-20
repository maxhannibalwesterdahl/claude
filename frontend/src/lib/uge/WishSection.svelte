<script lang="ts">
	import type { Plan } from '$lib/types';
	import { draggable } from '$lib/ui/drag.svelte';
	import { wishName } from '$lib/ui/glide.svelte';

	interface Props {
		plan: Plan;
		/** Dage uden ret, der ikke er gået. Uden dem kan ønskerne ikke fordeles. */
		freeDays: number;
		ondistribute: () => void;
		/** Åbner ønskelisten (tilføj, fjern, vælg dage). */
		onshow: () => void;
	}
	let { plan, freeDays, ondistribute, onshow }: Props = $props();

	const n = $derived(plan.wishlist.length);
</script>

<!-- Ønskelisten står altid under ugen og ser ens ud, med og uden ønsker. Hvert
     ønske kan trækkes hen på en dag (hold fingeren på det). Tryk åbner listen. -->
<section aria-label="Ønskeliste">
	<p class="sl">
		<span class="h">Ønskeliste{#if n}<span class="count">&nbsp;·&nbsp;{n}</span>{/if}</span>
		<button type="button" class="link add" onclick={onshow}>Tilføj</button>
	</p>
	{#if n}
		<div class="chips pad">
			{#each plan.wishlist as w (w.id)}
				<button type="button" class="chip" style:view-transition-name={wishName(w.id)} use:draggable={`wish:${w.id}`} onclick={onshow}><span class="ellipsis">{w.title}</span></button>
			{/each}
		</div>
		<p class="pad small muted hint">
			Hold på et ønske, og træk det til en dag.
			{#if freeDays > 0}<button type="button" class="link" onclick={ondistribute}>Fordel på ledige dage</button>{/if}
		</p>
	{/if}
</section>

<style>
	/* Overskriften er den samme som de andre afsnit; tallet er ikke råbt. */
	.h {
		font-weight: 700;
		letter-spacing: 0.07em;
		text-transform: uppercase;
	}
	.count {
		letter-spacing: 0;
	}
	/* Linket i overskriften skal kunne rammes med en finger. */
	.add {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
		font-size: 14.5px;
	}
	.sl {
		align-items: center;
		padding-bottom: 0;
	}
	.chips {
		padding-block: 2px 4px;
	}
	.hint {
		margin-top: 4px;
	}
	.hint .link {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
		margin-left: 4px;
	}
</style>
