#!/usr/bin/env python3
"""Adresse dédiée par projet.

http://localhost:8765/<adresse>/  →  le serveur propre à ce projet, sur son port (8766, 8767…), démarré au besoin.
Chaque projet s'ouvre ainsi dans son onglet, plusieurs projets en même temps, sans changer le « projet actif » du poste.

- adresse : projet.json > "adresse" (réglable dans Projet › Paramètres), sinon tirée du nom du projet ;
- port    : poste.json > projets[].port, attribué une fois pour toutes (premier port libre après le port principal) ;
- un serveur de projet démarré par un autre serveur (--parent) s'arrête quand celui-ci ne répond plus.
"""
import json, os, socket, subprocess, sys, time, urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import contexte as cx

PORT_PRINCIPAL = int(os.environ.get("ATELIER_PORT_PRINCIPAL", os.environ.get("ATELIER_PORT", "8765")))
# premiers segments d'URL déjà pris par l'application : jamais utilisables comme adresse de projet
RESERVES = {"api", "web", "flow", "rendus", "aide", "projet", "musique", "essai", "favicon-ico", "index-html", "travail"}


def _meme(a, b):
    return os.path.normcase(os.path.abspath(a or "")) == os.path.normcase(os.path.abspath(b or ""))


def adresse(chemin):
    """Adresse (segment d'URL) du projet rangé dans ce dossier."""
    try:
        pj = cx.projet(chemin)
    except Exception:
        pj = {}
    a = cx.slug(pj.get("adresse") or pj.get("nom") or os.path.basename(chemin.rstrip("\\/")))
    return a if a not in RESERVES else a + "-projet"


def valider(a, chemin):
    """Adresse proposée pour le projet `chemin` : normalisée, ou ValueError si réservée ou déjà prise."""
    a = cx.slug(a)
    if a in RESERVES:
        raise ValueError(f"« {a} » est réservé par l'application : choisis une autre adresse")
    for x in cx.poste().get("projets", []):
        if not _meme(x["chemin"], chemin) and os.path.isdir(x["chemin"]) and adresse(x["chemin"]) == a:
            raise ValueError(f"L'adresse « {a} » est déjà celle du projet « {x.get('nom', '')} »")
    return a


def trouver(a):
    """Projet du poste dont l'adresse est `a` (entrée de poste.json), ou None."""
    for x in cx.poste().get("projets", []):
        if os.path.isdir(x["chemin"]) and adresse(x["chemin"]) == a:
            return x
    return None


def url(chemin, port_principal=None):
    return f"http://localhost:{port_principal or PORT_PRINCIPAL}/{adresse(chemin)}/"


def identite(port, delai=0.8):
    """Ce que répond le serveur de ce port (racine du projet servi…), ou None s'il ne répond pas."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/identite", timeout=delai) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _occupe(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def port_de(chemin, eviter=()):
    """Port réservé à ce projet sur ce poste (attribué et mémorisé au premier appel)."""
    d = cx.poste()
    entree = next((x for x in d.get("projets", []) if _meme(x["chemin"], chemin)), None)
    if entree is None:
        entree = {"nom": cx.projet(chemin).get("nom", os.path.basename(chemin)), "chemin": os.path.abspath(chemin)}
        d.setdefault("projets", []).append(entree)
    if entree.get("port") and entree["port"] not in eviter:
        return int(entree["port"])
    pris = {int(x["port"]) for x in d.get("projets", []) if x.get("port") and x is not entree} | {PORT_PRINCIPAL} | set(eviter)
    p = PORT_PRINCIPAL + 1
    while p in pris or _occupe(p):
        p += 1
    entree["port"] = p
    cx.sauver_poste(d)
    return p


def demarrer(chemin, parent=None):
    """Port du serveur de ce projet ; le démarre (sans fenêtre) s'il ne tourne pas encore."""
    eviter = []
    for _ in range(3):
        port = port_de(chemin, eviter)
        idt = identite(port)
        if idt and _meme(idt.get("racine"), chemin):
            return port
        if idt or _occupe(port):             # port pris par autre chose : on en choisit un autre
            eviter.append(port)
            continue
        journal = os.path.join(ICI, "travail", "serveurs", adresse(chemin) + ".log")
        os.makedirs(os.path.dirname(journal), exist_ok=True)
        args = [sys.executable, os.path.join(ICI, "pilotage.py"), "--projet", chemin, "--port", str(port), "--sans-navigateur"]
        if parent:
            args += ["--parent", str(parent)]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", STUDIO_PROJET=chemin, ATELIER_PORT=str(port),
                   ATELIER_PORT_PRINCIPAL=str(PORT_PRINCIPAL))
        options = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}   # pas de fenêtre
        with open(journal, "a", encoding="utf-8") as log:
            subprocess.Popen(args, cwd=ICI, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **options)
        for _ in range(60):                  # jusqu'à 15 s (premier lancement : recherche des dossiers du projet)
            time.sleep(0.25)
            idt = identite(port, 0.5)
            if idt and _meme(idt.get("racine"), chemin):
                return port
        raise RuntimeError(f"Le serveur du projet n'a pas démarré (voir {journal})")
    raise RuntimeError("Aucun port libre trouvé pour ce projet")


def surveiller_parent(parent):
    """Arrête ce serveur quand le serveur qui l'a lancé ne répond plus (trois fois de suite, 20 s d'écart)."""
    import threading

    def boucle():
        absent = 0
        while True:
            time.sleep(20)
            absent = 0 if identite(parent, 2) else absent + 1
            if absent >= 3:
                os._exit(0)
    threading.Thread(target=boucle, daemon=True).start()
