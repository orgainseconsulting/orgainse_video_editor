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
  "treatment",
  "captionStyle",
  "voice",
  "scriptStyle",
];
let catalog = {};
let library = [], projectLayers = [], targetScene = null, libraryKind = "graphic";
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
const files = ["media", "image", "transcript", "narration", "music"];
let storyboard = [];
function showBoard() {
  const enabled = el("useScenes").checked;
  el("sceneTools").hidden = !enabled;
  el("script").disabled = enabled;
  if (!enabled) return;
  const list = el("sceneList");
  list.replaceChildren();
  storyboard.forEach((s, i) => {
    const row = document.createElement("fieldset");
    row.append(textNode("legend", "Scene " + (i + 1)));
    function field(key, label, choices) {
      const wrap = textNode("label", label);
      const input = document.createElement(
        choices ? "select" : key === "voice" ? "textarea" : "input",
      );
      if (choices) for (const [v, l] of choices) input.add(new Option(l, v));
      if (key === "start" || key === "seconds") {
        input.type = "number";
        input.step = "any";
        input.min = key === "start" ? "0" : "0.034";
      }
      input.value = s[key] ?? "";
      input.oninput = () => {
        s[key] = input.type === "number" ? Number(input.value) : input.value;
        if (key === "graphic") showBoard();
        if (key === "visual") {
          if (s.visual === "graphic" && !s.graphic) s.graphic = library.find(x => x.kind === "graphic")?.id;
          showBoard();
        }
      };
      wrap.append(input);
      row.append(wrap);
    }
    field("visual", "Visual", [
      ["title", "Title card"],
      ["website", "Product screen"],
      ["footage", "Source recording"],
      ["graphic", "Motion scene"],
    ]);
    if (s.visual === "graphic") {
      field("graphic", "Composition", library.filter(x => x.kind === "graphic").map(x => [x.id, x.name]));
      if (library.find(x => x.id === s.graphic)?.editable) field("subhead", "Supporting line");
    }
    field("headline", "On-screen text");
    field("voice", "Narration");
    field("start", "Source start (seconds)");
    field("seconds", "Scene seconds");
    field("motion", "Motion", [
      ["still", "Still"],
      ["push-in", "Push in"],
      ["pull-back", "Pull back"],
    ]);
    for (const [key, saved, name] of [
      ["upload", "image", "Scene image"],
      ["mobileUpload", "portraitImage", "Portrait image"],
    ]) {
      const label = textNode(
        "label",
        s[saved] || s[key] ? "Replace " + name.toLowerCase() : name,
      );
      const file = document.createElement("input");
      file.type = "file";
      file.accept = ".png,.jpg,.jpeg,.webp";
      file.onchange = () => {
        if (file.files[0]) {
          s[key] = file.files[0];
          if (s.visual !== "graphic") s.visual = "website";
          showBoard();
        }
      };
      label.append(file);
      row.append(label);
    }
    const actions = textNode("div", "", "actions");
    function action(name, fn, disabled) {
      const b = textNode("button", name, "secondary");
      b.type = "button";
      b.disabled = disabled;
      b.onclick = () => {
        fn();
        showBoard();
      };
      actions.append(b);
    }
    action(
      "Move up",
      () => {
        [storyboard[i - 1], storyboard[i]] = [s, storyboard[i - 1]];
      },
      i === 0,
    );
    action(
      "Move down",
      () => {
        [storyboard[i + 1], storyboard[i]] = [s, storyboard[i + 1]];
      },
      i === storyboard.length - 1,
    );
    action("Remove", () => storyboard.splice(i, 1), false);
    const fx = document.createElement("div");
    fx.className = "scene-fx";
    drawLayers(fx, s.effects ||= [], true);
    row.append(fx);
    action("Browse scene effects", () => openLibrary(s, "effect"), false);
    row.append(actions);
    list.append(row);
  });
}
function drawLayers(container, layers, timed) {
  container.replaceChildren();
  for (const [i, layer] of layers.entries()) {
    const group = document.createElement("div");
    group.className = "effect-layer";
    group.append(textNode("strong", library.find(item => item.id === layer.id)?.name || layer.id));
    const info = library.find(item => item.id === layer.id);
    if (info?.looks?.length) {
      const label = textNode("label","Look");
      const select = document.createElement("select");
      select.add(new Option("Original",""));
      for (const look of info.looks) select.add(new Option(look,look));
      select.value = layer.look || "";
      select.onchange = () => {layer.look = select.value;};
      label.append(select); group.append(label);
    }
    if (info?.cardImages) {
      const label = textNode("label",layer.cards?.length || layer.uploads?.length ? "Replace card images" : "Card images");
      const file = document.createElement("input");
      file.type = "file";file.multiple = true;file.accept = ".png,.jpg,.jpeg,.webp";
      file.onchange = () => {layer.uploads = Array.from(file.files);};
      label.append(file);group.append(label);
    }
    const options = timed ? [["text","Effect text"],["from","Start (s)"],["to","End (s)"]] : [["text","Effect text"]];
    for (const [key,label] of options) {
      const field = textNode("label", label);
      const input = document.createElement("input");
      input.type = key === "text" ? "text" : "number";
      input.placeholder = key === "text" ? "Use preset" : (key === "from" ? "0" : "Scene end");
      input.maxLength = 160;
      input.step = "any";
      input.min = "0";
      input.value = layer[key] ?? "";
      input.oninput = () => {
        if (!input.value) delete layer[key];
        else layer[key] = key === "text" ? input.value : Number(input.value);
      };
      field.append(input);
      group.append(field);
    }
    for (const label of ["Earlier","Remove"]) {
      if (label === "Earlier" && i === 0) continue;
      const btn = textNode("button",label,"secondary");
      btn.type = "button";
      btn.onclick = () => {
        if (label === "Earlier") [layers[i-1],layers[i]] = [layers[i],layers[i-1]];
        else layers.splice(i,1);
        drawLayers(container,layers,timed);
      };
      group.append(btn);
    }
    container.append(group);
  }
}
function libraryTab(kind) {
  libraryKind = kind;
  for (const b of document.querySelectorAll("[data-kind]")) {
    b.setAttribute("aria-pressed", String(b.dataset.kind === kind));
    b.disabled = mode === "shorts" && b.dataset.kind === "graphic";
  }
  const group = el("libraryGroup");
  group.replaceChildren(new Option("All categories",""));
  for (const g of new Set(library.filter(x => x.kind === kind).map(x => x.group))) group.add(new Option(g,g));
  el("librarySearch").value = "";
  drawLibrary();
}
function openLibrary(scene, kind) {
  targetScene = scene;
  libraryTab(kind);
  el("libraryDialog").showModal();
  el("librarySearch").focus();
}
function applyItem(item) {
  if (item.kind === "caption") {
    el("captionStyle").value = item.id;
    el("captions").checked = true;
    el("settings").open = true;
  } else if (item.kind === "effect") {
    const dest = targetScene ? (targetScene.effects ||= []) : projectLayers;
    if (dest.length >= 12) {el("libraryCount").textContent = "Twelve layers already selected."; return;}
    dest.push({id:item.id});
    drawLayers(el("projectLayers"),projectLayers,false);
    showBoard();
  } else {
    const scene = targetScene || newScene();
    scene.visual = "graphic";
    scene.graphic = item.id;
    if (!targetScene) {
      scene.seconds = Number((item.frames / 30).toFixed(2));
      storyboard.push(scene);
    }
    el("storyboard").open = true;
    el("useScenes").checked = true;
    el("fullLength").checked = false;
    showBoard();
  }
  el("libraryDialog").close();
}
function drawLibrary() {
  const query = el("librarySearch").value.trim().toLowerCase();
  const group = el("libraryGroup").value;
  const entries = library.filter(x => x.kind === libraryKind && (!group || x.group === group) &&
    [x.name,x.id,x.group,x.recipe,x.description].join(" ").toLowerCase().includes(query));
  const action = libraryKind === "guide" ? "Read guide" : libraryKind === "graphic" ? (targetScene ? "Replace scene" : "Add as scene") :
    libraryKind === "caption" ? "Use caption style" : (targetScene ? "Apply to scene" : "Apply to production");
  el("libraryCount").textContent = entries.length + " results · " + action;
  const grid = el("libraryItems");
  grid.replaceChildren();
  for (const item of entries) {
    if (item.kind === "guide") {
      const link = textNode("a","","library-card guide-card");
      link.href = "/guides/" + item.id;
      link.target = "_blank";
      link.rel = "noopener";
      link.append(textNode("strong", item.name), textNode("small", item.group));
      grid.append(link);
      continue;
    }
    const btn = textNode("button","","library-card");
    btn.type = "button";
    btn.setAttribute("aria-label", action + " · " + item.name);
    const pic = document.createElement("img");
    pic.src = "/previews/" + encodeURIComponent(item.id) + ".webp";
    pic.alt = "";
    pic.loading = "lazy";
    btn.append(pic,textNode("strong",item.name),textNode("small",item.group));
    btn.title = item.description || item.name;
    btn.onclick = () => applyItem(item);
    grid.append(btn);
  }
}
el("browseLibrary").onclick = () => openLibrary(null,mode === "shorts" ? "effect" : "graphic");
el("closeLibrary").onclick = () => el("libraryDialog").close();
el("librarySearch").oninput = drawLibrary;
el("libraryGroup").onchange = drawLibrary;
for (const button of document.querySelectorAll("[data-kind]")) button.onclick = () => libraryTab(button.dataset.kind);

function newScene() {
  return {
    visual: "title",
    headline: "",
    voice: "",
    seconds: 4,
    start: 0,
    motion: "still",
  };
}
el("useScenes").onchange = () => {
  if (!storyboard.length) storyboard.push(newScene());
  showBoard();
};
el("addScene").onclick = () => {
  storyboard.push(newScene());
  showBoard();
};
async function upload(file) {
  const ext = file.name.match(/\.[a-z0-9]+$/i)?.[0] || "";
  return (
    await api("/api/assets", {
      method: "POST",
      headers: { "X-Orgainse-Studio": "1", "X-File-Extension": ext },
      body: file,
    })
  ).asset;
}
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
    mode === "shorts" ? "Highlight brief" : "Editing instructions";
  el("brief").placeholder =
    mode === "shorts"
      ? "Find distinct moments about pricing and results. Keep each thought complete."
      : "Use Product focus in scene 1. Add the Tape label effect from 1 to 3 seconds. Use Retro Typer captions.";
  el("targetlabel").textContent =
    mode === "shorts" ? "Seconds per short" : "Target seconds";
  el("submit").firstChild.textContent =
    mode === "shorts" ? "Render shorts " : "Render video ";
  if (defaults) {
    el("ratio").value = "auto";
    trim = null;
  }
}
function monitor(url, name, ratio, poster = "") {
  const v = el("player");
  if (ratio === "auto") ratio = mode === "shorts" ? "9:16" : "16:9";
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
  el("keepRanges").value = (request?.keep || []).map(pair => pair.join(", ")).join("\n");
  projectLayers = structuredClone(request?.effects || []);
  drawLayers(el("projectLayers"), projectLayers, false);
  storyboard = structuredClone(request?.scenes || []);
  el("useScenes").checked = storyboard.length > 0;
  el("storyboard").open = storyboard.length > 0;
  showBoard();
  assets = {};
  el("error").textContent = "";
  setMode(request?.mode || "create", false);
  if (request) {
    for (const k of keys)
      if (request[k] !== undefined) el(k).value = request[k];
    for (const k of ["captions", "draft", "fullLength"])
      el(k).checked = !!request[k];
    for (const c of el("layouts").querySelectorAll("input"))
      c.checked =
        c.value !== request.ratio && !!request.ratios?.includes(c.value);
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
  el("editScenes").hidden = j.request.mode !== "create" || j.status !== "done";
  el("editScenes").onclick = async () => {
    try {
      const plan = await api(base + "edit-plan.json");
      editor({ ...j.request, captionStyle: plan.captionStyle || j.request.captionStyle, fullLength: false, scenes: plan.shots });
    } catch (e) {
      el("progress").textContent = e.message;
    }
  };
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
        o.ratio || j.request.ratio,
        o.poster ? base + o.poster : "",
      );
      el("player")
        .play()
        .catch(() => {});
    };
    actions.append(play, fileLink(base + o.file, "Save MP4", true));
    if (o.subtitles)
      actions.append(fileLink(base + o.subtitles, "Subtitles", true));
    if (o.webvtt) actions.append(fileLink(base + o.webvtt, "WebVTT", true));
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
    async function resolveLayers(list) {
      const resolved = [];
      for (const {uploads, ...layer} of list) {
        if (uploads?.length) {
          if (uploads.length > 12) throw Error("Choose up to twelve card images.");
          layer.cards = await Promise.all(uploads.map(upload));
        }
        resolved.push(layer);
      }
      return resolved;
    }
    const req = { mode, effects: await resolveLayers(projectLayers) };
    if (mode === "create" && el("keepRanges").value.trim()) {
      req.keep = el("keepRanges").value.trim().split(/\n+/).map(line => {
        const parts = line.trim().split(/[\s,]+/).map(Number);
        if (parts.length !== 2 || !parts.every(Number.isFinite)) throw Error("Enter one start and end time per line.");
        return parts;
      });
    }
    for (const id of keys) req[id] = el(id).value;
    req.ratios = Array.from(
      el("layouts").querySelectorAll("input:checked"),
      (c) => c.value,
    );
    req.fullLength = mode === "create" && el("fullLength").checked;
    if (mode === "create" && el("useScenes").checked) {
      if (!storyboard.length) throw Error("Add a scene to the storyboard.");
      req.script = "";
      req.scenes = [];
      for (const {
        upload: file,
        mobileUpload: phoneFile,
        ...s
      } of storyboard) {
        const acceptsScreen = ["graphic", "website"].includes(s.visual);
        if (file && acceptsScreen) s.image = await upload(file);
        if (phoneFile && acceptsScreen) s.portraitImage = await upload(phoneFile);
        if (!acceptsScreen) {
          delete s.image;
          delete s.portraitImage;
        }
        if (s.effects) s.effects = await resolveLayers(s.effects);
        req.scenes.push(s);
      }
    }
    req.seconds = Number(req.seconds);
    req.count = Number(req.count);
    for (const key of ["captions", "draft"]) req[key] = el(key).checked;
    if (req.url !== originalUrl && !el("image").files.length)
      delete assets.image;
    if ((el("media").files.length || el("narration").files.length) && !el("transcript").files.length)
      delete assets.transcript;
    if (el("media").files.length) trim = null;
    for (const key of files) {
      if (mode === "shorts" && ["narration", "image"].includes(key)) continue;
      const file = el(key).files[0];
      if (file) {
        el("actioninfo").textContent = "Saving " + file.name + " on this PC…";
        assets[key] = await upload(file);
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
  (el("monitorformat").textContent = el("ratio").value === "auto" ? "From instructions" : el("ratio").value);
for (const key of files)
  el(key).onchange = () => {
    if (el(key).files.length) el(key + "-note").textContent = "";
  };
(async () => {
  try {
    let guides;
    [catalog, library, guides] = await Promise.all([api("/brand/catalog.json"), api("/api/library"), api("/api/guides").catch(() => [])]);
    library.push(...guides);
    for (const style of library.filter(x => x.kind === "caption")) el("captionStyle").add(new Option(style.name, style.id));
    logoOptions(el("logo").value);
    const status = await api("/api/status");
    el("runtime").textContent = "Local workstation";
    for (const [key, name] of Object.entries({
      ffmpeg: "FFmpeg renderer",
      speech: "Speech recognition",
      britishVoice: "British neural narration",
      proofreading: "Oxford English proofreading",
      planner: "Scene planner",
      browser: "Website capture",
      motion: "Motion scenes",
      videoEffects: "Footage effects",
      animatedCaptions: "Animated captions",
    })) {
      const li = textNode("li", name);
      li.append(textNode("span", status[key] ? "Ready" : "Setup needed"));
      el("tools").append(li);
    }
    await refresh();
    if (/^[a-f0-9]{32}$/.test(location.hash.slice(1)))
      await show(location.hash.slice(1));
    if (location.hash === "#library") openLibrary(null,"graphic");
    setInterval(refresh, 2200);
  } catch (e) {
    el("error").textContent = e.message;
  }
})();
