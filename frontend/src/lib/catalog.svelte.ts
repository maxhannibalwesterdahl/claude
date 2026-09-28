import { api } from './api';
import { searchKey } from './format';
import type { Ingredient, Meta } from './types';

/** Ingredienstabel og afdelinger, hentet én gang og delt mellem siderne. */
class Catalog {
	ingredients = $state<Ingredient[]>([]);
	meta = $state<Meta>({ departments: [], units: [] });
	#loading: Promise<void> | null = null;

	load(force = false): Promise<void> {
		if (!this.#loading || force) {
			this.#loading = Promise.all([api<Ingredient[]>('/ingredients'), api<Meta>('/meta')])
				.then(([ings, meta]) => {
					this.ingredients = ings;
					this.meta = meta;
				})
				.catch((e) => {
					this.#loading = null;
					throw e;
				});
		}
		return this.#loading;
	}

	departmentName(code: string): string {
		return this.meta.departments.find((d) => d.code === code)?.name ?? code;
	}

	/** Varer, hvis navn eller alias indeholder teksten. Navne, der starter med den, først. */
	search(text: string, limit = 30): Ingredient[] {
		const q = searchKey(text);
		if (!q) return this.ingredients.slice(0, limit);
		const scored: [number, Ingredient][] = [];
		for (const ing of this.ingredients) {
			const name = searchKey(ing.name);
			let score = -1;
			if (name === q) score = 0;
			else if (name.startsWith(q)) score = 1;
			else if (name.includes(q)) score = 2;
			else if (ing.aliases.some((a) => searchKey(a).includes(q))) score = 3;
			if (score >= 0) scored.push([score, ing]);
		}
		scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name, 'da'));
		return scored.slice(0, limit).map(([, ing]) => ing);
	}

	upsert(ing: Ingredient) {
		const i = this.ingredients.findIndex((x) => x.id === ing.id);
		if (i >= 0) this.ingredients[i] = ing;
		else this.ingredients = [...this.ingredients, ing].sort((a, b) => a.name.localeCompare(b.name, 'da'));
	}
}

export const catalog = new Catalog();
