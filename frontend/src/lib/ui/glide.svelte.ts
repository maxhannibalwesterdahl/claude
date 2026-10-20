/**
 * Ændringer, der glider på plads i stedet for at hoppe (View Transitions API).
 * Browseren tager et billede af siden før og efter ændringen og lader elementer
 * med samme `view-transition-name` glide fra den gamle plads til den nye. Resten
 * toner kort over.
 *
 * Uden API'et (ældre Safari), med reduceret bevægelse og mens der trækkes, sker
 * ændringen bare med det samme, som før.
 *
 * Navnene skal være unikke på siden ad gangen; ellers springer browseren hele
 * overgangen over. Hver ret hedder `meal-<id>` og hvert ønske `wish-<id>`.
 */
import { flushSync } from 'svelte';
import { dragState } from './drag.svelte';

/** Et ønske, der lige er lagt på en dag: den nye ret låner ønskets navn, så den glider fra ønskelisten. */
const aliases = $state<Record<number, string>>({});

/** Navnet på en ret i overgangen. */
export const mealName = (id: number) => aliases[id] ?? `meal-${id}`;

/** Navnet på et ønske i overgangen. */
export const wishName = (id: number) => `wish-${id}`;

/** Kan der glides nu? */
export function canGlide(): boolean {
	return (
		typeof document !== 'undefined' &&
		!!document.startViewTransition &&
		!document.hidden &&
		!dragState.payload &&
		!matchMedia('(prefers-reduced-motion: reduce)').matches
	);
}

/**
 * Kører `update` (fx `this.plan = p`) som en overgang. Siden tegnes om med det
 * samme inde i overgangen, så browseren kan tage billedet efter. `lend` giver
 * retter et ønskes navn, mens overgangen står på.
 * Svarer, når ændringen er sket (ikke når den er færdig med at glide).
 */
export async function glide(update: () => void, lend: Record<number, string> = {}): Promise<void> {
	if (!canGlide()) {
		update();
		return;
	}
	const t = document.startViewTransition(() => {
		Object.assign(aliases, lend);
		update();
		flushSync();
	});
	// Springes overgangen over (fx fordi en ny begynder), er ændringen stadig sket.
	t.ready.catch(() => {});
	void t.finished
		.catch(() => {})
		.then(() => {
			for (const id in lend) if (aliases[id] === lend[id]) delete aliases[id];
		});
	await t.updateCallbackDone;
}
