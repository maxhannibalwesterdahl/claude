import { ApiError } from '$lib/api';
import { confirmDialog } from '$lib/confirm.svelte';
import { addDays, isoDate, parseDate, periodLong, weekdayName } from '$lib/dates';
import { sequencer } from '$lib/ordered';
import { planApi } from '$lib/planApi';
import { clock } from '$lib/resume.svelte';
import { shopping } from '$lib/shopping.svelte';
import type { Day, Meal, Plan, PlanBrief } from '$lib/types';
import { say } from '$lib/ui/copy';
import { weekApi } from './api';

/** "Lasagne" -> "lasagne", til brug midt i en sætning ("Rester fra lasagne"). */
export const lowerFirst = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

/** "lørdag" */
export const weekdayLower = (iso: string) => weekdayName(iso).toLowerCase();

/** Retter på tidligere dage, der kan give rester (husstandens og barnets). Nyeste først. */
export function leftoverSources(plan: Plan, date: string, except?: number): Meal[] {
	return plan.days
		.filter((d) => d.date < date)
		.flatMap((d) => [d.meal, d.child])
		.filter((m): m is Meal => !!m && m.kind === 'opskrift' && m.id !== except)
		.reverse();
}

/**
 * Ugen, der vises: planen, listen af uger og alle ændringer i den. Siden og
 * arkene deler den samme, så de altid viser serverens seneste udgave.
 */
export class Week {
	plan = $state<Plan | null>(null);
	/** Alle uger, nyeste først. */
	plans = $state<PlanBrief[]>([]);
	loaded = $state(false);
	/** En rolig sætning, når noget ikke gik. Vises på siden og i det åbne ark. */
	error = $state('');
	/** Tæller op ved hver ændring, så indkøbslisten ved siden af ugen henter igen. */
	rev = $state(0);

	// Alle svar med en hel plan går gennem samme rækkefølge, så et gammelt svar
	// aldrig overskriver et nyere (fx hurtige flueben eller en genindlæsning).
	#ordered = sequencer<Plan>((p) => {
		this.plan = p;
	});

	/** Dage uden ret, der ikke er gået. Kun de kan få ønsker fordelt. */
	get freeDays(): number {
		return this.plan?.days.filter((d) => !d.meal && d.date >= clock.today).length ?? 0;
	}

	get planned(): number {
		return this.plan?.days.filter((d) => d.meal).length ?? 0;
	}

	day(date: string): Day | null {
		return this.plan?.days.find((d) => d.date === date) ?? null;
	}

	/** Kører en ændring i planen. Bagefter følger indkøbslisten og tallet på fanen med. */
	mutate = async (fn: () => Promise<Plan>): Promise<Plan> => {
		const p = await this.#ordered(fn);
		this.#changed();
		return p;
	};

	/** Som mutate, men siger det roligt, hvis det ikke gik. Svarer true, når det lykkedes. */
	run = async (fn: () => Promise<Plan>): Promise<boolean> => {
		this.error = '';
		try {
			await this.mutate(fn);
			return true;
		} catch (e) {
			this.error = say(e);
			return false;
		}
	};

	#changed() {
		this.rev++;
		void shopping.sync();
	}

	/** Henter ugen med det id, ellers den aktuelle. 404 betyder, at der ingen madplan er. */
	async load(id?: number): Promise<void> {
		this.error = '';
		try {
			this.plans = await weekApi.list();
			await this.#ordered(() => (id ? weekApi.get(id) : weekApi.current(clock.today)));
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) {
				// Ugen findes ikke længere (slettet på en anden telefon): vis den aktuelle.
				if (id) return this.load();
				this.plan = null;
			} else this.error = say(e);
		} finally {
			this.loaded = true;
		}
	}

	/**
	 * Henter ugen, der dækker datoen. Datoen vinder over `id`, hvis de ikke passer
	 * sammen. Dækker ingen uge datoen, vises den aktuelle, og svaret er false.
	 */
	async loadForDate(date: string, id?: number): Promise<boolean> {
		this.error = '';
		let hit: PlanBrief | undefined;
		try {
			this.plans = await weekApi.list();
			const covers = (p: PlanBrief) => p.start_date <= date && date <= p.end_date;
			hit = this.plans.find((p) => p.id === id && covers(p)) ?? this.plans.find(covers);
		} catch (e) {
			this.error = say(e);
			this.loaded = true;
			return false;
		}
		await this.load(hit?.id);
		return !!hit && !!this.day(date);
	}

	/** Forslag til indkøbsdag: dagen efter den nyeste uge, ellers i dag. */
	suggestedStart(): string {
		const latest = this.plans[0];
		if (latest && latest.end_date >= clock.today) return isoDate(addDays(parseDate(latest.end_date), 1));
		return clock.today;
	}

	/** Laver en ny uge og viser den. Kaster serverens sætning, hvis ugen overlapper en anden. */
	async create(startDate: string): Promise<Plan> {
		const p = await this.#ordered(() => weekApi.create(startDate));
		this.#changed();
		this.plans = await weekApi.list().catch(() => this.plans);
		return p;
	}

	/** Sletter ugen, når der er sagt ja, og viser så den aktuelle. Svarer true, når den er slettet. */
	async remove(): Promise<boolean> {
		const plan = this.plan;
		if (!plan || !(await confirmDialog(`Slet ugen ${periodLong(plan.start_date, plan.end_date)}?`, 'Slet'))) return false;
		this.error = '';
		try {
			await weekApi.remove(plan.id);
		} catch (e) {
			this.error = say(e);
			return false;
		}
		this.plan = null;
		this.#changed();
		await this.load();
		return true;
	}

	distribute(): Promise<boolean> {
		const id = this.plan?.id;
		if (!id) return Promise.resolve(false);
		return this.run(() => weekApi.distribute(id, clock.today));
	}

	/** Spørger, før en ret på dagen bliver erstattet. */
	async mayReplace(d: Day): Promise<boolean> {
		return !d.meal || (await confirmDialog(`Erstat ${d.meal.title} ${weekdayLower(d.date)}?`, 'Erstat'));
	}

	/** Lægger et ønske på en dag. Står der allerede en ret, spørges der først. */
	async placeWish(wishId: number, d: Day): Promise<boolean> {
		const plan = this.plan;
		if (!plan || !(await this.mayReplace(d))) return false;
		return this.run(() => planApi.setSlot(plan, d.date, false, { kind: 'ønske', wish_id: wishId }));
	}
}
