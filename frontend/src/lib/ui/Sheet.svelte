<script lang="ts" module>
	// Antal åbne ark. Siden bagved er låst, så længe mindst ét er åbent.
	let openSheets = 0;
</script>

<script lang="ts">
	import { onMount, type Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	interface Props {
		/** Arkets titel. Dialogen er navngivet efter den. */
		title: string;
		/** Lille dæmpet linje ved titlen. */
		eyebrow?: string;
		/** true: linjen står over titlen (dagen). Ellers under (vælgeren). */
		eyebrowAbove?: boolean;
		/** auto: så højt som indholdet, højst 88dvh. tall: altid 88dvh. */
		size?: 'auto' | 'tall';
		/** Kaldes efter Escape, tryk på baggrunden, træk ned eller Luk, når arket er gledet ud. */
		onclose: () => void;
		/** Til højre for titlen (tallerken, "Færdig"). Erstatter Luk-knappen. */
		aside?: Snippet<[close: () => void]>;
		/** Ligger fast under indholdet (knapper, søgefelt). */
		footer?: Snippet<[close: () => void]>;
		/** Indholdet, der kan rulle. */
		children: Snippet<[close: () => void]>;
		/** none: fokus lander på arket selv, så tastaturet ikke springer frem. first: det første felt. */
		initialFocus?: 'none' | 'first';
		labelClose?: string;
	}
	let {
		title,
		eyebrow,
		eyebrowAbove = false,
		size = 'auto',
		onclose,
		aside,
		footer,
		children,
		initialFocus = 'none',
		labelClose = 'Luk'
	}: Props = $props();

	const uid = $props.id();
	// Samme tid som --t-sheet.
	const EXIT_MS = 200;

	let dialog: HTMLDialogElement | undefined = $state();
	let body: HTMLDivElement | undefined = $state();
	let closing = $state(false);
	/** Hvor langt arket er trukket ned (px). null = der trækkes ikke. */
	let pulled = $state<number | null>(null);
	let done = false;

	// showModal() holder Tab inde i arket, gør siden bagved inaktiv og lukker på
	// Escape. Når arket fjernes, får det, der åbnede det, fokus igen.
	onMount(() => {
		const el = dialog!;
		const opener = document.activeElement;
		el.showModal();
		const field = initialFocus === 'first' ? el.querySelector<HTMLElement>('input:not([type="hidden"]), select, textarea') : null;
		(field ?? el).focus();
		if (++openSheets === 1) document.documentElement.classList.add('sheet-open');
		return () => {
			done = true;
			if (--openSheets === 0) document.documentElement.classList.remove('sheet-open');
			el.close();
			if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
		};
	});

	function finish() {
		if (done) return;
		done = true;
		onclose();
	}

	/** Lad arket glide ud, og sig så til. Gives også til aside, footer og indholdet. */
	function close() {
		if (closing) return;
		closing = true;
		const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
		setTimeout(finish, still ? 0 : EXIT_MS);
	}

	// Træk ned i håndtaget eller toppen for at lukke. Kun på telefon, og kun når
	// indholdet står øverst, så det ikke forveksles med at rulle.
	let grip: { id: number; y: number } | null = null;
	let last = { y: 0, t: 0 };
	let speed = 0;

	function down(e: PointerEvent) {
		if (closing || !e.isPrimary || e.button !== 0) return;
		if (matchMedia('(min-width: 700px)').matches) return;
		if ((e.target as Element).closest('button, a, input, select, textarea, label')) return;
		if (body && body.scrollTop > 0) return;
		grip = { id: e.pointerId, y: e.clientY };
		last = { y: e.clientY, t: e.timeStamp };
		speed = 0;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function move(e: PointerEvent) {
		if (!grip || e.pointerId !== grip.id) return;
		const dt = e.timeStamp - last.t;
		if (dt > 0) speed = (e.clientY - last.y) / dt;
		last = { y: e.clientY, t: e.timeStamp };
		pulled = Math.max(0, e.clientY - grip.y);
	}

	function up(e: PointerEvent) {
		if (!grip || e.pointerId !== grip.id) return;
		grip = null;
		const far = pulled ?? 0;
		pulled = null;
		// Langt nok, eller et hurtigt svirp nedad. Ellers fjedrer arket tilbage.
		// En finger, der har ligget stille, før den slipper, svirper ikke.
		const flick = e.timeStamp - last.t < 100 && speed > 0.5;
		if (far > 120 || (far > 0 && flick)) close();
	}

	function cancel() {
		grip = null;
		pulled = null;
	}
</script>

<!-- Tryk på den mørke baggrund (dialogen selv, uden for indholdet) lukker. Tastaturet har Escape og Luk-knappen. -->
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog
	bind:this={dialog}
	class="sheet {size}"
	class:out={closing}
	class:pulling={pulled !== null}
	aria-labelledby="{uid}-title"
	aria-modal="true"
	tabindex="-1"
	style:transform={pulled !== null ? `translateY(${pulled}px)` : undefined}
	onclick={(e) => e.target === dialog && close()}
	oncancel={(e) => {
		e.preventDefault();
		close();
	}}
	onclose={finish}
>
	<div class="inner">
		<!-- Kun en genvej for fingeren: Luk-knappen, Escape og baggrunden gør det samme. -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="head" onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={cancel}>
			<div class="grab"></div>
			<header>
				<div class="grow">
					{#if eyebrow && eyebrowAbove}<p class="ey">{eyebrow}</p>{/if}
					<h2 id="{uid}-title" class="serif">{title}</h2>
					{#if eyebrow && !eyebrowAbove}<p class="ey">{eyebrow}</p>{/if}
				</div>
				{#if aside}
					{@render aside(close)}
				{:else}
					<button type="button" class="rnd" aria-label={labelClose} onclick={close}><Icon name="x" /></button>
				{/if}
			</header>
		</div>
		<div class="body" bind:this={body}>{@render children(close)}</div>
		{#if footer}<footer>{@render footer(close)}</footer>{/if}
	</div>
</dialog>

<style>
	/* Telefon: ark fra bunden af skærmen. Browserens egne dialog-mål nulstilles. */
	.sheet {
		position: fixed;
		inset: auto 0 0 0;
		width: 100%;
		max-width: none;
		max-height: 88dvh;
		margin: 0;
		padding: 0;
		border: none;
		overflow: hidden;
		outline: none;
		color: var(--ink);
		background: var(--card);
		border-radius: var(--r-sheet) var(--r-sheet) 0 0;
		box-shadow: var(--shadow-sheet);
		animation: sheet-up var(--t-sheet) var(--ease);
		transition: transform var(--t-sheet) var(--ease);
	}
	.sheet[open] {
		display: flex;
		flex-direction: column;
	}
	.tall {
		height: 88dvh;
	}
	.sheet::backdrop {
		background: var(--scrim);
		animation: scrim-in var(--t-sheet);
		transition: opacity var(--t-sheet);
	}
	/* Fingeren fører: ingen forsinkelse. */
	.pulling {
		transition: none;
	}
	.out {
		transform: translateY(100%);
	}
	.out::backdrop {
		opacity: 0;
	}
	@keyframes sheet-up {
		from {
			transform: translateY(100%);
		}
	}
	@keyframes sheet-pop {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}
	@keyframes scrim-in {
		from {
			opacity: 0;
		}
	}
	.inner {
		flex: 1 1 auto;
		min-height: 0;
		display: flex;
		flex-direction: column;
		padding-bottom: env(safe-area-inset-bottom);
	}
	/* Kun indholdet giver sig, når arket bliver lavt (fx over tastaturet). */
	.head,
	footer {
		flex: none;
	}
	.head {
		touch-action: none;
	}
	.grab {
		width: 40px;
		height: 5px;
		margin: 8px auto 2px;
		border-radius: 3px;
		background: var(--chipline);
	}
	header {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		padding: 8px max(var(--gutter), env(safe-area-inset-right)) 10px max(var(--gutter), env(safe-area-inset-left));
	}
	h2 {
		font-size: var(--fs-sheet-title);
		line-height: 30px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	.ey {
		margin-block: 2px;
	}
	.body {
		flex: 1 1 auto;
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding-bottom: 12px;
	}
	footer {
		padding: 8px max(var(--gutter), env(safe-area-inset-right)) 12px max(var(--gutter), env(safe-area-inset-left));
	}
	/* Tastaturet fremme: arket fylder pladsen over det, så feltet i bunden og
	   det, der er fundet, kan ses. Uden dette ligger et kort ark gemt bag tastaturet. */
	:global(html.kb-open) .sheet {
		top: calc(env(safe-area-inset-top) + 8px);
		bottom: var(--kb);
		height: auto;
		max-height: none;
	}
	:global(html.kb-open) .inner {
		padding-bottom: 0;
	}
	@media (min-width: 700px) {
		/* iPad og computer: dialog midt på skærmen, uden håndtag. */
		.sheet {
			inset: 8dvh 0 auto 0;
			margin: 0 auto;
			width: min(560px, 92vw);
			max-height: calc(92dvh - var(--kb, 0px));
			border-radius: var(--r-sheet);
			animation-name: sheet-pop;
			transition: opacity var(--t-sheet);
		}
		.tall {
			height: calc(84dvh - var(--kb, 0px));
		}
		.out {
			transform: none;
			opacity: 0;
		}
		.grab {
			display: none;
		}
		.head {
			touch-action: auto;
		}
		header {
			padding-top: 18px;
		}
		.inner {
			padding-bottom: 0;
		}
		:global(html.kb-open) .sheet {
			top: 8dvh;
			bottom: auto;
			max-height: calc(92dvh - var(--kb));
		}
		:global(html.kb-open) .tall {
			height: calc(84dvh - var(--kb));
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.sheet,
		.sheet::backdrop {
			animation: none;
			transition: none;
		}
	}
</style>
