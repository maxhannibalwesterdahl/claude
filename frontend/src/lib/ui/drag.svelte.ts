/**
 * Træk og slip, der virker med både mus og finger. HTML's egen træk og slip
 * virker ikke på telefonen, så det er bygget på pointer-hændelser:
 *
 * - Finger og pen: hold fingeren stille på en ret (et kort øjeblik), så løftes
 *   den, og den kan trækkes hen på en dag. Flytter fingeren sig før, er det en
 *   almindelig rulning.
 * - Mus: tryk og træk et par pixel.
 *
 * `use:draggable={'meal:12'}` gør et element trækbart. `use:dropzone={handler}`
 * gør et element til et sted, der kan slippes på. Et kort tryk er stadig et tryk.
 */

/** Det, der trækkes lige nu (fx "meal:12"). Tom, når der ikke trækkes. */
export const dragState = $state<{ payload: string }>({ payload: '' });

type DropHandler = (payload: string) => void;
const zones = new WeakMap<Element, DropHandler>();

/** Så længe skal fingeren holdes stille, før retten løftes. */
const HOLD_MS = 380;
/** Så langt må fingeren flytte sig under holdet; ellers er det en rulning. */
const SLOP = 8;
/** Musen: så langt skal der trækkes, før det er et træk og ikke et klik. */
const MOUSE_START = 6;
/** Tæt på skærmens top eller bund ruller siden med. */
const EDGE = 70;

interface Session {
	payload: string;
	source: HTMLElement;
	ghost: HTMLElement;
	dx: number;
	dy: number;
	over: Element | null;
	x: number;
	y: number;
	raf: number;
}

let active: Session | null = null;
/** Tryk, et trækbart element allerede har taget. */
const claimed = new WeakSet<Event>();

function zoneAt(x: number, y: number): Element | null {
	const hit = document.elementFromPoint(x, y);
	return hit?.closest('[data-dropzone]') ?? null;
}

function setOver(s: Session, zone: Element | null) {
	if (zone === s.over) return;
	s.over?.classList.remove('drop-over');
	zone?.classList.add('drop-over');
	s.over = zone;
	// Over skraldespanden bliver retten lille, så det ses, at den forsvinder.
	s.ghost.classList.toggle('to-trash', !!zone && zone.hasAttribute('data-trash'));
}

function place(s: Session) {
	s.ghost.style.transform = `translate(${s.x - s.dx}px, ${s.y - s.dy}px) scale(1.04)`;
	setOver(s, zoneAt(s.x, s.y));
}

/** Ruller siden, mens fingeren står ved kanten. */
function autoScroll() {
	const s = active;
	if (!s) return;
	const h = window.innerHeight;
	// Står fingeren på skraldespanden (nederst), skal siden ikke rulle.
	const onTrash = !!s.over?.hasAttribute('data-trash');
	const step = onTrash ? 0 : s.y < EDGE ? -Math.ceil((EDGE - s.y) / 6) : s.y > h - EDGE ? Math.ceil((s.y - (h - EDGE)) / 6) : 0;
	if (step) {
		window.scrollBy(0, step);
		setOver(s, zoneAt(s.x, s.y));
	}
	s.raf = requestAnimationFrame(autoScroll);
}

function begin(source: HTMLElement, payload: string, x: number, y: number) {
	const r = source.getBoundingClientRect();
	// En kopi af retten følger fingeren (placeret med translate fra hjørnet).
	const ghost = source.cloneNode(true) as HTMLElement;
	ghost.removeAttribute('id');
	ghost.removeAttribute('data-day');
	ghost.setAttribute('aria-hidden', 'true');
	ghost.classList.add('drag-ghost');
	// Skrumper den (over skraldespanden), er det ind mod fingeren.
	Object.assign(ghost.style, { width: `${r.width}px`, height: `${r.height}px`, transformOrigin: `${x - r.left}px ${y - r.top}px` });
	document.body.append(ghost);
	source.classList.add('drag-source');
	document.body.classList.add('dragging');
	active = { payload, source, ghost, dx: x - r.left, dy: y - r.top, over: null, x, y, raf: 0 };
	place(active);
	active.raf = requestAnimationFrame(autoScroll);
	dragState.payload = payload;
	navigator.vibrate?.(12);
}

function end(drop: boolean) {
	const s = active;
	if (!s) return;
	active = null;
	cancelAnimationFrame(s.raf);
	s.ghost.remove();
	s.source.classList.remove('drag-source');
	document.body.classList.remove('dragging');
	const zone = s.over;
	setOver(s, null);
	dragState.payload = '';
	if (drop && zone) zones.get(zone)?.(s.payload);
}

// Mens der trækkes, må siden ikke rulle under fingeren.
function blockTouch(e: TouchEvent) {
	if (active) e.preventDefault();
}
if (typeof document !== 'undefined') {
	document.addEventListener('touchmove', blockTouch, { passive: false });
}

/** Gør elementet trækbart. `payload` er det, stedet, der slippes på, får (fx "meal:12"). */
export function draggable(node: HTMLElement, payload: string) {
	let current = payload;
	let timer = 0;
	let start: { x: number; y: number; id: number; touch: boolean } | null = null;
	// Klikket, der følger efter et træk, må ikke også åbne dagen.
	let swallowClick = false;

	node.classList.add('can-drag');

	function reset() {
		clearTimeout(timer);
		start = null;
		window.removeEventListener('pointermove', move);
		window.removeEventListener('pointerup', up);
		window.removeEventListener('pointercancel', cancel);
	}

	function down(e: PointerEvent) {
		// Et trækbart element inde i et andet (en ekstra ret i dagens række): det inderste vinder.
		if (active || e.button !== 0 || !current || claimed.has(e)) return;
		claimed.add(e);
		const touch = e.pointerType !== 'mouse';
		start = { x: e.clientX, y: e.clientY, id: e.pointerId, touch };
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', up);
		window.addEventListener('pointercancel', cancel);
		if (touch) {
			timer = window.setTimeout(() => {
				if (!start) return;
				begin(node, current, start.x, start.y);
				swallowClick = true;
			}, HOLD_MS);
		}
	}

	function move(e: PointerEvent) {
		if (!start || e.pointerId !== start.id) return;
		if (active) {
			active.x = e.clientX;
			active.y = e.clientY;
			place(active);
			return;
		}
		const moved = Math.hypot(e.clientX - start.x, e.clientY - start.y);
		if (start.touch) {
			// Fingeren flyttede sig før holdet var nok: det er en rulning.
			if (moved > SLOP) reset();
		} else if (moved > MOUSE_START) {
			begin(node, current, start.x, start.y);
			swallowClick = true;
			active!.x = e.clientX;
			active!.y = e.clientY;
			place(active!);
		}
	}

	function up(e: PointerEvent) {
		if (start && e.pointerId !== start.id) return;
		const wasDragging = !!active;
		reset();
		if (wasDragging) end(true);
	}

	function cancel() {
		reset();
		end(false);
	}

	function click(e: MouseEvent) {
		if (!swallowClick) return;
		swallowClick = false;
		e.preventDefault();
		e.stopPropagation();
	}

	// iOS viser ellers sin egen menu ved langt tryk på links og billeder.
	function contextmenu(e: Event) {
		if (start?.touch || active) e.preventDefault();
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && active) end(false);
	}

	node.addEventListener('pointerdown', down);
	node.addEventListener('click', click, true);
	node.addEventListener('contextmenu', contextmenu);
	node.addEventListener('dragstart', (e) => e.preventDefault());
	window.addEventListener('keydown', keydown);

	return {
		update(p: string) {
			current = p;
		},
		destroy() {
			reset();
			if (active?.source === node) end(false);
			node.removeEventListener('pointerdown', down);
			node.removeEventListener('click', click, true);
			node.removeEventListener('contextmenu', contextmenu);
			window.removeEventListener('keydown', keydown);
		}
	};
}

/** Gør elementet til et sted, der kan slippes på. */
export function dropzone(node: HTMLElement, ondrop: DropHandler) {
	node.dataset.dropzone = '';
	zones.set(node, ondrop);
	return {
		update(fn: DropHandler) {
			zones.set(node, fn);
		},
		destroy() {
			zones.delete(node);
			node.classList.remove('drop-over');
		}
	};
}
