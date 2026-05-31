"""Modèles de données décrivant un programme de formation.

Ces structures sont indépendantes de Moodle : un parseur (PDF, Word, texte…)
les remplit, puis le `course_builder` les transforme en cours Moodle.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass
class Answer:
    """Une réponse possible à une question de quiz."""

    text: str
    correct: bool = False
    feedback: str = ""


@dataclass
class Question:
    """Une question de quiz (choix multiple ou vrai/faux)."""

    text: str
    answers: list[Answer] = field(default_factory=list)
    # 'multichoice' (une bonne réponse), 'multichoice_multi' (plusieurs),
    # ou 'truefalse'.
    qtype: str = "multichoice"
    name: str = ""
    general_feedback: str = ""

    @property
    def single(self) -> bool:
        """Vrai si une seule bonne réponse (choix unique)."""
        return self.qtype != "multichoice_multi"


@dataclass
class Module:
    """Un module / chapitre / section d'une formation."""

    title: str
    content_html: str = ""
    # Sous-points (objectifs, savoir-faire…) listés sous le module.
    bullets: list[str] = field(default_factory=list)
    # Durée du module en heures (ex: 7.0 pour un jour de 7h), si connue.
    hours: float | None = None
    # Questions de quiz rattachées au module.
    questions: list[Question] = field(default_factory=list)

    def display_title(self) -> str:
        """Titre de section, avec la durée si elle est renseignée."""
        if self.hours is not None and "h)" not in self.title:
            return f"{self.title} ({_fmt_hours(self.hours)})"
        return self.title

    def to_html(self) -> str:
        """Rend le contenu du module en HTML pour le résumé de section Moodle."""
        parts: list[str] = []
        if self.content_html:
            parts.append(self.content_html)
        if self.bullets:
            items = "".join(f"<li>{b}</li>" for b in self.bullets)
            parts.append(f"<ul>{items}</ul>")
        return "\n".join(parts)


def _fmt_hours(hours: float) -> str:
    """Formate une durée : 7.0 -> '7h', 1.5 -> '1h30'."""
    whole = int(hours)
    minutes = round((hours - whole) * 60)
    return f"{whole}h{minutes:02d}" if minutes else f"{whole}h"


@dataclass
class Program:
    """Un programme de formation complet, prêt à devenir un cours Moodle."""

    title: str
    summary_html: str = ""
    modules: list[Module] = field(default_factory=list)
    # Métadonnées optionnelles utilisées à la création du cours.
    category_name: str | None = None
    shortname: str | None = None
    # Durée totale annoncée (en heures), pour contrôle de cohérence.
    total_hours: float | None = None

    def all_questions(self) -> list[Question]:
        """Toutes les questions de quiz du programme, tous modules confondus."""
        out: list[Question] = []
        for module in self.modules:
            out.extend(module.questions)
        return out

    def modules_hours(self) -> float | None:
        """Somme des heures des modules, ou None si aucune n'est renseignée."""
        known = [m.hours for m in self.modules if m.hours is not None]
        return sum(known) if known else None

    def hours_mismatch(self) -> str | None:
        """Retourne un message si la somme des modules ≠ durée annoncée."""
        total = self.total_hours
        summed = self.modules_hours()
        if total is None or summed is None:
            return None
        if abs(total - summed) > 0.01:
            return (
                f"Durée annoncée {_fmt_hours(total)} ≠ somme des modules "
                f"{_fmt_hours(summed)}"
            )
        return None

    def suggested_shortname(self) -> str:
        """Génère un nom court (shortname) Moodle si aucun n'est fourni."""
        if self.shortname:
            return self.shortname
        # Translittère les accents en ASCII (é -> e) puis slugifie.
        ascii_title = (
            unicodedata.normalize("NFKD", self.title)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        slug = "".join(
            c if c.isalnum() else "-" for c in ascii_title.lower()
        ).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        # Moodle limite le shortname ; on tronque raisonnablement.
        return slug[:100] or "formation"
