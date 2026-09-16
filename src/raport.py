"""Raportul de rulare: o linie per produs problematic, motive în română."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

# Explicațiile apar în raport lângă fiecare motiv, ca să fie citibil fără cod.
EXPLICATII = {
    "fara_url": "Produsul nu are pagină publică pe Online Store. Publică-l în Shopify sau scoate-i tagul.",
    "fara_categorie": "Type-ul din Shopify nu e în maparea de categorii. Adaugă-l în config/categorii_favi.yaml.",
    "fara_imagine": "Produsul nu are nicio imagine în Shopify.",
    "fara_parametri": "Descrierea nu conține tabelul de specificații, deci produsul intră fără parametri.",
    "fara_dimensiuni": "Nicio dimensiune, nici în tabel, nici în titlu. Favi nu îl va prinde în filtre.",
    "imagine_sub_600px": "Imaginea principală e sub 600x600 px. Favi poate bloca afișarea.",
    "fara_pret_livrare": "Varianta nu are greutate în Shopify, deci nu pot calcula prețul de livrare.",
    "fara_stoc_in_feed": "Produsul e fără stoc, dar rămâne în feed cu termenul de livrare lung.",
    "exclus_date_lipsa": "Exclus din feed: îi lipsesc date obligatorii.",
    "exclus_stoc_zero": "Exclus din feed: stoc zero, iar configurarea cere excluderea.",
    "variante_incomplete": "Produsul are peste 250 de variante; doar primele 250 au intrat.",
    "eroare_validare": "Feedul nu a trecut validarea. Vezi detaliile.",
}

# Motivele care înseamnă că produsul NU a intrat în feed.
MOTIVE_EXCLUDERE = {"fara_url", "fara_categorie", "fara_imagine",
                    "exclus_date_lipsa", "exclus_stoc_zero"}


class Raport:
    def __init__(self):
        self.linii: list[list[str]] = []

    def adauga(self, motiv: str, id_produs, titlu: str, detalii: str,
               tip_id: str = "produs") -> None:
        """tip_id spune dacă numărul e al produsului sau al variantei.

        Fără el, aceeași problemă apare în raport sub două numere diferite și
        nu se vede că e vorba de același produs.
        """
        self.linii.append([motiv, str(id_produs), tip_id, str(titlu), str(detalii)])

    def __len__(self) -> int:
        return len(self.linii)

    def numarare(self) -> Counter:
        return Counter(l[0] for l in self.linii)

    def scrie_csv(self, cale: Path) -> None:
        cale.parent.mkdir(parents=True, exist_ok=True)
        with open(cale, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["motiv", "explicatie", "id", "id_este", "titlu", "detalii"])
            for motiv, id_produs, tip_id, titlu, detalii in self.linii:
                w.writerow([motiv, EXPLICATII.get(motiv, ""), id_produs, tip_id, titlu, detalii])

    def rezumat_markdown(self) -> str:
        """Tabel pentru rezumatul rulării din GitHub Actions."""
        numarare = self.numarare()
        if not numarare:
            return "Niciun produs problematic.\n"
        randuri = ["| Motiv | Produse | Ce înseamnă |", "| --- | ---: | --- |"]
        for motiv, n in numarare.most_common():
            eticheta = motiv.replace("_", " ")
            if motiv in MOTIVE_EXCLUDERE:
                eticheta += " (exclus)"
            randuri.append(f"| {eticheta} | {n} | {EXPLICATII.get(motiv, '')} |")
        return "\n".join(randuri) + "\n"
