# PressPilot na MacBook Air (Intel, 8 GB, Monterey)

Lokálny pilot používa Python, SQLite, jedno API a jeden worker. Docker,
Homebrew, PostgreSQL ani lokálny AI model nie sú potrebné. Hotový frontend
je už v repozitári, takže Node nepotrebuješ na bežné spustenie.

## Prvý štart

Potrebuješ Git a Python 3.13 alebo 3.12. Ak Python chýba, nainštaluj
**macOS universal2 installer** z [python.org](https://www.python.org/downloads/macos/)
a znovu otvor Terminál. Systémový Python nemeníme. Pri chybe overenia
certifikátu po inštalácii Pythonu spusti jeho `Install Certificates.command`
v priečinku Applications / Python 3.13; nevypínaj TLS overovanie.

Pre nové stiahnutie (existujúci priečinok sa neprepisuje):

```bash
mkdir -p "$HOME/Developer"
cd "$HOME/Developer"
git clone --branch setup/macbook-air-local --single-branch https://github.com/erikbabcan-commits/Faxcopy-PDF.git Faxcopy-PDF-Mac
cd Faxcopy-PDF-Mac
bash scripts/setup_local.sh
bash Start-PressPilot.command
```

Inštalácia vytvorí `.venv`, nainštaluje iba hotové Python balíky a pri prvom
spustení vyžiada názov pracovného priestoru, e-mail a nové heslo aspoň
s 12 znakmi. Heslo sa pri zadávaní nezobrazuje. Do fronty pridá osem
syntetických ukážok. Worker ich spracuje po štarte aplikácie.

Otvor **http://localhost:8080**. Prihlásenie vyžaduje workspace ID, e-mail
a tvoje heslo. Workspace ID a e-mail nájdeš v `.local/workspace.json`;
heslo v tomto súbore nie je. Existujúci pracovný priestor inštalácia zachová.
Po zlyhaní prvotného vytvorenia účtu môžeš setup spustiť znovu.

## Každodenné používanie

Spusti `Start-PressPilot.command` dvojklikom vo Finderi alebo cez Terminál:

```bash
cd "$HOME/Developer/Faxcopy-PDF-Mac"
bash Start-PressPilot.command
```

Zastav cez **Ctrl+C** v jeho termináli. API aj worker sa ukončia.
Databáza a PDF zostanú v `.local/`; tento priečinok ani `.venv` nemaž,
ak chceš zachovať dáta a pripravené prostredie. Spúšťač funguje aj z cesty
s medzerami a nepotrebuje aktiváciu virtualenv. Po prvotnej inštalácii
bežné spracovanie nepotrebuje internet.

Ak je port obsadený, zastav pôvodnú inštanciu alebo použi:

```bash
.venv/bin/python scripts/run_local.py --port 8081 serve
```

Potom otvor presne `http://localhost:8081`. Nezamieňaj `localhost`
a `127.0.0.1` v prehliadači: ochrana pôvodu požiadaviek používa presnú URL.

## Kontrola funkčnosti

```bash
bash scripts/setup_local.sh --verify
```

Príkaz doinštaluje iba pytest, spustí backend testy a skutočný HTTP scenár:
prihlásenie → upload PDF → fronta → worker → skener → náhľad → DTP rozhodnutie.
Používa dočasnú databázu a syntetické súbory; nemení tvoje účty ani zákazky.
HTTP výsledok uloží do `.local/verification/http-results.json`.

Voliteľný browser test potrebuje Playwright a jeho prehliadač. Novšie browser
balíky môžu vyžadovať novší macOS; na Monterey nie je súčasťou základnej
inštalácie. Základné overenie ho nevyžaduje.

## Úprava frontendu (voliteľné)

Iba pri úprave TypeScript zdrojov potrebuješ Node 22 a npm:

```bash
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
```

## Hranice lokálneho režimu

Aplikácia počúva iba na tomto počítači. Používaj vlastné dôveryhodné PDF
alebo dodané syntetické ukážky. Linuxové pamäťové limity parsera sa na macOS
neuplatňujú; časový limit subprocessu zostáva aktívny. Neznáme zákaznícke PDF
patria do oddeleného skenera podľa [prevádzkových pokynov](OPERATIONS.md).
Výsledok nie je certifikácia PDF/X, antivírusová kontrola ani automatické
povolenie tlače.

Príprava a testy prebehli v Linux prostredí; výber hotových runtime balíkov
pre Intel macOS 12 / CPython 3.13 bol overený stiahnutím. To nenahrádza
runtime test na konkrétnom Macu.
