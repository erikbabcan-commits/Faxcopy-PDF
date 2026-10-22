# Operator Cockpit PWA

React 19 + TypeScript + Vite + Zustand + Tailwind. Aplikácia zachováva české UI a paletu dark emerald `#040C09` / copper `#E2B48A`.

## Aktuálny stav

Projekt je pripravený na nasadenie frontendového náhľadu. Synchronizácia reálnych rezervačných účtov vyžaduje samostatný backend.

- `npm run lint`: prešlo bez chýb.
- `npm run build`: prešlo; build zahŕňa TypeScript, Vite a generovanie PWA súborov.
- Izolované kontroly potvrdili, že bez backendu nevznikajú API požiadavky a stav pripojenia sa nepreberá zo starých uložených dát.
- Automatizované overenie v prehliadači nebolo dokončené, pretože prostredie nedokázalo stiahnuť Chromium. Vizuálne správanie a inštalácia PWA preto nie sú potvrdené testom.
- Booking.com, Airbnb a OpenAI neboli testované s reálnymi účtami.
- Preview URL nevznikla: Vercel CLI nemá prihlásený účet a služba pre tento pokus odmietla aj dočasný deploy. Použi nižšie uvedené `login`, `link` a `deploy`.

Podrobný výsledok je v `verification/REPORT.md`; v balíku je aj overený `dist/`.

Dashboard a kalendár obsahujú ukážkové dáta. Editor cien počíta miestny náhľad; odosielanie zostáva vypnuté, kým nebude existovať backend a skutočné mapovanie jednotiek. Cesta `/channels` je zatiaľ zástupný modul.

## Lokálne spustenie

Použi **Node.js 24.x**; verziu deklarujú `package.json` a `.nvmrc`. Spúšťaj príkazy v priečinku, ktorý obsahuje `package.json` a `vercel.json`:

```bash
cd operator-cockpit-pwa
node --version
npm ci
npm run lint
npm run build
npm run preview
```

`npm run preview` sprístupní zostavený obsah `dist` na adrese vypísanej terminálom. Vývojový server spustíš cez `npm run dev`.

Na samostatný náhľad nepotrebuješ `.env` ani API kľúče. Ak pripájaš už existujúci backend, skopíruj `.env.example` do `.env.local` a doplň iba jeho verejnú adresu:

```dotenv
VITE_API_BASE_URL=https://api.example.com/api
```

`api.example.com` je ilustračná doména. Pre backend na rovnakom origine môže byť hodnota `/api`, ale táto statická aplikácia sama také API neposkytuje. Pri zmene konfigurácie reštartuj vývojový server alebo vytvor nový build.

## Environment variables a pôvodné názvy

**Do frontendového náhľadu nenastavuj Booking/Airbnb/OpenAI tajomstvá.** Vite štandardne sprístupňuje premenné `VITE_*` klientskemu kódu; opravený projekt používa `envPrefix: ['VITE_API_BASE_URL']` a frontend číta iba túto verejnú hodnotu. [Vite: env variables](https://vite.dev/guide/env-and-mode)

| Pôvodný názov | Názov v budúcom backende | Kde a kedy ho nastaviť |
|---|---|---|
| `VITE_BOOKING_CLIENT_ID` | `BOOKING_CLIENT_ID` | Serverové prostredie integrácie Booking.com |
| `VITE_BOOKING_CLIENT_SECRET` | `BOOKING_CLIENT_SECRET` | Iba server, spolu s Booking client ID |
| `VITE_AIRBNB_ACCESS_TOKEN` | `AIRBNB_ACCESS_TOKEN` | Iba server pre integráciu Airbnb |
| `VITE_OPENAI_API_KEY` | `OPENAI_API_KEY` | Iba server; voliteľné pre funkciu AI |
| — | `VITE_API_BASE_URL` | Verejná voliteľná URL v tomto frontendovom projekte |

Vercel premenné backendu nastavuj v projekte, ktorý backend skutočne prevádzkuje. Samotné pridanie štyroch kľúčov do nastavení tejto SPA žiadnu integráciu nezapne. Adresa `VITE_API_BASE_URL` nesmie obsahovať heslo, token ani tajné parametre.

## Nastavenie Vercelu

Použi existujúci `vercel.json`. Pri importe skontroluj tieto hodnoty:

| Nastavenie | Hodnota |
|---|---|
| Framework Preset | Vite |
| Root Directory | Priečinok s `package.json` a `vercel.json` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node.js Version | `24.x` |
| Env pre samostatný náhľad | Žiadne |

Ak sú súbory aplikácie v koreni Git repozitára, Root Directory je koreň. Ak je v repozitári nadradený priečinok, vyber vnorený `operator-cockpit-pwa`. [Vite na Verceli](https://vercel.com/docs/frameworks/frontend/vite)

`vercel.json` zachováva SPA rewrite na `/index.html` pre priame otvorenie trás. Zachované sú hlavičky `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` a `Referrer-Policy: strict-origin-when-cross-origin`.

Hashované assets majú dlhú cache; HTML, service worker a manifest sa revalidujú. PWA používa jeden generovaný worker, český manifest a doplnené ikony. Cache je určená pre aplikačné súbory; API odpovede sa do nej neukladajú. Cesty `/api` sú vylúčené z navigačného fallbacku workera.

`tailwind.config.js` a `postcss.config.js` zostávajú súčasťou buildu. `.vercelignore` vylučuje lokálne tajomstvá, `node_modules`, existujúci `dist`, overovacie súbory a `server-reference`.

## Deploy cez CLI

Návod používa overenú verziu **Vercel CLI 64.4.0**. Pri nasadení do vlastného účtu sa prihlás a prepoj správny projekt:

```bash
npx --yes vercel@64.4.0 login
npx --yes vercel@64.4.0 link
npx --yes vercel@64.4.0 deploy --target=preview
```

Po kontrole preview nasadíš produkčnú verziu:

```bash
npx --yes vercel@64.4.0 deploy --prod
```

Použi adresu, ktorú vráti úspešný deploy. Príkaz `--target=preview` vyjadruje zvolený cieľ explicitne; prostredie a priradené domény skontroluj vo výstupe alebo vo Vercel Dashboard. [Dokumentácia CLI](https://vercel.com/docs/cli/deploy)

### Dočasný náhľad bez prihlásenia

CLI podporuje aj dočasné nasadenie bez `login`:

```bash
npx --yes vercel@64.4.0 deploy --temporary --yes
```

Takýto náhľad má obmedzenú platnosť; aktuálnu URL a informácie o platnosti prevezmi z výstupu služby. Použi ho na zdieľanie ukážky bez tajomstiev. Pre trvalý projekt a vlastnú správu nasadení použi prihlásenie alebo GitHub import.

### Import z GitHubu

Nahraj pripravené zdrojové súbory vrátane `package-lock.json` do vlastného GitHub repozitára. Vercel → Add New → Project → Import Git Repository, potom nastav hodnoty z tabuľky vyššie. Tento balík nepredpokladá, že repozitár už existuje alebo že bol vytvorený na tvojom účte.

## Backend: migračný podklad a kontrakt

`src/services/api.ts` obsahuje klienta pre nasledujúce endpointy. Ich **serverová implementácia nie je súčasťou tohto nasadenia**. Bez `VITE_API_BASE_URL` klient skončí s českou chybou ešte pred sieťovým volaním.

`server-reference/providers.ts` zachováva pôvodnú provider vrstvu so serverovými názvami premenných a lazy inicializáciou OpenAI. Je to podklad na migráciu, nie hotový backend ani overená integrácia. Frontend ho neimportuje a `.vercelignore` ho vylučuje z deployu.

| Metóda | Cesta relatívna k `VITE_API_BASE_URL` | Požiadavka / očakávaná odpoveď |
|---|---|---|
| POST | `/booking/test-connection` | Odpoveď `{ ok: boolean }` |
| POST | `/airbnb/test-connection` | Odpoveď `{ ok: boolean }` |
| POST | `/booking/availability` | `{ hotelId, roomId, from, to, roomsToSell, price? }` |
| POST | `/booking/reservations-summary` | `{ hotelId? }` |
| GET | `/airbnb/listings/:id/calendar` | Query `start_date`, `end_date` |
| PUT | `/airbnb/listings/:id/calendar` | `{ days: [{ date, available?, price?, min_nights? }] }` |
| POST | `/ai/chat` | `{ prompt }`; odpoveď `{ text: string }` |

Klient očakáva JSON odpovede s príslušným content type, používa 20-sekundový timeout a posiela cookies cez `credentials: 'include'`. HTTP 401/403 oznámi ako chýbajúce prihlásenie/oprávnenie; surové provider chyby do UI nepreposiela.

Budúci backend musí overovať prihlásenie a oprávnenie správcu ku konkrétnemu ubytovaniu. Pri cookies implementuj ochranu proti CSRF a kontrolu povoleného pôvodu požiadaviek. Pri inej doméne nastav explicitný povolený frontend origin, CORS s credentials a vhodné atribúty cookies; nepoužívaj verejný proxy bez overenia prístupu.

Pred zapnutím zápisov doplň reálne mapovanie hotel/room/listing IDs, validáciu a escapovanie XML, dátumy, rozsah cien, spracovanie čiastočných zlyhaní a oprávnenia poskytovateľov. Dostupnosť pôvodných partner endpointov sa musí overiť na účtoch určených na integráciu.

Nezapínaj tlačidlo hromadného odoslania len po doplnení URL: súčasný editor používa ukážkové jednotky a nemá mapovanie. Pri implementácii API na rovnakom projekte zároveň uprav smerovanie pred všeobecným SPA fallbackom.

## Orientácia v projekte

| Súbor/priečinok | Úloha |
|---|---|
| `src/modules/cockpit/` | Dashboard, kalendár, náhľad cien, nastavenia |
| `src/store/appStore.ts` | Ukážkové údaje a dočasné stavy pripojenia |
| `src/services/api.ts` | Frontendový klient budúceho backendu |
| `server-reference/providers.ts` | Pôvodný provider kód na serverovú migráciu |
| `vite.config.ts`, `public/` | Build, PWA a ikony |
| `vercel.json`, `.env.example` | Hosting a verejná konfigurácia |

## Oficiálne zdroje

- [Vite: env variables a režimy](https://vite.dev/guide/env-and-mode)
- [Vite na Verceli](https://vercel.com/docs/frameworks/frontend/vite)
- [Konfigurácia vercel.json](https://vercel.com/docs/project-configuration/vercel-json)
- [Vercel CLI: deploy](https://vercel.com/docs/cli/deploy)
- [Vercel: podporované verzie Node.js](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions)
