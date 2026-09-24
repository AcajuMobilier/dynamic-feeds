# Feeduri dinamice pentru marketplace-uri și campanii

Generează automat, la fiecare 2 ore, toate feedurile de produse pentru magazinele Shopify **ocean.ro** și **acaju.ro**, direct din Shopify Admin API, și le publică la adrese fixe pe GitHub Pages. Înlocuiește feedurile generate până acum de aplicația Mulwi Feeds.

Adresa de bază a tuturor feedurilor:

```
https://acajumobilier.github.io/dynamic-feeds/
```

La adresa de bază e o pagină care arată, pentru fiecare feed, câte produse are, din ce magazin vine și dacă a fost regenerat la ultima rulare.

---

## Feedurile

| Feed | Adresa nouă | Adresa Mulwi pe care o înlocuiește | Cine îl consumă | Cine schimbă adresa la tranziție |
| --- | --- | --- | --- | --- |
| Favi ocean.ro | `oceanfavi.xml` | feedul auxiliar de la Favi | Favi | tu, prin managerul de cont Favi |
| Favi acaju.ro | `acajufavi.xml` | `feed.mulwi.com/f/velluttoro/1yc0-heureka.xml` | Favi | tu, prin managerul de cont Favi |
| Google Shopping ocean.ro | `oceangoogle.xml` | `feed.mulwi.com/f/ocean-acaju/shopping.xml` | Merchant Center | agenția de Ads, în Merchant Center |
| Facebook ocean.ro | `oceanfb.xml` | `feed.mulwi.com/f/ocean-acaju/custom.xml` | catalogul Facebook | cine administrează catalogul Facebook |
| Google Shopping acaju.ro | `acajugoogle.xml` | `feed.mulwi.com/f/velluttoro/s1nz-google_shopping.xml` | Merchant Center | agenția de Ads, în Merchant Center |
| DSA acaju.ro | `acajudsa.csv` | `feed.mulwi.com/f/velluttoro/custom_csv.csv` | Google Ads, campaniile DSA | agenția de Ads, în Google Ads |
| RTB House acaju.ro | `acajurtb.xml` | `feed.mulwi.com/f/velluttoro/rtb_house.xml` | RTB House | contactul de la RTB House |

Adresa completă a unui feed = adresa de bază + numele fișierului, de exemplu `https://acajumobilier.github.io/dynamic-feeds/acajugoogle.xml`.

**Feedurile Mulwi NU se opresc din acest proiect.** Ele continuă să existe până decizi tu, împreună cu șeful, pentru fiecare consumator în parte. Acest proiect doar publică echivalentele lor în paralel.

### Două feluri de feeduri

**Replicile** (Google, Facebook, DSA, RTB) reproduc feedurile Mulwi **identic**: aceleași ID-uri, aceleași valori, aceleași câmpuri, în aceeași ordine. Campaniile de pe ele au fost configurate de colaboratori externi și nu trebuie să vadă nicio diferență. Singura schimbare, agreată: etichetele `custom_label` goale sau formate doar din spații nu se mai trimit. Regulile de derivare au fost deduse comparând feedurile Mulwi cu datele din Shopify și verificate independent, câmp cu câmp; sunt documentate în [`docs/reguli_mulwi_2026-09-23.json`](docs/reguli_mulwi_2026-09-23.json), iar raportul de diff din ziua punerii în funcțiune e în [`docs/diff_mulwi_2026-09-23.md`](docs/diff_mulwi_2026-09-23.md).

**Feedurile Favi** folosesc motorul nostru, în formatul Heureka cerut de Favi: parametrii extrași din tabelul de specificații, categorii mapate pe arborele Favi, dimensiuni redenumite pe filtrele Favi, termen de livrare după stoc și preț de livrare pe grila GLS. La acaju, feedul Mulwi era de fapt în format Google; cel nou păstrează aceleași ID-uri de produs, deci istoricul pe Favi nu se pierde.

### Politica de ID

E proprietatea cea mai importantă a fiecărui feed și e fixată în configurarea lui. **Nu se schimbă niciodată**: un ID schimbat înseamnă produs nou la consumator, istoric de campanii pierdut.

- Toate feedurile Mulwi foloseau **ID-ul de produs**, un item per produs. Replicile și Favi acaju îl păstrează. La produsele cu mai multe variante, prețul, SKU-ul, stocul și greutatea vin de la varianta cu ID-ul cel mai mic, exact cum făcea Mulwi.
- Favi ocean e live cu **ID de variantă** și rămâne așa.

---

## Cum se face tranziția unui consumator

Pentru fiecare rând din tabelul de mai sus, în ordinea asta, fără să sari pași:

1. **Publicare în paralel.** Feedul nou e deja publicat și se actualizează la fiecare 2 ore. Feedul Mulwi rămâne neatins.
2. **Verificare.** Deschide adresa nouă în browser, verifică numărul de produse pe pagina de index și, dacă vrei, rulează diff-ul (vezi mai jos).
3. **Schimbarea adresei la consumator.** Persoana din coloana „cine schimbă adresa" înlocuiește adresa Mulwi cu cea nouă. La Favi, adresa se schimbă doar prin managerul de cont și doar cu aceleași ID-uri, altfel se pierde istoricul.
4. **Monitorizare.** Câteva zile: la consumator nu trebuie să apară produse noi, produse dispărute sau erori de citire. Rularea programată trebuie să fie verde.
5. **Abia apoi** se poate opri feedul Mulwi respectiv, decizie luată de tine cu șeful, nu de acest proiect. Când toate feedurile unui cont Mulwi sunt oprite, abonamentul se poate închide.

Repo-ul vechi de pe contul personal, `birzugeorge24-boop/dynamic-feeds`, publică în continuare feedul Favi ocean la adresa veche. Rămâne viu până schimbi adresa în dashboardul Favi și confirmi; abia apoi îl arhivezi manual.

---

## Cum urmăresc rulările

Tabul **Actions** din repo arată fiecare rulare. Rularea are trei pași: generarea, publicarea și un pas final care semnalează feedurile picate.

Deschide o rulare și te uiți la **Summary**. Acolo e un tabel cu fiecare feed: publicat, păstrat cel vechi sau lipsă, plus numărul de produse și motivele pentru care au picat produse.

**Un feed care pică nu blochează celelalte.** Feedurile bune se publică oricum. Pentru cel picat, în locul lui rămâne versiunea aflată deja online, ca adresa lui să nu rămână goală. Abia după publicare rularea se face roșie și primești mail.

**Dacă primești mail că rularea a eșuat**, deschide rularea și citește tabelul din Summary. Cauzele obișnuite:

| Ce scrie | Ce s-a întâmplat | Ce faci |
| --- | --- | --- |
| `401: token invalid sau expirat` | Tokenul Shopify al unui magazin nu mai e bun | Rotești tokenul, vezi mai jos |
| `403: aplicația nu are dreptul read_products` | Aplicația a fost dezinstalată din Shopify | O reinstalezi |
| `oprit de frâna de siguranță` | Feedul ar fi avut brusc mult mai puține produse | Vezi secțiunea despre frână |
| `niciun produs nu trece selecția` | Tagul de selecție nu mai e pe niciun produs | Verifici tagul în Shopify și în configurarea feedului |
| `nu trece validarea` | Feedul ar fi fost respins de consumator | Citești eroarea; de obicei e un produs cu date stricate |
| `lipsesc credențialele` | Un secret lipsește de pe GitHub | Settings → Secrets and variables → Actions |

Rularea programată pornește singură la fiecare 2 ore. Poți porni una manual oricând: **Actions** → în stânga alegi **Feeduri marketplace** → **Run workflow**. Poți restrânge la anumite feeduri scriind numele lor, separate prin virgulă, în căsuța „feeduri".

---

## Cum citesc rapoartele

Rapoartele sunt private: le vede doar cine are acces la repo. Ca să le iei:

1. Tabul **Actions** → click pe rularea care te interesează.
2. Derulează până jos, la secțiunea **Artifacts**.
3. Click pe **rapoarte**. Se descarcă o arhivă zip cu câte un `raport-<feed>.csv` pentru fiecare feed.

Rapoartele se păstrează 30 de zile, apoi se șterg singure. Un rezumat pe motive apare direct în **Summary**-ul rulării.

Fiecare CSV se deschide în Excel. Are șase coloane: motivul, explicația în română, ID-ul, dacă ID-ul e al produsului sau al variantei, titlul și detaliile. O linie per problemă.

Motivele care înseamnă că produsul **nu a intrat** în feed:

- **fara_url** — produsul nu e publicat pe Online Store; doar feedurile Favi cer pagină publică.
- **fara_categorie** — Type-ul din Shopify nu e în maparea de categorii Favi. Vezi mai jos cum adaugi unul.
- **fara_imagine** — produsul nu are nicio imagine. La replici intră totuși, cu imaginea goală, cum făcea Mulwi.
- **exclus_date_lipsa** — îi lipsește categoria, imaginea, adresa, descrierea sau prețul.

Motivele care sunt doar avertismente:

- **fara_stoc_in_feed** — produs fără stoc, trimis la Favi cu termen de livrare de 30 de zile.
- **fara_dimensiuni** — nicio dimensiune, nici în tabel, nici în titlu; Favi nu îl prinde în filtre.
- **fara_parametri** — descrierea nu are tabel de specificații.
- **imagine_sub_600px** — imaginea principală e prea mică pentru Favi.
- **fara_pret_livrare** — varianta nu are greutate în Shopify.
- **nepublicat_in_feed** — produs nepublicat pe Online Store, intrat totuși într-o replică, cu adresa construită din handle, cum făcea Mulwi.

---

## Ce pot schimba și de unde

Toate setările sunt în folderul `config/`. Le modifici direct pe GitHub: intri în fișier, apeși creionul din dreapta sus, editezi, apoi **Commit changes**. Modificarea declanșează automat o rulare nouă.

| Fișier | Ce conține |
| --- | --- |
| `config/magazine.yaml` | Magazinele: numele variabilelor cu credențiale, adresa produselor, termenele și grila de livrare |
| `config/publicare.yaml` | Adresa de bază a feedurilor și pragul frânei de siguranță |
| `config/feeduri/<nume>.yaml` | Un fișier per feed: magazin, format, selecție, politică de ID, fișier publicat |
| `config/categorii_favi.yaml` | Maparea Type Shopify → categorie Favi |
| `config/dimensiuni_favi.yaml` | Familiile de dimensiuni pe categorii Favi |
| `config/parametri.yaml` | Normalizarea numelor de parametri din tabelele de specificații |

### Selecția produselor unui feed

În `config/feeduri/<nume>.yaml`, secțiunea `selectie`:

```yaml
selectie:
  tag: "OCEANFAVI"                                     # doar produsele cu acest tag
  fara_taguri: ["FARA ADD TO CART", "RESIGILATE"]      # fără niciunul dintre aceste taguri
  doar_publicate: true                                 # doar cu pagină pe Online Store
```

Potrivirea tagurilor e exactă și nu ține cont de majuscule. Fără niciun filtru intră tot catalogul activ.

### Termenele și prețurile de livrare

În `config/magazine.yaml`, secțiunea `livrare` a fiecărui magazin. `zile_in_stoc` și `zile_fara_stoc` sunt termenele pentru Favi; Favi afișează „în stoc" doar pentru valorile 0 până la 3. Tagurile din `dupa_tag` au prioritate față de stoc. `preturi_kg` e grila GLS: fiecare rând e `[greutate_maximă_kg, preț_lei]`, primul prag mai mare sau egal cu greutatea produsului dă prețul. Grila e aceeași la ambele magazine.

### Maparea categoriilor Favi

În `config/categorii_favi.yaml`, secțiunea `dupa_type`:

```yaml
  Scaune: "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie"
```

Când raportul zice `fara_categorie` pentru un Type, adaugi un rând nou aici. Calea trebuie să existe exact în arborele Favi, cu diacritice și cu `>` între nivele. Maparea e comună ambelor magazine.

### Pragul frânei de siguranță

În `config/publicare.yaml`, `prag_minim_procent: 70`. Se poate suprascrie per feed, în fișierul lui, cu o secțiune `frana`.

### Un feed nou

Copiezi un fișier existent din `config/feeduri/` sub alt nume, schimbi magazinul, selecția și fișierul publicat. Formatele disponibile: `favi`, `google`, `rtb`, `dsa`. Pentru al treilea magazin adaugi o intrare în `config/magazine.yaml` și cele două secrete pe GitHub.

---

## Frâna de siguranță

Înainte de publicare, pentru fiecare feed în parte, sistemul descarcă versiunea aflată online și numără produsele. Dacă feedul nou are sub 70% din câte avea cel vechi, **nu îl publică**: în locul lui rămâne cel vechi, iar rularea se face roșie.

E acolo pentru cazul în care ceva se strică tăcut: tagul șters din greșeală de pe jumătate din produse, o eroare care exclude o categorie întreagă, un import Shopify prost. Dacă versiunea online nu poate fi citită, frâna oprește publicarea acelui feed, nu o lasă să treacă.

**Când se declanșează:** deschizi raportul din rularea eșuată și te uiți ce motiv a crescut brusc. Dacă scăderea e reală și intenționată, pornești o rulare manuală și bifezi **Publică chiar dacă frâna de siguranță ar opri un feed**.

La prima publicare a unui feed, când încă nu există versiune online, frâna se sare automat.

---

## Cum rotesc tokenul Shopify

Tokenurile nu sunt niciodată în cod sau în git. Stau în Secrets, pe GitHub, și în fișierul local `.env`, care e ignorat de git. Fiecare magazin are perechea lui:

| Magazin | Secrete |
| --- | --- |
| ocean.ro | `SHOPIFY_STORE`, `SHOPIFY_TOKEN` |
| acaju.ro | `SHOPIFY_STORE_ACAJU`, `SHOPIFY_TOKEN_ACAJU` |

**Aplicație custom creată în admin (token care începe cu `shpat_`):**

1. Shopify admin → **Settings** → **Apps** → secțiunea **Legacy custom apps** → aplicația.
2. Dezinstalează aplicația, apoi instaleaz-o din nou. Tokenul se poate vedea o singură dată, imediat după instalare. Copiază-l atunci.
3. Nu șterge aplicația. Ștearsă, nu mai poate fi recreată.
4. Pe GitHub: **Settings** → **Secrets and variables** → **Actions** → la secretul respectiv apeși pe creion → lipești valoarea nouă → **Update secret**.

**Aplicație creată în Dev Dashboard (Client ID + Client secret):** [dev.shopify.com/dashboard](https://dev.shopify.com/dashboard/) → **Apps** → aplicația → **Settings** → **Credentials** → **Rotate**. Sistemul acceptă și această variantă, prin secretele `SHOPIFY_CLIENT_ID` și `SHOPIFY_CLIENT_SECRET`.

---

## Rulare pe calculatorul tău

Ai nevoie de Python 3.11 sau mai nou.

```bash
pip install -r requirements.txt
```

Copiază `.env.example` în `.env` și completează secretele ambelor magazine. Apoi:

```bash
python genereaza.py
```

Scrie toate feedurile în `out/`, cu rapoartele lângă ele. Nu publică nimic. Opțiuni utile:

```bash
python genereaza.py --feed acajugoogle --feed acajudsa   # doar anumite feeduri
python genereaza.py --magazin acaju                      # toate feedurile unui magazin
python genereaza.py --limita 300                          # catalog trunchiat, pentru testarea frânei
python genereaza.py --fara-frana                          # sare peste frâna de siguranță
```

Raportul de diff față de feedurile Mulwi, descărcate în același interval cu generarea noastră:

```bash
python scripts/diff_mulwi.py
```

Scrie `docs/diff_mulwi_<data>.md`. Merită rulat înainte de fiecare tranziție și după orice schimbare de reguli.

Testele:

```bash
python -m pytest tests -q
```

---

## Cum e organizat codul

| Fișier | Ce face |
| --- | --- |
| `genereaza.py` | O extragere per magazin, apoi fiecare feed independent: selecție, generare, validare, frână |
| `src/extragere.py` | Vorbește cu Shopify. Nu știe nimic despre feeduri |
| `src/selectie.py` | Alege produsele unui feed după taguri și publicare |
| `src/normalizare.py` | Descrieri, parametri, dimensiuni, titluri, pentru Favi |
| `src/favi.py` | Formatul Heureka pentru Favi |
| `src/replica.py`, `src/google.py`, `src/rtb.py`, `src/dsa.py` | Replicile feedurilor Mulwi |
| `src/validare.py` | Verificările pe fiecare format și frâna de siguranță |
| `src/raport.py` | Rapoartele CSV și rezumatul din Actions |
| `scripts/diff_mulwi.py` | Raportul de diff față de Mulwi |
| `scripts/verifica_stare.py` | Pasul final care face rularea roșie dacă un feed a picat |

Logica pentru Favi e portată din `genereaza_feed_favi.py`, generatorul care mergea pe exporturi Excel, păstrat în repo ca referință.

---

## Întreținere

Sistemul nu are nimic de făcut în mod curent. Lucrurile de mai jos sunt fie automatizate, fie rare, fie semnalate singure.

**Rulările programate pe repo public.** GitHub le oprește după 60 de zile fără niciun commit în repo. E automatizat: la fiecare rulare programată, jobul „Ține repo-ul activ" verifică vârsta ultimului commit și, dacă a trecut de 45 de zile, face unul gol. Nu trebuie făcut nimic. Dacă totuși se întâmplă vreodată, GitHub trimite mail, iar reactivarea e un buton: **Actions** → workflow-ul → **Enable workflow**.

**Versiunea de API Shopify.** Shopify scoate o versiune nouă la fiecare trei luni și le retrage după aproximativ un an; cea folosită acum, `2026-07`, e disponibilă până pe 16 iulie 2027. După retragere Shopify răspunde automat cu cea mai veche versiune încă disponibilă, deci feedurile nu se opresc, dar sistemul semnalează situația cu un avertisment în Summary-ul rulării. Atunci se schimbă un singur șir, `API_VERSION` din `src/extragere.py`, cu versiunea curentă de pe [shopify.dev](https://shopify.dev/docs/api/usage/versioning).

**Tokenurile Shopify.** Cele din aplicațiile custom create în admin nu expiră. Shopify a anunțat că aplicațiile de acest tip existente continuă să funcționeze, dar nu mai pot fi create altele; dacă vreodată le retrage, sistemul acceptă deja și varianta nouă, cu Client ID și Client secret din Dev Dashboard (vezi „Cum rotesc tokenul").

**Versiunile acțiunilor GitHub** din workflow sunt fixate. Merg ani de zile; GitHub anunță din timp, cu avertismente în rulări, când o versiune de runtime iese din uz.

**Data de backorder din Google acaju.** Pentru produsele fără stoc, feedul trimite o dată fixă, `2026-10-15`, moștenită din setările Mulwi. E în `config/feeduri/acajugoogle.yaml`; trebuie actualizată când expiră sau eliminată de comun acord cu agenția. E singurul lucru din listă cu termen.

**Tipuri de produs noi.** Când apare în Shopify un Type care nu e în maparea Favi, produsele lui apar în raport ca `fara_categorie` și nu intră în feedurile Favi până nu adaugi rândul în `config/categorii_favi.yaml`. Nu e mentenanță, e operare curentă; raportul te anunță.

---

## Îmbunătățiri posibile după stabilizare

Doar notate, neimplementate. Fiecare schimbă valori pe care consumatorii le văd, deci se face cu cei care administrează campaniile.

- **google_product_category** e trimis gol, cum era la Mulwi. O mapare pe taxonomia Google ar îmbunătăți relevanța în Shopping.
- **brand** conține codurile interne de furnizor (ACAJU-H, OCEAN - B), păstrate pentru continuitate. Un brand real ar fi mai util în anunțuri.
- **gtin** lipsește la ocean și la două treimi din acaju. Codurile EAN reale se pot aduce de la furnizori și pune pe variante în Shopify; feedurile le preiau automat.
- **additional_image_link** la Facebook ocean reproduce formatul Mulwi, cu toate imaginile într-un singur element, între paranteze drepte. Formatul corect e câte un element per imagine.
- **shipping_weight** reproduce artefactele de virgulă mobilă ale Mulwi (147.20000000000002 kg). O formatare curată e trivială, dar schimbă valorile trimise.
- **Cele 19 produse de pe acaju** cu tipuri nemapate pe Favi intră în feed imediat ce maparea e aprobată.
