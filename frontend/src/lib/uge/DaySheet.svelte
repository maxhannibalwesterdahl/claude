<script lang="ts">
	import { longDate, parseDate, weekday } from '$lib/dates';
	import { planApi } from '$lib/planApi';
	import type { Plan } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import MealPanel from './MealPanel.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		date: string;
		/** Åbner vælgeren for dagens ret eller barnets ret. Siden lukker dette ark. */
		onchooser: (forChild: boolean) => void;
		onclose: () => void;
	}
	let { week, date, onchooser, onclose }: Props = $props();

	/** Arket viser barnets ret i stedet for husstandens. */
	let child = $state(false);
	/** Bunden viser ugens dage i stedet for knapperne. */
	let moving = $state(false);
	let busy = $state(false);

	const plan = $derived(week.plan);
	const day = $derived(week.day(date));
	const meal = $derived(day ? (child ? day.child : day.meal) : null);
	const recipe = $derived(meal?.kind === 'opskrift' ? meal.recipe : null);

	$effect(() => {
		// Barnets ret er fjernet eller flyttet: tilbage til aftensmaden.
		if (child && day && !day.child) child = false;
	});
	$effect(() => {
		// Dagen er blevet tom (retten er fjernet eller flyttet): der er ikke mere at vise.
		if (!day || (!day.meal && !day.child)) onclose();
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

	/** Flytter retten. Står der en ret på den anden dag, bytter de plads (uden at spørge). */
	async function moveTo(target: string, close: () => void) {
		if (!meal) return;
		const id = meal.id;
		const forChild = child;
		if (await run(() => planApi.move(id, target, forChild))) close();
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
		title={meal?.title ?? 'Ingen ret endnu'}
		eyebrow={child ? `${longDate(date)} · barnets ret` : longDate(date)}
		eyebrowAbove
		aside={recipe ? plate : undefined}
		{onclose}
	>
		{#if week.error}<p class="msg" role="alert">{week.error}</p>{/if}
		{#key `${child}:${meal?.id}`}
			<MealPanel
				{week}
				{plan}
				{day}
				{meal}
				forChild={child}
				{busy}
				{run}
				onchild={() => onchooser(true)}
				onswap={(c) => {
					child = c;
					moving = false;
				}}
			/>
		{/key}

		{#snippet footer(close)}
			{#if !meal}
				<div class="btns">
					<button type="button" class="btn primary" onclick={() => onchooser(false)}>Vælg ret</button>
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
					<button type="button" class="btn" disabled={busy} onclick={() => onchooser(child)}>Skift ret</button>
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
