import assert from 'node:assert/strict';
import {test} from 'node:test';
import {summarizeAVSync} from '../tools/av-sync-probe.mjs';

test('known offset and drift survive missing pulses and partial startup',()=>{
  const videoEdges=Array.from({length:181},(_,i)=>({outputMs:i*2000}));
  const audioEdges=videoEdges.filter((_,i)=>![37,41,80].includes(i))
    .map(({outputMs})=>({outputMs:outputMs+120+outputMs*.000025}));
  audioEdges[0].outputMs=-250; // A partial pulse when observation starts.
  const result=summarizeAVSync({videoEdges,audioEdges,startedMs:0},120,10000);
  assert.equal(result.count,173);
  assert(Math.abs(result.slopeMsPerMinute-1.5)<1e-9);
  assert(result.minMs>=.25&&result.maxMs<=9);
});

test('audio leads remain negative; an audio pulse cannot be reused',()=>{
  const videoEdges=[0,100,2000,4000,6000].map(outputMs=>({outputMs}));
  const audioEdges=[-120,1880,3880,5880].map(outputMs=>({outputMs}));
  const result=summarizeAVSync({audioEdges,videoEdges},0,0);
  assert.equal(result.count,4);assert.equal(result.medianMs,-120);
  assert.equal(result.slopeMsPerMinute,0);
});

test('missing or unrelated audio is rejected rather than accepted as synchronization',()=>{
  const videoEdges=[12000,14000,16000].map(outputMs=>({outputMs}));
  assert.throws(()=>summarizeAVSync({audioEdges:[],videoEdges}),/Insufficient/);
  assert.throws(()=>summarizeAVSync({audioEdges:[{outputMs:13000}],videoEdges}),/Insufficient/);
});
