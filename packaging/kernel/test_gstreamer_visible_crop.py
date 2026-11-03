#!/usr/bin/env python3
"""Replay Wave5 caps and padding/crop negotiation without opening any device."""
from pathlib import Path
import subprocess
import sys
import tempfile

from test_gstreamer_orphan import function

FIXTURE = r'''
#include <gst/video/video.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <errno.h>
#include <stdarg.h>
#include <assert.h>
#include <string.h>
typedef struct {
  struct v4l2_capability vcap;
  char *videodev;
  unsigned type;
  int video_fd;
  void *dbg_obj;
  GstVideoAlignment align;
  GstVideoInfo info;
  int (*ioctl)(int, unsigned long, ...);
} GstV4l2Object;
static gboolean capable;
static unsigned opens, closes, selections;
static struct v4l2_rect visible;
static struct v4l2_capability querycap;
static gboolean hevc = TRUE;
static int fake_open(const char *path, int flags, ...) {
  assert(!strcmp(path,"fake-wave5")); assert(flags&O_RDWR); opens++; return 42;
}
static int fake_close(int fd) { assert(fd==42); closes++; return 0; }
static int fake_ioctl(int fd,unsigned long request,...) {
  va_list args; va_start(args,request); void *arg=va_arg(args,void*); va_end(args);
  assert(fd==42);
  if(request==VIDIOC_QUERYCAP) { *(struct v4l2_capability*)arg=querycap; return 0; }
  if(request==VIDIOC_ENUM_FMT) {
    struct v4l2_fmtdesc *f=arg;
    if(f->index || !hevc) { errno=EINVAL; return -1; }
    f->pixelformat=V4L2_PIX_FMT_HEVC; return 0;
  }
  if(request==VIDIOC_S_FMT) return 0;
  if(request==VIDIOC_S_SELECTION) {
    struct v4l2_selection *s=arg;
    assert(s->target==V4L2_SEL_TGT_CROP);
    if(!capable) { errno=EINVAL; return -1; }
    visible=s->r; selections++; return 0;
  }
  if(request==VIDIOC_G_FMT) {
    struct v4l2_format *f=arg;
    f->fmt.pix_mp.pixelformat=V4L2_PIX_FMT_HEVC;
    f->fmt.pix_mp.width=(visible.width+7)&~7;
    f->fmt.pix_mp.height=(visible.height+7)&~7;
    return 0;
  }
  assert(!"Unexpected ioctl, including any buffer allocation or streaming");
  return -1;
}
#define open fake_open
#define close fake_close
#define ioctl fake_ioctl
'''

CHECK = r'''
static void check_steps(GstV4l2Object *v4l2object, guint32 pixelformat,
    int step, gboolean expected) {
  struct v4l2_frmsizeenum size={0};
  size.stepwise.step_width=step; size.stepwise.step_height=step;
  guint step_w,step_h;
  STEP_CODE
  GstCaps *caps=gst_caps_new_empty_simple("video/x-raw");
  GstStructure *s=gst_caps_get_structure(caps,0);
  GValue range=G_VALUE_INIT; g_value_init(&range,GST_TYPE_INT_RANGE);
  gst_value_set_int_range_step(&range,256,3840,step_w);
  gst_structure_set_value(s,"width",&range);
  gst_value_set_int_range_step(&range,128,2160,step_h);
  gst_structure_set_value(s,"height",&range); g_value_unset(&range);
  const unsigned modes[][2]={{1366,768},{1440,900},{1680,1050},{1600,900}};
  for(unsigned i=0;i<G_N_ELEMENTS(modes);i++) {
    GstCaps *frame=gst_caps_new_simple("video/x-raw","width",G_TYPE_INT,modes[i][0],
        "height",G_TYPE_INT,modes[i][1],NULL);
    assert(gst_caps_can_intersect(caps,frame)==expected);
    gst_caps_unref(frame);
    if(expected) {
      gst_video_info_set_format(&v4l2object->info,GST_VIDEO_FORMAT_NV12,modes[i][0],modes[i][1]);
      v4l2object->align.padding_right=((modes[i][0]+31)&~31)-modes[i][0];
      v4l2object->align.padding_bottom=((modes[i][1]+15)&~15)-modes[i][1];
      assert(gst_v4l2_object_setup_padding(v4l2object));
      assert(visible.width==modes[i][0]&&visible.height==modes[i][1]);
    }
  }
  gst_caps_unref(caps);
}
int main(int argc,char **argv) {
  gst_init(&argc,&argv);
  GstV4l2Object obj={.videodev="fake-wave5",.video_fd=42,
    .type=V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,.ioctl=fake_ioctl};
  /* Both kernels: querycap() sets driver/card to VPU_ENC_DRV_NAME;
   * V4L2 core supplies bus_info/device_caps. Evidence: r3 kernel-querycap-source.txt,
   * b1300-controls.log and both revisions' v4l2-ioctl.c/vdev registration. */
  strcpy((char*)querycap.driver,"wave5-enc");
  strcpy((char*)querycap.card,"wave5-enc");
  strcpy((char*)querycap.bus_info,"platform:fe310000.video-codec");
  querycap.device_caps=V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING;
  querycap.capabilities=querycap.device_caps|V4L2_CAP_DEVICE_CAPS;
  obj.vcap=querycap;
  capable=TRUE; /* 213f2715 */
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,TRUE);
  check_steps(&obj,V4L2_PIX_FMT_HEVC,8,TRUE);
  capable=FALSE; /* b1300eb: identical identity, selection rejects the crop */
  check_steps(&obj,V4L2_PIX_FMT_HEVC,8,FALSE);
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,FALSE);
  capable=TRUE;
  strcpy((char*)querycap.driver,"renamed-driver");
  strcpy((char*)querycap.card,"arbitrary card");
  strcpy((char*)querycap.bus_info,"arbitrary bus");
  obj.vcap=querycap;
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,TRUE);
  querycap.capabilities=querycap.device_caps; /* Older QUERYCAP convention */
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,TRUE);
  querycap.capabilities=querycap.device_caps|V4L2_CAP_DEVICE_CAPS;
  querycap.device_caps=V4L2_CAP_VIDEO_CAPTURE_MPLANE|V4L2_CAP_STREAMING;
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,FALSE);
  querycap.device_caps=V4L2_CAP_VIDEO_M2M_MPLANE|V4L2_CAP_STREAMING;
  hevc=FALSE;
  check_steps(&obj,V4L2_PIX_FMT_NV12M,16,FALSE);
  assert(opens==closes && opens>0 && selections>=8);
  return 0;
}
'''


def main():
    source = Path(sys.argv[1]).read_text()
    start = source.index('    step_w = MAX (size.stepwise.step_width, 1);')
    end = source.index('    w = MAX (size.stepwise.min_width, step_w);', start)
    name = 'gst_v4l2_object_wave5_visible_crop'
    probe = ('static gboolean\n' + function(source, name)) if '\n' + name + ' (' in source else ''
    padding = '\ngboolean\n' + function(source, 'gst_v4l2_object_set_crop')
    padding += '\ngboolean\n' + function(source, 'gst_v4l2_object_setup_padding')
    body = FIXTURE + probe + '\n#undef open\n#undef close\n#undef ioctl\n'
    body += '#define GST_V4L2_CHECK_OPEN(o) ((void)0)\n#undef GST_DEBUG_OBJECT\n#define GST_DEBUG_OBJECT(...) ((void)0)\n#undef GST_WARNING_OBJECT\n#define GST_WARNING_OBJECT(...) ((void)0)\n'
    body += padding + CHECK.replace('STEP_CODE', source[start:end])
    with tempfile.TemporaryDirectory() as temporary:
        cfile, binary = Path(temporary) / 'caps.c', Path(temporary) / 'caps'
        cfile.write_text(body)
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gstreamer-video-1.0'], text=True).split()
        subprocess.run(['cc', '-Wall', '-Wextra', str(cfile), *flags, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Wave5 visible caps, padding and crop negotiation passed')


if __name__ == '__main__':
    main()
