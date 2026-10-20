<script lang="ts">
	import { dragState, dropzone } from '$lib/ui/drag.svelte';
	import Icon from '$lib/ui/Icon.svelte';

	interface Props {
		/** En ret ("meal:<id>") eller et ønske ("wish:<id>") er sluppet i skraldespanden. */
		ondrop: (payload: string) => unknown;
	}
	let { ondrop }: Props = $props();

	// Kun retter og ønsker kan slettes herfra (ikke forslag fra jeres opskrifter).
	const kind = $derived(dragState.payload.split(':')[0]);
	const shown = $derived(kind === 'meal' || kind === 'wish');
</script>

<!-- Kommer frem nederst, mens en ret eller et ønske trækkes. Slip retten her for
     at fjerne den fra ugen (eller ønsket fra ønskelisten). -->
<div class="trash" class:shown data-trash use:dropzone={ondrop} aria-hidden={!shown}>
	<Icon name="trash" size={24} stroke={2} />
	<span>{kind === 'wish' ? 'Fjern ønsket' : 'Fjern retten'}</span>
</div>

<style>
	.trash {
		position: fixed;
		left: 50%;
		bottom: calc(var(--nav-h) + env(safe-area-inset-bottom) + 16px);
		z-index: 999;
		display: flex;
		align-items: center;
		gap: 8px;
		height: 56px;
		padding: 0 22px;
		border-radius: var(--r-pill);
		background: var(--card);
		box-shadow: var(--shadow-sheet);
		color: var(--ink);
		font-weight: 600;
		opacity: 0;
		pointer-events: none;
		transform: translate(-50%, 24px) scale(0.9);
		transition:
			opacity 160ms ease,
			transform 160ms ease;
	}
	/* Kun synlig (og en mulig plads at slippe) mens der trækkes. */
	.shown {
		opacity: 1;
		pointer-events: auto;
		transform: translate(-50%, 0) scale(1);
	}
	/* Fingeren er over spanden: rød og lidt større. Vinder over den fælles .drop-over. */
	.trash:global(.drop-over) {
		background: var(--tomat) !important;
		box-shadow: var(--shadow-sheet) !important;
		color: var(--paper);
		transform: translate(-50%, 0) scale(1.08);
	}
	@media (prefers-reduced-motion: reduce) {
		.trash {
			transition: none;
		}
	}
</style>
