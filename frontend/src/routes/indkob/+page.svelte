<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { api } from '$lib/api';
	import { periodLong, today } from '$lib/dates';
	import Fold from '$lib/Fold.svelte';
	import { formatAmounts, itemKey } from '$lib/format';
	import AddBar from '$lib/indkob/AddBar.svelte';
	import ItemRow from '$lib/indkob/ItemRow.svelte';
	import ItemSheet from '$lib/indkob/ItemSheet.svelte';
	import PickSheet from '$lib/indkob/PickSheet.svelte';
	import { navState } from '$lib/nav.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import type { IngredientRef, PlanBrief, ReviewLine, ShoppingData, ShoppingItem } from '$lib/types';
	import { OFFLINE, say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import SwipeRow from '$lib/ui/SwipeRow.svelte';
	import WeekNav from '$lib/ui/WeekNav.svelte';

	// Så længe bliver en række, der lige er købt, stående på sin plads med streg
	// over. Listen hopper ikke under tommelfingeren, og et fejltryk kan fortrydes.
	const LINGER_MS = 4000;
	// Så mange basisvarer vises, før resten foldes ind.
	const PANTRY_SHOWN = 6;

	/** Rækken, hvis ark er åbent. */
	let sheetKey = $state<string | null>(null);
	let newItem = $state('');
	let adding = $state(false);
	let actionError = $state('');
	let allPantry = $state(false);

	// Rækker, der lige er købt her på telefonen, og som stadig står i deres afdeling.
	let recent = $state<Record<string, true>>({});
	const timers = new Map<string, ReturnType<typeof setTimeout>>();
	function forget() {
		for (const t of timers.values()) clearTimeout(t);
		timers.clear();
	}

	$effect(() => {
		shopping.start();
		return () => {
			shopping.stop();
			forget();
		};
	});

	const data = $derived(shopping.data);

	// Uge-vælger: listen viser den uge, Uge sidst viste, men andre uger kan
	// vælges (fx næste uges indkøb). Planerne hentes igen, når listen viser en ukendt plan.
	let plans = $state<PlanBrief[]>([]);
	$effect(() => {
		const id = data?.plan?.id;
		if (id !== undefined && !plans.some((p) => p.id === id)) loadPlans();
	});
	async function loadPlans() {
		try {
			plans = await api<PlanBrief[]>('/plans');
		} catch {
			/* offline: vælgeren vises ikke */
		}
	}
	function showPlan(id: number | null) {
		sheetKey = null;
		shopping.show(id);
		// Uge viser samme uge, når man går tilbage dertil.
		navState.week = id === null ? '/' : `/?plan=${id}`;
	}
	// Uden net kan en anden uge ikke hentes, så pilene vises ikke.
	const canNavigate = $derived(
		!!data?.plan && plans.length > 1 && plans.some((p) => p.id === data.plan?.id) && shopping.status !== 'offline'
	);

	const isChecked = (i: ShoppingItem) => shopping.checked(i.key, i.checked);
	const total = $derived(data?.items.length ?? 0);
	const done = $derived(data?.items.filter(isChecked).length ?? 0);

	function toggle(item: ShoppingItem) {
		const was = isChecked(item);
		shopping.toggle(item.key, was);
		clearTimeout(timers.get(item.key));
		timers.delete(item.key);
		if (was) delete recent[item.key];
		else {
			recent[item.key] = true;
			timers.set(
				item.key,
				setTimeout(() => settle(item.key), LINGER_MS)
			);
		}
	}

	/** Tiden er gået: rækken flytter ned under "Købt". */
	function settle(key: string) {
		// Står tastaturets fokus på rækken, venter den, så fokus ikke forsvinder med den.
		const el = document.activeElement;
		if (el instanceof HTMLElement && el.matches(':focus-visible') && el.closest<HTMLElement>('[data-key]')?.dataset.key === key) {
			timers.set(
				key,
				setTimeout(() => settle(key), 1000)
			);
			return;
		}
		timers.delete(key);
		delete recent[key];
	}

	// En anden uge har de samme nøgler: ingen rækker hænger ved fra den forrige.
	let shownPlan: number | null | undefined;
	$effect(() => {
		const id = data?.plan?.id ?? null;
		if (id === shownPlan) return;
		shownPlan = id;
		untrack(() => {
			forget();
			recent = {};
		});
	});

	// Afdelingerne viser det, der mangler (og det, der lige er købt). Resten står under "Købt".
	const sections = $derived(
		(data?.departments ?? [])
			.map((d) => {
				const all = (data?.items ?? []).filter((i) => i.department === d.code);
				return {
					...d,
					rows: all.filter((i) => !isChecked(i) || recent[i.key]),
					left: all.filter((i) => !isChecked(i)).length
				};
			})
			.filter((s) => s.rows.length)
	);
	const bought = $derived((data?.items ?? []).filter((i) => isChecked(i) && !recent[i.key]));
	const pantry = $derived(allPantry ? (data?.pantry ?? []) : (data?.pantry ?? []).slice(0, PANTRY_SHOWN));

	const sheetItem = $derived(data?.items.find((i) => i.key === sheetKey) ?? null);

	async function action(fn: () => Promise<ShoppingData>) {
		actionError = '';
		try {
			shopping.set(await fn());
		} catch (e) {
			actionError = say(e);
		}
	}

	const planQuery = () => `?today=${today()}` + (data?.plan ? `&plan_id=${data.plan.id}` : '');

	// Egne varer kobles til en rigtig vare, så de sorteres efter afdeling. Er
	// appen ikke sikker, vælger man varen (eller opretter den) i vare-vælgeren.
	// En ukendt vare fra planen rettes på opskriftens linjer (som under Ryd op).
	type Picking =
		| { mode: 'new'; text: string; initial: string; suggestion: IngredientRef | null }
		| { mode: 'change'; key: string; text: string }
		| { mode: 'plan'; item: ShoppingItem; lines: ReviewLine[] | null };
	let picking = $state.raw<Picking | null>(null);

	async function addItem(text: string) {
		if (adding) return;
		actionError = '';
		adding = true;
		let parsed: { item: string; ingredient: IngredientRef | null; match_status: string };
		try {
			[parsed] = await api<(typeof parsed)[]>('/parse', { method: 'POST', body: { lines: [text] } });
		} catch (e) {
			actionError = say(e);
			return;
		} finally {
			adding = false;
		}
		newItem = '';
		if (parsed.ingredient && parsed.match_status === 'sikker') {
			saveExtra(text, parsed.ingredient.id);
		} else {
			picking = { mode: 'new', text, initial: parsed.item || text, suggestion: parsed.ingredient };
		}
	}

	function saveExtra(text: string, ingredientId: number | null) {
		action(() =>
			api<ShoppingData>(`/shopping/extras${planQuery()}`, { method: 'POST', body: { text, ingredient_id: ingredientId } })
		);
	}

	/** Vælg vare for en række: egne varer rettes direkte, planens på opskriftens linjer. */
	async function pickFor(item: ShoppingItem) {
		sheetKey = null;
		// Arket lukkes først, så fokus er tilbage på rækken, før vælgeren åbner.
		await tick();
		if (item.kind === 'extra') {
			picking = { mode: 'change', key: item.key, text: item.name };
			return;
		}
		const mine: Picking = { mode: 'plan', item, lines: null };
		picking = mine;
		try {
			const all = await api<ReviewLine[]>('/review');
			// Serverens nøgle fjerner også accenter, så navnet alene kan gå galt:
			// linjens tekst fra opskriften er den anden vej til den samme linje.
			const key = itemKey(item.name);
			const lines = all.filter((l) => itemKey(l.item) === key || item.sources.some((s) => s.raw === l.raw));
			if (picking === mine) picking = { ...mine, lines };
		} catch (e) {
			if (picking !== mine) return;
			picking = null;
			actionError = say(e);
		}
	}

	function picked(ing: IngredientRef | null) {
		const p = picking;
		picking = null;
		if (!p) return;
		if (p.mode === 'new') saveExtra(p.text, ing?.id ?? null);
		else if (p.mode === 'change')
			action(() =>
				api<ShoppingData>(`/shopping/extras/${p.key.slice(2)}${planQuery()}`, {
					method: 'PATCH',
					body: { ingredient_id: ing?.id ?? null }
				})
			);
		else resolveLines(p.lines ?? [], ing);
	}

	async function resolveLines(lines: ReviewLine[], ing: IngredientRef | null) {
		actionError = '';
		try {
			if (ing) {
				// Serveren retter selv de andre linjer med samme varenavn.
				const seen = new Set<string>();
				for (const l of lines) {
					const k = itemKey(l.item);
					if (seen.has(k)) continue;
					seen.add(k);
					await api(`/lines/${l.id}/confirm`, { method: 'POST', body: { ingredient_id: ing.id } });
				}
			} else {
				for (const l of lines) await api(`/lines/${l.id}/ignore`, { method: 'POST' });
			}
		} catch (e) {
			actionError = say(e);
		}
		await shopping.sync();
	}

	/** Vælgeren lukket uden et valg. En ny vare er ikke gemt: teksten kommer tilbage i feltet. */
	function closePicker() {
		const p = picking;
		picking = null;
		if (p?.mode === 'new' && !newItem) newItem = p.text;
	}

	const pickText = $derived(!picking ? '' : picking.mode === 'plan' ? picking.item.name : picking.text);
	const pickInstead = $derived(
		picking?.mode !== 'plan'
			? ''
			: picking.lines === null
				? 'Henter.'
				: picking.lines.length
					? ''
					: 'Varen er valgt fra i opskriften. I kan rette den under Opskrifter.'
	);
	// Appens bud: en vare, den var i tvivl om på en af linjerne.
	const pickSuggestion = $derived(
		!picking
			? null
			: picking.mode === 'new'
				? picking.suggestion
				: picking.mode === 'plan'
					? (picking.lines?.find((l) => l.match_status === 'usikker' && l.ingredient)?.ingredient ?? null)
					: null
	);

	const deptName = (code: string) => data?.departments.find((d) => d.code === code)?.name ?? code;

	function setHome(key: string, home: boolean) {
		if (!data?.plan) return;
		const planId = data.plan.id;
		sheetKey = null;
		action(() => api<ShoppingData>('/shopping/home', { method: 'POST', body: { plan_id: planId, key, home } }));
	}

	function removeExtra(key: string) {
		sheetKey = null;
		action(() => api<ShoppingData>(`/shopping/extras/${key.slice(2)}${planQuery()}`, { method: 'DELETE' }));
	}

	function outOfStock(ingredientId: number) {
		action(() =>
			api<ShoppingData>(`/shopping/extras${planQuery()}`, {
				method: 'POST',
				body: { ingredient_id: ingredientId, source: 'løbet tør' }
			})
		);
	}
</script>

<main class="docked">
	<!-- Toppen bliver stående, så man altid kan se, hvor langt man er. -->
	<div class="top">
		<ScreenHeader title="Indkøb" eyebrow={data?.plan ? periodLong(data.plan.start_date, data.plan.end_date) : undefined}>
			{#snippet actions()}
				{#if total}<p class="count"><b>{done}</b> af {total}</p>{/if}
				{#if canNavigate && data?.plan}<WeekNav plan={data.plan} {plans} onselect={showPlan} />{/if}
			{/snippet}
		</ScreenHeader>
		{#if total}
			<div class="bar" role="progressbar" aria-label="Købt" aria-valuemin="0" aria-valuemax={total} aria-valuenow={done}>
				<span style:width="{(done / total) * 100}%"></span>
			</div>
		{/if}
	</div>

	<!-- Kun når listen ikke er helt opdateret: en rolig sætning om hvorfor. -->
	<div role="status">
		{#if shopping.status === 'offline'}
			{@const waiting = shopping.pending.length}
			<p class="net">
				<Icon name="nonet" size={16} />
				<span><b>{OFFLINE}</b> Listen er gemt her{#if waiting}, {waiting} kryds venter{/if}.</span>
			</p>
		{:else if shopping.status === 'error'}
			<p class="net">{shopping.error || 'Listen kunne ikke hentes lige nu.'}</p>
		{:else if shopping.status === 'loading' && !data}
			<p class="net">Henter listen.</p>
		{/if}
	</div>

	{#if shopping.selected !== null}
		<p class="pad back"><button type="button" class="chip" onclick={() => showPlan(null)}>Denne uge</button></p>
	{/if}

	{#if data && !data.plan && !total}
		<div class="empty">
			<p>Der er ingen madplan endnu.</p>
			<p><a class="btn primary" href="/">Lav en uge</a></p>
		</div>
	{:else if data && !total}
		<p class="empty">Listen er tom. Vælg retter i ugen, så kommer varerne her.</p>
	{:else if total && !sections.length}
		<p class="empty">Alt på listen er købt.</p>
	{/if}

	{#each sections as s (s.code)}
		<h2 class="dep">{s.name}<span>{s.left} tilbage</span></h2>
		<ul>
			{#each s.rows as item (item.key)}
				<li data-key={item.key}>
					<!-- Træk mod højre er en genvej til "Har hjemme". Det samme står i rækkens ark. -->
					<SwipeRow label="Har hjemme" icon="home" disabled={item.kind !== 'plan'} onaction={() => setHome(item.key, true)}>
						<ItemRow
							{item}
							checked={isChecked(item)}
							ontoggle={() => toggle(item)}
							onmore={() => (sheetKey = item.key)}
							onpick={() => pickFor(item)}
						/>
					</SwipeRow>
				</li>
			{/each}
		</ul>
	{/each}

	{#if bought.length}
		<Fold title="Købt" count={bought.length}>
			<ul>
				{#each bought as item (item.key)}
					<li data-key={item.key}>
						<ItemRow
							{item}
							checked
							ontoggle={() => toggle(item)}
							onmore={() => (sheetKey = item.key)}
							onpick={() => pickFor(item)}
						/>
					</li>
				{/each}
			</ul>
		</Fold>
	{/if}

	{#if data?.home.length}
		<Fold title="Har hjemme" count={data.home.length}>
			{#each data.home as h (h.key)}
				<div class="kv">
					<span class="k">{h.name}</span>
					<button type="button" class="v" aria-label="Fortryd, {h.name} skal købes" onclick={() => setHome(h.key, false)}>Fortryd</button>
				</div>
			{/each}
		</Fold>
	{/if}

	{#if data?.pantry.length}
		<h2 class="sl">Basisvarer brugt i ugen<span>altid hjemme</span></h2>
		{#each pantry as p (p.ingredient_id)}
			<div class="kv">
				<span class="k">{p.name} <span class="small muted">{formatAmounts(p.amounts)}</span></span>
				{#if p.requested}
					<span class="tag">på listen</span>
				{:else}
					<button type="button" class="btn sm" aria-label="Løbet tør for {p.name}" onclick={() => outOfStock(p.ingredient_id)}>Løbet tør</button>
				{/if}
			</div>
		{/each}
		{#if !allPantry && data.pantry.length > PANTRY_SHOWN}
			<p class="pad"><button type="button" class="btn quiet sm" onclick={() => (allPantry = true)}>{data.pantry.length - PANTRY_SHOWN} mere</button></p>
		{/if}
	{/if}

	<AddBar bind:value={newItem} busy={adding} onadd={addItem}>
		{#snippet above()}
			<!-- Det, der kræver serveren, siger til her, lige over feltet. -->
			{#if actionError}
				<p class="msg said" role="alert" aria-live="assertive">
					<span class="grow">{actionError}</span>
					<button type="button" class="rnd" aria-label="Luk beskeden" onclick={() => (actionError = '')}><Icon name="x" size={16} /></button>
				</p>
			{/if}
		{/snippet}
	</AddBar>
</main>

{#if sheetItem}
	{@const item = sheetItem}
	<ItemSheet
		{item}
		department={deptName(item.department)}
		onhome={() => setHome(item.key, true)}
		onpick={() => pickFor(item)}
		onremove={() => removeExtra(item.key)}
		onclose={() => (sheetKey = null)}
	/>
{/if}

{#if picking}
	{#key picking.mode === 'plan' ? picking.item.key : picking.text}
		<PickSheet
			text={pickText}
			initial={picking.mode === 'new' ? picking.initial : pickText}
			suggestion={pickSuggestion}
			instead={pickInstead}
			onpick={picked}
			onclose={closePicker}
		/>
	{/key}
{/if}

<style>
	/* Toppen klæber til skærmens kant, så den sikre afstand ligger i den og ikke i main. */
	main {
		padding-top: 0;
	}
	.top {
		position: sticky;
		top: 0;
		z-index: 5;
		padding-block: env(safe-area-inset-top) 6px;
		background: var(--paper);
	}
	.count {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.count b {
		font-size: 20px;
		font-weight: 700;
		color: var(--ink);
	}
	.bar {
		height: 3px;
		margin-inline: max(var(--gutter), env(safe-area-inset-left)) max(var(--gutter), env(safe-area-inset-right));
		border-radius: 2px;
		background: var(--line);
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--kobt);
		transition: width 0.3s;
	}
	.net {
		padding-top: 8px;
	}
	.back {
		padding-block: 8px 4px;
	}
	.empty .btn {
		margin-top: 16px;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.said {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 0 0 8px;
		background: var(--card);
		box-shadow: var(--shadow-float);
	}
</style>
