import assert from 'node:assert/strict';
import { loginManager } from '../../../tools/manager-login.mjs';
assert(process.env.BOARD_TICKET);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE);
const browser = await chromium.launch({ executablePath: process.env.VIM4_TEST_CHROME, headless: true });
try {
  const context=await browser.newContext();await loginManager(context,'http://127.0.0.1:18088',{localBackend:true});
  const page=await context.newPage();await page.goto('http://127.0.0.1:18088/api/setup');
  await page.evaluate(async()=>{
    const ws=new WebSocket('ws://'+location.host+'/api/ws/hid');
    await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
    for(const dx of [30,-30,30,-30]){
      const packet=new Uint8Array(7);packet[0]=2;new DataView(packet.buffer).setInt16(2,dx,true);ws.send(packet);
      await new Promise(resolve=>setTimeout(resolve,200));
    }
    ws.close();
  });
} finally { await browser.close(); }

