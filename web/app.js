"use strict";
const el = (id) => document.getElementById(id);
const keys = [
  "title",
  "brief",
  "script",
  "url",
  "ratio",
  "seconds",
  "count",
  "framing",
  "planner",
  "brand",
  "logo",
];
let catalog = {};
function logoOptions(wanted = "auto") {
  const copy = ["title", "brief", "script", "url"]
    .map((k) => el(k).value)
    .join(" ");
  const brand =
    el("brand").value === "auto"
      ? /\borqyne\b/i.test(copy)
        ? "orqyne"
        : "orgainse"
      : el("brand").value;
  const select = el("logo");
  select.replaceChildren(
    new Option(brand === "none" ? "No logo" : "Match the background", "auto"),
  );
  for (const [id, item] of Object.entries(catalog[brand] || {}))
    select.add(new Option(id.padStart(2, "0") + " · " + item.label, id));
  select.value = catalog[brand]?.[wanted] ? wanted : "auto";
  select.disabled = brand === "none";
  select.dataset.brand = brand;
}
const files = ["media", "image", "transcript"];
let mode = "create",
  selected = "",
  assets = {},
  lastView = "",
  jobs = [],
  trim = null,
  originalUrl = "";
const textNode = (tag, value, cls) => {
  const node = document.createElement(tag);
  node.textContent = value;
  if (cls) node.className = cls;
  return node;
};
async function api(path, opts) {
  const response = await fetch(path, opts);
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error || "The local studio could not complete this request.",
    );
  return data;
}
function setMode(next, defaults = true) {
  mode = next;
  document.body.classList.toggle("shorts", next === "shorts");
  document.querySelectorAll("[data-mode]").forEach((b) => {
    const active = b.dataset.mode === mode;
    b.classList.toggle("selected", active);
    b.setAttribute("aria-pressed", String(active));
  });
  el("brieflabel").firstElementChild.textContent =
    mode === "shorts" ? "Highlight brief" : "Scene brief";
  el("brief").placeholder =
    mode === "shorts"
      ? "Find distinct moments about pricing and results. Keep each thought complete."
      : "Open with the founder, cut to the product screen, then end on the call to action.";
  el("targetlabel").textContent =
    mode === "shorts" ? "Seconds per short" : "Target seconds";
  el("submit").firstChild.textContent =
    mode === "shorts" ? "Render shorts " : "Render video ";
  if (defaults) {
    el("ratio").value = mode === "shorts" ? "9:16" : "16:9";
    trim = null;
  }
}
function monitor(url, name, ratio, poster = "") {
  const v = el("player");
  v.parentElement.style.aspectRatio = ratio.replace(":", " / ");
  if (poster) v.poster = poster;
  else v.removeAttribute("poster");
  if (url) {
    if (v.getAttribute("src") !== url) {
      v.src = url;
      v.load();
    }
    v.hidden = false;
    el("standby").hidden = true;
  } else {
    v.pause();
    v.removeAttribute("src");
    v.load();
    v.hidden = true;
    el("standby").hidden = false;
  }
  el("playername").textContent = name || "Preview";
  el("monitorformat").textContent = ratio;
}
function editor(request, cut) {
  selected = "";
  lastView = "";
  trim = cut || null;
  originalUrl = request?.url || "";
  el("form").reset();
  assets = {};
  el("error").textContent = "";
  setMode(request?.mode || "create", false);
  if (request) {
    for (const k of keys)
      if (request[k] !== undefined) el(k).value = request[k];
    for (const k of ["captions", "draft"]) el(k).checked = request[k];
    for (const k of files) if (request[k]) assets[k] = request[k];
    if (cut) el("count").value = 1;
  }
  for (const k of files) {
    const note = el(k + "-note");
    note.replaceChildren();
    if (assets[k]) {
      const clear = textNode("button", "Remove saved source", "tiny");
      clear.type = "button";
      clear.onclick = () => {
        delete assets[k];
        note.replaceChildren();
        if (k === "media") trim = null;
      };
      note.append(clear);
    }
  }
  logoOptions(request?.logo || "auto");
  el("actioninfo").textContent = trim
    ? "Source range " + trim.map((v) => v.toFixed(1) + "s").join(" – ")
    : "Saves on this PC";
  el("editor").querySelector("h1").textContent = request
    ? "Revise production"
    : "New production";
  el("editor").hidden = false;
  el("detail").hidden = true;
  monitor(null, null, el("ratio").value);
  drawNav();
  history.replaceState(null, "", location.pathname);
}
function drawNav() {
  const nav = el("jobs");
  nav.replaceChildren();
  if (!jobs.length) {
    nav.append(textNode("small", "Your saved projects appear here."));
    return;
  }
  for (const j of jobs) {
    const b = textNode(
      "button",
      "",
      "job" + (j.id === selected ? " active" : ""),
    );
    b.append(
      textNode("b", j.request.title),
      textNode("small", j.request.ratio + " · " + j.status),
    );
    b.onclick = () => show(j.id);
    nav.append(b);
  }
}
function fileLink(href, label, download = false) {
  const a = textNode("a", label);
  a.href = href;
  if (download) a.download = href.split("/").pop();
  else {
    a.target = "_blank";
    a.rel = "noopener";
  }
  return a;
}
function clock(seconds) {
  return (
    Math.floor(seconds / 60) +
    ":" +
    String(Math.floor(seconds % 60)).padStart(2, "0")
  );
}
function detail(j) {
  const signature = JSON.stringify([j.id, j.status, j.step, j.outputs]);
  if (signature === lastView) return;
  lastView = signature;
  el("editor").hidden = true;
  el("detail").hidden = false;
  el("jobtitle").textContent = j.request.title;
  el("progress").textContent = j.step;
  el("progress").className = j.status === "failed" ? "error" : "";
  el("outputs").replaceChildren();
  const base = "/api/jobs/" + j.id + "/";
  el("plan").hidden = j.status !== "done";
  el("plan").href = base + "edit-plan.json";
  el("plan").target = "_blank";
  el("revise").onclick = () => editor(j.request, j.request.trim);
  if (!j.outputs.length) {
    monitor(null, null, j.request.ratio);
    return;
  }
  for (const o of j.outputs) {
    const row = textNode("article", "", "export"),
      actions = textNode("div", "", "actions");
    row.append(
      textNode("h3", o.title || o.file),
      textNode(
        "p",
        o.width +
          " × " +
          o.height +
          " · " +
          clock(o.duration) +
          (o.start === undefined
            ? ""
            : " · Source " + clock(o.start) + "–" + clock(o.end)),
      ),
    );
    const play = textNode("button", "Preview", "secondary");
    play.onclick = () => {
      monitor(
        base + o.file,
        o.title,
        j.request.ratio,
        o.poster ? base + o.poster : "",
      );
      el("player")
        .play()
        .catch(() => {});
    };
    actions.append(play, fileLink(base + o.file, "Save MP4", true));
    if (o.subtitles)
      actions.append(fileLink(base + o.subtitles, "Subtitles", true));
    if (o.start !== undefined) {
      const trimButton = textNode("button", "Adjust cut", "secondary");
      trimButton.onclick = () => {
        const range = prompt(
          "Enter source start and end in seconds, separated by a comma.",
          o.start.toFixed(2) + ", " + o.end.toFixed(2),
        );
        if (range === null) return;
        const vals = range
          .split(",")
          .map((x) => (x.trim() === "" ? NaN : Number(x)));
        if (
          vals.length !== 2 ||
          !vals.every(Number.isFinite) ||
          vals[0] < 0 ||
          vals[1] <= vals[0]
        ) {
          alert("Enter a valid source range.");
          return;
        }
        editor({ ...j.request, title: o.title }, vals);
      };
      actions.append(trimButton);
    }
    row.append(actions);
    el("outputs").append(row);
  }
  const first = j.outputs[0];
  monitor(
    base + first.file,
    first.title,
    j.request.ratio,
    first.poster ? base + first.poster : "",
  );
}
async function show(id) {
  selected = id;
  lastView = "";
  location.hash = id;
  drawNav();
  const cached = jobs.find((j) => j.id === id);
  if (cached) detail(cached);
  else {
    const j = await api("/api/jobs/" + id);
    if (selected === id) detail(j);
  }
}
async function refresh() {
  try {
    jobs = await api("/api/jobs");
    drawNav();
    const j = jobs.find((j) => j.id === selected);
    if (j) detail(j);
  } catch {
    el("runtime").textContent = "Studio disconnected";
  }
}
el("form").onsubmit = async (event) => {
  event.preventDefault();
  el("error").textContent = "";
  el("submit").disabled = true;
  try {
    const req = { mode };
    for (const id of keys) req[id] = el(id).value;
    req.seconds = Number(req.seconds);
    req.count = Number(req.count);
    for (const key of ["captions", "draft"]) req[key] = el(key).checked;
    if (req.url !== originalUrl && !el("image").files.length)
      delete assets.image;
    if (el("media").files.length && !el("transcript").files.length) {
      delete assets.transcript;
      trim = null;
    }
    for (const key of files) {
      const file = el(key).files[0];
      if (file) {
        el("actioninfo").textContent = "Saving " + file.name + " on this PC…";
        const ext = file.name.match(/\.[a-z0-9]+$/i)?.[0] || "";
        const uploaded = await api("/api/assets", {
          method: "POST",
          headers: { "X-Orgainse-Studio": "1", "X-File-Extension": ext },
          body: file,
        });
        assets[key] = uploaded.asset;
      }
      req[key] = assets[key] || "";
    }
    if (trim && mode === "shorts") req.trim = trim;
    const j = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Orgainse-Studio": "1" },
      body: JSON.stringify(req),
    });
    jobs.unshift(j);
    await show(j.id);
  } catch (e) {
    el("error").textContent = e.message;
  } finally {
    el("submit").disabled = false;
    el("actioninfo").textContent = "Saves on this PC";
  }
};
document
  .querySelectorAll("[data-mode]")
  .forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
el("new").onclick = () => editor();
el("brand").onchange = () => logoOptions();
for (const key of ["title", "brief", "script", "url"])
  el(key).addEventListener("input", () => {
    if (el("brand").value !== "auto") return;
    const previous = el("logo").dataset.brand;
    logoOptions(el("logo").value);
    if (el("logo").dataset.brand !== previous) el("logo").value = "auto";
  });
el("ratio").onchange = () =>
  (el("monitorformat").textContent = el("ratio").value);
for (const key of files)
  el(key).onchange = () => {
    if (el(key).files.length) el(key + "-note").textContent = "";
  };
(async () => {
  try {
    catalog = await api("/brand/catalog.json");
    logoOptions(el("logo").value);
    const status = await api("/api/status");
    el("runtime").textContent = "Local workstation";
    for (const [key, name] of Object.entries({
      ffmpeg: "FFmpeg renderer",
      speech: "Speech recognition",
      planner: "Scene planner",
      browser: "Website capture",
    })) {
      const li = textNode("li", name);
      li.append(textNode("span", status[key] ? "Ready" : "Setup needed"));
      el("tools").append(li);
    }
    await refresh();
    if (/^[a-f0-9]{32}$/.test(location.hash.slice(1)))
      await show(location.hash.slice(1));
    setInterval(refresh, 2200);
  } catch (e) {
    el("error").textContent = e.message;
  }
})();
