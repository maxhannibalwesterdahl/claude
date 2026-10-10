import type { RecipeBrief } from './types';

export interface Suggestion {
	recipe: RecipeBrief;
	source_host: string | null;
	last_planned: string | null;
}

/** null = forslag kan ikke hentes lige nu (vis ikke gruppen). */
export function fetchSuggestions(opts?: { planId?: number; limit?: number }): Promise<Suggestion[] | null> {
	// Indtil serveren har GET /api/suggestions: intet kald, og dermed ingen gruppe.
	void opts;
	return Promise.resolve(null);
}
