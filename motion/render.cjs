// Render only local, allowlisted graphics, caption scripts, fonts and textures.
const fs = require("node:fs");
const path = require("node:path");
const {spawn,execFileSync} = require("node:child_process");
const {once} = require("node:events");
const {chromium} = require("playwright-core");
const root = path.resolve(__dirname, "..");
const catalog = require("./catalog.json");
const byId = new Map(catalog.map(item => [item.id, item]));
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8").replace(/^\uFEFF/, ""));
const caps = path.join(root, "upstream/caption-styles/captions.js");
const textures = path.join(root, "upstream/shotcraft/demos/_textures");
const fontDir = path.join(root, "upstream/video-effects/fonts");
const fonts = {"Anton":"Anton-Regular.ttf","Inter Tight":"Inter.ttf","JetBrains Mono":"SpaceMono-Bold.ttf",
  "Newsreader":"InstrumentSerif-Italic.ttf","Special Elite":"SpaceMono-Bold.ttf"};
const html = '<meta charset="utf-8"><style>html,body,#stage{margin:0;width:100%;height:100%;overflow:hidden}' +
  Object.entries(fonts).map(([family,file]) => '@font-face{font-family:"'+family+'";src:url(/fonts/'+file+')}').join("") +
  '</style><link data-cs-fonts><div id="stage"></div>';

async function render(page, cdp, item, opts) {
  const preview = Boolean(opts.thumbnail);
  const caption = item.kind === "caption";
  const errors = [];
  const onError = e => errors.push(e.message);
  page.on("pageerror", onError);
  let proc, done;
  try {
    await page.goto("http://studio.local/", {waitUntil:"load"});
    if (caption) {
      await page.addScriptTag({path:caps});
      await page.evaluate(async cfg => {
        await CaptionStyles.fontsReady();
        window.cap = CaptionStyles.create(document.querySelector("#stage"), cfg);
      }, {style:item.id, words:opts.words, y:opts.y ?? 70, size:opts.size ?? 1});
    } else {
      await page.addScriptTag({url:"http://studio.local/graphics.js"});
    }
    const frames = caption ? opts.frames : await page.evaluate(([id,data]) => window.openCard(id,data),
      [item.id,{headline:opts.headline,subhead:opts.subhead,logo:Boolean(opts.logo),screen:Boolean(opts.screen),
                editable:Boolean(item.editable),portrait:spec.height>spec.width}]);
    const samples = preview ? [0.09,0.21,0.34,0.47,0.60,0.74,0.87,0.96] : null;
    const n = preview ? samples.length : opts.frames;
    const args = ["-v","error","-nostdin","-y"];
    if (caption && opts.input) args.push("-i",opts.input);
    args.push("-f","image2pipe","-framerate",preview ? "5" : "30","-vcodec","png","-i","pipe:0");
    if (caption && opts.input) args.push("-filter_complex","[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
      "-map","[v]","-map","0:a?","-c:a","copy");
    if (preview) args.push("-c:v","libwebp_anim","-quality","74","-loop","0");
    else args.push("-c:v","libx264","-threads","2","-preset","veryfast","-crf","18","-pix_fmt","yuv420p","-frames:v",String(n));
    proc = spawn(spec.ffmpeg, [...args, opts.output], {stdio:["pipe","ignore","pipe"], windowsHide:true});
    let log = "";
    proc.stderr.on("data", b => {log = (log + b).slice(-1600);});
    proc.stdin.on("error", () => {});
    done = new Promise((resolve,reject) => {
      proc.on("error",reject);
      proc.on("close", code => code === 0 ? resolve() : reject(Error(log || "Image encoder exited " + code)));
    });
    done.catch(() => {});
    const images = new Set();
    let previousFrame = -1;
    let pixels;
    for (let i=0; i<n; i++) {
      const fraction = preview ? samples[i] : i / Math.max(1,n-1);
      const sourceFrame = Math.round(fraction * (frames-1));
      if (caption) {
        await page.evaluate(t => window.cap.seek(t), preview ? fraction * (opts.frames / 30) : i/30);
      } else if (sourceFrame !== previousFrame) {
        await page.evaluate(async frame => {
          let timer;
          try {
            await Promise.race([window.seekCard(frame), new Promise((_, reject) => {
              timer = setTimeout(() => reject(Error("Frame did not settle")), 8000);
            })]);
          } finally {
            clearTimeout(timer);
          }
        },
          sourceFrame);
      }
      if (errors.length) throw Error(errors[0]);
      if (caption || sourceFrame !== previousFrame) {
        const shot = await cdp.send("Page.captureScreenshot",{format:"png",fromSurface:true,optimizeForSpeed:true});
        pixels = Buffer.from(shot.data,"base64");
        if (preview) images.add(shot.data);
        previousFrame = sourceFrame;
      }
      if (!proc.stdin.write(pixels)) await Promise.race([once(proc.stdin,"drain"), done]);
    }
    proc.stdin.end();
    await done;
    if (preview && images.size < 2) throw Error("All sampled frames were identical");
  } finally {
    page.off("pageerror",onError);
    if (proc && proc.exitCode === null) proc.kill();
  }
}

async function main() {
  const browser = await chromium.launch({executablePath:spec.browser, headless:true,
    args:["--disable-background-timer-throttling","--disable-renderer-backgrounding"]});
  try {
    let logoBytes;
    if (spec.logo) {
      const variants = Object.values(require("../brand/catalog.json")).flatMap(Object.values);
      const art = variants.find(v => v.file === path.basename(spec.logo));
      if (!art) throw Error("Unknown brand artwork");
      const [x,y,w,h] = art.crop;
      logoBytes = execFileSync(spec.ffmpeg, ["-v","error","-i",spec.logo,"-vf","crop="+[w,h,x,y].join(":")+",scale=660:-1",
        "-frames:v","1","-f","image2pipe","-c:v","png","pipe:1"], {windowsHide:true,maxBuffer:8*1024*1024});
    }
    const context = await browser.newContext({viewport:{width:spec.width,height:spec.height},deviceScaleFactor:1});
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Emulation.setDefaultBackgroundColorOverride",{color:{r:0,g:0,b:0,a:spec.input ? 0 : 1}});
    await page.route("**/*", async route => {
      const url = new URL(route.request().url());
      if (url.origin !== "http://studio.local") return route.abort();
      if (url.pathname === "/") return route.fulfill({contentType:"text/html",body:html});
      if (url.pathname === "/graphics.js") return route.fulfill({path:path.join(root,".local/motion/graphics.js"),contentType:"text/javascript"});
      if (url.pathname === "/current-logo" && logoBytes) return route.fulfill({contentType:"image/png",body:logoBytes});
      if (url.pathname === "/current-screen" && spec.screen) return route.fulfill({path:spec.screen});
      const name = path.posix.basename(url.pathname);
      if (url.pathname.startsWith("/fonts/") && Object.values(fonts).includes(name))
        return route.fulfill({path:path.join(fontDir,name)});
      if (/\/textures\/live\/[\w-]+\.png$/.test(url.pathname) && fs.existsSync(path.join(textures,name)))
        return route.fulfill({path:(spec.screen && /^(projects-full|wbr-full|papers-full)\.png$/.test(name)) ? spec.screen : path.join(textures,name)});
      return route.fulfill({status:404,body:"Missing local asset"});
    });
    const jobs = spec.items || [spec];
    const failed = [];
    for (const opts of jobs) {
      const item = byId.get(opts.id);
      if (!item || !["graphic","caption"].includes(item.kind)) throw Error("Invalid animation ID");
      try { await render(page,cdp,item,{...spec,...opts}); }
      catch(error) {
        if (!spec.items) throw error;
        failed.push([opts.id,error.message]);
      }
    }
    if (failed.length) throw Error(JSON.stringify(failed));
  } finally { await browser.close(); }
}
main().catch(e => {console.error(e.message);process.exitCode=1;});
