#!/usr/bin/env python3
"""MKS Movie Producer — étapes « IA » : bible et plan, écriture d'épisodes, réécriture des prompts, relecture des images.

Chaque étape utilise le profil de modèle choisi dans Réglages (reglages.json > ia > par_tache) :
Claude (API Anthropic) ou tout service compatible OpenAI (OpenAI, OpenRouter, Mistral, Gemini, Ollama local…).
Les clés sont gérées par cles.py (Gestionnaire d'identification Windows), jamais dans les fichiers du projet.
"""
import base64, json, os, re, shutil, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from contexte import projet, chemin, dossier, fichier, reglages, regles_ia, remplacer_tags


# ---------------------------------------------------------------- appel modèle
def appeler(systeme, message, images=None, max_tokens=16000, tache=None, pid=None):
    """images : liste de chemins d'images à joindre (vision). tache : ecrire | prompts | verifier."""
    from cles import profil, lire_cle
    conf = profil(reglages(), tache, pid)
    four = conf["fournisseur"]
    cle = lire_cle(conf)
    if not cle and not conf.get("sans_cle"):
        raise RuntimeError(f"Clé API absente pour « {conf['nom']} » : renseigne-la dans Réglages.")
    images = images or []

    def b64(p):
        ext = os.path.splitext(p)[1].lower().strip(".")
        mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
        return mt, base64.b64encode(open(p, "rb").read()).decode()

    if four == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=cle)
        contenu = []
        for p in images:
            mt, d = b64(p)
            contenu.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": d}})
        contenu.append({"type": "text", "text": message})
        texte = []
        with client.messages.stream(model=conf["modele"], max_tokens=max_tokens, system=systeme,
                                    messages=[{"role": "user", "content": contenu}]) as flux:
            for morceau in flux.text_stream:
                texte.append(morceau)
        return "".join(texte)

    if four == "openai_compatible":
        from openai import OpenAI
        client = OpenAI(api_key=cle or "local", base_url=conf.get("url_base"))
        contenu = [{"type": "text", "text": message}]
        for p in images:
            mt, d = b64(p)
            contenu.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{d}"}})
        r = client.chat.completions.create(model=conf["modele"], max_tokens=max_tokens,
                                           messages=[{"role": "system", "content": systeme},
                                                     {"role": "user", "content": contenu}])
        return r.choices[0].message.content

    raise RuntimeError(f"Fournisseur inconnu : {four}")


def extraire_json(texte):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texte, re.S)
    brut = m.group(1) if m else texte[texte.find("{"): texte.rfind("}") + 1]
    return json.loads(brut)


# ---------------------------------------------------------------- sources du projet
EXT_TEXTE = (".txt", ".md", ".srt", ".fountain", ".json", ".csv")


def chemin_livre():
    pj = projet()
    if pj.get("livre"):
        f = fichier(pj["livre"])
        if f:
            return f
    for d in (dossier("sources"), chemin()):
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(".pdf"):
                    return os.path.join(d, f)
    return ""


def lire_livre(pages):
    """pages : '45-52' (numéros de pages du PDF, à partir de 1)."""
    from pypdf import PdfReader
    pdf = chemin_livre()
    if not pdf:
        raise RuntimeError("Aucun livre PDF dans le projet (Projet > Sources).")
    lecteur = PdfReader(pdf)
    pages = pages.replace("–", "-").replace("—", "-").replace(" ", "")
    a, b = (int(x) for x in pages.split("-")) if "-" in pages else (int(pages), int(pages))
    b = min(b, len(lecteur.pages))
    return "\n".join((lecteur.pages[i].extract_text() or "") for i in range(a - 1, b))


def nb_pages_livre():
    from pypdf import PdfReader
    pdf = chemin_livre()
    return len(PdfReader(pdf).pages) if pdf else 0


def lire_document(p):
    ext = os.path.splitext(p)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
    if ext == ".docx":
        import zipfile
        x = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8", "ignore")
        return re.sub(r"<[^>]+>", " ", x.replace("</w:p>", "\n"))
    if ext in EXT_TEXTE:
        return open(p, encoding="utf-8", errors="ignore").read()
    return ""


def texte_sources(limite=180000):
    """Texte de tous les documents de sources/ (livre, scripts, notes), tronqué à `limite` caractères."""
    morceaux, d = [], dossier("sources")
    fichiers = [chemin_livre()] if chemin_livre() else []
    if os.path.isdir(d):
        fichiers += [os.path.join(d, f) for f in sorted(os.listdir(d)) if not f.startswith(".") and os.path.join(d, f) not in fichiers]
    for f in fichiers:
        try:
            t = lire_document(f)
        except Exception as ex:
            t = f"(illisible : {ex})"
        if t.strip():
            morceaux.append(f"=== {os.path.basename(f)} ===\n{t}")
    tout = "\n\n".join(morceaux)
    return tout[:limite] + ("\n[… tronqué …]" if len(tout) > limite else "")


# ---------------------------------------------------------------- bible et plan
def generer_bible(consignes=""):
    """Écrit bible/bible.md et bible/plan.json à partir des sources et de la structure du projet."""
    pj = projet()
    S, E = int(pj.get("saisons", 1)), int(pj.get("episodes_par_saison", 7))
    systeme = (f"Tu es showrunner. Tu prépares la bible et le plan de « {pj['nom']} » ({pj.get('sous_titre', '')}), "
               f"{S} saison(s) × {E} épisode(s) de {pj.get('duree_min', 7)} minutes. Tu restes fidèle aux sources. "
               "Réponds UNIQUEMENT avec un JSON : {\"bible_md\": \"...markdown...\", \"plan\": [ {\"code\":\"E101\", "
               "\"saison\":1, \"titre_saison\":\"...\", \"num\":\"1.1\", \"titre\":\"...\", \"resume\":\"...\", \"pages\":\"5-6\"} ] }. "
               "La bible contient : concept, ton, règles éditoriales, direction artistique (prompt de style en anglais), "
               "personnages récurrents (apparence précise), lieux, architecture des saisons, pipeline. "
               f"Le plan contient exactement {S * E} épisodes, codes E<saison><numéro sur 2 chiffres>.")
    msg = f"Consignes : {consignes or 'aucune'}\n\nSOURCES DU PROJET :\n{texte_sources()}"
    r = extraire_json(appeler(systeme, msg, tache="ecrire", max_tokens=32000))
    dossier("bible", creer=True)
    for f in ("bible.md", "plan.json"):
        if os.path.exists(dossier("bible", f)):
            shutil.copy(dossier("bible", f), dossier("bible", f + ".ancien"))
    open(dossier("bible", "bible.md"), "w", encoding="utf-8").write(r["bible_md"])
    json.dump(r["plan"], open(dossier("bible", "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"episodes": len(r["plan"])}


# ---------------------------------------------------------------- épisodes
def _exemple():
    """Un épisode existant sert de modèle de format et de ton."""
    d = dossier("episodes")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d), reverse=True):
            if f.endswith(".json"):
                e = json.load(open(os.path.join(d, f), encoding="utf-8"))
                if len(e.get("shots", [])) > 10:
                    for s in e["shots"]:
                        s.pop("img_url", None); s.pop("vid_url", None)
                    return json.dumps(e, ensure_ascii=False, indent=1)
    return "(pas encore d'épisode : respecte le format décrit)"


def _bible():
    try:
        return open(dossier("bible", "bible.md"), encoding="utf-8").read()[:40000]
    except Exception:
        return ""


def ecrire_episode(ep, titre, pages="", consignes=""):
    """Écrit episodes/<ep>.json (pages du livre si fournies, sinon les sources). Sauvegarde l'ancienne version."""
    texte = lire_livre(pages) if pages and chemin_livre() else texte_sources(60000)
    msg = (f"Écris l'épisode {ep} intitulé « {titre} ».\n\nBible de la série :\n{_bible()}\n\n"
           f"Exemple d'épisode existant (format et ton) :\n{_exemple()}\n\n"
           f"Passage à adapter{' (pages ' + pages + ')' if pages else ''} :\n{texte}\n\nConsignes supplémentaires : {consignes or 'aucune'}")
    e = extraire_json(appeler(regles_ia(ep), msg, tache="ecrire"))
    e["id"] = e.get("id") or ep
    e.setdefault("title", titre)
    _sauver(ep, e)
    return e


def ameliorer_prompts(ep, consignes=""):
    """Réécrit les prompts image d'un épisode (même structure, mêmes clés)."""
    e = json.load(open(dossier("episodes", ep + ".json"), encoding="utf-8"))
    msg = (f"Réécris uniquement les champs \"p\" (et \"vid_prompt\" s'il y en a) de cet épisode pour qu'ils respectent "
           f"parfaitement la direction artistique. Ne change ni les clés ni la narration.\nConsignes : {consignes or 'aucune'}\n\n"
           f"Bible :\n{_bible()[:15000]}\n\n" + json.dumps(e, ensure_ascii=False, indent=1))
    e2 = extraire_json(appeler(regles_ia(ep), msg, tache="prompts"))
    _garder_traductions(e, e2)
    _sauver(ep, e2)
    return e2


GARDES = ("media", "voix_fichier", "mus_off", "fx", "qui", "amb", "amb_vol", "sfx", "sfx_t", "sfx_vol", "son_video", "son_video_vol", "img_url", "vid_url")


def _garder_traductions(avant, apres):
    """Le modèle réécrit tout le JSON : on recolle les traductions, les choix de la vue Studio (média, voix importée)
    et les champs de production (répliques, sons, médias hébergés) qu'il aurait omis (même clé de plan)."""
    if avant.get("versions") and not apres.get("versions"):
        apres["versions"] = avant["versions"]
    par_cle = {s.get("k") or f"#{i}": s for i, s in enumerate(avant.get("shots", []))}
    for i, s in enumerate(apres.get("shots", [])):
        a = par_cle.get(s.get("k") or f"#{i}")
        if a and a.get("versions") and not s.get("versions"):
            s["versions"] = a["versions"]
        for c in GARDES:                                    # choix du Studio, répliques, sons, médias hébergés
            if a and c in a and c not in s:
                s[c] = a[c]


# ---------------------------------------------------------------- versions linguistiques
def traduire_episode(ep, langue, consignes="", tout=False):
    """Traduit (adapte) les textes d'un épisode dans une langue du projet : narration, mots à l'écran, cartons, titre.
    Incrémental : seuls les éléments sans traduction, ou dont le texte d'origine a changé, sont envoyés au modèle."""
    import langues as lg
    pj = projet()
    if langue not in lg.versions(pj):
        raise RuntimeError(f"Langue « {langue} » non déclarée : ajoute-la dans Projet > Versions linguistiques.")
    e = json.load(open(dossier("episodes", ep + ".json"), encoding="utf-8"))
    elements = [e] + e.get("shots", [])
    a_faire = [i for i, el in enumerate(elements) if lg.statut(el, langue) in (("ok", "manquante", "a_revoir") if tout else ("manquante", "a_revoir"))]
    if not a_faire:
        print(f"{ep} : traduction {langue} déjà à jour.", file=sys.stderr, flush=True)
        return lg.etat_traduction(e, langue)
    cible, origine = lg.nom_langue(langue), lg.nom_langue(lg.source(pj))
    titre_serie = (lg.versions(pj)[langue] or {}).get("titre") or ""
    lot = []
    for i in a_faire:
        el = elements[i]
        if i == 0:
            lot.append({"i": 0, "type": "titre de l'épisode", "title": el.get("title", "")})
        elif el.get("card") is not None:
            lot.append({"i": i, "type": "carton", "card": el.get("card", ""), "sub": el.get("sub", "")})
        else:
            d = {"i": i, "type": "plan", "vo": el.get("vo", "")}
            if el.get("qui"):
                d["type"] = f"réplique de {el['qui']} (paroles prononcées, à garder au style direct)"
            if el.get("title"):
                d["title"] = el["title"]
            lot.append(d)
    deja = {}                                   # traductions existantes : cohérence des noms et du vocabulaire
    for el in elements:
        t = (el.get("versions") or {}).get(langue)
        if t and t.get("vo"):
            deja[el.get("vo", "")[:120]] = t["vo"][:120]
        if len(deja) >= 12:
            break
    systeme = (f"Tu es adaptateur de voix off pour la série « {pj['nom']} ». Tu traduis du {origine} vers le {cible} "
               f"des textes destinés à être LUS À VOIX HAUTE par un narrateur, sur des images déjà montées.\n"
               f"Règles :\n- Garde le sens, le ton, le registre et la personne de narration (un récit à la première personne le reste).\n"
               f"- Longueur proche de l'original (±10 %) : chaque plan dure le temps de sa narration.\n"
               f"- Phrases naturelles et rythmées pour l'oral dans la langue cible, pas de traduction mot à mot.\n"
               f"- Les noms propres, titres bibliques et termes récurrents restent cohérents d'un plan à l'autre ; "
               f"cite les Écritures selon une version reconnue dans la langue cible quand le texte en cite une.\n"
               f"- « title » : mot ou courte expression affiché à l'écran, en MAJUSCULES, aussi court que l'original.\n"
               f"- Cartons : « card » est le nom de la série en majuscules"
               f"{(' (titre dans cette langue : ' + titre_serie + ')') if titre_serie else ''}, ou l'équivalent de « À SUIVRE » ; "
               f"« sub » suit le format « Saison X · Épisode Y — Titre » traduit.\n"
               f"Réponds UNIQUEMENT avec un JSON : {{\"elements\": [{{\"i\": 3, \"vo\": \"…\", \"title\": \"…\"}}, "
               f"{{\"i\": 2, \"card\": \"…\", \"sub\": \"…\"}}, {{\"i\": 0, \"title\": \"…\"}}]}} "
               f"avec exactement les mêmes « i » et les mêmes champs que l'entrée.")
    msg = (f"Contexte de la série (bible, extrait) :\n{_bible()[:12000]}\n\n"
           + (f"Traductions déjà validées (pour la cohérence) :\n{json.dumps(deja, ensure_ascii=False, indent=1)}\n\n" if deja else "")
           + f"Consignes supplémentaires : {consignes or 'aucune'}\n\n"
           f"Éléments à traduire ({len(lot)}) :\n{json.dumps(lot, ensure_ascii=False, indent=1)}")
    print(f"{ep} : {len(lot)} élément(s) à traduire en {cible}…", file=sys.stderr, flush=True)
    r = extraire_json(appeler(systeme, msg, tache="ecrire"))
    recus = {int(x["i"]): x for x in r.get("elements", []) if "i" in x}
    for i in a_faire:
        if i in recus:
            lg.poser(elements[i], langue, recus[i])
    _sauver(ep, e)
    et = lg.etat_traduction(e, langue)
    manque = len(et["manquantes"]) + len(et["a_revoir"])
    print(f"{ep} : {et['ok']}/{et['total']} élément(s) traduits en {cible}"
          + (f" — {manque} restant(s), relance la traduction." if manque else "."), file=sys.stderr, flush=True)
    return et


def verifier_images(ep):
    """Fait relire chaque image par le modèle (vision). Rapport dans Flow/<ep>/verification.txt."""
    from moteur import trouver_media
    pj = projet()
    e = json.load(open(dossier("episodes", ep + ".json"), encoding="utf-8"))
    lignes = []
    for s in e["shots"]:
        if s.get("card"):
            continue
        src, video = trouver_media(ep, s, None, telecharger=False)
        if not src or video or str(src).startswith("http"):
            lignes.append(f"{s.get('k')} : {'vidéo' if video else 'absente'}"); continue
        p, _ = remplacer_tags(s.get("p", ""), pj)
        rep = appeler("Tu es directeur artistique. Réponds en une ligne en français : « OK » ou « À REFAIRE : raison ».",
                      f"Narration : {s.get('vo')}\nPrompt demandé : {p}\nStyle de la série : {pj.get('style_image')}\n"
                      f"L'image correspond-elle à la scène et à la direction artistique (pas de texte parasite, "
                      f"pas de visage déformé) ?", images=[src], max_tokens=300, tache="verifier")
        lignes.append(f"{s.get('k')} : {rep.strip()}")
        print(lignes[-1], file=sys.stderr, flush=True)
    out = dossier("images", ep, "verification.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8-sig").write("\r\n".join(lignes))
    return out


def _sauver(ep, e):
    d = dossier("episodes", creer=True)
    os.makedirs(os.path.join(d, "anciennes"), exist_ok=True)
    p = os.path.join(d, ep + ".json")
    if os.path.exists(p):
        n = 1
        while os.path.exists(os.path.join(d, "anciennes", f"{ep}_{n}.json")):
            n += 1
        shutil.copy(p, os.path.join(d, "anciennes", f"{ep}_{n}.json"))
    json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
