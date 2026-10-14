#!/usr/bin/env python3
"""Logos SVG générés : un emblème générique à partir du nom du projet (initiales, couleur),
et l'emblème dessiné de « L'Ultime Assaut » (épée, montagne, rayons)."""
import hashlib, html, re, unicodedata


def initiales(nom):
    mots = [m for m in re.split(r"[\s'’\-]+", nom) if m and m.lower() not in ("le", "la", "les", "l", "de", "du", "des", "d", "un", "une", "the", "of", "a")]
    s = "".join(m[0] for m in mots[:3]).upper() or nom[:2].upper()
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode() or "S"


def logo_generique(nom, couleur="#d8b46a", sous_titre=""):
    h = int(hashlib.md5(nom.encode()).hexdigest()[:6], 16)
    rot = h % 45
    ini = html.escape(initiales(nom))
    taille = 150 if len(ini) == 1 else (118 if len(ini) == 2 else 92)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" aria-label="{html.escape(nom)}">
  <defs>
    <radialGradient id="f" cx="50%" cy="40%" r="65%"><stop offset="0" stop-color="#2a2016"/><stop offset="1" stop-color="#0d0b10"/></radialGradient>
    <linearGradient id="o" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6e2a8"/><stop offset=".55" stop-color="{couleur}"/><stop offset="1" stop-color="#8a6a2c"/></linearGradient>
  </defs>
  <circle cx="200" cy="200" r="192" fill="url(#f)" stroke="url(#o)" stroke-width="6"/>
  <circle cx="200" cy="200" r="170" fill="none" stroke="url(#o)" stroke-width="1.5" stroke-dasharray="2 7" transform="rotate({rot} 200 200)"/>
  <g stroke="url(#o)" stroke-width="2" opacity=".55">{"".join(f'<line x1="200" y1="62" x2="200" y2="40" transform="rotate({i * 30} 200 200)"/>' for i in range(12))}</g>
  <text x="200" y="{200 + taille * 0.35:.0f}" text-anchor="middle" font-family="Cinzel, Trajan Pro, Georgia, serif" font-weight="700"
        font-size="{taille}" fill="url(#o)" letter-spacing="4">{ini}</text>
</svg>'''


def logo_ultime_assaut():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" aria-label="L'Ultime Assaut">
  <defs>
    <radialGradient id="ciel" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="#5a3a14"/><stop offset=".45" stop-color="#22160d"/><stop offset="1" stop-color="#0b090d"/></radialGradient>
    <linearGradient id="or" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff1c4"/><stop offset=".5" stop-color="#e2bb63"/><stop offset="1" stop-color="#8f6a26"/></linearGradient>
    <linearGradient id="lame" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#cfd6e0"/><stop offset=".5" stop-color="#ffffff"/><stop offset="1" stop-color="#9aa6b6"/></linearGradient>
    <linearGradient id="mont" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b2c1c"/><stop offset="1" stop-color="#120d0a"/></linearGradient>
    <clipPath id="disque"><circle cx="200" cy="200" r="186"/></clipPath>
  </defs>
  <circle cx="200" cy="200" r="194" fill="#0b090d" stroke="url(#or)" stroke-width="6"/>
  <g clip-path="url(#disque)">
    <rect width="400" height="400" fill="url(#ciel)"/>
    <g stroke="#f3d68a" stroke-width="3" opacity=".35">
      <line x1="200" y1="150" x2="40" y2="20"/><line x1="200" y1="150" x2="110" y2="0"/><line x1="200" y1="150" x2="200" y2="0"/>
      <line x1="200" y1="150" x2="290" y2="0"/><line x1="200" y1="150" x2="360" y2="20"/><line x1="200" y1="150" x2="400" y2="110"/><line x1="200" y1="150" x2="0" y2="110"/>
    </g>
    <circle cx="200" cy="150" r="46" fill="#f6dc95" opacity=".25"/>
    <path d="M0 330 L70 270 L110 292 L170 205 L200 228 L236 176 L300 268 L340 246 L400 300 L400 400 L0 400 Z" fill="url(#mont)" stroke="#e2bb63" stroke-width="2" stroke-opacity=".6"/>
    <path d="M150 238 L250 238 M132 262 L268 262 M114 286 L286 286" stroke="#e2bb63" stroke-width="2" opacity=".45"/>
  </g>
  <g>
    <polygon points="200,58 210,82 210,262 200,280 190,262 190,82" fill="url(#lame)" stroke="#6b7480" stroke-width="1"/>
    <line x1="200" y1="84" x2="200" y2="258" stroke="#8e98a6" stroke-width="1.4"/>
    <rect x="156" y="262" width="88" height="12" rx="6" fill="url(#or)"/>
    <rect x="194" y="274" width="12" height="44" rx="4" fill="#5b3b1d" stroke="url(#or)" stroke-width="1.5"/>
    <circle cx="200" cy="326" r="10" fill="url(#or)"/>
    <circle cx="200" cy="268" r="4" fill="#b8312a"/>
  </g>
  <path id="arc" d="M70 200 A130 130 0 0 1 330 200" fill="none"/>
  <text font-family="Cinzel, Trajan Pro, Georgia, serif" font-weight="700" font-size="30" fill="url(#or)" letter-spacing="5">
    <textPath href="#arc" startOffset="50%" text-anchor="middle">L'ULTIME ASSAUT</textPath>
  </text>
</svg>'''


def logo_pour(nom, couleur="#d8b46a"):
    return logo_ultime_assaut() if "ultime assaut" in nom.lower() else logo_generique(nom, couleur)
