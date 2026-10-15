#!/usr/bin/env python3
"""MKS Movie Producer — interface web de pilotage (locale).

Lancement : double-clic sur PILOTAGE.bat  ->  http://localhost:8765
Le serveur n'écoute que sur 127.0.0.1 : rien n'est accessible depuis le réseau.
Le projet affiché est le « projet actif » (menu Projet) ; tout son état est recalculé à partir de ses fichiers.
"""
import json, mimetypes, os, re, string, subprocess, sys, threading, time, urllib.parse, uuid, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import contexte as cx

PORT = int(os.environ.get("ATELIER_PORT", "8765"))
EP_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".PNG", ".JPG")
VID_EXT = (".mp4", ".mov", ".webm")
# envoi de fichiers : le premier segment de la destination désigne un rôle (ou son ancien nom de dossier)
ALIAS_ROLES = {"sources": "sources", "characters": "personnages", "personnages": "personnages", "musique": "musique",
               "flow": "images", "images": "images", "bible": "bible"}
JOBS = {}
ETAPES = ["À écrire", "Script écrit", "Fiche prête", "Images en cours", "Prêt à monter", "Monté", "Validé"]


# ---------------------------------------------------------------- épisodes
def chemin_ep(ep):
    if not EP_RE.match(ep):
        raise ValueError("nom d'épisode invalide")
    return cx.dossier("episodes", ep + ".json")


def media_local(ep, k):
    """(url, type) du média d'un plan : dans le dossier des images, sinon n'importe où dans le projet."""
    d = cx.dossier("images", ep)
    for ext in VID_EXT:
        if os.path.exists(os.path.join(d, k + ext)):
            return f"/flow/{ep}/{urllib.parse.quote(k + ext)}", "video"
    for ext in IMG_EXT:
        if os.path.exists(os.path.join(d, k + ext)):
            return f"/flow/{ep}/{urllib.parse.quote(k + ext)}", "image"
    if k:
        p, video = cx.chercher_media(k)
        if p:
            return "/projet/" + urllib.parse.quote(cx._rel(p)), "video" if video else "image"
    return None, None


def fichiers_rendus(langue=None):
    """Rendus de la langue d'origine (racine du dossier des rendus) ou d'une version (sous-dossier <langue>/)."""
    d = cx.dossier("rendus", langue) if langue else cx.dossier("rendus")
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".mp4")) if os.path.isdir(d) else []


def tous_les_rendus():
    """[(chemin relatif au dossier des rendus, langue ou None)]"""
    import langues as lg
    out = [(f, None) for f in fichiers_rendus()]
    for l in lg.versions(cx.projet()):
        out += [(f"{l}/{f}", l) for f in fichiers_rendus(l)]
    return out


def etat_episode(ep, rendus=None):
    e = json.load(open(chemin_ep(ep), encoding="utf-8"))
    plans = [s for s in e["shots"] if not s.get("card")]
    ok = vid = 0
    for s in plans:
        f, t = media_local(ep, s.get("k", ""))
        if f or s.get("img_url") or s.get("vid_url"):
            ok += 1
        if t == "video" or (not f and s.get("vid_url")):
            vid += 1
    mots = sum(len(s.get("vo", "").split()) for s in plans)
    rendus = [f for f in (rendus if rendus is not None else fichiers_rendus())
              if f.startswith(e["id"] + "_") or f.startswith(ep + "_")]
    import langues as lg
    traductions = {}
    for l in lg.versions(cx.projet()):
        et = lg.etat_traduction(e, l)
        traductions[l] = {"ok": et["ok"], "total": et["total"], "a_revoir": len(et["a_revoir"]),
                          "manquantes": len(et["manquantes"]), "complete": et["complete"],
                          "rendus": [f for f in fichiers_rendus(l) if f.startswith(e["id"] + "_") or f.startswith(ep + "_")]}
    return {"ep": ep, "id": e["id"], "title": e.get("title", ""), "plans": len(plans), "medias": ok,
            "videos": vid, "videos_prevues": sum(1 for s in plans if s.get("vid_prompt") or s.get("vid_url")),
            "mots": mots, "minutes": round(mots / 115, 1), "rendus": rendus, "traductions": traductions}


def liste_episodes():
    d = cx.dossier("episodes")
    out, rendus = [], fichiers_rendus()
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".json"):
            try:
                out.append(etat_episode(f[:-5], rendus))
            except Exception as ex:
                out.append({"ep": f[:-5], "erreur": str(ex)})
    return out


def lire_episode(ep):
    import langues as lg
    e = json.load(open(chemin_ep(ep), encoding="utf-8"))
    vs = lg.versions(cx.projet())
    for el in [e] + e["shots"]:                          # état de chaque traduction : ok | manquante | a_revoir | rien
        el["_tr"] = {l: lg.statut(el, l) for l in vs}
    for s in e["shots"]:
        if s.get("card"):
            continue
        f, t = media_local(ep, s.get("k", ""))
        if f:
            s["_media"] = f; s["_type"] = t
        elif s.get("vid_url"):
            s["_media"] = s["vid_url"]; s["_type"] = "video"
        elif s.get("img_url"):
            s["_media"] = s["img_url"]; s["_type"] = "image"
    return e


def sauver_episode(ep, e):
    """L'éditeur signale par « _retouche » les traductions corrigées à la main : elles redeviennent à jour
    vis-à-vis du texte d'origine actuel."""
    from ia import _sauver
    import langues as lg
    for el in [e] + e.get("shots", []):
        for l in el.get("_retouche") or []:
            t = (el.get("versions") or {}).get(l)
            if t is not None:
                for c in [c for c in t if c != "de" and not str(t[c]).strip()]:
                    t.pop(c)
                if any(c != "de" for c in t):
                    t["de"] = lg.empreinte(el)
                else:
                    el["versions"].pop(l)
        if el.get("versions") == {}:
            el.pop("versions")
        for k in [k for k in el if k.startswith("_")]:
            el.pop(k)
    _sauver(ep, e)


# ---------------------------------------------------------------- suivi, plan, assistant
def suivi():
    try:
        return json.load(open(cx.chemin("suivi.json"), encoding="utf-8"))
    except Exception:
        return {}


def plan_brut():
    try:
        return json.load(open(cx.dossier("bible", "plan.json"), encoding="utf-8"))
    except Exception:
        return []


def etape_episode(code, pl=None, rendus=None, sv=None):
    pl = pl or {}
    if not os.path.exists(cx.dossier("episodes", code + ".json")):
        pages = f" (livre p. {pl['pages']})" if pl.get("pages") else ""
        return {"n": 0, "etape": ETAPES[0], "suite": f"Écrire le script{pages} : onglet Nouvel épisode, ou demande-le à Claude.",
                "action": {"type": "nouveau", "ep": code}}
    info = etat_episode(code, rendus)
    fiche = os.path.exists(cx.dossier("fiches", f"{code}_fiche_Flow.txt"))
    valide = (sv if sv is not None else suivi()).get(code, {}).get("valide")
    if info["medias"] < info["plans"]:
        if not fiche:
            return {"n": 1, "etape": ETAPES[1], "suite": "Relire le script dans l'éditeur, puis générer la fiche de prompts.",
                    "action": {"type": "fiche", "ep": code}}
        n = 2 if info["medias"] == 0 else 3
        return {"n": n, "etape": f"{ETAPES[n]} ({info['medias']}/{info['plans']})",
                "suite": f"Générer les {info['plans'] - info['medias']} images manquantes avec la fiche et les ranger dans {rel_win('images')}\\{code}\\. "
                         f"Plans vidéo prévus : {info['videos_prevues']}.", "action": {"type": "fiche", "ep": code}}
    if not info["rendus"]:
        return {"n": 4, "etape": ETAPES[4], "suite": "Toutes les images sont là : lancer le montage.",
                "action": {"type": "monter", "ep": code}}
    if not valide:
        return {"n": 5, "etape": ETAPES[5], "suite": f"Regarder {info['rendus'][-1]} et le valider (ou corriger les plans puis remonter).",
                "action": {"type": "valider", "ep": code}}
    return {"n": 6, "etape": ETAPES[6], "suite": "Épisode terminé.", "action": None}


def plan_complet():
    plan, rendus, sv = plan_brut(), fichiers_rendus(), suivi()
    for p in plan:
        try:
            p.update(etape_episode(p["code"], p, rendus, sv))
        except Exception as ex:
            p.update({"n": 0, "etape": "erreur", "suite": str(ex), "action": None})
    return plan


def regenerer_fiches():
    """Les fiches de prompts contiennent les chemins des images et des références : on les réécrit après un rangement."""
    from fiche import fiche_flow
    d, faites = cx.dossier("fiches"), []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            m = re.match(r"^(.+)_fiche_Flow\.txt$", f)
            if m and os.path.exists(cx.dossier("episodes", m.group(1) + ".json")):
                try:
                    fiche_flow(m.group(1)); faites.append(m.group(1))
                except Exception:
                    pass
    return faites


def rel_win(role):
    return cx._rel(cx.dossier(role)).replace("/", "\\")


def sources():
    d = cx.dossier("sources")
    pj = cx.projet()
    livre = cx.fichier(pj.get("livre", ""))
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p) and not f.startswith("."):
                out.append({"nom": f, "mo": round(os.path.getsize(p) / 1e6, 2), "livre": bool(livre) and os.path.samefile(p, livre)})
    if livre and not any(s["livre"] for s in out):
        out.insert(0, {"nom": cx._rel(livre), "mo": round(os.path.getsize(livre) / 1e6, 2), "livre": True})
    return out


def verifications():
    import shutil
    pj, r = cx.projet(), cx.reglages()
    from cles import etat_cles
    cles = etat_cles(r)
    musiques = [m for m in pj.get("musiques", []) if any(os.path.exists(os.path.join(d, m + ".mp3"))
                                                          for d in (os.path.join(ICI, "musique"), cx.dossier("musique")))]
    try:
        import edge_tts  # noqa
        edge = True
    except Exception:
        edge = False
    v = [
        {"ok": bool(shutil.which("ffmpeg")), "titre": "ffmpeg installé", "aide": "Lancer INSTALLER.bat puis relancer PILOTAGE.bat"},
        {"ok": edge, "titre": "Voix Edge (module edge-tts)", "aide": "Lancer INSTALLER.bat"},
        {"ok": len(musiques) == len(pj.get("musiques", [])), "titre": f"Musiques ({len(musiques)}/{len(pj.get('musiques', []))})", "aide": "Lancer INSTALLER.bat"},
        {"ok": os.path.exists(os.path.join(ICI, "polices", "Cinzel.ttf")), "titre": "Police des titres", "aide": "Lancer INSTALLER.bat"},
        {"ok": bool(sources()), "titre": "Sources du projet (livre, scripts…)", "aide": "Projet › Sources : ajouter les documents"},
    ]
    for p in pj.get("personnages", []):
        if p.get("reference"):
            v.append({"ok": bool(cx.fichier(p["reference"])), "titre": f"Référence : {p['nom']}",
                      "aide": f"Déposer l'image dans {p['reference']}"})
    v.append({"ok": all(cles.get(r["ia"]["par_tache"][t]) for t in r["ia"]["par_tache"]),
              "titre": "Clés IA pour les étapes IA (facultatif)", "aide": "Réglages > Modèles IA"})
    return v


def assistant():
    plan = plan_complet()
    verifs = verifications()
    courant = next((p for p in plan if p["n"] < 6), None)
    a_preparer = not plan or (all(not p.get("resume") for p in plan) and not any(p["n"] > 0 for p in plan))
    if a_preparer:
        pj = cx.projet()
        a_sources = bool(sources())
        courant = {"code": "—", "num": "", "titre": "Préparer le projet", "n": 0,
                   "etape": "Bible et plan à créer" if a_sources else "Sources à ajouter",
                   "suite": ("Générer la bible et le plan des épisodes à partir des sources (IA), ou les écrire dans l'onglet Bible."
                             if a_sources else f"Ajouter le livre, le script ou les documents de « {pj['nom']} » dans Projet › Sources."),
                   "action": {"type": "bible"} if a_sources else {"type": "projet"}}
    par_saison = {}
    for p in plan:
        d = par_saison.setdefault(p["saison"], {"saison": p["saison"], "titre": p.get("titre_saison", ""), "faits": 0, "total": 0})
        d["total"] += 1; d["faits"] += p["n"] == 6
    return {"courant": courant, "suivants": [] if a_preparer else [p for p in plan if p["n"] < 6][:4], "verifications": verifs,
            "saisons": list(par_saison.values()), "valides": sum(p["n"] == 6 for p in plan), "total": len(plan)}


# ---------------------------------------------------------------- projets
def infos_projet():
    if cx.est_projet(cx.racine()):
        cx.reparer_fichiers()
    pj, ps = cx.projet(), cx.poste()
    projets = [dict(x, existe=os.path.isdir(x["chemin"])) for x in ps.get("projets", [])]
    dossiers = {r: cx._rel(cx.dossier(r)) for r in cx.ROLES}
    return {"projet": cx.projet(), "racine": cx.racine(), "projets": projets, "logiciel": cx.NOM_LOGICIEL, "app": ICI,
            "est_projet": cx.est_projet(cx.racine()), "dossiers": dossiers}


def creer_projet(d):
    from logo import logo_pour
    parent = d.get("parent", "").strip()
    if not parent or not os.path.isdir(parent):
        raise ValueError("Dossier parent introuvable")
    rac = os.path.join(parent, d.get("dossier") or d["nom"])
    if os.path.exists(rac) and os.listdir(rac) and not d.get("dans_existant"):
        raise ValueError(f"Le dossier {rac} existe déjà et n'est pas vide")
    for role in ("sources", "bible", "episodes", "personnages", "images", "fiches", "rendus"):
        os.makedirs(cx._abs(cx.DISPOSITION_NOUVEAU[role], rac), exist_ok=True)
    pj = dict(cx.DEFAUT_PROJET)
    pj["dossiers"] = dict(cx.DISPOSITION_NOUVEAU)
    for k in ("nom", "sous_titre", "type", "style_image", "regles_ia", "couleur", "langue"):
        if d.get(k):
            pj[k] = d[k]
    for k in ("saisons", "episodes_par_saison", "duree_min"):
        if d.get(k):
            pj[k] = int(d[k])
    if d.get("voix"):
        pj["voix"] = dict(pj["voix"], nom=d["voix"])
    if d.get("narrateur"):
        pj["personnages"] = [{"tag": "NARRATEUR", "nom": d["narrateur"], "description": d.get("narrateur_desc", d["narrateur"]),
                              "reference": cx.DISPOSITION_NOUVEAU["personnages"] + "/narrateur_reference.png"}]
    pj["logo"] = "bibliotheque/logo.svg"
    cx.sauver_projet(pj, rac)
    open(cx._abs(pj["logo"], rac), "w", encoding="utf-8").write(logo_pour(pj["nom"], pj.get("couleur", "#d8b46a")))
    S, E = pj["saisons"], pj["episodes_par_saison"]
    bible = cx._abs(cx.DISPOSITION_NOUVEAU["bible"], rac)
    if not os.path.exists(os.path.join(bible, "bible.md")):
        open(os.path.join(bible, "bible.md"), "w", encoding="utf-8").write(
            f"# {pj['nom']} — Bible\n\n{pj.get('sous_titre', '')}\n\n## Concept\n\n(à écrire, ou : Assistant > Générer la bible avec l'IA)\n")
    if not os.path.exists(os.path.join(bible, "plan.json")):
        plan = [{"code": f"E{s}{e:02d}", "saison": s, "titre_saison": f"Saison {s}", "num": f"{s}.{e}",
                 "titre": f"Épisode {s}.{e}", "resume": "", "pages": ""} for s in range(1, S + 1) for e in range(1, E + 1)]
        json.dump(plan, open(os.path.join(bible, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cx.definir_projet_actif(rac)
    return rac


def parcourir(c):
    if not c:
        if os.name == "nt":
            lecteurs = [f"{l}:\\" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")]
            return {"chemin": "", "dossiers": lecteurs + [os.path.expanduser("~")], "parent": ""}
        c = os.path.expanduser("~")
    c = os.path.abspath(c)
    try:
        ds = sorted(x for x in os.listdir(c) if os.path.isdir(os.path.join(c, x)) and not x.startswith((".", "$")))
    except Exception:
        ds = []
    parent = os.path.dirname(c) if os.path.dirname(c) != c else ""
    return {"chemin": c, "dossiers": [os.path.join(c, x) for x in ds], "parent": parent, "est_projet": cx.est_projet(c)}


# ---------------------------------------------------------------- tâches de fond
def lancer(cmd, args):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "cmd": cmd, "args": args, "etat": "en cours", "log": "", "debut": time.time(), "projet": cx.racine()}
    JOBS[jid] = job

    def tourner():
        env = dict(os.environ, PYTHONIOENCODING="utf-8", STUDIO_PROJET=job["projet"])
        p = subprocess.Popen([sys.executable, os.path.join(ICI, "atelier.py"), cmd] + args, cwd=ICI,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", env=env)
        for ligne in p.stdout:
            job["log"] += ligne
        p.wait()
        job["etat"] = "terminé" if p.returncode == 0 and "!! Erreur" not in job["log"] else "erreur"
        job["fin"] = time.time()

    threading.Thread(target=tourner, daemon=True).start()
    return job


def essai_voix(c):
    """Court extrait d'une voix Edge TTS (pour choisir la voix d'une langue avant de monter un épisode)."""
    import hashlib
    nom, debit, hauteur = (c.get("nom") or "").strip(), (c.get("debit") or "+0%").strip(), (c.get("hauteur") or "+0Hz").strip()
    texte = (c.get("texte") or "").strip()[:600]
    if not re.match(r"^[a-z]{2,3}-[A-Za-z]{2,4}-[A-Za-z]+Neural$", nom) or not texte:
        raise ValueError("Voix ou texte invalide")
    if not re.match(r"^[+-]\d{1,3}%$", debit) or not re.match(r"^[+-]\d{1,3}Hz$", hauteur):
        raise ValueError("Débit (ex. -10%) ou hauteur (ex. -4Hz) invalide")
    d = os.path.join(ICI, "cache", "essais"); os.makedirs(d, exist_ok=True)
    f = hashlib.sha1(f"{nom}|{debit}|{hauteur}|{texte}".encode("utf-8")).hexdigest()[:12] + ".mp3"
    if not os.path.exists(os.path.join(d, f)):
        txt = os.path.join(d, f + ".txt"); open(txt, "w", encoding="utf-8").write(texte)
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", nom, f"--rate={debit}", f"--pitch={hauteur}",
                            "-f", txt, "--write-media", os.path.join(d, f)], capture_output=True, text=True, timeout=60)
        os.remove(txt)
        if r.returncode != 0:
            raise RuntimeError("Voix Edge indisponible (connexion internet ? nom de voix ?) : " + r.stderr[-200:])
    return {"url": "/essai/" + f}


# ---------------------------------------------------------------- serveur HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def envoyer(self, code, corps, ctype="application/json; charset=utf-8"):
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps, ensure_ascii=False)
        if isinstance(corps, str):
            corps = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def fichier(self, chemin, base):
        chemin = os.path.realpath(chemin)
        if not chemin.startswith(os.path.realpath(base) + os.sep) or not os.path.isfile(chemin):
            return self.envoyer(404, {"erreur": "introuvable"})
        taille = os.path.getsize(chemin)
        ctype = mimetypes.guess_type(chemin)[0] or "application/octet-stream"
        if chemin.endswith(".svg"):
            ctype = "image/svg+xml"
        debut, fin = 0, taille - 1
        plage = self.headers.get("Range")
        if plage:
            m = re.match(r"bytes=(\d*)-(\d*)", plage)
            if m:
                debut = int(m.group(1) or 0)
                fin = int(m.group(2)) if m.group(2) else taille - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(fin - debut + 1))
        self.end_headers()
        with open(chemin, "rb") as f:
            f.seek(debut)
            reste = fin - debut + 1
            while reste > 0:
                bloc = f.read(min(1 << 20, reste))
                if not bloc:
                    break
                try:
                    self.wfile.write(bloc)
                except (BrokenPipeError, ConnectionResetError):
                    return
                reste -= len(bloc)

    def corps(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = urllib.parse.unquote(u.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if p in ("/", "/index.html"):
                return self.envoyer(200, open(os.path.join(ICI, "web", "index.html"), encoding="utf-8").read(),
                                    "text/html; charset=utf-8")
            if p == "/api/projet":
                return self.envoyer(200, infos_projet())
            if p == "/api/logo":
                pj = cx.projet()
                f = cx.fichier(pj.get("logo") or "logo.svg")
                if not f:
                    from logo import logo_pour
                    return self.envoyer(200, logo_pour(pj["nom"], pj.get("couleur", "#d8b46a")), "image/svg+xml")
                return self.fichier(f, cx.racine())
            if p == "/api/episodes":
                return self.envoyer(200, liste_episodes())
            if p.startswith("/api/episode/"):
                return self.envoyer(200, lire_episode(p.split("/")[-1]))
            if p == "/api/reglages":
                from cles import TACHES
                r = cx.reglages(); r["_taches"] = TACHES
                return self.envoyer(200, r)
            if p == "/api/cles":
                from cles import etat_cles
                return self.envoyer(200, etat_cles(cx.reglages()))
            if p == "/api/bible":
                try:
                    t = open(cx.dossier("bible", "bible.md"), encoding="utf-8").read()
                except Exception:
                    t = ""
                return self.envoyer(200, {"texte": t})
            if p == "/api/plan":
                return self.envoyer(200, plan_complet())
            if p == "/api/assistant":
                return self.envoyer(200, assistant())
            if p == "/api/organisation":
                return self.envoyer(200, cx.organisation())
            if p == "/api/sources":
                return self.envoyer(200, sources())
            if p == "/api/parcourir":
                return self.envoyer(200, parcourir(q.get("chemin", [""])[0]))
            if p == "/api/rendus":
                import langues as lg
                eps = {e["ep"]: e for e in liste_episodes() if "erreur" not in e}
                out = []
                for f, langue in tous_les_rendus():
                    nom = f.split("/")[-1]
                    ep = next((k for k, e in eps.items() if nom.startswith(e["id"] + "_") or nom.startswith(k + "_")), None)
                    st = os.stat(cx.dossier("rendus", *f.split("/")))
                    srt = cx.dossier("rendus", *f.split("/"))[:-4] + ".srt"
                    out.append({"f": f, "ep": ep, "id": eps[ep]["id"] if ep else "", "titre": eps[ep]["title"] if ep else "",
                                "langue": langue or lg.source(cx.projet()), "srt": f[:-4] + ".srt" if os.path.exists(srt) else "",
                                "mo": round(st.st_size / 1e6, 1), "date": time.strftime("%d/%m %H:%M", time.localtime(st.st_mtime))})
                return self.envoyer(200, out)
            if p == "/api/langues":
                import langues as lg
                pj = cx.projet()
                return self.envoyer(200, {"source": lg.source(pj), "versions": lg.versions(pj), "noms": lg.NOMS,
                                          "voix": lg.VOIX_PROPOSEES, "voix_defaut": lg.VOIX_DEFAUT})
            if p.startswith("/essai/"):
                return self.fichier(os.path.join(ICI, "cache", "essais", p.split("/")[-1]), os.path.join(ICI, "cache", "essais"))
            if p == "/api/jobs":
                return self.envoyer(200, sorted(JOBS.values(), key=lambda j: -j["debut"])[:20])
            if p.startswith("/api/job/"):
                return self.envoyer(200, JOBS.get(p.split("/")[-1], {"erreur": "inconnu"}))
            if p.startswith("/api/fiche/"):
                from fiche import fiche_flow
                chemin = fiche_flow(p.split("/")[-1])
                return self.envoyer(200, {"chemin": chemin, "texte": open(chemin, encoding="utf-8-sig").read()})
            if p == "/api/livre":
                from ia import lire_livre, nb_pages_livre
                if "pages" in q:
                    return self.envoyer(200, {"texte": lire_livre(q["pages"][0])})
                return self.envoyer(200, {"pages": nb_pages_livre()})
            if p.startswith("/flow/"):
                return self.fichier(cx.dossier("images", *p.split("/")[2:]), cx.dossier("images"))
            if p.startswith("/rendus/"):
                return self.fichier(cx.dossier("rendus", *p.split("/")[2:]), cx.dossier("rendus"))
            if p.startswith("/api/aide/"):
                nom = {"installation": "MANUEL_INSTALLATION.md", "utilisation": "MANUEL_UTILISATION.md"}.get(p.split("/")[-1])
                if not nom:
                    return self.envoyer(404, {"erreur": "manuel inconnu"})
                return self.envoyer(200, {"texte": open(os.path.join(ICI, "docs", nom), encoding="utf-8").read()})
            if p.startswith("/aide/"):
                return self.fichier(os.path.join(ICI, "docs", *p.split("/")[2:]), os.path.join(ICI, "docs"))
            if p.startswith("/projet/"):
                return self.fichier(cx.chemin(*p.split("/")[2:]), cx.racine())
            return self.envoyer(404, {"erreur": "introuvable"})
        except Exception as ex:
            return self.envoyer(500, {"erreur": str(ex)})

    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)
        p = urllib.parse.unquote(u.path)
        try:
            if p.startswith("/api/episode/"):
                sauver_episode(p.split("/")[-1], self.corps())
                return self.envoyer(200, {"ok": True})
            if p == "/api/projet":
                pj = self.corps()
                cx.sauver_projet(pj)
                cx.definir_projet_actif(cx.racine())
                return self.envoyer(200, {"ok": True})
            if p == "/api/reglages":
                r = self.corps(); r.pop("_taches", None)
                cx.sauver_reglages(r)
                return self.envoyer(200, {"ok": True})
            if p == "/api/bible":
                open(cx.dossier("bible", "bible.md", creer=True), "w", encoding="utf-8").write(self.corps()["texte"])
                return self.envoyer(200, {"ok": True})
            if p == "/api/fichier":
                dest = urllib.parse.parse_qs(u.query)["dest"][0].replace("\\", "/").lstrip("/")
                parties = [x for x in dest.split("/") if x]
                if ".." in parties or not parties:
                    return self.envoyer(400, {"erreur": "destination non autorisée"})
                if len(parties) == 1 and re.match(r"^logo\.(svg|png|jpg|jpeg|webp)$", parties[0]):
                    cible = cx.chemin(parties[0])
                elif len(parties) > 1 and parties[0].lower() in ALIAS_ROLES:
                    cible = cx.dossier(ALIAS_ROLES[parties[0].lower()], *parties[1:], creer=True)
                else:
                    return self.envoyer(400, {"erreur": "destination non autorisée"})
                os.makedirs(os.path.dirname(cible), exist_ok=True)
                n = int(self.headers.get("Content-Length", 0))
                with open(cible, "wb") as f:
                    while n > 0:
                        bloc = self.rfile.read(min(1 << 20, n))
                        if not bloc:
                            break
                        f.write(bloc); n -= len(bloc)
                if len(parties) == 1:
                    pj = cx.projet(); pj["logo"] = parties[0]; cx.sauver_projet(pj)
                cx.oublier_index()
                return self.envoyer(200, {"ok": True, "chemin": cible, "rel": cx._rel(cible)})
            return self.envoyer(404, {"erreur": "introuvable"})
        except Exception as ex:
            return self.envoyer(500, {"erreur": str(ex)})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            c = self.corps()
            if p == "/api/action":
                if c.get("cmd") not in ("monter", "etat", "fiche", "ecrire", "prompts", "verifier", "bible", "exporter", "traduire"):
                    return self.envoyer(400, {"erreur": "commande inconnue"})
                args = [str(a) for a in c.get("args", [])]
                if c["cmd"] not in ("bible", "exporter") and args and not EP_RE.match(args[0]):
                    return self.envoyer(400, {"erreur": "épisode invalide"})
                import langues as lg
                langue = args[1] if c["cmd"] == "traduire" and len(args) > 1 else (
                    args[args.index("--langue") + 1] if "--langue" in args[:-1] else None)
                if (c["cmd"] == "traduire" and not langue) or (langue and not lg.CODE_RE.match(langue)):
                    return self.envoyer(400, {"erreur": "langue invalide"})
                return self.envoyer(200, lancer(c["cmd"], args))
            if p == "/api/projet/ouvrir":
                rac = os.path.abspath(c["chemin"].strip().strip('"'))
                if not os.path.isdir(rac):
                    return self.envoyer(400, {"erreur": "Dossier introuvable"})
                if not cx.est_projet(rac):
                    if not c.get("initialiser"):
                        return self.envoyer(200, {"ok": False, "a_initialiser": True, "chemin": rac})
                    pj = dict(cx.DEFAUT_PROJET, nom=os.path.basename(rac))
                    cx.sauver_projet(pj, rac)
                cx.definir_projet_actif(rac)
                return self.envoyer(200, {"ok": True, "chemin": rac})
            if p == "/api/organisation":
                if c.get("vers"):
                    rel = cx.deplacer_dossier(c["role"], c["vers"])
                else:
                    rel = cx.definir_dossier(c["role"], c["chemin"])
                regenerer_fiches()
                return self.envoyer(200, {"ok": True, "chemin": rel, "organisation": cx.organisation()})
            if p == "/api/organisation/ranger":
                r = cx.ranger_racine(appliquer=bool(c.get("appliquer")))
                if c.get("appliquer"):
                    r["fiches"] = regenerer_fiches()
                return self.envoyer(200, dict(r, organisation=cx.organisation()))
            if p == "/api/organisation/rechercher":
                return self.envoyer(200, {"ok": True, "trouves": cx.rechercher(), "organisation": cx.organisation()})
            if p == "/api/projet/nouveau":
                return self.envoyer(200, {"ok": True, "chemin": creer_projet(c)})
            if p == "/api/projet/oublier":
                d = cx.poste()
                d["projets"] = [x for x in d.get("projets", []) if x["chemin"] != c["chemin"]]
                cx.sauver_poste(d)
                return self.envoyer(200, {"ok": True})
            if p == "/api/projet/logo":
                from logo import logo_pour, logo_generique
                pj = cx.projet()
                svg = logo_generique(pj["nom"], pj.get("couleur", "#d8b46a")) if c.get("generique") else logo_pour(pj["nom"], pj.get("couleur", "#d8b46a"))
                cible = cx.fichier(pj.get("logo", "")) if (pj.get("logo") or "").endswith(".svg") else ""
                cible = cible or cx.chemin("logo.svg")
                open(cible, "w", encoding="utf-8").write(svg)
                pj["logo"] = cx._rel(cible); cx.sauver_projet(pj)
                return self.envoyer(200, {"ok": True})
            if p == "/api/cle":
                from cles import ecrire_cle, profil, compte
                pr = profil(cx.reglages(), pid=c["profil"])
                ou = ecrire_cle(pr["id"], c.get("cle", "").strip())
                if c.get("partager"):
                    ecrire_cle(compte(pr), c.get("cle", "").strip())
                return self.envoyer(200, {"ok": True, "ou": ou})
            if p == "/api/test_ia":
                import ia
                t0 = time.time()
                rep = ia.appeler("Réponds en un seul mot.", "Dis simplement : OK", max_tokens=20, pid=c["profil"])
                return self.envoyer(200, {"ok": True, "reponse": rep.strip()[:80], "secondes": round(time.time() - t0, 1)})
            if p == "/api/voix/essai":
                return self.envoyer(200, essai_voix(c))
            if p == "/api/valider":
                d = suivi()
                d.setdefault(c["ep"], {})["valide"] = bool(c.get("valide", True))
                d[c["ep"]]["date"] = time.strftime("%Y-%m-%d %H:%M")
                json.dump(d, open(cx.chemin("suivi.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                return self.envoyer(200, {"ok": True})
            if p == "/api/ouvrir":
                nom = c.get("dossier", "")
                cible = {"flow": "images"}.get(nom, nom)
                if cible == "projet" or cible in cx.ROLES:
                    d = cx.racine() if cible == "projet" else cx.dossier(cible, creer=True)
                    if sys.platform == "win32":
                        os.startfile(d)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", d])
                    else:
                        subprocess.Popen(["xdg-open", d])
                return self.envoyer(200, {"ok": cible == "projet" or cible in cx.ROLES})
            return self.envoyer(404, {"erreur": "introuvable"})
        except Exception as ex:
            return self.envoyer(500, {"erreur": str(ex)})


if __name__ == "__main__":
    fait = cx.migrer()
    if fait:
        print("Migration vers le format projet :", ", ".join(fait))
    if cx.est_projet(cx.racine()):
        cx.rechercher()           # dossiers et fichiers déplacés depuis la dernière session
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"{cx.NOM_LOGICIEL} — projet « {cx.projet()['nom']} » ({cx.racine()})")
    print(f"Interface : {url}  (laisser cette fenêtre ouverte, Ctrl+C pour arrêter)")
    if "--sans-navigateur" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    srv.serve_forever()
