/**
 * Hver ændring i planen svarer med hele planen. Kører flere ændringer samtidig
 * (hurtige tryk), kan svarene komme i forkert rækkefølge, og et gammelt svar
 * ville overskrive et nyere. `ordered` viser kun et svar, hvis det er nyere end
 * det, der allerede vises. Svarer `apply` med et løfte (fx en overgang), venter
 * `ordered` på det, så svaret er vist, når `ordered` svarer.
 */
export function sequencer<T>(apply: (value: T) => void | Promise<void>) {
	let started = 0;
	let applied = 0;
	return async function ordered(fn: () => Promise<T>): Promise<T> {
		const mine = ++started;
		const value = await fn();
		if (mine > applied) {
			applied = mine;
			await apply(value);
		}
		return value;
	};
}
