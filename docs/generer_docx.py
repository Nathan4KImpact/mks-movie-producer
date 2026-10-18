#!/usr/bin/env python3
"""Version Word (.docx) des manuels, fabriquée à la demande à partir des fichiers Markdown de ce dossier.

Bibliothèque standard uniquement (rien à installer). Les .docx ne sont jamais commités : l'application les fabrique
au clic sur « Télécharger en Word » (menu Aide) dans le dossier `cache/manuels/` du logiciel, et les refait dès qu'un
manuel ou une capture change.

Usage : python docs/generer_docx.py [dossier de sortie]      (par défaut : cache/manuels/)
"""
import datetime, os, re, struct, sys, zipfile
from xml.sax.saxutils import escape

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(os.path.dirname(ICI), "cache", "manuels")
MANUELS = {"installation": "MANUEL_INSTALLATION", "utilisation": "MANUEL_UTILISATION"}

LARGEUR_CM = 16.0            # largeur utile d'une page A4 avec des marges de 2,5 cm
EMU_CM = 360000
OR, OR_FONCE, ENCRE, GRIS = "A07A2C", "7A5A1E", "24201A", "7D7466"


# ------------------------------------------------------------------ texte en ligne : **gras**, *italique*, `code`, [lien](url)
JETON = re.compile(r"(`[^`]+`|\*\*.+?\*\*|(?<![\w*])\*(?!\s).+?(?<!\s)\*(?![\w*])|\[[^\]]+\]\([^)]+\))")


def _run(texte, gras=False, ital=False, code=False, lien=False, taille=None, couleur=None):
    p = []
    if code:
        p.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>')
    if gras:
        p.append("<w:b/>")
    if ital:
        p.append("<w:i/>")
    if lien or couleur:
        p.append(f'<w:color w:val="{couleur or OR_FONCE}"/>')
    if code:
        p.append('<w:sz w:val="18"/><w:shd w:val="clear" w:color="auto" w:fill="F3EEE3"/>')
    elif taille:
        p.append(f'<w:sz w:val="{taille}"/>')
    if lien:
        p.append('<w:u w:val="single"/>')
    rpr = f"<w:rPr>{''.join(p)}</w:rPr>" if p else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(texte)}</w:t></w:r>'


class Doc:
    def __init__(self, dossier_images):
        self.corps, self.medias, self.liens, self.nums = [], [], [], []
        self.images = dossier_images

    # -------------------------------------------------------------- en ligne
    def en_ligne(self, texte, gras=False, ital=False, taille=None, couleur=None):
        out = []
        for morceau in JETON.split(texte):
            if not morceau:
                continue
            if morceau.startswith("`") and morceau.endswith("`") and len(morceau) > 1:
                out.append(_run(morceau[1:-1], gras, ital, code=True))
            elif morceau.startswith("**") and morceau.endswith("**") and len(morceau) > 4:
                out.append(self.en_ligne(morceau[2:-2], True, ital, taille, couleur))
            elif re.fullmatch(r"\*[^*].*\*", morceau):
                out.append(self.en_ligne(morceau[1:-1], gras, True, taille, couleur))
            elif re.fullmatch(r"\[[^\]]+\]\([^)]+\)", morceau):
                txt, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", morceau).groups()
                if url.startswith(("http://", "https://", "mailto:")):
                    self.liens.append(url)
                    rid = f"rLien{len(self.liens)}"
                    out.append(f'<w:hyperlink r:id="{rid}">{_run(txt, gras, ital, lien=True)}</w:hyperlink>')
                else:                                 # lien interne (autre manuel, ancre) : texte seul
                    out.append(_run(txt, gras, ital, taille=taille, couleur=couleur))
            else:
                out.append(_run(morceau, gras, ital, taille=taille, couleur=couleur))
        return "".join(out)

    # -------------------------------------------------------------- blocs
    def para(self, texte, style=None, num=None, niveau=0, saut_avant=False, centre=False, gras=False, taille=None, couleur=None):
        ppr = []
        if style:
            ppr.append(f'<w:pStyle w:val="{style}"/>')
        if saut_avant:
            ppr.append("<w:pageBreakBefore/>")
        if num:
            ppr.append(f'<w:numPr><w:ilvl w:val="{niveau}"/><w:numId w:val="{num}"/></w:numPr>')
        if centre:
            ppr.append('<w:jc w:val="center"/>')
        self.corps.append(f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{self.en_ligne(texte, gras, False, taille, couleur)}</w:p>")

    def code(self, lignes):
        for l in lignes or [""]:
            self.corps.append(f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>{_run(l)}</w:p>')
        self.corps.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')

    def tableau(self, lignes):
        rangs = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lignes]
        rangs = [r for r in rangs if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
        n = max(len(r) for r in rangs)
        larg = int(LARGEUR_CM * 567 / n)
        xml = ['<w:tbl><w:tblPr><w:tblStyle w:val="Tableau"/><w:tblW w:w="5000" w:type="pct"/>'
               '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
               "</w:tblPr><w:tblGrid>" + ('<w:gridCol w:w="%d"/>' % larg) * n + "</w:tblGrid>"]
        for i, r in enumerate(rangs):
            tete = i == 0
            xml.append("<w:tr>" + ('<w:trPr><w:tblHeader/></w:trPr>' if tete else ""))
            for c in r + [""] * (n - len(r)):
                fond = '<w:shd w:val="clear" w:color="auto" w:fill="F3EAD6"/>' if tete else ""
                xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{larg}" w:type="dxa"/>{fond}</w:tcPr>'
                           f'<w:p><w:pPr><w:pStyle w:val="Cellule"/></w:pPr>{self.en_ligne(c, gras=tete)}</w:p></w:tc>')
            xml.append("</w:tr>")
        xml.append("</w:tbl>")
        self.corps.append("".join(xml))
        self.corps.append('<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>')

    def image(self, rel, legende):
        f = os.path.join(self.images, *rel.replace("images/", "", 1).split("/"))
        if not os.path.isfile(f):
            return self.para(f"[image manquante : {rel}]", couleur=GRIS)
        dim = taille_image(f)
        if not dim:
            return self.para(f"[image illisible : {rel}]", couleur=GRIS)
        w, h = dim
        cx = int(LARGEUR_CM * EMU_CM)
        cy = int(cx * h / w)
        if cy > 20 * EMU_CM:                       # une capture très haute tient sur la page
            cy = int(20 * EMU_CM); cx = int(cy * w / h)
        self.medias.append(f)
        n = len(self.medias)
        rid = f"rImg{n}"
        self.corps.append(
            '<w:p><w:pPr><w:pStyle w:val="Image"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{n}" name="Image {n}" descr="{escape(legende, {chr(34): "&quot;"})}"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{n}" name="{escape(os.path.basename(f))}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:ln w="6350"><a:solidFill><a:srgbClr val="D8CFBF"/></a:solidFill></a:ln></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
        if legende:
            self.para(legende, style="Legende")

    def nouvelle_liste(self, ordonnee):
        self.nums.append(2 if ordonnee else 1)      # 1 = puces, 2 = numéros (une instance par liste : la numérotation repart à 1)
        return len(self.nums)


def taille_image(f):
    """(largeur, hauteur) d'un JPEG ou d'un PNG, sans dépendance."""
    with open(f, "rb") as h:
        d = h.read(64 * 1024)
    if d[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", d[16:24])
    if d[:2] == b"\xff\xd8":
        i = 2
        with open(f, "rb") as h:
            d = h.read()
        while i < len(d) - 9:
            if d[i] != 0xFF:
                i += 1; continue
            m = d[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                hh, ww = struct.unpack(">HH", d[i + 5:i + 9])
                return ww, hh
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2; continue
            i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
    return None


# ------------------------------------------------------------------ Markdown → blocs
LISTE = re.compile(r"^( *)([-*]|\d+\.) +(.*)$")


def convertir(texte, doc, titre_couv):
    lignes = texte.split("\n")
    i, premier_h2 = 0, True
    # couverture : titre (# …) et ligne de version
    while i < len(lignes) and not lignes[i].strip():
        i += 1
    titre = lignes[i][2:].strip() if i < len(lignes) and lignes[i].startswith("# ") else titre_couv
    if lignes[i].startswith("# "):
        i += 1
    while i < len(lignes) and not lignes[i].strip():
        i += 1
    version = ""
    if i < len(lignes) and re.match(r"^Version\b", lignes[i]):
        version = lignes[i].strip(); i += 1
    app, _, sous = titre.partition(" — ")
    for _ in range(8):
        doc.para("")
    doc.para(app, style="Couverture", centre=True)
    if sous:
        doc.para(sous, style="SousTitre", centre=True)
    doc.para(version + (" · " if version else "") + "généré le " + datetime.date.today().strftime("%d/%m/%Y"),
             centre=True, couleur=GRIS)
    liste_ids = {}                                   # indentation → identifiant de liste en cours
    while i < len(lignes):
        l = lignes[i]
        s = l.strip()
        if not s:
            i += 1
            if not (i < len(lignes) and LISTE.match(lignes[i])):
                liste_ids = {}
            continue
        if s.startswith("```"):
            bloc = []
            i += 1
            while i < len(lignes) and not lignes[i].strip().startswith("```"):
                bloc.append(lignes[i]); i += 1
            i += 1
            doc.code(bloc); liste_ids = {}
            continue
        m = re.match(r"^(#{1,4}) +(.*)$", s)
        if m:
            n = len(m.group(1))
            doc.para(m.group(2), style=f"Titre{min(n, 4)}" if n > 1 else "Titre2", saut_avant=(n == 2 and premier_h2))
            premier_h2 = premier_h2 and n != 2
            liste_ids = {}; i += 1
            continue
        if s.startswith("|"):
            bloc = []
            while i < len(lignes) and lignes[i].strip().startswith("|"):
                bloc.append(lignes[i]); i += 1
            doc.tableau(bloc); liste_ids = {}
            continue
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", s)
        if m:
            doc.image(m.group(2), m.group(1)); i += 1; liste_ids = {}
            continue
        if s.startswith(">"):
            bloc = []
            while i < len(lignes) and lignes[i].strip().startswith(">"):
                bloc.append(lignes[i].strip()[1:].strip()); i += 1
            for p in " ".join(bloc).split("  "):
                if p.strip():
                    doc.para(p.strip(), style="Citation")
            liste_ids = {}
            continue
        if re.fullmatch(r"-{3,}|\*{3,}", s):
            i += 1; continue
        m = LISTE.match(l)
        if m:
            ind, puce, txt = len(m.group(1)), m.group(2), m.group(3)
            niveau = min(ind // 2, 2) if ind < 4 else min(ind // 4, 2)
            i += 1
            while i < len(lignes) and lignes[i].strip() and not LISTE.match(lignes[i]) \
                    and not lignes[i].strip().startswith(("|", "```", "#", ">", "![")):
                txt += " " + lignes[i].strip(); i += 1     # suite de l'élément sur la ligne suivante
            ordonnee = puce[0].isdigit()
            cle = (niveau, ordonnee)
            for k in [k for k in liste_ids if k[0] > niveau]:
                del liste_ids[k]
            if cle not in liste_ids:
                liste_ids[cle] = doc.nouvelle_liste(ordonnee)
            doc.para(txt, num=liste_ids[cle], niveau=niveau)
            continue
        bloc = [s]
        i += 1
        while i < len(lignes) and lignes[i].strip() and not re.match(r"^(#{1,4} |\||```|>|!\[)", lignes[i].strip()) \
                and not LISTE.match(lignes[i]):
            bloc.append(lignes[i].strip()); i += 1
        doc.para(" ".join(bloc)); liste_ids = {}


# ------------------------------------------------------------------ parties fixes du paquet Word
W_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"')


def _style(sid, nom, ppr="", rpr="", base="Normal", suivant="Normal", niveau=None):
    out = f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{nom}"/><w:basedOn w:val="{base}"/>' \
          f'<w:next w:val="{suivant}"/><w:qFormat/>'
    if niveau is not None:
        ppr += f'<w:outlineLvl w:val="{niveau}"/>'
    return out + f"<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>"


STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W_NS}>
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>
<w:sz w:val="21"/><w:szCs w:val="21"/><w:color w:val="{ENCRE}"/><w:lang w:val="fr-FR"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
{_style("Couverture", "Couverture", '<w:spacing w:after="120"/>', f'<w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/><w:b/><w:color w:val="{OR_FONCE}"/><w:sz w:val="60"/>')}
{_style("SousTitre", "Sous-titre de couverture", '<w:spacing w:after="480"/>', '<w:sz w:val="34"/>')}
{_style("Titre2", "heading 1", '<w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="2" w:color="E2CFA4"/></w:pBdr><w:spacing w:before="420" w:after="140"/>',
        f'<w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/><w:b/><w:color w:val="{OR_FONCE}"/><w:sz w:val="32"/>', niveau=0)}
{_style("Titre3", "heading 2", '<w:keepNext/><w:spacing w:before="280" w:after="100"/>',
        f'<w:rFonts w:ascii="Cambria" w:hAnsi="Cambria"/><w:b/><w:color w:val="{OR}"/><w:sz w:val="25"/>', niveau=1)}
{_style("Titre4", "heading 3", '<w:keepNext/><w:spacing w:before="200" w:after="60"/>', '<w:b/><w:sz w:val="22"/>', niveau=2)}
{_style("Code", "Code", '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:shd w:val="clear" w:color="auto" w:fill="F7F3EA"/><w:ind w:left="170"/>',
        '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="18"/>')}
{_style("Citation", "Encadré", '<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="C9A24F"/></w:pBdr><w:shd w:val="clear" w:color="auto" w:fill="FBF6EA"/><w:ind w:left="200" w:right="200"/><w:spacing w:before="80" w:after="160"/>')}
{_style("Cellule", "Cellule", '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>', '<w:sz w:val="19"/>')}
{_style("Image", "Image", '<w:keepNext/><w:jc w:val="center"/><w:spacing w:before="80" w:after="40"/>')}
{_style("Legende", "Légende", '<w:jc w:val="center"/><w:spacing w:after="220"/>', f'<w:i/><w:color w:val="{GRIS}"/><w:sz w:val="18"/>')}
<w:style w:type="table" w:styleId="Tableau"><w:name w:val="Tableau du manuel"/><w:tblPr><w:tblBorders>
<w:top w:val="single" w:sz="4" w:color="E3D9C5"/><w:left w:val="single" w:sz="4" w:color="E3D9C5"/><w:bottom w:val="single" w:sz="4" w:color="E3D9C5"/>
<w:right w:val="single" w:sz="4" w:color="E3D9C5"/><w:insideH w:val="single" w:sz="4" w:color="E3D9C5"/><w:insideV w:val="single" w:sz="4" w:color="E3D9C5"/>
</w:tblBorders><w:tblCellMar><w:top w:w="50" w:type="dxa"/><w:left w:w="90" w:type="dxa"/><w:bottom w:w="50" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>"""


def numerotation(nums):
    def niveaux(ordonnee):
        out = []
        for n in range(3):
            if ordonnee:
                fmt, txt = "decimal", f"%{n + 1}."
            else:
                fmt, txt = "bullet", ["•", "–", "·"][n]
            out.append(f'<w:lvl w:ilvl="{n}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/><w:lvlText w:val="{txt}"/>'
                       f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{360 + n * 360}" w:hanging="300"/></w:pPr></w:lvl>')
        return "".join(out)
    abst = (f'<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/>{niveaux(False)}</w:abstractNum>'
            f'<w:abstractNum w:abstractNumId="2"><w:multiLevelType w:val="hybridMultilevel"/>{niveaux(True)}</w:abstractNum>')
    inst = "".join(f'<w:num w:numId="{i + 1}"><w:abstractNumId w:val="{a}"/>'
                   + ("".join(f'<w:lvlOverride w:ilvl="{n}"><w:startOverride w:val="1"/></w:lvlOverride>' for n in range(3)) if a == 2 else "")
                   + "</w:num>" for i, a in enumerate(nums))
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering {W_NS}>{abst}{inst}</w:numbering>'


def paquet(doc, sortie, titre):
    pied = ('<w:ftr ' + W_NS + '><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            f'{_run(titre + " · page ", couleur=GRIS, taille=16)}'
            f'<w:r><w:rPr><w:color w:val="{GRIS}"/><w:sz w:val="16"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:rPr><w:color w:val="{GRIS}"/><w:sz w:val="16"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
            f'<w:r><w:rPr><w:color w:val="{GRIS}"/><w:sz w:val="16"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')
    sect = ('<w:sectPr><w:footerReference w:type="default" r:id="rPied"/><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="567" w:gutter="0"/>'
            '<w:titlePg/></w:sectPr>')
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>'
                + "".join(doc.corps) + sect + "</w:body></w:document>")
    rels = ['<Relationship Id="rStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rNum" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>',
            '<Relationship Id="rPied" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    for i, f in enumerate(doc.medias, 1):
        ext = os.path.splitext(f)[1].lower().lstrip(".").replace("jpeg", "jpg")
        rels.append(f'<Relationship Id="rImg{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{i}.{ext}"/>')
    for i, u in enumerate(doc.liens, 1):
        rels.append(f'<Relationship Id="rLien{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                    f'Target="{escape(u, {chr(34): "&quot;"})}" TargetMode="External"/>')
    maintenant = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp = sortie + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Default Extension="jpg" ContentType="image/jpeg"/><Default Extension="png" ContentType="image/png"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                   '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
                   '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                   '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '<Relationship Id="r2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                   '</Relationships>')
        z.writestr("docProps/core.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                   'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                   f'<dc:title>{escape(titre)}</dc:title><dc:creator>MKS Movie Producer</dc:creator><dc:language>fr-FR</dc:language>'
                   f'<dcterms:created xsi:type="dcterms:W3CDTF">{maintenant}</dcterms:created></cp:coreProperties>')
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/numbering.xml", numerotation(doc.nums or [1]))
        z.writestr("word/footer1.xml", pied)
        for i, f in enumerate(doc.medias, 1):
            ext = os.path.splitext(f)[1].lower().lstrip(".").replace("jpeg", "jpg")
            z.write(f, f"word/media/image{i}.{ext}", compress_type=zipfile.ZIP_STORED)
    os.replace(tmp, sortie)


# ------------------------------------------------------------------ point d'entrée
def a_jour(md, sortie):
    """Le .docx existe et il est plus récent que le manuel et que toutes ses captures."""
    if not os.path.isfile(sortie):
        return False
    t = os.path.getmtime(sortie)
    if os.path.getmtime(md) > t or os.path.getmtime(__file__) > t:
        return False
    imgs = os.path.join(ICI, "images")
    return not any(os.path.getmtime(os.path.join(imgs, f)) > t for f in os.listdir(imgs)) if os.path.isdir(imgs) else True


def generer(quel, dossier=SORTIE):
    """Chemin du .docx du manuel `quel` (installation | utilisation), fabriqué s'il manque ou s'il est périmé."""
    nom = MANUELS[quel]
    md = os.path.join(ICI, nom + ".md")
    os.makedirs(dossier, exist_ok=True)
    sortie = os.path.join(dossier, nom + ".docx")
    if a_jour(md, sortie):
        return sortie
    doc = Doc(os.path.join(ICI, "images"))
    titre = "Manuel d'installation" if quel == "installation" else "Manuel d'utilisation"
    convertir(open(md, encoding="utf-8").read(), doc, "MKS Movie Producer — " + titre)
    paquet(doc, sortie, "MKS Movie Producer — " + titre)
    return sortie


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else SORTIE
    for q in MANUELS:
        f = generer(q, d)
        print(f"{f}  ({os.path.getsize(f) / 1e6:.2f} Mo)")
