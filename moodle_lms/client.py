"""Client léger pour l'API REST des Web Services Moodle.

Authentification par token (jeton de service web), jamais par mot de passe.
Doc Moodle : https://docs.moodle.org/dev/Web_service_API_functions
"""

from __future__ import annotations

import json
from typing import Any

import requests


class MoodleError(RuntimeError):
    """Erreur renvoyée par l'API Moodle (exception/warning)."""


class MoodleClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        if not base_url or not token:
            raise ValueError("base_url et token sont requis.")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._endpoint = f"{self.base_url}/webservice/rest/server.php"

    # --- Bas niveau -------------------------------------------------------

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Appelle une fonction de Web Service et renvoie la réponse décodée.

        Les paramètres complexes (listes/dicts) sont aplatis au format
        attendu par Moodle (ex: courses[0][fullname]=...).
        """
        payload: dict[str, str] = {
            "wstoken": self.token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        payload.update(_flatten(params))

        resp = requests.post(self._endpoint, data=payload, timeout=self.timeout)
        resp.raise_for_status()

        # Une réponse vide (ex: void) est valide.
        if not resp.text.strip():
            return None

        data = resp.json()
        if isinstance(data, dict) and data.get("exception"):
            raise MoodleError(
                f"{data.get('errorcode')}: {data.get('message')} "
                f"(fonction {wsfunction})"
            )
        return data

    # --- Helpers haut niveau ---------------------------------------------

    def site_info(self) -> dict[str, Any]:
        """Vérifie la connexion et renvoie les infos du site / de l'utilisateur."""
        return self.call("core_webservice_get_site_info")

    def find_category(self, name: str) -> int | None:
        """Retourne l'id d'une catégorie par son nom, ou None."""
        try:
            res = self.call(
                "core_course_get_categories",
                criteria=[{"key": "name", "value": name}],
            )
        except MoodleError:
            return None
        if res:
            return res[0]["id"]
        return None

    def ensure_category(self, name: str, parent: int = 0) -> int:
        """Retourne l'id d'une catégorie, en la créant si nécessaire."""
        existing = self.find_category(name)
        if existing is not None:
            return existing
        created = self.call(
            "core_course_create_categories",
            categories=[{"name": name, "parent": parent}],
        )
        return created[0]["id"]

    def create_course(
        self,
        fullname: str,
        shortname: str,
        categoryid: int,
        summary: str = "",
        numsections: int | None = None,
        format: str = "topics",
    ) -> dict[str, Any]:
        """Crée un cours et renvoie {id, shortname}."""
        course: dict[str, Any] = {
            "fullname": fullname,
            "shortname": shortname,
            "categoryid": categoryid,
            "summary": summary,
            "summaryformat": 1,  # HTML
            "format": format,
        }
        if numsections is not None:
            course["courseformatoptions"] = [
                {"name": "numsections", "value": numsections}
            ]
        created = self.call("core_course_create_courses", courses=[course])
        return created[0]

    def update_section(
        self, courseid: int, section_number: int, name: str, summary: str
    ) -> None:
        """Met à jour le titre et le résumé HTML d'une section.

        Nécessite le plugin `local_wsmanagesections`. Si absent, lève MoodleError
        avec un message explicite (voir README).
        """
        self.call(
            "local_wsmanagesections_update_sections",
            courseid=courseid,
            sections=[
                {
                    "type": "num",
                    "section": section_number,
                    "name": name,
                    "summary": summary,
                    "summaryformat": 1,
                }
            ],
        )


def _flatten(params: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Aplatit listes/dicts imbriqués au format de formulaire attendu par Moodle."""
    flat: dict[str, str] = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                item_name = f"{name}[{i}]"
                if isinstance(item, (dict, list, tuple)):
                    flat.update(_flatten({str(i): item}, name))
                else:
                    flat[item_name] = _scalar(item)
        else:
            flat[name] = _scalar(value)
    return flat


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)
