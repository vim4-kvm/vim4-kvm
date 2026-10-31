#!/usr/bin/env python3
"""Exercise the actual V4L2 caps path that rejected the native HDR source.

No device is opened. Requires the pinned GStreamer source tree, development
libraries and a C compiler. The old patch maps P010 to a video format but
returns NULL before the encoder can expose it as sink caps.
"""
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

from test_gstreamer_orphan import function


def main():
    source = Path(sys.argv[1]).resolve()
    text = source.read_text()
    fixture = r'''
#include <gst/video/video.h>
#include "ext/videodev2.h"
'''
    fixture += '\nstatic GstVideoFormat\n' + function(
        text, 'gst_v4l2_object_v4l2fourcc_to_video_format')
    fixture += '\nstatic GstStructure *\n' + function(
        text, 'gst_v4l2_object_v4l2fourcc_to_bare_struct')
    fixture += r'''
int main(void) {
  gst_init(NULL, NULL);
  GstCaps *source = gst_caps_from_string(
      "video/x-raw,format=P010_10LE,width=3840,height=2160,framerate=60/1");
  GstStructure *structure =
      gst_v4l2_object_v4l2fourcc_to_bare_struct(V4L2_PIX_FMT_P010);
  g_assert_nonnull(structure);
  GstCaps *encoder = gst_caps_new_full(structure, NULL);
  g_assert_true(gst_caps_can_intersect(source, encoder));
  GstCaps *negotiated = gst_caps_intersect(source, encoder);
  GstVideoInfo info;
  g_assert_true(gst_video_info_from_caps(&info, negotiated));
  g_assert_cmpint(GST_VIDEO_INFO_FORMAT(&info), ==, GST_VIDEO_FORMAT_P010_10LE);
  g_assert_cmpint(info.stride[0], ==, 7680);
  g_assert_cmpuint(info.size, ==, 24883200);
  gst_caps_unref(negotiated);
  gst_caps_unref(encoder);
  structure = gst_v4l2_object_v4l2fourcc_to_bare_struct(V4L2_PIX_FMT_NV12);
  g_assert_nonnull(structure);
  encoder = gst_caps_new_full(structure, NULL);
  g_assert_false(gst_caps_can_intersect(source, encoder));
  gst_caps_unref(encoder);
  gst_caps_unref(source);
  /* Private packed 4:2:2 data must never acquire standard raw caps here. */
  g_assert_null(gst_v4l2_object_v4l2fourcc_to_bare_struct(
      v4l2_fourcc('A', 'M', 'L', 'Y')));
  return 0;
}
'''
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'gstreamer-video-1.0'], text=True))
    with tempfile.TemporaryDirectory() as temporary:
        cfile, binary = Path(temporary) / 'caps.c', Path(temporary) / 'caps'
        cfile.write_text(fixture)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-I', str(source.parent),
                        str(cfile), *flags, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Native P010 source intersects actual V4L2 encoder caps: PASS')


if __name__ == '__main__':
    main()
