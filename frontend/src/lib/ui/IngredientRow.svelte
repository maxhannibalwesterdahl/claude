<script lang="ts">
	import type { Snippet } from 'svelte';
	import Tick from './Tick.svelte';

	interface Props {
		/** Mængden, som formatQuantity(...) giver den. */
		qty: string;
		name: string;
		/** ", finthakket" i dæmpet skrift. */
		note?: string | null;
		/** Dæmpet navn (rest, basisvare). */
		dim?: boolean;
		/** undefined: ingen afkrydsning. */
		checked?: boolean;
		/** Givet: linjen kan krydses af ved at trykke på den. */
		ontoggle?: (next: boolean) => void;
		/** Det, afkrydsningen betyder, for skærmlæsere (fx "har hjemme"). */
		tickLabel?: string;
		/** Til sidst på linjen (stjerne, "rest", mærker). */
		trailing?: Snippet;
	}
	let { qty, name, note = null, dim = false, checked, ontoggle, tickLabel, trailing }: Props = $props();

	const uid = $props.id();
</script>

{#snippet text()}
	<span class="q">{qty}</span>
	<span class="n" class:dim={dim || checked}>{name}{#if note}<span class="more">, {note}</span>{/if}</span>
{/snippet}

<!-- Én ingredienslinje. Med ontoggle er mængde, navn og afkrydsning ledetekst for
     et skjult afkrydsningsfelt, så hele linjen kan trykkes. Det, der står til
     sidst (fx en knap), ligger uden for ledeteksten og har sit eget tryk. -->
<div class="ing">
	{#if ontoggle}
		<input
			id={uid}
			type="checkbox"
			class="sr"
			checked={!!checked}
			aria-label={[qty, name].filter(Boolean).join(' ') + (tickLabel ? `, ${tickLabel}` : '')}
			onchange={(e) => ontoggle(e.currentTarget.checked)}
		/>
		<label class="main" for={uid}>{@render text()}</label>
		{#if trailing}<span class="t">{@render trailing()}</span>{/if}
		<label class="end" for={uid}><Tick checked={!!checked} /></label>
	{:else}
		<span class="main">{@render text()}</span>
		{#if trailing}<span class="t">{@render trailing()}</span>{/if}
		{#if checked !== undefined}<span class="end"><Tick {checked} /></span>{/if}
	{/if}
</div>

<style>
	.ing {
		display: flex;
		align-items: stretch;
		gap: 10px;
		min-height: var(--ing-h);
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	.main {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 10px;
		padding-block: 6px;
	}
	.q {
		flex: none;
		width: 72px;
		text-align: right;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.n {
		flex: 1;
		min-width: 0;
		font-size: 16.5px;
		transition: color var(--t-tick);
	}
	/* Krydset af: dæmpet, ikke streget over. Det er kun købte varer, der streges. */
	.dim,
	.more {
		color: var(--muted);
	}
	.t,
	.end {
		flex: none;
		display: flex;
		align-items: center;
		gap: 6px;
	}
	label {
		cursor: pointer;
	}
	.ing:has(input:focus-visible) {
		outline: 2px solid var(--ink);
		outline-offset: 2px;
		border-radius: 4px;
	}
</style>
