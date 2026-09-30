<script lang="ts">
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { parseDate, periodLabel, shortDate, weekdayName } from '$lib/dates';
	import { clock, onResume } from '$lib/resume.svelte';
	import { untrack } from 'svelte';
	import { refreshReviewCount } from '$lib/review.svelte';
	import type { Plan, PlanBrief } from '$lib/types';

	let plan = $state<Plan | null>(null);
	let plans = $state<PlanBrief[]>([]);
	let loaded = $state(false);
	let error = $state('');

	const planIndex = $derived(plan ? plans.findIndex((p) => p.id === plan!.id) : -1);
	const planned = $derived(plan?.days.filter((d) => d.meal).length ?? 0);

	async function load(id?: number) {
		error = '';
		try {
			plans = await api<PlanBrief[]>('/plans');
			plan = await api<Plan>(id ? `/plans/${id}` : `/plans/current?today=${clock.today}`);
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) plan = null;
			else error = e instanceof ApiError ? e.message : 'Kunne ikke hente madplanen';
		} finally {
			loaded = true;
		}
	}

	$effect(() => {
		const wanted = Number(page.url.searchParams.get('plan')) || undefined;
		untrack(() => load(wanted));
		// Åbnes appen igen efter et stykke tid, hentes planen igen.
		return onResume(() => untrack(() => load(plan?.id ?? wanted)));
		refreshReviewCount().catch(() => {});
	});

	const mult = (m: number) => (m === 0.5 ? '×½' : `×${m}`);
</script>

<main>
	<header class="top">
		<div class="grow">
			<h1>Madplan</h1>
			{#if plan}
				<div class="period">
					{#if plans.length > 1}
						<button class="plain" aria-label="Forrige plan" disabled={planIndex >= plans.length - 1} onclick={() => load(plans[planIndex + 1].id)}>‹</button>
					{/if}
					<span>{periodLabel(plan.start_date, plan.end_date)}</span>
					{#if plans.length > 1}
						<button class="plain" aria-label="Næste plan" disabled={planIndex <= 0} onclick={() => load(plans[planIndex - 1].id)}>›</button>
					{/if}
				</div>
			{/if}
		</div>
		{#if plan}<a class="button" href="/planlaeg?plan={plan.id}">Planlæg</a>{/if}
	</header>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	{#if plan}
		{#if planned === 0}
			<div class="empty">
				<p>Ingen retter i planen endnu.</p>
				<p><a class="button primary" href="/planlaeg?plan={plan.id}">Planlæg ugen</a></p>
			</div>
		{/if}
		<ul class="days">
			{#each plan.days as d (d.date)}
				{@const isToday = d.date === clock.today}
				{@const past = d.date < clock.today}
				<li>
					<a href="/dag/{d.date}" class="card day" class:today={isToday} class:past>
						{#if d.meal?.recipe?.image_url}
							<img src={d.meal.recipe.image_url} alt="" loading="lazy" />
						{:else}
							<div class="noimg" aria-hidden="true">
								<span class="dn">{parseDate(d.date).getDate()}</span>
							</div>
						{/if}
						<div class="grow body">
							<div class="when">
								{weekdayName(d.date)} <span class="muted">{shortDate(d.date)}</span>
								{#if isToday}<span class="badge ok">i dag</span>{/if}
							</div>
							{#if d.meal}
								<div class="title">
									{d.meal.title}{#if d.meal.kind === 'opskrift' && d.meal.multiplier !== 1}&nbsp;<b class="mult">{mult(d.meal.multiplier)}</b>{/if}
								</div>
							{:else}
								<div class="title muted">Ingen ret</div>
							{/if}
							{#if d.child}<div class="child">Barnet: {d.child.title}</div>{/if}
						</div>
						<span class="chev" aria-hidden="true">›</span>
					</a>
				</li>
			{/each}
		</ul>
	{:else if loaded && !error}
		<div class="empty">
			<p>Ingen madplan endnu.</p>
			<p><a class="button primary" href="/planlaeg">Lav en madplan</a></p>
		</div>
	{/if}
</main>

<style>
	.period {
		display: flex;
		align-items: center;
		gap: 2px;
		font-size: 0.9rem;
		color: var(--muted);
		margin-left: -6px;
	}
	.period span {
		padding: 0 6px;
	}
	.period button {
		min-height: 28px;
		padding: 0 8px;
		font-size: 1.1rem;
		color: var(--accent);
	}
	.period button:disabled {
		visibility: hidden;
	}
	.days {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 10px;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr));
	}
	.day {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 10px;
		color: inherit;
		text-decoration: none;
		min-height: 84px;
	}
	.day.today {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent), var(--shadow);
	}
	.day.past {
		opacity: 0.6;
	}
	img,
	.noimg {
		width: 64px;
		height: 64px;
		border-radius: 10px;
		object-fit: cover;
		flex: none;
	}
	.noimg {
		display: grid;
		place-items: center;
		background: var(--accent-soft);
		color: var(--accent);
	}
	.dn {
		font-size: 1.5rem;
		font-weight: 800;
	}
	.body {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.when {
		font-size: 0.85rem;
		font-weight: 700;
		display: flex;
		gap: 6px;
		align-items: center;
		flex-wrap: wrap;
	}
	.title {
		font-weight: 600;
		font-size: 1.05rem;
		line-height: 1.3;
	}
	.mult {
		color: var(--accent);
	}
	.child {
		font-size: 0.85rem;
		color: var(--muted);
	}
	.chev {
		font-size: 1.5rem;
		color: var(--muted);
		flex: none;
	}
</style>
