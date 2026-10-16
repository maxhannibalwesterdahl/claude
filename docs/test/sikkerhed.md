# Sikkerhedstest (whitehat), 16-10-2026

Gren `rolig`. Testet mod egen lokal instans (`127.0.0.1:8103`, egen `DATA_DIR`,
egen `APP_SECRET`) plus kodegennemgang. Driften og prøven er ikke kontaktet.
Ingen filer ændret (kun denne rapport er ny). Serveren er stoppet, og den
midlertidige datamappe er slettet.

## 1. Konklusion

**Ikke klar til go-live med flere familier.** Appen har i dag ingen
familie-/husstandsadskillelse overhovedet: `docs/flere-familier.md` er kun et
design ("ikke bygget"), og hverken modeller, migrationer eller ruter kender
begrebet. Alle indloggede brugere kan læse, rette og slette alt, som andre
brugere har lavet, og påmindelser sendes til alle abonnerede telefoner
(S-01, S-02). `madplan-admin` har heller ingen måde at oprette en familie på,
så "to brugere i to familier" kunne kun testes som to brugere i samme
database. Det er præcis den situation, de to familier vil være i.

Ud over det er grundlaget solidt for en lille, lukket gruppe: argon2,
signeret HttpOnly-cookie, alle ruter bag login, ingen rå SQL, ingen
`{@html}`, god SSRF-filtrering, billedtjek på indhold, ingen hemmeligheder i
git, `/docs` og `/openapi.json` er slået fra, og containeren kører ikke som root. Manglende
sikkerhedsheadere, svag rate-limit-forankring og logout uden server-side
tilbagekaldelse bør rettes sammen med familie-arbejdet.

Antal fund: **1 kritisk, 1 høj, 5 mellem, 7 lav.**

## 2. Fund

| ID | Alvor | Titel | Sted |
|---|---|---|---|
| S-01 | Kritisk | Ingen adskillelse mellem familier: alle brugere ser/ændrer/sletter alt | `api/*.py` (alle ruter), `models.py` |
| S-02 | Høj | Påmindelser sendes til alle telefoner; push-abonnement kan overtages | `reminders.py:87`, `api/reminders.py:112` |
| S-03 | Mellem | Alle kan ændre det fælles katalog (varer, aliaser) uden historik | `api/ingredients.py:79-107`, `api/recipes.py:352-382` |
| S-04 | Mellem | Login-begrænsning kan omgås/misbruges via `X-Forwarded-For` | `api/deps.py:41`, `api/auth_routes.py:11-18`, `auth.py:67` |
| S-05 | Mellem | Ingen sikkerhedsheadere (CSP, X-Frame-Options, nosniff, HSTS, Referrer-Policy) | `api/__init__.py` |
| S-06 | Mellem | SSRF-tjek kan omgås med DNS rebinding (tjek og forbindelse slår op hver for sig) | `importer.py:60-72, 87-103` |
| S-07 | Mellem | Logout ugyldiggør ikke sessionen; ingen nulstilling i appen; lokal indkøbsliste overlever logout | `api/auth_routes.py:41`, `rydop/+page.svelte:86`, `shopping.svelte.ts:8` |
| S-08 | Lav | Uautentificeret 500 ved cookie med ikke-ASCII tegn | `auth.py:60` |
| S-09 | Lav | 500 ved meget store id'er i stien | alle `/{id}`-ruter |
| S-10 | Lav | Ingen kvote på billeder/opskrifter; importerede billeder indholdstjekkes ikke | `api/recipes.py:211-232`, `importer.py:225-240` |
| S-11 | Lav | `Secure` på cookien afhænger af, at headeren `X-Forwarded-For` findes | `api/auth_routes.py:30` |
| S-12 | Lav | Container og afhængigheder kunne hærdes mere | `Dockerfile`, `deploy/compose.yaml`, `requirements.lock` |
| S-13 | Lav | Push-endpoint-tilladelsen er bred, og enhver bruger kan sætte VAPID-afsenderen | `push.py:26-37`, `api/reminders.py:121-128` |
| S-14 | Lav | Importens fejlbeskeder afslører, om et internt værtsnavn findes | `importer.py:62-68` |

## 3. Detaljer

Fælles opsætning til PoC'erne:

```sh
cd backend
export DATA_DIR=$(mktemp -d) APP_SECRET=$(openssl rand -hex 32) STATIC_DIR=../frontend/build
printf 'pw-alice-longenough\npw-alice-longenough\n' | .venv/bin/madplan-admin create-user alice
printf 'pw-bob-longenough\npw-bob-longenough\n'     | .venv/bin/madplan-admin create-user bob
.venv/bin/uvicorn --factory madplan.api:create_app --port 8103 &
B=http://127.0.0.1:8103; J='Content-Type: application/json'
curl -s -c a.jar -H "$J" -d '{"username":"alice","password":"pw-alice-longenough"}' $B/api/login
curl -s -c b.jar -H "$J" -d '{"username":"bob","password":"pw-bob-longenough"}'     $B/api/login
```

### S-01 Kritisk: ingen familieadskillelse

Ingen tabel har `household_id`; `CurrentUser` bruges kun som "er logget ind"
(`_: CurrentUser`), aldrig til at filtrere. `list_plans` (`api/plans.py:296`),
`list_recipes`, `get_shopping`, `choose_plan` osv. læser alt i databasen.
Opslag på id (`session.get(Model, id)`) tjekker aldrig ejer. Det gælder
opskrifter, planer, måltider, ønskeliste, "har hjemme"-markeringer,
påmindelser, indkøbsliste og egne varer, billeder (`/api/images/{navn}`
kræver kun login), afdelingsrækkefølge (`Setting` er global) og push.

PoC (alice har lavet opskrift 1 og plan 1):

```sh
curl -s -b a.jar -H "$J" -d '{"title":"Alices","child_note":"barn: allergi","ingredients":[{"raw":"2 løg"}]}' $B/api/recipes
curl -s -b a.jar -H "$J" -d '{"start_date":"2026-10-19"}' $B/api/plans
# bob (anden "familie"):
curl -s -b b.jar $B/api/recipes/1                      # 200, læser alt inkl. child_note
curl -s -b b.jar $B/api/plans                          # 200, alices planer
curl -s -b b.jar -X PUT -H "$J" -d '{"title":"HACKED","ingredients":[]}' $B/api/recipes/1   # 200, overskrevet
curl -s -b b.jar -X DELETE $B/api/plans/1 -w '%{http_code}\n'                                # 204, alices plan slettet
curl -s -b a.jar $B/api/plans/1                        # 404 hos alice: planen er væk
```

Alle tre handlinger lykkedes (læse, ændre, slette). Samme mønster gælder de
øvrige id-ruter, fordi ingen af dem har ejerskab at tjekke mod: `/api/meals/{id}`
(PATCH/DELETE/move), `/api/meals/{id}/reminders`, `/api/reminders/{id}`,
`/api/plans/{id}/slots|wishlist`, `/api/wishlist/{id}`,
`/api/shopping/extras/{id}`, `/api/recipes/{id}/image` (POST/DELETE),
`/api/lines/{id}/confirm|main|ignore`. Desuden lækker `409` ved opskriftsimport
(`_check_duplicate`) id'et på en andens opskrift.

Forventet: 404 for alt, der tilhører en anden familie (designet i
`flere-familier.md` §6). Forslag: byg `CurrentHousehold` som beskrevet, tilføj
`household_id` på `plan`, `shopping_extra`, `setting`, og lad hver rute filtrere
på det. Billeder bør serveres via opskriften (kontrollér, at navnet hører til
en opskrift, som familien må se). Skriv test-matrixen fra §6 *før* ruterne
omskrives. Bemærk også `choose_plan`/`pick_current`/`create_plan`
(`api/plans.py:286, 310`): de leder i *alle* planer, så en families plan
blokerer en andens ("Overlapper planen"), og "nuværende plan" bliver
tilfældig. Tilføj et `madplan-admin create-household`/`--household` til CLI'en.

### S-02 Høj: påmindelser til alle telefoner, abonnement kan overtages

`reminders.targets()` returnerer *alle* `PushSubscription` uanset bruger, og
`send_due` sender hver påmindelse til dem alle. Familie A's "husk kød op af
fryseren" (med ret-titel) lander på familie B's telefoner. `subscribe` slår op
på `endpoint` alene og overskriver `user_id`, `p256dh`, `auth`
(`api/reminders.py:112-120`), så en bruger, der kender en andens endpoint, kan
overtage det.

```sh
E='{"endpoint":"https://fcm.googleapis.com/fcm/send/abc","keys":{"p256dh":"BAAA","auth":"AAAA"}}'
curl -s -b a.jar -H "$J" -d "$E" $B/api/push/subscriptions -w '%{http_code}\n'   # 204
curl -s -b b.jar -H "$J" -d "$E" $B/api/push/subscriptions -w '%{http_code}\n'   # 204
sqlite3 $DATA_DIR/madplan.db 'select id,user_id,endpoint from push_subscription'
# 2|2|https://fcm.googleapis.com/fcm/send/abc   <- user_id skiftet fra alice til bob
```

Forslag: filtrér mål på familien for den plan, påmindelsen hører til; afvis
(409) en eksisterende endpoint, der tilhører en anden bruger, eller slet først
den gamle.

### S-03 Mellem: fælles katalog kan vandaliseres

Ingredienser og aliaser deles bevidst (designet), men enhver bruger kan i dag
oprette/ændre varer (`PUT /api/ingredients/{id}`, afdeling, g/stk) og via
`/api/lines/{id}/confirm` lære et alias, der ændrer matchningen for alle
familiers opskrifter. Der er hverken historik, fortryd eller rolle.

```sh
curl -s -b b.jar -X PUT -H "$J" -d '{"name":"løg","department":"Frost","pantry":true}' $B/api/ingredients/1
```

Forslag: byg `catalog_change` + fortryd (§3 i designet) før åbning, eller
begræns skrivning til admin indtil da.

### S-04 Mellem: login-begrænsning

`client_ip` bruger sidste led i `X-Forwarded-For`. Det er kun sikkert, hvis
Tailscale Funnel/serve *overskriver eller tilføjer* headeren i alle tilfælde.
Det kunne ikke verificeres uden at røre driften.

Lokalt (ingen proxy) kan grænsen omgås, og det modsatte kan misbruges til at
udelukke andre:

```sh
# 8 forkerte forsøg, hvert med ny "IP": alle 401, aldrig 429
for i in $(seq 1 8); do curl -s -o /dev/null -w '%{http_code} ' -H "X-Forwarded-For: 10.0.0.$i" -H "$J" \
  -d '{"username":"alice","password":"x"}' $B/api/login; done
# uden header: 401 401 401 401 401 429 429
# udelukke en kendt IP (offerets): 5 forsøg med X-Forwarded-For: 203.0.113.9 giver 429 til den adresse
```

Andre svagheder: kun pr. IP (ingen grænse pr. brugernavn, så en
distribueret gætning på ét brugernavn er mulig; kodeord er dog ≥ 12 tegn);
`_attempts` er en ubegrænset dict med nøgle pr. set "IP" og vokser med
falske `X-Forwarded-For`-værdier (langsom hukommelseslæk); den globale
`HASH_GATE` (2 samtidige) kan holdes optaget af en angriber, så ægte logins får
429 (login-DoS). Argon2-tid er ens for kendt/ukendt bruger (~30 ms begge, målt),
så ingen timing-orakel.

Forslag: tilføj en grænse pr. brugernavn (fx 10/time) ud over pr. IP; ryd
`_attempts` periodisk; verificér i prøven, hvad Funnel faktisk sætter
(`curl -H 'X-Forwarded-For: 1.1.1.1'` mod prøven og se serverens log) før
go-live, og overvej at kræve, at headeren har præcis forventet antal led.

### S-05 Mellem: sikkerhedsheadere mangler

```sh
curl -si $B/ | head      # ingen Content-Security-Policy, X-Frame-Options, X-Content-Type-Options,
                         # Referrer-Policy, Strict-Transport-Security eller Permissions-Policy
```

Følger: appen kan lægges i en iframe (clickjacking på login/slet-knapper), og
der er intet forsvar i dybden, hvis der engang kommer XSS. Svelte-skabelonerne
bruger ingen `{@html}`, så der er ingen kendt XSS i dag. CORS er ikke
aktiveret (preflight giver 405, ingen `Access-Control-*`): korrekt.
Forslag: en middleware (eller `serve.json`/Tailscale-headers) med
`Content-Security-Policy: default-src 'self'; img-src 'self' data: https:;
frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin`, `Strict-Transport-Security: max-age=31536000`.
`img-src https:` kræves, fordi søgeresultaters billeder hentes direkte fra
Valdemarsro/nemlig.

### S-06 Mellem: DNS rebinding omgår SSRF-filteret

`check_url` slår værten op og afviser ikke-offentlige adresser, men `httpx`
slår derefter værten op *igen* ved forbindelsen. En angriber-styret DNS-server
med TTL 0 kan svare offentligt første gang og `127.0.0.1`/`169.254.169.254`
anden gang. Direkte adresser, `localhost`, `[::1]`, decimal/hex-IP,
`::ffff:127.0.0.1`, `file://`, `ftp://`, `10/8`, `192.168/16`, `100.100.100.100`
blev alle afvist rent (se §4). PoC af selve vinduet (modellerer en rebinding-
DNS ved at lade `getaddrinfo` svare forskelligt første og andet kald):

```sh
cd backend && .venv/bin/python - <<'EOF'
import socket; from madplan import importer
real=socket.getaddrinfo; n={"c":0}
def fake(h,p,*a,**k):
    if h=="rebind.example":
        n["c"]+=1; ip="93.184.216.34" if n["c"]==1 else "127.0.0.1"
        return [(socket.AF_INET,socket.SOCK_STREAM,6,"",(ip,p))]
    return real(h,p,*a,**k)
socket.getaddrinfo=fake
print(importer.fetch("http://rebind.example:9999/")[:60])   # med python3 -m http.server 9999 --bind 127.0.0.1 kørende
EOF
# udskriver indholdet fra 127.0.0.1
```

Udnyttelse kræver en domæne under angriberens kontrol, og indholdet vises kun,
hvis det ligner en opskrift (JSON-LD eller recipe-scrapers) – i praksis blind,
men kan ramme interne tjenester (Tailscale-API'er, `app`-containeren,
metadata). Forslag: slå op én gang, og forbind til den fundne IP (httpx-transport
med fast IP og `Host`/SNI sat til værtsnavnet), eller brug en
`httpx.HTTPTransport` med egen resolver, der gentager `is_global`-tjekket på den
IP, der faktisk forbindes til. Billeddownload og redirects går gennem samme `_get`
og er dækket af samme rettelse. Redirects kontrolleres pr. led (`follow_redirects=False`,
5 led): i orden.

### S-07 Mellem: session og logout

Cookien er stateless (`bruger.version.udløb.hmac`, 90 dage). `/api/logout`
sletter kun cookien i browseren; serveren ugyldiggør intet. En kopieret/stjålet
cookie virker i 90 dage, uanset logout:

```sh
cp a.jar a2.jar
curl -s -b a.jar -X POST $B/api/logout        # 204
curl -s -b a2.jar $B/api/me                   # stadig 200 {"id":1,"username":"alice"}
```

Der er ingen "skift kodeord" i appen; kun `madplan-admin set-password` øger
`session_version`. Familier uden CLI-adgang kan derfor ikke selv afbryde en
stjålet session. Desuden rydder frontend ikke `localStorage['madplan.indkob.v1']`
ved logout (`rydop/+page.svelte:86`), så næste bruger på samme enhed kan se den
forrige families indkøbsliste, og afventende ændringer kan synkes ind på den
nye brugers konto. Forslag: øg `session_version` ved logout (logger alle
enheder ud) eller giv sessionen et tilfældigt id i en tabel; ryd `localStorage`
ved logout og ved skift af bruger-id; tilføj skift af kodeord i appen.

Cookie-attributter ellers: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` 90
dage; `Secure` kun bag proxy (S-11). Signering er HMAC-SHA256 med
`compare_digest`; forfalskede/afkortede/ændrede cookies giver 401.

### S-08 Lav: 500 ved ikke-ASCII cookie

`hmac.compare_digest(parts[3], …)` kaster `TypeError` for ikke-ASCII `str`.

```sh
curl -s -o /dev/null -w '%{http_code}\n' -H 'Cookie: madplan_session=1.1.9999999999.é' $B/api/me   # 500
```

Ingen datalæk (kun stakspor i serverlog), men uautentificeret 500. Forslag:
sammenlign `.encode()`-bytes, eller fang `TypeError` i `read_session`.

### S-09 Lav: 500 på store id'er

```sh
curl -s -b a.jar $B/api/recipes/99999999999999999999     # "Internal Server Error"
```

SQLite `OverflowError`. Forslag: `Path(ge=1, le=2**31)` på id-parametre, eller en
generel exception handler.

### S-10 Lav: billeder og kvoter

Upload (`POST /api/recipes/{id}/image`) er i orden: 8 MB-grænse (`413`),
filtype efter magic bytes (HTML med `image/jpeg` som content-type afvist
`422`), serversat UUID-filnavn (klientens `filename=../../evil.jpg` ignoreres),
sti-gennemløb afvist (`..%2f`, `%2e%2e%2f`, `..`, `.x` giver 404). Men:

- Ingen kvote pr. bruger/familie og ingen grænse for antal opskrifter: en
  bruger kan fylde disken (8 MB pr. kald, hvert på ny opskrift).
- Importerede billeder (`download_image`) vurderes kun på serverens
  `Content-Type`, ikke på indholdet; `avif` accepteres her, men ikke ved upload.
  En fjendtlig side kan få vilkårligt indhold gemt som `.jpg`. Indholdet serveres
  med `image/*` og uden `nosniff` (S-05); browsere sniffer ikke `image/*` til HTML,
  så det er ikke udnytteligt i dag.
- Billednavne er 128-bit tilfældige (ikke gættelige), men kræver kun login (S-01).

```sh
printf '\xff\xd8\xff<html><script>alert(1)</script></html>' > poly.jpg
curl -s -b a.jar -F 'file=@poly.jpg;filename=../../evil.jpg' $B/api/recipes/1/image   # 200 (accepteres: magic bytes)
```

Forslag: kontrollér magic bytes også ved import, tilføj `nosniff`, og tæl
bytes pr. familie.

### S-11 Lav: Secure-flag

`secure = request.url.scheme == "https" or "x-forwarded-for" in request.headers`
(`api/auth_routes.py:30`). Bag Funnel er headeren der, og cookien får `Secure`
(målt med `-H 'X-Forwarded-For: 1.2.3.4'`); uden header over http får den ikke.
Svagt koblet, men uden praktisk risiko, så længe appen kun nås via proxyen.
Forslag: styr det med en miljøvariabel (`COOKIE_SECURE=1`) eller
`X-Forwarded-Proto`.

### S-12 Lav: container og afhængigheder

- OK: appen kører som `app` (uid 1000), ingen porte publiceret ud af Docker,
  `mem_limit: 512m`, `pids_limit: 256`, logrotation, healthcheck.
- Mangler: `read_only: true` med tmpfs, `cap_drop: [ALL]`,
  `security_opt: [no-new-privileges:true]`, cpu-grænse. Basisbilleder er ikke
  fastlåst (`python:3.12-slim`, `node:24-slim`, `tailscale/tailscale:stable`);
  `requirements.lock` har ingen hashes (`pip install --require-hashes`).
- `--forwarded-allow-ips "*"` er ok, fordi porten kun er nået via
  tailscale-containeren, men bør kommenteres som antagelse (prøve og drift deler
  `serve.json`).
- Python-afhængigheder (fastapi 0.141.1, starlette 1.7.0, uvicorn 0.54.0, httpx
  0.28.1, cryptography 50.0.2, argon2-cffi 25.1.0, python-multipart 0.0.32,
  recipe-scrapers 15.12.0, lxml 6.1.3, sqlalchemy 2.1.1): alle er fastlåste og
  nyere end det, jeg kender kendte sårbarheder for. Jeg kan ikke slå CVE'er op
  uden netværk og har ikke `pip-audit`; kør `pip-audit -r requirements.lock` i CI.
- Frontend: `package.json` har kun `devDependencies` (statisk build, ingen
  runtime-npm). `npm audit --omit=dev --offline` svarede "found 0
  vulnerabilities" (kun cachede data; sammenlign med en online-kørsel).
- Git: se §4, ingen hemmeligheder i historikken.

### S-13 Lav: push-endpoint og VAPID-afsender

`allowed_endpoint` tillader alt under `googleapis.com`, fx
`storage.googleapis.com/<bucket>/…`, så serveren vil POSTe krypterede,
signerede beskeder dertil (fx til en bucket, brugeren selv råder over). Ikke
SSRF mod interne adresser (kun https mod disse værter), men bredere end nødvendigt.
Desuden kan enhver bruger sætte VAPID-`sub` (`push_subject`) ved at sende en
`Origin: https://…`-header til `/api/push/subscriptions` (målt: `Setting
push_subject = https://evil.example`). Det er en global indstilling; med flere
familier kan den ændres af en hvilken som helst bruger.
Forslag: tillad kun `fcm.googleapis.com`, `*.push.apple.com`,
`*.push.services.mozilla.com`, `*.notify.windows.com`; sæt afsenderen fra en
miljøvariabel (`PUBLIC_URL`).

VAPID-nøglen genereres første gang og skrives atomisk til `DATA_DIR/vapid.pem`
(`os.replace`), men med standardrettigheder (umask), ikke `0600`. Forslag:
`os.chmod(tmp, 0o600)`. Nøglen ligger i data-volumen og er ikke i git.

### S-14 Lav: DNS-orakel i import

`/api/recipes/import` svarer "Linket peger på en lokal adresse" for et
værtsnavn, der findes internt, og "Kan ikke finde siden …" for et, der ikke gør. En
bruger kan kortlægge interne navne.

```sh
curl -s -b a.jar -H "$J" -d '{"url":"http://printer.local/"}' $B/api/recipes/import
curl -s -b a.jar -H "$J" -d '{"url":"http://nonexistent.invalid/"}' $B/api/recipes/import
```

Forslag: samme besked for begge.

## 4. Tjekket og fundet i orden

- **Autentificering:** alle `/api/*`-ruter undtagen `/api/login` og `/api/health`
  giver 401 uden cookie (recipes, plans, shopping, ingredients, meta, review,
  suggestions, push/key, images). Ukendte `/api/...` giver 404 JSON.
- **Kodeord:** argon2id (standardparametre), min. 12 tegn, ens svartid for
  kendt/ukendt bruger (~30 ms), generisk fejlbesked, begrænset samtidighed
  (`HASH_GATE`) mod RAM-udmattelse, brugernavn og kodeord har maksimal længde.
- **Cookie:** HMAC-SHA256, konstant-tids-sammenligning, udløb tjekkes,
  `session_version` ved kodeordsskift via CLI. Forfalskning uden `APP_SECRET`
  kunne ikke lade sig gøre; `APP_SECRET` kræves ≥ 32 tegn ved start.
- **CSRF:** `SameSite=Lax` plus at alle muterende JSON-ruter kræver
  `Content-Type: application/json` (en `text/plain`-POST med `Origin:
  https://evil.example` giver 422). Ingen muterende GET-ruter fundet.
  Upload er multipart (cross-site form-POST sender ikke Lax-cookien). Ingen CORS
  (ingen `Access-Control-*`-headere, preflight 405).
- **SSRF (import):** `127.0.0.1`, `localhost`, `[::1]`, `2130706433`, `0x7f.1`,
  `0`, `169.254.169.254`, `[::ffff:127.0.0.1]`, `user@127.0.0.1`, `10.0.0.1`,
  `192.168.1.1`, `100.100.100.100` blev alle afvist; `file://` og `ftp://` afvist
  på skema. Redirects tjekkes pr. led (maks. 5), siden begrænses til 5 MB og
  billedet til 8 MB, `Content-Type` skal være billede. Søgning (`/api/search/*`)
  går kun til faste værter (`valdemarsro.dk`, `nemlig.com`) med brugerens tekst
  som `params` (ingen URL-injektion); `redirects` følges dog i klienten uden
  tjek, men målet styres af disse to sider. Rest: S-06 og S-14.
- **Injection:** ingen rå SQL i appen (kun `PRAGMA` i `db.py`), alt går via
  SQLAlchemy med bundne parametre; søgning bruger `icontains`. Ingen brugerinput
  havner i svar-headere (ingen header-injektion), `Origin` gemmes kun som
  indstilling (S-13).
- **XSS:** `grep` efter `{@html}`, `innerHTML`, `document.write`, `eval` i
  `frontend/src` giver ingen forekomster. Svelte escaper tekst. `source_url`
  afvises, hvis den ikke starter med `http(s)://` (`javascript:` giver 422),
  og frontend tjekker skemaet igen før `href`. Eksterne links har
  `rel="noopener noreferrer"`. Opskriftstitler med `<img onerror>` og `<script>` i
  ingredienser gemmes som tekst og vises escaped.
- **Sti-gennemløb:** `/api/images/..%2f..%2fmadplan.db`, `%2e%2e%2f`, `..`, `.x`
  giver 404; statiske filer kontrolleres med `is_relative_to` (`/../../etc/passwd`
  og kodede varianter returnerer blot `index.html`).
- **Fejlmeddelelser:** valideringsfejl er standard FastAPI-422 (ekkoer kun
  eget input), ingen stakspor i svar; `/docs`, `/redoc`, `/openapi.json` er
  slået fra (returnerer SPA'ens `index.html`, ikke skemaet).
- **Hemmeligheder:** `git log --all -p` søgt efter `tskey-`, `BEGIN … PRIVATE
  KEY`, `APP_SECRET=<hex>`, `ghp_`, `AKIA`: ingen fund. Kun `.env.example` er
  versioneret (ingen rigtige værdier); `deploy/.env` og `deploy/proeve/.env` står i
  `.gitignore`, `*.db`/`*.pem` er ikke i repoet. Repoet er offentligt, så
  hold det sådan. Afgørende: `git check-ignore deploy/.env` bekræfter reglen.
- **Container:** ikke-root bruger, ingen udadgående porte, hukommelses- og
  pid-grænser, `.dockerignore` udelukker `.git`, `.claude`, tests.
- **Service worker:** cacher ikke `/api/`-svar.

## 5. Kunne ikke testes

- **Familie-isolation med rigtige familier:** findes ikke endnu (S-01); testet
  som to brugere i samme database. Test-matrixen fra `flere-familier.md` §6 skal
  skrives, når `CurrentHousehold` er bygget, og testen bør køre alle ruter.
- **Funnel/Tailscale-adfærd:** om `X-Forwarded-For` overskrives eller
  tilføjes, om der tilføjes HSTS/andre headere, og TLS-opsætning. Kræver
  kontakt til prøven/driften, som er forbudt. Anbefaling: test i prøven af
  ejeren selv.
- **Docker-bygning og kørsel:** `docker build`/`compose` er ikke kørt (kun
  læst); pid-/mem-grænser og brugeren er vurderet ud fra filerne.
- **SSRF med rigtige redirects/DNS:** kun logikken og en simuleret rebinding er
  testet; ingen eksterne værter er kontaktet. Valdemarsro/nemlig-søgning er ikke
  kørt (ville kræve udgående kald til tredjepart).
- **CVE-opslag:** ingen netværk/`pip-audit`; `npm audit` kun offline.
- **Belastning/DoS:** bevidst ikke gjort.
- **Selve browser-UI:** XSS er vurderet ved kodegennemgang og et søg efter
  farlige konstruktioner, ikke ved at åbne siden i en browser.
