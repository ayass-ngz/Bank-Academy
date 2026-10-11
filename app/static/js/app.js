// Confirmation des formulaires de suppression
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
  }
});

// Formulaire admin de création de compte : la date de naissance ne concerne que les clients
document.querySelectorAll("[data-toggle-birth]").forEach((select) => {
  const row = document.getElementById("birth-row");
  const update = () => { row.hidden = select.value !== "client"; };
  select.addEventListener("change", update);
  update();
});

// Parcours : à l'ouverture, on fait défiler jusqu'à l'étape en cours
(() => {
  const current = document.querySelector(".track-step.state-current:not(.is-milestone)")
    || document.querySelector(".track-step.state-current");
  if (current) current.scrollIntoView({ block: "center" });
})();

// Hub des jeux : filtre par catégorie
document.querySelectorAll("[data-game-filter]").forEach((chip) => {
  chip.addEventListener("click", (event) => {
    event.preventDefault();
    const category = chip.dataset.gameFilter;
    document.querySelectorAll("[data-game-filter]").forEach((c) => c.classList.toggle("active", c === chip));
    document.querySelectorAll("[data-game-group]").forEach((group) => {
      group.hidden = Boolean(category) && group.dataset.gameGroup !== category;
    });
  });
});

// Éditeur de fiches (banque) : affiche les champs propres au type choisi
document.querySelectorAll("[data-card-kind]").forEach((select) => {
  const form = select.closest("form");
  const update = () => {
    form.querySelectorAll("[data-kind]").forEach((block) => {
      block.hidden = !block.dataset.kind.split(" ").includes(select.value);
    });
  };
  select.addEventListener("change", update);
  update();
});
