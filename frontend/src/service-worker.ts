/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

// App-skallen gemmes, så appen kan åbnes uden dækning. API-kald gemmes ikke
// her (indkøbslisten får sin egen offline-lagring i fase 3).

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `madplan-${version}`;
const ASSETS = [...build, ...files, '/'];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((c) => c.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => sw.clients.claim())
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	const url = new URL(req.url);
	if (req.method !== 'GET' || url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;

	if (req.mode === 'navigate') {
		// Nyeste udgave, når der er net. Ellers den gemte app-skal.
		event.respondWith(fetch(req).catch(async () => (await caches.match('/')) ?? Response.error()));
		return;
	}
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(req).then((hit) => hit ?? fetch(req)));
	}
});

// Påmindelser ("Husk: kød op af fryseren") fra serveren. Se backend/madplan/reminders.py.
interface Besked {
	title?: string;
	body?: string;
	tag?: string;
	url?: string;
	reminder_id?: number;
}

sw.addEventListener('push', (event) => {
	let msg: Besked = {};
	try {
		msg = event.data?.json() ?? {};
	} catch {
		msg = { body: event.data?.text() };
	}
	// "Klaret" krydser påmindelsen af direkte fra beskeden (vises ikke på iPhone).
	const options: NotificationOptions & { actions?: { action: string; title: string }[] } = {
		body: msg.body,
		tag: msg.tag,
		data: msg,
		icon: '/icon-192.png',
		badge: '/icon-192.png',
		actions: msg.reminder_id ? [{ action: 'klaret', title: 'Klaret' }] : []
	};
	event.waitUntil(sw.registration.showNotification(msg.title ?? 'Madplan', options));
});

sw.addEventListener('notificationclick', (event) => {
	const msg: Besked = event.notification.data ?? {};
	event.notification.close();
	if (event.action === 'klaret' && msg.reminder_id) {
		event.waitUntil(
			fetch(`/api/reminders/${msg.reminder_id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ done: true }),
				credentials: 'same-origin'
			})
		);
		return;
	}
	// Åbner dagen med retten, så påmindelsen kan krydses af der.
	const url = msg.url ?? '/';
	event.waitUntil(
		(async () => {
			const [win] = await sw.clients.matchAll({ type: 'window', includeUncontrolled: true });
			if (win) {
				await win.focus();
				if (await win.navigate(url).catch(() => null)) return;
			}
			await sw.clients.openWindow(url);
		})()
	);
});
