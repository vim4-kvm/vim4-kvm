// Objective receiver-side continuity probe for a known 440 Hz HDMI tone.
// Usage: --exclusive [--headed] [--seconds=45] [--context-rate=48000]
// Optional: --legacy-worklet, --decode-opus, --local-tone, --calibrate.
// --calibrate --inject-gap inserts 20 ms of silence and must exit nonzero.
// --trace=FILE saves a bounded Chrome media-stream trace for diagnosis only.
// AudioData observes the track before the extra MediaStreamAudioSourceNode FIFO.
// Tab capture includes rendered audio, but is not a physical speaker recording.
// Requires PLAYWRIGHT_MODULE, MANAGER_PASSWORD, VIM4_TEST_CHROME (or Chrome channel).
// Caller owns board/heavy locks and the source. AUDIO_RATES and AUDIO_RATE_TOOL
// optionally invoke an executable as TOOL DEVICE RATE between bounded segments.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
import {loginManager} from './manager-login.mjs';

const args = process.argv.slice(2);
const option = (name, fallback) => args.find(x => x.startsWith(`--${name}=`))?.split('=').slice(1).join('=') ?? fallback;
const seconds = Number(option('seconds', process.env.AUDIO_SECONDS || 45));
const calibrate = args.includes('--calibrate');
assert(!args.includes('--inject-gap') || calibrate, '--inject-gap requires local calibration');
assert(calibrate || args.includes('--exclusive'), 'Coordinate board access and pass --exclusive');
assert(seconds >= 10 && seconds <= 120, 'Segment duration must be 10..120 seconds');
const rates = (process.env.AUDIO_RATES || '48000').split(',').map(Number);
assert(rates.length <= 14 && rates.every(r => [32000,44100,48000,88200,96000,176400,192000].includes(r)));
const origin = process.env.VIM4_KVM_URL || 'http://192.168.50.210:8080';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const headless = !args.includes('--headed');
const browser = await chromium.launch({
  ...(process.env.VIM4_TEST_CHROME ? {executablePath:process.env.VIM4_TEST_CHROME} : {channel:'chrome'}),
  headless, ignoreDefaultArgs:['--mute-audio'],
  args:['--autoplay-policy=no-user-gesture-required', '--auto-accept-this-tab-capture',
    `--unsafely-treat-insecure-origin-as-secure=${origin}`,
    ...(process.env.CHROME_LOG_FILE ? ['--enable-logging','--vmodule=webaudio_media_stream_audio_sink=2'] : [])],
});
const emit = value => console.log(JSON.stringify(value));
const counters = ['jitterBufferDelay','jitterBufferEmittedCount','concealedSamples',
  'silentConcealedSamples','concealmentEvents','insertedSamplesForDeceleration',
  'removedSamplesForAcceleration','packetsLost'];
function statsDelta(before, after) {
  if(!before||!after)return null;
  const a=before.rows.find(row=>row.type==='inbound-rtp'&&row.kind==='audio');
  const b=after.rows.find(row=>row.type==='inbound-rtp'&&row.kind==='audio');
  if(!a||!b||a.ssrc!==b.ssrc)return null;
  const delta=Object.fromEntries(counters.filter(key=>key in a&&key in b).map(key=>[key,b[key]-a[key]]));
  return {from:before.wall,to:after.wall,ssrc:a.ssrc,delta,jitter:[a.jitter,b.jitter],
    meanJitterBufferMs:delta.jitterBufferEmittedCount>0 ? 1000*delta.jitterBufferDelay/delta.jitterBufferEmittedCount : null};
}
let failed = false;
let traceSession;
let traceStarted = false;
try {
  const context = await browser.newContext();
  const versionPage=await context.newPage();
  await versionPage.goto('chrome://version');
  const version=await versionPage.evaluate(()=>({commandLine:document.querySelector('#command_line')?.textContent,
    revision:document.querySelector('#revision')?.textContent}));
  emit({kind:'launch',...version});
  await versionPage.close();
  if (!calibrate) await loginManager(context, origin);
  const page = await context.newPage();
  if(option('trace', '')) {
    traceSession=await context.newCDPSession(page);
    await traceSession.send('Performance.enable');
    const before=Date.now();
    const metrics=await traceSession.send('Performance.getMetrics');
    emit({kind:'trace-clock',wallBefore:before,wallAfter:Date.now(),monotonic:metrics.metrics.find(m=>m.name==='Timestamp')?.value});
    await traceSession.send('Tracing.start',{transferMode:'ReturnAsStream',traceConfig:{
      recordMode:'recordContinuously',traceBufferSizeInKb:16384,
      includedCategories:['disabled-by-default-mediastream'],excludedCategories:['*']}});
    traceStarted=true;
  }
  await page.addInitScript(({decode}) => {
    window.audioProbe = {peers:[], streams:[], windows:[], packets:[], errors:[], resources:[]};
    const Native = RTCPeerConnection;
    window.RTCPeerConnection = class extends Native {
      constructor(config,...rest) {
        super(decode ? {...config,encodedInsertableStreams:true} : config,...rest);
        window.audioProbe.peers.push(this);
        this.addEventListener('track', event => {
          if (event.track.kind === 'audio') window.audioProbe.remote = event.track;
          if (!decode) return;
          const streams = event.receiver.createEncodedStreams();
          if (event.track.kind !== 'audio') {streams.readable.pipeTo(streams.writable);return;}
          let decoder, previous;
          streams.readable.pipeThrough(new TransformStream({transform(frame, controller) {
            if (!decoder && window.audioProbe.observeFrame) {
              decoder = new AudioDecoder({output:data => {
                window.audioProbe.observeFrame('opus', data);data.close();
              }, error:e => window.audioProbe.errors.push(String(e))});
              decoder.configure({codec:'opus',sampleRate:48000,numberOfChannels:2});
              window.audioProbe.resources.push(decoder);
            }
            if (window.audioProbe.packets.length < 100000) window.audioProbe.packets.push({
              wall:performance.timeOrigin+performance.now(), timestamp:frame.timestamp,
              delta:previous === undefined ? null : (frame.timestamp-previous)>>>0, bytes:frame.data.byteLength});
            previous = frame.timestamp;
            if (decoder) {
              if (decoder.decodeQueueSize >= 50) window.audioProbe.errors.push('Opus observer backlog');
              else decoder.decode(new EncodedAudioChunk({type:'key',timestamp:frame.timestamp*1e6/48000,data:frame.data}));
            }
            controller.enqueue(frame);
          }})).pipeTo(streams.writable).catch(e => window.audioProbe.errors.push(String(e)));
        });
      }
    };
  }, {decode:args.includes('--decode-opus')});
  if (calibrate) {
    await page.route('http://localhost:18761/**', route => route.fulfill({contentType:'text/html',body:'<!doctype html><title>Audio continuity calibration</title>'}));
    await page.goto('http://localhost:18761');
  } else {
    await page.goto(origin);
    await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0, {}, {timeout:45000});
  }
  await page.bringToFront();
  const metadata = await page.evaluate(async ({legacy, contextRate, local, calibrate, injectGap}) => {
    const state = window.audioProbe;
    const now = () => performance.timeOrigin+performance.now();
    const meters = new Map();
    let clips = 0;
    const bad = w => w.step >= .015 || w.hz < 420 || w.hz > 460 || w.rms < .02 || w.rms > .12 || w.peak >= .3;
    function observe(name, samples, rate, timestamp, received) {
      let m = meters.get(name);
      if (!m) {m={n:0,sum:0,peak:0,step:0,stepOffset:0,crossings:0,previous:0,frames:0,rate,raw:[],start:timestamp,expected:timestamp,gaps:0,maxGapUs:0};meters.set(name,m);}
      if (rate !== m.rate) throw Error('Observer sample rate changed');
      const gap = timestamp-m.expected;
      // AudioData timestamps can be rounded to integer microseconds.
      if (Math.abs(gap) > 2) {m.gaps++;m.maxGapUs=Math.max(m.maxGapUs,Math.abs(gap));}
      m.expected=timestamp+samples.length*1e6/rate;
      for (let i=0;i<samples.length;i++) {
        const x=samples[i];m.sum+=x*x;m.peak=Math.max(m.peak,Math.abs(x));
        const step=Math.abs(x-m.previous);if(step>m.step){m.step=step;m.stepOffset=m.n;}
        if(x>=0&&m.previous<0)m.crossings++;
        m.previous=x;m.raw.push(x);m.n++;m.frames++;
        if(m.n === rate/10) {
          const w={name,rate,frames:m.frames,mediaStartUs:m.start,mediaEndUs:timestamp+(i+1)*1e6/rate,
            observedWall:received,wall:received-(samples.length-i-1)*1000/rate,
            rms:Math.sqrt(m.sum/m.n),peak:m.peak,step:m.step,stepOffset:m.stepOffset,hz:m.crossings*10,
            timestampGaps:m.gaps,maxTimestampGapUs:m.maxGapUs};
          // Bounded raw failing windows support phase/discontinuity inspection.
          if(bad(w)&&clips<24&&m.frames>rate*5){w.samples=m.raw;clips++;}
          if(state.windows.length>=50000)throw Error('Observer window capacity exceeded');
          state.windows.push(w);
          m.n=0;m.sum=0;m.peak=0;m.step=0;m.stepOffset=0;m.crossings=0;m.raw=[];m.start=w.mediaEndUs;m.gaps=0;m.maxGapUs=0;
        }
      }
    }
    state.observeFrame=(name,frame)=>{
      const samples=new Float32Array(frame.numberOfFrames);
      frame.copyTo(samples,{planeIndex:0,format:'f32-planar'});
      observe(name,samples,frame.sampleRate,frame.timestamp,now());
    };
    async function readTrack(name,track) {
      const reader=new MediaStreamTrackProcessor({track,maxBufferSize:50}).readable.getReader();
      state.resources.push(reader);
      try {while(true){const {value,done}=await reader.read();if(done)break;try{state.observeFrame(name,value);}finally{value.close();}}}
      catch(e){state.errors.push(`${name}: ${e}`);}
    }
    const capture=await navigator.mediaDevices.getDisplayMedia({video:true,
      audio:{suppressLocalAudioPlayback:true,echoCancellation:false,noiseSuppression:false,autoGainControl:false},
      preferCurrentTab:true,selfBrowserSurface:'include',systemAudio:'exclude'});
    const settings=capture.getAudioTracks()[0]?.getSettings();
    if(capture.getVideoTracks()[0]?.getSettings().displaySurface!=='browser'||!settings?.suppressLocalAudioPlayback)
      throw Error('Dedicated suppressed tab capture required');
    state.capture=capture;readTrack('tab-direct',capture.getAudioTracks()[0]);
    if(!calibrate&&!state.remote)throw Error('No remote audio receiver');
    if(state.remote)readTrack('track-direct',state.remote);
    let audio;
    if(legacy) {
      audio=new AudioContext({sampleRate:contextRate});
      const module=URL.createObjectURL(new Blob([`class Meter extends AudioWorkletProcessor {
        constructor(){super();this.buffer=new Float32Array(sampleRate/10);this.n=0;}
        process(inputs){const samples=inputs[0]?.[0]||[];for(let i=0;i<samples.length;i++){
          this.buffer[this.n++]=samples[i];if(this.n===this.buffer.length){
            this.port.postMessage({samples:this.buffer,endFrame:currentFrame+i+1});this.n=0;}}
          return true;}}registerProcessor('continuity',Meter);`],{type:'text/javascript'}));
      await audio.audioWorklet.addModule(module);URL.revokeObjectURL(module);
      for(const [name,track] of [['tab-worklet',capture.getAudioTracks()[0]],['track-worklet',state.remote]]) {
        if(!track)continue;
        const source=audio.createMediaStreamSource(new MediaStream([track]));
        const meter=new AudioWorkletNode(audio,'continuity');source.connect(meter);meter.connect(audio.destination);
        meter.port.onmessage=({data})=>observe(name,data.samples,audio.sampleRate,(data.endFrame-data.samples.length)*1e6/audio.sampleRate,now());
        state.resources.push(source,meter);
      }
      await audio.resume();state.context=audio;
    }
    if(local||calibrate) {
      const toneContext=new AudioContext({sampleRate:48000});
      const oscillator=toneContext.createOscillator(),gain=toneContext.createGain();
      oscillator.frequency.value=440;gain.gain.value=.1;oscillator.connect(gain).connect(toneContext.destination);
      if(injectGap){gain.gain.setValueAtTime(0,toneContext.currentTime+12);gain.gain.setValueAtTime(.1,toneContext.currentTime+12.02);}
      oscillator.start();await toneContext.resume();state.tone={toneContext,oscillator,gain};
    }
    return {capture:settings,contextRate:audio?.sampleRate,visibility:document.visibilityState,
      hasFocus:document.hasFocus(),hardwareConcurrency:navigator.hardwareConcurrency,userAgent:navigator.userAgent};
  },{legacy:args.includes('--legacy-worklet'),contextRate:Number(option('context-rate',48000)),local:args.includes('--local-tone'),calibrate,injectGap:args.includes('--inject-gap')});
  if(!calibrate) {
    await page.getByRole('button',{name:/^(Audio|音频)( ·.*)?$/}).click();
    await page.getByRole('slider').first().press(args.includes('--local-tone')?'Home':'End');
    await page.keyboard.press('Escape');
  }
  emit({kind:'metadata',browser:browser.version(),headless,decode:args.includes('--decode-opus'),...metadata});
  emit({kind:'audio-sdp',descriptions:await page.evaluate(()=>window.audioProbe.peers.map(p=>{
    const audio=sdp=>sdp?.split(/(?=m=)/).find(s=>s.startsWith('m=audio'))?.split('\r\n')
      .filter(line=>/^(m=audio|a=(rtpmap|fmtp|ptime|maxptime|rtcp-fb):)/.test(line));
    return {local:audio(p.localDescription?.sdp),remote:audio(p.remoteDescription?.sdp)};
  }))});
  for(const rate of rates) {
    let source;
    if(process.env.AUDIO_RATE_TOOL&&!calibrate) {
      const result=spawnSync(process.env.AUDIO_RATE_TOOL,[process.env.AUDIO_DEVICE||'RTK UHD HDR',String(rate)],{encoding:'utf8',timeout:10000});
      assert.equal(result.status,0,result.stderr);
      source=result.stdout;
    }
    const start=Date.now();emit({kind:'start',rate,start,source});
    const stats=[];
    while(Date.now()-start < seconds*1000) {
      await page.waitForTimeout(500);
      stats.push(await page.evaluate(async()=>{
        const state=window.audioProbe,rows=[];
        for(const p of state.peers)for(const s of (await p.getStats()).values())
          if((s.type==='inbound-rtp'&&s.kind==='audio')||s.type==='media-playout'||s.type==='candidate-pair'&&s.nominated)rows.push({...s});
        const clock=state.context?.getOutputTimestamp();const v=document.querySelector('video');
        return {wall:performance.timeOrigin+performance.now(),visibility:document.visibilityState,focus:document.hasFocus(),
          context:state.context?{state:state.context.state,currentTime:state.context.currentTime,clock,baseLatency:state.context.baseLatency,outputLatency:state.context.outputLatency}:null,
          media:v?{muted:v.muted,volume:v.volume,paused:v.paused,currentTime:v.currentTime}:null,rows};
      }));
    }
    const result=await page.evaluate(start=>({windows:window.audioProbe.windows.filter(w=>w.wall>=start),
      packets:window.audioProbe.packets.filter(w=>w.wall>=start),errors:window.audioProbe.errors}),start);
    const summary={};
    for(const name of new Set(result.windows.map(w=>w.name))) {
      const windows=result.windows.filter(w=>w.name===name&&w.wall>=start+5000);
      const bad=windows.filter(w=>w.step>=.015||w.hz<420||w.hz>460||w.rms<.02||w.rms>.12||w.peak>=.3);
      summary[name]={count:windows.length,bad:bad.map(({samples,...w})=>({...w,
        stats:statsDelta(stats.filter(s=>s.wall<w.wall-200).at(-1),stats.find(s=>s.wall>w.wall+200))}))};
      if(!name.endsWith('worklet')&&(bad.length||windows.length<(seconds-6)*9))failed=true;
    }
    if(result.errors.length||!summary['tab-direct'])failed=true;
    emit({kind:'segment',rate,start,summary,
      steadyStats:statsDelta(stats.find(s=>s.wall>=start+5000),stats.at(-1)),stats,...result});
  }
} finally {
  try {
  if(traceStarted) {
    const completed=new Promise(resolve=>traceSession.once('Tracing.tracingComplete',resolve));
    await traceSession.send('Tracing.end');
    const {stream}=await completed;
    const parts=[];let bytes=0;
    try {while(true){const chunk=await traceSession.send('IO.read',{handle:stream});
      const data=Buffer.from(chunk.data,chunk.base64Encoded?'base64':'utf8');bytes+=data.length;
      if(bytes>128*1024*1024)throw Error('Trace exceeded 128 MiB export limit');
      parts.push(data);if(chunk.eof)break;
    }await writeFile(option('trace'),Buffer.concat(parts));}
    finally {await traceSession.send('IO.close',{handle:stream});}
  }
  } finally {await browser.close();}
}
if(failed)process.exitCode=1;
