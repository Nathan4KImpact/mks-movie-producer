#!/usr/bin/env python3
"""Profils de modèles IA et clés API.

Les clés sont rangées dans le Gestionnaire d'identification Windows (module keyring),
jamais dans config.json. Si keyring est indisponible, repli sur atelier/.cles.json
(fichier local, à ne jamais partager). Une variable d'environnement reste possible.
"""
import json, os

ICI = os.path.dirname(os.path.abspath(__file__))
SERVICE = "ultime-assaut-atelier"
FICHIER = os.path.join(ICI, ".cles.json")

PROFILS_DEFAUT = [
    {"id": "claude-sonnet", "nom": "Claude Sonnet (équilibré)", "fournisseur": "anthropic", "modele": "claude-sonnet-5-5"},
    {"id": "claude-opus", "nom": "Claude Opus (meilleur)", "fournisseur": "anthropic", "modele": "claude-opus-5-5"},
    {"id": "claude-haiku", "nom": "Claude Haiku (économique)", "fournisseur": "anthropic", "modele": "claude-haiku-5-5"},
    {"id": "openrouter", "nom": "OpenRouter (autre modèle)", "fournisseur": "openai_compatible",
     "url_base": "https://openrouter.ai/api/v1", "modele": "A_RENSEIGNER"},
    {"id": "ollama", "nom": "Ollama (local, gratuit)", "fournisseur": "openai_compatible",
     "url_base": "http://localhost:11434/v1", "modele": "A_RENSEIGNER", "sans_cle": True},
]
TACHES = {"ecrire": "Écrire un épisode", "prompts": "Réécrire les prompts", "verifier": "Relire les images (vision)"}


def config_ia(config):
    """Renvoie la section ia au format profils (convertit l'ancien format si besoin)."""
    ia = config.setdefault("ia", {})
    if "profils" not in ia:
        ancien = ia.get("anthropic", {})
        profils = [dict(p) for p in PROFILS_DEFAUT]
        if ancien.get("modele"):
            profils[0]["modele"] = ancien["modele"]
        oc = ia.get("openai_compatible", {})
        if oc.get("url_base"):
            profils[3]["url_base"] = oc["url_base"]; profils[3]["modele"] = oc.get("modele", "A_RENSEIGNER")
        actif = "openrouter" if ia.get("fournisseur") == "openai_compatible" else "claude-sonnet"
        for k in ("fournisseur", "anthropic", "openai_compatible", "_fournisseurs_possibles"):
            ia.pop(k, None)
        ia["profils"] = profils
        ia["par_tache"] = {t: actif for t in TACHES}
    for t in TACHES:
        ia.setdefault("par_tache", {}).setdefault(t, ia["profils"][0]["id"])
    return ia


def profil(config, tache=None, pid=None):
    ia = config_ia(config)
    pid = pid or ia["par_tache"].get(tache) or ia["profils"][0]["id"]
    for p in ia["profils"]:
        if p["id"] == pid:
            return p
    raise RuntimeError(f"Profil IA introuvable : {pid}")


def _keyring():
    try:
        import keyring
        keyring.get_keyring()
        return keyring
    except Exception:
        return None


def _fichier():
    try:
        return json.load(open(FICHIER, encoding="utf-8"))
    except Exception:
        return {}


def compte(p):
    """Identifiant partagé par tous les profils d'un même fournisseur (même clé pour Sonnet/Opus/Haiku)."""
    return "compte:" + (p.get("fournisseur", "") if p.get("fournisseur") == "anthropic" else p.get("url_base", ""))


def _lire(nom):
    kr = _keyring()
    if kr:
        try:
            v = kr.get_password(SERVICE, nom)
            if v:
                return v
        except Exception:
            pass
    return _fichier().get(nom, "")


def lire_cle(p):
    if p.get("variable_cle") and os.environ.get(p["variable_cle"]):
        return os.environ[p["variable_cle"]]
    v = _lire(p["id"]) or _lire(compte(p))
    if v:
        return v
    if p.get("fournisseur") == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    return ""


def ecrire_cle(pid, cle):
    """cle vide = suppression. Renvoie l'emplacement utilisé."""
    kr = _keyring()
    if kr:
        try:
            if cle:
                kr.set_password(SERVICE, pid, cle)
            else:
                try:
                    kr.delete_password(SERVICE, pid)
                except Exception:
                    pass
            return "Gestionnaire d'identification Windows"
        except Exception:
            pass
    d = _fichier()
    if cle:
        d[pid] = cle
    else:
        d.pop(pid, None)
    json.dump(d, open(FICHIER, "w", encoding="utf-8"))
    return "fichier local .cles.json"


def etat_cles(config):
    ia = config_ia(config)
    return {p["id"]: (True if p.get("sans_cle") else bool(lire_cle(p))) for p in ia["profils"]}
