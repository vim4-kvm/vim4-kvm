// Offline comparison for the reviewed 1920x1080 TestUFO layout. The screenshot
// review separately verifies the URL/layout and the cursor in its known corner.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const { chromium }=await import(process.env.PLAYWRIGHT_MODULE);
const browser=await chromium.launch({executablePath:process.env.VIM4_TEST_CHROME,headless:true});
try {
  const page=await browser.newPage();
  const urls=await Promise.all(process.argv.slice(2,4).map(async path=>'data:image/jpeg;base64,'+(await fs.readFile(path)).toString('base64')));
  const result=await page.evaluate(async urls=>{
    const buffers=[];
    for(const src of urls){
      const image=new Image();image.src=src;await image.decode();
      if(image.width!==1920||image.height!==1080)throw new Error('Unknown TestUFO screenshot geometry');
      const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=1080;
      const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);buffers.push(ctx.getImageData(0,0,1920,1080).data);
    }
    let changed=0,compared=0,cursorCornerChanged=0;
    for(let y=0;y<1080;y++)for(let x=0;x<1920;x++){
      const i=(y*1920+x)*4;
      const different=[0,1,2].some(c=>Math.abs(buffers[0][i+c]-buffers[1][i+c])>20);
      if(x<20&&y<25&&different)cursorCornerChanged++;
      if(y<28||(y>=460&&y<752))continue;
      compared++;if(different)changed++;
    }
    return {knownLayoutMask:true,maskedRegions:['menu clock/status y0..27','three UFO bands y460..751'],changedFraction:changed/compared,cursorCornerChanged};
  },urls);
  result.stable=result.changedFraction<.001&&result.cursorCornerChanged<=3;
  console.log(JSON.stringify(result));
  assert(result.stable,'Unexpected activity outside the authorized TestUFO animation bands or cursor moved');
} finally {await browser.close();}

