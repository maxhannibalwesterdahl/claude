<script lang="ts">
	import { confirmState } from './confirm.svelte';

	let dialog: HTMLDialogElement | undefined = $state();
	const request = $derived(confirmState.request);

	// showModal() flytter fokus ind i dialogen (til "Annullér"), holder Tab inde i
	// den og giver fokus tilbage til knappen, der åbnede den, når den lukkes.
	$effect(() => {
		if (request && !dialog?.open) dialog?.showModal();
	});

	function answer(ok: boolean) {
		const r = confirmState.request;
		confirmState.request = null;
		dialog?.close();
		r?.resolve(ok);
	}
</script>

<dialog
	bind:this={dialog}
	class="card"
	aria-labelledby="confirm-message"
	oncancel={(e) => {
		e.preventDefault();
		answer(false);
	}}
>
	{#if request}
		<p id="confirm-message">{request.message}</p>
		<div class="row">
			<button onclick={() => answer(false)}>Annullér</button>
			<button class="primary" class:danger={request.danger} onclick={() => answer(true)}>{request.confirmLabel}</button>
		</div>
	{/if}
</dialog>

<style>
	dialog {
		width: min(400px, calc(100vw - 32px));
		padding: 16px;
		color: var(--fg);
		box-shadow: var(--shadow-sheet);
	}
	dialog::backdrop {
		background: var(--scrim);
	}
	p {
		margin: 0 0 16px;
		font-weight: 600;
	}
	.row {
		justify-content: flex-end;
	}
	.danger {
		background: var(--danger);
		border-color: var(--danger);
		color: var(--card);
	}
</style>
