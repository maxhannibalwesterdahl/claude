<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { addDays, isoDate, nextWeekday, parseDate, periodLabel, shortDate, today, weekday, weekdayName } from '$lib/dates';
	import MealSlot from '$lib/MealSlot.svelte';
	import { planApi } from '$lib/planApi';
	import { refreshReviewCount } from '$lib/review.svelte';
	import type { Plan, PlanBrief, RecipeSummary } from '$lib/types';

	let plan = $state<Plan | null>(null);
	let plans = $state<PlanBrief[]>([]);
	let loaded = $state(false);
	let error = $state('');
	let selected = $state('');
	let childOpen = $state<Record<string, boolean>>({});
	let creating = $state(false);
	let startDate = $state('');
	let wishText = $state('');
	let recipes = $state<RecipeSummary[]>([]);
	let dragOver = $state('');

	const day = $derived(plan?.days.find((d) => d.date === selected) ?? plan?.days[0] ?? null);
	const index = $derived(plan && day ? plan.days.indexOf(day) : 0);
	const planIndex = $derived(plan ? plans.findIndex((p) => p.id === plan!.id) : -1);

	function show(p: Plan) {
		plan = p;
		if (!p.days.some((d) => d.date === selected)) {
			const t = today();
			selected = p.days.some((d) => d.date === t) ? t : p.days[0].date;
		}
	}

	async function load(id?: number) {
		error = '';
		try {
			plans = await api<PlanBrief[]>('/plans');
			show(await api<Plan>(id ? `/plans/${id}` : '/plans/current'));
			creating = false;
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) {
				plan = null;
				creating = true;
				startDate = suggestedStart();
			} else error = e instanceof ApiError ? e.message : 'Kunne ikke hente madplanen';
		} finally {
			loaded = true;
		}
	}

	$effect(() => {
		load();
		api<RecipeSummary[]>('/recipes').then((r) => (recipes = r)).catch(() => {});
		refreshReviewCount().catch(() => {});
	});

	function suggestedStart(): string {
		const latest = plans[0];
		if (latest && latest.end_date >= today()) return isoDate(addDays(parseDate(latest.end_date), 1));
		return today();
	}

	function newPlan() {
		creating = true;
		startDate = suggestedStart();
	}

	async function create(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			const p = await api<Plan>('/plans', { method: 'POST', body: { start_date: startDate } });
			plans = await api<PlanBrief[]>('/plans');
			selected = p.days[0].date;
			show(p);
			creating = false;
		} catch (err) {
			error = err instanceof ApiError ? err.message : 'Kunne ikke oprette planen';
		}
	}

	async function removePlan() {
		if (!plan || !confirm(`Slet madplanen ${periodLabel(plan.start_date, plan.end_date)}?`)) return;
		await api(`/plans/${plan.id}`, { method: 'DELETE' });
		plan = null;
		await load();
	}

	async function run(fn: () => Promise<Plan>) {
		error = '';
		try {
			show(await fn());
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Noget gik galt';
		}
	}

	function addWish(e: SubmitEvent) {
		e.preventDefault();
		if (!plan || !wishText.trim()) return;
		const match = recipes.find((r) => r.title.toLowerCase() === wishText.trim().toLowerCase());
		const body = match ? { recipe_id: match.id } : { text: wishText.trim() };
		const id = plan.id;
		run(() => planApi.addWish(id, body));
		wishText = '';
	}

	// Swipe mellem dage på telefonen.
	let touchX = 0;
	let touchY = 0;
	function touchstart(e: TouchEvent) {
		touchX = e.touches[0].clientX;
		touchY = e.touches[0].clientY;
	}
	function touchend(e: TouchEvent) {
		if (!plan) return;
		const dx = e.changedTouches[0].clientX - touchX;
		const dy = e.changedTouches[0].clientY - touchY;
		if (Math.abs(dx) < 70 || Math.abs(dy) > Math.abs(dx) * 0.7) return;
		const target = plan.days[index + (dx < 0 ? 1 : -1)];
		if (target) selected = target.date;
	}

	// Træk og slip i ugegitteret.
	function dragstart(e: DragEvent, payload: string) {
		e.dataTransfer?.setData('text/plain', payload);
		if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
	}
	function drop(e: DragEvent, date: string) {
		e.preventDefault();
		dragOver = '';
		const data = e.dataTransfer?.getData('text/plain') ?? '';
		const [kind, id] = data.split(':');
		if (!plan || !id) return;
		if (kind === 'meal') run(() => planApi.move(Number(id), date, false));
		if (kind === 'wish') run(() => planApi.setSlot(plan!, date, false, { kind: 'ønske', wish_id: Number(id) }));
	}

	const nextSunday = () => isoDate(nextWeekday(new Date(), 0));
	const nextMonday = () => isoDate(nextWeekday(new Date(), 1));
</script>

<main>
	<header class="top">
		<div class="grow">
			<h1>Madplan</h1>
			{#if plan}<div class="period muted">{periodLabel(plan.start_date, plan.end_date)}</div>{/if}
		</div>
		{#if plan}
			<button aria-label="Forrige plan" disabled={planIndex >= plans.length - 1} onclick={() => load(plans[planIndex + 1].id)}>‹</button>
			<button aria-label="Næste plan" disabled={planIndex <= 0} onclick={() => load(plans[planIndex - 1].id)}>›</button>
			<button onclick={newPlan}>+ Ny</button>
		{/if}
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	{#if creating}
		<form class="create card" onsubmit={create}>
			<h2>Ny madplan</h2>
			<p class="muted small">Planen starter på indkøbsdagen og varer 7 dage.</p>
			<label class="field">
				<span>Indkøbsdag</span>
				<input type="date" bind:value={startDate} required />
			</label>
			<div class="row">
				<button type="button" onclick={() => (startDate = nextSunday())}>Søndag {shortDate(nextSunday())}</button>
				<button type="button" onclick={() => (startDate = nextMonday())}>Mandag {shortDate(nextMonday())}</button>
			</div>
			<div class="row">
				{#if plan}<button type="button" onclick={() => (creating = false)}>Annullér</button>{/if}
				<button class="primary">Opret plan</button>
			</div>
		</form>
	{/if}

	{#if plan && day}
		<!-- Telefon: én dag ad gangen -->
		<nav class="strip" aria-label="Dage">
			{#each plan.days as d (d.date)}
				<button class:on={d.date === day.date} class:today={d.date === today()} onclick={() => (selected = d.date)}>
					<span class="wd">{weekday(d.date)}</span>
					<span class="dn">{parseDate(d.date).getDate()}</span>
					<span class="dot" class:filled={!!d.meal}></span>
				</button>
			{/each}
		</nav>

		<!-- iPad/computer: hele ugen, træk retter mellem dage -->
		<div class="grid">
			{#each plan.days as d (d.date)}
				<div
					class="cell"
					class:on={d.date === day.date}
					class:over={dragOver === d.date}
					role="button"
					tabindex="0"
					onclick={() => (selected = d.date)}
					onkeydown={(e) => e.key === 'Enter' && (selected = d.date)}
					ondragover={(e) => {
						e.preventDefault();
						dragOver = d.date;
					}}
					ondragleave={() => (dragOver = '')}
					ondrop={(e) => drop(e, d.date)}
				>
					<div class="cell-head" class:today={d.date === today()}>{weekday(d.date)} {parseDate(d.date).getDate()}.</div>
					{#if d.meal}
						<div class="mini" draggable="true" ondragstart={(e) => dragstart(e, `meal:${d.meal!.id}`)} role="listitem">
							{#if d.meal.recipe?.image_url}<img src={d.meal.recipe.image_url} alt="" draggable="false" />{/if}
							<span>{d.meal.title}</span>
							{#if d.meal.multiplier !== 1}<b class="mult">×{d.meal.multiplier === 0.5 ? '½' : d.meal.multiplier}</b>{/if}
						</div>
					{:else}
						<div class="mini empty muted small">Træk en ret hertil</div>
					{/if}
					{#if d.child}<div class="child small">Barn: {d.child.title}</div>{/if}
				</div>
			{/each}
		</div>

		<!-- svelte-ignore a11y_no_static_element_interactions (swipe er en genvej; dagene kan også vælges i strimlen) -->
		<section class="day" aria-label="Dagens ret" ontouchstart={touchstart} ontouchend={touchend}>
			<h2 class="day-title">
				{weekdayName(day.date)} <span class="muted">{shortDate(day.date)}</span>
			</h2>
			{#key day.date}
				<MealSlot {plan} date={day.date} forChild={false} meal={day.meal} onplan={show} />
				{#if day.child || childOpen[day.date]}
					<div class="child-slot">
						<MealSlot {plan} date={day.date} forChild={true} meal={day.child} onplan={show} />
					</div>
				{:else}
					<button class="plain child-toggle" onclick={() => (childOpen[day.date] = true)}>+ Barnet får noget andet</button>
				{/if}
			{/key}
		</section>

		<section class="wishes">
			<h2>Ønskeliste</h2>
			<p class="muted small">Retter I vil have i perioden. Læg dem på en dag, når I planlægger.</p>
			<ul>
				{#each plan.wishlist as w (w.id)}
					<li draggable="true" ondragstart={(e) => dragstart(e, `wish:${w.id}`)}>
						<span class="grow">
							{#if w.recipe}<a href="/opskrift/{w.recipe.id}">{w.title}</a>{:else}{w.title}{/if}
						</span>
						<select
							value=""
							aria-label="Læg på dag"
							onchange={(e) => {
								const d = e.currentTarget.value;
								if (d) run(() => planApi.setSlot(plan!, d, false, { kind: 'ønske', wish_id: w.id }));
							}}
						>
							<option value="">Læg på…</option>
							{#each plan.days as d}
								<option value={d.date}>{weekdayName(d.date)}{d.meal ? ` (erstat ${d.meal.title})` : ''}</option>
							{/each}
						</select>
						<button class="plain" aria-label="Fjern ønske" onclick={() => run(() => planApi.removeWish(w.id))}>✕</button>
					</li>
				{/each}
			</ul>
			<form class="row" onsubmit={addWish}>
				<input class="grow" list="recipe-titles" bind:value={wishText} placeholder="Opskrift eller ret" aria-label="Nyt ønske" />
				<datalist id="recipe-titles">
					{#each recipes as r}<option value={r.title}></option>{/each}
				</datalist>
				<button disabled={!wishText.trim()}>Tilføj</button>
			</form>
		</section>

		<p class="footer"><button class="plain danger small" onclick={removePlan}>Slet denne plan</button></p>
	{:else if loaded && !creating && !error}
		<div class="empty"><button class="primary" onclick={newPlan}>Lav en madplan</button></div>
	{/if}
</main>

<style>
	.period {
		font-size: 0.9rem;
	}
	.top button {
		padding: 8px 12px;
	}
	.create {
		display: grid;
		gap: 12px;
		padding: 16px;
		margin-bottom: 16px;
	}
	.create h2 {
		margin: 0;
	}

	/* Dagsstrimmel (telefon) */
	.strip {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: 4px;
		margin-bottom: 12px;
	}
	.strip button {
		flex-direction: column;
		gap: 0;
		padding: 6px 0;
		justify-content: center;
		align-items: center;
		text-align: center;
		min-height: 58px;
	}
	.strip .wd {
		font-size: 0.75rem;
		color: var(--muted);
	}
	.strip .dn {
		font-weight: 700;
		font-size: 1.05rem;
	}
	.strip .today .dn {
		color: var(--accent);
	}
	.strip button.on {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-fg);
	}
	.strip button.on .wd,
	.strip button.on .dn {
		color: inherit;
	}
	.dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		margin-top: 2px;
	}
	.dot.filled {
		background: currentColor;
	}

	/* Ugegitter (iPad/computer) */
	.grid {
		display: none;
	}
	@media (min-width: 900px) {
		.strip {
			display: none;
		}
		.grid {
			display: grid;
			grid-template-columns: repeat(7, minmax(0, 1fr));
			gap: 8px;
			margin-bottom: 16px;
		}
	}
	.cell {
		background: var(--card);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 8px;
		min-height: 150px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		cursor: pointer;
	}
	.cell.on {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent);
	}
	.cell.over {
		background: var(--accent-soft);
	}
	.cell-head {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--muted);
		text-transform: capitalize;
	}
	.cell-head.today {
		color: var(--accent);
	}
	.mini {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 0.9rem;
		font-weight: 600;
		line-height: 1.25;
		cursor: grab;
		position: relative;
	}
	.mini img {
		width: 100%;
		aspect-ratio: 4 / 3;
		object-fit: cover;
		border-radius: 8px;
	}
	.mini.empty {
		font-weight: 400;
		cursor: default;
		border: 1px dashed var(--line);
		border-radius: 8px;
		padding: 12px 6px;
		text-align: center;
		flex: 1;
		display: grid;
		place-items: center;
	}
	.mult {
		position: absolute;
		top: 4px;
		right: 4px;
		background: var(--accent);
		color: var(--accent-fg);
		border-radius: 6px;
		padding: 0 6px;
		font-size: 0.8rem;
	}
	.child {
		color: var(--muted);
		border-top: 1px solid var(--line);
		padding-top: 4px;
	}

	/* Dagen */
	.day {
		display: grid;
		gap: 12px;
	}
	.day-title {
		text-transform: none;
		letter-spacing: 0;
		font-size: 1.25rem;
		color: var(--fg);
		margin: 4px 0 0;
	}
	.child-slot {
		border-left: 3px solid var(--accent-soft);
		padding-left: 10px;
	}
	.child-toggle {
		justify-self: start;
		color: var(--accent);
	}

	/* Ønskeliste */
	.wishes ul {
		list-style: none;
		padding: 0;
		margin: 0 0 10px;
	}
	.wishes li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 0;
		border-bottom: 1px solid var(--line);
	}
	.wishes select {
		width: auto;
		max-width: 45%;
	}
	.footer {
		text-align: center;
		margin-top: 32px;
	}
</style>
