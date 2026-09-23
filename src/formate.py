"""Registrul formatelor de feed.

Fiecare modul de format expune același trio de funcții:
    genereaza(produse, cfg, raport) -> str      textul feedului
    valideaza(text, cfg) -> validare.Rezultat   verificările înainte de publicare
    numara(text) -> int                          câte produse are (pentru frână)
"""

from __future__ import annotations

from importlib import import_module

MODULE = {
    "favi": "src.favi",
    "google": "src.google",
    "rtb": "src.rtb",
    "dsa": "src.dsa",
}


def modul(format_feed: str):
    if format_feed not in MODULE:
        raise SystemExit(f"EROARE: format de feed necunoscut: {format_feed!r}")
    return import_module(MODULE[format_feed])
