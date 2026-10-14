#!/usr/bin/env bash
# MKS Movie Producer — installation macOS / Linux
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "Installer ffmpeg : brew install ffmpeg  (macOS)  ou  sudo apt install ffmpeg  (Linux)"; }
python3 -m pip install --upgrade -r requirements.txt
mkdir -p polices musique
[ -f polices/Cinzel.ttf ] || curl -fsSL -o polices/Cinzel.ttf "https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf"
for t in "Clash Defiant" "Crusade - Heavy Industry" "Dark Walk" "Darkest Child" "Echoes of Time v2" "Ever Mindful" "Heroic Age" \
         "Interloper" "Lightless Dawn" "Long Note Four" "Lord of the Land" "Ossuary 6 - Air" "Prelude and Action" "Rising Game"; do
  f="musique/${t// /_}.mp3"
  [ -f "$f" ] || curl -fsSL -o "$f" "https://incompetech.com/music/royalty-free/mp3-royaltyfree/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$t").mp3"
done
echo "Installation terminée. Lancer : python3 pilotage.py"
