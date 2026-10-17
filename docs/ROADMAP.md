# Od MVP k predajnému produktu

Tieto etapy sú návrh, nie implementované funkcie ani odhad založený na podpísaných zmluvách.

## P0: Overiteľný externý pilot

Dokončiť čistú inštaláciu, závislostný audit, Docker a PostgreSQL testy, live browser smoke a obnovu zo zálohy. Doplniť PDF corpus od partnerskej tlačiarne, odsúhlasené výrobné profily a prepress odborníka. Merať false positives/negatives, p95 latenciu, percento zlyhaní parsera a čas operátora na zákazku. Žiadne „ušetrené hodiny“ bez meranej baseline.

## P1: Profesionálna kontrola a opakovateľné nasadenie

Vyjednať SaaS/OEM alebo vhodné customer-owned licenčné nasadenie pre callas alebo Enfocus. Implementovať jeden normalizačný engine adapter, nie oba naraz. Viazať report na verziu binary, profil, zákazku a nástroj. Pridať golden dataset/regresie, crash corpus, sandbox hardening, least-privilege DB, RLS podľa threat modelu, S3 adapter a orphan reconciliation.

## P2: Platený B2B workflow

Tenant provisioning, SSO/MFA, invite/reset, usage events, fakturácia, API rate limits, podpísané webhooky s outboxom a retry, tenant fairness. Zákaznícky claim „print-ready“ povoliť iba pri presne definovanom a odborne schválenom rozsahu; label zostáva obmedzený konkrétnym výrobným profilom.

## P3: Povolené opravy

Začať iba whitelisted deterministickými úpravami so samostatnou výstupnou revíziou, kontrolou po oprave a vizuálnym diffom. CMYK konverzie, flattening a generatívne úpravy spadávky nie sú automaticky bezpečné. Zachovať originál, schvaľovateľa aj audit. Vyhodnotiť presné reklamácie a riziko zásahu do zákazníckeho návrhu.

## Obchodný model na validáciu

Prvá ponuka: platený discovery + časovo obmedzený pilot jedného workflow s dohodnutými metrikami. Nevyvíjať bezplatne kompletný MIS. Predávať dohľadateľnosť, kratší intake a menej ručných rozhodnutí pri opakovaných problémoch, nie abstraktnú „AI tlač“.

Následná cenotvorba: mesačný poplatok za pracovisko + zahrnutý objem kontrol + cena za nadlimit, prípadne osobitne licencovaný profesionálny engine a onboarding/integrácia. Minimálna predajná cena musí pokryť licenciu, reálny compute/render čas, storage/egress, support a riziko reklamácií. Konkrétne ceny sa stanovia až po cenovej ponuke vendora a pilotných meraniach; tento balík ich nevymýšľa.

Rozhodnutie go/no-go: pilot preukázal merateľnú úsporu po odčítaní review a licenčných nákladov, známy kritický chybný PDF nikdy neprešiel bránou, zákazník rozumie obmedzeniam a existuje bezpečný postup pri neznámom výsledku. Pred rozšírením na knihy a priame výrobné zariadenia začať s malým počtom opakovateľných produktových profilov.
