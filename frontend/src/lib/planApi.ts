import { api } from './api';
import type { Plan, SlotChoice } from './types';

/** Alle ændringer i planen svarer med hele planen, så siden altid viser serverens udgave. */
export const planApi = {
	setSlot(plan: Plan, date: string, forChild: boolean, choice: SlotChoice, multiplier = 1): Promise<Plan> {
		if (choice.kind === 'ønske') {
			return api<Plan>(`/wishlist/${choice.wish_id}/place`, { method: 'POST', body: { date, for_child: forChild } });
		}
		return api<Plan>(`/plans/${plan.id}/slots`, {
			method: 'PUT',
			body: { date, for_child: forChild, multiplier, ...choice }
		});
	},
	patchMeal: (mealId: number, body: { multiplier?: number; text?: string; leftover_from_id?: number | null }) =>
		api<Plan>(`/meals/${mealId}`, { method: 'PATCH', body }),
	move: (mealId: number, date: string, forChild: boolean) =>
		api<Plan>(`/meals/${mealId}/move`, { method: 'POST', body: { date, for_child: forChild } }),
	remove: (mealId: number) => api<Plan>(`/meals/${mealId}`, { method: 'DELETE' }),
	setLine: (mealId: number, lineId: number, state: 'hjemme' | 'rest' | null) =>
		api<Plan>(`/meals/${mealId}/lines/${lineId}`, { method: 'PUT', body: { state } }),
	addWish: (planId: number, body: { recipe_id?: number; text?: string }) =>
		api<Plan>(`/plans/${planId}/wishlist`, { method: 'POST', body }),
	removeWish: (wishId: number) => api<Plan>(`/wishlist/${wishId}`, { method: 'DELETE' })
};
