# Presný rozsah v0.1.0

## Zásada

Ide o **asistenčný intake/inspection workflow**, nie o autoritatívny systém na schválenie produkčnej tlače. Profesionálna tlač vyžaduje rozhodnutia založené na konkrétnom stroji, substráte, zákazke, farebných profiloch a pravidlách tlačiarne. Implementované kontroly sú orientačná technická brána.

| Oblasť | Implementované | Neimplementované / obmedzenie |
|---|---|---|
| Geometria | MediaBox/CropBox/TrimBox/BleedBox, rozmer, rotácia, UserUnit, fyzický limit | Nenahrádza vizuálne porovnanie so zákazkou; nie technologické rozmery knižnej väzby |
| Spadávka | Číselné okraje BleedBox okolo TrimBox | Kresba v spadávke, bezpečná zóna, dorobenie pozadia |
| Fonty | Použité Tf zdroje, prítomnosť vloženého programu, kontrola potomkov Type0 | Validita fontového programu, všetky glyfy, shaping; Type3 vyžaduje review |
| Raster | Efektívne najhoršie DPI podľa transformácie, inline obrázky, vnorené Form | Obsah skrytý clippingom alebo v shading/pattern môže vyžadovať iný prístup; nie ostrosť skutočnej snímky |
| Farby | Základný inventár a konfigurovateľné RGB upozornenie | ICC konverzia, proof, spot color mapping, TAC, GCR, trapping |
| Overprint/priehľadnosť | Vybrané prítomnostné signály | Správnosť nastavení a finálny RIP výstup |
| PDF/X | Informačné zachytenie deklarácie v Document Info | Žiadny konformančný test; XMP nie je úplne inventarizované |
| Interaktivita | Vybrané action/attachment/form/signature markery | Antivírus, záruka neexistencie exploitu, validácia digitálnych podpisov |
| Náhľad | Raster prvej strany pomocou PDFium | Nie nátlačok a nie farebná verifikácia; všetky strany nie sú vizuálne renderované |
| Opravy | Žiadne | Originál ostáva nezmenený; nový opravený súbor je nová zákazka |

Limity: 25 MB štandardný upload (konfigurovateľný do 100 MB), najviac 200 strán, limit parserových operácií/objektov/hĺbky, časový limit skenera. Nástroj môže správne tlačiteľný, ale neštandardný PDF odmietnuť (`strict=True`). Falošné pozitíva sú prijateľnejšie než neodôvodnené schválenie. Zlyhanie parsera alebo prekročenie limitu je `error`, nie čiastočný „úspech“.

## Osem pribalených kontrolných súborov

| Súbor | Očakávaný stav | Nález |
|---|---|---|
| 01-vizitka-kontrola.pdf | review | Bez nálezov v obmedzenom rozsahu |
| 02-chybajuca-spadavka.pdf | blocked | BLEED_TOO_SMALL |
| 03-nizke-rozlisenie.pdf | blocked | IMAGE_LOW_DPI |
| 04-nevlozeny-font.pdf | blocked | FONT_NOT_EMBEDDED |
| 05-aktivny-obsah.pdf | blocked | ACTIVE_CONTENT; obsahuje iba neškodný syntetický JavaScript marker |
| 06-poskodeny-subor.pdf | error | PDF_PARSE_FAILED; zámerne poškodený fixture |
| 07-sifrovany.pdf | blocked | PDF_ENCRYPTED; nešifrovaný obsah sa nespracuje |
| 08-deklaracia-pdfx.pdf | review | PDFX_DECLARATION_ONLY; nejde o skutočný PDF/X dôkaz |

Testuje sa profil „Vizitka · 85 × 55 mm“, 3 mm geometrická spadávka, 300 DPI. Toto nie je všeobecne platná výrobná požiadavka pre všetky produkty.

## Dopady pri zmene enginu

Nový profesionálny engine musí implementovať vlastný normalizačný adaptér, mať explicitne dohodnutú SaaS/OEM licenciu a nezávislú golden dataset validáciu. Nestačí nahradiť názov enginu. Pri povolení automatických opráv treba pridať oddelené revízie, preflight po každej úprave a vizuálny diff; v tejto verzii nič také povolené nie je.
