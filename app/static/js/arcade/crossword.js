// Mots croisés : grille générée par le serveur, vérifiée à la fin (ou indice payant).
(() => {
  const A = Arcade;
  const { rows, cols, blocks, numbers, words } = A.data;
  const inputs = [];          // inputs[r][c]
  const cellWords = [];       // cellWords[r][c] = { A: word, D: word }
  let dir = "A";
  let active = null;          // mot actif
  let hints = 0;

  const layout = A.el("div", "cw-layout");
  const grid = A.el("div", "cw-grid");
  grid.style.setProperty("--cols", cols);
  const cluesBox = A.el("div", "cw-clues");

  for (let r = 0; r < rows; r += 1) {
    inputs.push([]);
    cellWords.push([]);
    for (let c = 0; c < cols; c += 1) {
      cellWords[r].push({});
      if (blocks[r][c]) {
        grid.append(A.el("div", "cw-block"));
        inputs[r].push(null);
        continue;
      }
      const cell = A.el("label", "cw-cell");
      if (numbers[r][c]) cell.append(A.el("span", "cw-num", numbers[r][c]));
      const input = A.el("input", "cw-input");
      input.maxLength = 1;
      input.autocomplete = "off";
      input.setAttribute("autocapitalize", "characters");
      input.setAttribute("aria-label", `Case ligne ${r + 1}, colonne ${c + 1}`);
      input.dataset.r = r;
      input.dataset.c = c;
      cell.append(input);
      grid.append(cell);
      inputs[r].push(input);
    }
  }
  words.forEach((w) => w.cells.forEach(([r, c]) => { cellWords[r][c][w.dir] = w; }));

  // Définitions
  const clueItems = new Map();
  [["A", "Horizontalement", "bi-arrow-right"], ["D", "Verticalement", "bi-arrow-down"]].forEach(([d, label, ic]) => {
    const block = A.el("div", "cw-clue-block");
    const title = A.el("div", "cw-clue-title");
    title.append(A.icon(ic), document.createTextNode(` ${label}`));
    const list = A.el("ol", "cw-clue-list");
    words.filter((w) => w.dir === d).forEach((w) => {
      const item = A.el("li", "cw-clue");
      item.append(A.el("strong", null, `${w.num}. `), document.createTextNode(`${w.clue} (${w.len})`));
      item.addEventListener("click", () => focusWord(w));
      clueItems.set(w, item);
      list.append(item);
    });
    block.append(title, list);
    cluesBox.append(block);
  });
  layout.append(grid, cluesBox);
  A.board.append(layout);

  function highlight(word) {
    active = word;
    grid.querySelectorAll(".is-word").forEach((n) => n.classList.remove("is-word"));
    clueItems.forEach((item) => item.classList.remove("is-active"));
    if (!word) return;
    word.cells.forEach(([r, c]) => inputs[r][c].parentElement.classList.add("is-word"));
    clueItems.get(word).classList.add("is-active");
    A.say(null, `${word.num}. ${word.dir === "A" ? "Horizontal" : "Vertical"}`, word.clue);
  }

  function focusWord(word) {
    dir = word.dir;
    const target = word.cells.find(([r, c]) => !inputs[r][c].value) || word.cells[0];
    inputs[target[0]][target[1]].focus();
  }

  function onFocus(input) {
    const words = cellWords[input.dataset.r][input.dataset.c];
    if (!words[dir]) dir = dir === "A" ? "D" : "A";
    highlight(words[dir]);
  }

  function move(input, step) {
    if (!active) return;
    const idx = active.cells.findIndex(([r, c]) => r === +input.dataset.r && c === +input.dataset.c);
    const next = active.cells[idx + step];
    if (next) inputs[next[0]][next[1]].focus();
  }

  grid.addEventListener("focusin", (e) => { if (e.target.matches(".cw-input")) onFocus(e.target); });
  grid.addEventListener("click", (e) => {
    const input = e.target.closest(".cw-cell")?.querySelector(".cw-input");
    if (input && document.activeElement === input && cellWords[input.dataset.r][input.dataset.c][dir === "A" ? "D" : "A"]) {
      dir = dir === "A" ? "D" : "A";   // second clic : on change de sens
      onFocus(input);
    }
  });
  grid.addEventListener("input", (e) => {
    const input = e.target;
    input.value = input.value.toUpperCase().replace(/[^A-Z]/g, "").slice(-1);
    if (input.value) move(input, 1);
    progress();
  });
  grid.addEventListener("keydown", (e) => {
    const input = e.target;
    if (!input.matches(".cw-input")) return;
    const r = +input.dataset.r;
    const c = +input.dataset.c;
    const go = (dr, dc) => {
      e.preventDefault();
      let nr = r + dr;
      let nc = c + dc;
      while (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
        if (inputs[nr][nc]) { inputs[nr][nc].focus(); return; }
        nr += dr; nc += dc;
      }
    };
    if (e.key === "Backspace" && !input.value) { e.preventDefault(); move(input, -1); }
    else if (e.key === "ArrowRight") { dir = "A"; go(0, 1); }
    else if (e.key === "ArrowLeft") { dir = "A"; go(0, -1); }
    else if (e.key === "ArrowDown") { dir = "D"; go(1, 0); }
    else if (e.key === "ArrowUp") { dir = "D"; go(-1, 0); }
  });

  function progress() {
    const filled = words.filter((w) => w.cells.every(([r, c]) => inputs[r][c].value)).length;
    A.setStatus(A.statusItem("bi-grid-3x3", `${filled} / ${words.length} mots remplis`),
      A.statusItem("bi-lightbulb", `${hints} indice${hints > 1 ? "s" : ""}`));
  }

  async function hint() {
    const input = document.activeElement && document.activeElement.matches(".cw-input") ? document.activeElement : null;
    const target = input || (active && active.cells.map(([r, c]) => inputs[r][c]).find((i) => !i.value));
    if (!target) { A.say(null, "Indice", "Clique d'abord sur une case de la grille."); return; }
    try {
      const r = await A.action({ hint: [+target.dataset.r, +target.dataset.c] });
      hints = r.hints;
      target.value = r.letter;
      target.readOnly = true;
      target.parentElement.classList.add("is-hint");
      move(target, 1);
      progress();
    } catch (err) { A.error(err); }
  }

  function validate() {
    const empty = inputs.flat().filter((i) => i && !i.value).length;
    if (empty && !window.confirm(`Il reste ${empty} case(s) vide(s). Valider quand même ?`)) return;
    A.finish({ grid: inputs.map((row) => row.map((i) => (i ? i.value : ""))) });
  }

  A.setActions(
    A.button([A.icon("bi-lightbulb"), document.createTextNode(" Indice (−5 pts)")], "btn btn-outline-secondary", hint),
    A.button("Valider la grille", "btn btn-lesson", validate),
  );
  progress();
  focusWord(words[0]);
})();
