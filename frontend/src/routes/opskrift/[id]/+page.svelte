<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { confirmDialog } from '$lib/confirm.svelte';
	import { weekdayName } from '$lib/dates';
	import { formatQuantity } from '$lib/format';
	import { groupLines } from '$lib/lines';
	import PlaceSheet from '$lib/opskrifter/PlaceSheet.svelte';
	import { clock } from '$lib/resume.svelte';
	import { groupSteps } from '$lib/steps';
	import { say } from '$lib/ui/copy';
	import Hero from '$lib/ui/Hero.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import IngredientRow from '$lib/ui/IngredientRow.svelte';
	import type { Line, Plan, Recipe } from '$lib/types';

	let recipe = $state<Recipe | null>(null);
	let error = $state('');
	const warning = $derived(page.url.searchParams.get('advarsel'));
	/** Den aktuelle uge, når opskriften står på dens ønskeliste. */
	let current = $state<Plan | null>(null);
	let placing = $state(false);
	/** Det, der lige er sket i "Læg på en dag": sætningen og linket til ugen. */
	let placed = $state<{ text: string; href: string; link: string } | null>(null);

	$effect(() => {
		const id = page.params.id;
		placed = null;
		api<Recipe>(`/recipes/${id}`)
			.then((r) => (recipe = r))
			.catch((e) => (error = say(e)));
		// Kun til ordene "på ønskelisten": uden en uge, eller uden net, står de der bare ikke.
		api<Plan>(`/plans/current?today=${clock.today}`)
			.then((p) => (current = p))
			.catch(() => (current = null));
	});

	const groups = $derived(recipe ? groupLines(recipe.ingredients) : []);

	const stepGroups = $derived(groupSteps(recipe?.instructions ?? []));
	const stepCount = $derived(stepGroups.reduce((n, g) => n + g.steps.length, 0));
	const toReview = $derived(recipe?.ingredients.filter((l) => l.match_status === 'usikker' || l.match_status === 'ingen').length ?? 0);
	const wished = $derived(!!recipe && !!current?.wishlist.some((w) => w.recipe?.id === recipe?.id));
	// Kun rigtige links vises som link.
	const source = $derived(recipe?.source_url && /^https?:\/\//i.test(recipe.source_url) ? recipe.source_url : null);

	async function toggleMain(line: Line) {
		const next = !line.is_main;
		line.is_main = next;
		try {
			await api(`/lines/${line.id}/main`, { method: 'PUT', body: { is_main: next } });
		} catch (e) {
			line.is_main = !next;
			error = say(e);
		}
	}

	async function setCollection(add: boolean) {
		if (!recipe) return;
		try {
			recipe = await api<Recipe>(`/recipes/${recipe.id}/collection`, { method: add ? 'POST' : 'DELETE' });
		} catch (e) {
			error = say(e);
		}
	}

	/** Familiens egen note om barnet (rører ikke den fælles opskrift). */
	let editingNote = $state(false);
	let noteText = $state('');
	function editNote() {
		noteText = recipe?.child_note ?? '';
		editingNote = true;
	}
	async function saveNote(e: SubmitEvent) {
		e.preventDefault();
		if (!recipe) return;
		try {
			recipe = await api<Recipe>(`/recipes/${recipe.id}/note`, { method: 'PUT', body: { child_note: noteText } });
			editingNote = false;
		} catch (err) {
			error = say(err);
		}
	}

	// --- Jeres udgave: tilpasninger lagt oven på den fælles opskrift ---
	let showOriginal = $state(false);
	let adjusting = $state<number | null>(null);
	let adjSkip = $state(false);
	let adjQty = $state('');
	let extraText = $state('');
	let ownNote = $state('');
	let editingOwn = $state(false);
	const adjusted = $derived(
		!!recipe && (recipe.ingredients.some((l) => l.skipped || l.my_quantity != null) || !!recipe.extra_lines?.length)
	);

	async function adjust(path: string, method: string, body?: unknown) {
		if (!recipe) return;
		try {
			recipe = await api<Recipe>(`/recipes/${recipe.id}/adjustments/${path}`, { method, body });
		} catch (e) {
			error = say(e);
		}
	}

	function openAdjust(l: Line) {
		adjusting = adjusting === l.id ? null : l.id;
		adjSkip = !!l.skipped;
		adjQty = l.my_quantity != null ? String(l.my_quantity).replace('.', ',') : '';
	}

	async function saveAdjust(l: Line, clear = false) {
		const q = adjQty.trim() === '' ? null : Number(adjQty.replace(',', '.'));
		if (!clear && q !== null && !(q >= 0)) return;
		await adjust(`lines/${l.id}`, 'PUT', clear ? {} : { skip: adjSkip, quantity: adjSkip ? null : q });
		adjusting = null;
	}

	async function addExtra(e: SubmitEvent) {
		e.preventDefault();
		if (!extraText.trim()) return;
		await adjust('extra', 'POST', { raw: extraText });
		extraText = '';
	}

	async function saveOwnNote(e: SubmitEvent) {
		e.preventDefault();
		await adjust('note', 'PUT', { text: ownNote });
		editingOwn = false;
	}

	async function remove() {
		const id = recipe?.id;
		if (!recipe || !(await confirmDialog(`Slet "${recipe.title}"?`, 'Slet'))) return;
		try {
			await api(`/recipes/${id}`, { method: 'DELETE' });
			await goto('/opskrifter');
		} catch (e) {
			error = say(e);
		}
	}

	function onplaced(plan: Plan, date: string | null) {
		if (current && plan.id === current.id) current = plan;
		placed = date
			? { text: `Lagt på ${weekdayName(date).toLowerCase()}.`, href: `/?plan=${plan.id}&dag=${date}`, link: 'Se ugen' }
			: { text: 'Lagt på ønskelisten.', href: `/?plan=${plan.id}&onsker=1`, link: 'Se ønskelisten' };
	}
</script>

<main>
	<Hero src={recipe?.image_url} seed={recipe?.id ?? page.params.id} back="/opskrifter" />

	{#if error}<p class="msg" role="alert">{error}</p>{/if}
	{#if warning}<p class="msg" role="alert">{warning}</p>{/if}

	{#if recipe}
		<div class="pad head">
			<!-- Titlen står i siden og ikke i en fast top, så lange navne kan læses helt. -->
			<h1 class="serif">{recipe.title}</h1>
			{#if recipe.servings || source || wished}
				<p class="ey meta">
					{#if recipe.servings}{recipe.servings} pers.{/if}
					{#if recipe.servings && source}<span aria-hidden="true"> · </span>{/if}
					{#if source}
						<a href={source} target="_blank" rel="noopener noreferrer">{new URL(source).hostname.replace(/^www\./, '')}</a>
					{/if}
					{#if (recipe.servings || source) && wished}<span aria-hidden="true"> · </span>{/if}
					{#if wished}på ønskelisten{/if}
				</p>
			{/if}
			<div class="btns">
				<button type="button" class="btn primary" onclick={() => (placing = true)}><Icon name="cal" />Læg på en dag</button>
				{#if recipe.owned}<a class="btn" href="/opskrift/{recipe.id}/rediger">Rediger</a>{/if}
				{#if recipe.in_collection}
					<button type="button" class="btn quiet" onclick={() => setCollection(false)}>Fjern fra vores samling</button>
				{:else}
					<button type="button" class="btn" onclick={() => setCollection(true)}>Læg i vores samling</button>
				{/if}
			</div>
		</div>

		{#if placed}
			<p class="note placed" role="status">
				<span class="grow">{placed.text}</span>
				<a class="link" href={placed.href}>{placed.link}</a>
			</p>
		{/if}

		{#if editingNote}
			<form class="pad" onsubmit={saveNote}>
				<label class="field"><span>Note om barnet (kun for jer)</span><textarea rows="2" maxlength="2000" bind:value={noteText}></textarea></label>
				<button class="btn sm">Gem</button>
				<button type="button" class="btn quiet sm" onclick={() => (editingNote = false)}>Annuller</button>
			</form>
		{:else}
			{#if recipe.child_note}
				<p class="note"><b>Barnet:</b> {recipe.child_note}</p>
			{/if}
			<p class="pad"><button type="button" class="link" onclick={editNote}>{recipe.child_note ? 'Ret noten om barnet' : 'Skriv en note om barnet'}</button></p>
		{/if}

		<div class="columns">
			<section>
				<h2 class="sl">Ingredienser<span>stjerne = hovedingrediens</span></h2>
				{#if toReview && recipe.owned}
					<p class="pad review">
						<span class="tag">{toReview} at tjekke</span>
						<a class="link" href="/opskrift/{recipe.id}/rediger">Ret varerne</a>
					</p>
				{/if}
				{#each groups as g}
					{#if g.name}<h3 class="pad">{g.name}</h3>{/if}
					<ul>
						{#each g.lines as l}
							<li>
								<IngredientRow
									qty={!showOriginal && l.my_quantity != null ? formatQuantity(l.my_quantity, null, l.unit) : formatQuantity(l.quantity, l.quantity_max, l.unit)}
									name={l.item}
									note={l.note}
									dim={!showOriginal && l.skipped}
								>
									{#snippet trailing()}
										{#if !showOriginal && l.skipped}<span class="tag">springes over</span>{/if}
										{#if !showOriginal && l.my_quantity != null}<span class="tag">jeres mængde</span>{/if}
										<button type="button" class="link tilpas" onclick={() => openAdjust(l)} aria-expanded={adjusting === l.id}>Tilpas</button>
										{#if l.match_status === 'usikker'}
											<span class="tag">{l.ingredient?.name}?</span>
										{:else if l.match_status === 'ingen'}
											<span class="tag">ingen vare</span>
										{/if}
										<button
											type="button"
											class="star"
											class:on={l.is_main}
											aria-pressed={l.is_main}
											aria-label="Hovedingrediens: {l.item}"
											title={l.is_main ? 'Hovedingrediens (fjern stjernen)' : 'Gør til hovedingrediens'}
											onclick={() => toggleMain(l)}><Icon name="star" size={20} /></button
										>
									{/snippet}
								</IngredientRow>
								{#if adjusting === l.id}
									<form class="pad adjust" onsubmit={(e) => { e.preventDefault(); saveAdjust(l); }}>
										<label class="check"><input type="checkbox" bind:checked={adjSkip} /> Spring over (kommer ikke på jeres liste)</label>
										{#if !adjSkip}
											<label class="field"><span>Jeres mængde{l.unit ? ` (${l.unit})` : ''}</span><input inputmode="decimal" bind:value={adjQty} placeholder="som i opskriften" /></label>
										{/if}
										<button class="btn sm">Gem</button>
										<button type="button" class="btn quiet sm" onclick={() => saveAdjust(l, true)}>Nulstil</button>
									</form>
								{/if}
							</li>
						{/each}
					</ul>
				{:else}
					<p class="pad muted">Ingen ingredienser.</p>
				{/each}

				{#if recipe.extra_lines?.length}
					<h3 class="pad">Jeres ekstra</h3>
					<ul>
						{#each recipe.extra_lines as x (x.id)}
							<li>
								<IngredientRow qty={formatQuantity(x.quantity, null, x.unit)} name={x.item}>
									{#snippet trailing()}
										<button type="button" class="link" onclick={() => adjust(String(x.id), 'DELETE')} aria-label="Fjern {x.raw}">Fjern</button>
									{/snippet}
								</IngredientRow>
							</li>
						{/each}
					</ul>
				{/if}
				<form class="pad extra" onsubmit={addExtra}>
					<label class="field"><span>Ekstra linje, kun til jer</span><input bind:value={extraText} placeholder="fx 1 dåse majs" maxlength="300" /></label>
					<button class="btn sm" disabled={!extraText.trim()}>Tilføj</button>
				</form>
				{#if adjusted}
					<p class="pad"><button type="button" class="link" onclick={() => (showOriginal = !showOriginal)}>{showOriginal ? 'Vis jeres udgave' : 'Vis original'}</button></p>
				{/if}
				{#if editingOwn}
					<form class="pad" onsubmit={saveOwnNote}>
						<label class="field"><span>Jeres egen note (fx "vi bruger halv chili")</span><textarea rows="2" maxlength="2000" bind:value={ownNote}></textarea></label>
						<button class="btn sm">Gem</button>
						<button type="button" class="btn quiet sm" onclick={() => (editingOwn = false)}>Annuller</button>
					</form>
				{:else}
					{#if recipe.own_note}<p class="note">{recipe.own_note}</p>{/if}
					<p class="pad"><button type="button" class="link" onclick={() => { ownNote = recipe?.own_note ?? ''; editingOwn = true; }}>{recipe.own_note ? 'Ret jeres note' : 'Skriv jeres egen note'}</button></p>
				{/if}
			</section>

			<section>
				{#if recipe.instructions.length}
					<h2 class="sl">Fremgangsmåde<span>{stepCount} trin</span></h2>
					{#each stepGroups as sg}
						{#if sg.title}<h3 class="pad">{sg.title}</h3>{/if}
						<ol class="steps">
							{#each sg.steps as step}
								<li>{step}</li>
							{/each}
						</ol>
					{/each}
				{/if}
			</section>
		</div>

		{#if recipe.owned}<p class="actions"><button type="button" class="btn quiet" onclick={remove}>Slet opskrift</button></p>{/if}
	{/if}
</main>

{#if placing && recipe}
	<PlaceSheet recipe={{ id: recipe.id, title: recipe.title }} {onplaced} onclose={() => (placing = false)} />
{/if}

<style>
	/* iPad på tværs og computer: plads til to spalter. */
	@media (min-width: 900px) {
		main {
			max-width: 980px;
		}
	}
	.head {
		padding-top: 16px;
	}
	h1 {
		font-size: var(--fs-dish);
		line-height: 28px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	.meta {
		margin-top: 4px;
		font-weight: 500;
	}
	/* Trykfladen på linket rækker ud over linjen. */
	.meta a {
		padding-block: 14px;
	}
	.btns {
		margin-top: 14px;
	}
	.placed {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.placed .link {
		flex: none;
		padding-block: 12px;
		margin-block: -12px;
	}
	.review {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: var(--tap);
		font-size: 14.5px;
	}
	.review .link {
		padding-block: 12px;
	}
	h3 {
		font-size: 15px;
		font-weight: 700;
		margin-top: 14px;
		padding-bottom: 2px;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	/* Stjernen: 44px trykflade. Udfyldt = hovedingrediens. */
	.star {
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--tap);
		height: var(--tap);
		margin-right: -12px;
		border-radius: 50%;
		color: var(--ring);
	}
	.star.on {
		color: var(--tomat);
	}
	.star.on :global(svg) {
		fill: currentColor;
	}
	.steps {
		margin: 6px 0 0;
		padding-left: calc(var(--gutter) + 1.4em);
		padding-right: var(--gutter);
		font-size: 16.5px;
		line-height: 1.5;
	}
	.steps li {
		margin-bottom: 10px;
	}
	.actions {
		margin-top: 32px;
		text-align: center;
	}
</style>
