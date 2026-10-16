<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import { shopping } from '$lib/shopping.svelte';
	import type { Me } from '$lib/types';
	import { say } from '$lib/ui/copy';

	const token = $derived(page.params.token);
	let info = $state<{ household: string; role: string } | null>(null);
	let invalid = $state(false);
	let username = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	$effect(() => {
		untrack(() => {
			api<{ household: string; role: string }>(`/invites/${token}`)
				.then((i) => (info = i))
				.catch(() => (invalid = true));
		});
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			const me = await api<Me>(`/invites/${token}/accept`, { method: 'POST', body: { username, password } });
			shopping.use(me.id);
			await goto('/');
		} catch (err) {
			error = say(err);
		} finally {
			busy = false;
		}
	}
</script>

<main class="login pad">
	<h1 class="serif">Madplan</h1>
	{#if invalid}
		<p role="alert">Invitationen er ugyldig eller udløbet. Bed om en ny.</p>
		<p><a class="link" href="/login">Til login</a></p>
	{:else if info}
		<p class="muted intro">Du er inviteret til <b>{info.household}</b>. Vælg et brugernavn og et kodeord (mindst 12 tegn).</p>
		<form onsubmit={submit}>
			<label class="field">
				<span>Brugernavn</span>
				<input bind:value={username} autocomplete="username" autocapitalize="none" required />
			</label>
			<label class="field">
				<span>Kodeord</span>
				<input type="password" bind:value={password} autocomplete="new-password" minlength="12" required />
			</label>
			{#if error}<p class="msg" role="alert">{error}</p>{/if}
			<button class="btn primary block" disabled={busy}>{busy ? 'Opretter…' : 'Opret bruger'}</button>
		</form>
	{/if}
</main>

<style>
	.login {
		max-width: 392px;
		padding-top: calc(12vh + env(safe-area-inset-top));
		text-align: center;
	}
	h1 {
		margin: 12px 0 24px;
		font-size: var(--fs-title);
		line-height: 36px;
	}
	.intro {
		margin: 0 0 18px;
	}
	form {
		display: grid;
		gap: 14px;
		text-align: left;
	}
	.msg {
		margin: 0;
	}
</style>
