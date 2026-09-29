<script lang="ts">
	import { ApiError } from './api';
	import { shortDate, weekday, weekdayName } from './dates';
	import { formatQuantity } from './format';
	import { groupLines } from './lines';
	import MealChooser from './MealChooser.svelte';
	import { planApi } from './planApi';
	import type { Meal, MealLine, Plan, SlotChoice } from './types';

	interface Props {
		plan: Plan;
		date: string;
		forChild: boolean;
		meal: Meal | null;
		onplan: (plan: Plan) => void;
	}
	let { plan, date, forChild, meal, onplan }: Props = $props();

	let choosing = $state(false);
	let busy = $state(false);
	let error = $state('');

	const MULTS: [number, string][] = [
		[0.5, '×½'],
		[1, '×1'],
		[2, '×2']
	];

	const sources = $derived(
		plan.days
			.filter((d) => d.date < date)
			.flatMap((d) => [d.meal, d.child])
			.filter((m): m is Meal => !!m && m.kind === 'opskrift' && m.id !== meal?.id)
	);
	const groups = $derived(meal ? groupLines(meal.lines) : []);
	const toBuy = $derived(meal?.lines.filter((l) => !l.state && !l.ingredient?.pantry).length ?? 0);

	async function run(fn: () => Promise<Plan>) {
		busy = true;
		error = '';
		try {
			onplan(await fn());
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Noget gik galt';
		} finally {
			busy = false;
		}
	}

	function choose(choice: SlotChoice) {
		choosing = false;
		run(() => planApi.setSlot(plan, date, forChild, choice));
	}

	function toggleHome(line: MealLine) {
		if (!meal) return;
		const id = meal.id;
		run(() => planApi.setLine(id, line.line_id, line.state ? null : 'hjemme'));
	}

	function toggleRest(line: MealLine) {
		if (!meal) return;
		const id = meal.id;
		run(() => planApi.setLine(id, line.line_id, line.state === 'rest' ? null : 'rest'));
	}

	function moveTo(target: string) {
		if (!meal || !target) return;
		const id = meal.id;
		run(() => planApi.move(id, target, forChild));
	}

	function remove() {
		if (!meal) return;
		const id = meal.id;
		run(() => planApi.remove(id));
	}
</script>

{#if meal}
	<article class="meal card" aria-busy={busy}>
		<div class="head">
			{#if meal.recipe?.image_url}
				<img src={meal.recipe.image_url} alt="" />
			{/if}
			<div class="grow">
				{#if forChild}<div class="label">Barnet</div>{/if}
				<h3>
					{#if meal.recipe}
						<a href="/opskrift/{meal.recipe.id}">{meal.title}</a>
					{:else}
						{meal.title}
					{/if}
				</h3>
				<div class="muted small">
					{#if meal.kind === 'opskrift' && meal.recipe?.servings}
						Opskrift til {meal.recipe.servings} pers.
					{:else if meal.kind === 'rester' && meal.leftover_from}
						Fra {weekdayName(meal.leftover_from.date).toLowerCase()} · intet indkøb
					{:else if meal.kind !== 'opskrift'}
						Intet indkøb
					{/if}
				</div>
			</div>
		</div>

		{#if meal.kind === 'opskrift' && meal.recipe}
			<div class="controls">
				<div class="seg" role="group" aria-label="Gange">
					{#each MULTS as [value, label]}
						<button
							class:on={meal.multiplier === value}
							aria-pressed={meal.multiplier === value}
							disabled={busy}
							onclick={() => run(() => planApi.patchMeal(meal!.id, { multiplier: value }))}>{label}</button
						>
					{/each}
				</div>
				{#if sources.length}
					<label class="rest-from">
						<span class="muted small">Bruger rest fra</span>
						<select
							value={meal.leftover_from?.id ?? ''}
							disabled={busy}
							onchange={(e) => {
								const v = e.currentTarget.value;
								run(() => planApi.patchMeal(meal!.id, { leftover_from_id: v ? Number(v) : null }));
							}}
						>
							<option value="">Ingen</option>
							{#each sources as s (s.id)}
								<option value={s.id}>{weekday(s.date)}: {s.title}</option>
							{/each}
						</select>
					</label>
				{/if}
			</div>
		{/if}

		{#if meal.suggest_double && meal.leftover_from}
			<div class="suggest">
				<span class="grow">Lav dobbelt portion af <strong>{meal.leftover_from.title}</strong> ({weekday(meal.leftover_from.date)})?</span>
				<button
					class="primary"
					disabled={busy}
					onclick={() => run(() => planApi.patchMeal(meal!.leftover_from!.id, { multiplier: 2 }))}>Sæt ×2</button
				>
			</div>
		{/if}

		{#if meal.lines.length}
			<details class="lines" open>
				<summary>
					Ingredienser
					<span class="muted small">{toBuy} skal købes</span>
				</summary>
				{#if meal.leftover_from}
					<p class="muted small">Tryk "rest" på det, resten fra {meal.leftover_from.title.toLowerCase()} dækker.</p>
				{/if}
				{#each groups as g}
					{#if g.name}<h4>{g.name}</h4>{/if}
					<ul>
						{#each g.lines as l (l.line_id)}
							<li class:done={!!l.state} class:pantry={l.ingredient?.pantry}>
								<label>
									<input type="checkbox" checked={!!l.state} disabled={busy} onchange={() => toggleHome(l)} />
									<span class="qty">{formatQuantity(l.quantity, l.quantity_max, l.unit)}</span>
									<span class="grow">
										{l.item}{#if l.is_main}<span class="star">★</span>{/if}
										{#if l.state === 'rest'}<span class="badge ok">rest</span>
										{:else if l.state === 'hjemme'}<span class="muted small">har hjemme</span>
										{:else if l.ingredient?.pantry}<span class="muted small">basis</span>{/if}
									</span>
								</label>
								{#if meal.leftover_from}
									<button class="plain rest" class:on={l.state === 'rest'} disabled={busy} onclick={() => toggleRest(l)}>rest</button>
								{/if}
							</li>
						{/each}
					</ul>
				{/each}
			</details>
		{/if}

		<div class="actions">
			<button disabled={busy} onclick={() => (choosing = true)}>Skift</button>
			<label class="move">
				<select value="" disabled={busy} onchange={(e) => moveTo(e.currentTarget.value)} aria-label="Flyt til dag">
					<option value="">Flyt til…</option>
					{#each plan.days.filter((d) => d.date !== date) as d}
						<option value={d.date}>{weekdayName(d.date)} {shortDate(d.date)}</option>
					{/each}
				</select>
			</label>
			<button class="danger" disabled={busy} onclick={remove}>Fjern</button>
		</div>
		{#if error}<p class="error">{error}</p>{/if}
	</article>
{:else}
	<button class="empty-slot" disabled={busy} onclick={() => (choosing = true)}>
		+ {forChild ? 'Ret til barnet' : 'Vælg aftensmad'}
	</button>
	{#if error}<p class="error">{error}</p>{/if}
{/if}

{#if choosing}
	<MealChooser {plan} {date} {forChild} onchoose={choose} oncancel={() => (choosing = false)} />
{/if}

<style>
	.meal {
		padding: 12px;
		display: grid;
		gap: 12px;
	}
	.meal[aria-busy='true'] {
		opacity: 0.7;
	}
	.head {
		display: flex;
		gap: 12px;
		align-items: center;
	}
	.head img {
		width: 72px;
		height: 72px;
		border-radius: 10px;
		object-fit: cover;
		flex: none;
	}
	h3 {
		margin: 0;
		font-size: 1.15rem;
		line-height: 1.25;
	}
	h3 a {
		color: inherit;
		text-decoration: none;
	}
	.label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 16px;
		align-items: end;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--line);
		border-radius: 10px;
		overflow: hidden;
		flex: none;
	}
	.seg button {
		border: none;
		border-radius: 0;
		min-width: 52px;
		justify-content: center;
		font-weight: 600;
	}
	.seg button + button {
		border-left: 1px solid var(--line);
	}
	.seg button.on {
		background: var(--accent);
		color: var(--accent-fg);
	}
	.rest-from {
		display: grid;
		gap: 2px;
		flex: 1 1 180px;
		min-width: 0;
	}
	.suggest {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
		background: var(--accent-soft);
		border-radius: 10px;
		padding: 8px 10px;
	}
	.lines summary {
		cursor: pointer;
		font-weight: 600;
		display: flex;
		gap: 8px;
		align-items: baseline;
		padding: 4px 0;
	}
	h4 {
		margin: 10px 0 2px;
		font-size: 0.9rem;
	}
	.lines ul {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.lines li {
		display: flex;
		align-items: center;
		gap: 6px;
		border-bottom: 1px solid var(--line);
	}
	.lines label {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 46px;
		cursor: pointer;
	}
	.lines input[type='checkbox'] {
		width: 22px;
		height: 22px;
		min-height: 0;
		flex: none;
		accent-color: var(--accent);
	}
	.qty {
		flex: 0 0 auto;
		min-width: 56px;
		max-width: 40%;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	li.done .grow {
		text-decoration: line-through;
		color: var(--muted);
	}
	li.pantry .grow {
		color: var(--muted);
	}
	.star {
		color: var(--star);
		margin-left: 4px;
	}
	.badge {
		margin-left: 6px;
	}
	.rest {
		font-size: 0.8rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		padding: 2px 10px;
		color: var(--muted);
	}
	.rest.on {
		background: var(--accent-soft);
		border-color: var(--accent);
		color: var(--accent);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.move {
		flex: 1 1 140px;
		min-width: 0;
	}
	.empty-slot {
		width: 100%;
		justify-content: center;
		border-style: dashed;
		min-height: 64px;
		color: var(--accent);
		font-weight: 600;
		background: transparent;
	}
</style>
