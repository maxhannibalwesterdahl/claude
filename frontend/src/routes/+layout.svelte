<script lang="ts">
	import '../app.css';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import ConfirmDialog from '$lib/ConfirmDialog.svelte';
	import { navState } from '$lib/nav.svelte';
	import { reviewCount } from '$lib/review.svelte';

	let { children } = $props();

	afterNavigate(({ from }) => {
		if (from) navState.inApp = true;
	});

	const tabs = [
		{ href: '/', label: 'Madplan', icon: 'M4 6h16v14H4zM4 10h16M8 3v5M16 3v5' },
		{ href: '/planlaeg', label: 'Planlæg', icon: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4' },
		{ href: '/indkob', label: 'Indkøb', icon: 'M3 4h2l2.4 11h10.2L20 7H6.2M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM17 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z' },
		{ href: '/opskrifter', label: 'Opskrifter', icon: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11' },
		{ href: '/varer', label: 'Varer', icon: 'M4 6h16M4 12h16M4 18h10' }
	];

	function active(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p.startsWith('/dag/');
		if (href === '/varer') return p.startsWith('/varer') || p.startsWith('/tjek');
		if (href === '/opskrifter') return p.startsWith('/opskrift') || p === '/ny' || p === '/importer';
		return p.startsWith(href);
	}

	const showNav = $derived(page.url.pathname !== '/login');

	// Skærmtastaturet lægger sig oven på siden uden at gøre den lavere (iPhone).
	// --kb er højden, det dækker i bunden, så ark kan holde sig fri af det.
	$effect(() => {
		const vv = window.visualViewport;
		if (!vv) return;
		const root = document.documentElement;
		const update = () => {
			const kb = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
			root.style.setProperty('--kb', `${kb}px`);
			root.classList.toggle('kb-open', kb > 100);
		};
		update();
		vv.addEventListener('resize', update);
		vv.addEventListener('scroll', update);
		return () => {
			vv.removeEventListener('resize', update);
			vv.removeEventListener('scroll', update);
		};
	});
</script>

{@render children()}

<ConfirmDialog />

{#if showNav}
	<nav aria-label="Hovedmenu">
		{#each tabs as tab}
			<a href={tab.href} class:active={active(tab.href)} aria-current={active(tab.href) ? 'page' : undefined}>
				<span class="icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d={tab.icon} /></svg></span>
				<span>{tab.label}</span>
				{#if tab.href === '/varer' && reviewCount.value > 0}
					<b class="count">{reviewCount.value}</b>
				{/if}
			</a>
		{/each}
	</nav>
{/if}

<style>
	nav {
		position: fixed;
		inset: auto 0 0 0;
		z-index: 10;
		display: flex;
		justify-content: center;
		background: var(--card);
		border-top: 1px solid var(--line);
		padding-bottom: env(safe-area-inset-bottom);
	}
	a {
		position: relative;
		flex: 0 1 160px;
		height: var(--nav-h);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		font-size: 0.75rem;
		color: var(--muted);
		text-decoration: none;
	}
	a.active {
		color: var(--fg);
		font-weight: 700;
	}
	/* Tydelig markering af den aktive fane: farvet "pille" bag ikonet. */
	.icon {
		display: grid;
		place-items: center;
		width: 56px;
		height: 30px;
		border-radius: var(--radius-pill);
		transition: background 0.15s;
	}
	a.active .icon {
		background: var(--accent-soft);
		color: var(--accent);
	}
	svg {
		width: 24px;
		height: 24px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.count {
		position: absolute;
		top: 4px;
		left: calc(50% + 10px);
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: var(--radius-pill);
		background: var(--warn);
		color: var(--card);
		font-size: 0.7rem;
		line-height: 18px;
		text-align: center;
	}
</style>
