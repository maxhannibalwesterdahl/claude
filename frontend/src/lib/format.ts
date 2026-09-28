const FRACTIONS: [number, string][] = [
	[0.25, '¼'],
	[1 / 3, '⅓'],
	[0.5, '½'],
	[2 / 3, '⅔'],
	[0.75, '¾']
];

/** 1.5 -> "1½", 0.25 -> "¼", 2.2 -> "2,2" */
export function formatNumber(n: number): string {
	const whole = Math.floor(n);
	const frac = n - whole;
	if (frac < 0.01) return String(whole);
	for (const [value, sign] of FRACTIONS) {
		if (Math.abs(frac - value) < 0.01) return (whole ? String(whole) : '') + sign;
	}
	return (Math.round(n * 100) / 100).toString().replace('.', ',');
}

// Enheder gemmes i ental. Flertal til visning, når mængden er over 1.
const PLURAL: Record<string, string> = {
	dåse: 'dåser',
	pakke: 'pakker',
	pose: 'poser',
	bundt: 'bundter',
	håndfuld: 'håndfulde',
	skive: 'skiver',
	stængel: 'stængler',
	bakke: 'bakker',
	potte: 'potter',
	terning: 'terninger',
	plade: 'plader',
	blad: 'blade',
	kvist: 'kviste',
	knsp: 'knsp',
	dryp: 'dryp',
	stænk: 'stænk'
};

export function unitLabel(unit: string, amount: number): string {
	return amount > 1 ? (PLURAL[unit] ?? unit) : unit;
}

export function formatQuantity(q: number | null, qMax: number | null, unit: string | null): string {
	if (q === null) return unit ?? '';
	const amount = qMax !== null ? `${formatNumber(q)}-${formatNumber(qMax)}` : formatNumber(q);
	return unit ? `${amount} ${unitLabel(unit, qMax ?? q)}` : amount;
}

/** Normaliseret søgetekst: små bogstaver, uden accenter (men med æøå). */
export function searchKey(text: string): string {
	return text
		.toLowerCase()
		.normalize('NFD')
		.replace(/[\u0300-\u0309\u030b-\u036f]/g, '')
		.normalize('NFC')
		.replace(/[\s-]+/g, ' ')
		.trim();
}

/** Dansk tal fra et inputfelt: "1,5" og "1½" -> 1.5. Tomt -> null. */
export function parseNumber(text: string): number | null {
	const t = text.trim().replace(',', '.');
	if (!t) return null;
	const m = t.match(/^(\d*)\s*([¼½¾⅓⅔])$/);
	if (m) {
		const frac = { '¼': 0.25, '½': 0.5, '¾': 0.75, '⅓': 1 / 3, '⅔': 2 / 3 }[m[2]]!;
		return (m[1] ? Number(m[1]) : 0) + frac;
	}
	const n = Number(t);
	return Number.isFinite(n) ? n : null;
}
