// Exclusive software A/V measurement; start latency-source.swift --sync-audio
// separately. --calibrate=clip.mp4 --expected-ms=120 measures a known offset
// without board access. Clips must flash the center pixel every two seconds.
// Tab loopback adds latency: calibrate with the same browser before interpreting
// absolute skew. Does not change EDID, restart services, or reboot the board.
import assert from 'node:assert/strict';
import {loginManager} from './manager-login.mjs';
import {installAVSyncProbe,summarizeAVSync} from './av-sync-probe.mjs';
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const args=process.argv.slice(2);
const option=(name,fallback)=>args.find(arg=>arg.startsWith(`--${name}=`))?.slice(name.length+3)??fallback;
const calibration=option('calibrate',null),expectedMs=Number(option('expected-ms','0'));
assert(Number.isFinite(expectedMs)&&Math.abs(expectedMs)<800);
if(!calibration)assert(args.includes('--exclusive'),'Coordinate board access and pass --exclusive');
const url=option('url','http://192.168.50.210:8080'),mode=option('mode','h265');
const seconds=Number(option('seconds','180'));
assert(['h264','h265'].includes(mode));assert(Number.isInteger(seconds)&&seconds>=30&&seconds<=1800);
let stopping=false;
process.once('SIGINT',()=>{stopping=true;});process.once('SIGTERM',()=>{stopping=true;});
const browser=await chromium.launch({...(process.env.VIM4_TEST_CHROME?{executablePath:process.env.VIM4_TEST_CHROME}:{channel:'chrome'}),
  headless:true,ignoreDefaultArgs:['--mute-audio'],args:['--autoplay-policy=no-user-gesture-required','--auto-accept-this-tab-capture',
    `--unsafely-treat-insecure-origin-as-secure=${new URL(url).origin}`]});
let context,originalMode,server;
try{
  context=await browser.newContext();
  if(calibration){
    const media=readFileSync(calibration);
    server=createServer((req,res)=>{
      if(req.url==='/clip.mp4'){
        res.writeHead(200,{'Content-Type':'video/mp4','Content-Length':media.length});res.end(media);
      }else{res.setHeader('Content-Type','text/html');res.end('<video src="/clip.mp4" playsinline></video>');}
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const page=await context.newPage();await page.goto('http://127.0.0.1:'+server.address().port);
    await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
    const clock=await page.evaluate(installAVSyncProbe,{y:.5});
    console.log(JSON.stringify({kind:'start',calibration,expectedMs,browser:browser.version(),clock}));
    const duration=await page.evaluate(()=>document.querySelector('video').duration);
    assert(Number.isFinite(duration)&&duration>=20&&duration<=1800,'Calibration clip must last 20–1800 seconds');
    const deadline=Date.now()+(duration+30)*1000;
    while(!await page.evaluate(()=>document.querySelector('video').ended)){
      await page.waitForTimeout(10000);
      assert(!stopping,'Calibration cancelled');assert(Date.now()<deadline,'Calibration playback stalled');
      console.log(JSON.stringify({kind:'window',...await page.evaluate(()=>({
        audioEdges:window.avSyncProbe.state.audioEdges.length,videoEdges:window.avSyncProbe.state.videoEdges.length,
        mediaTime:document.querySelector('video').currentTime}))}));
    }
    const state=await page.evaluate(()=>window.avSyncProbe.state);
    console.log(JSON.stringify({kind:'raw',state}));
    console.log(JSON.stringify({kind:'complete',calibration,expectedMs,...summarizeAVSync(state,expectedMs)}));
  }else{
  await loginManager(context,url);
  originalMode=(await(await context.request.get(url+'/api/stream/mode')).json()).mode;
  if(originalMode!==mode)assert((await context.request.post(url+'/api/stream/mode',{data:{mode}})).ok());
  const page=await context.newPage();
  await page.addInitScript(()=>{
    window.avPeers=[];const Native=window.RTCPeerConnection;
    window.RTCPeerConnection=class extends Native{constructor(...args){super(...args);window.avPeers.push(this);}};
  });
  await page.goto(url);
  await page.waitForFunction(()=>document.querySelector('video')?.videoWidth===3840,{}, {timeout:45000});
  const clock=await page.evaluate(installAVSyncProbe);
  console.log(JSON.stringify({kind:'start',mode,seconds,browser:browser.version(),clock}));
  const start=Date.now();let initialStats,previousVideo;
  while(Date.now()-start<seconds*1000){
    await page.waitForTimeout(10000);
    assert(!stopping,'A/V measurement cancelled');
    const sample=await page.evaluate(async()=>{
      const stats=[];
      for(const peer of window.avPeers)if(peer.connectionState==='connected'){
        const report=await peer.getStats();
        for(const s of report.values())if(s.type==='inbound-rtp')stats.push({...s,mime:report.get(s.codecId)?.mimeType});
      }
      return {audioEdges:window.avSyncProbe.state.audioEdges.length,videoEdges:window.avSyncProbe.state.videoEdges.length,
        pulses:{startedMs:window.avSyncProbe.state.startedMs,audioEdges:window.avSyncProbe.state.audioEdges,
          videoEdges:window.avSyncProbe.state.videoEdges},
        stats,muted:document.querySelector('video').muted,clock:window.avSyncProbe.state.clocks.at(-1)};
    });
    const {pulses,...metrics}=sample;
    let progress;
    if(Date.now()-start>25000){const {pairs,...summary}=summarizeAVSync(pulses);progress=summary;}
    console.log(JSON.stringify({kind:'window',seconds:(Date.now()-start)/1000,...metrics,progress}));
    assert(sample.audioEdges>0,'Tab playback audio probe is silent');
    assert(sample.videoEdges>0,'Missing video pulses');
    const video=sample.stats.find(s=>s.kind==='video');
    const audio=sample.stats.find(s=>s.kind==='audio');
    assert(audio,'No inbound audio track');
    assert.equal(video?.mime.toLowerCase(),`video/${mode}`);
    assert.deepEqual([video.frameWidth,video.frameHeight],[3840,2160]);
    if(!initialStats)initialStats={audio,video};
    for(const track of [audio,video]){
      const initial=initialStats[track.kind];
      assert.equal(track.ssrc,initial.ssrc,'Unexpected peer replacement');
      assert.equal(track.packetsLost,initial.packetsLost,'RTP loss increased');
    }
    for(const metric of ['framesDropped','freezeCount'])
      assert.equal(video[metric],initialStats.video[metric],`Video ${metric} increased`);
    if(previousVideo){
      const fps=1000*(video.framesDecoded-previousVideo.framesDecoded)/(video.timestamp-previousVideo.timestamp);
      assert(fps>55&&fps<65,'Decoded cadence outside UHD60 range');
    }
    previousVideo=video;
  }
  const state=await page.evaluate(()=>window.avSyncProbe.state);
  console.log(JSON.stringify({kind:'raw',state}));
  const summary=summarizeAVSync(state);
  assert(summary.count>=Math.floor((seconds-15)/2)*.8,'Missing A/V pulse pairs');
  console.log(JSON.stringify({kind:'complete',mode,...summary}));
  }
}finally{
  try{if(context&&originalMode&&originalMode!==mode)
    assert((await context.request.post(url+'/api/stream/mode',{data:{mode:originalMode}})).ok());
  }finally{await browser.close();if(server)await new Promise(resolve=>server.close(resolve));}
}
