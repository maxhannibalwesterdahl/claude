<script lang="ts">
	import BackButton from '$lib/BackButton.svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { formatQuantity } from '$lib/format';
	import { groupLines } from '$lib/lines';
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

	// Korte trin uden punktum er afsnitsoverskrifter ("Mornaysauce").
	const isHeading = (s: string) => s.length <= 40 && !/[.!?:]$/.test(s) && s.split(' ').length <= 5;
	const stepGroups = $derived.by(() => {
		const out: { title: string; steps: string[] }[] = [];
		for (const step of recipe?.instructions ?? []) {
			if (isHeading(step)) out.push({ title: step, steps: [] });
			else if (out.length) out[out.length - 1].steps.push(step);
			else out.push({ title: '', steps: [step] });
		}
		return out;
	});
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
		if (!recipe || !confirm(`Slet "${recipe.title}"?`)) return;
		try {
			await api(`/recipes/${recipe.id}`, { method: 'DELETE' });
			await goto('/opskrifter');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke slette';
		}
	}
</script>

<main>
	<header class="top">
		<BackButton fallback="/opskrifter" />
		<h1>{recipe?.title ?? ''}</h1>
		{#if recipe}<a class="button" href="/opskrift/{recipe.id}/rediger">Rediger</a>{/if}
	</header>

	{#if error}<p class="error">{error}</p>{/if}
	{#if warning}<p class="error">{warning}</p>{/if}

	{#if recipe}
		{#if recipe.image_url}
			<img class="hero" src={recipe.image_url} alt="" />
		{/if}

		<p class="muted">
			{#if recipe.servings}<strong class="servings">{recipe.servings} portioner</strong>{/if}
			{#if recipe.servings && recipe.source_url} · {/if}
			{#if recipe.source_url}
				<a href={recipe.source_url} target="_blank" rel="noopener noreferrer">{new URL(recipe.source_url).hostname.replace(/^www\./, '')}</a>
			{/if}
		</p>

		{#if recipe.child_note}
			<p class="child"><strong>Barnet:</strong> {recipe.child_note}</p>
		{/if}

		<div class="columns">
		<section>
		<h2>Ingredienser</h2>
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
						<span class="qty">{formatQuantity(l.quantity, l.quantity_max, l.unit)}</span>
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
			<h2>Fremgangsmåde</h2>
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
	/* iPad på tværs og computer: ingredienser ved siden af fremgangsmåden. */
	@media (min-width: 900px) {
		.columns {
			display: grid;
			grid-template-columns: minmax(280px, 2fr) 3fr;
			gap: 40px;
			align-items: start;
		}
		.columns > section:first-child {
			position: sticky;
			top: 80px;
		}
	}
	.hero {
		width: 100%;
		max-height: min(320px, 40vh);
		object-fit: cover;
		border-radius: var(--radius);
	}
	.servings {
		color: var(--fg);
	}
	.child {
		background: var(--accent-soft);
		border-radius: 10px;
		padding: 10px 12px;
	}
	h3 {
		font-size: 1rem;
		margin: 16px 0 4px;
	}
	.ingredients {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.ingredients li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 7px 0;
		border-bottom: 1px solid var(--line);
	}
	.qty {
		flex: 0 0 auto;
		min-width: 64px;
		max-width: 40%;
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}
	.main .grow {
		font-weight: 600;
	}
	.star {
		flex: none;
		width: 32px;
		min-height: 32px;
		justify-content: center;
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
