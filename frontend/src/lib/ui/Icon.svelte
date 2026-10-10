<script lang="ts">
	import { ICONS, type IconName } from './icons';

	interface Props {
		name: IconName;
		size?: number;
		stroke?: number;
	}
	let { name, size = 18, stroke = 2 }: Props = $props();
</script>

<!-- Altid skjult for skærmlæsere: knappen eller linket omkring bærer teksten. -->
<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill={name === 'play' ? 'currentColor' : 'none'}
	stroke="currentColor"
	stroke-width={stroke}
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"><path d={ICONS[name]} /></svg
>

<style>
	svg {
		display: block;
		flex: none;
	}
</style>
