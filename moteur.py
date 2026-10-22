#!/usr/bin/env python3
"""MKS Movie Producer — moteur de montage local (Windows / Mac / Linux).

Entrée  : <dossier des épisodes>/<EP>.json  +  images/vidéos dans <dossier des images>/<EP>/<clé>.png|jpg|mp4
Sortie  : <dossier des rendus>/<ID>_<titre>.mp4 (+ .srt) ; version traduite : <rendus>/<langue>/<ID>_<titre>_EN.mp4 (+ .srt)

Pas de shell : toutes les commandes ffmpeg sont passées en listes d'arguments,
ce qui évite les problèmes d'apostrophes et d'espaces dans les chemins Windows.
"""
import hashlib, json, os, re, subprocess, sys, shutil, time, urllib.request, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))          # dossier du logiciel
sys.path.insert(0, ICI)
from contexte import racine, projet, chemin, dossier, slug as slug_projet

W, H, FPS = 1920, 1080, 25
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def run(args, cwd=None):
    r = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log("ERREUR commande :", " ".join(str(x) for x in args)[:500])
        log(r.stderr[-2500:])
        raise RuntimeError("ffmpeg a échoué")
    return r.stdout


def duree(f):
    return float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).strip())


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")[:40]


# ---------------------------------------------------------------- sources
def trouver_media(ep, s, wd, telecharger=True):
    """Renvoie (chemin, est_video) pour un plan, ou (None, False) si introuvable."""
    k = s.get("k")
    if s.get("media"):                          # média choisi dans la bibliothèque ou importé (vue Studio)
        from contexte import fichier
        p = fichier(s["media"])
        if p:
            return p, os.path.splitext(p)[1].lower() in (".mp4", ".mov", ".webm")
        log(f"  média introuvable : {s['media']} (repli sur la clé {k})")
    rep = dossier("images", ep)
    if k:
        for ext in (".mp4", ".mov", ".webm"):
            p = os.path.join(rep, k + ext)
            if os.path.exists(p):
                return p, True
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".PNG", ".JPG"):
            p = os.path.join(rep, k + ext)
            if os.path.exists(p):
                return p, False
    if k:                                       # rangé ailleurs dans le projet (ancien dossier, autre sous-dossier…)
        from contexte import chercher_media
        p, video = chercher_media(k)
        if p:
            return p, video
    for champ, est_video in (("vid_url", True), ("img_url", False)):
        u = s.get(champ)
        if u and not telecharger:
            return u, est_video
        if u:
            cache = os.path.join(ICI, "cache", slug_projet(projet()["nom"]))
            os.makedirs(cache, exist_ok=True)
            dst = os.path.join(cache, os.path.basename(u.split("?")[0]))
            if not os.path.exists(dst):
                log(f"  téléchargement {os.path.basename(dst)}")
                urllib.request.urlretrieve(u, dst)
            return dst, est_video
    return None, False


def etat_images(ep):
    """Liste des plans dont le média manque (pour vérifier avant montage)."""
    e = charger_episode(ep)
    manquants, videos, images = [], 0, 0
    for s in e["shots"]:
        if s.get("card"):
            continue
        p, v = trouver_media(ep, s, None, telecharger=False)
        if p is None:
            manquants.append(s.get("k"))
        elif v:
            videos += 1
        else:
            images += 1
    return {"episode": ep, "manquants": manquants, "images": images, "videos": videos}


def a_un_son(f):
    try:
        return bool(run([FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                         "-of", "csv=p=0", f]).strip())
    except RuntimeError:
        return False


def charger_episode(ep):
    return json.load(open(dossier("episodes", ep + ".json"), encoding="utf-8"))


# ---------------------------------------------------------------- voix
def signature(*elements):
    """Empreinte d'un plan : s'il change (texte, image, mouvement…), le plan est recalculé au prochain montage."""
    return hashlib.sha1(json.dumps(elements, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def a_jour(fichier, sig):
    try:
        return os.path.getsize(fichier) > 0 and open(fichier + ".sig", encoding="utf-8").read() == sig
    except OSError:
        return False


def marquer(fichier, sig):
    open(fichier + ".sig", "w", encoding="utf-8").write(sig)


def empreinte_media(src):
    if src and os.path.exists(src):
        st = os.stat(src)
        return [os.path.abspath(src), st.st_size, int(st.st_mtime)]
    return [src]


def voix(texte, dst, v=None):
    v = v or projet()["voix"]
    sig = signature(texte, v.get("nom"), v.get("debit"), v.get("hauteur"), v.get("effet"))
    if a_jour(dst, sig):
        return dst
    txt = dst + ".txt"
    open(txt, "w", encoding="utf-8").write(texte)
    brut = dst[:-4] + "_brut.mp3" if v.get("effet") else dst
    # Le service Edge refuse parfois une requête (« No audio was received ») après une longue série de voix :
    # on réessaie en espaçant les essais (≈ 1 min 30 au total) avant d'abandonner.
    attentes = [0, 3, 8, 15, 25, 40]
    for k, attente in enumerate(attentes):
        if attente:
            log(f"  voix refusée par le service Edge ({_raison(r.stderr)}) — nouvel essai dans {attente} s ({k + 1}/{len(attentes)})")
            time.sleep(attente)
        if os.path.exists(brut):
            os.remove(brut)                 # fichier vide ou partiel d'un essai précédent
        try:
            r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", v["nom"],
                                f"--rate={v.get('debit', '+0%')}", f"--pitch={v.get('hauteur', '+0Hz')}",
                                "-f", txt, "--write-media", brut], capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            r = subprocess.CompletedProcess([], 1, "", "délai dépassé (120 s)")
        if "No module named edge_tts" in (r.stderr or ""):
            raise RuntimeError("module edge-tts absent : lancer INSTALLER.bat")
        if r.returncode == 0 and os.path.exists(brut) and os.path.getsize(brut) > 0:
            if brut != dst:                 # effet de voix (écho du Seigneur…)
                from langues import EFFETS
                run([FFMPEG, "-y", "-i", brut, "-af", EFFETS.get(v["effet"], "anull"), dst])
                os.remove(brut)
            marquer(dst, sig)
            return dst
    raise RuntimeError(f"Voix Edge indisponible après {len(attentes)} essais ({_raison(r.stderr)}). Les plans déjà calculés "
                       "sont gardés : relancer le montage reprend à ce plan. Si l'erreur persiste : vérifier la connexion "
                       "internet, puis mettre edge-tts à jour (python -m pip install -U edge-tts).")


def _raison(stderr):
    """Dernière ligne utile d'une erreur edge-tts (« No audio was received… », délai…)."""
    lignes = [l.strip() for l in (stderr or "").splitlines() if l.strip()]
    return (lignes[-1] if lignes else "aucun message")[-160:]


# ---------------------------------------------------------------- image
def mouvement(m, frames):
    zs = {
        "in":   (f"1.0+0.12*on/{frames}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        "out":  (f"1.12-0.12*on/{frames}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        "left": ("1.12", f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"),
        "right": ("1.12", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"),
        "up":   ("1.12", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-on/{frames})"),
        "down": ("1.12", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*on/{frames}"),
        "still": ("1.03", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    }
    return zs.get(m, zs["in"])


def titre(texte, L, wd, nom, taille=64, y="h*0.80", couleur="0xE8D9A8"):
    """drawtext via textfile= (chemins relatifs, aucun échappement d'apostrophes nécessaire)."""
    if not texte:
        return ""
    rel = f"t_{nom}.txt"
    open(os.path.join(wd, rel), "w", encoding="utf-8").write(texte)
    a = f"'if(lt(t,0.6),0,if(lt(t,1.2),(t-0.6)/0.6,if(lt(t,{L-0.8:.2f}),1,max(0,({L:.2f}-t-0.2)/0.6))))'"
    return (f",drawtext=fontfile={police(wd)}:textfile={rel}:fontsize={taille}:fontcolor={couleur}"
            f":x=(w-text_w)/2:y={y}:shadowcolor=black@0.8:shadowx=3:shadowy=3:alpha={a}")


def police(wd):
    """Chemin relatif (sans « C: ») vers la police, pour le filtre drawtext."""
    for p in (chemin("polices", "titre.ttf"), os.path.join(ICI, "polices", "Cinzel.ttf")):
        if os.path.exists(p):
            try:
                return os.path.relpath(p, wd).replace("\\", "/")
            except ValueError:          # autre lecteur : on copie la police dans le dossier de travail
                shutil.copy(p, os.path.join(wd, "police.ttf")); return "police.ttf"
    return "police.ttf"


def carton(principal, sous, L, wd, nom):
    f = (f"color=c=0x07060a:s={W}x{H}:d={L}:r={FPS}"
         + titre(principal, L, wd, nom + "a", 96, "h*0.40")
         + titre(sous, L, wd, nom + "b", 44, "h*0.56", "0xBFB49A")
         + f",fade=t=in:st=0:d=0.5,fade=t=out:st={L-0.6:.2f}:d=0.6")
    run([FFMPEG, "-y", "-f", "lavfi", "-i", f, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", nom + ".mp4"], cwd=wd)


FONDUS = ("noir", "aucun", "enchaine")


def fondu_de(s, pj=None):
    """Transition d'un plan : « noir » (fondu au noir à l'entrée et à la sortie, par défaut), « aucun » (coupe franche)
    ou « enchaine » (fondu enchaîné depuis la dernière image du plan précédent, durée « fondu_d », 0,5 s par défaut :
    diapositives, étapes d'apparition d'un texte). Champ « fondu » du plan, sinon projet.json > fondu_plans."""
    f = s.get("fondu") or (pj if pj is not None else projet()).get("fondu_plans") or "noir"
    return f if f in FONDUS else "noir"


def duree_fondu(s, L):
    """Durée du fondu enchaîné d'un plan (bornée pour laisser le plan lisible)."""
    try:
        d = float(s.get("fondu_d", 0.5))
    except (TypeError, ValueError):
        d = 0.5
    return round(max(0.1, min(d, 3.0, L * 0.6)), 2)


def enchainer(wd, nom, precedent, d):
    """Fondu enchaîné : les d premières secondes du plan « nom » passent de la dernière image du clip précédent
    à son image (durée du plan inchangée : la voix et la musique restent calées). Sans clip précédent : fondu depuis le noir."""
    clip = os.path.join(wd, nom + ".mp4")
    if not precedent:
        run([FFMPEG, "-y", "-i", nom + ".mp4", "-vf", f"fade=t=in:st=0:d={d}", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "19", "-pix_fmt", "yuv420p", nom + "_x.mp4"], cwd=wd)
    else:
        run([FFMPEG, "-y", "-sseof", "-0.2", "-i", precedent, "-update", "1", "-q:v", "2", nom + "_avant.png"], cwd=wd)
        fc = (f"[0:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1[a];[1:v]fps={FPS},format=yuv420p,setsar=1[b];"
              f"[a][b]xfade=transition=fade:duration={d}:offset=0[v]")
        run([FFMPEG, "-y", "-loop", "1", "-t", f"{d}", "-i", nom + "_avant.png", "-i", nom + ".mp4", "-filter_complex", fc,
             "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", nom + "_x.mp4"], cwd=wd)
    os.replace(os.path.join(wd, nom + "_x.mp4"), clip)


def plan(s, L, src, wd, nom, est_video, fondu_plan="noir", dernier=False):
    frames = int(round(L * FPS))
    tf = titre(s.get("title", ""), L, wd, nom)
    fondu = f",fade=t=in:st=0:d=0.35,fade=t=out:st={L-0.35:.2f}:d=0.35" if fondu_plan == "noir" else ""
    if fondu_plan == "enchaine" and dernier:                # fin du film : fondu au noir de sortie
        fondu = f",fade=t=out:st={max(0, L - 0.8):.2f}:d=0.8"
    eq = ",eq=contrast=1.05:saturation=1.12:brightness=0.03"
    if est_video:
        vitesse = max(1.0, L / duree(src))
        vf = (f"setpts={vitesse:.4f}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}"
              f",trim=duration={L},setpts=PTS-STARTPTS{eq}{tf}{fondu}")
        run([FFMPEG, "-y", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
             "-pix_fmt", "yuv420p", nom + ".mp4"], cwd=wd)
    else:
        z, x, y = mouvement(s.get("m", s.get("motion", "in")), frames)
        vf = (f"scale=2880:1620:force_original_aspect_ratio=increase,crop=2880:1620,"
              f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}{eq}{tf}{fondu}")
        run([FFMPEG, "-y", "-loop", "1", "-i", src, "-vf", vf, "-frames:v", frames, "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", nom + ".mp4"], cwd=wd)


# ---------------------------------------------------------------- musique
def musique(total, sections, wd):
    """sections : [(debut_s, piste, decalage[, fx])] ; fondu enchaîné de 3 s entre pistes.
    fx (effets.lire(plan, "mus")) : fondus d'entrée / de sortie, volume et effet de cette section."""
    import effets
    XF = 3.0
    dossiers = [dossier("musique"), os.path.join(ICI, "musique")]
    entrees, chaine = [], []
    for k, sec in enumerate(sections):
        t0, piste, off = sec[:3]
        fx = sec[3] if len(sec) > 3 else {}
        t1 = sections[k + 1][0] if k + 1 < len(sections) else total
        L = (t1 - t0) + (XF if k + 1 < len(sections) else 0)
        f = next((os.path.join(d, piste + ext) for d in dossiers for ext in (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac")
                  if os.path.exists(os.path.join(d, piste + ext))), "")
        if not f:
            log(f"  (musique absente : {piste}, section ignorée)")
            continue
        seg = f"mus{k:02d}.wav"
        fin = 0.5 if k == 0 else XF
        af = ",".join(["loudnorm=I=-20:TP=-2"] + effets.chaine(fx, L=L, fin_def=fin, fout_def=XF))
        run([FFMPEG, "-y", "-stream_loop", "-1", "-ss", off, "-i", f, "-t", f"{L:.2f}", "-af", af,
             "-ar", "44100", "-ac", "2", seg], cwd=wd)
        entrees.append((t0, seg))
    if not entrees:
        run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{total:.2f}", "fond.wav"], cwd=wd)
        return
    args = [FFMPEG, "-y"]
    for _, sg in entrees:
        args += ["-i", sg]
    fc = ";".join(f"[{i}:a]adelay={int(t0 * 1000)}|{int(t0 * 1000)}[d{i}]" for i, (t0, _) in enumerate(entrees))
    fc += ";" + "".join(f"[d{i}]" for i in range(len(entrees))) + \
          f"amix=inputs={len(entrees)}:normalize=0,atrim=0:{total:.2f},afade=t=out:st={max(0, total - 5):.2f}:d=5[m]"
    run(args + ["-filter_complex", fc, "-map", "[m]", "-ar", "44100", "-ac", "2", "fond.wav"], cwd=wd)


# ---------------------------------------------------------------- montage
def monter(ep, reprendre=True, langue=None):
    """Monte un épisode. langue : None (langue d'origine) ou code d'une version (ex. "en") déclarée dans le projet."""
    import langues as lg
    pj = projet()
    if lg.est_source(langue, pj):
        langue = None
    elif langue not in lg.versions(pj):
        raise RuntimeError(f"Langue « {langue} » non déclarée : ajoute-la dans Projet > Versions linguistiques.")
    e = lg.localiser(charger_episode(ep), langue, pj)
    if e.get("_a_revoir"):
        log(f"  ATTENTION : {len(e['_a_revoir'])} traduction(s) à revoir (texte d'origine modifié depuis) : "
            + ", ".join(e["_a_revoir"][:10]))
    v_langue = lg.voix_de(langue, pj)
    wd = os.path.join(ICI, "travail", slug_projet(pj["nom"]), ep + (f".{langue}" if langue else ""))
    if langue:
        log(f"Version {lg.nom_langue(langue)} — voix {v_langue['nom']}")
    if not reprendre and os.path.isdir(wd):
        shutil.rmtree(wd)
    os.makedirs(wd, exist_ok=True)
    clips, segs, manquants, textes, sons_video = [], [], [], {}, []
    prec_sig = None                                  # signature du clip précédent (fondu enchaîné)
    for i, s in enumerate(e["shots"]):
        nom = f"p{i:03d}"
        if s.get("card"):
            L = float(s.get("dur", 6))
            sig = signature("carton", s["card"], s.get("sub", ""), L)
            if not a_jour(os.path.join(wd, nom + ".mp4"), sig):
                carton(s["card"], s.get("sub", ""), L, wd, nom)
                marquer(os.path.join(wd, nom + ".mp4"), sig)
            clips.append(nom + ".mp4"); segs.append((L, None)); prec_sig = sig; continue
        vo = s.get("vo", "").strip()
        a, d = None, 0.0
        if s.get("voix_fichier") and not langue:     # narration enregistrée ou importée (langue d'origine seulement)
            from contexte import fichier
            a = fichier(s["voix_fichier"]) or None
            if a:
                d = duree(a)
            else:
                log(f"  voix introuvable : {s['voix_fichier']} (repli sur la voix de synthèse)")
        if a is None and vo:
            a = voix(vo, os.path.join(wd, nom + ".mp3"), lg.voix_plan(s, langue, pj)); d = duree(a)
        L = round(max(float(s.get("min", 4.0)), d + float(s.get("pad", 1.5))), 2)
        src, est_video = trouver_media(ep, s, wd)
        fd = fondu_de(s, pj)
        dernier = i == len(e["shots"]) - 1
        extra = [] if fd == "noir" else [fd]
        if fd == "enchaine":                         # dépend aussi de l'image de fin du plan précédent
            extra += [duree_fondu(s, L), prec_sig, dernier]
        sig = signature("plan", L, empreinte_media(src), est_video, s.get("m", s.get("motion", "in")), s.get("title", ""),
                        *extra)
        if src is None:
            manquants.append(s.get("k"))
        if not a_jour(os.path.join(wd, nom + ".mp4"), sig):
            if src is None:
                carton("", f"[plan manquant : {s.get('k')}]", L, wd, nom)
            else:
                plan(s, L, src, wd, nom, est_video, fd, dernier)
                if fd == "enchaine":
                    enchainer(wd, nom, clips[-1] if clips else None, duree_fondu(s, L))
            marquer(os.path.join(wd, nom + ".mp4"), sig)
        prec_sig = sig
        clips.append(nom + ".mp4"); segs.append((L, a)); textes[len(segs) - 1] = (vo, d)
        if s.get("son_video") and est_video and src and a_un_son(src):     # son de la vidéo gardé (horde générée avec son…)
            sv = f"sv{i:03d}.wav"
            run([FFMPEG, "-y", "-i", src, "-vn", "-af", f"loudnorm=I=-26:TP=-3,apad=whole_dur={L},atrim=0:{L},"
                 f"afade=t=in:d=0.3,afade=t=out:st={max(0, L - 0.5):.2f}:d=0.5", "-ar", "44100", "-ac", "2", sv], cwd=wd)
            sons_video.append((i, sv, float(s.get("son_video_vol", 1))))
        log(f"  plan {i + 1}/{len(e['shots'])} {s.get('k', '')} ok ({L:.1f} s)")
    open(os.path.join(wd, "liste.txt"), "w", encoding="utf-8").write("".join(f"file '{c}'\n" for c in clips))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", "video.mp4"], cwd=wd)
    import effets
    parts = []
    for k, (L, a) in enumerate(segs):
        p = f"n{k:03d}.wav"
        if a:
            fx = effets.lire(e["shots"][k], "voix")       # fondus, volume, effet de la voix de ce plan
            pre = effets.chaine(fx, L=duree(a)) if fx else []
            run([FFMPEG, "-y", "-i", a, "-af", ",".join(pre + [f"adelay=450|450,apad=whole_dur={L},atrim=0:{L}"]),
                 "-ar", "44100", "-ac", "2", p], cwd=wd)
        else:
            run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(L), p], cwd=wd)
        parts.append(p)
    open(os.path.join(wd, "aliste.txt"), "w", encoding="utf-8").write("".join(f"file '{p}'\n" for p in parts))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "aliste.txt", "-c", "pcm_s16le", "voix.wav"], cwd=wd)
    total = duree(os.path.join(wd, "video.mp4"))
    debuts, t = [], 0.0
    for L, _ in segs:
        debuts.append(t); t += L
    sections = [(debuts[i], s["mus"], float(s.get("mus_off", 0)), effets.lire(s, "mus"))
                for i, s in enumerate(e["shots"]) if s.get("mus")]
    if not sections:
        sections = [(0.0, projet().get("musique_defaut", "Lord_of_the_Land"), 0.0)]
    sections[0] = (0.0,) + tuple(sections[0][1:])
    musique(total, sections, wd)
    import sons
    bruits = sons.piste(e["shots"], debuts, [L for L, _ in segs], total, wd,
                        [(debuts[i], f, v) for i, f, v in sons_video], signature, a_jour, marquer)
    vol = pj.get("volume_musique", 0.47)
    if bruits:                       # ambiances et bruitages : sous la musique, baissés aussi quand on parle
        va = pj.get("volume_ambiance", 0.8)
        run([FFMPEG, "-y", "-i", "voix.wav", "-i", "fond.wav", "-i", bruits, "-filter_complex",
             f"[0:a]loudnorm=I=-16:TP=-1.5,asplit=3[v1][v2][v3];[1:a]volume={vol}[b];[2:a]volume={va}[s];"
             f"[b][v1]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600[bd];"
             f"[s][v3]sidechaincompress=threshold=0.03:ratio=3:attack=40:release=700[sd];"
             f"[bd][sd][v2]amix=inputs=3:normalize=0,alimiter=limit=0.97,atrim=0:{total:.2f}[m]",
             "-map", "[m]", "-ar", "44100", "mix.wav"], cwd=wd)
    else:
        run([FFMPEG, "-y", "-i", "voix.wav", "-i", "fond.wav", "-filter_complex",
             f"[0:a]loudnorm=I=-16:TP=-1.5,asplit=2[v1][v2];[1:a]volume={vol}[b];"
             f"[b][v1]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600[bd];"
             f"[bd][v2]amix=inputs=2:normalize=0,atrim=0:{total:.2f}[m]",
             "-map", "[m]", "-ar", "44100", "mix.wav"], cwd=wd)
    nom_sortie = f"{e['id']}_{slug(e.get('title', ''))}{lg.suffixe(langue, pj)}.mp4"
    sortie = dossier("rendus", *([langue] if langue else []), nom_sortie, creer=True)
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    if os.path.exists(sortie):
        base, n = sortie[:-4], 2
        while os.path.exists(f"{base}_v{n}.mp4"):
            n += 1
        sortie = f"{base}_v{n}.mp4"
    partiel = sortie + ".part"           # un montage arrêté en cours de route ne laisse pas de vidéo tronquée dans les rendus
    run([FFMPEG, "-y", "-i", "video.mp4", "-i", "mix.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "-f", "mp4", partiel], cwd=wd)
    os.replace(partiel, sortie)
    # sous-titres calés sur la voix (la narration démarre 0,45 s après le début du plan)
    segments = [(debuts[k] + 0.45, textes[k][1], textes[k][0]) for k in sorted(textes)]
    sous_titres = sortie[:-4] + ".srt"
    open(sous_titres, "w", encoding="utf-8").write(lg.srt(segments))
    res = {"sortie": sortie, "sous_titres": sous_titres, "langue": langue or lg.source(pj),
           "duree_s": round(duree(sortie), 1), "plans": len(clips), "plans_manquants": manquants}
    log(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    lang = sys.argv[sys.argv.index("--langue") + 1] if "--langue" in sys.argv else None
    monter(sys.argv[1], reprendre="--neuf" not in sys.argv, langue=lang)
