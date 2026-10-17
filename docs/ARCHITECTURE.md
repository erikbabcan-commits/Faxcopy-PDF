# Architektúra MVP

## Moduly a dátový tok

```
Browser (HTML/CSS/TypeScript, rovnaký origin)
              |
              v
API: login / tenant RBAC / CSRF / profiles / jobs / audit
              |                 |
              v                 v
PostgreSQL alebo SQLite    volume: original.pdf
 [jobs = durable queue]       + preview.png
              |
              v
Worker: atomický claim -> lease -> SHA + profile digest
              |
              +-- lokálny pilot: limitovaný subproces (NIE sandbox)
              |
              +-- Docker: súkromné HTTP -> oddelený scanner
                                             |
                                             v
                                    krátko žijúci parser
                                  pypdf + PDFium render
                                             |
              <------------ štruktúrovaný report -----------+
              |
              v
Validácia digestov + fail-closed výsledku -> uloženie -> audit
              |
              v
Človek: prevziať DTP / vrátiť podklad
```

Modulárny monolit: modul API a samostatné worker procesy používajú spoločné modely a databázu. Nie je potrebný Redis. Neexistuje distribučná transakcia DB/filesystem; upload čistí svoje dočasné súbory pri zachytených chybách, avšak tvrdý pád môže nechať orphan súbory. Pred produkciou treba zaviesť reconciliation a alarm na rozdiel logických a fyzických objemov.

## Dátové entity

`tenants`, `users`, `sessions`, `profiles`, `jobs`, `audit_events`, `api_keys`, `login_buckets`, `worker_heartbeats`. Tenant ID sa odvodzuje zo session/API key principal, nie z form-data parametra. Všetky verejné čítania zákaziek a profilov sú tenant-scoped. Toto je aplikačná izolácia, nie databázové RLS. V produkcii rozdeliť migration owner a runtime DB identity, doplniť minimálne privilégia a zvážiť RLS.

Profil je append-only cez API: nová verzia v rovnakej `family_id`; existujúce joby uchovajú snapshot/digest. V jednej rodine je verzia unikátna. Job má tenant-scoped idempotency key a porovnáva hash, profil, meno aj referenciu pri opakovanom upload requeste.

## Konzervatívna fronta

`queued -> processing -> review | blocked | error`. Claim v PostgreSQL používa `FOR UPDATE SKIP LOCKED`; SQLite používame pre jedného workera a lokálny pilot. Conditional update a lease token bránia prepísaniu zákazky zastaraným workerom. Expirovaný lease ide do `error`, nie do automatického nekonečného retry. Operátor môže zopakovať systémovú chybu najviac do troch pokusov. Nie je tu záruka exactly-once vykonania parsera, ale je obmedzené prijatie opakovaného/zastaraného výsledku.

Manuálne rozhodnutie je oddelené od výsledku kontroly. Prijatie chybného reportu je odmietnuté. Conditional update nad decision=NULL zabraňuje dvojitému schváleniu. Worker akceptuje iba reporty s `print_ready=false`, `release_allowed=false` a očakávaným hashom; pri ne-error výsledku overuje aj digest profilu. Report je deterministicky JSON canonicalizovaný; neobsahuje runtime timestamp vo výpočte nálezov.

## Bezpečnostné a súkromné hranice

Súbory nie sú webovo verejné, originál sa sťahuje ako attachment a náhľad je PNG. Parser nebeží v API procese. Docker scanner nemá DB ani volume iných zákaziek, proces dostáva vyčistené env a dočasné vstupy. Interná Docker sieť nie je náhradou host firewallu ani mikroVM; post-exploit útoky a supply-chain riziko vyžadujú samostatný audit.

API dáta sa vložia do DOM cez escape helper; nie sú tu inline script handlers. CSP nemá unsafe-inline, cookies sú HttpOnly, server kontroluje Origin a CSRF. Bearer API token má samostatnú úzku allowlist ciest. Prehliadač neukladá session/API kľúče do localStorage; ukladá iba ID pracoviska na ľahšie prihlásenie.

Audit je transakčný prevádzkový log, **nie** nemenný/forenzný archív. Súbor read-only permissions a hash nie sú WORM. Tenant retencia vymaže originály, náhľady a report/meno/reference, ale pseudonymné auditné udalosti a hashe ostávajú; politika osobných údajov a úplného výmazu pracoviska si vyžaduje vlastné dopracovanie.

## Dokumentačné východiská

Oficiálne materiály konzultované pri odovzdaní (neznamenajú certifikáciu aplikácie):

- FastAPI: https://fastapi.tiangolo.com/deployment/docker/
- TypeScript strict: https://www.typescriptlang.org/tsconfig/strict.html
- pypdf strict parsing: https://pypdf.readthedocs.io/en/stable/user/robustness.html
- Docker Compose networking: https://docs.docker.com/compose/how-tos/networking/

## Report contract

Every persisted worker result carries the job and tenant IDs, input SHA-256, profile ID/version/digest, engine identity/version, UTC timestamp, bounded common PDF metadata, findings, and final state. Worker-side failures also produce an error report with `print_ready=false` and `release_allowed=false`; an incomplete check is never a pass. The current terminal states are `review`, `blocked`, and `error`.
