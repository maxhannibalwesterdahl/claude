import { api } from './api';
import { say } from './ui/copy';

/**
 * Beskeder (Web Push) på denne telefon.
 *
 * - `ingen`: browseren kan ikke få beskeder.
 * - `hjemmeskaerm`: iPhone, hvor appen ikke er lagt på hjemmeskærmen endnu
 *   (Safari giver kun beskeder til apps på hjemmeskærmen).
 * - `spoerg`: der er ikke spurgt endnu.
 * - `til`: slået til.
 * - `afvist`: der er sagt nej. Kan kun ændres i telefonens indstillinger.
 */
export type PushState = 'ukendt' | 'ingen' | 'hjemmeskaerm' | 'spoerg' | 'til' | 'afvist';

export const beskeder = $state({ state: 'ukendt' as PushState, busy: false, error: '' });

function supported(): boolean {
	return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

function iosInBrowser(): boolean {
	const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
	const standalone = (navigator as { standalone?: boolean }).standalone || matchMedia('(display-mode: standalone)').matches;
	return ios && !standalone;
}

function check(): void {
	if (!supported()) {
		beskeder.state = iosInBrowser() ? 'hjemmeskaerm' : 'ingen';
		return;
	}
	const p = Notification.permission;
	beskeder.state = p === 'granted' ? 'til' : p === 'denied' ? 'afvist' : 'spoerg';
}

function bytes(b64url: string): Uint8Array<ArrayBuffer> {
	const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (b64url.length % 4)) % 4);
	const raw = atob(b64);
	const out = new Uint8Array(new ArrayBuffer(raw.length));
	for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
	return out;
}

function same(a: ArrayBuffer | null, b: Uint8Array): boolean {
	if (!a || a.byteLength !== b.length) return false;
	const x = new Uint8Array(a);
	return x.every((v, i) => v === b[i]);
}

/** Tilmelder telefonen med serverens nøgle og fortæller serveren om den.
 *  Har serveren fået en ny nøgle, tilmeldes telefonen igen. */
async function register(hello: boolean): Promise<void> {
	const { public_key } = await api<{ public_key: string }>('/push/key');
	const key = bytes(public_key);
	const reg = await navigator.serviceWorker.ready;
	let sub = await reg.pushManager.getSubscription();
	if (sub && !same(sub.options.applicationServerKey, key)) {
		await sub.unsubscribe();
		sub = null;
	}
	sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
	const { endpoint, keys } = sub.toJSON();
	await api('/push/subscriptions', { method: 'POST', body: { endpoint, keys, hello } });
}

/** Spørger om lov og slår beskeder til. Skal kaldes fra et tryk. */
export async function enable(): Promise<void> {
	beskeder.error = '';
	beskeder.busy = true;
	try {
		await Notification.requestPermission();
		check();
		if (beskeder.state === 'til') await register(true);
	} catch (e) {
		beskeder.error = say(e, 'Beskeder kunne ikke slås til. Prøv igen.');
	} finally {
		beskeder.busy = false;
	}
}

/** Ved opstart: er beskeder slået til, sikres det, at serveren kender telefonen. */
export function syncPush(): void {
	check();
	if (beskeder.state === 'til') register(false).catch(() => {});
}
