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
def monter_episode(ep: str, depuis_zero: bool = False) -> dict:
    """Monte l'épisode (voix, musique par scène, titres) et dépose le MP4 dans le dossier des rendus. Peut prendre 10 à 20 min."""
    from moteur import monter
    return monter(ep, reprendre=not depuis_zero)


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
