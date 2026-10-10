/** Ikonernes streger på et felt på 24×24. Tegnes af Icon.svelte. */
export const ICONS = {
	cal: 'M4 6h16v14H4zM4 10h16M8 3v5M16 3v5',
	cart: 'M3 4h2l2.4 11h10.2L20 7H6.2M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM17 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
	book: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11',
	check: 'M5 12.5l4.5 4.5L19 7.5',
	plus: 'M12 5v14M5 12h14',
	search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
	left: 'M15 5l-7 7 7 7',
	right: 'M9 5l7 7-7 7',
	play: 'M8 5v14l11-7z',
	home: 'M4 11l8-7 8 7v9H4zM10 20v-6h4v6',
	nonet: 'M3 3l18 18M5 12a10 10 0 0 1 3-2M9 16a5 5 0 0 1 6 0M12 20h.01M16 10a10 10 0 0 1 3 2',
	move: 'M5 12h14M13 6l6 6-6 6',
	star: 'M12 4l2.4 5 5.6.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.6-.8z',
	link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
	list: 'M4 6h16M4 12h16M4 18h10',
	more: 'M5 12h.01M12 12h.01M19 12h.01',
	child: 'M12 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21v-5a6 6 0 0 1 12 0v5',
	x: 'M6 6l12 12M18 6L6 18',
	trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
	up: 'M12 19V5M6 11l6-6 6 6',
	down: 'M12 5v14M6 13l6 6 6-6',
	chev: 'M9 6l6 6-6 6',
	edit: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',
	camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
	out: 'M9 4H5v16h4M14 8l4 4-4 4M18 12H9'
} as const;

export type IconName = keyof typeof ICONS;
