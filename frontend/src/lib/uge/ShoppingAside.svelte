<script lang="ts">
	import { untrack } from 'svelte';
	import { formatAmounts } from '$lib/format';
	import { clock } from '$lib/resume.svelte';
	import type { ShoppingData, ShoppingItem } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import IngredientRow from '$lib/ui/IngredientRow.svelte';
	import { weekApi } from './api';

	interface Props {
		/** Ugen, listen hører til. */
		planId: number;
		/** Tæller op ved hver ændring i ugen: listen hentes igen lidt efter. */
		rev: number;
	}
	let { planId, rev }: Props = $props();

	// Listen hentes direkte, kun til visning. Den rører ikke indkøbslisten, der
	// ligger gemt på telefonen (den hører til Indkøb-fanen).
	let data = $state<ShoppingData | null>(null);
	let error = $state('');

	$effect(() => {
		const id = planId;
		const today = clock.today;
		void rev;
		let stale = false;
		// Første gang og ved ny uge: straks. Efter en ændring: når der har været ro et øjeblik.
		const wait = untrack(() => data?.plan?.id) === id ? 400 : 0;
		const timer = setTimeout(async () => {
			try {
				const d = await weekApi.shopping(id, today);
				if (stale) return;
				data = d;
				error = '';
			} catch (e) {
				if (!stale) error = say(e);
			}
		}, wait);
		return () => {
			stale = true;
			clearTimeout(timer);
		};
	});

	const groups = $derived.by(() => {
		if (!data) return [];
		const known = new Set(data.departments.map((d) => d.code));
		const rest = data.items.filter((i) => !known.has(i.department));
		const out: { name: string; items: ShoppingItem[] }[] = data.departments.map((d) => ({
			name: d.name,
			items: data!.items.filter((i) => i.department === d.code)
		}));
		if (rest.length) out.push({ name: 'Andet', items: rest });
		return out.filter((g) => g.items.length);
	});
	const count = $derived(data?.items.length ?? 0);
</script>

<aside aria-label="Indkøb for ugen">
	<header class="pad">
		<div class="grow">
			<p class="ey">Følger planen</p>
			<h2 class="serif">Indkøb</h2>
		</div>
		{#if data}<p class="cnt"><b>{count}</b> {count === 1 ? 'vare' : 'varer'}</p>{/if}
	</header>
	{#if error}<p class="msg" role="alert">{error}</p>{/if}
	{#each groups as g (g.name)}
		<p class="dep">{g.name}</p>
		{#each g.items as i (i.key)}
			<IngredientRow qty={formatAmounts(i.amounts, i.unquantified)} name={i.name} dim={i.checked} />
		{/each}
	{:else}
		{#if data}<p class="empty">Der er ingen varer endnu.</p>{/if}
	{/each}
</aside>

<style>
	aside {
		background: var(--card);
		border-left: 1px solid var(--line);
		padding-bottom: 24px;
	}
	header {
		display: flex;
		align-items: flex-end;
		gap: 12px;
		min-height: 68px;
		padding-top: 8px;
		padding-bottom: 10px;
	}
	h2 {
		font-size: var(--fs-sheet-title);
		line-height: 30px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	.cnt {
		font-size: var(--fs-cap);
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.cnt b {
		font-size: var(--fs-dish);
		color: var(--ink);
	}
</style>
