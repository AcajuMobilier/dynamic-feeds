"""Stratul de extragere: Shopify Admin API (GraphQL) -> produse brute.

Nu conține nicio regulă specifică Favi. Întoarce dicționare simple, ca să poată
fi refolosit pentru Biano sau pentru al doilea magazin.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

# Ultima versiune stabilă la 2026-09 (accesibilă până pe 16 iulie 2027).
# Shopify scoate o versiune nouă trimestrial; vezi README, secțiunea „Actualizări".
API_VERSION = "2026-07"

PRODUSE_PER_PAGINA = 250   # maximul permis de Shopify
VARIANTE_PER_PRODUS = 250
# Favi acceptă 1 imagine principală + 20 alternative. Cerem mai multe media,
# pentru că lista include și videouri sau modele 3D, care nu au imagine și ar
# consuma din buget fără să ajungă în feed.
MEDIA_PER_PRODUS = 40

QUERY_PRODUSE = """
query ProduseDupaTag($cursor: String, $q: String!) {
  products(first: %d, after: $cursor, query: $q) {
    pageInfo { hasNextPage endCursor }
    nodes {
      legacyResourceId
      handle
      title
      descriptionHtml
      vendor
      productType
      tags
      status
      onlineStoreUrl
      totalInventory
      media(first: %d, sortKey: POSITION) {
        nodes {
          ... on MediaImage {
            image { url width height }
          }
        }
      }
      variants(first: %d) {
        pageInfo { hasNextPage }
        nodes {
          legacyResourceId
          title
          sku
          barcode
          price
          compareAtPrice
          position
          inventoryQuantity
          inventoryItem { measurement { weight { value unit } } }
        }
      }
    }
  }
}
""" % (PRODUSE_PER_PAGINA, MEDIA_PER_PRODUS, VARIANTE_PER_PRODUS)


class EroareShopify(RuntimeError):
    """Eroare care trebuie să oprească rularea zgomotos, fără feed parțial."""


def normalizeaza_store(valoare: str) -> str:
    """'handle', 'handle.myshopify.com' sau 'https://handle.myshopify.com/' -> 'handle.myshopify.com'."""
    v = valoare.strip().lower().replace("https://", "").replace("http://", "").strip("/")
    if "/" in v:
        v = v.split("/", 1)[0]
    if not v.endswith(".myshopify.com"):
        v += ".myshopify.com"
    return v


def _post(url: str, date: bytes, antete: dict, incercari: int = 5):
    """POST cu backoff la erori de rețea și 5xx. Întoarce (status, antete, corp)."""
    ultima = None
    for i in range(incercari):
        cerere = urllib.request.Request(url, data=date, headers=antete, method="POST")
        try:
            with urllib.request.urlopen(cerere, timeout=90) as r:
                return r.status, dict(r.headers), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            corp = e.read().decode("utf-8", errors="replace")
            if e.code >= 500 and i < incercari - 1:
                ultima = f"HTTP {e.code}"
                time.sleep(2 ** i)
                continue
            return e.code, dict(e.headers), corp
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultima = str(e)
            if i < incercari - 1:
                time.sleep(2 ** i)
                continue
    raise EroareShopify(f"Rețea indisponibilă după {incercari} încercări: {ultima}")


def obtine_token(store: str, client_id: str, client_secret: str) -> str:
    """Client credentials grant: Client ID + secret -> token valabil 24 h."""
    date = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    status, _, corp = _post(
        f"https://{store}/admin/oauth/access_token",
        date,
        {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    if status != 200:
        detaliu = ""
        if "shop_not_permitted" in corp:
            detaliu = (" Aplicația nu e instalată pe magazin sau nu e în aceeași "
                       "organizație Shopify.")
        raise EroareShopify(f"Nu pot obține tokenul (HTTP {status}).{detaliu} {corp[:300]}")
    raspuns = json.loads(corp)
    return raspuns["access_token"]


class ClientShopify:
    """Client GraphQL minimal, cu respectarea limitei de rată."""

    def __init__(self, store: str, token: str):
        self.store = normalizeaza_store(store)
        self.token = token
        self.url = f"https://{self.store}/admin/api/{API_VERSION}/graphql.json"
        self.versiune_servita = None

    def interogheaza(self, query: str, variabile: dict) -> dict:
        antete = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Shopify-Access-Token": self.token,
        }
        date = json.dumps({"query": query, "variables": variabile}).encode("utf-8")
        for _ in range(12):
            status, antete_r, corp = _post(self.url, date, antete)
            if status == 401:
                raise EroareShopify("401: token invalid sau expirat.")
            if status == 403:
                raise EroareShopify("403: aplicația nu are dreptul read_products pe acest magazin.")
            if status == 404:
                raise EroareShopify(f"404: magazinul {self.store} nu există la această adresă.")
            if status == 429:
                time.sleep(4)
                continue
            if status != 200:
                raise EroareShopify(f"HTTP {status}: {corp[:400]}")

            raspuns = json.loads(corp)
            erori = raspuns.get("errors") or []
            if erori:
                coduri = {(e.get("extensions") or {}).get("code") for e in erori}
                mesaje = " ".join(str(e.get("message", "")) for e in erori)
                if "THROTTLED" in coduri or "Throttled" in mesaje:
                    time.sleep(self._pauza_throttling(raspuns))
                    continue
                raise EroareShopify("GraphQL: " + json.dumps(erori, ensure_ascii=False)[:600])
            if raspuns.get("data") is None:
                raise EroareShopify("Răspuns fără date de la Shopify.")

            self.versiune_servita = (antete_r.get("X-Shopify-API-Version")
                                     or antete_r.get("x-shopify-api-version")
                                     or self.versiune_servita)
            return raspuns
        raise EroareShopify("Prea multe reîncercări din cauza limitei de rată Shopify.")

    @staticmethod
    def _pauza_throttling(raspuns: dict) -> float:
        """Citește bugetul rămas din răspuns; nu presupune valori fixe."""
        stare = ((raspuns.get("extensions") or {}).get("cost") or {}).get("throttleStatus") or {}
        maxim = float(stare.get("maximumAvailable") or 1000)
        disponibil = float(stare.get("currentlyAvailable") or 0)
        rata = float(stare.get("restoreRate") or 50) or 50.0
        lipsa = max(0.0, maxim * 0.5 - disponibil)
        return min(30.0, max(1.0, lipsa / rata))


def _greutate_kg(varianta: dict):
    """Greutatea variantei în kilograme, sau None dacă lipsește."""
    masura = ((varianta.get("inventoryItem") or {}).get("measurement") or {})
    greutate = masura.get("weight")
    if not greutate or greutate.get("value") in (None, ""):
        return None
    valoare = float(greutate["value"])
    unitate = (greutate.get("unit") or "KILOGRAMS").upper()
    factori = {"KILOGRAMS": 1.0, "GRAMS": 0.001, "POUNDS": 0.45359237, "OUNCES": 0.028349523125}
    return valoare * factori.get(unitate, 1.0)


def descarca_produse(client: ClientShopify, tag: str, la_pagina=None) -> list[dict]:
    """Toate produsele cu tagul dat, paginat. Potrivirea pe tag se face exact,
    pentru că filtrul Shopify caută tokenizat (tag:camera ar prinde camera-cable)."""
    produse, cursor, pagina = [], None, 0
    total_brut = 0
    while True:
        pagina += 1
        raspuns = client.interogheaza(QUERY_PRODUSE, {"cursor": cursor, "q": f"tag:{tag}"})
        bloc = raspuns["data"]["products"]
        noduri = bloc["nodes"]
        total_brut += len(noduri)
        for p in noduri:
            taguri = p.get("tags") or []
            if tag.lower() not in {t.strip().lower() for t in taguri}:
                continue
            produse.append(_curata_produs(p))
        if la_pagina:
            la_pagina(pagina, len(noduri), total_brut)
        if not bloc["pageInfo"]["hasNextPage"]:
            break
        cursor = bloc["pageInfo"]["endCursor"]
    return produse


def _curata_produs(p: dict) -> dict:
    """Transformă răspunsul GraphQL într-un dicționar simplu, independent de API."""
    imagini = []
    for nod in ((p.get("media") or {}).get("nodes") or []):
        imagine = (nod or {}).get("image")
        if not imagine or not imagine.get("url"):
            continue          # media încă neprocesată (status != READY) sau video/3D
        imagini.append({
            "url": imagine["url"],
            "latime": imagine.get("width"),
            "inaltime": imagine.get("height"),
        })

    variante = []
    for v in ((p.get("variants") or {}).get("nodes") or []):
        variante.append({
            "id": str(v.get("legacyResourceId") or ""),
            "titlu": v.get("title") or "",
            "sku": v.get("sku") or "",
            "barcode": v.get("barcode") or "",
            "pret": v.get("price"),
            "pret_comparat": v.get("compareAtPrice"),
            "pozitie": v.get("position"),
            "stoc": v.get("inventoryQuantity"),
            "greutate_kg": _greutate_kg(v),
        })

    return {
        "id": str(p.get("legacyResourceId") or ""),
        "handle": p.get("handle") or "",
        "titlu": p.get("title") or "",
        "descriere_html": p.get("descriptionHtml") or "",
        "vendor": p.get("vendor") or "",
        "tip": p.get("productType") or "",
        "taguri": p.get("tags") or [],
        "status": p.get("status") or "",
        "url": p.get("onlineStoreUrl"),
        "stoc_total": p.get("totalInventory"),
        "imagini": imagini,
        "variante": variante,
        "variante_incomplete": bool(((p.get("variants") or {}).get("pageInfo") or {}).get("hasNextPage")),
    }
