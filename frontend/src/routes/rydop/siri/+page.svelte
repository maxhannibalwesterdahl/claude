<script lang="ts">
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { confirmDialog } from '$lib/confirm.svelte';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';

	interface Key {
		id: number;
		name: string;
		created_at: string;
		last_used_at: string | null;
	}

	let keys = $state<Key[] | null>(null);
	let error = $state('');
	let notice = $state('');
	let name = $state('Siri');
	/** Den nye nøgle i klartekst. Vises kun lige efter oprettelsen. */
	let token = $state('');

	const url = $derived(typeof location === 'undefined' ? '' : `${location.origin}/api/siri/add`);

	async function load() {
		keys = await api<Key[]>('/me/keys');
	}

	$effect(() => {
		untrack(() => {
			load().catch((e) => (error = say(e)));
		});
	});

	async function run(fn: () => Promise<unknown>) {
		error = '';
		notice = '';
		try {
			await fn();
		} catch (e) {
			error = say(e);
		}
	}

	const create = () =>
		run(async () => {
			token = (await api<{ token: string }>('/me/keys', { method: 'POST', body: { name } })).token;
			await load();
		});

	async function remove(k: Key) {
		if (!(await confirmDialog(`Slet nøglen "${k.name}"? Genvejen med den holder op med at virke.`, 'Slet'))) return;
		await run(async () => {
			await api(`/me/keys/${k.id}`, { method: 'DELETE' });
			await load();
		});
	}

	async function copy(text: string, what: string) {
		try {
			await navigator.clipboard.writeText(text);
			notice = `${what} er kopieret.`;
		} catch {
			/* afvist */
		}
	}

	const day = (iso: string) => new Date(iso).toLocaleDateString('da-DK');
</script>

<main>
	<ScreenHeader title="Siri" eyebrow="Ryd op" back="/rydop" />
	<p class="pad">
		Sig <q>Hej Siri, tilføj til indkøb</q> og så varerne, fx <q>mælk, æg og kaffe</q>. De kommer på listen for næste uge.
		Er næste uge ikke lavet endnu, laver appen den.
	</p>

	{#if error}<p class="msg pad" role="alert">{error}</p>{/if}
	{#if notice}<p class="pad muted" role="status">{notice}</p>{/if}

	<h2 class="sl">1. Lav en nøgle</h2>
	<p class="pad muted lead">Nøglen lader genvejen tilføje varer for dig. Den kan ikke læse jeres data. Lav en til hver telefon.</p>
	<form class="pad row" onsubmit={(e) => { e.preventDefault(); create(); }}>
		<label class="field grow"><span>Navn, fx telefonens</span><input bind:value={name} maxlength="50" required /></label>
		<button class="btn sm" disabled={!name.trim()}>Lav nøgle</button>
	</form>
	{#if token}
		<div class="pad stack">
			<input readonly value={token} onfocus={(e) => e.currentTarget.select()} aria-label="Ny nøgle" />
			<p><button type="button" class="btn sm" onclick={() => copy(token, 'Nøglen')}>Kopiér nøglen</button> <span class="muted">Vises kun nu.</span></p>
		</div>
	{/if}

	<h2 class="sl">2. Lav genvejen</h2>
	<ol class="pad steps">
		<li>Åbn appen <b>Genveje</b> på telefonen og tryk <b>+</b>.</li>
		<li>Tilføj <b>Spørg efter input</b> (Ask for Input). Skriv spørgsmålet <q>Hvad skal på?</q></li>
		<li>
			Tilføj <b>Hent indhold af URL</b> (Get Contents of URL) med adressen
			<button type="button" class="link" onclick={() => copy(url, 'Adressen')}>{url}</button>. Tryk på pilen og vælg:
			<ul>
				<li>Metode: <b>POST</b></li>
				<li>Overskrift: <b>Authorization</b> med værdien <b>Bearer</b>, et mellemrum og nøglen</li>
				<li>Anmodningstekst: <b>JSON</b> med feltet <b>text</b> sat til <b>Angivet input</b></li>
			</ul>
		</li>
		<li>Tilføj <b>Læs tekst op</b> (Speak Text) med <b>Indhold af URL</b>, så Siri siger, hvad der kom på.</li>
		<li>Kald genvejen <b>Tilføj til indkøb</b>. Navnet er det, du siger til Siri.</li>
	</ol>

	{#if keys?.length}
		<h2 class="sl">Nøgler</h2>
		{#each keys as k (k.id)}
			<div class="key pad">
				<span class="grow">{k.name}<small class="muted">Lavet {day(k.created_at)} · {k.last_used_at ? `brugt ${day(k.last_used_at)}` : 'ikke brugt endnu'}</small></span>
				<button type="button" class="btn danger sm" onclick={() => remove(k)}>Slet</button>
			</div>
		{/each}
	{/if}
</main>

<style>
	.lead {
		margin-bottom: 12px;
	}
	.row {
		display: flex;
		gap: 8px;
		align-items: end;
		flex-wrap: wrap;
	}
	.stack {
		display: grid;
		gap: 12px;
	}
	.steps {
		display: grid;
		gap: 10px;
		padding-inline-start: 36px;
		margin: 0;
	}
	.steps ul {
		margin: 6px 0 0;
		padding-inline-start: 18px;
	}
	.steps .link {
		word-break: break-all;
		text-align: start;
	}
	.key {
		display: flex;
		gap: 8px;
		align-items: center;
		padding-block: 8px;
	}
	.key small {
		display: block;
	}
	.msg {
		margin: 0;
	}
</style>
