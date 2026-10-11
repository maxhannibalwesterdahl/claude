<script lang="ts">
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { catalog } from '$lib/catalog.svelte';
	import { formatNumber, parseNumber } from '$lib/format';
	import { say } from '$lib/ui/copy';
	import IngredientForm, { type IngredientFields } from './IngredientForm.svelte';
	import type { Ingredient } from '$lib/types';

	interface Props {
		/** alle: hele varelisten. basis: kun basisvarerne, og varer kan gøres til basis. */
		mode: 'alle' | 'basis';
	}
	let { mode }: Props = $props();

	let q = $state('');
	let error = $state('');
	let editing = $state<number | 'ny' | null>(null);
	let form = $state<IngredientFields>({ name: '', department: 'fg', pantry: false, perPiece: '', perDl: '' });
	let loaded = $state(false);
	let busy = $state<number | null>(null);

	$effect(() => {
		untrack(() => {
			catalog
				.load(true)
				.then(() => (loaded = true))
				.catch((e) => (error = say(e)));
		});
	});

	const found = $derived(q.trim() ? catalog.search(q, 500) : catalog.ingredients);
	const groups = $derived.by(() => {
		const shown = mode === 'basis' ? found.filter((i) => i.pantry) : found;
		return catalog.meta.departments
			.map((d) => ({ ...d, items: shown.filter((i) => i.department === d.code) }))
			.filter((g) => g.items.length);
	});
	// Under Basisvarer: varer, der matcher søgningen, men ikke er basis endnu.
	const addable = $derived(mode === 'basis' && q.trim() ? found.filter((i) => !i.pantry).slice(0, 8) : []);

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
			error = say(e);
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

	/** "Ny vare" i sidens top: formularen åbnes med søgeteksten som navn. */
	export function openNew() {
		open(null);
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
			error = say(err);
		}
	}

	// Formularen til en ny vare står øverst: rul den frem, når den åbnes nede fra listen.
	function reveal(node: HTMLElement) {
		node.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
		node.querySelector('input')?.focus();
	}
</script>

{#if editing === 'ny'}
	<div use:reveal><IngredientForm bind:form {error} onsubmit={save} oncancel={() => (editing = null)} /></div>
{/if}
{#if error && editing === null}<p class="msg" role="alert">{error}</p>{/if}

{#if mode === 'basis'}
	<p class="pad muted small intro">Basisvarer er altid hjemme og kommer ikke på indkøbslisten. Mangler I en, så tryk "Løbet tør" under Indkøb.</p>
{/if}

<div class="pad search">
	<input
		type="search"
		bind:value={q}
		placeholder={mode === 'basis' ? 'Søg, eller find en vare at tilføje' : `Søg i ${catalog.ingredients.length} varer`}
		aria-label={mode === 'basis' ? 'Søg i basisvarer' : 'Søg i varer'}
	/>
</div>

{#if addable.length}
	<h2 class="sl">Tilføj som basisvare</h2>
	<ul>
		{#each addable as ing (ing.id)}
			<li class="line">
				<span class="grow name">
					<span class="ellipsis">{ing.name}</span>
					<span class="muted small">{catalog.departmentName(ing.department)}</span>
				</span>
				<button type="button" class="btn sm" disabled={busy === ing.id} aria-label="Gør {ing.name} til basisvare" onclick={() => setPantry(ing, true)}>Tilføj</button>
			</li>
		{/each}
	</ul>
{/if}

{#each groups as g (g.code)}
	<h2 class="sl">{g.name}<span>{g.items.length}</span></h2>
	<ul>
		{#each g.items as ing (ing.id)}
			<li>
				<div class="line">
					<button type="button" class="item" aria-expanded={editing === ing.id} onclick={() => (editing === ing.id ? (editing = null) : open(ing))}>
						<span class="grow name">
							<span class="ellipsis">{ing.name}</span>
							{#if ing.aliases.length}<span class="muted small ellipsis">{ing.aliases.join(', ')}</span>{/if}
						</span>
						{#if ing.pantry && mode === 'alle'}<span class="tag">basis</span>{/if}
						{#if ing.used_in}<span class="muted small used" title="Bruges i {ing.used_in} opskrifter">{ing.used_in} opskr.</span>{/if}
					</button>
					{#if mode === 'basis'}
						<button type="button" class="btn sm" disabled={busy === ing.id} aria-label="{ing.name} er ikke basisvare" onclick={() => setPantry(ing, false)}>Ikke basis</button>
					{/if}
				</div>
				{#if editing === ing.id}
					<IngredientForm bind:form {error} onsubmit={save} oncancel={() => (editing = null)} />
				{/if}
			</li>
		{/each}
	</ul>
{:else}
	{#if loaded && !addable.length}
		<p class="empty">
			{#if mode === 'basis' && !q.trim()}Der er ingen basisvarer endnu.{:else}Ingen varer matcher "{q.trim()}".{/if}
		</p>
	{/if}
{/each}

<style>
	.intro {
		margin-bottom: 10px;
	}
	.search {
		margin-top: 4px;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.line {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: var(--row-h);
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	/* Hele rækken åbner varen. */
	.item {
		flex: 1;
		min-width: 0;
		align-self: stretch;
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.name {
		display: grid;
		font-size: var(--fs-row);
		font-weight: 500;
	}
	.name .small {
		font-weight: 400;
	}
	.used {
		flex: none;
	}
</style>
