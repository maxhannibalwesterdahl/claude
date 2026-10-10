<script lang="ts">
	import '../app.css';
	import { untrack } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import ConfirmDialog from '$lib/ConfirmDialog.svelte';
	import { navState } from '$lib/nav.svelte';
	import { onResume } from '$lib/resume.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import type { IconName } from '$lib/ui/icons';

	let { children } = $props();

	afterNavigate(({ from }) => {
		if (from) navState.inApp = true;
	});

	const tabs: { href: string; label: string; icon: IconName }[] = [
		{ href: '/', label: 'Uge', icon: 'cal' },
		{ href: '/indkob', label: 'Indkøb', icon: 'cart' },
		{ href: '/opskrifter', label: 'Opskrifter', icon: 'book' }
	];

	function active(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/' || p.startsWith('/lav/') || p.startsWith('/planlaeg') || p.startsWith('/dag/');
		if (href === '/indkob') return p.startsWith('/indkob');
		return (
			p.startsWith('/opskrift') || p === '/ny' || p === '/importer' || p.startsWith('/rydop') || p.startsWith('/varer') || p.startsWith('/tjek')
		);
	}

	const onLogin = $derived(page.url.pathname === '/login');
	// Ingen fanelinje på login og mens der laves mad.
	const showNav = $derived(!onLogin && !page.url.pathname.startsWith('/lav/'));

	// Tallet på Indkøb-fanen: rækker, der ikke er købt endnu. Listen ligger gemt
	// på telefonen, så tallet også vises uden net.
	const left = $derived(shopping.data?.items.filter((i) => !shopping.checked(i.key, i.checked)).length ?? 0);

	// Hent listen én gang ved start og når appen åbnes igen, så tallet følger med,
	// når planen er ændret på en anden telefon. Ikke på login: der er ingen session.
	$effect(() => {
		if (onLogin) return;
		untrack(() => void shopping.sync());
		return onResume(() => void shopping.sync());
	});

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
			{@const on = active(tab.href)}
			{@const badge = tab.href === '/indkob' && !on && left > 0}
			<a
				href={tab.href}
				class:on
				aria-current={on ? 'page' : undefined}
				aria-label={badge ? `Indkøb, ${left} ${left === 1 ? 'vare' : 'varer'} mangler` : undefined}
			>
				<Icon name={tab.icon} size={24} stroke={1.8} />
				<span>{tab.label}</span>
				{#if badge}<b class="count">{left}</b>{/if}
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
		height: calc(var(--nav-h) + env(safe-area-inset-bottom));
		padding-bottom: env(safe-area-inset-bottom);
		background: var(--paper);
		border-top: 1px solid var(--line);
	}
	a {
		position: relative;
		flex: 0 1 140px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 3px;
		font-size: 12px;
		font-weight: 600;
		color: var(--muted);
		text-decoration: none;
	}
	/* Den aktive fane er tomatfarvet. Skærmlæsere får aria-current. */
	a.on {
		color: var(--tomat);
	}
	a:focus-visible {
		outline-offset: -4px;
	}
	.count {
		position: absolute;
		top: 3px;
		left: calc(50% + 6px);
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: var(--r-pill);
		background: var(--ink);
		color: var(--paper);
		font-size: 11px;
		font-weight: 600;
		line-height: 18px;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}
</style>
