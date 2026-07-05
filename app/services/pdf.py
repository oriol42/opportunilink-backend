# app/services/pdf.py
# Génère des PDF sobres (lettre de motivation, CV) à archiver dans le coffre-fort.
# fpdf2 avec police cœur (Helvetica) → encodage latin-1 : on nettoie le texte
# pour éviter tout crash sur un caractère non latin-1 (emoji, guillemets courbes…).
from fpdf import FPDF

ACCENT = (13, 148, 136)     # teal discret, unique couleur d'accent
DARK   = (15, 23, 42)
GRAY   = (100, 116, 139)
BODY   = (30, 41, 59)

_SUBST = {"’": "'", "‘": "'", "“": '"', "”": '"',
          "–": "-", "—": "-", "…": "...", " ": " ", "•": "-"}


def _clean(s: str) -> str:
    s = s or ""
    for k, v in _SUBST.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _section_title(pdf: FPDF, label: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 6, _clean(label.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(2)


def letter_pdf(author: str, subtitle: str, body: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(22, 20, 22)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 8, _clean(author), new_x="LMARGIN", new_y="NEXT")
    if subtitle:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, _clean(subtitle), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*BODY)
    for para in (body or "").split("\n"):
        para = para.strip()
        if para:
            pdf.multi_cell(0, 6.4, _clean(para), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2.2)
    return bytes(pdf.output())


def cv_pdf(author: str, contact: str, cv: dict) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    # En-tête
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, _clean(author), new_x="LMARGIN", new_y="NEXT")
    if cv.get("titre_accroche"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*ACCENT)
        pdf.cell(0, 6, _clean(cv["titre_accroche"]), new_x="LMARGIN", new_y="NEXT")
    if contact:
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, _clean(contact), new_x="LMARGIN", new_y="NEXT")

    if cv.get("resume_profil"):
        _section_title(pdf, "Profil")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*BODY)
        pdf.multi_cell(0, 5.6, _clean(cv["resume_profil"]), new_x="LMARGIN", new_y="NEXT")

    if cv.get("formation"):
        _section_title(pdf, "Formation")
        for f in cv["formation"]:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 5.6, _clean(f.get("titre", "")), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(*GRAY)
            line = " - ".join(x for x in [f.get("etablissement", ""), f.get("periode", "")] if x)
            pdf.multi_cell(0, 5.2, _clean(line), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

    if cv.get("competences_techniques"):
        _section_title(pdf, "Compétences techniques")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*BODY)
        pdf.multi_cell(0, 5.6, _clean(", ".join(cv["competences_techniques"])), new_x="LMARGIN", new_y="NEXT")

    if cv.get("competences_transverses"):
        _section_title(pdf, "Compétences transversales")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*BODY)
        pdf.multi_cell(0, 5.6, _clean(", ".join(cv["competences_transverses"])), new_x="LMARGIN", new_y="NEXT")

    if cv.get("langues"):
        _section_title(pdf, "Langues")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*BODY)
        langs = ", ".join(f'{l.get("langue","")} ({l.get("niveau","")})' for l in cv["langues"])
        pdf.multi_cell(0, 5.6, _clean(langs), new_x="LMARGIN", new_y="NEXT")

    if cv.get("points_forts"):
        _section_title(pdf, "Points forts")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*BODY)
        for p in cv["points_forts"]:
            pdf.multi_cell(0, 5.6, _clean(f"- {p}"), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
