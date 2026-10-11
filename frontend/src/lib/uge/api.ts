import { api } from '$lib/api';
import type { Plan, PlanBrief, ShoppingData } from '$lib/types';

/** Kaldene om hele uger, som planApi ikke har: hent, lav, slet og fordel ønsker. */
export const weekApi = {
	/** Alle uger, nyeste først. */
	list: () => api<PlanBrief[]>('/plans'),
	current: (today: string) => api<Plan>(`/plans/current?today=${today}`),
	get: (id: number) => api<Plan>(`/plans/${id}`),
	create: (startDate: string) => api<Plan>('/plans', { method: 'POST', body: { start_date: startDate } }),
	remove: (id: number) => api<void>(`/plans/${id}`, { method: 'DELETE' }),
	/** Lægger ønskerne på de ledige dage, der ikke er gået. */
	distribute: (id: number, today: string) => api<Plan>(`/plans/${id}/wishlist/distribute?today=${today}`, { method: 'POST' }),
	/** Indkøbslisten for en bestemt uge. Kun til visning ved siden af ugen. */
	shopping: (id: number, today: string) => api<ShoppingData>(`/shopping?plan_id=${id}&today=${today}`)
};
