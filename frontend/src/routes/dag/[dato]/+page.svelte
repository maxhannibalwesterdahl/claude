<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { shortDate, weekday, weekdayName } from '$lib/dates';
	import { formatQuantity } from '$lib/format';
	import { groupLines } from '$lib/lines';
	import { groupSteps } from '$lib/steps';
	import type { Meal, Plan, PlanBrief, Recipe } from '$lib/types';

	let plan = $state<Plan | null>(null);
	let recipes = $state<Record<number, Recipe>>({});
	let error = $state('');
	let loaded = $state(false);

	const date = $derived(page.params.dato ?? '');
	const day = $derived(plan?.days.find((d) => d.date === date) ?? null);
	const index = $derived(plan && day ? plan.days.indexOf(day) : -1);
	const prev = $derived(plan && index > 0 ? plan.days[index - 1].date : null);
	const next = $derived(plan && index >= 0 && index < plan.days.length - 1 ? plan.days[index + 1].date : null);
	const main = $derived(day?.meal ?? null);
	const recipe = $derived(main?.recipe ? recipes[main.recipe.id] : undefined);

	/** Planen, der dækker datoen. Genbruges, når man bladrer mellem dage i samme plan. */
	async function load(d: string) {
		error = '';
		try {
			if (!plan || !plan.days.some((x) => x.date === d)) {
				const plans = await api<PlanBrief[]>('/plans');
				const hit = plans.find((p) => p.start_date <= d && d <= p.end_date);
				plan = hit ? await api<Plan>(`/plans/${hit.id}`) : null;
			}
			const meals = plan?.days.find((x) => x.date === d);
			for (const m of [meals?.meal, meals?.child]) {
				if (m?.recipe && !recipes[m.recipe.id]) {
					recipes[m.recipe.id] = await api<Recipe>(`/recipes/${m.recipe.id}`);
				}
			}
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke hente dagen';
		} finally {
			loaded = true;
		}
	}

	$effect(() => {
		load(date);
	});

	// Hold skærmen tændt, mens man laver mad (hvor browseren understøtter det).
	$effect(() => {
		let lock: { release: () => Promise<void> } | null = null;
		const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<typeof lock> } };
		const request = () => {
			if (document.visibilityState === 'visible') nav.wakeLock?.request('screen').then((l) => (lock = l)).catch(() => {});
		};
		request();
		document.addEventListener('visibilitychange', request);
		return () => {
			document.removeEventListener('visibilitychange', request);
			lock?.release().catch(() => {});
		};
	});

	// Swipe til forrige/næste dag.
	let touchX = 0;
	let touchY = 0;
	function touchstart(e: TouchEvent) {
		touchX = e.touches[0].clientX;
		touchY = e.touches[0].clientY;
	}
	function touchend(e: TouchEvent) {
		const dx = e.changedTouches[0].clientX - touchX;
		const dy = e.changedTouches[0].clientY - touchY;
		if (Math.abs(dx) < 70 || Math.abs(dy) > Math.abs(dx) * 0.7) return;
		const target = dx < 0 ? next : prev;
		if (target) goto(`/dag/${target}`, { replaceState: true, noScroll: false });
	}

	const mult = (m: number) => (m === 0.5 ? '×½' : `×${m}`);
	const persons = (m: Meal) =>
		m.recipe?.servings ? `${Math.round(m.recipe.servings * m.multiplier)} pers.` : '';
</script>

<main>
	<header class="top">
		<div class="grow">
			<h1>{date ? weekdayName(date) : ''}</h1>
			<div class="muted small">{date ? shortDate(date) : ''}</div>
		</div>
		<!-- Bladr mellem dage. Ugedagen står på knappen, så det ikke forveksles med "tilbage". -->
		<a class="button daynav" class:disabled={!prev} href={prev ? `/dag/${prev}` : undefined} aria-label="Forrige dag" data-sveltekit-replacestate>‹ {prev ? weekday(prev) : ''}</a>
		<a class="button daynav" class:disabled={!next} href={next ? `/dag/${next}` : undefined} aria-label="Næste dag" data-sveltekit-replacestate>{next ? weekday(next) : ''} ›</a>
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	<!-- svelte-ignore a11y_no_static_element_interactions (swipe er en genvej; pilene i toppen gør det samme) -->
	<div class="content" ontouchstart={touchstart} ontouchend={touchend}>
		{#if loaded && !day}
			<div class="empty"><p>Datoen er ikke med i en madplan.</p><p><a href="/">Til madplanen</a></p></div>
		{:else if day && !main && !day.child}
			<div class="empty">
				<p>Ingen ret denne dag.</p>
				<p><a class="button primary" href="/planlaeg?plan={plan?.id}&dag={date}">Vælg en ret</a></p>
			</div>
		{/if}

		{#if main}
			{#if main.kind === 'opskrift'}
				{#if main.recipe?.image_url}<img class="hero" src={main.recipe.image_url} alt="" />{/if}
				<h2 class="dish">
					{#if main.recipe}<a href="/opskrift/{main.recipe.id}">{main.title}</a>{:else}{main.title}{/if}
				</h2>
				<p class="meta">
					{#if main.multiplier !== 1}<span class="badge ok">{mult(main.multiplier)}</span>{/if}
					{#if persons(main)}{persons(main)}{/if}
					{#if main.multiplier !== 1 && main.recipe?.servings}<span class="muted">(opskriften er til {main.recipe.servings})</span>{/if}
				</p>
				{#if main.leftover_from}
					<p class="note">
						Bruger rest fra <a href="/dag/{main.leftover_from.date}">{weekdayName(main.leftover_from.date).toLowerCase()}: {main.leftover_from.title}</a>.
						Det, resten dækker, er markeret.
					</p>
				{/if}
				{#if recipe?.child_note}
					<p class="note child"><strong>Barnet:</strong> {recipe.child_note}</p>
				{/if}

				<div class="columns">
					<section>
						<h3>Ingredienser</h3>
						{#each groupLines(main.lines) as g}
							{#if g.name}<h4>{g.name}</h4>{/if}
							<ul class="ingredients">
								{#each g.lines as l (l.line_id)}
									<li class:dim={l.state === 'rest'}>
										<span class="qty">{formatQuantity(l.quantity, l.quantity_max, l.unit)}</span>
										<span class="grow">
											{l.item}{#if l.note}<span class="muted">, {l.note}</span>{/if}
											{#if l.state === 'rest'}<span class="badge ok">rest</span>{/if}
										</span>
									</li>
								{/each}
							</ul>
						{/each}
						{#if main.multiplier !== 1}
							<p class="muted small">Mængderne er ganget med {mult(main.multiplier).slice(1)}.</p>
						{/if}
					</section>

					<section>
						{#if recipe?.instructions.length}
							<h3>Fremgangsmåde</h3>
							{#if main.multiplier !== 1}
								<p class="muted small">Teksten er fra opskriften. Brug mængderne til venstre.</p>
							{/if}
							{#each groupSteps(recipe.instructions) as sg}
								{#if sg.title}<h4>{sg.title}</h4>{/if}
								<ol class="steps">
									{#each sg.steps as step}<li>{step}</li>{/each}
								</ol>
							{/each}
						{:else if recipe}
							<p class="muted">Opskriften har ingen fremgangsmåde. {#if recipe.source_url}<a href={recipe.source_url} target="_blank" rel="noopener noreferrer">Se den på siden</a>.{/if}</p>
						{/if}
					</section>
				</div>
			{:else if main.kind === 'rester'}
				<div class="plain-meal card">
					<h2 class="dish">{main.title}</h2>
					{#if main.leftover_from}
						<p>Fra <a href="/dag/{main.leftover_from.date}">{weekdayName(main.leftover_from.date).toLowerCase()}</a>. Intet at lave.</p>
					{/if}
				</div>
			{:else}
				<div class="plain-meal card">
					<h2 class="dish">{main.title}</h2>
					<p class="muted">Ingen opskrift.</p>
				</div>
			{/if}
		{/if}

		{#if day?.child}
			<section class="child-meal card">
				<div class="label">Barnet får</div>
				<div class="dish-sm">
					{#if day.child.recipe}<a href="/opskrift/{day.child.recipe.id}">{day.child.title}</a>{:else}{day.child.title}{/if}
				</div>
			</section>
		{/if}

		{#if day && (main || day.child)}
			<p class="edit"><a class="button" href="/planlaeg?plan={plan?.id}&dag={date}">Ret i Planlæg</a></p>
		{/if}
	</div>
</main>

<style>
	.top a.disabled {
		visibility: hidden;
	}
	.daynav {
		padding: 8px 10px;
		font-weight: 600;
	}
	.content {
		display: grid;
		gap: 12px;
	}
	.hero {
		width: 100%;
		max-height: min(300px, 38vh);
		object-fit: cover;
		border-radius: var(--radius);
	}
	.dish {
		font-size: 1.5rem;
		line-height: 1.25;
		margin: 4px 0 0;
		text-transform: none;
		letter-spacing: 0;
		color: var(--fg);
	}
	.dish a {
		color: inherit;
		text-decoration: none;
	}
	.meta {
		display: flex;
		gap: 8px;
		align-items: center;
		flex-wrap: wrap;
		margin: 0;
		font-weight: 600;
	}
	.meta .badge {
		font-size: 0.9rem;
	}
	.note {
		margin: 0;
		background: var(--accent-soft);
		border-radius: 10px;
		padding: 10px 12px;
	}
	h3 {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted);
		margin: 16px 0 6px;
	}
	h4 {
		margin: 12px 0 4px;
		font-size: 1rem;
	}
	.ingredients {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.ingredients li {
		display: flex;
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--line);
		font-size: 1.05rem;
	}
	.ingredients li.dim .grow {
		color: var(--muted);
	}
	.qty {
		flex: 0 0 auto;
		min-width: 72px;
		max-width: 40%;
		text-align: right;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.badge {
		margin-left: 6px;
	}
	/* Større tekst: læses på afstand, mens man laver mad */
	.steps {
		padding-left: 1.4em;
		font-size: 1.05rem;
		line-height: 1.55;
	}
	.steps li {
		margin-bottom: 12px;
	}
	@media (min-width: 900px) {
		.columns {
			display: grid;
			grid-template-columns: minmax(280px, 2fr) 3fr;
			gap: 40px;
			align-items: start;
		}
		.columns > section:first-child {
			position: sticky;
			top: 80px;
		}
	}
	.plain-meal {
		padding: 20px;
	}
	.plain-meal p {
		margin: 8px 0 0;
	}
	.child-meal {
		padding: 12px 14px;
	}
	.label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.dish-sm {
		font-weight: 600;
		font-size: 1.1rem;
	}
	.edit {
		text-align: center;
		margin-top: 16px;
	}
</style>
