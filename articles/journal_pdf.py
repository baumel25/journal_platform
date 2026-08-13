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
)

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
