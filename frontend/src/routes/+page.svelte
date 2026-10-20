<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { afterNavigate, replaceState } from '$app/navigation';
	import { periodLong, shoppingDayLabel, weekTitle } from '$lib/dates';
	import { navState } from '$lib/nav.svelte';
	import { planApi } from '$lib/planApi';
	import { clock, onResume } from '$lib/resume.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import { fetchSuggestions, type Suggestion } from '$lib/suggestions';
	import { MAIN, type Day, type Slot, type SlotChoice } from '$lib/types';
	import { draggable } from '$lib/ui/drag.svelte';
	import { wishName } from '$lib/ui/glide.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import WeekNav from '$lib/ui/WeekNav.svelte';
	import ChooserSheet from '$lib/uge/ChooserSheet.svelte';
	import DayRow from '$lib/uge/DayRow.svelte';
	import DaySheet from '$lib/uge/DaySheet.svelte';
	import FillSheet from '$lib/uge/FillSheet.svelte';
	import NewWeekSheet from '$lib/uge/NewWeekSheet.svelte';
	import ShoppingAside from '$lib/uge/ShoppingAside.svelte';
	import TrashZone from '$lib/uge/TrashZone.svelte';
	import TonightCard from '$lib/uge/TonightCard.svelte';
	import WeekGrid from '$lib/uge/WeekGrid.svelte';
	import WishSection from '$lib/uge/WishSection.svelte';
	import WishlistSheet from '$lib/uge/WishlistSheet.svelte';
	import { Week } from '$lib/uge/week.svelte';

	const week = new Week();
	// iPad på tværs og computer: hele ugen som gitter med indkøbslisten ved siden af.
	const wide = new MediaQuery('min-width: 900px');

	type Open =
		| { kind: 'day'; date: string }
		| { kind: 'chooser'; date: string; slot: Slot; focusSearch: boolean }
		| { kind: 'wishlist' }
		| { kind: 'fill' }
		| { kind: 'new' }
		| null;
	/** Arket, der er åbent. */
	let sheet = $state<Open>(null);
	/** Vælgeren til ønskelisten ligger oven på ønskelisten. */
	let addingWishes = $state(false);
	/** En oplysning om adressen, siden blev åbnet med. */
	let notice = $state('');
	let suggestions = $state<Suggestion[] | null>(null);
	/** Ugen, der er bedt om (?plan=). Tom: den aktuelle uge. Bruges, når siden hentes igen. */
	let wanted: number | undefined;

	const plan = $derived(week.plan);
	const planId = $derived(week.plan?.id);
	// Der er en tom dag, der ikke er gået: så kan ugen fyldes.
	const canFill = $derived(!!plan?.days.some((d) => !d.meal && !d.extras.length && d.date >= clock.today));

	const ISO = /^\d{4}-\d{2}-\d{2}$/;

	// ?plan=ID viser den uge, ellers den aktuelle. ?dag=ÅÅÅÅ-MM-DD åbner dagen
	// (datoen vinder, hvis den ligger i en anden uge end ?plan=). ?onsker=1 åbner
	// ønskelisten. dag og onsker bruges én gang og fjernes fra adressen, så et ark
	// ikke åbner igen, når det er lukket, og siden hentes igen.
	afterNavigate(({ to }) => {
		const params = to?.url.searchParams ?? new URLSearchParams(location.search);
		const id = Number(params.get('plan')) || undefined;
		const dag = params.get('dag');
		open(id, dag && ISO.test(dag) ? dag : null, params.has('onsker'));
	});

	async function open(id: number | undefined, dag: string | null, wishes: boolean) {
		wanted = id;
		sheet = null;
		addingWishes = false;
		notice = '';
		if (dag) {
			const found = await week.loadForDate(dag, id);
			if (found) openDay(dag);
			else if (week.loaded && !week.error) notice = 'Datoen er ikke med i en madplan.';
		} else {
			await week.load(id);
			if (wishes && week.plan) sheet = { kind: 'wishlist' };
		}
		if (!week.error) address();
	}

	/** Adressen følger ugen, der vises: den aktuelle uge er "/", andre "/?plan=ID". */
	function address() {
		const p = week.plan;
		const current = !p || (p.start_date <= clock.today && clock.today <= p.end_date);
		const url = current ? '/' : `/?plan=${p.id}`;
		wanted = current ? undefined : p.id;
		navState.week = url;
		// Indkøb viser samme uge som Uge.
		const view = current ? null : p.id;
		if (shopping.selected !== view) {
			shopping.selected = view;
			void shopping.sync();
		}
		if (location.pathname + location.search !== url) replaceState(url, {});
	}

	// Åbnes appen igen efter et stykke tid, hentes ugen igen (den anden kan have
	// ændret den). Vises den aktuelle uge, hentes den aktuelle: er en ny uge
	// begyndt imens, er det den, der vises, og ikke den gamle.
	onMount(() => onResume(() => week.load(wanted)));

	async function select(id: number) {
		await week.load(id);
		if (!week.error) address();
	}

	async function removeWeek() {
		if (await week.remove()) address();
	}

	/** Dagen åbner arket med retten. En helt tom dag åbner vælgeren. */
	function openDay(date: string) {
		const d = week.day(date);
		if (!d) return;
		if (d.meal || d.extras.length) {
			week.error = '';
			notice = '';
			sheet = { kind: 'day', date };
		} else openChooser(date);
	}

	function openChooser(date: string, slot: Slot = MAIN, focusSearch = false) {
		week.error = '';
		notice = '';
		sheet = { kind: 'chooser', date, slot, focusSearch };
	}

	/** Et ark er lukket. Er rækken, der åbnede det, skiftet ud imens, får dagens række fokus. */
	async function closed(date?: string) {
		sheet = null;
		if (date) refocus(date);
	}

	async function refocus(date: string) {
		await tick();
		const at = document.activeElement;
		if (at && at !== document.body) return;
		document.querySelector<HTMLElement>(`[data-day="${date}"]`)?.focus({ preventScroll: true });
	}

	async function choose(choice: SlotChoice) {
		const p = week.plan;
		if (sheet?.kind !== 'chooser' || !p) return;
		const { date, slot } = sheet;
		sheet = null;
		await week.run(() => planApi.setSlot(p, date, slot, choice));
		refocus(date);
	}

	function addWish(choice: SlotChoice) {
		const id = week.plan?.id;
		if (!id) return;
		if (choice.kind === 'opskrift') week.run(() => planApi.addWish(id, { recipe_id: choice.recipe_id }));
		else if (choice.kind === 'fritekst') week.run(() => planApi.addWish(id, { text: choice.text }));
	}

	// Træk og slip (finger og mus): en ret bytter plads med den, der står på dagen.
	// Et ønske eller en opskrift spørger, hvis dagen har en ret. Se Week.drop.
	// Løftet holder kopien af retten, hvor den blev sluppet, til ugen er tegnet om.
	function drop(payload: string, d: Day) {
		return week.drop(payload, d);
	}

	/** Sluppet i skraldespanden: retten fjernes fra ugen, ønsket fra ønskelisten.
	 *  Løftet holder originalen falmet, til den er væk. */
	function trash(payload: string) {
		const [kind, raw] = payload.split(':');
		const id = Number(raw);
		if (!id) return;
		if (kind === 'meal') return week.run(() => planApi.remove(id));
		if (kind === 'wish') return week.run(() => planApi.removeWish(id));
	}

	// Forslagene under gitteret følger ugen: det, der er lagt på en dag, forsvinder herfra.
	$effect(() => {
		const id = planId;
		void week.rev;
		if (!wide.current || !id) return;
		let stale = false;
		fetchSuggestions({ planId: id, limit: 6 })
			.then((s) => !stale && (suggestions = s))
			.catch(() => {});
		return () => {
			stale = true;
		};
	});
</script>

{#snippet messages()}
	{#if week.error}<p class="msg" role="alert">{week.error}</p>{/if}
	{#if notice}<p class="msg" role="alert">{notice}</p>{/if}
{/snippet}

<main class:wide={wide.current && !!plan}>
	{#if plan}
		{#if wide.current}
			<div class="panes">
				<div class="left">
					<ScreenHeader title={weekTitle(plan, clock.today)} eyebrow="{periodLong(plan.start_date, plan.end_date)} · {shoppingDayLabel(plan, clock.today)}">
						{#snippet actions()}
							<button type="button" class="chip" onclick={() => (sheet = { kind: 'wishlist' })}>Ønskeliste · {plan.wishlist.length}</button>
							{#if canFill}<button type="button" class="chip" onclick={() => (sheet = { kind: 'fill' })}>Fyld ugen</button>{/if}
							<WeekNav {plan} plans={week.plans} onselect={select} onnew={() => (sheet = { kind: 'new' })} />
						{/snippet}
					</ScreenHeader>
					{@render messages()}

					<div class="grid">
						<WeekGrid {plan} today={clock.today} onopen={openDay} ondrop={drop} />
					</div>

					{#if plan.wishlist.length}
						<p class="sl">Ønskeliste<span>træk til en dag</span></p>
						<div class="grid2">
							{#each plan.wishlist as w (w.id)}
								{#if w.recipe}
									<a class="rc tile" href="/opskrift/{w.recipe.id}" style:view-transition-name={wishName(w.id)} use:draggable={`wish:${w.id}`}>
										<Plate src={w.recipe.image_url} seed={w.recipe.id} size={40} lazy />
										<p class="n">{w.title}</p>
									</a>
								{:else}
									<!-- En idé uden opskrift kan kun trækkes. Uden mus og finger lægges den på en dag fra ønskelisten (chippen i toppen). -->
									<div class="rc tile" style:view-transition-name={wishName(w.id)} use:draggable={`wish:${w.id}`}>
										<p class="n">{w.title}</p>
									</div>
								{/if}
							{/each}
						</div>
					{/if}

					{#if suggestions?.length}
						<p class="sl">Længe siden<span>fra jeres egne opskrifter</span></p>
						<div class="grid2">
							{#each suggestions as s (s.recipe.id)}
								<a class="rc tile" href="/opskrift/{s.recipe.id}" use:draggable={`recipe:${s.recipe.id}`}>
									<Plate src={s.recipe.image_url} seed={s.recipe.id} size={40} lazy />
									<p class="n">{s.recipe.title}</p>
								</a>
							{/each}
						</div>
					{/if}

					<p class="foot"><button type="button" class="btn quiet sm" onclick={removeWeek}>Slet denne uge</button></p>
				</div>
				<ShoppingAside planId={plan.id} rev={week.rev} />
			</div>
		{:else}
			<ScreenHeader title={weekTitle(plan, clock.today)} eyebrow="{periodLong(plan.start_date, plan.end_date)} · {shoppingDayLabel(plan, clock.today)}">
				{#snippet actions()}
					<WeekNav {plan} plans={week.plans} onselect={select} onnew={() => (sheet = { kind: 'new' })} />
				{/snippet}
			</ScreenHeader>
			{@render messages()}

			{#each plan.days as d (d.date)}
				{#if d.date === clock.today}
					<TonightCard day={d} onopen={() => openDay(d.date)} onchoose={() => openChooser(d.date)} ondrop={(p) => drop(p, d)} />
				{:else}
					<DayRow day={d} today={clock.today} onopen={() => openDay(d.date)} ondrop={(p) => drop(p, d)} />
				{/if}
			{/each}

			<!-- Ønskelisten står lige under dagene, så ønskerne kan trækkes op på en dag. -->
			<WishSection {plan} freeDays={week.freeDays} ondistribute={() => week.distribute()} onshow={() => (sheet = { kind: 'wishlist' })} />

			{#if canFill}
				<p class="fill pad"><button type="button" class="btn sm" onclick={() => (sheet = { kind: 'fill' })}>Fyld ugen</button></p>
			{/if}

			<p class="foot"><button type="button" class="btn quiet sm" onclick={removeWeek}>Slet denne uge</button></p>
		{/if}
	{:else if week.loaded}
		<ScreenHeader title="Uge" />
		{@render messages()}
		{#if !week.error}
			<div class="empty">
				<p>Der er ingen madplan endnu.</p>
				<p><button type="button" class="btn primary" onclick={() => (sheet = { kind: 'new' })}>Lav en uge</button></p>
			</div>
		{/if}
	{/if}
</main>

{#if plan}<TrashZone ondrop={trash} />{/if}

{#if sheet?.kind === 'new'}
	<NewWeekSheet {week} oncreated={address} onclose={() => closed()} />
{:else if plan && sheet?.kind === 'day'}
	{@const date = sheet.date}
	<DaySheet {week} {date} onchooser={(slot) => openChooser(date, slot)} onclose={() => closed(date)} />
{:else if plan && sheet?.kind === 'chooser'}
	{@const date = sheet.date}
	<ChooserSheet {plan} {date} extra={sheet.slot.extra} focusSearch={sheet.focusSearch} onchoose={choose} onclose={() => closed(date)} />
{:else if plan && sheet?.kind === 'fill'}
	<FillSheet {week} onclose={() => closed()} />
{:else if plan && sheet?.kind === 'wishlist'}
	<WishlistSheet {week} onadd={() => (addingWishes = true)} onclose={() => closed()} />
	{#if addingWishes}
		<ChooserSheet {plan} mode="wish" message={week.error} onchoose={addWish} onclose={() => (addingWishes = false)} />
	{/if}
{/if}

<style>
	.foot {
		margin-top: 28px;
		text-align: center;
	}
	.empty p + p {
		margin-top: 16px;
	}
	.fill {
		margin-top: 16px;
	}

	/* Bred skærm: ugen til venstre, indkøbslisten til højre i fuld højde. */
	.panes {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 300px;
		min-height: calc(100dvh - var(--nav-h) - env(safe-area-inset-bottom) - env(safe-area-inset-top) - 24px);
	}
	.left {
		min-width: 0;
		padding-bottom: 24px;
	}
	.grid {
		margin-top: 10px;
	}
	.tile {
		cursor: grab;
	}
</style>
