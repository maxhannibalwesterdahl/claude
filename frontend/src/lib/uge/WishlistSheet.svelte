<script lang="ts">
	import { weekday } from '$lib/dates';
	import { planApi } from '$lib/planApi';
	import { clock } from '$lib/resume.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		/** Åbner vælgeren, hvor flere retter kan lægges på listen. */
		onadd: () => void;
		onclose: () => void;
	}
	let { week, onadd, onclose }: Props = $props();

	const plan = $derived(week.plan);
</script>

{#if plan}
	<Sheet title="Ønskeliste" eyebrow="Retter, I vil have i ugen. Tryk på en dag for at lægge retten der." {onclose}>
		{#if week.error}<p class="msg" role="alert">{week.error}</p>{/if}
		{#each plan.wishlist as w (w.id)}
			<div class="wish">
				<div class="op">
					{#if w.recipe}<Plate src={w.recipe.image_url} seed={w.recipe.id} size={44} lazy />{/if}
					<span class="grow n">
						{#if w.recipe}<a href="/opskrift/{w.recipe.id}">{w.title}</a>{:else}{w.title}{/if}
					</span>
					<button type="button" class="rnd" aria-label="Fjern {w.title} fra ønskelisten" onclick={() => week.run(() => planApi.removeWish(w.id))}>
						<Icon name="x" />
					</button>
				</div>
				<!-- Ledige dage er tegnet op i tomat. En dag med en ret kan også vælges: så spørges der først. -->
				<div class="days" role="group" aria-label="Læg {w.title} på en dag">
					{#each plan.days as d (d.date)}
						{@const past = d.date < clock.today}
						<button
							type="button"
							class="chip"
							class:a={!d.meal && !past}
							disabled={past}
							title={past ? 'Dagen er gået' : d.meal ? `Erstatter ${d.meal.title}` : 'Ledig'}
							onclick={() => week.placeWish(w.id, d)}>{weekday(d.date)}</button
						>
					{/each}
				</div>
			</div>
		{:else}
			<p class="empty">Ønskelisten er tom.</p>
		{/each}

		{#snippet footer()}
			<div class="btns">
				{#if plan.wishlist.length && week.freeDays > 0}
					<button type="button" class="btn primary" onclick={() => week.distribute()}>Fordel ønsker</button>
				{/if}
				<button type="button" class="btn" onclick={onadd}>Tilføj ønsker</button>
			</div>
		{/snippet}
	</Sheet>
{/if}

<style>
	.wish {
		margin-inline: var(--gutter);
		padding-bottom: 12px;
		border-bottom: 1px solid var(--line);
	}
	.op {
		margin-inline: 0;
		border-bottom: 0;
	}
	.op a {
		text-decoration: none;
	}
	/* Syv små dage på én linje. */
	.days {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
		gap: 4px;
	}
	.days .chip {
		justify-content: center;
		padding: 0;
	}
</style>
