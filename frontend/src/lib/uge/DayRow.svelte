<script lang="ts">
	import { parseDate, weekday } from '$lib/dates';
	import { mult } from '$lib/format';
	import type { Day } from '$lib/types';
	import { draggable, dropzone } from '$lib/ui/drag.svelte';
	import { mealName } from '$lib/ui/glide.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';

	interface Props {
		day: Day;
		today: string;
		/** Åbner dagen: arket med retten, eller vælgeren, når dagen er tom. */
		onopen: () => void;
		/** Noget er trukket hen på dagen ("meal:<id>", "wish:<id>" eller "recipe:<id>"). */
		ondrop: (payload: string) => unknown;
	}
	let { day, today, onopen, ondrop }: Props = $props();

	const past = $derived(day.date < today);
	const meal = $derived(day.meal);
	const wd = $derived.by(() => {
		const s = weekday(day.date);
		return s.charAt(0).toUpperCase() + s.slice(1);
	});
	// Påmindelser, der ikke er krydset af endnu ("Husk: kød op af fryseren").
	const husk = $derived(meal?.reminders.filter((r) => !r.done).map((r) => r.text) ?? []);
	const scaled = $derived(meal?.kind === 'opskrift' && meal.multiplier !== 1 ? ` ${mult(meal.multiplier)}` : '');
</script>

<!-- Én dag i ugen på telefonen. data-day bruges af siden til at give rækken
     fokus igen, når et ark lukkes, og rækken imens har skiftet udseende.
     Hver ret har sit eget navn i overgangen (mealName), så den glider til sin nye dag. -->
{#if past}
	<!-- Dage, der er gået, fylder mindst, men kan stadig åbnes og rettes. Fluebenet
	     betyder, at dagen er gået og havde en ret (appen ved ikke, om den blev lavet). -->
	<button type="button" class="past" data-day={day.date} onclick={onopen}>
		<span class="d">{wd}</span>
		<span class="g ellipsis" style:view-transition-name={meal ? mealName(meal.id) : undefined}>
			{#if meal}{meal.title}{scaled}{:else if day.extras.length}{day.extras.map((x) => x.title).join(', ')}{:else}Ingen ret{/if}
		</span>
		{#if meal}<Icon name="check" size={17} stroke={2.4} /><span class="sr">, dagen er gået</span>{/if}
	</button>
{:else}
	<!-- Hold fingeren på retten for at trække den til en anden dag. Ekstra retter
	     kan trækkes hver for sig. Et kort tryk åbner dagen. -->
	<button type="button" class="row" data-day={day.date} onclick={onopen} use:dropzone={ondrop} use:draggable={meal ? `meal:${meal.id}` : ''}>
		<span class="d">{wd}<span>{parseDate(day.date).getDate()}.</span></span>
		<span class="g">
			{#if meal}
				<span class="n" style:view-transition-name={mealName(meal.id)}>{meal.title}{scaled}</span>
			{:else}
				<span class="c pick">{day.extras.length ? 'Vælg hovedret' : 'Vælg ret'}</span>
			{/if}
			{#if day.extras.length}
				<span class="xs">
					{#each day.extras as x (x.id)}
						<span class="x" style:view-transition-name={mealName(x.id)} use:draggable={`meal:${x.id}`}>+ {x.title}</span>
					{/each}
				</span>
			{/if}
			{#if husk.length}<span class="c husk ellipsis">Husk: {husk.join(', ')}</span>{/if}
		</span>
		{#if !meal}
			<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>
		{:else if meal.kind === 'opskrift' && meal.recipe}
			<Plate src={meal.recipe.image_url} seed={meal.recipe.id} size={34} lazy />
		{:else}
			<span class="tag">ingen indkøb</span>
		{/if}
	</button>
{/if}

<style>
	.row,
	.past {
		display: flex;
		align-items: center;
		gap: 12px;
		width: calc(100% - 2 * var(--gutter));
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
		text-align: left;
	}
	.row {
		min-height: var(--row-h);
		padding-block: 6px;
	}
	.past {
		position: relative;
		height: 34px;
		font-size: 15.5px;
		color: var(--muted);
	}
	/* Linjen er lav, men trykfladen rækker ud til 44px. */
	.past::after {
		content: '';
		position: absolute;
		inset: -5px 0;
	}
	.past :global(svg) {
		color: var(--kobt);
	}
	.d {
		flex: none;
		width: 44px;
		font-size: 15.5px;
		font-weight: 700;
		line-height: 1.2;
	}
	.past .d {
		font-weight: 600;
	}
	.d span {
		display: block;
		font-size: var(--fs-cap);
		font-weight: 500;
		color: var(--muted);
	}
	.g {
		flex: 1;
		min-width: 0;
	}
	.n,
	.c {
		display: block;
	}
	.n {
		font-size: var(--fs-row);
		font-weight: 500;
		line-height: 1.25;
	}
	.c {
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	.husk {
		color: var(--tomat);
	}
	.pick {
		font-size: 15.5px;
	}
	/* Ekstra retter: små, så hovedretten stadig fylder mest. */
	.xs {
		display: flex;
		flex-wrap: wrap;
		gap: 2px 10px;
		margin-top: 1px;
	}
	.x {
		font-size: var(--fs-cap);
		line-height: 1.5;
		color: var(--muted);
	}
</style>
