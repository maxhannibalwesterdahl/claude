<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { periodLabel, weekday } from '$lib/dates';
	import { formatAmounts } from '$lib/format';
	import { shopping } from '$lib/shopping.svelte';
	import type { Department, ShoppingData, ShoppingItem } from '$lib/types';

	let hideBought = $state(false);
	let open = $state<string | null>(null);
	let newItem = $state('');
	let actionError = $state('');
	let editingOrder = $state(false);
	let order = $state<Department[]>([]);

	$effect(() => {
		shopping.start();
		return () => shopping.stop();
	});

	const data = $derived(shopping.data);
	const isChecked = (i: ShoppingItem) => shopping.checked(i.key, i.checked);
	const total = $derived(data?.items.length ?? 0);
	const done = $derived(data?.items.filter(isChecked).length ?? 0);

	const sections = $derived(
		(data?.departments ?? [])
			.map((d) => ({
				...d,
				items: (data?.items ?? []).filter((i) => i.department === d.code && !(hideBought && isChecked(i)))
			}))
			.filter((s) => s.items.length)
	);

	const statusText = $derived.by(() => {
		const waiting = shopping.pending.length;
		if (shopping.status === 'offline')
			return waiting ? `Offline – ${waiting} ${waiting === 1 ? 'ændring venter' : 'ændringer venter'}` : 'Offline – viser gemt liste';
		if (shopping.status === 'error') return shopping.error || 'Kunne ikke synkronisere';
		if (shopping.status === 'loading') return data ? 'Opdaterer…' : 'Henter listen…';
		const t = shopping.syncedAt;
		return t ? `Synkroniseret ${t.toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })}` : '';
	});

	async function action(fn: () => Promise<ShoppingData>) {
		actionError = '';
		try {
			shopping.set(await fn());
		} catch (e) {
			actionError =
				e instanceof ApiError && e.status === 0 ? 'Kræver forbindelse. Prøv igen, når du har net.' : e instanceof ApiError ? e.message : 'Noget gik galt';
		}
	}

	const planQuery = () => (data?.plan ? `?plan_id=${data.plan.id}` : '');

	function addItem(e: SubmitEvent) {
		e.preventDefault();
		const text = newItem.trim();
		if (!text) return;
		newItem = '';
		action(() => api<ShoppingData>(`/shopping/extras${planQuery()}`, { method: 'POST', body: { text } }));
	}

	function setHome(key: string, home: boolean) {
		if (!data?.plan) return;
		const planId = data.plan.id;
		open = null;
		action(() => api<ShoppingData>('/shopping/home', { method: 'POST', body: { plan_id: planId, key, home } }));
	}

	function removeExtra(key: string) {
		open = null;
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

	function startOrder() {
		order = [...(data?.departments ?? [])];
	}

	function moveDept(i: number, delta: number) {
		const j = i + delta;
		if (j < 0 || j >= order.length) return;
		[order[i], order[j]] = [order[j], order[i]];
	}

	async function saveOrder() {
		try {
			await api('/settings/departments', { method: 'PUT', body: { order: order.map((d) => d.code) } });
			editingOrder = false;
			await shopping.sync();
		} catch (e) {
			actionError = e instanceof ApiError ? e.message : 'Kunne ikke gemme rækkefølgen';
		}
	}

	const days = (list: string[]) => list.map(weekday).join(', ');
</script>

<main>
	<header class="top">
		<div class="grow">
			<h1>Indkøb</h1>
			<div class="muted small">
				{#if data?.plan}{periodLabel(data.plan.start_date, data.plan.end_date)} · {/if}
				<span class:warn={shopping.status === 'offline' || shopping.status === 'error'}>{statusText}</span>
			</div>
		</div>
		{#if total}<div class="progress" aria-label="{done} af {total} købt"><b>{done}</b>/{total}</div>{/if}
	</header>

	{#if actionError}<p class="error" role="alert">{actionError}</p>{/if}

	<form class="add" onsubmit={addItem}>
		<input bind:value={newItem} placeholder="Tilføj vare, fx bleer eller kaffe" aria-label="Tilføj vare" maxlength="200" />
		<button disabled={!newItem.trim()}>Tilføj</button>
	</form>

	{#if data && !data.plan && !total}
		<div class="empty">
			<p>Ingen madplan endnu.</p>
			<p><a class="button primary" href="/">Lav en madplan</a></p>
		</div>
	{:else if data && !total}
		<div class="empty"><p>Listen er tom. Vælg retter i madplanen, så kommer ingredienserne her.</p></div>
	{/if}

	{#if total}
		<label class="hide"><input type="checkbox" bind:checked={hideBought} /> Skjul købte</label>
	{/if}

	{#each sections as s (s.code)}
		<h2>{s.name}</h2>
		<ul class="list">
			{#each s.items as item (item.key)}
				{@const checked = isChecked(item)}
				<li class:checked>
					<div class="row-main">
						<button class="tick" aria-pressed={checked} onclick={() => shopping.toggle(item.key, checked)}>
							<span class="box" aria-hidden="true">{checked ? '✓' : ''}</span>
							<span class="grow text">
								<span class="name">{item.name}</span>
								{#if item.days.length}<span class="days">{days(item.days)}</span>{/if}
								{#if item.source === 'løbet tør'}<span class="days">løbet tør</span>{/if}
							</span>
							<span class="amount">{formatAmounts(item.amounts, item.unquantified)}</span>
						</button>
						<button
							class="plain more"
							aria-expanded={open === item.key}
							aria-label="Mere om {item.name}"
							onclick={() => (open = open === item.key ? null : item.key)}>⋯</button
						>
					</div>
					{#if open === item.key}
						<div class="details">
							{#if item.unknown}
								<p class="small"><span class="badge">ukendt vare</span> <a href="/tjek">Vælg vare under Tjek</a></p>
							{/if}
							{#each item.sources as src}
								<div class="small muted">{weekday(src.date)} · {src.meal}: {src.raw}</div>
							{/each}
							<div class="row">
								{#if item.kind === 'plan'}
									<button onclick={() => setHome(item.key, true)}>Har hjemme</button>
								{:else}
									<button class="danger" onclick={() => removeExtra(item.key)}>Fjern fra listen</button>
								{/if}
							</div>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/each}

	{#if data?.home.length}
		<details class="section">
			<summary>Har hjemme ({data.home.length})</summary>
			<ul class="simple">
				{#each data.home as h (h.key)}
					<li>
						<span class="grow">{h.name}</span>
						<button onclick={() => setHome(h.key, false)}>Fortryd</button>
					</li>
				{/each}
			</ul>
		</details>
	{/if}

	{#if data?.pantry.length}
		<details class="section">
			<summary>Basisvarer brugt i denne uge ({data.pantry.length})</summary>
			<p class="muted small">Kommer ikke på listen. Tryk "Løbet tør", hvis I mangler en.</p>
			<ul class="simple">
				{#each data.pantry as p (p.ingredient_id)}
					<li>
						<span class="grow">
							{p.name}
							<span class="muted small">{formatAmounts(p.amounts)}</span>
						</span>
						{#if p.requested}
							<span class="badge ok">på listen</span>
						{:else}
							<button onclick={() => outOfStock(p.ingredient_id)}>Løbet tør</button>
						{/if}
					</li>
				{/each}
			</ul>
		</details>
	{/if}

	{#if data}
		<details class="section" bind:open={editingOrder} ontoggle={() => editingOrder && startOrder()}>
			<summary>Rækkefølge i butikken</summary>
			<p class="muted small">Sæt afdelingerne i den rækkefølge, I går rundt i Bilka.</p>
			<ol class="order">
				{#each order as d, i (d.code)}
					<li>
						<span class="grow">{d.name}</span>
						<button class="plain" aria-label="Flyt {d.name} op" disabled={i === 0} onclick={() => moveDept(i, -1)}>↑</button>
						<button class="plain" aria-label="Flyt {d.name} ned" disabled={i === order.length - 1} onclick={() => moveDept(i, 1)}>↓</button>
					</li>
				{/each}
			</ol>
			<button class="primary" onclick={saveOrder}>Gem rækkefølge</button>
		</details>
	{/if}
</main>

<style>
	.progress {
		font-size: 1.1rem;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.progress b {
		color: var(--accent);
	}
	.warn {
		color: var(--warn);
		font-weight: 600;
	}
	.add {
		display: flex;
		gap: 8px;
		margin-bottom: 8px;
	}
	.add input {
		flex: 1;
	}
	.add button {
		flex: none;
	}
	.hide {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--muted);
		font-size: 0.9rem;
		margin: 8px 0;
	}
	.hide input,
	.order button {
		width: auto;
		min-height: 0;
	}
	.list {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.list li {
		border-bottom: 1px solid var(--line);
	}
	.row-main {
		display: flex;
		align-items: stretch;
	}
	/* Store felter til én hånd i butikken */
	.tick {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 14px;
		min-height: 60px;
		padding: 8px 4px;
		border: none;
		border-radius: 0;
		background: none;
		text-align: left;
	}
	.box {
		flex: none;
		width: 30px;
		height: 30px;
		border-radius: 8px;
		border: 2px solid var(--line);
		display: grid;
		place-items: center;
		font-weight: 800;
		color: var(--accent-fg);
	}
	li.checked .box {
		background: var(--accent);
		border-color: var(--accent);
	}
	.text {
		display: flex;
		flex-direction: column;
	}
	.name {
		font-size: 1.05rem;
		font-weight: 600;
	}
	.days {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.amount {
		flex: none;
		max-width: 45%;
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--fg);
	}
	li.checked .name,
	li.checked .amount {
		text-decoration: line-through;
		color: var(--muted);
	}
	.more {
		flex: none;
		width: 44px;
		justify-content: center;
		font-size: 1.3rem;
		color: var(--muted);
	}
	.details {
		display: grid;
		gap: 6px;
		padding: 0 4px 12px 48px;
	}
	.section {
		margin-top: 24px;
		border-top: 1px solid var(--line);
		padding-top: 12px;
	}
	.section summary {
		cursor: pointer;
		font-weight: 600;
		min-height: 36px;
	}
	.simple,
	.order {
		list-style: none;
		padding: 0;
		margin: 8px 0;
	}
	.simple li,
	.order li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 48px;
		border-bottom: 1px solid var(--line);
	}
	.order button {
		padding: 6px 12px;
		font-size: 1.1rem;
	}
</style>
