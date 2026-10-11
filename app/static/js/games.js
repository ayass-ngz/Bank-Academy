// Écran « leçon » (leçons du programme et jeux de questions) : on sélectionne une réponse,
// le serveur la corrige, puis un bandeau affiche la correction avant de continuer.
// Mode chronométré (data-time-limit) : compte à rebours et enchaînement automatique.
(() => {
  const root = document.getElementById("game");
  const dataEl = document.getElementById("game-data");
  if (!root || !dataEl) return;
  const rounds = JSON.parse(dataEl.textContent);
  if (!rounds.length) return;

  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const $ = (id) => document.getElementById(id);
  const els = {
    title: $("game-title"), prompt: $("game-prompt"), promptWrap: $("game-prompt-wrap"), answers: $("game-answers"), feedback: $("game-feedback"),
    action: $("game-action"), footer: $("game-footer"), bar: $("game-bar"), combo: $("game-combo"),
  };
  const PRAISE = ["Excellent !", "Bravo !", "Parfait !", "Génial !", "Super !", "Bien joué !"];
  const instruction = els.title.textContent;
  let index = 0;
  let selected = null;
  let phase = "answer"; // info | answer → checking → feedback → … → done
  let combo = 0;
  const timeLimit = Number.parseInt(root.dataset.timeLimit || "0", 10);
  let remaining = timeLimit;
  let timer = null;

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body || {}),
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(name) { return el("i", `bi ${name}`); }

  function setAction(label, enabled, variant = "") {
    els.action.textContent = label;
    els.action.disabled = !enabled;
    els.action.className = `btn btn-lesson ${variant}`;
  }

  function updateCombo() {
    els.combo.querySelector("span").textContent = combo;
    els.combo.classList.toggle("hot", combo >= 2);
  }

  function showRound() {
    const round = rounds[index];
    phase = "answer";
    selected = null;
    els.bar.style.width = `${(index / rounds.length) * 100}%`;
    els.footer.className = "lesson-footer";
    els.feedback.replaceChildren();
    els.answers.replaceChildren();

    if (round.type === "info") {  // fiche de cours : on lit puis on continue
      phase = "info";
      els.title.textContent = round.title;
      els.promptWrap.hidden = true;
      const card = el("div", "theory-card");
      card.append(el("span", "theory-badge", "Fiche de cours"));
      round.text.split("\n").forEach((line) => card.append(el("p", null, line)));
      els.answers.append(card);
      setAction("Continuer", true);
      els.action.focus();
      return;
    }

    els.promptWrap.hidden = false;
    els.title.textContent = round.instruction || instruction;
    if (round.message) {  // message reçu (SMS / mail) affiché comme sur un téléphone
      const sms = el("div", "sms");
      sms.append(el("div", "sms-sender", round.message.sender), el("div", "sms-bubble", round.message.text));
      els.prompt.replaceChildren(sms);
    } else {
      els.prompt.textContent = round.prompt;
    }

    if (round.choices) {
      round.choices.forEach((label, i) => {
        const button = el("button", "choice");
        button.type = "button";
        button.append(el("span", "choice-key", String(i + 1)), el("span", null, label));
        button.addEventListener("click", () => select(i));
        els.answers.append(button);
      });
    } else {
      const wrap = el("label", "lesson-input-wrap");
      const input = el("input", "lesson-input");
      input.inputMode = "decimal";
      input.autocomplete = "off";
      input.placeholder = "Ta réponse";
      input.setAttribute("aria-label", "Ta réponse en euros");
      input.addEventListener("input", () => {
        selected = input.value.trim() || null;
        setAction("Vérifier", selected !== null);
      });
      wrap.append(input);
      const unit = round.unit === undefined ? "€" : round.unit;
      if (unit) wrap.append(el("span", "lesson-input-unit", unit));
      els.answers.append(wrap);
      input.focus();
    }
    setAction("Vérifier", false);
  }

  function select(i) {
    if (phase !== "answer") return;
    selected = i;
    els.answers.querySelectorAll(".choice").forEach((c, j) => c.classList.toggle("selected", j === i));
    setAction("Vérifier", true);
  }

  async function check() {
    phase = "checking";
    els.action.disabled = true;
    els.answers.querySelectorAll("button, input").forEach((n) => { n.disabled = true; });
    try {
      const r = await post(root.dataset.checkUrl, { index, answer: selected });
      combo = r.correct ? combo + 1 : 0;
      updateCombo();
      const picked = els.answers.querySelector(".choice.selected, .lesson-input-wrap");
      if (picked) picked.classList.add(r.correct ? "correct" : "wrong");

      els.footer.className = `lesson-footer ${r.correct ? "is-ok" : "is-ko"}`;
      const badge = el("span", "feedback-icon");
      badge.append(icon(r.correct ? "bi-check-lg" : "bi-x-lg"));
      const text = el("div");
      text.append(el("div", "feedback-title", r.correct ? PRAISE[Math.floor(Math.random() * PRAISE.length)] : "Bonne réponse :"));
      if (!r.correct) text.append(el("div", "feedback-answer", r.expected));
      if (r.explanation) text.append(el("div", "feedback-text", r.explanation));
      els.feedback.replaceChildren(badge, text);

      phase = "feedback";
      setAction("Continuer", true, r.correct ? "" : "is-ko");
      els.action.focus();
      if (timeLimit) setTimeout(() => { if (phase === "feedback") els.action.click(); }, r.correct ? 500 : 1400);
    } catch (err) {
      phase = "answer";
      els.answers.querySelectorAll("button, input").forEach((n) => { n.disabled = false; });
      els.feedback.replaceChildren(el("div", "text-danger fw-bold", "Erreur de connexion, réessaie."));
      setAction("Vérifier", true);
    }
  }

  function resultBox(label, value, iconName, color) {
    const box = el("div", "result-box");
    box.style.setProperty("--c", color);
    const val = el("div", "result-box-value");
    val.append(icon(iconName), document.createTextNode(value));
    box.append(el("div", "result-box-label", label), val);
    return box;
  }

  async function finish() {
    if (phase === "done") return;
    phase = "done";
    if (timer) clearInterval(timer);
    els.bar.style.width = "100%";
    els.answers.replaceChildren();
    els.footer.className = "lesson-footer";
    els.feedback.replaceChildren();
    setAction("Continuer", false);
    try {
      const r = await post(root.dataset.finishUrl);
      if (r.redirect) { window.location.href = r.redirect; return; }  // ex. test de niveau → page de résultat
      const accuracy = r.total ? Math.round((100 * r.correct) / r.total) : 100;
      els.promptWrap.hidden = false;
      els.title.textContent = "Leçon terminée !";
      els.prompt.textContent = accuracy === 100 ? "Sans faute, impressionnant ! 🏆"
        : accuracy >= 50 ? `${r.correct} bonnes réponses sur ${r.total}, bien joué ! 👏`
        : `${r.correct} sur ${r.total} : continue, tu progresses ! 💪`;

      const result = el("div", "lesson-result");
      const boxes = el("div", "result-boxes");
      boxes.append(
        resultBox("Points", `+${r.points}`, "bi-trophy-fill", "#e0a100"),
        resultBox("Précision", `${accuracy}%`, "bi-bullseye", "#2f6fed"),
        resultBox("Série", `${r.streak} j`, "bi-fire", "#f76707"),
      );
      result.append(boxes);
      if (r.note) result.append(el("p", "text-muted small", r.note));
      els.answers.append(result);

      const replay = el("a", "btn btn-outline-secondary btn-lesson-secondary", "Rejouer");
      replay.href = root.dataset.replayUrl;
      els.feedback.replaceChildren(replay);
      setAction("Continuer", true);
      els.action.focus();
    } catch (err) {
      els.feedback.replaceChildren(el("div", "text-danger fw-bold", "Impossible d'enregistrer le score."));
    }
  }

  els.action.addEventListener("click", () => {
    if (phase === "answer" && selected !== null) check();
    else if (phase === "feedback" || phase === "info") {
      index += 1;
      if (index < rounds.length) showRound();
      else finish();
    } else if (phase === "done") window.location.href = root.dataset.homeUrl;
  });

  document.addEventListener("keydown", (event) => {
    const tag = document.activeElement ? document.activeElement.tagName : "";
    if (event.key === "Enter" && tag !== "BUTTON" && tag !== "A") {
      if (!els.action.disabled) { event.preventDefault(); els.action.click(); }
      return;
    }
    const n = Number.parseInt(event.key, 10);
    const choices = els.answers.querySelectorAll(".choice");
    if (phase === "answer" && n >= 1 && n <= choices.length) select(n - 1);
  });

  if (timeLimit) {  // le compte à rebours remplace le compteur de bonnes réponses
    const clock = el("span", "lesson-clock");
    els.combo.after(clock);
    const tick = () => {
      clock.replaceChildren(icon("bi-stopwatch"), document.createTextNode(` ${remaining} s`));
      clock.classList.toggle("is-urgent", remaining <= 10);
      if (remaining <= 0) finish();
      remaining -= 1;
    };
    tick();
    timer = setInterval(tick, 1000);
  }
  showRound();
})();
