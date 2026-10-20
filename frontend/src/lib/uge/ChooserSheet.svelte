<script lang="ts">
	import { untrack } from 'svelte';
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
		/** Der vælges en ekstra ret til dagen (ved siden af hovedretten). */
		extra?: boolean;
		/** "wish": vælg flere retter til ønskelisten. Arket bliver åbent. */
		mode?: 'slot' | 'wish';
		/** Åbn med søgefeltet klar. */
		focusSearch?: boolean;
		/** En sætning fra siden, når det valgte ikke kunne gemmes (arket er stadig åbent ved "wish"). */
		message?: string;
		onchoose: (choice: SlotChoice) => void;
		onclose: () => void;
	}
	let { plan, date = '', extra = false, mode = 'slot', focusSearch = false, message = '', onchoose, onclose }: Props = $props();

	const wishMode = $derived(mode === 'wish');
	// Ønsker, der er trykket på, men som serveren ikke har svaret på endnu. De vises
	// som "på listen" med det samme, så det ses, at trykket virkede (og ikke trykkes igen).
	let pending = $state<string[]>([]);
	// Den seneste ret, der er lagt på ønskelisten. Vises nederst i arket.
	let added = $state('');
	const recipeKey = (id: number) => `r:${id}`;
	const textKey = (t: string) => `t:${t.trim().toLocaleLowerCase('da')}`;
	// Ønsker på listen (og dem på vej): opskrifter og idéer uden opskrift. Kan ikke vælges igen.
	const wished = $derived(
		new Set([...plan.wishlist.map((w) => (w.recipe ? recipeKey(w.recipe.id) : textKey(w.text))), ...pending])
	);
	const isWished = (id: number) => wishMode && wished.has(recipeKey(id));
	// Gik det ikke, er ønskerne alligevel ikke på listen.
	$effect(() => {
		if (message) pending = [];
	});
	// Opskrifter, der allerede ligger på dagene i ugen. Ikke med, når der vælges til en dag.
	const onPlan = $derived(
		new Set(wishMode ? [] : plan.days.flatMap((d) => [d.meal, ...d.extras].map((m) => m?.recipe?.id)).filter(Boolean))
	);

	/** Vælger. På ønskelisten markeres retten med det samme, og arket bliver åbent. */
	function pick(choice: SlotChoice, title: string) {
		if (wishMode) {
			const key = choice.kind === 'opskrift' ? recipeKey(choice.recipe_id) : choice.kind === 'fritekst' ? textKey(choice.text) : '';
			if (!key || wished.has(key)) return;
			pending = [...pending, key];
			added = title;
		}
		onchoose(choice);
	}

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
		wishMode ? ['Tacos', 'Pizza', 'Suppe', 'Fisk'] : extra ? ['Grød', 'Salat', 'Rugbrød', 'Pasta'] : ['Pizza ude', 'Rugbrød', 'Takeaway', 'Spiser ude']
	);

	// Retter på tidligere dage, der kan give rester.
	const sources = $derived(wishMode ? [] : leftoverSources(plan, date));

	const shown = $derived((recipes ?? []).filter((r) => searchKey([r.title, ...r.ingredients].join(' ')).includes(searchKey(q))));
	const byId = $derived(new Map((recipes ?? []).map((r) => [r.id, r])));
	// Favoritter, der ikke allerede er på ugen. Højst otte, sorteret efter titel.
	const favorites = $derived(
		(recipes ?? [])
			.filter((r) => r.favorite && !onPlan.has(r.id))
			.sort((a, b) => a.title.localeCompare(b.title, 'da'))
			.slice(0, 8)
	);

	const loadRecipes = () => api<RecipeSummary[]>('/recipes').then((r) => (recipes = r));

	$effect(() => {
		loadRecipes().catch((e) => (error = say(e)));
	});

	// Forslagene hentes én gang, når arket åbnes. Uden svar vises gruppen bare ikke.
	// (Ikke igen, når planen ændrer sig: så forsvinder det, der lige er trykket på,
	// i stedet for at stå der som "på listen".)
	$effect(() => {
		fetchSuggestions({ planId: untrack(() => plan.id), limit: 4 })
			.then((s) => (suggestions = s))
			.catch(() => {});
	});

	function submitText(e: SubmitEvent) {
		e.preventDefault();
		if (text.trim()) pick({ kind: 'fritekst', text: text.trim() }, text.trim());
		text = '';
		writing = false;
	}

	function pickExternal(id: number) {
		pick({ kind: 'opskrift', recipe_id: id }, byId.get(id)?.title ?? 'Retten');
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
	eyebrow={wishMode ? 'Vælg de retter, I vil have i ugen' : extra ? 'Ekstra ret' : 'Aftensmad'}
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

		{#if favorites.length}
			<p class="sl">Favoritter</p>
			{#each favorites as r (r.id)}
				{@const taken = isWished(r.id)}
				<button type="button" class="op" disabled={taken} onclick={() => pick({ kind: 'opskrift', recipe_id: r.id }, r.title)}>
					<Plate src={r.image_url} seed={r.id} size={44} lazy />
					<span class="grow">
						<span class="n">{r.title}</span>
						<span class="m">{r.main_ingredients.join(', ')}</span>
					</span>
					{#if taken}<span class="tag">på listen</span>{:else}<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>{/if}
				</button>
			{/each}
		{/if}

		{#if suggestions?.length}
			<p class="sl">Længe siden</p>
			{#each suggestions as s (s.recipe.id)}
				{@const taken = isWished(s.recipe.id)}
				<button type="button" class="op" disabled={taken} onclick={() => pick({ kind: 'opskrift', recipe_id: s.recipe.id }, s.recipe.title)}>
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
				<input bind:value={text} placeholder={wishMode ? 'Fx lasagne' : extra ? 'Fx grød' : 'Fx pizza ude'} maxlength="200" aria-label="Ret" use:focusNow />
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
					{@const taken = wishMode && wished.has(textKey(t))}
					<button type="button" class="chip" class:on={taken} disabled={taken} onclick={() => pick({ kind: 'fritekst', text: t }, t)}>
						{#if taken}<Icon name="check" size={15} stroke={2.4} />{/if}{t}
					</button>
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
		<!-- Ønskelisten: en rolig bekræftelse af det seneste tryk. -->
		{#if wishMode}
			<p class="added small" role="status">
				{#if added}<Icon name="check" size={15} stroke={2.4} />{added} er på ønskelisten · {plan.wishlist.length} i alt{/if}
			</p>
		{/if}
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
		{@const taken = isWished(r.id)}
		<button type="button" class="op" disabled={taken} onclick={() => pick({ kind: 'opskrift', recipe_id: r.id }, r.title)}>
			<Plate src={r.image_url} seed={r.id} size={44} lazy />
			<span class="grow">
				<span class="n">{r.title}</span>
				<span class="m">{[r.servings ? `${r.servings} pers.` : '', r.total_minutes ? `${r.total_minutes} min` : '', r.main_ingredients.join(', ')].filter(Boolean).join(' · ')}</span>
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
	/* Allerede på listen: den udfyldte chip med flueben, ikke den falmede. */
	.chip.on:disabled {
		gap: 4px;
		opacity: 1;
	}
	.added {
		display: flex;
		align-items: center;
		gap: 6px;
		min-height: 22px;
		margin-bottom: 8px;
		color: var(--kobt);
	}
	.added:empty {
		display: none;
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
