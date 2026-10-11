<script lang="ts">
	import { api } from '$lib/api';
	import { lastPlannedLabel, longDate } from '$lib/dates';
	import ExternalResults from '$lib/ExternalResults.svelte';
	import Fold from '$lib/Fold.svelte';
	import { searchKey } from '$lib/format';
	import { clock } from '$lib/resume.svelte';
	import { fetchSuggestions, type Suggestion } from '$lib/suggestions';
	import type { Plan, RecipeSummary, SlotChoice } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import { leftoverSources, lowerFirst } from './week.svelte';

	interface Props {
		plan: Plan;
		/** Dagen, der vælges til. Tom ved "wish": tilføj til ønskelisten. */
		date?: string;
		forChild?: boolean;
		/** "wish": vælg flere retter til ønskelisten. Arket bliver åbent. */
		mode?: 'slot' | 'wish';
		/** Åbn med søgefeltet klar. */
		focusSearch?: boolean;
		/** En sætning fra siden, når det valgte ikke kunne gemmes (arket er stadig åbent ved "wish"). */
		message?: string;
		onchoose: (choice: SlotChoice) => void;
		onclose: () => void;
	}
	let { plan, date = '', forChild = false, mode = 'slot', focusSearch = false, message = '', onchoose, onclose }: Props = $props();

	const wishMode = $derived(mode === 'wish');
	// Opskrifter, der allerede er på ønskelisten (kan ikke vælges igen).
	const wished = $derived(new Set(plan.wishlist.map((w) => w.recipe?.id).filter(Boolean)));

	let q = $state('');
	let text = $state('');
	let writing = $state(false);
	// Søgning bliver stående, til man selv går tilbage til forslagene. Ellers ville
	// listen skifte under fingeren, i det øjeblik feltet mister fokus.
	// svelte-ignore state_referenced_locally
	let searching = $state(focusSearch);
	let recipes = $state<RecipeSummary[] | null>(null);
	let suggestions = $state<Suggestion[] | null>(null);
	let error = $state('');

	const quick = $derived(
		wishMode ? ['Tacos', 'Pizza', 'Suppe', 'Fisk'] : forChild ? ['Grød', 'Mos', 'Rugbrød', 'Pasta'] : ['Pizza ude', 'Rugbrød', 'Takeaway', 'Spiser ude']
	);

	// Retter på tidligere dage, der kan give rester.
	const sources = $derived(wishMode ? [] : leftoverSources(plan, date));

	const shown = $derived((recipes ?? []).filter((r) => searchKey([r.title, ...r.ingredients].join(' ')).includes(searchKey(q))));
	const byId = $derived(new Map((recipes ?? []).map((r) => [r.id, r])));

	const loadRecipes = () => api<RecipeSummary[]>('/recipes').then((r) => (recipes = r));

	$effect(() => {
		loadRecipes().catch((e) => (error = say(e)));
	});

	// Forslagene hentes én gang, når arket åbnes. Uden svar vises gruppen bare ikke.
	$effect(() => {
		fetchSuggestions({ planId: plan.id, limit: 4 })
			.then((s) => (suggestions = s))
			.catch(() => {});
	});

	function submitText(e: SubmitEvent) {
		e.preventDefault();
		if (text.trim()) onchoose({ kind: 'fritekst', text: text.trim() });
		text = '';
		writing = false;
	}

	function pickExternal(id: number) {
		if (!(wishMode && wished.has(id))) onchoose({ kind: 'opskrift', recipe_id: id });
		// Opskriften er nu en af jeres egne.
		loadRecipes().catch(() => {});
	}

	/** "Valdemarsro · 4 pers." eller "Egen opskrift · 4 pers." */
	function wishMeta(recipeId: number | undefined, servings: number | null | undefined): string {
		if (!recipeId) return 'Idé uden opskrift';
		const host = byId.get(recipeId)?.source_host;
		const from = recipes ? (host ? host.replace(/^www\./, '') : 'Egen opskrift') : '';
		return [from, servings ? `${servings} pers.` : ''].filter(Boolean).join(' · ');
	}

	/** Feltet kommer frem, fordi man lige har bedt om det: giv det fokus. */
	function focusNow(node: HTMLElement) {
		node.focus();
	}

	function back() {
		searching = false;
		q = '';
	}
</script>

<Sheet
	title={wishMode ? 'Ønskeliste' : longDate(date)}
	eyebrow={wishMode ? 'Vælg de retter, I vil have i ugen' : forChild ? 'Barnets ret' : 'Aftensmad'}
	size="tall"
	initialFocus={focusSearch ? 'first' : 'none'}
	aside={wishMode ? done : undefined}
	{onclose}
>
	{#if message}<p class="msg" role="alert">{message}</p>{/if}
	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	{#if searching || q.trim()}
		<button type="button" class="kv back" onclick={back}>
			<span class="k"><Icon name="left" size={16} stroke={2.2} />Forslag</span>
		</button>
		<!-- Under søgning: lukkede afsnit med antal, der foldes ud ved tryk. Uden tekst vises alle egne. -->
		{#if q.trim()}
			<Fold title="Egne opskrifter" count={shown.length}>{@render own()}</Fold>
		{:else}
			{@render own()}
		{/if}
		<!-- Ikke i jeres samling? Find den på Valdemarsro eller nemlig.com, og vælg den med ét tryk. -->
		<ExternalResults site="valdemarsro" {q} haveLabel="Vælg" onpick={pickExternal} />
		<ExternalResults site="nemlig" {q} haveLabel="Vælg" onpick={pickExternal} />
	{:else}
		{#if !wishMode && plan.wishlist.length}
			<p class="sl">Fra ønskelisten</p>
			{#each plan.wishlist as w (w.id)}
				<button type="button" class="op" onclick={() => onchoose({ kind: 'ønske', wish_id: w.id })}>
					{#if w.recipe}<Plate src={w.recipe.image_url} seed={w.recipe.id} size={44} lazy />{/if}
					<span class="grow">
						<span class="n">{w.title}</span>
						<span class="m">{wishMeta(w.recipe?.id, w.recipe?.servings)}</span>
					</span>
					<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>
				</button>
			{/each}
		{/if}

		{#if suggestions?.length}
			<p class="sl">Længe siden</p>
			{#each suggestions as s (s.recipe.id)}
				{@const taken = wishMode && wished.has(s.recipe.id)}
				<button type="button" class="op" disabled={taken} onclick={() => onchoose({ kind: 'opskrift', recipe_id: s.recipe.id })}>
					<Plate src={s.recipe.image_url} seed={s.recipe.id} size={44} lazy />
					<span class="grow">
						<span class="n">{s.recipe.title}</span>
						<span class="m">{lastPlannedLabel(s.last_planned, clock.today)}</span>
					</span>
					{#if taken}<span class="tag">på listen</span>{:else}<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>{/if}
				</button>
			{/each}
		{/if}

		<p class="sl">{wishMode ? 'Idéer uden opskrift' : 'Uden indkøb'}</p>
		{#if writing}
			<form class="write pad" onsubmit={submitText}>
				<input bind:value={text} placeholder={forChild ? 'Fx grød' : 'Fx pizza ude'} maxlength="200" aria-label="Ret" use:focusNow />
				<button class="btn primary" disabled={!text.trim()}>Vælg</button>
				<button type="button" class="btn quiet" onclick={() => (writing = false)}>Fortryd</button>
			</form>
		{:else}
			<div class="chips pad">
				{#each sources as m (m.id)}
					<button type="button" class="chip" onclick={() => onchoose({ kind: 'rester', leftover_from_id: m.id })}>
						<span class="ellipsis">Rester fra {lowerFirst(m.title)}</span>
					</button>
				{/each}
				{#each quick as t}
					<button type="button" class="chip" onclick={() => onchoose({ kind: 'fritekst', text: t })}>{t}</button>
				{/each}
				<button type="button" class="chip" onclick={() => (writing = true)}>Skriv selv</button>
			</div>
		{/if}

		<button type="button" class="kv all" onclick={() => (searching = true)}>
			<span class="k">Alle opskrifter</span>
			{#if recipes}<span class="tag">{recipes.length}</span>{/if}
		</button>
	{/if}

	{#snippet footer()}
		<label class="find">
			<Icon name="search" stroke={2.2} />
			<input type="search" bind:value={q} placeholder="Søg i egne, Valdemarsro og nemlig" aria-label="Søg" onfocus={() => (searching = true)} />
		</label>
	{/snippet}
</Sheet>

{#snippet done(close: () => void)}
	<button type="button" class="btn sm primary" onclick={close}>Færdig</button>
{/snippet}

{#snippet own()}
	{#each shown as r (r.id)}
		{@const taken = wishMode && wished.has(r.id)}
		<button type="button" class="op" disabled={taken} onclick={() => onchoose({ kind: 'opskrift', recipe_id: r.id })}>
			<Plate src={r.image_url} seed={r.id} size={44} lazy />
			<span class="grow">
				<span class="n">{r.title}</span>
				<span class="m">{[r.servings ? `${r.servings} pers.` : '', r.main_ingredients.join(', ')].filter(Boolean).join(' · ')}</span>
			</span>
			{#if taken}<span class="tag">på listen</span>{:else}<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>{/if}
		</button>
	{:else}
		{#if recipes}<p class="muted small none">{q.trim() ? 'Ingen af jeres opskrifter passer.' : 'I har ingen opskrifter endnu.'}</p>{/if}
	{/each}
{/snippet}

<style>
	.op .n,
	.op .m {
		display: block;
	}
	.op:disabled {
		cursor: default;
	}
	.op:disabled .n {
		color: var(--muted);
	}
	.chips {
		padding-block: 4px 6px;
	}
	.write {
		display: flex;
		gap: 8px;
		padding-block: 4px 6px;
	}
	.write input {
		flex: 1;
	}
	.write .btn {
		flex: none;
		height: 48px;
	}
	.all {
		margin-top: 10px;
	}
	.back .k {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--muted);
	}
	.none {
		margin: 12px var(--gutter);
	}
	/* Søgefeltet med lup: feltet selv er uden baggrund, så de to ses som ét. */
	.find {
		display: flex;
		align-items: center;
		gap: 10px;
		padding-left: 14px;
		border-radius: var(--r-control);
		background: var(--band);
		color: var(--muted);
	}
	.find input {
		padding-left: 0;
		background: none;
	}
	.find:focus-within {
		outline: 2px solid var(--ink);
	}
	.find input:focus-visible {
		outline: none;
	}
</style>
