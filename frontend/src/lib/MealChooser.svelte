<script lang="ts">
	import { api } from './api';
	import { shortDate, weekdayName } from './dates';
	import { searchKey } from './format';
	import type { Meal, Plan, RecipeSummary, SlotChoice } from './types';
	import ValdemarsroResults from './ValdemarsroResults.svelte';

	interface Props {
		plan: Plan;
		/** Dagen, der vælges til. Tom ved "wish": tilføj til ønskelisten. */
		date?: string;
		forChild?: boolean;
		/** "wish": vælg flere retter til ønskelisten. Arket bliver åbent. */
		mode?: 'slot' | 'wish';
		onchoose: (choice: SlotChoice) => void;
		oncancel: () => void;
	}
	let { plan, date = '', forChild = false, mode = 'slot', onchoose, oncancel }: Props = $props();

	const wishMode = $derived(mode === 'wish');
	// Opskrifter, der allerede er på ønskelisten (vises med flueben).
	const wished = $derived(new Set(plan.wishlist.map((w) => w.recipe?.id).filter(Boolean)));

	type Tab = 'opskrift' | 'ønske' | 'rester' | 'fritekst';
	let tab = $state<Tab>('opskrift');
	let q = $state('');
	let text = $state('');
	let recipes = $state<RecipeSummary[] | null>(null);
	let error = $state('');

	const quick = $derived(
		wishMode ? ['Tacos', 'Pizza', 'Suppe', 'Fisk'] : forChild ? ['Grød', 'Mos', 'Rugbrød', 'Pasta'] : ['Pizza ude', 'Rugbrød', 'Takeaway', 'Spiser ude']
	);

	// Retter på tidligere dage, der kan give rester.
	const sources = $derived(
		plan.days
			.filter((d) => d.date < date)
			.flatMap((d) => [d.meal, d.child])
			.filter((m): m is Meal => !!m && m.kind === 'opskrift')
	);

	const shown = $derived(
		(recipes ?? []).filter((r) => searchKey([r.title, ...r.ingredients].join(' ')).includes(searchKey(q)))
	);

	$effect(() => {
		api<RecipeSummary[]>('/recipes')
			.then((r) => (recipes = r))
			.catch(() => (error = 'Kunne ikke hente opskrifter'));
	});

	function submitText(e: SubmitEvent) {
		e.preventDefault();
		if (text.trim()) onchoose({ kind: 'fritekst', text: text.trim() });
		text = '';
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape') oncancel();
	}
</script>

<svelte:window onkeydown={keydown} />

<div class="backdrop" onclick={oncancel} aria-hidden="true"></div>
<div class="sheet" role="dialog" aria-modal="true" aria-label="Vælg ret">
	<header>
		<div class="grow">
			{#if wishMode}
				<strong>Tilføj til ønskelisten</strong>
				<div class="muted small">Vælg alle de retter, I vil have i perioden</div>
			{:else}
				<strong>{forChild ? 'Barnets ret' : 'Aftensmad'}</strong>
				<div class="muted small">{weekdayName(date)} {shortDate(date)}</div>
			{/if}
		</div>
		<button class:primary={wishMode} onclick={oncancel}>{wishMode ? 'Færdig' : 'Luk'}</button>
	</header>

	<div class="tabs segmented" role="tablist">
		<button role="tab" aria-selected={tab === 'opskrift'} onclick={() => (tab = 'opskrift')}>Opskrift</button>
		{#if plan.wishlist.length && !wishMode}
			<button role="tab" aria-selected={tab === 'ønske'} onclick={() => (tab = 'ønske')}>Ønsker ({plan.wishlist.length})</button>
		{/if}
		{#if sources.length && !wishMode}
			<button role="tab" aria-selected={tab === 'rester'} onclick={() => (tab = 'rester')}>Rester</button>
		{/if}
		<button role="tab" aria-selected={tab === 'fritekst'} onclick={() => (tab = 'fritekst')}>Fritekst</button>
	</div>

	<div class="body">
		{#if error}<p class="error">{error}</p>{/if}

		{#if tab === 'opskrift'}
			<input type="search" bind:value={q} placeholder="Søg i jeres opskrifter og på Valdemarsro" aria-label="Søg" />
			<ul>
				{#each shown as r (r.id)}
					<li>
						<button
							class="option"
							disabled={wishMode && wished.has(r.id)}
							onclick={() => onchoose({ kind: 'opskrift', recipe_id: r.id })}
						>
							{#if r.image_url}<img src={r.image_url} alt="" loading="lazy" />{:else}<span class="noimg"></span>{/if}
							<span class="grow">
								<span class="title">{r.title}{#if wishMode && wished.has(r.id)} <span class="badge ok">på listen</span>{/if}</span>
								<span class="muted small">
									{[r.servings ? `${r.servings} pers.` : '', r.main_ingredients.length ? `★ ${r.main_ingredients.join(', ')}` : ''].filter(Boolean).join(' · ')}
								</span>
							</span>
						</button>
					</li>
				{:else}
					{#if recipes}<li class="muted empty-row">Ingen af jeres opskrifter matcher.</li>{/if}
				{/each}
			</ul>
			<!-- Ikke i jeres samling? Find den på Valdemarsro og vælg den med ét tryk. -->
			<ValdemarsroResults
				{q}
				haveLabel="Vælg"
				onpick={(id) => {
					if (!(wishMode && wished.has(id))) onchoose({ kind: 'opskrift', recipe_id: id });
					api<RecipeSummary[]>('/recipes').then((r) => (recipes = r)).catch(() => {});
				}}
			/>
		{:else if tab === 'ønske'}
			<ul>
				{#each plan.wishlist as w (w.id)}
					<li>
						<button class="option" onclick={() => onchoose({ kind: 'ønske', wish_id: w.id })}>
							{#if w.recipe?.image_url}<img src={w.recipe.image_url} alt="" />{:else}<span class="noimg"></span>{/if}
							<span class="grow title">{w.title}</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else if tab === 'rester'}
			<p class="muted small">Ingen indkøb. Skal der laves dobbelt, så sæt retten til ×2.</p>
			<ul>
				{#each sources as m (m.id)}
					<li>
						<button class="option" onclick={() => onchoose({ kind: 'rester', leftover_from_id: m.id })}>
							<span class="grow">
								<span class="title">Rester: {m.title}</span>
								<span class="muted small">{weekdayName(m.date)} · ×{m.multiplier === 0.5 ? '½' : m.multiplier}</span>
							</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else}
			<form onsubmit={submitText}>
				<input bind:value={text} placeholder={forChild ? 'Fx grød' : 'Fx pizza ude'} maxlength="200" aria-label="Ret" />
				<button class="primary" disabled={!text.trim()}>Vælg</button>
			</form>
			<div class="chips">
				{#each quick as t}
					<button onclick={() => onchoose({ kind: 'fritekst', text: t })}>{t}</button>
				{/each}
			</div>
			<p class="muted small">{wishMode ? 'Fritekst er en idé uden opskrift og giver ingen indkøb.' : 'Fritekst giver ingen indkøb.'}</p>
		{/if}
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 20;
		background: rgb(0 0 0 / 0.4);
	}
	.sheet {
		position: fixed;
		z-index: 21;
		left: 0;
		right: 0;
		bottom: 0;
		max-height: 88dvh;
		display: flex;
		flex-direction: column;
		background: var(--bg);
		border-radius: 16px 16px 0 0;
		padding: 12px max(16px, env(safe-area-inset-right)) env(safe-area-inset-bottom) max(16px, env(safe-area-inset-left));
		box-shadow: 0 -8px 32px rgb(0 0 0 / 0.25);
	}
	/* Tastaturet fremme: arket fylder pladsen over det, så søgefeltet og de
	   fundne retter kan ses. Uden dette ligger et kort ark gemt bag tastaturet. */
	:global(html.kb-open) .sheet {
		top: calc(env(safe-area-inset-top) + 8px);
		bottom: var(--kb);
		max-height: none;
		padding-bottom: 0;
	}
	@media (min-width: 700px) {
		/* iPad og computer: dialog midt på skærmen. */
		.sheet {
			left: 50%;
			right: auto;
			bottom: auto;
			top: 8dvh;
			width: min(560px, 92vw);
			max-height: calc(92dvh - var(--kb, 0px));
			transform: translateX(-50%);
			border-radius: 16px;
		}
		:global(html.kb-open) .sheet {
			top: 8dvh;
			bottom: auto;
			max-height: calc(92dvh - var(--kb));
		}
	}
	header {
		display: flex;
		align-items: center;
		gap: 12px;
		padding-bottom: 8px;
	}
	.tabs {
		margin-bottom: 4px;
	}
	/* Kun listen giver sig, når arket bliver lavt (fx over tastaturet). */
	header,
	.tabs {
		flex: none;
	}
	.body {
		flex: 1 1 auto;
		min-height: 0;
		overflow-y: auto;
		padding: 12px 0 16px;
		overscroll-behavior: contain;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 8px 0 0;
	}
	.option {
		width: 100%;
		border: none;
		border-bottom: 1px solid var(--line);
		border-radius: 0;
		background: none;
		padding: 8px 2px;
		gap: 12px;
		min-height: 56px;
	}
	.option img,
	.noimg {
		width: 48px;
		height: 48px;
		border-radius: 8px;
		object-fit: cover;
		flex: none;
		background: var(--accent-soft);
	}
	.option:disabled {
		opacity: 0.6;
	}
	.option .grow {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
	}
	.title {
		font-weight: 600;
	}
	form {
		display: flex;
		gap: 8px;
	}
	form input {
		flex: 1;
	}
	form button {
		flex: none;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
	}
	.empty-row {
		padding: 16px 0;
	}
</style>
