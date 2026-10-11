<script lang="ts">
	import { untrack } from 'svelte';
	import { weekday } from '$lib/dates';
	import { formatQuantity } from '$lib/format';
	import { groupLines } from '$lib/lines';
	import { planApi } from '$lib/planApi';
	import type { Day, LineState, Meal, MealLine, Plan } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import IngredientRow from '$lib/ui/IngredientRow.svelte';
	import Segmented from '$lib/ui/Segmented.svelte';
	import { leftoverSources, lowerFirst, weekdayLower, type Week } from './week.svelte';

	interface Props {
		week: Week;
		plan: Plan;
		day: Day;
		/** Retten, panelet handler om. null: dagen har kun barnets ret. */
		meal: Meal | null;
		/** Panelet viser barnets ret. */
		forChild: boolean;
		/** En ændring er på vej: knapperne er slået fra. */
		busy: boolean;
		/** Kører en ændring og siger det roligt, hvis det ikke gik. Svarer true, når det lykkedes. */
		run: (fn: () => Promise<Plan>) => Promise<boolean>;
		/** Åbner vælgeren for barnets ret. */
		onchild: () => void;
		/** Skifter mellem husstandens og barnets ret. */
		onswap: (child: boolean) => void;
	}
	let { week, plan, day, meal, forChild, busy, run, onchild, onswap }: Props = $props();

	const MULTS = [
		{ value: 0.5, label: '×½' },
		{ value: 1, label: '×1' },
		{ value: 2, label: '×2' }
	];

	const recipe = $derived(meal?.kind === 'opskrift' ? meal.recipe : null);
	// Tidligste dag først, som ugen læses.
	const sources = $derived(meal ? leftoverSources(plan, day.date, meal.id).reverse() : []);
	const groups = $derived(meal ? groupLines(meal.lines) : []);
	const have = $derived(meal?.lines.filter((l) => l.state).length ?? 0);
	// Første senere dag uden ret: den kan få resterne, hvis der laves dobbelt.
	const later = $derived(plan.days.find((d) => d.date > day.date && !d.meal) ?? null);
	const canDouble = $derived(!!recipe && !forChild && meal!.multiplier === 1 && !!later);

	// Mængden: det sidst trykkede gælder. Trykkes der flere gange hurtigt, sendes
	// ét ad gangen, og kun det seneste valg sendes videre, så visningen ikke hopper.
	let wanted = $state<number | null>(null);
	let sending = false;
	async function setMultiplier(value: number) {
		if (!meal) return;
		const id = meal.id;
		wanted = value;
		if (sending) return;
		sending = true;
		try {
			while (wanted !== null) {
				const v: number = wanted;
				const ok = await run(() => planApi.patchMeal(id, { multiplier: v }));
				if (!ok || wanted === v) wanted = null;
			}
		} finally {
			sending = false;
		}
	}

	/** Flueben vises med det samme og rulles tilbage, hvis serveren afviser dem.
	 *  Den ønskede tilstand sendes (ikke "skift"), så gentagne tryk ikke vender om. */
	async function setLine(line: MealLine, state: LineState) {
		if (!meal) return;
		const id = meal.id;
		const before = line.state;
		line.state = state;
		week.error = '';
		try {
			await week.mutate(() => planApi.setLine(id, line.line_id, state));
		} catch (e) {
			line.state = before;
			week.error = say(e);
		}
	}

	/** Lav dobbelt i dag, og læg resterne på den første senere dag uden ret.
	 *  Går det andet kald galt, bliver mængden stående, og sætningen vises. */
	async function doubleForLater() {
		if (!meal || !later) return;
		const id = meal.id;
		const target = later.date;
		if (await run(() => planApi.patchMeal(id, { multiplier: 2 }))) {
			await run(() => planApi.setSlot(plan, target, false, { kind: 'rester', leftover_from_id: id }));
		}
	}

	// Når retten får en rest-kilde, skal ingredienserne frem: nu kan det markeres,
	// hvad resten dækker.
	let list: HTMLElement | undefined = $state();
	let lastSource = untrack(() => meal?.leftover_from?.id ?? null);
	$effect(() => {
		const source = meal?.leftover_from?.id ?? null;
		if (source !== null && source !== lastSource) list?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		lastSource = source;
	});
</script>

<div class="panel" aria-busy={busy}>
	{#if forChild}
		<button type="button" class="link up" onclick={() => onswap(false)}><Icon name="left" size={16} stroke={2.2} />Aftensmad</button>
	{/if}

	{#if meal && !recipe}
		<p class="pad small muted plain">
			{#if meal.kind === 'rester' && meal.leftover_from}Fra {weekdayLower(meal.leftover_from.date)} · ingen indkøb{:else}Ingen indkøb{/if}
		</p>
	{/if}

	{#if meal && recipe}
		<div class="kv">
			<p class="k">Mængde{#if recipe.servings}<small>Opskriften er til {recipe.servings}</small>{/if}</p>
			<Segmented label="Mængde" options={MULTS} value={wanted ?? meal.multiplier} onchange={setMultiplier} />
		</div>
	{/if}

	{#if !forChild}
		<div class="kv">
			{#if day.child}
				<!-- Tryk på navnet viser barnets ret med de samme muligheder som husstandens. -->
				<button type="button" class="k open" onclick={() => onswap(true)}>
					Barnet<small>{day.child.title}</small>
				</button>
				<span class="acts">
					<button type="button" class="v" disabled={busy} onclick={onchild}>Skift</button>
					<button
						type="button"
						class="btn quiet sm"
						disabled={busy}
						aria-label="Fjern barnets ret"
						onclick={() => {
							const id = day.child!.id;
							run(() => planApi.remove(id));
						}}>Fjern</button
					>
				</span>
			{:else}
				<p class="k">Barnet<small>Samme som de voksne</small></p>
				<button type="button" class="v" disabled={busy} onclick={onchild}>Noget andet</button>
			{/if}
		</div>
	{/if}

	{#if meal && recipe}
		{#if sources.length}
			<label class="kv">
				<span class="k">Rester<small>Bruger rest fra</small></span>
				<select
					value={meal.leftover_from?.id ?? ''}
					disabled={busy}
					onchange={(e) => {
						const v = e.currentTarget.value;
						const id = meal.id;
						run(() => planApi.patchMeal(id, { leftover_from_id: v ? Number(v) : null }));
					}}
				>
					<option value="">Ingen</option>
					{#each sources as s (s.id)}
						<option value={s.id}>{weekday(s.date)}: {s.title}</option>
					{/each}
				</select>
			</label>
		{/if}
		{#if meal.suggest_double && meal.leftover_from}
			{@const from = meal.leftover_from}
			<div class="kv">
				<p class="k">Lav dobbelt<small>af {lowerFirst(from.title)} ({weekday(from.date)})</small></p>
				<button type="button" class="v" disabled={busy} onclick={() => run(() => planApi.patchMeal(from.id, { multiplier: 2 }))}>Sæt ×2</button>
			</div>
		{/if}
		{#if canDouble && later}
			<div class="kv">
				<p class="k">{sources.length ? 'Lav dobbelt' : 'Rester'}<small>{sources.length ? 'Så' : 'Lav dobbelt, så'} er {weekdayLower(later.date)} klaret</small></p>
				<button type="button" class="v" disabled={busy} onclick={doubleForLater}>Lav ×2</button>
			</div>
		{/if}
	{/if}

	{#if meal?.lines.length}
		<p class="sl" bind:this={list}>Ingredienser<span>{have} af {meal.lines.length} har I hjemme</span></p>
		{#if meal.leftover_from}
			<p class="note">Tryk rest på det, resten fra {lowerFirst(meal.leftover_from.title)} dækker.</p>
		{/if}
		{#each groups as g}
			{#if g.name}<p class="group pad">{g.name}</p>{/if}
			{#each g.lines as l (l.line_id)}
				<IngredientRow
					qty={formatQuantity(l.quantity, l.quantity_max, l.unit)}
					name={l.item}
					note={l.note}
					dim={l.ingredient?.pantry}
					checked={!!l.state}
					ontoggle={(next) => setLine(l, next ? 'hjemme' : null)}
					tickLabel={l.state === 'rest' ? 'dækkes af resten' : 'har hjemme'}
				>
					{#snippet trailing()}
						{#if l.ingredient?.pantry}<span class="tag">basis</span>{/if}
						{#if meal.leftover_from}
							<button
								type="button"
								class="chip"
								aria-pressed={l.state === 'rest'}
								aria-label="{l.item}: dækkes af resten"
								onclick={() => setLine(l, l.state === 'rest' ? null : 'rest')}>rest</button
							>
						{/if}
					{/snippet}
				</IngredientRow>
			{/each}
		{/each}
	{/if}

	{#if recipe}
		<p class="links pad">
			<a class="link" href="/opskrift/{recipe.id}">Se opskriften</a>
			{#if !forChild}<a class="link" href="/lav/{day.date}">Lav mad</a>{/if}
		</p>
	{/if}
</div>

<style>
	.panel {
		transition: opacity var(--t-tick);
	}
	.panel[aria-busy='true'] {
		opacity: 0.7;
	}
	.plain {
		padding-bottom: 6px;
	}
	.up {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		min-height: var(--tap);
		margin-inline: var(--gutter);
	}
	.open {
		flex: 1;
		align-self: stretch;
		text-align: left;
	}
	.acts {
		flex: none;
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.v:disabled {
		opacity: 0.5;
		cursor: default;
	}
	/* Feltet fylder ikke hele rækken: navnet til venstre skal kunne læses. */
	select {
		flex: 0 1 56%;
		width: auto;
		min-height: var(--tap);
	}
	.group {
		padding-top: 12px;
		font-size: var(--fs-cap);
		font-weight: 700;
	}
	.links {
		display: flex;
		gap: 24px;
		padding-top: 6px;
	}
	.links a {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
	}
</style>
