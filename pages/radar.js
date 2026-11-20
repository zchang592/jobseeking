// Timestamps come from the generator, which interprets announcement dates in Asia/Shanghai.
function statusFor(item, now) {
  const deadline = Number(item.dataset.deadline || Infinity);
  const starts = Number(item.dataset.starts || -Infinity);
  if (now > deadline) return "已截止";
  if (item.dataset.unverified === "true") return "待核实";
  if (now < starts) return "未开始";
  if (deadline === Infinity || item.dataset.earlyClose === "true") return "待核实";
  return "招聘中";
}

const jobs = [...document.querySelectorAll("[data-job]")];
const form = document.querySelector("#filters");
const results = document.querySelector("#job-list");
const activeCount = document.querySelector("#open-count");
const currentCount = document.querySelector("#result-count");
const noResults = document.querySelector("#no-results");

function update() {
  const now = Date.now();
  for (const job of jobs) {
    const status = statusFor(job, now);
    job.dataset.status = status;
    const badge = job.querySelector(".badge");
    badge.dataset.status = status;
    badge.textContent = status;
  }
  if (activeCount) activeCount.textContent = jobs.filter(job => job.dataset.status === "招聘中").length;
  if (!form) return;

  const terms = form.elements.namedItem("q").value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const status = form.elements.namedItem("status").value;
  const school = form.elements.namedItem("school").value;
  const stage = form.elements.namedItem("stage").value;
  let shown = 0;
  for (const job of jobs) {
    const matches = (!status || job.dataset.status === status)
      && (!school || job.dataset.school === school)
      && (!stage || job.dataset.stage === stage)
      && terms.every(term => job.dataset.search.includes(term));
    job.hidden = !matches;
    if (matches) shown++;
  }
  currentCount.textContent = "显示 " + shown + " 个岗位";
  noResults.hidden = shown > 0;
  const params = new URLSearchParams();
  for (const name of ["q", "status", "school", "stage"]) {
    const value = form.elements.namedItem(name).value;
    if (value) params.set(name, value);
  }
  const search = params.toString();
  history.replaceState(null, "", location.pathname + (search ? "?" + search : "") + location.hash);
}

if (form) {
  const initial = new URLSearchParams(location.search);
  for (const key of ["q", "status", "school", "stage"]) {
    const field = form.elements.namedItem(key);
    field.value = initial.get(key) || "";
    if (field instanceof HTMLSelectElement && field.selectedIndex < 0) field.selectedIndex = 0;
  }
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("submit", event => { event.preventDefault(); update(); });
  form.addEventListener("reset", () => requestAnimationFrame(update));
}
update();
if (jobs.length) setInterval(update, 60_000);
