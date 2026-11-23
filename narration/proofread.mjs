import { readFile } from "node:fs/promises";
import { LocalLinter, Dialect, SuggestionKind } from "harper.js";
import { binaryInlined } from "harper.js/binaryInlined";

// Keep quoted copy, URLs, identifiers, acronyms and multiword proper names literal.
const protectedText = /(?:https?:\/\/|www\.)[^\s<>]+|[\w.+-]+@[\w.-]+\.\w+|\x60[^\x60]*\x60|"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)'[^'\n]+'(?!\w)|\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b|\b[\w-]*[a-z][A-Z]\w*\b|\b[A-Z][A-Z\d_-]+\b/gu;
const spellings = new Map();
function pair(source, preferred, endings = [""]) {
  for (const ending of endings) spellings.set(source + ending, preferred + ending);
}
for (const stem of ["col", "flav", "hon", "hum", "lab", "neighb", "rum", "sav", "behavi"]) {
  pair(stem + "or", stem + "our", ["", "s", "ed", "ing"]);
}
for (const [us, uk] of [["center","centre"], ["liter","litre"], ["fiber","fibre"], ["theater","theatre"],
                        ["defense","defence"], ["offense","offence"]]) {
  pair(us, uk, ["", "s"]);
}
for (const stem of ["organ", "recogn", "priorit", "optim", "custom", "real", "standard", "author", "central", "special", "visual", "categor", "maxim", "minim", "final", "local"]) {
  pair(stem + "is", stem + "iz", ["e", "es", "ed", "ing", "ation", "ations"]);
}
for (const stem of ["anal", "paral", "catal"]) pair(stem + "yz", stem + "ys", ["e","es","ed","ing"]);
for (const stem of ["travel","cancel","label","model"]) pair(stem, stem + "l", ["ed","ing"]);
pair("gray", "grey", ["", "s"]);
pair("grammer", "grammar");
pair("teh", "the");

const linter = new LocalLinter({ binary: binaryInlined, dialect: Dialect.British });
const safeCategories = new Set(["Agreement", "Repetition"]);
const safeRules = new Set(["AnA"]);

async function revise(text) {
  // Mask for linting with one space per Unicode scalar, preserving the original offsets.
  const masked = text.replace(protectedText, m => " ".repeat([...m].length));
  const original = [...text];
  const available = [...masked];
  const edits = [];
  const lintGroups = await linter.organizedLints(masked, { language: "plaintext" });
  for (const [rule, group] of Object.entries(lintGroups)) {
    for (const lint of group) {
      const options = lint.suggestions();
      if ((!safeRules.has(rule) && !safeCategories.has(lint.lint_kind())) || options.length !== 1) continue;
      const { start, end } = lint.span();
      const suggestion = options[0];
      if (suggestion.kind() !== SuggestionKind.Replace && suggestion.kind() !== SuggestionKind.Remove) continue;
      const before = original.slice(start, end).join("");
      if (before !== lint.get_problem_text() || !before.trim()) continue;
      edits.push({ start, end, before, after: suggestion.get_replacement_text(), rule });
    }
  }
  for (let i = 0; i < available.length;) {
    if (!/[A-Za-z]/.test(available[i])) { i++; continue; }
    const start = i;
    while (i < available.length && /[A-Za-z]/.test(available[i])) i++;
    const before = original.slice(start, i).join("");
    const preferred = spellings.get(before.toLowerCase());
    if (!preferred || (available[start - 1] || "").match(/[\w\u2019']/) || (available[i] || "").match(/[\w\u2019']/)) continue;
    const after = /^[A-Z]/.test(before) ? preferred[0].toUpperCase() + preferred.slice(1) : preferred;
    edits.push({ start, end: i, before, after, rule: "Oxford spelling" });
  }
  let boundary = original.length;
  for (const edit of edits.sort((a,b) => b.start-a.start || b.end-a.end)) {
    if (edit.end > boundary || edit.before === edit.after) continue;
    original.splice(edit.start, edit.end - edit.start, edit.after);
    boundary = edit.start;
  }
  return original.join("");
}

try {
  const texts = JSON.parse(await readFile(process.argv[2], "utf8"));
  const result = [];
  for (const text of texts) {
    let checked = text;
    for (let pass = 0; pass < 3; pass++) {
      const next = await revise(checked);
      if (next === checked) break;
      checked = next;
    }
    result.push(checked);
  }
  process.stdout.write(JSON.stringify(result));
} finally {
  await linter.dispose();
}
