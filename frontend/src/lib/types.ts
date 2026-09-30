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
	ingredients: string[];
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

// --- Madplan (backend/src/madplan/api/plans.py) ---

export type MealKind = 'opskrift' | 'fritekst' | 'rester';
export type LineState = 'hjemme' | 'rest' | null;

export interface RecipeBrief {
	id: number;
	title: string;
	servings: number | null;
	image_url: string | null;
}

export interface MealRef {
	id: number;
	date: string;
	title: string;
	multiplier: number;
}

export interface MealLine {
	line_id: number;
	group: string;
	raw: string;
	quantity: number | null;
	quantity_max: number | null;
	unit: string | null;
	item: string;
	note: string | null;
	ingredient: IngredientRef | null;
	is_main: boolean;
	state: LineState;
}

export interface Meal {
	id: number;
	date: string;
	for_child: boolean;
	kind: MealKind;
	title: string;
	recipe: RecipeBrief | null;
	text: string;
	multiplier: number;
	leftover_from: MealRef | null;
	suggest_double: boolean;
	lines: MealLine[];
}

export interface Day {
	date: string;
	meal: Meal | null;
	child: Meal | null;
}

export interface Wish {
	id: number;
	recipe: RecipeBrief | null;
	text: string;
	title: string;
}

export interface PlanBrief {
	id: number;
	start_date: string;
	end_date: string;
}

export interface Plan extends PlanBrief {
	days: Day[];
	wishlist: Wish[];
}

/** Det, der kan sættes på en dag. */
export type SlotChoice =
	| { kind: 'opskrift'; recipe_id: number }
	| { kind: 'fritekst'; text: string }
	| { kind: 'rester'; leftover_from_id: number }
	| { kind: 'ønske'; wish_id: number };

// --- Indkøbsliste (backend/src/madplan/api/shopping.py) ---

export interface Amount {
	quantity: number;
	unit: string | null;
}

export interface ShoppingItem {
	key: string;
	name: string;
	department: string;
	amounts: Amount[];
	unquantified: boolean;
	days: string[];
	sources: { date: string; meal: string; raw: string }[];
	checked: boolean;
	kind: 'plan' | 'extra';
	source: 'egen' | 'løbet tør' | null;
	unknown: boolean;
	ingredient_name: string | null;
}

export interface PantryItem {
	ingredient_id: number;
	name: string;
	amounts: Amount[];
	days: string[];
	requested: boolean;
}

export interface ShoppingData {
	plan: PlanBrief | null;
	departments: Department[];
	items: ShoppingItem[];
	pantry: PantryItem[];
	home: { key: string; name: string }[];
	server_ms: number;
}
