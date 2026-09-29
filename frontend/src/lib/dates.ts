/** Datoer fra API'et er "ÅÅÅÅ-MM-DD" uden tidszone. De læses som lokal dato. */
export function parseDate(iso: string): Date {
	const [y, m, d] = iso.split('-').map(Number);
	return new Date(y, m - 1, d);
}

export function isoDate(d: Date): string {
	const p = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function addDays(d: Date, n: number): Date {
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

export const today = () => isoDate(new Date());

const weekdayShort = new Intl.DateTimeFormat('da-DK', { weekday: 'short' });
const weekdayLong = new Intl.DateTimeFormat('da-DK', { weekday: 'long' });
const dayMonth = new Intl.DateTimeFormat('da-DK', { day: 'numeric', month: 'short' });

/** "man." -> "man" */
export const weekday = (iso: string) => weekdayShort.format(parseDate(iso)).replace('.', '');
/** "mandag" -> "Mandag" */
export const weekdayName = (iso: string) => {
	const s = weekdayLong.format(parseDate(iso));
	return s.charAt(0).toUpperCase() + s.slice(1);
};
/** "5. okt." */
export const shortDate = (iso: string) => dayMonth.format(parseDate(iso));

/** "4.-10. okt." eller "28. sep.-4. okt." */
export function periodLabel(start: string, end: string): string {
	const a = parseDate(start);
	const b = parseDate(end);
	if (a.getMonth() === b.getMonth()) return `${a.getDate()}.-${dayMonth.format(b)}`;
	return `${dayMonth.format(a)}-${dayMonth.format(b)}`;
}

/** Næste dag med den ugedag (0 = søndag), i dag medregnet. */
export function nextWeekday(from: Date, weekdayIndex: number): Date {
	return addDays(from, (weekdayIndex - from.getDay() + 7) % 7);
}
