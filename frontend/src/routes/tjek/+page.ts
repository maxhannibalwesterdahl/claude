import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Tjek er flyttet ind under Ryd op. Gamle links og bogmærker sendes videre.
export const load: PageLoad = () => {
	redirect(307, '/rydop');
};
