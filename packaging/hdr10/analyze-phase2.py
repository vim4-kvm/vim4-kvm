#!/usr/bin/env python3
"""Offline HEVC checks after the board ticket is released. FFmpeg parses SPS/VUI;
this independent Annex-B reader compares unescaped SEI bytes to HDMI controls.
Does not connect to the board or claim that RR proves official UU decoding.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess


def sei(data):
    starts=list(re.finditer(b'\x00\x00\x00\x01|\x00\x00\x01',data))
    if not starts: raise ValueError('keyframe is not Annex-B')
    messages={};irap=False
    for index,start in enumerate(starts):
        nal=data[start.end():starts[index+1].start() if index+1<len(starts) else len(data)]
        if len(nal)<2: raise ValueError('truncated NAL')
        kind=(nal[0]>>1)&63
        if 16<=kind<=23: irap=True
        if kind!=39: continue
        payload=nal[2:].replace(b'\0\0\3',b'\0\0');cursor=0
        while cursor<len(payload):
            if payload[cursor:]==b'\x80': break
            values=[]
            for _ in range(2):
                value=0
                while True:
                    if cursor>=len(payload): raise ValueError('truncated SEI header')
                    byte=payload[cursor];cursor+=1;value+=byte
                    if byte!=255: break
                values.append(value)
            kind,length=values
            if cursor+length>len(payload): raise ValueError('truncated SEI message')
            if kind in (137,144):
                if irap or kind in messages: raise ValueError('late or duplicate HDR SEI')
                messages[kind]=payload[cursor:cursor+length]
            cursor+=length
    if not irap: raise ValueError('no random access picture')
    return messages


def check_trace(trace,pq):
    fields={}
    for line in trace.splitlines():
        match=re.search(r'\]\s+\d+\s+(\w+)\s+.*=\s+(-?\d+)\s*$',line)
        if match: fields.setdefault(match[1],set()).add(int(match[2]))
    expected=dict(general_profile_idc=2 if pq else 1,bit_depth_luma_minus8=2 if pq else 0,
        bit_depth_chroma_minus8=2 if pq else 0,video_full_range_flag=0,
        colour_primaries=9 if pq else 1,transfer_characteristics=16 if pq else 1,
        matrix_coefficients=9 if pq else 1)
    for key,value in expected.items():
        if fields.get(key)!={value}: raise ValueError(f'{key}: {fields.get(key)} != {value}')
    return expected


def check_sei(data,metadata):
    messages=sei(data)
    primary=[v for pair in metadata['primaries'] for v in pair]
    expected={137:struct.pack('>8H2I',*primary,*metadata['white'],*metadata['luminance']),
        144:struct.pack('>2H',*metadata['cll'])}
    if messages!=expected: raise ValueError('SEI bytes differ from HDMI controls')
    return dict(payloads={str(k):v.hex() for k,v in messages.items()},matches_hdmi=True,
        nonzero_source=any(any(value) for value in expected.values()))


def analyze(directory,ffmpeg):
    results=[]
    for prefix in sorted(directory.glob('*/first-keyframe.h265')):
        result=json.loads((prefix.parent/'result.json').read_text())['result']
        gpu=prefix.parent.name.split('-',1)[0]
        process=subprocess.run([ffmpeg,'-hide_banner','-v','verbose','-f','hevc','-i',str(prefix),
            '-map','0:v','-c:v','copy','-bsf:v','trace_headers','-f','null','-'],capture_output=True,text=True)
        prefix.with_name('headers.log').write_text(process.stderr)
        if process.returncode: raise ValueError('FFmpeg failed: '+str(prefix))
        pq=result['hdr']=='pq';proof=dict(sample=prefix.parent.name,sps_vui=check_trace(process.stderr,pq))
        if pq: proof['sei']=check_sei(prefix.read_bytes(),json.loads((directory/f'{gpu}-hdmi-metadata.json').read_text()))
        results.append(proof)
    if len(results)!=28: raise ValueError(f'expected 14 HEVC samples per GPU, got {len(results)}')
    (directory/'bitstream-proof.json').write_text(json.dumps(dict(samples=results,
        uu_limit='Shared producer plus official-client RR; client decoding/rendering remains unproven'),indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args();analyze(args.directory,args.ffmpeg)
