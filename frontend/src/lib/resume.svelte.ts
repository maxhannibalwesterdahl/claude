import { today } from './dates';

/**
 * Appen på hjemmeskærmen genoptager ofte den side, den havde i hukommelsen.
 * `clock.today` følger med, når appen åbnes igen, og `onResume` henter data
 * igen, hvis de er ældre end `staleMs` (fx hvis den anden har ændret planen).
 */
export const clock = $state({ today: today() });

export function onResume(reload: () => void, staleMs = 60_000): () => void {
	let last = Date.now();
	const handler = () => {
		if (document.visibilityState !== 'visible') return;
		clock.today = today();
		if (Date.now() - last > staleMs) {
			last = Date.now();
			reload();
		}
	};
	const mark = () => {
		if (document.visibilityState === 'hidden') last = Math.min(last, Date.now());
	};
	document.addEventListener('visibilitychange', handler);
	document.addEventListener('visibilitychange', mark);
	addEventListener('pageshow', handler);
	return () => {
		document.removeEventListener('visibilitychange', handler);
		document.removeEventListener('visibilitychange', mark);
		removeEventListener('pageshow', handler);
	};
}
