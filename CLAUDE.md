# MKS Movie Producer — notes pour Claude

Application locale Python (bibliothèque standard + ffmpeg) pour produire des séries narrées par IA.
Répondre en français à l'utilisateur.

## Architecture
- `contexte.py` : sépare le LOGICIEL (ce dossier : code, `reglages.json`, `poste.json`, musiques, police)
  du PROJET actif (dossier de données, voir README). `racine()` = projet actif (variable `STUDIO_PROJET`,
  sinon `poste.json`, sinon dossier parent). `projet()` lit `projet.json`. `migrer()` convertit l'ancien format.
- `pilotage.py` : serveur HTTP local (127.0.0.1:8765) + API JSON ; interface dans `web/index.html` (vanilla JS).
  Vue Studio d'un épisode (montage : moniteur, timeline, inspecteur, bibliothèque) dans `web/studio.js` + `web/studio.css`
  (servis par `/web/…`) ; elle modifie directement `EP` et réutilise `sauver()`. Bibliothèque : `GET /api/bibliotheque?ep=`,
  musiques servies par `/musique/<nom>`, import sans écrasement : `PUT /api/fichier?unique=1&dest=…`.
  Timeline : pistes Vidéo, Titres, Voix, Musique, Ambiance (`ST.amb`, sections calculées dans `stCalcul` d'après `amb`) et
  Bruitage (`ST.sfx`, un repère par plan) ; l'aperçu joue les sons via l'extrait de `POST /api/sons/essai` (`stUrlSon`).
  **Toute couche ajoutée au moteur (`moteur.py`) doit avoir sa piste et son écoute dans le Studio.**
  Effets audio (`effets.py`) : `fx.<voix|mus|amb|sfx> = {in, out, vol, effet}` sur un plan ; réglés dans l'inspecteur
  (`blocFx`, champs `data-st="fx.<couche>.<clé>"` gérés par `stChamp`), dessinés sur les blocs (`fxDessin`), entendus
  dans l'aperçu par WebAudio (`stRoute`/`stEffet`/`stGain`, effets approchés). Liste des effets : `GET /api/sons > effets`.
  Disposition : séparateurs `.st-gut` (glisser = largeur de la bibliothèque / de l'inspecteur, hauteur de la timeline ;
  double-clic ou bouton `.st-pli` = replier), appliquée par `stDisposer()`, gardée par poste dans `localStorage`
  (`ua_studio_dispo`) ; `stDispoDefaut()` remet les tailles d'origine. La grille `.st-body` place chaque enfant par
  `grid-column` explicite (un panneau replié est en `display:none`).
  Favicon de l'application : `web/img/favicon.svg` (source, dessin 64×64), `favicon.ico` (16/32/48) et
  `apple-touch-icon.png` (180) qui en sont tirés ; servis par `/web/img/…` et `/favicon.ico`. Redessiner les deux images
  si le SVG change.
  Les tâches longues lancent `atelier.py <commande>` en sous-processus avec `STUDIO_PROJET`.
- `adresses.py` : adresse dédiée par projet. `GET /<adresse>/` (tout serveur) → `demarrer()` lance au besoin
  `pilotage.py --projet <dossier> --port <p> --parent <port>` sans fenêtre, puis redirige vers `http://localhost:<p>/`.
  Adresse = `projet.json > adresse` (validée par `valider` : `RESERVES`, unicité) sinon `slug(nom)` ; port mémorisé dans
  `poste.json > projets[].port`. Un serveur lancé avec `STUDIO_PROJET`/`--projet` est **dédié** (`DEDIE`) : il ne change
  jamais `projet_actif` (`cx.ajouter_au_poste`), et y ouvrir/créer un autre projet renvoie son `url`. `--parent` : arrêt
  quand le serveur parent ne répond plus (`surveiller_parent`). `GET /api/identite` dit quel projet sert un port.
  `PILOTAGE.bat <adresse|dossier>` démarre un projet dédié. Tout nouveau premier segment d'URL de l'application doit
  entrer dans `adresses.RESERVES`.
- `atelier.py` : CLI — `monter [--langue en]`, `etat`, `fiche`, `lots`, `ecrire`, `prompts`, `verifier`, `bible`, `traduire`, `exporter`.
- `moteur.py` : montage ffmpeg (arguments en listes, jamais de shell), voix `edge_tts`, musique par sections
  (champ `mus` d'un plan = changement de piste), plans recalculés seulement si leur empreinte change (`.sig`), sortie dans le dossier des rendus (jamais d'écrasement).
- `ia.py` : appels modèles (Anthropic ou compatible OpenAI) selon `reglages.json > ia > par_tache`,
  lecture des sources (PDF, docx, txt…), génération bible/plan/épisodes, relecture d'images.
- `cles.py` : profils de modèles et clés (keyring, repli `.cles.json`).
- `fiche.py` : fiche de prompts d'un épisode (tags `[TAG]` de personnages remplacés par leur description).
- `lots.py` : export par lots d'une fiche (relit la fiche générée : un fichier par type IMG/VID et par combinaison de
  personnages, + `<EP>_index.csv` ordre → nom final) dans `<dossier fiches>/lots/<EP>/`. Commande `lots`, `POST /api/lots`.
  Dépend du format des en-têtes de la fiche (`--- E104-01.png  [VOYANT, SAGESSE]`) : le garder compatible si `fiche.py` change.
- Logo : `projet.json > logo` (fixe, `/api/logo`) et `logo_anime` (facultatif, `/api/logo/anime` : WebM transparent conseillé,
  MP4, GIF, WebP, SVG). Import `PUT /api/fichier?dest=logo_anime.<ext>`, retrait `POST /api/projet/logo_anime`. `PUT /api/projet`
  conserve `logo_anime` si la page ne l'envoie pas. Interface : `logoAnime(sel, taille)` dans `web/index.html` (joué une fois,
  arrêt sur la dernière image, survol = rejouer ; la bannière le rejoue en changeant de page, au plus une fois par minute :
  `logoRejouer()` appelé par `go()`). Le logo animé est une donnée de projet : absent sur un poste dont les données n'ont pas
  été copiées.
- `sons.py` : ambiances et bruitages (voir plus bas). `langues.py` : versions linguistiques (voir plus bas). `logo.py` : logos SVG générés. `mcp_server.py` : outils MCP.

## Organisation d'un projet (aucun chemin en dur)
Seuls `projet.json` et `suivi.json` sont à la racine. Les dossiers de travail s'obtiennent TOUJOURS par
`contexte.dossier(rôle, *sous_parties)` — rôles : `sources`, `personnages`, `bible`, `episodes`, `fiches`, `images`,
`rendus`, `exports`, `musique`, `sons` (voir `ROLES`). La carte est dans `projet.json > dossiers` ; un dossier déplacé est
retrouvé d'après son contenu (`detecter`) puis mémorisé. Les fichiers notés en relatif (livre, logo, références)
passent par `contexte.fichier(rel)` (recherche par nom), et `reparer_fichiers()` met `projet.json` à jour.
Média d'un plan hors du dossier des images : `chercher_media(clé)`. Ne jamais écrire `chemin("Flow", …)`.
Nouveau projet : `DISPOSITION_NOUVEAU` (bibliotheque/… et production/…). `ranger_racine()` range un projet existant.

## Format d'un épisode (`<dossier episodes>/E104.json`)
`{"id":"S1E04","title":"…","shots":[{"k":"E104-01","vo":"narration","p":"prompt image anglais","m":"in|out|left|right|up|down|still",
"title":"MOT À L'ÉCRAN","min":5,"mus":"Heroic_Age","vid_prompt":"…"},{"card":"TITRE","sub":"…","dur":7}, …]}`
Réplique : `"qui": "SAGESSE"` sur un plan = `vo` dit par ce personnage (mots prononcés seulement) avec sa voix
`personnages[].voix.<langue>` (+ `effet` echo|grave|lointain, `sans_visage`) ; sans `qui` ni voix → narrateur
(`langues.voix_plan`). La fiche marque les RÉPLIQUES et demande des vidéos où le personnage parle (son Flow coupé).
Sons (`sons.py`) : `"amb": "horde"` = ambiance qui démarre à ce plan et continue jusqu'au prochain `amb` (`"aucune"` coupe,
`amb_vol` = niveau) ; `"sfx": "cor"` ou liste = bruitage au début du plan (`sfx_t` décalage) ; `"son_video": true` garde le son
de la vidéo du plan. Source : `<dossier sons>/<nom>.mp3|wav…` sinon synthèse ffmpeg de repli (`sons.CATALOGUE`, recettes
`aevalsrc`/`anoisesrc` ; incrémenter `VERSION` si une recette change). Mixage : voix + musique + sons, ces deux derniers
baissés par la voix (`sidechaincompress`) ; `projet.json > volume_ambiance`. Les IA qui réécrivent le JSON recollent ces
champs (`ia.GARDES`).
Effets audio (`effets.py`) : `"fx": {"voix"|"mus"|"amb"|"sfx": {"in": s, "out": s, "vol": ×, "effet": clé de EFFETS}}` —
fondus (remplacent ceux par défaut de la couche), volume, effet ffmpeg (`effets.chaine`). `mus`/`amb` valent pour la section
qui démarre à ce plan ; le niveau d'une ambiance / d'un bruitage reste `amb_vol` / `sfx_vol`. Filtres sans hypothèse de
fréquence (entrée ramenée à 44,1 kHz) ; `grave`/`aigu` compensent la durée (`atempo`). Les signatures des sons incluent `fx`.
Médias : `<dossier images>/E104/E104-01.png` (ou `.mp4`, prioritaire), sinon même nom ailleurs dans le projet ; à défaut `img_url`/`vid_url`.
Transition : `"fondu": "noir"|"aucun"` sur un plan, sinon `projet.json > fondu_plans` (défaut `noir` = fondu au noir 0,35 s à
l'entrée et à la sortie ; `aucun` = coupe franche) — `moteur.fondu_de()`, dans la signature du plan seulement si ≠ `noir`
(les caches existants restent valides) ; reproduit par l'aperçu du Studio, réglé dans l'inspecteur et dans Projet.
Champs posés par la vue Studio (facultatifs) : `media` (image/vidéo choisie, chemin relatif au projet, PRIORITAIRE sur la clé),
`voix_fichier` (narration enregistrée/importée, remplace la synthèse pour la langue d'origine seulement), `mus_off` (décalage
en s dans la piste `mus`). Les résoudre par `contexte.fichier(rel)` ; `ia._garder_traductions` les recolle après une réécriture IA.

## Versions linguistiques (`langues.py`)
Une seule série, plusieurs langues : plans, images et musiques communs ; textes et voix par langue, une vidéo par langue.
`projet.json > langue` (origine) et `versions` : `{"en": {"titre": "The Final Quest", "voix": {"nom", "debit", "hauteur"}}}`.
Traductions DANS le JSON de l'épisode : `"versions": {"en": {"vo", "title", "de", "media"?}}` sur chaque plan, `{"card", "sub", "de"}`
sur les cartons, `{"title", "de"}` sur l'épisode. `de` = empreinte du texte d'origine traduit (`langues.empreinte`) :
si l'origine change, statut `a_revoir`. Toujours écrire une traduction via `langues.poser()` (calcule `de`).
`versions.<langue>.media` = image/vidéo propre à la langue (texte incrusté) : `localiser()` la substitue à `media`, elle
**ne compte pas comme une traduction** (`langues.a_du_texte` ; `statut`, `poser` qui la conserve, `sauver_episode` qui ne
pose pas `de` pour elle seule) ; écrite par `langues.poser_media()` ou le bouton « Choisir pour EN » de l'inspecteur
(`ST.cibleLangue` → `stAppliquer`).
`ia.traduire_episode` est incrémental (manquantes + à revoir). `moteur.monter(ep, langue="en")` : `localiser()` refuse
un épisode incomplet, travail dans `travail/<projet>/<EP>.en`, sortie `<rendus>/en/<ID>_<titre>_EN.mp4`. Chaque montage
écrit un `.srt` calé sur la voix (`langues.srt`). L'éditeur envoie `_retouche: ["en"]` pour une traduction corrigée à la
main (le serveur remet `de` à jour). Toute IA qui réécrit le JSON complet doit recoller les `versions`
(`ia._garder_traductions`).

## Documentation
`docs/MANUEL_INSTALLATION.md` et `docs/MANUEL_UTILISATION.md` (servis dans l'interface, menu Aide, via `/api/aide/<nom>`
et `/aide/…`). Captures dans `docs/images/`. **Pas de PDF ni de .docx dans le dépôt** (binaires lourds, conflits à chaque PR) :
la version Word est fabriquée à la demande par `docs/generer_docx.py` (bibliothèque standard seule) — bouton « Télécharger en
Word » du menu Aide (`GET /aide/word/<installation|utilisation>`, cache `cache/manuels/`, refaite si le .md ou une capture
change) ou `python docs/generer_docx.py [dossier]`. Le convertisseur gère titres, paragraphes, listes, tableaux, blocs de code,
encadrés `>` et images seules sur leur ligne : rester dans ce sous-ensemble de Markdown. Tenir les manuels à jour quand une
fonction change.

## Dépôt et conventions
Branche `main` (dépôt GitHub privé), messages de commit en français. **Deux PR par demande, pas plus** : celle de ce dépôt
(code, manuels **et ce `CLAUDE.md`**, mis à jour dans la même PR que l'évolution qui le rend inexact) et celle de la mémoire
dans `mon-second-cerveau-mks-777`. Pas de PR séparée pour `CLAUDE.md`. Le poste de l'utilisateur est une copie du dépôt
(`git pull` via `METTRE_A_JOUR.bat`) : ne jamais committer de données de projet ni de clés. `modele-projet/` est un projet
vide généré par `creer_projet()` (+ `.gitkeep`) : le régénérer si `DISPOSITION_NOUVEAU` ou `DEFAUT_PROJET` change.

## Installer sur un nouveau poste
Windows : `INSTALLER.bat` puis `PILOTAGE.bat`. macOS/Linux : `./install.sh` puis `python3 pilotage.py`.
Ne jamais committer : `reglages.json`, `poste.json`, `.cles.json`, `musique/`, `polices/`, `travail/`, `cache/`.

## Vérifications rapides
`python3 -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('*.py')]"` puis lancer
`python3 pilotage.py --sans-navigateur` et ouvrir http://localhost:8765.

## Règles permanentes du porteur (toutes les sessions Claude sur ce dépôt)

Reprises de sa mémoire partagée — le dépôt GitHub privé `Nathan4KImpact/mon-second-cerveau-mks-777` (index `CLAUDE.md`
à sa racine) —, appliquées à tous ses dépôts. **La mémoire n'est plus sur Google Drive** (depuis le 12/10/2026, Drive = archive en
lecture seule) : ne jamais y écrire.

### 1. Nourrir la mémoire partagée après chaque merge de PR
- Après chaque fusion, relire le diff et se demander : qu'est-ce qui a été appris ici qui resservira **sur un autre projet** ?
  Si rien de transposable, ne rien écrire.
- Sinon, dans le dépôt `Nathan4KImpact/mon-second-cerveau-mks-777` (l'ajouter à la session par `add_repo`, accès `push`,
  puis le cloner) : écrire ou compléter une fiche `memory/skills/expertise_<sujet>.md` (en français, au format des fiches
  voisines, **avec les pièges** qui ont coûté cher), mettre à jour `memory/projects/mks-movie-producer.md` et la liste des
  fiches de l'index `CLAUDE.md` de la mémoire.
- Fichiers modifiés **en place** (l'historique Git sert d'archive), sur une branche et par une PR de ce dépôt-là, fusionnée
  par avance rapide (règle 3) **sans attendre l'accord du porteur** : droit qu'il a donné le 18/10/2026, pour le seul dépôt
  de mémoire. Fusionner une PR de la mémoire ne redéclenche pas cette règle 1.
- **Ne verser que ce qui est fusionné** : une PR ouverte n'entre pas dans la mémoire.

### 2. Pull requests — toujours ouvrir, ne jamais fusionner sans accord
- Toute évolution passe par une branche et une PR, créée en fin de travail sans attendre qu'on la demande.
- **Ne jamais fusionner sans l'accord explicite du porteur** (« tu peux merger »). Sinon : ouvrir la PR, la décrire, s'arrêter.
  Seule exception : les PR du dépôt de mémoire `mon-second-cerveau-mks-777` (règle 1).
- Une PR fusionnée est finie : le travail suivant repart de `main` dans une nouvelle PR. Vérifier l'état réel d'une PR
  avant de dire qu'elle est à jour.

### 3. Git — historique linéaire, mêmes commits sur la branche et sur `main`
- Récupérer avec `git pull --rebase`, jamais de commit de fusion local.
- Fusionner une PR (avec accord) **par avance rapide** : `git fetch`, puis `git push origin <sha de la tête de la PR>:main`.
  GitHub marque alors la PR comme fusionnée — **à condition que la branche de la PR soit poussée avant `main`** : après un
  rebase, pousser d'abord la branche (`--force-with-lease`), puis `main`. Dans l'autre ordre, GitHub ferme la PR sans la
  marquer fusionnée, et elle ne peut plus être rouverte (vu sur la PR #7, 18/10/2026).
- **Jamais** les boutons « Create a merge commit », « Squash » ni « Rebase and merge » (ce dernier recrée les commits).
- Seul force-push admis : rebaser la branche de travail sur `origin/main` puis `git push --force-with-lease`, avant la
  fusion. Jamais sur `main`.
- Le poste du porteur se met à jour par `git pull --ff-only` (`METTRE_A_JOUR.bat`).
