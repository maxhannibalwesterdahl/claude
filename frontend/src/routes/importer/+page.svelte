<script lang="ts">
	import BackButton from '$lib/BackButton.svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import type { Recipe } from '$lib/types';

	let url = $state('');
	let error = $state('');
	let existing = $state<number | null>(null);
	let busy = $state(false);

	const sites = ['valdemarsro.dk', 'nemlig.com', 'madensverden.dk', 'arla.dk', 'dr.dk/mad', 'sundpaabudget.dk', 'hellofresh.dk'];

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		existing = null;
		try {
			const r = await api<Recipe>('/recipes/import', { method: 'POST', body: { url: url.trim() } });
			const note = r.warnings.length ? `?advarsel=${encodeURIComponent(r.warnings.join('. '))}` : '';
			await goto(`/opskrift/${r.id}${note}`);
		} catch (err) {
			if (err instanceof ApiError) {
				error = err.message;
				const d = err.detail as { id?: number } | null;
				if (err.status === 409 && d?.id) existing = d.id;
			} else error = 'Noget gik galt';
		} finally {
			busy = false;
		}
	}

	async function paste() {
		try {
			url = (await navigator.clipboard.readText()).trim();
		} catch {
			error = 'Kunne ikke læse udklipsholderen. Indsæt linket i feltet.';
		}
	}
</script>

<main>
	<header class="top">
		<BackButton fallback="/opskrifter" />
		<h1>Importér opskrift</h1>
	</header>

	<form onsubmit={submit}>
		<label class="field">
			<span>Link til opskriften</span>
			<input type="url" inputmode="url" placeholder="https://www.valdemarsro.dk/…" bind:value={url} required />
		</label>
		<div class="row">
			<button type="button" onclick={paste}>Indsæt link</button>
			<button class="primary grow" disabled={busy || !url.trim()}>{busy ? 'Henter opskriften…' : 'Importér'}</button>
		</div>
	</form>

	{#if error}
		<p class="error" role="alert">
			{error}
			{#if existing}<br /><a href="/opskrift/{existing}">Åbn opskriften</a>{/if}
		</p>
	{/if}

	<h2 class="section-title">Virker med</h2>
	<p class="muted small">
		{sites.join(', ')} og de fleste andre sider med opskriftsdata. Spis Bedre virker ikke. Ingredienserne læses
		automatisk, og I kan rette dem bagefter.
	</p>
</main>

<style>
	form {
		display: grid;
		gap: 12px;
	}
	button.grow {
		justify-content: center;
	}
</style>
