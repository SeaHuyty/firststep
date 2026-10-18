// Print an HTML file to an A4 PDF with page numbers: node scripts/print-pdf.mjs in.html out.pdf
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const [input, output] = process.argv.slice(2);
// Cloud containers ship a Chromium here; elsewhere Playwright's own browser is used.
const preinstalled = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(existsSync(preinstalled) ? { executablePath: preinstalled } : {});
const page = await browser.newPage();
await page.goto(`file://${resolve(input)}`, { waitUntil: "networkidle" });
await page.pdf({
  path: output,
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate:
    '<div style="width:100%;font-size:8px;color:#5A6C6E;text-align:center">FirstStep · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  margin: { top: "16mm", bottom: "16mm", left: "14mm", right: "14mm" },
});
await browser.close();
