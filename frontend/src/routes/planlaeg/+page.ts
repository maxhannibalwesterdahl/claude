import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Planlæg er flyttet til Uge. Gamle links og bogmærker beholder ?plan= og ?dag=.
export const load: PageLoad = ({ url }) => {
	redirect(307, '/' + url.search);
};
