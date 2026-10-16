import type { Action } from 'svelte/action';

const HOLD_MS = 500;
const SLOP = 10;

/**
 * Langt tryk: `use:longpress={() => …}`. Udløses efter et halvt sekund uden at
 * fingeren flytter sig, og af højreklik og tastaturets menutast. Trykket, der
 * følger, når fingeren slippes, bliver ikke til et klik: hverken på elementet
 * selv eller på det, der er åbnet imens (et ark, der ligger under fingeren).
 * Et langt tryk kan ikke nås med skærmlæser: tilbyd altid det samme på en knap.
 */
export const longpress: Action<HTMLElement, () => void> = (node, callback) => {
	let fn = callback;
	let timer: ReturnType<typeof setTimeout> | undefined;
	let x = 0;
	let y = 0;
	let fired = false;
	/** Fingeren er nede på elementet. */
	let held = false;

	const clear = () => {
		clearTimeout(timer);
		timer = undefined;
	};

	// Det lange tryk udløses, mens fingeren stadig er nede. Åbner det et ark,
	// lander trykket, der følger, når fingeren slippes, på arket: på baggrunden
	// (som lukker det igen) eller på en knap i det. Derfor fanges det ene tryk
	// på hele siden og ikke kun på elementet.
	let unswallow: (() => void) | undefined;
	function swallow() {
		unswallow?.();
		let after: ReturnType<typeof setTimeout> | undefined;
		const eat = (e: Event) => {
			e.preventDefault();
			e.stopPropagation();
			stop();
		};
		// Trykket følger lige efter, at fingeren er sluppet. Kommer det ikke, er der ikke noget at fange.
		const lifted = () => (after = setTimeout(stop, 400));
		const stop = () => {
			clearTimeout(after);
			removeEventListener('click', eat, true);
			removeEventListener('pointerup', lifted, true);
			removeEventListener('pointercancel', stop, true);
			removeEventListener('pointerdown', stop, true);
			unswallow = undefined;
			fired = false;
		};
		addEventListener('click', eat, true);
		addEventListener('pointerup', lifted, true);
		addEventListener('pointercancel', stop, true);
		addEventListener('pointerdown', stop, true);
		unswallow = stop;
	}

	function down(e: PointerEvent) {
		fired = false;
		if (!e.isPrimary || e.button !== 0) return;
		x = e.clientX;
		y = e.clientY;
		held = true;
		clear();
		timer = setTimeout(() => {
			timer = undefined;
			fired = true;
			swallow();
			fn();
		}, HOLD_MS);
	}

	function move(e: PointerEvent) {
		if (timer && Math.hypot(e.clientX - x, e.clientY - y) > SLOP) clear();
	}

	function up() {
		held = false;
		clear();
	}

	function menu(e: Event) {
		e.preventDefault();
		clear();
		// På Android følger en menu-hændelse efter et langt tryk: kun én gang.
		// Kommer den først, er fingeren stadig nede, og trykket bagefter fanges også.
		if (fired) return;
		if (held) swallow();
		fn();
	}

	node.style.setProperty('-webkit-touch-callout', 'none');
	node.style.setProperty('-webkit-user-select', 'none');
	node.style.setProperty('user-select', 'none');

	node.addEventListener('pointerdown', down);
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerup', up);
	node.addEventListener('pointercancel', up);
	node.addEventListener('pointerleave', up);
	node.addEventListener('contextmenu', menu);

	return {
		update(next) {
			fn = next;
		},
		destroy() {
			clear();
			unswallow?.();
			node.removeEventListener('pointerdown', down);
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerup', up);
			node.removeEventListener('pointercancel', up);
			node.removeEventListener('pointerleave', up);
			node.removeEventListener('contextmenu', menu);
		}
	};
};
