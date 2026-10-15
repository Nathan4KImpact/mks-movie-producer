#!/usr/bin/env python3
"""MKS Movie Producer — ligne de commande (le projet actif est celui choisi dans l'interface, ou STUDIO_PROJET).

  python atelier.py monter E104            monte l'épisode -> <projet>/Rendus
  python atelier.py monter E104 --neuf     remonte tout depuis zéro
  python atelier.py monter E104 --langue en   monte la version anglaise -> <rendus>/en/ (+ sous-titres .srt)
  python atelier.py traduire E104 en ["consignes"]   [IA] traduit les textes manquants ou à revoir (--tout : tout refaire)
  python atelier.py etat E104              liste les images manquantes
  python atelier.py fiche E104             (re)génère la fiche de prompts
  python atelier.py ecrire E107 "Titre" 61-68 ["consignes"]   [IA] écrit l'épisode (pages du livre facultatives)
  python atelier.py prompts E106           [IA] réécrit les prompts dans la direction artistique
  python atelier.py verifier E104          [IA] relit les images et signale celles à refaire
  python atelier.py bible ["consignes"]    [IA] écrit la bible et le plan à partir des sources du projet
  python atelier.py exporter [--rendus]    crée un zip du projet (pour le transférer sur un autre poste)
"""
import json, os, sys, time, zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from contexte import racine, projet, slug, migrer, dossier, reparer_fichiers, APP


def episodes():
    d = dossier("episodes")
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


def exporter(avec_rendus=False):
    rac = racine()
    exp = dossier("exports", creer=True)
    out = os.path.join(exp, f"{slug(projet()['nom'])}_{time.strftime('%Y%m%d-%H%M')}.zip")
    exclus = {os.path.realpath(exp), os.path.realpath(APP)}          # exports et logiciel (s'il est dans le projet)
    if not avec_rendus:
        exclus.add(os.path.realpath(dossier("rendus")))
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for d, sous, fichiers in os.walk(rac):
            rel = os.path.relpath(d, rac)
            if os.path.realpath(d) in exclus:
                sous[:] = []; continue
            sous[:] = [s for s in sous if os.path.realpath(os.path.join(d, s)) not in exclus and s != "__pycache__"]
            for f in fichiers:
                z.write(os.path.join(d, f), os.path.join(os.path.basename(rac), rel, f)); n += 1
                if n % 50 == 0:
                    print(f"  {n} fichiers…", flush=True)
    print(f"Export : {out} ({n} fichiers, {os.path.getsize(out) / 1e6:.0f} Mo)")
    return out


def executer(cmd, args):
    if cmd == "monter":
        from moteur import monter
        lang = args[args.index("--langue") + 1] if "--langue" in args else None
        return monter(args[0], reprendre="--neuf" not in args, langue=lang)
    if cmd == "traduire":
        from ia import traduire_episode
        libres = [a for a in args[2:] if a != "--tout"]
        r = traduire_episode(args[0], args[1], libres[0] if libres else "", tout="--tout" in args)
        print(json.dumps(r, ensure_ascii=False, indent=1)); return r
    if cmd == "etat":
        from moteur import etat_images
        r = etat_images(args[0]); print(json.dumps(r, ensure_ascii=False, indent=1)); return r
    if cmd == "fiche":
        from fiche import fiche_flow
        p = fiche_flow(args[0]); print("Fiche :", p); return p
    if cmd == "ecrire":
        from ia import ecrire_episode
        from fiche import fiche_flow
        e = ecrire_episode(args[0], args[1], args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "")
        print(f"Épisode écrit : {len(e['shots'])} plans. Fiche :", fiche_flow(args[0])); return e
    if cmd == "prompts":
        from ia import ameliorer_prompts
        from fiche import fiche_flow
        ameliorer_prompts(args[0], args[1] if len(args) > 1 else ""); print("Fiche :", fiche_flow(args[0])); return True
    if cmd == "verifier":
        from ia import verifier_images
        p = verifier_images(args[0]); print("Rapport :", p); return p
    if cmd == "bible":
        from ia import generer_bible
        r = generer_bible(args[0] if args else ""); print("Bible et plan écrits :", r); return r
    if cmd == "exporter":
        return exporter("--rendus" in args)
    print(__doc__)


def menu():
    while True:
        print(f"\n=== {projet()['nom'].upper()} — ATELIER ({racine()}) ===")
        print("Épisodes :", ", ".join(episodes()))
        print(" 1  Monter un épisode              4  [IA] Écrire un nouvel épisode")
        print(" 2  Vérifier les images manquantes 5  [IA] Réécrire les prompts d'un épisode")
        print(" 3  Générer la fiche de prompts    6  [IA] Relire les images (vision)")
        print(" 0  Quitter        (l'interface PILOTAGE.bat fait tout cela et plus)")
        c = input("Choix : ").strip()
        try:
            if c == "0":
                return
            ep = input("Épisode (ex. E104) : ").strip()
            if c == "1":
                neuf = input("Repartir de zéro ? (o/N) : ").strip().lower() == "o"
                executer("monter", [ep] + (["--neuf"] if neuf else []))
            elif c == "2":
                executer("etat", [ep])
            elif c == "3":
                executer("fiche", [ep])
            elif c == "4":
                executer("ecrire", [ep, input("Titre : ").strip(), input("Pages du livre (facultatif) : ").strip(),
                                    input("Consignes (facultatif) : ").strip()])
            elif c == "5":
                executer("prompts", [ep, input("Consignes (facultatif) : ").strip()])
            elif c == "6":
                executer("verifier", [ep])
        except Exception as ex:
            print("\n!! Erreur :", ex)


if __name__ == "__main__":
    migrer()
    reparer_fichiers()
    if len(sys.argv) > 1:
        try:
            executer(sys.argv[1], sys.argv[2:])
        except Exception as ex:
            print("!! Erreur :", ex)
            sys.exit(1)
    else:
        menu()
