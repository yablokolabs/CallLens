/* Render CallLens Coach diagrams to a single PDF via headless Chromium. */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const BIN = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
const ROOT = "/home/azureuser/yablokolabs/CallLens";
const OUT = process.argv[2] || path.join(ROOT, "docs", "CallLens-Coach-Architecture.pdf");

// (svg file, page heading) — architecture first, then supporting flows
const DIAGRAMS = [
  ["architecture.svg", "CallLens Coach — System Architecture"],
  ["agent-flow.svg", "Strands Agent Flow — Tool Loop"],
  ["decision-flow.svg", "Decision Logic — NO_ACTION / COACH / ESCALATE"],
  ["pipeline.svg", "Existing CallLens Analysis Pipeline"],
];

const MERGE = `
import sys
from pypdf import PdfWriter
workdir, *pages, out = sys.argv[1:]
w = PdfWriter()
for p in pages:
    w.append(p)
with open(out, "wb") as f:
    w.write(f)
`;

const workdir = fs.mkdtempSync("/tmp/archpdf-");

const pages = DIAGRAMS.map(([file, heading], idx) => {
  const svg = fs.readFileSync(path.join(ROOT, "docs/diagrams", file), "utf8");
  const [w, h] = (svg.match(/viewBox="0 0 (\d+) (\d+)"/) || [null, "1000", "640"]).slice(1).map(Number);
  const html = `<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page { size: ${w}px ${h + 130}px; margin: 0; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 34px 40px; background: #ffffff;
         font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: #18181b; }
  header { display: flex; align-items: baseline; justify-content: space-between;
           border-bottom: 2px solid #4f46e5; padding-bottom: 10px; margin-bottom: 22px; }
  .brand { font-size: 13px; font-weight: 700; letter-spacing: 2.5px; color: #4f46e5; }
  h1 { font-size: 17px; font-weight: 600; color: #27272a; margin: 0; }
  .page { font-size: 11px; color: #71717a; }
  .canvas { width: ${w}px; height: ${h}px; }
  .canvas svg { width: 100%; height: 100%; display: block; }
  footer { margin-top: 18px; font-size: 10.5px; color: #71717a; line-height: 1.5; }
</style></head>
<body>
  <header>
    <span class="brand">CALLLENS COACH</span>
    <h1>${heading}</h1>
    <span class="page">Page ${idx + 1} / ${DIAGRAMS.length}</span>
  </header>
  <div class="canvas">${svg}</div>
  <footer>Strands Agents SDK is the autonomous decision layer &middot; CallLens (LangGraph + rubric scoring) is the evidence layer &middot; NO_ACTION / COACH / ESCALATE with human-in-the-loop escalation.</footer>
</body></html>`;
  const htmlPath = path.join(workdir, `page${idx}.html`);
  fs.writeFileSync(htmlPath, html);
  const pdfPath = path.join(workdir, `page${idx}.pdf`);
  execFileSync(BIN, [
    "--headless", "--no-sandbox", "--disable-gpu", "--run-all-compositor-stages-before-draw",
    "--virtual-time-budget=3000",
    `--print-to-pdf=${pdfPath}`, "--no-pdf-header-footer", `file://${htmlPath}`,
  ], { stdio: "pipe" });
  if (!fs.existsSync(pdfPath) || fs.statSync(pdfPath).size < 1000) throw new Error(`render failed: ${file}`);
  return pdfPath;
});

fs.mkdirSync(path.dirname(OUT), { recursive: true });
execFileSync("python3", ["-c", MERGE, workdir, ...pages, OUT]);
fs.rmSync(workdir, { recursive: true, force: true });
console.log("PDF written:", OUT, fs.statSync(OUT).size, "bytes");
