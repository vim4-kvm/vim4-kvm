/* macOS diagnostic: 20 seconds of 440Hz PCM sent only to the HDMI sink.
 * The sink is named by the board's EDID: "AML TV" for the vendor tables,
 * "JetKVM v1" for JetKVM's default. Usage: hdmi-audio-tone [NAME]
 * Does not change the system default output. Pair with audio-smoke.mjs.
 * Build: clang tools/hdmi-audio-tone.c -framework AudioToolbox
 *        -framework CoreAudio -framework CoreFoundation -o /tmp/hdmi-audio-tone
 */
#include <AudioToolbox/AudioToolbox.h>
#include <CoreAudio/CoreAudio.h>
#include <CoreFoundation/CoreFoundation.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned long phase;
static void fill(void *ctx, AudioQueueRef q, AudioQueueBufferRef b) {
 float *p=b->mAudioData;
 for(int i=0;i<4800;i++) {float v=0.1f*sin(2*M_PI*440*(phase++)/48000.0);p[2*i]=v;p[2*i+1]=v;}
 b->mAudioDataByteSize=4800*2*sizeof(float);AudioQueueEnqueueBuffer(q,b,0,NULL);
}
int main(int argc,char **argv){
 CFStringRef sink=CFStringCreateWithCString(NULL,argc>1?argv[1]:"AML TV",kCFStringEncodingUTF8);
 AudioObjectPropertyAddress p={kAudioHardwarePropertyDevices,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};UInt32 size=0;
 AudioObjectGetPropertyDataSize(kAudioObjectSystemObject,&p,0,NULL,&size);
 AudioDeviceID *ids=malloc(size);AudioObjectGetPropertyData(kAudioObjectSystemObject,&p,0,NULL,&size,ids);CFStringRef uid=NULL;
 for(unsigned i=0;i<size/sizeof(*ids);i++){
  AudioObjectPropertyAddress n={kAudioObjectPropertyName,kAudioObjectPropertyScopeGlobal,kAudioObjectPropertyElementMain};CFStringRef name=NULL;UInt32 len=sizeof(name);AudioObjectGetPropertyData(ids[i],&n,0,NULL,&len,&name);
  if(name&&CFStringFind(name,sink,0).location!=kCFNotFound){n.mSelector=kAudioDevicePropertyDeviceUID;len=sizeof(uid);AudioObjectGetPropertyData(ids[i],&n,0,NULL,&len,&uid);}
  if(name)CFRelease(name);
 }
 if(!uid)return 1;
 AudioStreamBasicDescription f={.mSampleRate=48000,.mFormatID=kAudioFormatLinearPCM,.mFormatFlags=kAudioFormatFlagIsFloat|kAudioFormatFlagIsPacked,.mBytesPerPacket=8,.mFramesPerPacket=1,.mBytesPerFrame=8,.mChannelsPerFrame=2,.mBitsPerChannel=32};
 AudioQueueRef q;OSStatus e=AudioQueueNewOutput(&f,fill,NULL,CFRunLoopGetCurrent(),kCFRunLoopCommonModes,0,&q);if(e)return 2;
 e=AudioQueueSetProperty(q,kAudioQueueProperty_CurrentDevice,&uid,sizeof(uid));if(e){printf("device error %d\n",e);return 3;}
 for(int i=0;i<3;i++){AudioQueueBufferRef b;AudioQueueAllocateBuffer(q,4800*8,&b);fill(NULL,q,b);}
 e=AudioQueueStart(q,NULL);if(e)return 4;puts("HDMI-only 440Hz tone started");fflush(stdout);
 CFRunLoopRunInMode(kCFRunLoopDefaultMode,20,false);AudioQueueStop(q,true);AudioQueueDispose(q,true);return 0;
}
