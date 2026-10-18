// Render an SVG to a PNG at 2x: node scripts/svg-to-png.mjs in.svg out.png
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const [input, output] = process.argv.slice(2);
const svg = readFileSync(input, "utf8");
const [, width, height] = svg.match(/viewBox="0 0 (\d+) (\d+)"/) ?? [];
// Cloud containers ship a Chromium here; elsewhere Playwright's own browser is used.
const preinstalled = "/opt/pw-browsers/chromium";
const browser = await chromium.launch(existsSync(preinstalled) ? { executablePath: preinstalled } : {});
const page = await browser.newPage({
  viewport: { width: Number(width ?? 1200), height: Number(height ?? 650) },
  deviceScaleFactor: 2,
});
await page.goto(`file://${resolve(input)}`);
await page.screenshot({ path: output });
await browser.close();
