<script lang="ts">
	import Fold from '$lib/Fold.svelte';
	import { lastPlannedLabel, longDate, periodLong, shoppingDayLabel, today, weekTitle } from '$lib/dates';
	import type { PlanBrief } from '$lib/types';
	import { NEEDS_NET } from '$lib/ui/copy';
	import Hero from '$lib/ui/Hero.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import { ICONS, type IconName } from '$lib/ui/icons';
	import IngredientRow from '$lib/ui/IngredientRow.svelte';
	import { longpress } from '$lib/ui/longpress';
	import Plate from '$lib/ui/Plate.svelte';
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
	import Segmented from '$lib/ui/Segmented.svelte';
	import Sheet from '$lib/ui/Sheet.svelte';
	import SwipeRow from '$lib/ui/SwipeRow.svelte';
	import Tick from '$lib/ui/Tick.svelte';
	import WeekNav from '$lib/ui/WeekNav.svelte';

	// Prøveside for grundpakken: alle fælles komponenter og klasser samlet ét sted.
	// Bruger ingen data fra serveren. Slettes, når de nye sider er på plads.
	const plans: PlanBrief[] = [
		{ id: 3, start_date: '2026-10-11', end_date: '2026-10-17' },
		{ id: 2, start_date: '2026-10-04', end_date: '2026-10-10' },
		{ id: 1, start_date: '2026-09-27', end_date: '2026-10-03' }
	];
	let planId = $state(2);
	const plan = $derived(plans.find((p) => p.id === planId)!);

	let sheet = $state<'day' | 'tall' | 'nested' | null>(null);
	let inner = $state(false);
	let mult = $state(1);
	let filter = $state('alle');
	let bought = $state(false);
	let have = $state([false, true, false]);
	let log = $state<string[]>([]);
	const say = (s: string) => (log = [s, ...log].slice(0, 4));

	const names = Object.keys(ICONS) as IconName[];
	const lines = [
		{ qty: '500 g', name: 'hakket oksekød', note: null },
		{ qty: '2', name: 'løg', note: 'finthakket' },
		{ qty: '2 dåser', name: 'hakkede tomater', note: null }
	];
</script>

<main class="docked">
	<ScreenHeader title={weekTitle(plan, today())} eyebrow="{periodLong(plan.start_date, plan.end_date)} · {shoppingDayLabel(plan, today())}">
		{#snippet actions()}
			<WeekNav {plan} {plans} onselect={(id) => (planId = id)} onnew={() => say('Ny uge')} />
		{/snippet}
	</ScreenHeader>

	<p class="sl">Ark<span>Sheet</span></p>
	<div class="chips pad">
		<button class="chip" onclick={() => (sheet = 'day')}>Dag</button>
		<button class="chip" onclick={() => (sheet = 'tall')}>Højt, med felt</button>
		<button class="chip a" onclick={() => (sheet = 'nested')}><Icon name="search" size={15} stroke={2.4} />Ark i ark</button>
	</div>

	<p class="sl">Knapper<span>.btn</span></p>
	<div class="pad stack">
		<div class="btns">
			<button class="btn primary"><Icon name="play" size={16} />Lav mad</button>
			<button class="btn">Skift ret</button>
		</div>
		<div class="btns">
			<button class="btn"><Icon name="move" />Flyt</button>
			<button class="btn danger">Fjern</button>
			<button class="btn" disabled>Slået fra</button>
		</div>
		<div class="chips">
			<button class="btn sm primary"><Icon name="check" size={15} stroke={3} />piskefløde</button>
			<button class="btn sm">Anden vare</button>
			<button class="btn sm quiet">Slet denne uge</button>
			<a class="link" href="/_ui">Et link</a>
		</div>
		<button class="btn primary block">Log ind</button>
		<div class="chips">
			<button class="rnd" aria-label="Tilbage"><Icon name="left" stroke={2.2} /></button>
			<button class="rnd float" aria-label="Luk"><Icon name="x" /></button>
			<button class="rnd" aria-label="Næste" disabled><Icon name="right" stroke={2.2} /></button>
			<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>
			<span class="tag">ingen indkøb</span>
		</div>
	</div>

	<p class="sl">Filtre<span>.chip</span></p>
	<div class="chips pad">
		{#each [['alle', 'Alle'], ['onsker', 'Ønskeliste · 2'], ['laenge', 'Længe siden']] as [value, label]}
			<button class="chip" aria-pressed={filter === value} onclick={() => (filter = value)}>{label}</button>
		{/each}
		<a class="chip a" href="/_ui">Ryd op · 3</a>
	</div>

	<p class="sl">Felter<span>.field</span></p>
	<div class="pad stack">
		<label class="field"><span>Titel</span><input placeholder="Fx lasagne" /></label>
		<label class="field">
			<span>Afdeling</span>
			<select><option>Frugt og grønt</option><option>Mejeri</option></select>
		</label>
		<label class="field"><span>Barnets note</span><textarea rows="2"></textarea></label>
	</div>

	<p class="sl">I aften<span>.card .lab</span></p>
	<div class="card tonight">
		<div class="grow">
			<p class="lab">I aften · onsdag</p>
			<p class="serif dish">Fiskefrikadeller med rodfrugter</p>
			<p class="small muted">4 pers. · Barnet: Grød</p>
		</div>
		<Plate seed="fisk" size={72} />
	</div>
	<p class="note"><b>Barnet:</b> tag en portion fra, før du salter farsen.</p>
	<p class="msg" role="alert">{NEEDS_NET}</p>
	<p class="net"><Icon name="nonet" size={16} /><span><b>Uden net.</b> Listen er gemt her, 3 kryds venter.</span></p>

	<p class="sl">Rækker<span>.kv .op</span></p>
	<div class="kv">
		<p class="k">Mængde<small>Opskriften er til 4</small></p>
		<Segmented
			label="Mængde"
			options={[
				{ value: 0.5, label: '×½' },
				{ value: 1, label: '×1' },
				{ value: 2, label: '×2' }
			]}
			value={mult}
			onchange={(v) => (mult = v)}
		/>
	</div>
	<div class="kv">
		<p class="k">Barnet<small>Samme som de voksne</small></p>
		<button class="v" onclick={() => say('Noget andet')}>Noget andet</button>
	</div>
	<a class="kv" href="/_ui"><span class="k">Basisvarer<small>Altid hjemme, kommer ikke på listen</small></span><span class="tag">42</span></a>
	<button class="op" onclick={() => say('Tacos')}>
		<Plate seed={1} size={44} />
		<span class="grow"><span class="n">Tacos med oksekød</span><br /><span class="m">Egen opskrift · 4 pers.</span></span>
		<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>
	</button>
	<Fold title="Købt" count={3}>
		<div class="kv"><p class="k">løg</p></div>
		<div class="kv"><p class="k">pasta</p></div>
	</Fold>

	<p class="sl">Ingredienser<span>{have.filter(Boolean).length} af {lines.length} har I hjemme</span></p>
	{#each lines as l, i}
		<IngredientRow qty={l.qty} name={l.name} note={l.note} checked={have[i]} ontoggle={(next) => (have[i] = next)} tickLabel="har hjemme">
			{#snippet trailing()}
				{#if i === 2}<button class="chip" aria-pressed="false" onclick={() => say('rest')}>rest</button>{/if}
			{/snippet}
		</IngredientRow>
	{/each}
	<IngredientRow qty="1 tsk" name="salt" dim>
		{#snippet trailing()}<span class="tag">basis</span>{/snippet}
	</IngredientRow>
	<IngredientRow qty="8" name="tortillas">
		{#snippet trailing()}
			<button class="star" aria-pressed="true" aria-label="Hovedingrediens: tortillas"><Icon name="star" /></button>
		{/snippet}
	</IngredientRow>

	<div class="dep">Frugt &amp; grønt<span>1 tilbage</span></div>
	<SwipeRow label="Har hjemme" onaction={() => say('Har hjemme')}>
		<button class="item" aria-pressed={bought} onclick={() => (bought = !bought)} use:longpress={() => say('Langt tryk')}>
			<Tick checked={bought} size="lg" />
			<span class="grow"><span class="what" class:done={bought}><b>600 g</b> rodfrugter</span><br /><span class="small muted">ons · træk mod højre, eller hold nede</span></span>
		</button>
	</SwipeRow>
	<p class="small muted pad" aria-live="polite">{log.join(' · ') || 'Her står det, der sidst er trykket på.'}</p>

	<p class="sl">Opskrifter<span>.grid2 .rc</span></p>
	<div class="grid2">
		{#each ['Lasagne', 'Tomatsuppe', 'Ovnbagt laks med citron', 'Karrykylling med ris'] as title, i}
			<a class="rc" href="/_ui">
				<Plate seed={title} size={60} />
				<p class="n">{title}</p>
				<p class="m">{lastPlannedLabel(i ? `2026-0${i + 5}-12` : null, today())}</p>
			</a>
		{/each}
	</div>
	<p class="sl">Tallerkener<span>Plate</span></p>
	<div class="chips pad">
		{#each [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as id}<Plate seed={id} size={40} />{/each}
		<Plate src="/icon-192.png" size={44} />
	</div>

	<p class="sl">Top uden og med billede<span>Hero</span></p>
	<Hero seed="tacos" back="/_ui" />
	<br />
	<Hero src="/icon-512.png" />

	<p class="sl">Ikoner<span>Icon</span></p>
	<div class="chips pad">
		{#each names as name}<span class="tag icon"><Icon {name} />{name}</span>{/each}
	</div>

	<div class="empty">Der er ingen madplan endnu.</div>

	<form class="dock card bar" onsubmit={(e) => e.preventDefault()}>
		<Icon name="plus" stroke={2.4} />
		<input placeholder="Tilføj vare, fx bleer" aria-label="Tilføj vare" />
	</form>
	<button class="fab" aria-label="Ny opskrift" onclick={() => say('Plus')}><Icon name="plus" size={26} stroke={2.4} /></button>
</main>

{#if sheet === 'day'}
	<Sheet title="Pasta med kødsovs" eyebrow={longDate('2026-10-08')} eyebrowAbove onclose={() => (sheet = null)}>
		{#snippet aside()}<Plate seed="pasta" size={44} />{/snippet}
		<div class="kv">
			<p class="k">Mængde<small>Opskriften er til 4</small></p>
			<Segmented
				label="Mængde"
				options={[
					{ value: 0.5, label: '×½' },
					{ value: 1, label: '×1' },
					{ value: 2, label: '×2' }
				]}
				value={mult}
				onchange={(v) => (mult = v)}
			/>
		</div>
		<p class="sl">Ingredienser</p>
		{#each lines as l, i}
			<IngredientRow qty={l.qty} name={l.name} checked={have[i]} ontoggle={(next) => (have[i] = next)} tickLabel="har hjemme" />
		{/each}
		{#snippet footer(close)}
			<div class="btns">
				<button class="btn"><Icon name="move" />Flyt</button>
				<button class="btn">Skift ret</button>
				<button class="btn danger" onclick={close}>Fjern</button>
			</div>
		{/snippet}
	</Sheet>
{:else if sheet === 'tall'}
	<Sheet title={longDate('2026-10-10')} eyebrow="Aftensmad" size="tall" onclose={() => (sheet = null)}>
		<p class="sl">Fra ønskelisten</p>
		{#each ['Tacos med oksekød', 'Karrykylling med ris', 'Ovnbagt laks', 'Frikadeller', 'Tomatsuppe', 'Lasagne', 'Pizza', 'Boller i karry'] as title}
			<button class="op">
				<Plate seed={title} size={44} />
				<span class="grow n">{title}</span>
				<span class="pc"><Icon name="plus" size={17} stroke={2.4} /></span>
			</button>
		{/each}
		{#snippet footer()}
			<input type="search" placeholder="Søg i egne, Valdemarsro og nemlig" aria-label="Søg" />
		{/snippet}
	</Sheet>
{:else if sheet === 'nested'}
	<Sheet title="Ønskeliste" eyebrow="Vælg de retter, I vil have i ugen" onclose={() => (sheet = null)}>
		{#snippet aside(close)}<button class="btn sm primary" onclick={close}>Færdig</button>{/snippet}
		<div class="pad stack">
			<button class="btn block" onclick={() => (inner = true)}>Åbn et ark ovenpå</button>
		</div>
	</Sheet>
	{#if inner}
		<Sheet title="Vælg vare" initialFocus="first" onclose={() => (inner = false)}>
			<div class="pad stack">
				<input placeholder="Søg vare" aria-label="Søg vare" />
				<p class="small muted">Feltet har fokus fra start. Escape lukker kun dette ark.</p>
			</div>
		</Sheet>
	{/if}
{/if}

<style>
	.stack {
		display: grid;
		gap: 10px;
	}
	.tonight {
		display: flex;
		gap: 12px;
		margin: 10px var(--gutter);
		padding: 16px;
	}
	.dish {
		margin-block: 6px 4px;
		font-size: var(--fs-dish);
		line-height: 28px;
		font-weight: 700;
	}
	.star {
		display: grid;
		place-items: center;
		width: var(--tap);
		height: var(--tap);
		color: var(--tomat);
	}
	.item {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		min-height: var(--shop-h);
		padding-inline: var(--gutter);
		border-bottom: 1px solid var(--line);
		text-align: left;
	}
	.what {
		font-size: 18px;
		transition: color var(--t-tick);
	}
	.what.done {
		color: var(--muted);
		text-decoration: line-through;
	}
	.what.done b {
		font-weight: 400;
	}
	.icon {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 52px;
		padding: 0 14px;
		border-radius: 16px;
		box-shadow: var(--shadow-float);
	}
	.bar :global(svg) {
		color: var(--tomat);
	}
	.bar input {
		background: none;
		padding: 0;
	}
</style>
