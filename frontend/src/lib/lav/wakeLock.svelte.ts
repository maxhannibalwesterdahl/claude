interface Sentinel extends EventTarget {
	released: boolean;
	release: () => Promise<void>;
}
type WakeNavigator = Navigator & { wakeLock?: { request: (type: 'screen') => Promise<Sentinel> } };

/**
 * Holder skærmen tændt, mens man laver mad (hvor browseren understøtter det).
 * Browseren slipper selv låsen, når siden skjules, så der bedes om den igen,
 * når siden kommer frem. `active` er kun sand, mens låsen faktisk holdes.
 */
class WakeLock {
	active = $state(false);

	/** Bed om låsen. Returnerer oprydningen, så den kan stå direkte i en $effect. */
	hold(): () => void {
		let lock: Sentinel | null = null;
		let gone = false;
		const nav = navigator as WakeNavigator;
		const released = () => (this.active = false);
		const request = () => {
			if (document.visibilityState !== 'visible' || (lock && !lock.released)) return;
			// Uden understøttelse, eller hvis telefonen siger nej (fx strømsparetilstand): stille.
			nav.wakeLock
				?.request('screen')
				.then((l) => {
					// Siden kan være forladt, mens der blev spurgt.
					if (gone) return void l.release().catch(() => {});
					lock = l;
					l.addEventListener('release', released);
					this.active = true;
				})
				.catch(() => {});
		};
		request();
		document.addEventListener('visibilitychange', request);
		return () => {
			gone = true;
			document.removeEventListener('visibilitychange', request);
			lock?.release().catch(() => {});
			this.active = false;
		};
	}
}

export const wakeLock = new WakeLock();
