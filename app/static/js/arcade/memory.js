// Memory des notions : associer chaque notion à sa définition.
(() => {
  const A = Arcade;
  const { count, pairs } = A.data;
  const grid = A.el("div", "memory-grid");
  const cards = [];
  let first = null;
  let busy = false;
  let found = 0;
  let attempts = 0;

  function status() {
    A.setStatus(A.statusItem("bi-collection", `${found} / ${pairs} paires`), A.statusItem("bi-arrow-repeat", `${attempts} essais`));
  }

  function show(i, face) {
    const card = cards[i];
    card.querySelector(".memory-back").textContent = face.text;
    card.classList.toggle("is-definition", face.kind === "definition");
    card.classList.add("is-flipped");
  }

  function hide(i) { cards[i].classList.remove("is-flipped"); }

  async function flip(i) {
    const card = cards[i];
    if (busy || card.classList.contains("is-matched") || i === first) return;
    busy = true;
    try {
      const r = await A.action({ flip: i });
      show(i, r.face);
      if (r.other === undefined) {
        first = i;
        busy = false;
        return;
      }
      attempts = r.attempts;
      const other = r.other;
      first = null;
      if (r.match) {
        found += 1;
        cards[i].classList.add("is-matched");
        cards[other].classList.add("is-matched");
        A.say("ok", "Bien vu, c'est une paire !",
          `${cards[other].querySelector(".memory-back").textContent} ↔ ${r.face.text}`);
        busy = false;
      } else {
        A.say("ko", "Ce n'est pas une paire", "Mémorise bien l'emplacement des cartes.");
        setTimeout(() => { hide(i); hide(other); busy = false; }, 1200);
      }
      status();
      if (r.done) setTimeout(() => A.finish(), 900);
    } catch (err) {
      busy = false;
      A.error(err);
    }
  }

  for (let i = 0; i < count; i += 1) {
    const card = A.el("button", "memory-card");
    card.type = "button";
    card.setAttribute("aria-label", `Carte ${i + 1}`);
    const inner = A.el("span", "memory-inner");
    const front = A.el("span", "memory-front");
    front.append(A.icon("bi-mortarboard-fill"));
    inner.append(front, A.el("span", "memory-back"));
    card.append(inner);
    card.addEventListener("click", () => flip(i));
    cards.push(card);
    grid.append(card);
  }
  A.board.append(grid);
  A.setActions(A.button("Terminer la partie", "btn btn-outline-secondary", () => A.finish()));
  status();
})();
