// Real local Chrome WebRTC encode/decode; no board, source computer or HID.
import http from 'node:http';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { receive } from './application-receiver.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = process.argv[2];
await fs.mkdir(output, {recursive:true});
const html = `<!doctype html><video autoplay muted playsinline></video><canvas width=160 height=96></canvas><script>
(async()=>{
 const Sender=Object.getPrototypeOf(RTCPeerConnection);
 const a=new Sender(), b=new RTCPeerConnection();
 a.onicecandidate=e=>e.candidate&&b.addIceCandidate(e.candidate);
 b.onicecandidate=e=>e.candidate&&a.addIceCandidate(e.candidate);
 b.ontrack=e=>document.querySelector('video').srcObject=new MediaStream([e.track]);
 const canvas=document.querySelector('canvas'), ctx=canvas.getContext('2d');
 const track=canvas.captureStream(0).getVideoTracks()[0];
 const sender=a.addTrack(track), transceiver=a.getTransceivers()[0];
 transceiver.setCodecPreferences(RTCRtpSender.getCapabilities('video').codecs.filter(c=>c.mimeType==='video/VP8'));
 await a.setLocalDescription(await a.createOffer());await b.setRemoteDescription(a.localDescription);
 await b.setLocalDescription(await b.createAnswer());await a.setRemoteDescription(b.localDescription);
 let n=0;
 const timer=setInterval(()=>{ctx.fillStyle=n++%2?'red':'blue';ctx.fillRect(0,0,160,96);track.requestFrame();},33);
 if(location.search.includes('freeze'))setTimeout(()=>clearInterval(timer),1200);
})();</script>`;
const senderHtml = `<!doctype html><canvas width=160 height=96></canvas><script>
window.answerOffer=async sdp=>{
 const pc=new RTCPeerConnection({iceServers:[]});window.pc=pc;
 const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
 const track=canvas.captureStream(0).getVideoTracks()[0];
 await pc.setRemoteDescription({type:'offer',sdp});
 const transceiver=pc.getTransceivers()[0];transceiver.direction='sendonly';
 transceiver.setCodecPreferences(RTCRtpSender.getCapabilities('video').codecs.filter(c=>c.mimeType==='video/VP8'));
 await transceiver.sender.replaceTrack(track);
 await pc.setLocalDescription(await pc.createAnswer());
 if(pc.iceGatheringState!=='complete')await new Promise(resolve=>pc.onicegatheringstatechange=()=>{
   if(pc.iceGatheringState==='complete')resolve();});
 let n=0;window.timer=setInterval(()=>{ctx.fillStyle=n++%2?'red':'blue';ctx.fillRect(0,0,160,96);track.requestFrame();},33);
 return pc.localDescription.sdp;
};</script>`;
let senderPage, closedSessions=0;
const server = http.createServer(async(req,res)=>{
 try {
   if(req.method==='POST') {
     let body='';for await(const chunk of req)body+=chunk;
     const value=JSON.parse(body);
     if(req.url==='/api/webrtc/offer') {
       const sdp=await senderPage.evaluate(sdp=>window.answerOffer(sdp),value.sdp);
       res.writeHead(200,{'Content-Type':'application/json'});
       res.end(JSON.stringify({sdp,session_id:'local-fixture',ice_candidates:[]}));return;
     }
     if(req.url==='/api/webrtc/close') {
       assert.equal(value.session_id,'local-fixture');closedSessions++;
       await senderPage.evaluate(()=>{window.pc.close();clearInterval(window.timer);});
       res.writeHead(200,{'Content-Type':'application/json'});res.end('{}');return;
     }
     throw Error('Unexpected API '+req.url);
   }
   res.writeHead(200,{'Content-Type':'text/html'});res.end(req.url==='/sender'?senderHtml:html);
 } catch(error) {res.writeHead(500);res.end(String(error));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
try {
 for(const app of ['nanokvm','jetkvm','pikvm']) {
   await receive({url:origin,app,output:`${output}/${app}`,hdr:'sdr',seconds:1,
     codec:'video/VP8',minFps:20,localBackend:true,width:160,height:96});
 }
 const senderBrowser=await chromium.launch({channel:'chrome',headless:true});
 try {
   senderPage=await senderBrowser.newPage();await senderPage.goto(origin+'/sender');
   await receive({url:origin,app:'onekvm',output:`${output}/onekvm`,hdr:'sdr',seconds:1,
     codec:'video/VP8',minFps:20,localBackend:true,width:160,height:96,prepareSource:true});
   assert(JSON.parse(await fs.readFile(`${output}/onekvm/ready.json`)).decoded>0);
   assert.equal((await fs.readFile(`${output}/onekvm/source-ready.jpg`)).readUInt16BE(),0xffd8);
   assert.equal(closedSessions,1,'One-KVM close API must release the session');
 } finally {await senderBrowser.close();}
 await assert.rejects(receive({url:origin,app:'nanokvm',output:`${output}/wrong-codec`,hdr:'sdr',seconds:1,
   localBackend:true,minFps:20}), /video\/h265|video\/vp8/i);
 await assert.rejects(receive({url:origin,app:'pikvm',output:`${output}/wrong-pq`,hdr:'pq',seconds:1,
   codec:'video/VP8',localBackend:true,minFps:20}), /pq/);
 await assert.rejects(receive({url:origin+'/?freeze',app:'jetkvm',output:`${output}/freeze`,hdr:'sdr',seconds:3,
   codec:'video/VP8',localBackend:true,minFps:20}), /fps|stopped|Decoded frames/i);
 console.log('PASS: four local decoded receivers including HTTP offer/close; wrong codec/PQ/frozen video rejected');
} finally { server.close(); }
