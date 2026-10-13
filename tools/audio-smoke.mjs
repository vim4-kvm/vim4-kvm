// Verify the real volume control and received audio without bypassing autoplay.
// Optional --expect-signal requires a non-silent HDMI source during the sample.
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const url = process.argv[2] || "http://192.168.50.210:8080";
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage();
  await page.addInitScript(() => {
    window.audioTestPeers = [];
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) {
        super(...args);
        window.audioTestPeers.push(this);
      }
    };
  });
  await page.goto(url);
  await page.waitForFunction(
    () => document.querySelector("video")?.videoWidth > 0,
  );
  await page.locator("svg.lucide-volume-x").click();
  await page.getByRole("slider").focus();
  await page.getByRole("slider").press("End");
  await page.waitForFunction(() => {
    const audio = document.querySelector("audio");
    return audio && !audio.muted && audio.volume === 1 && !audio.paused;
  });
  const stats = () =>
    page.evaluate(async () => {
      for (const peer of window.audioTestPeers) {
        for (const entry of (await peer.getStats()).values()) {
          if (entry.type === "inbound-rtp" && entry.kind === "audio")
            return entry;
        }
      }
      throw new Error("No inbound audio track");
    });
  await page.waitForTimeout(3000);
  const before = await stats();
  await page.waitForTimeout(6000);
  const after = await stats();
  if (before.id !== after.id)
    throw new Error("Audio track changed during measurement");
  const seconds = (after.timestamp - before.timestamp) / 1000;
  const delta = (key) => after[key] - before[key];
  const result = {
    seconds,
    packetsPerSecond: delta("packetsReceived") / seconds,
    packetsLost: delta("packetsLost"),
    samples: delta("totalSamplesReceived"),
    concealedSamples: delta("concealedSamples"),
    concealmentEvents: delta("concealmentEvents"),
    energy: delta("totalAudioEnergy"),
    before,
    after,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!(result.samples > 48000)) throw new Error("No sustained decoded audio");
  if (process.argv.includes("--expect-signal") && !(result.energy > 0)) {
    throw new Error("Audio is silent despite an expected HDMI test signal");
  }
} finally {
  await browser.close();
}
