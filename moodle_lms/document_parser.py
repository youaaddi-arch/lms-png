"""Conversion d'un document de programme (PDF / Word / texte) en `Program`.

Heuristique simple et robuste :
  - La 1re ligne non vide « titre » devient le titre du cours.
  - Les lignes qui ressemblent à des titres de section (numérotées, en
    MAJUSCULES, ou préfixées "Module"/"Chapitre") ouvrent un nouveau module.
  - Les puces (-, *, •, 1.) deviennent des bullets ; le reste, du contenu.

Le but n'est pas une IA de compréhension parfaite, mais une structure
exploitable que tu peux relire/ajuster avant publication.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from .models import Module, Program

_BULLET_RE = re.compile(r"^\s*(?:[-*•▪◦]|\d+[.)])\s+(.*)$")
_SECTION_RE = re.compile(
    r"^\s*(?:module|chapitre|partie|séquence|sequence|unité|unite)\b",
    re.IGNORECASE,
)
_NUMBERED_TITLE_RE = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+\S")


def extract_text(path: str | Path) -> str:
    """Extrait le texte brut d'un fichier .pdf, .docx ou .txt/.md."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(p)
    if suffix in {".docx"}:
        return _extract_docx(p)
    if suffix in {".txt", ".md"}:
        return p.read_text(encoding="utf-8")
    raise ValueError(
        f"Format non supporté : {suffix}. Utilise .pdf, .docx, .txt ou .md "
        "(convertis les .doc en .docx au préalable)."
    )


def _extract_pdf(p: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(p))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(p: Path) -> str:
    import docx

    doc = docx.Document(str(p))
    return "\n".join(par.text for par in doc.paragraphs)


def _looks_like_section(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _SECTION_RE.match(stripped):
        return True
    if _NUMBERED_TITLE_RE.match(stripped):
        return True
    # Titre court tout en majuscules.
    letters = [c for c in stripped if c.isalpha()]
    if letters and len(stripped) <= 80 and stripped == stripped.upper():
        return True
    return False


def parse_text(text: str, title: str | None = None) -> Program:
    """Transforme un texte brut en `Program` structuré."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    non_empty = [ln for ln in lines if ln.strip()]

    program_title = title or (non_empty[0].strip() if non_empty else "Formation")

    program = Program(title=program_title)
    current: Module | None = None
    # On saute la 1re ligne si elle a servi de titre (et qu'aucun titre forcé).
    start_index = 0
    if title is None and non_empty:
        # Retrouver l'index réel de la 1re ligne non vide.
        for i, ln in enumerate(lines):
            if ln.strip():
                start_index = i + 1
                break

    for line in lines[start_index:]:
        stripped = line.strip()
        if not stripped:
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            text_b = html.escape(bullet.group(1).strip())
            if current is None:
                current = Module(title="Introduction")
                program.modules.append(current)
            current.bullets.append(text_b)
            continue

        if _looks_like_section(line):
            current = Module(title=stripped)
            program.modules.append(current)
            continue

        # Paragraphe de contenu.
        para = f"<p>{html.escape(stripped)}</p>"
        if current is None:
            program.summary_html += para
        else:
            current.content_html += para

    return program


def parse_document(path: str | Path, title: str | None = None) -> Program:
    """Pipeline complet : fichier -> texte -> `Program`."""
    return parse_text(extract_text(path), title=title)
