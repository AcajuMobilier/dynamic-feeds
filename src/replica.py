"""Ajutoare comune pentru feedurile care REPLICĂ feedurile Mulwi.

Aceste feeduri (Google Shopping, Facebook, RTB House, DSA) sunt consumate de
campanii configurate de colaboratori externi, deci trebuie să iasă IDENTIC cu
ce produce Mulwi azi: aceleași ID-uri, aceleași valori, același format. Toate
regulile de aici au fost deduse prin compararea feedurilor Mulwi cu datele din
Shopify (2026-09-23) și verificate independent, câmp cu câmp; scripturile de
verificare și raportul sunt în docs/.

Nu se „repară" nimic aici: dacă Mulwi scrie greutatea ca 147.20000000000002 kg,
la fel scriem și noi, pentru că asta primește Merchant Center acum.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .normalizare import curata_control

RE_TAG = re.compile(r"<[^>]*>")
RE_COMENTARIU = re.compile(r"<!--.*?-->", re.S)


def cdata(s) -> str:
    s = curata_control("" if s is None else str(s))
    return "<![CDATA[" + s.replace("]]>", "]] >") + "]]>"


def varianta_principala(p: dict, regula: str = "id_minim") -> dict | None:
    """Varianta care dă prețul, SKU-ul, stocul și greutatea unui item per produs.

    Mulwi folosește varianta cu ID-ul cel mai mic (cea mai veche), dovedit pe
    singurul produs unde diferă de poziția 1 (un card cadou cu 8 variante).
    Pentru celelalte produse cele două reguli coincid.
    """
    variante = [v for v in (p.get("variante") or []) if v.get("id")]
    if not variante:
        return None
    if regula == "pozitie":
        return min(variante, key=lambda v: (v.get("pozitie") or 0, int(v["id"])))
    return min(variante, key=lambda v: int(v["id"]))


def pret_ron(valoare) -> str:
    """„264 RON": număr întreg, fără zecimale, fără separator de mii.

    Toate prețurile din ambele magazine sunt întregi, deci rotunjirea unui
    preț cu zecimale nu a putut fi observată la Mulwi; scriem zecimalele
    doar dacă există (264.5 RON).
    """
    d = Decimal(str(valoare))
    if d == d.to_integral_value():
        return f"{int(d)} RON"
    return f"{d.normalize()} RON"


def pret_si_pret_redus(v: dict) -> tuple[str, str, bool]:
    """(g:price, g:sale_price, are_compare_at).

    Cu preț „compare at" în Shopify: g:price = compare at, g:sale_price = prețul
    curent. Fără: ambele = prețul curent. Ambele se trimit mereu.
    """
    are = v.get("pret_comparat") not in (None, "")
    baza = v["pret_comparat"] if are else v["pret"]
    return pret_ron(baza), pret_ron(v["pret"]), are


def greutate_kg_text(kg) -> str:
    """Greutatea așa cum o scrie Mulwi: din grame, înmulțit cu 0.001 în virgulă
    mobilă, cu reprezentarea cea mai scurtă; 147.2 kg iese „147.20000000000002 kg".
    Reproducem artefactul pentru că exact asta primește Merchant Center azi."""
    if kg is None:
        kg = 0.0
    grame = round(float(kg) * 1000)
    x = grame * 0.001
    return (f"{int(x)} kg") if x == int(x) else (f"{x!r} kg")


def titlu_70(titlu: str) -> str:
    """Primele 70 de caractere, tăiere dură, fără curățare (spațiul final rămâne)."""
    return curata_control(titlu or "")[:70]


def url_produs(p: dict, prefix: str) -> str:
    """Adresa produsului construită din handle, ca la Mulwi: se emite și pentru
    produsele nepublicate pe Online Store, iar handle-ul cu diacritice rămâne
    neencodat (Shopify l-ar da percent-encodat în onlineStoreUrl)."""
    return prefix + (p.get("handle") or "")


def descriere_plata(html: str, limita: int = 500) -> str:
    """Textul tabelului de parametri și al descrierii, aplatizat ca la Mulwi.

    Algoritmul, verificat caracter cu caracter pe toate produsele:
      1. doar „<br>" exact devine separator de linie („<br data-...>" nu);
      2. se șterg comentariile HTML și apoi orice tag, fără a lăsa spațiu;
      3. textul se împarte pe liniile din HTML-ul sursă; fiecare linie se
         curăță la margini (inclusiv NBSP; str.strip face exact asta);
      4. liniile goale dispar (dar „0" rămâne), restul se unesc cu „. ";
      5. se taie la 500 de caractere. Entitățile HTML nu se decodează.
    """
    t = curata_control(html or "")
    t = t.replace("<br>", "\n")
    t = RE_COMENTARIU.sub("", t)
    t = RE_TAG.sub("", t)
    linii = [l.strip() for l in t.split("\n")]
    linii = [l for l in linii if l != ""]
    return ". ".join(linii)[:limita]


def in_stoc(v: dict) -> bool:
    """Regula Mulwi pentru disponibilitate și eticheta de livrare: stocul
    variantei principale mai mare ca zero."""
    try:
        return int(v.get("stoc") or 0) > 0
    except (TypeError, ValueError):
        return False


def sortate_dupa_id(produse: list[dict]) -> list[dict]:
    """Mulwi scrie produsele în ordinea crescătoare a ID-ului."""
    return sorted(produse, key=lambda p: int(p["id"]))


def crlf(text: str) -> str:
    """Toate feedurile Mulwi au terminații de linie CRLF."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def e_gol(valoare: str) -> bool:
    """O etichetă goală sau formată doar din spații și linii noi."""
    return not (valoare or "").strip()
