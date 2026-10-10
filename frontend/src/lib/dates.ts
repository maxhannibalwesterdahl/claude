import type { PlanBrief } from './types';

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

const dayMonthLong = new Intl.DateTimeFormat('da-DK', { day: 'numeric', month: 'long' });
const monthLong = new Intl.DateTimeFormat('da-DK', { month: 'long' });

/** Hele dage fra `from` til `to` (negativt, når `to` ligger før). */
function daysBetween(from: string, to: string): number {
	return Math.round((parseDate(to).getTime() - parseDate(from).getTime()) / 86_400_000);
}

/** "Lørdag 10. oktober" */
export const longDate = (iso: string) => `${weekdayName(iso)} ${dayMonthLong.format(parseDate(iso))}`;

/** "4.–10. oktober" eller "28. september–4. oktober" */
export function periodLong(start: string, end: string): string {
	const a = parseDate(start);
	const b = parseDate(end);
	if (a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) return `${a.getDate()}.–${dayMonthLong.format(b)}`;
	return `${dayMonthLong.format(a)}–${dayMonthLong.format(b)}`;
}

/** Ugens titel set fra i dag: "Denne uge", "Næste uge", "Kommende uge" eller "Tidligere uge". */
export function weekTitle(plan: PlanBrief, today: string): string {
	if (plan.end_date < today) return 'Tidligere uge';
	if (plan.start_date <= today) return 'Denne uge';
	return daysBetween(today, plan.start_date) <= 7 ? 'Næste uge' : 'Kommende uge';
}

/** Ugen starter på indkøbsdagen: "indkøb i dag" eller "indkøb søndag". */
export function shoppingDayLabel(plan: PlanBrief, today: string): string {
	return plan.start_date === today ? 'indkøb i dag' : `indkøb ${weekdayLong.format(parseDate(plan.start_date))}`;
}

/** Hvornår en opskrift sidst var på en plan: "Sidst på planen i august". */
export function lastPlannedLabel(iso: string | null, today: string): string {
	if (!iso) return 'Ikke lavet endnu';
	if (iso > today) return 'På en kommende plan';
	if (daysBetween(iso, today) <= 6) return 'Sidst for få dage siden';
	const d = parseDate(iso);
	const month = monthLong.format(d);
	return d.getFullYear() === parseDate(today).getFullYear() ? `Sidst på planen i ${month}` : `Sidst på planen i ${month} ${d.getFullYear()}`;
}
