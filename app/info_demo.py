"""Contenus de démonstration supplémentaires pour le package Information."""
from datetime import datetime, timedelta

from .models import Announcement
from .packages import CUSTOMER_RELATIONS


def extra_information(bank_id):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def at(days, hour):
        return today + timedelta(days=days, hours=hour)

    specs = [
        ("evenement", "all", "Escape game « Le coffre-fort »",
         "Résous des énigmes sur l'argent en équipe pour ouvrir le coffre ! Gratuit, sur inscription.",
         at(6, 14), "Agence Centre-ville"),
        ("intervention", "10-17", "Atelier « Mon premier budget » au collège",
         "Un conseiller vient en classe pour un atelier ludique autour de l'argent de poche.",
         at(12, 10), "Collège Jean-Moulin"),
        ("evenement", "18-24", "Job dating étudiant",
         "Rencontre des employeurs locaux qui recrutent pour des jobs étudiants et alternances.",
         at(27, 18), "Maison de l'étudiant"),
        ("intervention", "18-24", "Conférence : « Bien choisir son premier logement »",
         "Bail, dépôt de garantie, aides au logement : toutes les clés pour bien démarrer.",
         at(34, 19), "En ligne (lien envoyé aux inscrits)"),
        ("annonce", "all", "Nouveau : 13 jeux dans l'Éducation basique",
         "Mots croisés, memory, bourse junior, simulation de budget… Découvre les nouveaux jeux !", None, None),
        ("annonce", "all", "Ta banque t'accompagne pendant les vacances",
         "Pendant les vacances scolaires, tes conseillers restent joignables depuis l'application.", None, None),
    ]
    return [Announcement(bank_id=bank_id, package_code=CUSTOMER_RELATIONS, kind=kind, audience=audience, title=title,
                         body=body, event_date=event_date, location=location)
            for kind, audience, title, body, event_date, location in specs]
