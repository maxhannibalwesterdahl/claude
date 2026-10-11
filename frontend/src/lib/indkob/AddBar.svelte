<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from '$lib/ui/Icon.svelte';

	interface Props {
		/** Teksten i feltet. Siden tømmer den, når varen er læst. */
		value: string;
		/** Varen er ved at blive læst: der kan ikke sendes igen imens. */
		busy?: boolean;
		onadd: (text: string) => void;
		/** Lige over feltet: sætningen, når noget ikke gik. */
		above?: Snippet;
	}
	let { value = $bindable(), busy = false, onadd, above }: Props = $props();

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const text = value.trim();
		if (text && !busy) onadd(text);
	}
</script>

<!-- Ligger fast over fanelinjen og løfter sig over skærmtastaturet (.dock). -->
<div class="dock">
	{@render above?.()}
	<form class="bar" onsubmit={submit}>
		<Icon name="plus" size={22} stroke={2.4} />
		<input
			bind:value
			placeholder="Tilføj vare, fx bleer"
			aria-label="Tilføj vare"
			maxlength="200"
			enterkeyhint="done"
			autocomplete="off"
			autocapitalize="off"
		/>
		{#if value.trim()}<button class="btn sm primary" disabled={busy}>Tilføj</button>{/if}
	</form>
</div>

<style>
	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 52px;
		padding: 0 6px 0 14px;
		border-radius: 16px;
		background: var(--card);
		box-shadow: var(--shadow-float);
	}
	.bar :global(svg) {
		color: var(--tomat);
	}
	/* Feltet har ingen egen flade: bjælken er feltet, og den bærer fokusringen. */
	input {
		flex: 1;
		height: 100%;
		min-height: 0;
		padding: 0;
		border-radius: 0;
		background: none;
		outline: none;
	}
	.bar:focus-within {
		outline: 2px solid var(--ink);
		outline-offset: 2px;
	}
	.bar:has(.btn:focus-visible) {
		outline: none;
	}
</style>
