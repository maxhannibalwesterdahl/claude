<script lang="ts">
	import ScreenHeader from '$lib/ui/ScreenHeader.svelte';
</script>

<main>
	<ScreenHeader title="Privatliv" eyebrow="Madplan" back="/" />
	<div class="pad text">
		<h2 class="sl">Hvad gemmer Madplan?</h2>
		<p>
			Brugernavn og kodeord (kodeordet gemmes krypteret, så ingen kan læse det), jeres madplaner,
			indkøbslister, opskrifter, noter og påmindelser. Hvis I slår beskeder til, gemmes
			telefonens adresse til beskeder. Appen bruger ingen reklamer og ingen sporing.
		</p>
		<h2 class="sl">Hvem kan se det?</h2>
		<p>
			Planer, indkøb, noter og indstillinger er kun for jeres egen familie. Opskrifter deles
			med de andre familier i Madplan, så alle kan finde og bruge dem; jeres noter om dem deles ikke.
			Den, der driver Madplan, kan teknisk set se alt, der ligger i databasen, og bruger det kun til
			drift og fejlsøgning.
		</p>
		<h2 class="sl">Jeres rettigheder</h2>
		<p>
			Familiens administrator kan under <b>Ryd op → Familie</b> hente alle familiens data som en fil og
			slette familien med alt, hvad den har lagt ind. Opskrifter, andre familier bruger, bliver
			liggende uden ejer; alt andet slettes for altid. Sletningen kan ikke fortrydes.
		</p>
		<h2 class="sl">Kopier</h2>
		<p>
			Der tages natlige sikkerhedskopier af hele databasen. Slettede data forsvinder fra kopierne,
			når de ældste er rullet ud (højst et par uger).
		</p>
	</div>
</main>

<style>
	.text p {
		max-width: 60ch;
		margin: 6px 0 14px;
	}
</style>
