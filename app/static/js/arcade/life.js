// La vie en euros : un choix par mois, trouver l'équilibre entre argent et bien-être.
(() => {
  const A = Arcade;
  const d = A.data;
  let money = d.money;
  let wellbeing = d.wellbeing;
  let month = d.month;
  let busy = false;

  const euros = (v) => `${v.toLocaleString("fr-FR")} €`;
  const top = A.el("div", "life-top");
  const moneyBox = A.el("div", "life-stat");
  const wellBox = A.el("div", "life-stat");
  top.append(moneyBox, wellBox);
  const budgetLine = A.el("p", "life-budget");
  budgetLine.textContent = `Chaque mois : +${euros(d.income)} (${d.income_label})` +
    (d.fixed ? ` − ${euros(d.fixed)} (${d.fixed_label})` : "");
  const card = A.el("div", "life-event");
  A.board.append(top, budgetLine, card);

  function renderStats(deltaMoney, deltaWell) {
    moneyBox.replaceChildren(A.el("span", "life-stat-label", "Mon argent"),
      A.el("span", `life-stat-value ${money < 0 ? "is-negative" : ""}`, euros(money)));
    if (deltaMoney) moneyBox.append(A.el("span", `life-delta ${deltaMoney > 0 ? "up" : "down"}`, `${deltaMoney > 0 ? "+" : ""}${euros(deltaMoney)}`));
    const gauge = A.el("span", "life-gauge");
    for (let i = 0; i < 10; i += 1) gauge.append(A.el("span", i < wellbeing ? "on" : ""));
    wellBox.replaceChildren(A.el("span", "life-stat-label", "Mon bien-être"), gauge);
    if (deltaWell) wellBox.append(A.el("span", `life-delta ${deltaWell > 0 ? "up" : "down"}`, `${deltaWell > 0 ? "+" : ""}${deltaWell}`));
    A.setStatus(A.statusItem("bi-calendar3", `Mois ${Math.min(month, d.months)} / ${d.months}`));
  }

  function renderEvent(event) {
    card.replaceChildren(A.el("div", "life-event-kicker", `Mois ${month}`), A.el("div", "life-event-text", event.text));
    const options = A.el("div", "life-options");
    event.options.forEach((label, i) => {
      const btn = A.el("button", "choice", label);
      btn.type = "button";
      btn.addEventListener("click", () => choose(i, btn));
      options.append(btn);
    });
    card.append(options);
    A.clearSay();
    A.setActions();
  }

  async function choose(i, btn) {
    if (busy) return;
    busy = true;
    card.querySelectorAll(".choice").forEach((b) => { b.disabled = true; });
    btn.classList.add("selected");
    try {
      const r = await A.action({ choice: i });
      money = r.money;
      wellbeing = r.wellbeing;
      month = r.month;
      renderStats(r.delta_money, r.delta_wellbeing);
      const good = r.delta_wellbeing >= 0 && r.delta_money >= -0.5 * d.income;
      A.say(good ? "ok" : "ko", good ? "Bon choix" : "À méditer…", r.lesson);
      A.setActions(A.button(r.done ? "Voir mon bilan" : "Mois suivant", "btn btn-lesson", () => {
        if (r.done) A.finish(); else renderEvent(r.event);
      }));
    } catch (err) {
      A.error(err);
      card.querySelectorAll(".choice").forEach((b) => { b.disabled = false; });
    }
    busy = false;
  }

  renderStats(0, 0);
  renderEvent(d.event);
})();
