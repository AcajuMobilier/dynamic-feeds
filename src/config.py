"""Citirea fișierelor de configurare din folderul config/."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

RADACINA = Path(__file__).resolve().parent.parent
FOLDER_CONFIG = RADACINA / "config"


def _citeste(nume: str) -> dict:
    cale = FOLDER_CONFIG / nume
    if not cale.exists():
        raise SystemExit(f"EROARE: lipsește fișierul de configurare {cale}")
    with open(cale, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Configurare:
    """Toate setările, citite o singură dată la pornire."""

    def __init__(self, magazin: str = "ocean"):
        self.magazin_nume = magazin
        self.ocean = _citeste(f"{magazin}.yaml")
        categorii = _citeste("categorii_favi.yaml")
        dimensiuni = _citeste("dimensiuni_favi.yaml")
        parametri = _citeste("parametri.yaml")

        # --- selecție ---
        sel = self.ocean.get("selectie", {})
        self.tag = sel.get("tag", "")
        self.exclude_fara_stoc = bool(sel.get("exclude_fara_stoc", False))

        # --- livrare ---
        liv = self.ocean.get("livrare", {})
        self.zile_in_stoc = int(liv.get("zile_in_stoc", 2))
        self.zile_fara_stoc = int(liv.get("zile_fara_stoc", 30))
        self.livrare_dupa_tag = {
            str(k).lower(): int(v) for k, v in (liv.get("dupa_tag") or {}).items()
        }
        self.curier = liv.get("curier") or ""
        self.preturi_kg = [(float(a), float(b)) for a, b in (liv.get("preturi_kg") or [])]

        # --- producător ---
        prod = self.ocean.get("producator", {})
        self.manufacturer_mod = prod.get("mod", "nimic")
        self.branduri_reale = {str(b).upper() for b in (prod.get("branduri_reale") or [])}

        # --- descriere ---
        desc = self.ocean.get("descriere", {})
        self.taguri_permise = set(desc.get("taguri_permise") or [])
        self.deriva_culoare = bool(desc.get("deriva_culoare", True))

        # --- imagini ---
        img = self.ocean.get("imagini", {})
        self.max_alternative = int(img.get("max_alternative", 20))
        self.latime_minima = int(img.get("latime_minima", 600))
        self.inaltime_minima = int(img.get("inaltime_minima", 600))

        # --- publicare ---
        pub = self.ocean.get("publicare", {})
        self.fisier_feed = pub.get("fisier_feed", "feed.xml")
        self.fisier_raport = pub.get("fisier_raport", "raport.csv")
        self.prag_minim_procent = float(pub.get("prag_minim_procent", 70))

        # --- categorii ---
        self.categorii_dupa_type = categorii.get("dupa_type") or {}
        # căutarea nu ține cont de majuscule („Masa Gradina" = „Masa gradina")
        self.categorii_lc = {
            str(k).strip().lower(): v for k, v in self.categorii_dupa_type.items()
        }
        self.categorii_dupa_titlu = [
            (re.compile(r["potrivire"], re.I), r["categorie"])
            for r in (categorii.get("dupa_titlu") or [])
        ]

        # --- dimensiuni ---
        familii = dimensiuni.get("familii") or {}
        self.dim_familia = {
            cat: familii.get(fam, {}) for cat, fam in (dimensiuni.get("categorii") or {}).items()
        }

        # --- parametri ---
        self.param_rename = parametri.get("redenumiri") or {}
        self.param_skip = set(parametri.get("ignorate") or [])
        self.chei_cm = set(parametri.get("unitate_cm") or [])
        self.chei_kg = set(parametri.get("unitate_kg") or [])

    # ------------------------------------------------------------------
    def pret_livrare_pentru(self, greutate_kg: float) -> float:
        """Primul prag >= greutate dă prețul (grila din config)."""
        for limita, pret in self.preturi_kg:
            if greutate_kg <= limita:
                return pret
        return self.preturi_kg[-1][1] if self.preturi_kg else 0.0


def credentiale() -> tuple[str, str, str, str]:
    """(store, token, client_id, client_secret).

    Local, fișierul .env are prioritate: e fișierul pe care îl editezi, deci
    o variabilă rămasă dintr-o sesiune veche de terminal nu trebuie să îl
    umbrească în tăcere. Pe GitHub Actions nu există .env, iar valorile vin
    din Secrets, prin variabile de mediu.
    """
    cale = RADACINA / ".env"
    if cale.exists():
        for linie in cale.read_text(encoding="utf-8-sig").splitlines():
            linie = linie.strip()
            if not linie or linie.startswith("#") or "=" not in linie:
                continue
            cheie, valoare = linie.split("=", 1)
            valoare = valoare.strip().strip('"').strip("'")
            if valoare:
                os.environ[cheie.strip()] = valoare
    return (
        os.environ.get("SHOPIFY_STORE", "").strip(),
        os.environ.get("SHOPIFY_TOKEN", "").strip(),
        os.environ.get("SHOPIFY_CLIENT_ID", "").strip(),
        os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip(),
    )
