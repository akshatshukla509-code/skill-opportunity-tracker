"""Build docs/Project_Guide.pdf from docs/GUIDE.md (simple markdown subset). Run: python docs/build_pdf.py"""
import os, re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (ListFlowable, ListItem, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13.5, spaceAfter=4)
CELL = ParagraphStyle("c", parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, textColor=colors.HexColor("#3b5bdb"), spaceBefore=14)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=10, backColor=colors.HexColor("#f1f3f9"),
                      borderPadding=5, spaceBefore=4, spaceAfter=8)


def inline(t):
    t = escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`(.+?)`", r'<font name="Courier" size="8.5">\1</font>', t)


def build():
    lines = open(os.path.join(HERE, "GUIDE.md"), encoding="utf-8").read().split("\n")
    story, i = [], 0
    story += [Spacer(1, 5 * cm), Paragraph("Student Skill &amp; Opportunity Tracker", ss["Title"]),
              Paragraph("Process, UI and backend development guide", ParagraphStyle("s", parent=ss["Heading2"], alignment=1)),
              Spacer(1, 1 * cm),
              Paragraph("Flask REST API &middot; SQLite &middot; vanilla JavaScript UI &middot; unittest", ParagraphStyle("t", parent=BODY, alignment=1)),
              PageBreak()]
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1; code = []
            while not lines[j].startswith("```"): code.append(lines[j]); j += 1
            story.append(Preformatted("\n".join(code), CODE)); i = j + 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.fullmatch(r"\|[-| ]+\|", lines[i]):
                    rows.append([Paragraph(inline(c.strip()), CELL) for c in lines[i].strip("|").split("|")])
                i += 1
            W = A4[0] - 4 * cm
            fr = [0.22, 0.30, 0.48] if len(rows[0]) == 3 else [0.42, 0.58]
            t = Table(rows, colWidths=[W * f for f in fr], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe4ff")),
                                   ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 8)]; continue
        if ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(ListItem(Paragraph(inline(lines[i][2:]), BODY))); i += 1
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=14)); continue
        if re.match(r"\d+\. ", ln):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                items.append(ListItem(Paragraph(inline(re.sub(r"^\d+\. ", "", lines[i])), BODY))); i += 1
            story.append(ListFlowable(items, bulletType="1", leftIndent=16)); continue
        if ln.startswith("# "): i += 1; continue  # title is on the cover
        if ln.startswith("## "): story.append(Paragraph(inline(ln[3:]), H1))
        elif ln.startswith("### "): story.append(Paragraph(inline(ln[4:]), H2))
        elif ln.strip(): story.append(Paragraph(inline(ln), BODY))
        i += 1
    out = os.path.join(HERE, "Project_Guide.pdf")
    SimpleDocTemplate(out, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                      title="Skill & Opportunity Tracker Guide").build(
        story, onLaterPages=lambda c, d: (c.setFont("Helvetica", 8), c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {d.page}")))
    print("wrote", out)


build()
