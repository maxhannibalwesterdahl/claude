<script lang="ts">
	import { longDate } from '$lib/dates';
	import { planApi } from '$lib/planApi';
	import { clock } from '$lib/resume.svelte';
	import type { RecipeBrief } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import Plate from '$lib/ui/Plate.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		onclose: () => void;
	}
	let { week, onclose }: Props = $props();

	/** En dag i forslaget. Efter et byt står der ingen grund. */
	interface Row {
		date: string;
		recipe: RecipeBrief;
		reason: string | null;
	}

	const plan = $derived(week.plan);
	const planId = $derived(plan?.id);
	// Ledige dage, der ikke er gået.
	const empty = $derived(plan?.days.filter((d) => !d.meal && !d.child && d.date >= clock.today).length ?? 0);
	const eyebrow = $derived(empty === 1 ? '1 ledig dag' : `${empty} ledige dage`);

	let rows = $state<Row[]>([]);
	// Reserverne, i den rækkefølge de bliver byttet ind.
	let pool = $state<RecipeBrief[]>([]);
	let loaded = $state(false);
	let error = $state('');
	let busy = $state(false);

	$effect(() => {
		const id = planId;
		if (!id) return;
		let stale = false;
		planApi
			.fillProposal(id, clock.today)
			.then((p) => {
				if (stale) return;
				rows = p.days.map((d) => ({ date: d.date, recipe: d.recipe, reason: d.reason }));
				pool = p.alternatives;
				loaded = true;
			})
			.catch((e) => {
				if (!stale) error = say(e);
			});
		return () => {
			stale = true;
		};
	});

	/** Byt retten på dagen med den næste reserve. Den, der går ud, ryger bagerst i reserverne. */
	function swap(i: number) {
		const next = pool[0];
		if (!next) return;
		pool = [...pool.slice(1), rows[i].recipe];
		rows[i] = { date: rows[i].date, recipe: next, reason: null };
	}

	/** Dagen skal stå tom. Retten går tilbage til reserverne. */
	function leave(i: number) {
		pool = [...pool, rows[i].recipe];
		rows = rows.filter((_, j) => j !== i);
	}

	async function save(close: () => void) {
		if (!planId || busy || !rows.length) return;
		busy = true;
		const days = rows.map((r) => ({ date: r.date, recipe_id: r.recipe.id }));
		const ok = await week.run(() => planApi.fill(planId, days, clock.today));
		busy = false;
		if (ok) close();
	}
</script>

{#if plan}
	<Sheet title="Fyld ugen" {eyebrow} {onclose}>
		{#if error}<p class="msg" role="alert">{error}</p>{/if}
		{#if week.error}<p class="msg" role="alert">{week.error}</p>{/if}

		{#if empty === 0}
			<p class="empty">Alle dage har en ret.</p>
		{:else if !loaded && !error}
			<p class="empty">Finder retter til de ledige dage.</p>
		{:else if loaded && !rows.length}
			<p class="empty">Der er ingen opskrifter at foreslå. Læg nogle i jeres samling først.</p>
		{:else}
			{#each rows as r, i (r.date)}
				<div class="row">
					<div class="op">
						<Plate src={r.recipe.image_url} seed={r.recipe.id} size={44} lazy />
						<span class="grow">
							<span class="n">{r.recipe.title}</span>
							<span class="m">{longDate(r.date)}{r.reason ? ` · ${r.reason}` : ''}</span>
						</span>
						<button type="button" class="btn sm" disabled={!pool.length} onclick={() => swap(i)}>Byt</button>
						<button type="button" class="rnd" aria-label="Lad {longDate(r.date)} stå tom" onclick={() => leave(i)}>
							<Icon name="x" />
						</button>
					</div>
				</div>
			{/each}
		{/if}

		{#snippet footer(close)}
			<div class="btns">
				<button type="button" class="btn primary" disabled={busy || !rows.length} onclick={() => save(close)}>Læg ind</button>
				<button type="button" class="btn quiet" onclick={close}>Annuller</button>
			</div>
		{/snippet}
	</Sheet>
{/if}

<style>
	.row {
		margin-inline: var(--gutter);
		padding-block: 12px;
		border-bottom: 1px solid var(--line);
	}
	.op {
		margin-inline: 0;
		border-bottom: 0;
	}
	.op .n,
	.op .m {
		display: block;
	}
</style>
