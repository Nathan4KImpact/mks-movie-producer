#!/usr/bin/env python3
"""MKS Movie Producer — versions linguistiques d'une série.

Une seule série, plusieurs langues : les plans (clés, images, vidéos, mouvements, musiques) sont communs ;
seuls les textes changent (narration, mot à l'écran, cartons, titre de l'épisode).

projet.json :
    "langue": "fr",                                   langue d'origine des scripts
    "versions": {"en": {"titre": "…", "voix": {"nom": "en-US-AndrewNeural", "debit": "-10%", "hauteur": "-4Hz"}}}

épisode (E104.json) — la traduction vit à côté du texte d'origine :
    {"id": "S1E04", "title": "…", "versions": {"en": {"title": "…", "de": "a1b2c3d4"}},
     "shots": [{"k": "E104-01", "vo": "…", "title": "…", "versions": {"en": {"vo": "…", "title": "…", "de": "…"}}},
               {"card": "…", "sub": "…", "versions": {"en": {"card": "…", "sub": "…", "de": "…"}}}]}

« de » est l'empreinte du texte d'origine au moment de la traduction : si la narration d'origine change ensuite,
la traduction est signalée « à revoir » et la prochaine traduction ne refait que ces plans-là.
"""
import copy, hashlib, re

NOMS = {"fr": "français", "en": "anglais", "es": "espagnol", "de": "allemand", "it": "italien", "pt": "portugais",
        "nl": "néerlandais", "ar": "arabe", "sw": "swahili", "ln": "lingala", "zh": "chinois", "ja": "japonais",
        "ko": "coréen", "ru": "russe", "pl": "polonais", "ro": "roumain", "hi": "hindi", "id": "indonésien"}

VOIX_PROPOSEES = {
    "fr": ["fr-FR-HenriNeural", "fr-FR-RemyMultilingualNeural", "fr-FR-DeniseNeural", "fr-FR-VivienneMultilingualNeural",
           "fr-FR-EloiseNeural", "fr-CA-AntoineNeural", "fr-CA-JeanNeural", "fr-CA-ThierryNeural", "fr-CA-SylvieNeural",
           "fr-BE-GerardNeural", "fr-BE-CharlineNeural", "fr-CH-FabriceNeural", "fr-CH-ArianeNeural"],
    "en": ["en-US-AndrewNeural", "en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-BrianNeural", "en-US-EricNeural",
           "en-US-RogerNeural", "en-GB-RyanNeural", "en-GB-ThomasNeural", "en-AU-WilliamNeural",
           "en-US-JennyNeural", "en-US-AriaNeural", "en-US-EmmaNeural", "en-US-AnaNeural", "en-GB-SoniaNeural",
           "en-GB-LibbyNeural", "en-GB-MaisieNeural"],
    "es": ["es-ES-AlvaroNeural", "es-MX-JorgeNeural", "es-ES-ElviraNeural", "es-MX-DaliaNeural"],
    "de": ["de-DE-ConradNeural", "de-DE-KillianNeural", "de-DE-KatjaNeural", "de-DE-AmalaNeural"],
    "pt": ["pt-BR-AntonioNeural", "pt-PT-DuarteNeural", "pt-BR-FranciscaNeural", "pt-PT-RaquelNeural"],
    "it": ["it-IT-DiegoNeural", "it-IT-ElsaNeural", "it-IT-IsabellaNeural"],
}
CODE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
CHAMPS_PLAN = ("vo", "title")
CHAMPS_CARTON = ("card", "sub")


def nom_langue(code):
    return NOMS.get(code.split("-")[0], code)


def source(pj):
    return (pj.get("langue") or "fr").strip()


def versions(pj):
    """Langues cibles déclarées dans le projet (hors langue d'origine)."""
    return {k: v for k, v in (pj.get("versions") or {}).items() if k != source(pj)}


def langues(pj):
    return [source(pj)] + sorted(versions(pj))


def est_source(langue, pj):
    return not langue or langue == source(pj)


def voix_de(langue, pj):
    if est_source(langue, pj):
        return pj["voix"]
    v = dict(VOIX_DEFAUT.get(langue.split("-")[0], pj["voix"]))
    v.update({k: x for k, x in ((versions(pj).get(langue) or {}).get("voix") or {}).items() if x})
    return v


def personnage(tag, pj):
    return next((p for p in pj.get("personnages", []) if p.get("tag") == tag), None)


def voix_plan(s, langue, pj):
    """Voix d'un plan : celle du personnage qui parle (« qui ») dans cette langue, sinon celle du narrateur.
    personnages[].voix = {"fr": {"nom", "debit", "hauteur"}, "en": {...}} ; personnages[].effet = "echo" (facultatif)."""
    base = voix_de(langue, pj)
    p = personnage(s.get("qui"), pj) if s.get("qui") else None
    if not p:
        return base
    code = langue or source(pj)
    pv = (p.get("voix") or {})
    v = pv.get(code) or pv.get(code.split("-")[0])
    if not v or not v.get("nom"):
        return base                     # personnage sans voix dans cette langue : le narrateur lit la réplique
    out = {"debit": "+0%", "hauteur": "+0Hz"}
    out.update({k: x for k, x in v.items() if x})
    if p.get("effet"):
        out["effet"] = p["effet"]
    return out


EFFETS = {                              # filtres ffmpeg appliqués après la synthèse
    "echo": "aecho=0.8:0.7:70|140:0.28|0.16",
    "grave": "asetrate=24000*0.92,aresample=24000,atempo=1.087",
    "lointain": "highpass=f=250,lowpass=f=3500,aecho=0.8:0.5:40:0.2",
}


VOIX_DEFAUT = {
    "en": {"nom": "en-US-AndrewNeural", "debit": "-10%", "hauteur": "-4Hz"},
    "es": {"nom": "es-ES-AlvaroNeural", "debit": "-10%", "hauteur": "-4Hz"},
    "de": {"nom": "de-DE-ConradNeural", "debit": "-10%", "hauteur": "-4Hz"},
    "pt": {"nom": "pt-BR-AntonioNeural", "debit": "-10%", "hauteur": "-4Hz"},
    "it": {"nom": "it-IT-DiegoNeural", "debit": "-10%", "hauteur": "-4Hz"},
}


# ---------------------------------------------------------------- empreintes
def empreinte(element):
    """Empreinte du texte d'origine d'un plan, d'un carton ou de l'épisode (titre)."""
    if "shots" in element:
        txt = [element.get("title", "")]
    elif element.get("card") is not None:
        txt = [element.get("card", ""), element.get("sub", "")]
    else:
        txt = [element.get("vo", ""), element.get("title", "")]
    return hashlib.sha1("\x1f".join(t.strip() for t in txt).encode("utf-8")).hexdigest()[:8]


def a_traduire(element):
    """Vrai si l'élément porte du texte (un plan muet sans titre n'a rien à traduire)."""
    if "shots" in element:
        return bool(element.get("title"))
    if element.get("card") is not None:
        return bool(element.get("card") or element.get("sub"))
    return bool((element.get("vo") or "").strip() or element.get("title"))


def statut(element, langue):
    """'ok' | 'manquante' | 'a_revoir' | 'rien' (rien à traduire)."""
    if not a_traduire(element):
        return "rien"
    t = (element.get("versions") or {}).get(langue)
    if not t:
        return "manquante"
    return "ok" if t.get("de") == empreinte(element) else "a_revoir"


def etat_traduction(e, langue):
    """Compte des éléments traduits / à revoir / manquants pour un épisode."""
    r = {"langue": langue, "ok": 0, "a_revoir": [], "manquantes": [], "total": 0}
    for i, el in enumerate([e] + e.get("shots", [])):
        st = statut(el, langue)
        if st == "rien":
            continue
        r["total"] += 1
        ref = "titre" if i == 0 else (el.get("k") or f"carton {i}")
        if st == "ok":
            r["ok"] += 1
        elif st == "a_revoir":
            r["a_revoir"].append(ref)
        else:
            r["manquantes"].append(ref)
    r["complete"] = r["ok"] == r["total"]
    return r


def poser(element, langue, valeurs):
    """Enregistre la traduction d'un élément (avec l'empreinte du texte d'origine)."""
    champs = ("title",) if "shots" in element else (CHAMPS_CARTON if element.get("card") is not None else CHAMPS_PLAN)
    t = {c: (valeurs.get(c) or "").strip() for c in champs if element.get(c) or valeurs.get(c)}
    t["de"] = empreinte(element)
    element.setdefault("versions", {})[langue] = t


def localiser(e, langue, pj, strict=True):
    """Copie de l'épisode avec les textes de la langue demandée. strict : refuse un épisode incomplètement traduit
    (on ne mélange jamais deux langues dans un film)."""
    if est_source(langue, pj):
        return e
    et = etat_traduction(e, langue)
    if strict and et["manquantes"]:
        raise RuntimeError(f"Traduction {langue} incomplète ({len(et['manquantes'])} élément(s) : "
                           f"{', '.join(et['manquantes'][:8])}{'…' if len(et['manquantes']) > 8 else ''}). "
                           f"Lance « Traduire » d'abord.")
    out = copy.deepcopy(e)
    for el in [out] + out.get("shots", []):
        t = (el.get("versions") or {}).get(langue)
        if t:
            for c, v in t.items():
                if c != "de":
                    el[c] = v
    if et["a_revoir"]:
        out["_a_revoir"] = et["a_revoir"]
    return out


def suffixe(langue, pj):
    return "" if est_source(langue, pj) else "_" + langue.upper()


# ---------------------------------------------------------------- sous-titres
def _morceaux(texte, maxi=84):
    """Découpe une narration en sous-titres d'au plus 2 lignes de 42 caractères, sur les phrases puis les virgules."""
    phrases = [p for p in re.split(r"(?<=[.!?…;:])\s+", " ".join(texte.split())) if p]
    out = []
    for p in phrases:
        while len(p) > maxi:
            coupe = max((m.end() for m in re.finditer(r",\s|\s[-—–]\s", p[:maxi])), default=0)
            if coupe < maxi * 0.4:
                coupe = p.rfind(" ", 0, maxi) + 1 or maxi
            out.append(p[:coupe].strip()); p = p[coupe:].strip()
        if p:
            out.append(p)
    return out


def _deux_lignes(t, largeur=42):
    if len(t) <= largeur:
        return t
    milieu = len(t) // 2
    espaces = [m.start() for m in re.finditer(" ", t)]
    if not espaces:
        return t
    c = min(espaces, key=lambda i: abs(i - milieu))
    return t[:c] + "\n" + t[c + 1:]


def _horodatage(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(segments):
    """segments : [(début_s, durée_voix_s, texte)] -> contenu d'un fichier .srt (horaires calés sur la voix)."""
    blocs, n = [], 0
    for debut, d, texte in segments:
        if not texte or d <= 0:
            continue
        parts = _morceaux(texte)
        poids = [max(len(p), 1) for p in parts]
        t = debut
        for p, w in zip(parts, poids):
            dur = d * w / sum(poids)
            n += 1
            blocs.append(f"{n}\n{_horodatage(t)} --> {_horodatage(t + dur - 0.04)}\n{_deux_lignes(p)}\n")
            t += dur
    return "\n".join(blocs)
