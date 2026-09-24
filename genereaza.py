#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generează feedurile pentru marketplace-uri din Shopify Admin API.

Rulare locală:
    python genereaza.py                        toate feedurile din config/feeduri/
    python genereaza.py --feed oceanfavi       doar unul (se poate repeta)
    python genereaza.py --magazin acaju        toate feedurile unui magazin

Opțiuni:
    --iesire public          folderul în care se scriu feedurile (se publică)
    --iesire-raport raport   folderul rapoartelor (rămâne privat)
    --fara-frana             sare peste frâna de siguranță (doar local)
    --fara-live              nu descarcă versiunile live ale feedurilor picate
    --limita N               oprește după N produse per magazin (teste)

Fiecare feed e independent: o problemă la unul nu oprește publicarea
celorlalte. Pentru un feed care pică, în folderul de ieșire se pune copia
aflată live, ca adresa lui să nu rămână goală.

Coduri de ieșire:
    0  folderul de ieșire e complet (toate feedurile bune sau păstrate din live)
    7  folderul de ieșire NU e complet: un feed a picat și nici versiunea
       live nu a putut fi luată; NU se publică
    2  configurare sau credențiale lipsă
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from src import extragere, formate, selectie, validare
from src.config import Configurare, feeduri_disponibile, magazine
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


# ---------------------------------------------------------------- extragere
def extrage_catalog(magazin, limita: int) -> tuple[list[dict] | None, str]:
    """Catalogul activ al unui magazin, sau (None, motiv) la eșec."""
    store, token = magazin.credentiale()
    if not store or not token:
        return None, (f"lipsesc credențialele: variabilele {magazin.variabila_store} și "
                      f"{magazin.variabila_token} (în .env local sau în Secrets pe GitHub)")
    client = extragere.ClientShopify(store, token)
    print(f"\n[{magazin.cheie}] {client.store} | API {extragere.API_VERSION}")

    def progres(pagina, n, total):
        if pagina % 5 == 0 or n < extragere.PRODUSE_PER_PAGINA:
            print(f"  pagina {pagina}: cumulat {total} produse", flush=True)

    try:
        produse = extragere.descarca_catalog(client, "status:active", la_pagina=progres)
    except extragere.EroareShopify as e:
        return None, f"Shopify: {e}"
    # Shopify retrage versiunile de API după ~un an și răspunde atunci cu cea
    # mai veche versiune încă disponibilă. Semnalăm din timp, ca schimbarea
    # din src/extragere.py să nu fie o surpriză.
    servita = client.versiune_servita
    if servita and servita != extragere.API_VERSION:
        mesaj = (f"Shopify a răspuns cu versiunea de API {servita}, nu cu {extragere.API_VERSION} "
                 f"cerută de cod: versiunea cerută a fost retrasă. Schimbă API_VERSION în "
                 f"src/extragere.py cu una curentă (vezi README, secțiunea Întreținere).")
        print(f"  ATENȚIE: {mesaj}")
        _sumar(f"### ⚠️ Versiune de API Shopify retrasă\n\n{mesaj}\n")
    if limita:
        produse = produse[:limita]
        print(f"  ATENȚIE: catalog limitat artificial la {len(produse)} produse (--limita).")
    print(f"  {len(produse)} produse active")
    return produse, ""


# ---------------------------------------------------------------- un feed
def genereaza_feed(cfg, catalog: list[dict], folder: Path, folder_raport: Path,
                   fara_frana: bool) -> dict:
    """Generează, validează și decide pentru un singur feed.

    Întoarce starea: ok (bool), mesaj, contoare. Scrie feedul în folder doar
    dacă e bun de publicat.
    """
    stare = {"feed": cfg.nume_feed, "fisier": cfg.fisier, "magazin": cfg.magazin.cheie,
             "format": cfg.format, "ok": False, "mesaj": "", "produse": 0,
             "selectate": 0, "raport": 0, "frana": ""}
    raport = Raport()
    produse, contor = selectie.selecteaza(catalog, cfg)
    stare["selectate"] = len(produse)
    print(f"\n== {cfg.nume_feed} ({cfg.fisier}): {selectie.descrie_selectia(cfg)} -> {len(produse)}")
    if not produse:
        stare["mesaj"] = "niciun produs nu trece selecția; verifică tagurile din config"
        return stare

    modul = formate.modul(cfg.format)
    try:
        text = modul.genereaza(produse, cfg, raport)
    except Exception as e:                       # noqa: BLE001 - un feed nu trebuie să le oprească pe celelalte
        stare["mesaj"] = f"eroare la generare: {type(e).__name__}: {e}"
        stare["raport"] = len(raport)
        raport.scrie_csv(folder_raport / f"raport-{cfg.nume_feed}.csv")
        return stare

    raport.scrie_csv(folder_raport / f"raport-{cfg.nume_feed}.csv")
    stare["raport"] = len(raport)
    stare["motive"] = dict(raport.numarare())

    rezultat = modul.valideaza(text, cfg)
    stare["produse"] = rezultat.numar_produse
    stare["statistici"] = rezultat.statistici
    for a in rezultat.avertizari:
        print(f"  avertisment: {a}")
    if not rezultat.valid:
        for e in rezultat.erori:
            print(f"  EROARE de validare: {e}")
        stare["mesaj"] = "nu trece validarea: " + " | ".join(rezultat.erori)
        return stare

    if fara_frana:
        stare["frana"] = "sărită la cerere"
    else:
        live = validare.citeste_feed_live(cfg.url_live, numara=modul.numara)
        poate, mesaj = validare.verifica_frana(rezultat.numar_produse, live, cfg.prag_minim_procent)
        stare["frana"] = mesaj
        print(f"  {mesaj}")
        if not poate:
            stare["mesaj"] = "oprit de frâna de siguranță"
            return stare

    (folder / cfg.fisier).write_text(text, encoding="utf-8")
    stare["ok"] = True
    stare["mesaj"] = f"{rezultat.numar_produse} produse"
    print(f"  scris {folder / cfg.fisier}: {rezultat.numar_produse} produse, "
          f"{len(raport)} rânduri în raport")
    return stare


def pastreaza_versiunea_live(cfg, folder: Path) -> bool:
    """Pentru un feed care a picat: pune în folder copia aflată live."""
    text = validare.descarca_feed_live(cfg.url_live)
    if text is None:
        return False
    (folder / cfg.fisier).write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------- rezumat
def scrie_rezumat(stari: list[dict], complet: bool) -> None:
    linii = ["## Feeduri", "", "| Feed | Magazin | Stare | Produse | Selectate | Raport |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    for s in stari:
        if s["ok"]:
            eticheta = "✅ publicat"
        elif s.get("pastrat_live"):
            eticheta = "⚠️ păstrat cel vechi"
        else:
            eticheta = "❌ lipsă"
        linii.append(f"| {s['feed']} | {s['magazin']} | {eticheta} | {s['produse']} | "
                     f"{s['selectate']} | {s['raport']} |")
    linii.append("")
    for s in stari:
        if not s["ok"]:
            linii.append(f"- **{s['feed']}**: {s['mesaj']}")
        elif s.get("frana"):
            linii.append(f"- {s['feed']}: {s['frana']}")
    linii.append("")
    for s in stari:
        if s.get("motive"):
            linii.append(f"### {s['feed']}: produse problematice")
            linii.append("")
            linii.append("| Motiv | Produse |")
            linii.append("| --- | ---: |")
            for motiv, n in sorted(s["motive"].items(), key=lambda x: -x[1]):
                linii.append(f"| {motiv.replace('_', ' ')} | {n} |")
            linii.append("")
    linii.append("Rapoartele complete, cu o linie per produs, sunt în secțiunea **Artifacts** "
                 "a acestei pagini, în arhiva `rapoarte`. Nu se publică la o adresă publică, "
                 "pentru că includ produse nepublicate sau arhivate.")
    if not complet:
        linii.append("")
        linii.append("**Publicarea a fost oprită**: un feed a picat și nici versiunea lui live "
                     "nu a putut fi păstrată. Feedurile de la adresa publică rămân cele vechi.")
    _sumar("\n".join(linii))


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", action="append", default=[])
    ap.add_argument("--magazin", action="append", default=[])
    ap.add_argument("--iesire", default="out")
    ap.add_argument("--iesire-raport", default=None)
    ap.add_argument("--fara-frana", action="store_true")
    ap.add_argument("--fara-live", action="store_true")
    ap.add_argument("--limita", type=int, default=0)
    args = ap.parse_args()

    inceput = time.time()
    folder = RADACINA / args.iesire
    folder_raport = RADACINA / args.iesire_raport if args.iesire_raport else folder
    folder.mkdir(parents=True, exist_ok=True)
    folder_raport.mkdir(parents=True, exist_ok=True)

    toate = feeduri_disponibile()
    nume_feeduri = args.feed or toate
    necunoscute = [f for f in nume_feeduri if f not in toate]
    if necunoscute:
        print(f"EROARE: feeduri necunoscute: {necunoscute}. Există: {toate}")
        return 2
    configuri = [Configurare(n) for n in nume_feeduri]
    if args.magazin:
        configuri = [c for c in configuri if c.magazin.cheie in args.magazin]
    if not configuri:
        print("EROARE: niciun feed de generat.")
        return 2
    print("Feeduri: " + ", ".join(c.nume_feed for c in configuri))

    # 1. o extragere per magazin
    cataloage: dict[str, list[dict] | None] = {}
    erori_magazin: dict[str, str] = {}
    for cheie in sorted({c.magazin.cheie for c in configuri}):
        catalog, motiv = extrage_catalog(magazine()[cheie], args.limita)
        cataloage[cheie] = catalog
        if catalog is None:
            erori_magazin[cheie] = motiv
            print(f"  EROARE la {cheie}: {motiv}")

    # 2. fiecare feed, independent
    stari = []
    for cfg in configuri:
        catalog = cataloage.get(cfg.magazin.cheie)
        if catalog is None:
            stari.append({"feed": cfg.nume_feed, "fisier": cfg.fisier, "magazin": cfg.magazin.cheie,
                          "format": cfg.format, "ok": False, "produse": 0, "selectate": 0,
                          "raport": 0, "frana": "",
                          "mesaj": f"magazinul nu a putut fi citit: {erori_magazin[cfg.magazin.cheie]}"})
            continue
        stari.append(genereaza_feed(cfg, catalog, folder, folder_raport, args.fara_frana))

    # 3. feedurile picate: păstrăm versiunea live, ca adresa să nu rămână goală
    complet = True
    for s, cfg in zip(stari, configuri):
        if s["ok"]:
            continue
        if args.fara_live:
            s["pastrat_live"] = False
            continue
        s["pastrat_live"] = pastreaza_versiunea_live(cfg, folder)
        if s["pastrat_live"]:
            print(f"  {cfg.nume_feed}: păstrată versiunea aflată live")
        else:
            print(f"  {cfg.nume_feed}: nu există versiune live de păstrat")
            # fără feed live (prima rulare) publicarea poate merge înainte;
            # altfel adresa lui ar rămâne goală și nu publicăm nimic
            if validare.exista_feed_live(cfg.url_live):
                complet = False

    (folder / "stare.json").write_text(
        json.dumps({"generat_la": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                    "complet": complet, "feeduri": stari}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    scrie_rezumat(stari, complet)

    print("\n" + "=" * 62)
    for s in stari:
        semn = "OK  " if s["ok"] else ("VECHI" if s.get("pastrat_live") else "PICA")
        print(f"  {semn:5s} {s['feed']:14s} {s['mesaj']}")
    print("=" * 62)
    durata = time.time() - inceput
    print(f"Gata în {durata:.0f} s. Ieșire: {folder}")
    if not complet:
        print("Folderul de ieșire NU e complet. Nu se publică.")
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())
