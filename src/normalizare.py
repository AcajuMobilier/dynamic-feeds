"""Stratul de normalizare: descriere, parametri, dimensiuni, titluri.

Toată logica de aici e portată din generatorul validat `genereaza_feed_favi.py`
(care mergea pe exporturi Excel). Semantica e neschimbată; s-au eliminat doar
dependențele de pandas și de sursele de URL din sitemap/arhivă.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

RE_NA = re.compile(r"^\s*(N/?A\.?(\s*(kg|cm|mm|m|l))?|-|–|\?|nespecificat)\s*$", re.I)
RE_NUM = re.compile(r"^[\d.,]+(\s*[-–±]\s*[\d.,]+)?$")
RE_URL = re.compile(r"https?://\S+|www\.\S+")
RE_EMAIL = re.compile(r"\S+@\S+\.\S+")

# „Pentru saltea cu dimensiunea: 160x200 cm" / „Dimensiuni: 80x150 cm"
RE_2DIM = re.compile(r"^(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*cm$", re.I)

RE_TITLU_3DIM = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?", re.I)
RE_TITLU_2DIM = re.compile(
    r"(?<![\d.,x×])(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*cm", re.I)

CHEI_DIMENSIUNE = {"Lățime", "Lungime", "Adâncime", "Înălțime",
                   "Lățime saltea", "Dimensiuni", "Diametru"}

# Caractere pe care XML 1.0 nu le acceptă deloc. Dacă ajung în feed din
# descrierile Shopify, fișierul devine neparsabil și Favi îl respinge întreg.
# Sunt codurile 0-8, 11, 12, 14-31 și 127; tab (9), LF (10) și CR (13) rămân.
CODURI_ILEGALE_XML = frozenset(
    list(range(0, 9)) + [11, 12] + list(range(14, 32)) + [127])


def curata_control(s) -> str:
    """Scoate caracterele interzise în XML 1.0, păstrând tab, LF și CR."""
    return "".join(c for c in str(s) if ord(c) not in CODURI_ILEGALE_XML)


def curata_text(s) -> str:
    return re.sub(r"\s+", " ", curata_control(s)).strip()


def curata_titlu(t: str) -> str:
    """Favi nu acceptă cuvinte promoționale în titlu."""
    t = curata_text(t)
    t = re.sub(r"\bpromo\b\s*", "", t, flags=re.I)
    return curata_text(t)


def sufix_varianta(sku: str, titlu_varianta: str = "") -> str:
    """Sufixul care distinge variantele aceluiași produs.

    Se uită întâi după marcajele de stânga/dreapta din SKU. Dacă SKU-ul
    lipsește, cade pe titlul variantei din Shopify, ca titlul să nu se
    termine cu o paranteză goală.
    """
    s = str(sku or "").upper()
    if re.search(r"(^|[^A-Z])(STG|ST)([^A-Z]|$)|DL", s):
        return " (varianta stânga)"
    if re.search(r"(^|[^A-Z])DR([^A-Z]|$)|DP", s):
        return " (varianta dreapta)"
    if sku:
        return f" ({sku})"
    titlu_varianta = curata_text(titlu_varianta or "")
    if titlu_varianta and titlu_varianta.lower() not in ("default title", "default"):
        return f" ({titlu_varianta})"
    return ""


def ean_valid(v):
    """GTIN de 8/12/13/14 cifre, cu cifra de control GS1 corectă. Altfel None.

    Codul se citește ca text, ca să nu se piardă zerourile din față
    (036000291452 e un UPC-A valid, dar ca număr ar deveni 36000291452).
    """
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith(".0"):          # vine uneori ca număr dintr-un export
        s = s[:-2]
    if not s.isdigit():
        return None
    if len(s) not in (8, 12, 13, 14):
        return None
    cifre = [int(c) for c in s]
    suma = sum(d * (3 if (len(cifre) - i) % 2 == 0 else 1) for i, d in enumerate(cifre[:-1]))
    return s if (10 - suma % 10) % 10 == cifre[-1] else None


def url_sigur(u) -> str:
    """Adresă utilizabilă de Favi: fără spații și fără diacritice.

    Favi respinge URL-urile cu spații sau cu caractere non-ASCII. Shopify
    poate produce așa ceva în numele fișierelor de imagine, deci le codificăm
    procentual (spațiu devine %20, „ă" devine %C4%83). Restul adresei,
    inclusiv separatorii, rămâne neatins.
    """
    from urllib.parse import quote
    u = curata_control(u).strip()
    return quote(u, safe="%:/?#[]@!$&'()*+,;=~._-")


def format_pret(p) -> str:
    p = float(p)
    return str(int(p)) if p == int(p) else f"{p:.2f}"


# ---------------------------------------------------------------- parametri
def extrage_parametri(soup, cfg) -> list[tuple[str, str]]:
    """Perechile cheie/valoare din tabelele HTML de la începutul descrierii."""
    parametri, vazute = [], set()
    for tabel in soup.find_all("table"):
        for tr in tabel.find_all("tr"):
            celule = tr.find_all(["td", "th"])
            if len(celule) < 2:
                continue
            cheie = curata_text(celule[0].get_text(" ", strip=True)).rstrip(":").strip()
            val = curata_text(celule[1].get_text(" ", strip=True))
            if not cheie or cheie in cfg.param_skip:
                continue
            cheie = cfg.param_rename.get(cheie, cheie)
            if cheie in vazute:            # fără parametri duplicați (regula Favi)
                continue
            if not val or RE_NA.match(val):  # aruncăm N/A, „-", gol
                continue
            if RE_NUM.match(val):            # unitatea de măsură la valorile numerice
                if cheie in cfg.chei_cm:
                    val += " cm"
                elif cheie in cfg.chei_kg:
                    val += " kg"
            parametri.append((cheie, val))
            vazute.add(cheie)
    return parametri


# ---------------------------------------------------------------- structura descrierii
# Favi acceptă tagurile inline, dar rendererul lor le afișează ca text când
# stau direct la rădăcina descrierii, în afara unui bloc. Cazul tipic vine din
# Shopify: <div><strong>TITLU</strong></div>, iar <div> nu e permis și se
# desface, lăsând <strong> singur la rădăcină.
TAGURI_INLINE = ["strong", "b", "em", "i"]
TAGURI_BLOC = {"p", "ul", "ol"}


def _e_gol(text) -> bool:
    """Doar spații, &nbsp; sau caractere invizibile de lățime zero."""
    return not str(text).replace("​", "").replace("﻿", "").strip()


def _e_br(nod) -> bool:
    return isinstance(nod, Tag) and nod.name == "br"


def _e_spatiu(nod) -> bool:
    return isinstance(nod, NavigableString) and _e_gol(nod)


def _sterge_inline_goale(soup) -> None:
    """<strong>, <b>, <em>, <i> goale sau doar cu spații dispar.

    Tagul se desface, nu se șterge cu tot cu conținut: un spațiu dintre două
    cuvinte sau un <br> dinăuntru rămân pe loc. Se repetă până nu mai rămâne
    niciunul, ca să prindă și cazurile imbricate (<b><strong> </strong></b>).
    """
    while True:
        goale = [t for t in soup.find_all(TAGURI_INLINE) if _e_gol(t.get_text())]
        if not goale:
            return
        for tag in reversed(goale):         # copiii înaintea părinților
            if tag.parent is not None:
                tag.unwrap()


def _tunde_margini(bloc) -> None:
    """Scoate <br>-urile și spațiile de la începutul și sfârșitul unui bloc."""
    while bloc.contents and (_e_br(bloc.contents[0]) or _e_spatiu(bloc.contents[0])):
        bloc.contents[0].extract()
    while bloc.contents and (_e_br(bloc.contents[-1]) or _e_spatiu(bloc.contents[-1])):
        bloc.contents[-1].extract()


def _normalizeaza_radacina(soup) -> None:
    """La rădăcina descrierii rămân doar blocuri <p>, <ul>, <ol>.

    Textul și elementele inline aflate direct la rădăcină (strong, b, em, i,
    <br>-uri) se strâng în paragrafe. <br>-urile și spațiile rămase singure
    între blocuri dispar, la fel cele de la marginea descrierii. Un <li>
    rătăcit la rădăcină primește o listă <ul> în jurul lui.
    """
    noduri = [n.extract() for n in list(soup.contents)]
    blocuri, grup = [], []
    lista = None

    def inchide_grup():
        if grup and not all(_e_br(n) or _e_spatiu(n) for n in grup):
            p = soup.new_tag("p")
            for n in grup:
                p.append(n)
            _tunde_margini(p)
            blocuri.append(p)
        grup.clear()

    for nod in noduri:
        if isinstance(nod, Tag) and nod.name == "li":
            inchide_grup()
            if lista is None:
                lista = soup.new_tag("ul")
                blocuri.append(lista)
            lista.append(nod)
        elif isinstance(nod, Tag) and nod.name in TAGURI_BLOC:
            inchide_grup()
            lista = None
            # un <p> gol desparte conținutul din jur, dar nu apare în rezultat
            if not (nod.name == "p" and _e_gol(nod.get_text())):
                blocuri.append(nod)
        elif not grup and (_e_br(nod) or _e_spatiu(nod)):
            continue                        # nimic de păstrat între blocuri
        else:
            lista = None
            grup.append(nod)
    inchide_grup()

    # <br>-urile de la începutul și finalul întregii descrieri
    if blocuri and blocuri[0].name == "p":
        _tunde_margini(blocuri[0])
    if blocuri and blocuri[-1].name == "p":
        _tunde_margini(blocuri[-1])

    for i, bloc in enumerate(blocuri):
        if i:
            soup.append(NavigableString("\n"))
        soup.append(bloc)


def _sterge_paragrafe_goale(soup) -> None:
    """<p>-urile rămase fără text dispar, inclusiv cele care au doar <br>."""
    for p in soup.find_all("p"):
        if p.parent is not None and _e_gol(p.get_text()):
            p.decompose()


def construieste_descriere(body_html: str, cfg) -> tuple[str, list[tuple[str, str]]]:
    """Scoate tabelele de specificații și lasă doar HTML-ul permis de Favi."""
    soup = BeautifulSoup(body_html or "", "html.parser")
    parametri = extrage_parametri(soup, cfg)
    for tabel in soup.find_all("table"):
        tabel.decompose()
    # <style> și <script> se scot cu tot cu conținut. Desfăcute ca celelalte
    # taguri nepermise, ar lăsa CSS-ul sau codul ca text vizibil pe Favi
    # (apare în descrieri lipite din Excel: <style><!-- td {border...} --></style>).
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
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
        if tag.name not in cfg.taguri_permise:
            tag.unwrap()
        else:
            # Favi acceptă tagurile goale, fără atribute. Un style sau un
            # title ar trece de filtrul de text și ar putea ascunde un URL.
            tag.attrs = {}
    # fără linkuri / emailuri în text (interzise de Favi)
    for nod in soup.find_all(string=True):
        txt = RE_URL.sub("", str(nod))
        txt = RE_EMAIL.sub("", txt)
        if txt != str(nod):
            nod.replace_with(txt)
    # structură pe blocuri: rendererul Favi afișează tagurile ca text când
    # găsește conținut inline direct la rădăcina descrierii
    _sterge_inline_goale(soup)
    _normalizeaza_radacina(soup)
    _sterge_paragrafe_goale(soup)
    htm = str(soup)
    htm = re.sub(r"<p>(\s|&nbsp;|<br\s*/?>)*</p>", "", htm)   # paragrafe goale
    htm = re.sub(r"<ul>\s*</ul>|<ol>\s*</ol>", "", htm)       # liste goale
    htm = re.sub(r"\n{3,}", "\n\n", htm).strip()
    return curata_control(htm), parametri


# ---------------------------------------------------------------- dimensiuni
def completeaza_dimensiuni_din_titlu(parametri, titlu, categorie):
    """Multe titluri conțin dimensiunile („..., 45x51x90 cm"). Când tabelul nu
    le are, le luăm de acolo, în aceeași convenție L×A×Î ca tabelul."""
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
    # a doua pereche „AxB cm" din titlu: la paturi e dimensiunea saltelei,
    # la covoare/textile e dimensiunea produsului
    if categorie:
        text_2dim = RE_TITLU_3DIM.sub(" ", titlu)   # scoatem tripletul, să nu-l reciclăm
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


def ajusteaza_pentru_favi(parametri, categorie, cfg):
    """Redenumește dimensiunile pe numele exacte pe care filtrează Favi în
    fiecare categorie și sparge dimensiunile împachetate în parametri separați."""
    redenumiri = cfg.dim_familia.get(categorie or "", {})
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
    if cfg.deriva_culoare and "Culoare" not in chei:
        sezut = next((v for k, v in rezultat if k == "Culoare șezut"), None)
        if sezut:
            extra.append(("Culoare", sezut))
    return rezultat + extra


# ---------------------------------------------------------------- categorii
def categoria_pentru(tip, titlu, cfg):
    """Corecțiile după titlu au prioritate față de Type-ul din Shopify."""
    for rx, cat in cfg.categorii_dupa_titlu:
        if rx.search(titlu or ""):
            return cat
    if not tip:
        return None
    return cfg.categorii_lc.get(str(tip).strip().lower())
