/** Svaret: bekræft, det andet valg (fx "Tilføj som ekstra ret") eller annullér (null). */
export type ConfirmAnswer = 'ok' | 'alt' | null;

interface ConfirmRequest {
	message: string;
	/** Teksten på knappen, der bekræfter (fx "Slet"). */
	confirmLabel: string;
	/** Et andet valg end at bekræfte (fx "Tilføj som ekstra ret"). Tom: kun ja og nej. */
	altLabel?: string;
	/** Sletter eller overskriver noget: knappen bliver rød. */
	danger: boolean;
	resolve: (answer: ConfirmAnswer) => void;
}

/** Spørgsmålet, der vises lige nu (se ConfirmDialog.svelte i layoutet). */
export const confirmState = $state<{ request: ConfirmRequest | null }>({ request: null });

function ask(request: Omit<ConfirmRequest, 'resolve'>): Promise<ConfirmAnswer> {
	confirmState.request?.resolve(null);
	return new Promise((resolve) => (confirmState.request = { ...request, resolve }));
}

/** Appens egen "er I sikre?" i stedet for browserens confirm(). Svarer true ved ja. */
export async function confirmDialog(message: string, confirmLabel: string, danger = true): Promise<boolean> {
	return (await ask({ message, confirmLabel, danger })) === 'ok';
}

/** Som confirmDialog, men med et valg mere. Svarer 'ok', 'alt' eller null (annullér). */
export function chooseDialog(message: string, confirmLabel: string, altLabel: string): Promise<ConfirmAnswer> {
	return ask({ message, confirmLabel, altLabel, danger: false });
}
