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
	.count {
		min-width: 20px;
		height: 20px;
		padding: 0 6px;
		border-radius: var(--radius-pill);
		background: var(--warn);
		color: var(--card);
		font-size: 0.75rem;
		line-height: 20px;
		text-align: center;
	}
</style>
