#!/usr/bin/env python3
"""Serveur MCP de MKS Movie Producer (projet actif) : permet à Claude (Claude Desktop, Claude Code, ou tout client MCP)
de piloter l'atelier — lire/écrire les épisodes, vérifier les images, générer les fiches, monter.

Configuration (Claude Desktop > Paramètres > Développeur > Modifier la config) : voir LISEZ-MOI.
"""
import json, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)
import contexte as cx
cx.migrer()
cx.reparer_fichiers()

try:                                   # SDK MCP 1.x
    from mcp.server.fastmcp import FastMCP as _Serveur
except ImportError:                    # SDK MCP 2.x
    from mcp.server.mcpserver import MCPServer as _Serveur

mcp = _Serveur("mks-movie-producer")


@mcp.tool()
def lister_episodes() -> list[str]:
    """Liste les épisodes disponibles (scripts du dossier des épisodes)."""
    from atelier import episodes
    return episodes()


@mcp.tool()
def lire_episode(ep: str) -> str:
    """Renvoie le JSON complet d'un épisode (narration, prompts, musiques, plans vidéo)."""
    return open(cx.dossier("episodes", ep + ".json"), encoding="utf-8").read()


@mcp.tool()
def ecrire_episode(ep: str, json_episode: str) -> str:
    """Remplace le JSON d'un épisode (l'ancienne version est sauvegardée dans episodes/anciennes)."""
    from ia import _sauver
    e = json.loads(json_episode)
    _sauver(ep, e)
    return f"{ep} enregistré ({len(e.get('shots', []))} plans)"


@mcp.tool()
def etat_images(ep: str) -> dict:
    """Indique quelles images/vidéos Flow manquent pour un épisode."""
    from moteur import etat_images as f
    return f(ep)


@mcp.tool()
def generer_fiche_flow(ep: str) -> str:
    """Génère la fiche de prompts <ep>_fiche_Flow.txt (dossier des fiches) à partir du JSON de l'épisode."""
    from fiche import fiche_flow
    return fiche_flow(ep)


@mcp.tool()
def lire_livre(pages: str) -> str:
    """Texte du livre pour une plage de pages du PDF (ex. '61-68')."""
    from ia import lire_livre as f
    return f(pages)


@mcp.tool()
def monter_episode(ep: str, depuis_zero: bool = False, langue: str = "") -> dict:
    """Monte l'épisode (voix, musique par scène, titres) et dépose le MP4 + sous-titres .srt dans le dossier des rendus.
    langue : vide = langue d'origine ; sinon code d'une version du projet (ex. "en"), rendu dans <rendus>/en/. 10 à 20 min."""
    from moteur import monter
    return monter(ep, reprendre=not depuis_zero, langue=langue or None)


@mcp.tool()
def etat_traductions(ep: str) -> dict:
    """Pour chaque langue cible du projet : éléments traduits, manquants, et à revoir (texte d'origine modifié depuis).
    Les traductions sont dans le JSON de l'épisode : "versions": {"en": {"vo", "title" | "card", "sub", "de"}} sur chaque
    plan et carton, et sur l'épisode pour son titre. Pour traduire toi-même : lis l'épisode, remplis ces champs, puis
    appelle enregistrer_traductions (qui calcule l'empreinte « de »)."""
    import langues as lg
    e = json.load(open(cx.dossier("episodes", ep + ".json"), encoding="utf-8"))
    return {l: lg.etat_traduction(e, l) for l in lg.versions(cx.projet())}


@mcp.tool()
def enregistrer_traductions(ep: str, langue: str, elements_json: str) -> dict:
    """Enregistre des traductions écrites par Claude. elements_json : [{"i": 0, "title": "…"}, {"i": 3, "vo": "…", "title": "…"},
    {"i": 2, "card": "…", "sub": "…"}] où i = 0 pour l'épisode (titre) et i = n pour shots[n-1]."""
    import langues as lg
    from ia import _sauver
    e = json.load(open(cx.dossier("episodes", ep + ".json"), encoding="utf-8"))
    elements = [e] + e.get("shots", [])
    for x in json.loads(elements_json):
        lg.poser(elements[int(x["i"])], langue, x)
    _sauver(ep, e)
    return lg.etat_traduction(e, langue)


@mcp.tool()
def traduire_episode(ep: str, langue: str, consignes: str = "", tout: bool = False) -> dict:
    """[IA de l'application] Traduit les textes manquants ou à revoir d'un épisode avec le modèle choisi dans Réglages."""
    from ia import traduire_episode as f
    return f(ep, langue, consignes, tout)


@mcp.tool()
def catalogue_sons() -> list:
    """Ambiances (champ "amb" d'un plan, continue jusqu'au prochain "amb" ; "aucune" coupe) et bruitages ponctuels
    (champ "sfx", nom ou liste) disponibles, avec leur provenance (fichier du projet ou synthèse) et un prompt anglais
    pour générer un vrai son. "son_video": true garde le son de la vidéo du plan.
    Effets par plan : "fx": {"voix"|"mus"|"amb"|"sfx": {"in": fondu d'entrée s, "out": fondu de sortie s, "vol": ×,
    "effet": echo|salle|lointain|radio|etouffe|grave|aigu}}."""
    import sons
    return sons.liste()


@mcp.tool()
def projet_actif() -> dict:
    """Nom, dossier, paramètres du projet actif (structure, style, personnages, voix) et organisation de ses dossiers."""
    return {"racine": cx.racine(), "projet": cx.projet(), "organisation": cx.organisation()}


@mcp.tool()
def lire_sources(limite: int = 60000) -> str:
    """Texte des sources du projet (livre, scripts, notes), tronqué."""
    from ia import texte_sources
    return texte_sources(limite)


@mcp.tool()
def etat_production() -> dict:
    """Assistant de production : étape actuelle, prochaine étape, épisodes suivants et vérifications d'installation."""
    from pilotage import assistant
    return assistant()


@mcp.tool()
def lire_bible() -> str:
    """Bible de la série (direction artistique, personnages, plan des épisodes avec pages du livre)."""
    return open(cx.dossier("bible", "bible.md"), encoding="utf-8").read()


if __name__ == "__main__":
    mcp.run()
