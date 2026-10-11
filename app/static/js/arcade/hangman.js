// Le mot mystère : deviner le mot lettre par lettre, chaque erreur coûte une pièce.
(() => {
  const A = Arcade;
  const total = A.data.total;
  let word = A.data;
  let found = 0;
  let busy = false;
  let slots = [];
  const keys = new Map();

  const clue = A.el("div", "hm-clue");
  const slotsBox = A.el("div", "hm-slots");
  const coins = A.el("div", "hm-coins");
  const keyboard = A.el("div", "hm-keyboard");
  A.board.append(clue, slotsBox, coins, keyboard);

  "AZERTYUIOPQSDFGHJKLMWXCVBN".split("").forEach((letter) => {
    const key = A.el("button", "hm-key", letter);
    key.type = "button";
    key.addEventListener("click", () => guess(letter));
    keys.set(letter, key);
    keyboard.append(key);
  });

  function renderCoins(lives) {
    coins.replaceChildren();
    for (let i = 0; i < 6; i += 1) {
      const coin = A.el("span", `hm-coin ${i < lives ? "" : "is-lost"}`, "€");
      coins.append(coin);
    }
    coins.setAttribute("aria-label", `${lives} pièce(s) restante(s)`);
  }

  function status() {
    A.setStatus(A.statusItem("bi-incognito", `Mot ${word.index} / ${total}`), A.statusItem("bi-check2-circle", `${found} trouvé${found > 1 ? "s" : ""}`));
  }

  function load(next) {
    word = next;
    clue.replaceChildren(A.el("span", "hm-clue-label", "Définition"), document.createTextNode(next.clue));
    slots = [];
    slotsBox.replaceChildren();
    for (let i = 0; i < next.length; i += 1) {
      const slot = A.el("span", "hm-slot");
      slots.push(slot);
      slotsBox.append(slot);
    }
    keys.forEach((key) => { key.disabled = false; key.className = "hm-key"; });
    renderCoins(next.lives);
    A.clearSay();
    status();
  }

  async function guess(letter) {
    const key = keys.get(letter);
    if (busy || !key || key.disabled) return;
    busy = true;
    key.disabled = true;
    try {
      const r = await A.action({ letter });
      key.classList.add(r.positions.length ? "is-hit" : "is-miss");
      r.positions.forEach((i) => { slots[i].textContent = letter; slots[i].classList.add("is-filled"); });
      renderCoins(r.lives);
      if (r.solved || r.failed) {
        if (r.solved) found += 1;
        [...r.word].forEach((ch, i) => { if (!slots[i].textContent) { slots[i].textContent = ch; slots[i].classList.add("is-missed"); } });
        keys.forEach((k) => { k.disabled = true; });
        A.say(r.solved ? "ok" : "ko", r.solved ? "Bravo, mot trouvé !" : "Plus de pièces…", `Le mot était : ${r.word}`);
        status();
        A.setActions(A.button(r.next ? "Mot suivant" : "Voir mon score", "btn btn-lesson", () => {
          A.setActions();
          if (r.next) load(r.next); else A.finish();
        }));
      }
    } catch (err) {
      key.disabled = false;
      A.error(err);
    }
    busy = false;
  }

  document.addEventListener("keydown", (event) => {
    const letter = event.key.toUpperCase();
    if (/^[A-Z]$/.test(letter)) guess(letter);
  });
  load(word);
})();
