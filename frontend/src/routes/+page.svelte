<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { searchKey } from '$lib/format';
	import { refreshReviewCount } from '$lib/review.svelte';
	import type { RecipeSummary } from '$lib/types';

	let recipes = $state<RecipeSummary[] | null>(null);
	let error = $state('');
	let q = $state('');

	const shown = $derived(
		recipes?.filter((r) => searchKey(r.title + ' ' + r.main_ingredients.join(' ')).includes(searchKey(q))) ?? []
	);

	$effect(() => {
		api<RecipeSummary[]>('/recipes')
			.then((r) => (recipes = r))
			.catch((e) => (error = e instanceof ApiError ? e.message : 'Kunne ikke hente opskrifter'));
		refreshReviewCount().catch(() => {});
	});

	async function logout() {
		await api('/logout', { method: 'POST' }).catch(() => {});
		await goto('/login');
	}
</script>

<main>
	<header class="top">
		<h1>Opskrifter</h1>
		<a class="button" href="/ny">+ Ny</a>
		<a class="button primary" href="/importer">Importér</a>
	</header>

	{#if error}<p class="error">{error}</p>{/if}

	{#if recipes && recipes.length > 0}
		<input type="search" placeholder="Søg i {recipes.length} opskrifter" bind:value={q} aria-label="Søg" />
		<ul>
			{#each shown as r (r.id)}
				<li>
					<a href="/opskrift/{r.id}" class="card">
						{#if r.image_url}
							<img src={r.image_url} alt="" loading="lazy" />
						{:else}
							<div class="noimg" aria-hidden="true">{r.title.slice(0, 1)}</div>
						{/if}
						<div class="grow">
							<strong>{r.title}</strong>
							<div class="muted small">
								{#if r.main_ingredients.length}★ {r.main_ingredients.join(', ')}{/if}
								{#if r.main_ingredients.length && r.source_host} · {/if}
								{#if r.source_host}{r.source_host}{/if}
							</div>
							{#if r.to_review}<span class="badge">{r.to_review} at tjekke</span>{/if}
						</div>
					</a>
				</li>
			{:else}
				<li class="empty">Ingen opskrifter matcher "{q}"</li>
			{/each}
		</ul>
	{:else if recipes}
		<div class="empty">
			<p>Ingen opskrifter endnu.</p>
			<p><a class="button primary" href="/importer">Importér fra et link</a></p>
			<p><a href="/ny">eller skriv en selv</a></p>
		</div>
	{/if}

	<p class="footer"><button class="plain muted small" onclick={logout}>Log ud</button></p>
</main>

<style>
	input[type='search'] {
		margin-bottom: 12px;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 8px;
	}
	li > a {
		display: flex;
		gap: 12px;
		align-items: center;
		padding: 8px;
		color: inherit;
		text-decoration: none;
	}
	img,
	.noimg {
		width: 72px;
		height: 72px;
		border-radius: 8px;
		object-fit: cover;
		flex: none;
	}
	.noimg {
		display: grid;
		place-items: center;
		background: var(--accent-soft);
		color: var(--accent);
		font-size: 1.8rem;
		font-weight: 700;
	}
	strong {
		display: block;
		line-height: 1.25;
	}
	.footer {
		text-align: center;
		margin-top: 32px;
	}
</style>
