"""Interface en ligne de commande.

Exemples :
    # Vérifier la connexion à Moodle
    python -m moodle_lms.cli check

    # Voir la structure parsée d'un programme SANS rien créer
    python -m moodle_lms.cli preview programmes/mon-programme.pdf

    # Créer le cours sur Moodle
    python -m moodle_lms.cli build programmes/mon-programme.pdf \
        --category "Marque Manque"
"""

from __future__ import annotations

import argparse
import html
import os
import sys

from dotenv import load_dotenv

from .client import MoodleClient
from .course_builder import build_course
from .document_parser import parse_document


class _DummyClient:
    """Substitut non fonctionnel utilisé uniquement en --dry-run."""

    base_url = "(dry-run)"


def _make_client() -> MoodleClient:
    load_dotenv()
    url = os.getenv("MOODLE_URL")
    token = os.getenv("MOODLE_TOKEN")
    if not url or not token:
        sys.exit(
            "Erreur : MOODLE_URL et MOODLE_TOKEN doivent être définis "
            "(copie .env.example vers .env)."
        )
    return MoodleClient(url, token)


def cmd_check(_: argparse.Namespace) -> None:
    client = _make_client()
    info = client.site_info()
    print("Connexion OK ✅")
    print(f"  Site      : {info.get('sitename')}")
    print(f"  Utilisateur: {info.get('fullname')}")
    print(f"  Version   : {info.get('release')}")


def cmd_preview(args: argparse.Namespace) -> None:
    program = parse_document(args.document, title=args.title)
    print(f"Titre du cours : {program.title}")
    print(f"Modules détectés : {len(program.modules)}\n")
    for i, module in enumerate(program.modules, start=1):
        print(f"  {i}. {module.title}")
        for bullet in module.bullets:
            print(f"       - {html.unescape(bullet)}")


def cmd_build(args: argparse.Namespace) -> None:
    program = parse_document(args.document, title=args.title)
    # En dry-run, build_course n'appelle jamais le client : on en passe un factice.
    client = _DummyClient() if args.dry_run else _make_client()
    result = build_course(client, program, args.category, dry_run=args.dry_run)

    print(f"Cours : {program.title}")
    print(f"  shortname : {result.shortname}")
    print(f"  id        : {result.course_id}")
    print(f"  URL       : {result.course_url}")
    print(f"  sections remplies : {result.sections_filled}")
    for warning in result.warnings:
        print(f"  ⚠️  {warning}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="moodle_lms",
        description="Crée des formations Moodle à partir de documents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Teste la connexion à Moodle")
    p_check.set_defaults(func=cmd_check)

    p_prev = sub.add_parser("preview", help="Affiche la structure parsée")
    p_prev.add_argument("document", help="Chemin du programme (.pdf/.docx/.txt)")
    p_prev.add_argument("--title", help="Forcer le titre du cours")
    p_prev.set_defaults(func=cmd_preview)

    p_build = sub.add_parser("build", help="Crée le cours sur Moodle")
    p_build.add_argument("document", help="Chemin du programme (.pdf/.docx/.txt)")
    p_build.add_argument("--title", help="Forcer le titre du cours")
    p_build.add_argument(
        "--category", default="Marque Manque", help="Catégorie cible"
    )
    p_build.add_argument(
        "--dry-run", action="store_true", help="Simuler sans écrire sur Moodle"
    )
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
