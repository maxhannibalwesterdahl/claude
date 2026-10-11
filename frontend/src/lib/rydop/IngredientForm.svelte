<script lang="ts" module>
	/** Felterne, som de står i formularen (tal som tekst, så "1,5" og "1½" kan skrives). */
	export interface IngredientFields {
		name: string;
		department: string;
		pantry: boolean;
		perPiece: string;
		perDl: string;
	}
</script>

<script lang="ts">
	import { catalog } from '$lib/catalog.svelte';

	interface Props {
		form: IngredientFields;
		/** Sætningen, hvis varen ikke kunne gemmes. */
		error: string;
		onsubmit: (e: SubmitEvent) => void;
		oncancel: () => void;
	}
	let { form = $bindable(), error, onsubmit, oncancel }: Props = $props();
</script>

<!-- Opret eller ret en vare. Den, der bruger formularen, gemmer. -->
<form class="card" {onsubmit}>
	<label class="field"><span>Navn på indkøbslisten</span><input bind:value={form.name} required /></label>
	<div class="two">
		<label class="field"><span>Afdeling</span>
			<select bind:value={form.department}>
				{#each catalog.meta.departments as d}<option value={d.code}>{d.name}</option>{/each}
			</select>
		</label>
		<label class="check"><input type="checkbox" bind:checked={form.pantry} /> Basisvare</label>
	</div>
	<div class="two">
		<label class="field"><span>Gram pr. stk</span><input bind:value={form.perPiece} inputmode="decimal" /></label>
		<label class="field"><span>Gram pr. dl</span><input bind:value={form.perDl} inputmode="decimal" /></label>
	</div>
	<p class="muted small">Basisvarer er altid hjemme og kommer ikke på indkøbslisten. Gram bruges til at lægge fx "2 løg" og "150 g løg" sammen.</p>
	{#if error}<p class="msg" role="alert">{error}</p>{/if}
	<div class="btns">
		<button type="button" class="btn" onclick={oncancel}>Annullér</button>
		<button class="btn primary">Gem</button>
	</div>
</form>

<style>
	form {
		display: grid;
		gap: 10px;
		padding: 14px;
		margin: 8px var(--gutter) 12px;
	}
	.two {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 10px;
		align-items: end;
	}
	.check {
		display: flex;
		gap: 8px;
		align-items: center;
		min-height: 48px;
	}
	.check input {
		width: 22px;
		height: 22px;
	}
	.msg {
		margin: 0;
	}
</style>
