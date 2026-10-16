<script lang="ts">
	import { weekday } from '$lib/dates';
	import { formatAmounts } from '$lib/format';
	import type { ShoppingItem } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import { longpress } from '$lib/ui/longpress';
	import Tick from '$lib/ui/Tick.svelte';

	interface Props {
		item: ShoppingItem;
		/** Købt, med ventende kryds lagt oveni serverens udgave. */
		checked: boolean;
		ontoggle: () => void;
		/** Åbner arket med resten: knappen til sidst og et langt tryk. */
		onmore: () => void;
		/** Appen kender ikke varen: åbner vare-vælgeren. */
		onpick: () => void;
	}
	let { item, checked, ontoggle, onmore, onpick }: Props = $props();

	const amount = $derived(formatAmounts(item.amounts, item.unquantified));
	const caption = $derived(
		[
			item.days.map(weekday).join(', '),
			item.source === 'egen' ? 'egen vare' : '',
			item.source === 'løbet tør' ? 'løbet tør' : '',
			item.unknown ? 'appen kender ikke varen' : ''
		]
			.filter(Boolean)
			.join(' · ')
	);
</script>

<!-- Rækken er tre knapper ved siden af hinanden, ikke knapper inden i en knap:
     den store krydser af, de små til sidst vælger vare og åbner arket.
     Langt tryk er kun en genvej til det samme ark som knappen "Mere". -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="row"
	class:done={checked}
	use:longpress={onmore}
>
	<button type="button" class="toggle" aria-pressed={checked} onclick={ontoggle}>
		<Tick {checked} size="lg" />
		<span class="grow">
			<span class="what">{#if amount}<b>{amount}</b>{' '}{/if}{item.name}</span>
			{#if caption}<span class="cap">{caption}</span>{/if}
		</span>
	</button>
	{#if item.unknown}
		<button type="button" class="btn sm quiet" aria-label="Vælg vare til {item.name}" onclick={onpick}>Vælg vare</button>
	{/if}
	<button type="button" class="more" aria-label="Mere om {item.name}" onclick={onmore}><Icon name="more" size={22} stroke={2.6} /></button>
</div>

<style>
	.row {
		display: flex;
		align-items: center;
		min-height: var(--shop-h);
		padding-right: max(4px, env(safe-area-inset-right));
		border-bottom: 1px solid var(--line);
	}
	/* Store felter til én hånd i butikken: hele rækken frem til de små knapper. */
	.toggle {
		flex: 1;
		min-width: 0;
		align-self: stretch;
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 8px 4px 8px max(var(--gutter), env(safe-area-inset-left));
		/* Rækken ligger i en ramme, der skærer af: fokusringen tegnes indenfor. */
		outline-offset: -2px;
	}
	.what {
		display: block;
		font-size: 18px;
		line-height: 1.25;
		text-decoration: line-through;
		text-decoration-color: transparent;
		transition:
			color var(--t-tick),
			text-decoration-color var(--t-tick);
	}
	.what b {
		font-weight: 700;
	}
	.cap {
		display: block;
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	/* Købt: flueben, streg over og dæmpet tekst. Aldrig farven alene. */
	.done .what {
		color: var(--muted);
		text-decoration-color: currentColor;
	}
	.more {
		flex: none;
		align-self: stretch;
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--tap);
		min-height: var(--tap);
		color: var(--faint);
		outline-offset: -2px;
	}
</style>
