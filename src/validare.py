"""Validarea feedului rezultat, înainte de publicare.

Aceleași verificări pe care le făcea generatorul de referință, plus cele cerute
explicit de Favi. O eroare oprește publicarea; o avertizare doar se raportează.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter

RE_URL = re.compile(r"https?://\S+|www\.\S+")
RE_EMAIL = re.compile(r"[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}")
RE_TAG = re.compile(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)")
# Favi acceptă la ITEM_ID doar cifre, litere ASCII, cratimă și underscore.
RE_ITEM_ID = re.compile(r"^[0-9A-Za-z_-]+$")
RE_PRET = re.compile(r"^\d+(\.\d{1,2})?$")


class Rezultat:
    def __init__(self):
        self.erori: list[str] = []
        self.avertizari: list[str] = []
        self.numar_produse = 0
        self.statistici: dict = {}

    @property
    def valid(self) -> bool:
        return not self.erori


def valideaza(xml_text: str, cfg) -> Rezultat:
    r = Rezultat()

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        r.erori.append(f"XML invalid: {e}")
        return r

    itemuri = root.findall("SHOPITEM")
    r.numar_produse = len(itemuri)
    if not itemuri:
        r.erori.append("Feedul e gol: niciun SHOPITEM.")
        return r

    ids, urluri = [], []
    nr_parametri = []
    fara_obligatorii = Counter()
    descrieri_cu_url = descrieri_cu_email = taguri_interzise = 0
    preturi_gresite = imagini_prea_multe = param_duplicat = 0
    id_format_gresit = 0

    obligatorii = ["ITEM_ID", "PRODUCTNAME", "DESCRIPTION", "CATEGORYTEXT",
                   "PRICE_VAT", "URL", "IMGURL", "DELIVERY_DATE"]

    for item in itemuri:
        for camp in obligatorii:
            nod = item.find(camp)
            if nod is None or (nod.text or "").strip() == "":
                fara_obligatorii[camp] += 1

        nod_id = item.find("ITEM_ID")
        if nod_id is not None and nod_id.text:
            ids.append(nod_id.text.strip())
            if not RE_ITEM_ID.match(nod_id.text.strip()):
                id_format_gresit += 1

        nod_url = item.find("URL")
        if nod_url is not None and nod_url.text:
            urluri.append(nod_url.text.strip())

        nod_pret = item.find("PRICE_VAT")
        if nod_pret is not None and nod_pret.text and not RE_PRET.match(nod_pret.text.strip()):
            preturi_gresite += 1

        descriere = (item.findtext("DESCRIPTION") or "")
        if RE_URL.search(descriere):
            descrieri_cu_url += 1
        if RE_EMAIL.search(descriere):
            descrieri_cu_email += 1
        for tag in RE_TAG.findall(descriere):
            if tag.lower() not in cfg.taguri_permise:
                taguri_interzise += 1
                break

        if len(item.findall("IMGURL_ALTERNATIVE")) > cfg.max_alternative:
            imagini_prea_multe += 1

        nume_param = [n.text for n in item.findall("PARAM/PARAM_NAME")]
        nr_parametri.append(len(nume_param))
        if len(nume_param) != len(set(nume_param)):
            param_duplicat += 1

    # --- erori care opresc publicarea ---
    for camp, n in fara_obligatorii.items():
        r.erori.append(f"{n} produse fără {camp} (element obligatoriu la Favi).")

    dubluri_id = [i for i, n in Counter(ids).items() if n > 1]
    if dubluri_id:
        r.erori.append(f"{len(dubluri_id)} ITEM_ID duplicate (ex. {dubluri_id[:3]}).")

    dubluri_url = [u for u, n in Counter(urluri).items() if n > 1]
    if dubluri_url:
        r.erori.append(f"{len(dubluri_url)} URL-uri duplicate (Favi ar contopi produsele).")

    if id_format_gresit:
        r.erori.append(f"{id_format_gresit} ITEM_ID cu caractere neacceptate de Favi.")
    if preturi_gresite:
        r.erori.append(f"{preturi_gresite} prețuri în format greșit.")
    if descrieri_cu_url:
        r.erori.append(f"{descrieri_cu_url} descrieri conțin un URL (interzis de Favi).")
    if descrieri_cu_email:
        r.erori.append(f"{descrieri_cu_email} descrieri conțin o adresă de email (interzis de Favi).")
    if taguri_interzise:
        r.erori.append(f"{taguri_interzise} descrieri conțin taguri HTML nepermise de Favi.")
    if param_duplicat:
        r.erori.append(f"{param_duplicat} produse au parametri duplicați.")
    if imagini_prea_multe:
        r.erori.append(f"{imagini_prea_multe} produse au peste {cfg.max_alternative} imagini alternative.")

    # --- avertizări ---
    sub_patru = sum(1 for n in nr_parametri if n <= 3)
    if sub_patru:
        r.avertizari.append(
            f"{sub_patru} produse au cel mult 3 parametri — Favi nu le afișează tabelul.")

    r.statistici = {
        "produse": r.numar_produse,
        "parametri_min": min(nr_parametri) if nr_parametri else 0,
        "parametri_medie": round(sum(nr_parametri) / len(nr_parametri), 1) if nr_parametri else 0,
        "parametri_max": max(nr_parametri) if nr_parametri else 0,
        "produse_sub_4_parametri": sub_patru,
        "categorii_distincte": len({item.findtext("CATEGORYTEXT") for item in itemuri}),
        "cu_ean": sum(1 for item in itemuri if item.find("EAN") is not None),
        "cu_delivery": sum(1 for item in itemuri if item.find("DELIVERY") is not None),
        "cu_itemgroup": sum(1 for item in itemuri if item.find("ITEMGROUP_ID") is not None),
    }
    return r


# ---------------------------------------------------------------- frâna
# Ce a găsit citirea feedului live:
#   ("numar", n)    – feedul există și are n produse
#   ("lipseste", 0) – feedul nu există încă (prima rulare); frâna se sare
#   ("eroare", 0)   – nu am putut verifica; frâna NU se sare
def _cerere(url: str):
    import urllib.request
    return urllib.request.Request(url, headers={
        "User-Agent": "dynamic-feeds/1.0 (verificare frana de siguranta)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })


def _numara_implicit(text: str) -> int:
    return text.count("<SHOPITEM>")


def descarca_feed_live(url: str, timeout: int = 120, incercari: int = 3, numara=None):
    """Textul feedului publicat, sau None dacă nu poate fi luat întreg.

    Folosit ca să păstrăm versiunea live a unui feed care a picat la
    regenerare, ca adresa lui să nu rămână goală pe Pages.
    """
    stare, _, _, text = _citeste(url, timeout, incercari, numara or _numara_implicit)
    return text if stare == "numar" else None


def exista_feed_live(url: str, timeout: int = 60) -> bool:
    """True dacă la adresă răspunde ceva (orice cod în afară de 404)."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(_cerere(url), timeout=timeout) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code != 404
    except Exception:
        return True      # nu știm; presupunem că există, ca să nu publicăm un folder incomplet


def _citeste(url, timeout, incercari, numara):
    import time
    import urllib.error
    import urllib.request
    ultima = ""
    for i in range(incercari):
        try:
            with urllib.request.urlopen(_cerere(url), timeout=timeout) as r:
                date = r.read().decode("utf-8", errors="replace")
            n = numara(date)
            if n <= 0 and "<" not in date[:200] and "," not in date[:200]:
                ultima = "răspunsul nu pare a fi un feed"
            elif not _pare_intreg(date):
                ultima = "feedul live pare trunchiat"
            else:
                return "numar", n, "", date
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "lipseste", 0, "feedul nu există încă la această adresă", None
            ultima = f"HTTP {e.code}"
        except Exception as e:                      # rețea, DNS, TLS, timeout
            ultima = str(e)
        if i < incercari - 1:
            time.sleep(3 * (i + 1))
    return "eroare", 0, ultima, None


def _pare_intreg(text: str) -> bool:
    """Un XML se termină cu eticheta rădăcinii închise; un CSV cu linie nouă."""
    coada = text.rstrip()[-40:]
    if text.lstrip().startswith("<"):
        return coada.endswith("</SHOP>") or coada.endswith("</rss>") or coada.endswith("</feed>")
    return True


def citeste_feed_live(url: str, timeout: int = 120, incercari: int = 3, numara=None):
    """Citește feedul publicat și numără produsele; întoarce (stare, număr, detaliu).

    Distincția dintre „nu există încă" și „nu am putut verifica" e esențială:
    dacă tratăm o eroare de rețea ca pe o primă rulare, frâna se dezactivează
    exact în situațiile în care ar trebui să apere feedul.
    """
    stare, n, detaliu, _ = _citeste(url, timeout, incercari, numara or _numara_implicit)
    return stare, n, detaliu


def verifica_frana(numar_nou: int, live, prag_procent: float):
    """Întoarce (poate_publica, mesaj).

    `live` e fie un număr, fie None (fără feed live), fie tuplul întors de
    citeste_feed_live.
    """
    if live is None:
        stare, numar_live, detaliu = "lipseste", 0, ""
    elif isinstance(live, tuple):
        stare, numar_live, detaliu = live
    else:
        stare, numar_live, detaliu = "numar", int(live), ""

    if stare == "eroare":
        return False, (f"OPRIT: nu am putut citi feedul aflat live, deci nu pot verifica "
                       f"dacă numărul de produse a scăzut ({detaliu}). "
                       f"Feedul vechi rămâne publicat.")
    if stare == "lipseste":
        return True, "Nu există feed live (prima rulare) — frâna de siguranță se sare."
    if numar_live == 0:
        return True, "Feedul live e gol — frâna de siguranță se sare."

    procent = 100.0 * numar_nou / numar_live
    if procent < prag_procent:
        return False, (f"OPRIT: feedul nou are {numar_nou} produse, adică {procent:.1f}% "
                       f"din cele {numar_live} aflate live. Pragul minim e {prag_procent:.0f}%. "
                       f"Feedul vechi rămâne publicat.")
    return True, (f"Frâna de siguranță: {numar_nou} produse noi față de {numar_live} live "
                  f"({procent:.1f}%), peste pragul de {prag_procent:.0f}%.")


# ---------------------------------------------------------------- RSS (Google, Facebook, RTB)
NS_G = "{http://base.google.com/ns/1.0}"
RE_PRET_RON = re.compile(r"^\d+(\.\d+)? RON$")


def valideaza_rss(text: str, cfg, camp_id: str, camp_link: str) -> Rezultat:
    """Verificările minime înainte de publicare pentru un feed RSS replicat:
    XML bine format, ID-uri și adrese unice, prețuri „N RON", câmpuri
    obligatorii prezente."""
    r = Rezultat()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        r.erori.append(f"XML invalid: {e}")
        return r
    itemuri = root.findall("./channel/item")
    r.numar_produse = len(itemuri)
    if not itemuri:
        r.erori.append("Feedul e gol: niciun item.")
        return r

    def cauta(item, nume):
        if nume.startswith("g:"):
            return item.findtext(NS_G + nume[2:])
        return item.findtext(nume)

    ids, linkuri = [], []
    preturi_gresite = fara_id = fara_link = fara_titlu = fara_imagine = 0
    for item in itemuri:
        i = (cauta(item, camp_id) or "").strip()
        if not i:
            fara_id += 1
        ids.append(i)
        adresa = (cauta(item, camp_link) or "").strip()
        if not adresa.startswith("https://"):
            fara_link += 1
        linkuri.append(adresa)
        if not (cauta(item, "title") or cauta(item, "product_name") or "").strip():
            fara_titlu += 1
        if not (cauta(item, "g:image_link") or cauta(item, "image_link") or "").strip():
            fara_imagine += 1
        for camp in ("g:price", "g:sale_price", "price", "sale_price"):
            val = cauta(item, camp)
            if val is not None and not RE_PRET_RON.match(val.strip()):
                preturi_gresite += 1
    dubluri = [i for i, n in Counter(ids).items() if n > 1 and i]
    if dubluri:
        r.erori.append(f"{len(dubluri)} ID-uri duplicate (ex. {dubluri[:3]}).")
    dubluri_l = [u for u, n in Counter(linkuri).items() if n > 1 and u]
    if dubluri_l:
        r.erori.append(f"{len(dubluri_l)} adrese duplicate.")
    if fara_id:
        r.erori.append(f"{fara_id} produse fără ID.")
    if fara_link:
        r.erori.append(f"{fara_link} produse fără adresă https.")
    if fara_titlu:
        r.erori.append(f"{fara_titlu} produse fără titlu.")
    if preturi_gresite:
        r.erori.append(f"{preturi_gresite} prețuri care nu sunt în formatul „N RON”.")
    if fara_imagine:
        r.avertizari.append(f"{fara_imagine} produse fără imagine (intră în feed cu image_link gol, ca la Mulwi).")
    r.statistici = {"produse": r.numar_produse}
    return r


def valideaza_csv(text: str, cfg) -> Rezultat:
    import csv
    import io
    r = Rezultat()
    linii = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not linii or linii[0] != ["Page URL", "Custom label"]:
        r.erori.append("Antetul CSV nu e „Page URL,Custom label”.")
        return r
    randuri = linii[1:]
    r.numar_produse = len(randuri)
    if not randuri:
        r.erori.append("Feedul e gol.")
        return r
    if any(len(rd) != 2 for rd in randuri):
        r.erori.append("Există rânduri care nu au exact două coloane.")
    urluri = [rd[0] for rd in randuri if rd]
    if any(not u.startswith("https://") for u in urluri):
        r.erori.append("Există adrese care nu încep cu https://.")
    dubluri = [u for u, n in Counter(urluri).items() if n > 1]
    if dubluri:
        r.erori.append(f"{len(dubluri)} adrese duplicate.")
    r.statistici = {"produse": r.numar_produse}
    return r
