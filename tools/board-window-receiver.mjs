// Reuses the project's browser/login transport. No audio tracks or HID.
import fs from 'node:fs/promises';
import { loginManager } from './manager-login.mjs';
import { measureDecoded, connectVideo, closeVideo } from './board-window-timing.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }),
  headless: true, args: ['--autoplay-policy=no-user-gesture-required',
    '--disable-features=WebRtcHideLocalIpsWithMdns'] });
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  if (process.argv[2] === '--compare') {
    const data = await Promise.all(process.argv.slice(3, 5).map(async p =>
      'data:image/jpeg;base64,' + (await fs.readFile(p)).toString('base64')));
    const menu = Number(process.argv[5]);
    const result = await page.evaluate(async ({data, menu}) => {
      const pixels = [];
      let dimensions;
      for (const src of data) {
        const image = new Image(); image.src = src; await image.decode();
        if (menu < 0 || menu >= image.height) throw new Error('Invalid menu crop');
        const size = [image.width, image.height];
        if (dimensions && String(dimensions) !== String(size)) throw new Error('Screen size changed');
        dimensions = size;
        const canvas = document.createElement('canvas');
        canvas.width = image.width; canvas.height = image.height - menu;
        const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, -menu);
        pixels.push(ctx.getImageData(0, 0, canvas.width, canvas.height).data);
      }
      let changed = 0;
      for (let i = 0; i < pixels[0].length; i += 4) {
        if ([0, 1, 2].some(c => Math.abs(pixels[0][i+c] - pixels[1][i+c]) > 20)) changed++;
      }
      const changedFraction = changed / (pixels[0].length / 4);
      return { idle: changedFraction < .001, changedFraction, ignoredMenuPixels: menu,
        caveat: 'Visual stability only; does not prove absence of a user' };
    }, {data, menu});
    console.log(JSON.stringify(result));
  } else {
    const url = process.argv[2], seconds = Number(process.argv[3]);
    if (!Number.isFinite(seconds) || seconds <= 0 || seconds > 1800) throw new Error('Invalid seconds');
    const localIP = process.argv.find(a => a.startsWith('--local-ip='))?.split('=')[1];
    if (localIP && !/^\d{1,3}(\.\d{1,3}){3}$/.test(localIP)) throw new Error('Invalid LAN IPv4');
    const target = new URL(url);
    await loginManager(context, url, { localBackend: ['127.0.0.1', 'localhost', '[::1]'].includes(target.hostname) });
    await connectVideo(page, url, localIP);
    const sample = () => page.evaluate(async () => {
      for (const peer of window.boardPeers) {
        if (peer.connectionState !== 'connected') continue;
        const report = await peer.getStats();
        for (const stat of report.values()) {
          if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
            return { ...stat, codec: report.get(stat.codecId)?.mimeType };
          }
        }
      }
      return null;
    });
    const result = await measureDecoded(sample, seconds);
    console.log(JSON.stringify({ browser: browser.version(), ...result }));
  }
} finally {
  for (const context of browser.contexts()) for (const page of context.pages()) {
    await closeVideo(page).catch(() => {});
  }
  await browser.close();
}
