<script lang="ts" module>
	import type { IngredientRef, ReviewLine } from '$lib/types';

	/** Én vare, appen er i tvivl om, med alle de linjer, den står i. */
	export interface ReviewItem {
		key: string;
		item: string;
		suggestion: IngredientRef | null;
		lines: ReviewLine[];
	}
</script>

<script lang="ts">
	import Icon from '$lib/ui/Icon.svelte';

	interface Props {
		item: ReviewItem;
		/** Kortets eget valg er ved at blive gemt. */
		busy: boolean;
		/** Et valg (her eller på et andet kort) er ved at blive gemt: ingen knapper virker. */
		locked: boolean;
		/** Appens forslag er rigtigt. */
		onaccept: () => void;
		/** Åbn vælgeren med alle varer. */
		onchoose: () => void;
		/** Ingen vare: linjerne kommer ikke på indkøbslisten. */
		onignore: () => void;
	}
	let { item, busy, locked, onaccept, onchoose, onignore }: Props = $props();

	const uid = $props.id();
	let all = $state(false);
	const first = $derived(item.lines[0]);
</script>

<li class="card" aria-busy={busy} class:busy>
	<h2>{item.item}</h2>
	<p class="uses">
		{item.lines.length === 1 ? '1 opskrift' : `${item.lines.length} opskrifter`}
		{#if !all}
			· <a href="/opskrift/{first.recipe_id}">{first.recipe_title}</a>: "{first.raw}"
		{/if}
		{#if item.lines.length > 1}
			<button type="button" class="link more" aria-expanded={all} aria-controls="{uid}-uses" onclick={() => (all = !all)}>
				{all ? 'vis færre' : 'vis alle'}
			</button>
		{/if}
	</p>
	{#if all}
		<ul id="{uid}-uses">
			{#each item.lines as l (l.id)}
				<li><a href="/opskrift/{l.recipe_id}">{l.recipe_title}</a>: "{l.raw}"</li>
			{/each}
		</ul>
	{/if}
	<div class="choices">
		{#if item.suggestion}
			<button type="button" class="btn sm primary" disabled={locked} onclick={onaccept}>
				<Icon name="check" size={16} stroke={3} />{item.suggestion.name}
			</button>
		{/if}
		<button type="button" class="btn sm" disabled={locked} onclick={onchoose}>{item.suggestion ? 'Anden vare' : 'Vælg vare'}</button>
		<button type="button" class="btn sm" disabled={locked} aria-label="Ingen vare til {item.item}" onclick={onignore}>Ingen</button>
	</div>
</li>

<style>
	.card {
		margin: 0 var(--gutter) 12px;
		padding: 14px;
		list-style: none;
	}
	.busy {
		opacity: 0.5;
	}
	h2 {
		font-size: 17px;
		font-weight: 700;
	}
	.uses,
	ul {
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	.uses {
		margin-top: 2px;
	}
	/* Større trykflade på links til opskrifterne, uden at linjerne rykker sig. */
	.uses a {
		padding-block: 14px;
	}
	.more {
		position: relative;
		margin-left: 4px;
	}
	.more::after {
		content: '';
		position: absolute;
		inset: -14px -6px;
	}
	ul {
		list-style: none;
		margin: 4px 0 0;
		padding: 0;
	}
	ul li {
		padding-block: 5px;
	}
	ul a {
		display: inline-block;
		padding-block: 7px;
	}
	.choices {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
	}
	/* Et langt varenavn må ikke skubbe knapperne ud over kortet. */
	.choices .btn {
		max-width: 100%;
		overflow: hidden;
	}
</style>
