import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// Under udvikling: backend kører på 8000 (se README).
		proxy: { '/api': 'http://127.0.0.1:8000' }
	}
});
