#!/usr/bin/env python3
"""Effets audio par plan et par couche (voix, musique, ambiance, bruitage) : fondus, volume, effet.

Dans le JSON d'un plan :  "fx": {"voix": {"in": 0.5, "out": 1, "vol": 1.2, "effet": "echo"},
                                 "mus": {...}, "amb": {...}, "sfx": {...}}
- voix : la voix (ou la réplique) de ce plan ;
- mus  : la musique qui démarre à ce plan (champ "mus") ;
- amb  : l'ambiance qui démarre à ce plan (champ "amb") — son niveau reste "amb_vol" ;
- sfx  : les bruitages de ce plan (champ "sfx") — leur niveau reste "sfx_vol".
"in" / "out" : durée du fondu d'entrée / de sortie en secondes (remplace le fondu par défaut de la couche).
"vol" : multiplicateur de volume (1 = inchangé). "effet" : une clé de EFFETS.
"""

COUCHES = ("voix", "mus", "amb", "sfx")

# filtres ffmpeg, indépendants de la fréquence d'échantillonnage (l'entrée est d'abord ramenée à 44,1 kHz)
EFFETS = {
    "echo": ("Écho", "aecho=0.8:0.7:70|140:0.28|0.16"),
    "salle": ("Réverbération (grande salle)", "aecho=0.8:0.85:110|230|390:0.4|0.3|0.2"),
    "lointain": ("Lointain", "highpass=f=250,lowpass=f=3500,aecho=0.8:0.5:40:0.2"),
    "radio": ("Radio / téléphone", "highpass=f=450,lowpass=f=3200,acompressor=threshold=0.1:ratio=6:makeup=2"),
    "etouffe": ("Étouffé (derrière un mur)", "lowpass=f=800,volume=1.4"),
    "grave": ("Plus grave", "asetrate=44100*0.9,aresample=44100,atempo=1.1111"),
    "aigu": ("Plus aigu", "asetrate=44100*1.12,aresample=44100,atempo=0.8929"),
}


def liste():
    """Pour l'interface : [{cle, nom}]."""
    return [{"cle": k, "nom": v[0]} for k, v in EFFETS.items()]


def lire(s, couche):
    """Réglages normalisés d'une couche d'un plan : {"in", "out", "vol", "effet"} (clés absentes = défaut)."""
    fx = ((s or {}).get("fx") or {}).get(couche) or {}
    out = {}
    for k in ("in", "out"):
        try:
            v = float(fx[k])
            if v >= 0:
                out[k] = min(v, 60.0)
        except (KeyError, TypeError, ValueError):
            pass
    try:
        v = float(fx["vol"])
        if v >= 0:
            out["vol"] = min(v, 4.0)
    except (KeyError, TypeError, ValueError):
        pass
    if fx.get("effet") in EFFETS:
        out["effet"] = fx["effet"]
    return out


def chaine(fx, L=None, fin_def=None, fout_def=None, avec_fondus=True):
    """Filtres ffmpeg (liste) pour ces réglages, sur un son de L secondes : effet, volume, fondus.
    fin_def / fout_def : fondus par défaut de la couche, utilisés si fx ne les précise pas."""
    f = ["aresample=44100"]
    if fx.get("effet"):
        f.append(EFFETS[fx["effet"]][1])
    if fx.get("vol") is not None and abs(fx["vol"] - 1) > 1e-3:
        f.append(f"volume={fx['vol']:.3f}")
    if avec_fondus:
        fi = fx.get("in", fin_def)
        fo = fx.get("out", fout_def)
        if fi:
            f.append(f"afade=t=in:d={fi:.2f}")
        if fo and L:
            fo = min(fo, L)
            f.append(f"afade=t=out:st={max(0.0, L - fo):.2f}:d={fo:.2f}")
    return f


def signature(fx):
    return tuple(sorted(fx.items()))
