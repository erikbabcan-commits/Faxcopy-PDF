# Prevádzka a brána pred verejným pilotom

## Toto nie je „deploy and forget“

Predvolený lokálny štart a Compose publikujú iba loopback. Neotvárajte port do internetu bez bezpečnostného overenia. Zvlášť nepoužívajte základný lokálny skener na neznáme zákaznícke dokumenty na vašom pracovnom počítači.

## Povinné kroky pred externými zákazníkmi

1. Čistý build obrazu, `pip check`, vulnerability audit závislostí (`pip-audit`), fix všetkých relevantných zraniteľností, nový beh testov. Dodané piny sú testovaný runtime, nie potvrdenie aktuálnej bezpečnosti. Zamknúť tranzitívne závislosti a image digesty. Nepoužívať automatické major upgrades bez regresií.
2. Spustiť CI vrátane browser smoke a PostgreSQL testov. Overiť Compose sieťovú izoláciu, pamäťové/time limity, roly DB, pád workera, retry a vytváranie volumes na čistej inštalácii. SQL kompatibilita PostgreSQL je navrhnutá, zatiaľ tu nebola runtime overená.
3. HTTPS reverse proxy pred API, presný `APP_ORIGIN=https://...`, `SECURE_COOKIES=true`, `APP_ENV=production`. Kód production flag vynucuje HTTPS/cookies, PostgreSQL a nakonfigurovaný skener s tokenom >=32 znakov; nevykonáva bezpečnostný audit.
4. Edge request rate limiting, limity prenosovej rýchlosti/connection timeout a aplikačných kvót, zákaz priameho prístupu ku skeneru, firewall od skenera na host a DB. Posudzovať izoláciu na samostatnom hoste/mikroVM pri nedôveryhodných PDF. Nastavenie interného bridge samo o sebe nie je záruka úplného egress firewallu.
5. Zálohovanie DB aj volume ako konzistentný celok, šifrovanie dát a záloh, test obnovy do separátnej inštancie. SQLite režim nie je HA konfigurácia; archivačný snapshot samotného .db počas WAL zápisu nie je bezpečná konzistentná záloha.
6. Návrh DPA/retencie a oprávneného prístupu so zákazníkom; sledovanie kapacity disku a voliteľné malware scan. Nevyhlasovať „GDPR compliant“, „malware clean“ alebo „print ready“ len na základe tejto aplikácie.

## Overenie po štarte

`GET /healthz` overí API proces. `GET /readyz` overí databázové spojenie a schému, **nie** dostupnosť skenera ani plnú pripravenosť výroby. Dashboard worker-online používa heartbeat do 120 sekúnd. Nedávny heartbeat nie je test všetkých vstupov. Bez workera zostanú zákazky queued; skutočný upload test musí skončiť explicitným výsledkom.

```bash
docker compose ps
docker compose logs --tail=100 api worker scanner
docker compose exec api python -m app.manage purge-expired
```

## Zálohovanie a výmaz

Použite spravovaný databázový backup alebo overený `pg_dump` postup. Zastavte upload/worker pri prvej jednoduchej konzistentnej zálohe a súčasne uložte volume dokumentov. Presný postup snapshotov závisí od hosta a úložiska; v balíku nie je neoverený skript, ktorý by tvrdil atómovú zálohu.

Retenčný job beží vo worker slučke približne každých 10 minút. Chyba výmazu sa má odsledovať a znovu spracovať. Audit a hashe pretrvajú. Kvóta `storage_bytes` účtuje originály, nie náhľady, databázu ani dočasné súbory; nezamieňať s reálnou diskovou kapacitou. Po hard crash overiť `.incoming` a orphan adresáre. Automatický orphan reconciler nie je implementovaný.

## Identity a tajomstvá

`python scripts/make_env.py` vytvorí náhodné secrets a neprepíše existujúci `.env`. V produkcii presuňte secrets do správcu tajomstiev. Rotácia scanner tokenu vyžaduje koordinovaný restart worker/scanner. Nikdy ho nevkladajte do browser buildu. Zmena používateľského hesla odhlási browser relácie; explicitný administrátorský reset navyše zruší jeho API kľúče. Deaktivácia používateľa zruší oboje.

MFA, SSO, invitation flow, self-service reset cez e-mail a vynútená prvá zmena dočasného hesla nie sú implementované. Owner pridáva členov lokálne a odovzdá credential bezpečným kanálom.

Pri reverse proxy je predvolené `--no-proxy-headers`: bráni slepému dôverovaniu podvrhnutého X-Forwarded-For. Skonfigurujte konkrétny trusted proxy rozsah a edge rate limiting; inak IP rate limiter môže vidieť všetkých klientov ako jednu IP. Automatické akceptovanie forward headers od kohokoľvek je nesprávne.

## Ollama

API musí mať dostupnú vami zvolenú súkromnú modelovú endpoint adresu. Default Compose API má egress, worker/scanner nie sú zdieľaná AI gateway. Nepublikujte Ollama bez autentifikovanej hranice. Pri nedostupnom modeli sa vráti pravidlová šablóna; návrh nie je automaticky odoslaný. Lokálny launcher zámerne vypína model aj v prípade zdedených LLM env variables.

## Obmedzenia horizontálneho škálovania

Compose je jednohostový pilot: lokálny spoločný volume, žiadne S3, žiadny autoscaling, žiadne garantované SLA. Viac workerov vyžaduje PostgreSQL, odmerané limity skenera, bezpečné úložisko a tenant fairness scheduler. Súčasná globálna FIFO fronta môže nechať veľkého tenanta zablokovať ostatných.
