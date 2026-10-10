<script lang="ts">
	import Icon from './Icon.svelte';

	interface Props {
		checked: boolean;
		/** md 26px (ingredienslinjer), lg 30px (indkøbsrækker). */
		size?: 'md' | 'lg';
	}
	let { checked, size = 'md' }: Props = $props();
</script>

<!-- Kun til øjet. Om der er krydset af, fortæller knappen eller feltet omkring. -->
<span class="tick {size}" class:on={checked} aria-hidden="true">
	<Icon name="check" size={size === 'lg' ? 17 : 15} stroke={3} />
</span>

<style>
	.tick {
		flex: none;
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		box-shadow: inset 0 0 0 2px var(--ring);
		color: var(--paper);
		transition:
			background var(--t-tick),
			box-shadow var(--t-tick);
	}
	.lg {
		width: 30px;
		height: 30px;
	}
	.tick :global(svg) {
		opacity: 0;
		transform: scale(0.6);
		transition:
			opacity var(--t-tick),
			transform var(--t-tick) var(--ease);
	}
	.on {
		background: var(--kobt);
		box-shadow: none;
	}
	.on :global(svg) {
		opacity: 1;
		transform: none;
	}
</style>
