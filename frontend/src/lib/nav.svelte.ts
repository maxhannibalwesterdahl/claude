/**
 * inApp: om brugeren er kommet til siden inde fra appen (så "Tilbage" kan gå tilbage).
 * week: adressen på den uge, Uge sidst viste ("/" eller "/?plan=ID"). Fanen Uge
 * går dertil, så man kommer tilbage til den uge, man var i gang med.
 */
export const navState = $state({ inApp: false, week: '/' });
