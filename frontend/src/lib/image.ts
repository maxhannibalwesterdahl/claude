import { goto } from '$app/navigation';
import { ApiError } from './api';
import type { Recipe } from './types';

/**
 * Gør et foto mindre på telefonen før upload: højst `max` px på den længste led,
 * gemt som JPEG. Et iPhone-foto på 3-5 MB bliver typisk 200-400 KB.
 * Kan billedet ikke læses i browseren, sendes originalen (serveren tjekker den).
 */
export async function shrinkImage(file: File, max = 1600, quality = 0.85): Promise<Blob> {
	try {
		const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
		const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
		const canvas = document.createElement('canvas');
		canvas.width = Math.round(bitmap.width * scale);
		canvas.height = Math.round(bitmap.height * scale);
		canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
		bitmap.close();
		const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', quality));
		return blob ?? file;
	} catch {
		return file;
	}
}

/** Sæt opskriftens billede. */
export async function uploadRecipeImage(recipeId: number, image: Blob): Promise<Recipe> {
	const form = new FormData();
	form.append('file', image, 'billede.jpg');
	let res: Response;
	try {
		res = await fetch(`/api/recipes/${recipeId}/image`, { method: 'POST', body: form, credentials: 'same-origin' });
	} catch {
		throw new ApiError(0, 'Ingen forbindelse. Prøv igen.');
	}
	if (res.status === 401) {
		await goto(`/login?til=${encodeURIComponent(location.pathname)}`);
		throw new ApiError(401, 'Ikke logget ind');
	}
	const data = await res.json().catch(() => null);
	if (!res.ok) throw new ApiError(res.status, typeof data?.detail === 'string' ? data.detail : 'Kunne ikke gemme billedet');
	return data as Recipe;
}
