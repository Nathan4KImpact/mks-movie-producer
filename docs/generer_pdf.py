#!/usr/bin/env python3
"""Régénère les versions PDF des manuels à partir des fichiers Markdown de ce dossier.

Prérequis (poste de développement uniquement) : pip install markdown playwright ; playwright install chromium
Usage : python docs/generer_pdf.py
"""
import datetime, os, re, sys
import markdown
from playwright.sync_api import sync_playwright

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
from logo import logo_generique  # noqa: E402

POLICE = os.environ.get("CINZEL_TTF", os.path.join(os.path.dirname(ICI), "polices", "Cinzel.ttf"))
MANUELS = [("MANUEL_INSTALLATION.md", "Manuel d'installation"), ("MANUEL_UTILISATION.md", "Manuel d'utilisation")]

CSS = """
@font-face{font-family:'Cinzel';src:url('file://%(police)s') format('truetype');font-weight:400 900}
@page{size:A4;margin:20mm 18mm 20mm 18mm}
*{box-sizing:border-box}
body{font:10.2pt/1.55 'Inter',system-ui,sans-serif;color:#24201a;margin:0}
.couv{height:257mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;
      break-after:page;background:radial-gradient(120mm 90mm at 50% 35%,#f6ecd4 0%,#fff 70%)}
.couv svg{width:62mm;height:62mm}
.couv .app{font:700 30pt 'Cinzel',serif;letter-spacing:.06em;color:#7a5a1e;margin:10mm 0 2mm}
.couv .titre{font:600 17pt 'Inter',sans-serif;color:#24201a;margin:0 0 14mm}
.couv .meta{color:#7d7466;font-size:9.5pt}
.sommaire{break-after:page}
.sommaire h2{border:0}
.sommaire ol{padding-left:0;list-style:none;columns:1}
.sommaire li{padding:2.2mm 0;border-bottom:1px dotted #d9cfbd;font-size:10.5pt}
.sommaire a{color:#24201a;text-decoration:none}
.sommaire .n{display:inline-block;width:9mm;color:#a07a2c;font-weight:600}
h1{display:none}
h1+p{display:none}
h2{font:700 15pt 'Cinzel',serif;color:#7a5a1e;letter-spacing:.03em;border-bottom:1.5px solid #e2cfa4;padding-bottom:1.5mm;
   margin:9mm 0 3mm;break-after:avoid}
h3{font:700 11.5pt 'Cinzel',serif;color:#a07a2c;margin:6mm 0 2mm;break-after:avoid}
h4{font-size:10.5pt;margin:4mm 0 1mm;break-after:avoid}
p{margin:0 0 2.6mm}
ul,ol{margin:0 0 3mm;padding-left:6mm}
li{margin:0 0 1mm}
table{width:100%;border-collapse:collapse;margin:2mm 0 4mm;font-size:9.2pt;break-inside:auto}
tr{break-inside:avoid}
th{background:#f3ead6;color:#5d4415;text-align:left;font-weight:600}
th,td{border:1px solid #e3d9c5;padding:1.6mm 2.2mm;vertical-align:top}
code{font:8.8pt/1.4 'DejaVu Sans Mono',Consolas,monospace;background:#f5f1e8;border:1px solid #e7dfcf;border-radius:3px;padding:0 1mm}
pre{background:#f7f3ea;border:1px solid #e7dfcf;border-left:3px solid #c9a24f;border-radius:4px;padding:3mm;white-space:pre-wrap;break-inside:avoid}
pre code{background:none;border:0;padding:0}
blockquote{margin:3mm 0 4mm;padding:2.5mm 4mm;background:#fbf6ea;border-left:3px solid #c9a24f;border-radius:0 4px 4px 0;break-inside:avoid}
blockquote p{margin:0}
img{display:block;width:100%;border:1px solid #d8cfbf;border-radius:3px;margin:2mm 0 5mm;break-inside:avoid}
a{color:#7a5a1e}
"""


def ancre(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def construire(md_nom, titre, page):
    texte = open(os.path.join(ICI, md_nom), encoding="utf-8").read()
    corps = markdown.markdown(texte, extensions=["tables", "fenced_code", "toc"],
                              extension_configs={"toc": {"slugify": lambda v, s: ancre(v)}})
    sections = re.findall(r"^## (.*)$", texte, re.M)
    sommaire = "".join(f'<li><a href="#{ancre(s)}"><span class="n">{s.split(".")[0]}.</span>{s.split(". ", 1)[-1]}</a></li>'
                       for s in sections)
    version = re.search(r"^Version (.*)$", texte, re.M).group(1)
    # texte en couleur unie : le dégradé sur du texte s'imprime mal en PDF (rectangle plein)
    logo = re.sub(r'(<text[^>]*?)fill="url\(#o\)"', r'\1fill="#c9a24f"',
                  logo_generique("MKS Movie Producer", "#c9a24f").replace(">MMP<", ">MKS<"))
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<style>{CSS.replace('%(police)s', POLICE)}</style></head><body>
<section class="couv">{logo}<div class="app">MKS Movie Producer</div><div class="titre">{titre}</div>
<div class="meta">Version {version}</div></section>
<section class="sommaire"><h2>Sommaire</h2><ol>{sommaire}</ol></section>
{corps}</body></html>"""
    sortie = os.path.join(ICI, md_nom.replace(".md", ".pdf"))
    pied = (f'<div style="width:100%;font:7.5pt Inter,sans-serif;color:#9a8f7d;padding:0 18mm;display:flex">'
            f'<span>MKS Movie Producer — {titre}</span><span style="flex:1"></span>'
            f'<span class="pageNumber"></span>&nbsp;/&nbsp;<span class="totalPages"></span></div>')
    tmp = os.path.join(ICI, "_manuel_tmp.html")
    open(tmp, "w", encoding="utf-8").write(html)
    try:
        page.goto("file://" + tmp, wait_until="load")
        page.wait_for_timeout(400)
        page.pdf(path=sortie, format="A4", print_background=True, display_header_footer=True,
                 header_template="<div></div>", footer_template=pied,
                 margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"})
    finally:
        os.remove(tmp)
    print("PDF :", sortie)


if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for nom, titre in MANUELS:
            construire(nom, titre, pg)
        b.close()
