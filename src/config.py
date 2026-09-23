"""Citirea fișierelor de configurare din folderul config/.

Structura:
    config/magazine.yaml        – magazinele Shopify (numele variabilelor cu credențiale, livrare)
    config/publicare.yaml       – adresa de bază a feedurilor publicate, pragul frânei
    config/feeduri/<nume>.yaml  – un fișier per feed: magazin, format, selecție, politică de ID
    config/categorii_favi.yaml, dimensiuni_favi.yaml, parametri.yaml – comune tuturor feedurilor Favi
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

RADACINA = Path(__file__).resolve().parent.parent
FOLDER_CONFIG = RADACINA / "config"
FOLDER_FEEDURI = FOLDER_CONFIG / "feeduri"

FORMATE = {"favi", "google", "rtb", "dsa"}
POLITICI_ID = {"varianta", "produs"}


def _citeste(cale: Path) -> dict:
    if not cale.exists():
        raise SystemExit(f"EROARE: lipsește fișierul de configurare {cale}")
    with open(cale, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def feeduri_disponibile() -> list[str]:
    """Numele tuturor feedurilor definite în config/feeduri/, în ordine alfabetică."""
    return sorted(p.stem for p in FOLDER_FEEDURI.glob("*.yaml"))


class Magazin:
    """Un magazin Shopify: de unde vin credențialele și regulile lui de livrare."""

    def __init__(self, cheie: str, date: dict):
        self.cheie = cheie
        self.nume = date.get("nume", cheie)
        # adresa produselor, construită din handle (așa fac feedurile Mulwi,
        # inclusiv pentru produsele nepublicate pe Online Store)
        self.url_produse = date.get("url_produse") or f"https://{self.nume}/products/"
        self.variabila_store = date.get("variabila_store", "SHOPIFY_STORE")
        self.variabila_token = date.get("variabila_token", "SHOPIFY_TOKEN")
        liv = date.get("livrare") or {}
        self.zile_in_stoc = int(liv.get("zile_in_stoc", 2))
        self.zile_fara_stoc = int(liv.get("zile_fara_stoc", 30))
        self.livrare_dupa_tag = {
            str(k).lower(): int(v) for k, v in (liv.get("dupa_tag") or {}).items()
        }
        self.curier = liv.get("curier") or ""
        self.preturi_kg = [(float(a), float(b)) for a, b in (liv.get("preturi_kg") or [])]

    def credentiale(self) -> tuple[str, str]:
        incarca_env()
        return (os.environ.get(self.variabila_store, "").strip(),
                os.environ.get(self.variabila_token, "").strip())

    def pret_livrare_pentru(self, greutate_kg: float) -> float:
        """Primul prag >= greutate dă prețul (grila din config)."""
        for limita, pret in self.preturi_kg:
            if greutate_kg <= limita:
                return pret
        return self.preturi_kg[-1][1] if self.preturi_kg else 0.0


def magazine() -> dict[str, Magazin]:
    return {k: Magazin(k, v or {}) for k, v in _citeste(FOLDER_CONFIG / "magazine.yaml").items()}


class Configurare:
    """Toate setările unui feed, citite o singură dată la pornire.

    Expune și setările magazinului și pe cele comune (categorii, dimensiuni,
    parametri), ca motorul de formatare să primească un singur obiect.
    """

    def __init__(self, nume_feed: str = "oceanfavi"):
        self.nume_feed = nume_feed
        feed = _citeste(FOLDER_FEEDURI / f"{nume_feed}.yaml")
        publicare = _citeste(FOLDER_CONFIG / "publicare.yaml")
        toate_magazinele = magazine()

        cheie_magazin = feed.get("magazin")
        if cheie_magazin not in toate_magazinele:
            raise SystemExit(f"EROARE: feedul {nume_feed} cere magazinul {cheie_magazin!r}, "
                             f"care nu e definit în config/magazine.yaml")
        self.magazin: Magazin = toate_magazinele[cheie_magazin]

        self.format = feed.get("format", "favi")
        if self.format not in FORMATE:
            raise SystemExit(f"EROARE: feedul {nume_feed} are formatul necunoscut {self.format!r}")
        self.fisier = feed.get("fisier") or f"{nume_feed}.xml"
        self.politica_id = feed.get("id", "varianta")
        if self.politica_id not in POLITICI_ID:
            raise SystemExit(f"EROARE: feedul {nume_feed} are politica de ID necunoscută "
                             f"{self.politica_id!r} (acceptate: varianta, produs)")

        # --- selecție ---
        sel = feed.get("selectie") or {}
        self.tag = (sel.get("tag") or "").strip()
        self.fara_taguri = {str(t).strip().lower() for t in (sel.get("fara_taguri") or [])}
        self.doar_publicate = bool(sel.get("doar_publicate", self.format == "favi"))
        self.exclude_fara_stoc = bool(sel.get("exclude_fara_stoc", False))

        # --- publicare / frână ---
        self.url_baza = (publicare.get("url_baza") or "").rstrip("/") + "/"
        self.url_live = self.url_baza + self.fisier
        frana = feed.get("frana") or {}
        self.prag_minim_procent = float(
            frana.get("prag_minim_procent", publicare.get("prag_minim_procent", 70)))

        # --- livrare (de la magazin) ---
        m = self.magazin
        self.zile_in_stoc = m.zile_in_stoc
        self.zile_fara_stoc = m.zile_fara_stoc
        self.livrare_dupa_tag = m.livrare_dupa_tag
        self.curier = m.curier
        self.preturi_kg = m.preturi_kg

        # --- setările motorului Favi ---
        favi = feed.get("favi") or {}
        prod = favi.get("producator") or {}
        self.manufacturer_mod = prod.get("mod", "nimic")
        self.branduri_reale = {str(b).upper() for b in (prod.get("branduri_reale") or [])}
        desc = favi.get("descriere") or {}
        self.taguri_permise = set(desc.get("taguri_permise")
                                  or ["p", "b", "strong", "i", "em", "br", "ul", "li", "ol"])
        self.deriva_culoare = bool(desc.get("deriva_culoare", True))
        img = favi.get("imagini") or {}
        self.max_alternative = int(img.get("max_alternative", 20))
        self.latime_minima = int(img.get("latime_minima", 600))
        self.inaltime_minima = int(img.get("inaltime_minima", 600))

        # --- câmpurile feedurilor RSS (Google, Facebook, RTB), în ordinea din referință ---
        self.campuri = list(feed.get("campuri") or [])
        self.extra = feed.get("extra") or {}

        # --- comune: categorii, dimensiuni, parametri ---
        categorii = _citeste(FOLDER_CONFIG / "categorii_favi.yaml")
        dimensiuni = _citeste(FOLDER_CONFIG / "dimensiuni_favi.yaml")
        parametri = _citeste(FOLDER_CONFIG / "parametri.yaml")
        self.categorii_dupa_type = categorii.get("dupa_type") or {}
        # căutarea nu ține cont de majuscule („Masa Gradina" = „Masa gradina")
        self.categorii_lc = {
            str(k).strip().lower(): v for k, v in self.categorii_dupa_type.items()
        }
        self.categorii_dupa_titlu = [
            (re.compile(r["potrivire"], re.I), r["categorie"])
            for r in (categorii.get("dupa_titlu") or [])
        ]
        familii = dimensiuni.get("familii") or {}
        self.dim_familia = {
            cat: familii.get(fam, {}) for cat, fam in (dimensiuni.get("categorii") or {}).items()
        }
        self.param_rename = parametri.get("redenumiri") or {}
        self.param_skip = set(parametri.get("ignorate") or [])
        self.chei_cm = set(parametri.get("unitate_cm") or [])
        self.chei_kg = set(parametri.get("unitate_kg") or [])

    def pret_livrare_pentru(self, greutate_kg: float) -> float:
        return self.magazin.pret_livrare_pentru(greutate_kg)


def incarca_env() -> None:
    """Încarcă .env în variabilele de mediu.

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


def credentiale() -> tuple[str, str, str, str]:
    """Compatibilitate cu scripturile vechi: credențialele magazinului implicit."""
    incarca_env()
    return (
        os.environ.get("SHOPIFY_STORE", "").strip(),
        os.environ.get("SHOPIFY_TOKEN", "").strip(),
        os.environ.get("SHOPIFY_CLIENT_ID", "").strip(),
        os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip(),
    )
