<script lang="ts">
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { catalog } from '$lib/catalog.svelte';
	import { weekdayName } from '$lib/dates';
	import { itemKey } from '$lib/format';
	import IngredientPicker from '$lib/IngredientPicker.svelte';
	import { clock } from '$lib/resume.svelte';
	import { refreshReviewCount } from '$lib/review.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import ReviewCard, { type ReviewItem } from '$lib/rydop/ReviewCard.svelte';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import type { IngredientRef, Plan, ReviewLine } from '$lib/types';

	let lines = $state<ReviewLine[] | null>(null);
	let error = $state('');
	let picking = $state<ReviewItem | null>(null);
	let busy = $state<string | null>(null);
	/** Ugedagen, den aktuelle uge starter på. null = der er ingen uge. */
	let shoppingDay = $state<string | null>(null);
	let dayInfo = $state(false);

	const items = $derived.by(() => {
		const map = new Map<string, ReviewItem>();
		for (const l of lines ?? []) {
			const k = itemKey(l.item);
			const it = map.get(k) ?? { key: k, item: l.item, suggestion: null, lines: [] };
			it.lines.push(l);
			if (l.match_status === 'usikker' && l.ingredient) it.suggestion = l.ingredient;
			map.set(k, it);
		}
		// Varer i flest opskrifter først: de giver mest at rette.
		return [...map.values()].sort((a, b) => b.lines.length - a.lines.length || a.item.localeCompare(b.item, 'da'));
	});

	const pantryCount = $derived(catalog.ingredients.filter((i) => i.pantry).length);

	const WORDS = ['Én', 'To', 'Tre', 'Fire', 'Fem', 'Seks', 'Syv', 'Otte', 'Ni', 'Ti', 'Elleve', 'Tolv'];
	const intro = $derived.by(() => {
		const n = items.length;
		if (!lines) return '';
		if (n === 0) return 'Alt er på plads.';
		return `${WORDS[n - 1] ?? n} ${n === 1 ? 'vare' : 'varer'}, appen er i tvivl om. Jeres valg huskes i alle opskrifter.`;
	});

	async function load() {
		try {
			lines = await refreshReviewCount();
		} catch (e) {
			error = say(e);
		}
	}

	$effect(() => {
		untrack(() => {
			load();
			// Kun til tallene på rækkerne: uden dem står rækkerne der stadig.
			catalog.load().catch(() => {});
			api<Plan>(`/plans/current?today=${clock.today}`)
				.then((p) => (shoppingDay = weekdayName(p.start_date).toLowerCase()))
				.catch(() => (shoppingDay = null));
		});
	});

	async function resolve(it: ReviewItem, ing: IngredientRef | null) {
		busy = it.key;
		picking = null;
		error = '';
		try {
			if (ing) {
				// Serveren retter selv de andre linjer med samme varenavn.
				await api(`/lines/${it.lines[0].id}/confirm`, { method: 'POST', body: { ingredient_id: ing.id } });
			} else {
				for (const l of it.lines) await api(`/lines/${l.id}/ignore`, { method: 'POST' });
			}
			await load();
		} catch (e) {
			error = say(e);
		} finally {
			busy = null;
		}
	}

	async function logout() {
		await api('/logout', { method: 'POST' }).catch(() => {});
		shopping.clear();
		await goto('/login');
	}
</script>

<main>
	<ScreenHeader title="Ryd op" eyebrow="Opskrifter" back="/opskrifter" />
	{#if intro}<p class="pad muted intro">{intro}</p>{/if}

	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	{#if items.length}
		<ul class="cards">
			{#each items as it (it.key)}
				<ReviewCard
					item={it}
					busy={busy === it.key}
					locked={busy !== null}
					onaccept={() => resolve(it, it.suggestion)}
					onchoose={() => (picking = it)}
					onignore={() => resolve(it, null)}
				/>
			{/each}
		</ul>
	{/if}

	<h2 class="sl">Indstillinger</h2>
	<a class="kv" href="/rydop/basisvarer">
		<span class="k">Basisvarer<small>Altid hjemme, kommer ikke på listen</small></span>
		{#if catalog.ingredients.length}<span class="tag">{pantryCount}</span>{/if}
	</a>
	<a class="kv" href="/rydop/butik"><span class="k">Rækkefølge i butikken</span></a>
	<button type="button" class="kv" onclick={() => (dayInfo = true)}>
		<span class="k">Indkøbsdag</span>
		<span class="tag">{shoppingDay ?? '–'}</span>
	</button>
	<a class="kv" href="/rydop/familie"><span class="k">Familie<small>Medlemmer, invitation og kodeord</small></span></a>
	<a class="kv" href="/rydop/varer">
		<span class="k">Alle varer</span>
		{#if catalog.ingredients.length}<span class="tag">{catalog.ingredients.length}</span>{/if}
	</a>
	<button type="button" class="kv" onclick={logout}><span class="k">Log ud</span></button>
</main>

{#if picking}
	{@const it = picking}
	<Sheet title={it.suggestion ? 'Anden vare' : 'Vælg vare'} eyebrow={`"${it.item}" i ${it.lines.length === 1 ? '1 opskrift' : `${it.lines.length} opskrifter`}`} onclose={() => (picking = null)}>
		{#snippet children(close)}
			<IngredientPicker initial={it.item} suggestion={it.suggestion} onpick={(ing) => resolve(it, ing)} oncancel={close} />
		{/snippet}
	</Sheet>
{/if}

{#if dayInfo}
	<Sheet title="Indkøbsdag" eyebrow={shoppingDay ? `Denne uge: ${shoppingDay}` : undefined} onclose={() => (dayInfo = false)}>
		<p class="pad info">Ugen starter på indkøbsdagen. I vælger dagen, når I laver en ny uge.</p>
	</Sheet>
{/if}

<style>
	.intro {
		font-size: 15px;
		padding-bottom: 14px;
	}
	.cards {
		margin: 0;
		padding: 0;
	}
	.info {
		padding-block: 4px 16px;
	}
</style>
