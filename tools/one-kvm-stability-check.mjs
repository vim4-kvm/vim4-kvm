// Exclusive motion/AV soak. Run latency-source.swift with --verify-coherence
// --sync-audio=HDMI_NAME separately. Input HDR state is owned by the caller.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {loginManager} from './manager-login.mjs';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const args=process.argv.slice(2);
assert(args.includes('--exclusive'),'Coordinate board access and pass --exclusive');
const option=(name,fallback)=>args.find(arg=>arg.startsWith(`--${name}=`))?.slice(name.length+3) ?? fallback;
const url=option('url','http://192.168.50.210:8080'),mode=option('mode','h265');
const seconds=Number(option('seconds','1800')),board=option('board','vim4');
let stopping=false;
process.once('SIGINT',()=>{stopping=true});
process.once('SIGTERM',()=>{stopping=true});
assert(['h264','h265'].includes(mode));
assert(Number.isInteger(seconds)&&seconds>=10&&seconds<=7200);
assert(/^[a-zA-Z0-9_.@-]+$/.test(board));
const boardState=()=>JSON.parse(execFileSync('ssh',[board,'sudo','-n','python3','-'],{
  encoding:'utf8',timeout:10000,input:`
import json,os,subprocess,time
from pathlib import Path
pid=int(subprocess.check_output(['systemctl','show','one-kvm-edge','-p','MainPID','--value']))
proc=Path('/proc')/str(pid)
stat=(proc/'stat').read_text().split(') ')[1].split()
memory=dict(line.replace(':','').split()[:2] for line in Path('/proc/meminfo').read_text().splitlines())
fan=Path('/sys/bus/platform/devices/khadas-mcu-fan-ctrl')
print(json.dumps(dict(time=time.monotonic(),pid=pid,ticks=int(stat[11])+int(stat[12]),
 hz=os.sysconf('SC_CLK_TCK'),rss_kib=int(stat[21])*os.sysconf('SC_PAGE_SIZE')//1024,
 fds=len(list((proc/'fd').iterdir())),cma_free_kib=int(memory['CmaFree']),
 cpu=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:])),
 temperature_millic=int((fan/'temperature_millic').read_text()),
 fan_percent=int((fan/'speed_percent').read_text()),sensor_fault=int((fan/'sensor_fault').read_text()),
 taint=int(Path('/proc/sys/kernel/tainted').read_text()),
 vdin=Path('/sys/kernel/debug/ff000000.video-capture/status').read_text())))
` }));
const browser=await chromium.launch({...(process.env.VIM4_TEST_CHROME
  ? {executablePath:process.env.VIM4_TEST_CHROME}:{channel:'chrome'}),headless:true,
  args:['--autoplay-policy=no-user-gesture-required']});
let context,originalMode;
try {
  context=await browser.newContext();await loginManager(context,url);
  originalMode=(await(await context.request.get(url+'/api/stream/mode')).json()).mode;
  if(originalMode!==mode)assert((await context.request.post(url+'/api/stream/mode',{data:{mode}})).ok());
  const settings=await(await context.request.get(url+'/api/config/stream')).json();
  const profile={encoder:settings.encoder,bitratePreset:settings.bitrate_preset};
  const page=await context.newPage();
  await page.addInitScript(()=>{
    window.soak={peers:[],audioEdges:[],videoEdges:[],gaps:[],readbackCosts:[],audioPollGaps:[],audioPeak:0};
    const Native=window.RTCPeerConnection;
    window.RTCPeerConnection=class extends Native {
      constructor(...args){super(...args);window.soak.peers.push(this);
        this.addEventListener('track',e=>{
          if(e.track.kind!=='audio')return;e.track.enabled=true;
          const ctx=new AudioContext({sampleRate:48000}),source=ctx.createMediaStreamSource(new MediaStream([e.track]));
          const analyser=ctx.createAnalyser(),silent=ctx.createGain();analyser.fftSize=128;silent.gain.value=0;
          source.connect(analyser);analyser.connect(silent);silent.connect(ctx.destination);ctx.resume().catch(()=>{});
          const data=new Float32Array(128);let wasOn=false,lastPoll=performance.now();
          setInterval(()=>{
            analyser.getFloatTimeDomainData(data);let peak=0;
            for(const n of data)peak=Math.max(peak,Math.abs(n));
            window.soak.audioPeak=Math.max(window.soak.audioPeak,peak);
            const now=performance.now();window.soak.audioPollGaps.push(now-lastPoll);lastPoll=now;
            const on=peak>.02;
            if(on&&!wasOn){
              const output=ctx.getOutputTimestamp();
              // Use the audio render clock, not delivery time on the busy UI
              // thread. The 128-sample analyser window bounds edge precision.
              const audioTime=ctx.currentTime-data.length/ctx.sampleRate;
              window.soak.audioEdges.push(output.performanceTime+(audioTime-output.contextTime)*1000);
            }
            wasOn=on;
          },5);
        });
      }
    };
  });
  await page.goto(url);
  await page.waitForFunction(()=>document.querySelector('video')?.videoWidth===3840,{}, {timeout:45000});
  await page.evaluate(()=>{
    const video=document.querySelector('video'),canvas=document.createElement('canvas');canvas.width=1;canvas.height=1;
    const ctx=canvas.getContext('2d',{willReadFrequently:false});let last,wasOn=false;
    const onFrame=(_now,frame)=>{
      if(last!==undefined)window.soak.gaps.push(frame.presentationTime-last);last=frame.presentationTime;
      window.soak.presented=frame.presentedFrames;
      const probeStarted=performance.now();
      ctx.drawImage(video,video.videoWidth*.5,video.videoHeight*700/1080,1,1,0,0,1,1);
      const on=ctx.getImageData(0,0,1,1).data[0]>128;
      window.soak.readbackCosts.push(performance.now()-probeStarted);
      if(on&&!wasOn)window.soak.videoEdges.push(frame.presentationTime);wasOn=on;
      video.requestVideoFrameCallback(onFrame);
    };video.requestVideoFrameCallback(onFrame);
  });
  const sample=()=>page.evaluate(async()=>{
    let videoStats,audioStats,mediaPath;
    for(const peer of window.soak.peers)if(peer.connectionState==='connected'){
      const report=await peer.getStats();
      for(const s of report.values())if(s.type==='candidate-pair'&&s.nominated&&s.state==='succeeded'){
        const local=report.get(s.localCandidateId),remote=report.get(s.remoteCandidateId);
        mediaPath={local:local?.address,remote:remote?.address,protocol:local?.protocol,localType:local?.candidateType};
      }
      for(const s of report.values())if(s.type==='inbound-rtp'){
        const item={ssrc:s.ssrc,time:s.timestamp,frames:s.framesDecoded,width:s.frameWidth,height:s.frameHeight,
          lost:s.packetsLost,dropped:s.framesDropped,freezes:s.freezeCount,bytes:s.bytesReceived,
          jitterDelay:s.jitterBufferDelay,jitterEmitted:s.jitterBufferEmittedCount,
          samples:s.totalSamplesReceived,concealed:s.concealedSamples,mime:report.get(s.codecId)?.mimeType};
        if(s.kind==='video')videoStats=item;else if(s.kind==='audio')audioStats=item;
      }
    }
    const video=document.querySelector('video'),frame=await createImageBitmap(video);
    const snapshotMs=Date.now();
    const canvas=document.createElement('canvas');canvas.width=32;canvas.height=3;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    // Hold one decoded frame while sampling all three rows. Separate reads
    // from the live video can span frames and falsely report torn DMA.
    for(let row=0;row<3;row++)for(let bit=0;bit<32;bit++)ctx.drawImage(frame,
      video.videoWidth*(20+(bit+.5)*1880/32)/1920,video.videoHeight*[85,540,995][row]/1080,1,1,bit,row,1,1);
    frame.close();
    const pixels=ctx.getImageData(0,0,32,3).data;
    const markers=[0,1,2].map(row=>{
      let word=0;for(let bit=0;bit<32;bit++)word=(word*2+(pixels[(row*32+bit)*4]>128?1:0))>>>0;
      const id=(word>>>8)&65535;return {id,valid:(word>>>24)===0xa5&&(word&255)===(((id>>>8)^(id&255)^0xa5)&255)};
    });
    const result={video:videoStats,audio:audioStats,mediaPath,markers,snapshotMs,audioPeak:window.soak.audioPeak,
      coveringOverlays:document.querySelectorAll('[class*="bg-black/70"][class*="backdrop-blur-sm"], img[src^="data:image/jpeg"]').length,
      presented:window.soak.presented,readbackCosts:window.soak.readbackCosts.splice(0),
      gaps:window.soak.gaps.splice(0),audioPollGaps:window.soak.audioPollGaps.splice(0),
      audioEdges:window.soak.audioEdges.splice(0),videoEdges:window.soak.videoEdges.splice(0)};
    window.soak.audioPeak=0;return result;
  });
  await page.waitForTimeout(15000);
  let previous=await sample(),previousBoard=boardState(),initial=previous.video;
  assert(initial?.frames>0,'No decoded video after warmup');
  const start=Date.now(),audioEdges=[],videoEdges=[],skews=[];
  console.log(JSON.stringify({kind:'start',mode,seconds,profile,browser:browser.version(),sample:{...previous,gaps:undefined,audioPollGaps:undefined,readbackCosts:undefined},board:previousBoard}));
  while(Date.now()-start<seconds*1000){
    await page.waitForTimeout(10000);
    assert(!stopping,'Stability measurement cancelled');
    const next=await sample(),resource=boardState(),elapsed=(next.video.time-previous.video.time)/1000;
    const fps=(next.video.frames-previous.video.frames)/elapsed;
    const procCpu=100*(resource.ticks-previousBoard.ticks)/resource.hz/(resource.time-previousBoard.time);
    const ticks=resource.cpu.map((n,i)=>n-previousBoard.cpu[i]),total=ticks.slice(0,8).reduce((a,b)=>a+b,0);
    const cpuBusy=100*(total-ticks[3]-ticks[4])/total;
    audioEdges.push(...next.audioEdges);videoEdges.push(...next.videoEdges);
    const sorted=[...next.gaps].sort((a,b)=>a-b),p=f=>sorted[Math.floor((sorted.length-1)*f)];
    console.log(JSON.stringify({kind:'window',seconds:(Date.now()-start)/1000,mode,fps,procCpu,cpuBusy,
      receivedMbps:8*(next.video.bytes-previous.video.bytes)/elapsed/1e6,
      presentedFps:(next.presented-previous.presented)/elapsed,
      presentationMs:{p50:p(.5),p99:p(.99),max:p(1)},audioPollMaxMs:Math.max(...next.audioPollGaps),
      readbackMeanMs:next.readbackCosts.reduce((a,b)=>a+b,0)/next.readbackCosts.length,
      readbackMaxMs:Math.max(...next.readbackCosts),
      sample:{...next,gaps:undefined,audioPollGaps:undefined,readbackCosts:undefined},board:resource}));
    assert.equal(next.video.ssrc,initial.ssrc,'Unexpected reconnect');
    assert.equal(next.coveringOverlays,0,'An overlay covered the live video');
    assert.equal(next.video.mime.toLowerCase(),`video/${mode}`,'Actual codec differs');
    for(const metric of ['lost','dropped','freezes'])assert.equal(next.video[metric],initial[metric],`Video ${metric} increased`);
    assert.deepEqual([next.video.width,next.video.height],[3840,2160]);
    assert(next.markers.every(m=>m.valid&&m.id===next.markers[0].id),'Incoherent source markers');
    assert.notEqual(next.markers[0].id,previous.markers[0].id,'Source content stopped');
    assert(fps>55&&fps<65,'Decoded cadence outside UHD60 range: '+fps);
    assert(next.audioPeak>.02,'Audio pulse missing');
    assert.equal(resource.pid,previousBoard.pid,'Service restarted');
    assert.equal(resource.taint,0);assert.equal(resource.sensor_fault,0);
    assert(resource.vdin.includes('faulted: 0\n'),'VDIN DMA fault');
    previous=next;previousBoard=resource;
  }
  for(const edge of videoEdges){
    const nearest=audioEdges.reduce((best,a)=>Math.abs(a-edge)<Math.abs(best-edge)?a:best,Infinity);
    if(Math.abs(nearest-edge)<800)skews.push({videoMs:edge,audioMinusVideoMs:nearest-edge});
  }
  assert(skews.length>=Math.floor(seconds/2)*.8,'Insufficient matched A/V pulses');
  console.log(JSON.stringify({kind:'complete',mode,seconds:(Date.now()-start)/1000,skews}));
} finally {
  try {
    if(context&&originalMode&&originalMode!==mode)
      await context.request.post(url+'/api/stream/mode',{data:{mode:originalMode}});
  } finally {await browser.close();}
}
const deadline=Date.now()+15000;
while(true){
  const dma=execFileSync('ssh',[board,'sudo','-n','cat','/sys/kernel/debug/dma_buf/bufinfo'],{encoding:'utf8',timeout:5000});
  if(dma.includes('Total 0 objects, 0 bytes'))break;
  assert(Date.now()<deadline,'DMA retained after closing viewer');await new Promise(resolve=>setTimeout(resolve,250));
}
console.log(JSON.stringify({kind:'idle',dmaBytes:0}));
