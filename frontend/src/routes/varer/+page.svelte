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
	let tab = $state<'alle' | 'basis'>('alle');
	let busy = $state<number | null>(null);

	$effect(() => {
		catalog
			.load(true)
			.then(() => (loaded = true))
			.catch((e) => (error = e instanceof ApiError ? e.message : 'Kunne ikke hente varer'));
	});

	const pantryCount = $derived(catalog.ingredients.filter((i) => i.pantry).length);
	const found = $derived(q.trim() ? catalog.search(q, 500) : catalog.ingredients);
	const groups = $derived.by(() => {
		const shown = tab === 'basis' ? found.filter((i) => i.pantry) : found;
		return catalog.meta.departments
			.map((d) => ({ ...d, items: shown.filter((i) => i.department === d.code) }))
			.filter((g) => g.items.length);
	});
	// Under Basisvarer: varer, der matcher søgningen, men ikke er basis endnu.
	const addable = $derived(tab === 'basis' && q.trim() ? found.filter((i) => !i.pantry).slice(0, 8) : []);

	async function setPantry(ing: Ingredient, pantry: boolean) {
		busy = ing.id;
		error = '';
		try {
			const saved = await api<Ingredient>(`/ingredients/${ing.id}`, {
				method: 'PUT',
				body: {
					name: ing.name,
					department: ing.department,
					pantry,
					grams_per_piece: ing.grams_per_piece,
					grams_per_dl: ing.grams_per_dl
				}
			});
			catalog.upsert(saved);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke gemme';
		} finally {
			busy = null;
		}
	}

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

	<div class="tabs" role="tablist">
		<button role="tab" aria-selected={tab === 'alle'} onclick={() => (tab = 'alle')}>Alle varer</button>
		<button role="tab" aria-selected={tab === 'basis'} onclick={() => (tab = 'basis')}>Basisvarer ({pantryCount})</button>
	</div>

	{#if tab === 'basis'}
		<p class="muted small">Basisvarer er altid hjemme og kommer ikke på indkøbslisten. Mangler I en, så tryk "Løbet tør" under Indkøb.</p>
	{/if}

	<input
		type="search"
		bind:value={q}
		placeholder={tab === 'basis' ? 'Søg, eller find en vare at tilføje' : `Søg i ${catalog.ingredients.length} varer`}
		aria-label="Søg"
	/>

	{#if addable.length}
		<h2>Tilføj som basisvare</h2>
		<ul>
			{#each addable as ing (ing.id)}
				<li class="quick">
					<span class="grow ellipsis">{ing.name} <span class="muted small">{catalog.departmentName(ing.department)}</span></span>
					<button disabled={busy === ing.id} onclick={() => setPantry(ing, true)}>+ Basis</button>
				</li>
			{/each}
		</ul>
	{/if}

	{#each groups as g (g.code)}
		<h2>{g.name}</h2>
		<ul>
			{#each g.items as ing (ing.id)}
				<li>
					<div class="line">
						<button class="plain item" onclick={() => (editing === ing.id ? (editing = null) : open(ing))}>
							<span class="grow ellipsis">
								{ing.name}{#if ing.aliases.length}<span class="muted small">&nbsp;· {ing.aliases.join(', ')}</span>{/if}
							</span>
							{#if ing.pantry && tab === 'alle'}<span class="badge ok">basis</span>{/if}
							{#if ing.used_in}<span class="muted small used" title="Bruges i {ing.used_in} opskrifter">{ing.used_in} opskr.</span>{/if}
						</button>
						{#if tab === 'basis'}
							<button class="unset" disabled={busy === ing.id} onclick={() => setPantry(ing, false)}>Ikke basis</button>
						{/if}
					</div>
					{#if editing === ing.id}{@render editor()}{/if}
				</li>
			{/each}
		</ul>
	{:else}
		{#if loaded && !addable.length}
			<p class="empty">
				{#if tab === 'basis' && !q.trim()}Ingen basisvarer endnu.{:else}Ingen varer matcher "{q}".{/if}
			</p>
		{/if}
	{/each}
</main>

<style>
	.tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 4px;
		padding: 4px;
		margin-bottom: 12px;
		background: var(--card);
		border: 1px solid var(--line);
		border-radius: 12px;
	}
	.tabs button {
		border: none;
		justify-content: center;
		background: none;
		font-weight: 600;
		color: var(--muted);
	}
	.tabs button[aria-selected='true'] {
		background: var(--accent);
		color: var(--accent-fg);
	}
	.line {
		display: flex;
		align-items: center;
		gap: 8px;
		border-bottom: 1px solid var(--line);
	}
	.line .item {
		flex: 1;
		min-width: 0;
		border-bottom: none;
	}
	.unset {
		flex: none;
		min-height: 36px;
		padding: 4px 10px;
		font-size: 0.85rem;
	}
	.quick {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 48px;
		border-bottom: 1px solid var(--line);
	}
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
	.used {
		flex: none;
	}
	.edit {
		display: grid;
		gap: 10px;
		padding: 12px;
		margin: 8px 0 12px;
	}
	.two {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
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
