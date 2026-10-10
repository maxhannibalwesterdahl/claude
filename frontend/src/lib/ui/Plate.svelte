<script lang="ts">
	interface Props {
		/** Opskriftens billede. */
		src?: string | null;
		/** Opskriftens id eller titel. Vælger farverne, når der ikke er et billede. */
		seed?: string | number;
		/** Diameter i px. */
		size?: number;
		lazy?: boolean;
		/** 'no-referrer' til billeder fra andre sider (søgeresultater). */
		referrerpolicy?: ReferrerPolicy;
	}
	let { src = null, seed = '', size = 40, lazy = false, referrerpolicy }: Props = $props();

	// Designets otte tallerkener. Data kender ikke rettens type, så farverne er
	// tilfældige, men altid de samme for den samme opskrift.
	const PALETTES = [
		['#C98A3C', '#B8792F', '#E07B39', '#7A9B4A'],
		['#8A3B22', '#A6452A', '#E9C46A', '#4E8B46'],
		['#7A4A2A', '#D8452E', '#F2D16B', '#6FA04A'],
		['#E0A22E', '#C9861F', '#F1C55A', '#FBFAF4'],
		['#F08A6B', '#EE7B5C', '#3F7D45', '#5B9A56'],
		['#D8452E', '#C73A25', '#E8563D', '#F3E9D2'],
		['#B5482A', '#E3B04B', '#F1D9A0', '#4E8B46'],
		['#7B4B2C', '#6C3F24', '#F0DC9A', '#5B9A56']
	];

	function pick(seed: string | number): string[] {
		let h = 0;
		for (const ch of String(seed)) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
		return PALETTES[h % PALETTES.length];
	}
	const colors = $derived(pick(seed));

	// Et billede, der ikke kan hentes, giver den tegnede tallerken i stedet.
	let failed = $state<string | null>(null);
</script>

{#if src && failed !== src}
	<span class="plate photo" style:width="{size}px" style:height="{size}px" style:padding="{size * 0.07}px" aria-hidden="true">
		<img {src} alt="" loading={lazy ? 'lazy' : undefined} {referrerpolicy} onerror={() => (failed = src)} />
	</span>
{:else}
	<span
		class="plate drawn"
		style:width="{size}px"
		style:height="{size}px"
		style:--a={colors[0]}
		style:--b={colors[1]}
		style:--c={colors[2]}
		style:--d={colors[3]}
		aria-hidden="true"
	></span>
{/if}

<style>
	.plate {
		flex: none;
		display: block;
		border-radius: 50%;
	}
	.drawn {
		box-shadow: 0 1px 3px rgba(40, 38, 30, 0.18);
		background:
			radial-gradient(circle at 38% 40%, var(--a) 0 15%, transparent 16%),
			radial-gradient(circle at 62% 36%, var(--b) 0 14%, transparent 15%),
			radial-gradient(circle at 50% 65%, var(--a) 0 15%, transparent 16%),
			radial-gradient(circle at 73% 62%, var(--c) 0 9%, transparent 10%),
			radial-gradient(circle at 29% 66%, var(--d) 0 8%, transparent 9%),
			radial-gradient(circle, var(--plate) 0 58%, var(--rim) 59% 100%);
	}
	/* Billedet ligger på tallerkenen med kanten udenom. */
	.photo {
		background: var(--plate);
		box-shadow:
			0 1px 3px rgba(40, 38, 30, 0.18),
			inset 0 0 0 1px var(--rim);
	}
	img {
		display: block;
		width: 100%;
		height: 100%;
		border-radius: 50%;
		object-fit: cover;
	}
</style>
