<script lang="ts">
	import { weekdayName } from '$lib/dates';
	import { formatNumber, mult } from '$lib/format';
	import type { Day } from '$lib/types';
	import { draggable, dropzone } from '$lib/ui/drag.svelte';
	import { mealName } from '$lib/ui/glide.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';

	interface Props {
		day: Day;
		/** Åbner dagen (arket med retten, eller vælgeren, når dagen er tom). */
		onopen: () => void;
		/** Åbner vælgeren for aftensmaden. */
		onchoose: () => void;
		/** Noget er trukket hen på i aften ("meal:<id>", "wish:<id>" eller "recipe:<id>"). */
		ondrop: (payload: string) => void;
	}
	let { day, onopen, onchoose, ondrop }: Props = $props();

	const meal = $derived(day.meal);
	const recipe = $derived(meal?.kind === 'opskrift' ? meal.recipe : null);
	const husk = $derived(meal?.reminders.filter((r) => !r.done).map((r) => r.text) ?? []);
	const meta = $derived(
		[
			recipe?.servings ? `${formatNumber(recipe.servings * meal!.multiplier)} pers.` : '',
			meal && !recipe ? 'Ingen indkøb' : '',
			day.extras.length ? `Også: ${day.extras.map((x) => x.title).join(', ')}` : '',
			husk.length ? `Husk: ${husk.join(', ')}` : ''
		]
			.filter(Boolean)
			.join(' · ')
	);
</script>

<!-- Dagens ret fylder mest: det er den, der skal laves. Tryk på kortet åbner dagen. -->
<section class="card tonight" aria-label="I aften" use:dropzone={ondrop}>
	<button type="button" class="body" data-day={day.date} onclick={onopen} use:draggable={meal ? `meal:${meal.id}` : ''}>
		<span class="grow">
			<span class="lab">I aften · {weekdayName(day.date)}</span>
			{#if meal}
				<span class="serif dish" style:view-transition-name={mealName(meal.id)}>{meal.title}{#if recipe && meal.multiplier !== 1}&nbsp;{mult(meal.multiplier)}{/if}</span>
			{:else}
				<span class="serif dish muted">Ingen ret endnu.</span>
			{/if}
			{#if meta}<span class="small muted">{meta}</span>{/if}
		</span>
		{#if recipe}<Plate src={recipe.image_url} seed={recipe.id} size={72} />{/if}
	</button>
	<div class="btns">
		{#if recipe}
			<a class="btn primary" href="/lav/{day.date}"><Icon name="play" size={16} />Lav mad</a>
		{/if}
		{#if meal}
			<button type="button" class="btn" onclick={onchoose}>Skift ret</button>
		{:else}
			<button type="button" class="btn primary" onclick={onchoose}>Vælg ret</button>
		{/if}
	</div>
</section>

<style>
	.tonight {
		margin: 12px var(--gutter) 6px;
		padding: 16px;
	}
	.body {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		width: 100%;
		min-height: var(--tap);
		border-radius: var(--r-small);
	}
	.body .grow > span {
		display: block;
	}
	.dish {
		margin-block: 6px 4px;
		font-size: var(--fs-dish);
		line-height: 28px;
		font-weight: 700;
	}
	.btns {
		margin-top: 14px;
	}
</style>
