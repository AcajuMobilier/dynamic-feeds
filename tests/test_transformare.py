# -*- coding: utf-8 -*-
"""Teste pe funcțiile de transformare portate din generatorul de referință.

Rulare:  python -m pytest tests -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import favi, validare                                    # noqa: E402
from src.config import Configurare                                # noqa: E402
from src.normalizare import (                                     # noqa: E402
    ajusteaza_pentru_favi,
    categoria_pentru,
    completeaza_dimensiuni_din_titlu,
    construieste_descriere,
    curata_titlu,
    ean_valid,
    format_pret,
    sufix_varianta,
)
from src.raport import Raport                                     # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return Configurare("ocean")


# ------------------------------------------------------------------ titluri
def test_titlul_pierde_cuvantul_promo():
    assert curata_titlu("Scaun PROMO  rosu,  45x51x90 cm") == "Scaun rosu, 45x51x90 cm"


def test_spatiile_din_titlu_se_normalizeaza():
    assert curata_titlu("Masa\n\tlemn   nuc") == "Masa lemn nuc"


@pytest.mark.parametrize("sku,asteptat", [
    ("ROSARIO-STG", " (varianta stânga)"),
    ("ROSARIO-DR", " (varianta dreapta)"),
    ("COLT-DL", " (varianta stânga)"),
    ("COLT-DP", " (varianta dreapta)"),
])
def test_sufixul_de_varianta_dupa_sku(sku, asteptat):
    assert sufix_varianta(sku) == asteptat


def test_sku_necunoscut_devine_sufix_literal():
    assert sufix_varianta("ABC123") == " (ABC123)"


# ------------------------------------------------------------------ preț și EAN
@pytest.mark.parametrize("intrare,asteptat", [
    (361, "361"), ("361.00", "361"), (361.5, "361.50"), ("1299.90", "1299.90"),
])
def test_formatul_pretului(intrare, asteptat):
    assert format_pret(intrare) == asteptat


def test_ean_valid_trece_cifra_de_control():
    assert ean_valid("5901738171916") == "5901738171916"


@pytest.mark.parametrize("gresit", ["5901738171917", "12345", "", None, "abc", "0"])
def test_ean_invalid_este_respins(gresit):
    assert ean_valid(gresit) is None


# ------------------------------------------------------------------ parametri
TABEL = """
<table><tbody>
<tr><td>Latime</td><td>76</td></tr>
<tr><td>Inaltime</td><td>44 cm</td></tr>
<tr><td>Greutate</td><td>20</td></tr>
<tr><td>Culoare</td><td>N/A</td></tr>
<tr><td>Categorie</td><td>Masute</td></tr>
<tr><td>Material</td><td>PAL</td></tr>
<tr><td>Material</td><td>MDF</td></tr>
</tbody></table>
<h2>Descriere</h2>
<p>Text cu <a href="https://ocean.ro/x">link</a> și mail@ocean.ro.</p>
<div><span>Text în tag nepermis</span></div>
"""


def test_parametrii_se_extrag_si_se_normalizeaza(cfg):
    _, parametri = construieste_descriere(TABEL, cfg)
    d = dict(parametri)
    assert d["Lățime"] == "76 cm"        # diacritice + unitate adăugată
    assert d["Înălțime"] == "44 cm"      # unitate deja prezentă, nu se dublează
    assert d["Greutate"] == "20 kg"
    assert "Culoare" not in d            # N/A aruncat
    assert "Categorie" not in d          # rând de navigație, nu parametru
    assert d["Material"] == "PAL"        # primul câștigă, fără duplicate
    assert [k for k, _ in parametri].count("Material") == 1


def test_descrierea_pastreaza_doar_tagurile_permise(cfg):
    descriere, _ = construieste_descriere(TABEL, cfg)
    assert "<table" not in descriere
    assert "<h2" not in descriere
    assert "<strong>Descriere</strong>" in descriere   # h2 devine paragraf bold
    assert "<div" not in descriere and "<span" not in descriere
    assert "<a " not in descriere
    assert "https://" not in descriere
    assert "@ocean.ro" not in descriere


def test_descrierea_goala_nu_crapa(cfg):
    descriere, parametri = construieste_descriere("", cfg)
    assert descriere == "" and parametri == []


# ------------------------------------------------------------------ dimensiuni
def test_dimensiunile_din_titlu_completeaza_ce_lipseste(cfg):
    p = completeaza_dimensiuni_din_titlu([], "Masuta LEVKE, 76x76x44 cm", "Living > Măsuțe")
    assert dict(p) == {"Lungime": "76 cm", "Adâncime": "76 cm", "Înălțime": "44 cm"}


def test_dimensiunile_din_tabel_au_prioritate_fata_de_titlu(cfg):
    p = completeaza_dimensiuni_din_titlu([("Lungime", "80 cm")], "Masa, 76x76x44 cm", "Living > Măsuțe")
    d = dict(p)
    assert d["Lungime"] == "80 cm"
    assert d["Înălțime"] == "44 cm"


def test_perechea_din_titlu_devine_dimensiunea_saltelei_la_paturi(cfg):
    p = completeaza_dimensiuni_din_titlu([], "Pat tapitat ARIA 120x200 cm", "Dormitor > Paturi")
    assert dict(p)["Pentru saltea cu dimensiunea"] == "120x200 cm"


def test_perechea_din_titlu_devine_dimensiune_la_covoare(cfg):
    p = completeaza_dimensiuni_din_titlu([], "Covor shaggy 80x150 cm", "Textile > Covoare")
    assert dict(p)["Dimensiuni"] == "80x150 cm"


def test_la_scaune_lungimea_devine_latime(cfg):
    p = ajusteaza_pentru_favi([("Lungime", "45 cm"), ("Înălțime", "90 cm")],
                              "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie", cfg)
    d = dict(p)
    assert d["Lățime"] == "45 cm" and "Lungime" not in d


def test_la_mese_adancimea_devine_latime(cfg):
    p = ajusteaza_pentru_favi([("Lungime", "120 cm"), ("Adâncime", "80 cm")],
                              "Bucătărie > Mobilă de bucătărie > Mese de bucătărie", cfg)
    d = dict(p)
    assert d["Lungime"] == "120 cm" and d["Lățime"] == "80 cm"


def test_la_paturi_dimensiunile_se_rotesc(cfg):
    p = ajusteaza_pentru_favi([("Lungime", "160 cm"), ("Adâncime", "200 cm")],
                              "Dormitor > Paturi", cfg)
    d = dict(p)
    assert d["Lățime"] == "160 cm" and d["Lungime"] == "200 cm"


def test_redenumirea_nu_suprascrie_o_cheie_existenta(cfg):
    p = ajusteaza_pentru_favi([("Lungime", "45 cm"), ("Lățime", "50 cm")],
                              "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie", cfg)
    d = dict(p)
    assert d["Lățime"] == "50 cm" and d["Lungime"] == "45 cm"


def test_dimensiunea_saltelei_se_sparge_in_doi_parametri(cfg):
    p = ajusteaza_pentru_favi([("Pentru saltea cu dimensiunea", "160x200 cm")],
                              "Dormitor > Paturi", cfg)
    d = dict(p)
    assert d["Lățime saltea"] == "160 cm" and d["Lungime saltea"] == "200 cm"


def test_dimensiunile_covorului_se_sparg_in_latime_si_lungime(cfg):
    p = ajusteaza_pentru_favi([("Dimensiuni", "80x150 cm")], "Textile > Covoare", cfg)
    d = dict(p)
    assert d["Lățime"] == "80 cm" and d["Lungime"] == "150 cm"


def test_culoarea_se_deriva_din_culoarea_sezutului(cfg):
    p = ajusteaza_pentru_favi([("Culoare șezut", "verde")],
                              "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie", cfg)
    assert dict(p)["Culoare"] == "verde"


def test_culoarea_existenta_nu_se_suprascrie(cfg):
    p = ajusteaza_pentru_favi([("Culoare", "rosu"), ("Culoare șezut", "verde")],
                              "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie", cfg)
    assert dict(p)["Culoare"] == "rosu"


# ------------------------------------------------------------------ categorii
def test_categoria_vine_din_type(cfg):
    assert categoria_pentru("Scaune", "Scaun rosu", cfg) == \
        "Bucătărie > Mobilă de bucătărie > Scaune de bucătărie"


def test_maparea_categoriei_ignora_majusculele(cfg):
    assert categoria_pentru("masa gradina", "Masa", cfg) == "Grădină > Mese de grădină"


def test_titlul_are_prioritate_fata_de_type(cfg):
    assert categoria_pentru("Scaune", "Coltar extensibil ROSARIO", cfg) == "Living > Canapele"


def test_type_nemapat_nu_da_categorie(cfg):
    assert categoria_pentru("Ceva inexistent", "Produs", cfg) is None


# ------------------------------------------------------------------ livrare
@pytest.mark.parametrize("kg,pret", [(0.05, 0), (2.9, 35), (3, 35), (4, 39),
                                     (9.9, 49), (30, 119), (250, 299), (5000, 399)])
def test_pretul_de_livrare_pe_praguri(cfg, kg, pret):
    assert cfg.pret_livrare_pentru(kg) == pret


# ------------------------------------------------------------------ feed complet
def produs_de_test(**override):
    p = dict(
        id="7282346098860", handle="masuta-levke", titlu="Masuta LEVKE, 76x76x44 cm",
        descriere_html=TABEL, vendor="KONDELA", tip="Masuta", taguri=["OCEANFAVI"],
        status="ACTIVE", url="https://www.ocean.ro/products/masuta-levke",
        stoc_total=5,
        imagini=[{"url": "https://cdn.shopify.com/a.jpg", "latime": 1000, "inaltime": 1000}],
        variante=[dict(id="41576199389356", titlu="Default", sku="ABC", barcode="5901738171916",
                       pret="361.00", pret_comparat=None, pozitie=1, stoc=5, greutate_kg=20.0)],
        variante_incomplete=False,
    )
    p.update(override)
    return p


def feed_din(produse, cfg):
    raport = Raport()
    pregatite = favi.pregateste_produse(produse, cfg, raport)
    itemuri = favi.construieste_itemuri(pregatite, cfg, raport)
    return favi.construieste_xml(itemuri), raport


def test_feedul_minimal_e_valid_si_complet(cfg):
    xml, raport = feed_din([produs_de_test()], cfg)
    rezultat = validare.valideaza(xml, cfg)
    assert rezultat.valid, rezultat.erori
    assert rezultat.numar_produse == 1
    assert "<ITEM_ID>41576199389356</ITEM_ID>" in xml
    assert "<ITEMGROUP_ID>" not in xml               # o singură variantă
    assert "<EAN>5901738171916</EAN>" in xml
    assert "<DELIVERY_ID>GLS</DELIVERY_ID>" in xml
    assert "<DELIVERY_PRICE>79</DELIVERY_PRICE>" in xml   # 20 kg -> 79 lei
    assert "<DELIVERY_DATE>2</DELIVERY_DATE>" in xml
    assert "<MANUFACTURER>" not in xml               # mod „nimic"
    assert "<![CDATA[" in xml


def test_produsul_cu_doua_variante_primeste_itemgroup_si_variant_in_url(cfg):
    p = produs_de_test(variante=[
        dict(id="111", titlu="stanga", sku="ROSARIO-STG", barcode="", pret="3600",
             pret_comparat=None, pozitie=1, stoc=2, greutate_kg=130.0),
        dict(id="222", titlu="dreapta", sku="ROSARIO-DR", barcode="", pret="3600",
             pret_comparat=None, pozitie=2, stoc=2, greutate_kg=130.0),
    ])
    xml, _ = feed_din([p], cfg)
    assert xml.count("<ITEMGROUP_ID>7282346098860</ITEMGROUP_ID>") == 2
    assert "?variant=111" in xml and "?variant=222" in xml
    assert "(varianta stânga)" in xml and "(varianta dreapta)" in xml
    assert validare.valideaza(xml, cfg).valid


def test_produsul_nepublicat_este_exclus_si_raportat(cfg):
    xml, raport = feed_din([produs_de_test(url=None)], cfg)
    assert "<SHOPITEM>" not in xml
    motive = dict(raport.numarare())
    assert motive["fara_url"] == 1
    assert any("nepublicat pe Online Store" in l[4] for l in raport.linii)


def test_produsul_fara_categorie_este_exclus_si_raportat(cfg):
    xml, raport = feed_din([produs_de_test(tip="Inexistent", titlu="Obiect oarecare")], cfg)
    assert "<SHOPITEM>" not in xml
    assert dict(raport.numarare())["fara_categorie"] == 1


def test_produsul_fara_stoc_intra_cu_termen_lung(cfg):
    xml, raport = feed_din([produs_de_test(stoc_total=0)], cfg)
    assert "<DELIVERY_DATE>30</DELIVERY_DATE>" in xml
    assert dict(raport.numarare())["fara_stoc_in_feed"] == 1


def test_tagul_de_livrare_are_prioritate_fata_de_stoc(cfg):
    xml, _ = feed_din([produs_de_test(taguri=["OCEANFAVI", "livrare14zile"], stoc_total=9)], cfg)
    assert "<DELIVERY_DATE>14</DELIVERY_DATE>" in xml


def test_imaginile_alternative_sunt_limitate_la_20(cfg):
    imagini = [{"url": f"https://cdn.shopify.com/{i}.jpg", "latime": 800, "inaltime": 800}
               for i in range(30)]
    xml, _ = feed_din([produs_de_test(imagini=imagini)], cfg)
    assert xml.count("<IMGURL_ALTERNATIVE>") == 20
    assert xml.count("<IMGURL>") == 1
    assert validare.valideaza(xml, cfg).valid


def test_caracterele_speciale_se_escapeaza(cfg):
    xml, _ = feed_din([produs_de_test(titlu="Masa <lemn> & fier, 76x76x44 cm")], cfg)
    assert "&amp;" in xml and "&lt;lemn&gt;" in xml
    assert validare.valideaza(xml, cfg).valid


def test_greutatea_lipsa_din_tabel_vine_de_la_varianta(cfg):
    p = produs_de_test(
        descriere_html="<table><tr><td>Latime</td><td>50</td></tr></table><p>Descriere.</p>")
    xml, _ = feed_din([p], cfg)
    assert "<VAL>20 kg</VAL>" in xml


# ------------------------------------------------------------------ produse stricate
def test_un_produs_fara_descriere_este_exclus_nu_blocheaza_feedul(cfg):
    """Descrierea e obligatorie la Favi. Un produs fără ea trebuie scos din
    feed, nu lăsat să pice validarea și să oprească publicarea pentru toate."""
    bun = produs_de_test()
    stricat = produs_de_test(id="999", descriere_html="",
                             url="https://www.ocean.ro/products/altul",
                             variante=[dict(id="888", titlu="D", sku="X", barcode="",
                                            pret="99", pret_comparat=None, pozitie=1,
                                            stoc=1, greutate_kg=2.0)])
    xml, raport = feed_din([bun, stricat], cfg)
    rezultat = validare.valideaza(xml, cfg)
    assert rezultat.valid, rezultat.erori
    assert rezultat.numar_produse == 1
    assert any("descrierea" in l[4] for l in raport.linii)


def test_un_pret_zero_este_exclus_nu_publicat_ca_gratuit(cfg):
    p = produs_de_test(variante=[dict(id="41576199389356", titlu="D", sku="A", barcode="",
                                      pret="0.00", pret_comparat=None, pozitie=1,
                                      stoc=5, greutate_kg=20.0)])
    xml, raport = feed_din([p], cfg)
    assert "<SHOPITEM>" not in xml
    assert any("preț mai mare ca zero" in l[4] for l in raport.linii)


def test_caracterele_de_control_nu_rup_feedul(cfg):
    """Shopify poate livra caractere pe care XML 1.0 nu le acceptă; dacă ajung
    în fișier, Favi nu îl mai poate citi deloc."""
    p = produs_de_test(descriere_html="<p>Text\x0bcu\x00control\x07aici</p>")
    xml, _ = feed_din([p], cfg)
    rezultat = validare.valideaza(xml, cfg)
    assert rezultat.valid, rezultat.erori
    assert rezultat.numar_produse == 1
    assert "\x0b" not in xml and "\x00" not in xml


def test_produsul_fara_variante_este_raportat(cfg):
    xml, raport = feed_din([produs_de_test(variante=[])], cfg)
    assert "<SHOPITEM>" not in xml
    assert any("nicio variantă" in l[4] for l in raport.linii)


def test_o_singura_varianta_ramasa_nu_primeste_itemgroup(cfg):
    """Dacă una din două variante pică, cea rămasă e un produs simplu: fără
    ITEMGROUP_ID și fără ?variant= în adresă."""
    p = produs_de_test(variante=[
        dict(id="111", titlu="bun", sku="ROSARIO-STG", barcode="", pret="3600",
             pret_comparat=None, pozitie=1, stoc=2, greutate_kg=130.0),
        dict(id="222", titlu="fara pret", sku="ROSARIO-DR", barcode="", pret=None,
             pret_comparat=None, pozitie=2, stoc=2, greutate_kg=130.0),
    ])
    xml, _ = feed_din([p], cfg)
    assert xml.count("<SHOPITEM>") == 1
    assert "<ITEMGROUP_ID>" not in xml
    assert "?variant=" not in xml


def test_adresele_cu_spatii_sau_diacritice_sunt_codificate(cfg):
    p = produs_de_test(imagini=[{"url": "https://cdn.shopify.com/Masuță lemn.jpg",
                                 "latime": 900, "inaltime": 900}])
    xml, _ = feed_din([p], cfg)
    assert "%20" in xml and "%C4%83" in xml
    assert " lemn.jpg" not in xml


def test_ean_cu_zero_in_fata_nu_se_pierde():
    assert ean_valid("036000291452") == "036000291452"


def test_sufixul_gol_nu_lasa_paranteze_goale():
    assert sufix_varianta("", "Default Title") == ""
    assert sufix_varianta("", "Verde") == " (Verde)"


def test_atributele_html_sunt_scoase_din_descriere(cfg):
    descriere, _ = construieste_descriere(
        '<p style="color:red" title="scrie la mail@ocean.ro">Text</p>', cfg)
    assert descriere == "<p>Text</p>"


# ------------------------------------------------------------------ validare
def test_validarea_prinde_iduri_duplicate(cfg):
    p1 = produs_de_test()
    p2 = produs_de_test(id="999", url="https://www.ocean.ro/products/alt")
    xml, _ = feed_din([p1, p2], cfg)
    rezultat = validare.valideaza(xml, cfg)
    assert not rezultat.valid
    assert any("ITEM_ID duplicate" in e for e in rezultat.erori)


def test_validarea_prinde_urluri_duplicate(cfg):
    p1 = produs_de_test()
    p2 = produs_de_test(id="999", variante=[dict(
        id="888", titlu="D", sku="X", barcode="", pret="10", pret_comparat=None,
        pozitie=1, stoc=1, greutate_kg=1.0)])
    xml, _ = feed_din([p1, p2], cfg)
    rezultat = validare.valideaza(xml, cfg)
    assert not rezultat.valid
    assert any("URL-uri duplicate" in e for e in rezultat.erori)


def test_validarea_prinde_url_in_descriere(cfg):
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n<SHOP>\n  <SHOPITEM>\n'
           '    <ITEM_ID>1</ITEM_ID>\n    <PRODUCTNAME>X</PRODUCTNAME>\n'
           '    <DESCRIPTION><![CDATA[<p>vezi https://ocean.ro/x</p>]]></DESCRIPTION>\n'
           '    <CATEGORYTEXT>Living > Măsuțe</CATEGORYTEXT>\n    <PRICE_VAT>10</PRICE_VAT>\n'
           '    <URL>https://www.ocean.ro/a</URL>\n    <IMGURL>https://cdn/a.jpg</IMGURL>\n'
           '    <DELIVERY_DATE>2</DELIVERY_DATE>\n  </SHOPITEM>\n</SHOP>\n')
    rezultat = validare.valideaza(xml, cfg)
    assert not rezultat.valid
    assert any("URL" in e and "descrieri" in e for e in rezultat.erori)


def test_feedul_gol_nu_trece_validarea(cfg):
    rezultat = validare.valideaza('<?xml version="1.0" encoding="utf-8"?>\n<SHOP>\n</SHOP>\n', cfg)
    assert not rezultat.valid


# ------------------------------------------------------------------ frâna
def test_frana_opreste_scaderea_brusca():
    poate, mesaj = validare.verifica_frana(1000, 2363, 70)
    assert not poate and "OPRIT" in mesaj


def test_frana_lasa_sa_treaca_o_scadere_mica():
    poate, _ = validare.verifica_frana(2227, 2363, 70)
    assert poate


def test_frana_se_sare_la_prima_rulare():
    poate, mesaj = validare.verifica_frana(2227, None, 70)
    assert poate and "prima rulare" in mesaj


# ------------------------------------------------------------------ structura descrierii
# Rendererul Favi afișează tagurile ca text când conținutul inline stă direct
# la rădăcina descrierii. Fixture-ul e descrierea reală a produsului
# „Masa extensibila WENANTY" (ITEM_ID 49674480091466), unde bug-ul a fost văzut.
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _blocuri_radacina(descriere):
    from bs4 import BeautifulSoup, NavigableString
    soup = BeautifulSoup(descriere, "html.parser")
    return [("text" if isinstance(n, NavigableString) else n.name)
            for n in soup.contents if not (isinstance(n, NavigableString) and not n.strip())]


def test_wenanty_descrierea_incepe_cu_titlul_in_paragraf(cfg):
    brut = (FIXTURES / "descriere_wenanty.html").read_text(encoding="utf-8")
    descriere, parametri = construieste_descriere(brut, cfg)
    assert descriere.startswith(
        "<p><strong>MASA EXTENSIBILA WENANTY, STEJAR, 160/240X100X77 CM</strong></p>")
    assert "<strong></strong>" not in descriere
    assert set(_blocuri_radacina(descriere)) <= {"p", "ul", "ol"}
    assert len(parametri) == 11          # tabelul se citește în continuare


@pytest.mark.parametrize("brut", [
    "<p>A<strong></strong>B</p>",
    "<p>A<strong> </strong>B</p>",
    "<p>A<em>\xa0</em>B</p>",
    "<p>A<b><strong> <i></i> </strong></b>B</p>",
])
def test_tagurile_inline_goale_dispar(cfg, brut):
    descriere, _ = construieste_descriere(brut, cfg)
    for tag in ("strong", "b", "em", "i"):
        assert f"<{tag}>" not in descriere


def test_spatiul_din_tagul_gol_ramane_intre_cuvinte(cfg):
    descriere, _ = construieste_descriere("<p>unu<strong> </strong>doi</p>", cfg)
    assert descriere == "<p>unu doi</p>"


def test_continutul_inline_de_la_radacina_intra_in_paragraf(cfg):
    descriere, _ = construieste_descriere(
        "<div><strong>Titlu</strong> text</div><ul><li>a</li></ul>simplu<br/>rand", cfg)
    assert descriere == ("<p><strong>Titlu</strong> text</p>\n<ul><li>a</li></ul>\n"
                         "<p>simplu<br/>rand</p>")


def test_br_de_la_margini_si_paragrafele_goale_dispar(cfg):
    descriere, _ = construieste_descriere(
        "<br/><br/><div><strong></strong><br></div><p> </p><p><br/></p>"
        "<p>Text</p><br/><br/>", cfg)
    assert descriere == "<p>Text</p>"


def test_li_ratacit_la_radacina_primeste_lista(cfg):
    descriere, _ = construieste_descriere("<li>a</li><li>b</li><p>c</p>", cfg)
    assert descriere == "<ul><li>a</li><li>b</li></ul>\n<p>c</p>"
    assert set(_blocuri_radacina(descriere)) <= {"p", "ul", "ol"}


def test_blocul_style_nu_ajunge_text_in_descriere(cfg):
    """Descrierile lipite din Excel aduc un <style> cu CSS; desfăcut, CSS-ul
    ar apărea ca text pe Favi."""
    brut = ('<p>Nota</p>\n<style type="text/css"><!--\ntd {border: 1px solid #ccc;}\n--></style>'
            '<p><br></p> <p><strong>Atenție</strong></p><p>x<script>alert(1)</script></p>')
    descriere, _ = construieste_descriere(brut, cfg)
    assert "td {" not in descriere and "border" not in descriere
    assert "alert" not in descriere
    assert descriere == "<p>Nota</p>\n<p><strong>Atenție</strong></p>\n<p>x</p>"
