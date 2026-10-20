<script lang="ts">
	import { longDate, parseDate, weekday } from '$lib/dates';
	import { mult } from '$lib/format';
	import type { Day, Plan } from '$lib/types';
	import { draggable, dropzone } from '$lib/ui/drag.svelte';
	import { mealName } from '$lib/ui/glide.svelte';
	import Plate from '$lib/ui/Plate.svelte';

	interface Props {
		plan: Plan;
		today: string;
		/** Åbner dagen: arket med retten, eller vælgeren, når dagen er tom. */
		onopen: (date: string) => void;
		/** Noget er sluppet på dagen: "meal:<id>", "wish:<id>" eller "recipe:<id>". */
		ondrop: (payload: string, day: Day) => void;
	}
	let { plan, today, onopen, ondrop }: Props = $props();
</script>

<!-- iPad og computer: hele ugen på én gang. Retter trækkes mellem dagene med
     musen eller ved at holde fingeren på dem; det samme kan gøres fra dagens ark
     (Flyt) og fra ønskelisten. Hver ret glider til sin nye dag (mealName). -->
<div class="wk">
	{#each plan.days as d (d.date)}
		{@const meal = d.meal}
		{@const recipe = meal?.kind === 'opskrift' ? meal.recipe : null}
		{@const isToday = d.date === today}
		<!-- Dagen åbnes med knappen i toppen (tastatur og skærmlæser). Tryk hvor
		     som helst i cellen gør det samme for mus og finger. -->
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div
			class="card cell"
			class:past={d.date < today}
			class:today={isToday}
			class:void={!meal && !d.extras.length}
			onclick={() => onopen(d.date)}
			use:dropzone={(payload) => ondrop(payload, d)}
		>
			<button type="button" class="d" data-day={d.date} aria-label="{longDate(d.date)}: {meal?.title ?? 'ingen ret'}">
				{#if isToday}I aften{:else}{weekday(d.date)} {parseDate(d.date).getDate()}.{/if}
			</button>
			{#if meal}
				<div class="meal" style:view-transition-name={mealName(meal.id)} use:draggable={`meal:${meal.id}`}>
					{#if recipe}<Plate src={recipe.image_url} seed={recipe.id} size={44} lazy />{/if}
					<span class="n">{meal.title}{#if recipe && meal.multiplier !== 1}&nbsp;{mult(meal.multiplier)}{/if}</span>
				</div>
			{:else if !d.extras.length}
				<p class="hint">Træk en ret hertil</p>
			{/if}
			{#each d.extras as x (x.id)}
				<p class="x" style:view-transition-name={mealName(x.id)} use:draggable={`meal:${x.id}`}>+ {x.title}</p>
			{/each}
			{#if meal && !recipe}
				<p class="c">ingen indkøb</p>
			{/if}
		</div>
	{/each}
</div>

<style>
	.wk {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: 10px;
		padding-inline: var(--gutter);
	}
	.cell {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 180px;
		padding: 10px;
		border-radius: 14px;
		font-size: 15px;
		cursor: pointer;
	}
	.past {
		opacity: 0.55;
	}
	/* I dag: tomatfarvet kant og teksten "I aften" (ikke farven alene). */
	.today {
		box-shadow:
			0 0 0 2px var(--tomat),
			var(--shadow);
	}
	.void {
		background: none;
		box-shadow: none;
		outline: 1.5px dashed var(--chipline);
		outline-offset: -1.5px;
	}
	.void.today {
		outline-color: var(--tomat);
	}
	/* Hele cellen er trykfladen, så knappen selv behøver ikke at være 44px høj. */
	.d {
		font-size: 12.5px;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.today .d {
		color: var(--tomat);
	}
	.meal {
		display: flex;
		flex-direction: column;
		gap: 8px;
		cursor: grab;
	}
	/* Ekstra retter: én pr. linje, så hver kan trækkes for sig. */
	.x {
		font-size: var(--fs-cap);
		line-height: 1.3;
		color: var(--muted);
		cursor: grab;
		hyphens: auto;
	}
	/* Cellerne er smalle: lange ord deles med bindestreg i stedet for midt i ordet. */
	.n {
		font-weight: 600;
		line-height: 1.25;
		hyphens: auto;
	}
	.hint {
		flex: 1;
		display: grid;
		place-items: center;
		text-align: center;
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	.c {
		margin-top: auto;
		font-size: var(--fs-cap);
		line-height: 1.3;
		color: var(--muted);
	}
</style>
