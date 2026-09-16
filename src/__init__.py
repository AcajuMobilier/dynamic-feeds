"""Generator de feeduri pentru marketplace-uri, pornind de la Shopify Admin API.

Straturi:
    config      – citirea fișierelor de configurare
    extragere   – Shopify Admin API (GraphQL) -> produse brute
    normalizare – descriere, parametri, dimensiuni, titluri (independent de canal)
    favi        – formatare XML în specificația Heureka cerută de Favi
    validare    – verificări pe feedul rezultat + frâna de siguranță
    raport      – raportul CSV cu produsele problematice
"""
