<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
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
			error = say(err);
			if (err instanceof ApiError) {
				const d = err.detail as { id?: number } | null;
				if (err.status === 409 && d?.id) existing = d.id;
			}
		} finally {
			busy = false;
		}
	}

	async function paste() {
		try {
			url = (await navigator.clipboard.readText()).trim();
		} catch {
			error = 'Udklipsholderen kunne ikke læses. Indsæt linket i feltet.';
		}
	}
</script>

<main>
	<ScreenHeader title="Importér opskrift" eyebrow="Opskrifter" back="/opskrifter" />

	<form class="pad" onsubmit={submit}>
		<label class="field">
			<span>Link til opskriften</span>
			<input type="url" inputmode="url" placeholder="https://www.valdemarsro.dk/…" bind:value={url} required />
		</label>
		<div class="btns">
			<button type="button" class="btn" onclick={paste}>Indsæt link</button>
			<button class="btn primary" disabled={busy || !url.trim()}>{busy ? 'Henter opskriften…' : 'Importér'}</button>
		</div>
	</form>

	{#if error}
		<p class="msg" role="alert">
			{error}
			{#if existing}<a class="link" href="/opskrift/{existing}">Åbn opskriften</a>{/if}
		</p>
	{/if}

	<h2 class="sl">Virker med</h2>
	<p class="pad muted small">
		{sites.join(', ')} og de fleste andre sider med opskriftsdata. Spis Bedre virker ikke. Ingredienserne læses
		automatisk, og I kan rette dem bagefter.
	</p>
</main>

<style>
	form {
		display: grid;
		gap: 12px;
		margin-top: 8px;
	}
	.msg .link {
		display: block;
		padding-block: 10px 2px;
	}
</style>
