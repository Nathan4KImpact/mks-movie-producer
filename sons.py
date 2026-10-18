#!/usr/bin/env python3
"""MKS Movie Producer — bruitages et ambiances sonores.

Trois couches sous la voix, mixées après la musique et baissées automatiquement quand quelqu'un parle :
  - ambiance  : champ "amb" d'un plan = l'ambiance démarre à ce plan et continue jusqu'au prochain "amb"
                ("aucune" = silence). "amb_vol" règle le niveau de cette section (1 = normal, 1.5 = plus fort).
  - bruitage  : champ "sfx" d'un plan (un nom ou une liste) = son ponctuel joué au début du plan
                (décalage "sfx_t" en secondes, 0.2 par défaut).
  - son vidéo : "son_video": true = on garde le son de la vidéo du plan (ex. horde générée AVEC son par Flow/Veo).

D'où vient chaque son (dans cet ordre) :
  1. un fichier du projet : <dossier des sons>/<nom>.mp3|wav|ogg|flac|m4a (enregistrement libre de droits,
     bruitage généré par une IA de sons…) ; tout fichier du dossier est utilisable par son nom, même hors catalogue ;
  2. sinon une SYNTHÈSE de repli fabriquée par ffmpeg (sans téléchargement) : utilisable tout de suite,
     moins riche qu'un vrai enregistrement. La fiche de l'épisode liste les sons à remplacer et un prompt anglais
     pour les générer.
"""
import os, subprocess, sys, zlib

ICI = os.path.dirname(os.path.abspath(__file__))
EXTS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".opus")
XF = 2.0                   # fondu enchaîné entre deux ambiances (s)
VERSION = 1                # à incrémenter si les recettes changent (recalcul des sons de synthèse)

# ---------------------------------------------------------------- briques de synthèse (filtres ffmpeg)
# Chaque recette = liste de chaînes « source,filtres » ; {d} = durée, {g} = graine aléatoire.
_GRONDEMENT = "anoisesrc=d={d}:c=brown:a=0.9:r=44100:seed={g},lowpass=f=110,lowpass=f=110,volume=2.2"
_VENT = ("anoisesrc=d={d}:c=pink:a=0.7:r=44100:seed={g}1,bandpass=f=520:width_type=o:w=2,"
         "tremolo=f=0.13:d=0.75,tremolo=f=0.31:d=0.4")
_VENT_DOUX = ("anoisesrc=d={d}:c=pink:a=0.4:r=44100:seed={g}2,highpass=f=900,lowpass=f=4000,"
              "tremolo=f=0.11:d=0.6,volume=0.6")


def _pas(periodes, f=50, bruit=0.3, k=15):
    """Pas lourds (troupes) : une impulsion grave + un crissement par pas, plusieurs groupes décalés."""
    termes = []
    for i, (per, dec) in enumerate(periodes):
        m = f"mod(t+{dec},{per})"
        termes.append(f"0.7*sin(2*PI*{f + 6 * i}*t)*exp(-{k}*{m})+{bruit}*(random({i})*2-1)*exp(-40*{m})")
    return f"aevalsrc=exprs='({'+'.join(termes)})/{len(periodes)}':s=44100:d={{d}},lowpass=f=900"


def _metal(instants, freqs=(3100, 4300, 5200), amp=0.05):
    """Tintements d'armures / chaînes : sons métalliques brefs à des périodes irrégulières."""
    t = [f"{amp}*sin(2*PI*{freqs[i % len(freqs)]}*t)*exp(-28*mod(t+{d},{p}))" for i, (p, d) in enumerate(instants)]
    return f"aevalsrc=exprs='{'+'.join(t)}':s=44100:d={{d}},highpass=f=1500"


def _foule(f=550, a=0.6, g="3"):
    """Rumeur de foule : bruit rose dans la bande de la voix, modulé comme une conversation de masse."""
    return (f"anoisesrc=d={{d}}:c=pink:a={a}:r=44100:seed={{g}}{g},bandpass=f={f}:width_type=o:w=1.6,"
            "tremolo=f=3.7:d=0.45,tremolo=f=5.3:d=0.35,tremolo=f=0.17:d=0.5")


def _cri(periode, duree_cri, f0, df, amp=0.18):
    """Cri ou glapissement lointain, répété à une période donnée."""
    m = f"mod(t,{periode})"
    return (f"aevalsrc=exprs='if(lt({m},{duree_cri}),{amp}*sin(2*PI*({f0}+{df}*{m})*t)*sin(PI*{m}/{duree_cri}),0)'"
            f":s=44100:d={{d}},lowpass=f=2600,aecho=0.8:0.6:180|340:0.35|0.2")


def _nappe(freqs, amp=0.1, vib=5.0):
    """Nappe de voix tenues (chœur lointain) : sons purs avec léger vibrato, très doux."""
    t = [f"{amp / (1 + i * 0.4):.3f}*sin(2*PI*{f}*t+0.3*sin(2*PI*{vib + 0.3 * i}*t))" for i, f in enumerate(freqs)]
    return (f"aevalsrc=exprs='({'+'.join(t)})*(0.75+0.25*sin(2*PI*0.07*t))':s=44100:d={{d}},lowpass=f=2200,"
            "aecho=0.8:0.7:70|140|230:0.35|0.25|0.15")


def _crepitement(seuil=0.9992, amp=0.6):
    return (f"aevalsrc=exprs='if(gt(random(0),{seuil}),{amp}*(random(1)*2-1),0)':s=44100:d={{d}},"
            "highpass=f=700,lowpass=f=6000")


# ---------------------------------------------------------------- catalogue
# type : "ambiance" (en boucle sur une section) | "bruitage" (ponctuel)
CATALOGUE = {
    "horde": {"type": "ambiance", "nom": "Horde démoniaque qui avance",
              "en": "massive demonic horde marching, heavy irregular footsteps of thousands, low guttural growls, "
                    "distant shrieks, ground rumble, ominous",
              "recette": [_GRONDEMENT + ",volume=0.45", _pas([(0.58, 0), (0.67, 0.21), (0.73, 0.4)], f=46, bruit=0.35, k=13) + ",volume=1.6",
                          _foule(230, 0.5, "4") + ",tremolo=f=6:d=0.6,volume=1.4", _cri(9.7, 1.1, 650, 420)]},
    "grondement": {"type": "ambiance", "nom": "Grondement lointain de l'ennemi",
                   "en": "distant ominous rumble of an approaching army, low drones, faint growls, no music",
                   "recette": [_GRONDEMENT, _foule(200, 0.35, "5") + ",tremolo=f=4:d=0.5",
                               "aevalsrc=exprs='0.08*sin(2*PI*55*t)+0.08*sin(2*PI*58.3*t)':s=44100:d={d}"]},
    "marche": {"type": "ambiance", "nom": "Armée du Seigneur en marche (pas réguliers, armures)",
               "en": "disciplined army marching in step, armored boots on rock, soft metallic armor clinks, wind",
               "recette": [_pas([(0.5, 0), (0.5, 0.03)], f=60, bruit=0.25, k=20),
                           _metal([(1.0, 0.25), (1.3, 0.1), (1.7, 0.6)]), _VENT_DOUX]},
    "armee": {"type": "ambiance", "nom": "Camp de l'armée (murmures, armures, préparatifs)",
              "en": "large camp of soldiers talking quietly, murmurs of many voices, armor and weapons being handled, "
                    "occasional sword clinks, outdoor",
              "recette": [_foule(520, 0.55, "6"), _metal([(1.9, 0.3), (2.7, 1.1), (3.4, 0.5), (4.1, 2.0)], amp=0.04),
                          _VENT_DOUX]},
    "eveil": {"type": "ambiance", "nom": "Armée qui s'éveille (voix qui montent, élan)",
              "en": "army of believers rising, voices growing in confidence, murmurs of awe turning into prayers, "
                    "armor shining, hopeful",
              "recette": [_foule(650, 0.55, "7") + ",tremolo=f=0.1:d=0.5",
                          _nappe([146.83, 220.0, 293.66], amp=0.05), _metal([(2.3, 0.4), (3.1, 1.2)], amp=0.035)]},
    "louange": {"type": "ambiance", "nom": "Louange et adoration (chœur lointain, acclamations douces)",
                "en": "distant choir of thousands worshiping, sustained voices, gentle cheering, reverent, reverberant",
                "recette": [_nappe([146.83, 220.0, 293.66, 369.99, 440.0], amp=0.11),
                            _foule(800, 0.35, "8") + ",tremolo=f=0.1:d=0.6"]},
    "bataille": {"type": "ambiance", "nom": "Bataille (cris, épées, flèches, impacts)",
                 "en": "epic battle, clashing swords and shields, war cries, arrows whooshing, heavy impacts, chaos",
                 "recette": [_GRONDEMENT, _pas([(0.41, 0), (0.47, 0.13), (0.53, 0.29), (0.61, 0.07)], f=52, bruit=0.4, k=12),
                             _metal([(0.83, 0), (1.17, 0.4), (1.61, 0.9), (0.97, 0.2)], (2400, 3300, 4700, 2900), 0.09),
                             _foule(900, 0.6, "9") + ",tremolo=f=2.1:d=0.9",
                             "aevalsrc=exprs='0.4*(random(0)*2-1)*pow(sin(PI*mod(t,1.9)/1.9),8)':s=44100:d={d},highpass=f=2200"]},
    "vautours": {"type": "ambiance", "nom": "Vautours (battements d'ailes, cris rauques)",
                 "en": "giant vultures circling overhead, heavy wing flaps, harsh raspy screeches, wind on a cliff",
                 "recette": [_VENT,
                             "aevalsrc=exprs='0.6*(random(0)*2-1)*pow(0.5+0.5*sin(2*PI*1.6*t),6)*(0.6+0.4*sin(2*PI*0.11*t))'"
                             ":s=44100:d={d},lowpass=f=700",
                             _cri(6.3, 0.9, 1500, -600, 0.14)]},
    "prisonniers": {"type": "ambiance", "nom": "Prisonniers (chaînes, gémissements, pas traînants)",
                    "en": "shackled prisoners dragged along, rattling chains, weary moans, shuffling feet, oppressive",
                    "recette": [_GRONDEMENT + ",volume=0.5",
                                _metal([(0.9, 0), (1.3, 0.5), (1.1, 0.2), (1.7, 0.8)], (2600, 3700, 4400), 0.07),
                                "aevalsrc=exprs='if(lt(mod(t,5.9),2.2),0.15*sin(2*PI*(160-30*mod(t,5.9)/2.2)*t)"
                                "*sin(PI*mod(t,5.9)/2.2),0)':s=44100:d={d},lowpass=f=700,aecho=0.8:0.5:120:0.3",
                                _pas([(1.1, 0), (1.25, 0.4)], f=70, bruit=0.5, k=9) + ",volume=0.5"]},
    "brume": {"type": "ambiance", "nom": "Brume de condamnation (oppression, souffle sourd)",
              "en": "oppressive dark mist, low dissonant drone, muffled whispers, heavy air, dread",
              "recette": ["aevalsrc=exprs='0.1*sin(2*PI*55*t)+0.1*sin(2*PI*58.3*t)+0.05*sin(2*PI*82.4*t)':s=44100:d={d}",
                          "anoisesrc=d={d}:c=brown:a=0.6:r=44100:seed={g}5,lowpass=f=300,tremolo=f=0.2:d=0.7",
                          _foule(1200, 0.12, "10") + ",tremolo=f=7:d=0.8"]},
    "feu": {"type": "ambiance", "nom": "Soufre et feu (brasier, crépitements)",
            "en": "sulfurous fire, roaring flames, crackling embers, low rumble",
            "recette": ["anoisesrc=d={d}:c=brown:a=0.8:r=44100:seed={g}6,lowpass=f=420,tremolo=f=0.4:d=0.4",
                        _crepitement(), _crepitement(0.9997, 0.9)]},
    "vent": {"type": "ambiance", "nom": "Vent sur la montagne",
             "en": "strong wind on a high mountain, gusts, open space",
             "recette": [_VENT, _VENT_DOUX]},
    "hauteurs": {"type": "ambiance", "nom": "Hauteurs paisibles (air pur, brise légère)",
                 "en": "peaceful high mountain plateau, light breeze, airy calm, faint distant birds",
                 "recette": [_VENT_DOUX,
                             "aevalsrc=exprs='if(lt(mod(t,7.1),0.25),0.04*sin(2*PI*(3200+900*mod(t,7.1))*t),0)':s=44100:d={d}"]},
    "sacre": {"type": "ambiance", "nom": "Présence sacrée (silence lumineux, scintillement)",
              "en": "holy presence, luminous silence, soft high shimmering tones, gentle air, awe",
              "recette": ["aevalsrc=exprs='(0.03*sin(2*PI*1318.5*t)+0.025*sin(2*PI*1975.5*t)+0.02*sin(2*PI*2637*t))"
                          "*(0.6+0.4*sin(2*PI*0.09*t))':s=44100:d={d},aecho=0.8:0.8:300|500:0.4|0.3",
                          _VENT_DOUX + ",volume=0.5"]},
    # ---------------- bruitages ponctuels
    "tonnerre": {"type": "bruitage", "nom": "Tonnerre", "duree": 6,
                 "en": "deep rolling thunder, long rumble",
                 "recette": ["aevalsrc=exprs='(random(0)*2-1)*exp(-1.1*t)*(1-exp(-25*t))':s=44100:d={d},lowpass=f=260,volume=2"]},
    "eclair": {"type": "bruitage", "nom": "Éclair (claquement puis tonnerre)", "duree": 6,
               "en": "lightning strike crack followed by thunder",
               "recette": ["aevalsrc=exprs='(random(0)*2-1)*exp(-22*t)':s=44100:d={d},highpass=f=1500",
                           "aevalsrc=exprs='(random(1)*2-1)*exp(-1.2*max(0,t-0.4))*(1-exp(-25*max(0,t-0.4)))*gt(t,0.4)'"
                           ":s=44100:d={d},lowpass=f=300,volume=2"]},
    "cor": {"type": "bruitage", "nom": "Cor / shofar (appel de l'armée)", "duree": 4,
            "en": "ancient ram's horn shofar blast, rising call to battle, reverberant",
            "recette": ["aevalsrc=exprs='(" + "+".join(
                f"sin({n}*if(lt(t,1.2),2*PI*(233*t+48.3*t*t),2*PI*(349.2*(t-1.2)+349.15)))/{n}" for n in range(1, 7))
                + ")*0.25*min(1,t*8)*min(1,max(0,3.6-t))':s=44100:d={d},bandpass=f=900:width_type=o:w=3,"
                  "aecho=0.8:0.7:180|360:0.4|0.25"]},
    "acclamation": {"type": "bruitage", "nom": "Acclamation de l'armée", "duree": 5,
                    "en": "army cheering in triumph, many voices shouting with joy, swords raised",
                    "recette": [_foule(1000, 0.9, "11") + ",tremolo=f=9:d=0.5,"
                                "volume='min(1,t/0.4)*max(0,1-(t-1.5)/3)':eval=frame"]},
    "rugissement": {"type": "bruitage", "nom": "Rugissement de la horde", "duree": 4,
                    "en": "monstrous demonic roar from a massive horde, guttural, terrifying",
                    "recette": ["anoisesrc=d={d}:c=pink:a=0.9:r=44100:seed={g}7,bandpass=f=170:width_type=o:w=1.4,"
                                "tremolo=f=28:d=0.8,volume='min(1,t/0.3)*max(0,1-(t-1)/2.5)':eval=frame,volume=2.5",
                                "aevalsrc=exprs='0.4*sin(2*PI*(90-8*t)*t)*min(1,t/0.3)*max(0,1-(t-1)/2.5)':s=44100:d={d}"]},
    "epee": {"type": "bruitage", "nom": "Épée tirée / qui résonne", "duree": 3,
             "en": "sword being drawn from its sheath, bright metallic ring",
             "recette": ["aevalsrc=exprs='(0.3*sin(2*PI*2093*t)+0.2*sin(2*PI*3135*t)+0.15*sin(2*PI*4711*t)+0.1*sin(2*PI*6100*t))"
                         "*exp(-2*t)':s=44100:d={d}",
                         "aevalsrc=exprs='0.3*(random(0)*2-1)*if(lt(t,0.4),sin(PI*t/0.4),0)':s=44100:d={d},highpass=f=3000"]},
    "impact": {"type": "bruitage", "nom": "Impact sourd", "duree": 3,
               "en": "heavy deep impact, boom, short",
               "recette": ["aevalsrc=exprs='0.9*sin(2*PI*45*t)*exp(-5*t)+0.5*(random(0)*2-1)*exp(-20*t)':s=44100:d={d},lowpass=f=800"]},
    "souffle": {"type": "bruitage", "nom": "Souffle / passage d'un ange", "duree": 3,
                "en": "soft whoosh of a luminous angel passing by, airy, ethereal",
                "recette": ["anoisesrc=d={d}:c=pink:a=0.7:r=44100:seed={g}8,highpass=f=700,lowpass=f=6000,"
                            "volume='pow(sin(PI*min(t,3)/3),2)':eval=frame,aecho=0.8:0.6:90:0.3"]},
    "fleches": {"type": "bruitage", "nom": "Volée de flèches", "duree": 3,
                "en": "volley of many arrows whooshing through the air",
                "recette": ["aevalsrc=exprs='" + "+".join(
                    f"0.25*(random({i})*2-1)*if(between(t,{0.1 * i:.1f},{0.1 * i + 0.6:.1f}),pow(sin(PI*(t-{0.1 * i:.1f})/0.6),3),0)"
                    for i in range(8)) + "':s=44100:d={d},highpass=f=1800,lowpass=f=8000"]},
}
ALIAS = {"aucun": "aucune", "silence": "aucune", "none": "aucune"}


# ---------------------------------------------------------------- outils
def _ff():
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"


def _run(args, cwd=None):
    r = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ERREUR ffmpeg (sons) :", r.stderr[-1500:], file=sys.stderr)
        raise RuntimeError("ffmpeg a échoué (sons)")


def nom_propre(n):
    n = (n or "").strip().lower()
    return ALIAS.get(n, n)


def dossier_sons():
    from contexte import dossier
    return dossier("sons")


def fichier_son(nom):
    """Fichier du projet pour ce son (prioritaire sur la synthèse), ou None."""
    try:
        d = dossier_sons()
    except Exception:
        return None
    if not d or not os.path.isdir(d):
        return None
    for ext in EXTS:
        p = os.path.join(d, nom + ext)
        if os.path.exists(p):
            return p
    bas = nom.lower()
    for f in os.listdir(d):                      # tolère la casse et les noms longs (« horde_marche_01.mp3 »)
        b, ext = os.path.splitext(f)
        if ext.lower() in EXTS and (b.lower() == bas or b.lower().startswith(bas + "_")):
            return os.path.join(d, f)
    return None


def fichiers_du_projet():
    try:
        d = dossier_sons()
        return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if os.path.splitext(f)[1].lower() in EXTS)
    except Exception:
        return []


def liste():
    """Catalogue + fichiers du projet, avec la provenance de chaque son (pour l'interface)."""
    out = []
    for n, c in CATALOGUE.items():
        f = fichier_son(n)
        out.append({"nom": n, "libelle": c["nom"], "type": c["type"], "prompt_en": c["en"],
                    "source": "fichier" if f else "synthese", "fichier": os.path.basename(f) if f else ""})
    for n in fichiers_du_projet():
        if n not in CATALOGUE and not any(n.startswith(k + "_") for k in CATALOGUE):
            out.append({"nom": n, "libelle": n.replace("_", " "), "type": "fichier", "prompt_en": "",
                        "source": "fichier", "fichier": n})
    return out


def connu(nom):
    nom = nom_propre(nom)
    return nom == "aucune" or nom in CATALOGUE or fichier_son(nom) is not None


def synthese(nom, d, dst):
    """Fabrique le son de repli « nom » sur d secondes (stéréo 44,1 kHz)."""
    c = CATALOGUE[nom]
    g = zlib.crc32(nom.encode()) % 900 + 100
    chaines = [r.format(d=f"{d:.2f}", g=g) for r in c["recette"]]
    fc = ";".join(f"{ch},aformat=sample_rates=44100:channel_layouts=mono[s{i}]" for i, ch in enumerate(chaines))
    fc += ";" + "".join(f"[s{i}]" for i in range(len(chaines))) + \
          f"amix=inputs={len(chaines)}:normalize=0,atrim=0:{d:.2f},pan=stereo|c0=c0|c1=c0,aecho=0.6:0.5:13:0.3," \
          f"alimiter=limit=0.9[o]"
    _run([_ff(), "-y", "-filter_complex", fc, "-map", "[o]", "-ar", "44100", "-ac", "2", dst])
    return dst


def preparer(nom, d, dst, cible=-28.0):
    """Écrit dans dst le son « nom » sur d secondes, normalisé en sonie (fichier du projet en boucle, sinon synthèse)."""
    f = fichier_son(nom)
    brut = dst[:-4] + "_brut.wav"
    if f:
        _run([_ff(), "-y", "-stream_loop", "-1", "-i", f, "-t", f"{d:.2f}", "-ar", "44100", "-ac", "2", brut])
    elif nom in CATALOGUE:
        synthese(nom, d, brut)
    else:
        raise KeyError(nom)
    fin = min(XF, d / 3)
    _run([_ff(), "-y", "-i", brut, "-af", f"loudnorm=I={cible}:TP=-3,afade=t=in:d={fin:.2f},"
          f"afade=t=out:st={max(0, d - fin):.2f}:d={fin:.2f}", "-ar", "44100", "-ac", "2", dst])
    os.remove(brut)
    return dst


# ---------------------------------------------------------------- piste d'ambiance d'un épisode
def evenements(shots, debuts, durees):
    """Découpe l'épisode en sections d'ambiance et en bruitages ponctuels.
    Renvoie (sections [(t0, t1, nom, vol)], ponctuels [(t, nom, vol)], inconnus)."""
    sections, ponctuels, inconnus = [], [], set()
    for i, s in enumerate(shots):
        if s.get("amb") is not None:
            n = nom_propre(s["amb"])
            if sections:
                sections[-1][1] = debuts[i]
            if n and n != "aucune":
                if not connu(n):
                    inconnus.add(n)
                else:
                    sections.append([debuts[i], None, n, float(s.get("amb_vol", 1))])
        sf = s.get("sfx")
        for n in ([sf] if isinstance(sf, str) else (sf or [])):
            n = nom_propre(n)
            if not connu(n):
                inconnus.add(n); continue
            ponctuels.append((debuts[i] + float(s.get("sfx_t", 0.2)), n, float(s.get("sfx_vol", 1))))
    total = debuts[-1] + durees[-1] if debuts else 0
    for sct in sections:
        if sct[1] is None:
            sct[1] = total
    return [tuple(x) for x in sections if x[1] - x[0] > 0.5], ponctuels, sorted(inconnus)


def piste(shots, debuts, durees, total, wd, sons_video=(), signature=None, a_jour=None, marquer=None):
    """Fabrique bruits.wav (ou None s'il n'y a aucun son). sons_video : [(t, fichier wav, vol)]."""
    sections, ponctuels, inconnus = evenements(shots, debuts, durees)
    for n in inconnus:
        print(f"  (son inconnu : « {n} » — ni dans le catalogue ni dans le dossier des sons, ignoré)", file=sys.stderr)
    entrees = []                                     # (début, fichier, volume)
    for k, (t0, t1, n, vol) in enumerate(sections):
        L = (t1 - t0) + (XF if t1 < total else 0)
        seg = f"amb{k:02d}.wav"
        sig = signature("amb", n, round(L, 2), VERSION, fichier_son(n) and os.path.getmtime(fichier_son(n))) if signature else None
        if not (a_jour and a_jour(os.path.join(wd, seg), sig)):
            preparer(n, L, os.path.join(wd, seg))
            if marquer:
                marquer(os.path.join(wd, seg), sig)
        entrees.append((t0, seg, vol))
    for k, (t, n, vol) in enumerate(ponctuels):
        L = CATALOGUE.get(n, {}).get("duree", 5)
        seg = f"sfx{k:02d}.wav"
        sig = signature("sfx", n, L, VERSION, fichier_son(n) and os.path.getmtime(fichier_son(n))) if signature else None
        if not (a_jour and a_jour(os.path.join(wd, seg), sig)):
            f = fichier_son(n)
            if f:                                        # fichier ponctuel : joué une fois, en entier
                _run([_ff(), "-y", "-i", f, "-af", "loudnorm=I=-22:TP=-2", "-ar", "44100", "-ac", "2",
                      os.path.join(wd, seg)])
            else:
                synthese(n, L, os.path.join(wd, seg + ".brut.wav"))
                _run([_ff(), "-y", "-i", seg + ".brut.wav", "-af", "loudnorm=I=-22:TP=-2", "-ar", "44100", "-ac", "2", seg], cwd=wd)
                os.remove(os.path.join(wd, seg + ".brut.wav"))
            if marquer:
                marquer(os.path.join(wd, seg), sig)
        entrees.append((t, seg, vol))
    entrees += list(sons_video)
    if not entrees:
        return None
    args = [_ff(), "-y"]
    for _, f, _ in entrees:
        args += ["-i", f]
    fc = ";".join(f"[{i}:a]volume={v:.2f},adelay={int(t * 1000)}|{int(t * 1000)}[d{i}]" for i, (t, _, v) in enumerate(entrees))
    fc += ";" + "".join(f"[d{i}]" for i in range(len(entrees))) + \
          f"amix=inputs={len(entrees)}:normalize=0,apad=whole_dur={total:.2f},atrim=0:{total:.2f}," \
          f"afade=t=out:st={max(0, total - 4):.2f}:d=4[m]"
    _run(args + ["-filter_complex", fc, "-map", "[m]", "-ar", "44100", "-ac", "2", "bruits.wav"], cwd=wd)
    return "bruits.wav"


def essai(nom):
    """Extrait de 10 s (ou le bruitage entier) pour écouter un son dans l'interface. Renvoie le chemin du .mp3."""
    nom = nom_propre(nom)
    d = os.path.join(ICI, "cache", "essais")
    os.makedirs(d, exist_ok=True)
    f = fichier_son(nom)
    tag = f"{int(os.path.getmtime(f))}" if f else f"s{VERSION}"
    dst = os.path.join(d, f"son_{nom}_{tag}.mp3")
    if not os.path.exists(dst):
        L = CATALOGUE.get(nom, {}).get("duree", 10) if CATALOGUE.get(nom, {}).get("type") == "bruitage" else 10
        wav = dst[:-4] + ".wav"
        preparer(nom, L, wav, cible=-20)
        _run([_ff(), "-y", "-i", wav, "-b:a", "160k", dst])
        os.remove(wav)
    return dst


def utilises(e):
    """Sons utilisés par un épisode : {nom: [clés des plans]} (pour la fiche)."""
    out = {}
    for s in e.get("shots", []):
        sf = s.get("sfx")
        for n in ([s.get("amb")] if s.get("amb") else []) + ([sf] if isinstance(sf, str) else list(sf or [])):
            n = nom_propre(n)
            if n and n != "aucune":
                out.setdefault(n, []).append(s.get("k") or "carton")
    return out
