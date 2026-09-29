/** Fremgangsmåde delt op i afsnit. Korte trin uden punktum er overskrifter ("Mornaysauce"). */
export function groupSteps(steps: string[]): { title: string; steps: string[] }[] {
	const isHeading = (s: string) => s.length <= 40 && !/[.!?:]$/.test(s) && s.split(' ').length <= 5;
	const out: { title: string; steps: string[] }[] = [];
	for (const step of steps) {
		if (isHeading(step)) out.push({ title: step, steps: [] });
		else if (out.length) out[out.length - 1].steps.push(step);
		else out.push({ title: '', steps: [step] });
	}
	return out;
}
