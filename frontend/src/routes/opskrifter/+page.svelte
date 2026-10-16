<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { lastPlannedLabel } from '$lib/dates';
	import { searchKey } from '$lib/format';
	import { clock } from '$lib/resume.svelte';
	import { refreshReviewCount, reviewCount } from '$lib/review.svelte';
	import { fetchSuggestions, type Suggestion } from '$lib/suggestions';
	import ExternalResults from '$lib/ExternalResults.svelte';
	import Fold from '$lib/Fold.svelte';
	import AddSheet from '$lib/opskrifter/AddSheet.svelte';
	import RecipeTile from '$lib/opskrifter/RecipeTile.svelte';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import type { Plan, RecipeSummary, TagCount } from '$lib/types';

	/** "tid" = under 30 minutter, "maerke:<mærke>" = familiens eget mærke. */
	type Filter = 'alle' | 'favoritter' | 'onsker' | 'laenge' | 'tid' | `maerke:${string}`;

	/** Filteret fra ?filter=, eller "alle", hvis det ikke kendes. */
	function fromUrl(f: string | null): Filter {
		if (f === 'favoritter' || f === 'onsker' || f === 'laenge' || f === 'tid') return f;
		return f?.startsWith('maerke:') && f.length > 7 ? (f as Filter) : 'alle';
	}
	const tagOf = (f: Filter): string | null => (f.startsWith('maerke:') ? f.slice(7) : null);

	let recipes = $state<RecipeSummary[] | null>(null);
	let error = $state('');
	let q = $state('');
	let adding = $state(false);
	// ?filter=favoritter|onsker|laenge|tid|maerke:<mærke> vælger et filter fra start.
	let filter = $state<Filter>(untrack(() => fromUrl(page.url.searchParams.get('filter'))));
	/** Familiens mærker med antal (til chips). */
	let tagCounts = $state<TagCount[]>([]);
	const hasTime = $derived((recipes ?? []).some((r) => r.total_minutes !== null));
	/** Opskrifter på ønskelisten i den aktuelle uge. null = der er ingen uge (filteret vises ikke). */
	let wished = $state<Set<number> | null>(null);
	/** Opskrifterne, længst siden først. null eller tom = filteret vises ikke. */
	let longAgo = $state<Suggestion[] | null>(null);

	const favCount = $derived((recipes ?? []).filter((r) => r.favorite).length);

	// Et filter, der ikke findes (endnu), tæller som "Alle".
	const active = $derived<Filter>(
		(filter === 'favoritter' && !favCount) ||
			(filter === 'onsker' && !wished) ||
			(filter === 'laenge' && !longAgo?.length) ||
			(filter === 'tid' && !hasTime) ||
			(!!tagOf(filter) && !tagCounts.some((t) => t.tag === tagOf(filter)))
			? 'alle'
			: filter
	);
	const lastPlanned = $derived(new Map((longAgo ?? []).map((s) => [s.recipe.id, s.last_planned])));

	const filtered = $derived.by(() => {
		const all = recipes ?? [];
		if (active === 'favoritter') return all.filter((r) => r.favorite);
		if (active === 'onsker') return all.filter((r) => wished?.has(r.id));
		if (active === 'laenge') {
			const byId = new Map(all.map((r) => [r.id, r]));
			return (longAgo ?? []).flatMap((s) => byId.get(s.recipe.id) ?? []);
		}
		if (active === 'tid') return all.filter((r) => r.total_minutes !== null && r.total_minutes <= 30);
		const tag = tagOf(active);
		if (tag) return all.filter((r) => r.tags.includes(tag));
		return all;
	});
	// Søger i titel og alle varer, så "kylling" også finder retter med kylling i.
	const shown = $derived(
		filtered.filter((r) => searchKey([r.title, ...r.ingredients].join(' ')).includes(searchKey(q)))
	);

	function meta(r: RecipeSummary): string {
		if (wished?.has(r.id)) return 'På ønskelisten';
		if (active === 'laenge') return lastPlannedLabel(lastPlanned.get(r.id) ?? null, clock.today);
		return [r.main_ingredients.join(', '), r.source_host].filter(Boolean).join(' · ');
	}

	/** Delte opskrifter, familien ikke har i sin samling endnu. Hentes første gang, der søges. */
	let shared = $state<RecipeSummary[] | null>(null);
	$effect(() => {
		if (q.trim().length >= 2 && shared === null) {
			untrack(() => {
				api<RecipeSummary[]>('/recipes?alle=true')
					.then((r) => (shared = r.filter((x) => !x.in_collection)))
					.catch(() => (shared = []));
			});
		}
	});
	const sharedShown = $derived(
		(shared ?? []).filter((r) => searchKey([r.title, ...r.ingredients].join(' ')).includes(searchKey(q)))
	);

	function loadRecipes() {
		shared = null;
		return api<RecipeSummary[]>('/recipes')
			.then((r) => (recipes = r))
			.catch((e) => (error = say(e)));
	}

	$effect(() => {
		untrack(() => {
			loadRecipes();
			refreshReviewCount().catch(() => {});
			// Uden en uge (404) er der ingen ønskeliste at filtrere på.
			api<Plan>(`/plans/current?today=${clock.today}`)
				.then((p) => (wished = new Set(p.wishlist.flatMap((w) => (w.recipe ? [w.recipe.id] : [])))))
				.catch(() => (wished = null));
			fetchSuggestions({ limit: 500 })
				.then((s) => (longAgo = s))
				.catch(() => (longAgo = null));
			api<TagCount[]>('/tags')
				.then((t) => (tagCounts = t))
				.catch(() => (tagCounts = []));
		});
	});

	// Filteret skrives i adressen, så det er der, næste gang siden åbnes.
	function setFilter(f: Filter) {
		filter = f;
		goto(f === 'alle' ? page.url.pathname : `?filter=${encodeURIComponent(f)}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	// Fra Valdemarsro og nemlig.com: ny import bliver på listen (og dukker op i jeres egne); en,
	// vi allerede har, åbnes.
	function picked(id: number, imported: boolean) {
		if (imported) loadRecipes();
		else goto(`/opskrift/${id}`);
	}
</script>

<main class="docked">
	<ScreenHeader title="Opskrifter" eyebrow={recipes ? (recipes.length === 1 ? '1 opskrift' : `${recipes.length} opskrifter`) : undefined}>
		{#snippet actions()}
			<!-- Ryd op rummer også indstillinger og Log ud, så den kan altid nås. -->
			{#if reviewCount.value > 0}
				<a class="chip a" href="/rydop">Ryd op · {reviewCount.value}</a>
			{:else}
				<a class="rnd" href="/rydop" aria-label="Ryd op"><Icon name="list" /></a>
			{/if}
		{/snippet}
	</ScreenHeader>

	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	{#if recipes}
		<div class="search pad">
			<Icon name="search" />
			<input type="search" placeholder="Søg i egne, Valdemarsro og nemlig" bind:value={q} aria-label="Søg i opskrifter" />
		</div>

		{#if recipes.length > 0 && (wished || longAgo?.length || favCount || hasTime || tagCounts.length)}
			<div class="chips pad filters" role="group" aria-label="Vis">
				<button type="button" class="chip" aria-pressed={active === 'alle'} onclick={() => setFilter('alle')}>Alle</button>
				{#if favCount}
					<button type="button" class="chip" aria-pressed={active === 'favoritter'} onclick={() => setFilter('favoritter')}>
						Favoritter · {favCount}
					</button>
				{/if}
				{#if wished}
					<button type="button" class="chip" aria-pressed={active === 'onsker'} onclick={() => setFilter('onsker')}>
						Ønskeliste · {wished.size}
					</button>
				{/if}
				{#if longAgo?.length}
					<button type="button" class="chip" aria-pressed={active === 'laenge'} onclick={() => setFilter('laenge')}>Længe siden</button>
				{/if}
				{#if hasTime}
					<button type="button" class="chip" aria-pressed={active === 'tid'} onclick={() => setFilter('tid')}>Under 30 min</button>
				{/if}
				{#each tagCounts.slice(0, 8) as t (t.tag)}
					<button type="button" class="chip" aria-pressed={tagOf(active) === t.tag} onclick={() => setFilter(`maerke:${t.tag}`)}>{t.tag}</button>
				{/each}
			</div>
		{/if}
	{/if}

	{#snippet own()}
		{#if shown.length}
			<ul class="grid2">
				{#each shown as r (r.id)}
					<li><RecipeTile recipe={r} meta={meta(r)} /></li>
				{/each}
			</ul>
		{:else if q.trim()}
			<p class="none muted">Ingen af jeres opskrifter matcher "{q.trim()}".</p>
		{:else if active === 'favoritter'}
			<p class="none muted">Der er ingen favoritter endnu.</p>
		{:else if active === 'onsker'}
			<p class="none muted">Der er ingen opskrifter på ønskelisten.</p>
		{:else if active === 'tid'}
			<p class="none muted">Ingen opskrifter under 30 minutter.</p>
		{:else if tagOf(active)}
			<p class="none muted">Ingen opskrifter med mærket "{tagOf(active)}".</p>
		{/if}
	{/snippet}

	<!-- Under søgning: tre lukkede afsnit med antal, der foldes ud ved tryk. -->
	{#if recipes && recipes.length > 0}
		{#if q.trim()}
			<Fold title="Egne opskrifter" count={shown.length}>{@render own()}</Fold>
		{:else}
			{@render own()}
		{/if}
	{/if}

	{#if q.trim() && sharedShown.length}
		<Fold title="Delte opskrifter" count={sharedShown.length}>
			<ul class="grid2">
				{#each sharedShown as r (r.id)}
					<li><RecipeTile recipe={r} meta="Fra en anden familie" /></li>
				{/each}
			</ul>
		</Fold>
	{/if}

	<ExternalResults site="valdemarsro" {q} onpick={picked} />
	<ExternalResults site="nemlig" {q} onpick={picked} />

	{#if recipes && recipes.length === 0 && q.trim().length < 3}
		<div class="empty">
			<p>Der er ingen opskrifter endnu.</p>
			<div class="btns first">
				<a class="btn primary" href="/importer">Importér fra link</a>
				<a class="btn" href="/ny">Skriv selv</a>
			</div>
		</div>
	{/if}

	<button type="button" class="fab" aria-label="Ny opskrift" onclick={() => (adding = true)}><Icon name="plus" size={26} stroke={2.4} /></button>
</main>

{#if adding}<AddSheet onclose={() => (adding = false)} />{/if}

<style>
	/* Søgefeltet med et lille forstørrelsesglas i. */
	.search {
		position: relative;
		margin-top: 4px;
	}
	.search :global(svg) {
		position: absolute;
		left: calc(max(var(--gutter), env(safe-area-inset-left)) + 14px);
		top: 50%;
		transform: translateY(-50%);
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		padding-left: 42px;
	}
	.filters {
		margin-top: 12px;
	}
	ul {
		list-style: none;
		margin: 14px 0 8px;
		padding-block: 0;
	}
	li {
		display: grid;
	}
	.none {
		padding: 16px var(--gutter);
	}
	.first {
		margin-top: 16px;
	}
</style>
