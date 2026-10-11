// Bourse junior : répartir son argent entre plusieurs placements, trimestre après trimestre.
(() => {
  const A = Arcade;
  const d = A.data;
  let value = d.value;
  let turn = d.turn;
  let busy = false;
  const alloc = d.assets.map((_, i) => (i === 0 ? 100 : 0));
  const history = [value];

  const euros = (v) => `${Math.round(v).toLocaleString("fr-FR")} €`;
  const news = A.el("div", "stock-news");
  const assetsBox = A.el("div", "stock-assets");
  const footerInfo = A.el("div", "stock-info");
  A.board.append(news, assetsBox, footerInfo);

  const sliders = [];
  d.assets.forEach((asset, i) => {
    const card = A.el("div", "stock-asset");
    const head = A.el("div", "stock-asset-head");
    const art = A.el("span", "stock-asset-icon");
    art.append(A.icon(asset.icon));
    const title = A.el("div", "min-w-0");
    title.append(A.el("div", "stock-asset-name", asset.name), A.el("div", "stock-asset-sector", asset.sector));
    head.append(art, title, A.el("span", `stock-risk risk-${asset.risk.toLowerCase()}`, `Risque : ${asset.risk}`));
    const slider = A.el("input", "form-range");
    slider.type = "range";
    slider.min = 0; slider.max = 100; slider.step = 5;
    slider.value = alloc[i];
    slider.setAttribute("aria-label", `Part placée sur ${asset.name}`);
    const pct = A.el("span", "stock-pct", `${alloc[i]} %`);
    const result = A.el("span", "stock-result");
    slider.addEventListener("input", () => { alloc[i] = +slider.value; pct.textContent = `${alloc[i]} %`; refresh(); });
    const row = A.el("div", "stock-asset-row");
    row.append(slider, pct);
    card.append(head, row, result);
    sliders.push({ slider, pct, result });
    assetsBox.append(card);
  });

  function setNews(text) {
    news.replaceChildren(A.el("span", "stock-news-label", `Actu du trimestre ${turn}`), document.createTextNode(text));
  }

  function refresh() {
    const sum = alloc.reduce((a, b) => a + b, 0);
    footerInfo.replaceChildren(
      A.el("span", `stock-sum ${sum === 100 ? "is-ok" : "is-ko"}`, `Total réparti : ${sum} %${sum === 100 ? "" : " (il faut 100 %)"}`),
      A.el("span", "stock-history", `Évolution : ${history.map(euros).join(" → ")}`),
    );
    A.setStatus(A.statusItem("bi-calendar3", `Trimestre ${Math.min(turn, d.turns)} / ${d.turns}`), A.statusItem("bi-wallet2", euros(value)));
    invest.disabled = sum !== 100 || busy;
  }

  function preset(values) {
    values.forEach((v, i) => { alloc[i] = v; sliders[i].slider.value = v; sliders[i].pct.textContent = `${v} %`; });
    refresh();
  }

  async function play() {
    busy = true;
    refresh();
    sliders.forEach((s) => { s.slider.disabled = true; });
    try {
      const r = await A.action({ allocation: alloc.slice() });
      value = r.value;
      turn = r.turn;
      history.push(value);
      r.returns.forEach((ret, i) => {
        sliders[i].result.textContent = `${ret >= 0 ? "+" : ""}${ret.toLocaleString("fr-FR")} %`;
        sliders[i].result.className = `stock-result ${ret >= 0 ? "up" : "down"}`;
      });
      const up = r.portfolio >= 0;
      A.say(up ? "ok" : "ko", `${up ? "+" : ""}${r.portfolio.toLocaleString("fr-FR")} % ce trimestre`,
        `Ton portefeuille vaut maintenant ${euros(value)}.`);
      A.setActions(A.button(r.done ? "Voir mon bilan" : "Trimestre suivant", "btn btn-lesson", () => {
        if (r.done) { A.finish(); return; }
        busy = false;
        sliders.forEach((s) => { s.slider.disabled = false; s.result.textContent = ""; });
        setNews(r.news);
        A.clearSay();
        A.setActions(...controls());
        refresh();
      }));
      refresh();
    } catch (err) {
      busy = false;
      sliders.forEach((s) => { s.slider.disabled = false; });
      A.error(err);
      refresh();
    }
  }

  const invest = A.button("Investir pour ce trimestre", "btn btn-lesson", play);
  const controls = () => [
    A.button("Tout sur le livret", "btn btn-outline-secondary btn-sm", () => preset([100, 0, 0, 0])),
    A.button("Équilibré (25 % partout)", "btn btn-outline-secondary btn-sm", () => preset([25, 25, 25, 25])),
    invest,
  ];
  setNews(d.news);
  A.setActions(...controls());
  refresh();
})();
