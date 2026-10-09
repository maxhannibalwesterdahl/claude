<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { parseDate, shortDate, weekdayName } from '$lib/dates';
	import { mult } from '$lib/format';
	import PeriodNav from '$lib/PeriodNav.svelte';
	import Thumb from '$lib/Thumb.svelte';
	import { clock, onResume } from '$lib/resume.svelte';
	import { untrack } from 'svelte';
	import { refreshReviewCount } from '$lib/review.svelte';
	import type { Plan, PlanBrief } from '$lib/types';

	let plan = $state<Plan | null>(null);
	let plans = $state<PlanBrief[]>([]);
	let loaded = $state(false);
	let error = $state('');

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
		refreshReviewCount().catch(() => {});
		// Åbnes appen igen efter et stykke tid, hentes planen igen.
		return onResume(() => untrack(() => load(plan?.id ?? wanted)));
	});

	async function logout() {
		await api('/logout', { method: 'POST' }).catch(() => {});
		await goto('/login');
	}
</script>

<main>
	<header class="top">
		<div class="grow">
			<h1>Madplan</h1>
			{#if plan}<PeriodNav {plan} {plans} onselect={load} />{/if}
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
						<Thumb src={d.meal?.recipe?.image_url} lazy>
							<span class="dn">{parseDate(d.date).getDate()}</span>
						</Thumb>
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

	{#if loaded}<p class="footer"><button class="plain muted small" onclick={logout}>Log ud</button></p>{/if}
</main>

<style>
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
	/* Dage, der er gået, træder tilbage uden at teksten bliver sværere at læse:
	   fladt kort, dæmpet tekst og billede. */
	.day.past {
		background: transparent;
		box-shadow: none;
	}
	.day.past .when,
	.day.past .title {
		color: var(--muted);
	}
	.day.past :global(img) {
		opacity: 0.6;
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
	.footer {
		text-align: center;
		margin-top: 32px;
	}
</style>
