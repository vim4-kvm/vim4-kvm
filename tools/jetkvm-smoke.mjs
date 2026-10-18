import { loginManager } from './manager-login.mjs';
// JetKVM UI smoke test. Requires Playwright and Chrome; opens one viewer, so
// coordinate encoder access. JSON-RPC calls use the page's own "rpc" channel.
// PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
//   node tools/jetkvm-smoke.mjs [URL] [--seconds N] [--call METHOD JSON]... [--expect-codec video/H265]
//   [--terminal COMMAND]  runs COMMAND in the web terminal and prints its output
// Without --call it reads capabilities and settings only. Calls run in order
// after the video check; each result or error is printed. Exit 1 on no video,
// a wrong codec or a failed call.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args = process.argv.slice(2);
let url = 'http://192.168.50.210:8080';
let seconds = 10;
let expectCodec = null;
let terminal = null;
const calls = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--seconds') seconds = Number(args[++i]);
  else if (args[i] === '--expect-codec') expectCodec = args[++i];
  else if (args[i] === '--call') calls.push([args[++i], JSON.parse(args[++i])]);
  else if (args[i] === '--terminal') terminal = args[++i];
  else url = args[i];
}
if (!Number.isFinite(seconds) || seconds < 1 || seconds > 300) throw new Error('--seconds must be 1..300');
const reads = ['getDeviceCapabilities', 'getLocalVersion', 'getSupportedVideoCodecs', 'getVideoCodecPreference',
  'getStreamQualityFactor', 'getEDIDPresets', 'getEDID', 'getAudioConfig', 'getNetworkSettings', 'getNetworkState',
  'getUsbEmulationState', 'getVirtualMediaState', 'getStorageSpace', 'listStorageFiles', 'getTailscaleStatus',
  'getSSHUsername', 'getUpdateSource', 'getTLSState', 'getJigglerState', 'getMqttStatus'];

const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
let failed = false;
try {
  const page = await browser.newPage();
  await loginManager(page.context(), url);
  await page.addInitScript(() => {
    window.smokePeers = [];
    window.smokeEvents = [];
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) {
        super(...args);
        window.smokePeers.push(this);
        const create = this.createDataChannel.bind(this);
        this.createDataChannel = (label, options) => {
          const channel = create(label, options);
          if (label === 'rpc') {
            window.smokeRpc = channel;
            window.smokePending = new Map();
            channel.addEventListener('message', (event) => {
              const message = JSON.parse(event.data);
              const pending = message.id !== undefined && window.smokePending.get(message.id);
              if (pending) {
                window.smokePending.delete(message.id);
                pending(message);
              } else if (message.method) {
                window.smokeEvents.push(message.method);
              }
            });
          }
          return channel;
        };
      }
    };
    window.smokeCall = (method, params) => new Promise((resolve) => {
      const id = `smoke-${Math.random()}`;
      const timer = setTimeout(() => { window.smokePending.delete(id); resolve({ error: { message: 'timeout' } }); }, 90000);
      window.smokePending.set(id, (message) => { clearTimeout(timer); resolve(message); });
      window.smokeRpc.send(JSON.stringify({ jsonrpc: '2.0', method, params, id }));
    });
  });
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0 && window.smokeRpc?.readyState === 'open',
    {}, { timeout: 60000 });
  const sample = () => page.evaluate(async () => {
    const result = {};
    for (const peer of window.smokePeers) {
      const stats = await peer.getStats();
      for (const stat of stats.values()) {
        if (stat.type === 'inbound-rtp') {
          result[stat.kind] = { ...stat, codec: stats.get(stat.codecId)?.mimeType };
        }
      }
    }
    return result;
  });
  const start = await sample();
  await page.waitForTimeout(seconds * 1000);
  const end = await sample();
  const video = end.video;
  const report = {
    codec: video?.codec, width: video?.frameWidth, height: video?.frameHeight,
    decoded: (video?.framesDecoded ?? 0) - (start.video?.framesDecoded ?? 0),
    dropped: (video?.framesDropped ?? 0) - (start.video?.framesDropped ?? 0),
    packetsLost: (video?.packetsLost ?? 0) - (start.video?.packetsLost ?? 0),
    keyframes: (video?.keyFramesDecoded ?? 0) - (start.video?.keyFramesDecoded ?? 0),
    pliSent: video?.pliCount ?? 0,
    kbps: Math.round(((video?.bytesReceived ?? 0) - (start.video?.bytesReceived ?? 0)) * 8 / seconds / 1000),
    audio: end.audio && {
      codec: end.audio.codec,
      packets: (end.audio.packetsReceived ?? 0) - (start.audio?.packetsReceived ?? 0),
      energy: (end.audio.totalAudioEnergy ?? 0) - (start.audio?.totalAudioEnergy ?? 0),
    },
    seconds,
  };
  console.log(JSON.stringify({ video: report }));
  if (report.decoded < seconds * 5 || (expectCodec && report.codec !== expectCodec)) failed = true;
  for (const method of reads) {
    const response = await page.evaluate(([m]) => window.smokeCall(m, {}), [method]);
    console.log(JSON.stringify({ method, result: response.result, error: response.error }));
  }
  for (const [method, params] of calls) {
    const response = await page.evaluate(([m, p]) => window.smokeCall(m, p), [method, params]);
    console.log(JSON.stringify({ call: method, params, result: response.result, error: response.error }));
    if (response.error) failed = true;
  }
  if (terminal) {
    const output = await page.evaluate((command) => new Promise((resolve) => {
      const channel = window.smokePeers.at(-1).createDataChannel('terminal');
      let text = '';
      channel.onmessage = (event) => {
        text += typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data);
      };
      channel.onopen = () => setTimeout(() => channel.send(`${command}\n`), 500);
      setTimeout(() => { channel.close(); resolve(text); }, 4000);
    }), terminal);
    console.log(JSON.stringify({ terminal, output }));
  }
  console.log(JSON.stringify({ events: [...new Set(await page.evaluate(() => window.smokeEvents))] }));
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
