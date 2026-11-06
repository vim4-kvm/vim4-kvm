#!/usr/bin/env python3
"""Replay initial SOURCE_CHANGE/LAST using the actual driver and GST 1.24.2 C.

Usage: test_gstreamer_hevc_eos.py PATH/aml_vdec.c PATH/gstv4l2videodec.c
No device or threads: the queued event is delivered at a controlled boundary.
This checks consumer event ordering, not hardware decoding or ioctl compliance.
"""
from pathlib import Path
import subprocess
import sys
import tempfile


def block(text, opening):
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[opening:end]


def function(text, name):
    start = text.index(name + '(') if name.startswith(('vidioc_', 'vdec_')) else text.index(name + ' (')
    opening = text.index('{', start)
    return text[start:opening] + block(text, opening)


FIXTURE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define TRUE true
#define FALSE false
#define EINVAL 22
#define AML_FMT_DEC 1
#define AML_FMT_FRAME 2
#define CODEC_TYPE_HEVC 1
#define CODEC_TYPE_MJPEG 2
#define V4L2_PIX_FMT_NV12M 3
#define V4L2_PIX_FMT_YUV420 4
#define V4L2_FMT_FLAG_DYN_RESOLUTION 0x0008
struct aml_video_fmt {int type,codec_type; unsigned fourcc; const char *name;};
struct platform {int num_fmts; const struct aml_video_fmt *dec_fmt;};
struct aml_vdec_dev {struct platform *pvdec_data;};
struct aml_vdec_ctx {bool is_hevc,is_jpeg; struct aml_vdec_dev *dev;};
struct v4l2_fmtdesc {unsigned index,pixelformat,flags; char description[32];};
#define strscpy(d,s,n) ((void)snprintf(d,n,"%s",s))
/* DRIVER */
typedef int GstFlowReturn;
#define GST_FLOW_OK 0
#define GST_V4L2_FLOW_RESOLUTION_CHANGE 1
#define GST_V4L2_FLOW_LAST_BUFFER 2
#define GST_CLOCK_TIME_NONE 0
#define GST_VIDEO_DECODER_STREAM_LOCK(p) ((void)(p))
#define GST_VIDEO_DECODER_STREAM_UNLOCK(p) ((void)(p))
#define GST_DEBUG_OBJECT(...) ((void)0)
#define GST_INFO_OBJECT(...) ((void)0)
#define GST_VIDEO_DECODER(p) (p)
#define GST_V4L2_IS_ACTIVE(p) ((p)->active)
typedef struct {bool active; struct v4l2_fmtdesc *fmtdesc;} Object;
typedef struct {bool wait_for_source_change,draining,paused; Object *v4l2capture,*v4l2output;} GstV4l2VideoDec;
static bool source_event;
static int capture_stops, polls;
static void gst_v4l2_object_unlock_stop(Object *obj) {(void)obj;}
static void gst_v4l2_object_stop(Object *obj) {obj->active=false; capture_stops++;}
static int gst_v4l2_object_poll(Object *obj, int timeout) {
  (void)obj; (void)timeout; polls++;
  if(source_event) {source_event=false; return GST_V4L2_FLOW_RESOLUTION_CHANGE;}
  return GST_FLOW_OK;
}
/* WAIT */
static void arm_initial_wait(GstV4l2VideoDec *self) {
/* ARM */
}
static void process_boundary(GstV4l2VideoDec *self, int ret) {
  GstV4l2VideoDec *decoder=self;
/* BOUNDARY */
  self->paused=true;
}
int main(void) {
  const struct aml_video_fmt formats[]={{AML_FMT_DEC,CODEC_TYPE_HEVC,1,"HEVC"},
    {AML_FMT_FRAME,0,V4L2_PIX_FMT_NV12M,"NV12M"}};
  struct platform platform={2,formats}; struct aml_vdec_dev dev={&platform};
  struct aml_vdec_ctx ctx={.is_hevc=true,.dev=&dev}; struct v4l2_fmtdesc fmt={0};
  Object capture={0},output={.fmtdesc=&fmt};
  GstV4l2VideoDec decoder={.v4l2capture=&capture,.v4l2output=&output};
  assert(vidioc_vdec_enum_fmt(&ctx,&fmt,true)==0);
  /* One AU queued, STOP accepted, initial event pending, CAPTURE not yet on. */
  source_event=true;
  arm_initial_wait(&decoder);
  assert(gst_v4l2_video_dec_wait_for_src_ch(&decoder)==GST_FLOW_OK);
  capture.active=true;
  if(source_event)
    process_boundary(&decoder,gst_v4l2_object_poll(&capture,0));
  /* The decoded picture is delivered once, then LAST/EPIPE ends the drain. */
  unsigned frames=1;
  process_boundary(&decoder,GST_V4L2_FLOW_LAST_BUFFER);
  if(!decoder.paused || capture_stops || source_event) {
    fprintf(stderr,"EOS lost: frames=%u capture_stops=%d paused=%d polls=%d\n",
      frames,capture_stops,decoder.paused,polls); return 1;
  }
  /* A later resolution change still ends CAPTURE and resumes negotiation. */
  decoder.paused=false; source_event=true;
  process_boundary(&decoder,gst_v4l2_object_poll(&capture,0));
  process_boundary(&decoder,GST_V4L2_FLOW_LAST_BUFFER);
  assert(!decoder.paused && !capture.active && capture_stops==1);
  capture.active=true;
  process_boundary(&decoder,GST_V4L2_FLOW_LAST_BUFFER);
  assert(decoder.paused && capture_stops==1);
  puts("PASS: initial SOURCE_CHANGE consumed before CAPTURE; EOS terminates; DRC resumes");
}
'''


def main():
    driver, gst = (Path(p).read_text() for p in sys.argv[1:])
    driver_functions = 'static bool ' + function(driver, 'vdec_format_supported')
    driver_functions += '\nstatic int ' + function(driver, 'vidioc_vdec_enum_fmt')
    arm_start = gst.index('    if (!GST_V4L2_IS_ACTIVE (self->v4l2capture) &&')
    arm_open = gst.index('{', arm_start)
    arm = gst[arm_start:arm_open] + block(gst, arm_open)
    boundary = gst[gst.index('  if (ret == GST_V4L2_FLOW_RESOLUTION_CHANGE)', gst.index('beach:')):]
    boundary = boundary[:boundary.index('  GST_DEBUG_OBJECT (decoder, "Leaving output thread:')]
    source = FIXTURE.replace('/* DRIVER */', driver_functions)
    source = source.replace('/* WAIT */', 'static GstFlowReturn ' +
                            function(gst, 'gst_v4l2_video_dec_wait_for_src_ch'))
    source = source.replace('/* ARM */', arm).replace('/* BOUNDARY */', boundary)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        (path / 'fixture.c').write_text(source)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                        str(path / 'fixture.c'), '-o', str(path / 'fixture')], check=True)
        subprocess.run([str(path / 'fixture')], check=True)


if __name__ == '__main__':
    main()
