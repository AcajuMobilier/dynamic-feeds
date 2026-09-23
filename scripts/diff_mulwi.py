#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raport de diff semantic între feedurile noastre și feedurile Mulwi.

Descarcă feedurile Mulwi vii și, în același interval, extrage catalogul din
Shopify și generează feedurile noastre; apoi le compară item cu item:
aceleași ID-uri, aceleași valori pe câmpurile esențiale (preț, preț redus,
disponibilitate, adresă, imagine, titlu, tip, brand, SKU, etichete),
raportând tot ce diferă și de ce.

Rulare:  python scripts/diff_mulwi.py            -> docs/diff_mulwi_<data>.md
         python scripts/diff_mulwi.py --local    -> fără descărcare, folosește fișierele deja existente
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADACINA))
from src import extragere, formate, selectie                  # noqa: E402
from src.config import Configurare, magazine                  # noqa: E402
from src.consola import pregateste as pregateste_consola      # noqa: E402
from src.raport import Raport                                 # noqa: E402

pregateste_consola()

MULWI = {
    "acajugoogle": "https://feed.mulwi.com/f/velluttoro/s1nz-google_shopping.xml",
    "acajudsa": "https://feed.mulwi.com/f/velluttoro/custom_csv.csv",
    "acajurtb": "https://feed.mulwi.com/f/velluttoro/rtb_house.xml",
    "oceangoogle": "https://feed.mulwi.com/f/ocean-acaju/shopping.xml",
    "oceanfb": "https://feed.mulwi.com/f/ocean-acaju/custom.xml",
    # feedul Favi de acaju e in format Google la Mulwi; noi trecem pe Heureka,
    # deci comparam doar ID-urile
    "acajufavi": "https://feed.mulwi.com/f/velluttoro/1yc0-heureka.xml",
}
NS = "{http://base.google.com/ns/1.0}"
FOLDER = RADACINA / "out" / "diff"


def descarca(url: str) -> str:
    cerere = urllib.request.Request(url, headers={"User-Agent": "dynamic-feeds diff"})
    with urllib.request.urlopen(cerere, timeout=600) as r:
        return r.read().decode("utf-8", errors="replace")


def itemuri_rss(text: str, camp_id: str) -> dict[str, dict]:
    """id -> {camp: valoare}, cu etichetele curățate de spații."""
    rez = {}
    root = ET.fromstring(text)
    for it in root.findall("./channel/item"):
        d = {}
        for ch in it:
            nume = ch.tag.replace(NS, "g:")
            val = (ch.text or "")
            if nume.startswith("g:custom_label"):
                val = " ".join(val.split())        # etichetele: doar tokenii
            d.setdefault(nume, []).append(val.strip() if nume not in ("description",) else val)
        d = {k: (v[0] if len(v) == 1 else v) for k, v in d.items()}
        rez[d.get(camp_id, "")] = d
    return rez


def randuri_csv(text: str) -> dict[str, str]:
    linii = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    return {r[0]: r[1] for r in linii[1:] if len(r) == 2}


def compara_rss(feed, al_nostru, mulwi, camp_id, esentiale):
    a, b = itemuri_rss(al_nostru, camp_id), itemuri_rss(mulwi, camp_id)
    ida, idb = set(a), set(b)
    dif_camp = defaultdict(list)
    for pid in ida & idb:
        for c in esentiale:
            va, vb = a[pid].get(c, ""), b[pid].get(c, "")
            if va != vb:
                dif_camp[c].append((pid, vb, va))
    campuri_a = Counter(k for d in a.values() for k in d)
    campuri_b = Counter(k for d in b.values() for k in d)
    return {"noi": len(ida), "mulwi": len(idb), "comune": len(ida & idb),
            "doar_noi": sorted(ida - idb), "doar_mulwi": sorted(idb - ida),
            "dif_camp": dif_camp, "campuri_noi": campuri_a, "campuri_mulwi": campuri_b}


def scrie_raport(rezultate: dict, moment: str) -> Path:
    L = [f"# Diff semantic față de feedurile Mulwi", "",
         f"Feedurile Mulwi și catalogul Shopify au fost luate în același interval: {moment}.", "",
         "Pentru fiecare feed: numărul de produse, ID-urile care există doar într-o parte, "
         "și valorile diferite pe câmpurile esențiale. Etichetele (custom_label) se compară "
         "după conținut, fără spațiile de umplutură din Mulwi; cele goale sunt omise la noi, "
         "cum s-a agreat.", ""]
    for feed, r in rezultate.items():
        L.append(f"## {feed}")
        L.append("")
        if "eroare" in r:
            L += [f"Nu s-a putut compara: {r['eroare']}", ""]
            continue
        L += ["| | Al nostru | Mulwi |", "| --- | ---: | ---: |",
              f"| Produse | {r['noi']} | {r['mulwi']} |",
              f"| ID-uri comune | {r['comune']} | |",
              f"| ID-uri doar la noi | {len(r['doar_noi'])} | |",
              f"| ID-uri doar la Mulwi | | {len(r['doar_mulwi'])} |", ""]
        if r["doar_noi"]:
            L.append(f"Doar la noi (ex.): {', '.join(r['doar_noi'][:10])}")
        if r["doar_mulwi"]:
            L.append(f"Doar la Mulwi (ex.): {', '.join(r['doar_mulwi'][:10])}")
        if r["doar_noi"] or r["doar_mulwi"]:
            L.append("")
        dif = r.get("dif_camp") or {}
        if not dif:
            L.append("Toate câmpurile esențiale sunt identice pe toate ID-urile comune.")
        else:
            L += ["| Câmp | Produse diferite | Exemplu (ID: Mulwi → al nostru) |", "| --- | ---: | --- |"]
            for c, lista in sorted(dif.items(), key=lambda x: -len(x[1])):
                pid, vb, va = lista[0]
                ex = f"{pid}: `{str(vb)[:60]}` → `{str(va)[:60]}`"
                L.append(f"| {c} | {len(lista)} | {ex} |")
        # câmpuri prezente doar într-o parte
        cn, cm = r.get("campuri_noi") or {}, r.get("campuri_mulwi") or {}
        doar_m = {k: v for k, v in cm.items() if k not in cn}
        doar_n = {k: v for k, v in cn.items() if k not in cm}
        if doar_m or doar_n:
            L.append("")
            if doar_m:
                L.append("Câmpuri prezente doar la Mulwi (număr de produse): " +
                         ", ".join(f"{k} ({v})" for k, v in doar_m.items()))
            if doar_n:
                L.append("Câmpuri prezente doar la noi: " + ", ".join(f"{k} ({v})" for k, v in doar_n.items()))
        L.append("")
    cale = RADACINA / "docs" / f"diff_mulwi_{moment[:10]}.md"
    cale.write_text("\n".join(L), encoding="utf-8")
    return cale


def main() -> int:
    local = "--local" in sys.argv
    FOLDER.mkdir(parents=True, exist_ok=True)
    moment = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    # 1. referințele Mulwi
    referinte = {}
    for feed, url in MULWI.items():
        cale = FOLDER / f"mulwi_{feed}{'.csv' if feed == 'acajudsa' else '.xml'}"
        if local and cale.exists():
            referinte[feed] = cale.read_text(encoding="utf-8")
            continue
        print(f"descarc {feed}...", flush=True)
        try:
            referinte[feed] = descarca(url)
            cale.write_text(referinte[feed], encoding="utf-8", newline="")
        except Exception as e:                       # noqa: BLE001
            referinte[feed] = None
            print(f"  nu am putut descărca {feed}: {e}")

    # 2. cataloagele noastre, în același interval
    cataloage = {}
    for cheie, m in magazine().items():
        cale = FOLDER / f"catalog_{cheie}.json"
        if local and cale.exists():
            cataloage[cheie] = json.loads(cale.read_text(encoding="utf-8"))
            continue
        store, token = m.credentiale()
        print(f"extrag {cheie}...", flush=True)
        cataloage[cheie] = extragere.descarca_catalog(extragere.ClientShopify(store, token))
        cale.write_text(json.dumps(cataloage[cheie], ensure_ascii=False), encoding="utf-8")

    # 3. generare + comparare
    rezultate = {}
    for feed in MULWI:
        if referinte.get(feed) is None:
            rezultate[feed] = {"eroare": "feedul Mulwi nu a putut fi descărcat"}
            continue
        cfg = Configurare(feed)
        sel, _ = selectie.selecteaza(cataloage[cfg.magazin.cheie], cfg)
        text = formate.modul(cfg.format).genereaza(sel, cfg, Raport())
        (FOLDER / cfg.fisier).write_text(text, encoding="utf-8", newline="")
        if feed == "acajudsa":
            a, b = randuri_csv(text), randuri_csv(referinte[feed])
            dif = [(u, b[u], a[u]) for u in set(a) & set(b) if a[u] != b[u]]
            rezultate[feed] = {"noi": len(a), "mulwi": len(b), "comune": len(set(a) & set(b)),
                               "doar_noi": sorted(set(a) - set(b)), "doar_mulwi": sorted(set(b) - set(a)),
                               "dif_camp": {"Custom label": dif} if dif else {},
                               "campuri_noi": {}, "campuri_mulwi": {}}
        elif feed == "acajufavi":
            noi = {it.findtext("ITEM_ID") for it in ET.fromstring(text).findall("SHOPITEM")}
            mulwi = set(itemuri_rss(referinte[feed], "g:id"))
            rezultate[feed] = {"noi": len(noi), "mulwi": len(mulwi), "comune": len(noi & mulwi),
                               "doar_noi": sorted(noi - mulwi), "doar_mulwi": sorted(mulwi - noi),
                               "dif_camp": {}, "campuri_noi": {}, "campuri_mulwi": {}}
        elif feed == "acajurtb":
            rezultate[feed] = compara_rss(feed, text, referinte[feed], "product_id",
                                          ["product_name", "product_url", "price", "sale_price",
                                           "category", "image_link", "g:availability"])
        else:
            rezultate[feed] = compara_rss(feed, text, referinte[feed], "g:id",
                                          ["title", "link", "g:price", "g:sale_price", "g:availability",
                                           "g:image_link", "g:product_type", "brand", "g:mpn", "g:gtin",
                                           "g:shipping_weight", "g:custom_label_0", "g:custom_label_1",
                                           "g:custom_label_2", "g:custom_label_3", "g:custom_label_4",
                                           "g:additional_image_link", "description"])
        r = rezultate[feed]
        print(f"{feed:12s} noi={r['noi']} mulwi={r['mulwi']} comune={r['comune']} "
              f"doar_noi={len(r['doar_noi'])} doar_mulwi={len(r['doar_mulwi'])} "
              f"campuri_cu_diferente={ {k: len(v) for k, v in (r.get('dif_camp') or {}).items()} }")
    cale = scrie_raport(rezultate, moment)
    print(f"\nRaport scris în {cale}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
