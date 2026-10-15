#!/usr/bin/env python3
"""MKS Movie Producer — moteur de montage local (Windows / Mac / Linux).

Entrée  : <projet>/episodes/<EP>.json  +  images/vidéos dans <projet>/Flow/<EP>/<clé>.png|jpg|mp4
Sortie  : <projet>/Rendus/<EP>_<titre>.mp4

Pas de shell : toutes les commandes ffmpeg sont passées en listes d'arguments,
ce qui évite les problèmes d'apostrophes et d'espaces dans les chemins Windows.
"""
import hashlib, json, os, re, subprocess, sys, shutil, urllib.request, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))          # dossier du logiciel
sys.path.insert(0, ICI)
from contexte import racine, projet, chemin, slug as slug_projet

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
    dossier = chemin("Flow", ep)
    if k:
        for ext in (".mp4", ".mov", ".webm"):
            p = os.path.join(dossier, k + ext)
            if os.path.exists(p):
                return p, True
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".PNG", ".JPG"):
            p = os.path.join(dossier, k + ext)
            if os.path.exists(p):
                return p, False
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


def charger_episode(ep):
    return json.load(open(chemin("episodes", ep + ".json"), encoding="utf-8"))


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


def voix(texte, dst):
    v = projet()["voix"]
    sig = signature(texte, v.get("nom"), v.get("debit"), v.get("hauteur"))
    if a_jour(dst, sig):
        return dst
    txt = dst + ".txt"
    open(txt, "w", encoding="utf-8").write(texte)
    for _ in range(3):
        r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", v["nom"],
                            f"--rate={v['debit']}", f"--pitch={v['hauteur']}",
                            "-f", txt, "--write-media", dst], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(dst):
            marquer(dst, sig)
            return dst
    raise RuntimeError("Voix Edge indisponible (connexion internet ?) : " + r.stderr[-300:])


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


def plan(s, L, src, wd, nom, est_video):
    frames = int(round(L * FPS))
    tf = titre(s.get("title", ""), L, wd, nom)
    fondu = f",fade=t=in:st=0:d=0.35,fade=t=out:st={L-0.35:.2f}:d=0.35"
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
    """sections : [(debut_s, piste, decalage)] ; fondu enchaîné de 3 s entre pistes."""
    XF = 3.0
    dossiers = [chemin("musique"), os.path.join(ICI, "musique")]
    entrees, chaine = [], []
    for k, (t0, piste, off) in enumerate(sections):
        t1 = sections[k + 1][0] if k + 1 < len(sections) else total
        L = (t1 - t0) + (XF if k + 1 < len(sections) else 0)
        f = next((os.path.join(d, piste + ext) for d in dossiers for ext in (".mp3", ".wav", ".m4a")
                  if os.path.exists(os.path.join(d, piste + ext))), "")
        if not f:
            log(f"  (musique absente : {piste}, section ignorée)")
            continue
        seg = f"mus{k:02d}.wav"
        fin = 0.5 if k == 0 else XF
        run([FFMPEG, "-y", "-stream_loop", "-1", "-ss", off, "-i", f, "-t", f"{L:.2f}", "-af",
             f"loudnorm=I=-20:TP=-2,afade=t=in:d={fin},afade=t=out:st={max(0, L - XF):.2f}:d={XF}",
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
def monter(ep, reprendre=True):
    e = charger_episode(ep)
    wd = os.path.join(ICI, "travail", slug_projet(projet()["nom"]), ep)
    if not reprendre and os.path.isdir(wd):
        shutil.rmtree(wd)
    os.makedirs(wd, exist_ok=True)
    clips, segs, manquants = [], [], []
    for i, s in enumerate(e["shots"]):
        nom = f"p{i:03d}"
        if s.get("card"):
            L = float(s.get("dur", 6))
            sig = signature("carton", s["card"], s.get("sub", ""), L)
            if not a_jour(os.path.join(wd, nom + ".mp4"), sig):
                carton(s["card"], s.get("sub", ""), L, wd, nom)
                marquer(os.path.join(wd, nom + ".mp4"), sig)
            clips.append(nom + ".mp4"); segs.append((L, None)); continue
        vo = s.get("vo", "").strip()
        a, d = None, 0.0
        if vo:
            a = voix(vo, os.path.join(wd, nom + ".mp3")); d = duree(a)
        L = round(max(float(s.get("min", 4.0)), d + float(s.get("pad", 1.5))), 2)
        src, est_video = trouver_media(ep, s, wd)
        sig = signature("plan", L, empreinte_media(src), est_video, s.get("m", s.get("motion", "in")), s.get("title", ""))
        if src is None:
            manquants.append(s.get("k"))
        if not a_jour(os.path.join(wd, nom + ".mp4"), sig):
            if src is None:
                carton("", f"[plan manquant : {s.get('k')}]", L, wd, nom)
            else:
                plan(s, L, src, wd, nom, est_video)
            marquer(os.path.join(wd, nom + ".mp4"), sig)
        clips.append(nom + ".mp4"); segs.append((L, a))
        log(f"  plan {i + 1}/{len(e['shots'])} {s.get('k', '')} ok ({L:.1f} s)")
    open(os.path.join(wd, "liste.txt"), "w", encoding="utf-8").write("".join(f"file '{c}'\n" for c in clips))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", "video.mp4"], cwd=wd)
    parts = []
    for k, (L, a) in enumerate(segs):
        p = f"n{k:03d}.wav"
        if a:
            run([FFMPEG, "-y", "-i", a, "-af", f"adelay=450|450,apad=whole_dur={L},atrim=0:{L}",
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
    sections = [(debuts[i], s["mus"], float(s.get("mus_off", 0))) for i, s in enumerate(e["shots"]) if s.get("mus")]
    if not sections:
        sections = [(0.0, projet().get("musique_defaut", "Lord_of_the_Land"), 0.0)]
    sections[0] = (0.0, sections[0][1], sections[0][2])
    musique(total, sections, wd)
    vol = projet().get("volume_musique", 0.47)
    run([FFMPEG, "-y", "-i", "voix.wav", "-i", "fond.wav", "-filter_complex",
         f"[0:a]loudnorm=I=-16:TP=-1.5,asplit=2[v1][v2];[1:a]volume={vol}[b];"
         f"[b][v1]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600[bd];"
         f"[bd][v2]amix=inputs=2:normalize=0,atrim=0:{total:.2f}[m]",
         "-map", "[m]", "-ar", "44100", "mix.wav"], cwd=wd)
    os.makedirs(chemin("Rendus"), exist_ok=True)
    sortie = chemin("Rendus", f"{e['id']}_{slug(e.get('title', ''))}.mp4")
    if os.path.exists(sortie):
        base, n = sortie[:-4], 2
        while os.path.exists(f"{base}_v{n}.mp4"):
            n += 1
        sortie = f"{base}_v{n}.mp4"
    run([FFMPEG, "-y", "-i", "video.mp4", "-i", "mix.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", sortie], cwd=wd)
    res = {"sortie": sortie, "duree_s": round(duree(sortie), 1), "plans": len(clips), "plans_manquants": manquants}
    log(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    monter(sys.argv[1], reprendre="--neuf" not in sys.argv)
