<script lang="ts">
	import { weekdayName } from '$lib/dates';
	import { formatNumber, mult } from '$lib/format';
	import type { Day, Wish } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';

	interface Props {
		day: Day;
		/** Ønsker, der tilbydes, når der ingen ret er i aften. */
		wishes?: Wish[];
		/** Åbner dagen (arket med retten, eller vælgeren, når dagen er tom). */
		onopen: () => void;
		/** Åbner vælgeren for aftensmaden. */
		onchoose: () => void;
		onplace?: (wish: Wish) => void;
	}
	let { day, wishes = [], onopen, onchoose, onplace }: Props = $props();

	const meal = $derived(day.meal);
	const recipe = $derived(meal?.kind === 'opskrift' ? meal.recipe : null);
	const husk = $derived(meal?.reminders.filter((r) => !r.done).map((r) => r.text) ?? []);
	const meta = $derived(
		[
			recipe?.servings ? `${formatNumber(recipe.servings * meal!.multiplier)} pers.` : '',
			meal && !recipe ? 'Ingen indkøb' : '',
			day.child ? `Barnet: ${day.child.title}` : '',
			husk.length ? `Husk: ${husk.join(', ')}` : ''
		]
			.filter(Boolean)
			.join(' · ')
	);
</script>

<!-- Dagens ret fylder mest: det er den, der skal laves. Tryk på kortet åbner dagen. -->
<section class="card tonight" aria-label="I aften">
	<button type="button" class="body" data-day={day.date} onclick={onopen}>
		<span class="grow">
			<span class="lab">I aften · {weekdayName(day.date)}</span>
			{#if meal}
				<span class="serif dish">{meal.title}{#if recipe && meal.multiplier !== 1}&nbsp;{mult(meal.multiplier)}{/if}</span>
			{:else}
				<span class="serif dish muted">Ingen ret endnu.</span>
			{/if}
			{#if meta}<span class="small muted">{meta}</span>{/if}
		</span>
		{#if recipe}<Plate src={recipe.image_url} seed={recipe.id} size={72} />{/if}
	</button>
	{#if !meal && !day.child && wishes.length}
		<div class="chips">
			{#each wishes as w (w.id)}
				<button type="button" class="chip" onclick={() => onplace?.(w)}><span class="ellipsis">{w.title}</span></button>
			{/each}
		</div>
	{/if}
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
	.chips {
		margin-top: 10px;
	}
	.btns {
		margin-top: 14px;
	}
</style>
