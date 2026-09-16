# Feeduri dinamice pentru marketplace-uri

Generează automat feedul XML pentru **Favi.ro** din produsele magazinului Shopify **ocean.ro**, la fiecare 2 ore, și îl publică la o adresă fixă.

**Adresa feedului, cea pe care o dai la Favi:**

```
https://birzugeorge24-boop.github.io/dynamic-feeds/oceanfavi.xml
```

La [adresa de bază](https://birzugeorge24-boop.github.io/dynamic-feeds/) e o pagină care arată câte produse are feedul și când a fost generat ultima dată.

Raportul cu produsele problematice **nu se publică**, pentru că include produse nepublicate sau arhivate. Îl descarci din pagina rulării, vezi mai jos.

---

## Ce face sistemul

1. Citește produsele din Shopify prin Admin API, filtrate după tagul `OCEANFAVI`.
2. Le transformă în format Heureka, așa cum cere Favi.
3. Verifică rezultatul: fără ID-uri sau adrese duplicate, fără linkuri în descrieri, prețuri în format corect.
4. Compară cu feedul aflat online. Dacă numărul de produse scade brusc, nu publică nimic și rularea eșuează vizibil.
5. Publică feedul și raportul pe GitHub Pages.

Un produs intră în feed doar dacă are tagul, e publicat pe Online Store, are o categorie mapabilă, cel puțin o imagine și un preț. Orice produs care pică e trecut în raport cu motivul exact.

---

## Cum urmăresc rulările

Tabul **Actions** din repo arată fiecare rulare. Verde înseamnă că feedul s-a publicat, roșu că nu.

Deschide o rulare și te uiți la **Summary**. Acolo găsești un tabel cu: câte produse aveau tagul, câte au intrat în feed, câte categorii distincte, și un tabel cu motivele pentru care au picat produse. Tot acolo scrie ce a decis frâna de siguranță.

**Dacă primești mail că rularea a eșuat**, deschide rularea și citește ultimele linii din pasul „Generează feedul". Cauzele obișnuite:

| Ce scrie | Ce s-a întâmplat | Ce faci |
| --- | --- | --- |
| `401: token invalid sau expirat` | Tokenul Shopify nu mai e bun | Rotești tokenul, vezi mai jos |
| `403: aplicația nu are dreptul read_products` | Aplicația a fost dezinstalată din Shopify | O reinstalezi |
| `OPRIT: feedul nou are N produse` | Au dispărut brusc multe produse | Vezi secțiunea despre frână |
| `Niciun produs cu tagul OCEANFAVI` | Tagul a fost șters de pe toate produsele | Verifici în Shopify |
| `EROARE de validare` | Feedul ar fi fost respins de Favi | Citești eroarea; de obicei e un produs cu date stricate |

Rularea programată pornește singură la fiecare 2 ore. Poți porni una manual oricând: **Actions** → în stânga alegi **Feed Favi ocean.ro** → butonul **Run workflow** → încă o dată **Run workflow**.

---

## Cum citesc raportul

Raportul e privat: îl vede doar cine are acces la repo. Ca să-l iei:

1. Tabul **Actions** → în stânga, **Feed Favi ocean.ro** → click pe rularea care te interesează.
2. Derulează până jos, la secțiunea **Artifacts**.
3. Click pe **raport**. Se descarcă o arhivă zip cu `raport.csv` înăuntru.

Rapoartele se păstrează 30 de zile, apoi se șterg singure.

`raport.csv` se deschide în Excel. Are șase coloane: motivul, explicația în română, ID-ul, dacă ID-ul e al produsului sau al variantei, titlul și detaliile. O linie per problemă.

Un rezumat pe motive apare direct în **Summary**-ul rulării, fără să descarci nimic.

Motivele care înseamnă că produsul **nu a intrat** în feed:

- **fara_url** — produsul nu e publicat pe Online Store. E cel mai frecvent motiv. Fie a fost arhivat, fie i-ai scos canalul Online Store în Shopify.
- **fara_categorie** — Type-ul din Shopify nu e în maparea de categorii. Vezi mai jos cum adaugi unul.
- **fara_imagine** — produsul nu are nicio imagine.
- **exclus_date_lipsa** — îi lipsește categoria, imaginea, adresa sau prețul.

Motivele care sunt doar avertismente, produsul a intrat totuși:

- **fara_stoc_in_feed** — produs fără stoc, trimis cu termen de livrare de 30 de zile.
- **fara_dimensiuni** — nicio dimensiune, nici în tabelul din descriere, nici în titlu. Favi nu îl va prinde în filtrele de dimensiuni, deci se vede mai puțin.
- **fara_parametri** — descrierea nu are tabel de specificații.
- **imagine_sub_600px** — imaginea principală e prea mică, Favi poate bloca afișarea.
- **fara_pret_livrare** — varianta nu are greutate în Shopify, deci nu am putut calcula prețul de livrare.

---

## Ce pot schimba și de unde

Toate setările sunt în folderul `config/`. Le modifici direct pe GitHub: intri în fișier, apeși creionul din dreapta sus, editezi, apoi **Commit changes**. Modificarea declanșează automat o rulare nouă.

### Tagul care selectează produsele

În [`config/ocean.yaml`](config/ocean.yaml), secțiunea `selectie`:

```yaml
selectie:
  tag: "OCEANFAVI"
```

### Termenele de livrare

Tot în `config/ocean.yaml`, secțiunea `livrare`. `zile_in_stoc` e termenul pentru produsele pe stoc, `zile_fara_stoc` pentru cele fără. Favi afișează „în stoc" doar pentru valorile 0 până la 3.

Tagurile au prioritate față de stoc:

```yaml
  dupa_tag:
    livrare14zile: 14
```

Ca să adaugi o regulă nouă, pui tagul din Shopify și numărul de zile pe un rând nou, la fel aliniat.

### Prețurile de livrare

În aceeași secțiune, `preturi_kg` e grila GLS. Fiecare rând e `[greutate_maximă_kg, preț_lei]`. Primul prag mai mare sau egal cu greutatea produsului dă prețul. Dacă se schimbă grila la curier, modifici cifrele aici.

### Maparea categoriilor

În [`config/categorii_favi.yaml`](config/categorii_favi.yaml). Secțiunea `dupa_type` leagă Type-ul din Shopify de o cale din arborele Favi:

```yaml
  Scaune: "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie"
```

Când raportul zice `fara_categorie` pentru un Type, adaugi un rând nou aici. Calea trebuie să existe exact în arborele Favi, cu diacritice și cu `>` între nivele.

Secțiunea `dupa_titlu` e pentru corecții care se uită la titlu în loc de Type, și are prioritate.

### Numele parametrilor

În [`config/parametri.yaml`](config/parametri.yaml). `redenumiri` normalizează numele din tabelele de specificații (fără diacritice în stânga, cu diacritice în dreapta). `unitate_cm` și `unitate_kg` sunt parametrii la care se adaugă automat unitatea când valoarea e doar un număr.

### Pragul frânei de siguranță

În `config/ocean.yaml`, `prag_minim_procent: 70`.

---

## Frâna de siguranță

Înainte de publicare, sistemul descarcă feedul aflat online și numără produsele. Dacă feedul nou are sub 70% din câte avea cel vechi, **nu publică** și rularea eșuează. Feedul vechi rămâne la adresa lui, deci Favi continuă să citească datele bune.

E acolo pentru cazul în care ceva se strică tăcut: tagul șters din greșeală de pe jumătate din produse, o eroare care exclude o categorie întreagă, un import Shopify prost.

**Când se declanșează:** deschizi raportul din rularea eșuată și te uiți ce motiv a crescut brusc. Dacă scăderea e reală și intenționată (ai scos tu produse), pornești o rulare manuală și bifezi **Publică chiar dacă frâna de siguranță ar opri rularea**.

La prima rulare, când încă nu există feed online, frâna se sare automat.

---

## Cum rotesc tokenul Shopify

Tokenul nu e niciodată în cod sau în git. Stă în Secrets, pe GitHub, și în fișierul local `.env`, care e ignorat de git.

**Dacă ai aplicație custom veche (token care începe cu `shpat_`):**

1. Shopify admin → **Settings** → **Apps** → secțiunea **Legacy custom apps** → aplicația ta.
2. Dezinstalează aplicația, apoi instaleaz-o din nou. Tokenul se poate vedea o singură dată, imediat după instalare. Copiază-l atunci.
3. Nu șterge aplicația. Ștearsă, nu mai poate fi recreată.
4. Pe GitHub: **Settings** → **Secrets and variables** → **Actions** → la `SHOPIFY_TOKEN` apeși pe creion → lipești valoarea nouă → **Update secret**.

**Dacă ai aplicație creată în Dev Dashboard (Client ID + Client secret):**

1. [dev.shopify.com/dashboard](https://dev.shopify.com/dashboard/) → **Apps** → aplicația ta → **Settings** → **Credentials**.
2. **Rotate** lângă Client secret → **Generate new secret**. Vechiul secret rămâne activ până apeși **Revoke** pe el, deci ai timp să schimbi.
3. Pe GitHub actualizezi `SHOPIFY_CLIENT_SECRET`.

Sistemul acceptă ambele variante. Dacă `SHOPIFY_TOKEN` e completat, îl folosește pe el; altfel schimbă Client ID și secret pe un token de 24 de ore, la fiecare rulare.

---

## Rulare pe calculatorul tău

Ai nevoie de Python 3.11 sau mai nou.

```bash
pip install -r requirements.txt
```

Copiază `.env.example` în `.env` și completează `SHOPIFY_STORE` și `SHOPIFY_TOKEN`. Apoi:

```bash
python genereaza.py
```

Scrie `out/oceanfavi.xml` și `out/raport.csv`. Nu publică nimic și nu atinge feedul online.

Opțiuni utile:

```bash
python genereaza.py --limita 50        # doar primele 50 de produse, pentru un test rapid
python genereaza.py --fara-frana       # sare peste frâna de siguranță
python genereaza.py --iesire public    # scrie în alt folder
```

Testele:

```bash
python -m pytest tests -q
```

---

## Cum e organizat codul

Straturile sunt separate ca să putem adăuga Biano și magazinul acaju.ro fără să rescriem nimic.

| Fișier | Ce face |
| --- | --- |
| `genereaza.py` | Leagă pașii și decide dacă feedul e bun de publicat |
| `src/extragere.py` | Vorbește cu Shopify. Nu știe nimic despre Favi |
| `src/normalizare.py` | Descrieri, parametri, dimensiuni, titluri. Comun tuturor canalelor |
| `src/favi.py` | Tot ce e specific Favi: ordinea elementelor, CDATA, limite |
| `src/validare.py` | Verificările pe feed și frâna de siguranță |
| `src/raport.py` | Raportul CSV și rezumatul din Actions |
| `config/` | Datele: categorii, dimensiuni, parametri, setările magazinului |

Pentru un canal nou se adaugă un modul lângă `favi.py`. Pentru un magazin nou se copiază `config/ocean.yaml`.

Logica de transformare e portată din `genereaza_feed_favi.py`, generatorul care mergea pe exporturi Excel. Fișierul e păstrat în repo ca referință. Nu mai e folosit de nimic.

---

## Adresa feedului la Favi

Adresa nu trebuie schimbată niciodată. Dacă totuși se schimbă, feedul nou trebuie să conțină **aceleași `ITEM_ID`**, altfel Favi consideră toate produsele ca noi și pierzi istoricul și pozițiile. Adresa se schimbă scriind managerului de cont Favi, nu din interfață.

Favi citește feedul de trei ori pe zi. Noi îl regenerăm la fiecare 2 ore, deci datele pe care le citesc sunt mereu proaspete.

---

## Întreținere

Shopify scoate o versiune nouă de API la fiecare trei luni și le retrage după aproximativ un an. Versiunea folosită e scrisă în `src/extragere.py`, la `API_VERSION`. Când se apropie termenul, se schimbă acolo un singur șir.

Repo-ul e public, deci GitHub dezactivează rulările programate după 60 de zile fără activitate. Orice modificare de fișier resetează numărătoarea. Dacă se întâmplă, GitHub trimite mail și le reactivezi dintr-un buton, din tabul Actions.
