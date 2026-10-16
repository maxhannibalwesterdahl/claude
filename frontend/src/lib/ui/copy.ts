import { ApiError } from '$lib/api';

// Fælles sætninger, så appen taler med én stemme: hele sætninger, aldrig
// ordet "Fejl" og ingen udråbstegn.
export const OFFLINE = 'Uden net.';
export const NEEDS_NET = 'Det kræver net. Prøv igen, når I har forbindelse.';
export const TRY_AGAIN = 'Det gik ikke. Prøv igen.';

/** Sætningen, der vises, når et kald ikke lykkedes. Bruges i alle catch-blokke. */
export function say(e: unknown, fallback = TRY_AGAIN): string {
	if (e instanceof ApiError) return e.status === 0 ? NEEDS_NET : e.message;
	return fallback;
}
