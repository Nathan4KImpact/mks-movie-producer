# MKS Movie Producer

Atelier local de production de mini-séries et films narrés par IA : bible et plan des épisodes,
scripts plan par plan, fiches de prompts pour les générateurs d'images (Google Flow, Higgsfield…),
montage automatique (voix off, musique par scène, titres, mouvements de caméra) et suivi de production.

Premier projet réalisé avec : **L'Ultime Assaut** (7 saisons × 7 épisodes).

## Installation

### Windows
1. Télécharger ce dépôt (bouton *Code › Download ZIP*) ou `git clone`.
2. Double-cliquer sur `INSTALLER.bat` (installe Python, ffmpeg, la voix Edge, les musiques et la police si besoin).
3. Double-cliquer sur `PILOTAGE.bat` : l'interface s'ouvre sur http://localhost:8765.

### macOS / Linux
```bash
./install.sh
python3 pilotage.py
```

### Avec Claude Code
```
claude "Installe MKS Movie Producer depuis ce dossier (lis CLAUDE.md) puis ouvre le projet <chemin du projet>"
```

## Projets
Le logiciel et les données sont séparés. Un **projet** est un dossier autonome :

```
MonProjet/
  projet.json      nom, logo, structure, style, personnages, voix, règles IA
  logo.svg
  sources/         livre (PDF), scripts, notes, documents de référence
  bible/           bible.md, plan.json
  episodes/        scripts des épisodes (E101.json…)
  Characters/      images de référence des personnages
  Flow/E101/       images et vidéos générées (E101-01.png…)
  Prompts_Flow/    fiches de prompts
  Rendus/          épisodes montés
  suivi.json       validations
```

- **Changer de poste** : copier le dossier du projet (ou *Projet › Exporter* en zip), installer le logiciel,
  puis *Projet › Ouvrir un dossier existant*. L'avancement est recalculé à partir des fichiers.
- **Nouveau projet** : *Projet › Nouveau projet*, ajouter les sources, puis suivre l'Assistant
  (bible et plan par IA, épisodes, images, montage, validation).

## IA
Réglages › Modèles IA : Claude (API Anthropic) ou tout service compatible OpenAI (OpenAI, OpenRouter,
Mistral, Gemini, Ollama local). Les clés vont dans le Gestionnaire d'identification du système (keyring),
jamais dans les fichiers.

Serveur MCP (`mcp_server.py`) : Claude Desktop ou Claude Code peuvent piloter le projet actif.

## Crédits
Musiques : Kevin MacLeod (incompetech.com), CC BY 4.0 — à créditer dans les descriptions.
Voix : Microsoft Edge TTS. Police : Cinzel (SIL OFL).
