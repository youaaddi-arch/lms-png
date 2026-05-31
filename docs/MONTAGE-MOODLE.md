# Guide de montage dans Moodle — Formation INC-03

Comment assembler les livrables générés pour obtenir un parcours e-learning
complet (cours + quiz + modules interactifs + gamification).

## 1. Importer le cours (contenu des 8 séances)
1. Connecte-toi en admin.
2. **Cours → Restaurer** → dépose `INC-03-cours.mbz` → **Restaurer comme nouveau cours**.
3. Choisis la catégorie « Marque Manque » → continue jusqu'au bout.

> Résultat : 8 sections (séances) remplies du contenu détaillé (~25 000 mots).

## 2. Importer les 57 questions de quiz
1. Dans le cours : **Banque de questions → Importer**.
2. Format : **« Format XML Moodle »** → dépose `INC-03-quiz.xml` → importer.
3. Crée une activité **Test** par séance (ou un test final) et **ajoute les
   questions** depuis la banque (catégorie créée à l'import).

## 3. Ajouter les modules interactifs H5P
Pour chaque fichier `.h5p` du dossier `h5p/` :
1. **Banque de contenus** (Content bank) du cours → **Téléverser** → choisis le `.h5p`.
2. Dans la séance voulue : **Ajouter une activité → H5P** → sélectionne le contenu
   depuis la banque de contenus.
3. Place dans chaque séance :
   - `INC-03-S{n}-flashcards.h5p` → révision active (active recall).
   - `INC-03-S{n}-quiz.h5p` → quiz interactif gamifié (score immédiat).

> Si Moodle affiche un avertissement de version à l'upload, accepte : les
> librairies embarquées s'installent automatiquement.

## 4. Gamification (natif Moodle, sans plugin)
### Achèvement d'activité
- Active **« Suivi d'achèvement »** dans les réglages du cours.
- Par activité : condition d'achèvement (ex. « obtenir une note » au quiz H5P).

### Badges par séance
- **Plus → Badges → Ajouter un badge** : un badge par séance (ex. « Séance 3
  validée »), critère = achèvement des activités de la séance.
- Un badge final « Formation D&I complétée » = tous les badges de séance obtenus.

### Barre de progression
- Active le **bloc « Progression »** (ou le suivi d'achèvement qui affiche le %).

## 5. Plan de révision espacée (active recall + spaced repetition)
Réutilise les **flashcards H5P** selon ce calendrier de relances :

| Échéance | Action | Outil |
|---|---|---|
| **J+1** | Revoir les flashcards des séances du jour | H5P Flashcards |
| **J+7** | Refaire le quiz de chaque séance | Test / H5P QuestionSet |
| **J+30** | Quiz final mélangé (interleaving) | Test (banque complète) |

- Programme ces relances via **rappels d'agenda** Moodle ou notifications.
- L'**interleaving** (mélanger les types) est déjà assuré par l'alternance
  flashcards / quiz / cas pratiques.

## 6. Supports de présentation (slides)
- `slides/INC-03-deck-master.pptx` : support formateur (modifiable).
- Decks par séance : à ajouter en ressource « Fichier » dans chaque section.
