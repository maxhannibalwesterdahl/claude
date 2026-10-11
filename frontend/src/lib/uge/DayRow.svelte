<script lang="ts">
	import { parseDate, weekday } from '$lib/dates';
	import { mult } from '$lib/format';
	import type { Day, Wish } from '$lib/types';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';

	interface Props {
		day: Day;
		today: string;
		/** Ønsker, der tilbydes direkte på dagen. Kun den første ledige dag får nogen. */
		wishes?: Wish[];
		/** Åbner dagen: arket med retten, eller vælgeren, når dagen er tom. */
		onopen: () => void;
		/** Lægger et ønske på dagen. */
		onplace?: (wish: Wish) => void;
		/** Åbner vælgeren med søgefeltet klar. */
		onsearch?: () => void;
	}
	let { day, today, wishes = [], onopen, onplace, onsearch }: Props = $props();

	const past = $derived(day.date < today);
	const meal = $derived(day.meal);
	const wd = $derived.by(() => {
		const s = weekday(day.date);
		return s.charAt(0).toUpperCase() + s.slice(1);
	});
	const scaled = $derived(meal?.kind === 'opskrift' && meal.multiplier !== 1 ? ` ${mult(meal.multiplier)}` : '');
</script>

<!-- Én dag i ugen på telefonen. data-day bruges af siden til at give rækken
     fokus igen, når et ark lukkes, og rækken imens har skiftet udseende. -->
{#if past}
	<!-- Dage, der er gået, fylder mindst, men kan stadig åbnes og rettes. Fluebenet
	     betyder, at dagen er gået og havde en ret (appen ved ikke, om den blev lavet). -->
	<button type="button" class="past" data-day={day.date} onclick={onopen}>
		<span class="d">{wd}</span>
		<span class="g ellipsis">
			{#if meal}{meal.title}{scaled}{:else if day.child}Barnet: {day.child.title}{:else}Ingen ret{/if}
		</span>
		{#if meal}<Icon name="check" size={17} stroke={2.4} /><span class="sr">, dagen er gået</span>{/if}
	</button>
{:else if !meal && !day.child && wishes.length}
	<div class="row offer">
		<p class="d">{wd}<span>{parseDate(day.date).getDate()}.</span></p>
		<div class="g">
			<p class="c">Ingen ret endnu. Fra ønskelisten:</p>
			<div class="chips">
				{#each wishes as w (w.id)}
					<button type="button" class="chip" onclick={() => onplace?.(w)}><span class="ellipsis">{w.title}</span></button>
				{/each}
				<button type="button" class="chip a" data-day={day.date} onclick={onsearch}>
					<Icon name="search" size={15} stroke={2.4} />Søg
				</button>
			</div>
		</div>
	</div>
{:else}
	<button type="button" class="row" data-day={day.date} onclick={onopen}>
		<span class="d">{wd}<span>{parseDate(day.date).getDate()}.</span></span>
		<span class="g">
			{#if meal}
				<span class="n">{meal.title}{scaled}</span>
			{:else}
				<span class="c pick">Vælg ret</span>
			{/if}
			{#if day.child}<span class="c">Barnet: {day.child.title}</span>{/if}
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
	.pick {
		font-size: 15.5px;
	}
	.offer {
		align-items: flex-start;
		padding-block: 10px 14px;
	}
	.offer .d {
		padding-top: 1px;
	}
	.offer .chips {
		margin-top: 8px;
	}
</style>
