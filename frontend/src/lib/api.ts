import { goto } from '$app/navigation';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
		public detail: unknown = null
	) {
		super(message);
	}
}

function message(detail: unknown, status: number): string {
	if (typeof detail === 'string') return detail;
	if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
	if (Array.isArray(detail)) {
		// Valideringsfejl fra serveren: vis den første besked ("Linket skal starte med https://").
		const msg = detail[0]?.msg;
		return typeof msg === 'string' ? msg.replace(/^Value error, /, '') : 'Ugyldige oplysninger';
	}
	return 'Det gik ikke. Prøv igen.';
}

/** JSON-kald til backend. Sender til login, hvis sessionen er udløbet. */
export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
	let res: Response;
	try {
		res = await fetch(`/api${path}`, {
			method: init.method ?? 'GET',
			headers: init.body !== undefined ? { 'Content-Type': 'application/json' } : {},
			body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
			credentials: 'same-origin'
		});
	} catch {
		throw new ApiError(0, 'Ingen forbindelse. Prøv igen.');
	}
	if (res.status === 401 && path !== '/login') {
		const back = location.pathname + location.search;
		await goto(`/login?til=${encodeURIComponent(back)}`);
		throw new ApiError(401, 'Ikke logget ind');
	}
	if (res.status === 204) return undefined as T;
	const data = await res.json().catch(() => null);
	if (!res.ok) {
		const detail = data?.detail ?? null;
		throw new ApiError(res.status, message(detail, res.status), detail);
	}
	return data as T;
}
