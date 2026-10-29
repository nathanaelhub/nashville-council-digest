// Filter the items on a page by topic and district; hide groups left empty.
const form = document.getElementById("filters");
if (form) {
  const cards = [...document.querySelectorAll("article.item")];
  const shown = document.getElementById("shown");
  const apply = () => {
    const topic = form.topic.value;
    const district = form.district ? form.district.value : "";
    let n = 0;
    for (const c of cards) {
      const ok = (!topic || c.dataset.topic === topic) &&
        (!district || c.dataset.districts.split(" ").includes(district));
      c.hidden = !ok;
      if (ok) n++;
    }
    for (const g of document.querySelectorAll("section.group")) {
      g.hidden = !g.querySelector("article.item:not([hidden])");
    }
    shown.textContent = topic || district ? `Showing ${n} of ${cards.length}` : "";
  };
  form.addEventListener("change", apply);
  form.addEventListener("submit", (ev) => ev.preventDefault());
  if (form.district && form.district.options.length <= 1) form.district.closest("label").hidden = true;
}
