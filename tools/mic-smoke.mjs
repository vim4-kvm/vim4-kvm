import { loginManager } from './manager-login.mjs';
// Enable the original microphone control with Chrome's synthetic microphone,
// then report the board's UAC2 playback state. Re-enumerates USB on the board
// (USB networking is replaced while the microphone is on); coordinate access.
// PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs node tools/mic-smoke.mjs [URL]
import { execFileSync } from 'node:child_process';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.argv[2] || 'http://192.168.50.210:8080';
const board = (command) => execFileSync('ssh', ['vim4', command], { encoding: 'utf8' }).trim();
// aplay receiving PCM proves browser audio reached the gadget. It blocks once
// the ALSA buffer is full, so bytesPerSecond approaches 192000 (48 kHz stereo
// S16) only while an application on the USB host records from the device.
const aplayRead = () => Number(board('p=$(pgrep -x aplay) && sed -n "s/^rchar: //p" /proc/$p/io || echo 0'));

const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  // getUserMedia requires a secure context; the board serves plain HTTP.
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
    `--unsafely-treat-insecure-origin-as-secure=${new URL(url).origin}`]
});
try {
  const context = await browser.newContext({ permissions: ['microphone'] });
  const page = await context.newPage();
  await loginManager(context, url);
  await page.addInitScript(() => localStorage.setItem('nano-kvm-vide-mode', 'h264-webrtc'));
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, { timeout: 45000 });
  await page.locator('svg.lucide-mic-off').dispatchEvent('click');
  await page.getByRole('button', { name: /enable|启用/i }).click();
  await page.locator('svg.lucide-mic').waitFor({ timeout: 30000 });
  // The track reaches NanoKVM after audio renegotiation, which starts aplay.
  for (let i = 0; i < 20 && !board('pgrep -x aplay || true'); i++) await page.waitForTimeout(1000);
  await page.waitForTimeout(1000);
  const received = aplayRead();
  const first = received;
  const started = Date.now();
  await page.waitForTimeout(5000);
  const bytesPerSecond = ((aplayRead() - first) * 1000) / (Date.now() - started);
  const enabled = {
    links: board('ls /sys/kernel/config/usb_gadget/kvm/configs/c.1 | grep -E "ncm|uac2|mass" | tr "\\n" " "'),
    aplay: board('pgrep -a aplay || true'),
    pcmBytesReceived: received,
    bytesPerSecond
  };
  await page.locator('svg.lucide-mic').dispatchEvent('click');
  await page.waitForTimeout(5000);
  const disabled = { links: board('ls /sys/kernel/config/usb_gadget/kvm/configs/c.1 | grep -E "ncm|uac2|mass" | tr "\\n" " "') };
  console.log(JSON.stringify({ enabled, disabled }, null, 2));
  if (!(enabled.pcmBytesReceived > 0) || !enabled.links.includes('uac2') || !disabled.links.includes('ncm')) {
    throw new Error('Microphone smoke test failed');
  }
} finally {
  await browser.close();
}
