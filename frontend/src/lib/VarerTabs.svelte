<script lang="ts">
	import { reviewCount } from './review.svelte';

	/** Fanerne øverst på Varer: alle varer, basisvarer og tjek af usikre varer. */
	let { active, pantryCount = null }: { active: 'alle' | 'basis' | 'tjek'; pantryCount?: number | null } = $props();
</script>

<nav class="tabs segmented" aria-label="Varer">
	<a href="/varer" aria-current={active === 'alle' ? 'page' : undefined}>Alle</a>
	<a href="/varer?fane=basis" aria-current={active === 'basis' ? 'page' : undefined}>
		Basis{#if pantryCount !== null}&nbsp;({pantryCount}){/if}
	</a>
	<a href="/tjek" aria-current={active === 'tjek' ? 'page' : undefined}>
		Tjek{#if reviewCount.value}&nbsp;<b class="count">{reviewCount.value}</b>{/if}
	</a>
</nav>

<style>
	.tabs {
		margin-bottom: 12px;
	}
	a {
		flex: 1 0 auto;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 9px;
		min-height: 38px;
		padding: 6px 12px;
		font-weight: 600;
		color: var(--muted);
		text-decoration: none;
	}
	a[aria-current='page'] {
		background: var(--accent);
		color: var(--accent-fg);
	}
	.count {
		min-width: 20px;
		height: 20px;
		padding: 0 6px;
		border-radius: 10px;
		background: var(--warn);
		color: var(--card);
		font-size: 0.75rem;
		line-height: 20px;
		text-align: center;
	}
</style>
