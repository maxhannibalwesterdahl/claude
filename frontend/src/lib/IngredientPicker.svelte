<script lang="ts">
	import { untrack } from 'svelte';
	import { api, ApiError } from './api';
	import { catalog } from './catalog.svelte';
	import type { Ingredient, IngredientRef } from './types';

	interface Props {
		/** Teksten fra opskriften, bruges som første søgning. */
		initial: string;
		onpick: (ing: IngredientRef | null) => void;
		oncancel: () => void;
		/** Appens bud (fx et usikkert match). Vises øverst. */
		suggestion?: IngredientRef | null;
		/** Afdeling, der er valgt på forhånd, når en ny vare oprettes. */
		defaultDepartment?: string;
	}
	let { initial, onpick, oncancel, suggestion = null, defaultDepartment = 'fg' }: Props = $props();

	let q = $state(untrack(() => initial));
	let creating = $state(false);
	let department = $state(untrack(() => defaultDepartment));
	let error = $state('');
	let input: HTMLInputElement | undefined = $state();

	const results = $derived(catalog.search(q, 12));
	const exact = $derived(results.some((r) => r.name === q.trim().toLowerCase()));

	$effect(() => {
		catalog.load().catch(() => (error = 'Kunne ikke hente varer'));
		input?.focus();
		input?.select();
	});

	async function create() {
		error = '';
		try {
			const ing = await api<Ingredient>('/ingredients', {
				method: 'POST',
				body: { name: q.trim(), department, pantry: false }
			});
			catalog.upsert(ing);
			onpick(ing);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke oprette varen';
		}
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape') oncancel();
		if (e.key === 'Enter') {
			e.preventDefault();
			if (results[0]) onpick(results[0]);
		}
	}
</script>

<div class="picker card">
	<div class="row">
		<input bind:this={input} bind:value={q} onkeydown={keydown} placeholder="Søg vare" aria-label="Søg vare" class="grow" />
		<button type="button" onclick={oncancel}>Luk</button>
	</div>
	{#if suggestion}
		<button type="button" class="primary suggestion" onclick={() => onpick(suggestion)}>✓ {suggestion.name}</button>
	{/if}
	<ul>
		{#each results as ing (ing.id)}
			<li>
				<button type="button" class="plain" onclick={() => onpick(ing)}>
					<span class="grow">{ing.name}</span>
					<span class="muted small">{catalog.departmentName(ing.department)}{ing.pantry ? ' · basis' : ''}</span>
				</button>
			</li>
		{/each}
	</ul>
	<div class="extra">
		{#if q.trim() && !exact}
			{#if creating}
				<div class="row">
					<select bind:value={department} class="grow" aria-label="Afdeling">
						{#each catalog.meta.departments as d}
							<option value={d.code}>{d.name}</option>
						{/each}
					</select>
					<button type="button" class="primary" onclick={create}>Opret</button>
				</div>
			{:else}
				<button type="button" onclick={() => (creating = true)}>+ Ny vare "{q.trim()}"</button>
			{/if}
		{/if}
		<button type="button" onclick={() => onpick(null)}>Ingen vare</button>
	</div>
	{#if error}<p class="error">{error}</p>{/if}
</div>

<style>
	.picker {
		padding: 10px;
		margin: 6px 0 10px;
		box-shadow: 0 6px 24px rgb(0 0 0 / 0.12);
	}
	ul {
		list-style: none;
		margin: 8px 0;
		padding: 0;
		max-height: 260px;
		overflow-y: auto;
	}
	li button {
		width: 100%;
		display: flex;
		gap: 8px;
		text-align: left;
		padding: 10px 6px;
		border-bottom: 1px solid var(--line);
		border-radius: 0;
		min-height: 44px;
	}
	.suggestion {
		width: 100%;
		justify-content: center;
		margin-top: 8px;
	}
	.extra {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
</style>
