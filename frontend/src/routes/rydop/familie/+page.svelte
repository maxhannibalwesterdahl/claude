<script lang="ts">
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { shopping } from '$lib/shopping.svelte';
	import { confirmDialog } from '$lib/confirm.svelte';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import type { HouseholdView } from '$lib/types';

	let view = $state<HouseholdView | null>(null);
	let error = $state('');
	let notice = $state('');
	let name = $state('');
	/** Medlemmet, der får nyt kodeord (id), og kodeordet, der skrives. */
	let resetting = $state<number | null>(null);
	let newPassword = $state('');
	let invite = $state<{ url: string; role: string } | null>(null);
	let current = $state('');
	let mine = $state('');

	const admin = $derived(view?.role === 'admin');

	async function load() {
		view = await api<HouseholdView>('/household');
		name = view.name;
	}

	$effect(() => {
		untrack(() => {
			load().catch((e) => (error = say(e)));
		});
	});

	async function run(fn: () => Promise<unknown>, done = '') {
		error = '';
		notice = '';
		try {
			await fn();
			if (done) notice = done;
		} catch (e) {
			error = say(e);
		}
	}

	const rename = () => run(async () => (view = await api<HouseholdView>('/household', { method: 'PATCH', body: { name } })), 'Navnet er gemt.');

	const makeInvite = (role: 'admin' | 'medlem') =>
		run(async () => {
			const inv = await api<{ token: string }>('/household/invites', { method: 'POST', body: { role } });
			invite = { url: `${location.origin}/join/${inv.token}`, role };
			await load();
		});

	async function share() {
		if (!invite) return;
		try {
			if (navigator.share) await navigator.share({ title: 'Madplan', text: 'Du er inviteret til Madplan', url: invite.url });
			else {
				await navigator.clipboard.writeText(invite.url);
				notice = 'Linket er kopieret.';
			}
		} catch {
			/* afbrudt */
		}
	}

	const revoke = (id: number) => run(async () => { await api(`/household/invites/${id}`, { method: 'DELETE' }); await load(); });

	const reset = (id: number) =>
		run(async () => {
			await api(`/household/members/${id}/password`, { method: 'POST', body: { password: newPassword } });
			resetting = null;
			newPassword = '';
		}, 'Kodeordet er ændret. Brugeren er logget ud overalt.');

	async function remove(id: number, username: string) {
		if (!(await confirmDialog(`Fjern ${username} fra familien?`, 'Fjern'))) return;
		await run(async () => { await api(`/household/members/${id}`, { method: 'DELETE' }); await load(); });
	}

	const setRole = (id: number, role: string) =>
		run(async () => { await api(`/household/members/${id}/role`, { method: 'PUT', body: { role } }); await load(); });

	let erasing = $state(false);
	let erasePassword = $state('');
	let eraseName = $state('');
	const erase = () =>
		run(async () => {
			await api('/household/erase', { method: 'POST', body: { password: erasePassword, name: eraseName } });
			shopping.clear();
			await goto('/login');
		});

	const changeMine = () =>
		run(async () => {
			await api('/me/password', { method: 'POST', body: { current, new: mine } });
			current = mine = '';
		}, 'Dit kodeord er ændret. Andre enheder er logget ud.');
</script>

<main>
	<ScreenHeader title="Familie" eyebrow="Ryd op" back="/rydop" />
	{#if error}<p class="msg pad" role="alert">{error}</p>{/if}
	{#if notice}<p class="pad muted" role="status">{notice}</p>{/if}

	{#if view}
		{#if admin}
			<form class="pad row" onsubmit={(e) => { e.preventDefault(); rename(); }}>
				<label class="field grow"><span>Familiens navn</span><input bind:value={name} maxlength="100" required /></label>
				<button class="btn sm" disabled={!name.trim() || name === view.name}>Gem</button>
			</form>
		{:else}
			<p class="pad muted">{view.name}</p>
		{/if}

		<h2 class="sl">Medlemmer</h2>
		{#each view.members as m (m.id)}
			<div class="member pad">
				<span class="grow">{m.username}{#if m.you} (dig){/if} <span class="tag">{m.role === 'admin' ? 'admin' : 'medlem'}</span></span>
				{#if admin && !m.you}
					<button type="button" class="btn quiet sm" onclick={() => { resetting = resetting === m.id ? null : m.id; newPassword = ''; }}>Nyt kodeord</button>
					<button type="button" class="btn quiet sm" onclick={() => setRole(m.id, m.role === 'admin' ? 'medlem' : 'admin')}>{m.role === 'admin' ? 'Gør til medlem' : 'Gør til admin'}</button>
					<button type="button" class="btn danger sm" onclick={() => remove(m.id, m.username)}>Fjern</button>
				{/if}
			</div>
			{#if resetting === m.id}
				<form class="pad row" onsubmit={(e) => { e.preventDefault(); reset(m.id); }}>
					<label class="field grow"><span>Nyt kodeord til {m.username} (mindst 12 tegn)</span><input type="password" bind:value={newPassword} minlength="12" autocomplete="new-password" required /></label>
					<button class="btn sm">Gem</button>
				</form>
			{/if}
		{/each}

		{#if admin}
			<h2 class="sl">Invitation</h2>
			<p class="pad muted">Send et link. Den inviterede vælger selv brugernavn og kodeord. Linket virker én gang i 7 dage.</p>
			<p class="pad row">
				<button type="button" class="btn sm" onclick={() => makeInvite('medlem')}>Inviter medlem</button>
				<button type="button" class="btn quiet sm" onclick={() => makeInvite('admin')}>Inviter admin</button>
			</p>
			{#if invite}
				<div class="pad">
					<input readonly value={invite.url} onfocus={(e) => e.currentTarget.select()} aria-label="Invitationslink" />
					<p><button type="button" class="btn sm" onclick={share}>Del linket</button> <span class="muted">Vises kun nu.</span></p>
				</div>
			{/if}
			{#each view.invites as i (i.id)}
				<div class="member pad">
					<span class="grow">Åben invitation ({i.role}) til {new Date(i.expires_at).toLocaleDateString('da-DK')}</span>
					<button type="button" class="btn danger sm" onclick={() => revoke(i.id)}>Træk tilbage</button>
				</div>
			{/each}
		{/if}
	{/if}

	{#if admin}
		<h2 class="sl">Jeres data</h2>
		<p class="pad"><a class="btn sm" href="/api/household/export" download>Hent familiens data</a></p>
		<p class="pad muted"><a class="link" href="/privatliv">Sådan passer vi på jeres data</a></p>
		{#if !erasing}
			<p class="pad"><button type="button" class="btn danger sm" onclick={() => (erasing = true)}>Slet familien og alle data</button></p>
		{:else}
			<form class="pad stack" onsubmit={(e) => { e.preventDefault(); erase(); }}>
				<p>Det sletter alle planer, indkøb, noter og brugere i familien for altid. Det kan ikke fortrydes.</p>
				<label class="field"><span>Skriv familiens navn: {view?.name}</span><input bind:value={eraseName} required /></label>
				<label class="field"><span>Dit kodeord</span><input type="password" bind:value={erasePassword} autocomplete="current-password" required /></label>
				<button class="btn danger sm">Slet for altid</button>
				<button type="button" class="btn quiet sm" onclick={() => (erasing = false)}>Annuller</button>
			</form>
		{/if}
	{/if}

	<h2 class="sl">Mit kodeord</h2>
	<form class="pad stack" onsubmit={(e) => { e.preventDefault(); changeMine(); }}>
		<label class="field"><span>Nuværende kodeord</span><input type="password" bind:value={current} autocomplete="current-password" required /></label>
		<label class="field"><span>Nyt kodeord (mindst 12 tegn)</span><input type="password" bind:value={mine} minlength="12" autocomplete="new-password" required /></label>
		<button class="btn sm">Skift kodeord</button>
	</form>
</main>

<style>
	.row {
		display: flex;
		gap: 8px;
		align-items: end;
		flex-wrap: wrap;
	}
	.member {
		display: flex;
		gap: 8px;
		align-items: center;
		flex-wrap: wrap;
		padding-block: 8px;
	}
	.stack {
		display: grid;
		gap: 12px;
	}
	.msg {
		margin: 0;
	}
</style>
