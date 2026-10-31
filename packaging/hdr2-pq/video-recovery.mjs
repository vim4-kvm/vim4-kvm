// Video-only receiver: no product input scripts, audio or data channels.
// Use an owned SSH forward to the One-KVM API and an exclusive board window.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = new URL(process.argv[2] || 'http://127.0.0.1:18084');
const seconds = Number(process.argv[3] || 180);
const sampleMs = Number(process.env.HDR2_SAMPLE_MS || 250);
const literalHostCandidates = process.argv.includes('--literal-host-candidates');
if (!Number.isFinite(seconds) || seconds < 1 || seconds > 600) throw Error('duration must be 1..600 seconds');
if (!Number.isFinite(sampleMs) || sampleMs < 50 || sampleMs > 1000) throw Error('HDR2_SAMPLE_MS must be 50..1000');
// Opt-in for isolated LAN diagnostics when the peer cannot resolve .local
// candidates. This changes only this owned browser process, not host networking.
const b=await chromium.launch({channel:'chrome',headless:true,
 args:literalHostCandidates ? ['--disable-features=WebRtcHideLocalIpsWithMdns'] : []});
const c=await b.newContext();
await c.route('**/__hdr_test',route=>route.fulfill({contentType:'text/html',body:'<video autoplay muted></video>'}));
const p=await c.newPage();
try {
 await p.goto(new URL('/__hdr_test', origin).href);
 console.log(await p.evaluate(async()=>{
  const api=async(path,data)=>{
   const r=await fetch('/api/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});
   if(!r.ok)throw Error(path+': '+r.status+' '+await r.text());return r.json();
  };
  const pc=window.pc=new RTCPeerConnection({iceServers:[]});
  pc.addTransceiver('video',{direction:'recvonly'});
  pc.ontrack=e=>{document.querySelector('video').srcObject=new MediaStream([e.track]);};
  await pc.setLocalDescription(await pc.createOffer());
  await Promise.race([new Promise(resolve=>{pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete')resolve();};}),new Promise(r=>setTimeout(r,2000))]);
  const a=await api('webrtc/offer',{sdp:pc.localDescription.sdp});window.sid=a.session_id;
  window.iceCandidates={local:pc.localDescription.sdp.split('\n').filter(x=>x.startsWith('a=candidate:')),
   remote:a.sdp.split('\n').filter(x=>x.startsWith('a=candidate:')),extra:a.ice_candidates};
  await pc.setRemoteDescription({type:'answer',sdp:a.sdp});
  for(const ice of a.ice_candidates||[])await pc.addIceCandidate(ice);
  return {session:a.session_id};
 }));
 try {await p.waitForFunction(()=>document.querySelector('video').videoWidth>0,{},{timeout:20000});}
 finally {console.log(JSON.stringify(await p.evaluate(async()=>({
  candidates:window.iceCandidates,ice:window.pc.iceConnectionState,
  stats:[...(await window.pc.getStats()).values()].filter(x=>
   ['candidate-pair','local-candidate','remote-candidate','transport','inbound-rtp'].includes(x.type))
 }))));}
 for(let i=0;i<seconds*1000/sampleMs;i++){
  const stats=await p.evaluate(async()=>{
   const rows=[];for(const r of(await window.pc.getStats()).values())if(r.type==='inbound-rtp'&&r.kind==='video')rows.push({frameWidth:r.frameWidth,frameHeight:r.frameHeight,framesDecoded:r.framesDecoded,keyFramesDecoded:r.keyFramesDecoded,totalDecodeTime:r.totalDecodeTime,lastPacketReceivedTimestamp:r.lastPacketReceivedTimestamp,framesDropped:r.framesDropped,packetsLost:r.packetsLost,freezeCount:r.freezeCount,bytesReceived:r.bytesReceived});
   return {at:Date.now(),video:rows};
  });console.log(JSON.stringify(stats));await p.waitForTimeout(sampleMs);
 }
} finally {
 await p.evaluate(async()=>{if(window.pc)window.pc.close();if(window.sid)await fetch('/api/webrtc/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:window.sid})});}).catch(()=>{});
 await b.close();
}
