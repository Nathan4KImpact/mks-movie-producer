#!/usr/bin/env python3
"""MKS Movie Producer — contexte : où est le logiciel, où est le projet actif, quels réglages.

Séparation :
  - LOGICIEL (ce dossier)      : code, interface, musiques, police, réglages du poste (modèles IA, clés).
  - PROJET (dossier de travail) : tout ce qui est propre à une œuvre et qui voyage d'un poste à l'autre.
    À la racine : projet.json (nom, logo, style, personnages, voix, structure, règles IA, carte des dossiers)
    et suivi.json (validations). Tout le reste est rangé librement : chaque rôle (sources, personnages,
    bible, episodes, fiches, images, rendus, exports, musique) a son dossier dans projet.json > "dossiers",
    retrouvé automatiquement d'après son contenu s'il a été déplacé (voir ROLES et dossier()).
L'état de production est entièrement recalculé à partir de ces fichiers : copier le dossier du projet
sur un autre poste suffit pour reprendre exactement au même point.
"""
import json, os, re, shutil, sys, time, unicodedata

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
    "versions": {},
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
    """Chemin à la racine du projet (projet.json, suivi.json). Pour les dossiers de travail, utiliser dossier(rôle)."""
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


# ---------------------------------------------------------------- organisation : carte des dossiers par rôle
# Le logiciel ne suppose plus d'arborescence fixe. Chaque rôle (épisodes, images…) a un dossier, noté dans
# projet.json > "dossiers". Si ce dossier n'existe plus (l'utilisateur a rangé le projet), il est retrouvé
# d'après son CONTENU (ex. des .json avec "shots" = scripts d'épisodes), puis la carte est mise à jour.
# Seuls projet.json et suivi.json restent à la racine du projet : ce sont ses ancres.
ROLES = {
    # rôle         (dossier par défaut, libellé,                 description,                               mots-clés de nom)
    "sources":     ("sources",      "Sources",                    "livre, scripts, notes, documents de référence", ("source", "input", "document", "livre")),
    "personnages": ("Characters",   "Personnages",                "images de référence des personnages",     ("charac", "personnage", "perso", "reference")),
    "bible":       ("bible",        "Bible et plan",              "bible.md et plan.json utilisés par l'application", ("bible",)),
    "episodes":    ("episodes",     "Scripts des épisodes",       "E101.json, E102.json…",                    ("episode", "script")),
    "fiches":      ("Prompts_Flow", "Fiches de prompts",          "E104_fiche_Flow.txt…",                     ("prompt", "fiche")),
    "images":      ("Flow",         "Images et vidéos",           "un sous-dossier par épisode : E104/E104-01.png…", ("flow", "image", "media", "visuel")),
    "rendus":      ("Rendus",       "Épisodes montés",            "fichiers .mp4 produits par le montage",    ("rendu", "render", "montage", "video")),
    "exports":     ("_exports",     "Exports",                    "zips d'export du projet",                  ("export",)),
    "musique":     ("bibliotheque/musique", "Musiques du projet",         "facultatif : pistes propres à ce projet",  ("musique", "music")),
}
CODE_EP = re.compile(r"^(?:[A-Z]{1,4}\d{2,4}|BA)$", re.I)
IMG = (".png", ".jpg", ".jpeg", ".webp")
VID = (".mp4", ".mov", ".webm")
_EXCLUS = {"__pycache__", "node_modules", "travail", "cache", "anciennes"}
_INDEX = {}      # racine -> (instant, [(dossier, sous-dossiers, fichiers)])
_ABSENTS = {}    # (racine, rôle) -> instant de la dernière recherche infructueuse
_NOMS = {}       # racine -> (instant de l'index, {nom de fichier en minuscules: chemin})
_TTL = 20


def _rel(p, rac=None):
    return os.path.relpath(p, rac or racine()).replace("\\", "/")


def _abs(rel, rac=None):
    return os.path.join(rac or racine(), *[x for x in rel.replace("\\", "/").split("/") if x])


def _sans_accents(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def index_projet(rac=None, frais=False):
    """Parcours du projet (profondeur 5), hors logiciel, dossiers cachés et fichiers de travail. Mis en cache 20 s."""
    rac = os.path.abspath(rac or racine())
    t, idx = _INDEX.get(rac, (0, None))
    if idx is not None and not frais and time.time() - t < _TTL:
        return idx
    app = os.path.realpath(APP)
    idx = []
    for d, sous, fichiers in os.walk(rac):
        prof = os.path.relpath(d, rac).count(os.sep)
        sous[:] = [s for s in sous if not s.startswith((".", "$")) and s not in _EXCLUS
                   and os.path.realpath(os.path.join(d, s)) != app and prof < 5]
        idx.append((d, list(sous), fichiers))
    _INDEX[rac] = (time.time(), idx)
    return idx


def oublier_index(rac=None):
    _INDEX.pop(os.path.abspath(rac or racine()), None)
    for k in [k for k in _ABSENTS if k[0] == os.path.abspath(rac or racine())]:
        _ABSENTS.pop(k)


def _score(role, d, sous, fichiers, pj):
    """Ressemblance d'un dossier avec un rôle, d'après ce qu'il contient (0 = aucun rapport)."""
    nom = _sans_accents(os.path.basename(d))
    low = [f.lower() for f in fichiers]
    bonus = 2 if any(m in nom for m in ROLES[role][3]) else 0
    if role == "episodes":
        n = 0
        for f in fichiers:
            if f.lower().endswith(".json") and f.lower() not in ("plan.json", "projet.json", "suivi.json"):
                try:
                    with open(os.path.join(d, f), encoding="utf-8") as fh:
                        n += '"shots"' in fh.read(4000)
                except Exception:
                    pass
        return n * 3 + bonus if n else 0
    if role == "bible":
        return (5 if "plan.json" in low else 0) + (3 if "bible.md" in low else 0) + (bonus if "plan.json" in low or "bible.md" in low else 0)
    if role == "fiches":
        n = sum(f.endswith("_fiche_flow.txt") for f in low)
        return n * 3 + bonus if n else 0
    if role == "images":
        n = 0
        for s in sous:
            if CODE_EP.match(s):
                n += 1
        return n * 3 + bonus if n else (1 if bonus and nom == "flow" else 0)
    if role == "rendus":
        if CODE_EP.match(os.path.basename(d)):
            return 0                                   # sous-dossier d'images d'un épisode
        n = sum(f.endswith(VID) for f in low)
        return n + 3 * bonus if n else 0
    if role == "sources":
        livre = os.path.basename(pj.get("livre", "") or "").lower()
        if livre and livre in low:
            return 10
        n = sum(f.endswith((".pdf", ".docx", ".txt", ".md", ".srt", ".fountain")) for f in low)
        return n + 3 if bonus and n else 0
    if role == "personnages":
        refs = {os.path.basename(p.get("reference", "")).lower() for p in pj.get("personnages", []) if p.get("reference")}
        n = len(refs & set(low))
        if n:
            return 10 * n
        return (sum(f.endswith(IMG) for f in low) + 3) if bonus and any(f.endswith(IMG) for f in low) else 0
    if role == "exports":
        n = sum(f.endswith(".zip") for f in low)
        return n + bonus if n and bonus else 0
    if role == "musique":
        n = sum(f.endswith((".mp3", ".wav", ".m4a")) for f in low)
        return n if n and bonus else 0
    return 0


def detecter(role, rac=None, pj=None):
    """Cherche dans le projet le dossier qui correspond le mieux à un rôle. Renvoie un chemin absolu ou ''."""
    rac = os.path.abspath(rac or racine()); pj = pj or projet(rac)
    meilleur, score = "", 0
    for d, sous, fichiers in index_projet(rac):
        if d == rac and role not in ("sources",):
            continue
        s = _score(role, d, sous, fichiers, pj)
        if s > score:
            meilleur, score = d, s
    return meilleur


def dossier(role, *parties, creer=False):
    """Chemin absolu du dossier d'un rôle (+ sous-parties). Retrouve et mémorise un dossier déplacé."""
    rac = racine(); pj = projet(rac)
    rel = (pj.get("dossiers") or {}).get(role) or ROLES[role][0]
    p = _abs(rel, rac)
    if not os.path.isdir(p):
        cle = (os.path.abspath(rac), role)
        if time.time() - _ABSENTS.get(cle, 0) > _TTL:
            trouve = detecter(role, rac, pj)
            if trouve:
                memoriser_dossier(role, _rel(trouve, rac), rac)
                p = trouve
            else:
                _ABSENTS[cle] = time.time()
    if creer:
        os.makedirs(p, exist_ok=True)
    return os.path.join(p, *parties)


def memoriser_dossier(role, rel, rac=None):
    rac = rac or racine()
    pj = _lire(os.path.join(rac, "projet.json"), {})
    pj.setdefault("dossiers", {})[role] = rel.replace("\\", "/")
    _ecrire(os.path.join(rac, "projet.json"), pj)
    _ABSENTS.pop((os.path.abspath(rac), role), None)
    print(f"[organisation] {ROLES[role][1]} : {rel}", file=sys.stderr)


def chercher_media(cle, rac=None):
    """Image ou vidéo d'un plan rangée ailleurs que dans le dossier des images (ex. ancien dossier Flow).
    Renvoie (chemin, est_video) ou ('', False). Les vidéos sont prioritaires, comme au montage."""
    rac = os.path.abspath(rac or racine())
    t, idx = _INDEX.get(rac, (0, None))
    carte = _NOMS.get(rac)
    if carte is None or carte[0] != t or idx is None:
        idx = index_projet(rac)
        noms = {}
        for d, _, fichiers in idx:
            for f in fichiers:
                noms.setdefault(f.lower(), os.path.join(d, f))
        carte = _NOMS[rac] = (_INDEX[rac][0], noms)
    for ext in VID + IMG:
        p = carte[1].get((cle + ext).lower())
        if p:
            return p, ext in VID
    return "", False


def fichier(rel, rac=None):
    """Chemin absolu d'un fichier du projet noté en relatif (livre, logo, référence…). S'il a été déplacé,
    il est retrouvé par son nom n'importe où dans le projet. Renvoie '' s'il est introuvable."""
    if not rel:
        return ""
    rac = rac or racine()
    p = _abs(rel, rac)
    if os.path.isfile(p):
        return p
    nom = os.path.basename(rel.replace("\\", "/")).lower()
    for d, _, fichiers in index_projet(rac):           # index rafraîchi toutes les 20 s
        for f in fichiers:
            if f.lower() == nom:
                return os.path.join(d, f)
    return ""


def reparer_fichiers(rac=None):
    """Met à jour dans projet.json les chemins du livre, du logo et des images de référence s'ils ont été déplacés."""
    rac = rac or racine()
    brut = _lire(os.path.join(rac, "projet.json"), None)
    if brut is None:
        return []
    faits = []

    def verifier(rel):
        if not rel or os.path.isfile(_abs(rel, rac)):
            return rel
        p = fichier(rel, rac)
        if p:
            faits.append(f"{rel} → {_rel(p, rac)}")
            return _rel(p, rac)
        return rel
    for k in ("livre", "logo"):
        if brut.get(k):
            brut[k] = verifier(brut[k])
    for perso in brut.get("personnages", []):
        if perso.get("reference"):
            perso["reference"] = verifier(perso["reference"])
    if faits:
        _ecrire(os.path.join(rac, "projet.json"), brut)
        print("[organisation] fichiers retrouvés : " + " ; ".join(faits), file=sys.stderr)
    return faits


def organisation(rac=None):
    """État de chaque rôle pour l'interface : dossier, existence, nombre de fichiers, détecté ou par défaut."""
    rac = rac or racine()
    out = []
    for role, (defaut, libelle, desc, _) in ROLES.items():
        p = dossier(role)
        carte = projet(rac).get("dossiers") or {}
        existe = os.path.isdir(p)
        n = sum(len(f) for d, _, f in index_projet(rac) if d == p or d.startswith(p + os.sep)) if existe else 0
        out.append({"role": role, "libelle": libelle, "description": desc, "chemin": _rel(p, rac), "existe": existe,
                    "fichiers": n, "personnalise": role in carte, "defaut": defaut})
    return out


def definir_dossier(role, chemin_choisi, rac=None):
    """Associe un rôle à un dossier existant (choisi dans l'interface), qui doit être dans le projet."""
    rac = rac or racine()
    p = os.path.realpath(chemin_choisi if os.path.isabs(chemin_choisi) else _abs(chemin_choisi, rac))
    if p != os.path.realpath(rac) and not p.startswith(os.path.realpath(rac) + os.sep):
        raise ValueError("Le dossier doit se trouver à l'intérieur du dossier du projet")
    os.makedirs(p, exist_ok=True)
    rel = _rel(p, os.path.realpath(rac))
    memoriser_dossier(role, rel, rac)
    oublier_index(rac)
    return rel


def rechercher(rac=None):
    """Relance la recherche de tous les dossiers et fichiers déplacés. Renvoie ce qui a été retrouvé."""
    rac = rac or racine()
    oublier_index(rac)
    avant = dict(projet(rac).get("dossiers") or {})
    for role in ROLES:
        dossier(role)
    apres = projet(rac).get("dossiers") or {}
    faits = [f"{ROLES[r][1]} : {apres[r]}" for r in apres if avant.get(r) != apres[r]]
    return faits + reparer_fichiers(rac)


def deplacer_dossier(role, vers, rac=None):
    """Déplace physiquement le dossier d'un rôle vers un autre emplacement du projet, et met à jour la carte
    ainsi que les chemins du livre, du logo et des références qui s'y trouvaient."""
    rac = rac or racine()
    vers = vers.replace("\\", "/").strip("/ ")
    cible = os.path.realpath(_abs(vers, rac))
    if not vers or ".." in vers.split("/") or not cible.startswith(os.path.realpath(rac) + os.sep):
        raise ValueError("Le nouvel emplacement doit être à l'intérieur du dossier du projet")
    src = dossier(role)
    if os.path.isdir(cible) and os.listdir(cible):
        raise ValueError(f"{vers} existe déjà et n'est pas vide")
    if os.path.isdir(src):
        if cible.startswith(os.path.realpath(src) + os.sep):
            raise ValueError("Impossible de déplacer un dossier dans lui-même")
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        if os.path.isdir(cible):
            os.rmdir(cible)
        shutil.move(src, cible)
    else:
        os.makedirs(cible, exist_ok=True)
    ancien = _rel(src, rac) + "/"
    memoriser_dossier(role, vers, rac)
    brut = _lire(os.path.join(rac, "projet.json"), {})
    for k in ("livre", "logo"):
        if brut.get(k, "").replace("\\", "/").startswith(ancien):
            brut[k] = vers + "/" + brut[k].replace("\\", "/")[len(ancien):]
    for perso in brut.get("personnages", []):
        r = perso.get("reference", "").replace("\\", "/")
        if r.startswith(ancien):
            perso["reference"] = vers + "/" + r[len(ancien):]
    _ecrire(os.path.join(rac, "projet.json"), brut)
    oublier_index(rac)
    return vers


# Rangement recommandé : ce qu'on prépare dans bibliotheque/, ce qu'on fabrique dans production/.
GROUPES = {"sources": "bibliotheque", "personnages": "bibliotheque", "bible": "bibliotheque", "episodes": "bibliotheque",
           "musique": "bibliotheque", "fiches": "production", "images": "production", "rendus": "production"}
DISPOSITION_NOUVEAU = {"sources": "bibliotheque/sources", "personnages": "bibliotheque/personnages",
                       "bible": "bibliotheque/bible", "episodes": "bibliotheque/episodes", "musique": "bibliotheque/musique",
                       "fiches": "production/fiches", "images": "production/images", "rendus": "production/rendus",
                       "exports": "_exports"}


def ranger_racine(appliquer=False, rac=None):
    """Range dans bibliotheque/ ou production/ les dossiers restés à la racine du projet (en gardant leur nom),
    ainsi que le logo. Renvoie la liste des déplacements (prévus, ou faits si appliquer=True)."""
    rac = rac or racine()
    prevus, erreurs = [], []
    for role, groupe in GROUPES.items():
        p = dossier(role)
        if os.path.isdir(p) and os.path.dirname(os.path.realpath(p)) == os.path.realpath(rac):
            vers = f"{groupe}/{os.path.basename(p)}"
            if os.path.isdir(_abs(vers, rac)) and os.listdir(_abs(vers, rac)):
                erreurs.append(f"{vers} existe déjà : {ROLES[role][1]} laissé en place")
                continue
            prevus.append({"role": role, "libelle": ROLES[role][1], "de": _rel(p, rac), "vers": vers})
    pj = projet(rac)
    a_la_racine = lambda f: f and os.path.dirname(os.path.realpath(f)) == os.path.realpath(rac)
    logo = fichier(pj.get("logo", ""), rac)
    if a_la_racine(logo):
        prevus.append({"role": "logo", "libelle": "Logo", "de": _rel(logo, rac), "vers": "bibliotheque/" + os.path.basename(logo)})
    livre = fichier(pj.get("livre", ""), rac)
    if a_la_racine(livre):
        srcs = next((d["vers"] for d in prevus if d["role"] == "sources"), None) or _rel(dossier("sources"), rac)
        if srcs in ("", "."):
            srcs = "bibliotheque/sources"
        prevus.append({"role": "livre", "libelle": "Livre", "de": _rel(livre, rac), "vers": srcs + "/" + os.path.basename(livre)})
    if appliquer:
        for d in prevus:
            if d["role"] in ("logo", "livre"):
                os.makedirs(os.path.dirname(_abs(d["vers"], rac)), exist_ok=True)
                shutil.move(_abs(d["de"], rac), _abs(d["vers"], rac))
                brut = _lire(os.path.join(rac, "projet.json"), {}); brut[d["role"]] = d["vers"]
                _ecrire(os.path.join(rac, "projet.json"), brut)
                if d["role"] == "livre" and not os.path.isdir(dossier("sources")):
                    memoriser_dossier("sources", os.path.dirname(d["vers"]), rac)
            else:
                deplacer_dossier(d["role"], d["vers"], rac)
        oublier_index(rac)
    return {"deplacements": prevus, "erreurs": erreurs}


def dossier_episodes():
    return dossier("episodes")


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
- Répliques : quand un personnage parle, un plan par réplique avec "qui" (son tag) et, dans "vo", seulement les mots
  prononcés (sans guillemets ni « dit-il ») ; le prompt image le montre en train de parler et "vid_prompt" décrit
  son attitude pendant qu'il parle. Sans "qui", "vo" est lu par le narrateur. Préférer les dialogues à la narration
  chaque fois que la source rapporte des paroles ou un échange.
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
