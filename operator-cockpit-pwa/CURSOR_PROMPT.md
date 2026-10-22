# Operator Cockpit PWA – kontext pre ďalšiu prácu

Stack: React 19, TypeScript strict, Vite, Zustand, Tailwind; Node.js 24.x. Zachovaj české UI a farby dark emerald `#040C09` / copper `#E2B48A`.

## Overený stav

- `npm run lint` a `npm run build` prešli.
- Frontend je pripravený na samostatné preview bez API kľúčov.
- Dashboard a kalendár zobrazujú ukážkové dáta; editor cien vytvára iba lokálny náhľad.
- Odoslanie hromadných zmien je vypnuté, pretože chýba backend a mapovanie skutočných jednotiek.
- `/channels` je zástupný modul. Samotná navigácia naň neznamená implementovanú správu kanálov.
- `src/services/api.ts` je proxy klient cez voliteľnú verejnú `VITE_API_BASE_URL`; žiadne provider tajomstvá nepatria do frontendu.
- `server-reference/providers.ts` obsahuje pôvodný provider kód ako podklad na migráciu. Nie je nasadený ani overený proti reálnym účtom.
- Automatizovaný browser test nebol dokončený pre zlyhanie sťahovania Chromium. Funkčnosť prihlásenia, synchronizácie a inštalácie PWA nebola potvrdená.

## Postup pri budúcom zadaní backendu

1. Najskôr potvrď konkrétny rozsah zadania, backendové prostredie a dostupné partner účty. Nevytváraj automaticky nové moduly.
2. Implementuj overenie prihlásenia a autorizáciu ku konkrétnym ubytovaniam; pri cookies aj CSRF ochranu a primerané CORS nastavenie.
3. Nastav `BOOKING_CLIENT_ID`, `BOOKING_CLIENT_SECRET`, `AIRBNB_ACCESS_TOKEN` a voliteľné `OPENAI_API_KEY` iba na serveri. Pôvodné názvy s `VITE_` nepoužívaj.
4. Implementuj a over endpointy podľa kontraktu v README. Provider referenciu doplň o validáciu, XML escaping, spracovanie chýb a overené partner rozhrania.
5. Doplň skutočné mapovanie jednotiek na hotel/room/listing IDs a skontroluj dátumy, ceny a správanie pri čiastočnom zlyhaní.
6. Až potom pripoj frontend cez `VITE_API_BASE_URL`, nahraď ukážkové dáta a povoľ potvrdené odosielanie zmien.
7. Pri API na rovnakom origine uprav Vercel routovanie pred SPA fallbackom. Autentifikované API odpovede neukladaj do zdieľanej offline cache.
8. Spusti relevantné overenia a jasne rozlíš lokálny build, testy so simulovanými odpoveďami a overenie skutočnej integrácie.

## Pravidlá pri úpravách

- Nikdy neobnovuj klientsky OpenAI konštruktor ani `dangerouslyAllowBrowser`.
- Zobrazený úspech musí vychádzať z potvrdeného výsledku; nezahadzuj chyby cez `.catch(() => null)`.
- Neodosielaj požiadavky s `DEMO-HOTEL` ani ukážkovými listing IDs do živých účtov.
- Stavy `connected`/`testing` nepersistuj a staré uložené hodnoty nepovažuj za overenie.
- Zachovaj SPA routing, bezpečnostné hlavičky, PWA ikony a jednu konfiguráciu generovaného service workera.
- Nepopisuj projekt ako plne produkčný channel manager, kým nie sú potrebné integrácie implementované a overené.

Podrobné nasadenie, env mapovanie a kontrakt endpointov sú v README.md.
