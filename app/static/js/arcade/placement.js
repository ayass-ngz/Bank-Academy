// Test de positionnement adaptatif : une question à la fois, choisie par le serveur
// selon les réponses précédentes. La difficulté monte après une bonne réponse et baisse après une erreur.
(() => {
  const A = Arcade;
  const LEVELS = ["Découverte", "Initié", "Confirmé"];
  let question = A.data;
  let selected = null;
  let busy = false;

  const progress = A.el("div", "lesson-progress pl-progress");
  const bar = A.el("div");
  progress.append(bar);
  const card = A.el("div", "pl-card");
  const answers = A.el("div", "lesson-choices");
  A.board.append(progress, card, answers);

  const validate = A.button("Valider", "btn btn-lesson", submit);

  function difficulty(tier) {
    const box = A.el("div", "pl-difficulty");
    box.append(A.el("span", "pl-difficulty-label", "Difficulté"));
    const dots = A.el("span", "pl-dots");
    LEVELS.forEach((name, i) => dots.append(A.el("span", `pl-dot ${i <= tier ? "on" : ""}`)));
    box.append(dots, A.el("span", "pl-difficulty-name", LEVELS[tier]));
    return box;
  }

  function render(q) {
    question = q;
    selected = null;
    busy = false;
    bar.style.width = `${((q.index - 1) / q.total) * 100}%`;
    A.setStatus(A.statusItem("bi-list-ol", `Question ${q.index} / ${q.total}`));
    card.replaceChildren(difficulty(q.tier), A.el("div", "pl-prompt", q.prompt));
    answers.replaceChildren();
    if (q.choices) {
      q.choices.forEach((label, i) => {
        const btn = A.el("button", "choice");
        btn.type = "button";
        btn.append(A.el("span", "choice-key", String(i + 1)), A.el("span", null, label));
        btn.addEventListener("click", () => choose(i));
        answers.append(btn);
      });
    } else {
      const wrap = A.el("label", "lesson-input-wrap");
      const input = A.el("input", "lesson-input");
      input.inputMode = "decimal";
      input.autocomplete = "off";
      input.placeholder = "Ta réponse";
      input.setAttribute("aria-label", "Ta réponse");
      input.addEventListener("input", () => {
        selected = input.value.trim() || null;
        validate.disabled = selected === null;
      });
      wrap.append(input);
      if (q.unit) wrap.append(A.el("span", "lesson-input-unit", q.unit));
      answers.append(wrap);
      setTimeout(() => input.focus(), 50);
    }
    validate.disabled = true;
    A.clearSay();
    A.setActions(validate);
  }

  function choose(i) {
    if (busy) return;
    selected = i;
    answers.querySelectorAll(".choice").forEach((b, j) => b.classList.toggle("selected", j === i));
    validate.disabled = false;
  }

  async function submit() {
    if (busy || selected === null) return;
    busy = true;
    validate.disabled = true;
    answers.querySelectorAll("button, input").forEach((n) => { n.disabled = true; });
    try {
      const r = await A.action({ answer: selected });
      const picked = answers.querySelector(".choice.selected, .lesson-input-wrap");
      if (picked) picked.classList.add(r.correct ? "correct" : "wrong");
      let hint = "";
      if (r.next && r.next.tier > question.tier) hint = "La question suivante sera plus difficile ⬆";
      else if (r.next && r.next.tier < question.tier) hint = "La question suivante sera plus facile ⬇";
      A.say(r.correct ? "ok" : "ko", r.correct ? "Bonne réponse !" : `Pas tout à fait : ${r.expected}`, hint);
      bar.style.width = `${(r.answered / question.total) * 100}%`;
      setTimeout(() => {
        if (r.done) {
          A.setActions();
          A.say(null, "Test terminé !", "Calcul de ton niveau…");
          A.finish();
        } else {
          render(r.next);
        }
      }, r.correct ? 900 : 1600);
    } catch (err) {
      busy = false;
      answers.querySelectorAll("button, input").forEach((n) => { n.disabled = false; });
      validate.disabled = false;
      A.error(err);
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !validate.disabled) { event.preventDefault(); submit(); return; }
    const n = Number.parseInt(event.key, 10);
    const buttons = answers.querySelectorAll(".choice");
    if (!busy && n >= 1 && n <= buttons.length && document.activeElement.tagName !== "INPUT") choose(n - 1);
  });

  render(question);
})();
