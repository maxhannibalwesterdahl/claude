<script lang="ts">
	import { untrack } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { confirmDialog } from '$lib/confirm.svelte';
	import { parseDate, periodLong, weekdayName, weekTitle } from '$lib/dates';
	import { planApi } from '$lib/planApi';
	import { clock } from '$lib/resume.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import WeekNav from '$lib/ui/WeekNav.svelte';
	import type { Day, Plan, PlanBrief } from '$lib/types';

	interface Props {
		recipe: { id: number; title: string };
		/** Opskriften er lagt på en dag (date) eller på ønskelisten (date = null). */
		onplaced: (plan: Plan, date: string | null) => void;
		onclose: () => void;
	}
	let { recipe, onplaced, onclose }: Props = $props();

	let plans = $state<PlanBrief[]>([]);
	let plan = $state<Plan | null>(null);
	let loaded = $state(false);
	let busy = $state(false);
	let error = $state('');

	// Kun svaret på den uge, der sidst blev bedt om, vises.
	let asked = 0;
	async function show(load: Promise<Plan | null>) {
		const mine = ++asked;
		error = '';
		try {
			const p = await load;
			if (mine === asked) plan = p;
		} catch (e) {
			if (mine === asked) error = say(e);
		} finally {
			if (mine === asked) loaded = true;
		}
	}

	$effect(() => {
		untrack(() => {
			api<PlanBrief[]>('/plans')
				.then((p) => (plans = p))
				.catch(() => {});
			// 404: der er ingen madplan endnu.
			show(
				api<Plan>(`/plans/current?today=${clock.today}`).catch((e) => {
					if (e instanceof ApiError && e.status === 404) return null;
					throw e;
				})
			);
		});
	});

	const onList = $derived(plan?.wishlist.some((w) => w.recipe?.id === recipe.id) ?? false);
	const here = (d: Day) => d.meal?.kind === 'opskrift' && d.meal.recipe?.id === recipe.id;

	async function run(close: () => void, date: string | null, call: () => Promise<Plan>) {
		busy = true;
		error = '';
		try {
			const p = await call();
			// Fanens tal på Indkøb følger med.
			shopping.sync();
			onplaced(p, date);
			close();
		} catch (e) {
			error = say(e);
		} finally {
			busy = false;
		}
	}

	async function place(day: Day, close: () => void) {
		const p = plan;
		if (!p || busy) return;
		if (day.meal && !(await confirmDialog(`Erstat ${day.meal.title} ${weekdayName(day.date).toLowerCase()}?`, 'Erstat'))) return;
		await run(close, day.date, () => planApi.setSlot(p, day.date, false, { kind: 'opskrift', recipe_id: recipe.id }));
	}

	async function wish(close: () => void) {
		const p = plan;
		if (!p || busy) return;
		await run(close, null, () => planApi.addWish(p.id, { recipe_id: recipe.id }));
	}
</script>

<Sheet title="Læg på en dag" eyebrow={recipe.title} {onclose}>
	{#snippet aside(close)}
		<!-- Ugerne kan kun skiftes, når der er flere. Luk står her, fordi arket ellers ingen synlig lukkeknap har. -->
		{#if plan && plans.length > 1}
			<WeekNav {plan} {plans} onselect={(id) => show(api<Plan>(`/plans/${id}`))} />
		{/if}
		<button type="button" class="rnd" aria-label="Luk" onclick={close}><Icon name="x" /></button>
	{/snippet}
	{#snippet children(close)}
		{#if error}<p class="msg" role="alert">{error}</p>{/if}
		{#if plan}
			<p class="sl" aria-live="polite">{weekTitle(plan, clock.today)}<span>{periodLong(plan.start_date, plan.end_date)}</span></p>
			<div aria-busy={busy} class:busy>
				{#each plan.days as d (d.date)}
					{@const past = d.date < clock.today}
					<button type="button" class="kv" disabled={busy || past || here(d)} onclick={() => place(d, close)}>
						<span class="k">
							{weekdayName(d.date)} {parseDate(d.date).getDate()}.
							<small>{d.meal ? d.meal.title : 'Ledig'}</small>
						</span>
						{#if here(d)}
							<span class="tag">står her</span>
						{:else if past}
							<span class="tag">forbi</span>
						{:else if d.date === clock.today}
							<span class="tag">i dag</span>
						{/if}
					</button>
				{/each}
				{#if onList}
					<div class="kv">
						<span class="k">Læg på ønskelisten</span>
						<span class="tag">på listen</span>
					</div>
				{:else}
					<button type="button" class="kv" disabled={busy} onclick={() => wish(close)}>
						<span class="k">Læg på ønskelisten<small>Så vælger I dagen senere</small></span>
					</button>
				{/if}
			</div>
		{:else if loaded && !error}
			<div class="empty">
				<p>Der er ingen madplan endnu.</p>
				<p><a class="link" href="/">Lav en uge</a></p>
			</div>
		{/if}
	{/snippet}
</Sheet>

<style>
	button.kv:disabled {
		cursor: default;
	}
	button.kv:disabled .k {
		color: var(--muted);
	}
	.busy {
		opacity: 0.7;
	}
	.empty .link {
		display: inline-block;
		padding: 12px;
	}
</style>
