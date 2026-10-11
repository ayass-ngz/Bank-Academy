// Plus ou moins cher ? : la prochaine carte coûte-t-elle plus ou moins cher ?
(() => {
  const A = Arcade;
  const total = A.data.total;
  let current = A.data.current;
  let round = 0;
  let correct = 0;
  let busy = false;

  const table = A.el("div", "price-table");
  const left = A.el("div", "price-card");
  const versus = A.el("div", "price-versus", "VS");
  const right = A.el("div", "price-card is-hidden");
  table.append(left, versus, right);
  A.board.append(table);

  function fill(card, data, hidden) {
    card.replaceChildren();
    const art = A.el("span", "price-card-art");
    art.append(A.icon(hidden ? "bi-question-lg" : data.icon));
    card.append(art, A.el("span", "price-card-name", hidden ? "Carte suivante" : data.name),
      A.el("span", "price-card-price", hidden ? "? €" : data.price));
  }

  function status() {
    A.setStatus(A.statusItem("bi-layers", `Manche ${Math.min(round + 1, total)} / ${total}`),
      A.statusItem("bi-check2-circle", `${correct} bonne${correct > 1 ? "s" : ""}`));
  }

  function ready() {
    fill(left, current, false);
    right.className = "price-card is-hidden";
    fill(right, null, true);
    A.setActions(
      A.button([A.icon("bi-arrow-down"), document.createTextNode(" Moins cher")], "btn btn-lesson price-btn", () => guess("moins")),
      A.button([A.icon("bi-arrow-up"), document.createTextNode(" Plus cher")], "btn btn-lesson price-btn", () => guess("plus")),
    );
    status();
  }

  async function guess(choice) {
    if (busy) return;
    busy = true;
    A.setActions();
    try {
      const r = await A.action({ guess: choice });
      round = r.round;
      if (r.correct) correct += 1;
      right.className = `price-card is-revealed ${r.correct ? "is-ok" : "is-ko"}`;
      fill(right, r.next, false);
      A.say(r.correct ? "ok" : "ko", r.correct ? "Bien joué !" : "Raté…",
        `${r.next.name} : ${r.next.price} (contre ${current.price} pour ${current.name.toLowerCase()}).`);
      current = r.next;
      status();
      setTimeout(() => {
        busy = false;
        A.clearSay();
        if (r.done) A.finish(); else ready();
      }, 1700);
    } catch (err) {
      busy = false;
      A.error(err);
      ready();
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowUp") guess("plus");
    if (event.key === "ArrowDown") guess("moins");
  });
  ready();
})();
