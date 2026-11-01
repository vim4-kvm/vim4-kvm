// Video-only P0-5 receiver; no input actions, audio analysis or source changes.
// Caller owns a board-queue ticket and sampling lease. Configure the selected
// application/codec/size before invoking this bounded receiver.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { loginManager } from '../../tools/manager-login.mjs';
import { measureDecoded } from '../../tools/board-window-timing.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
export async function receive({url, app, output, hdr = 'pq', seconds = 20,
  codec = 'video/H265', minFps = 59, localBackend = false, width, height, localIP, prepareSource = false}) {
assert(['onekvm', 'nanokvm', 'jetkvm', 'pikvm'].includes(app));
assert(['pq', 'sdr'].includes(hdr));
assert(seconds >= 1 && seconds <= 300);
await fs.mkdir(output, { recursive: false });
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--autoplay-policy=no-user-gesture-required', '--disable-features=WebRtcHideLocalIpsWithMdns'] });
// The window stops its process group on the first kernel fault. Close the
// browser too; Playwright launches it outside that group on some platforms.
const interrupted = () => { browser.close().finally(() => process.exit(130)); };
process.once('SIGTERM', interrupted);
process.once('SIGINT', interrupted);
try {
  const context = await browser.newContext();
  await loginManager(context, url, {localBackend});
  await context.addInitScript(app => {
    if (app === 'nanokvm') localStorage.setItem('nano-kvm-vide-mode', 'h265');
    window.hdrPeers = []; window.hdrPrefix = null; window.hdrColor = null;
    const Peer = RTCPeerConnection;
    window.RTCPeerConnection = class extends Peer {
      constructor(config, options) {
        super({ ...config, encodedInsertableStreams: true }, options);
        window.hdrPeers.push(this);
        this.addEventListener('track', async event => {
          if (event.track.kind !== 'video') return;
          const { readable, writable } = event.receiver.createEncodedStreams();
          window.hdrErrors = [];
          readable.pipeThrough(new TransformStream({ transform(frame, controller) {
            if (!window.hdrPrefix && frame.type === 'key') window.hdrPrefix = Array.from(new Uint8Array(frame.data));
            controller.enqueue(frame);
          }})).pipeTo(writable).catch(error => { window.hdrErrors.push(String(error)); });
          const clone = event.track.clone();
          const reader = new MediaStreamTrackProcessor({ track: clone }).readable.getReader();
          try {
            const sample = await reader.read();
            if (sample.value) {
              window.hdrColor = sample.value.colorSpace.toJSON();
              sample.value.close();
            }
          } catch(error) { window.hdrErrors.push(String(error)); }
          finally { await reader.cancel(); clone.stop(); }
        });
      }
      createDataChannel(label, options) {
        const channel = super.createDataChannel(label, options);
        if (/hid|keyboard|mouse/i.test(label)) channel.send = () => {};
        return channel;
      }
    };
    const Socket = WebSocket;
    window.WebSocket = class extends Socket {
      send(data) {
        if (typeof data !== 'string') return;
        try {
          const message = JSON.parse(data);
          const kind = message.event_type || message.type || '';
          if (/key|mouse|hid/i.test(kind)) return;
        } catch { return; }
        return super.send(data);
      }
    };
    document.addEventListener('play', event => {
      if (event.target instanceof HTMLMediaElement) event.target.muted = true;
    }, true);
  }, app);
  const page = await context.newPage();
  page.on('pageerror', error => console.error('Receiver page:', error.message));
  if (app === 'onekvm') {
    await context.route('**/__phase2_receiver', route => route.fulfill({contentType:'text/html',body:'<video autoplay muted playsinline></video>'}));
    await page.goto(new URL('/__phase2_receiver',url).href);
    await page.evaluate(async localIP => {
      const pc=new RTCPeerConnection({iceServers:[]});
      pc.addTransceiver('video',{direction:'recvonly'});
      pc.ontrack=e=>{document.querySelector('video').srcObject=new MediaStream([e.track]);};
      await pc.setLocalDescription(await pc.createOffer());
      if(pc.iceGatheringState!=='complete')await Promise.race([
        new Promise(resolve=>pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete')resolve();}),
        new Promise(resolve=>setTimeout(resolve,2000))]);
      let sdp=pc.localDescription.sdp;
      if (/[\w-]+\.local/.test(sdp)) {
        if (!localIP) throw Error('Host candidates still use mDNS; supply receiver LAN IP');
        sdp=sdp.replace(/[\w-]+\.local/g,localIP);
      }
      const response=await fetch('/api/webrtc/offer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sdp})});
      if(!response.ok)throw Error('offer HTTP '+response.status);
      const answer=await response.json();window.hdrSession=answer.session_id;
      await pc.setRemoteDescription({type:'answer',sdp:answer.sdp});
      for(const ice of answer.ice_candidates||[])await pc.addIceCandidate(ice);
    },localIP);
  } else await page.goto(url);
  await page.waitForFunction(() => {
    if (window.hdrErrors?.length) throw Error(window.hdrErrors.join('; '));
    return [...document.querySelectorAll('video')].some(v => v.videoWidth > 0)
      && window.hdrColor && window.hdrPrefix;
  }, null, { timeout: 45000 });
  const stats = () => page.evaluate(async () => {
    for (const peer of window.hdrPeers) {
      const reports = await peer.getStats();
      for (const report of reports.values()) {
        if (report.type === 'inbound-rtp' && report.kind === 'video' && report.framesDecoded > 0)
          return { ...report, codec: reports.get(report.codecId) };
      }
    }
    throw Error('No decoded video');
  });
  const before = await stats();
  if (prepareSource) {
    const warm = await measureDecoded(async () => {
      const value = await stats(); return {...value, codec:value.codec.mimeType};
    }, 2, {readyTimeoutMs:1000});
    const first = warm.samples[0], last = warm.samples.at(-1);
    const proof = {decoded:last.framesDecoded-first.framesDecoded,
      dropped:last.framesDropped-first.framesDropped,fps:warm.fps};
    assert(proof.decoded>0 && proof.fps>=minFps && proof.dropped===0,JSON.stringify(proof));
    const jpeg = await page.evaluate(() => {
      const video=document.querySelector('video'), canvas=document.createElement('canvas');
      canvas.width=Math.min(1920,video.videoWidth);
      canvas.height=Math.round(video.videoHeight*canvas.width/video.videoWidth);
      canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
      return canvas.toDataURL('image/jpeg',.95).split(',')[1];
    });
    await fs.writeFile(`${output}/source-ready.jpg`,Buffer.from(jpeg,'base64'));
    await fs.writeFile(`${output}/ready.json.tmp`,JSON.stringify(proof));
    await fs.rename(`${output}/ready.json.tmp`,`${output}/ready.json`);
  }
  const cadence = await measureDecoded(async () => {
    const value = await stats();
    return { ...value, codec: value.codec.mimeType };
  }, seconds, {readyTimeoutMs: 1000});
  const after = await stats();
  const evidence = await page.evaluate(() => ({ color: window.hdrColor, prefix: window.hdrPrefix }));
  const result = { app, hdr, elapsed: (after.timestamp - before.timestamp) / 1000,
    decoded: after.framesDecoded - before.framesDecoded,
    dropped: after.framesDropped - before.framesDropped,
    width: after.frameWidth, height: after.frameHeight, color: evidence.color, codec: after.codec };
  result.fps = result.decoded / result.elapsed;
  await fs.writeFile(`${output}/first-keyframe.${codec === 'video/H265' ? 'h265' : 'encoded'}`, Buffer.from(evidence.prefix));
  await fs.writeFile(`${output}/result.json`, JSON.stringify({ result, before, after, cadence }, null, 2));
  assert.equal(result.codec.mimeType.toLowerCase(), codec.toLowerCase());
  assert(result.decoded > 0 && result.fps >= minFps && result.dropped === 0, JSON.stringify(result));
  if (width) assert.equal(result.width, width);
  if (height) assert.equal(result.height, height);
  if (hdr === 'pq') {
    assert.equal(result.color.transfer, 'pq');
    assert.equal(result.color.primaries, 'bt2020');
    assert.equal(result.color.matrix, 'bt2020-ncl');
    assert.equal(result.color.fullRange, false);
  } else assert(!['pq', 'smpte2084'].includes(result.color.transfer));
  console.log(JSON.stringify(result));
  return result;
} finally {
  process.removeListener('SIGTERM', interrupted);
  process.removeListener('SIGINT', interrupted);
  for(const context of browser.contexts())for(const page of context.pages()) {
    await page.evaluate(async()=>{
      for(const peer of window.hdrPeers||[])peer.close();
      if(window.hdrSession)await fetch('/api/webrtc/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:window.hdrSession})});
    }).catch(()=>{});
  }
  await browser.close();
}
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [url, app, output, hdr = 'pq', seconds = '20', width, height, localIP] = process.argv.slice(2);
  await receive({ url, app, output, hdr, seconds: Number(seconds),
    width: width ? Number(width) : undefined, height: height ? Number(height) : undefined, localIP,
    prepareSource: process.argv.includes('--prepare-source') });
}
