<script lang="ts">
	import { longDate, parseDate, weekday } from '$lib/dates';
	import { planApi } from '$lib/planApi';
	import { MAIN, type Plan, type Slot } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import MealPanel from './MealPanel.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		date: string;
		/** Åbner vælgeren for hovedretten, en ny ekstra ret eller en ekstra ret, der skiftes ud. Siden lukker dette ark. */
		onchooser: (slot: Slot) => void;
		onclose: () => void;
	}
	let { week, date, onchooser, onclose }: Props = $props();

	/** Den ekstra ret, arket viser. Tom: dagens hovedret. */
	let shown = $state<number | null>(null);
	/** Bunden viser ugens dage i stedet for knapperne. */
	let moving = $state(false);
	let busy = $state(false);

	const plan = $derived(week.plan);
	const day = $derived(week.day(date));
	const meal = $derived(day ? (shown !== null ? (day.extras.find((m) => m.id === shown) ?? null) : day.meal) : null);
	const recipe = $derived(meal?.kind === 'opskrift' ? meal.recipe : null);

	$effect(() => {
		// Den ekstra ret er fjernet eller flyttet: tilbage til hovedretten.
		if (shown !== null && day && !day.extras.some((m) => m.id === shown)) shown = null;
	});
	$effect(() => {
		// Dagen er blevet tom (retten er fjernet eller flyttet): der er ikke mere at vise.
		if (!day || (!day.meal && !day.extras.length)) onclose();
	});

	/** Slår knapperne fra, mens ændringen er på vej. */
	async function run(fn: () => Promise<Plan>): Promise<boolean> {
		busy = true;
		try {
			return await week.run(fn);
		} finally {
			busy = false;
		}
	}

	/** Flytter retten. En hovedret bytter plads med hovedretten på den anden dag
	 *  (uden at spørge). En ekstra ret lægges til den anden dags ekstra retter. */
	async function moveTo(target: string, close: () => void) {
		if (!meal) return;
		const id = meal.id;
		const extra = meal.extra;
		if (await run(() => planApi.move(id, target, extra))) close();
	}

	function remove() {
		if (!meal) return;
		const id = meal.id;
		moving = false;
		run(() => planApi.remove(id));
	}

	/** Når dagene kommer frem i bunden, får den første, der kan vælges, fokus. */
	function focusFirst(node: HTMLElement) {
		node.querySelector<HTMLElement>('button:not(:disabled)')?.focus();
	}
</script>

{#if plan && day}
	<Sheet
		title={meal?.title ?? (day.extras.length ? 'Ingen hovedret endnu' : 'Ingen ret endnu')}
		eyebrow={shown !== null ? `${longDate(date)} · ekstra ret` : longDate(date)}
		eyebrowAbove
		aside={recipe ? plate : undefined}
		{onclose}
	>
		{#if week.error}<p class="msg" role="alert">{week.error}</p>{/if}
		{#key `${shown}:${meal?.id}`}
			<MealPanel
				{week}
				{plan}
				{day}
				{meal}
				extra={shown !== null}
				{busy}
				{run}
				onadd={() => onchooser({ extra: true })}
				onshow={(id) => {
					shown = id;
					moving = false;
				}}
			/>
		{/key}

		{#snippet footer(close)}
			{#if !meal}
				<div class="btns">
					<button type="button" class="btn primary" onclick={() => onchooser(MAIN)}>{day.extras.length ? 'Vælg hovedret' : 'Vælg ret'}</button>
				</div>
			{:else if moving}
				<p class="small muted to">Flyt til</p>
				<div class="chips" role="group" aria-label="Flyt til en anden dag" use:focusFirst>
					{#each plan.days as d (d.date)}
						<button type="button" class="chip" disabled={busy || d.date === date} onclick={() => moveTo(d.date, close)}>
							{weekday(d.date)} {parseDate(d.date).getDate()}.
						</button>
					{/each}
					<button type="button" class="btn quiet sm" onclick={() => (moving = false)}>Fortryd</button>
				</div>
			{:else}
				<div class="btns">
					<button type="button" class="btn" disabled={busy} onclick={() => (moving = true)}><Icon name="move" />Flyt</button>
					<button type="button" class="btn" disabled={busy} onclick={() => onchooser(meal.extra ? { extra: true, replaceId: meal.id } : MAIN)}>Skift ret</button>
					<button type="button" class="btn danger" disabled={busy} onclick={remove}>Fjern</button>
				</div>
			{/if}
		{/snippet}
	</Sheet>
{/if}

{#snippet plate()}
	<Plate src={recipe?.image_url} seed={recipe?.id} size={44} />
{/snippet}

<style>
	.to {
		margin-bottom: 8px;
	}
	.btns .btn {
		padding-inline: 8px;
	}
</style>
