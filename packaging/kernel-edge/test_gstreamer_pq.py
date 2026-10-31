#!/usr/bin/env python3
"""Exercise actual PQ caps probing with retained, rejected and changed tuples."""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()


def function(name, result='void'):
    start = text.index('static ' + result + '\n' + name + ' ')
    return text[start:text.index('\n}', start) + 2]


fixture = r'''
#include <gst/gst.h>
#include <gst/video/video.h>
#include <linux/videodev2.h>
#include <string.h>
typedef struct { enum v4l2_buf_type type; int mode; struct v4l2_capability vcap; GstVideoTransferFunction transfer; } GstV4l2Object;
static int gst_v4l2_object_try_fmt(GstV4l2Object *o, struct v4l2_format *f) {
 int multi=V4L2_TYPE_IS_MULTIPLANAR(o->type);
 unsigned cs=multi?f->fmt.pix_mp.colorspace:f->fmt.pix.colorspace;
 unsigned xf=multi?f->fmt.pix_mp.xfer_func:f->fmt.pix.xfer_func;
 if (!cs) cs=V4L2_COLORSPACE_BT2020;
 if (cs!=V4L2_COLORSPACE_BT2020) return -1;
 if (xf==V4L2_XFER_FUNC_SMPTE2084 && o->mode==2) return -1;
 if (o->mode==0) xf=V4L2_XFER_FUNC_709;
 if(multi) {f->fmt.pix_mp.colorspace=cs; f->fmt.pix_mp.xfer_func=xf;}
 else {f->fmt.pix.colorspace=cs; f->fmt.pix.xfer_func=xf;}
 if (multi) {
  if(o->mode==3)f->fmt.pix_mp.quantization=V4L2_QUANTIZATION_FULL_RANGE;
  if(o->mode==4)f->fmt.pix_mp.ycbcr_enc=V4L2_YCBCR_ENC_709;
  if(o->mode==5)f->fmt.pix_mp.colorspace=V4L2_COLORSPACE_REC709;
 } else {
  if(o->mode==3)f->fmt.pix.quantization=V4L2_QUANTIZATION_FULL_RANGE;
  if(o->mode==4)f->fmt.pix.ycbcr_enc=V4L2_YCBCR_ENC_709;
  if(o->mode==5)f->fmt.pix.colorspace=V4L2_COLORSPACE_REC709;
 }
 return 0;
}
'''
fixture += function('gst_v4l2_object_v4l2fourcc_is_rgb', 'gboolean')
fixture += '\n' + function('gst_v4l2_object_get_colorspace', 'gboolean')
fixture += '\n' + function('gst_v4l2_object_local_transfer', 'GstVideoTransferFunction')
fixture += function('gst_v4l2_object_fill_colorimetry_list')
fixture += '\n' + function('gst_v4l2_object_add_colorspace')
fixture += r'''
int main(void) {
 gst_init(NULL,NULL);
 GstVideoColorimetry pq;
 g_assert_true(gst_video_colorimetry_from_string(&pq,"bt2100-pq"));
 g_assert_cmpint(gst_v4l2_object_local_transfer(pq.transfer),==,GST_VIDEO_TRANSFER_SMPTE2084);
 for(int encoded=0;encoded<2;encoded++)
 for(int multi=0;multi<2;multi++) for(int mode=0;mode<6;mode++) {
  GstV4l2Object o={.type=multi?V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE:V4L2_BUF_TYPE_VIDEO_OUTPUT,.mode=mode};
  if(encoded) {
   o.type=multi?V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE:V4L2_BUF_TYPE_VIDEO_CAPTURE;
   strcpy((char *)o.vcap.driver,"wave5-enc");
  }
  GstStructure *s=gst_structure_new_empty("video/x-raw");
  gst_v4l2_object_add_colorspace(&o,s,3840,2160,
      encoded?V4L2_PIX_FMT_HEVC:V4L2_PIX_FMT_P010);
  const GValue *list=gst_structure_get_value(s,"colorimetry");
  if(encoded) {g_assert_null(list); gst_structure_free(s); continue;}
  gboolean found=FALSE;
  for(unsigned i=0;i<gst_value_list_get_size(list);i++)
   if (!strcmp(g_value_get_string(gst_value_list_get_value(list,i)),"bt2100-pq")) found=TRUE;
  g_assert_cmpint(found,==,mode==1);
  gst_structure_free(s);
 }
}
'''
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
                                            'gstreamer-video-1.0'], text=True))
with tempfile.TemporaryDirectory() as tmp:
    source, binary = Path(tmp) / 'probe.c', Path(tmp) / 'probe'
    source.write_text(fixture)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(source), *flags,
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PQ caps: accepted/rejected/changed transfer, range, matrix, primaries: PASS')
