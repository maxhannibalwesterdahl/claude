<script lang="ts">
	import { api } from './api';
	import ExternalResults from './ExternalResults.svelte';
	import Fold from './Fold.svelte';
	import { shortDate, weekdayName } from './dates';
	import { mult, searchKey } from './format';
	import Thumb from './Thumb.svelte';
	import type { Meal, Plan, RecipeSummary, SlotChoice } from './types';

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

	// showModal() flytter fokus ind i arket, holder Tab inde i det og lukker på
	// Escape. Når arket lukkes, får knappen, der åbnede det, fokus igen.
	let dialog: HTMLDialogElement | undefined = $state();
	$effect(() => {
		const el = dialog;
		if (!el) return;
		const opener = document.activeElement;
		el.showModal();
		return () => {
			el.close();
			if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
		};
	});

	function pickExternal(id: number) {
		if (!(wishMode && wished.has(id))) onchoose({ kind: 'opskrift', recipe_id: id });
		api<RecipeSummary[]>('/recipes').then((r) => (recipes = r)).catch(() => {});
	}
</script>

<!-- Klik på den mørke baggrund (dialogen selv, uden for indholdet) lukker. Tastaturet har Escape og Luk-knappen. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog
	bind:this={dialog}
	class="sheet"
	aria-labelledby="chooser-title"
	onclick={(e) => e.target === dialog && oncancel()}
	oncancel={(e) => {
		e.preventDefault();
		oncancel();
	}}
>
	<div class="inner">
	<header>
		<div class="grow">
			{#if wishMode}
				<h2 id="chooser-title">Tilføj til ønskelisten</h2>
				<div class="muted small">Vælg alle de retter, I vil have i perioden</div>
			{:else}
				<h2 id="chooser-title">{forChild ? 'Barnets ret' : 'Aftensmad'}</h2>
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
		{#if error}<p class="error" role="alert">{error}</p>{/if}

		{#if tab === 'opskrift'}
			<input type="search" bind:value={q} placeholder="Søg i jeres opskrifter, på Valdemarsro og nemlig.com" aria-label="Søg" />
			{#snippet own()}
			<ul>
				{#each shown as r (r.id)}
					<li>
						<button
							class="option"
							disabled={wishMode && wished.has(r.id)}
							onclick={() => onchoose({ kind: 'opskrift', recipe_id: r.id })}
						>
							<Thumb src={r.image_url} size="sm" lazy />
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
			{/snippet}
			<!-- Under søgning: tre lukkede afsnit med antal, der foldes ud ved tryk. -->
			{#if q.trim()}
				<Fold title="Egne opskrifter" count={shown.length}>{@render own()}</Fold>
			{:else}
				{@render own()}
			{/if}
			<!-- Ikke i jeres samling? Find den på Valdemarsro eller nemlig.com og vælg den med ét tryk. -->
			<ExternalResults site="valdemarsro" {q} haveLabel="Vælg" onpick={pickExternal} />
			<ExternalResults site="nemlig" {q} haveLabel="Vælg" onpick={pickExternal} />
		{:else if tab === 'ønske'}
			<ul>
				{#each plan.wishlist as w (w.id)}
					<li>
						<button class="option" onclick={() => onchoose({ kind: 'ønske', wish_id: w.id })}>
							<Thumb src={w.recipe?.image_url} size="sm" />
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
								<span class="muted small">{weekdayName(m.date)} · {mult(m.multiplier)}</span>
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
</dialog>

<style>
	/* Telefon: ark fra bunden af skærmen. Browserens egne dialog-mål nulstilles. */
	.sheet {
		position: fixed;
		inset: auto 0 0 0;
		width: 100%;
		max-width: none;
		max-height: 88dvh;
		margin: 0;
		padding: 0;
		border: none;
		overflow: hidden;
		color: var(--fg);
		background: var(--bg);
		border-radius: var(--radius-sheet) var(--radius-sheet) 0 0;
		box-shadow: var(--shadow-sheet);
	}
	.sheet::backdrop {
		background: var(--scrim);
	}
	.inner {
		display: flex;
		flex-direction: column;
		max-height: inherit;
		padding: 12px max(16px, env(safe-area-inset-right)) env(safe-area-inset-bottom) max(16px, env(safe-area-inset-left));
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
			inset: 8dvh auto auto 50%;
			width: min(560px, 92vw);
			max-height: calc(92dvh - var(--kb, 0px));
			transform: translateX(-50%);
			border-radius: var(--radius-sheet);
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
	h2 {
		margin: 0;
		font-size: 1rem;
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
	/* "Allerede på listen" er stadig oplysning: teksten dæmpes, men kan læses. */
	.option:disabled {
		opacity: 1;
	}
	.option:disabled .title {
		color: var(--muted);
	}
	.option:disabled :global(img) {
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
