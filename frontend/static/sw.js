// Fjerner service workeren fra testappen i fase 0.3 (den lå på /sw.js).
// Telefoner, der havde testappen på hjemmeskærmen, henter denne fil ved næste
// opdateringstjek, sletter den gamle cache og genindlæser med den rigtige app.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			const keys = await caches.keys();
			await Promise.all(keys.filter((k) => k.startsWith('madplan-spike')).map((k) => caches.delete(k)));
			await self.registration.unregister();
			const clients = await self.clients.matchAll({ type: 'window' });
			for (const client of clients) client.navigate(client.url);
		})()
	);
});
