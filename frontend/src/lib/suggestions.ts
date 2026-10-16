import { api, ApiError } from './api';
import type { RecipeBrief } from './types';

export interface Suggestion {
	recipe: RecipeBrief;
	source_host: string | null;
	last_planned: string | null;
}

/** null = forslag kan ikke hentes lige nu (vis ikke gruppen). */
export async function fetchSuggestions(opts: { planId?: number; limit?: number } = {}): Promise<Suggestion[] | null> {
	const q = new URLSearchParams();
	if (opts.planId !== undefined) q.set('plan_id', String(opts.planId));
	if (opts.limit !== undefined) q.set('limit', String(opts.limit));
	const qs = q.toString();
	try {
		return await api<Suggestion[]>(`/suggestions${qs ? `?${qs}` : ''}`);
	} catch (e) {
		// 401 har api() allerede sendt til login. Alt andet: ingen forslag.
		if (e instanceof ApiError && e.status !== 401) return null;
		throw e;
	}
}
