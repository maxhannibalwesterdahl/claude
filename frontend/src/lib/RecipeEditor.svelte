<script lang="ts">
	import { beforeNavigate, goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { api } from './api';
	import { confirmDialog } from './confirm.svelte';
	import { formatNumber, formatQuantity, parseNumber } from './format';
	import IngredientPicker from './IngredientPicker.svelte';
	import { shrinkImage, uploadRecipeImage } from './image';
	import { say } from './ui/copy';
	import Icon from './ui/Icon.svelte';
	import Plate from './ui/Plate.svelte';
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
	// Billede: vises med det samme, gemmes først ved "Gem".
	let imageUrl = $state<string | null>(start?.image_url ?? null);
	let newImage = $state<Blob | null>(null);
	let removeImage = $state(false);
	let imageBusy = $state(false);
	let picking = $state<number | null>(null);
	let error = $state('');
	let busy = $state(false);

	async function parse(raws: string[]): Promise<Parsed[]> {
		return api<Parsed[]>('/parse', { method: 'POST', body: { lines: raws } });
	}

	/** Tekst fra feltet "Tilføj": én linje pr. ingrediens, "Afsnit:" starter et afsnit. */
	/** Returnerer false, hvis linjerne ikke kunne læses (så "Gem" stopper). */
	async function addBulk(): Promise<boolean> {
		const raw = bulk.split('\n').map((s) => s.trim()).filter(Boolean);
		if (!raw.length) return true;
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
			return true;
		} catch (e) {
			error = say(e);
			return false;
		}
	}

	async function reparse(line: EditLine) {
		if (!line.raw.trim()) return;
		try {
			const [p] = await parse([line.raw]);
			Object.assign(line, p);
		} catch (e) {
			error = say(e);
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

	function currentBody() {
		return {
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
	}

	// Advar, hvis man forlader siden med ændringer, der ikke er gemt (fx trykker
	// på en fane i menuen midt i redigeringen).
	const startBody = untrack(() => JSON.stringify(currentBody()));
	let leaving = false;
	const dirty = () =>
		!leaving && (bulk.trim() !== '' || newImage !== null || removeImage || JSON.stringify(currentBody()) !== startBody);

	async function pickImage(e: Event & { currentTarget: HTMLInputElement }) {
		const file = e.currentTarget.files?.[0];
		e.currentTarget.value = '';
		if (!file) return;
		imageBusy = true;
		newImage = await shrinkImage(file);
		imageBusy = false;
		if (imageUrl?.startsWith('blob:')) URL.revokeObjectURL(imageUrl);
		imageUrl = URL.createObjectURL(newImage);
		removeImage = false;
	}

	function clearImage() {
		if (imageUrl?.startsWith('blob:')) URL.revokeObjectURL(imageUrl);
		imageUrl = null;
		newImage = null;
		removeImage = !!start?.image_url;
	}
	// Navigationen stoppes, mens der spørges, og gentages, hvis svaret er ja.
	// (Lukkes fanen, spørger browseren selv: se beforeunload nedenfor.)
	beforeNavigate((nav) => {
		if (nav.type === 'leave' || !dirty()) return;
		nav.cancel();
		const delta = nav.type === 'popstate' ? nav.delta : 0;
		const url = nav.to?.url;
		confirmDialog('I har ændringer, der ikke er gemt. Vil I forlade siden?', 'Forlad siden', false).then((ok) => {
			if (!ok) return;
			leaving = true;
			if (delta) history.go(delta);
			else if (url) goto(url);
		});
	});
	$effect(() => {
		const warn = (e: BeforeUnloadEvent) => {
			if (dirty()) e.preventDefault();
		};
		addEventListener('beforeunload', warn);
		return () => removeEventListener('beforeunload', warn);
	});

	async function save(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		// Kan indsatte linjer ikke læses, gemmes der ikke (ellers gik de tabt).
		if (bulk.trim() && !(await addBulk())) return;
		busy = true;
		const body = currentBody();
		try {
			let saved = recipe
				? await api<Recipe>(`/recipes/${recipe.id}`, { method: 'PUT', body })
				: await api<Recipe>('/recipes', { method: 'POST', body });
			if (newImage) saved = await uploadRecipeImage(saved.id, newImage);
			else if (removeImage) saved = await api<Recipe>(`/recipes/${saved.id}/image`, { method: 'DELETE' });
			leaving = true;
			onsave(saved);
		} catch (err) {
			error = say(err);
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
		let r: Recipe;
		try {
			r = await api<Recipe>(`/recipes/${recipe.id}/suggest-main`, { method: 'POST' });
		} catch (e) {
			error = say(e);
			return;
		}
		const main = new Set(r.ingredients.filter((l) => l.is_main).map((l) => l.id));
		for (const l of lines) l.is_main = l.id !== null && main.has(l.id);
	}
</script>

<form onsubmit={save}>
	<div class="pad stack">
		<div class="image">
			<Plate src={imageUrl} seed={recipe?.id ?? 'ny'} size={96} />
			<div class="image-actions">
				<label class="btn sm file">
					<input type="file" accept="image/*" onchange={pickImage} class="sr" />
					{imageBusy ? 'Behandler…' : imageUrl ? 'Skift billede' : 'Vælg billede'}
				</label>
				{#if imageUrl}<button type="button" class="btn sm danger" onclick={clearImage}>Fjern</button>{/if}
			</div>
		</div>

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
	</div>

	<h2 class="sl">Ingredienser<span>stjerne = hovedingrediens</span></h2>
	<p class="pad muted small">
		Tryk på stjernen ud for en ingrediens for at gøre den til hovedingrediens. Der må gerne være flere. Tryk på varen
		for at rette, hvad der skal købes.
	</p>
	{#if recipe}
		<p class="pad"><button type="button" class="btn sm quiet again" onclick={suggestMain}><Icon name="star" size={16} />Foreslå stjerner igen</button></p>
	{/if}

	{#each groups as g}
		{#if hasGroups}
			<div class="pad">
				<input
					class="group"
					value={g.name}
					placeholder="Uden afsnit"
					aria-label="Afsnit"
					onchange={(e) => renameGroup(g.name, e.currentTarget.value)}
				/>
			</div>
		{/if}
		{#each g.lines as line (line.uid)}
			<div class="line">
				<div class="top">
					<button
						type="button"
						class="star"
						class:on={line.is_main}
						aria-pressed={line.is_main}
						aria-label="Hovedingrediens: {line.item || line.raw}"
						onclick={() => (line.is_main = !line.is_main)}><Icon name="star" size={20} /></button
					>
					<input class="grow" bind:value={line.raw} onchange={() => reparse(line)} aria-label="Ingredienslinje" />
					<button type="button" class="rnd" aria-label="Flyt {line.item || line.raw} op" onclick={() => move(line, -1)}><Icon name="up" /></button>
					<button type="button" class="rnd" aria-label="Fjern {line.item || line.raw}" onclick={() => remove(line)}><Icon name="x" /></button>
				</div>
				<div class="parsed">
					<button
						type="button"
						class="qty"
						aria-expanded={line.showFields}
						aria-label="Mængde: {formatQuantity(line.quantity, line.quantity_max, line.unit) || 'ingen'}. Ret felterne"
						onclick={() => (line.showFields = !line.showFields)}
					>
						{formatQuantity(line.quantity, line.quantity_max, line.unit) || '–'}
					</button>
					<Icon name="move" size={14} />
					<button type="button" class="pick" aria-expanded={picking === line.uid} onclick={() => (picking = picking === line.uid ? null : line.uid)}>
						{#if line.ingredient}
							{line.ingredient.name}
						{:else if line.match_status === 'bekræftet'}
							<span class="muted">ingen vare</span>
						{:else}
							vælg vare
						{/if}
					</button>
					{#if line.match_status === 'usikker'}
						<span class="tag">usikker</span>
						<button type="button" class="btn sm" onclick={() => pick(line, line.ingredient)}><Icon name="check" size={16} stroke={3} />Rigtig</button>
					{:else if line.ingredient?.pantry}
						<span class="tag">basisvare</span>
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
					<!-- Vælgeren har ikke selv en lukkeknap: den står her, så den også kan lukkes med fingeren. -->
					<div class="card picker">
						<div class="picker-head">
							<span class="ey grow">Vare til "{line.item || line.raw}"</span>
							<button type="button" class="btn sm quiet" onclick={() => (picking = null)}>Luk</button>
						</div>
						<IngredientPicker
							initial={line.item}
							onpick={(ing) => pick(line, ing)}
							oncancel={() => (picking = null)}
						/>
					</div>
				{/if}
			</div>
		{/each}
	{/each}

	<div class="pad stack add">
		<label class="field">
			<span>Tilføj ingredienser</span>
			<textarea bind:value={bulk} rows={lines.length ? 3 : 8}
				placeholder={'Én pr. linje, fx\n500 g hakket oksekød\n2 løg\n\nSkriv "Sovs:" på en linje for at starte et afsnit.'}></textarea>
		</label>
		{#if bulk.trim()}<button type="button" class="btn" onclick={addBulk}>Læs linjerne</button>{/if}
	</div>

	<h2 class="sl">Fremgangsmåde<span>ét trin pr. linje</span></h2>
	<div class="pad">
		<textarea bind:value={steps} rows="8" aria-label="Fremgangsmåde, ét trin pr. linje"></textarea>
	</div>

	{#if error}<p class="msg" role="alert">{error}</p>{/if}

	<div class="save pad">
		<button class="btn primary block" disabled={busy || !title.trim()}>{busy ? 'Gemmer…' : 'Gem'}</button>
	</div>
</form>

<style>
	.stack {
		display: grid;
		gap: 12px;
	}
	.image {
		display: flex;
		gap: 14px;
		align-items: center;
		margin-top: 4px;
	}
	.image-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.file {
		cursor: pointer;
	}
	/* Filfeltet er skjult, men kan nås med tastaturet: knappen viser fokus. */
	.file:has(input:focus-visible) {
		outline: 2px solid var(--ink);
		outline-offset: 2px;
	}
	.two {
		display: grid;
		grid-template-columns: 6.5rem minmax(0, 1fr);
		gap: 10px;
	}
	.again {
		margin-left: -13px;
	}
	.group {
		font-weight: 700;
		margin-top: 12px;
	}
	.line {
		margin-inline: var(--gutter);
		padding-block: 8px;
		border-bottom: 1px solid var(--line);
	}
	.top {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	/* Stjernen: 44px trykflade. Udfyldt = hovedingrediens. */
	.star {
		flex: none;
		display: flex;
		align-items: center;
		justify-content: center;
		width: var(--tap);
		height: var(--tap);
		margin-left: -12px;
		border-radius: 50%;
		color: var(--ring);
	}
	.star.on {
		color: var(--tomat);
	}
	.star.on :global(svg) {
		fill: currentColor;
	}
	.parsed {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		padding-left: 38px;
		font-size: 14.5px;
		color: var(--muted);
	}
	/* Små knapper i en tekstlinje: trykfladen er stadig 44px høj. */
	.qty,
	.pick {
		display: inline-flex;
		align-items: center;
		min-height: var(--tap);
		min-width: 28px;
	}
	.qty {
		text-decoration: underline dotted;
		text-underline-offset: 3px;
	}
	.pick {
		font-weight: 600;
		color: var(--tomat);
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
		padding: 4px 0 6px 38px;
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
	.picker {
		margin-block: 6px 8px;
		padding-top: 6px;
	}
	.picker-head {
		display: flex;
		align-items: center;
		gap: 8px;
		padding-inline: var(--gutter) 4px;
	}
	.add {
		margin-top: 16px;
	}
	/* Fast bjælke over menuen, så Gem altid kan nås uden at dække felterne. */
	.save {
		position: sticky;
		bottom: calc(var(--nav-h) + env(safe-area-inset-bottom));
		background: var(--paper);
		border-top: 1px solid var(--line);
		padding-block: 8px;
		margin-top: 16px;
	}
</style>
