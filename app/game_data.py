"""Contenus des jeux du package « Éducation basique »."""

# (libellé, est un besoin, explication)
NEEDS_WANTS = [
    ("Payer le loyer", True, "Se loger est un besoin essentiel."),
    ("Faire les courses alimentaires", True, "Se nourrir est un besoin vital."),
    ("Acheter le dernier smartphone", False, "Un téléphone fonctionnel suffit : le dernier modèle est une envie."),
    ("Payer la facture d'électricité", True, "L'énergie du logement est une dépense essentielle."),
    ("Un abonnement à une 3e plateforme de streaming", False, "Le divertissement est agréable mais pas indispensable."),
    ("Acheter des fournitures scolaires", True, "Elles sont nécessaires pour étudier."),
    ("Des baskets de marque en édition limitée", False, "Des chaussures sont utiles, l'édition limitée est une envie."),
    ("Le titre de transport pour aller en cours", True, "Se déplacer pour étudier ou travailler est un besoin."),
    ("Un skin dans un jeu vidéo", False, "C'est un achat plaisir."),
    ("Une consultation chez le médecin", True, "La santé est un besoin prioritaire."),
    ("Un repas au restaurant tous les midis", False, "Manger est un besoin, le restaurant quotidien est une envie."),
    ("Une assurance habitation", True, "Elle est souvent obligatoire et protège ton logement."),
    ("Une console de jeux", False, "C'est un loisir, donc une envie."),
    ("Un manteau chaud pour l'hiver", True, "Se protéger du froid est un besoin."),
    ("Des bonbons à la sortie du collège", False, "C'est une petite envie : à prévoir dans ton budget plaisir !"),
    ("Le forfait téléphone de base", True, "Être joignable est devenu un besoin courant."),
    ("Un week-end à la mer avec des amis", False, "Un super projet… mais une envie : il faut épargner pour !"),
    ("Des produits d'hygiène", True, "L'hygiène fait partie des besoins essentiels."),
    ("Des écouteurs sans fil haut de gamme", False, "Des écouteurs basiques suffisent : le haut de gamme est une envie."),
    ("Les frais d'inscription à l'université", True, "Ta formation est un investissement nécessaire."),
]

# Arnaque ou pas ? (expéditeur, message, est une arnaque, explication)
MESSAGES = [
    ("+33 6 12 34 56 78", "Votre colis est bloqué. Payez 1,99 € de frais de douane ici : colis-livraison-fr.info",
     True, "Faux frais de livraison : un classique de l'hameçonnage. Ne clique jamais sur ce type de lien."),
    ("Ta banque", "Votre carte a été bloquée. Communiquez votre code secret à ce numéro pour la débloquer.",
     True, "Aucune banque ne demande jamais ton code secret."),
    ("Maman", "Coucou, je rentre vers 19 h, il reste des pâtes dans le frigo.", False,
     "Un message normal d'un proche, sans lien ni demande d'argent."),
    ("Inconnu", "Félicitations ! Vous avez gagné un iPhone 15. Cliquez vite pour réclamer votre lot avant ce soir !",
     True, "Gain inattendu + urgence = arnaque."),
    ("Ta banque (appli)", "Une nouvelle connexion à votre espace a été détectée. Si ce n'est pas vous, ouvrez votre appli.",
     False, "Un message qui te renvoie vers l'appli officielle, sans lien ni demande de code, est plutôt fiable."),
    ("Ameli", "Votre carte Vitale expire. Commandez la nouvelle (frais 4,90 €) via ce lien : ameli-renouvellement.com",
     True, "La carte Vitale est gratuite et l'adresse n'est pas le site officiel ameli.fr."),
    ("Coach crypto 💰", "Investis 50 € aujourd'hui, je te garantis 500 € dans une semaine. Places limitées !",
     True, "Un gain énorme et « garanti » : c'est une arnaque à l'investissement."),
    ("Léo (classe)", "Tu peux me prêter ton compte de jeu 5 min ? Envoie-moi ton mot de passe stp.",
     True, "Même un ami ne doit jamais avoir ton mot de passe : son compte a peut-être été piraté."),
    ("Ton opérateur", "Votre facture de mars est disponible dans votre espace client.", False,
     "Information simple, sans lien suspect ni urgence."),
    ("Service client", "Bonjour, nous avons remboursé 89 € par erreur. Merci de nous renvoyer 189 € par carte cadeau.",
     True, "Les paiements par carte cadeau sont typiques des escroqueries."),
    ("Papa", "Mon téléphone est cassé, c'est mon nouveau numéro. Envoie-moi vite 300 € par virement, je t'explique après.",
     True, "L'arnaque « au faux proche » : appelle l'ancien numéro pour vérifier avant tout virement."),
    ("Club de sport", "Rappel : séance de foot samedi à 10 h au stade municipal.", False,
     "Un rappel d'activité sans demande d'argent ni de données."),
    ("Impots.gouv", "Vous avez droit à un remboursement de 248 €. Saisissez vos coordonnées bancaires ici.",
     True, "L'administration ne demande pas tes coordonnées par SMS : c'est du hameçonnage."),
    ("Bibliothèque", "Le livre que vous avez réservé est disponible jusqu'au 12.", False,
     "Message d'information classique."),
    ("Vendeur Leboncoin", "Je t'achète ton vélo ! Clique sur ce lien pour recevoir le paiement sécurisé.",
     True, "Pour recevoir de l'argent, tu n'as jamais besoin de cliquer sur un lien ni de donner ta carte."),
    ("Ta banque", "Votre conseiller vous propose un rendez-vous. Prenez rendez-vous depuis votre application.", False,
     "Pas de lien ni de demande de code : on passe par l'appli officielle."),
]

# Le juste prix (objet, prix en euros, explication)
PRICES = [
    ("Une baguette de pain", 1.2, "Le prix d'une baguette tourne autour de 1 à 1,30 € en France."),
    ("Une place de cinéma (tarif plein)", 11, "Compte environ 10 à 13 € selon les villes."),
    ("Un abonnement mensuel de streaming vidéo", 12, "Les offres standards sont souvent entre 9 et 15 € par mois."),
    ("Un forfait mobile avec 100 Go", 15, "Les forfaits sans engagement vont de 10 à 20 € environ."),
    ("Un menu dans un fast-food", 10, "Un menu coûte souvent entre 8 et 12 €."),
    ("Un jean d'une grande enseigne", 40, "Un jean courant coûte entre 30 et 60 €."),
    ("Une console de jeux de salon récente", 480, "Les consoles récentes coûtent entre 400 et 550 €."),
    ("Un loyer de studio en ville moyenne (par mois)", 500, "Un studio coûte souvent de 400 à 650 € par mois hors grandes métropoles."),
    ("Un plein d'essence (40 litres)", 72, "À environ 1,80 € le litre, 40 L coûtent autour de 72 €."),
    ("Un livre de poche", 8, "Un livre de poche coûte en général entre 7 et 10 €."),
    ("Un vélo de ville neuf d'entrée de gamme", 300, "Comptez 250 à 400 € pour un vélo de ville neuf basique."),
    ("Un ticket de métro à l'unité (Paris)", 2.15, "Le ticket coûte un peu plus de 2 €."),
    ("Un smartphone haut de gamme", 1100, "Les modèles haut de gamme dépassent souvent 1 000 €."),
    ("Une pizza à emporter", 12, "Une pizza à emporter coûte souvent entre 9 et 14 €."),
    ("Un caddie de courses pour une semaine (une personne)", 60, "Environ 50 à 80 € pour une personne seule."),
]

# Plus ou moins cher ? (objet, prix, icône)
PRICE_CARDS = [
    ("Un chewing-gum", 0.5, "bi-emoji-smile"), ("Une baguette", 1.2, "bi-basket"), ("Un ticket de bus", 1.9, "bi-bus-front"),
    ("Un café en terrasse", 2.5, "bi-cup-hot"), ("Un magazine", 5.9, "bi-newspaper"), ("Un livre de poche", 8, "bi-book"),
    ("Une place de cinéma", 11, "bi-film"), ("Un abonnement streaming", 13, "bi-tv"), ("Un t-shirt", 18, "bi-bag"),
    ("Un ballon de foot", 25, "bi-dribbble"), ("Un jeu vidéo neuf", 69, "bi-controller"), ("Un plein d'essence", 75, "bi-fuel-pump"),
    ("Une paire de baskets", 110, "bi-person-walking"), ("Une trottinette électrique", 350, "bi-scooter"),
    ("Un loyer de studio", 550, "bi-house"), ("Une console de jeux", 480, "bi-joystick"), ("Un ordinateur portable", 800, "bi-laptop"),
    ("Un smartphone haut de gamme", 1150, "bi-phone"), ("Un scooter neuf", 2400, "bi-bicycle"),
    ("Une voiture d'occasion", 8500, "bi-car-front"), ("Une année d'études en école privée", 9000, "bi-mortarboard"),
    ("Une glace", 3.5, "bi-snow"), ("Un repas au restaurant", 22, "bi-egg-fried"), ("Un casque audio", 150, "bi-headphones"),
]

# Memory : (notion, définition courte)
PAIRS = [
    ("Épargne", "Argent mis de côté"), ("Budget", "Plan de ses revenus et dépenses"), ("Intérêts", "Rémunération d'un placement"),
    ("Crédit", "Argent prêté à rembourser"), ("Salaire", "Paiement d'un travail"), ("Inflation", "Hausse générale des prix"),
    ("Découvert", "Compte à solde négatif"), ("IBAN", "Identifiant d'un compte"), ("Livret A", "Épargne sans risque"),
    ("Action", "Part d'une entreprise"), ("Impôt", "Contribution à l'État"), ("Facture", "Document à payer"),
    ("Troc", "Échange sans argent"), ("Assurance", "Protection contre un risque"), ("Bénéfice", "Recettes − dépenses"),
    ("Agios", "Intérêts du découvert"),
]

# Mots croisés / mot mystère / mots mêlés : (mot sans accent, définition)
WORDS = [
    ("EPARGNE", "Argent que l'on met de côté"), ("BUDGET", "Plan qui prévoit revenus et dépenses"),
    ("BANQUE", "Établissement qui garde ton argent"), ("CREDIT", "Somme prêtée qu'il faut rembourser"),
    ("INTERET", "Ce que rapporte un placement"), ("SALAIRE", "Ce qu'on reçoit pour son travail"),
    ("IMPOT", "Somme versée à l'État"), ("LIVRET", "Compte d'épargne, comme le A ou le Jeune"),
    ("CARTE", "Elle permet de payer en magasin"), ("CHEQUE", "Moyen de paiement en papier"),
    ("VIREMENT", "Transfert d'argent entre deux comptes"), ("EURO", "La monnaie de la France"),
    ("PRIX", "Ce que coûte un produit"), ("SOLDE", "Argent disponible sur un compte"),
    ("AGIOS", "Frais d'un découvert"), ("BOURSE", "Marché où s'échangent les actions"),
    ("ACTION", "Part du capital d'une entreprise"), ("DETTE", "Argent que l'on doit"),
    ("LOYER", "Prix mensuel d'un logement loué"), ("TAUX", "Pourcentage d'un intérêt"),
    ("MONNAIE", "Pièces et billets"), ("PIECE", "Argent en métal"), ("BILLET", "Argent en papier"),
    ("DEPENSE", "Argent qui sort"), ("REVENU", "Argent qui entre"), ("FACTURE", "Document qui indique ce qu'on doit payer"),
    ("ACHAT", "Le fait d'acheter"), ("MARGE", "Prix de vente moins coût"), ("TROC", "Échange sans argent"),
    ("PRET", "Argent avancé à quelqu'un"), ("CAISSE", "Là où l'on paie au magasin"), ("RICHESSE", "Ensemble des biens"),
    ("RABAIS", "Réduction de prix"), ("RECU", "Preuve de paiement"), ("CODE", "Secret de ta carte"),
    ("PROMO", "Prix réduit temporaire"), ("TIRELIRE", "Elle garde tes pièces à la maison"), ("ARNAQUE", "Escroquerie"),
]

# La vie en euros : évènements par tranche d'âge.
# Chaque option : (libellé, variation d'argent, variation de bien-être, leçon)
LIFE_EVENTS = {
    "10-17": {
        "income": 30, "income_label": "argent de poche", "start": 20, "fixed": 0, "fixed_label": "",
        "events": [
            ("Tes amis vont au cinéma ce samedi (11 €).", [
                ("J'y vais", -11, 2, "Se faire plaisir avec ses amis, c'est important… si c'est prévu dans le budget."),
                ("Je propose une soirée film à la maison", -3, 1, "Une alternative moins chère qui garde le plaisir partagé !"),
                ("Je reste chez moi", 0, -1, "Économiser, oui, mais s'isoler n'est pas toujours la bonne solution.")]),
            ("L'écran de ton téléphone se fissure. Réparation : 45 €.", [
                ("Je paie avec mes économies", -45, 0, "C'est exactement à ça que sert l'épargne de précaution !"),
                ("J'attends et je fais attention", 0, -1, "Possible, mais l'écran risque d'empirer."),
                ("Je demande une avance à mes parents", 0, 0, "C'est une dette : il faudra la rembourser sur ton argent de poche.")]),
            ("Une nouvelle paire de baskets à la mode coûte 90 €.", [
                ("Je l'achète tout de suite", -90, 2, "Un gros achat impulsif peut vider ton budget d'un coup."),
                ("J'épargne pour l'acheter plus tard", 0, 0, "Patience = achat réfléchi. Bien joué !"),
                ("Je cherche un modèle similaire à 40 €", -40, 1, "Comparer permet souvent de se faire plaisir pour moins cher.")]),
            ("Ta tante t'offre 20 € pour ton anniversaire.", [
                ("Je mets tout de côté", 20, 0, "Super réflexe d'épargne !"),
                ("Moitié épargne, moitié plaisir", 10, 1, "L'équilibre parfait entre plaisir et épargne."),
                ("Je dépense tout en bonbons et jeux", 0, 1, "Un plaisir rapide… qui ne laisse rien pour plus tard.")]),
            ("Un jeu mobile te propose un pack de gemmes à 9,99 €.", [
                ("Je l'achète", -10, 1, "Les petits achats in-app s'additionnent vite."),
                ("Je continue à jouer gratuitement", 0, 0, "Le jeu reste fun sans dépenser !")]),
            ("Tu peux garder le chat des voisins pendant les vacances (15 €).", [
                ("J'accepte", 15, 1, "Rendre service peut aussi rapporter un peu d'argent."),
                ("Je refuse", 0, 0, "Pas grave, mais c'était une belle occasion de gagner un peu d'argent.")]),
            ("Sortie scolaire : il faut 12 € pour la journée au parc.", [
                ("Je paie avec mon argent de poche", -12, 2, "Une dépense prévue et utile."),
                ("Je n'y vais pas", 0, -2, "Une économie… qui te prive d'un bon moment avec ta classe.")]),
            ("Tu vois une promo : 3 paquets de chips pour le prix de 2 (4 €).", [
                ("J'en profite", -4, 1, "Une promo n'est utile que si tu en avais vraiment envie."),
                ("Je n'en ai pas besoin", 0, 0, "Bien vu : une promo n'est pas une raison d'acheter.")]),
            ("Tu veux offrir un cadeau à ton meilleur ami (budget libre).", [
                ("Un cadeau à 25 €", -25, 2, "Un beau geste, à prévoir dans ton budget."),
                ("Un cadeau fait main", -3, 2, "Original, personnel et économique !"),
                ("Rien du tout", 0, -2, "Partager compte aussi pour se sentir bien.")]),
            ("Tu peux vendre des jeux que tu n'utilises plus.", [
                ("Je les vends 25 € (avec mes parents)", 25, 0, "Donner une seconde vie aux objets rapporte de l'argent."),
                ("Je les garde", 0, 0, "Ils prennent la poussière… mais c'est ton choix.")]),
        ],
    },
    "18-24": {
        "income": 1400, "income_label": "salaire net", "start": 300, "fixed": 650,
        "fixed_label": "transport, forfait, assurances et dépenses courantes",
        "events": [
            ("Ton loyer et tes charges de ce mois : 620 €.", [
                ("Je paie à temps", -620, 0, "Le logement est une dépense prioritaire."),
                ("Je paie en retard", -650, -2, "Les retards entraînent des frais et des tensions avec le propriétaire.")]),
            ("Tes amis organisent un week-end à 180 €.", [
                ("J'y vais", -180, 3, "Un super souvenir, si ton budget le permet."),
                ("Je propose une version moins chère", -60, 2, "Bonne idée : le plaisir sans exploser le budget."),
                ("Je refuse", 0, -2, "Prudent, mais attention à ne pas tout sacrifier.")]),
            ("Ta voiture tombe en panne : 400 € de réparation.", [
                ("Je paie avec mon épargne", -400, 0, "L'épargne de précaution évite de s'endetter."),
                ("Je paie en 4 fois", -110, -1, "Un paiement fractionné est un crédit : à utiliser avec prudence."),
                ("Je prends les transports", -40, -1, "Une solution temporaire économique.")]),
            ("Ta banque te propose un crédit renouvelable de 2 000 € « disponible tout de suite ».", [
                ("Je l'accepte pour me faire plaisir", 2000, 2, "Attention : ce crédit coûte cher et doit être remboursé !"),
                ("Je refuse", 0, 0, "Bonne décision : un crédit doit répondre à un vrai besoin.")]),
            ("Une prime de 300 € arrive sur ton compte.", [
                ("Je la place sur mon livret", 300, 0, "Ton épargne grandit !"),
                ("Je m'offre un nouveau téléphone", -600, 2, "Tu dépenses plus que la prime : ton budget en souffre."),
                ("Moitié épargne, moitié plaisir", 150, 1, "Un bon équilibre.")]),
            ("Abonnements : tu paies 4 plateformes de streaming (45 €/mois).", [
                ("Je garde tout", -45, 1, "Les abonnements cumulés pèsent lourd sur l'année."),
                ("J'en garde une seule", -12, 0, "Tu économises plus de 30 € par mois !")]),
            ("Courses du mois.", [
                ("Je fais une liste et je compare", -220, 0, "Une liste limite les achats impulsifs."),
                ("Je commande souvent en livraison", -380, 1, "Pratique, mais nettement plus cher.")]),
            ("Une formation en ligne utile pour ton métier coûte 150 €.", [
                ("Je me forme", -150, 1, "Investir dans ses compétences peut augmenter ses revenus futurs."),
                ("Je reporte", 0, 0, "Pas de dépense, mais pas de progression non plus.")]),
            ("Un influenceur vante un placement crypto « garanti +30 % par mois ».", [
                ("J'investis 500 €", -500, -1, "C'était une arnaque : les rendements garantis élevés n'existent pas."),
                ("Je vérifie sur la liste noire de l'AMF", 0, 0, "Excellent réflexe !")]),
            ("Ton assurance habitation est à renouveler (120 €/an).", [
                ("Je compare plusieurs offres", -90, 0, "Comparer fait souvent économiser."),
                ("Je ne m'assure pas", 0, -1, "Risqué, et obligatoire pour un locataire !")]),
        ],
    },
}

# Bourse junior : actifs fictifs (nom, secteur, icône, volatilité)
STOCK_ASSETS = [
    ("Livret", "Épargne sans risque", "bi-safe", 0.0),
    ("SolarCo", "Énergie solaire", "bi-sun", 0.12),
    ("MiamBio", "Alimentation bio", "bi-basket", 0.05),
    ("PixelPlay", "Jeux vidéo", "bi-controller", 0.2),
]
# Actualités : (texte, actif concerné (index), effet moyen)
STOCK_NEWS = [
    ("Une canicule record fait exploser la production des panneaux solaires.", 1, 0.12),
    ("Le prix des matières premières agricoles s'envole.", 2, -0.06),
    ("Un jeu très attendu est reporté d'un an.", 3, -0.18),
    ("Le gouvernement annonce des aides pour l'énergie verte.", 1, 0.10),
    ("Un nouveau jeu de PixelPlay bat des records de ventes.", 3, 0.22),
    ("Les consommateurs achètent de plus en plus bio.", 2, 0.07),
    ("Une panne géante touche les serveurs de jeux en ligne.", 3, -0.12),
    ("Un rapport alerte sur la fiabilité de certains panneaux solaires.", 1, -0.10),
    ("Une chaîne de supermarchés référence tous les produits MiamBio.", 2, 0.09),
    ("Les marchés sont calmes cette période.", None, 0.0),
]

TIPS = [
    "Attends 48 heures avant un achat plaisir : souvent, l'envie passe.",
    "Mets de côté une partie de ton argent dès que tu le reçois, pas à la fin du mois.",
    "Le prix au kilo permet de comparer deux produits de tailles différentes.",
    "Ta banque ne te demandera jamais ton code secret, ni par SMS ni par téléphone.",
    "Un objectif d'épargne précis (quoi, combien, quand) est plus facile à atteindre.",
    "Les petites dépenses quotidiennes s'additionnent : 2 € par jour, c'est 60 € par mois.",
    "Le Livret A peut être ouvert à tout âge, et ses intérêts ne sont pas imposés.",
    "Une promotion n'est une bonne affaire que si tu avais besoin de l'objet.",
    "Avec les intérêts composés, commencer tôt compte plus que placer beaucoup.",
    "Un paiement en 3 ou 4 fois est un crédit : il engage ton budget des mois suivants.",
    "Diversifier ses placements limite les risques : ne mets pas tous tes œufs dans le même panier.",
    "Vérifie régulièrement tes relevés de compte pour repérer une erreur ou une fraude.",
    "Un rendement élevé et garanti, ça n'existe pas : méfie-toi des promesses trop belles.",
    "Faire une liste de courses évite les achats impulsifs.",
    "Note tes dépenses pendant un mois : tu découvriras où part vraiment ton argent.",
    "Le TAEG est le chiffre à comparer entre deux crédits : il inclut tous les frais.",
    "Revendre ce que tu n'utilises plus, c'est bon pour ton budget et pour la planète.",
    "L'épargne de précaution, c'est 3 à 6 mois de dépenses mis de côté pour les imprévus.",
]
