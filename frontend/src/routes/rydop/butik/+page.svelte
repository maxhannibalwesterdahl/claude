<script lang="ts">
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { navState } from '$lib/nav.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import type { Department } from '$lib/types';

	let order = $state<Department[] | null>(null);
	let error = $state('');
	let busy = $state(false);
	/** Læses op, når en afdeling er flyttet. */
	let moved = $state('');

	$effect(() => {
		untrack(() => {
			api<Department[]>('/settings/departments')
				.then((d) => (order = d))
				.catch((e) => (error = say(e)));
		});
	});

	function moveDept(i: number, delta: number) {
		const j = i + delta;
		if (!order || j < 0 || j >= order.length) return;
		[order[i], order[j]] = [order[j], order[i]];
		moved = `${order[j].name} er nu nummer ${j + 1} af ${order.length}.`;
	}

	async function saveOrder() {
		if (!order) return;
		busy = true;
		error = '';
		try {
			await api('/settings/departments', { method: 'PUT', body: { order: order.map((d) => d.code) } });
			// Indkøbslisten følger den nye rækkefølge, næste gang den hentes.
			shopping.sync();
			// Tilbage til Ryd op, uden at lægge en ekstra side i historikken: ellers
			// skulle der trykkes Tilbage to gange for at komme videre derfra.
			if (navState.inApp) history.back();
			else await goto('/rydop', { replaceState: true });
		} catch (e) {
			error = say(e);
		} finally {
			busy = false;
		}
	}
</script>

<main>
	<ScreenHeader title="Rækkefølge i butikken" eyebrow="Ryd op" back="/rydop" />
	<p class="pad muted intro">Sæt afdelingerne i den rækkefølge, I går rundt i butikken.</p>

	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	{#if order}
		<ol>
			{#each order as d, i (d.code)}
				<li>
					<span class="grow name">{d.name}</span>
					<button type="button" class="rnd" aria-label="Flyt {d.name} op" disabled={i === 0} onclick={() => moveDept(i, -1)}><Icon name="up" /></button>
					<button type="button" class="rnd" aria-label="Flyt {d.name} ned" disabled={i === order.length - 1} onclick={() => moveDept(i, 1)}><Icon name="down" /></button>
				</li>
			{/each}
		</ol>
		<p class="sr" aria-live="polite">{moved}</p>
		<div class="pad save">
			<button type="button" class="btn primary block" disabled={busy} onclick={saveOrder}>{busy ? 'Gemmer…' : 'Gem rækkefølge'}</button>
		</div>
	{/if}
</main>

<style>
	.intro {
		font-size: 15px;
	}
	ol {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
	}
	li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: var(--row-h);
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	.name {
		font-size: var(--fs-row);
		font-weight: 500;
	}
	.save {
		margin-top: 20px;
	}
</style>
