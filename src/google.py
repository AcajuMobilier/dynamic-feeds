"""Feeduri RSS în formatul Google Shopping (și varianta pentru Facebook).

Fiecare feed replicat are propriul șablon de item, copiat exact din feedul
Mulwi pe care îl înlocuiește, inclusiv spațiile de la capăt de linie: așa
diff-ul cu referința rămâne curat. Singura diferență agreată cu clientul:
etichetele (custom_label) goale sau doar cu spații se omit complet.

Șabloanele se aleg din config prin `extra.sablon`:
    ocean_google   – Google Shopping ocean.ro (Mulwi shopping.xml)
    ocean_fb       – Facebook ocean.ro (Mulwi custom.xml)
    acaju_google   – Google Shopping acaju.ro (Mulwi s1nz-google_shopping.xml)
"""

from __future__ import annotations

from . import replica
from .replica import cdata


def _antet(cfg) -> str:
    return ('<?xml version="1.0" encoding="utf-8" ?>\n'
            '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
            '<channel>\n'
            f'<title>{cfg.extra.get("titlu_canal", "Google Shopping " + cfg.magazin.nume)}</title>\n'
            f'<link>{cfg.extra.get("link_canal", "https://" + cfg.magazin.nume)}</link>\n'
            '<description>Data feed</description>\n\n')


def _eticheta(linii: list, nume: str, valoare: str, indent: str, omite_goale: bool,
              cdata_val: bool = False) -> None:
    """Adaugă o linie de custom_label; dacă e goală și clientul vrea omise, nu."""
    if omite_goale and replica.e_gol(valoare):
        return
    v = cdata(valoare) if cdata_val else valoare
    linii.append(f"{indent}<g:{nume}>{v}</g:{nume}>")


# ---------------------------------------------------------------- ocean Google
def _item_ocean_google(p, cfg, raport):
    v = replica.varianta_principala(p, cfg.extra.get("varianta", "id_minim"))
    pret, pret_redus, _ = replica.pret_si_pret_redus(v)
    stoc = (p.get("stoc_total") or 0) > 0
    taguri = set(p.get("taguri") or [])
    omite = cfg.extra.get("omite_etichete_goale", True)
    L = ["    <item>",
         f"    <g:id>{cdata(p['id'])}</g:id>    ",
         f"    <title>{cdata(replica.titlu_70(p['titlu']))}</title>",
         f"    <link>{cdata(replica.url_produs(p, cfg.magazin.url_produse))}</link>      ",
         "    ",
         f"        <g:price>{pret}</g:price>",
         f"        <g:sale_price>{pret_redus}</g:sale_price>",
         "          ",
         f"    <description>{cdata(replica.descriere_plata(p['descriere_html']))}</description>",
         f"    <g:product_type>{cdata(p['tip'])}</g:product_type>",
         f"    <g:google_product_category>{cdata('')}</g:google_product_category>",
         f"    <g:image_link>{cdata(p['imagini'][0]['url'] if p['imagini'] else '')}</g:image_link>",
         "    <g:condition>new</g:condition>",
         # Mulwi trimite „in stock" la toate produsele acestui feed, și la stoc 0
         "    <g:availability>in stock</g:availability>",
         f"    <brand>{cdata(p['vendor'])}</brand>",
         f"    <g:mpn>{cdata(v.get('sku') or '')}</g:mpn>  ",
         f"      <g:shipping_weight>{replica.greutate_kg_text(v.get('greutate_kg'))}</g:shipping_weight>",
         "      "]
    _eticheta(L, "custom_label_0", "livrare rapida" if stoc else "La Comanda", "        ", omite)
    L += ["    ", "    "]
    # custom_label_1 și 2 sunt mereu doar spații la Mulwi -> omise
    _eticheta(L, "custom_label_1", "\n         \n    ", "        ", omite)
    L += ["    "]
    _eticheta(L, "custom_label_2", " \n        \n    ", "    ", omite)
    L += ["    ", "    "]
    _eticheta(L, "custom_label_3", "PRETMICZILNIC" if "PRETMICZILNIC" in taguri else "", "        ", omite)
    L += ["    ", "    ", "    "]
    eticheta4 = (" \n            " + (" PROMO8 " if "PROMO8" in taguri else "")
                 + "\n             " + (" promolunar " if "promolunar" in taguri else "") + "\n        ")
    _eticheta(L, "custom_label_4", eticheta4, "        ", omite)
    L += ["    ", "    ", "     ",
          "        <g:shipping_label>paid</g:shipping_label>",
          "      ", "    ", "    </item>"]
    return "\n".join(L)


# ---------------------------------------------------------------- ocean Facebook
def _item_ocean_fb(p, cfg, raport):
    v = replica.varianta_principala(p, cfg.extra.get("varianta", "id_minim"))
    pret, pret_redus, _ = replica.pret_si_pret_redus(v)
    taguri = set(p.get("taguri") or [])
    omite = cfg.extra.get("omite_etichete_goale", True)
    # Mulwi pune TOATE media (inclusiv previzualizările de video/3D), cu
    # prima imagine inclusă, într-un singur element, între paranteze drepte.
    media = [m["url"] for m in (p.get("media") or [])] or [i["url"] for i in p["imagini"]]
    L = ["    <item>",
         f"    <g:id>{cdata(p['id'])}</g:id> ",
         f"    <title>{cdata(replica.titlu_70(p['titlu']))}</title>",
         f"    <link>{cdata(replica.url_produs(p, cfg.magazin.url_produse))}</link>",
         "    ",
         f"        <g:price>{pret}</g:price>",
         f"        <g:sale_price>{pret_redus}</g:sale_price>",
         "      ",
         f"    <description>{cdata(replica.descriere_plata(p['descriere_html']))}</description>",
         f"    <g:product_type>{cdata(p['tip'])}</g:product_type>",
         f"    <g:google_product_category>{cdata('')}</g:google_product_category>",
         f"    <g:image_link>{cdata(p['imagini'][0]['url'] if p['imagini'] else '')}</g:image_link> ",
         f"    <g:additional_image_link>{cdata('[' + ' '.join(media) + ']')}</g:additional_image_link> ",
         "    <g:condition>new</g:condition>",
         "    <g:availability>in stock</g:availability>",
         f"    <brand>{cdata(p['vendor'])}</brand> ",
         f"    <g:mpn>{cdata(v.get('sku') or '')}</g:mpn>",
         "     "]
    _eticheta(L, "custom_label_1", "\n         \n    ", "    ", omite)
    L += ["    "]
    _eticheta(L, "custom_label_2", " \n        \n    ", "    ", omite)
    L += ["    ", "    "]
    _eticheta(L, "custom_label_3", "", "        ", omite)
    L += ["    "]
    eticheta4 = (" \n            " + (" PROMO8 " if "PROMO8" in taguri else "")
                 + "\n             " + (" promolunar " if "promolunar" in taguri else "") + "\n        ")
    _eticheta(L, "custom_label_4", eticheta4, "    ", omite)
    L += ["    </item>"]
    return "\n".join(L)


# ---------------------------------------------------------------- acaju Google
def _item_acaju_google(p, cfg, raport):
    v = replica.varianta_principala(p, cfg.extra.get("varianta", "id_minim"))
    pret, pret_redus, are_comparat = replica.pret_si_pret_redus(v)
    stoc = replica.in_stoc(v)
    taguri = set(p.get("taguri") or [])
    omite = cfg.extra.get("omite_etichete_goale", True)
    data_backorder = cfg.extra.get("data_disponibilitate", "")
    L = ["    <item>",
         f"    <g:id>{cdata(p['id'])}</g:id>    ",
         f"    <title>{cdata(replica.titlu_70(p['titlu']))}</title>",
         f"    <link>{cdata(replica.url_produs(p, cfg.magazin.url_produse))}</link>      ",
         "    ",
         f"        <g:price>{pret}</g:price>",
         f"        <g:sale_price>{pret_redus}</g:sale_price>" + ("  " if are_comparat else ""),
         "          ",
         f"    <description>{cdata(replica.descriere_plata(p['descriere_html']))}</description>",
         f"    <g:product_type>{cdata(p['tip'])}</g:product_type>",
         f"    <g:google_product_category>{cdata('')}</g:google_product_category>",
         f"    <g:image_link>{cdata(p['imagini'][0]['url'] if p['imagini'] else '')}</g:image_link>",
         "    <g:condition>new</g:condition> ",
         "      "]
    if stoc:
        L.append("        <g:availability>in stock</g:availability>")
    else:
        L.append("        <g:availability>backorder</g:availability>")
        if data_backorder:
            L.append(f"        <g:availability_date>{data_backorder}</g:availability_date> ")
    L += ["      ",
          f"    <brand>{cdata(p['vendor'])}</brand>",
          f"    <g:mpn>{cdata(v.get('sku') or '')}</g:mpn>",
          f"    <g:gtin>{cdata(v.get('barcode') or '')}</g:gtin> ",
          f"    <g:shipping_weight>{replica.greutate_kg_text(v.get('greutate_kg'))}</g:shipping_weight>",
          "    ", "     "]
    _eticheta(L, "custom_label_0", "livrare rapida" if stoc else "La Comanda", "        ", omite)
    L += ["      "]
    _eticheta(L, "custom_label_1", v.get("sku") or "", "        ", omite, cdata_val=True)
    eticheta2 = "\n"
    for t in ("TOP1AKJ", "TOP2AKJ", "TOP3AKJ"):
        eticheta2 += " " * 12 + (f" {t} " if t in taguri else "") + "\n"
    eticheta2 += " " * 8
    if not (omite and replica.e_gol(eticheta2)):
        L.append(f"        <g:custom_label_2>{eticheta2}</g:custom_label_2>  ")
    L += ["    "]
    eticheta3 = next((t for t in ("ZILNICPRETBUN", "PROMO8", "FINALDEGAMA") if t in taguri), "")
    _eticheta(L, "custom_label_3", eticheta3, "        ", omite)
    L += ["     ", "  ", "  "]
    _eticheta(L, "custom_label_4", "PROMO7" if "PROMO7" in taguri else "", "        ", omite)
    L += ["     ", "    ",
          "        <g:shipping_label>paid</g:shipping_label>",
          "      ", "    ", "    </item>"]
    return "\n".join(L)


SABLOANE = {
    "ocean_google": _item_ocean_google,
    "ocean_fb": _item_ocean_fb,
    "acaju_google": _item_acaju_google,
}


def genereaza(produse: list[dict], cfg, raport) -> str:
    sablon = cfg.extra.get("sablon")
    if sablon not in SABLOANE:
        raise SystemExit(f"EROARE: feedul {cfg.nume_feed} cere șablonul necunoscut {sablon!r}; "
                         f"există: {sorted(SABLOANE)}")
    item = SABLOANE[sablon]
    itemuri = []
    for p in replica.sortate_dupa_id(produse):
        if not p.get("variante"):
            raport.adauga("exclus_date_lipsa", p["id"], p["titlu"],
                          "produsul nu are nicio variantă în Shopify")
            continue
        if not p.get("imagini"):
            raport.adauga("fara_imagine", p["id"], p["titlu"],
                          "produsul nu are nicio imagine în Shopify; intră cu image_link gol, ca la Mulwi")
        if not p.get("url"):
            raport.adauga("nepublicat_in_feed", p["id"], p["titlu"],
                          "nepublicat pe Online Store, dar intră în feed cu adresa din handle, ca la Mulwi")
        itemuri.append(item(p, cfg, raport))
    text = _antet(cfg) + "\n\n".join(itemuri) + "\n\n</channel>\n</rss>"
    return replica.crlf(text)


def numara(text: str) -> int:
    return text.count("<item>")


def valideaza(text: str, cfg):
    from . import validare
    return validare.valideaza_rss(text, cfg, camp_id="g:id", camp_link="link")
