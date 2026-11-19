// Capture visible editorial sections in an isolated Chrome/Edge browser session.
const fs = require("node:fs");
const path = require("node:path");
const [modulePath, executablePath, url, dir] = process.argv.slice(2);
const { chromium } = require(modulePath);
async function capture() {
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: ["--disable-sync", "--disable-background-networking"],
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page
      .locator("h1,h2,main,p")
      .first()
      .waitFor({ state: "attached", timeout: 8000 })
      .catch(() => {});
    await page.evaluate(() =>
      Promise.race([
        document.fonts.ready,
        new Promise((r) => setTimeout(r, 2500)),
      ]),
    );
    const entries = await page.evaluate(() => {
      const heads = [...document.querySelectorAll("h1,h2")].filter(
        (e) => e.getBoundingClientRect().height && e.innerText.trim(),
      );
      const result = [];
      for (const el of heads) {
        const area = el.closest("section,article") || el.parentElement;
        const summary = area?.querySelector("p")?.innerText?.trim() || "";
        result.push({
          heading: el.innerText.trim().slice(0, 140),
          summary: summary.slice(0, 320),
          top: Math.max(0, scrollY + el.getBoundingClientRect().top - 108),
        });
      }
      return result;
    });
    const brief = JSON.parse(
      fs.readFileSync(path.join(dir, "capture-brief.json"), "utf8"),
    ).brief.toLowerCase();
    const terms = brief.match(/[a-z0-9]{4,}/g) || [];
    const ranked = entries.map((e, i) => ({
      e,
      i,
      score: terms.reduce(
        (n, t) => n + (e.heading + " " + e.summary).toLowerCase().includes(t),
        0,
      ),
    }));
    const picks = ranked
      .slice(1)
      .sort((a, b) => b.score - a.score || a.i - b.i)
      .slice(0, 4);
    const chosen = [
      entries[0] || { heading: await page.title(), summary: "", top: 0 },
      ...picks.sort((a, b) => a.i - b.i).map((x) => x.e),
    ];
    for (const [i, e] of chosen.entries()) {
      await page.evaluate(
        (y) => window.scrollTo({ top: y, behavior: "instant" }),
        i ? e.top : 0,
      );
      await page.waitForTimeout(350);
      e.file = i ? "website-" + i + ".png" : "website.png";
      await page.screenshot({ path: path.join(dir, e.file), timeout: 12000 });
      delete e.top;
    }
    fs.writeFileSync(
      path.join(dir, "captured-sections.json"),
      JSON.stringify(chosen),
    );
  } finally {
    await browser.close();
  }
}
capture().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
