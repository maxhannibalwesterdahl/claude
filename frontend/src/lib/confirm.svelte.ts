interface ConfirmRequest {
	message: string;
	/** Teksten på knappen, der bekræfter (fx "Slet"). */
	confirmLabel: string;
	/** Sletter eller overskriver noget: knappen bliver rød. */
	danger: boolean;
	resolve: (ok: boolean) => void;
}

/** Spørgsmålet, der vises lige nu (se ConfirmDialog.svelte i layoutet). */
export const confirmState = $state<{ request: ConfirmRequest | null }>({ request: null });

/** Appens egen "er I sikre?" i stedet for browserens confirm(). Svarer true ved ja. */
export function confirmDialog(message: string, confirmLabel: string, danger = true): Promise<boolean> {
	confirmState.request?.resolve(false);
	return new Promise((resolve) => (confirmState.request = { message, confirmLabel, danger, resolve }));
}
