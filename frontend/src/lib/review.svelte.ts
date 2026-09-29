import { api } from './api';
import type { ReviewLine } from './types';

/** Antal linjer, der skal tjekkes. Vises som tal på fanen "Tjek". */
export const reviewCount = $state({ value: 0 });

export async function refreshReviewCount(): Promise<ReviewLine[]> {
	const lines = await api<ReviewLine[]>('/review');
	reviewCount.value = lines.length;
	return lines;
}
