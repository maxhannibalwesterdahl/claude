<script lang="ts" generics="T extends string | number">
	interface Props {
		options: { value: T; label: string }[];
		value: T;
		onchange: (v: T) => void;
		/** Navnet på gruppen for skærmlæsere (fx "Mængde"). */
		label: string;
		disabled?: boolean;
	}
	let { options, value, onchange, label, disabled = false }: Props = $props();

	let group: HTMLDivElement | undefined = $state();
	const current = $derived(options.findIndex((o) => o.value === value));

	// Som radioknapper: piletasterne flytter valget, og fokus følger med.
	function keydown(e: KeyboardEvent) {
		const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
		if (!step || !options.length) return;
		e.preventDefault();
		const next = (Math.max(current, 0) + step + options.length) % options.length;
		(group?.children[next] as HTMLElement | undefined)?.focus();
		onchange(options[next].value);
	}
</script>

<div class="seg" role="radiogroup" aria-label={label} bind:this={group}>
	{#each options as o, i (o.value)}
		<button
			type="button"
			role="radio"
			aria-checked={o.value === value}
			tabindex={i === Math.max(current, 0) ? 0 : -1}
			{disabled}
			onkeydown={keydown}
			onclick={() => o.value !== value && onchange(o.value)}
		>
			{o.label}
		</button>
	{/each}
</div>

<style>
	.seg {
		flex: none;
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		border-radius: 12px;
		background: var(--band);
	}
	button {
		position: relative;
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		height: 38px;
		min-width: 48px;
		padding: 0 12px;
		border-radius: 9px;
		font-size: 14.5px;
		font-weight: 600;
		color: var(--muted);
		white-space: nowrap;
	}
	/* Trykfladen rækker ud til 44px. */
	button::after {
		content: '';
		position: absolute;
		inset: -3px 0;
	}
	button[aria-checked='true'] {
		background: var(--card);
		color: var(--ink);
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
