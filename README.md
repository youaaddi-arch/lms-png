# lms-png — Création automatisée de formations Moodle

Outil en ligne de commande qui transforme un **programme de formation**
(PDF / Word / texte) en **cours Moodle**, via l'**API Web Services** de Moodle
(authentification par **token**, jamais par mot de passe).

> Flux : `Document (PDF/Word)` → structure analysée → `Cours Moodle` (catégorie + cours + sections).

---

## 1. Sécurité d'abord 🔐

- **Ne mets jamais ton mot de passe Moodle dans le code ou un fichier.**
  L'outil utilise un **jeton de service web** révocable.
- Le fichier `.env` (qui contient le token) est **ignoré par git** (`.gitignore`).
- Si tu as partagé ton mot de passe quelque part, **change-le**.

## 2. Pré-requis côté Moodle

À faire une fois par l'administrateur du site Moodle :

1. **Activer les services web**
   `Administration du site > Fonctionnalités avancées` → cocher *Activer les services web*.
2. **Activer le protocole REST**
   `Administration du site > Serveur > Services web > Gérer les protocoles` → activer *REST*.
3. **Créer/activer un service** avec les fonctions nécessaires :
   - `core_webservice_get_site_info`
   - `core_course_get_categories`
   - `core_course_create_categories`
   - `core_course_create_courses`
   - `local_wsmanagesections_update_sections` *(voir ci-dessous)*
4. **Générer un token**
   `Administration du site > Serveur > Services web > Gérer les jetons`.
5. Vérifier que l'utilisateur du token a les **droits** de créer cours/catégories.

### Plugin requis pour remplir les sections

L'API « core » de Moodle crée les cours et catégories mais **ne remplit pas le
contenu des sections**. On utilise pour cela le plugin gratuit
[`local_wsmanagesections`](https://moodle.org/plugins/local_wsmanagesections).
S'il n'est pas installé, l'outil **crée quand même le cours** mais affiche un
avertissement pour chaque section non remplie.

## 3. Installation locale

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # puis renseigne MOODLE_URL et MOODLE_TOKEN
```

## 4. Utilisation

```bash
# Tester la connexion à Moodle
python -m moodle_lms.cli check

# Prévisualiser la structure d'un programme SANS rien créer
python -m moodle_lms.cli preview programmes/mon-programme.pdf

# Simuler la création (aucune écriture sur Moodle)
python -m moodle_lms.cli build programmes/mon-programme.pdf --dry-run

# Créer réellement le cours dans la catégorie "Marque Manque"
python -m moodle_lms.cli build programmes/mon-programme.pdf --category "Marque Manque"
```

Options utiles :
- `--title "Titre exact"` : force le titre du cours (sinon = 1re ligne du doc).
- `--category "Nom"` : catégorie cible (créée si absente). Défaut : `Marque Manque`.

## 5. Comment le document est analysé

Heuristique simple et prévisible (relis toujours avec `preview` avant `build`) :

| Élément du document | Devient dans Moodle |
|---|---|
| 1re ligne non vide | Titre du cours |
| `Module X` / `Chapitre X` / `1.2 Titre` / TITRE EN MAJUSCULES | Une nouvelle **section** |
| Lignes `-`, `*`, `•`, `1.` | Puces dans la section |
| Autres paragraphes | Texte de la section / résumé du cours |

Un exemple est fourni : [`programmes/exemple-programme.txt`](programmes/exemple-programme.txt).

## 6. Structure du projet

```
moodle_lms/
  client.py            Client REST des Web Services Moodle (par token)
  models.py            Modèles Program / Module
  document_parser.py   PDF / DOCX / TXT  ->  Program
  course_builder.py    Program  ->  cours Moodle
  cli.py               Ligne de commande (check / preview / build)
programmes/            Tes documents de programmes (PDF/Word ignorés par git)
```

## 7. Donne-moi un programme

Envoie-moi un programme (PDF/Word) et je :
1. l'ajoute dans `programmes/`,
2. vérifie la structure avec `preview`,
3. l'adapte si besoin,
4. crée le cours sur ton Moodle (ou te donne la commande à lancer si tu
   préfères garder le token sur ta machine).
