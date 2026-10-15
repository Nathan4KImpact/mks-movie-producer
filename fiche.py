#!/usr/bin/env python3
"""Génère la fiche de prompts (Flow ou tout générateur d'images) d'un épisode, sans IA."""
import json, os, sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from contexte import projet, dossier, remplacer_tags, fichier, racine, _rel


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
        ["Les plans VIDÉO sont listés à la fin (à faire après les images).", ""]
    for s in e["shots"]:
        if "k" not in s:
            continue
        p, persos = remplacer_tags(s.get("p", ""), pj)
        vo = s.get("vo", "")
        L += [f"--- {s['k']}.png {'  [' + ', '.join(x['tag'] for x in persos) + ']' if persos else ''}",
              f"Narration : {vo[:140]}{'…' if len(vo) > 140 else ''}",
              f"PROMPT : {sty}{p}", ""]
    vids = [s for s in e["shots"] if s.get("vid_prompt")]
    L += ["=" * 70, f"PLANS VIDÉO ({len(vids)}) — « Frames to Video », image de départ = l'image du même nom",
          "Durée 5 à 8 s, sans son. Enregistrer sous le NOM indiqué (.mp4) dans le même dossier.", ""]
    for s in vids:
        L += [f"--- {s['k']}.mp4  (image de départ : {s['k']}.png)",
              f"PROMPT : cinematic, slow camera movement, {s['vid_prompt']}", ""]
    out = dossier("fiches", f"{ep}_fiche_Flow.txt", creer=False)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8-sig").write("\r\n".join(L))
    os.makedirs(dossier("images", ep), exist_ok=True)
    return out
