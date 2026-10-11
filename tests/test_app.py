import unittest
from datetime import date, timedelta

from app import create_app
from app.extensions import db
from app.models import GameScore, OfferInterest, QuizAttempt, User
from app.packages import BANK_OFFERS, PARENTAL, is_accessible
from app.seed import DEMO_PASSWORD, seed_demo
from config import TestConfig
from werkzeug.security import generate_password_hash

import app.models

# Hachage rapide pour les tests uniquement (scrypt est volontairement lent)
app.models.generate_password_hash = lambda pwd: generate_password_hash(pwd, method="pbkdf2:sha256:1000")


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_demo()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email):
        return self.client.post("/connexion", data={"email": email, "password": DEMO_PASSWORD})

    def user(self, email):
        return User.query.filter_by(email=email).one()


class AgeRulesTest(BaseCase):
    def test_rules(self):
        self.assertFalse(is_accessible(BANK_OFFERS, "10-17"))
        self.assertTrue(is_accessible(BANK_OFFERS, "18-24"))
        self.assertTrue(is_accessible(PARENTAL, "10-17"))
        self.assertFalse(is_accessible(PARENTAL, "18-24"))

    def test_minor_cannot_access_offers(self):
        self.login("lea@exemple.fr")
        dashboard = self.client.get("/app/").get_data(as_text=True)
        self.assertNotIn("Offres de la banque", dashboard)
        self.assertIn("Suivi parental", dashboard)
        self.assertEqual(self.client.get("/app/offres").status_code, 403)
        self.assertEqual(self.client.get("/app/suivi-parental").status_code, 200)

    def test_adult_has_no_parental_package(self):
        self.login("yanis@exemple.fr")
        dashboard = self.client.get("/app/").get_data(as_text=True)
        self.assertIn("Offres de la banque", dashboard)
        self.assertNotIn("Suivi parental", dashboard)
        self.assertEqual(self.client.get("/app/suivi-parental").status_code, 403)
        self.assertEqual(self.client.get("/app/offres").status_code, 200)

    def test_disabled_package_is_hidden(self):
        bank = self.user("admin@banque-demo.fr").bank
        bank.package("entrepreneurship").enabled = False
        db.session.commit()
        self.login("yanis@exemple.fr")
        self.assertEqual(self.client.get("/app/entrepreneuriat").status_code, 404)

    def test_registration_age_limits(self):
        bank_id = self.user("admin@banque-demo.fr").bank_id
        base = {"bank_id": bank_id, "first_name": "A", "last_name": "B", "password": "motdepasse",
                "confirm": "motdepasse"}
        too_young = date.today() - timedelta(days=365 * 9)
        r = self.client.post("/inscription", data={**base, "email": "kid@x.fr", "birth_date": too_young.isoformat()})
        self.assertIn("réservée aux 10", r.get_data(as_text=True))
        # Un mineur ne peut pas créer son compte seul
        minor = date.today() - timedelta(days=365 * 15)
        r = self.client.post("/inscription", data={**base, "email": "teen@x.fr", "birth_date": minor.isoformat()})
        self.assertIn("demande à ton parent", r.get_data(as_text=True))
        self.assertIsNone(User.query.filter_by(email="teen@x.fr").first())
        adult = date.today() - timedelta(days=365 * 20)
        r = self.client.post("/inscription", data={**base, "email": "adult@x.fr", "birth_date": adult.isoformat()})
        self.assertEqual(r.status_code, 302)
        # puis passage obligé par le test de niveau
        self.assertTrue(self.client.get("/app/").headers["Location"].endswith("/app/bienvenue"))


class RolesTest(BaseCase):
    def test_interfaces_are_separated(self):
        self.login("lea@exemple.fr")
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertEqual(self.client.get("/parent/").status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get("/app/").status_code, 302)


class FeaturesTest(BaseCase):
    def test_all_client_pages_render(self):
        for email in ("lea@exemple.fr", "yanis@exemple.fr"):
            self.login(email)
            pages = ["/app/", "/app/profil", "/app/education-avancee", "/app/education-avancee/podcasts",
                     "/app/education-avancee/actualites", "/app/education-avancee/quiz",
                     "/app/education-avancee/questions", "/app/entrepreneuriat", "/app/entrepreneuriat/communaute",
                     "/app/education-basique", "/app/information", "/app/parcours"]
            for page in pages:
                self.assertEqual(self.client.get(page).status_code, 200, f"{email} {page}")
            self.client.post("/deconnexion")

    def test_quiz_scoring(self):
        self.login("tom@exemple.fr")
        tom = self.user("tom@exemple.fr")
        before = tom.points
        from app.models import Quiz
        quiz = Quiz.query.filter_by(title="Quiz du jour : l'épargne").one()
        answers = {f"q{q.id}": next(c.id for c in q.choices if c.is_correct) for q in quiz.questions}
        self.client.post(f"/app/education-avancee/quiz/{quiz.id}", data=answers)
        attempt = QuizAttempt.query.filter_by(user_id=tom.id, quiz_id=quiz.id).one()
        self.assertEqual(attempt.score, attempt.total)
        db.session.refresh(tom)
        self.assertEqual(tom.points, before + attempt.total * 10 + 10)
        # Une seule tentative comptabilisée
        self.client.post(f"/app/education-avancee/quiz/{quiz.id}", data=answers)
        self.assertEqual(QuizAttempt.query.filter_by(user_id=tom.id).count(), 1)

    def test_adult_cannot_take_minor_only_content(self):
        from app.models import Quiz
        self.login("lea@exemple.fr")
        adult_quiz = Quiz.query.filter_by(band="18-24").first()
        self.assertEqual(self.client.get(f"/app/education-avancee/quiz/{adult_quiz.id}").status_code, 404)

    def test_game_is_scored_server_side(self):
        self.login("tom@exemple.fr")
        self.assertEqual(self.client.get("/app/education-basique/jeux/rendu_monnaie").status_code, 200)
        with self.client.session_transaction() as sess:
            secret = sess["game"]["secret"]
        for i, (price, paid) in enumerate(secret):
            answer = f"{(paid - price) / 100:.2f}".replace(".", ",") if i % 2 == 0 else "0"
            r = self.client.post("/app/education-basique/jeux/rendu_monnaie/verifier", json={"index": i, "answer": answer})
            self.assertEqual(r.get_json()["correct"], i % 2 == 0)
        # Changer d'avis après coup ne change pas le résultat
        price, paid = secret[1]
        r = self.client.post("/app/education-basique/jeux/rendu_monnaie/verifier",
                             json={"index": 1, "answer": str((paid - price) / 100)})
        self.assertFalse(r.get_json()["correct"])
        result = self.client.post("/app/education-basique/jeux/rendu_monnaie/terminer").get_json()
        self.assertEqual(result["correct"], len(secret) // 2)
        self.assertEqual(GameScore.query.count(), 1)

    def test_true_false_game(self):
        self.login("lea@exemple.fr")
        self.client.get("/app/education-basique/jeux/vrai_faux")
        r = self.client.post("/app/education-basique/jeux/vrai_faux/verifier", json={"index": 0, "answer": 0})
        self.assertIn("correct", r.get_json())

    def test_offer_interest(self):
        self.login("yanis@exemple.fr")
        from app.models import Offer
        offer = Offer.query.first()
        self.client.post(f"/app/offres/{offer.id}/interet", data={"message": "Bonjour"})
        self.assertEqual(OfferInterest.query.count(), 1)

    def test_post_and_comment(self):
        self.login("yanis@exemple.fr")
        r = self.client.post("/app/entrepreneuriat/communaute",
                             data={"title": "Mon idée", "body": "Détails", "category": "idee"})
        self.assertEqual(r.status_code, 302)
        r = self.client.post(r.headers["Location"], data={"body": "<script>alert(1)</script>"})
        page = self.client.get(r.headers["Location"].split("#")[0]).get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


class ParentTest(BaseCase):
    def test_parent_dashboard_and_child(self):
        self.login("parent@exemple.fr")
        page = self.client.get("/parent/").get_data(as_text=True)
        self.assertIn("Léa Dubois", page)
        self.assertIn("Bravo à Léa", page)
        lea = self.user("lea@exemple.fr")
        self.assertEqual(self.client.get(f"/parent/enfants/{lea.id}").status_code, 200)
        tom = self.user("tom@exemple.fr")
        self.assertEqual(self.client.get(f"/parent/enfants/{tom.id}").status_code, 404)

    def test_no_link_code_anymore(self):
        # Les enfants sont rattachés à la création de leur compte par le parent : plus de code de liaison
        self.login("parent@exemple.fr")
        self.assertEqual(self.client.post("/parent/enfants/lier", data={"code": "ABC"}).status_code, 404)
        self.assertNotIn("code de liaison", self.client.get("/parent/").get_data(as_text=True).lower())


class AdminTest(BaseCase):
    def setUp(self):
        super().setUp()
        self.login("admin@banque-demo.fr")

    def test_admin_pages_render(self):
        from app.crud import ENTITIES
        pages = ["/admin/", "/admin/packages", "/admin/quiz", "/admin/questions", "/admin/communaute",
                 "/admin/offres/interets", "/admin/utilisateurs", "/admin/utilisateurs/nouveau", "/admin/parametres"]
        pages += [f"/admin/contenu/{slug}" for slug in ENTITIES] + [f"/admin/contenu/{slug}/nouveau" for slug in ENTITIES]
        for page in pages:
            self.assertEqual(self.client.get(page).status_code, 200, page)

    def test_crud_create_and_url_validation(self):
        r = self.client.post("/admin/contenu/podcasts/nouveau", data={
            "title": "Nouveau", "band": "all", "published_at": "2026-01-01T10:00",
            "external_url": "javascript:alert(1)"})
        self.assertIn("doit commencer par http", r.get_data(as_text=True))
        r = self.client.post("/admin/contenu/podcasts/nouveau", data={
            "title": "Nouveau", "band": "all", "published_at": "2026-01-01T10:00",
            "external_url": "https://exemple.fr"})
        self.assertEqual(r.status_code, 302)

    def test_package_toggle(self):
        bank = self.user("admin@banque-demo.fr").bank
        data = {}
        for p in bank.packages:
            data[f"p{p.id}_name"] = p.name
            data[f"p{p.id}_band"] = p.recommended_band
            data[f"p{p.id}_position"] = p.position
            if p.code != "education_basic":
                data[f"p{p.id}_enabled"] = "on"
        self.client.post("/admin/packages", data=data)
        db.session.expire_all()
        self.assertFalse(bank.package("education_basic").enabled)
        self.assertTrue(bank.package("bank_offers").enabled)

    def test_quiz_builder(self):
        r = self.client.post("/admin/quiz", data={"title": "Test", "publish_date": date.today().isoformat(),
                                                  "band": "all"})
        quiz_url = r.headers["Location"]
        self.client.post(quiz_url + "/questions", data={"text": "2+2 ?", "choice_1": "3", "choice_2": "4",
                                                       "correct": "2"})
        from app.models import Quiz
        quiz = Quiz.query.filter_by(title="Test").one()
        self.assertEqual(len(quiz.questions), 1)
        self.assertTrue(quiz.questions[0].choices[1].is_correct)


class PathTest(BaseCase):
    def sections(self, email):
        from app.path import build_path
        with self.app.test_request_context():
            return build_path(self.user(email))

    def section(self, email, code):
        return next(s for s in self.sections(email) if s.package.code == code)

    def test_sections_follow_age(self):
        minor = [s.package.code for s in self.sections("tom@exemple.fr")]
        adult = [s.package.code for s in self.sections("yanis@exemple.fr")]
        self.assertEqual(minor[0], "education_basic")  # recommandé 10-17 en premier
        self.assertEqual(adult[0], "education_advanced")
        self.assertEqual(set(minor), set(adult))

    def test_curriculum_is_seeded_and_filtered_by_age(self):
        minor = self.section("tom@exemple.fr", "education_advanced")
        adult = self.section("yanis@exemple.fr", "education_advanced")
        # Les unités réservées aux 18-24 ans (crédit, logement…) ne sont pas proposées aux mineurs
        self.assertLess(len(minor.units), len(adult.units))
        self.assertNotIn("Le crédit", [u.title for u in minor.units])
        self.assertIn("Le crédit", [u.title for u in adult.units])
        basic = self.section("tom@exemple.fr", "education_basic")
        self.assertGreaterEqual(len(basic.units), 8)
        self.assertEqual(basic.units[-1].title, "Jeux & défis")

    def test_lessons_unlock_in_order(self):
        units = self.section("tom@exemple.fr", "education_basic").units
        states = [n.state for u in units[:-1] for n in u.nodes]
        self.assertEqual(states[0], "current")
        self.assertTrue(all(s == "locked" for s in states[1:]))
        # L'unité « Jeux & défis » a sa propre progression
        self.assertEqual(units[-1].nodes[0].state, "current")

    def play_lesson(self, lesson_id, all_correct=True):
        from app.models import LessonCard
        self.client.get(f"/app/lecons/{lesson_id}")
        with self.client.session_transaction() as sess:
            secret = sess["game"]["secret"]
        for i, card_id in enumerate(secret):
            if card_id is None:
                continue
            card = db.session.get(LessonCard, card_id)
            answer = card.answer if all_correct else "999"
            if card.kind == "choice" and not all_correct:
                answer = (int(card.answer) + 1) % len(card.choices)
            r = self.client.post(f"/app/lecons/{lesson_id}/verifier", json={"index": i, "answer": answer})
            self.assertEqual(r.get_json()["correct"], all_correct)
        return self.client.post(f"/app/lecons/{lesson_id}/terminer").get_json()

    def test_lesson_flow_points_and_unlock(self):
        self.login("tom@exemple.fr")
        unit = self.section("tom@exemple.fr", "education_basic").units[0]
        first, second = unit.nodes[0], unit.nodes[1]
        first_id, second_id = int(first.key.split(":")[1]), int(second.key.split(":")[1])
        # Leçon verrouillée : redirection
        self.assertEqual(self.client.get(f"/app/lecons/{second_id}").status_code, 302)
        before = self.user("tom@exemple.fr").points
        result = self.play_lesson(first_id)
        self.assertEqual(result["correct"], result["total"])
        self.assertEqual(result["points"], result["total"] * 10)
        db.session.expire_all()
        self.assertEqual(self.user("tom@exemple.fr").points, before + result["points"])
        # Révision : pas de points en plus
        again = self.play_lesson(first_id, all_correct=False)
        self.assertEqual(again["points"], 0)
        self.assertEqual(again["correct"], 0)
        # La leçon suivante est débloquée
        nodes = self.section("tom@exemple.fr", "education_basic").units[0].nodes
        self.assertEqual(nodes[0].state, "done")
        self.assertEqual(nodes[1].state, "current")
        self.assertEqual(self.client.get(f"/app/lecons/{second_id}").status_code, 200)

    def test_theory_rounds_cannot_be_checked(self):
        self.login("tom@exemple.fr")
        lesson_id = int(self.section("tom@exemple.fr", "education_basic").units[0].nodes[0].key.split(":")[1])
        self.client.get(f"/app/lecons/{lesson_id}")
        with self.client.session_transaction() as sess:
            info_index = sess["game"]["secret"].index(None)
        r = self.client.post(f"/app/lecons/{lesson_id}/verifier", json={"index": info_index, "answer": 0})
        self.assertEqual(r.status_code, 400)

    def test_minor_cannot_open_adult_lesson(self):
        from app.models import PathUnit
        adult_unit = PathUnit.query.filter_by(band="18-24").first()
        self.login("tom@exemple.fr")
        self.assertEqual(self.client.get(f"/app/lecons/{adult_unit.lessons[0].id}").status_code, 404)

    def test_chest_after_games(self):
        self.login("tom@exemple.fr")
        games_unit = self.section("tom@exemple.fr", "education_basic").units[-1]
        chest = next(n for n in games_unit.nodes if n.kind == "chest")
        ref = chest.key.split(":", 1)[1]
        before = self.user("tom@exemple.fr").points
        self.client.post(f"/app/parcours/coffre/{ref}")  # verrouillé : rien
        self.assertEqual(self.user("tom@exemple.fr").points, before)
        before_chest = games_unit.nodes[:games_unit.nodes.index(chest)]
        for node in before_chest:  # on joue chaque jeu placé avant le palier
            code = node.key.split(":", 1)[1]
            self.client.get(f"/app/education-basique/jeux/{code}")
            self.client.post(f"/app/education-basique/jeux/{code}/terminer", json={})
        db.session.expire_all()
        before = self.user("tom@exemple.fr").points
        self.client.post(f"/app/parcours/coffre/{ref}")
        self.client.post(f"/app/parcours/coffre/{ref}")  # une seule fois
        db.session.expire_all()
        self.assertEqual(self.user("tom@exemple.fr").points, before + 20)

    def test_reading_completes_step_once(self):
        from app.models import Completion, NewsArticle
        from app.path import find_node
        self.login("yanis@exemple.fr")
        article = NewsArticle.query.first()
        self.client.get(f"/app/education-avancee/actualites/{article.id}")
        self.client.get(f"/app/education-avancee/actualites/{article.id}")
        self.assertEqual(Completion.query.filter_by(kind="news").count(), 1)
        self.assertTrue(find_node(self.sections("yanis@exemple.fr"), f"news:{article.id}").done)

    def test_pages_with_path_render(self):
        self.login("lea@exemple.fr")
        page = self.client.get("/app/parcours").get_data(as_text=True)
        self.assertIn("track-step", page)
        self.assertIn("section-tab", page)
        self.assertIn("Objectifs du jour", page)
        self.assertEqual(self.client.get("/app/parcours?section=entrepreneurship").status_code, 200)
        self.client.post("/deconnexion")
        self.login("parent@exemple.fr")
        lea = self.user("lea@exemple.fr")
        self.assertIn("Parcours de Léa", self.client.get(f"/parent/enfants/{lea.id}").get_data(as_text=True))


class CurriculumAdminTest(BaseCase):
    def setUp(self):
        super().setUp()
        self.login("admin@banque-demo.fr")

    def test_pages_render(self):
        from app.models import Lesson
        lesson = Lesson.query.first()
        for page in ("/admin/parcours", f"/admin/parcours/lecons/{lesson.id}", "/admin/contenu/unites",
                     "/admin/contenu/lecons", f"/admin/contenu/lecons/nouveau?unit_id={lesson.unit_id}"):
            self.assertEqual(self.client.get(page).status_code, 200, page)

    def test_add_cards(self):
        from app.models import Lesson
        lesson = Lesson.query.first()
        count = len(lesson.cards)
        url = f"/admin/parcours/lecons/{lesson.id}"
        self.client.post(url, data={"kind": "choice", "body": "2 + 2 ?", "choice_1": "3", "choice_2": "4",
                                    "correct": "2"})
        self.client.post(url, data={"kind": "number", "body": "10 % de 50 ?", "answer": "5", "unit_label": "€"})
        self.client.post(url, data={"kind": "choice", "body": "Invalide", "choice_1": "seul"})  # refusée
        db.session.expire_all()
        lesson = db.session.get(Lesson, lesson.id)
        self.assertEqual(len(lesson.cards), count + 2)
        self.assertEqual(lesson.cards[-2].answer, "1")
        self.assertEqual(lesson.cards[-1].answer, "5")


class HomeAndInformationTest(BaseCase):
    def test_home_dashboard(self):
        self.login("tom@exemple.fr")
        page = self.client.get("/app/").get_data(as_text=True)
        for text in ("Ta prochaine étape", "Jeu du jour", "Objectifs du jour", "Ma semaine", "Le savais-tu ?",
                     "Mes parcours"):
            self.assertIn(text, page)
        # la connexion du jour apparaît dans la semaine
        self.assertIn("week-day is-active", page)

    def test_information_rsvp_and_calendar(self):
        from app.models import Announcement, EventRegistration
        self.login("yanis@exemple.fr")
        page = self.client.get("/app/information").get_data(as_text=True)
        self.assertIn("Prochain rendez-vous", page)
        event = Announcement.query.filter(Announcement.package_code == "customer_relations",
                                          Announcement.audience.in_(["all", "18-24"]),
                                          Announcement.event_date.isnot(None)).first()
        self.client.post(f"/app/information/{event.id}/participer")
        self.assertEqual(EventRegistration.query.count(), 1)
        self.client.post(f"/app/information/{event.id}/participer")  # second clic : annulation
        self.assertEqual(EventRegistration.query.count(), 0)
        ics = self.client.get(f"/app/information/{event.id}/agenda.ics")
        self.assertEqual(ics.mimetype, "text/calendar")
        self.assertIn("BEGIN:VEVENT", ics.get_data(as_text=True))
        self.assertEqual(self.client.get("/app/information?type=annonces").status_code, 200)

    def test_minor_cannot_see_adult_event(self):
        from app.models import Announcement
        adult_event = Announcement.query.filter_by(package_code="customer_relations", audience="18-24").first()
        self.login("tom@exemple.fr")
        self.assertEqual(self.client.post(f"/app/information/{adult_event.id}/participer").status_code, 404)

    def test_admin_registrations_page(self):
        from app.models import Announcement
        event = Announcement.query.filter(Announcement.event_date.isnot(None)).first()
        self.login("admin@banque-demo.fr")
        self.assertEqual(self.client.get(f"/admin/information/{event.id}/inscrits").status_code, 200)


class GamesTest(BaseCase):
    def setUp(self):
        super().setUp()
        self.login("tom@exemple.fr")

    def state(self):
        with self.client.session_transaction() as sess:
            return sess["game"]

    def act(self, code, payload):
        return self.client.post(f"/app/education-basique/jeux/{code}/action", json=payload)

    def finish(self, code, payload=None):
        return self.client.post(f"/app/education-basique/jeux/{code}/terminer", json=payload or {}).get_json()

    def test_every_game_starts(self):
        from app.games import GAMES
        for code in GAMES:
            self.assertEqual(self.client.get(f"/app/education-basique/jeux/{code}").status_code, 200, code)
        self.assertEqual(self.client.get("/app/education-basique").status_code, 200)

    def test_memory(self):
        self.client.get("/app/education-basique/jeux/memory")
        cards = self.state()["state"]["cards"]
        pairs = {}
        for i, (pair, _) in enumerate(cards):
            pairs.setdefault(pair, []).append(i)
        for a, b in pairs.values():
            self.assertIn("face", self.act("memory", {"flip": a}).get_json())
            r = self.act("memory", {"flip": b}).get_json()
            self.assertTrue(r["match"])
        self.assertTrue(r["done"])
        self.assertEqual(self.act("memory", {"flip": 0}).status_code, 400)  # déjà trouvée
        self.assertEqual(self.finish("memory")["score"], 100)

    def test_higher_lower(self):
        from app.game_data import PRICE_CARDS
        self.client.get("/app/education-basique/jeux/plus_moins")
        deck = self.state()["state"]["deck"]
        for k in range(10):
            higher = PRICE_CARDS[deck[k + 1]][1] > PRICE_CARDS[deck[k]][1]
            self.assertTrue(self.act("plus_moins", {"guess": "plus" if higher else "moins"}).get_json()["correct"])
        self.assertEqual(self.finish("plus_moins")["correct"], 10)

    def test_crossword(self):
        self.client.get("/app/education-basique/jeux/mots_croises")
        state = self.state()["state"]
        hint = self.act("mots_croises", {"hint": state["words"][0][0]}).get_json()
        self.assertEqual(len(hint["letter"]), 1)
        grid = [[ch if ch != "." else "" for ch in row] for row in state["solution"]]
        result = self.finish("mots_croises", {"grid": grid})
        self.assertEqual(result["correct"], result["total"])
        self.assertEqual(result["score"], result["total"] * 10 + 20 - 5)

    def test_word_search(self):
        self.client.get("/app/education-basique/jeux/mots_meles")
        placements = self.state()["state"]["placements"]
        word, cells = next(iter(placements.items()))
        r = self.act("mots_meles", {"select": [cells[-1], cells[0]]}).get_json()  # à l'envers aussi
        self.assertEqual(r["found"], word)
        self.assertEqual(self.finish("mots_meles")["correct"], 1)

    def test_hangman(self):
        from app.game_data import WORDS
        self.client.get("/app/education-basique/jeux/mot_mystere")
        state = self.state()["state"]
        word = WORDS[state["words"][0]][0]
        for letter in dict.fromkeys(word):
            r = self.act("mot_mystere", {"letter": letter}).get_json()
        self.assertTrue(r["solved"])
        self.assertEqual(r["word"], word)
        self.assertEqual(self.act("mot_mystere", {"letter": "1"}).status_code, 400)
        self.assertEqual(self.finish("mot_mystere")["score"], 20)

    def test_life_simulation(self):
        self.client.get("/app/education-basique/jeux/vie_en_euros")
        for _ in range(8):
            r = self.act("vie_en_euros", {"choice": 0}).get_json()
        self.assertTrue(r["done"])
        self.assertEqual(self.act("vie_en_euros", {"choice": 0}).status_code, 400)
        result = self.finish("vie_en_euros")
        self.assertTrue(0 <= result["score"] <= 100)

    def test_stock_market(self):
        self.client.get("/app/education-basique/jeux/bourse")
        self.assertEqual(self.act("bourse", {"allocation": [50, 0, 0, 0]}).status_code, 400)  # ≠ 100 %
        for _ in range(8):
            r = self.act("bourse", {"allocation": [100, 0, 0, 0]}).get_json()
        self.assertTrue(r["done"])
        self.assertGreater(r["value"], 1000)  # le livret ne perd jamais
        self.assertIn("Valeur finale", self.finish("bourse")["summary"])

    def test_scam_and_price_games(self):
        from app.game_data import MESSAGES, PRICES
        self.client.get("/app/education-basique/jeux/arnaque")
        item = self.state()["secret"][0]
        answer = 0 if MESSAGES[item][2] else 1
        r = self.client.post("/app/education-basique/jeux/arnaque/verifier", json={"index": 0, "answer": answer})
        self.assertTrue(r.get_json()["correct"])
        self.client.get("/app/education-basique/jeux/juste_prix")
        price = PRICES[self.state()["secret"][0]][1]
        r = self.client.post("/app/education-basique/jeux/juste_prix/verifier",
                             json={"index": 0, "answer": str(round(price * 1.1, 2))})  # 10 % d'écart : accepté
        self.assertTrue(r.get_json()["correct"])

    def test_chrono_time_limit(self):
        import time as _time
        self.client.get("/app/education-basique/jeux/chrono")
        with self.client.session_transaction() as sess:
            game = sess["game"]
            game["started"] = _time.time() - 120
            sess["game"] = game
        r = self.client.post("/app/education-basique/jeux/chrono/verifier", json={"index": 0, "answer": 0}).get_json()
        self.assertTrue(r.get("timeout"))
        self.assertEqual(self.client.post("/app/education-basique/jeux/chrono/terminer").get_json()["correct"], 0)


class OnboardingTest(BaseCase):
    def create_child(self, email="nina@exemple.fr", years=12):
        from app import mailer
        mailer.sent.clear()
        self.login("parent@exemple.fr")
        birth = (date.today() - timedelta(days=365 * years + 30)).isoformat()
        page = self.client.post("/parent/enfants/nouveau", data={
            "first_name": "Nina", "last_name": "Dubois", "email": email, "birth_date": birth})
        return page, mailer.sent

    def password_from(self, message):
        import re
        return re.search(r"Mot de passe provisoire : (\S+)", message.get_content()).group(1)

    def test_parent_creates_child_and_email_is_sent(self):
        page, sent = self.create_child()
        self.assertIn("est créé", page.get_data(as_text=True))
        child = self.user("nina@exemple.fr")
        self.assertTrue(child.must_change_password)
        self.assertIsNone(child.onboarded_at)
        self.assertIn(child, self.user("parent@exemple.fr").children)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["To"], "nina@exemple.fr")
        self.assertIn("nina@exemple.fr", sent[0].get_content())

    def test_parent_cannot_create_adult_or_duplicate(self):
        self.create_child(years=19)
        self.assertIsNone(User.query.filter_by(email="nina@exemple.fr").first())
        page, _ = self.create_child(email="lea@exemple.fr")
        self.assertIn("existe déjà", page.get_data(as_text=True))

    # --- élève simulé : répond juste aux questions dont la difficulté est sous son niveau réel
    def answer_as(self, true_level, wrong_all=False):
        from app.models import LessonCard
        tiers = []
        r = None
        for _ in range(25):
            with self.client.session_transaction() as sess:
                state = sess["placement_test"]
            if state.get("current") is None:
                break
            card = db.session.get(LessonCard, state["current"])
            tiers.append(state["tier"])
            knows = state["tier"] < true_level and not wrong_all
            if card.kind == "choice":
                answer = int(card.answer) if knows else (int(card.answer) + 1) % len(card.choices)
            else:
                answer = card.answer if knows else "123456"
            r = self.client.post("/app/bienvenue/test/reponse", json={"answer": answer}).get_json()
            if r["done"]:
                break
        return tiers, r

    def start_as_new_child(self):
        _, sent = self.create_child()
        password = self.password_from(sent[0])
        self.client.post("/deconnexion")
        self.client.post("/connexion", data={"email": "nina@exemple.fr", "password": password})
        return password

    def test_full_first_login_flow(self):
        password = self.start_as_new_child()
        # 1. mot de passe obligatoire, toutes les pages redirigent
        for url in ("/app/", "/app/parcours", "/app/bienvenue"):
            self.assertTrue(self.client.get(url).headers["Location"].endswith("/app/bienvenue/mot-de-passe"))
        r = self.client.post("/app/bienvenue/mot-de-passe", data={"password": password, "confirm": password})
        self.assertIn("différent", r.get_data(as_text=True))
        self.client.post("/app/bienvenue/mot-de-passe", data={"password": "MonSecret42", "confirm": "MonSecret42"})
        # 2. test de positionnement obligatoire
        self.assertTrue(self.client.get("/app/").headers["Location"].endswith("/app/bienvenue"))
        self.assertEqual(self.client.get("/app/bienvenue").status_code, 200)
        self.assertEqual(self.client.get("/app/bienvenue/test").status_code, 200)
        # impossible de terminer avant les 20 questions
        self.assertEqual(self.client.post("/app/bienvenue/test/terminer").status_code, 400)
        tiers, last = self.answer_as(2)
        self.assertEqual(len(tiers), 20)
        self.assertTrue(last["done"])
        result = self.client.post("/app/bienvenue/test/terminer").get_json()
        self.assertTrue(result["redirect"].endswith("/app/bienvenue/resultat"))
        child = self.user("nina@exemple.fr")
        self.assertEqual(child.level, 2)  # Confirmé
        self.assertIsNotNone(child.onboarded_at)
        self.assertIn("Confirmé", self.client.get("/app/bienvenue/resultat").get_data(as_text=True))
        self.assertEqual(self.client.get("/app/").status_code, 200)

    def test_adaptive_test_converges_to_real_level(self):
        self.login("tom@exemple.fr")  # 11 ans : banque de questions des 10-17 ans
        for true_level in range(4):
            self.client.get("/app/bienvenue/test")
            tiers, _ = self.answer_as(true_level)
            self.client.post("/app/bienvenue/test/terminer")
            with self.client.session_transaction() as sess:
                found = sess["placement"]["level"]
            self.assertEqual(found, true_level, f"niveau réel {true_level}, trouvé {found}, difficultés {tiers}")
            self.assertEqual(len(tiers), 20)

    def test_difficulty_follows_answers(self):
        self.login("tom@exemple.fr")
        self.client.get("/app/bienvenue/test")
        with self.client.session_transaction() as sess:
            first_tier = sess["placement_test"]["tier"]
        self.answer_as(4, wrong_all=False)  # tout juste
        with self.client.session_transaction() as sess:
            history = sess["placement_test"]["history"]
        self.assertTrue(all(ok for _, ok in history))
        self.assertGreater(max(t for t, _ in history), first_tier)  # la difficulté est montée
        # tout faux : la difficulté descend jusqu'au plus facile
        self.client.get("/app/bienvenue/test")
        self.answer_as(0, wrong_all=True)
        with self.client.session_transaction() as sess:
            history = sess["placement_test"]["history"]
        self.assertEqual(history[-1][0], 0)
        # jamais deux fois la même question
        with self.client.session_transaction() as sess:
            asked = sess["placement_test"]["asked"]
        self.assertEqual(len(asked), len(set(asked)))

    def test_higher_levels_are_locked(self):
        from app.path import build_path
        tom = self.user("tom@exemple.fr")
        tom.level = 1
        db.session.commit()
        with self.app.test_request_context():
            units = next(s for s in build_path(tom) if s.package.code == "education_basic").units
        lesson_units = [u for u in units if u.level is not None]
        self.assertTrue(all(u.opened_by_test for u in lesson_units if u.level < 1))
        self.assertTrue(all(u.blocked for u in lesson_units if u.level > 1))
        self.assertTrue(all(n.state == "locked" for u in lesson_units if u.blocked for n in u.nodes))
        current = [u for u in lesson_units if u.level == 1]
        self.assertEqual(current[0].nodes[0].state, "current")
        # une leçon d'un niveau supérieur est refusée, même par l'URL
        self.login("tom@exemple.fr")
        blocked_lesson = int(next(u for u in lesson_units if u.blocked).nodes[0].key.split(":")[1])
        r = self.client.get(f"/app/lecons/{blocked_lesson}")
        self.assertEqual(r.status_code, 302)
        # une leçon d'un niveau acquis reste jouable directement
        acquired_lesson = int(lesson_units[1].nodes[1].key.split(":")[1])
        self.assertEqual(self.client.get(f"/app/lecons/{acquired_lesson}").status_code, 200)

    def test_finishing_a_level_unlocks_the_next(self):
        from app.path import build_path
        self.login("tom@exemple.fr")  # niveau 0
        notes = []
        for _ in range(60):  # on suit le parcours : leçons du niveau en cours, puis paliers
            with self.app.test_request_context():
                sections = [s for s in build_path(self.user("tom@exemple.fr"))
                            if s.package.code in ("education_basic", "education_advanced")]
            node = next((n for s in sections for u in s.units if u.level == 0 for n in u.nodes
                         if n.state == "current"), None)
            if node is None:
                break
            kind, ref = node.key.split(":", 1)
            if kind == "chest":
                self.client.post(f"/app/parcours/coffre/{ref}")
            else:
                self.assertEqual(self.client.get(f"/app/lecons/{ref}").status_code, 200)
                notes.append(self.client.post(f"/app/lecons/{ref}/terminer").get_json()["note"])
        self.assertTrue(any(note and "niveau Initié" in note for note in notes))
        tom = self.user("tom@exemple.fr")
        self.assertEqual(tom.level, 1)
        with self.app.test_request_context():
            basic = next(s for s in build_path(tom) if s.package.code == "education_basic")
        self.assertTrue(any(u.level == 1 and not u.blocked for u in basic.units))

    def test_skip_test_and_retake_never_lowers_level(self):
        self.start_as_new_child()
        self.client.post("/app/bienvenue/mot-de-passe", data={"password": "MonSecret42", "confirm": "MonSecret42"})
        self.client.post("/app/bienvenue/passer")
        child = self.user("nina@exemple.fr")
        self.assertEqual(child.level, 0)
        self.assertEqual(self.client.get("/app/").status_code, 200)
        child.level = 2
        db.session.commit()
        self.client.get("/app/bienvenue/test")
        self.answer_as(0, wrong_all=True)
        self.client.post("/app/bienvenue/test/terminer")
        self.assertEqual(self.user("nina@exemple.fr").level, 2)

    def test_resend_credentials(self):
        from app import mailer
        self.create_child()
        child = self.user("nina@exemple.fr")
        old_hash = child.password_hash
        self.client.post(f"/parent/enfants/{child.id}/identifiants")
        self.assertEqual(len(mailer.sent), 2)
        db.session.expire_all()
        self.assertNotEqual(self.user("nina@exemple.fr").password_hash, old_hash)

    def test_admin_created_client_must_onboard(self):
        from app import mailer
        mailer.sent.clear()
        self.login("admin@banque-demo.fr")
        birth = (date.today() - timedelta(days=365 * 20)).isoformat()
        self.client.post("/admin/utilisateurs/nouveau", data={
            "role": "client", "email": "new@x.fr", "first_name": "N", "last_name": "X", "password": "Provisoire1",
            "birth_date": birth, "send_credentials": "on"})
        self.assertTrue(self.user("new@x.fr").must_change_password)
        self.assertEqual(len(mailer.sent), 1)


if __name__ == "__main__":
    unittest.main()
