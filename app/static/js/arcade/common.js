// Socle commun des jeux interactifs : requêtes, barre de retour, écran de fin.
window.Arcade = (() => {
  const root = document.getElementById("arcade");
  const data = JSON.parse(document.getElementById("arcade-data").textContent);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const $ = (id) => document.getElementById(id);
  const board = $("arcade-board");
  const statusBox = $("arcade-status");
  const feedback = $("arcade-feedback");
  const actions = $("arcade-actions");
  const footer = $("arcade-footer");
  const instruction = $("arcade-instruction");
  let finished = false;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function icon(name) { return el("i", `bi ${name}`); }

  async function post(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body || {}),
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(json.error || "Erreur de connexion, réessaie.");
    return json;
  }

  const action = (payload) => post(root.dataset.actionUrl, payload);

  function statusItem(iconName, text, className = "") {
    const item = el("span", `arcade-stat ${className}`);
    item.append(icon(iconName), document.createTextNode(` ${text}`));
    return item;
  }

  function setStatus(...items) { statusBox.replaceChildren(...items); }

  // kind : "ok" | "ko" | null (neutre)
  function say(kind, title, text) {
    footer.className = `lesson-footer${kind ? ` is-${kind}` : ""}`;
    const nodes = [];
    if (kind) {
      const badge = el("span", "feedback-icon");
      badge.append(icon(kind === "ok" ? "bi-check-lg" : "bi-x-lg"));
      nodes.push(badge);
    }
    const box = el("div");
    if (title) box.append(el("div", "feedback-title", title));
    if (text) box.append(el("div", "feedback-text", text));
    nodes.push(box);
    feedback.replaceChildren(...nodes);
  }

  function clearSay() { footer.className = "lesson-footer"; feedback.replaceChildren(); }

  function button(label, className, onClick) {
    const btn = el("button", `btn ${className || "btn-lesson"}`);
    btn.type = "button";
    if (typeof label === "string") btn.textContent = label; else btn.append(...label);
    btn.addEventListener("click", onClick);
    return btn;
  }

  function setActions(...buttons) { actions.replaceChildren(...buttons); }

  function error(err) { say("ko", "Oups", err.message || String(err)); }

  function resultBox(label, value, iconName, color) {
    const box = el("div", "result-box");
    box.style.setProperty("--c", color);
    const val = el("div", "result-box-value");
    val.append(icon(iconName), document.createTextNode(value));
    box.append(el("div", "result-box-label", label), val);
    return box;
  }

  async function finish(payload) {
    if (finished) return;
    finished = true;
    setActions();
    try {
      const r = await post(root.dataset.finishUrl, payload);
      if (r.redirect) { window.location.href = r.redirect; return; }  // ex. test de positionnement
      instruction.textContent = "Partie terminée !";
      clearSay();
      const result = el("div", "lesson-result arcade-result");
      const boxes = el("div", "result-boxes");
      boxes.append(
        resultBox("Score", `${r.score} pts`, "bi-bullseye", "#2f6fed"),
        resultBox("Points gagnés", `+${r.points}`, "bi-trophy-fill", "#e0a100"),
        resultBox("Jours d'affilée", `${r.streak} j`, "bi-fire", "#f76707"),
      );
      result.append(boxes);
      if (r.summary) result.append(el("p", "arcade-summary", r.summary));
      if (r.note) result.append(el("p", "text-muted small", r.note));
      board.replaceChildren(result);
      setStatus();
      const replay = el("a", "btn btn-outline-secondary btn-lesson-secondary", "Rejouer");
      replay.href = root.dataset.replayUrl;
      const back = el("a", "btn btn-lesson", "Retour aux jeux");
      back.href = root.dataset.homeUrl;
      setActions(replay, back);
    } catch (err) {
      finished = false;
      error(err);
    }
  }

  return { root, data, board, instruction, el, icon, post, action, statusItem, setStatus, say, clearSay,
    button, setActions, error, finish };
})();
