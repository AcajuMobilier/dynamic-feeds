"""Stratul de formatare pentru canalul Favi (specificația Heureka).

Primește produsele normalizate și scrie XML-ul. Toate regulile specifice Favi
stau aici: ordinea elementelor, CDATA la descriere, escape la rest, limita de
imagini alternative, DELIVERY_DATE, elementul DELIVERY.
"""

from __future__ import annotations

import html

from .normalizare import (
    CHEI_DIMENSIUNE,
    ajusteaza_pentru_favi,
    categoria_pentru,
    completeaza_dimensiuni_din_titlu,
    construieste_descriere,
    curata_titlu,
    ean_valid,
    format_pret,
    sufix_varianta,
    url_sigur,
)


def esc(s) -> str:
    """Escape XML pentru câmpurile din afara CDATA."""
    from .normalizare import curata_text
    return html.escape(curata_text(s), quote=False)


def cdata(s: str) -> str:
    return "<![CDATA[" + (s or "").replace("]]>", "]] >") + "]]>"


def _producator(vendor: str, cfg):
    vendor = (vendor or "").strip()
    if cfg.manufacturer_mod == "branduri_reale" and vendor.upper() in cfg.branduri_reale:
        return vendor.title()
    if cfg.manufacturer_mod == "ocean":
        return vendor.title() if vendor.upper() in cfg.branduri_reale else "Ocean"
    return None


def pregateste_produse(produse: list[dict], cfg, raport) -> dict:
    """Agregare pe produs: titlu, descriere, parametri, imagini, categorie, URL.

    Produsele care nu pot intra în feed sunt raportate aici, cu motivul exact.
    """
    pregatite = {}
    for p in produse:
        pid = p["id"]
        titlu = curata_titlu(p["titlu"])

        descriere, parametri = construieste_descriere(p["descriere_html"], cfg)
        if not parametri:
            raport.adauga("fara_parametri", pid, titlu,
                          "descrierea nu conține tabel de specificații")

        imagini = p["imagini"]
        img_principala = imagini[0]["url"] if imagini else None
        img_alternative = [i["url"] for i in imagini[1:1 + cfg.max_alternative]]
        if imagini:
            lat, inalt = imagini[0].get("latime"), imagini[0].get("inaltime")
            if lat and inalt and (lat < cfg.latime_minima or inalt < cfg.inaltime_minima):
                raport.adauga("imagine_sub_600px", pid, titlu,
                              f"{int(lat)}x{int(inalt)} px — Favi poate bloca afișarea")
        else:
            raport.adauga("fara_imagine", pid, titlu, "produsul nu are nicio imagine în Shopify")

        categorie = categoria_pentru(p["tip"], titlu, cfg)
        if not categorie:
            raport.adauga("fara_categorie", pid, titlu, f"Type nemapat: {p['tip'] or '(gol)'}")

        url = p["url"]
        if not url:
            motiv = ("nepublicat pe Online Store" if p["status"] == "ACTIVE"
                     else f"nepublicat pe Online Store (status {p['status']})")
            raport.adauga("fara_url", pid, titlu, motiv)

        if p.get("variante_incomplete"):
            raport.adauga("variante_incomplete", pid, titlu,
                          "produsul are peste 250 de variante; doar primele 250 au intrat în feed")

        pregatite[pid] = dict(
            titlu=titlu, descriere=descriere, parametri=parametri,
            url=url, img=img_principala, img_alt=img_alternative,
            categorie=categorie, vendor=p["vendor"], stoc=p["stoc_total"],
            taguri=p["taguri"], status=p["status"], variante=p["variante"],
        )
    return pregatite


def _zile_livrare(p, cfg, raport, pid):
    """DELIVERY_DATE: tagurile Shopify au prioritate, apoi stocul."""
    taguri = {str(t).strip().lower() for t in (p["taguri"] or [])}
    for tag, zile in cfg.livrare_dupa_tag.items():
        if tag in taguri:
            return zile
    stoc = p["stoc"] or 0
    if stoc > 0:
        return cfg.zile_in_stoc
    if cfg.exclude_fara_stoc:
        return None
    raport.adauga("fara_stoc_in_feed", pid, p["titlu"],
                  f"trimis cu DELIVERY_DATE={cfg.zile_fara_stoc} zile — confirmă termenul real")
    return cfg.zile_fara_stoc


def _variante_valide(pid: str, p: dict, cfg, raport) -> list[dict]:
    """Variantele care pot deveni SHOPITEM. Restul sunt raportate aici.

    Se rulează înaintea construirii XML-ului, ca să știm dinainte câte
    variante rămân: de asta depinde dacă produsul primește ITEMGROUP_ID.
    """
    valide = []
    for v in p["variante"]:
        if not v["id"]:
            raport.adauga("exclus_date_lipsa", pid, p["titlu"], "varianta nu are ID")
            continue
        lipsuri = []
        if not p["categorie"]:
            lipsuri.append("categoria")
        if not p["img"]:
            lipsuri.append("imaginea")
        if not p["url"]:
            lipsuri.append("URL-ul")
        if not p["descriere"]:
            # DESCRIPTION e obligatoriu la Favi; un produs fără descriere ar
            # face feedul să pice la validare și ar bloca publicarea pentru tot.
            lipsuri.append("descrierea")
        if v["pret"] in (None, ""):
            lipsuri.append("prețul")
        else:
            try:
                if float(v["pret"]) <= 0:
                    lipsuri.append("un preț mai mare ca zero")
            except (TypeError, ValueError):
                lipsuri.append("un preț numeric")
        if lipsuri:
            raport.adauga("exclus_date_lipsa", v["id"], p["titlu"],
                          "lipsește " + ", ".join(lipsuri), tip_id="variantă")
            continue
        valide.append(v)
    return valide


def construieste_itemuri(pregatite: dict, cfg, raport) -> list[str]:
    """Un SHOPITEM per variantă (sau per produs, după politica de ID a
    feedului), în ordinea elementelor cerută de Favi."""
    itemuri = []
    for pid, p in pregatite.items():
        if not p["variante"]:
            raport.adauga("exclus_date_lipsa", pid, p["titlu"],
                          "produsul nu are nicio variantă în Shopify")
            continue

        variante = _variante_valide(pid, p, cfg, raport)
        if not variante:
            continue

        zile = _zile_livrare(p, cfg, raport, pid)
        if zile is None:
            raport.adauga("exclus_stoc_zero", pid, p["titlu"], f"stoc={p['stoc']}")
            continue

        if cfg.politica_id == "produs":
            # Un item per produs, cu ID-ul produsului. Prețul, stocul și
            # greutatea vin de la prima variantă după poziție, cum face și
            # feedul pe care îl înlocuim; fără ITEMGROUP_ID, fără ?variant=.
            variante = [min(variante, key=lambda x: (x.get("pozitie") or 0, x["id"]))]
            multi = False
        else:
            # ITEMGROUP_ID se pune doar când chiar rămân mai multe variante în feed.
            multi = len(variante) > 1

        for v in variante:
            id_item = pid if cfg.politica_id == "produs" else v["id"]
            titlu = p["titlu"] + (sufix_varianta(v["sku"], v.get("titlu")) if multi else "")
            url = str(p["url"]) + (f"?variant={v['id']}" if multi else "")

            parametri = completeaza_dimensiuni_din_titlu(list(p["parametri"]), p["titlu"], p["categorie"])
            parametri = ajusteaza_pentru_favi(parametri, p["categorie"], cfg)
            if not any(k in CHEI_DIMENSIUNE for k, _ in parametri):
                raport.adauga("fara_dimensiuni", id_item, p["titlu"],
                              "nicio dimensiune în tabel sau titlu — de completat în Shopify",
                              tip_id="variantă" if multi else "produs")
            greutate = v.get("greutate_kg")
            if not any(k == "Greutate" for k, _ in parametri) and greutate and greutate > 0:
                parametri.append(
                    ("Greutate", (str(int(greutate)) if greutate == int(greutate) else f"{greutate:g}") + " kg"))

            rows = [f"    <ITEM_ID>{esc(id_item)}</ITEM_ID>"]
            if multi:
                rows.append(f"    <ITEMGROUP_ID>{esc(pid)}</ITEMGROUP_ID>")
            rows.append(f"    <PRODUCTNAME>{esc(titlu)}</PRODUCTNAME>")
            rows.append(f"    <DESCRIPTION>{cdata(p['descriere'])}</DESCRIPTION>")
            rows.append(f"    <CATEGORYTEXT>{esc(p['categorie'])}</CATEGORYTEXT>")
            rows.append(f"    <PRICE_VAT>{format_pret(v['pret'])}</PRICE_VAT>")
            rows.append(f"    <URL>{esc(url_sigur(url))}</URL>")
            rows.append(f"    <IMGURL>{esc(url_sigur(p['img']))}</IMGURL>")
            for alt in p["img_alt"]:
                rows.append(f"    <IMGURL_ALTERNATIVE>{esc(url_sigur(alt))}</IMGURL_ALTERNATIVE>")
            rows.append(f"    <DELIVERY_DATE>{zile}</DELIVERY_DATE>")
            if cfg.curier and greutate and greutate > 0:
                rows.append("    <DELIVERY>")
                rows.append(f"      <DELIVERY_ID>{esc(cfg.curier)}</DELIVERY_ID>")
                rows.append(f"      <DELIVERY_PRICE>{format_pret(cfg.pret_livrare_pentru(float(greutate)))}</DELIVERY_PRICE>")
                rows.append("    </DELIVERY>")
            elif cfg.curier:
                raport.adauga("fara_pret_livrare", id_item, p["titlu"],
                              "varianta nu are greutate în Shopify — nu pot calcula prețul de livrare",
                              tip_id="variantă" if multi else "produs")
            producator = _producator(p["vendor"], cfg)
            if producator:
                rows.append(f"    <MANUFACTURER>{esc(producator)}</MANUFACTURER>")
            ean = ean_valid(v.get("barcode"))
            if ean:
                rows.append(f"    <EAN>{ean}</EAN>")
            for cheie, val in parametri:
                rows.append("    <PARAM>")
                rows.append(f"      <PARAM_NAME>{esc(cheie)}</PARAM_NAME>")
                rows.append(f"      <VAL>{esc(val)}</VAL>")
                rows.append("    </PARAM>")
            itemuri.append("  <SHOPITEM>\n" + "\n".join(rows) + "\n  </SHOPITEM>")
    return itemuri


def construieste_xml(itemuri: list[str]) -> str:
    return '<?xml version="1.0" encoding="utf-8"?>\n<SHOP>\n' + "\n".join(itemuri) + "\n</SHOP>\n"


def genereaza(produse: list[dict], cfg, raport) -> str:
    """Punctul de intrare comun al formatelor: produse selectate -> text feed."""
    pregatite = pregateste_produse(produse, cfg, raport)
    return construieste_xml(construieste_itemuri(pregatite, cfg, raport))


def numara(text: str) -> int:
    """Câte produse are un feed în acest format (pentru frâna de siguranță)."""
    return text.count("<SHOPITEM>")


def valideaza(text: str, cfg):
    from . import validare
    return validare.valideaza(text, cfg)
