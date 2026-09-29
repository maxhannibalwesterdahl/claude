<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import IngredientPicker from '$lib/IngredientPicker.svelte';
	import { refreshReviewCount } from '$lib/review.svelte';
	import type { IngredientRef, ReviewLine } from '$lib/types';

	interface Item {
		key: string;
		item: string;
		suggestion: IngredientRef | null;
		lines: ReviewLine[];
	}

	let lines = $state<ReviewLine[] | null>(null);
	let error = $state('');
	let picking = $state<string | null>(null);
	let busy = $state<string | null>(null);

	// Samme nøgle som backend (matcher.key): små bogstaver uden mellemrum og bindestreger.
	const keyOf = (item: string) => item.toLowerCase().replace(/[\s-]/g, '');

	const items = $derived.by(() => {
		const map = new Map<string, Item>();
		for (const l of lines ?? []) {
			const k = keyOf(l.item);
			const it = map.get(k) ?? { key: k, item: l.item, suggestion: null, lines: [] };
			it.lines.push(l);
			if (l.match_status === 'usikker' && l.ingredient) it.suggestion = l.ingredient;
			map.set(k, it);
		}
		// Varer i flest opskrifter først: de giver mest at rette.
		return [...map.values()].sort((a, b) => b.lines.length - a.lines.length || a.item.localeCompare(b.item, 'da'));
	});

	async function load() {
		try {
			lines = await refreshReviewCount();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke hente listen';
		}
	}

	$effect(() => {
		load();
	});

	async function resolve(it: Item, ing: IngredientRef | null) {
		busy = it.key;
		picking = null;
		error = '';
		try {
			if (ing) {
				// Serveren retter selv de andre linjer med samme varenavn.
				await api(`/lines/${it.lines[0].id}/confirm`, { method: 'POST', body: { ingredient_id: ing.id } });
			} else {
				for (const l of it.lines) await api(`/lines/${l.id}/ignore`, { method: 'POST' });
			}
			await load();
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke gemme';
		} finally {
			busy = null;
		}
	}
</script>

<main>
	<header class="top">
		<h1>Tjek varer</h1>
	</header>

	<p class="muted small">
		Ingredienser, hvor appen ikke er sikker på, hvilken vare der skal købes. Dit valg huskes og bruges i alle
		opskrifter.
	</p>

	{#if error}<p class="error">{error}</p>{/if}

	{#if lines && items.length === 0}
		<div class="empty">
			<p class="badge ok">Alt er tjekket</p>
			<p>Alle ingredienser er koblet til en vare.</p>
		</div>
	{/if}

	<ul>
		{#each items as it (it.key)}
			<li class="card" aria-busy={busy === it.key}>
				<div class="head">
					<strong>{it.item}</strong>
					<span class="muted small">{it.lines.length === 1 ? '1 opskrift' : `${it.lines.length} opskrifter`}</span>
				</div>
				<ul class="uses small muted">
					{#each it.lines as l}
						<li><a href="/opskrift/{l.recipe_id}">{l.recipe_title}</a>: {l.raw}</li>
					{/each}
				</ul>
				<div class="row">
					{#if it.suggestion}
						<button class="primary" disabled={busy !== null} onclick={() => resolve(it, it.suggestion)}>✓ {it.suggestion.name}</button>
					{/if}
					<button disabled={busy !== null} onclick={() => (picking = picking === it.key ? null : it.key)}>
						{it.suggestion ? 'Anden vare' : 'Vælg vare'}
					</button>
					<button disabled={busy !== null} onclick={() => resolve(it, null)}>Ingen vare</button>
				</div>
				{#if picking === it.key}
					<IngredientPicker initial={it.item} onpick={(ing) => resolve(it, ing)} oncancel={() => (picking = null)} />
				{/if}
			</li>
		{/each}
	</ul>
</main>

<style>
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 10px;
	}
	li.card {
		padding: 12px;
	}
	li[aria-busy='true'] {
		opacity: 0.5;
	}
	.head {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		align-items: baseline;
	}
	.uses {
		gap: 2px;
		margin: 6px 0 10px;
	}
	/* Større trykflade på links til opskrifterne */
	.uses li {
		padding: 4px 0;
		line-height: 1.5;
	}
	.uses a {
		display: inline-block;
		padding: 4px 0;
	}
</style>
