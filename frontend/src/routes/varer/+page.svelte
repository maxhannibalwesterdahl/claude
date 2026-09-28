<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { catalog } from '$lib/catalog.svelte';
	import { formatNumber, parseNumber } from '$lib/format';
	import type { Ingredient } from '$lib/types';

	let q = $state('');
	let error = $state('');
	let editing = $state<number | 'ny' | null>(null);
	let form = $state({ name: '', department: 'fg', pantry: false, perPiece: '', perDl: '' });
	let loaded = $state(false);

	$effect(() => {
		catalog
			.load(true)
			.then(() => (loaded = true))
			.catch((e) => (error = e instanceof ApiError ? e.message : 'Kunne ikke hente varer'));
	});

	const groups = $derived.by(() => {
		const found = q.trim() ? catalog.search(q, 500) : catalog.ingredients;
		return catalog.meta.departments
			.map((d) => ({ ...d, items: found.filter((i) => i.department === d.code) }))
			.filter((g) => g.items.length);
	});

	function open(ing: Ingredient | null) {
		error = '';
		editing = ing ? ing.id : 'ny';
		form = {
			name: ing?.name ?? q.trim(),
			department: ing?.department ?? 'fg',
			pantry: ing?.pantry ?? false,
			perPiece: ing?.grams_per_piece ? formatNumber(ing.grams_per_piece) : '',
			perDl: ing?.grams_per_dl ? formatNumber(ing.grams_per_dl) : ''
		};
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		const body = {
			name: form.name,
			department: form.department,
			pantry: form.pantry,
			grams_per_piece: parseNumber(form.perPiece),
			grams_per_dl: parseNumber(form.perDl)
		};
		try {
			const ing =
				editing === 'ny'
					? await api<Ingredient>('/ingredients', { method: 'POST', body })
					: await api<Ingredient>(`/ingredients/${editing}`, { method: 'PUT', body });
			catalog.upsert(ing);
			editing = null;
		} catch (err) {
			error = err instanceof ApiError ? err.message : 'Kunne ikke gemme';
		}
	}
</script>

{#snippet editor()}
	<form class="edit card" onsubmit={save}>
		<label class="field"><span>Navn på indkøbslisten</span><input bind:value={form.name} required /></label>
		<div class="two">
			<label class="field"><span>Afdeling</span>
				<select bind:value={form.department}>
					{#each catalog.meta.departments as d}<option value={d.code}>{d.name}</option>{/each}
				</select>
			</label>
			<label class="check"><input type="checkbox" bind:checked={form.pantry} /> Basisvare</label>
		</div>
		<div class="two">
			<label class="field"><span>Gram pr. stk</span><input bind:value={form.perPiece} inputmode="decimal" /></label>
			<label class="field"><span>Gram pr. dl</span><input bind:value={form.perDl} inputmode="decimal" /></label>
		</div>
		<p class="muted small">Basisvarer er altid hjemme og kommer ikke på indkøbslisten. Gram bruges til at lægge fx "2 løg" og "150 g løg" sammen.</p>
		{#if error}<p class="error">{error}</p>{/if}
		<div class="row">
			<button type="button" onclick={() => (editing = null)}>Annullér</button>
			<button class="primary">Gem</button>
		</div>
	</form>
{/snippet}

<main>
	<header class="top">
		<h1>Varer</h1>
		<button class="primary" onclick={() => open(null)}>+ Ny vare</button>
	</header>

	{#if editing === 'ny'}{@render editor()}{/if}
	{#if error && editing === null}<p class="error">{error}</p>{/if}

	<input type="search" bind:value={q} placeholder="Søg i {catalog.ingredients.length} varer" aria-label="Søg" />

	{#each groups as g (g.code)}
		<h2>{g.name}</h2>
		<ul>
			{#each g.items as ing (ing.id)}
				<li>
					<button class="plain item" onclick={() => (editing === ing.id ? (editing = null) : open(ing))}>
						<span class="grow">
							{ing.name}
							{#if ing.aliases.length}<span class="muted small"> · {ing.aliases.slice(0, 4).join(', ')}{ing.aliases.length > 4 ? '…' : ''}</span>{/if}
						</span>
						{#if ing.pantry}<span class="badge ok">basis</span>{/if}
						{#if ing.used_in}<span class="muted small">{ing.used_in}</span>{/if}
					</button>
					{#if editing === ing.id}{@render editor()}{/if}
				</li>
			{/each}
		</ul>
	{:else}
		{#if loaded}<p class="empty">Ingen varer matcher "{q}".</p>{/if}
	{/each}
</main>

<style>
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.item {
		width: 100%;
		display: flex;
		gap: 8px;
		align-items: center;
		text-align: left;
		padding: 10px 2px;
		border-bottom: 1px solid var(--line);
		border-radius: 0;
		min-height: 44px;
	}
	.edit {
		display: grid;
		gap: 10px;
		padding: 12px;
		margin: 8px 0 12px;
	}
	.two {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
		align-items: end;
	}
	.check {
		display: flex;
		gap: 8px;
		align-items: center;
		min-height: 42px;
	}
	.check input {
		width: 22px;
		min-height: 0;
		height: 22px;
		accent-color: var(--accent);
	}
</style>
