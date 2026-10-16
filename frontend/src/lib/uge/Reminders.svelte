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

	// Standarden, hvis tidspunkterne ikke er ændret. Skal passe til backend/madplan/reminders.py.
	const FIRST = '19:00';
	const AGAIN = '07:00';

	let text = $state('');
	/** Påmindelsen, hvis tidspunkter er foldet ud. */
	let editing = $state<number | null>(null);
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

	/** "19:00" -> "kl. 19", "06:30" -> "kl. 6.30" */
	function clockText(t: string): string {
		const [h, m] = t.split(':');
		return `kl. ${Number(h)}${m === '00' ? '' : '.' + m}`;
	}

	function summary(r: Reminder): string {
		const again = r.again_on ? `${clockText(r.again_time)} på dagen` : 'ingen gentagelse';
		return `${clockText(r.first_time)} aftenen før · ${again}`;
	}

	const custom = (r: Reminder) => r.first_time !== FIRST || r.again_time !== AGAIN || !r.again_on;

	/** Et tomt felt (krydset ud) er standarden. */
	function setTimes(r: Reminder, body: { first_time?: string | null; again_time?: string | null; again_on?: boolean }) {
		run(() => planApi.setReminderTimes(r.id, body));
	}
</script>

<p class="sl">Husk<span>Besked, til den er krydset af</span></p>
{#each meal.reminders as r (r.id)}
	<div class="hk">
		<div class="husk">
			<input id="husk-{r.id}" type="checkbox" class="sr" checked={r.done} onchange={(e) => toggle(r, e.currentTarget.checked)} />
			<label for="husk-{r.id}" class="t" class:done={r.done}>{r.text}</label>
			<button type="button" class="rnd" disabled={busy} aria-label="Slet {r.text}" onclick={() => run(() => planApi.removeReminder(r.id))}>
				<Icon name="x" size={16} />
			</button>
			<label for="husk-{r.id}" class="end"><Tick checked={r.done} /></label>
		</div>

		{#if !r.done && !past}
			<button
				type="button"
				class="when"
				aria-expanded={editing === r.id}
				aria-label="Tidspunkter for {r.text}: {summary(r)}"
				onclick={() => (editing = editing === r.id ? null : r.id)}
			>
				<span class:own={custom(r)}>{summary(r)}</span>
				<Icon name={editing === r.id ? 'up' : 'down'} size={14} stroke={2.2} />
			</button>
			{#if editing === r.id}
				<div class="times">
					<label class="field">
						<span>Aftenen før</span>
						<input
							type="time"
							value={r.first_time}
							disabled={busy}
							onchange={(e) => setTimes(r, { first_time: e.currentTarget.value || null })}
						/>
					</label>
					<label class="field" class:off={!r.again_on}>
						<span>På dagen</span>
						<input
							type="time"
							value={r.again_time}
							disabled={busy || !r.again_on}
							onchange={(e) => setTimes(r, { again_time: e.currentTarget.value || null })}
						/>
					</label>
					<label class="rep">
						<input type="checkbox" checked={r.again_on} disabled={busy} onchange={(e) => setTimes(r, { again_on: e.currentTarget.checked })} />
						<span>Gentag på dagen, hvis den ikke er krydset af</span>
					</label>
					{#if custom(r)}
						<button
							type="button"
							class="link reset"
							disabled={busy}
							onclick={() => setTimes(r, { first_time: null, again_time: null, again_on: true })}>Brug standard</button
						>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
{/each}

{#if !past}
	<form class="write pad" onsubmit={add}>
		<input bind:value={text} placeholder="Fx kød op af fryseren" maxlength="200" aria-label="Husk" enterkeyhint="done" />
		<button class="btn" disabled={busy || !text.trim()}>Tilføj</button>
	</form>
	{#if meal.reminders.length === 0}
		<p class="small muted pad hint">Besked kl. 19 aftenen før og igen kl. 7 på dagen. Tiderne kan ændres under hver påmindelse.</p>
	{/if}
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
	.hk {
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	.husk {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: var(--ing-h);
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
	/* Tidspunkterne under påmindelsen. Tomatfarvet, når de er ændret. */
	.when {
		display: flex;
		align-items: center;
		gap: 6px;
		min-height: var(--tap);
		margin-top: -8px;
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	.own {
		color: var(--tomat);
	}
	.times {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
		padding-block: 2px 12px;
	}
	.off {
		opacity: 0.5;
	}
	.rep {
		grid-column: 1 / -1;
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: var(--tap);
		font-size: 15px;
		cursor: pointer;
	}
	.rep input {
		flex: none;
		width: 22px;
		height: 22px;
		min-height: 0;
	}
	.reset {
		grid-column: 1 / -1;
		justify-self: start;
		min-height: var(--tap);
	}
	.hint {
		padding-bottom: 6px;
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
