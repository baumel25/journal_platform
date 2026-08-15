"""
Standard two-column journal PDF generation (ReportLab).

Produces a published article in the layout of typical academic journals:
journal masthead / running header, centered title, author with affiliation
marker, affiliation line, corresponding-author email, abstract, keywords,
numbered uppercase section headings, two-column justified body, and a footer
with the article's page range and journal URL.
"""

import os
from html import escape
from io import BytesIO

from django.conf import settings
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pypdf import PdfReader

from .utils import parse_article_blocks

# ---------------------------------------------------------------------------
# Journal identity — edit these to match the real journal
# ---------------------------------------------------------------------------
JOURNAL_NAME = "Journal of Computer Science and Applications"
JOURNAL_SUBTITLE = "An Academic Journal Management System"
JOURNAL_ISSN = "ISSN 1673-064X"
JOURNAL_VOLUME = "VOLUME 1"
JOURNAL_ISSUE = "ISSUE 1"
JOURNAL_YEAR = "2026"
JOURNAL_URL = "www.journal-of-csa.org"

# First page number of this article (real journals paginate a whole issue).
START_PAGE = 1

# Journal logo (contains the journal name) shown at the top of the first page.
LOGO_PATH = os.path.join(settings.BASE_DIR, "static", "defaults", "logo.png")
LOGO_WIDTH = 300  # points (scaled to fit the title block)

# ---------------------------------------------------------------------------
# Editorial board — edit these names to match the real board
# ---------------------------------------------------------------------------
EDITORIAL_BOARD = {
    "Editor-in-Chief": ["Prof. [Name]"],
    "Associate Editors": ["[Name 1]", "[Name 2]", "[Name 3]"],
    "Editorial Board Members": [
        "[Name 1]", "[Name 2]", "[Name 3]", "[Name 4]", "[Name 5]", "[Name 6]",
    ],
    "Advisory Board": ["[Name 1]", "[Name 2]", "[Name 3]"],
}

# ---------------------------------------------------------------------------
# Page geometry (A4)
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
ML, MR, MT, MB = 1.7 * cm, 1.7 * cm, 2.5 * cm, 2.2 * cm
GUTTER = 0.6 * cm
CONTENT_W = PAGE_W - ML - MR
COL_W = (CONTENT_W - GUTTER) / 2.0
COL_H = PAGE_H - MT - MB

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
PRIMARY = colors.HexColor("#1F3864")   # dark blue (title / headings)
BLACK = colors.HexColor("#111111")
GRAY = colors.HexColor("#444444")
RULE = colors.HexColor("#999999")


def _esc(text):
    """HTML-escape text for use inside a ReportLab Paragraph."""
    return escape(text or "", quote=True).replace("&#x27;", "&#39;")


def _build_styles():
    return {
        "title": ParagraphStyle(
            "title", fontName="Times-Bold", fontSize=13.5, leading=17,
            alignment=TA_CENTER, textColor=PRIMARY, spaceAfter=7,
        ),
        "authors": ParagraphStyle(
            "authors", fontName="Times-Bold", fontSize=9.5, leading=12.5,
            alignment=TA_CENTER, textColor=BLACK, spaceAfter=3,
        ),
        "affiliations": ParagraphStyle(
            "affiliations", fontName="Times-Italic", fontSize=7.5, leading=9.5,
            alignment=TA_CENTER, textColor=GRAY, spaceAfter=3,
        ),
        "correspondence": ParagraphStyle(
            "correspondence", fontName="Times-Roman", fontSize=7.5, leading=9.5,
            alignment=TA_CENTER, textColor=GRAY, spaceAfter=6,
        ),
        "abstract_label": ParagraphStyle(
            "abstract_label", fontName="Times-Bold", fontSize=8.5, leading=10.5,
            alignment=TA_LEFT, textColor=BLACK, spaceBefore=5, spaceAfter=2,
        ),
        "abstract": ParagraphStyle(
            "abstract", fontName="Times-Italic", fontSize=8.5, leading=11,
            alignment=TA_JUSTIFY, textColor=BLACK, spaceAfter=3,
        ),
        "keywords": ParagraphStyle(
            "keywords", fontName="Times-Roman", fontSize=8, leading=10.5,
            alignment=TA_JUSTIFY, textColor=BLACK, spaceBefore=3, spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "heading", fontName="Times-Bold", fontSize=8.5, leading=11,
            alignment=TA_LEFT, textColor=PRIMARY, spaceBefore=7, spaceAfter=3,
            keepWithNext=1,
        ),
        "body": ParagraphStyle(
            "body", fontName="Times-Roman", fontSize=8.5, leading=11,
            alignment=TA_JUSTIFY, textColor=BLACK, spaceAfter=4,
        ),
        "reference": ParagraphStyle(
            "reference", fontName="Times-Roman", fontSize=7.5, leading=10,
            alignment=TA_LEFT, textColor=BLACK, spaceAfter=3,
            leftIndent=12, firstLineIndent=-12,
        ),
        "published": ParagraphStyle(
            "published", fontName="Times-Bold", fontSize=8, leading=10,
            alignment=TA_CENTER, textColor=PRIMARY, spaceBefore=2, spaceAfter=5,
        ),
    }


def _measure(flowables, width):
    """Return the total vertical height a list of flowables needs."""
    total = 0.0
    for flowable in flowables:
        _, height = flowable.wrap(width, 10 ** 9)
        total += height
    return total


def _draw_header(canv, doc):
    """Running header drawn at the top of every page."""
    canv.saveState()
    y = PAGE_H - 0.95 * cm
    canv.setFont("Times-Roman", 7.5)
    canv.setFillColor(GRAY)
    canv.drawString(ML, y, JOURNAL_NAME)
    canv.drawCentredString(PAGE_W / 2.0, y, f"{JOURNAL_VOLUME} {JOURNAL_ISSUE} {JOURNAL_YEAR}")
    canv.drawRightString(PAGE_W - MR, y, JOURNAL_ISSN)
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.7)
    canv.line(ML, y - 0.3 * cm, PAGE_W - MR, y - 0.3 * cm)
    canv.restoreState()


class _NumberedCanvas(canvas.Canvas):
    """Standard trick: lets the footer show the total page count."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        """Footer with article page range (e.g. 1-6) and journal URL."""
        first_page = START_PAGE
        last_page = START_PAGE + total - 1
        y = 1.0 * cm
        self.setFont("Times-Roman", 7)
        self.setFillColor(GRAY)
        self.drawString(ML, y, JOURNAL_URL)
        self.drawCentredString(PAGE_W / 2.0, y, f"{first_page}\u2013{last_page}")
        self.drawRightString(PAGE_W - MR, y, f"{JOURNAL_VOLUME} {JOURNAL_ISSUE} {JOURNAL_YEAR}")
        self.setStrokeColor(RULE)
        self.setLineWidth(0.7)
        self.line(ML, y + 0.35 * cm, PAGE_W - MR, y + 0.35 * cm)


def _build_title_flowables(article, styles):
    """Logo, title, authors, affiliations, email, abstract and keywords block."""
    author = article.author
    name = author.get_full_name() or author.username
    flowables = []

    # Journal logo (already contains the journal name), centered above the title
    if os.path.exists(LOGO_PATH):
        with PILImage.open(LOGO_PATH) as im:
            img_w, img_h = im.size
        logo_height = LOGO_WIDTH * img_h / float(img_w)
        logo = RLImage(LOGO_PATH, width=LOGO_WIDTH, height=logo_height)
        logo.hAlign = "CENTER"
        flowables.append(logo)

    flowables.append(Paragraph(_esc(article.title), styles["title"]))

    if author.affiliation:
        flowables.append(Paragraph(f"{_esc(name)}<super>1</super>", styles["authors"]))
        flowables.append(Paragraph(f"<super>1</super>{_esc(author.affiliation)}", styles["affiliations"]))
    else:
        flowables.append(Paragraph(_esc(name), styles["authors"]))

    if author.email:
        flowables.append(
            Paragraph(f"<i>Corresponding author: {_esc(author.email)}</i>", styles["correspondence"])
        )

    # Publication date (month and year) as required by the journal
    if article.published_date:
        flowables.append(
            Paragraph(f"Published: {article.published_date.strftime('%B %Y')}", styles["published"])
        )

    flowables.append(Paragraph("ABSTRACT", styles["abstract_label"]))
    flowables.append(Paragraph(_esc(article.abstract), styles["abstract"]))

    if article.keywords:
        flowables.append(
            Paragraph(f"<b>Keywords:</b> {_esc(article.keywords)}", styles["keywords"])
        )

    return flowables


def _build_body_flowables(article, styles):
    """Numbered section headings + body paragraphs (already parsed)."""
    flowables = []
    for block in parse_article_blocks(article.content):
        if block["type"] == "heading":
            flowables.append(
                Paragraph(f"{block['number']}. {block['text'].upper()}", styles["heading"])
            )
        else:
            flowables.append(Paragraph(block["text"], styles["body"]))
    return flowables


def generate_journal_pdf(article):
    """
    Generate the two-column journal PDF for a published article and return it
    as bytes.
    """
    styles = _build_styles()

    # --- Title block height is measured so long abstracts never overflow ---
    title_flowables = _build_title_flowables(article, styles)
    title_height = min(
        _measure(title_flowables, CONTENT_W) + 0.6 * cm,
        COL_H - 2.5 * cm,
    )
    body_top = PAGE_H - MT
    title_bottom = body_top - title_height
    body_height = title_bottom - MB

    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title=article.title,
        author=article.author.get_full_name() or article.author.username,
    )

    first_page = PageTemplate(
        id="first",
        frames=[
            Frame(ML, title_bottom, CONTENT_W, title_height,
                  id="title_frame", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0),
            Frame(ML, MB, COL_W, body_height,
                  id="col1", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0),
            Frame(ML + COL_W + GUTTER, MB, COL_W, body_height,
                  id="col2", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0),
        ],
        onPage=_draw_header,
    )
    body_page = PageTemplate(
        id="body",
        frames=[
            Frame(ML, MB, COL_W, COL_H,
                  id="col1", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0),
            Frame(ML + COL_W + GUTTER, MB, COL_W, COL_H,
                  id="col2", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0),
        ],
        onPage=_draw_header,
    )
    doc.addPageTemplates([first_page, body_page])

    story = list(title_flowables)
    story.append(NextPageTemplate("body"))
    story.extend(_build_body_flowables(article, styles))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


def generate_cover_pdf():
    """Front cover of the journal issue.

    Masthead ("INSTRUCTOR"), English + French journal name, volume/issue and
    date, the journal logo, and the University of Bamenda / Higher Teacher
    Training College-Bambili branding.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    GOLD = colors.HexColor("#c9a227")

    # -- Background: soft off-white --
    c.setFillColor(colors.HexColor("#f5f5f2"))
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # -- Decorative double border --
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(2.4)
    c.rect(0.9 * cm, 0.9 * cm, W - 1.8 * cm, H - 1.8 * cm)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.7)
    c.rect(1.15 * cm, 1.15 * cm, W - 2.3 * cm, H - 2.3 * cm)

    # -- Masthead --
    c.setFillColor(GOLD)
    c.setFont("Times-Bold", 46)
    c.drawCentredString(W / 2.0, H - 4.7 * cm, "INSTRUCTOR")
    c.setFillColor(PRIMARY)
    c.setFont("Times-Bold", 15.5)
    c.drawCentredString(W / 2.0, H - 6.0 * cm, "Journal of Computer Science and Applications")
    c.setFillColor(GRAY)
    c.setFont("Times-Italic", 11.5)
    c.drawCentredString(W / 2.0, H - 6.7 * cm, "Revue d'Informatique et Applications")

    # -- Volume / issue / date --
    c.setFillColor(PRIMARY)
    c.setFont("Times-Bold", 13.5)
    c.drawCentredString(W / 2.0, H - 7.7 * cm, "Vol. 1, Number 2")
    c.setFillColor(GRAY)
    c.setFont("Times-Roman", 11)
    c.drawCentredString(W / 2.0, H - 8.4 * cm, "February 2026")

    # -- Journal logo (contains the journal name), centered --
    logo_w = 12 * cm
    if os.path.exists(LOGO_PATH):
        with PILImage.open(LOGO_PATH) as im:
            iw, ih = im.size
        logo_h = logo_w * ih / float(iw)
        c.drawImage(
            LOGO_PATH, (W - logo_w) / 2.0, H - 10.5 * cm - logo_h,
            width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto',
        )

    # -- Institution footer --
    c.setFillColor(PRIMARY)
    c.setFont("Times-Bold", 12)
    c.drawCentredString(W / 2.0, 4.3 * cm, "Higher Teacher Training College \u2013 Bambili")
    c.setFillColor(GOLD)
    c.setFont("Times-Bold", 12)
    c.drawCentredString(W / 2.0, 3.6 * cm, "\u00c9cole Normale Sup\u00e9rieure \u2013 Bambili")

    c.setFillColor(PRIMARY)
    c.setFont("Times-Bold", 16)
    c.drawCentredString(W / 2.0, 2.8 * cm, "THE UNIVERSITY OF BAMENDA")
    c.setFillColor(GRAY)
    c.setFont("Times-Italic", 12)
    c.drawCentredString(W / 2.0, 2.1 * cm, "Universit\u00e9 de Bamenda")

    c.showPage()
    c.save()
    return buffer.getvalue()


def _pdf_page_count(pdf_bytes):
    """Return the number of pages in a generated PDF (best effort)."""
    try:
        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        return 1


def generate_toc_pdf(articles):
    """Table of contents for an issue: lists articles with real page ranges."""
    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title=f"{JOURNAL_NAME} - Table of Contents",
    )

    toc_title = ParagraphStyle(
        "toc_title", fontName="Times-Bold", fontSize=16, leading=20,
        alignment=TA_CENTER, textColor=PRIMARY, spaceAfter=4,
    )
    toc_sub = ParagraphStyle(
        "toc_sub", fontName="Times-Roman", fontSize=10, leading=13,
        alignment=TA_CENTER, textColor=GRAY, spaceAfter=14,
    )

    story = [
        Paragraph(JOURNAL_NAME, toc_title),
        Paragraph(f"{JOURNAL_VOLUME} {JOURNAL_ISSUE} {JOURNAL_YEAR}  \u2022  TABLE OF CONTENTS", toc_sub),
    ]

    # Compute page ranges by generating each published article's journal PDF.
    rows = []
    start = START_PAGE
    for index, article in enumerate(articles, start=1):
        try:
            count = _pdf_page_count(generate_journal_pdf(article))
        except Exception:
            count = 1
        end = start + count - 1
        author = article.author.get_full_name() or article.author.username
        rows.append([
            str(index),
            f"<b>{_esc(article.title)}</b><br/><font size=7.5 color=#444444>{_esc(author)}</font>",
            f"{start}\u2013{end}",
        ])
        start = end + 1

    if rows:
        table = Table(
            rows,
            colWidths=[1.2 * cm, CONTENT_W - 1.2 * cm - 2.2 * cm, 2.2 * cm],
            repeatRows=0,
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#dddddd")),
            ("TEXTCOLOR", (2, 0), (2, -1), GRAY),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No published articles yet.", styles["body"]))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


def generate_editorial_board_pdf():
    """Editorial board page for the journal."""
    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title=f"{JOURNAL_NAME} - Editorial Board",
    )

    board_title = ParagraphStyle(
        "board_title", fontName="Times-Bold", fontSize=16, leading=20,
        alignment=TA_CENTER, textColor=PRIMARY, spaceAfter=4,
    )
    board_sub = ParagraphStyle(
        "board_sub", fontName="Times-Roman", fontSize=10, leading=13,
        alignment=TA_CENTER, textColor=GRAY, spaceAfter=16,
    )
    role_style = ParagraphStyle(
        "role_style", fontName="Times-Bold", fontSize=11, leading=14,
        textColor=PRIMARY, spaceBefore=10, spaceAfter=4,
    )
    member_style = ParagraphStyle(
        "member_style", fontName="Times-Roman", fontSize=10, leading=14,
        textColor=BLACK, leftIndent=8,
    )

    story = [
        Paragraph(JOURNAL_NAME, board_title),
        Paragraph("EDITORIAL BOARD", board_sub),
    ]

    for role, members in EDITORIAL_BOARD.items():
        story.append(Paragraph(role, role_style))
        for member in members:
            story.append(Paragraph(member, member_style))
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
