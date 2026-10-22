# PressPilot · DTP Automation MVP

**Funkčné technické MVP pre riadený pilot. Nie certifikovaný preflight ani produkčne odskúšaný verejný SaaS.**

Webové pracovisko na prijatie PDF, základnú deterministickú kontrolu, riadenie fronty a odborné posúdenie. Žiadne nahrané PDF ani rozhodnutie nesúvisia s Exprestou; pribalené súbory sú syntetické. PressPilot je pracovný názov, nie overená ochranná známka.

## Čo je implementované

- Slovenské responzívne rozhranie: prihlásenie, prehľad, zákazky, detail PDF s rasterizovaným náhľadom, výrobné profily, audit, používatelia a API kľúče.
- FastAPI API, SQLAlchemy, Alembic migrácia, SQLite na lokálny pilot a konfigurácia PostgreSQL pre kontajnery.
- Tenant-scoped pracoviská; roly owner / operator / viewer; Argon2id heslá; HttpOnly SameSite cookies; serverové relácie a CSRF kontrola.
- Streamovaný príjem PDF s limitom veľkosti a idempotentným kľúčom. SHA-256 originálu, nemenný snapshot profilu a digest reportu.
- Trvalá databázová fronta, atomické prevzatie zákazky, lease/fencing, označenie zlyhaného workera a ručné opakovanie s limitom.
- Základné kontroly rozmerov, počtu strán, explicitného TrimBoxu, geometrickej spadávky, prítomnosti fontového programu a efektívneho DPI vrátane vnorených Form transformácií, rotácie a UserUnit.
- Základný farebný inventár, detekcia vybraného aktívneho obsahu, upozornenia na formuláre, overprint a priehľadnosť. Nie antivírus ani RIP simulácia.
- Ručné prevzatie na DTP alebo vrátenie podkladu; uloženie poznámky a auditnej udalosti. Známy chybný podklad nemožno prevziať.
- JSON report a pôvodný PDF na stiahnutie; pravidlový návrh správy zákazníkovi. Voliteľný adaptér Ollama, vypnutý v predvolenom nastavení.
- Mesačné kvóty, evidencia veľkosti originálov, retencia súborov a odstránenie údajov zákazky. Jednopriechodový hot-folder upload klient.

**Browser frontend je TypeScript + natívne DOM/CSS, nie React/Next.js.** Nemá žiadnu runtime závislosť ani externé CDN/fonty. Zdroj aj zostavený `frontend/dist` sú pribalené. Server môže okamžite servovať existujúci build; Node potrebujete iba pri úprave klienta.

## Najrýchlejšie lokálne spustenie

Požiadavky: Python 3.13, inštalácia Python závislostí z registra. Pri úprave frontendu navyše Node 22 a TypeScript 5.8.3. Testované verzie sú v `docs/VERIFICATION.md`.

### Windows PowerShell

Z koreňa rozbaleného projektu:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe scripts\run_local.py init --workspace "Moja tlačiareň" --email "admin@mojafirma.sk" --seed-demo
.\.venv\Scripts\python.exe scripts\run_local.py serve
```

### Linux / macOS

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python scripts/run_local.py init --workspace "Moja tlačiareň" --email "admin@mojafirma.sk" --seed-demo
.venv/bin/python scripts/run_local.py serve
```

Inicializácia si **interaktívne vyžiada vaše heslo** a vypíše ID pracoviska. Uložte si ID; spolu s e-mailom a heslom ho zadáte pri prihlásení. Nie je tu predvolené heslo, verejná registrácia ani hardcoded admin token.

Otvorte **http://localhost:8080**. Použite presne `localhost`, nie `127.0.0.1`: Origin pre zápisy sa kontroluje presnou zhodou. `Ctrl+C` ukončí API aj worker. Dáta sú v `.local/`. Opakované `serve` zachová databázu aj súbory. Ďalšie `init` vytvorí nové pracovisko, nevymaže pôvodné.

`--seed-demo` pridá osem syntetických súborov. Nie je to falošný dashboard: reálne prejdú skenerom a vytvoria uložené reporty. V lokálnom režime používajte výhradne dôveryhodné testovacie podklady. Subproces s resource limitmi **nie je plnohodnotný bezpečnostný sandbox**, najmä na Windows, kde sa linuxové `resource` limity neuplatnia.

Iný port: `python scripts/run_local.py --port 8081 serve`. Launcher zámerne nepoužíva produkčný `.env`, nezapne LLM a binduje iba loopback.

## Docker pilot s oddeleným skenerom

Pribalená konfigurácia je **pripravená, ale Docker build a PostgreSQL runtime neboli v tomto prostredí spustené**. Docker tu nie je dostupný. Pred používaním s reálnymi zákazníckymi PDF urobte bezpečnostné a kontajnerové overenie z `docs/OPERATIONS.md`.

```bash
python scripts/make_env.py
docker compose config --quiet
docker compose up --build -d
docker compose exec api python -m app.manage bootstrap --workspace "Moja tlačiareň" --email "admin@mojafirma.sk"
```

Voliteľné syntetické dáta po uložení ID pracoviska:

```bash
docker compose exec api python -m app.manage seed-demo --workspace-id VASE_UUID --samples /app/samples --confirm-synthetic-data
```

Služby: `db`, jednorazové `migrate`, `api`, `worker`, `scanner`. API má iba port `127.0.0.1:8080`. Databáza a skener nemajú publikované porty. Skener nemá dokumentový volume ani databázovú sieť; jeho sieť je interná. App a skener bežia bez root oprávnení, bez capabilities a s read-only root filesystemom. Ide o konfiguráciu hraníc, nie o dôkaz odolnosti voči všetkým exploitom.

**Nikdy nespúšťajte `docker compose down -v` bez zálohy**: `-v` odstráni dátové volumes. Na bežné zastavenie použite `docker compose down` bez tohto prepínača.

## Ako interpretovať výsledky

| Výsledok | Význam |
|---|---|
| `queued` | Uložené, čaká na worker. |
| `processing` | Prebieha kontrola; lease zabraňuje zápisu zastaraného výsledku. |
| `review` | Žiadna zistená blokujúca chyba v podporovanom rozsahu. Stále je nutné odborné posúdenie. |
| `blocked` | Zistená chyba. Nemožno označiť ako prevzaté. Možno vrátiť podklad na opravu. |
| `error` | Kontrola nedala úplný spoľahlivý výsledok; nikdy sa nepovažuje za úspech. |
| `decision=accepted` | Operátor prevzal na interné DTP posúdenie. Neznamená „print-ready“. |
| `decision=rejected` | Operátor vrátil podklad. |

V **každom** reporte zostáva `print_ready=false` a `release_allowed=false`. V MVP neexistuje endpoint na uvoľnenie do výroby. Ani LLM nemá oprávnenie meniť rozhodnutie, profil či originál.

Geometria spadávky neoveruje, že v spadávke naozaj pokračuje kresba. Prítomnosť fontového programu neoveruje správnosť glyfov. Zoznam farebných priestorov neoveruje ICC transformácie. Deklarácia PDF/X v metadátach nie je test zhody PDF/X. Viac v `docs/SCOPE.md`.

## Testy a vývoj

```bash
python -m pip install -r backend/requirements-dev.txt
cd frontend
npm install --ignore-scripts
npm run build
cd ../backend
python -m pytest -q
cd ..
python -m playwright install chromium
python scripts/browser_smoke.py
```

V dodacom prostredí: **65 pytest testov prešlo**, TypeScript strict build prešiel, Alembic migrácia na prázdnej SQLite prešla. Živý browser smoke test bol zablokovaný Chromium politikou (`ERR_BLOCKED_BY_ADMINISTRATOR`). Skript je pribalený na spustenie vo vašom prostredí. Offline render obrazoviek a merania layoutu sú samostatné overenie, nie náhrada end-to-end testu.

Registry neboli dostupné: čistú inštaláciu balíkov a vulnerability audit nemožno z tohto odovzdania označiť za overené. Priame verzie závislostí zodpovedajú testovanému runtime; transitive dependency lock a audit sú povinný krok pred verejným nasadením.

## Integrácie

V Nastaveniach vytvorte API kľúč `read` alebo `upload` s obmedzenou platnosťou. Raw token sa zobrazí raz, v databáze je jeho hash. API kľúč nesmie schvaľovať, čítať správu členov ani meniť profily. Na upload sa vyžaduje `Idempotency-Key`; opakovanie rovnakého payloadu vráti rovnakú zákazku.

Príklad s hot folderom:

```bash
# Uložte PRESSPILOT_API_KEY do prostredia, nie do zdrojového kódu.
python scripts/hot_folder.py --folder ./incoming --url http://localhost:8080 --profile UUID_PROFILU
```

Spúšťajte opakovane pomocou vlastného plánovača. PDF do priečinka vkladajte atomickým presunom po dokončení zápisu. Skript súbory nikdy nemaže ani nemení a drží idempotentný ledger. Je určený pre jedného plánovaného volajúceho; race/load test s externým MIS zatiaľ neprebehol. API schéma je dostupná prihlásenému používateľovi na `/api/openapi.json`.

Ollama je opt-in cez `LLM_BASE_URL` a `LLM_MODEL` pri manuálnom/Compose štarte. Posiela iba vybrané generické technické nálezy, nie PDF, extrahovaný obsah, názov zákazky či názvy fontov. Aj správu LLM musí skontrolovať človek. Nedostupný model vracia pravidlovú šablónu. Skutočná Ollama integrácia tu nebola overená; lokalita modelu a sieťový prístup sú zodpovednosťou prevádzkovateľa.

## Čo v balíku zámerne nie je

Profesionálny PDF/X engine (callas/Enfocus), prepress autofix, ICC konverzia, kontrola celkového nánosu farby, generatívne dorábanie spadov, fakturácia/Stripe, SSO/MFA, outbound webhooky, obojsmerné JDF/JMF/MIS integrácie, objektové S3 úložisko, verejný self-service onboarding ani produkčný deploy. Nie sú nahradené tlačidlami, ktoré predstierajú funkčnosť.

## Orientácia v projekte

```
backend/app/          API, autorizácia, inspector, worker, súbory, retencia
backend/migrations/  Alembic databázová migrácia
backend/tests/       automatické jednotkové a integračné testy
frontend/src/        strict TypeScript a CSS
frontend/dist/       zostavený webový klient
scripts/             lokálny štart, hot folder, fixtures, browser smoke
samples/             8 syntetických PDF (vrátane zámerne chybných)
infra/               Dockerfile skenera
compose.yaml         konfigurácia PostgreSQL + API + worker + scanner
docs/                rozsah, architektúra, prevádzka, roadmapa, overenie
.github/workflows/   pripravený CI workflow
```

Dokumenty: [Overenie](docs/VERIFICATION.md) · [Rozsah](docs/SCOPE.md) · [Architektúra](docs/ARCHITECTURE.md) · [Prevádzka](docs/OPERATIONS.md) · [Ďalšie kroky](docs/ROADMAP.md).
