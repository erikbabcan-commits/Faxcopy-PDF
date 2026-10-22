# Overenie dodávky · 17. 10. 2026

## Skutočne vykonané

| Kontrola | Výsledok | Dôkaz |
|---|---|---|
| Python jednotkové a integračné testy | **65 passed**, posledný beh 12,28 s | `pytest-results.txt`, `backend/tests/` |
| TypeScript strict build + asset assembly | **PASS**, TypeScript 5.8.3 | `npm run build`, `frontend/dist/` |
| Python syntaktická kompilácia | **PASS** | `python -m compileall -q backend/app scripts` |
| Alembic migrácia prázdnej SQLite | **PASS** | migrácia spustená v reálnom HTTP smoke aj browser štarte |
| Skutočné HTTP: API + worker + scanner ako oddelené procesy | **6 kontrol PASS** | `http-results.json`, `http-test-log.txt` |
| Offline render: login, dashboard, detail | **15/15 bez horizontálneho pretečenia dokumentu** | `layout-results.json`, `screenshots/` |
| Pripravené štartovacie CLI a hot-folder CLI | `--help` a syntaktická kontrola prešli | `scripts/run_local.py`, `scripts/hot_folder.py` |

## Čo obsahujú testy

Prihlásenie a serverové relácie; HttpOnly/SameSite/CSP; Origin/CSRF odmietnutie; tenant isolation a cudzí profil; viewer RBAC; API key scope/revokácia; upload idempotency a kvóty; príjem/parsovanie súboru; reálne vytvorenie PNG; uloženie reportu a kontrola hashov; ručný DTP handoff; zákaz prijatia podkladu s chybou; požiadavka na zmysluplnú poznámku; retry limit; stale lease a zmenený originál; profilový snapshot; výmaz a kapacitná kvóta; pravidlový asistent; overenie súkromného skenera; DPI/rotácie/transformácie a osem rôznych syntetických PDF.

HTTP smoke vytvoril tri reálne procesy a volal ich cez lokálne TCP/HTTP. Nahral štandardný, chybný a poškodený syntetický PDF. Overil stavy review/blocked/error, prenos skenerového výsledku, stiahnutie PNG/originálu a ručné rozhodnutie bez zmeny `release_allowed=false`. **Nevyplýva z toho kontajnerová bezpečnosť ani PostgreSQL kompatibilita.**

## Výslovne neoverené

| Oblasť | Stav / dôvod |
|---|---|
| Live end-to-end prehliadač | **BLOCKED**: Chromium politika zablokovala aj localhost navigáciu, `ERR_BLOCKED_BY_ADMINISTRATOR`. Bez úpravy tejto politiky. Pribalený `browser_smoke.py` čaká na beh v používateľovom/CI prostredí. |
| Docker image build / Compose štart | **NOT RUN**: Docker runtime nie je k dispozícii. YAML sa kontroluje osobitne iba syntakticky. |
| PostgreSQL runtime, SKIP LOCKED, súbeh viacerých workerov | **NOT RUN**; testované SQLite. |
| Čistá inštalácia závislostí a vulnerability scan | **BLOCKED**: registry neboli dostupné; DNS k registry.npmjs.org zlyhalo. Použité dostupné nainštalované knižnice. |
| Ollama s reálnym modelom | **NOT RUN**; odskúšaný pravidlový fallback. |
| Externý MIS/hot-folder na reálnej tlačiarni | **NOT RUN**. |
| Certifikovaný PDF/X, RIP/farebný proof, automatické opravy | **NOT IMPLEMENTED**. |
| Záťažový/pentest, nezávislý bezpečnostný audit, obnova záloh | **NOT RUN**. |
| Verejný deployment / živá URL | **NOT DEPLOYED**. |

## Ako vznikli obrázky

Obrazovky v `screenshots/` vznikli **offline vykreslením funkcií zo skompilovaného klienta**, s uloženými skutočnými výsledkami syntetických PDF. HTML sa renderovalo do Chromium bez pripojenia k serveru. Dátové pracovisko a používateľ sú fiktívni. Toto overuje rozloženie a čitateľnosť, nie klikateľný browser workflow alebo bezpečnosť CSP/CSRF v prehliadači.

Tri obrazovky boli vykreslené pri šírkach 1440, 360, 390, 430 a 932 px. Celá stránka po oprave nepretečie vodorovne; široké tabuľky majú vlastné horizontálne posúvanie. Skontrolované náhľady nie sú testom všetkých kombinácií obsahu, WCAG certifikáciou alebo testom na fyzickom iPhone/Safari.

## Reprodukcia

```bash
cd frontend && npm install --ignore-scripts && npm run build
cd ../backend && python -m pytest -q
cd ..
python scripts/http_smoke.py
python scripts/browser_smoke.py
```

HTTP a browser smoke vytvárajú iba dočasnú databázu/účty a pri ukončení zastavia procesy. Bežiaci verejný server netestujú a používateľské dáta nemažú. Browser script vyžaduje Playwright a Chromium. Ak sa tento beh nepodarí, nesmie sa výsledok premenovať na PASS.

Dodávka má pripnuté priame balíky a zaznamenané verzie v `observed-dependencies.json`; nemá potvrdený complete dependency lock ani potvrdenie, že konkrétne verzie nie sú zraniteľné. Pred internet-facing nasadením vykonajte postup z `OPERATIONS.md`.
