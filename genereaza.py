#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generează feedul XML Favi pentru ocean.ro din Shopify Admin API.

Rulare locală:
    python genereaza.py

Opțiuni:
    --magazin ocean        fișierul de configurare din config/ (implicit: ocean)
    --iesire out           folderul în care se scriu feedul și raportul
    --feed-live URL        feedul publicat, pentru frâna de siguranță
    --prag 70              procentul minim față de feedul live
    --limita N             oprește după N produse (doar pentru teste)
    --fara-frana           sare peste frâna de siguranță (doar local)

Ieșiri: out/oceanfavi.xml și out/raport.csv
Cod de ieșire 0 = feed bun de publicat; orice altceva = nu se publică.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from src import extragere, favi, validare
from src.config import Configurare, credentiale
from src.consola import pregateste as pregateste_consola
from src.raport import Raport

pregateste_consola()

RADACINA = Path(__file__).resolve().parent


def _sumar(text: str) -> None:
    """Scrie în rezumatul rulării din GitHub Actions, dacă rulăm acolo."""
    cale = os.environ.get("GITHUB_STEP_SUMMARY")
    if cale:
        with open(cale, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--magazin", default="ocean")
    ap.add_argument("--iesire", default="out")
    ap.add_argument("--feed-live", default=os.environ.get("FEED_LIVE_URL", ""))
    ap.add_argument("--prag", type=float, default=None)
    ap.add_argument("--limita", type=int, default=0)
    ap.add_argument("--fara-frana", action="store_true")
    args = ap.parse_args()

    inceput = time.time()
    cfg = Configurare(args.magazin)
    prag = args.prag if args.prag is not None else cfg.prag_minim_procent
    folder = (RADACINA / args.iesire)
    folder.mkdir(parents=True, exist_ok=True)
    raport = Raport()

    # ---------------------------------------------------------------- 1. extragere
    store, token, client_id, client_secret = credentiale()
    if not store:
        print("EROARE: lipsește SHOPIFY_STORE (în .env local sau în Secrets pe GitHub).")
        return 2
    if not token:
        if not (client_id and client_secret):
            print("EROARE: lipsesc credențialele Shopify. Completează SHOPIFY_TOKEN, "
                  "sau SHOPIFY_CLIENT_ID și SHOPIFY_CLIENT_SECRET.")
            return 2
        print("Obțin tokenul din Client ID + Client secret...")
        try:
            token = extragere.obtine_token(
                extragere.normalizeaza_store(store), client_id, client_secret)
        except extragere.EroareShopify as e:
            print(f"EROARE la obținerea tokenului: {e}")
            _sumar("## Rulare eșuată\n\nNu am putut obține tokenul Shopify: "
                   f"`{e}`\n")
            return 3

    client = extragere.ClientShopify(store, token)
    print(f"Magazin {client.store} | API {extragere.API_VERSION} | tag {cfg.tag}")

    def progres(pagina, n, total):
        print(f"  pagina {pagina}: {n} produse (cumulat {total})", flush=True)

    try:
        produse = extragere.descarca_produse(client, cfg.tag, la_pagina=progres)
    except extragere.EroareShopify as e:
        print(f"EROARE la extragerea din Shopify: {e}")
        _sumar(f"## Rulare eșuată\n\nNu am putut citi produsele din Shopify: `{e}`\n")
        return 3

    if args.limita:
        produse = produse[:args.limita]
        print(f"ATENȚIE: rulare limitată artificial la {len(produse)} produse (--limita). "
              f"Frâna de siguranță va vedea scăderea și va opri publicarea.")

    print(f"Produse cu tagul {cfg.tag}: {len(produse)}")
    if not produse:
        print("EROARE: niciun produs cu tagul cerut. Verifică numele tagului în config/ocean.yaml.")
        _sumar(f"## Rulare eșuată\n\nNiciun produs cu tagul `{cfg.tag}`.\n")
        return 4

    # ---------------------------------------------------------------- 2. normalizare + formatare
    pregatite = favi.pregateste_produse(produse, cfg, raport)
    itemuri = favi.construieste_itemuri(pregatite, cfg, raport)
    xml_text = favi.construieste_xml(itemuri)

    cale_feed = folder / cfg.fisier_feed
    cale_raport = folder / cfg.fisier_raport
    cale_feed.write_text(xml_text, encoding="utf-8")
    raport.scrie_csv(cale_raport)

    # ---------------------------------------------------------------- 3. validare
    rezultat = validare.valideaza(xml_text, cfg)
    stat = rezultat.statistici
    numarare = raport.numarare()

    print()
    print("=" * 62)
    print(f"Produse selectate din Shopify : {len(produse)}")
    print(f"SHOPITEM scrise în feed       : {rezultat.numar_produse}")
    print(f"Categorii distincte           : {stat.get('categorii_distincte', 0)}")
    print(f"Parametri per produs          : min {stat.get('parametri_min')}, "
          f"media {stat.get('parametri_medie')}, max {stat.get('parametri_max')}")
    print(f"Cu preț de livrare (DELIVERY) : {stat.get('cu_delivery', 0)}")
    print(f"Cu EAN valid                  : {stat.get('cu_ean', 0)}")
    print(f"Variante grupate (ITEMGROUP)  : {stat.get('cu_itemgroup', 0)}")
    print("-" * 62)
    for motiv, n in numarare.most_common():
        print(f"  {motiv:22s} {n}")
    print("=" * 62)
    for a in rezultat.avertizari:
        print(f"Avertisment: {a}")
    for e in rezultat.erori:
        print(f"EROARE de validare: {e}")

    rezumat = [
        f"## Feed {cfg.fisier_feed}",
        "",
        "| Indicator | Valoare |",
        "| --- | ---: |",
        f"| Produse cu tagul {cfg.tag} | {len(produse)} |",
        f"| Produse scrise în feed | {rezultat.numar_produse} |",
        f"| Categorii distincte | {stat.get('categorii_distincte', 0)} |",
        f"| Cu preț de livrare | {stat.get('cu_delivery', 0)} |",
        f"| Rânduri în raport | {len(raport)} |",
        "",
        "### Produse problematice",
        "",
        raport.rezumat_markdown(),
    ]
    if rezultat.avertizari:
        rezumat += ["### Avertismente", ""] + [f"- {a}" for a in rezultat.avertizari] + [""]
    if rezultat.erori:
        rezumat += ["### Erori de validare", ""] + [f"- {e}" for e in rezultat.erori] + [""]
    _sumar("\n".join(rezumat))

    if not rezultat.valid:
        print("\nFeedul NU trece validarea. Nu se publică.")
        return 5

    # ---------------------------------------------------------------- 4. frâna de siguranță
    if args.fara_frana:
        print("\nFrâna de siguranță: sărită la cerere (--fara-frana).")
    elif args.feed_live:
        live = validare.citeste_feed_live(args.feed_live)
        poate, mesaj = validare.verifica_frana(rezultat.numar_produse, live, prag)
        print(f"\n{mesaj}")
        _sumar(f"### Frâna de siguranță\n\n{mesaj}\n")
        if not poate:
            return 6
    else:
        print("\nFrâna de siguranță: fără URL de feed live, se sare.")

    durata = time.time() - inceput
    print(f"\nGata în {durata:.0f} s. Feed: {cale_feed}  |  Raport: {cale_raport}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
