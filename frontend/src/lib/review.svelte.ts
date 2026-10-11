import { api } from './api';
import { itemKey } from './format';
import type { ReviewLine } from './types';

/** Antal varer, appen er i tvivl om. Den samme vare i flere opskrifter tæller én gang,
 *  ligesom kortene under Ryd op. Vises på "Ryd op" i Opskrifter. */
export const reviewCount = $state({ value: 0 });

export async function refreshReviewCount(): Promise<ReviewLine[]> {
	const lines = await api<ReviewLine[]>('/review');
	reviewCount.value = new Set(lines.map((l) => itemKey(l.item))).size;
	return lines;
}
