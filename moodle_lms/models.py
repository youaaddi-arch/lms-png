"""Modèles de données décrivant un programme de formation.

Ces structures sont indépendantes de Moodle : un parseur (PDF, Word, texte…)
les remplit, puis le `course_builder` les transforme en cours Moodle.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass
class Module:
    """Un module / chapitre / section d'une formation."""

    title: str
    content_html: str = ""
    # Sous-points (objectifs, savoir-faire…) listés sous le module.
    bullets: list[str] = field(default_factory=list)

    def to_html(self) -> str:
        """Rend le contenu du module en HTML pour le résumé de section Moodle."""
        parts: list[str] = []
        if self.content_html:
            parts.append(self.content_html)
        if self.bullets:
            items = "".join(f"<li>{b}</li>" for b in self.bullets)
            parts.append(f"<ul>{items}</ul>")
        return "\n".join(parts)


@dataclass
class Program:
    """Un programme de formation complet, prêt à devenir un cours Moodle."""

    title: str
    summary_html: str = ""
    modules: list[Module] = field(default_factory=list)
    # Métadonnées optionnelles utilisées à la création du cours.
    category_name: str | None = None
    shortname: str | None = None

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
