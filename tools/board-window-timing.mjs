// Receiving video occupies the application's encoder; caller coordinates access.
// Private receive-only page: never load product HID or audio scripts.
export async function connectVideo(page, url, localIP) {
  await page.route('**/__board_receiver', route => route.fulfill({contentType: 'text/html',
    body: '<video autoplay muted playsinline></video>'}));
  await page.goto(new URL('/__board_receiver', url).href);
  await page.evaluate(async localIP => {
    const pc = new RTCPeerConnection({iceServers: []});
    window.boardPeers = [pc];
    window.peers = [pc];
    pc.addTransceiver('video', {direction: 'recvonly'});
    pc.ontrack = e => { document.querySelector('video').srcObject = new MediaStream([e.track]); };
    await pc.setLocalDescription(await pc.createOffer());
    if (pc.iceGatheringState !== 'complete') {
      await Promise.race([new Promise(resolve => { pc.onicegatheringstatechange = () => {
        if (pc.iceGatheringState === 'complete') resolve();
      }; }), new Promise(r => setTimeout(r, 2000))]);
    }
    let sdp = pc.localDescription.sdp;
    if (/[\w-]+\.local/.test(sdp)) {
      if (!localIP) throw new Error('Host candidates use mDNS; supply receiver LAN IP');
      sdp = sdp.replace(/[\w-]+\.local/g, localIP);
    }
    const response = await fetch('/api/webrtc/offer', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sdp})});
    if (!response.ok) throw new Error('offer HTTP ' + response.status);
    const answer = await response.json();
    window.boardSession = answer.session_id;
    await pc.setRemoteDescription({type: 'answer', sdp: answer.sdp});
    for (const ice of answer.ice_candidates || []) await pc.addIceCandidate(ice);
  }, localIP);
}

export async function closeVideo(page) {
  await page.evaluate(async () => {
    for (const peer of window.boardPeers || []) peer.close();
    if (window.boardSession) await fetch('/api/webrtc/close', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: window.boardSession})});
  });
}

// Timing boundary separated from browser transport for deterministic replay.
export async function measureDecoded(sample, seconds, {
  now = () => performance.now(), sleep = ms => new Promise(r => setTimeout(r, ms)),
  readyTimeoutMs = 60000,
} = {}) {
  const readyDeadline = now() + readyTimeoutMs;
  let first;
  while (now() < readyDeadline) {
    first = await sample();
    if (first?.framesDecoded > 0) break;
    await sleep(50);
  }
  if (!(first?.framesDecoded > 0)) throw new Error('No actual decoded frame before readiness deadline');
  const started = now(), samples = [{ elapsedMs: 0, ...first }];
  while (now() - started < seconds * 1000) {
    await sleep(Math.min(50, seconds * 1000 - (now() - started)));
    const stat = await sample();
    if (!stat || stat.ssrc !== first.ssrc || stat.id !== first.id || stat.codec !== first.codec ||
        stat.framesDecoded < samples.at(-1).framesDecoded) {
      throw new Error('Video stream changed; discard measurement');
    }
    samples.push({ elapsedMs: now() - started, ...stat });
  }
  const last = samples.at(-1);
  if (last.framesDecoded <= first.framesDecoded) throw new Error('Decoded frames stopped');
  return { intervalMs: 50, elapsedMs: now() - started, samples,
    fps: (last.framesDecoded - first.framesDecoded) * 1000 / last.elapsedMs };
}
