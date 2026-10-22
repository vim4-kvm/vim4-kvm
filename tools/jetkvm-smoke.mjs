import { loginManager } from './manager-login.mjs';
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
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
let expectAudio = false;
let checkUSB = false;
const calls = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--seconds') seconds = Number(args[++i]);
  else if (args[i] === '--expect-codec') expectCodec = args[++i];
  else if (args[i] === '--call') calls.push([args[++i], JSON.parse(args[++i])]);
  else if (args[i] === '--terminal') terminal = args[++i];
  else if (args[i] === '--audio') expectAudio = true;
  else if (args[i] === '--usb') checkUSB = true;
  else url = args[i];
}
if (!Number.isFinite(seconds) || seconds < 1 || seconds > 300) throw new Error('--seconds must be 1..300');
const reads = ['getDeviceCapabilities', 'getLocalVersion', 'getSupportedVideoCodecs', 'getVideoCodecPreference',
  'getStreamQualityFactor', 'getEDIDPresets', 'getEDID', 'getAudioConfig', 'getNetworkSettings', 'getNetworkState',
  'getUsbEmulationState', 'getVirtualMediaState', 'getStorageSpace', 'listStorageFiles', 'getTailscaleStatus',
  'getSSHUsername', 'getUpdateSource', 'getTLSState', 'getJigglerState', 'getMqttStatus'];

const browser = await chromium.launch({ ...(process.env.VIM4_TEST_CHROME
  ? { executablePath: process.env.VIM4_TEST_CHROME } : { channel: 'chrome' }), headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'] });
let failed = false;
try {
  const page = await browser.newPage();
  await loginManager(page.context(), url);
  await page.addInitScript(() => {
    window.smokePeers = [];
    window.smokeEvents = [];
    window.smokeAudioPeak = 0;
    window.smokeHID = [];
    // Decode without playing the captured sound back into this HDMI source.
    document.addEventListener('play', event => {
      if (event.target instanceof HTMLMediaElement) event.target.muted = true;
    }, true);
    const Original = RTCPeerConnection;
    window.RTCPeerConnection = class extends Original {
      constructor(...args) {
        super(...args);
        window.smokePeers.push(this);
        this.addEventListener('track', event => {
          if (event.track.kind !== 'audio') return;
          const audio = new AudioContext({sampleRate:48000});
          const source = audio.createMediaStreamSource(new MediaStream([event.track]));
          const analyser = audio.createAnalyser(), silent = audio.createGain();
          silent.gain.value = 0;
          source.connect(analyser).connect(silent).connect(audio.destination);
          void audio.resume();
          const values = new Float32Array(analyser.fftSize);
          setInterval(() => {
            analyser.getFloatTimeDomainData(values);
            for (const value of values) window.smokeAudioPeak = Math.max(window.smokeAudioPeak,Math.abs(value));
          },50);
        });
        const create = this.createDataChannel.bind(this);
        this.createDataChannel = (label, options) => {
          const channel = create(label, options);
          if (label.startsWith('hidrpc')) {
            const send = channel.send.bind(channel);
            channel.send = data => { window.smokeHID.push({label,bytes:Array.from(new Uint8Array(data))}); return send(data); };
          }
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
  if (expectAudio) {
    const peak = await page.evaluate(() => window.smokeAudioPeak);
    console.log(JSON.stringify({decodedAudioPeak:peak}));
    if (peak <= 0.001) failed = true;
  }
  if (checkUSB) {
    const foreground = () => Number(execFileSync('osascript',['-l','JavaScript','-e',
      'ObjC.import("AppKit"); $.NSWorkspace.sharedWorkspace.frontmostApplication.processIdentifier'],
    {encoding:'utf8'}).trim());
    const target = spawn(process.env.VIM4_INPUT_TARGET || '/tmp/vim4-input-target',['20']);
    const events = [];
    let pending = '';
    const ready = new Promise((resolve,reject) => {
      const timeout = setTimeout(() => reject(new Error('Native input target was not ready')),5000);
      target.on('error',reject);
      target.stdout.on('data',chunk => {
        pending += chunk;
        const lines = pending.split('\n'); pending = lines.pop();
        for (const line of lines) {
          const event = JSON.parse(line); events.push(event);
          if (event.kind === 'ready') { clearTimeout(timeout); resolve(); }
        }
      });
    });
    try {
      await ready;
      assert.equal(foreground(),target.pid,'Only the temporary target may receive host input');
      await page.locator('video').click();
      assert.equal(foreground(),target.pid,'A remote click must stay inside the temporary target');
      await page.keyboard.press('ArrowRight',{delay:100});
      await page.waitForTimeout(500);
      const diagnostic = JSON.stringify({events,sent:await page.evaluate(() => window.smokeHID)});
      assert(events.some(event => event.kind === 'keydown' && event.key === 124),diagnostic);
      assert(events.some(event => event.kind === 'keyup' && event.key === 124));
      assert(events.some(event => event.kind === 'mousedown'));
      assert(events.some(event => event.kind === 'mouseup'));
      console.log(JSON.stringify({nativeHID:{keyboard:true,click:true,events:events.length}}));
    } finally {
      await page.keyboard.up('ArrowRight').catch(() => {});
      target.stdin.end();
    }
  }
  if (report.decoded < seconds * 5 || (expectCodec && report.codec !== expectCodec)) failed = true;
  for (const method of reads) {
    const response = await page.evaluate(([m]) => window.smokeCall(m, {}), [method]);
    const result = method === 'getTLSState' && response.result ? {
      mode:response.result.mode,hasCertificate:!!response.result.certificate,hasPrivateKey:!!response.result.privateKey,
    } : response.result;
    console.log(JSON.stringify({ method, result, error: response.error }));
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
