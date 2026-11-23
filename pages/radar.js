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
const aliases = {
  "音乐": ["音乐", "music"],
  "music": ["音乐", "music"],
  "中学": ["中学", "中小学", "初中", "高中", "secondary", "middle school", "high school"],
  "高中": ["高中", "高级中学", "high school", "senior school"],
  "初中": ["初中", "初级中学", "middle school"],
  "国际学校": ["国际学校", "双语学校", "international school", "bilingual school"],
  "双语": ["双语", "bilingual"],
  "bilingual": ["双语", "bilingual"],
};

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
  const category = form.elements.namedItem("category").value;
  const school = form.elements.namedItem("school").value;
  const stage = form.elements.namedItem("stage").value;
  let shown = 0;
  for (const job of jobs) {
    const matches = (category === "all" || job.dataset.category === category)
      && (!status || job.dataset.status === status)
      && (!school || job.dataset.school === school)
      && (!stage || job.dataset.stage === stage)
      && terms.every(term => (aliases[term] || [term]).some(word => job.dataset.search.includes(word)));
    job.hidden = !matches;
    if (matches) shown++;
  }
  currentCount.textContent = "显示 " + shown + " 个岗位";
  for (const tab of document.querySelectorAll("[data-category-link]")) {
    if (tab.dataset.categoryLink === category) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  noResults.hidden = shown > 0;
  const params = new URLSearchParams();
  for (const name of ["q", "status", "school", "stage", "category"]) {
    const value = form.elements.namedItem(name).value;
    if (value) params.set(name, value);
  }
  const search = params.toString();
  history.replaceState(null, "", location.pathname + (search ? "?" + search : "") + location.hash);
}

if (form) {
  const initial = new URLSearchParams(location.search);
  for (const key of ["q", "status", "school", "stage", "category"]) {
    const field = form.elements.namedItem(key);
    field.value = initial.get(key) || (key === "category" ? "secondary" : "");
    if (field instanceof HTMLSelectElement && field.selectedIndex < 0) field.selectedIndex = 0;
  }
  for (const tab of document.querySelectorAll("[data-category-link]")) {
    tab.addEventListener("click", event => {
      event.preventDefault();
      form.elements.namedItem("category").value = tab.dataset.categoryLink;
      update();
    });
  }
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("submit", event => { event.preventDefault(); update(); });
  form.addEventListener("reset", () => requestAnimationFrame(() => {
    form.elements.namedItem("category").value = "secondary";
    update();
  }));
}
update();
if (jobs.length) setInterval(update, 60_000);
