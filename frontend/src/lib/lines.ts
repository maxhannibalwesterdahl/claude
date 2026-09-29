import type { Line } from './types';

export interface LineGroup<T> {
	name: string;
	lines: T[];
}

/** Saml linjer i afsnit i den rækkefølge, afsnittene optræder. */
export function groupLines<T extends Pick<Line, 'group'>>(lines: T[]): LineGroup<T>[] {
	const groups: LineGroup<T>[] = [];
	for (const line of lines) {
		const last = groups.at(-1);
		if (last && last.name === line.group) last.lines.push(line);
		else groups.push({ name: line.group, lines: [line] });
	}
	return groups;
}
