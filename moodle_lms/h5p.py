"""Génération de fichiers ``.h5p`` importables dans Moodle.

Un fichier ``.h5p`` est une archive ZIP auto-suffisante contenant :

* ``h5p.json`` — le manifeste (titre, librairie principale, langue, et la
  liste ``preloadedDependencies`` de toutes les librairies embarquées) ;
* ``content/content.json`` — le contenu, conforme à la *semantics* de la
  librairie principale ;
* un DOSSIER par librairie H5P nécessaire (avec ``library.json`` + les
  ``.js`` / ``.css`` + ``semantics.json``), y compris toutes les dépendances.

Pour que Moodle (Banque de contenus H5P) installe les types de contenu à
l'import, le ``.h5p`` doit EMBARQUER ces librairies. Ce module réutilise un
cache de librairies officielles (MIT) rangé dans ``moodle_lms/h5p_libs/`` et
ne fait que réécrire ``h5p.json`` + ``content/content.json`` à chaque
génération.

Types supportés :

* ``H5P.DialogCards`` — flashcards (révision active) via
  :func:`write_dialogcards`.
* ``H5P.QuestionSet`` contenant des ``H5P.MultiChoice`` et ``H5P.TrueFalse``
  (quiz gamifié avec score) via :func:`write_questionset`.
* ``H5P.DragText`` — texte à trous (glisser-déposer les mots manquants) via
  :func:`write_dragtext`.

Le cache de librairies a été constitué à partir de paquets ``.h5p`` officiels
(dialog-cards, multiple-choice) et de dépôts github.com/h5p (question-set
1.20.31, true-false, video). Les versions ont été choisies pour former un
arbre de dépendances cohérent et sans librairie manquante.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

# Dossier contenant les librairies H5P embarquées (un sous-dossier par
# librairie, nommé ``MachineName-major.minor``).
H5P_LIBS_DIR = Path(__file__).resolve().parent / "h5p_libs"

# Librairie principale + sa version (major, minor) pour chaque type.
_DIALOGCARDS_MAIN = ("H5P.Dialogcards", 1, 7)
_QUESTIONSET_MAIN = ("H5P.QuestionSet", 1, 20)
_MULTICHOICE = ("H5P.MultiChoice", 1, 16)
_TRUEFALSE = ("H5P.TrueFalse", 1, 8)
_DRAGTEXT_MAIN = ("H5P.DragText", 1, 10)


# --------------------------------------------------------------------------
# Outils internes : lecture du cache de librairies, résolution des dépendances
# --------------------------------------------------------------------------
def _read_library_json(lib_dir: Path) -> dict:
    return json.loads((lib_dir / "library.json").read_text(encoding="utf-8"))


def _index_libraries() -> dict[str, tuple[Path, dict]]:
    """Indexe les librairies disponibles par ``machineName`` (toutes versions).

    Retourne ``{machineName: (chemin_du_dossier, library.json)}``. En cas de
    plusieurs versions présentes, garde la plus élevée.
    """
    index: dict[str, tuple[Path, dict]] = {}
    if not H5P_LIBS_DIR.is_dir():
        raise FileNotFoundError(
            f"Cache de librairies H5P introuvable : {H5P_LIBS_DIR}. "
            "Les .h5p ne peuvent pas être auto-suffisants sans lui."
        )
    for entry in sorted(H5P_LIBS_DIR.iterdir()):
        lib_json = entry / "library.json"
        if not (entry.is_dir() and lib_json.is_file()):
            continue
        data = _read_library_json(entry)
        name = data["machineName"]
        ver = (int(data["majorVersion"]), int(data["minorVersion"]))
        if name not in index or ver > (
            int(index[name][1]["majorVersion"]),
            int(index[name][1]["minorVersion"]),
        ):
            index[name] = (entry, data)
    return index


def _resolve_dependencies(
    seed_machines: list[str],
) -> dict[str, tuple[Path, dict]]:
    """Calcule la fermeture transitive des dépendances d'exécution.

    On part des librairies « graines » (la librairie principale, plus toute
    librairie référencée dans le contenu — p. ex. les sous-questions d'un
    QuestionSet) et on suit récursivement les ``preloadedDependencies``. Lève
    une erreur si une dépendance manque dans le cache (un .h5p incomplet ne
    s'importe pas dans Moodle).
    """
    index = _index_libraries()
    needed: dict[str, tuple[Path, dict]] = {}
    stack = list(seed_machines)
    missing: list[str] = []
    while stack:
        machine = stack.pop()
        if machine in needed:
            continue
        if machine not in index:
            missing.append(machine)
            continue
        lib_dir, data = index[machine]
        needed[machine] = (lib_dir, data)
        for dep in data.get("preloadedDependencies", []):
            stack.append(dep["machineName"])
    if missing:
        raise RuntimeError(
            "Librairies H5P manquantes dans le cache pour "
            f"{', '.join(seed_machines)} : "
            f"{', '.join(sorted(set(missing)))}"
        )
    return needed


def _preloaded_dependencies(needed: dict[str, tuple[Path, dict]]) -> list[dict]:
    """Construit la liste ``preloadedDependencies`` du manifeste h5p.json."""
    deps = []
    for _machine, (_lib_dir, data) in sorted(needed.items()):
        deps.append(
            {
                "machineName": data["machineName"],
                "majorVersion": str(data["majorVersion"]),
                "minorVersion": str(data["minorVersion"]),
            }
        )
    return deps


def _write_h5p_archive(
    out_path: str | Path,
    title: str,
    main_machine: str,
    content: dict,
    extra_machines: list[str] | None = None,
) -> Path:
    """Assemble l'archive .h5p finale (manifeste + contenu + librairies).

    ``extra_machines`` liste les librairies référencées dans le contenu (en
    plus de la librairie principale) afin qu'elles et leurs dépendances soient
    embarquées — indispensable pour les sous-questions d'un QuestionSet.
    """
    seeds = [main_machine] + list(extra_machines or [])
    needed = _resolve_dependencies(seeds)

    manifest = {
        "title": title,
        "language": "fr",
        "mainLibrary": main_machine,
        "embedTypes": ["div"],
        "license": "U",
        "defaultLanguage": "fr",
        "preloadedDependencies": _preloaded_dependencies(needed),
    }

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("h5p.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr(
            "content/content.json", json.dumps(content, ensure_ascii=False)
        )
        # Embarque chaque dossier de librairie nécessaire.
        for _machine, (lib_dir, _data) in needed.items():
            arc_root = lib_dir.name
            for root, _dirs, files in os.walk(lib_dir):
                for fname in files:
                    abs_path = Path(root) / fname
                    rel = abs_path.relative_to(lib_dir)
                    zf.write(abs_path, f"{arc_root}/{rel.as_posix()}")
    return path


# --------------------------------------------------------------------------
# DialogCards (flashcards)
# --------------------------------------------------------------------------
def write_dialogcards(
    title: str, cards: list[dict], out_path: str | Path
) -> Path:
    """Génère un ``.h5p`` de type *Dialog Cards* (flashcards).

    :param title: titre du contenu.
    :param cards: liste de dictionnaires ``{"front": "...", "back": "..."}``.
        ``front`` = recto (question/terme), ``back`` = verso (réponse).
    :param out_path: chemin du fichier ``.h5p`` à écrire.
    :return: le chemin du fichier généré.
    """
    dialogs = []
    for card in cards:
        front = (card.get("front") or "").strip()
        back = (card.get("back") or "").strip()
        dialogs.append(
            {
                "text": front,
                "answer": back,
                "tips": {},
            }
        )

    content = {
        "title": title,
        "mode": "normal",
        "description": "",
        "dialogs": dialogs,
        "behaviour": {
            "enableRetry": True,
            "disableBackwardsNavigation": False,
            "scaleTextNotCard": False,
            "randomCards": False,
            "maxProficiency": 5,
            "quickProgression": False,
        },
        # Libellés d'interface en français.
        "answer": "Retourner",
        "next": "Suivant",
        "prev": "Précédent",
        "retry": "Recommencer",
        "correctAnswer": "Je l'ai eu juste !",
        "incorrectAnswer": "Je me suis trompé",
        "round": "Tour @round",
        "cardsLeft": "Cartes restantes : @number",
        "nextRound": "Passer au tour @round",
        "showSummary": "Suivant",
        "summary": "Résumé",
        "summaryCardsRight": "Cartes réussies :",
        "summaryCardsWrong": "Cartes ratées :",
        "summaryCardsNotShown": "Cartes non vues :",
        "summaryOverallScore": "Score global",
        "summaryCardsCompleted": "Cartes apprises :",
        "summaryCompletedRounds": "Tours terminés :",
        "summaryAllDone": "Bravo ! Vous avez réussi les @cards cartes @max fois de suite !",
        "progressText": "Carte @card sur @total",
        "cardFrontLabel": "Recto",
        "cardBackLabel": "Verso",
        "tipButtonLabel": "Afficher l'indice",
        "audioNotSupported": "Votre navigateur ne supporte pas cet audio.",
    }

    machine, _major, _minor = _DIALOGCARDS_MAIN
    return _write_h5p_archive(out_path, title, machine, content)


# --------------------------------------------------------------------------
# QuestionSet (quiz : MultiChoice + TrueFalse)
# --------------------------------------------------------------------------
def _multichoice_params(question: dict) -> dict:
    """Construit les ``params`` d'une question H5P.MultiChoice."""
    answers = []
    for ans in question.get("answers", []):
        answers.append(
            {
                "correct": bool(ans.get("correct", False)),
                "text": f"<div>{ans.get('text', '')}</div>\n",
                "tipsAndFeedback": {
                    "tip": "",
                    "chosenFeedback": ans.get("feedback", "") or "",
                    "notChosenFeedback": "",
                },
            }
        )
    n_correct = sum(1 for a in answers if a["correct"])
    return {
        "question": f"<p>{question.get('text', '')}</p>\n",
        "answers": answers,
        "behaviour": {
            # Si plusieurs bonnes réponses : choix multiple ; sinon réponse unique.
            "type": "auto",
            "singlePoint": False,
            "randomAnswers": True,
            "enableRetry": True,
            "enableSolutionsButton": True,
            "enableCheckButton": True,
            "showSolutionsRequiresInput": True,
            "passPercentage": 100,
            "showScorePoints": True,
            "singleAnswer": n_correct <= 1,
        },
        "UI": {
            "checkAnswerButton": "Vérifier",
            "submitAnswerButton": "Soumettre",
            "showSolutionButton": "Voir la solution",
            "tryAgainButton": "Recommencer",
            "tipsLabel": "Afficher l'indice",
            "scoreBarLabel": "Vous avez @score sur @total points",
            "tipAvailable": "Indice disponible",
            "feedbackAvailable": "Retour disponible",
            "readFeedback": "Lire le retour",
            "wrongAnswer": "Mauvaise réponse",
            "correctAnswer": "Bonne réponse",
            "shouldCheck": "Aurait dû être cochée",
            "shouldNotCheck": "N'aurait pas dû être cochée",
            "noInput": "Veuillez répondre avant de voir la solution",
        },
    }


def _truefalse_params(question: dict) -> dict:
    """Construit les ``params`` d'une question H5P.TrueFalse."""
    correct = bool(question.get("answer", question.get("correct", True)))
    return {
        "question": f"<p>{question.get('text', '')}</p>\n",
        "correct": "true" if correct else "false",
        "behaviour": {
            "enableRetry": True,
            "enableSolutionsButton": True,
            "enableCheckButton": True,
            "confirmCheckDialog": False,
            "confirmRetryDialog": False,
            "autoCheck": False,
        },
        "l10n": {
            "trueText": "Vrai",
            "falseText": "Faux",
            "score": "Vous avez @score sur @total points",
            "checkAnswer": "Vérifier",
            "submitAnswer": "Soumettre",
            "showSolutionButton": "Voir la solution",
            "tryAgain": "Recommencer",
            "wrongAnswerMessage": "Mauvaise réponse",
            "correctAnswerMessage": "Bonne réponse",
            "scoreBarLabel": "Vous avez :num sur :total points",
        },
    }


def _question_subcontent(question: dict, index: int) -> dict:
    """Enveloppe une question dans la structure attendue par QuestionSet."""
    qtype = (question.get("type") or "mc").lower()
    if qtype in ("tf", "truefalse", "true-false"):
        machine, major, minor = _TRUEFALSE
        params = _truefalse_params(question)
    else:
        machine, major, minor = _MULTICHOICE
        params = _multichoice_params(question)

    return {
        "library": f"{machine} {major}.{minor}",
        "params": params,
        "subContentId": f"q-{index}",
        "metadata": {
            "contentType": machine,
            "license": "U",
            "title": question.get("text", "")[:60] or f"Question {index + 1}",
        },
    }


def write_questionset(
    title: str, questions: list[dict], out_path: str | Path
) -> Path:
    """Génère un ``.h5p`` de type *Question Set* (quiz gamifié avec score).

    :param title: titre du quiz.
    :param questions: liste de dictionnaires décrivant chaque question :

        * choix multiple : ``{"type": "mc", "text": "...",
          "answers": [{"text": ..., "correct": bool, "feedback": ...}, ...]}``
        * vrai/faux : ``{"type": "tf", "text": "...", "answer": bool}``

    :param out_path: chemin du fichier ``.h5p`` à écrire.
    :return: le chemin du fichier généré.
    """
    sub_questions = [
        _question_subcontent(q, i) for i, q in enumerate(questions)
    ]

    content = {
        "introPage": {
            "showIntroPage": True,
            "title": title,
            "introduction": "<p>Répondez aux questions suivantes.</p>\n",
            "startButtonText": "Démarrer le quiz",
        },
        "progressType": "dots",
        "passPercentage": 50,
        "questions": sub_questions,
        "disableBackwardsNavigation": False,
        "randomQuestions": False,
        "texts": {
            "prevButton": "Question précédente",
            "nextButton": "Question suivante",
            "finishButton": "Terminer",
            "submitButton": "Soumettre",
            "textualProgress": "Question : @current sur @total questions",
            "jumpToQuestion": "Question %d sur %total",
            "questionLabel": "Question",
            "readSpeakerProgress": "Question @current sur @total",
            "unansweredText": "Sans réponse",
            "answeredText": "Répondu",
            "currentQuestionText": "Question en cours",
            "navigationLabel": "Questions",
        },
        "endGame": {
            "showResultPage": True,
            "showSolutionButton": True,
            "showRetryButton": True,
            "noResultMessage": "Terminé",
            "message": "Votre résultat :",
            "scoreBarLabel": "Vous avez @finals sur @totals points",
            "overallFeedback": {
                "overallFeedback": [{"from": 0, "to": 100, "feedback": ""}]
            },
            "solutionButtonText": "Voir les solutions",
            "retryButtonText": "Recommencer",
            "finishButtonText": "Terminer",
            "showAnimations": False,
            "skippable": False,
            "skipButtonText": "Passer la vidéo",
        },
        "override": {"checkButton": True},
    }

    # Les librairies de sous-questions (et leurs dépendances) doivent être
    # embarquées en plus de QuestionSet.
    extra = []
    for q in questions:
        qtype = (q.get("type") or "mc").lower()
        if qtype in ("tf", "truefalse", "true-false"):
            extra.append(_TRUEFALSE[0])
        else:
            extra.append(_MULTICHOICE[0])

    machine, _major, _minor = _QUESTIONSET_MAIN
    return _write_h5p_archive(
        out_path, title, machine, content, extra_machines=extra
    )


# --------------------------------------------------------------------------
# DragText (texte à trous : glisser-déposer les mots manquants)
# --------------------------------------------------------------------------
def write_dragtext(
    title: str, tasks: list[str], out_path: str | Path
) -> Path:
    """Génère un ``.h5p`` de type *Drag the Words* (texte à trous).

    Chaque élément de ``tasks`` est une phrase où les mots à retrouver sont
    entourés d'astérisques selon la SYNTAXE H5P DragText. Les mots ainsi
    marqués deviennent des étiquettes à glisser dans les emplacements
    correspondants. On peut associer un indice à un mot avec ``:`` à
    l'intérieur des astérisques.

    Exemples de syntaxe (à l'intérieur de ``tasks``) ::

        "La *diversité* désigne la présence de profils variés."
        "L'*inclusion:permet à chacun de contribuer* est essentielle."

    Les phrases sont concaténées dans le champ ``textField`` en les séparant
    par des retours à la ligne (chaque phrase = une ligne de l'énoncé).

    :param title: titre du contenu.
    :param tasks: liste de phrases contenant les mots à trouver entre
        astérisques.
    :param out_path: chemin du fichier ``.h5p`` à écrire.
    :return: le chemin du fichier généré.
    """
    # Concatène les phrases : une par ligne. La syntaxe ``*mot*`` est
    # conservée telle quelle (c'est elle qui définit les zones de dépôt).
    text_field = "\n".join((t or "").strip() for t in tasks if (t or "").strip())

    content = {
        "taskDescription": "<p>Glissez les mots manquants dans les bonnes cases.</p>\n",
        "textField": text_field,
        "overallFeedback": [
            {"from": 0, "to": 100, "feedback": "Score : @score sur @total."}
        ],
        "behaviour": {
            "enableRetry": True,
            "enableSolutionsButton": True,
            "enableCheckButton": True,
            "instantFeedback": False,
        },
        "media": {"disableImageZooming": False},
        # Libellés d'interface en français.
        "checkAnswer": "Vérifier",
        "submitAnswer": "Soumettre",
        "tryAgain": "Recommencer",
        "showSolution": "Voir la solution",
        "dropZoneIndex": "Zone de dépôt @index.",
        "empty": "La zone de dépôt @index est vide.",
        "contains": "La zone de dépôt @index contient l'étiquette @draggable.",
        "ariaDraggableIndex": "@index sur @count étiquettes.",
        "tipLabel": "Afficher l'indice",
        "correctText": "Correct !",
        "incorrectText": "Incorrect !",
        "resetDropTitle": "Réinitialiser le dépôt",
        "resetDropDescription": "Voulez-vous vraiment réinitialiser cette zone de dépôt ?",
        "grabbed": "Étiquette saisie.",
        "cancelledDragging": "Déplacement annulé.",
        "correctAnswer": "Bonne réponse :",
        "feedbackHeader": "Retour",
        "scoreBarLabel": "Vous avez :num sur :total points",
        "a11yCheck": "Vérifier les réponses. Les réponses seront marquées comme correctes, incorrectes ou sans réponse.",
        "a11yShowSolution": "Afficher la solution. La tâche sera marquée avec sa solution correcte.",
        "a11yRetry": "Recommencer la tâche. Réinitialise toutes les réponses et recommence la tâche.",
    }

    machine, _major, _minor = _DRAGTEXT_MAIN
    return _write_h5p_archive(out_path, title, machine, content)
