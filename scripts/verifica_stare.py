#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Face rularea roșie dacă vreun feed a picat, DUPĂ ce publicarea a avut loc.

Ordinea contează: feedurile bune se publică oricum, împreună cu versiunile
live păstrate ale celor picate. Abia apoi rularea eșuează vizibil, ca să
primești mail. Citește public/stare.json scris de genereaza.py.

Rulare:  python scripts/verifica_stare.py public/stare.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.consola import pregateste as pregateste_consola  # noqa: E402

pregateste_consola()


def main() -> int:
    cale = Path(sys.argv[1] if len(sys.argv) > 1 else "public/stare.json")
    if not cale.exists():
        print(f"EROARE: lipsește {cale}; generarea nu a scris starea.")
        return 1
    stare = json.loads(cale.read_text(encoding="utf-8"))
    picate = [f for f in stare.get("feeduri", []) if not f.get("ok")]
    for f in stare.get("feeduri", []):
        semn = "OK   " if f.get("ok") else ("VECHI" if f.get("pastrat_live") else "LIPSA")
        print(f"  {semn} {f['feed']:14s} {f.get('mesaj', '')}")
    if not picate:
        print("Toate feedurile au fost generate și publicate.")
        return 0
    print(f"\n{len(picate)} feed(uri) au picat: " + ", ".join(f["feed"] for f in picate))
    print("Feedurile bune s-au publicat; pentru cele picate a rămas versiunea veche.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
