#!/usr/bin/env python3
"""MKS Movie Producer — contexte : où est le logiciel, où est le projet actif, quels réglages.

Séparation :
  - LOGICIEL (ce dossier)      : code, interface, musiques, police, réglages du poste (modèles IA, clés).
  - PROJET (dossier de travail) : tout ce qui est propre à une œuvre et qui voyage d'un poste à l'autre :
        projet.json   nom, logo, style, personnages, voix, structure (saisons × épisodes), règles IA
        sources/      livre, scripts, documents de référence
        bible/        bible.md, plan.json
        episodes/     scripts des épisodes (JSON)
        Characters/   images de référence des personnages
        Flow/<EP>/    images et vidéos générées
        Prompts_Flow/ fiches de prompts
        Rendus/       épisodes montés
        suivi.json    validations
L'état de production est entièrement recalculé à partir de ces fichiers : copier le dossier du projet
sur un autre poste suffit pour reprendre exactement au même point.
"""
import json, os, re, shutil, unicodedata

APP = os.path.dirname(os.path.abspath(__file__))
POSTE = os.path.join(APP, "poste.json")          # projets connus + projet actif (propre à ce poste)
REGLAGES = os.path.join(APP, "reglages.json")    # profils de modèles IA (propre à ce poste)
NOM_LOGICIEL = "MKS Movie Producer"

DEFAUT_PROJET = {
    "nom": "Nouveau projet",
    "sous_titre": "",
    "type": "serie",
    "saisons": 1,
    "episodes_par_saison": 7,
    "duree_min": 7,
    "langue": "fr",
    "livre": "",
    "voix": {"nom": "fr-FR-HenriNeural", "debit": "-15%", "hauteur": "-6Hz"},
    "volume_musique": 0.47,
    "musique_defaut": "Lord_of_the_Land",
    "musiques": ["Clash_Defiant", "Crusade_-_Heavy_Industry", "Dark_Walk", "Darkest_Child", "Echoes_of_Time_v2",
                 "Ever_Mindful", "Heroic_Age", "Interloper", "Lightless_Dawn", "Long_Note_Four", "Lord_of_the_Land",
                 "Ossuary_6_-_Air", "Prelude_and_Action", "Rising_Game"],
    "style_image": "Cinematic film still, photorealistic, vivid colors, dramatic lighting, high detail, 16:9, no text. ",
    "personnages": [],
    "regles_ia": "",
    "logo": "logo.svg",
    "couleur": "#d8b46a",
}


def slug(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()[:40] or "projet"


def _lire(p, defaut):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return defaut


def _ecrire(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, p)


# ---------------------------------------------------------------- poste
def poste():
    return _lire(POSTE, {"projets": [], "projet_actif": ""})


def sauver_poste(d):
    _ecrire(POSTE, d)


def racine():
    """Dossier du projet actif. Priorité : variable STUDIO_PROJET, poste.json, puis dossier parent du logiciel."""
    env = os.environ.get("STUDIO_PROJET")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    p = poste().get("projet_actif")
    if p and os.path.isdir(p):
        return os.path.abspath(p)
    return os.path.dirname(APP)


def definir_projet_actif(chemin):
    chemin = os.path.abspath(chemin)
    d = poste()
    d["projet_actif"] = chemin
    nom = projet(chemin).get("nom", os.path.basename(chemin))
    d["projets"] = [x for x in d.get("projets", []) if os.path.abspath(x["chemin"]) != chemin]
    d["projets"].insert(0, {"nom": nom, "chemin": chemin})
    sauver_poste(d)


def chemin(*parties):
    return os.path.join(racine(), *parties)


# ---------------------------------------------------------------- projet
def projet(rac=None):
    rac = rac or racine()
    p = dict(DEFAUT_PROJET)
    p.update(_lire(os.path.join(rac, "projet.json"), {}))
    return p


def sauver_projet(p, rac=None):
    _ecrire(os.path.join(rac or racine(), "projet.json"), p)


def est_projet(rac):
    return os.path.exists(os.path.join(rac, "projet.json"))


def dossier_episodes():
    return chemin("episodes")


def remplacer_tags(prompt, pj=None):
    """[VOYANT] (ou tout tag de personnage) -> description du personnage. Renvoie (texte, [tags trouvés])."""
    pj = pj or projet()
    trouves = []
    for perso in pj.get("personnages", []):
        tag = f"[{perso['tag']}]"
        if tag in prompt:
            prompt = prompt.replace(tag, perso.get("description", perso["nom"]))
            trouves.append(perso)
    return prompt, trouves


# ---------------------------------------------------------------- réglages du poste (IA)
def reglages():
    from cles import config_ia
    r = _lire(REGLAGES, None)
    if r is None:
        ancien = _lire(os.path.join(APP, "config.json"), {})
        r = {"ia": ancien.get("ia", {})}
    config_ia(r)
    return r


def sauver_reglages(r):
    _ecrire(REGLAGES, r)


# ---------------------------------------------------------------- migration de l'ancien atelier
def migrer():
    """Ancien format : episodes/, bible/, suivi.json et config.json dans le dossier du logiciel.
    On les range dans le dossier du projet (parent) et on crée projet.json / reglages.json."""
    ancien_cfg = os.path.join(APP, "config.json")
    rac = os.path.dirname(APP) if not poste().get("projet_actif") else racine()
    fait = []
    if os.path.exists(ancien_cfg) and not est_projet(rac):
        c = _lire(ancien_cfg, {})
        pj = dict(DEFAUT_PROJET)
        for k in ("voix", "volume_musique", "musique_defaut", "musiques", "style_image"):
            if k in c:
                pj[k] = c[k]
        if "Ultime" in c.get("livre_pdf", "") or os.path.exists(os.path.join(APP, "episodes", "E101.json")):
            pj.update(PROJET_ULTIME_ASSAUT)
            pj["livre"] = c.get("livre_pdf", pj["livre"])
            if c.get("voyant"):
                pj["personnages"][0]["description"] = c["voyant"]
        sauver_projet(pj, rac)
        fait.append("projet.json")
    if os.path.exists(ancien_cfg) and not os.path.exists(REGLAGES):
        sauver_reglages({"ia": _lire(ancien_cfg, {}).get("ia", {})})
        reglages()
        fait.append("reglages.json")
    for nom in ("episodes", "bible"):
        src, dst = os.path.join(APP, nom), os.path.join(rac, nom)
        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            for racine_src, _, fichiers in os.walk(src):
                rel = os.path.relpath(racine_src, src)
                os.makedirs(os.path.join(dst, rel), exist_ok=True)
                for f in fichiers:
                    cible = os.path.join(dst, rel, f)
                    if not os.path.exists(cible):
                        shutil.copy2(os.path.join(racine_src, f), cible)
            shutil.rmtree(src)
            fait.append(nom + "/")
    s = os.path.join(APP, "suivi.json")
    if os.path.exists(s):
        if not os.path.exists(os.path.join(rac, "suivi.json")):
            shutil.move(s, os.path.join(rac, "suivi.json"))
        else:
            os.remove(s)
        fait.append("suivi.json")
    if os.path.exists(ancien_cfg) and est_projet(rac):
        os.replace(ancien_cfg, os.path.join(APP, "config.ancien.json"))
    if fait and not poste().get("projet_actif"):
        definir_projet_actif(rac)
    return fait


PROJET_ULTIME_ASSAUT = {
    "nom": "L'Ultime Assaut",
    "sous_titre": "Mini-série · 7 saisons × 7 épisodes · d'après Rick Joyner",
    "type": "serie", "saisons": 7, "episodes_par_saison": 7, "duree_min": 7,
    "livre": "L'Ultime Assaut - Rick Joyer.pdf",
    "style_image": "Epic cinematic fantasy film still, photorealistic, vivid saturated colors, bright dramatic lighting, high detail, grand scale, 16:9, no text. ",
    "personnages": [{"tag": "VOYANT", "nom": "Le Voyant",
                     "description": "the man from the reference image (same face, dark-brown tousled hair, short dark-brown beard, light blue-grey eyes, rough brown wool tunic and cloak)",
                     "reference": "Characters/Voyant_reference.png"}],
    "regles_ia": """Tu es scénariste et réalisateur de la mini-série « L'Ultime Assaut », adaptée du livre de Rick Joyner.
Règles de la série :
- Narration à la première personne par « le Voyant », personnage fictif d'environ 44 ans (jamais le visage réel de l'auteur).
- Ton symbolique, tout public, fidèle au livre ; français soigné, phrases rythmées pour la voix off.
- Épisode d'environ 7 minutes : 28 à 36 plans, 650 à 780 mots de narration au total.
- Direction artistique : couleurs vives et lumineuses, photoréaliste épique ; créatures démoniaques très explicites
  (démons hideux montés sur les épaules des croyants, vautours noirs géants, horde en armure aux ailes rouges),
  armée de lumière en armures brillantes, montagne sainte à corniches.""",
    "logo": "logo.svg",
    "couleur": "#d8b46a",
}

REGLES_FORMAT = """
Format technique (obligatoire) :
- Chaque plan : "k" (clé ex. {code}-01), "vo" (narration), "p" (prompt image EN ANGLAIS, sans le préfixe de style),
  "m" (mouvement : in, out, left, right, up, down, still), optionnels "title" (mot-clé en capitales affiché à l'écran),
  "min" (durée mini en s), "mus" (changement de musique à ce plan), "vid_prompt" (pour 4 à 7 plans à animer).
- Personnages récurrents : mettre leur tag au début de "p" quand ils sont visibles de face : {tags}.
- Deux cartons : après les 1 ou 2 premiers plans {{"card":"{titre_carton}","sub":"Saison X · Épisode Y — Titre","dur":7}}
  et à la fin {{"card":"À SUIVRE","sub":"Épisode suivant — Titre","dur":6}}.
- Durée visée : {duree} minutes, soit environ {mots} mots de narration.
- "mus" : 6 à 8 changements par épisode, choisis selon le ton de la scène, uniquement parmi : {musiques}.
Réponds UNIQUEMENT avec le JSON complet de l'épisode."""


def regles_ia(code="E101", pj=None):
    pj = pj or projet()
    base = pj.get("regles_ia") or (f"Tu es scénariste et réalisateur de « {pj['nom']} ». "
                                   "Reste fidèle aux sources du projet ; écris une narration fluide pour la voix off.")
    tags = ", ".join(f"[{p['tag']}] = {p['nom']}" for p in pj.get("personnages", [])) or "aucun"
    return base + REGLES_FORMAT.format(code=code, tags=tags, titre_carton=pj["nom"].upper(),
                                       duree=pj.get("duree_min", 7), mots=int(pj.get("duree_min", 7) * 110),
                                       musiques=", ".join(pj.get("musiques", [])))
