<script lang="ts">
	import { api, ApiError } from './api';
	import Thumb from './Thumb.svelte';
	import type { Recipe } from './types';

	interface Hit {
		title: string;
		url: string;
		image_url: string;
		recipe_id: number | null;
	}

	interface Props {
		/** Søgeteksten. Der søges fra 3 tegn, lidt efter man er holdt op med at skrive. */
		q: string;
		/** Knaptekst for en opskrift, vi allerede har ("Åbn" eller "Vælg"). */
		haveLabel?: string;
		/** Kaldes med opskriftens id, når den er importeret eller allerede fandtes. */
		onpick: (recipeId: number, imported: boolean) => void;
	}
	let { q, haveLabel = 'Åbn', onpick }: Props = $props();

	let hits = $state<Hit[]>([]);
	let loading = $state(false);
	let error = $state('');
	let importing = $state<string | null>(null);
	let searched = $state('');

	$effect(() => {
		const term = q.trim();
		error = '';
		if (term.length < 3) {
			hits = [];
			searched = '';
			return;
		}
		loading = true;
		let stale = false;
		const timer = setTimeout(async () => {
			try {
				const res = await api<Hit[]>(`/search/valdemarsro?q=${encodeURIComponent(term)}`);
				if (!stale) {
					hits = res;
					searched = term;
				}
			} catch (e) {
				if (!stale) error = e instanceof ApiError ? e.message : 'Kunne ikke søge på Valdemarsro';
			} finally {
				if (!stale) loading = false;
			}
		}, 450);
		return () => {
			stale = true;
			clearTimeout(timer);
		};
	});

	async function take(hit: Hit) {
		if (hit.recipe_id) return onpick(hit.recipe_id, false);
		importing = hit.url;
		error = '';
		try {
			const r = await api<Recipe>('/recipes/import', { method: 'POST', body: { url: hit.url } });
			hit.recipe_id = r.id;
			onpick(r.id, true);
		} catch (e) {
			const existing = e instanceof ApiError && e.status === 409 ? (e.detail as { id?: number })?.id : undefined;
			if (existing) {
				hit.recipe_id = existing;
				onpick(existing, false);
			} else error = e instanceof ApiError ? `${hit.title}: ${e.message}` : 'Kunne ikke importere';
		} finally {
			importing = null;
		}
	}
</script>

{#if q.trim().length >= 3}
	<section class="ext" aria-live="polite">
		<h2 class="section-title">
			Fra Valdemarsro
			{#if loading}<span class="muted small">søger…</span>{/if}
		</h2>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if !loading && searched && !hits.length && !error}
			<p class="muted small">Ingen opskrifter på Valdemarsro matcher "{searched}".</p>
		{/if}
		<ul>
			{#each hits as hit (hit.url)}
				<li>
					<Thumb src={hit.image_url} size="sm" lazy referrerpolicy="no-referrer" />
					<span class="grow title">{hit.title}</span>
					<button
						class:primary={!hit.recipe_id}
						disabled={importing !== null}
						onclick={() => take(hit)}
						aria-label="{hit.recipe_id ? haveLabel : 'Importér'} {hit.title}"
					>
						{importing === hit.url ? 'Henter…' : hit.recipe_id ? haveLabel : 'Importér'}
					</button>
				</li>
			{/each}
		</ul>
		{#if hits.length}
			<p class="muted small credit">
				Opskrifter fra <a href="https://www.valdemarsro.dk" target="_blank" rel="noopener noreferrer">valdemarsro.dk</a>. Import gemmer opskriften i jeres egen samling.
			</p>
		{/if}
	</section>
{/if}

<style>
	.ext {
		margin-top: 16px;
	}
	h2 {
		margin: 0 0 8px;
		display: flex;
		gap: 8px;
		align-items: baseline;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 6px;
	}
	li {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 6px;
		border-radius: var(--radius-seg);
		background: var(--card);
		border: 1px solid var(--line);
	}
	.title {
		font-weight: 600;
		line-height: 1.3;
	}
	button {
		flex: none;
	}
	.credit {
		margin-top: 8px;
	}
</style>
