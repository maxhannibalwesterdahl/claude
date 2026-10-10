<script lang="ts">
	import { untrack } from 'svelte';
	import { api } from './api';
	import { catalog } from './catalog.svelte';
	import type { Ingredient, IngredientRef } from './types';
	import { say } from './ui/copy';
	import Icon from './ui/Icon.svelte';

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
		catalog.load().catch((e) => (error = say(e)));
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
			error = say(e);
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

<!-- Kun indholdet: den, der bruger vælgeren, lægger den i et ark eller på et kort.
     Escape i feltet kalder oncancel. -->
<div class="picker">
	<div class="search">
		<input bind:this={input} bind:value={q} onkeydown={keydown} placeholder="Søg vare" aria-label="Søg vare" class="grow" />
		<button type="button" class="btn sm legacy-only" onclick={oncancel}>Luk</button>
	</div>
	{#if suggestion}
		<div class="suggestion">
			<button type="button" class="btn primary block" onclick={() => onpick(suggestion)}>
				<Icon name="check" size={16} stroke={3} />{suggestion.name}
			</button>
		</div>
	{/if}
	<ul>
		{#each results as ing (ing.id)}
			<li>
				<button type="button" class="kv" onclick={() => onpick(ing)}>
					<span class="k">{ing.name}</span>
					<span class="muted small">{catalog.departmentName(ing.department)}{ing.pantry ? ' · basis' : ''}</span>
				</button>
			</li>
		{/each}
	</ul>
	<div class="extra">
		{#if q.trim() && !exact}
			{#if creating}
				<select bind:value={department} class="grow" aria-label="Afdeling">
					{#each catalog.meta.departments as d}
						<option value={d.code}>{d.name}</option>
					{/each}
				</select>
				<button type="button" class="btn sm primary" onclick={create}>Opret</button>
			{:else}
				<button type="button" class="btn sm" onclick={() => (creating = true)}><Icon name="plus" size={16} />Ny vare "{q.trim()}"</button>
			{/if}
		{/if}
		<button type="button" class="btn sm" onclick={() => onpick(null)}>Ingen vare</button>
	</div>
	{#if error}<p class="msg" role="alert">{error}</p>{/if}
</div>

<style>
	.picker {
		padding-block: 4px 12px;
	}
	.search,
	.suggestion,
	.extra {
		display: flex;
		align-items: center;
		gap: 8px;
		padding-inline: var(--gutter);
	}
	.suggestion {
		margin-top: 8px;
	}
	ul {
		list-style: none;
		margin: 4px 0 12px;
		padding: 0;
		max-height: 260px;
		overflow-y: auto;
	}
	.extra {
		flex-wrap: wrap;
	}
	/* Et langt varenavn må ikke skubbe knappen ud over kanten. */
	.extra .btn {
		max-width: 100%;
		overflow: hidden;
	}
	.extra select {
		flex: 1 1 160px;
		min-height: var(--btn-sm-h);
	}
</style>
