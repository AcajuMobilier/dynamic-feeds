# -*- coding: utf-8 -*-
"""Afișare cu diacritice, indiferent de terminal.

Pe Windows consola folosește implicit o codificare veche (cp1252) în care
„ș" sau „ț" nu există, iar orice print cu diacritice oprește programul.
Apelăm `pregateste()` la pornirea fiecărui script.
"""

from __future__ import annotations

import sys


def pregateste() -> None:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass    # flux redirecționat sau deja UTF-8; nu e nimic de făcut
