import { api, ApiError } from './api';
import { today } from './dates';
import type { ShoppingData } from './types';

// Listen og ventende afkrydsninger gemmes på telefonen, så listen kan bruges
// uden dækning. Samme metode som testet i fase 0 (localStorage + seneste
// ændring vinder på serveren).
const STORAGE = 'madplan.indkob.v1';
const POLL_MS = 20_000;

export interface Change {
	key: string;
	checked: boolean;
	ts: number;
}

type Status = 'loading' | 'synced' | 'offline' | 'error';

function read(): { data: ShoppingData | null; pending: Change[]; offset?: number } {
	try {
		const raw = localStorage.getItem(STORAGE);
		if (raw) return JSON.parse(raw);
	} catch {
		/* privat vindue eller ødelagte data: start forfra */
	}
	return { data: null, pending: [] };
}

class ShoppingStore {
	data = $state<ShoppingData | null>(null);
	pending = $state<Change[]>([]);
	status = $state<Status>('loading');
	syncedAt = $state<Date | null>(null);
	// Forskel mellem serverens og telefonens ur (ms). "Seneste ændring vinder"
	// sammenligner tidsstempler fra to telefoner, så de skal regnes i samme tid.
	#offset = 0;
	error = $state('');
	#syncing = false;
	// Nye ændringer, mens en synkronisering kører, sendes lige bagefter.
	#again = false;
	#timer: ReturnType<typeof setInterval> | null = null;

	constructor() {
		const saved = read();
		this.data = saved.data;
		this.pending = saved.pending;
		this.#offset = saved.offset ?? 0;
	}

	#save() {
		try {
			localStorage.setItem(STORAGE, JSON.stringify({ data: this.data, pending: this.pending, offset: this.#offset }));
		} catch {
			/* fuld eller blokeret lagring: listen virker stadig, indtil siden lukkes */
		}
	}

	/** Afkrydset, med ventende ændringer lagt oveni serverens udgave. */
	checked(key: string, serverValue: boolean): boolean {
		for (let i = this.pending.length - 1; i >= 0; i--) if (this.pending[i].key === key) return this.pending[i].checked;
		return serverValue;
	}

	toggle(key: string, current: boolean) {
		this.pending = [...this.pending.filter((c) => c.key !== key), { key, checked: !current, ts: Date.now() + this.#offset }];
		this.#save();
		this.sync();
	}

	/** Send ventende ændringer og hent den nyeste liste. */
	async sync(): Promise<void> {
		if (this.#syncing) {
			this.#again = true;
			return;
		}
		this.#syncing = true;
		this.#again = false;
		const sending = $state.snapshot(this.pending);
		try {
			const data = await api<ShoppingData>(`/shopping/sync?today=${today()}`, {
				method: 'POST',
				body: { plan_id: this.data?.plan?.id ?? null, changes: sending }
			});
			// Ændringer lavet, mens vi ventede på svar, bliver liggende.
			this.pending = this.pending.filter((c) => !sending.some((s) => s.key === c.key && s.ts === c.ts));
			this.set(data);
		} catch (e) {
			if (e instanceof ApiError && e.status === 0) this.status = 'offline';
			else if (e instanceof ApiError && e.status !== 401) {
				this.status = 'error';
				this.error = e.message;
			}
		} finally {
			this.#syncing = false;
		}
		if (this.#again && this.status !== 'offline') await this.sync();
	}

	/** Nyt svar fra serveren (fx efter "har hjemme" eller en ny vare). */
	set(data: ShoppingData) {
		this.data = data;
		this.#offset = data.server_ms - Date.now();
		this.status = 'synced';
		this.syncedAt = new Date();
		this.error = '';
		this.#save();
	}

	start() {
		this.sync();
		this.#timer ??= setInterval(() => {
			if (document.visibilityState === 'visible') this.sync();
		}, POLL_MS);
		addEventListener('online', this.#wake);
		document.addEventListener('visibilitychange', this.#wake);
	}

	stop() {
		if (this.#timer) clearInterval(this.#timer);
		this.#timer = null;
		removeEventListener('online', this.#wake);
		document.removeEventListener('visibilitychange', this.#wake);
	}

	#wake = () => {
		if (document.visibilityState === 'visible') this.sync();
	};
}

export const shopping = new ShoppingStore();
