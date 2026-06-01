"""Chargement d'un programme structuré au format JSON vers un `Program`.

Ce format est recommandé pour les programmes officiels (ex: fiches Qualiopi) :
il est fidèle, relisable et versionnable, contrairement au parsing heuristique
d'un PDF dont la mise en page peut être bruitée.

Schéma attendu (tous les champs hors `title`/`modules` sont optionnels) :

{
  "title": "Diversité et inclusion en entreprise",
  "shortname": "alios-inc-03-diversite-inclusion",
  "category_name": "Marque Manque",
  "ref": "INC-03",
  "duration": "2 jours · 14h",
  "total_hours": 14,
  "price_ht": "1 290 €",
  "tagline": "Construire une politique D&I efficace…",
  "objectives": ["…", "…"],
  "public": "Responsables RH, managers…",
  "prerequisites": "Aucun prérequis technique…",
  "modalities": ["Études de cas…"],
  "evaluation": ["Test de positionnement…"],
  "means": ["Salle équipée…"],
  "modules": [
    {
      "title": "Jour 1 — Enjeux et cadre",
      "hours": 7,
      "blocks": [
        {"title": "Diversité et inclusion", "bullets": ["…", "…"]},
        {"title": "Cadre légal", "bullets": ["…"]}
      ]
    }
  ]
}
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .models import Answer, Module, Program, Question


def _esc(text: str) -> str:
    return html.escape(str(text))


def _bullets_html(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>"


def _build_summary(data: dict[str, Any]) -> str:
    """Construit le résumé HTML du cours à partir des métadonnées."""
    parts: list[str] = []
    if data.get("tagline"):
        parts.append(f"<p><em>{_esc(data['tagline'])}</em></p>")

    facts = []
    for label, key in (
        ("Référence", "ref"),
        ("Durée", "duration"),
        ("Tarif HT", "price_ht"),
    ):
        if data.get(key):
            facts.append(f"<li><strong>{label} :</strong> {_esc(data[key])}</li>")
    if facts:
        parts.append("<ul>" + "".join(facts) + "</ul>")

    if data.get("objectives"):
        parts.append("<h4>Objectifs pédagogiques</h4>")
        parts.append(_bullets_html(data["objectives"]))
    if data.get("public"):
        parts.append(f"<h4>Public concerné</h4><p>{_esc(data['public'])}</p>")
    if data.get("prerequisites"):
        parts.append(f"<h4>Prérequis</h4><p>{_esc(data['prerequisites'])}</p>")

    return "\n".join(parts)


def _block_style(title: str) -> tuple[str, str, str]:
    """Retourne (emoji, couleur de bord, fond) selon le type de bloc."""
    t = title.lower()
    table = [
        (("accroche", "objectif"), ("🎯", "#4361ee", "#eef2ff")),
        (("mise en situation", "storytelling"), ("🎬", "#7209b7", "#f6edff")),
        (("cas pratique", "atelier"), ("🧩", "#3a86ff", "#e9f2ff")),
        (("exemple",), ("💡", "#f4a261", "#fff6ec")),
        (("exercice", "mission", "défi", "application", "test"), ("✍️", "#2a9d8f", "#e9f7f4")),
        (("outil", "grille", "checklist", "modèle", "méthode", "catalogue",
          "trame", "canevas", "protocole", "cartograph", "calendrier"),
         ("🛠️", "#6c757d", "#f3f4f6")),
        (("à retenir", "synthèse", "récapitulatif"), ("✅", "#2b9348", "#eaf7ec")),
        (("erreur", "vigilance", "piège"), ("⚠️", "#e63946", "#fdecec")),
        (("pour aller plus loin", "ressource"), ("🔗", "#0077b6", "#e7f5fb")),
    ]
    for keys, style in table:
        if any(k in t for k in keys):
            return style
    return ("📌", "#4361ee", "#f5f7ff")


def _module_html(mod: dict[str, Any]) -> str:
    """Construit le HTML du module : chaque bloc devient un encadré stylé."""
    parts: list[str] = []
    if mod.get("intro"):
        parts.append(
            "<p style=\"font-size:1.05em;font-style:italic;color:#333;"
            f"border-left:4px solid #4361ee;padding-left:.8em\">{_esc(mod['intro'])}</p>"
        )
    for block in mod.get("blocks", []):
        title = block.get("title", "")
        emoji, border, bg = _block_style(title)
        inner: list[str] = []
        if title:
            inner.append(
                f"<h4 style=\"margin:0 0 .4em;color:{border}\">{emoji} {_esc(title)}</h4>"
            )
        if block.get("text"):
            inner.append(f"<p style=\"margin:.2em 0\">{_esc(block['text'])}</p>")
        if block.get("bullets"):
            inner.append(_bullets_html(block["bullets"]))
        parts.append(
            f"<div style=\"border-left:5px solid {border};background:{bg};"
            "padding:.7em 1em;margin:.9em 0;border-radius:8px\">"
            + "\n".join(inner)
            + "</div>"
        )
    return "\n".join(parts)


_TYPE_MAP = {
    "mc": "multichoice",
    "qcu": "multichoice",
    "multichoice": "multichoice",
    "mcm": "multichoice_multi",
    "qcm": "multichoice_multi",
    "multichoice_multi": "multichoice_multi",
    "tf": "truefalse",
    "vf": "truefalse",
    "truefalse": "truefalse",
}


def _parse_questions(raw_quiz: list[dict[str, Any]]) -> list[Question]:
    """Transforme la liste 'quiz' du JSON en objets Question."""
    questions: list[Question] = []
    for item in raw_quiz:
        qtype = _TYPE_MAP.get(item.get("type", "mc"), "multichoice")
        text = item.get("q") or item.get("question", "")
        if qtype == "truefalse":
            correct = bool(item.get("answer", item.get("correct", True)))
            answers = [
                Answer("true", correct, item.get("feedback_true", "")),
                Answer("false", not correct, item.get("feedback_false", "")),
            ]
        else:
            answers = [
                Answer(
                    text=a["text"],
                    correct=bool(a.get("correct", False)),
                    feedback=a.get("feedback", ""),
                )
                for a in item.get("answers", [])
            ]
        questions.append(
            Question(
                text=text,
                answers=answers,
                qtype=qtype,
                name=item.get("name", ""),
                general_feedback=item.get("feedback", ""),
            )
        )
    return questions


def load_json(path: str | Path) -> Program:
    """Charge un programme JSON et renvoie un `Program` enrichi."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    summary = data.get("summary_html") or _build_summary(data)

    # Sections additionnelles (modalités, évaluation, moyens) ajoutées au résumé.
    extras = []
    for label, key in (
        ("Modalités pédagogiques", "modalities"),
        ("Modalités d'évaluation", "evaluation"),
        ("Moyens techniques et accessibilité", "means"),
    ):
        if data.get(key):
            extras.append(f"<h4>{label}</h4>" + _bullets_html(data[key]))
    if extras:
        summary = summary + "\n" + "\n".join(extras)

    modules = [
        Module(
            title=mod["title"],
            content_html=_module_html(mod),
            bullets=mod.get("bullets", []),
            hours=mod.get("hours"),
            questions=_parse_questions(mod.get("quiz", [])),
        )
        for mod in data.get("modules", [])
    ]

    return Program(
        title=data["title"],
        summary_html=summary,
        modules=modules,
        category_name=data.get("category_name"),
        shortname=data.get("shortname"),
        total_hours=data.get("total_hours"),
    )
