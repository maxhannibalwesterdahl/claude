<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { reviewCount } from '$lib/review.svelte';

	let { children } = $props();

	const tabs = [
		{ href: '/', label: 'Opskrifter', icon: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11' },
		{ href: '/tjek', label: 'Tjek', icon: 'M5 12l4 4 10-10' },
		{ href: '/varer', label: 'Varer', icon: 'M4 6h16M4 12h16M4 18h10' }
	];

	function active(href: string): boolean {
		const p = page.url.pathname;
		return href === '/' ? p === '/' || p.startsWith('/opskrift') || p === '/ny' || p === '/importer' : p.startsWith(href);
	}

	const showNav = $derived(page.url.pathname !== '/login');
</script>

{@render children()}

{#if showNav}
	<nav aria-label="Hovedmenu">
		{#each tabs as tab}
			<a href={tab.href} class:active={active(tab.href)} aria-current={active(tab.href) ? 'page' : undefined}>
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d={tab.icon} /></svg>
				<span>{tab.label}</span>
				{#if tab.href === '/tjek' && reviewCount.value > 0}
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
		color: var(--accent);
		font-weight: 600;
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
		top: 8px;
		left: calc(50% + 8px);
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: 9px;
		background: var(--warn);
		color: var(--card);
		font-size: 0.7rem;
		line-height: 18px;
		text-align: center;
	}
</style>
