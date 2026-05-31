"""Orchestration : transforme un `Program` en cours Moodle via l'API.

Deux modes de remplissage du contenu :

- ``sections`` : une section Moodle par module (titre + résumé). Nécessite le
  plugin ``local_wsmanagesections`` (impossible sur MoodleCloud).
- ``summary`` : tout le programme est concentré dans la présentation du cours,
  via les seules fonctions « core ». **Compatible MoodleCloud** (sans plugin).
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from .client import MoodleClient, MoodleError
from .models import Program


@dataclass
class BuildResult:
    course_id: int
    shortname: str
    course_url: str
    sections_filled: int
    warnings: list[str]


def full_content_html(program: Program) -> str:
    """Assemble tout le programme en un seul bloc HTML (mode ``summary``)."""
    parts: list[str] = []
    if program.summary_html:
        parts.append(program.summary_html)
    if program.modules:
        parts.append("<h3>Programme détaillé</h3>")
    for index, module in enumerate(program.modules, start=1):
        parts.append(f"<h4>{index}. {html.escape(module.display_title())}</h4>")
        body = module.to_html()
        if body:
            parts.append(body)
    return "\n".join(parts)


def build_course(
    client: MoodleClient,
    program: Program,
    category_name: str | None = None,
    dry_run: bool = False,
    content_mode: str = "summary",
) -> BuildResult:
    """Crée la catégorie (si besoin) et le cours, puis remplit le contenu.

    En ``dry_run``, rien n'est envoyé à Moodle : on simule pour vérifier la
    structure parsée.
    """
    warnings: list[str] = []
    cat_name = category_name or program.category_name or "Marque Manque"
    shortname = program.suggested_shortname()
    num_modules = len(program.modules)

    mismatch = program.hours_mismatch()
    if mismatch:
        warnings.append(mismatch)

    if dry_run:
        return BuildResult(
            course_id=-1,
            shortname=shortname,
            course_url="(dry-run)",
            sections_filled=num_modules,
            warnings=["dry-run : aucune écriture sur Moodle"],
        )

    # En mode summary, tout le contenu va dans la présentation du cours.
    course_summary = (
        full_content_html(program)
        if content_mode == "summary"
        else program.summary_html
    )

    categoryid = client.ensure_category(cat_name)
    course = client.create_course(
        fullname=program.title,
        shortname=shortname,
        categoryid=categoryid,
        summary=course_summary,
        numsections=num_modules,
    )
    course_id = course["id"]

    filled = 0
    if content_mode == "sections":
        for index, module in enumerate(program.modules, start=1):
            try:
                client.update_section(
                    courseid=course_id,
                    section_number=index,
                    name=module.display_title(),
                    summary=module.to_html(),
                )
                filled += 1
            except MoodleError as exc:
                warnings.append(
                    f"Section {index} '{module.title}' non remplie : {exc}. "
                    "Le plugin local_wsmanagesections est-il installé ?"
                )
    else:
        warnings.append(
            "Mode 'summary' (MoodleCloud) : tout le programme est dans la "
            "présentation du cours. Pour des sections séparées, il faut un "
            "Moodle auto-hébergé avec le plugin local_wsmanagesections."
        )

    return BuildResult(
        course_id=course_id,
        shortname=course["shortname"],
        course_url=f"{client.base_url}/course/view.php?id={course_id}",
        sections_filled=filled,
        warnings=warnings,
    )
