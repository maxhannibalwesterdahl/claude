import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Dagen åbnes nu som et ark på Uge. Gamle links og bogmærker ender der.
export const load: PageLoad = ({ params }) => {
	redirect(307, `/?dag=${encodeURIComponent(params.dato)}`);
};
