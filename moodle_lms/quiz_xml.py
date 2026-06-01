"""Génération d'un fichier de questions au format **Moodle XML**.

Ce fichier s'importe dans Moodle (y compris MoodleCloud) via :
    Banque de questions → Importer → format « Format XML Moodle ».
On peut ensuite créer une activité « Test » et y piocher les questions.

Types supportés : choix multiple (réponse unique ou multiple) et vrai/faux.
"""

from __future__ import annotations

from pathlib import Path

from .models import Program, Question


def _cdata(text: str) -> str:
    safe = (text or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _question_xml(q: Question, number: int) -> str:
    name = q.name or f"Q{number} — {q.text[:60]}"
    parts = [
        f'  <question type="{q.qtype if q.qtype != "multichoice_multi" else "multichoice"}">',
        f"    <name><text>{_cdata(name)}</text></name>",
        f'    <questiontext format="html"><text>{_cdata(q.text)}</text></questiontext>',
        '    <defaultgrade>1.0000000</defaultgrade>',
        '    <penalty>0.3333333</penalty>',
        '    <hidden>0</hidden>',
    ]

    if q.general_feedback:
        parts.append(
            f'    <generalfeedback format="html"><text>{_cdata(q.general_feedback)}</text>'
            "</generalfeedback>"
        )

    if q.qtype in ("multichoice", "multichoice_multi"):
        parts.append(f"    <single>{'true' if q.single else 'false'}</single>")
        parts.append("    <shuffleanswers>true</shuffleanswers>")
        parts.append("    <answernumbering>abc</answernumbering>")
        n_correct = sum(1 for a in q.answers if a.correct) or 1
        for a in q.answers:
            if q.single:
                fraction = "100" if a.correct else "0"
            else:
                # Réponses multiples : les bonnes se partagent 100 %,
                # les mauvaises retirent des points.
                fraction = (
                    f"{100 / n_correct:.5f}" if a.correct else "-100"
                )
            parts.append(f'    <answer fraction="{fraction}" format="html">')
            parts.append(f"      <text>{_cdata(a.text)}</text>")
            parts.append(
                f'      <feedback format="html"><text>{_cdata(a.feedback)}</text></feedback>'
            )
            parts.append("    </answer>")
    elif q.qtype == "truefalse":
        for a in q.answers:
            fraction = "100" if a.correct else "0"
            parts.append(f'    <answer fraction="{fraction}" format="html">')
            parts.append(f"      <text>{a.text}</text>")
            parts.append(
                f'      <feedback format="html"><text>{_cdata(a.feedback)}</text></feedback>'
            )
            parts.append("    </answer>")

    parts.append("  </question>")
    return "\n".join(parts)


def render_quiz_xml(program: Program, category: str | None = None) -> str:
    """Construit le contenu XML Moodle de toutes les questions du programme."""
    cat = category or f"{program.suggested_shortname()}"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]

    # Catégorie d'accueil des questions dans la banque.
    lines.append('  <question type="category">')
    lines.append(
        f"    <category><text>$course$/top/{_escape_cat(cat)}</text></category>"
    )
    lines.append("  </question>")

    number = 0
    for module in program.modules:
        if not module.questions:
            continue
        for q in module.questions:
            number += 1
            if not q.name:
                q.name = f"{module.title} — Q{number}"
            lines.append(_question_xml(q, number))

    lines.append("</quiz>")
    return "\n".join(lines) + "\n"


def _escape_cat(name: str) -> str:
    return name.replace("/", "-")


def write_quiz_xml(
    program: Program, out_path: str | Path, category: str | None = None
) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_quiz_xml(program, category), encoding="utf-8")
    return path
