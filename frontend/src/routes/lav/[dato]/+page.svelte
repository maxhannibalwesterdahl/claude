<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { api } from '$lib/api';
	import { navState } from '$lib/nav.svelte';
	import { clock, onResume } from '$lib/resume.svelte';
	import { longDate, weekdayName } from '$lib/dates';
	import { formatQuantity, mult } from '$lib/format';
	import { groupLines } from '$lib/lines';
	import { groupSteps } from '$lib/steps';
	import { say } from '$lib/ui/copy';
	import Hero from '$lib/ui/Hero.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import IngredientRow from '$lib/ui/IngredientRow.svelte';
	import StepView, { type Step } from '$lib/lav/StepView.svelte';
	import { wakeLock } from '$lib/lav/wakeLock.svelte';
	import type { Plan, PlanBrief, Recipe } from '$lib/types';

	let plan = $state<Plan | null>(null);
	let recipes = $state<Record<number, Recipe>>({});
	let error = $state('');
	/** Datoen, der sidst er hentet færdig. */
	let loadedFor = $state('');

	const date = $derived(page.params.dato ?? '');
	const loaded = $derived(loadedFor === date);
	const day = $derived(plan?.days.find((d) => d.date === date) ?? null);
	const main = $derived(day?.meal ?? null);
	const recipe = $derived(main?.recipe ? recipes[main.recipe.id] : undefined);

	/** Planen, der dækker datoen. Genbruges, når man går til en anden dag i samme
	 *  plan, medmindre `fresh` (appen er åbnet igen, og planen kan være ændret). */
	async function load(d: string, fresh = false) {
		error = '';
		try {
			let current = untrack(() => plan);
			if (fresh || !current || !current.days.some((x) => x.date === d)) {
				const plans = await api<PlanBrief[]>('/plans');
				const hit = plans.find((p) => p.start_date <= d && d <= p.end_date);
				current = hit ? await api<Plan>(`/plans/${hit.id}`) : null;
				// Brugeren kan være gået videre imens: vis kun svaret for den dag, der vises nu.
				if (d !== untrack(() => date)) return;
				plan = current;
			}
			const meals = current?.days.find((x) => x.date === d);
			const known = untrack(() => recipes);
			const missing = [meals?.meal, meals?.child]
				.map((m) => m?.recipe?.id)
				.filter((id): id is number => !!id && (fresh || !known[id]));
			const fetched = await Promise.all(missing.map((id) => api<Recipe>(`/recipes/${id}`)));
			for (const r of fetched) recipes[r.id] = r;
		} catch (e) {
			error = say(e);
		} finally {
			if (d === untrack(() => date)) loadedFor = d;
		}
	}

	$effect(() => {
		const d = date;
		untrack(() => load(d));
	});

	$effect(() => onResume(() => untrack(() => load(date, true))));

	// Skærmen holdes tændt på hele siden, også i oversigten.
	$effect(() => wakeLock.hold());

	// Fremgangsmåden som en række trin. Overskrifter ("Mornaysauce") er ikke trin
	// og tælles ikke med. En overskrift uden noget under sig er et kort trin, der
	// bare mangler punktum ("Server med ris"), og vises som et trin.
	const steps = $derived.by(() => {
		const out: Step[] = [];
		for (const g of groupSteps(recipe?.instructions ?? [])) {
			if (!g.steps.length) out.push({ text: g.title, heading: '' });
			for (const text of g.steps) out.push({ text, heading: g.title });
		}
		return out;
	});

	// ?trin=3 er trin 3. Over antallet: det sidste. Mangler, 0 eller ikke et tal: oversigten.
	const trin = $derived.by(() => {
		const raw = page.url.searchParams.get('trin') ?? '';
		return /^\d+$/.test(raw) ? Number(raw) : 0;
	});
	const index = $derived(trin > 0 && main?.kind === 'opskrift' && steps.length ? Math.min(trin, steps.length) - 1 : null);

	// Alle skift mellem trin erstatter adressen, så hele "Lav mad" er ét skridt
	// i historikken: ét "tilbage" forlader det.
	const toStep = (n: number) => goto(`?trin=${n}`, { replaceState: true, noScroll: true, keepFocus: true });
	const toOverview = () => goto(page.url.pathname, { replaceState: true });

	// Forlad "Lav mad": tilbage til siden, man kom fra (ugen), ellers til ugen
	// med retten. Tilbage-knappen på billedet gør det samme.
	const weekUrl = $derived(plan ? `/?plan=${plan.id}` : '/');
	function leave() {
		if (navState.inApp) history.back();
		else goto(weekUrl, { replaceState: true });
	}

	// "Find frem": kryds, der kun findes på denne telefon. De gemmes, så de
	// overlever en genindlæsning, men sendes aldrig til serveren og har intet
	// med "har hjemme" at gøre.
	let found = $state<Record<number, boolean>>({});
	const storeKey = $derived(main ? `madplan.findfrem.${main.id}` : '');
	$effect(() => {
		const key = storeKey;
		let ids: unknown = [];
		try {
			ids = JSON.parse((key && sessionStorage.getItem(key)) || '[]');
		} catch {
			// Ulæselig eller utilgængelig hukommelse: begynd forfra.
		}
		found = Object.fromEntries((Array.isArray(ids) ? ids : []).map((id) => [id, true]));
	});
	function tick(lineId: number, next: boolean) {
		found[lineId] = next;
		try {
			const ids = Object.keys(found).filter((id) => found[Number(id)]).map(Number);
			sessionStorage.setItem(storeKey, JSON.stringify(ids));
		} catch {
			// Krydset står stadig på skærmen.
		}
	}
	const lines = $derived(main?.lines ?? []);
	const foundCount = $derived(lines.filter((l) => found[l.line_id]).length);

	const isToday = $derived(date === clock.today);
	const scaled = $derived(!!main && main.multiplier !== 1);
	const persons = $derived(main?.recipe?.servings ? `${Math.round(main.recipe.servings * main.multiplier)} pers.` : '');
	/** Kun rigtige links (http/https) vises og kan følges. */
	const sourceUrl = $derived(recipe?.source_url && /^https?:\/\//i.test(recipe.source_url) ? recipe.source_url : '');
	const host = $derived.by(() => {
		try {
			return sourceUrl ? new URL(sourceUrl).hostname.replace(/^www\./, '') : '';
		} catch {
			return '';
		}
	});
	const meta = $derived([persons, steps.length ? `${steps.length} trin` : '', host ? `fra ${host}` : ''].filter(Boolean).join(' · '));

	const wide = new MediaQuery('(min-width: 900px)');
	const pinned = $derived(index === null && loaded && main?.kind === 'opskrift' && steps.length > 0 && !wide.current);
</script>

{#snippet when()}
	<p class="lab">{isToday ? `I aften · ${weekdayName(date)}` : longDate(date)}</p>
{/snippet}

{#snippet ingredients()}
	{#each groupLines(lines) as g}
		{#if g.name}<p class="pad group">{g.name}</p>{/if}
		{#each g.lines as l (l.line_id)}
			<IngredientRow
				qty={formatQuantity(l.quantity, l.quantity_max, l.unit)}
				name={l.item}
				note={l.note}
				dim={l.state === 'rest'}
				checked={!!found[l.line_id]}
				ontoggle={(next) => tick(l.line_id, next)}
				tickLabel="fundet frem"
			>
				{#snippet trailing()}
					{#if l.state === 'rest'}<span class="tag">rest</span>{/if}
				{/snippet}
			</IngredientRow>
		{/each}
	{/each}
	{#if scaled && main}
		<p class="pad muted small caption">Mængderne er ganget med {mult(main.multiplier).slice(1)}.</p>
	{/if}
{/snippet}

{#snippet childNotes()}
	{#if recipe?.child_note}<p class="note"><b>Barnet:</b> {recipe.child_note}</p>{/if}
	{#if day?.child}
		<p class="note">
			<b>Barnet får:</b>
			{#if day.child.recipe}<a class="link" href="/opskrift/{day.child.recipe.id}">{day.child.title}</a>{:else}{day.child.title}{/if}
		</p>
	{/if}
{/snippet}

{#snippet start()}
	<button type="button" class="btn primary block start" onclick={() => toStep(1)}>
		<Icon name="play" size={17} />Start · {steps.length} trin
	</button>
{/snippet}

<main class:step={index !== null} class:pinned>
	{#if index !== null && main}
		<StepView
			title={main.title}
			{steps}
			{index}
			found={foundCount}
			total={lines.length}
			{scaled}
			awake={wakeLock.active}
			ongo={toStep}
			onclose={toOverview}
			ondone={leave}
			{ingredients}
			notes={childNotes}
		/>
	{:else if loaded}
		{#if error}<p class="msg" role="alert">{error}</p>{/if}

		{#if !day}
			<div class="empty">
				{#if !error}<p>Datoen er ikke med i en madplan.</p>{/if}
				<p><a class="link go" href="/">Til ugen</a></p>
			</div>
		{:else if main?.kind === 'opskrift'}
			<div class="columns">
				<section class="intro">
					<Hero src={main.recipe?.image_url} seed={main.recipe?.id ?? main.title} back={weekUrl} />
					<div class="pad head">
						{@render when()}
						<h1 class="serif">{main.title}</h1>
						{#if meta}<p class="ey meta">{meta}</p>{/if}
					</div>
					{#if main.leftover_from}
						<p class="note">
							Bruger rest fra
							<a class="link" href="/lav/{main.leftover_from.date}">{weekdayName(main.leftover_from.date).toLowerCase()}: {main.leftover_from.title}</a>.
							Det, resten dækker, er markeret.
						</p>
					{/if}
					{@render childNotes()}
					{#if recipe && !steps.length}
						<p class="note">
							Opskriften har ingen fremgangsmåde.
							{#if sourceUrl}<a class="link" href={sourceUrl} target="_blank" rel="noopener noreferrer">Se den på siden</a>.{/if}
						</p>
					{/if}
					{#if steps.length && wide.current}<div class="pad inline">{@render start()}</div>{/if}
				</section>

				<section class="list">
					<h2 class="sl">Find frem<span>{foundCount} af {lines.length}</span></h2>
					{@render ingredients()}
				</section>
			</div>
			{#if pinned}<div class="pad bar">{@render start()}</div>{/if}
		{:else}
			<!-- Ingen ret, en ret uden opskrift eller rester: en rolig sætning i stedet for en opskrift. -->
			<div class="pad head calm">
				{@render when()}
				<h1 class="serif">{main ? main.title : 'Ingen ret'}</h1>
				<p class="muted">
					{#if main?.kind === 'rester' && main.leftover_from}
						Rester fra <a class="link" href="/lav/{main.leftover_from.date}">{weekdayName(main.leftover_from.date).toLowerCase()}</a>.
					{:else}
						Der er ikke noget at lave i dag.
					{/if}
				</p>
			</div>
			{@render childNotes()}
			<p class="pad"><a class="link go" href={weekUrl}>Til ugen</a></p>
		{/if}
	{/if}
</main>

<style>
	/* Ingen fanelinje her: siden fylder skærmen, og knappen i bunden står fast. */
	main {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
		padding-bottom: calc(24px + env(safe-area-inset-bottom));
	}
	main.pinned {
		padding-bottom: 0;
	}
	/* Et trin ad gangen: siden ruller ikke, kun trinets tekst. */
	main.step {
		height: 100dvh;
		padding-bottom: 0;
	}
	.head {
		padding-top: 16px;
	}
	.calm {
		padding-top: 28px;
	}
	h1 {
		margin-top: 4px;
		font-size: var(--fs-dish);
		line-height: 28px;
		font-weight: 700;
	}
	.meta {
		margin-top: 4px;
		font-weight: 500;
	}
	.calm p:last-child {
		margin-top: 10px;
	}
	.group {
		padding-top: 12px;
		font-size: var(--fs-cap);
		font-weight: 700;
	}
	.caption {
		padding-top: 10px;
	}
	/* Et link, der står alene, har en hel trykflade. */
	.go {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
	.start {
		height: 56px;
		font-size: 17px;
	}
	/* Start står fast i bunden, fri af telefonens streg. Listen toner ud bag den. */
	.bar {
		position: sticky;
		bottom: 0;
		margin-top: auto;
		padding-top: 20px;
		padding-bottom: calc(12px + env(safe-area-inset-bottom));
		background: linear-gradient(to top, var(--paper) 78%, transparent);
	}
	.inline {
		margin-top: 20px;
	}
	@media (min-width: 900px) {
		main {
			max-width: 1180px;
		}
		/* Ingredienserne til venstre, retten og Start til højre. */
		.intro {
			order: 2;
			padding-right: var(--gutter);
		}
	}
</style>
