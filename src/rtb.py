"""Feedul RTB House (RSS), replică a feedului Mulwi rtb_house.xml.

Tot catalogul activ, un item per produs, opt câmpuri. Disponibilitatea e
„in stock" la toate produsele, cum trimite Mulwi (nu depinde de stoc).
"""

from __future__ import annotations

from . import replica
from .replica import cdata


def _item(p, cfg):
    v = replica.varianta_principala(p, cfg.extra.get("varianta", "id_minim"))
    pret, pret_redus, are_comparat = replica.pret_si_pret_redus(v)
    img = p["imagini"][0]["url"] if p["imagini"] else ""
    return ("    <item>\n"
            f"    <product_id>{cdata(p['id'])}</product_id> \n"
            f"    <product_name>{cdata(replica.titlu_70(p['titlu']))}</product_name>\n"
            f"    <product_url>{cdata(replica.url_produs(p, cfg.magazin.url_produse))}</product_url>\n"
            "    \n"
            f"        <price>{pret}</price>\n"
            f"        <sale_price>{pret_redus}</sale_price>" + ("  " if are_comparat else "") + "\n"
            "      \n"
            f"    <category>{cdata(p['tip'])}</category>\n"
            f"    <image_link>{cdata(img)}</image_link>  \n"
            "    <g:availability>in stock</g:availability>\n"
            "    </item>\n")


def genereaza(produse: list[dict], cfg, raport) -> str:
    itemuri = []
    for p in replica.sortate_dupa_id(produse):
        if not p.get("variante"):
            raport.adauga("exclus_date_lipsa", p["id"], p["titlu"],
                          "produsul nu are nicio variantă în Shopify")
            continue
        if not p.get("imagini"):
            raport.adauga("fara_imagine", p["id"], p["titlu"],
                          "produsul nu are nicio imagine în Shopify; intră cu image_link gol, ca la Mulwi")
        itemuri.append(_item(p, cfg))
    text = ('<?xml version="1.0" encoding="utf-8" ?>\n'
            '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
            '<channel>\n'
            f'<title>{cfg.extra.get("titlu_canal", "RTB " + cfg.magazin.nume)}</title>\n'
            f'<link>{cfg.extra.get("link_canal", "https://" + cfg.magazin.nume)}</link>\n'
            '<description>Data feed</description>\n\n'
            + "\n".join(itemuri) + "\n</channel>\n</rss>")
    return replica.crlf(text)


def numara(text: str) -> int:
    return text.count("<item>")


def valideaza(text: str, cfg):
    from . import validare
    return validare.valideaza_rss(text, cfg, camp_id="product_id", camp_link="product_url")
