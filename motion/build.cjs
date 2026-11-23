// Bundle the pinned TSX components for offline, frame-addressable playback.
const fs = require("node:fs");
const path = require("node:path");
const esbuild = require("esbuild");
const catalog = require("./catalog.json");
const output = path.resolve(__dirname, "../.local/motion");
const cards = catalog.filter(item => item.kind === "graphic");
const imports = cards.map((item, i) => 'import * as c' + i + ' from ' + JSON.stringify(item.editable ? "./" + item.source : "../upstream/" + item.source));
const entries = cards.map((item, i) => JSON.stringify(item.id) + ': [c' + i + '.' + item.id + ', ' +
  (item.frameExport ? 'c' + i + '.' + item.frameExport : item.frames) + ']');
const source = imports.join("\n") + '\nimport { mount } from "./player";\nmount({' + entries.join(",\n") + '});';
fs.mkdirSync(output, {recursive:true});
async function build() {
  const bundle = await esbuild.build({
    stdin: {contents: source, resolveDir: __dirname, loader: "tsx"},
    bundle: true, write: false, outfile: path.join(output, "graphics.js"),
    nodePaths: [path.join(__dirname, "node_modules")], jsx: "automatic",
    define: {"process.env.NODE_ENV": '"production"'}, minify:true, logLevel:"warning"
  });
  const target = path.join(output, "graphics.js");
  const temp = target + "." + process.pid + ".tmp";
  try {
    fs.writeFileSync(temp, bundle.outputFiles[0].contents);
    fs.renameSync(temp, target);
  } finally {
    fs.rmSync(temp, {force:true});
  }
}
build().catch(err => {console.error(err); process.exitCode = 1;});
