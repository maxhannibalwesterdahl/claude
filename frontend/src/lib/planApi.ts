import { api } from './api';
import type { FillPick, FillProposal, Plan, Slot, SlotChoice } from './types';

/** Alle ændringer i planen svarer med hele planen, så siden altid viser serverens udgave. */
export const planApi = {
	setSlot(plan: Plan, date: string, slot: Slot, choice: SlotChoice, multiplier = 1): Promise<Plan> {
		const where = { date, extra: slot.extra, replace_id: slot.extra ? (slot.replaceId ?? null) : null };
		if (choice.kind === 'ønske') {
			return api<Plan>(`/wishlist/${choice.wish_id}/place`, { method: 'POST', body: where });
		}
		return api<Plan>(`/plans/${plan.id}/slots`, { method: 'PUT', body: { ...where, multiplier, ...choice } });
	},
	patchMeal: (mealId: number, body: { multiplier?: number; text?: string; leftover_from_id?: number | null }) =>
		api<Plan>(`/meals/${mealId}`, { method: 'PATCH', body }),
	/** Som hovedret byttes retten med dagens hovedret. Som ekstra ret lægges den til dagens andre. */
	move: (mealId: number, date: string, extra = false) =>
		api<Plan>(`/meals/${mealId}/move`, { method: 'POST', body: { date, extra } }),
	remove: (mealId: number) => api<Plan>(`/meals/${mealId}`, { method: 'DELETE' }),
	setLine: (mealId: number, lineId: number, state: 'hjemme' | 'rest' | null) =>
		api<Plan>(`/meals/${mealId}/lines/${lineId}`, { method: 'PUT', body: { state } }),
	addReminder: (mealId: number, text: string) => api<Plan>(`/meals/${mealId}/reminders`, { method: 'POST', body: { text } }),
	setReminder: (id: number, done: boolean) => api<Plan>(`/reminders/${id}`, { method: 'PATCH', body: { done } }),
	/** null nulstiller et tidspunkt til standarden. */
	setReminderTimes: (id: number, body: { first_time?: string | null; again_time?: string | null; again_on?: boolean }) =>
		api<Plan>(`/reminders/${id}`, { method: 'PATCH', body }),
	removeReminder: (id: number) => api<Plan>(`/reminders/${id}`, { method: 'DELETE' }),
	addWish: (planId: number, body: { recipe_id?: number; text?: string }) =>
		api<Plan>(`/plans/${planId}/wishlist`, { method: 'POST', body }),
	removeWish: (wishId: number) => api<Plan>(`/wishlist/${wishId}`, { method: 'DELETE' }),
	/** Forslag til de tomme dage fra i dag. Gemmer ikke noget. */
	fillProposal: (planId: number, today: string) => api<FillProposal>(`/plans/${planId}/fill?today=${today}`),
	/** Lægger de valgte retter på planen i ét hug. Dage, der er fyldt i mellemtiden, springes over. */
	fill: (planId: number, days: FillPick[], today: string) =>
		api<Plan>(`/plans/${planId}/fill?today=${today}`, { method: 'POST', body: { days } })
};
