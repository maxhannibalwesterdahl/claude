import type { Action } from 'svelte/action';

const HOLD_MS = 500;
const SLOP = 10;

/**
 * Langt tryk: `use:longpress={() => …}`. Udløses efter et halvt sekund uden at
 * fingeren flytter sig, og af højreklik og tastaturets menutast. Trykket, der
 * følger, når fingeren slippes, bliver ikke til et klik.
 * Et langt tryk kan ikke nås med skærmlæser: tilbyd altid det samme på en knap.
 */
export const longpress: Action<HTMLElement, () => void> = (node, callback) => {
	let fn = callback;
	let timer: ReturnType<typeof setTimeout> | undefined;
	let x = 0;
	let y = 0;
	let fired = false;

	const clear = () => {
		clearTimeout(timer);
		timer = undefined;
	};

	function down(e: PointerEvent) {
		fired = false;
		if (!e.isPrimary || e.button !== 0) return;
		x = e.clientX;
		y = e.clientY;
		clear();
		timer = setTimeout(() => {
			timer = undefined;
			fired = true;
			fn();
		}, HOLD_MS);
	}

	function move(e: PointerEvent) {
		if (timer && Math.hypot(e.clientX - x, e.clientY - y) > SLOP) clear();
	}

	function menu(e: Event) {
		e.preventDefault();
		clear();
		// På Android følger en menu-hændelse efter et langt tryk: kun én gang.
		if (!fired) fn();
	}

	function click(e: Event) {
		if (!fired) return;
		fired = false;
		e.preventDefault();
		e.stopPropagation();
	}

	node.style.setProperty('-webkit-touch-callout', 'none');
	node.style.setProperty('-webkit-user-select', 'none');
	node.style.setProperty('user-select', 'none');

	node.addEventListener('pointerdown', down);
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerup', clear);
	node.addEventListener('pointercancel', clear);
	node.addEventListener('pointerleave', clear);
	node.addEventListener('contextmenu', menu);
	node.addEventListener('click', click, true);

	return {
		update(next) {
			fn = next;
		},
		destroy() {
			clear();
			node.removeEventListener('pointerdown', down);
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerup', clear);
			node.removeEventListener('pointercancel', clear);
			node.removeEventListener('pointerleave', clear);
			node.removeEventListener('contextmenu', menu);
			node.removeEventListener('click', click, true);
		}
	};
};
