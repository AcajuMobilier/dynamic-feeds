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
def citeste_feed_live(url: str, timeout: int = 120, incercari: int = 3):
    """Citește feedul publicat și numără produsele.

    Distincția dintre „nu există încă" și „nu am putut verifica" e esențială:
    dacă tratăm o eroare de rețea ca pe o primă rulare, frâna se dezactivează
    exact în situațiile în care ar trebui să apere feedul.
    """
    import time
    import urllib.error
    import urllib.request

    cerere = urllib.request.Request(url, headers={
        "User-Agent": "feed-favi/1.0 (verificare frana de siguranta)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    ultima = ""
    for i in range(incercari):
        try:
            with urllib.request.urlopen(cerere, timeout=timeout) as r:
                date = r.read().decode("utf-8", errors="replace")
            if "<SHOP" not in date:
                # Pages poate răspunde cu o pagină de eroare HTML, cu cod 200.
                ultima = "răspunsul nu e un feed XML"
            elif "</SHOP>" not in date:
                ultima = "feedul live pare trunchiat (nu are eticheta de final)"
            else:
                return "numar", date.count("<SHOPITEM>"), ""
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "lipseste", 0, "feedul nu există încă la această adresă"
            ultima = f"HTTP {e.code}"
        except Exception as e:                      # rețea, DNS, TLS, timeout
            ultima = str(e)
        if i < incercari - 1:
            time.sleep(3 * (i + 1))
    return "eroare", 0, ultima


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
