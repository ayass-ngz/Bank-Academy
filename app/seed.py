"""Commandes CLI : `flask init-db`, `flask seed`, `flask create-bank`."""
import re
from datetime import date, datetime, timedelta

import click

from .curriculum import seed_curriculum
from .extensions import db
from .info_demo import extra_information
from .models import (ROLE_ADMIN, ROLE_CLIENT, ROLE_PARENT, Announcement, Bank, NewsArticle, Offer, Package, Podcast,
                     Post, PostComment, QAAnswer, QAQuestion, Quiz, QuizChoice, QuizQuestion, Resource,
                     TrueFalseQuestion, User)
from .packages import BAND_ADULT, BAND_ALL, BAND_MINOR, CUSTOMER_RELATIONS, PACKAGE_CATALOG, PARENTAL

DEMO_PASSWORD = "Demo1234!"


def create_bank(name, slug, color="#2b59c3"):
    """Crée une banque avec les 6 packages par défaut."""
    bank = Bank(name=name, slug=slug, primary_color=color)
    for position, spec in enumerate(PACKAGE_CATALOG):
        bank.packages.append(Package(code=spec["code"], name=spec["name"], description=spec["description"],
                                     icon=spec["icon"], recommended_band=spec["recommended_band"],
                                     position=position))
    db.session.add(bank)
    return bank


def years_ago(years, days=0):
    today = date.today()
    return today.replace(year=today.year - years) - timedelta(days=days)


def _user(bank, role, email, first, last, birth=None):
    user = User(bank=bank, role=role, email=email, first_name=first, last_name=last, birth_date=birth)
    user.set_password(DEMO_PASSWORD)
    if role == ROLE_CLIENT:
        user.onboarded_at = datetime.now()  # comptes de démo : test de niveau déjà passé
    db.session.add(user)
    return user


def _quiz(bank, title, publish_date, band, questions):
    quiz = Quiz(bank_id=bank.id, title=title, publish_date=publish_date, band=band)
    for pos, (text, choices, correct, explanation) in enumerate(questions):
        q = QuizQuestion(text=text, explanation=explanation, position=pos)
        q.choices = [QuizChoice(text=c, is_correct=(i == correct)) for i, c in enumerate(choices)]
        quiz.questions.append(q)
    db.session.add(quiz)


def seed_demo():
    now = datetime.now().replace(second=0, microsecond=0)
    today = date.today()
    bank = create_bank("Bank Academy", "bank-academy")
    db.session.flush()
    b = bank.id
    seed_curriculum(b)

    admin = _user(bank, ROLE_ADMIN, "admin@banque-demo.fr", "Claire", "Martin")
    lea = _user(bank, ROLE_CLIENT, "lea@exemple.fr", "Léa", "Dubois", years_ago(14, 40))
    tom = _user(bank, ROLE_CLIENT, "tom@exemple.fr", "Tom", "Bernard", years_ago(11, 100))
    yanis = _user(bank, ROLE_CLIENT, "yanis@exemple.fr", "Yanis", "Moreau", years_ago(20, 15))
    ines = _user(bank, ROLE_CLIENT, "ines@exemple.fr", "Inès", "Petit", years_ago(23, 200))
    parent = _user(bank, ROLE_PARENT, "parent@exemple.fr", "Sophie", "Dubois")
    parent.children.append(lea)

    # Un peu d'historique pour les classements
    yanis.level = 1  # « Initié » : ses 2 premières unités sont ouvertes
    for user, points, streak in [(lea, 340, 6), (tom, 210, 3), (yanis, 280, 4), (ines, 150, 2)]:
        user.points, user.current_streak, user.best_streak = points, streak, streak + 2
        user.last_active_date = today - timedelta(days=1)

    # ---- Éducation avancée
    db.session.add_all([
        Podcast(bank_id=b, title="Budget : la méthode 50/30/20 expliquée", duration_min=12, band=BAND_ALL,
                description="Besoins, envies, épargne : comment répartir ses revenus simplement.",
                external_url="https://www.lafinancepourtous.com/", published_at=now - timedelta(days=1)),
        Podcast(bank_id=b, title="Premier job : comprendre sa fiche de paie", duration_min=18, band=BAND_ADULT,
                description="Brut, net, cotisations, prélèvement à la source… on décortique tout.",
                published_at=now - timedelta(days=4)),
        Podcast(bank_id=b, title="L'argent de poche, mode d'emploi", duration_min=9, band=BAND_MINOR,
                description="Comment gérer son argent de poche et commencer à épargner.",
                published_at=now - timedelta(days=6)),
        Podcast(bank_id=b, title="Investir à 20 ans : par où commencer ?", duration_min=25, band=BAND_ADULT,
                description="Livret, assurance-vie, ETF : les bases de l'investissement et la notion de risque.",
                published_at=now - timedelta(days=9)),
    ])
    db.session.add_all([
        NewsArticle(bank_id=b, title="Inflation : ce que cela change pour ton pouvoir d'achat", band=BAND_ALL,
                    summary="Quand les prix montent, ton argent achète moins de choses. Explications.",
                    content="L'inflation mesure la hausse générale des prix.\n\nSi l'inflation est de 3 % et "
                            "que ton épargne rapporte 2 %, tu perds en réalité 1 % de pouvoir d'achat.\n\n"
                            "C'est pourquoi il est utile de comparer le rendement de son épargne à l'inflation.",
                    published_at=now - timedelta(hours=5)),
        NewsArticle(bank_id=b, title="Les taux du Livret A expliqués simplement", band=BAND_ALL,
                    summary="Comment est fixé le taux du Livret A et combien ton épargne peut rapporter.",
                    content="Le taux du Livret A est fixé par l'État sur proposition de la Banque de France.\n\n"
                            "Les intérêts sont calculés par quinzaine et versés une fois par an.",
                    published_at=now - timedelta(days=2)),
        NewsArticle(bank_id=b, title="Paiement fractionné : attention aux pièges", band=BAND_ADULT,
                    summary="Payer en 3 ou 4 fois semble indolore, mais peut vite déséquilibrer un budget.",
                    content="Le paiement fractionné est un crédit.\n\nAvant de l'utiliser, vérifie que les "
                            "échéances futures rentrent dans ton budget mensuel.",
                    published_at=now - timedelta(days=3)),
        NewsArticle(bank_id=b, title="Arnaques en ligne : les réflexes à adopter", band=BAND_ALL,
                    summary="Ta banque ne te demandera jamais tes codes par SMS ou par téléphone.",
                    content="Ne communique jamais ton code secret ni les codes reçus par SMS.\n\nEn cas de doute, "
                            "raccroche et appelle toi-même ta banque.",
                    published_at=now - timedelta(days=5)),
    ])
    _quiz(bank, "Quiz du jour : l'épargne", today, BAND_ALL, [
        ("Qu'est-ce que l'épargne ?", ["Dépenser tout son argent", "Mettre de l'argent de côté",
                                       "Emprunter de l'argent"], 1,
         "Épargner, c'est mettre de côté une partie de son argent pour plus tard."),
        ("Que sont les intérêts d'un livret d'épargne ?", ["Des frais à payer", "Une rémunération de ton épargne",
                                                            "Une amende"], 1,
         "La banque te rémunère en échange de l'argent que tu laisses sur ton livret."),
        ("Quel livret est réservé aux 12-25 ans ?", ["Le Livret Jeune", "Le PEL", "Le LDDS"], 0,
         "Le Livret Jeune est accessible de 12 à 25 ans, avec un taux au moins égal à celui du Livret A."),
    ])
    _quiz(bank, "Le budget au quotidien", today - timedelta(days=1), BAND_ALL, [
        ("Dans la règle 50/30/20, à quoi correspondent les 20 % ?", ["Aux loisirs", "À l'épargne", "Au loyer"], 1,
         "50 % pour les besoins, 30 % pour les envies et 20 % pour l'épargne."),
        ("Un découvert bancaire, c'est…", ["Un compte à solde négatif", "Un nouveau compte", "Un bonus"], 0,
         "Le découvert correspond à un solde négatif, souvent facturé par la banque (agios)."),
    ])
    _quiz(bank, "Crédit et taux d'intérêt", today - timedelta(days=2), BAND_ADULT, [
        ("Que signifie TAEG ?", ["Taux annuel effectif global", "Taxe annuelle sur l'épargne générale",
                                 "Taux appliqué en général"], 0,
         "Le TAEG inclut tous les coûts du crédit : c'est l'indicateur pour comparer les offres."),
        ("Plus la durée d'un crédit est longue…", ["Plus le coût total est faible", "Plus le coût total est élevé",
                                                   "Rien ne change"], 1,
         "Des mensualités plus petites, mais plus d'intérêts payés au total."),
    ])
    q1 = QAQuestion(bank_id=b, author=yanis, title="Faut-il ouvrir un livret dès son premier salaire ?",
                    body="Je commence mon alternance le mois prochain, est-ce que ça vaut le coup d'épargner tout de "
                         "suite même une petite somme ?")
    q1.answers = [QAAnswer(author=admin, is_official=True,
                           body="Oui ! Même 20 € par mois créent une habitude. Commence par une épargne de précaution "
                                "(3 mois de dépenses) sur un livret disponible à tout moment."),
                  QAAnswer(author=ines, body="Je fais un virement automatique le jour de la paie, ça aide beaucoup.")]
    q2 = QAQuestion(bank_id=b, author=lea, title="C'est quoi la différence entre carte de débit et de crédit ?",
                    body="Mes parents parlent des deux mais je ne comprends pas bien.")
    db.session.add_all([q1, q2])

    # ---- Entrepreneuriat
    resources = [
        ("idee", "Valider son idée en 5 étapes", "Problème, cible, solution, concurrents, premiers retours.",
         "1. Formule le problème que tu résous.\n2. Identifie qui a ce problème.\n3. Décris ta solution en une "
         "phrase.\n4. Liste les alternatives existantes.\n5. Interroge 10 personnes de ta cible."),
        ("marche", "Réaliser une étude de marché sans budget", "Questionnaires, observation, données publiques.",
         "Utilise les données publiques (INSEE), des questionnaires en ligne et l'observation de la concurrence."),
        ("business_plan", "Le Business Model Canvas", "Décrire son modèle économique sur une seule page.",
         "Le canvas comporte 9 blocs : segments clients, proposition de valeur, canaux, relation client, revenus, "
         "ressources clés, activités clés, partenaires clés et structure de coûts."),
        ("juridique", "Micro-entreprise, SAS, SARL : que choisir ?", "Comparatif des statuts pour débuter.",
         "La micro-entreprise est simple pour tester une activité seul. La SAS est flexible pour s'associer."),
        ("financement", "Financer son projet quand on est jeune", "Prêt d'honneur, subventions, financement "
         "participatif, love money.",
         "Renseigne-toi auprès des réseaux d'accompagnement, des concours étudiants et de ta banque."),
        ("lancement", "Trouver ses premiers clients", "Réseaux sociaux, bouche-à-oreille, partenariats.",
         "Commence par ton réseau proche, recueille des avis et améliore ton offre en continu."),
    ]
    db.session.add_all([Resource(bank_id=b, category=c, title=t, summary=s, content=ct, position=i)
                        for i, (c, t, s, ct) in enumerate(resources)])
    post = Post(bank_id=b, author=ines, category="associe", title="Cherche associé(e) dev pour appli anti-gaspi",
                body="Je suis en école de commerce et je cherche un profil technique pour une appli qui met en "
                     "relation commerces et étudiants pour les invendus. Intéressé(e) ?")
    post.comments = [PostComment(author=yanis, body="Super idée ! Je code en Python, on peut en parler ?")]
    db.session.add_all([post, Post(bank_id=b, author=yanis, category="conseil", title="Micro-entreprise et études ?",
                                   body="Est-ce compatible avec un statut étudiant boursier ?")])

    # ---- Éducation basique : contenu du jeu Vrai ou Faux
    statements = [
        ("Épargner, c'est mettre de l'argent de côté pour plus tard.", True, "Exactement !", BAND_ALL),
        ("Une carte bancaire permet de dépenser de l'argent sans limite.", False,
         "Chaque carte a un plafond et dépend de l'argent disponible sur le compte.", BAND_ALL),
        ("Ton code secret de carte peut être donné à un ami de confiance.", False,
         "Ton code est strictement personnel : ne le donne jamais à personne.", BAND_ALL),
        ("Les billets en euros sont les mêmes dans tous les pays de la zone euro.", True,
         "Les billets sont identiques ; seules les pièces ont une face nationale.", BAND_ALL),
        ("Un livret d'épargne te rapporte des intérêts.", True, "La banque te rémunère pour ton épargne.", BAND_ALL),
        ("Si un article est en promotion, c'est toujours une bonne affaire.", False,
         "Une promo n'est utile que si tu avais vraiment besoin de l'article.", BAND_ALL),
        ("Un budget aide à savoir où va son argent.", True, "C'est son rôle principal !", BAND_ALL),
        ("La banque garde ton argent dans un coffre à ton nom.", False,
         "Ton argent est enregistré sur ton compte : la banque le fait travailler en toute sécurité.", BAND_ALL),
        ("Il existe des pièces de 3 euros.", False, "Il existe des pièces de 1 et 2 €, pas de 3 €.", BAND_MINOR),
        ("L'argent de poche peut servir à apprendre à gérer un budget.", True,
         "C'est un excellent entraînement !", BAND_MINOR),
        ("Un découvert autorisé est gratuit.", False, "Il génère généralement des agios (intérêts).", BAND_ADULT),
        ("Le salaire net est inférieur au salaire brut.", True,
         "Le net correspond au brut moins les cotisations sociales.", BAND_ADULT),
        ("Un crédit à la consommation doit toujours être remboursé.", True,
         "Un crédit t'engage : vérifie ta capacité de remboursement.", BAND_ADULT),
        ("Le taux d'intérêt d'un crédit est le même dans toutes les banques.", False,
         "Les taux varient : compare le TAEG des offres.", BAND_ADULT),
        ("Il faut vérifier régulièrement ses relevés de compte.", True,
         "C'est le meilleur moyen de repérer une erreur ou une fraude.", BAND_ALL),
        ("Un SMS qui te demande tes codes bancaires vient forcément de ta banque.", False,
         "C'est du hameçonnage (phishing) : ta banque ne te demandera jamais tes codes.", BAND_ALL),
    ]
    db.session.add_all([TrueFalseQuestion(bank_id=b, statement=s, is_true=t, explanation=e, band=band)
                        for s, t, e, band in statements])

    # ---- Suivi parental & relation client
    db.session.add_all([
        Announcement(bank_id=b, package_code=PARENTAL, kind="plateforme", audience="parents",
                     title="Nouveau : le jeu « Besoin ou envie ? »",
                     body="Vos enfants peuvent désormais apprendre à distinguer besoins et envies grâce à un "
                          "nouveau jeu dans le package Éducation basique."),
        Announcement(bank_id=b, package_code=PARENTAL, kind="enfant", audience="parents", child_id=lea.id,
                     title="Bravo à Léa : 6 jours de série !",
                     body="Léa s'est connectée 6 jours d'affilée et progresse au classement. Félicitez-la !"),
        Announcement(bank_id=b, package_code=PARENTAL, kind="annonce", audience="10-17",
                     title="Parle de tes progrès à tes parents",
                     body="Tes parents voient ta progression depuis leur espace : montre-leur tes dernières leçons !"),
        Announcement(bank_id=b, package_code=CUSTOMER_RELATIONS, kind="evenement", audience="all",
                     title="Atelier « Gérer son premier budget »",
                     body="Un conseiller anime un atelier gratuit et ouvert à tous en agence.",
                     event_date=now + timedelta(days=10), location="Agence Centre-ville"),
        Announcement(bank_id=b, package_code=CUSTOMER_RELATIONS, kind="intervention", audience="10-17",
                     title="Intervention dans les collèges partenaires",
                     body="Nos conseillers interviennent dans les collèges partenaires pour une séance ludique "
                          "sur l'argent.", event_date=now + timedelta(days=21), location="Collèges partenaires"),
        Announcement(bank_id=b, package_code=CUSTOMER_RELATIONS, kind="evenement", audience="18-24",
                     title="Afterwork entrepreneurs",
                     body="Rencontre les jeunes entrepreneurs accompagnés par la banque.",
                     event_date=now + timedelta(days=15), location="Espace coworking"),
        Announcement(bank_id=b, package_code=CUSTOMER_RELATIONS, kind="annonce", audience="all",
                     title="Maintenance de l'application",
                     body="L'application sera indisponible dimanche de 2 h à 4 h pour maintenance."),
    ])
    db.session.add_all(extra_information(b))

    # ---- Offres
    db.session.add_all([
        Offer(bank_id=b, category="compte", title="Compte Jeune Actif",
              summary="Un compte sans frais de tenue jusqu'à 25 ans.",
              description="Compte courant, application mobile et virements instantanés inclus.",
              conditions="Réservé aux 18-24 ans. Offre soumise à conditions."),
        Offer(bank_id=b, category="epargne", title="Livret Jeune boosté",
              summary="Un taux préférentiel pour démarrer ton épargne.",
              conditions="Plafond de 1 600 €. Jusqu'à 25 ans."),
        Offer(bank_id=b, category="credit", title="Prêt étudiant",
              summary="Finance tes études avec un remboursement différé.",
              description="Commence à rembourser après la fin de tes études.",
              conditions="Sous réserve d'acceptation du dossier. Un crédit vous engage et doit être remboursé. "
                         "Vérifiez vos capacités de remboursement avant de vous engager."),
    ])
    db.session.commit()
    return bank


def register_commands(app):
    @app.cli.command("init-db")
    @click.option("--drop", is_flag=True, help="Supprime toutes les tables avant de les recréer.")
    def init_db(drop):
        """Crée les tables de la base de données."""
        if drop:
            db.drop_all()
        db.create_all()
        click.echo("Base de données initialisée.")

    @app.cli.command("seed")
    def seed():
        """Recrée la base avec une banque de démonstration."""
        db.drop_all()
        db.create_all()
        seed_demo()
        click.echo("Données de démonstration créées. Mot de passe de tous les comptes : " + DEMO_PASSWORD)
        click.echo("  Banque  : admin@banque-demo.fr")
        click.echo("  Client  : lea@exemple.fr (14 ans), tom@exemple.fr (11 ans)")
        click.echo("            yanis@exemple.fr (20 ans), ines@exemple.fr (23 ans)")
        click.echo("  Parent  : parent@exemple.fr (parent de Léa)")

    @app.cli.command("seed-curriculum")
    def seed_curriculum_command():
        """Installe le programme pédagogique par défaut dans les banques qui n'en ont pas."""
        from .models import PathUnit
        db.create_all()
        for bank in Bank.query:
            if PathUnit.query.filter_by(bank_id=bank.id).first():
                click.echo(f"{bank.name} : programme déjà présent.")
                continue
            count = seed_curriculum(bank.id)
            db.session.commit()
            click.echo(f"{bank.name} : {count} leçons installées.")

    @app.cli.command("create-bank")
    @click.argument("name")
    @click.option("--admin-email", prompt=True)
    @click.option("--admin-password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_bank_command(name, admin_email, admin_password):
        """Crée une nouvelle banque cliente et son premier administrateur."""
        db.create_all()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if Bank.query.filter_by(slug=slug).first():
            raise click.ClickException("Une banque avec ce nom existe déjà.")
        bank = create_bank(name, slug)
        db.session.flush()
        seed_curriculum(bank.id)
        admin = User(bank=bank, role=ROLE_ADMIN, email=admin_email.strip().lower(), first_name="Admin",
                     last_name=name)
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Banque « {name} » créée avec l'administrateur {admin.email}.")
