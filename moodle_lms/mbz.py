"""Génération d'un fichier de sauvegarde Moodle (.mbz) à partir d'un `Program`.

Le .mbz est une archive tar gzip contenant un backup au format ``moodle2``.
Cette version produit un backup **de cours sans activités** : chaque module
devient une **section** (thème) dont le **résumé** porte le contenu développé,
visible directement dans le corps du cours. C'est le format le plus robuste à
restaurer, et il fonctionne sur MoodleCloud (Cours → Restaurer).

Le backup est volontairement déclaré en version Moodle « ancienne » (4.3) :
Moodle autorise la restauration d'un backup plus ancien dans une instance plus
récente, ce qui maximise la compatibilité (testé pour cible Moodle 4.x / 5.x).
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import time
from pathlib import Path

from .course_builder import full_content_html  # noqa: F401  (réutilisable)
from .models import Program

# Versions déclarées dans le backup (4.3 : compatible restauration vers 5.x).
_MOODLE_VERSION = "2023100900"
_MOODLE_RELEASE = "4.3"
_BACKUP_VERSION = "2023100900"
_BACKUP_RELEASE = "4.3"

_NULL = "$@NULL@$"


def _x(text: str) -> str:
    """Échappe le texte pour XML (le contenu HTML est encapsulé en CDATA)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cdata(html_content: str) -> str:
    """Encapsule du HTML dans une section CDATA (sûr pour les résumés)."""
    safe = (html_content or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


class _Section:
    def __init__(self, sid: int, number: int, name: str, summary_html: str):
        self.id = sid
        self.number = number
        self.name = name
        self.summary = summary_html


def _build_sections(program: Program) -> list[_Section]:
    """Section 0 (général) = présentation ; sections 1..N = les modules."""
    sections = [
        _Section(1, 0, "", _section0_summary(program)),
    ]
    for index, module in enumerate(program.modules, start=1):
        sections.append(
            _Section(index + 1, index, module.display_title(), module.to_html())
        )
    return sections


def _section0_summary(program: Program) -> str:
    """Contenu de la section générale : présentation du cours."""
    return program.summary_html or ""


def _moodle_backup_xml(program: Program, sections: list[_Section], name: str) -> str:
    now = int(time.time())
    backup_id = hashlib.md5(name.encode()).hexdigest()
    shortname = program.suggested_shortname()

    sec_contents = "\n".join(
        f"""      <section>
        <sectionid>{s.id}</sectionid>
        <title>{_x(s.name or str(s.number))}</title>
        <directory>sections/section_{s.id}</directory>
      </section>"""
        for s in sections
    )

    root_settings = [
        ("filename", name),
        ("users", "0"),
        ("anonymize", "0"),
        ("role_assignments", "0"),
        ("activities", "0"),
        ("blocks", "0"),
        ("files", "0"),
        ("filters", "0"),
        ("comments", "0"),
        ("badges", "0"),
        ("calendarevents", "0"),
        ("userscompletion", "0"),
        ("logs", "0"),
        ("grade_histories", "0"),
        ("questionbank", "0"),
        ("groups", "0"),
        ("competencies", "0"),
        ("customfield", "0"),
        ("contentbankcontent", "0"),
        ("legacyfiles", "0"),
    ]
    settings_xml = "\n".join(
        f"""    <setting>
      <level>root</level>
      <name>{_x(n)}</name>
      <value>{_x(v)}</value>
    </setting>"""
        for n, v in root_settings
    )

    section_settings = "\n".join(
        f"""    <setting>
      <level>section</level>
      <section>section_{s.id}</section>
      <name>section_{s.id}_included</name>
      <value>1</value>
    </setting>
    <setting>
      <level>section</level>
      <section>section_{s.id}</section>
      <name>section_{s.id}_userinfo</name>
      <value>0</value>
    </setting>"""
        for s in sections
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<moodle_backup>
  <information>
    <name>{_x(name)}</name>
    <moodle_version>{_MOODLE_VERSION}</moodle_version>
    <moodle_release>{_MOODLE_RELEASE}</moodle_release>
    <backup_version>{_BACKUP_VERSION}</backup_version>
    <backup_release>{_BACKUP_RELEASE}</backup_release>
    <backup_date>{now}</backup_date>
    <mnet_remoteusers>0</mnet_remoteusers>
    <include_files>1</include_files>
    <include_file_references_to_external_content>0</include_file_references_to_external_content>
    <original_wwwroot>https://localhost</original_wwwroot>
    <original_site_identifier_hash>{backup_id}</original_site_identifier_hash>
    <original_course_id>2</original_course_id>
    <original_course_format>topics</original_course_format>
    <original_course_fullname>{_x(program.title)}</original_course_fullname>
    <original_course_shortname>{_x(shortname)}</original_course_shortname>
    <original_course_startdate>{now}</original_course_startdate>
    <original_course_enddate>0</original_course_enddate>
    <original_course_contextid>100</original_course_contextid>
    <original_system_contextid>1</original_system_contextid>
    <details>
      <detail backup_id="{backup_id}">
        <type>course</type>
        <format>moodle2</format>
        <interactive>1</interactive>
        <mode>10</mode>
        <execution>1</execution>
        <executiontime>0</executiontime>
      </detail>
    </details>
    <contents>
      <activities></activities>
      <sections>
{sec_contents}
      </sections>
      <course>
        <courseid>2</courseid>
        <title>{_x(shortname)}</title>
        <directory>course</directory>
      </course>
    </contents>
    <settings>
{settings_xml}
{section_settings}
  </settings>
  </information>
</moodle_backup>
"""


def _course_xml(program: Program) -> str:
    now = int(time.time())
    shortname = program.suggested_shortname()
    numsections = len(program.modules)
    category = program.category_name or "Marque Manque"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<course id="2" contextid="100">
  <shortname>{_x(shortname)}</shortname>
  <fullname>{_x(program.title)}</fullname>
  <idnumber></idnumber>
  <summary>{_cdata(program.summary_html)}</summary>
  <summaryformat>1</summaryformat>
  <format>topics</format>
  <showgrades>1</showgrades>
  <newsitems>0</newsitems>
  <startdate>{now}</startdate>
  <enddate>0</enddate>
  <marker>0</marker>
  <maxbytes>0</maxbytes>
  <legacyfiles>0</legacyfiles>
  <showreports>0</showreports>
  <visible>1</visible>
  <groupmode>0</groupmode>
  <groupmodeforce>0</groupmodeforce>
  <defaultgroupingid>0</defaultgroupingid>
  <lang></lang>
  <theme></theme>
  <timecreated>{now}</timecreated>
  <timemodified>{now}</timemodified>
  <requested>0</requested>
  <showactivitydates>1</showactivitydates>
  <showcompletionconditions>1</showcompletionconditions>
  <enablecompletion>0</enablecompletion>
  <completionnotify>0</completionnotify>
  <category id="10">
    <name>{_x(category)}</name>
    <description></description>
  </category>
  <tags></tags>
  <customfields></customfields>
  <courseformatoptions>
    <courseformatoption>
      <format>topics</format>
      <sectionid>0</sectionid>
      <name>hiddensections</name>
      <value>1</value>
    </courseformatoption>
    <courseformatoption>
      <format>topics</format>
      <sectionid>0</sectionid>
      <name>coursedisplay</name>
      <value>0</value>
    </courseformatoption>
    <courseformatoption>
      <format>topics</format>
      <sectionid>0</sectionid>
      <name>numsections</name>
      <value>{numsections}</value>
    </courseformatoption>
  </courseformatoptions>
</course>
"""


def _section_xml(section: _Section) -> str:
    now = int(time.time())
    name = _x(section.name) if section.name else _NULL
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<section id="{section.id}">
  <number>{section.number}</number>
  <name>{name}</name>
  <summary>{_cdata(section.summary)}</summary>
  <summaryformat>1</summaryformat>
  <sequence></sequence>
  <visible>1</visible>
  <availabilityjson>{_NULL}</availabilityjson>
  <timemodified>{now}</timemodified>
</section>
"""


def write_mbz(program: Program, out_path: str | Path) -> Path:
    """Génère le fichier .mbz et renvoie son chemin."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = path.name

    sections = _build_sections(program)

    files: dict[str, str] = {
        "moodle_backup.xml": _moodle_backup_xml(program, sections, name),
        "files.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<files></files>\n",
        "scales.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<scales_definition></scales_definition>\n",
        "outcomes.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<outcomes_definition></outcomes_definition>\n",
        "roles.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<roles_definition></roles_definition>\n",
        "questions.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<question_categories></question_categories>\n",
        "groups.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<groups><groupings></groupings></groups>\n",
        "badges.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<badges></badges>\n",
        "gradebook.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<gradebook>"
            "<grade_categories></grade_categories><grade_items></grade_items>"
            "<grade_letters></grade_letters><grade_settings></grade_settings>"
            "</gradebook>\n"
        ),
        "grade_history.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<grade_history><grade_grades></grade_grades></grade_history>\n"
        ),
        "course/course.xml": _course_xml(program),
        "course/enrolments.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<enrolments><enrols></enrols></enrolments>\n"
        ),
        "course/inforef.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<inforef></inforef>\n",
        "course/roles.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<roles>"
            "<role_overrides></role_overrides>"
            "<role_assignments></role_assignments></roles>\n"
        ),
        "course/filters.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<filters>"
            "<filter_actives></filter_actives>"
            "<filter_configs></filter_configs></filters>\n"
        ),
        "course/calendar.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<calendar>"
            "<events></events></calendar>\n"
        ),
        "course/completiondefaults.xml": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<course_completion_defaults></course_completion_defaults>\n"
        ),
    }

    for section in sections:
        base = f"sections/section_{section.id}"
        files[f"{base}/section.xml"] = _section_xml(section)
        files[f"{base}/inforef.xml"] = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<inforef></inforef>\n"
        )

    now = int(time.time())
    with tarfile.open(path, "w:gz") as tar:
        for arcname, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=arcname)
            info.size = len(data)
            info.mtime = now
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))

    return path
