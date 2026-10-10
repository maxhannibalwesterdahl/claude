<script lang="ts">
	import BackButton from '$lib/BackButton.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { confirmDialog } from '$lib/confirm.svelte';
	import { formatQuantity } from '$lib/format';
	import { groupLines } from '$lib/lines';
	import { groupSteps } from '$lib/steps';
	import type { Line, Recipe } from '$lib/types';

	let recipe = $state<Recipe | null>(null);
	let error = $state('');
	const warning = $derived(page.url.searchParams.get('advarsel'));

	$effect(() => {
		const id = page.params.id;
		api<Recipe>(`/recipes/${id}`)
			.then((r) => (recipe = r))
			.catch((e) => (error = e instanceof ApiError ? e.message : 'Kunne ikke hente opskriften'));
	});

	const groups = $derived(recipe ? groupLines(recipe.ingredients) : []);

	const stepGroups = $derived(groupSteps(recipe?.instructions ?? []));
	const toReview = $derived(recipe?.ingredients.filter((l) => l.match_status === 'usikker' || l.match_status === 'ingen').length ?? 0);

	async function toggleMain(line: Line) {
		const next = !line.is_main;
		line.is_main = next;
		try {
			await api(`/lines/${line.id}/main`, { method: 'PUT', body: { is_main: next } });
		} catch (e) {
			line.is_main = !next;
			error = e instanceof ApiError ? e.message : 'Kunne ikke gemme stjernen';
		}
	}

	async function remove() {
		const id = recipe?.id;
		if (!recipe || !(await confirmDialog(`Slet "${recipe.title}"?`, 'Slet'))) return;
		try {
			await api(`/recipes/${id}`, { method: 'DELETE' });
			await goto('/opskrifter');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke slette';
		}
	}
</script>

<main class="legacy">
	<header class="top">
		<BackButton fallback="/opskrifter" />
		<span class="grow"></span>
		{#if recipe}<a class="button" href="/opskrift/{recipe.id}/rediger">Rediger</a>{/if}
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if warning}<p class="error" role="alert">{warning}</p>{/if}

	{#if recipe}
		<!-- Titlen står i siden og ikke i den faste top, så lange navne kan læses helt. -->
		<h1 class="title">{recipe.title}</h1>
		{#if recipe.image_url}
			<img class="hero" src={recipe.image_url} alt="" />
		{/if}

		<p class="muted">
			{#if recipe.servings}<strong class="servings">{recipe.servings} portioner</strong>{/if}
			{#if recipe.servings && recipe.source_url && /^https?:\/\//i.test(recipe.source_url)} · {/if}
			{#if recipe.source_url && /^https?:\/\//i.test(recipe.source_url)}
				<a href={recipe.source_url} target="_blank" rel="noopener noreferrer">{new URL(recipe.source_url).hostname.replace(/^www\./, '')}</a>
			{/if}
		</p>

		{#if recipe.child_note}
			<p class="child"><strong>Barnet:</strong> {recipe.child_note}</p>
		{/if}

		<div class="columns">
		<section>
		<h2 class="section-title">Ingredienser</h2>
		<p class="muted small hint">Tryk ☆ for at markere hovedingredienser. Appen holder øje med tilbud på dem.</p>
		{#if toReview}
			<p class="small">
				<span class="badge">{toReview} at tjekke</span>
				<a href="/opskrift/{recipe.id}/rediger">Ret varerne</a>
			</p>
		{/if}
		{#each groups as g}
			{#if g.name}<h3>{g.name}</h3>{/if}
			<ul class="ingredients">
				{#each g.lines as l}
					<li class:main={l.is_main}>
						<button
							class="plain star"
							class:on={l.is_main}
							aria-pressed={l.is_main}
							aria-label="Hovedingrediens: {l.item}"
							title={l.is_main ? 'Hovedingrediens (fjern stjernen)' : 'Gør til hovedingrediens'}
							onclick={() => toggleMain(l)}>{l.is_main ? '★' : '☆'}</button
						>
						<span class="ing-qty">{formatQuantity(l.quantity, l.quantity_max, l.unit)}</span>
						<span class="grow">
							{l.item}{#if l.note}<span class="muted">, {l.note}</span>{/if}
							{#if l.match_status === 'usikker'}
								<span class="badge">{l.ingredient?.name}?</span>
							{:else if l.match_status === 'ingen'}
								<span class="badge">ingen vare</span>
							{/if}
						</span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="muted">Ingen ingredienser.</p>
		{/each}

		</section>
		<section>
		{#if recipe.instructions.length}
			<h2 class="section-title">Fremgangsmåde</h2>
			{#each stepGroups as sg}
				{#if sg.title}<h3>{sg.title}</h3>{/if}
				<ol class="steps">
					{#each sg.steps as step}
						<li>{step}</li>
					{/each}
				</ol>
			{/each}
		{/if}

		</section>
		</div>

		<p class="actions"><button class="danger" onclick={remove}>Slet opskrift</button></p>
	{/if}
</main>

<style>
	.title {
		margin-bottom: 12px;
	}
	.servings {
		color: var(--fg);
	}
	.child {
		background: var(--accent-soft);
		border-radius: var(--radius-control);
		padding: 10px 12px;
	}
	h3 {
		font-size: 1rem;
		margin: 16px 0 4px;
	}
	.ingredients li {
		align-items: center;
		gap: 8px;
	}
	.main .grow {
		font-weight: 600;
	}
	/* Trykfladen er 44px, men må ikke gøre linjen højere: den rækker ud over den. */
	.star {
		flex: none;
		margin: -6px;
		font-size: 1.2rem;
		line-height: 1;
		color: var(--muted);
		padding: 0;
	}
	.star.on {
		color: var(--star);
	}
	.hint {
		margin-top: -4px;
	}
	.steps {
		padding-left: 1.4em;
	}
	.steps li {
		margin-bottom: 10px;
	}
	.actions {
		margin-top: 40px;
		text-align: center;
	}
</style>
