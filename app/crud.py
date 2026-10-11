"""CRUD générique de l'interface banque.

Chaque type de contenu simple est décrit par une `Entity` (modèle, champs,
colonnes affichées). Les écrans liste/formulaire sont partagés.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from flask_login import current_user

from .models import (ANNOUNCEMENT_KINDS, AUDIENCES, OFFER_CATEGORIES, RESOURCE_CATEGORIES, ROLE_CLIENT,
                     Announcement, Lesson, NewsArticle, Offer, PathUnit, Podcast, Resource, TrueFalseQuestion, User)
from .packages import (BAND_CHOICES, BANK_OFFERS, CATALOG_BY_CODE, CUSTOMER_RELATIONS, EDUCATION_ADVANCED,
                       EDUCATION_BASIC, ENTREPRENEURSHIP, PARENTAL)
from .utils import is_safe_url


@dataclass
class Field:
    name: str
    label: str
    type: str = "text"  # text, textarea, url, int, bool, select, date, datetime
    required: bool = False
    choices: object = None  # liste de (valeur, libellé) ou fonction qui la retourne
    help: str = ""

    def get_choices(self):
        return self.choices() if callable(self.choices) else self.choices

    def input_value(self, obj):
        value = getattr(obj, self.name, None) if obj is not None else None
        if value is None:
            return ""
        if self.type == "datetime":
            return value.strftime("%Y-%m-%dT%H:%M")
        if self.type == "date":
            return value.isoformat()
        return str(value)

    def parse(self, form):
        """Convertit la valeur du formulaire ; lève ValueError avec un message lisible."""
        if self.type == "bool":
            return self.name in form
        raw = form.get(self.name, "").strip()
        if not raw:
            if self.required:
                raise ValueError(f"« {self.label} » est obligatoire.")
            return None
        try:
            if self.type == "int":
                return int(raw)
            if self.type == "date":
                return date.fromisoformat(raw)
            if self.type == "datetime":
                return datetime.fromisoformat(raw)
        except ValueError:
            raise ValueError(f"« {self.label} » : valeur invalide.") from None
        if self.type == "url" and not is_safe_url(raw):
            raise ValueError(f"« {self.label} » doit commencer par http:// ou https://.")
        if self.type == "select":
            values = {str(v): v for v, _ in self.get_choices()}
            if raw not in values:
                raise ValueError(f"« {self.label} » : choix invalide.")
            return values[raw]
        return raw


@dataclass
class Entity:
    slug: str
    model: type
    title: str
    singular: str
    package: str
    fields: list
    columns: list  # [(attribut, libellé)]
    order_by: object
    fixed: dict = field(default_factory=dict)  # valeurs imposées (et filtre de liste)
    row_link: tuple = None  # (libellé, endpoint, nom du paramètre) : lien supplémentaire par ligne
    back: tuple = None  # (libellé, endpoint) : retour depuis la liste et le formulaire

    def query(self):
        q = self.model.query.filter_by(bank_id=current_user.bank_id, **self.fixed)
        return q.order_by(*self.order_by())

    def get(self, obj_id):
        return self.model.query.filter_by(id=obj_id, bank_id=current_user.bank_id, **self.fixed).first()

    def cell(self, obj, name):
        value = getattr(obj, name)
        fld = next((f for f in self.fields if f.name == name), None)
        if isinstance(value, bool):
            return "Oui" if value else "Non"
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        if fld is not None and fld.type == "select" and value is not None:
            return dict((str(k), v) for k, v in fld.get_choices()).get(str(value), value)
        return "" if value is None else value

    def fill(self, obj, form):
        """Remplit `obj` depuis le formulaire. Retourne la liste des erreurs."""
        errors, values = [], {}
        for f in self.fields:
            try:
                values[f.name] = f.parse(form)
            except ValueError as e:
                errors.append(str(e))
        if not errors:
            for name, value in values.items():
                setattr(obj, name, value)
            for name, value in self.fixed.items():
                setattr(obj, name, value)
            obj.bank_id = current_user.bank_id
        return errors


def minor_client_choices():
    clients = User.query.filter_by(bank_id=current_user.bank_id, role=ROLE_CLIENT) \
        .order_by(User.last_name, User.first_name).all()
    return [(c.id, f"{c.full_name} ({c.age} ans)") for c in clients if c.is_minor]


LEVEL_CHOICES = [(0, "Découverte"), (1, "Initié"), (2, "Confirmé"), (3, "Expert")]
PATH_PACKAGE_CHOICES = [(code, CATALOG_BY_CODE[code]["name"])
                        for code in (EDUCATION_BASIC, EDUCATION_ADVANCED, ENTREPRENEURSHIP)]


def unit_choices():
    units = PathUnit.query.filter_by(bank_id=current_user.bank_id).order_by(PathUnit.package_code, PathUnit.position)
    return [(u.id, f"{CATALOG_BY_CODE[u.package_code]['name']} · {u.title}") for u in units]


def _announcement_fields(kinds, audiences, with_child=False):
    fields = [
        Field("kind", "Type", "select", required=True, choices=[k for k in ANNOUNCEMENT_KINDS if k[0] in kinds]),
        Field("title", "Titre", required=True),
        Field("body", "Message", "textarea", required=True),
        Field("audience", "Destinataires", "select", required=True,
              choices=[a for a in AUDIENCES if a[0] in audiences]),
    ]
    if with_child:
        fields.append(Field("child_id", "Enfant concerné (optionnel)", "select", choices=minor_client_choices,
                            help="Si un enfant est choisi, seuls ses parents rattachés verront l'annonce."))
    fields += [
        Field("event_date", "Date de l'évènement (optionnel)", "datetime"),
        Field("location", "Lieu (optionnel)"),
    ]
    return fields


ENTITIES = {e.slug: e for e in [
    Entity(
        slug="unites", model=PathUnit, title="Unités du parcours", singular="une unité", package=EDUCATION_BASIC,
        fields=[
            Field("package_code", "Section (package)", "select", required=True, choices=PATH_PACKAGE_CHOICES),
            Field("title", "Titre", required=True),
            Field("description", "Description", "textarea"),
            Field("band", "Public", "select", required=True, choices=BAND_CHOICES),
            Field("position", "Ordre dans la section", "int", required=True),
            Field("level", "Niveau requis", "select", required=True, choices=LEVEL_CHOICES),
            Field("active", "Unité active", "bool"),
        ],
        columns=[("package_code", "Section"), ("title", "Titre"), ("level", "Niveau"), ("band", "Public"),
                 ("position", "Ordre"), ("active", "Active")],
        order_by=lambda: (PathUnit.package_code, PathUnit.position, PathUnit.id),
        back=("Parcours", "admin.curriculum"),
    ),
    Entity(
        slug="lecons", model=Lesson, title="Leçons du parcours", singular="une leçon", package=EDUCATION_BASIC,
        fields=[
            Field("unit_id", "Unité", "select", required=True, choices=unit_choices),
            Field("title", "Titre", required=True),
            Field("position", "Ordre dans l'unité", "int", required=True),
        ],
        columns=[("unit_id", "Unité"), ("title", "Titre"), ("position", "Ordre")],
        order_by=lambda: (Lesson.unit_id, Lesson.position, Lesson.id),
        row_link=("Fiches", "admin.lesson_cards", "lesson_id"),
        back=("Parcours", "admin.curriculum"),
    ),
    Entity(
        slug="podcasts", model=Podcast, title="Podcasts", singular="un podcast", package=EDUCATION_ADVANCED,
        fields=[
            Field("title", "Titre", required=True),
            Field("description", "Description", "textarea"),
            Field("audio_url", "URL du fichier audio (mp3)", "url"),
            Field("external_url", "Lien externe (Spotify, YouTube, Deezer…)", "url"),
            Field("duration_min", "Durée (minutes)", "int"),
            Field("band", "Public", "select", required=True, choices=BAND_CHOICES),
            Field("published_at", "Date de publication", "datetime", required=True),
        ],
        columns=[("title", "Titre"), ("band", "Public"), ("published_at", "Publication")],
        order_by=lambda: (Podcast.published_at.desc(),),
    ),
    Entity(
        slug="actualites", model=NewsArticle, title="Actualités financières", singular="une actualité",
        package=EDUCATION_ADVANCED,
        fields=[
            Field("title", "Titre", required=True),
            Field("summary", "Chapô / résumé", "textarea"),
            Field("content", "Contenu", "textarea"),
            Field("image_url", "URL de l'image", "url"),
            Field("source_url", "Source", "url"),
            Field("band", "Public", "select", required=True, choices=BAND_CHOICES),
            Field("published_at", "Date de publication", "datetime", required=True),
        ],
        columns=[("title", "Titre"), ("band", "Public"), ("published_at", "Publication")],
        order_by=lambda: (NewsArticle.published_at.desc(),),
    ),
    Entity(
        slug="ressources", model=Resource, title="Ressources entrepreneuriat", singular="une ressource",
        package=ENTREPRENEURSHIP,
        fields=[
            Field("category", "Étape", "select", required=True, choices=RESOURCE_CATEGORIES),
            Field("title", "Titre", required=True),
            Field("summary", "Résumé", "textarea"),
            Field("content", "Contenu", "textarea"),
            Field("external_url", "Lien utile", "url"),
            Field("position", "Ordre d'affichage", "int", required=True),
        ],
        columns=[("category", "Étape"), ("title", "Titre"), ("position", "Ordre")],
        order_by=lambda: (Resource.category, Resource.position),
    ),
    Entity(
        slug="vrai-faux", model=TrueFalseQuestion, title="Jeu « Vrai ou Faux »", singular="une affirmation",
        package=EDUCATION_BASIC,
        fields=[
            Field("statement", "Affirmation", required=True),
            Field("is_true", "L'affirmation est vraie", "bool"),
            Field("explanation", "Explication affichée après la réponse", "textarea"),
            Field("band", "Public", "select", required=True, choices=BAND_CHOICES),
        ],
        columns=[("statement", "Affirmation"), ("is_true", "Vraie ?"), ("band", "Public")],
        order_by=lambda: (TrueFalseQuestion.id.desc(),),
    ),
    Entity(
        slug="annonces-parents", model=Announcement, title="Annonces aux parents", singular="une annonce",
        package=PARENTAL, fixed={"package_code": PARENTAL},
        fields=_announcement_fields({"annonce", "plateforme", "enfant", "evenement"},
                                    {"parents", "all", "10-17"}, with_child=True),
        columns=[("title", "Titre"), ("kind", "Type"), ("audience", "Destinataires"), ("created_at", "Créée le")],
        order_by=lambda: (Announcement.created_at.desc(),),
    ),
    Entity(
        slug="evenements", model=Announcement, title="Information : annonces & évènements", singular="une information",
        package=CUSTOMER_RELATIONS, fixed={"package_code": CUSTOMER_RELATIONS},
        fields=_announcement_fields({"annonce", "evenement", "intervention"},
                                    {"all", "clients", "10-17", "18-24", "parents"}),
        columns=[("title", "Titre"), ("kind", "Type"), ("audience", "Destinataires"), ("event_date", "Date")],
        order_by=lambda: (Announcement.created_at.desc(),),
        row_link=("Inscrits", "admin.event_registrations", "announcement_id"),
    ),
    Entity(
        slug="offres", model=Offer, title="Offres de la banque", singular="une offre", package=BANK_OFFERS,
        fields=[
            Field("category", "Catégorie", "select", required=True, choices=OFFER_CATEGORIES),
            Field("title", "Titre", required=True),
            Field("summary", "Accroche", "textarea"),
            Field("description", "Description", "textarea"),
            Field("conditions", "Conditions", "textarea"),
            Field("cta_url", "Lien « En savoir plus »", "url"),
            Field("active", "Offre active", "bool"),
        ],
        columns=[("title", "Titre"), ("category", "Catégorie"), ("active", "Active")],
        order_by=lambda: (Offer.created_at.desc(),),
    ),
]}
