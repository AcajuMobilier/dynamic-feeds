"""Selecția produselor pentru un feed, din catalogul complet al magazinului.

O singură extragere per magazin alimentează toate feedurile lui; fiecare feed
își alege produsele de aici, după regulile din config/feeduri/<feed>.yaml:

    selectie:
      tag: "OCEANFAVI"                      # doar produsele cu acest tag
      fara_taguri: ["RESIGILATE", "..."]    # fără niciunul dintre aceste taguri
      doar_publicate: true                  # doar cu pagină pe Online Store

Potrivirea tagurilor e exactă și fără majuscule, cum era și la ocean.
"""

from __future__ import annotations


def _taguri(p: dict) -> set[str]:
    return {str(t).strip().lower() for t in (p.get("taguri") or [])}


def selecteaza(produse: list[dict], cfg) -> tuple[list[dict], dict]:
    """Întoarce (produsele selectate, contorizarea excluderilor)."""
    tag = cfg.tag.lower()
    contor = {"total": len(produse), "fara_tag": 0, "cu_tag_exclus": 0,
              "nepublicate": 0, "selectate": 0}
    selectate = []
    for p in produse:
        taguri = _taguri(p)
        if tag and tag not in taguri:
            contor["fara_tag"] += 1
            continue
        if cfg.fara_taguri and (taguri & cfg.fara_taguri):
            contor["cu_tag_exclus"] += 1
            continue
        if cfg.doar_publicate and not p.get("url"):
            contor["nepublicate"] += 1
            continue
        selectate.append(p)
    contor["selectate"] = len(selectate)
    return selectate, contor


def descrie_selectia(cfg) -> str:
    """Selecția, în cuvinte, pentru rezumatul rulării."""
    parti = []
    if cfg.tag:
        parti.append(f"cu tagul {cfg.tag}")
    if cfg.fara_taguri:
        parti.append("fără tagurile " + ", ".join(sorted(cfg.fara_taguri)))
    if cfg.doar_publicate:
        parti.append("publicate pe Online Store")
    return "produse active" + (", " + ", ".join(parti) if parti else " (tot catalogul)")
