"""Export par lots des fiches Flow : un fichier de prompts par épisode, type (images/vidéos) et personnage.

Un lot = une seule image de référence à charger dans Flow, puis tous les prompts du lot lancés à la suite
(à la main, ou avec une extension de lot : un prompt par bloc, blocs séparés par une ligne vide).
Sortie : <dossier des fiches>/lots/<EP>/<EP>_IMG_<TAG>.txt, <EP>_VID_<TAG>.txt, <EP>_index.csv
(l'index donne l'ordre des prompts et le nom final de chaque fichier à renommer après téléchargement).
"""
import collections
import csv
import os
import re

_TETE = re.compile(r"^--- (\S+?\.(png|mp4))\s*(?:\[([\w, ]+)\])?(.*)$")


def lire_fiche(chemin):
    """Découpe une fiche Flow en blocs {fichier, ext, tag, prompt, texte}."""
    blocs, cur = [], None
    for ligne in open(chemin, encoding="utf-8-sig").read().splitlines():
        m = _TETE.match(ligne)
        if m:
            tags = [t.strip() for t in (m.group(3) or "").split(",") if t.strip()]   # plusieurs personnages : un lot par combinaison
            cur = {"fichier": m.group(1), "ext": m.group(2), "tag": "+".join(tags) or None, "prompt": None, "texte": ""}
            blocs.append(cur)
        elif cur is not None:
            if ligne.startswith("PROMPT :"):
                cur["prompt"] = ligne[8:].strip()
            elif ligne.startswith(("RÉPLIQUE", "Réplique", "Narration")):
                cur["texte"] = ligne.strip()
    return [b for b in blocs if b["prompt"]]


def exporter_depuis_fiche(chemin_fiche, ep, dossier_sortie):
    blocs = lire_fiche(chemin_fiche)
    tag_image = {b["fichier"][:-4]: b["tag"] or "SANS-REF" for b in blocs if b["ext"] == "png"}
    lots = collections.OrderedDict()
    for b in blocs:
        if b["ext"] == "png":
            cle = ("IMG", b["tag"] or "SANS-REF")
        else:  # une vidéo reprend le personnage de son image de départ
            cle = ("VID", b["tag"] or tag_image.get(b["fichier"][:-4], "SANS-REF"))
        lots.setdefault(cle, []).append(b)
    os.makedirs(dossier_sortie, exist_ok=True)
    index = []
    for (genre, tag), liste in lots.items():
        nom = f"{ep}_{genre}_{tag}.txt"
        with open(os.path.join(dossier_sortie, nom), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n\n".join(b["prompt"] for b in liste) + "\n")
        index += [[nom, i, b["fichier"], tag, b["texte"][:120]] for i, b in enumerate(liste, 1)]
    with open(os.path.join(dossier_sortie, f"{ep}_index.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["lot", "ordre", "fichier_final", "reference", "texte"])
        w.writerows(index)
    return {"dossier": dossier_sortie, "lots": {f"{g}-{t}": len(v) for (g, t), v in lots.items()}}


def exporter_lots(ep):
    """Régénère la fiche de l'épisode puis écrit ses lots à côté d'elle."""
    from fiche import fiche_flow
    chemin = fiche_flow(ep)
    return exporter_depuis_fiche(chemin, ep, os.path.join(os.path.dirname(chemin), "lots", ep))
