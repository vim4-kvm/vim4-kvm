import { loginManager } from './manager-login.mjs';
import { spawn } from "node:child_process";
import fs from "node:fs";
// Usage: PLAYWRIGHT_MODULE=... node tools/input-check.mjs TARGET_BINARY LOG_PREFIX [URL]
// Mac must also be the VIM4 USB host. This briefly covers its displays with a
// disposable receiving app, moves the pointer, and uses only ArrowRight/clicks.
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const [targetBinary, prefix, url = "http://192.168.50.210:8080"] =
  process.argv.slice(2);
if (!targetBinary || !prefix)
  throw new Error("Expected TARGET_BINARY LOG_PREFIX [URL]");
fs.accessSync(targetBinary, fs.constants.X_OK);
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: "chrome" }), headless: true });
const page = await browser.newPage();
await loginManager(page.context(), url);
const reports = [];
await page.exposeFunction("recordInput", (row) => reports.push(row));
await page.addInitScript(() => {
  const original = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    if (this.url.includes("/api/ws") && ArrayBuffer.isView(data)) {
      window.recordInput({
        kind: "report",
        at: performance.timeOrigin + performance.now(),
        clockOffset: Date.now() - performance.timeOrigin - performance.now(),
        bytes: Array.from(
          new Uint8Array(data.buffer, data.byteOffset, data.byteLength),
        ),
      });
    }
    return original.call(this, data);
  };
});
let target;
let started;
const phase = (name) => {
  // Leave time to release input before the target's 40s watchdog closes it.
  if (target.exitCode !== null || Date.now() - started > 35000)
    throw new Error("Input target expired");
  reports.push({ kind: "phase", name, at: Date.now() });
};
try {
  await page.goto(url);
  await page.waitForFunction(
    () => document.querySelector("video")?.videoWidth > 0,
  );
  const fd = fs.openSync(`${prefix}-host.jsonl`, "w");
  started = Date.now();
  target = spawn(targetBinary, ["40"], { stdio: ["pipe", fd, "inherit"] });
  fs.closeSync(fd);
  await page.waitForTimeout(1800);
  phase("tap");
  for (let i = 0; i < 20; i++) {
    await page.keyboard.down("ArrowRight");
    await page.waitForTimeout(70);
    await page.keyboard.up("ArrowRight");
    await page.waitForTimeout(80);
  }
  phase("hold");
  await page.keyboard.down("ArrowRight");
  for (let i = 0; i < 10; i++) {
    await page.waitForTimeout(200);
    await page.keyboard.down("ArrowRight");
  }
  await page.keyboard.up("ArrowRight");
  await page.waitForTimeout(600);
  phase("blur");
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(800);
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.keyboard.up("ArrowRight");
  await page.waitForTimeout(600);
  phase("move");
  const rect = await page.locator("#screen").boundingBox();
  for (let i = 0; i < 20; i++) {
    await page.mouse.move(
      rect.x + rect.width * (i % 2 ? 0.65 : 0.35),
      rect.y + rect.height * 0.5,
    );
    await page.waitForTimeout(120);
  }
  phase("click");
  for (let i = 0; i < 5; i++) {
    await page.mouse.down();
    await page.waitForTimeout(70);
    await page.mouse.up();
    await page.waitForTimeout(100);
  }
  phase("wheel-default");
  for (const y of [100, -100, 100, -100]) {
    await page.mouse.wheel(0, y);
    await page.waitForTimeout(200);
  }
  await page.evaluate(() =>
    localStorage.setItem("nanokvm-kvm-mouse-scroll-direction", "1"),
  );
  await page.reload();
  await page.waitForFunction(
    () => document.querySelector("video")?.videoWidth > 0,
  );
  phase("wheel-inverted");
  await page.mouse.move(rect.x + rect.width * 0.5, rect.y + rect.height * 0.5);
  await page.waitForTimeout(500);
  for (const y of [100, -100, 100, -100]) {
    await page.mouse.wheel(0, y);
    await page.waitForTimeout(200);
  }
  phase("done");
} finally {
  await page.keyboard.up("ArrowRight").catch(() => {});
  await page.mouse.up().catch(() => {});
  await browser.close();
  fs.writeFileSync(`${prefix}-browser.json`, JSON.stringify(reports, null, 2));
  target?.stdin.end();
  if (target && target.exitCode === null)
    await new Promise((resolve) => target.on("exit", resolve));
}
