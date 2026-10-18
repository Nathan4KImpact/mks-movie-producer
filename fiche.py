#!/usr/bin/env python3
"""Génère la fiche de prompts (Flow ou tout générateur d'images) d'un épisode, sans IA."""
import json, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from contexte import projet, dossier, remplacer_tags, fichier, racine, _rel


def nom_de(tag, pj):
    if not tag:
        return ""
    p = next((x for x in pj.get("personnages", []) if x.get("tag") == tag), None)
    return p.get("nom", tag) if p else tag


def parlant(s, pj):
    """Plan où l'on voit un personnage parler (synchro labiale demandée), sauf personnage « sans visage »."""
    if not s.get("qui"):
        return False
    p = next((x for x in pj.get("personnages", []) if x.get("tag") == s["qui"]), {})
    return not p.get("sans_visage")


def bloc_sons(e):
    """Sons de l'épisode : d'où ils viendront au montage, et comment en obtenir un vrai enregistrement."""
    import sons
    u = sons.utilises(e)
    if not u:
        return []
    rel = _rel(dossier("sons")).replace("/", "\\")
    L = ["=" * 70, f"SONS DE L'ÉPISODE ({len(u)}) — ambiances et bruitages ajoutés au montage",
         "« synthèse » = son de repli fabriqué par l'outil (déjà utilisable). Pour un rendu réaliste, déposer un vrai son",
         f"(enregistrement libre de droits ou générateur de bruitages, avec le prompt ci-dessous) dans :  {rel}\\<nom>.mp3", ""]
    for n, plans in u.items():
        c = sons.CATALOGUE.get(n, {})
        f = sons.fichier_son(n)
        L += [f"--- {n}  ({c.get('nom', 'son du projet')}, {c.get('type', 'fichier')}) — "
              + (f"fichier : {os.path.basename(f)}" if f else ("synthèse" if c else "INTROUVABLE"))
              + f" — plans : {', '.join(plans[:12])}{'…' if len(plans) > 12 else ''}"]
        if c.get("en"):
            L += [f"PROMPT SON : {c['en']}" + (f", {c.get('duree', 4)} seconds" if c.get("type") == "bruitage"
                                               else ", seamless loop, 30 seconds")]
        L += [""]
    return L


def fiche_flow(ep):
    pj = projet()
    e = json.load(open(dossier("episodes", ep + ".json"), encoding="utf-8"))
    sty = pj.get("style_image", "")
    def ref(p):
        f = fichier(p.get("reference", ""))
        return _rel(f).replace("/", "\\") if f else (p.get("reference") or "la référence de " + p["nom"])
    refs = [f"[{p['tag']}] = ajouter {ref(p)} comme ingrédient / référence." for p in pj.get("personnages", [])]
    rel_images = _rel(dossier("images")).replace("/", "\\")
    L = [f"{pj['nom'].upper()} — {e['id']} « {e.get('title', '')} » — FICHE DE PROMPTS", "=" * 70,
         "Format : 16:9. Copier-coller chaque prompt tel quel (en anglais : meilleur rendu).",
         f"Enregistrer chaque image sous le NOM indiqué dans :  {rel_images}\\{ep}\\  (dossier du projet)"] + refs + \
        ["Les plans VIDÉO sont listés à la fin (à faire après les images).",
         "RÉPLIQUE = un personnage parle à l'écran : la vidéo le montre en train de parler ; COUPER LE SON généré",
         "par Flow (nos voix sont ajoutées au montage).", ""]
    for s in e["shots"]:
        if "k" not in s:
            continue
        p, persos = remplacer_tags(s.get("p", ""), pj)
        vo = s.get("vo", "")
        qui = nom_de(s.get("qui"), pj)
        if s.get("media"):                       # média déjà choisi dans la vue Studio : rien à générer
            L += [f"--- {s['k']} : média choisi dans le Studio ({s['media']}) — rien à générer", ""]
            continue
        L += [f"--- {s['k']}.png {'  [' + ', '.join(x['tag'] for x in persos) + ']' if persos else ''}",
              (f"RÉPLIQUE — {qui} : « {vo[:140]}{'…' if len(vo) > 140 else ''} »" if qui else
               f"Narration : {vo[:140]}{'…' if len(vo) > 140 else ''}"),
              f"PROMPT : {sty}{p}", ""]
    vids = [s for s in e["shots"] if s.get("vid_prompt")]
    L += ["=" * 70, f"PLANS VIDÉO ({len(vids)}) — « Frames to Video », image de départ = l'image du même nom",
          "Durée 5 à 8 s, sans son (sauf plans marqués GARDER LE SON : le son de Flow sert alors d'ambiance).",
          "Enregistrer sous le NOM indiqué (.mp4) dans le même dossier.", ""]
    import sons
    amb_courante = ""
    ambiance_de = {}
    for s in e["shots"]:                           # ambiance en cours à chaque plan (pour le son des vidéos)
        if s.get("amb"):
            amb_courante = "" if sons.nom_propre(s["amb"]) == "aucune" else sons.nom_propre(s["amb"])
        if s.get("k"):
            ambiance_de[s["k"]] = amb_courante
    for s in vids:
        parle = parlant(s, pj)
        garde = bool(s.get("son_video")) and not parle
        son_en = sons.CATALOGUE.get(ambiance_de.get(s["k"], ""), {}).get("en", "")
        vp, _ = remplacer_tags(s["vid_prompt"], pj)
        depart = f"{s['k']}.png"
        if s.get("img_url"):                       # image hébergée (Higgsfield…) : donner son lien si elle n'est pas dans le projet
            from moteur import trouver_media
            src, est_video = trouver_media(ep, {k: v for k, v in s.items() if k != "vid_url"}, None, telecharger=False)
            if src and str(src).startswith("http"):
                depart += f", à télécharger : {src}"
        L += [f"--- {s['k']}.mp4  (image de départ : {depart})" + ("  — RÉPLIQUE, couper le son" if parle else
                                                                  "  — GARDER LE SON" if garde else ""),
              (f"PROMPT : cinematic close shot, {vp}, the character is speaking with natural lip and facial movement, "
               f"steady camera, no subtitles, no text" if parle else
               f"PROMPT : cinematic, slow camera movement, {vp}" + (f", realistic ambient sound: {son_en}, no music, no dialogue"
                                                                   if garde and son_en else "")), ""]
        if parle:
            L.insert(len(L) - 1, f"Réplique ({len(s.get('vo', '').split())} mots, ≈ {max(3, round(len(s.get('vo', '').split()) / 2.3))} s) : « {s.get('vo', '')} »")
    L += bloc_sons(e)
    out = dossier("fiches", f"{ep}_fiche_Flow.txt", creer=False)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8-sig").write("\r\n".join(L))
    os.makedirs(dossier("images", ep), exist_ok=True)
    return out
