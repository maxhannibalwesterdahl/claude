<script lang="ts">
	import { untrack } from 'svelte';
	import { api, ApiError } from './api';
	import { formatNumber, formatQuantity, parseNumber } from './format';
	import IngredientPicker from './IngredientPicker.svelte';
	import type { IngredientRef, Line, Recipe } from './types';

	interface Props {
		recipe: Recipe | null;
		onsave: (recipe: Recipe) => void;
	}
	let { recipe, onsave }: Props = $props();

	type EditLine = Line & { uid: number; showFields: boolean };
	type Parsed = Omit<Line, 'id' | 'group' | 'is_main'>;

	let uid = 0;
	const toEdit = (l: Line): EditLine => ({ ...l, uid: ++uid, showFields: false });

	// Kopi af opskriften, som først gemmes ved "Gem".
	const start = untrack(() => recipe);
	let title = $state(start?.title ?? '');
	let servings = $state(start?.servings ? String(start.servings) : '');
	let sourceUrl = $state(start?.source_url ?? '');
	let childNote = $state(start?.child_note ?? '');
	let steps = $state(start?.instructions.join('\n') ?? '');
	let lines = $state<EditLine[]>(start?.ingredients.map(toEdit) ?? []);
	let bulk = $state('');
	let picking = $state<number | null>(null);
	let error = $state('');
	let busy = $state(false);

	async function parse(raws: string[]): Promise<Parsed[]> {
		return api<Parsed[]>('/parse', { method: 'POST', body: { lines: raws } });
	}

	/** Tekst fra feltet "Tilføj": én linje pr. ingrediens, "Afsnit:" starter et afsnit. */
	async function addBulk() {
		const raw = bulk.split('\n').map((s) => s.trim()).filter(Boolean);
		if (!raw.length) return;
		let group = lines.at(-1)?.group ?? '';
		const entries: { raw: string; group: string }[] = [];
		for (const r of raw) {
			if (r.endsWith(':') && r.length < 60) group = r.slice(0, -1).trim();
			else entries.push({ raw: r.replace(/^[-•*]\s*/, ''), group });
		}
		try {
			const parsed = await parse(entries.map((e) => e.raw));
			lines.push(
				...parsed.map((p, i) => toEdit({ ...p, id: null, group: entries[i].group, is_main: false }))
			);
			bulk = '';
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke læse linjerne';
		}
	}

	async function reparse(line: EditLine) {
		if (!line.raw.trim()) return;
		try {
			const [p] = await parse([line.raw]);
			Object.assign(line, p);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Kunne ikke læse linjen';
		}
	}

	function pick(line: EditLine, ing: IngredientRef | null) {
		line.ingredient = ing;
		line.match_status = 'bekræftet';
		picking = null;
	}

	function remove(line: EditLine) {
		lines = lines.filter((l) => l.uid !== line.uid);
	}

	function move(line: EditLine, delta: number) {
		const i = lines.findIndex((l) => l.uid === line.uid);
		const j = i + delta;
		if (j < 0 || j >= lines.length) return;
		// Linjen overtager afsnittet på sin nye plads.
		const group = lines[j].group;
		[lines[i], lines[j]] = [lines[j], lines[i]];
		lines[j].group = group;
	}

	function renameGroup(oldName: string, newName: string) {
		for (const l of lines) if (l.group === oldName) l.group = newName.trim();
	}

	function setNumber(line: EditLine, field: 'quantity' | 'quantity_max', text: string) {
		line[field] = parseNumber(text);
	}

	const groups = $derived.by(() => {
		const out: { name: string; lines: EditLine[] }[] = [];
		for (const l of lines) {
			const last = out.at(-1);
			if (last && last.name === l.group) last.lines.push(l);
			else out.push({ name: l.group, lines: [l] });
		}
		return out;
	});
	const hasGroups = $derived(lines.some((l) => l.group));

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (bulk.trim()) await addBulk();
		busy = true;
		const body = {
			title: title.trim(),
			servings: servings.trim() ? Number(servings) : null,
			source_url: sourceUrl.trim() || null,
			child_note: childNote,
			instructions: steps.split('\n').map((s) => s.trim()).filter(Boolean),
			ingredients: lines.map((l) => ({
				id: l.id,
				raw: l.raw,
				group: l.group,
				quantity: l.quantity,
				quantity_max: l.quantity_max,
				unit: l.unit || null,
				item: l.item || l.raw,
				note: l.note,
				ingredient_id: l.ingredient?.id ?? null,
				match_status: l.match_status,
				is_main: l.is_main
			}))
		};
		try {
			const saved = recipe
				? await api<Recipe>(`/recipes/${recipe.id}`, { method: 'PUT', body })
				: await api<Recipe>('/recipes', { method: 'POST', body });
			onsave(saved);
		} catch (err) {
			error = err instanceof ApiError ? err.message : 'Kunne ikke gemme';
		} finally {
			busy = false;
		}
	}

	function scrollIntoView(node: HTMLElement) {
		node.scrollIntoView({ block: 'start', behavior: 'smooth' });
	}

	async function suggestMain() {
		if (!recipe) return;
		// Forslaget laves af serveren ud fra de gemte linjer.
		const r = await api<Recipe>(`/recipes/${recipe.id}/suggest-main`, { method: 'POST' });
		const main = new Set(r.ingredients.filter((l) => l.is_main).map((l) => l.id));
		for (const l of lines) l.is_main = l.id !== null && main.has(l.id);
	}
</script>

<form onsubmit={save}>
	<label class="field">
		<span>Titel</span>
		<input bind:value={title} required maxlength="200" />
	</label>

	<div class="two">
		<label class="field">
			<span>Portioner</span>
			<input bind:value={servings} inputmode="numeric" pattern="[0-9]*" placeholder="4" />
		</label>
		<label class="field">
			<span>Link</span>
			<input bind:value={sourceUrl} type="url" placeholder="https://…" />
		</label>
	</div>

	<label class="field">
		<span>Note om barnet</span>
		<input bind:value={childNote} placeholder="Fx: tag barnets portion fra før chili" />
	</label>

	<h2>Ingredienser</h2>
	<p class="muted small">
		★ = hovedingrediens (bruges til tilbudsforslag). Tryk på varen for at rette, hvad der skal købes.
		{#if recipe}<button type="button" class="plain small" onclick={suggestMain}>Foreslå ★ igen</button>{/if}
	</p>

	{#each groups as g}
		{#if hasGroups}
			<input
				class="group"
				value={g.name}
				placeholder="Uden afsnit"
				aria-label="Afsnit"
				onchange={(e) => renameGroup(g.name, e.currentTarget.value)}
			/>
		{/if}
		{#each g.lines as line (line.uid)}
			<div class="line" class:review={line.match_status === 'usikker' || line.match_status === 'ingen'}>
				<div class="row nowrap">
					<button
						type="button"
						class="plain star"
						class:on={line.is_main}
						aria-pressed={line.is_main}
						aria-label="Hovedingrediens"
						onclick={() => (line.is_main = !line.is_main)}>★</button
					>
					<input class="grow" bind:value={line.raw} onchange={() => reparse(line)} aria-label="Ingredienslinje" />
					<button type="button" class="plain" aria-label="Flyt op" onclick={() => move(line, -1)}>↑</button>
					<button type="button" class="plain" aria-label="Fjern" onclick={() => remove(line)}>✕</button>
				</div>
				<div class="parsed small">
					<button type="button" class="plain qty" onclick={() => (line.showFields = !line.showFields)}>
						{formatQuantity(line.quantity, line.quantity_max, line.unit) || '–'}
					</button>
					<span>→</span>
					<button type="button" class="plain pick" onclick={() => (picking = picking === line.uid ? null : line.uid)}>
						{#if line.ingredient}
							{line.ingredient.name}
						{:else if line.match_status === 'bekræftet'}
							<span class="muted">ingen vare</span>
						{:else}
							<span class="badge">vælg vare</span>
						{/if}
					</button>
					{#if line.match_status === 'usikker'}
						<span class="badge">usikker</span>
						<button type="button" class="plain ok" onclick={() => pick(line, line.ingredient)}>✓ rigtig</button>
					{:else if line.ingredient?.pantry}
						<span class="muted">basisvare</span>
					{/if}
				</div>
				{#if line.showFields}
					<div class="fields">
						<label class="field"><span>Mængde</span>
							<input value={line.quantity === null ? '' : formatNumber(line.quantity)} inputmode="decimal"
								onchange={(e) => setNumber(line, 'quantity', e.currentTarget.value)} /></label>
						<label class="field"><span>Til</span>
							<input value={line.quantity_max === null ? '' : formatNumber(line.quantity_max)} inputmode="decimal"
								onchange={(e) => setNumber(line, 'quantity_max', e.currentTarget.value)} /></label>
						<label class="field"><span>Enhed</span>
							<input bind:value={line.unit} placeholder="stk" /></label>
						<label class="field wide"><span>Vare i opskriften</span>
							<input bind:value={line.item} /></label>
						<label class="field wide"><span>Note</span>
							<input bind:value={line.note} /></label>
					</div>
				{/if}
				{#if picking === line.uid}
					<div use:scrollIntoView></div>
					<IngredientPicker
						initial={line.item}
						onpick={(ing) => pick(line, ing)}
						oncancel={() => (picking = null)}
					/>
				{/if}
			</div>
		{/each}
	{/each}

	<label class="field add">
		<span>Tilføj ingredienser</span>
		<textarea bind:value={bulk} rows={lines.length ? 3 : 8}
			placeholder={'Én pr. linje, fx\n500 g hakket oksekød\n2 løg\n\nSkriv "Sovs:" på en linje for at starte et afsnit.'}></textarea>
	</label>
	{#if bulk.trim()}<button type="button" onclick={addBulk}>Læs linjerne</button>{/if}

	<h2>Fremgangsmåde</h2>
	<label class="field">
		<span class="muted">Ét trin pr. linje</span>
		<textarea bind:value={steps} rows="8"></textarea>
	</label>

	{#if error}<p class="error" role="alert">{error}</p>{/if}

	<div class="save">
		<button class="primary" disabled={busy || !title.trim()}>{busy ? 'Gemmer…' : 'Gem'}</button>
	</div>
</form>

<style>
	form {
		display: grid;
		gap: 12px;
	}
	.two {
		display: grid;
		grid-template-columns: 6.5rem minmax(0, 1fr);
		gap: 10px;
	}
	h2 {
		margin-bottom: 0;
	}
	.group {
		font-weight: 700;
		border-style: dashed;
		margin-top: 8px;
	}
	.line {
		border-bottom: 1px solid var(--line);
		padding-bottom: 8px;
	}
	.line.review {
		border-left: 3px solid var(--warn);
		padding-left: 6px;
	}
	.nowrap {
		flex-wrap: nowrap;
	}
	.star {
		font-size: 1.4rem;
		color: var(--line);
		width: 36px;
	}
	.star.on {
		color: var(--star);
	}
	.parsed {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		padding-left: 44px;
		margin-top: 2px;
	}
	.parsed .qty {
		color: var(--muted);
		text-decoration: underline dotted;
	}
	.parsed .pick {
		font-weight: 600;
		color: var(--accent);
	}
	.parsed .ok {
		color: var(--accent);
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
		padding: 8px 0 0 44px;
	}
	@media (max-width: 380px) {
		/* Smalle telefoner: brug hele bredden til felterne. */
		.parsed,
		.fields {
			padding-left: 0;
		}
	}
	.fields .wide {
		grid-column: 1 / -1;
	}
	.add {
		margin-top: 8px;
	}
	/* Fast bjælke over menuen, så Gem altid kan nås uden at dække felterne. */
	.save {
		position: sticky;
		bottom: calc(var(--nav-h) + env(safe-area-inset-bottom));
		display: flex;
		justify-content: flex-end;
		background: var(--bg);
		border-top: 1px solid var(--line);
		padding: 8px 0;
		margin-top: 8px;
	}
	.save button {
		min-width: 140px;
		justify-content: center;
	}
</style>
