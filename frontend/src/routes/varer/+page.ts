import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Varer er flyttet ind under Ryd op. Gamle links og bogmærker sendes videre.
export const load: PageLoad = ({ url }) => {
	redirect(307, url.searchParams.get('fane') === 'basis' ? '/rydop/basisvarer' : '/rydop/varer');
};
