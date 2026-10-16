<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';
	import type { IconName } from './icons';

	interface Props {
		/** Teksten på feltet, der kommer frem ("Har hjemme"). */
		label: string;
		icon?: IconName;
		onaction: () => void;
		disabled?: boolean;
		/** Rækken. */
		children: Snippet;
	}
	let { label, icon = 'home', onaction, disabled = false, children }: Props = $props();

	// De yderste 24px i venstre side er iPhonens "tilbage"-træk: dem rører vi ikke.
	const EDGE = 24;
	// Først efter 10px ved vi, om fingeren vil til siden eller rulle.
	const LOCK = 10;
	const MAX = 128;
	const FIRE = 96;
	const SLIDE_MS = 160;

	let row: HTMLDivElement | undefined = $state();
	let dx = $state(0);
	let dragging = $state(false);
	let start: { id: number; x: number; y: number } | null = null;
	// Et træk må ikke også blive til et tryk på rækken (fx "købt").
	let swallow = false;

	function down(e: PointerEvent) {
		swallow = false;
		if (disabled || dx > 0 || e.pointerType === 'mouse' || !e.isPrimary) return;
		if (e.clientX < EDGE) return;
		start = { id: e.pointerId, x: e.clientX, y: e.clientY };
	}

	function move(e: PointerEvent) {
		if (!start || e.pointerId !== start.id) return;
		const mx = e.clientX - start.x;
		const my = e.clientY - start.y;
		if (!dragging) {
			if (Math.hypot(mx, my) < LOCK) return;
			// Kun et tydeligt træk mod højre er vores. Alt andet er rulning.
			if (!(mx > 0 && Math.abs(mx) > 1.5 * Math.abs(my))) {
				start = null;
				return;
			}
			dragging = true;
			swallow = true;
			row?.setPointerCapture(e.pointerId);
		}
		dx = Math.min(MAX, Math.max(0, mx));
	}

	function up(e: PointerEvent) {
		if (!start || e.pointerId !== start.id) return;
		start = null;
		if (!dragging) return;
		dragging = false;
		if (dx < FIRE) {
			dx = 0;
			return;
		}
		// Rækken glider ud, og så udføres handlingen. Bliver rækken stående
		// (fx uden net), glider den tilbage på plads.
		dx = row?.offsetWidth ?? MAX;
		const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
		setTimeout(
			() => {
				onaction();
				dx = 0;
			},
			still ? 0 : SLIDE_MS
		);
	}

	function cancel() {
		start = null;
		dragging = false;
		dx = 0;
	}

	function click(e: MouseEvent) {
		if (!swallow) return;
		swallow = false;
		e.preventDefault();
		e.stopPropagation();
	}
</script>

<!-- Træk mod højre for en genvej. Kun for fingre: den, der bruger rækken, skal
     også tilbyde det samme uden træk (en knap), for trækket kan hverken nås med
     tastatur eller skærmlæser. -->
<div class="swipe" class:open={dx > 0}>
	<div class="act" aria-hidden="true"><Icon name={icon} size={20} />{label}</div>
	<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
	<div
		class="slide"
		class:dragging
		bind:this={row}
		style:transform={dx > 0 ? `translateX(${dx}px)` : undefined}
		onpointerdown={down}
		onpointermove={move}
		onpointerup={up}
		onpointercancel={cancel}
		onclickcapture={click}
	>
		{@render children()}
	</div>
</div>

<style>
	.swipe {
		position: relative;
		overflow: hidden;
	}
	.swipe.open {
		background: var(--kobt);
	}
	.act {
		position: absolute;
		inset: 0 auto 0 0;
		width: 96px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		color: var(--onkobt);
		font-size: 12px;
		font-weight: 700;
		visibility: hidden;
	}
	.open .act {
		visibility: visible;
	}
	.slide {
		position: relative;
		background: var(--paper);
		/* Lodret rulning er browserens. Vandret træk får vi. */
		touch-action: pan-y;
		transition: transform 160ms var(--ease);
	}
	.open .slide {
		box-shadow: -6px 0 12px rgba(0, 0, 0, 0.08);
	}
	.slide.dragging {
		transition: none;
	}
</style>
