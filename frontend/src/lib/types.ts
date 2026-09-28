// Svarer til backend/src/madplan/api/schemas.py

export type MatchStatus = 'sikker' | 'usikker' | 'ingen' | 'bekræftet';

export interface IngredientRef {
	id: number;
	name: string;
	department: string;
	pantry: boolean;
}

export interface Ingredient extends IngredientRef {
	grams_per_piece: number | null;
	grams_per_dl: number | null;
	aliases: string[];
	used_in: number;
}

export interface Line {
	id: number | null;
	raw: string;
	group: string;
	quantity: number | null;
	quantity_max: number | null;
	unit: string | null;
	item: string;
	note: string | null;
	ingredient: IngredientRef | null;
	match_status: MatchStatus;
	is_main: boolean;
}

export interface Recipe {
	id: number;
	title: string;
	servings: number | null;
	instructions: string[];
	child_note: string;
	source_url: string | null;
	image_url: string | null;
	ingredients: Line[];
	warnings: string[];
}

export interface RecipeSummary {
	id: number;
	title: string;
	servings: number | null;
	image_url: string | null;
	source_host: string | null;
	main_ingredients: string[];
	to_review: number;
}

export interface ReviewLine {
	id: number;
	recipe_id: number;
	recipe_title: string;
	raw: string;
	item: string;
	unit: string | null;
	ingredient: IngredientRef | null;
	match_status: MatchStatus;
}

export interface Department {
	code: string;
	name: string;
}

export interface Meta {
	departments: Department[];
	units: string[];
}
