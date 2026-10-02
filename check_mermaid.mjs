// Parses every ```mermaid block with Mermaid's own parser, in Node with a
// jsdom shim standing in for the browser: no browser, no CDN, no server.
// Catches the syntax errors that make a diagram render as "Syntax error in
// text" on the site. It doesn't check layout: look at a new diagram once.
//
// Usage: node check_mermaid.mjs [FILE.md ...]
// With no arguments, checks every markdown file Git tracks. Exits 1 on any
// syntax error.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";

const { window } = new JSDOM("<!doctype html><html><body></body></html>");
for (const name of ["document", "DOMParser", "Element", "HTMLElement", "SVGElement", "Node"]) {
  globalThis[name] ??= window[name];
}
globalThis.window ??= window;
const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false });

// Same pattern as MERMAID_FENCE_RE in build_site.py
const FENCE = /^```mermaid[ \t]*\n([\s\S]*?)\n^```[ \t]*$/gm;

const files = process.argv.length > 2
  ? process.argv.slice(2)
  : execFileSync("git", ["ls-files", "*.md"], { encoding: "utf8" }).split("\n").filter(Boolean);

let blocks = 0;
let failed = 0;
for (const file of files) {
  const text = readFileSync(file, "utf8");
  for (const match of text.matchAll(FENCE)) {
    blocks++;
    const line = text.slice(0, match.index).split("\n").length;
    try {
      await mermaid.parse(match[1]);
    } catch (error) {
      failed++;
      const message = String(error.message ?? error).split("\n").slice(0, 3).join(" | ");
      console.log(`${file}:${line}: ${message}`);
    }
  }
}
console.log(`${blocks} Mermaid diagram(s) checked, ${failed} with syntax errors.`);
process.exit(failed ? 1 : 0);
