<script lang="ts">
	import { weekday } from '$lib/dates';
	import { formatAmounts } from '$lib/format';
	import type { ShoppingItem } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';

	interface Props {
		item: ShoppingItem;
		/** Afdelingens navn, for egne varer med en vare valgt. */
		department: string;
		/** Planens vare: I har den hjemme. */
		onhome: () => void;
		/** Vælg eller skift varen. */
		onpick: () => void;
		/** Egen vare: fjern den fra listen. */
		onremove: () => void;
		onclose: () => void;
	}
	let { item, department, onhome, onpick, onremove, onclose }: Props = $props();

	// Knapperne lader først arket glide ud. Så udføres handlingen, og rækken
	// får fokus igen, før vare-vælgeren eventuelt åbner.
	let after: (() => void) | null = null;
	function then(close: () => void, fn: () => void) {
		after = fn;
		close();
	}
</script>

<!-- Alt det, der ikke er at krydse af: hvor varen kommer fra, og hvad der kan gøres ved den. -->
<Sheet
	title={item.name}
	eyebrow={formatAmounts(item.amounts, item.unquantified) || undefined}
	onclose={() => {
		// Handlingen først: den kender stadig rækken, og den lukker selv arket.
		after?.();
		onclose();
	}}
>
	{#if item.kind === 'extra'}
		<p class="pad line">
			{#if item.ingredient_name}Vare: <b>{item.ingredient_name}</b> · {department}
			{:else}Ingen vare valgt. Den står under Andet.{/if}
		</p>
	{:else if item.staple}
		<p class="pad line">Fast vare: {item.staple}. Rettes under <a href="/rydop/faste">Ryd op</a>.</p>
	{:else if item.unknown}
		<p class="pad line">Appen kender ikke varen. Den står under Andet.</p>
	{/if}
	{#if item.sources.length}
		<ul>
			{#each item.sources as src}
				<li class="pad small muted">{weekday(src.date)} · {src.meal}: {src.raw}</li>
			{/each}
		</ul>
	{/if}

	{#snippet footer(close)}
		<div class="btns">
			{#if item.kind === 'plan'}
				{#if item.unknown}<button type="button" class="btn" onclick={() => then(close, onpick)}>Vælg vare</button>{/if}
				<button type="button" class="btn" onclick={() => then(close, onhome)}><Icon name="home" />Har hjemme</button>
			{:else if item.kind === 'extra'}
				<button type="button" class="btn" onclick={() => then(close, onpick)}>{item.ingredient_name ? 'Skift vare' : 'Vælg vare'}</button>
				<button type="button" class="btn danger" onclick={() => then(close, onremove)}>Fjern fra listen</button>
			{/if}
		</div>
	{/snippet}
</Sheet>

<style>
	.line {
		padding-block: 4px 8px;
	}
	.line b {
		font-weight: 600;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0 0 4px;
	}
	li {
		padding-block: 3px;
	}
</style>
