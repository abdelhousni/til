// Screenshots pages of the locally served TIL site with headless Chromium
// and checks what the build can get wrong without failing:
//   - list lines left inside a <p> ("- item" right after a paragraph);
//   - ```mermaid blocks that didn't render to an SVG;
//   - console errors and failed requests to the site itself.
// Usage: node driver.mjs [--base http://localhost:8000] [--out DIR] PATH...
// PATH is relative to the site root, e.g. ansible/foo.html or "" for /.
// Exits 1 if any page has a problem.
import { createRequire } from "node:module";
import { existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";

// The cloud container keeps Chromium in /opt/pw-browsers and points
// PLAYWRIGHT_BROWSERS_PATH at it; a shell without that variable would look in
// ~/.cache/ms-playwright and fail.
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && existsSync("/opt/pw-browsers")) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = "/opt/pw-browsers";
}
const require = createRequire(import.meta.url);
let playwright;
for (const p of ["playwright", "/opt/node-tools/node_modules/playwright"]) {
  try { playwright = require(p); break; } catch {}
}
if (!playwright) {
  console.error("playwright not found: npm i -g playwright, or set the path in driver.mjs");
  process.exit(2);
}

const args = process.argv.slice(2);
let base = "http://localhost:8000";
let out = "/tmp/til-shots";
const paths = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--base") base = args[++i];
  else if (args[i] === "--out") out = args[++i];
  else paths.push(args[i]);
}
if (!paths.length) paths.push("");
mkdirSync(out, { recursive: true });

const browser = await playwright.chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
// The GoatCounter script is protocol-relative, so on http://localhost it is
// fetched over plain HTTP, which a proxy may refuse. A local preview shouldn't
// count as a visit anyway.
await context.route("**/gc.zgo.at/**", (route) => route.abort());
// External resources (Mermaid from cdn.jsdelivr.net, the shields.io badge)
// fail in Chromium behind the cloud container's TLS-inspecting proxy:
// ERR_CERT_AUTHORITY_INVALID, or ERR_TOO_MANY_RETRIES with ignoreHTTPSErrors.
// curl trusts the proxy's CA, so fetch them with curl and hand the bytes over.
if (process.env.HTTPS_PROXY) {
  await context.route(/^https:\/\//, (route) => {
    try {
      const out = execFileSync("curl",
        ["-sSfL", "-o", "-", "-w", "\n%{content_type}", route.request().url()],
        { maxBuffer: 64 << 20 });
      const nl = out.lastIndexOf(10);
      route.fulfill({ status: 200, body: out.subarray(0, nl), headers: {
        "content-type": out.subarray(nl + 1).toString() || "application/octet-stream",
        "access-control-allow-origin": "*" } });
    } catch { route.abort(); }
  });
}
const page = await context.newPage();
let failed = false;

for (const path of paths) {
  const url = `${base.replace(/\/$/, "")}/${path}`;
  const problems = [];
  const onConsole = (m) => m.type() === "error" && !/ERR_FAILED|ERR_BLOCKED/.test(m.text())
    && problems.push(`console: ${m.text()}`);
  const onFail = (r) => r.url().startsWith(base) && problems.push(`request failed: ${r.url()}`);
  page.on("console", onConsole);
  page.on("requestfailed", onFail);

  const res = await page.goto(url, { waitUntil: "networkidle" });
  if (!res || !res.ok()) problems.push(`HTTP ${res ? res.status() : "no response"}`);

  const stray = await page.$$eval("p", (ps) =>
    ps.filter((p) => /\n\s*(?:[-*+]|\d+[.)])\s/.test(p.textContent))
      .map((p) => p.textContent.trim().slice(0, 80)));
  for (const s of stray) problems.push(`list inside <p>: ${JSON.stringify(s)}`);

  const mermaid = await page.$$eval("pre.mermaid", (els) =>
    els.map((e) => !!e.querySelector("svg")));
  if (mermaid.includes(false)) problems.push(`mermaid blocks not rendered: ${mermaid.filter((x) => !x).length}`);

  const shot = `${out}/${(path || "index").replace(/\//g, "_").replace(/\.html$/, "")}.png`;
  await page.screenshot({ path: shot, fullPage: true });
  const title = await page.title();

  page.off("console", onConsole);
  page.off("requestfailed", onFail);
  console.log(`${problems.length ? "FAIL" : "ok  "} ${url}  "${title}"  -> ${shot}`);
  for (const p of problems) console.log(`     ${p}`);
  if (problems.length) failed = true;
}

await browser.close();
process.exit(failed ? 1 : 0);
