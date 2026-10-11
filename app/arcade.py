"""Jeux interactifs (cartes, lettres, simulations) du package « Éducation basique ».

Chaque moteur expose trois fonctions :
  start(user)                  -> (état public envoyé au navigateur, état secret gardé en session)
  action(state, payload)       -> réponse JSON (l'état secret est modifié sur place)
  finish(state, payload)       -> {"score", "correct", "total", "summary"}
Les solutions ne quittent jamais le serveur avant d'être méritées.
"""
import random
import string

from .game_data import LIFE_EVENTS, PAIRS, PRICE_CARDS, STOCK_ASSETS, STOCK_NEWS, WORDS
from .games import euros_value


class GameError(ValueError):
    """Action invalide envoyée par le navigateur."""


def _clamp(value, low, high):
    return max(low, min(high, value))


# ------------------------------------------------------------------ Memory des notions
class Memory:
    @staticmethod
    def start(user):
        n_pairs = 6 if user.is_minor else 8
        pairs = random.sample(range(len(PAIRS)), n_pairs)
        cards = [[p, side] for p in pairs for side in (0, 1)]
        random.shuffle(cards)
        return ({"count": len(cards), "pairs": n_pairs},
                {"cards": cards, "matched": [], "attempts": 0, "pending": None})

    @staticmethod
    def action(state, payload):
        """Une carte à la fois : la 1re est mémorisée, la 2e compte comme un essai."""
        i = payload.get("flip")
        cards = state["cards"]
        if (not isinstance(i, int) or not 0 <= i < len(cards) or i in state["matched"]
                or i == state.get("pending")):
            raise GameError("Retournement invalide.")
        face = {"text": PAIRS[cards[i][0]][cards[i][1]], "kind": "notion" if cards[i][1] == 0 else "definition"}
        pending = state.get("pending")
        if pending is None:
            state["pending"] = i
            return {"face": face}
        state["pending"] = None
        state["attempts"] += 1
        match = cards[i][0] == cards[pending][0]
        if match:
            state["matched"] += [pending, i]
        return {"face": face, "other": pending, "match": match, "attempts": state["attempts"],
                "done": len(state["matched"]) == len(cards)}

    @staticmethod
    def finish(state, payload):
        pairs = len(state["cards"]) // 2
        found = len(state["matched"]) // 2
        if found == pairs:
            score = max(20, 100 - 8 * max(0, state["attempts"] - pairs))
        else:
            score = found * 8
        return {"score": score, "correct": found, "total": pairs,
                "summary": f"{found} paire(s) sur {pairs} en {state['attempts']} essais."}


# ------------------------------------------------------------------ Plus ou moins cher ?
class HigherLower:
    ROUNDS = 10

    @staticmethod
    def _card(i):
        name, price, icon = PRICE_CARDS[i]
        return {"name": name, "price": euros_value(price), "icon": icon}

    @classmethod
    def start(cls, user):
        deck = random.sample(range(len(PRICE_CARDS)), cls.ROUNDS + 1)
        return ({"current": cls._card(deck[0]), "total": cls.ROUNDS},
                {"deck": deck, "pos": 0, "correct": 0})

    @classmethod
    def action(cls, state, payload):
        guess = payload.get("guess")
        if guess not in ("plus", "moins") or state["pos"] >= cls.ROUNDS:
            raise GameError("Choix invalide.")
        current, nxt = state["deck"][state["pos"]], state["deck"][state["pos"] + 1]
        higher = PRICE_CARDS[nxt][1] > PRICE_CARDS[current][1]
        correct = higher == (guess == "plus")
        state["pos"] += 1
        state["correct"] += int(correct)
        return {"next": cls._card(nxt), "correct": correct, "round": state["pos"],
                "done": state["pos"] >= cls.ROUNDS}

    @classmethod
    def finish(cls, state, payload):
        return {"score": state["correct"] * 10, "correct": state["correct"], "total": cls.ROUNDS,
                "summary": f"{state['correct']} bonne(s) réponse(s) sur {cls.ROUNDS}."}


# ------------------------------------------------------------------ Mots croisés
class Crossword:
    SIZE = 13

    @classmethod
    def _can_place(cls, grid, word, r, c, d):
        dr, dc = (0, 1) if d == "A" else (1, 0)
        end_r, end_c = r + dr * (len(word) - 1), c + dc * (len(word) - 1)
        if r < 0 or c < 0 or end_r >= cls.SIZE or end_c >= cls.SIZE:
            return False
        if grid.get((r - dr, c - dc)) or grid.get((end_r + dr, end_c + dc)):
            return False
        crossings = 0
        for k, letter in enumerate(word):
            cell = (r + dr * k, c + dc * k)
            existing = grid.get(cell)
            if existing:
                if existing != letter:
                    return False
                crossings += 1
            else:  # pas de lettre collée parallèlement
                side_a = (cell[0] + dc, cell[1] + dr)
                side_b = (cell[0] - dc, cell[1] - dr)
                if grid.get(side_a) or grid.get(side_b):
                    return False
        return 0 < crossings < len(word)

    @classmethod
    def generate(cls, target=8):
        for _ in range(30):  # plusieurs essais pour obtenir une grille bien remplie
            pool = random.sample(WORDS, len(WORDS))
            first = next(w for w in pool if 6 <= len(w[0]) <= 8)
            pool.remove(first)
            grid, placed = {}, []

            def place(word, clue, r, c, d):
                dr, dc = (0, 1) if d == "A" else (1, 0)
                for k, letter in enumerate(word):
                    grid[(r + dr * k, c + dc * k)] = letter
                placed.append((word, clue, r, c, d))

            place(first[0], first[1], cls.SIZE // 2, (cls.SIZE - len(first[0])) // 2, "A")
            for word, clue in pool:
                if len(placed) >= target or len(word) > 9:
                    continue
                options = []
                for k, letter in enumerate(word):
                    for (gr, gc), existing in list(grid.items()):
                        if existing != letter:
                            continue
                        for d in ("A", "D"):
                            r, c = (gr, gc - k) if d == "A" else (gr - k, gc)
                            if cls._can_place(grid, word, r, c, d):
                                options.append((r, c, d))
                if options:
                    place(word, clue, *random.choice(options))
            if len(placed) >= target - 2:
                return placed
        return placed

    @classmethod
    def start(cls, user):
        placed = cls.generate(7 if user.is_minor else 9)
        min_r = min(r for _, _, r, _, _ in placed)
        min_c = min(c for _, _, _, c, _ in placed)
        cells_of = []
        for word, clue, r, c, d in placed:
            dr, dc = (0, 1) if d == "A" else (1, 0)
            cells_of.append([[r - min_r + dr * k, c - min_c + dc * k] for k in range(len(word))])
        rows = max(cell[0] for cells in cells_of for cell in cells) + 1
        cols = max(cell[1] for cells in cells_of for cell in cells) + 1
        solution = [["."] * cols for _ in range(rows)]
        for (word, *_), cells in zip(placed, cells_of):
            for letter, (r, c) in zip(word, cells):
                solution[r][c] = letter
        # Numérotation dans l'ordre de lecture
        starts = sorted({tuple(cells[0]) for cells in cells_of})
        numbers = {start: i + 1 for i, start in enumerate(starts)}
        words = []
        for idx, ((word, clue, r, c, d), cells) in enumerate(zip(placed, cells_of)):
            words.append({"id": idx, "num": numbers[tuple(cells[0])], "dir": d, "clue": clue, "len": len(word),
                          "cells": cells})
        words.sort(key=lambda w: (w["dir"], w["num"]))
        public = {"rows": rows, "cols": cols,
                  "blocks": [[solution[r][c] == "." for c in range(cols)] for r in range(rows)],
                  "numbers": [[numbers.get((r, c)) for c in range(cols)] for r in range(rows)],
                  "words": words}
        return public, {"solution": ["".join(row) for row in solution], "words": [w["cells"] for w in words],
                        "hints": 0}

    @staticmethod
    def action(state, payload):
        cell = payload.get("hint")
        solution = state["solution"]
        if (not isinstance(cell, list) or len(cell) != 2 or not all(isinstance(v, int) for v in cell)
                or not 0 <= cell[0] < len(solution) or not 0 <= cell[1] < len(solution[0])
                or solution[cell[0]][cell[1]] == "."):
            raise GameError("Case invalide.")
        state["hints"] += 1
        return {"letter": solution[cell[0]][cell[1]], "hints": state["hints"]}

    @staticmethod
    def finish(state, payload):
        grid = payload.get("grid") or []
        solution = state["solution"]

        def letter(r, c):
            try:
                return str(grid[r][c] or "").strip().upper()[:1]
            except (IndexError, TypeError):
                return ""

        correct = sum(1 for cells in state["words"] if all(letter(r, c) == solution[r][c] for r, c in cells))
        total = len(state["words"])
        score = max(0, correct * 10 + (20 if correct == total else 0) - state["hints"] * 5)
        return {"score": score, "correct": correct, "total": total,
                "summary": f"{correct} mot(s) sur {total} trouvés"
                           + (f", {state['hints']} indice(s) utilisé(s)." if state["hints"] else ".")}


# ------------------------------------------------------------------ Mots mêlés
class WordSearch:
    LETTERS = "EEEEAAASSIINNTTRRULLOODCMPVQFBGHJXYZK"

    @classmethod
    def start(cls, user):
        size, count = (10, 7) if user.is_minor else (12, 9)
        directions = [(0, 1), (1, 0), (1, 1)] + ([] if user.is_minor else [(0, -1), (-1, 0), (1, -1), (-1, -1)])
        candidates = [w for w, _ in WORDS if len(w) <= size - 1]
        for _ in range(50):
            grid = [[""] * size for _ in range(size)]
            placements = {}
            for word in random.sample(candidates, len(candidates)):
                if len(placements) >= count:
                    break
                for _ in range(80):
                    dr, dc = random.choice(directions)
                    r, c = random.randrange(size), random.randrange(size)
                    end_r, end_c = r + dr * (len(word) - 1), c + dc * (len(word) - 1)
                    if not (0 <= end_r < size and 0 <= end_c < size):
                        continue
                    cells = [(r + dr * k, c + dc * k) for k in range(len(word))]
                    if all(grid[a][b] in ("", word[k]) for k, (a, b) in enumerate(cells)):
                        for k, (a, b) in enumerate(cells):
                            grid[a][b] = word[k]
                        placements[word] = [list(cell) for cell in cells]
                        break
            if len(placements) == count:
                break
        for r in range(size):
            for c in range(size):
                grid[r][c] = grid[r][c] or random.choice(cls.LETTERS)
        words = sorted(placements)
        return ({"size": size, "grid": ["".join(row) for row in grid], "words": words},
                {"placements": placements, "found": []})

    @staticmethod
    def action(state, payload):
        sel = payload.get("select")
        try:
            (r1, c1), (r2, c2) = sel
            r1, c1, r2, c2 = int(r1), int(c1), int(r2), int(c2)
        except (TypeError, ValueError):
            raise GameError("Sélection invalide.") from None
        dr, dc = r2 - r1, c2 - c1
        if not (dr == 0 or dc == 0 or abs(dr) == abs(dc)):
            return {"found": None}
        steps = max(abs(dr), abs(dc))
        sr, sc = (dr // steps if steps else 0), (dc // steps if steps else 0)
        cells = [[r1 + sr * k, c1 + sc * k] for k in range(steps + 1)]
        for word, placed in state["placements"].items():
            if word not in state["found"] and (cells == placed or cells[::-1] == placed):
                state["found"].append(word)
                return {"found": word, "cells": placed, "done": len(state["found"]) == len(state["placements"])}
        return {"found": None}

    @staticmethod
    def finish(state, payload):
        found, total = len(state["found"]), len(state["placements"])
        return {"score": found * 10 + (20 if found == total else 0), "correct": found, "total": total,
                "summary": f"{found} mot(s) trouvé(s) sur {total}."}


# ------------------------------------------------------------------ Le mot mystère
class Hangman:
    WORDS_PER_GAME = 5
    LIVES = 6

    @classmethod
    def _public(cls, state):
        word, clue = WORDS[state["words"][state["i"]]]
        return {"length": len(word), "clue": clue, "lives": state["lives"], "index": state["i"] + 1,
                "total": cls.WORDS_PER_GAME}

    @classmethod
    def start(cls, user):
        pool = [i for i, (w, _) in enumerate(WORDS) if (len(w) <= 7 if user.is_minor else len(w) >= 5)]
        state = {"words": random.sample(pool, cls.WORDS_PER_GAME), "i": 0, "guessed": [], "lives": cls.LIVES,
                 "results": []}
        return cls._public(state), state

    @classmethod
    def action(cls, state, payload):
        letter = str(payload.get("letter", "")).upper()
        if state["i"] >= cls.WORDS_PER_GAME or len(letter) != 1 or letter not in string.ascii_uppercase \
                or letter in state["guessed"]:
            raise GameError("Lettre invalide.")
        word, clue = WORDS[state["words"][state["i"]]]
        state["guessed"].append(letter)
        positions = [k for k, ch in enumerate(word) if ch == letter]
        if not positions:
            state["lives"] -= 1
        solved = all(ch in state["guessed"] for ch in word)
        failed = state["lives"] <= 0
        response = {"positions": positions, "lives": state["lives"], "solved": solved, "failed": failed}
        if solved or failed:
            state["results"].append(solved)
            response["word"] = word
            state["i"] += 1
            state["guessed"], state["lives"] = [], cls.LIVES
            response["next"] = cls._public(state) if state["i"] < cls.WORDS_PER_GAME else None
        return response

    @classmethod
    def finish(cls, state, payload):
        found = sum(1 for r in state["results"] if r)
        return {"score": found * 20, "correct": found, "total": cls.WORDS_PER_GAME,
                "summary": f"{found} mot(s) trouvé(s) sur {cls.WORDS_PER_GAME}."}


# ------------------------------------------------------------------ La vie en euros
class Life:
    MONTHS = 8

    @staticmethod
    def _event(state):
        text, options = LIFE_EVENTS[state["band"]]["events"][state["events"][state["i"]]]
        return {"text": text, "options": [label for label, *_ in options]}

    @classmethod
    def start(cls, user):
        config = LIFE_EVENTS[user.band]
        state = {"band": user.band, "events": random.sample(range(len(config["events"])), cls.MONTHS), "i": 0,
                 "money": config["start"], "wellbeing": 5}
        public = {"money": state["money"], "wellbeing": 5, "month": 1, "months": cls.MONTHS,
                  "income": config["income"], "income_label": config["income_label"],
                  "fixed": config["fixed"], "fixed_label": config["fixed_label"], "event": cls._event(state)}
        return public, state

    @classmethod
    def action(cls, state, payload):
        if state["i"] >= cls.MONTHS:
            raise GameError("La simulation est terminée.")
        config = LIFE_EVENTS[state["band"]]
        _, options = config["events"][state["events"][state["i"]]]
        choice = payload.get("choice")
        if not isinstance(choice, int) or not 0 <= choice < len(options):
            raise GameError("Choix invalide.")
        label, money, wellbeing, lesson = options[choice]
        state["money"] += config["income"] - config["fixed"] + money
        state["wellbeing"] = _clamp(state["wellbeing"] + wellbeing, 0, 10)
        state["i"] += 1
        done = state["i"] >= cls.MONTHS
        return {"lesson": lesson, "delta_money": money, "delta_wellbeing": wellbeing, "money": state["money"],
                "wellbeing": state["wellbeing"], "month": state["i"] + 1, "done": done,
                "event": None if done else cls._event(state)}

    @classmethod
    def finish(cls, state, payload):
        config = LIFE_EVENTS[state["band"]]
        total_income = config["start"] + (config["income"] - config["fixed"]) * cls.MONTHS
        savings_score = 0 if state["money"] <= 0 else min(50, round(50 * state["money"] / (0.25 * total_income)))
        score = savings_score + state["wellbeing"] * 5
        return {"score": score, "correct": state["i"], "total": cls.MONTHS,
                "summary": f"Argent à la fin : {euros_value(state['money'])} · Bien-être : {state['wellbeing']}/10. "
                           "Le secret : épargner sans oublier de vivre !"}


# ------------------------------------------------------------------ Bourse junior
class Stock:
    TURNS = 8
    START = 1000

    @classmethod
    def start(cls, user):
        returns, news = [], []
        for _ in range(cls.TURNS):
            n = random.randrange(len(STOCK_NEWS))
            text, target, effect = STOCK_NEWS[n]
            row = []
            for i, (_, _, _, vol) in enumerate(STOCK_ASSETS):
                if vol == 0:
                    r = 0.0075  # livret : environ 3 % par an, soit 0,75 % par trimestre
                else:
                    r = 0.015 + random.gauss(0, vol) + (effect if target == i else 0)
                row.append(round(_clamp(r, -0.45, 0.6), 4))
            returns.append(row)
            news.append(n)
        assets = [{"name": n, "sector": s, "icon": icon, "risk": ["Aucun", "Faible", "Moyen", "Élevé"][
            0 if vol == 0 else (1 if vol < 0.08 else (2 if vol < 0.15 else 3))]} for n, s, icon, vol in STOCK_ASSETS]
        public = {"value": cls.START, "turn": 1, "turns": cls.TURNS, "assets": assets, "news": STOCK_NEWS[news[0]][0]}
        return public, {"turn": 0, "value": cls.START, "returns": returns, "news": news, "spread": []}

    @classmethod
    def action(cls, state, payload):
        alloc = payload.get("allocation")
        if (state["turn"] >= cls.TURNS or not isinstance(alloc, list) or len(alloc) != len(STOCK_ASSETS)
                or not all(isinstance(a, int) and 0 <= a <= 100 for a in alloc) or sum(alloc) != 100):
            raise GameError("La répartition doit totaliser 100 %.")
        returns = state["returns"][state["turn"]]
        portfolio = sum(a / 100 * r for a, r in zip(alloc, returns))
        state["value"] = round(state["value"] * (1 + portfolio), 2)
        state["spread"].append(sum(1 for a in alloc if a > 0))
        state["turn"] += 1
        done = state["turn"] >= cls.TURNS
        return {"returns": [round(r * 100, 1) for r in returns], "portfolio": round(portfolio * 100, 1),
                "value": state["value"], "turn": state["turn"] + 1, "done": done,
                "news": None if done else STOCK_NEWS[state["news"][state["turn"]]][0]}

    @classmethod
    def finish(cls, state, payload):
        value = state["value"]
        score = int(_clamp(round(50 + (value - cls.START) / 6), 0, 100))
        spread = sum(state["spread"]) / len(state["spread"]) if state["spread"] else 0
        advice = ("Bravo, tu as diversifié tes placements !" if spread >= 2.5
                  else "Astuce : répartir sur plusieurs placements limite les mauvaises surprises.")
        gain = value - cls.START
        return {"score": score, "correct": state["turn"], "total": cls.TURNS,
                "summary": f"Valeur finale : {euros_value(round(value))} ({'+' if gain >= 0 else '−'}"
                           f"{euros_value(abs(round(gain)))}). {advice}"}


ENGINES = {"memory": Memory, "higherlower": HigherLower, "crossword": Crossword, "wordsearch": WordSearch,
           "hangman": Hangman, "life": Life, "stock": Stock}
