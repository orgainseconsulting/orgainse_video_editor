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
esbuild.build({
  stdin: {contents: source, resolveDir: __dirname, loader: "tsx"},
  bundle: true, outfile: path.join(output, "graphics.js"),
  nodePaths: [path.join(__dirname, "node_modules")], jsx: "automatic",
  define: {"process.env.NODE_ENV": '"production"'}, minify:true, logLevel:"warning"
}).catch(err => {console.error(err); process.exitCode = 1;});
