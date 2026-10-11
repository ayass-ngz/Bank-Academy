# Bank Academy

Application web responsive d'éducation financière pour les 10 – 24 ans, proposée en marque blanche aux banques.
Stack : **Flask** (Python) + **SQLAlchemy** sur un SGBD relationnel (SQLite par défaut, MySQL/MariaDB ou PostgreSQL en production) + Bootstrap 5.

## Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # puis renseigner SECRET_KEY (et DATABASE_URL si besoin)

flask --app run seed              # crée la base + une banque de démonstration
flask --app run run --debug       # http://127.0.0.1:5000
```

Comptes de démonstration (mot de passe `Demo1234!`) :

| Interface | E-mail | Remarque |
|---|---|---|
| Banque (admin) | admin@banque-demo.fr | |
| Client | lea@exemple.fr | 14 ans, rattachée au parent |
| Client | tom@exemple.fr | 11 ans |
| Client | yanis@exemple.fr | 20 ans |
| Client | ines@exemple.fr | 23 ans |
| Parent | parent@exemple.fr | parent de Léa |

Autres commandes :

```bash
flask --app run init-db [--drop]              # crée les tables (sans données)
flask --app run create-bank "Ma Banque"       # nouvelle banque cliente + 1er administrateur
flask --app run seed-curriculum               # installe le programme pédagogique dans les banques qui n'en ont pas
python -m unittest discover -s tests -t .     # tests
```

## Base de données

Par défaut : SQLite dans `instance/bank_academy.db`. Pour un autre SGBD, définir `DATABASE_URL` dans `.env` et installer le driver :

```
DATABASE_URL=mysql+pymysql://user:pwd@localhost/bank_academy        # pip install PyMySQL
DATABASE_URL=postgresql+psycopg://user:pwd@localhost/bank_academy   # pip install "psycopg[binary]"
```

Flask-Migrate est configuré pour faire évoluer le schéma (`flask --app run db init / migrate / upgrade`).

## Architecture

```
config.py                 configuration (variables d'environnement)
run.py                    point d'entrée
app/
  __init__.py             application factory, extensions, blueprints
  packages.py             catalogue des 6 packages + RÈGLES D'ÂGE (source unique)
  models.py               modèles SQLAlchemy (tables)
  games.py                jeux éducatifs (manches générées et corrigées côté serveur)
  crud.py                 CRUD générique de l'interface banque
  seed.py                 commandes CLI + données de démonstration
  utils.py                décorateurs d'accès (role_required, package_required), filtres
  blueprints/
    auth.py               connexion, inscription client / parent
    client.py             interface client (/app)
    parent.py             interface parent (/parent)
    admin.py              interface banque (/admin)
  templates/, static/
tests/                    tests unitaires (unittest)
```

### Multi-banques (marque blanche)

Chaque banque (`Bank`) possède ses utilisateurs, ses contenus et sa propre configuration des packages
(activation, nom, description, ordre, tranche d'âge recommandée) ainsi que sa couleur de marque.
Toutes les requêtes sont filtrées par `bank_id`.

### Packages et règles d'âge

| # | Package | Recommandé | 10 – 17 ans | 18 – 24 ans |
|---|---|---|---|---|
| 1 | Éducation avancée : podcasts, actualités, quiz quotidiens, Q&R | 18 – 24 | ✔ | ✔ |
| 2 | Entrepreneuriat : ressources d'incubation + communauté (posts/commentaires) | 18 – 24 | ✔ | ✔ |
| 3 | Éducation basique : 13 jeux (cartes, lettres, quiz, calcul, simulations), classements | 10 – 17 | ✔ | ✔ |
| 4 | Suivi parental : parents rattachés, annonces aux parents | 10 – 17 | ✔ | **masqué** |
| 5 | Information : évènements (inscription, ajout à l'agenda .ics), interventions, annonces | tous | ✔ | ✔ |
| 6 | Offres de la banque (+ collecte de prospects) | 18 – 24 | **interdit** | ✔ |

Les règles d'accès sont définies dans `app/packages.py` (`ACCESS_RULES`) et appliquées à deux niveaux :
le menu et le tableau de bord n'affichent pas le package, et le décorateur `package_required` renvoie une erreur 403
si l'URL est appelée directement. La banque ne peut pas lever ces règles, seulement activer/désactiver les packages.
Les contenus (podcasts, actualités, quiz, questions du jeu) peuvent en plus être ciblés sur une tranche d'âge.

### Les 3 interfaces

- **Banque** (`/admin`) : tableau de bord, packages, contenus (podcasts, actualités, quiz et questions, Q&R avec réponses
  officielles, ressources entrepreneuriat, modération de la communauté, questions du jeu Vrai/Faux, annonces parents,
  évènements, offres), prospects intéressés par les offres, comptes utilisateurs, paramètres de marque.
- **Client** (`/app`) : tableau de bord adapté à l'âge (packages recommandés, série, points, rang, quiz du jour), et les packages.
- **Parent** (`/parent`) : création du compte de ses enfants (rattachés automatiquement), suivi (points, séries, quiz, jeux),
  annonces générales et annonces ciblant son enfant, évènements de la banque.

### Parcours et programme pédagogique

La page d'accueil du client est un parcours façon Duolingo, découpé en **sections** (une par package éducatif :
Éducation basique, Éducation avancée, Entrepreneuriat), elles-mêmes composées d'**unités** et de **leçons**.

- Programme par défaut (`app/curriculum/`) : 22 unités, 66 leçons, environ 390 fiches (cours, QCM, vrai/faux, calculs),
  installé automatiquement pour chaque nouvelle banque. Certaines unités (crédit, logement, fiche de paie, investissement)
  sont réservées aux 18 – 24 ans.
- Les leçons d'une section se débloquent dans l'ordre ; une dernière unité « activités » regroupe les contenus publiés
  par la banque (jeux, quiz, actualités, podcasts, ressources) avec sa propre progression. Des coffres (+20 points)
  ponctuent chaque unité.
- Une leçon rapporte 10 points par bonne réponse la première fois ; les révisions entretiennent la série sans points.
- La banque modifie tout depuis **Parcours** : unités (ordre, public, activation), leçons et fiches (ajout, suppression, ordre).

### Création des comptes et test de niveau

- **10 – 17 ans** : un mineur ne peut pas s'inscrire seul. Le parent crée le compte depuis son espace
  (« Créer le compte de mon enfant ») ; l'enfant reçoit par e-mail son identifiant et un mot de passe provisoire.
- **18 – 24 ans** : inscription libre depuis la page d'inscription.
- **Première connexion** : choix obligatoire d'un mot de passe personnel (comptes créés par un parent ou la banque),
  puis **test de positionnement adaptatif** de 20 questions (`app/onboarding.py`) :
  - les questions sont tirées du programme pédagogique (QCM et calculs), avec la difficulté du niveau de leur unité ;
  - le niveau est estimé par une probabilité sur les 4 niveaux, mise à jour après chaque réponse (règle de Bayes) ;
  - chaque question suivante est choisie dans la difficulté la plus informative : elle monte après une bonne réponse,
    descend après une erreur. En simulation, le niveau réel est retrouvé dans environ 98 % des cas.
- **Niveaux et verrouillage** : chaque unité a un niveau requis (Découverte, Initié, Confirmé, Expert ; modifiable par la
  banque). Pour l'élève, les unités des niveaux inférieurs au sien sont acquises (révision libre), celles de son niveau
  forment son parcours, et **celles des niveaux supérieurs sont verrouillées** (y compris par l'URL). Terminer toutes les
  unités de son niveau fait passer automatiquement au niveau suivant. Le test peut être repassé (le niveau ne baisse jamais).
- **E-mails** : configurez `MAIL_SERVER` (voir `.env.example`). Sans serveur SMTP, les messages sont enregistrés dans
  `instance/outbox` et consultables sur `/dev/emails` (mode debug uniquement).

### Accueil de l'élève

À la connexion, l'élève arrive sur un accueil (`/app/`) : prochaine étape du parcours, jeu et quiz du jour,
objectifs du jour, progression par section, semaine de connexion, astuce du jour et dernières infos de la banque.
Le parcours complet est sur `/app/parcours`.

### Jeux de l'Éducation basique

| Catégorie | Jeux |
|---|---|
| Questions-réponses | Vrai ou Faux · Défi chrono (60 s) · Arnaque ou pas ? · Besoin ou envie ? |
| Jeux de cartes | Memory des notions · Plus ou moins cher ? |
| Jeux de lettres | Mots croisés (grille générée à chaque partie) · Mots mêlés · Le mot mystère |
| Calcul & estimation | Le rendu de monnaie · Le juste prix |
| Simulations | La vie en euros (budget mois par mois) · Bourse junior (diversification) |

Les jeux de questions utilisent l'écran « leçon » (`games.py`) ; les autres ont leur moteur dans `arcade.py`
et leur interface dans `static/js/arcade/`. Les solutions restent en session et le score est toujours calculé par le serveur.

### Gamification

- **Série (streak)** : +1 par jour consécutif d'activité (connexion, jeu ou quiz), remise à zéro après un jour manqué.
- **Points** : 10 par bonne réponse (quiz : +10 si sans faute, une seule tentative par quiz). Les 5 premières parties
  de chaque jeu par jour rapportent des points (`GAME_DAILY_SCORED_PLAYS`).
- **Classements** par tranche d'âge (points et séries). Les noms sont affichés sous la forme « Prénom N. ».

## Sécurité

- Mots de passe hachés (Werkzeug), sessions HttpOnly / SameSite, protection CSRF sur tous les formulaires et appels JSON.
- Échappement systématique des contenus saisis (Jinja) ; les liens saisis par la banque doivent être en http(s).
- Scores des jeux calculés côté serveur (les réponses attendues ne sont jamais envoyées au navigateur).
- Isolation des données par banque et contrôle d'accès par rôle et par âge.

## À prévoir avant la production

- Consentement parental à l'inscription des moins de 15 ans (RGPD, art. 8 / loi française) et vérification de l'e-mail.
- Réinitialisation de mot de passe par e-mail, limitation des tentatives de connexion (Flask-Limiter).
- Signalement de contenus par les utilisateurs dans la communauté.
- Hébergement des fichiers audio et images, et serveur WSGI (gunicorn / waitress) derrière HTTPS.
