"""Orchestration : transforme un `Program` en cours Moodle via l'API."""

from __future__ import annotations

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


def build_course(
    client: MoodleClient,
    program: Program,
    category_name: str | None = None,
    dry_run: bool = False,
) -> BuildResult:
    """Crée la catégorie (si besoin), le cours et remplit les sections.

    En `dry_run`, rien n'est envoyé à Moodle : on simule pour vérifier la
    structure parsée.
    """
    warnings: list[str] = []
    cat_name = category_name or program.category_name or "Marque Manque"
    shortname = program.suggested_shortname()
    num_modules = len(program.modules)

    if dry_run:
        return BuildResult(
            course_id=-1,
            shortname=shortname,
            course_url="(dry-run)",
            sections_filled=num_modules,
            warnings=["dry-run : aucune écriture sur Moodle"],
        )

    categoryid = client.ensure_category(cat_name)
    course = client.create_course(
        fullname=program.title,
        shortname=shortname,
        categoryid=categoryid,
        summary=program.summary_html,
        numsections=num_modules,
    )
    course_id = course["id"]

    filled = 0
    for index, module in enumerate(program.modules, start=1):
        try:
            client.update_section(
                courseid=course_id,
                section_number=index,
                name=module.title,
                summary=module.to_html(),
            )
            filled += 1
        except MoodleError as exc:
            warnings.append(
                f"Section {index} '{module.title}' non remplie : {exc}. "
                "Le plugin local_wsmanagesections est-il installé ?"
            )

    return BuildResult(
        course_id=course_id,
        shortname=course["shortname"],
        course_url=f"{client.base_url}/course/view.php?id={course_id}",
        sections_filled=filled,
        warnings=warnings,
    )
