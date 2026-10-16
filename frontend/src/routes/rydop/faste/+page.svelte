<script lang="ts">
	import { untrack } from 'svelte';
	import { api } from '$lib/api';
	import IngredientPicker from '$lib/IngredientPicker.svelte';
	import { shopping } from '$lib/shopping.svelte';
	import type { Department, IngredientRef, Staple } from '$lib/types';
	import { say } from '$lib/ui/copy';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';

	let staples = $state<Staple[] | null>(null);
	let departments = $state<Department[]>([]);
	let text = $state('');
	let busy = $state(false);
	let error = $state('');
	/** Fast vare, hvis tekst appen ikke kunne koble til en vare. */
	let picking = $state<Staple | null>(null);

	const deptName = (code: string) => departments.find((d) => d.code === code)?.name ?? code;

	$effect(() => {
		untrack(() => {
			api<Staple[]>('/staples')
				.then((s) => (staples = s))
				.catch((e) => (error = say(e)));
			api<Department[]>('/settings/departments')
				.then((d) => (departments = d))
				.catch(() => {});
		});
	});

	async function add(e: SubmitEvent) {
		e.preventDefault();
		const value = text.trim();
		if (!value || busy) return;
		busy = true;
		error = '';
		try {
			const s = await api<Staple>('/staples', { method: 'POST', body: { text: value } });
			text = '';
			staples = [...(staples ?? []), s];
			if (s.ingredient_id === null) picking = s;
			shopping.sync();
		} catch (err) {
			error = say(err);
		} finally {
			busy = false;
		}
	}

	async function choose(s: Staple, ing: IngredientRef | null) {
		picking = null;
		error = '';
		try {
			const u = await api<Staple>(`/staples/${s.id}`, { method: 'PATCH', body: { ingredient_id: ing?.id ?? null } });
			staples = (staples ?? []).map((x) => (x.id === u.id ? u : x));
			shopping.sync();
		} catch (err) {
			error = say(err);
		}
	}

	async function remove(s: Staple) {
		error = '';
		try {
			await api(`/staples/${s.id}`, { method: 'DELETE' });
			staples = (staples ?? []).filter((x) => x.id !== s.id);
			shopping.sync();
		} catch (err) {
			error = say(err);
		}
	}
</script>

<main>
	<ScreenHeader title="Faste varer" eyebrow="Ryd op" back="/rydop" />
	<p class="pad muted intro">Varer, I køber hver uge. Skal ugens retter bruge den samme vare, tæller den største mængde, ikke begge.</p>

	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	{#if staples?.length}
		<ul class="list">
			{#each staples as s (s.id)}
				<li>
					<span class="grow">
						<span class="what">{s.text}</span>
						{#if s.ingredient_id === null}<span class="cap">Appen kender ikke varen</span>{/if}
					</span>
					<span class="tag">{deptName(s.department)}</span>
					{#if s.ingredient_id === null}
						<button type="button" class="btn sm quiet" aria-label="Vælg vare til {s.text}" onclick={() => (picking = s)}>Vælg vare</button>
					{/if}
					<button type="button" class="btn sm quiet" aria-label="Fjern {s.text}" onclick={() => remove(s)}>Fjern</button>
				</li>
			{/each}
		</ul>
	{:else if staples}
		<p class="pad muted">Ingen faste varer endnu.</p>
	{/if}

	<form class="add" onsubmit={add}>
		<input
			bind:value={text}
			placeholder="Fx 2 l mælk"
			aria-label="Ny fast vare"
			maxlength="200"
			enterkeyhint="done"
			autocomplete="off"
			autocapitalize="off"
		/>
		<button type="submit" class="btn primary" disabled={busy || !text.trim()}>Tilføj</button>
	</form>
</main>

{#if picking}
	{@const s = picking}
	<Sheet title="Hvilken vare er det?" eyebrow={s.text} size="tall" initialFocus="first" onclose={() => (picking = null)}>
		{#snippet children(close)}
			<IngredientPicker initial={s.item} onpick={(ing) => choose(s, ing)} oncancel={close} />
		{/snippet}
	</Sheet>
{/if}

<style>
	.intro {
		font-size: 15px;
	}
	.list {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
	}
	.list li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: var(--row-h);
		margin-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
	}
	.what {
		display: block;
		font-size: var(--fs-row);
		font-weight: 500;
	}
	.cap {
		display: block;
		font-size: var(--fs-cap);
		color: var(--muted);
	}
	.add {
		display: flex;
		gap: 10px;
		margin: 20px var(--gutter) 0;
	}
	.add input {
		flex: 1;
		min-width: 0;
	}
</style>
