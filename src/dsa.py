"""Feedul CSV pentru Google Ads DSA, replică a feedului Mulwi custom_csv.csv.

Două coloane, „Page URL" și „Custom label", un rând per produs, tot
catalogul activ. Fișierul are BOM UTF-8, toate valorile între ghilimele și
terminații de linie LF, exact ca la Mulwi. Rândurile sunt în ordinea
crescătoare a ID-ului de produs (Mulwi le scrie în trei blocuri fără o regulă
derivabilă; conținutul e același).
"""

from __future__ import annotations

import csv
import io

from . import replica


def genereaza(produse: list[dict], cfg, raport) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(["Page URL", "Custom label"])
    for p in replica.sortate_dupa_id(produse):
        w.writerow([replica.url_produs(p, cfg.magazin.url_produse), p.get("tip") or ""])
    return "﻿" + buf.getvalue()


def numara(text: str) -> int:
    return max(0, text.count("\n") - 1)


def valideaza(text: str, cfg):
    from . import validare
    return validare.valideaza_csv(text, cfg)
