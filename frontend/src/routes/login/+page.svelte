<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			await api('/login', { method: 'POST', body: { username, password } });
			const target = page.url.searchParams.get('til') ?? '/';
			// Kun stier i appen, ikke andre sider.
			await goto(target.startsWith('/') && !target.startsWith('//') ? target : '/');
		} catch (err) {
			error = err instanceof ApiError ? err.message : 'Noget gik galt';
		} finally {
			busy = false;
		}
	}
</script>

<main class="login">
	<svg viewBox="0 0 64 64" class="logo" aria-hidden="true">
		<rect width="64" height="64" rx="14" fill="var(--accent)" />
		<path d="M14 30h36a18 18 0 0 1-36 0z" fill="var(--accent-fg)" />
		<path d="M25 22c0-4 4-4 4-8M35 22c0-4 4-4 4-8" stroke="var(--accent-fg)" stroke-width="3" stroke-linecap="round" fill="none" />
	</svg>
	<h1>Madplan</h1>
	<form onsubmit={submit}>
		<label class="field">
			<span>Brugernavn</span>
			<input bind:value={username} autocomplete="username" autocapitalize="none" required />
		</label>
		<label class="field">
			<span>Kodeord</span>
			<input type="password" bind:value={password} autocomplete="current-password" required />
		</label>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		<button class="primary" disabled={busy}>{busy ? 'Logger ind…' : 'Log ind'}</button>
	</form>
</main>

<style>
	.login {
		max-width: 360px;
		padding-top: calc(12vh + env(safe-area-inset-top));
		text-align: center;
	}
	.logo {
		width: 64px;
		height: 64px;
	}
	h1 {
		margin: 12px 0 24px;
	}
	form {
		display: grid;
		gap: 14px;
		text-align: left;
	}
	button {
		justify-content: center;
		margin-top: 4px;
	}
</style>
