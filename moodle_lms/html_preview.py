"""Génère un aperçu HTML autonome d'un `Program`.

Utile pour valider visuellement le cours avant de le créer sur Moodle
(notamment quand on n'a pas encore de token / d'accès au site).
"""

from __future__ import annotations

import html
from pathlib import Path

from .models import Program

_CSS = """
body{font-family:system-ui,Arial,sans-serif;max-width:820px;margin:2rem auto;
padding:0 1rem;color:#1a1a2e;line-height:1.5}
h1{border-bottom:3px solid #4361ee;padding-bottom:.3rem}
.section{border:1px solid #e0e0e0;border-radius:8px;margin:1rem 0;padding:1rem 1.25rem}
.section h2{margin-top:0;color:#3a0ca3}
.meta{background:#f5f7ff;border-radius:8px;padding:1rem 1.25rem}
h4,h5{margin:.6rem 0 .2rem}
ul{margin:.2rem 0 .6rem}
.badge{display:inline-block;background:#4361ee;color:#fff;border-radius:4px;
padding:.1rem .5rem;font-size:.85rem;margin-left:.5rem}
"""


def render_html(program: Program) -> str:
    """Construit une page HTML complète représentant le cours."""
    title = html.escape(program.title)
    parts: list[str] = [
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>",
        f"<title>{title}</title><style>{_CSS}</style></head><body>",
        f"<h1>{title}</h1>",
    ]

    if program.total_hours is not None:
        from .models import _fmt_hours

        parts.append(
            f"<p class='badge'>Durée totale : {_fmt_hours(program.total_hours)}</p>"
        )

    if program.summary_html:
        parts.append(f"<div class='meta'>{program.summary_html}</div>")

    for i, module in enumerate(program.modules, start=1):
        parts.append("<div class='section'>")
        parts.append(f"<h2>{i}. {html.escape(module.display_title())}</h2>")
        body = module.to_html()
        if body:
            parts.append(body)
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


def write_html(program: Program, out_path: str | Path) -> Path:
    """Écrit l'aperçu HTML sur disque et renvoie le chemin."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(program), encoding="utf-8")
    return path
