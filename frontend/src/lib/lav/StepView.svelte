<script lang="ts" module>
	/** Ét trin i fremgangsmåden, med afsnittets overskrift ("Mornaysauce"), hvis det har en. */
	export interface Step {
		text: string;
		heading: string;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import Icon from '$lib/ui/Icon.svelte';
	import IngredientsSheet from './IngredientsSheet.svelte';

	interface Props {
		/** Rettens navn. */
		title: string;
		steps: Step[];
		/** Trinet, der vises (0 = det første). */
		index: number;
		/** Antal ingredienser, der er fundet frem, og antal i alt. */
		found: number;
		total: number;
		/** Retten er ganget op eller ned. */
		scaled: boolean;
		/** Skærmen holdes faktisk tændt. */
		awake: boolean;
		/** Gå til et trin (1 = det første). */
		ongo: (n: number) => void;
		/** Tilbage til oversigten. */
		onclose: () => void;
		/** Færdig med retten. */
		ondone: () => void;
		/** Ingredienslisten med de lokale kryds. */
		ingredients: Snippet;
		/** Barnets noter, gentaget under trinet. */
		notes?: Snippet;
	}
	let { title, steps, index, found, total, scaled, awake, ongo, onclose, ondone, ingredients, notes }: Props = $props();

	const step = $derived(steps[index]);
	const last = $derived(index === steps.length - 1);
	const where = $derived(`Trin ${index + 1} af ${steps.length}`);

	// iPad på tværs og computer: ingredienserne står fast til venstre i stedet for i et ark.
	const wide = new MediaQuery('(min-width: 900px)');
	let sheet = $state(false);
	let stage: HTMLDivElement | undefined = $state();

	const prev = () => index > 0 && ongo(index);
	const next = () => !last && ongo(index + 2);

	/** Nyt trin: teksten står øverst og får fokus, så skærmlæsere læser den op. */
	function arrive(node: HTMLElement) {
		if (stage) stage.scrollTop = 0;
		node.focus({ preventScroll: true });
	}

	// Piletasterne bladrer. Ikke bag et åbent ark og ikke fra et felt, der selv bruger pilene.
	function key(e: KeyboardEvent) {
		if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
		if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
		const el = e.target instanceof Element ? e.target : null;
		if (el?.closest('dialog, textarea, select, input:not([type="checkbox"])')) return;
		e.preventDefault();
		if (e.key === 'ArrowRight') next();
		else prev();
	}

	// Swipe til forrige/næste trin. Et strøg, der starter helt ude ved venstre
	// kant, er telefonens eget "tilbage" og bladrer ikke.
	const EDGE = 24;
	function swipe(node: HTMLElement) {
		let touch: { x: number; y: number } | null = null;
		const start = (e: TouchEvent) => {
			const t = e.touches[0];
			touch = e.touches.length === 1 && t.clientX >= EDGE ? { x: t.clientX, y: t.clientY } : null;
		};
		// Et tydeligt vandret strøg er vores: browseren skal ikke også bruge det
		// til at gå en side tilbage (berøringsskærme på computer).
		const move = (e: TouchEvent) => {
			if (!touch || !e.cancelable) return;
			const dx = e.touches[0].clientX - touch.x;
			const dy = e.touches[0].clientY - touch.y;
			if (Math.abs(dx) > 10 && Math.abs(dy) <= Math.abs(dx) * 0.7) e.preventDefault();
		};
		const end = (e: TouchEvent) => {
			if (!touch) return;
			const dx = e.changedTouches[0].clientX - touch.x;
			const dy = e.changedTouches[0].clientY - touch.y;
			touch = null;
			if (Math.abs(dx) < 70 || Math.abs(dy) > Math.abs(dx) * 0.7) return;
			if (dx < 0) next();
			else prev();
		};
		const cancel = () => (touch = null);
		node.addEventListener('touchstart', start, { passive: true });
		node.addEventListener('touchmove', move, { passive: false });
		node.addEventListener('touchend', end);
		node.addEventListener('touchcancel', cancel);
		return {
			destroy() {
				node.removeEventListener('touchstart', start);
				node.removeEventListener('touchmove', move);
				node.removeEventListener('touchend', end);
				node.removeEventListener('touchcancel', cancel);
			}
		};
	}
</script>

<svelte:window onkeydown={key} />

<div class="view">
	{#if wide.current}
		<aside aria-label="Ingredienser">
			<p class="sl">Find frem<span>{found} af {total}</span></p>
			{#if scaled}<p class="pad muted small">Teksten er fra opskriften. Brug mængderne her.</p>{/if}
			{@render ingredients()}
		</aside>
	{/if}

	<!-- Swipe er en genvej; knapperne i bunden og piletasterne gør det samme. -->
	<div class="col" use:swipe>
		<header class="pad">
			<h1 class="ey ellipsis grow">{title}</h1>
			<button type="button" class="btn sm" onclick={onclose}>Luk</button>
		</header>

		<div class="pad">
			<div class="prog" role="progressbar" aria-label="Fremgang" aria-valuemin={1} aria-valuemax={steps.length} aria-valuenow={index + 1} aria-valuetext={where}>
				{#each steps as _, i}<i class:on={i <= index}></i>{/each}
			</div>
		</div>

		<div class="stage" bind:this={stage}>
			{#key index}
				<div class="step">
					<!-- Skjult for skærmlæsere her: det samme står først i teksten, der får fokus. -->
					<p class="lab" aria-hidden="true">{where}</p>
					{#if step.heading}<p class="ey">{step.heading}</p>{/if}
					<p class="serif text" tabindex="-1" use:arrive><span class="sr">{where}.</span> {step.text}</p>
				</div>
			{/key}
			{#if notes}<div class="notes">{@render notes()}</div>{/if}
		</div>

		<div class="foot pad">
			{#if awake}<p class="ey awake">Skærmen holder sig tændt</p>{/if}
			{#if !wide.current}
				<button type="button" class="btn block" onclick={() => (sheet = true)}><Icon name="list" />Se ingredienser</button>
			{/if}
			<div class="btns">
				{#if index > 0}
					<button type="button" class="btn" onclick={prev}><span class="sr">Tilbage til trin {index}</span><span aria-hidden="true">Trin {index}</span></button>
				{/if}
				{#if last}
					<button type="button" class="btn primary" onclick={ondone}>Færdig</button>
				{:else}
					<button type="button" class="btn primary" onclick={next}>Næste trin</button>
				{/if}
			</div>
		</div>
	</div>
</div>

{#if sheet && !wide.current}
	<IngredientsSheet {found} {total} {scaled} onclose={() => (sheet = false)}>
		{@render ingredients()}
	</IngredientsSheet>
{/if}

<style>
	/* Fylder skærmen: top og knapper står fast, kun trinets tekst kan rulle. */
	.view {
		flex: 1;
		min-height: 0;
		display: flex;
	}
	.col {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		/* Vandrette strøg bladrer i trinene; browseren ruller kun lodret (og zoomer). */
		touch-action: pan-y pinch-zoom;
	}
	header {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 56px;
	}
	h1 {
		font-weight: 600;
	}
	.prog {
		display: flex;
		gap: 4px;
	}
	.prog i {
		flex: 1;
		min-width: 0;
		height: 4px;
		border-radius: 2px;
		background: var(--line);
	}
	.prog i.on {
		background: var(--ink);
	}
	.stage {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding-bottom: 16px;
	}
	.step {
		padding: 28px max(20px, env(safe-area-inset-right)) 0 max(20px, env(safe-area-inset-left));
		animation: step-in var(--t-tick) ease-out;
	}
	@keyframes step-in {
		from {
			opacity: 0;
		}
	}
	.step .ey {
		margin-top: 10px;
	}
	/* Læses på en armslængdes afstand. */
	.text {
		margin-top: 10px;
		font-size: var(--fs-step);
		line-height: 36px;
		font-weight: 600;
		outline: none;
	}
	.notes {
		margin-top: 14px;
	}
	/* Knapperne går fri af telefonens streg i bunden. */
	.foot {
		flex: none;
		display: grid;
		gap: 10px;
		padding-top: 8px;
		padding-bottom: calc(12px + env(safe-area-inset-bottom));
	}
	.awake {
		text-align: center;
	}
	@media (min-width: 900px) {
		aside {
			flex: none;
			width: 320px;
			overflow-y: auto;
			padding-bottom: 24px;
			border-right: 1px solid var(--line);
		}
		/* Teksten bliver ikke bredere, end den kan læses. */
		.col > * {
			width: 100%;
			max-width: 640px;
			margin-inline: auto;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.step {
			animation: none;
		}
	}
</style>
