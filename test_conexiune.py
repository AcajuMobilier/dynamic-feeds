#!/usr/bin/env python3
"""
Test de conexiune Shopify (Pasul 0.3).

Ce face:
  1. Citește credențialele din fișierul .env aflat lângă acest script.
  2. Obține un token de acces (24 h) din Client ID + Client secret, sau folosește SHOPIFY_TOKEN dacă există.
  3. Numără produsele cu tagul OCEANFAVI prin GraphQL Admin API și afișează cifrele.

Rulare (din folderul D:\\feed-favi):
    python test_conexiune.py

Nu are nevoie de pachete instalate: folosește doar biblioteca standard Python.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API_VERSION = "2026-07"   # ultima versiune stabilă la 2026-09-08 (accesibilă până pe 16 iulie 2027)
TAG = "OCEANFAVI"
PAGINA = 250              # maximul permis de Shopify per pagină


# ---------------------------------------------------------------- .env
def incarca_env(cale: Path) -> None:
    """Încarcă perechile CHEIE=valoare din .env în variabilele de mediu (fără a le suprascrie)."""
    if not cale.exists():
        return
    for linie in cale.read_text(encoding="utf-8-sig").splitlines():
        linie = linie.strip()
        if not linie or linie.startswith("#") or "=" not in linie:
            continue
        cheie, valoare = linie.split("=", 1)
        valoare = valoare.strip().strip('"').strip("'")
        if valoare:
            os.environ.setdefault(cheie.strip(), valoare)


def normalizeaza_store(valoare: str) -> str:
    """Acceptă 'handle', 'handle.myshopify.com' sau 'https://handle.myshopify.com/' și întoarce 'handle.myshopify.com'."""
    v = valoare.strip().lower()
    v = v.replace("https://", "").replace("http://", "").strip("/")
    if "/" in v:
        v = v.split("/", 1)[0]
    if not v.endswith(".myshopify.com"):
        v = v + ".myshopify.com"
    return v


# ---------------------------------------------------------------- HTTP
def post_json(url: str, date: bytes, antete: dict, incercari: int = 5):
    """POST cu reîncercare la erori de rețea / 5xx. Întoarce (status, antete_raspuns, corp_text)."""
    ultima_eroare = None
    for i in range(incercari):
        req = urllib.request.Request(url, data=date, headers=antete, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            corp = e.read().decode("utf-8", errors="replace")
            if e.code >= 500 and i < incercari - 1:
                ultima_eroare = f"HTTP {e.code}"
                time.sleep(2 * (i + 1))
                continue
            return e.code, dict(e.headers), corp
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultima_eroare = str(e)
            if i < incercari - 1:
                time.sleep(2 * (i + 1))
                continue
    raise SystemExit(f"EROARE de rețea, am renunțat după {incercari} încercări: {ultima_eroare}")


def obtine_token(store: str, client_id: str, client_secret: str) -> str:
    """Client credentials grant: Client ID + Client secret -> token de acces valabil 24 h."""
    url = f"https://{store}/admin/oauth/access_token"
    date = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    status, _, corp = post_json(url, date, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    })
    if status != 200:
        print(f"EROARE la obținerea tokenului (HTTP {status}): {corp[:500]}")
        if "shop_not_permitted" in corp:
            print("  -> Aplicația și magazinul nu sunt în aceeași organizație Shopify, sau aplicația NU este instalată pe magazin.")
            print("     Verifică în Dev Dashboard: aplicația -> Home -> Installs -> Install app.")
        elif status in (401, 400):
            print("  -> Client ID sau Client secret greșit, sau SHOPIFY_STORE greșit. Verifică valorile din .env.")
        elif status == 404:
            print("  -> Adresa magazinului nu există. Verifică SHOPIFY_STORE (trebuie să fie <handle>.myshopify.com).")
        raise SystemExit(1)
    j = json.loads(corp)
    print(f"Token obținut. Scope acordat: {j.get('scope')}  | expiră în {j.get('expires_in')} secunde")
    if "read_products" not in (j.get("scope") or ""):
        print("ATENȚIE: scope-ul read_products lipsește. În Dev Dashboard, la Versions, adaugă read_products și dă Release, apoi reinstalează.")
    return j["access_token"]


def graphql(store: str, token: str, query: str, variabile: dict) -> dict:
    """Trimite o interogare GraphQL; la THROTTLED așteaptă și reia."""
    url = f"https://{store}/admin/api/{API_VERSION}/graphql.json"
    antete = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Shopify-Access-Token": token,
    }
    date = json.dumps({"query": query, "variables": variabile}).encode("utf-8")
    for _ in range(10):
        status, antete_r, corp = post_json(url, date, antete)
        if status == 401:
            raise SystemExit("EROARE 401: token invalid sau expirat. Verifică credențialele din .env.")
        if status == 403:
            raise SystemExit("EROARE 403: aplicația nu are dreptul read_products sau nu e instalată pe magazin.")
        if status == 404:
            raise SystemExit(f"EROARE 404: verifică SHOPIFY_STORE ({store}).")
        if status == 429:
            time.sleep(3)
            continue
        if status != 200:
            raise SystemExit(f"EROARE HTTP {status}: {corp[:500]}")
        j = json.loads(corp)
        erori = j.get("errors") or []
        if erori:
            coduri = {(e.get("extensions") or {}).get("code") for e in erori}
            if "THROTTLED" in coduri or any("Throttled" in (e.get("message") or "") for e in erori):
                ts = ((j.get("extensions") or {}).get("cost") or {}).get("throttleStatus") or {}
                lipsa = max(0.0, float(ts.get("maximumAvailable", 1000)) * 0.5 - float(ts.get("currentlyAvailable", 0)))
                rata = float(ts.get("restoreRate", 50)) or 50.0
                pauza = min(30.0, max(1.0, lipsa / rata))
                print(f"  (limită de rată atinsă, aștept {pauza:.1f} s)")
                time.sleep(pauza)
                continue
            raise SystemExit("EROARE GraphQL: " + json.dumps(erori, ensure_ascii=False)[:800])
        versiune_reala = antete_r.get("X-Shopify-API-Version") or antete_r.get("x-shopify-api-version")
        j["_versiune_servita"] = versiune_reala
        return j
    raise SystemExit("EROARE: prea multe reîncercări din cauza limitei de rată.")


QUERY = """
query ($cursor: String, $q: String!) {
  products(first: %d, query: $q, after: $cursor) {
    nodes {
      legacyResourceId
      title
      status
      tags
      onlineStoreUrl
    }
    pageInfo { hasNextPage endCursor }
  }
}
""" % PAGINA


# ---------------------------------------------------------------- main
def main() -> int:
    aici = Path(__file__).resolve().parent
    incarca_env(aici / ".env")

    store = os.environ.get("SHOPIFY_STORE", "").strip()
    token = os.environ.get("SHOPIFY_TOKEN", "").strip()
    client_id = os.environ.get("SHOPIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip()

    if not store or store.startswith("exemplu."):
        print("EROARE: completează SHOPIFY_STORE în fișierul .env (vezi .env.example).")
        return 1
    store = normalizeaza_store(store)
    print(f"Magazin: {store}   | API {API_VERSION}")

    if token:
        print("Folosesc SHOPIFY_TOKEN (aplicație legacy).")
    elif client_id and client_secret:
        print("Obțin token din Client ID + Client secret...")
        token = obtine_token(store, client_id, client_secret)
    else:
        print("EROARE: completează SHOPIFY_CLIENT_ID și SHOPIFY_CLIENT_SECRET (sau SHOPIFY_TOKEN) în .env.")
        return 1

    total_query = 0
    cu_tag_exact = 0
    active = 0
    publicate = 0          # active + onlineStoreUrl prezent
    nepublicate_active = []
    cursor = None
    pagina = 0
    versiune = None

    while True:
        pagina += 1
        j = graphql(store, token, QUERY, {"cursor": cursor, "q": f"tag:{TAG}"})
        versiune = j.get("_versiune_servita") or versiune
        bloc = j["data"]["products"]
        noduri = bloc["nodes"]
        total_query += len(noduri)
        for p in noduri:
            if TAG not in (p.get("tags") or []):
                continue                       # tagul e căutat „tokenizat”; păstrăm doar potrivirea exactă
            cu_tag_exact += 1
            if p.get("status") == "ACTIVE":
                active += 1
                if p.get("onlineStoreUrl"):
                    publicate += 1
                else:
                    nepublicate_active.append((p["legacyResourceId"], p["title"]))
        print(f"  pagina {pagina}: {len(noduri)} produse (cumulat {total_query})")
        if not bloc["pageInfo"]["hasNextPage"]:
            break
        cursor = bloc["pageInfo"]["endCursor"]

    print()
    print("=" * 60)
    print(f"Versiune API servită de Shopify : {versiune}")
    print(f"Produse întoarse de căutarea tag:{TAG} : {total_query}")
    print(f"Produse cu tagul EXACT {TAG}         : {cu_tag_exact}")
    print(f"  din care cu status ACTIVE           : {active}")
    print(f"  din care ACTIVE și publicate pe Online Store (au URL) : {publicate}")
    print("=" * 60)
    if nepublicate_active:
        print(f"ACTIVE dar fără URL pe Online Store (vor fi excluse din feed): {len(nepublicate_active)}")
        for pid, titlu in nepublicate_active[:15]:
            print(f"   - {pid}  {titlu}")
        if len(nepublicate_active) > 15:
            print(f"   ... și încă {len(nepublicate_active) - 15}")
        print("Notă: dacă TOATE produsele apar fără URL, magazinul are probabil parolă activată pe Online Store.")
    print("\nCifra de comparat cu ~2.450: produsele ACTIVE și publicate pe Online Store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
