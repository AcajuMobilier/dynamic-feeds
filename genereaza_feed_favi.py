#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator feed XML Favi (specificația Heureka) pentru ocean.ro
==============================================================
Citește exportul Matrixify (xlsx), extrage parametrii din tabelul HTML
aflat la începutul descrierii (Body HTML) și scrie un feed conform cu
cerințele Favi: https://help.favionline.com/ro/semnificatii-si-cerinte-pentru-elementele-individuale

Rulare:  python3 genereaza_feed_favi.py [cale_export.xlsx]
Ieșire:  favi_feed_ocean.xml + raport_feed_favi.csv
"""

import sys, re, html, csv
import pandas as pd
from bs4 import BeautifulSoup, NavigableString

# ============================ CONFIG ============================

INPUT_XLSX  = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/Ocean_Favi_cu_stoc.xlsx"
OUTPUT_XML  = "favi_feed_ocean.xml"
OUTPUT_CSV  = "raport_feed_favi.csv"

# Dacă exportul nu are coloana URL (sau Handle), URL-urile se iau din
# sitemap-ul magazinului: fiecare <url> conține și imaginea principală,
# iar potrivirea se face pe Image Src. Sitemap-ul e generat de Shopify în
# timp real, deci reflectă handle-urile curente și include doar produsele
# publicate pe Online Store — un produs care lipsește de acolo nu are
# pagină publică și nu are ce căuta în feed.
SITEMAP_URL   = "https://www.ocean.ro/sitemap.xml"
SITEMAP_CACHE = "sitemap_ocean_urls.json"   # se refolosește dacă descărcarea eșuează
# Surse de rezervă când sitemap-ul nu e accesibil (ex. IP blocat de anti-bot):
URL_ARHIVA_FEED   = "/mnt/user-data/outputs/favi_feed_ocean.xml"       # feedul precedent: Variant ID -> URL
URL_ARHIVA_EXPORT = "/mnt/user-data/uploads/Ocean_Favi_cu_stoc.xlsx"   # export vechi cu coloana URL: ID -> URL

# Selecția produselor: un produs intră în feed DOAR dacă are acest tag în
# Shopify (potrivire exactă, indiferent de majuscule). Pune None ca să iei
# tot exportul. Pe acaju.ro tagul va fi "favi", pe ocean.ro "oceanfavi".
TAG_FEED = "oceanfavi"

# Produsele tagate rămân în feed și când stocul e 0 — se scot manual, din tag.
# DELIVERY_DATE spune însă adevărul: Favi verifică disponibilitatea la click.
EXCLUDE_FARA_STOC = False
DELIVERY_DATE_IN_STOC = 2      # zile până la expediere pt. produsele pe stoc (0–3 = badge "în stoc" pe Favi)
DELIVERY_DATE_FARA_STOC = 30   # DE CONFIRMAT: termenul real pentru ce nu e pe stoc
# Termen de livrare per produs, luat din tagurile Shopify (au prioritate):
LIVRARE_DUPA_TAG = {"livrare14zile": 14}

# Prețul de livrare (elementul DELIVERY cerut de Favi): calculat per produs
# din greutatea variantei, pe grila GLS din Shopify Shipping (ocean.ro).
# Perechi (limită_superioară_kg, preț_lei) — primul prag >= greutate dă prețul.
CURIER_LIVRARE = "GLS"
PRETURI_LIVRARE_KG = [
    (0.1, 0), (3, 35), (5, 39), (10, 49), (15, 59), (20, 79), (25, 89),
    (31, 119), (35, 129), (50, 139), (70, 169), (100, 199), (200, 249),
    (300, 299), (99999, 399),
]

def pret_livrare_pentru(greutate_kg):
    for limita, pret in PRETURI_LIVRARE_KG:
        if greutate_kg <= limita:
            return pret
    return PRETURI_LIVRARE_KG[-1][1]

# Ce se trimite la MANUFACTURER (element opțional la Favi):
#   "nimic"          -> nu se trimite deloc (implicit)
#   "branduri_reale" -> doar brandurile din lista de mai jos
#   "ocean"          -> brandurile reale își păstrează numele, restul primesc "Ocean"
MANUFACTURER_MODE = "nimic"
PRODUCATORI_REALI = {"KONDELA", "FORTE", "FURNIVAL"}

# ---------------- Mapare Type (Shopify) -> categorie Favi ----------------
# Căile respectă arborele Favi.ro: https://favi.ro/ramificaie-de-categorii
CATEGORII = {
    "Scaune":                    "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie",
    "Masa":                      "Bucătărie > Mobilă de bucătărie > Mese de bucătărie",
    "Masuta":                    "Living > Măsuțe",
    "Fotolii":                   "Living > Fotolii",
    "Comoda":                    "Living > Comode",
    "Paturi":                    "Dormitor > Paturi",
    "Scaune birou":              "Birou > Scaune de birou",
    "Scaun gaming":              "Birou > Scaune de birou",
    "Scaun bar":                 "Bucătărie > Mobilă de bucătărie > Scaune pentru bar",
    "Masa bar":                  "Bucătărie > Mobilă de bucătărie > Mese de bar",
    "Dulap":                     "Dormitor > Dulapuri de haine și dressinguri",
    "Dressing":                  "Dormitor > Dulapuri de haine și dressinguri",
    "Noptiere":                  "Dormitor > Noptiere",
    "Covor Living":              "Textile > Covoare",
    "Covor Hol":                 "Textile > Covoare",
    "Covor Dormitor":            "Textile > Covoare",
    "Covoare Pufoase":           "Textile > Covoare",
    "Taburet":                   "Living > Otomane",
    "Pantofar":                  "Hol > Dulapuri de pantofi",
    "Vitrina":                   "Living > Vitrine",
    "Birouri":                   "Birou > Mese de birou",
    "Masa birou":                "Birou > Mese de birou",
    "Set birou":                 "Birou > Seturi de birou",
    "Saltele":                   "Dormitor > Saltele și accesorii",
    "Somiera":                   "Dormitor > Saltele și accesorii",
    "Biblioteca":                "Living > Biblioteci",
    "Bucatarii":                 "Bucătărie > Linii de bucătărie",
    "Dulap bucatarie":           "Bucătărie > Mobilă de bucătărie > Dulapuri de bucătărie",
    "Canapele":                  "Living > Canapele",
    "Coltare":                   "Living > Canapele",
    "Bancheta":                  "Hol > Taburete și banchete",
    "Polita":                    "Living > Etajere",
    "Etajera":                   "Living > Etajere",
    "Rafturi":                   "Living > Rafturi",
    "Lenjerii de pat":           "Textile > Lenjerii de pat",
    "PACHET-TEXTILE":            "Textile > Lenjerii de pat",
    "Cuverturi pat":             "Textile > Textile pentru dormitor",
    "Huse de pat":               "Textile > Huse",
    "Perne si fete de perna":    "Textile > Perne și fețe de perne",
    "Halat de baie":             "Textile > Textile baie",
    "Scaune Gradina":            "Grădină > Scaune de grădină",
    "Masa gradina":              "Grădină > Mese de grădină",
    "Banca gradina":             "Grădină > Bănci terasă și grădină",
    "Set mobilier gradina":      "Grădină > Seturi de grădină",
    "Set masa si scaune gradina":"Grădină > Seturi de grădină",
    "Oglinda perete":            "Dormitor > Oglinzi",
    "Oglinda de podea":          "Dormitor > Oglinzi",
    "Oglinzi":                   "Dormitor > Oglinzi",
    "Set Masa si Scaune":        "Bucătărie > Mobilă de bucătărie > Seturi de mese si scaune",
    "Cuier":                     "Hol > Cuiere",
    "Cuier pom":                 "Hol > Cuiere",
    "Living":                    "Living > Mobilă living",
    "Masa toaleta":              "Dormitor > Măsuțe de toaletă",
    "Hol":                       "Hol > Mobilă pereți hol",
    "Balansoar":                 "Living > Fotolii",
    "Consola":                   "Hol > Mese consolă",
    "Dulap baie":                "Baie > Mobilă baie",
    "Baie":                      "Baie > Mobilă baie",
    "Suport uscator rufe":       "Baie > Accesorii pentru baie",
    "Fotoliu puf":               "Living > Fotolii puf",
    "Dormitor":                  "Dormitor > Seturi de dormitor",
    "Lampa":                     "Corpuri de iluminat > Lustre",
    "Veioza":                    "Corpuri de iluminat > Lămpi de masă",
    "Cutie depozitare":          "Dormitor > Cutii și coșuri pentru depozitare",
    "Stander haine":             "Dormitor > Stative pentru haine",
    "Pentru Copii":              "Camera copiilor > Fotolii și scaune copii",
    "Ghiveci":                   "Decorațiuni > Ghivece de flori",
    "Accesorii decorative":      "Decorațiuni > Mici decorațiuni",
    "Dulap dormitor":            "Dormitor > Dulapuri de haine și dressinguri",
    "Etajera baie":              "Baie > Mobilă baie",
    "Balansoar Gradina":         "Grădină > Balansoare de grădină",
    "Lustre":                    "Corpuri de iluminat > Lustre",
    "Aplica":                    "Corpuri de iluminat > Aplice",
    "Tablouri":                  "Decorațiuni > Tablouri",
    "Ceas de perete":            "Decorațiuni > Ceasuri",
    "Gradina":                   "Grădină > Decorațiuni de grădină",
    "Fotoliu Gradina":           "Grădină > Scaune de grădină",
    "Covor Baie":                "Baie > Covorașe de baie",
    "Covor Copii":               "Camera copiilor > Covoare pentru copii",
    "Covor intrare":             "Textile > Covoare",
    "Prosoape":                  "Textile > Textile baie",
    "Draperii":                  "Textile > Draperii și perdele",
    "Pilote si plapumi":         "Textile > Pilote și pături",
    "Accesorii baie":            "Baie > Accesorii pentru baie",
    "Organizator baie":          "Baie > Accesorii pentru baie",
    "Stander prosoape":          "Baie > Accesorii pentru baie",
    "Suport umerase":            "Dormitor > Stative pentru haine",
    "Tava si platouri":          "Bucătărie > Veselă",
    "Set farfurii":              "Bucătărie > Veselă",
    "Ustensile bucatarie":       "Bucătărie > Ustensile de bucătărie",
    "Suporturi bucatarie":       "Bucătărie > Ustensile de bucătărie",
    "Borcane si Recipiente bucatarie": "Bucătărie > Depozitarea alimentelor",
}
# căutarea în mapare nu ține cont de majuscule ("Masa Gradina" = "Masa gradina")
CATEGORII_LC = {k.strip().lower(): v for k, v in CATEGORII.items()}
# Corecții punctuale după titlu (au prioritate față de Type):
CATEGORII_DUPA_TITLU = [
    (re.compile(r"suport\s+umbrel", re.I),      "Hol > Suporturi umbrelă"),
    (re.compile(r"rama\s+iluminatoare", re.I),  "Living > Mobilă living"),
    (re.compile(r"scaun\s+de\s+bar", re.I),     "Bucătărie > Mobilă de bucătărie > Scaune pentru bar"),
    (re.compile(r"canapea", re.I),              "Living > Canapele"),
    (re.compile(r"coltar|colțar", re.I),        "Living > Canapele"),
]

# ---------------- Normalizarea numelor de parametri ----------------
# Favi combină denumiri apropiate, dar trimitem forme curate, cu diacritice,
# și unificăm dubletele (4 variante de „greutate maximă" -> una singură).
PARAM_RENAME = {
    "Lungime": "Lungime",
    "Latime": "Lățime",
    "Adancime": "Adâncime",
    "Inaltime": "Înălțime",
    "Inaltime totala": "Înălțime totală",
    "Inaltime sezut": "Înălțime șezut",
    "Inaltime pana la sezut": "Înălțime șezut",
    "Grosime(cm)": "Grosime",
    "Grosime": "Grosime",
    "Dimensiuni": "Dimensiuni",
    "Greutate": "Greutate",
    "Greutate maxima suportata": "Greutate maximă suportată",
    "Greutatea maxima suportata": "Greutate maximă suportată",
    "Capacitate maxima suportata": "Greutate maximă suportată",
    "Capacitate maxima greutate": "Greutate maximă suportată",
    "Culoare": "Culoare",
    "Culoare picioare": "Culoare picioare",
    "Culoare sezut": "Culoare șezut",
    "Culoare blat": "Culoare blat",
    "Culoare cadru": "Culoare cadru",
    "Material": "Material",
    "Materiale": "Material",
    "Material sezut": "Material șezut",
    "Material picioare": "Material picioare",
    "Material blat": "Material blat",
    "Material cadru": "Material cadru",
    "Material manere": "Material mânere",
    "Materiale masa": "Material masă",
    "Materiale scaune": "Material scaune",
    "Forma": "Formă",
    "Garantie": "Garanție",
    "Numar sertare": "Număr sertare",
    "Numar usi": "Număr uși",
    "Numar Usi": "Număr uși",
    "Numar piese": "Număr piese",
    "Numar corpuri": "Număr corpuri",
    "Numar persoane": "Număr persoane",
    "Extensibila": "Extensibilă",
    "Picioare": "Cu picioare",
    "Cu brate": "Cu brațe",
    "Cu rafturi": "Cu rafturi",
    "Spatiu depozitare": "Spațiu de depozitare",
    "Spatiu de depozitare": "Spațiu de depozitare",
    "Tip (usi, sertare, rafturi)": "Tip",
    "Tip (usi, sertare)": "Tip",
    "Tip": "Tip",
    "Tip fotoliu": "Tip fotoliu",
    "Tip comoda": "Tip comodă",
    "Tip somiera": "Tip somieră",
    "Sistem": "Sistem",
    "Sistem de inchidere": "Sistem de închidere",
    "Saltea": "Saltea inclusă",
    "Somiera pat": "Somieră inclusă",
    "Pentru saltea cu dimensiunea": "Pentru saltea cu dimensiunea",
    "Setul contine": "Setul conține",
    "Detalii tehnice": "Detalii tehnice",
    "Fermitatea saltelei": "Fermitatea saltelei",
    "Compartimentare": "Compartimentare",
    "Dimensiune masa mare": "Dimensiune masă mare",
    "Dimensiune masa mica": "Dimensiune masă mică",
}
# „Categorie" din tabel e navigație internă (link la colecție), nu parametru.
PARAM_SKIP = {"Categorie"}

# ---------------- Aliniere dimensiuni la filtrele Favi ----------------
# Convenția ocean.ro: „Lungime" = dimensiunea frontală la orice produs.
# Favi filtrează însă diferit per categorie (vezi coloana „Dimensiuni
# recomandate" din lista de categorii Favi):
#   FAM_A  mobilier frontal (scaune, dulapuri, comode, canapele...):
#          filtre = adâncime + înălțime + lățime  ->  Lungime devine Lățime
#   FAM_B  mese & textile (masă, covor, măsuță...):
#          filtre = lungime + lățime              ->  Adâncime devine Lățime
#   FAM_PAT paturi: cadrul e „lat x lung"         ->  Lungime->Lățime, Adâncime->Lungime
# Categoriile nemenționate rămân neschimbate.
FAM_A   = {"Lungime": "Lățime"}
FAM_B   = {"Adâncime": "Lățime"}
FAM_PAT = {"Lungime": "Lățime", "Adâncime": "Lungime"}
DIM_FAMILIA = {
    "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie": FAM_A,
    "Bucătărie > Mobilă de bucătărie > Scaune pentru bar":   FAM_A,
    "Bucătărie > Mobilă de bucătărie > Dulapuri de bucătărie": FAM_A,
    "Bucătărie > Linii de bucătărie":                        FAM_A,
    "Birou > Scaune de birou":                               FAM_A,
    "Birou > Seturi de birou":                               FAM_A,
    "Living > Fotolii":                                      FAM_A,
    "Living > Canapele":                                     FAM_A,
    "Living > Comode":                                       FAM_A,
    "Living > Vitrine":                                      FAM_A,
    "Living > Biblioteci":                                   FAM_A,
    "Living > Etajere":                                      FAM_A,
    "Living > Rafturi":                                      FAM_A,
    "Dormitor > Dulapuri de haine și dressinguri":           FAM_A,
    "Dormitor > Noptiere":                                   FAM_A,
    "Dormitor > Oglinzi":                                    FAM_A,
    "Hol > Dulapuri de pantofi":                             FAM_A,
    "Hol > Taburete și banchete":                            FAM_A,
    "Baie > Mobilă baie":                                    FAM_A,
    "Grădină > Scaune de grădină":                           FAM_A,
    "Grădină > Bănci terasă și grădină":                     FAM_A,
    "Grădină > Balansoare de grădină":                       FAM_A,
    "Camera copiilor > Fotolii și scaune copii":             FAM_A,
    "Bucătărie > Mobilă de bucătărie > Mese de bucătărie":   FAM_B,
    "Bucătărie > Mobilă de bucătărie > Mese de bar":         FAM_B,
    "Birou > Mese de birou":                                 FAM_B,
    "Living > Măsuțe":                                       FAM_B,
    "Living > Otomane":                                      FAM_B,
    "Living > Fotolii puf":                                  FAM_B,
    "Dormitor > Măsuțe de toaletă":                          FAM_B,
    "Dormitor > Saltele și accesorii":                       FAM_B,
    "Dormitor > Cutii și coșuri pentru depozitare":          FAM_B,
    "Dormitor > Stative pentru haine":                       FAM_B,
    "Hol > Mese consolă":                                    FAM_B,
    "Hol > Cuiere":                                          FAM_B,
    "Textile > Covoare":                                     FAM_B,
    "Textile > Draperii și perdele":                         FAM_B,
    "Textile > Pilote și pături":                            FAM_B,
    "Baie > Covorașe de baie":                               FAM_B,
    "Camera copiilor > Covoare pentru copii":                FAM_B,
    "Textile > Lenjerii de pat":                             FAM_B,
    "Textile > Textile pentru dormitor":                     FAM_B,
    "Textile > Huse":                                        FAM_B,
    "Textile > Perne și fețe de perne":                      FAM_B,
    "Textile > Textile baie":                                FAM_B,
    "Grădină > Mese de grădină":                             FAM_B,
    "Dormitor > Paturi":                                     FAM_PAT,
}

# Ridică în parametri separați dimensiunile „împachetate" (filtrele Favi
# citesc doar dimensiuni separate): „Pentru saltea cu dimensiunea: 160x200 cm"
# devine Lățime saltea + Lungime saltea; „Dimensiuni: 80x150 cm" (covoare,
# textile) devine Lățime + Lungime.
RE_2DIM = re.compile(r"^(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*cm$", re.I)

# Scaunele au doar „Culoare șezut" / „Culoare picioare", fără „Culoare"
# generală — culoarea produsului din titlu e cea a șezutului, așa că o
# ridicăm și ca parametru „Culoare" pentru filtrul de culoare. Pune False
# dacă preferi să nu se dubleze valoarea.
DERIVA_CULOARE = True

def ajusteaza_pentru_favi(parametri, categorie):
    redenumiri = DIM_FAMILIA.get(categorie or "", {})
    # numele care rămân neschimbate — doar cu acestea poate intra în coliziune o redenumire
    persistente = {k for k, _ in parametri if redenumiri.get(k, k) == k}
    rezultat, folosite = [], set()
    for k, v in parametri:
        nk = redenumiri.get(k, k)
        if nk != k and (nk in persistente or nk in folosite):
            nk = k  # nu suprascriem o cheie deja prezentă
        rezultat.append((nk, v))
        folosite.add(nk)
    chei = {k for k, _ in rezultat}
    extra = []
    for k, v in rezultat:
        m = RE_2DIM.match(v.strip())
        if not m:
            continue
        a, b = m.group(1), m.group(2)
        if k == "Pentru saltea cu dimensiunea" and "Lățime saltea" not in chei:
            extra += [("Lățime saltea", a + " cm"), ("Lungime saltea", b + " cm")]
        elif k == "Dimensiuni" and "Lățime" not in chei and "Lungime" not in chei:
            extra += [("Lățime", a + " cm"), ("Lungime", b + " cm")]
    if DERIVA_CULOARE and "Culoare" not in chei:
        sezut = next((v for k, v in rezultat if k == "Culoare șezut"), None)
        if sezut:
            extra.append(("Culoare", sezut))
    return rezultat + extra

# Chei la care, dacă valoarea e doar un număr, adăugăm unitatea de măsură
# (regula Favi: „Listați unitățile de măsură pentru valorile numerice").
CHEI_CM = {"Lungime", "Lățime", "Adâncime", "Înălțime", "Înălțime totală",
           "Înălțime șezut", "Grosime", "Dimensiuni", "Diametru"}
CHEI_KG = {"Greutate", "Greutate maximă suportată"}

RE_NA    = re.compile(r"^\s*(N/?A\.?(\s*(kg|cm|mm|m|l))?|-|–|\?|nespecificat)\s*$", re.I)
RE_NUM   = re.compile(r"^[\d.,]+(\s*[-–±]\s*[\d.,]+)?$")
RE_URL   = re.compile(r"https?://\S+|www\.\S+")
RE_EMAIL = re.compile(r"\S+@\S+\.\S+")

TAGURI_PERMISE = {"p", "b", "strong", "i", "em", "br", "ul", "li", "ol"}

# ============================ FUNCȚII ============================

def incarca_urluri_sitemap():
    """Întoarce (imagine -> URL produs, titlu -> URL produs) din sitemap-ul Shopify."""
    import json, os, urllib.request
    import xml.etree.ElementTree as ET
    NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "i": "http://www.google.com/schemas/sitemap-image/1.1"}
    UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

    def descarca(u):
        cerere = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(cerere, timeout=60) as r:
            return r.read()

    dupa_img, dupa_titlu = {}, {}
    try:
        index = ET.fromstring(descarca(SITEMAP_URL))
        harti = [s.find("s:loc", NS).text for s in index.findall("s:sitemap", NS)]
        img_multi, titlu_multi = {}, {}
        for harta in [h for h in harti if "products" in h]:
            root = ET.fromstring(descarca(harta))
            for url in root.findall("s:url", NS):
                loc = url.find("s:loc", NS).text
                if "/products/" not in loc:
                    continue
                img = url.find("i:image", NS)
                if img is None:
                    continue
                src = img.find("i:loc", NS)
                if src is not None and src.text:
                    img_multi.setdefault(src.text.split("?")[0], set()).add(loc)
                titlu = img.find("i:title", NS)
                if titlu is not None and titlu.text:
                    titlu_multi.setdefault(curata_text(titlu.text).lower(), set()).add(loc)
        # câteva produse duplicate în magazin împart aceeași imagine (sau același
        # titlu); acolo potrivirea nu e sigură, așa că renunțăm la ea
        dupa_img = {k: next(iter(v)) for k, v in img_multi.items() if len(v) == 1}
        dupa_titlu = {k: next(iter(v)) for k, v in titlu_multi.items() if len(v) == 1}
        ambigue = sum(1 for v in img_multi.values() if len(v) > 1)
        with open(SITEMAP_CACHE, "w", encoding="utf-8") as f:
            json.dump({"img": dupa_img, "titlu": dupa_titlu}, f)
        print(f"Sitemap: {len(img_multi)} produse publicate pe Online Store"
              + (f" ({ambigue} imagini folosite de mai multe produse, ignorate)." if ambigue else "."))
    except Exception as e:
        if os.path.exists(SITEMAP_CACHE):
            print(f"Sitemap indisponibil ({e}); folosesc copia locală {SITEMAP_CACHE}.")
            with open(SITEMAP_CACHE, encoding="utf-8") as f:
                c = json.load(f)
            dupa_img, dupa_titlu = c["img"], c["titlu"]
        else:
            print(f"ATENȚIE: sitemap indisponibil ({e}) și fără copie locală — nu pot construi URL-urile.")
    return dupa_img, dupa_titlu

def curata_text(s):
    return re.sub(r"\s+", " ", str(s)).strip()

def esc(s):
    """Escape XML pentru câmpurile din afara CDATA."""
    return html.escape(curata_text(s), quote=False)

def cdata(s):
    return "<![CDATA[" + s.replace("]]>", "]] >") + "]]>"

def format_pret(p):
    p = float(p)
    return str(int(p)) if p == int(p) else f"{p:.2f}"

def ean_valid(v):
    """GTIN de 8/12/13/14 cifre, cu cifra de control corectă."""
    try:
        s = str(int(float(v)))
    except (ValueError, TypeError):
        return None
    if len(s) not in (8, 12, 13, 14):
        return None
    cifre = [int(c) for c in s]
    suma = sum(d * (3 if (len(cifre) - i) % 2 == 0 else 1) for i, d in enumerate(cifre[:-1]))
    return s if (10 - suma % 10) % 10 == cifre[-1] else None

def extrage_parametri(soup):
    """Extrage perechile cheie/valoare din tabelele HTML și le normalizează."""
    parametri, vazute = [], set()
    for tabel in soup.find_all("table"):
        for tr in tabel.find_all("tr"):
            celule = tr.find_all(["td", "th"])
            if len(celule) < 2:
                continue
            cheie = curata_text(celule[0].get_text(" ", strip=True)).rstrip(":").strip()
            val = curata_text(celule[1].get_text(" ", strip=True))
            if not cheie or cheie in PARAM_SKIP:
                continue
            cheie = PARAM_RENAME.get(cheie, cheie)
            if cheie in vazute:            # fără parametri duplicați (regula Favi)
                continue
            if not val or RE_NA.match(val):  # aruncăm N/A, „-", gol
                continue
            # completăm unitatea de măsură la valorile pur numerice
            if RE_NUM.match(val):
                if cheie in CHEI_CM:
                    val += " cm"
                elif cheie in CHEI_KG:
                    val += " kg"
            parametri.append((cheie, val))
            vazute.add(cheie)
    return parametri

def construieste_descriere(body_html):
    """Scoate tabelele de specificații și lasă doar HTML-ul permis de Favi."""
    soup = BeautifulSoup(body_html, "html.parser")
    parametri = extrage_parametri(soup)
    for tabel in soup.find_all("table"):
        tabel.decompose()
    # titlurile devin paragrafe bold (Favi nu acceptă h1–h6)
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.name = "p"
        continut = tag.decode_contents()
        tag.clear()
        tag.append(BeautifulSoup(f"<strong>{continut}</strong>", "html.parser"))
    # doar tagurile acceptate de Favi; restul se desfac păstrând textul
    # (parcurgem invers: copiii înaintea părinților, altfel unwrap detașează noduri)
    for tag in reversed(soup.find_all(True)):
        if tag.parent is None:
            continue
        if tag.name not in TAGURI_PERMISE:
            tag.unwrap()
    # fără linkuri / emailuri în text (interzise de Favi)
    for nod in soup.find_all(string=True):
        txt = RE_URL.sub("", str(nod))
        txt = RE_EMAIL.sub("", txt)
        if txt != str(nod):
            nod.replace_with(txt)
    htm = str(soup)
    htm = re.sub(r"<p>(\s|&nbsp;|<br\s*/?>)*</p>", "", htm)   # paragrafe goale
    htm = re.sub(r"<ul>\s*</ul>|<ol>\s*</ol>", "", htm)       # liste goale
    htm = re.sub(r"\n{3,}", "\n\n", htm).strip()
    return htm, parametri

def curata_titlu(t):
    t = curata_text(t)
    t = re.sub(r"\bpromo\b\s*", "", t, flags=re.I)   # Favi nu vrea „promo" în titlu
    return curata_text(t)

def sufix_varianta(sku):
    s = str(sku).upper()
    if re.search(r"(^|[^A-Z])(STG|ST)([^A-Z]|$)|DL", s):
        return " (varianta stânga)"
    if re.search(r"(^|[^A-Z])DR([^A-Z]|$)|DP", s):
        return " (varianta dreapta)"
    return f" ({sku})"

RE_TITLU_3DIM = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?", re.I)
RE_TITLU_2DIM = re.compile(r"(?<![\d.,x×])(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*cm", re.I)

def completeaza_dimensiuni_din_titlu(parametri, titlu, categorie):
    """Multe titluri conțin dimensiunile (ex. „..., 45x51x90 cm"). Când tabelul
    nu le are, le luăm de acolo, în aceeași convenție L×A×Î ca tabelul."""
    chei = {k for k, _ in parametri}
    extra = []

    def nr(s):
        return s.replace(",", ".")

    m3 = RE_TITLU_3DIM.search(titlu)
    if m3:
        valori = [nr(x) for x in m3.groups()]
        if all(float(v) <= 1000 for v in valori):
            for cheie, val in zip(("Lungime", "Adâncime", "Înălțime"), valori):
                if cheie not in chei:
                    extra.append((cheie, val + " cm"))
    # a doua pereche de tip „AxB cm" din titlu: la paturi e dimensiunea saltelei,
    # la covoare/textile e dimensiunea produsului
    if categorie:
        text_2dim = RE_TITLU_3DIM.sub(" ", titlu)  # scoatem tripletul, să nu-l reciclăm
        m2 = RE_TITLU_2DIM.search(text_2dim) or RE_TITLU_2DIM.search(titlu if not m3 else "")
        if m2:
            a, b = nr(m2.group(1)), nr(m2.group(2))
            if float(a) <= 1000 and float(b) <= 1000:
                if categorie.startswith("Dormitor > Paturi") and "Pentru saltea cu dimensiunea" not in chei:
                    extra.append(("Pentru saltea cu dimensiunea", f"{a}x{b} cm"))
                elif ("Covoare" in categorie or categorie.startswith("Textile") or "Covorașe" in categorie) \
                        and "Dimensiuni" not in chei and "Lățime" not in chei and "Lungime" not in chei:
                    extra.append(("Dimensiuni", f"{a}x{b} cm"))
    return parametri + extra

def categoria_pentru(tip, titlu):
    for rx, cat in CATEGORII_DUPA_TITLU:
        if rx.search(titlu or ""):
            return cat
    return CATEGORII_LC.get(str(tip).strip().lower()) if pd.notna(tip) else None

# ============================ PIPELINE ============================

def incarca_urluri_arhiva():
    """Surse de rezervă: (Variant ID -> URL) din feedul precedent și
    (Product ID -> URL) din exportul vechi cu coloană URL. URL-urile vechi
    rămân valabile: la schimbarea handle-ului, Shopify creează redirect."""
    import os
    import xml.etree.ElementTree as ET
    dupa_varianta, dupa_pid = {}, {}
    if os.path.exists(URL_ARHIVA_FEED):
        try:
            root = ET.parse(URL_ARHIVA_FEED).getroot()
            for it in root.findall("SHOPITEM"):
                dupa_varianta[int(it.find("ITEM_ID").text)] = it.find("URL").text.split("?")[0]
        except Exception as e:
            print(f"Nu pot citi feedul precedent ({e}).")
    if os.path.exists(URL_ARHIVA_EXPORT):
        try:
            vechi = pd.read_excel(URL_ARHIVA_EXPORT, sheet_name="Products")
            if "URL" in vechi.columns:
                dupa_pid = vechi.drop_duplicates("ID").set_index("ID")["URL"].dropna().to_dict()
        except Exception as e:
            print(f"Nu pot citi exportul de arhivă ({e}).")
    return dupa_varianta, dupa_pid

def rezolva_urluri(df, dupa_titlu, dupa_img, dupa_varianta, dupa_pid, raport):
    """ID produs -> URL. Produsele cu stoc revendică primele URL-ul, ca un
    duplicat fără stoc din magazin să nu blocheze varianta care se vinde.
    Ordinea surselor: sitemap (titlu, apoi imagine) -> feedul precedent
    (Variant ID) -> exportul vechi (Product ID)."""
    from collections import Counter
    candidati = []
    for pid, grup in df.groupby("ID", sort=False):
        primul = grup.iloc[0]
        imagini = list(grup.sort_values("Image Position")["Image Src"].dropna())
        varianti = [int(x) for x in grup["Variant ID"].dropna().unique()]
        candidati.append((pid, curata_text(primul["Title"]), imagini, varianti,
                          primul["Total Inventory Qty"]))
    candidati.sort(key=lambda c: -(c[4] if pd.notna(c[4]) else 0))

    urluri, folosite, surse = {}, {}, Counter()
    for pid, titlu, imagini, varianti, _ in candidati:
        url, sursa = dupa_titlu.get(titlu.lower()), "sitemap"
        if not url:
            for src in imagini:
                url = dupa_img.get(str(src).split("?")[0])
                if url:
                    break
        if not url:
            sursa = "feed precedent"
            for vid in varianti:
                url = dupa_varianta.get(vid)
                if url:
                    break
        if not url:
            url, sursa = dupa_pid.get(pid), "export vechi"
        if url and url in folosite:
            raport.append(["url_ambiguu", pid, titlu,
                           f"trimite la aceeași pagină ca produsul {folosite[url]} — duplicat în magazin"])
            url = None
        if url:
            folosite[url] = pid
            urluri[pid] = url
            surse[sursa] += 1
        else:
            raport.append(["fara_url", pid, titlu,
                           "URL negăsit în nicio sursă — intră în feed la prima rulare cu sitemap accesibil"])
    if surse:
        print("Surse URL:", ", ".join(f"{k}: {v}" for k, v in surse.items()))
    return urluri

def main():
    df = pd.read_excel(INPUT_XLSX, sheet_name="Products")
    raport = []
    if "ID" not in df.columns:
        if "Handle" not in df.columns:
            print("EROARE: exportul nu are nici coloana ID, nici Handle — nu pot identifica produsele.")
            return
        df["ID"] = df["Handle"]
        print("Notă: exportul nu are coloana ID — folosesc Handle drept identificator de produs.")

    # selecția pe tag — singura pârghie de intrare în feed
    if TAG_FEED:
        def are_tag(s):
            return TAG_FEED.lower() in {t.strip().lower() for t in str(s).split(",")}
        tag_per_produs = df.drop_duplicates("ID").set_index("ID")["Tags"].fillna("").map(are_tag)
        selectate = set(tag_per_produs[tag_per_produs].index)
        if not selectate:
            print(f"ATENȚIE: niciun produs nu are tagul {TAG_FEED} — verifică numele tagului.")
        total = df["ID"].nunique()
        df = df[df["ID"].isin(selectate)]
        print(f"Tag {TAG_FEED}: {len(selectate)} produse selectate din {total}.")

    # URL-urile: din export dacă există coloana, altfel din sitemap
    are_url = "URL" in df.columns
    if are_url:
        urluri = {}
    else:
        dupa_img, dupa_titlu = incarca_urluri_sitemap()
        dupa_varianta, dupa_pid = incarca_urluri_arhiva()
        urluri = rezolva_urluri(df, dupa_titlu, dupa_img, dupa_varianta, dupa_pid, raport)

    # --- agregare pe produs: descriere, parametri, imagini, categorie ---
    produse = {}
    for pid, grup in df.groupby("ID", sort=False):
        primul = grup.iloc[0]
        titlu = curata_titlu(primul["Title"])
        body = grup["Body HTML"].dropna()
        descriere, parametri = ("", [])
        if len(body):
            descriere, parametri = construieste_descriere(body.iloc[0])
        if not parametri:
            raport.append(["fara_parametri", pid, titlu, "descrierea nu conține tabel de specificații"])

        imagini = grup[grup["Image Src"].notna()].sort_values("Image Position")
        img_principala, img_alternative = None, []
        if len(imagini):
            img_principala = imagini.iloc[0]["Image Src"]
            img_alternative = list(imagini["Image Src"].iloc[1:21])
            w, h = imagini.iloc[0]["Image Width"], imagini.iloc[0]["Image Height"]
            if pd.notna(w) and (w < 600 or h < 600):
                raport.append(["imagine_sub_600px", pid, titlu, f"{int(w)}x{int(h)} px — Favi poate bloca afișarea"])

        url = primul["URL"] if are_url else urluri.get(pid)

        categorie = categoria_pentru(primul.get("Type"), titlu)
        if not categorie:
            raport.append(["fara_categorie", pid, titlu, f"Type nemapat: {primul.get('Type')}"])

        produse[pid] = dict(
            titlu=titlu, descriere=descriere, parametri=parametri,
            url=url, img=img_principala, img_alt=img_alternative,
            categorie=categorie, vendor=curata_text(primul.get("Vendor", "")),
            stoc=primul["Total Inventory Qty"], taguri=primul.get("Tags", ""),
        )

    # --- iterare pe variante -> SHOPITEM ---
    variante = df[df["Variant ID"].notna()]
    nr_variante_per_produs = variante.groupby("ID")["Variant ID"].nunique()

    itemuri, excluse_stoc = [], 0
    for _, v in variante.drop_duplicates("Variant ID").iterrows():
        p = produse[v["ID"]]
        taguri = {t.strip().lower() for t in str(p["taguri"]).split(",")}
        livrare = next((zile for tag, zile in LIVRARE_DUPA_TAG.items() if tag.lower() in taguri), None)
        if livrare is None:
            if p["stoc"] > 0:
                livrare = DELIVERY_DATE_IN_STOC
            elif EXCLUDE_FARA_STOC:
                excluse_stoc += 1
                raport.append(["exclus_stoc_zero", v["ID"], p["titlu"], f"stoc={p['stoc']}"])
                continue
            else:
                livrare = DELIVERY_DATE_FARA_STOC
                raport.append(["fara_stoc_in_feed", v["ID"], p["titlu"],
                               f"trimis cu DELIVERY_DATE={livrare} zile — confirmă termenul real"])

        if not (p["categorie"] and p["img"] and p["url"] and pd.notna(v["Variant Price"])):
            raport.append(["exclus_date_lipsa", v["ID"], p["titlu"], "lipsește categoria, imaginea, URL-ul sau prețul"])
            continue

        multi = nr_variante_per_produs.get(v["ID"], 1) > 1
        titlu = p["titlu"] + (sufix_varianta(v["Variant SKU"]) if multi else "")
        url = str(p["url"]) + (f"?variant={int(v['Variant ID'])}" if multi else "")

        parametri = completeaza_dimensiuni_din_titlu(list(p["parametri"]), p["titlu"], p["categorie"])
        parametri = ajusteaza_pentru_favi(parametri, p["categorie"])
        chei_dim = {"Lățime", "Lungime", "Adâncime", "Înălțime", "Lățime saltea", "Dimensiuni", "Diametru"}
        if not any(k in chei_dim for k, _ in parametri):
            raport.append(["fara_dimensiuni", v["ID"], p["titlu"],
                           "nicio dimensiune în tabel sau titlu — de completat în Shopify"])
        if not any(k == "Greutate" for k, _ in parametri) and pd.notna(v.get("Variant Weight")) and v["Variant Weight"] > 0:
            g = float(v["Variant Weight"])
            parametri.append(("Greutate", (str(int(g)) if g == int(g) else f"{g:g}") + " kg"))

        rows = [f"    <ITEM_ID>{int(v['Variant ID'])}</ITEM_ID>"]
        if multi:
            gid = re.sub(r"\.0$", "", str(v["ID"]))
            rows.append(f"    <ITEMGROUP_ID>{esc(gid)}</ITEMGROUP_ID>")
        rows.append(f"    <PRODUCTNAME>{esc(titlu)}</PRODUCTNAME>")
        rows.append(f"    <DESCRIPTION>{cdata(p['descriere'])}</DESCRIPTION>")
        rows.append(f"    <CATEGORYTEXT>{esc(p['categorie'])}</CATEGORYTEXT>")
        rows.append(f"    <PRICE_VAT>{format_pret(v['Variant Price'])}</PRICE_VAT>")
        rows.append(f"    <URL>{esc(url)}</URL>")
        rows.append(f"    <IMGURL>{esc(p['img'])}</IMGURL>")
        for alt in p["img_alt"]:
            rows.append(f"    <IMGURL_ALTERNATIVE>{esc(alt)}</IMGURL_ALTERNATIVE>")
        rows.append(f"    <DELIVERY_DATE>{livrare}</DELIVERY_DATE>")
        greutate = v.get("Variant Weight")
        if CURIER_LIVRARE and pd.notna(greutate) and greutate > 0:
            rows.append("    <DELIVERY>")
            rows.append(f"      <DELIVERY_ID>{esc(CURIER_LIVRARE)}</DELIVERY_ID>")
            rows.append(f"      <DELIVERY_PRICE>{format_pret(pret_livrare_pentru(float(greutate)))}</DELIVERY_PRICE>")
            rows.append("    </DELIVERY>")
        else:
            raport.append(["fara_pret_livrare", v["ID"], p["titlu"],
                           "varianta nu are greutate în Shopify — nu pot calcula prețul de livrare"])
        producator = None
        if MANUFACTURER_MODE == "branduri_reale" and p["vendor"] in PRODUCATORI_REALI:
            producator = p["vendor"].title()
        elif MANUFACTURER_MODE == "ocean":
            producator = p["vendor"].title() if p["vendor"] in PRODUCATORI_REALI else "Ocean"
        if producator:
            rows.append(f"    <MANUFACTURER>{esc(producator)}</MANUFACTURER>")
        ean = ean_valid(v.get("Variant Barcode"))
        if ean:
            rows.append(f"    <EAN>{ean}</EAN>")
        for cheie, val in parametri:
            rows.append("    <PARAM>")
            rows.append(f"      <PARAM_NAME>{esc(cheie)}</PARAM_NAME>")
            rows.append(f"      <VAL>{esc(val)}</VAL>")
            rows.append("    </PARAM>")
        itemuri.append("  <SHOPITEM>\n" + "\n".join(rows) + "\n  </SHOPITEM>")

    xml = '<?xml version="1.0" encoding="utf-8"?>\n<SHOP>\n' + "\n".join(itemuri) + "\n</SHOP>\n"
    with open(OUTPUT_XML, "w", encoding="utf-8") as f:
        f.write(xml)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["motiv", "product_id", "titlu", "detalii"])
        w.writerows(raport)

    # --- validare + statistici ---
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    nr = len(root.findall("SHOPITEM"))
    nr_param = [len(i.findall("PARAM")) for i in root.findall("SHOPITEM")]
    print(f"Feed valid XML. {nr} produse scrise în {OUTPUT_XML}.")
    print(f"Excluse (stoc<=0): {excluse_stoc}. Probleme raportate: {len(raport)} rânduri în {OUTPUT_CSV}.")
    if not nr_param:
        print("ATENȚIE: feedul e GOL — nu-l publica; vezi raportul pentru cauze.")
        return
    print(f"Parametri per produs: min {min(nr_param)}, media {sum(nr_param)/len(nr_param):.1f}, max {max(nr_param)}.")
    print(f"Produse cu <=3 parametri (tabelul nu se afișează pe Favi): {sum(1 for n in nr_param if n <= 3)}")

if __name__ == "__main__":
    main()
