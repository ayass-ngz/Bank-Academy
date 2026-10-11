// Mots mêlés : cliquer la première puis la dernière lettre d'un mot.
(() => {
  const A = Arcade;
  const { size, grid: letters, words } = A.data;
  const cells = [];
  const found = new Set();
  let start = null;
  let busy = false;
  let colorIndex = 0;

  const layout = A.el("div", "ws-layout");
  const grid = A.el("div", "ws-grid");
  grid.style.setProperty("--size", size);
  const list = A.el("ul", "ws-words");
  const items = new Map();

  letters.forEach((row, r) => {
    cells.push([]);
    [...row].forEach((letter, c) => {
      const cell = A.el("button", "ws-cell", letter);
      cell.type = "button";
      cell.addEventListener("click", () => pick(r, c));
      grid.append(cell);
      cells[r].push(cell);
    });
  });
  words.forEach((word) => {
    const item = A.el("li", "ws-word", word);
    items.set(word, item);
    list.append(item);
  });
  layout.append(grid, list);
  A.board.append(layout);

  function status() {
    A.setStatus(A.statusItem("bi-search", `${found.size} / ${words.length} mots`));
  }

  function clearStart() {
    if (start) cells[start[0]][start[1]].classList.remove("is-start");
    start = null;
  }

  async function pick(r, c) {
    if (busy) return;
    if (!start) {
      start = [r, c];
      cells[r][c].classList.add("is-start");
      return;
    }
    if (start[0] === r && start[1] === c) { clearStart(); return; }
    busy = true;
    try {
      const res = await A.action({ select: [start, [r, c]] });
      if (res.found) {
        found.add(res.found);
        colorIndex = (colorIndex + 1) % 6;
        res.cells.forEach(([a, b]) => cells[a][b].classList.add("is-found", `c${colorIndex}`));
        items.get(res.found).classList.add("is-found");
        A.say("ok", `Trouvé : ${res.found} !`, "");
        status();
        if (res.done) setTimeout(() => A.finish(), 800);
      } else {
        A.say("ko", "Pas de mot ici", "Clique sur la première puis la dernière lettre d'un mot de la liste.");
        cells[r][c].classList.add("is-miss");
        setTimeout(() => cells[r][c].classList.remove("is-miss"), 500);
      }
    } catch (err) {
      A.error(err);
    }
    clearStart();
    busy = false;
  }

  A.setActions(A.button("Terminer la partie", "btn btn-outline-secondary", () => A.finish()));
  status();
})();
