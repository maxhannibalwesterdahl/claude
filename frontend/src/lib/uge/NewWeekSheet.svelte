<script lang="ts">
	import { isoDate, nextWeekday, shortDate, weekdayName } from '$lib/dates';
	import type { Plan } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import Sheet from '$lib/ui/Sheet.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		/** Den nye uge er lavet og vises. */
		oncreated: (plan: Plan) => void;
		onclose: () => void;
	}
	let { week, oncreated, onclose }: Props = $props();

	// Forslag: dagen efter den nyeste uge, ellers i dag.
	// svelte-ignore state_referenced_locally
	let startDate = $state(week.suggestedStart());
	let busy = $state(false);
	let error = $state('');

	// Genveje til de to mest brugte indkøbsdage.
	const shortcuts = [isoDate(nextWeekday(new Date(), 0)), isoDate(nextWeekday(new Date(), 1))];

	async function create(e: SubmitEvent, close: () => void) {
		e.preventDefault();
		busy = true;
		error = '';
		try {
			oncreated(await week.create(startDate));
			close();
		} catch (err) {
			// Overlapper ugen en anden, står serverens sætning her.
			error = say(err);
		} finally {
			busy = false;
		}
	}
</script>

<Sheet title="Ny uge" {onclose}>
	{#snippet children(close)}
		<form class="pad" onsubmit={(e) => create(e, close)}>
			<p class="muted">Ugen starter på indkøbsdagen og varer syv dage.</p>
			<label class="field">
				<span>Indkøbsdag</span>
				<input type="date" bind:value={startDate} required />
			</label>
			<div class="chips">
				{#each shortcuts as d}
					<button type="button" class="chip" aria-pressed={startDate === d} onclick={() => (startDate = d)}>
						{weekdayName(d)} {shortDate(d)}
					</button>
				{/each}
			</div>
			{#if error}<p class="msg" role="alert">{error}</p>{/if}
			<button class="btn primary block" disabled={busy}>Lav ugen</button>
		</form>
	{/snippet}
</Sheet>

<style>
	form {
		display: grid;
		gap: 14px;
		padding-bottom: 8px;
	}
	.msg {
		margin: 0;
	}
</style>
