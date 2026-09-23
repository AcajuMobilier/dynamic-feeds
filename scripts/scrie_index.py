#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrie o pagină simplă de index lângă feeduri, ca să se vadă dintr-o privire
ce e publicat și când. Nu e cerută de Favi; e doar pentru verificare umană.

Rulare:  python scripts/scrie_index.py public
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.consola import pregateste as pregateste_consola  # noqa: E402

pregateste_consola()

SABLON = """<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Feeduri pentru marketplace-uri</title>
<style>
  :root {{ color-scheme: light dark; --fundal:#fff; --text:#1a1a1a; --slab:#666; --linie:#e5e5e5; --accent:#0a5; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fundal:#151515; --text:#eee; --slab:#999; --linie:#333; --accent:#3c9; }}
  }}
  body {{ background:var(--fundal); color:var(--text); font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;
         max-width:52rem; margin:0 auto; padding:2.5rem 1rem; }}
  h1 {{ font-size:1.5rem; margin:0 0 .25rem; }}
  p.sub {{ color:var(--slab); margin:0 0 2rem; }}
  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ text-align:left; padding:.7rem .6rem; border-bottom:1px solid var(--linie); }}
  th {{ color:var(--slab); font-weight:600; font-size:.85rem; text-transform:uppercase; letter-spacing:.03em; }}
  td.nr {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  a {{ color:var(--accent); }}
  footer {{ color:var(--slab); font-size:.85rem; margin-top:2.5rem; }}
</style>
</head>
<body>
<h1>Feeduri pentru marketplace-uri</h1>
<p class="sub">Generate automat din Shopify. Actualizare la fiecare 2 ore.</p>
<table>
<thead><tr><th>Fișier</th><th>Magazin</th><th>Ultima rulare</th><th class="nr">Produse</th><th class="nr">Mărime</th></tr></thead>
<tbody>
{randuri}
</tbody>
</table>
<footer>Ultima generare: {moment} UTC{rulare}</footer>
</body>
</html>
"""


def marime_lizibila(octeti: int) -> str:
    for unitate in ("B", "KB", "MB", "GB"):
        if octeti < 1024 or unitate == "GB":
            return f"{octeti:.0f} {unitate}" if unitate == "B" else f"{octeti:.1f} {unitate}"
        octeti /= 1024
    return f"{octeti:.1f} GB"


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "public")
    if not folder.is_dir():
        print(f"EROARE: folderul {folder} nu există.")
        return 1

    # starea scrisă de genereaza.py: ce feed a fost regenerat și ce a rămas vechi
    stare = {}
    try:
        for f in json.loads((folder / "stare.json").read_text(encoding="utf-8")).get("feeduri", []):
            stare[f.get("fisier")] = f
    except (OSError, ValueError):
        pass

    randuri = []
    for fisier in sorted(folder.iterdir()):
        if fisier.name in ("index.html", "stare.json") or not fisier.is_file():
            continue
        produse = ""
        if fisier.suffix == ".xml":
            try:
                text = fisier.read_text(encoding="utf-8")
                produse = str(len(re.findall(r"<SHOPITEM>|<item>", text)))
            except OSError:
                produse = "?"
        elif fisier.suffix == ".csv":
            try:
                with open(fisier, encoding="utf-8-sig") as f:
                    produse = str(max(0, sum(1 for _ in f) - 1))
            except OSError:
                produse = "?"
        st = stare.get(fisier.name) or {}
        magazin = st.get("magazin", "")
        if not st:
            ultima = ""
        elif st.get("ok"):
            ultima = "regenerat"
        elif st.get("pastrat_live"):
            ultima = "a picat, păstrat cel vechi"
        else:
            ultima = "a picat"
        nume = html.escape(fisier.name)
        randuri.append(
            f'<tr><td><a href="{nume}">{nume}</a></td>'
            f'<td>{html.escape(magazin)}</td><td>{html.escape(ultima)}</td>'
            f'<td class="nr">{produse}</td>'
            f'<td class="nr">{marime_lizibila(fisier.stat().st_size)}</td></tr>'
        )

    rulare = ""
    server, repo, run_id = (os.environ.get("GITHUB_SERVER_URL"),
                            os.environ.get("GITHUB_REPOSITORY"),
                            os.environ.get("GITHUB_RUN_ID"))
    if server and repo and run_id:
        rulare = f' — <a href="{server}/{repo}/actions/runs/{run_id}">vezi rularea</a>'

    (folder / "index.html").write_text(
        SABLON.format(
            randuri="\n".join(randuri) or '<tr><td colspan="5">Niciun fișier.</td></tr>',
            moment=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            rulare=rulare,
        ),
        encoding="utf-8",
    )
    print(f"Index scris în {folder / 'index.html'} ({len(randuri)} fișiere).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
