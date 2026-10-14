# MKS Movie Producer - installation (a lancer via INSTALLER.bat)
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$ici = $PSScriptRoot
Write-Host "=== Installation de MKS Movie Producer ===" -ForegroundColor Yellow

# 1. Python
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
if (-not $py) {
  Write-Host "Python absent : installation via winget..." -ForegroundColor Cyan
  winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
  Write-Host "Python installe. FERME cette fenetre et relance INSTALLER.bat." -ForegroundColor Green
  Read-Host "Entree pour fermer"; exit
}
Write-Host "Python : OK ($py)"

# 2. ffmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "ffmpeg absent : installation via winget..." -ForegroundColor Cyan
  winget install -e --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
  Write-Host "ffmpeg installe (actif apres reouverture des fenetres)."
} else { Write-Host "ffmpeg : OK" }

# 3. Modules Python
Write-Host "Modules Python (voix Edge, PDF, IA, MCP)..." -ForegroundColor Cyan
if ($py -eq "py") { py -3 -m pip install --upgrade --quiet edge-tts pypdf anthropic openai mcp keyring } else { python -m pip install --upgrade --quiet edge-tts pypdf anthropic openai mcp keyring }

# 4. Police des titres (Cinzel, licence OFL)
New-Item -ItemType Directory -Force -Path "$ici\polices" | Out-Null
if (-not (Test-Path "$ici\polices\Cinzel.ttf")) {
  Invoke-WebRequest -Uri "https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf" -OutFile "$ici\polices\Cinzel.ttf"
}
Write-Host "Police : OK"

# 5. Musiques (Kevin MacLeod - incompetech.com - licence CC BY 4.0, credit obligatoire)
New-Item -ItemType Directory -Force -Path "$ici\musique" | Out-Null
$pistes = @(
  "Clash Defiant",
  "Crusade - Heavy Industry",
  "Dark Walk",
  "Darkest Child",
  "Echoes of Time v2",
  "Ever Mindful",
  "Heroic Age",
  "Interloper",
  "Lightless Dawn",
  "Long Note Four",
  "Lord of the Land",
  "Ossuary 6 - Air",
  "Prelude and Action",
  "Rising Game"
)
foreach ($t in $pistes) {
  $nom = ($t -replace " ", "_") + ".mp3"
  $dst = Join-Path "$ici\musique" $nom
  if (-not (Test-Path $dst)) {
    Write-Host "  musique : $t"
    Invoke-WebRequest -Uri ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + [uri]::EscapeDataString($t) + ".mp3") -OutFile $dst
  }
}
Write-Host "Musiques : OK"

Write-Host ""
Write-Host "=== Installation terminee. Lance PILOTAGE.bat ===" -ForegroundColor Green
Read-Host "Entree pour fermer"
