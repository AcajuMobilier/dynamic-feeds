# -*- coding: utf-8 -*-
"""Feedurile care replică Mulwi trebuie să iasă IDENTIC cu referința.

Fixture-urile din tests/fixtures/mulwi/ sunt item-uri luate ca atare din
feedurile Mulwi descărcate pe 2026-09-23, împreună cu produsul din Shopify
din același moment. Cu etichetele goale păstrate, item-ul generat trebuie să
fie identic octet cu octet; cu ele omise (setarea din producție), identic
mai puțin liniile de etichete goale.

Rulare:  python -m pytest tests -q
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dsa, formate, replica, selectie              # noqa: E402
from src.config import Configurare                            # noqa: E402
from src.raport import Raport                                 # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "mulwi"


def _citeste_exact(cale):
    """Conținutul octet cu octet (fără conversia terminațiilor de linie)."""
    with open(cale, encoding="utf-8", newline="") as f:
        return f.read()

CAZURI = [
    ("oceangoogle", "7281974804652"),
    ("oceanfb", "7281974804652"),
    ("acajugoogle", "4666580697151"),     # in stock, fără compare-at
    ("acajugoogle", "4666618871871"),     # cu compare-at
    ("acajugoogle", "4666610909247"),     # backorder
    ("acajurtb", "4666580697151"),
]


def _item_generat(feed, pid, omite_goale):
    cfg = Configurare(feed)
    cfg.extra["omite_etichete_goale"] = omite_goale
    produs = json.loads((FIX / f"{feed}_{pid}.produs.json").read_text(encoding="utf-8"))
    text = formate.modul(cfg.format).genereaza([produs], cfg, Raport())
    return re.search(r"    <item>.*?</item>", text, re.S).group(0)


def _fara_etichete_goale(item):
    return re.sub(r"^ *<g:custom_label_(\d)>(\s*)</g:custom_label_\1> *\r?\n",
                  lambda m: "" if not m.group(2).strip() else m.group(0), item, flags=re.M)


@pytest.mark.parametrize("feed,pid", CAZURI)
def test_itemul_este_identic_cu_mulwi(feed, pid):
    referinta = _citeste_exact(FIX / f"{feed}_{pid}.item.txt")
    assert _item_generat(feed, pid, omite_goale=False) == referinta


@pytest.mark.parametrize("feed,pid", CAZURI)
def test_cu_etichetele_goale_omise_restul_ramane_identic(feed, pid):
    referinta = _citeste_exact(FIX / f"{feed}_{pid}.item.txt")
    assert _item_generat(feed, pid, omite_goale=True) == _fara_etichete_goale(referinta)


def test_dsa_primele_randuri_sunt_identice():
    cfg = Configurare("acajudsa")
    referinta = _citeste_exact(FIX / "acajudsa_primele.csv")
    produse = [
        {"id": "1", "handle": "canapea-extensibila-gandi-160-stofa-catifelata-mov-lila-monolith-62-cu-tetiere-reglabile-227x102x95-cm", "tip": "Canapele"},
        {"id": "2", "handle": "canapea-extensibila-gandi-160-stofa-catifelata-verde-cloud-39-gama-premium-cu-tetiere-reglabile-227x102x95-cm", "tip": "Canapele"},
    ]
    assert dsa.genereaza(produse, cfg, Raport()) == referinta


# ------------------------------------------------------------------ regulile de bază
def test_pretul_intreg_fara_zecimale_si_fara_separator():
    assert replica.pret_ron("16496.00") == "16496 RON"
    assert replica.pret_ron("264.50") == "264.5 RON"


def test_pretul_redus_vine_din_compare_at():
    assert replica.pret_si_pret_redus({"pret": "486.00", "pret_comparat": "540.00"}) == ("540 RON", "486 RON", True)
    assert replica.pret_si_pret_redus({"pret": "264.00", "pret_comparat": None}) == ("264 RON", "264 RON", False)


def test_greutatea_reproduce_artefactul_de_virgula_mobila():
    assert replica.greutate_kg_text(20.0) == "20 kg"
    assert replica.greutate_kg_text(147.2) == "147.20000000000002 kg"
    assert replica.greutate_kg_text(0.001) == "0.001 kg"
    assert replica.greutate_kg_text(None) == "0 kg"


def test_titlul_se_taie_dur_la_70_de_caractere():
    t = "Canapea extensibila Aldo, STOFA DE LUX catifelata turcoaz - Piano 10, 227x106x92 cm"
    assert replica.titlu_70(t) == t[:70] and replica.titlu_70(t).endswith(", ")


def test_varianta_principala_este_cea_cu_id_minim():
    p = {"variante": [{"id": "49459970048336", "pozitie": 1, "pret": "100"},
                      {"id": "49431462642000", "pozitie": 2, "pret": "200"}]}
    assert replica.varianta_principala(p)["pret"] == "200"
    assert replica.varianta_principala(p, "pozitie")["pret"] == "100"


def test_descrierea_plata_urmeaza_regulile_mulwi():
    html = ('<table>\n<tr>\n<td><strong>Categorie</strong></td>\n<td><a href="x">Scaune</a></td>\n</tr>\n'
            '<tr>\n<td>Lungime</td>\n<td>42 cm</td>\n</tr>\n</table>\n<p> </p>\n<p>0</p>\n'
            '<style><!--\ntd {border:1px}\n--></style>\n<p>A<br>B<br data-mce-fragment="1">C</p>\n'
            '<li>Gata.</li>')
    assert replica.descriere_plata(html) == "Categorie. Scaune. Lungime. 42 cm. 0. A. BC. Gata."


def test_adresa_din_handle_ramane_neencodata():
    assert replica.url_produs({"handle": "set-mic-dejun-roșu"}, "https://acaju.ro/products/") == \
        "https://acaju.ro/products/set-mic-dejun-roșu"


def test_selectia_google_acaju_exclude_oricare_tag_interzis():
    cfg = Configurare("acajugoogle")
    produse = [{"id": "1", "taguri": ["x"], "url": None},
               {"id": "2", "taguri": ["FARA ADD TO CART"], "url": "u"},
               {"id": "3", "taguri": ["resigilate"], "url": "u"},
               {"id": "4", "taguri": ["NON ADDS", "x"], "url": "u"}]
    sel, contor = selectie.selecteaza(produse, cfg)
    assert [p["id"] for p in sel] == ["1"]           # nepublicatul intră, ca la Mulwi
    assert contor["cu_tag_exclus"] == 3
