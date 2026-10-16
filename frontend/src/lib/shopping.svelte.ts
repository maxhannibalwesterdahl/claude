import { api, ApiError } from './api';
import { today } from './dates';
import type { ShoppingData } from './types';

// Listen og ventende afkrydsninger gemmes på telefonen, så listen kan bruges
// uden dækning. Samme metode som testet i fase 0 (localStorage + seneste
// ændring vinder på serveren).
// Listen gemmes pr. bruger, så den næste på telefonen ikke ser og sender den forrige
// brugers liste (en anden families indkøb). Ryddes ved logout.
const STORAGE = 'madplan.indkob.v2.';
const LEGACY = 'madplan.indkob.v1'; // én fælles nøgle fra før familier: slettes
const USER = 'madplan.bruger';
const POLL_MS = 20_000;

export interface Change {
	key: string;
	checked: boolean;
	ts: number;
	// Planen, der blev vist, da rækken blev krydset af (mangler i ældre gemte ændringer)
	plan_id?: number | null;
}

type Status = 'loading' | 'synced' | 'offline' | 'error';

function savedUser(): number | null {
	try {
		const id = Number(localStorage.getItem(USER));
		return Number.isInteger(id) && id > 0 ? id : null;
	} catch {
		return null;
	}
}

function read(user: number | null): { data: ShoppingData | null; pending: Change[]; offset?: number } {
	if (user === null) return { data: null, pending: [] };
	try {
		const raw = localStorage.getItem(STORAGE + user);
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
	// Den uge, der er valgt (på Uge eller med uge-vælgeren). null = den
	// igangværende uge. Gemmes ikke, så appen åbner på den igangværende uge igen.
	selected = $state<number | null>(null);
	// Forskel mellem serverens og telefonens ur (ms). "Seneste ændring vinder"
	// sammenligner tidsstempler fra to telefoner, så de skal regnes i samme tid.
	#offset = 0;
	error = $state('');
	#syncing = false;
	// Nye ændringer, mens en synkronisering kører, sendes lige bagefter.
	#again = false;
	#timer: ReturnType<typeof setInterval> | null = null;

	// Brugeren, listen på telefonen tilhører. null = ingen er logget ind her.
	#user: number | null = null;

	constructor() {
		try {
			localStorage.removeItem(LEGACY);
		} catch {
			/* blokeret lagring */
		}
		this.#user = savedUser();
		this.#load();
	}

	#load() {
		const saved = read(this.#user);
		this.data = saved.data;
		this.pending = saved.pending;
		this.#offset = saved.offset ?? 0;
	}

	/** Den indloggede bruger. Skifter brugeren, forlades den forrige brugers liste. */
	use(userId: number) {
		if (this.#user === userId) return;
		try {
			if (this.#user !== null) localStorage.removeItem(STORAGE + this.#user);
			localStorage.setItem(USER, String(userId));
		} catch {
			/* blokeret lagring */
		}
		this.#user = userId;
		this.selected = null;
		this.#load();
	}

	/** Logout: listen og ventende ændringer slettes fra telefonen. */
	clear() {
		try {
			for (const k of Object.keys(localStorage)) if (k.startsWith('madplan.')) localStorage.removeItem(k);
		} catch {
			/* blokeret lagring */
		}
		this.#user = null;
		this.selected = null;
		this.data = null;
		this.pending = [];
		this.#offset = 0;
		this.status = 'loading';
		this.syncedAt = null;
	}

	#save() {
		if (this.#user === null) return;
		try {
			localStorage.setItem(STORAGE + this.#user, JSON.stringify({ data: this.data, pending: this.pending, offset: this.#offset }));
		} catch {
			/* fuld eller blokeret lagring: listen virker stadig, indtil siden lukkes */
		}
	}

	/** Afkrydset, med ventende ændringer lagt oveni serverens udgave. */
	checked(key: string, serverValue: boolean): boolean {
		const planId = this.data?.plan?.id ?? null;
		for (let i = this.pending.length - 1; i >= 0; i--) {
			const c = this.pending[i];
			if (c.key === key && this.#samePlan(c, planId)) return c.checked;
		}
		return serverValue;
	}

	// Egne varer ("e:") hører ikke til en plan. Plan-rækker med samme nøgle findes i
	// flere uger, så en afkrydsning i én uge må ikke vises i en anden.
	#samePlan(c: Change, planId: number | null) {
		return c.key.startsWith('e:') || c.plan_id == null || c.plan_id === planId;
	}

	toggle(key: string, current: boolean) {
		const planId = this.data?.plan?.id ?? null;
		this.pending = [
			...this.pending.filter((c) => !(c.key === key && this.#samePlan(c, planId))),
			{ key, checked: !current, ts: Date.now() + this.#offset, plan_id: key.startsWith('e:') ? null : planId }
		];
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
		const view = this.selected;
		try {
			const data = await api<ShoppingData>(`/shopping/sync?today=${today()}`, {
				method: 'POST',
				body: { plan_id: this.data?.plan?.id ?? null, view_plan_id: view, changes: sending }
			});
			// Ændringer lavet, mens vi ventede på svar, bliver liggende.
			this.pending = this.pending.filter((c) => !sending.some((s) => s.key === c.key && s.ts === c.ts));
			// Skiftet uge undervejs: svaret er for den gamle uge, og en ny hentning følger.
			if (view === this.selected) {
				// Er den valgte plan slettet, svarer serveren med den igangværende uge.
				if (view !== null && data.plan?.id !== view) this.selected = null;
				this.set(data);
			}
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

	/** Vis en anden uge (null = den igangværende uge). */
	show(planId: number | null) {
		this.selected = planId;
		this.status = 'loading';
		return this.sync();
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
