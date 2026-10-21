// Browser-side software A/V probe. Pass installAVSyncProbe to page.evaluate.
// It observes tab audio after rendering, not a second remote-track audio sink.
// AudioWorklet needs HTTPS/localhost (or a dedicated test-browser secure-origin flag).
// The capture/observer path adds latency. Measure its bias with a known A/V clip;
// this does not calibrate an HDMI transmitter, panel, or physical speaker.
export async function installAVSyncProbe({selector='video', x=.5, y=700/1080}={}) {
  const video=document.querySelector(selector);
  if (!video) throw new Error('Missing media element');
  const audio=new AudioContext({sampleRate:48000,latencyHint:'interactive'});
  if (!audio.audioWorklet) throw new Error('AudioWorklet requires a secure context');
  const module=URL.createObjectURL(new Blob([`
    class PulseProbe extends AudioWorkletProcessor {
      constructor(){super();this.lastLoud=-Infinity;}
      process(inputs){
        const channels=inputs[0];
        for(let i=0;i<(channels[0]?.length||0);i++){
          let peak=0;for(const channel of channels)peak=Math.max(peak,Math.abs(channel[i]));
          if(peak>.02){
            const frame=currentFrame+i;
            if(frame-this.lastLoud>sampleRate*.1)
              this.port.postMessage({audioTime:frame/sampleRate});
            this.lastLoud=frame;
          }
        }
        // Observe playback without emitting the test tone into the room.
        return true;
      }
    }
    registerProcessor('pulse-probe',PulseProbe);
  `],{type:'text/javascript'}));
  try {await audio.audioWorklet.addModule(module);} finally {URL.revokeObjectURL(module);}
  const capture=await navigator.mediaDevices.getDisplayMedia({video:true,
    audio:{suppressLocalAudioPlayback:true,echoCancellation:false,noiseSuppression:false,autoGainControl:false},
    preferCurrentTab:true,selfBrowserSurface:'include',systemAudio:'exclude'});
  if(capture.getVideoTracks()[0]?.getSettings().displaySurface!=='browser')
    throw new Error('Only the dedicated test tab may be captured');
  if(capture.getAudioTracks().length!==1)throw new Error('Tab audio capture unavailable');
  if(capture.getAudioTracks()[0].getSettings().suppressLocalAudioPlayback!==true)
    throw new Error('Tab capture must suppress local speaker playback');
  // Capture first so unmuting the player never emits the fixture into the room.
  video.muted=false;video.volume=1;
  for(const track of video.srcObject?.getAudioTracks?.()||[])track.enabled=true;
  const source=audio.createMediaStreamSource(new MediaStream(capture.getAudioTracks()));
  const worklet=new AudioWorkletNode(audio,'pulse-probe');
  source.connect(worklet);worklet.connect(audio.destination);
  const state={startedMs:performance.now(),audioEdges:[],videoEdges:[],clocks:[],readbackCosts:[],missedVideoCallbacks:0};
  worklet.port.onmessage=({data})=>{
    const clock=audio.getOutputTimestamp();
    state.audioEdges.push({audioTime:data.audioTime,
      outputMs:clock.performanceTime+(data.audioTime-clock.contextTime)*1000,
      observedMs:performance.now(),clock});
  };
  await audio.resume();await video.play();
  const canvas=document.createElement('canvas');canvas.width=1;canvas.height=1;
  const ctx=canvas.getContext('2d',{willReadFrequently:false});
  let wasOn=false,previousFrames;
  const callback=(_now,frame)=>{
    const started=performance.now();
    ctx.drawImage(video,video.videoWidth*x,video.videoHeight*y,1,1,0,0,1,1);
    const on=ctx.getImageData(0,0,1,1).data[0]>128;
    state.readbackCosts.push(performance.now()-started);
    if(on&&!wasOn)state.videoEdges.push({outputMs:frame.expectedDisplayTime,
      submittedMs:frame.presentationTime,mediaTime:frame.mediaTime,rtpTimestamp:frame.rtpTimestamp});
    wasOn=on;
    if(previousFrames!==undefined)state.missedVideoCallbacks+=Math.max(0,frame.presentedFrames-previousFrames-1);
    previousFrames=frame.presentedFrames;
    video.requestVideoFrameCallback(callback);
  };
  video.requestVideoFrameCallback(callback);
  const timer=setInterval(()=>state.clocks.push({now:performance.now(),currentTime:audio.currentTime,
    ...audio.getOutputTimestamp(),baseLatency:audio.baseLatency,outputLatency:audio.outputLatency}),1000);
  window.avSyncProbe={state,audio,source,worklet,timer,capture};
  return {route:'tab',sampleRate:audio.sampleRate,baseLatency:audio.baseLatency,outputLatency:audio.outputLatency,
    capture: capture?.getAudioTracks()[0].getSettings()};
}

// Match each two-second pulse once; reject partial startup/tail pulses.
export function summarizeAVSync({audioEdges,videoEdges,startedMs=0},expectedMs=0,warmupMs=15000) {
  const used=new Set(),pairs=[];
  for(const video of videoEdges){
    if(video.outputMs<startedMs+warmupMs)continue;
    let index=-1,distance=800;
    for(let i=0;i<audioEdges.length;i++){
      const d=Math.abs(audioEdges[i].outputMs-video.outputMs);
      if(!used.has(i)&&d<distance){index=i;distance=d;}
    }
    if(index>=0){used.add(index);pairs.push({videoMs:video.outputMs,
      audioMinusVideoMs:audioEdges[index].outputMs-video.outputMs-expectedMs});}
  }
  if(pairs.length<3)throw new Error('Insufficient matched audio/video pulses');
  const median=values=>{const s=[...values].sort((a,b)=>a-b),n=s.length;return (s[(n-1)>>1]+s[n>>1])/2;};
  const center=pairs.reduce((n,p)=>n+p.videoMs,0)/pairs.length;
  const mean=pairs.reduce((n,p)=>n+p.audioMinusVideoMs,0)/pairs.length;
  const slope=pairs.reduce((n,p)=>n+(p.videoMs-center)*(p.audioMinusVideoMs-mean),0)
    /pairs.reduce((n,p)=>n+(p.videoMs-center)**2,0);
  const first=pairs[0].videoMs,last=pairs.at(-1).videoMs;
  return {count:pairs.length,spanSeconds:(last-first)/1000,
    medianMs:median(pairs.map(p=>p.audioMinusVideoMs)),
    minMs:Math.min(...pairs.map(p=>p.audioMinusVideoMs)),maxMs:Math.max(...pairs.map(p=>p.audioMinusVideoMs)),
    firstMinuteMs:median(pairs.filter(p=>p.videoMs<first+60000).map(p=>p.audioMinusVideoMs)),
    lastMinuteMs:median(pairs.filter(p=>p.videoMs>last-60000).map(p=>p.audioMinusVideoMs)),
    slopeMsPerMinute:slope*60000,pairs};
}
