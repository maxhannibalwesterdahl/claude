<script lang="ts">
	import { planApi } from '$lib/planApi';
	import { beskeder, enable } from '$lib/push.svelte';
	import { clock } from '$lib/resume.svelte';
	import type { Meal, Plan, Reminder } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import Icon from '$lib/ui/Icon.svelte';
	import Tick from '$lib/ui/Tick.svelte';
	import type { Week } from './week.svelte';

	interface Props {
		week: Week;
		meal: Meal;
		busy: boolean;
		run: (fn: () => Promise<Plan>) => Promise<boolean>;
	}
	let { week, meal, busy, run }: Props = $props();

	let text = $state('');
	const past = $derived(meal.date < clock.today);
	const open = $derived(meal.reminders.some((r) => !r.done));

	async function add(e: SubmitEvent) {
		e.preventDefault();
		const t = text.trim();
		if (!t) return;
		const id = meal.id;
		if (await run(() => planApi.addReminder(id, t))) text = '';
	}

	/** Fluebenet vises med det samme og rulles tilbage, hvis serveren afviser det. */
	async function toggle(r: Reminder, done: boolean) {
		const before = r.done;
		r.done = done;
		week.error = '';
		try {
			await week.mutate(() => planApi.setReminder(r.id, done));
		} catch (e) {
			r.done = before;
			week.error = say(e);
		}
	}
</script>

<p class="sl">Husk<span>Besked kl. 19 dagen før</span></p>
{#each meal.reminders as r (r.id)}
	<div class="husk">
		<input id="husk-{r.id}" type="checkbox" class="sr" checked={r.done} onchange={(e) => toggle(r, e.currentTarget.checked)} />
		<label for="husk-{r.id}" class="t" class:done={r.done}>{r.text}</label>
		<button type="button" class="rnd" disabled={busy} aria-label="Slet {r.text}" onclick={() => run(() => planApi.removeReminder(r.id))}>
			<Icon name="x" size={16} />
		</button>
		<label for="husk-{r.id}" class="end"><Tick checked={r.done} /></label>
	</div>
{/each}

{#if !past}
	<form class="write pad" onsubmit={add}>
		<input bind:value={text} placeholder="Fx kød op af fryseren" maxlength="200" aria-label="Husk" enterkeyhint="done" />
		<button class="btn" disabled={busy || !text.trim()}>Tilføj</button>
	</form>
{/if}

{#if open && !past}
	{#if beskeder.state === 'spoerg'}
		<div class="kv">
			<p class="k">Beskeder<small>Ikke slået til på denne telefon</small></p>
			<button type="button" class="v" disabled={beskeder.busy} onclick={enable}>Slå til</button>
		</div>
	{:else if beskeder.state === 'hjemmeskaerm'}
		<p class="note">Læg appen på hjemmeskærmen for at få beskeder: Del, og så Føj til hjemmeskærm.</p>
	{:else if beskeder.state === 'afvist'}
		<p class="note">Beskeder er slået fra for appen. Slå dem til i telefonens indstillinger.</p>
	{:else if beskeder.state === 'ingen'}
		<p class="note">Denne browser kan ikke vise beskeder.</p>
	{/if}
	{#if beskeder.error}<p class="msg" role="alert">{beskeder.error}</p>{/if}
{/if}

<style>
	.husk {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: var(--ing-h);
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	.t {
		flex: 1;
		min-width: 0;
		align-self: stretch;
		display: flex;
		align-items: center;
		padding-block: 6px;
		font-size: 16.5px;
		cursor: pointer;
		transition: color var(--t-tick);
	}
	/* Klaret: dæmpet, som de andre afkrydsninger. */
	.done {
		color: var(--muted);
	}
	.end {
		flex: none;
		display: flex;
		align-items: center;
		align-self: stretch;
		cursor: pointer;
	}
	.husk:has(input:focus-visible) {
		outline: 2px solid var(--ink);
		outline-offset: 2px;
		border-radius: 4px;
	}
	.write {
		display: flex;
		gap: 8px;
		padding-block: 10px 6px;
	}
	.write input {
		flex: 1;
	}
	.write .btn {
		flex: none;
		height: 48px;
	}
</style>
